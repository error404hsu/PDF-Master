import sys
import os
import ast
import copy
import shutil
import logging
from pathlib import Path
from typing import Dict, List, Optional

from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QListView,
    QPushButton,
    QFileDialog,
    QLabel,
    QFrame,
    QAbstractItemView,
    QStyledItemDelegate,
    QStyle,
    QDialog,
    QMessageBox,
    QScrollArea,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QDialogButtonBox,
)
from PySide6.QtCore import (
    Qt,
    QSize,
    QPoint,
    QRect,
    QAbstractListModel,
    QModelIndex,
    QRunnable,
    QThreadPool,
    Slot,
    Signal,
    QObject,
    QMimeData,
)
from PySide6.QtGui import (
    QPixmap,
    QPainter,
    QColor,
    QPen,
    QImage,
    QKeySequence,
    QShortcut,
    QResizeEvent,
    QDragMoveEvent,
    QDropEvent,
    QDragEnterEvent,
    QFont,
)

try:
    from core.models import ExportOptions
    from core.workspace import WorkspaceManager
    from adapters.pymupdf_backend import PyMuPdfBackend
    from core.thumbnail_service import ThumbnailService
    from core.export_service import ExportService
except ImportError as e:
    print(f"匯入核心邏輯失敗，請確保 gui_main.py 放在專案根目錄。錯誤: {e}")
    sys.exit(1)


logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger("gui_main")

PAGE_ROLE = Qt.UserRole
THUMB_STATE_ROLE = Qt.UserRole + 1
THUMB_ERROR_ROLE = Qt.UserRole + 2


class ThumbState:
    IDLE = "idle"
    LOADING = "loading"
    READY = "ready"
    FAILED = "failed"


class UiStyles:
    WINDOW_BG = "#f8fafc"
    HEADER_BG = "#ffffff"
    PANEL_BORDER = "#e2e8f0"
    TEXT_MAIN = "#1e293b"
    TEXT_MUTED = "#64748b"
    TEXT_LIGHT = "#94a3b8"
    PRIMARY = "#3b82f6"
    PRIMARY_HOVER = "#2563eb"
    PRIMARY_SOFT = "#eff6ff"
    CARD_BORDER = "#cbd5e1"
    DANGER = "#f43f5e"
    DANGER_BG = "#fff1f2"
    DANGER_BORDER = "#fecdd3"
    DANGER_HOVER = "#ffe4e6"
    DANGER_HOVER_BORDER = "#fda4af"

    BASE_BUTTON = """
    QPushButton {
        background-color: #f8fafc;
        color: #64748b;
        border: 1px solid #e2e8f0;
        border-radius: 4px;
        font-weight: normal;
        font-size: 10pt;
        padding: 2px 8px;
    }
    QPushButton:hover {
        background-color: #f1f5f9;
        border-color: #cbd5e1;
    }
    QPushButton:pressed {
        background-color: #e2e8f0;
    }
    QPushButton:disabled {
        color: #cbd5e1;
        background-color: #ffffff;
        border-color: #f1f5f9;
    }
    """

    DANGER_BUTTON = """
    QPushButton {
        color: #f43f5e;
        background-color: #fff1f2;
        border: 1px solid #fecdd3;
        border-radius: 4px;
        font-weight: normal;
        font-size: 10pt;
        padding: 2px 8px;
    }
    QPushButton:hover {
        background-color: #ffe4e6;
        border-color: #fda4af;
    }
    QPushButton:disabled {
        color: #fda4af;
        background-color: #fffafa;
        border-color: #ffe4e6;
    }
    """

    PRIMARY_BUTTON = """
    QPushButton {
        background-color: #3b82f6;
        color: white;
        border: none;
        border-radius: 6px;
        font-weight: normal;
        font-size: 10pt;
        padding: 4px 12px;
    }
    QPushButton:hover {
        background-color: #2563eb;
    }
    QPushButton:disabled {
        background-color: #93c5fd;
        color: #eff6ff;
    }
    """

    LIST_VIEW = """
    QListView {
        background-color: #f8fafc;
        border: none;
        padding: 20px 20px 20px 50px;
        outline: none;
    }
    """

    FOOTER = """
    background-color: white;
    border-top: 1px solid #e2e8f0;
    color: #64748b;
    font-size: 10pt;
    padding-left: 20px;
    font-weight: normal;
    """


class WorkerSignals(QObject):
    thumbnail_finished = Signal(str, str, int)
    thumbnail_error = Signal(str, str, int)
    preview_ready = Signal(QImage, str)
    preview_error = Signal(str)


class ThumbnailWorker(QRunnable):
    """Renders off the UI thread; completion applies ``thumb_path`` on the main thread only."""

    def __init__(self, workspace: WorkspaceManager, page, zoom: float):
        super().__init__()
        self.workspace = workspace
        self.page_id = page.page_id
        self.source_path = page.source_path
        self.source_page_index = page.source_page_index
        self.rotation_at_start = page.effective_rotation
        self.zoom = zoom
        self.signals = WorkerSignals()

    @Slot()
    def run(self):
        try:
            path = self.workspace.render_thumbnail_to_disk(
                page_id=self.page_id,
                source_path=self.source_path,
                source_page_index=self.source_page_index,
                final_rotation=self.rotation_at_start,
                zoom=self.zoom,
            )
            self.signals.thumbnail_finished.emit(
                self.page_id, str(path), self.rotation_at_start
            )
        except Exception as e:
            logger.exception("縮圖渲染失敗，page_id=%s", self.page_id)
            self.signals.thumbnail_error.emit(self.page_id, str(e), self.rotation_at_start)


class HighResWorker(QRunnable):
    def __init__(self, backend: PyMuPdfBackend, page_ref, label: str):
        super().__init__()
        self.backend = backend
        self.page_ref = page_ref
        self.label = label
        self.signals = WorkerSignals()

    @Slot()
    def run(self):
        try:
            image_data = self.backend.render_page_to_image(
                self.page_ref.source_path,
                self.page_ref.source_page_index,
                zoom=4.0,
                rotation=self.page_ref.effective_rotation,
            )
            qimg = QImage.fromData(image_data)
            if qimg.isNull():
                self.signals.preview_error.emit("影像解析失敗")
            else:
                self.signals.preview_ready.emit(qimg, self.label)
        except Exception as e:
            logger.exception("高解析預覽渲染失敗")
            self.signals.preview_error.emit(str(e))


class PreviewDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("高品質預覽")
        self.setMinimumSize(800, 900)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setAlignment(Qt.AlignCenter)

        self.image_label = QLabel("正在渲染高品質影像...")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setStyleSheet(
            "color: #94a3b8; font-size: 10pt; font-weight: normal;"
        )

        self.scroll.setWidget(self.image_label)
        layout.addWidget(self.scroll)

        self.setStyleSheet("background-color: #0f172a; color: white; border: none;")
        self.full_pixmap: Optional[QPixmap] = None

    @Slot(QImage, str)
    def update_image(self, qimage: QImage, label: str):
        if not self.isVisible():
            return
        self.setWindowTitle(f"高品質預覽 - {label}")
        self.full_pixmap = QPixmap.fromImage(qimage)
        self._update_display()

    @Slot(str)
    def show_error(self, error_msg: str):
        if self.isVisible():
            self.image_label.setPixmap(QPixmap())
            self.image_label.setText(f"渲染失敗：\n{error_msg}")

    def _update_display(self):
        if not self.full_pixmap:
            return
        view_size = self.scroll.viewport().size()
        scaled = self.full_pixmap.scaled(
            view_size,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        self.image_label.setPixmap(scaled)

    def resizeEvent(self, event: QResizeEvent):
        super().resizeEvent(event)
        self._update_display()


class ExportPdfDialog(QDialog):
    """Office-oriented merge export: metadata source and page labels (see TODO.md for roadmap)."""

    def __init__(self, parent=None, *, export_subset: bool = False):
        super().__init__(parent)
        title = "匯出合併 PDF — 選項"
        if export_subset:
            title = "匯出選取頁面 — 選項"
        self.setWindowTitle(title)
        self.setModal(True)

        outer = QVBoxLayout(self)
        outer.setSpacing(12)

        hint = QLabel(
            "書籤、附件與互動表單的保留方式將在後續版本提供（詳見專案根目錄 TODO.md）。"
        )
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color: {UiStyles.TEXT_MUTED}; font-size: 9pt;")
        outer.addWidget(hint)

        form = QFormLayout()
        self._chk_metadata = QCheckBox("寫入文件資訊（標題、作者等）")
        self._chk_metadata.setChecked(True)
        self._chk_labels = QCheckBox("依目前頁序產生頁碼標籤（Page labels）")
        self._chk_labels.setChecked(True)

        self._policy_combo = QComboBox()
        self._policy_combo.addItem("沿用順序第一份來源的內容資訊", "first_pdf")
        self._policy_combo.addItem("沿用順序最末份來源的內容資訊", "last_pdf")
        self._policy_combo.addItem("清空內容欄位（空白 metadata）", "empty")
        self._policy_combo.setCurrentIndex(0)

        form.addRow(self._chk_metadata)
        form.addRow("內容資訊來源：", self._policy_combo)
        form.addRow(self._chk_labels)
        outer.addLayout(form)

        self._chk_metadata.toggled.connect(self._sync_policy_enabled)
        self._sync_policy_enabled(self._chk_metadata.isChecked())

        bbox = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        bbox.accepted.connect(self.accept)
        bbox.rejected.connect(self.reject)
        outer.addWidget(bbox)

    def _sync_policy_enabled(self, on: bool) -> None:
        self._policy_combo.setEnabled(on)

    def export_options(self) -> ExportOptions:
        policy = self._policy_combo.currentData()
        if not isinstance(policy, str):
            policy = "first_pdf"
        return ExportOptions(
            keep_metadata=self._chk_metadata.isChecked(),
            keep_page_labels=self._chk_labels.isChecked(),
            metadata_policy=policy,  # type: ignore[arg-type]
        )


class SnapshotHistory:
    def __init__(self, max_entries: int = 20):
        self.max_entries = max_entries
        self.undo_stack: List[list] = []
        self.redo_stack: List[list] = []

    def clear(self):
        self.undo_stack.clear()
        self.redo_stack.clear()

    def push_snapshot(self, snapshot: list):
        self.undo_stack.append(snapshot)
        if len(self.undo_stack) > self.max_entries:
            self.undo_stack.pop(0)
        self.redo_stack.clear()

    def can_undo(self) -> bool:
        return bool(self.undo_stack)

    def can_redo(self) -> bool:
        return bool(self.redo_stack)

    def undo(self, current_pages: list) -> Optional[list]:
        if not self.undo_stack:
            return None
        self.redo_stack.append(copy.deepcopy(current_pages))
        return self.undo_stack.pop()

    def redo(self, current_pages: list) -> Optional[list]:
        if not self.redo_stack:
            return None
        self.undo_stack.append(copy.deepcopy(current_pages))
        return self.redo_stack.pop()


class PdfPageModel(QAbstractListModel):
    def __init__(self, workspace: WorkspaceManager, thumb_service: ThumbnailService):
        super().__init__()
        self.workspace = workspace
        self.thumb_service = thumb_service
        self.thread_pool = QThreadPool.globalInstance()
        self._thumb_cache: Dict[int, QPixmap] = {}
        self._rendering_page_ids: set[str] = set()
        self._failed_page_ids: Dict[str, str] = {}

    def rowCount(self, parent=QModelIndex()):
        return len(self.workspace.pages)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None

        row = index.row()
        if row < 0 or row >= len(self.workspace.pages):
            return None

        page = self.workspace.pages[row]

        if role == PAGE_ROLE:
            return page

        if role == THUMB_STATE_ROLE:
            if page.page_id in self._failed_page_ids:
                return ThumbState.FAILED
            if page.page_id in self._rendering_page_ids:
                return ThumbState.LOADING
            if row in self._thumb_cache:
                return ThumbState.READY
            if page.thumb_path and page.thumb_path.exists():
                return ThumbState.READY
            return ThumbState.IDLE

        if role == THUMB_ERROR_ROLE:
            return self._failed_page_ids.get(page.page_id)

        if role == Qt.DecorationRole:
            return self._get_thumbnail(row, page)

        return None

    def _get_thumbnail(self, row: int, page):
        if row in self._thumb_cache:
            return self._thumb_cache[row]

        if page.thumb_path and page.thumb_path.exists():
            pixmap = QPixmap(str(page.thumb_path))
            if not pixmap.isNull():
                self._thumb_cache[row] = pixmap
                return pixmap

        if (
            page.page_id not in self._rendering_page_ids
            and page.page_id not in self._failed_page_ids
        ):
            self.start_thumbnail_worker(row)

        return None

    def _row_for_page_id(self, page_id: str) -> int | None:
        for i, p in enumerate(self.workspace.pages):
            if p.page_id == page_id:
                return i
        return None

    def start_thumbnail_worker(self, row: int):
        if row < 0 or row >= len(self.workspace.pages):
            return
        page = self.workspace.pages[row]
        if page.page_id in self._rendering_page_ids:
            return

        self._rendering_page_ids.add(page.page_id)
        worker = ThumbnailWorker(
            self.workspace, page, ThumbnailService.DEFAULT_ZOOM
        )
        worker.signals.thumbnail_finished.connect(self._on_thumb_ready)
        worker.signals.thumbnail_error.connect(self._on_thumb_error)
        self.thread_pool.start(worker)

    @Slot(str, str, int)
    def _on_thumb_ready(self, page_id: str, path_str: str, rotation_at_start: int):
        self._rendering_page_ids.discard(page_id)
        self._failed_page_ids.pop(page_id, None)
        row = self._row_for_page_id(page_id)
        if row is None:
            return

        page = self.workspace.pages[row]
        path = Path(path_str)
        if page.effective_rotation != rotation_at_start:
            path.unlink(missing_ok=True)
        else:
            page.thumb_path = path

        self._thumb_cache.pop(row, None)

        idx = self.index(row)
        if idx.isValid():
            self.dataChanged.emit(
                idx,
                idx,
                [Qt.DecorationRole, THUMB_STATE_ROLE, THUMB_ERROR_ROLE, PAGE_ROLE],
            )

    @Slot(str, str, int)
    def _on_thumb_error(self, page_id: str, error_msg: str, rotation_at_start: int):
        self._rendering_page_ids.discard(page_id)
        row = self._row_for_page_id(page_id)
        if row is None:
            return

        page = self.workspace.pages[row]
        if page.effective_rotation != rotation_at_start:
            idx = self.index(row)
            if idx.isValid():
                self.dataChanged.emit(
                    idx,
                    idx,
                    [Qt.DecorationRole, THUMB_STATE_ROLE, THUMB_ERROR_ROLE],
                )
            return

        self._failed_page_ids[page_id] = error_msg

        idx = self.index(row)
        if idx.isValid():
            self.dataChanged.emit(
                idx,
                idx,
                [Qt.DecorationRole, THUMB_STATE_ROLE, THUMB_ERROR_ROLE],
            )

    def clear_thumbnail_state(self, rows: Optional[List[int]] = None):
        if rows is None:
            self._thumb_cache.clear()
            self._rendering_page_ids.clear()
            self._failed_page_ids.clear()
            return

        for row in rows:
            if 0 <= row < len(self.workspace.pages):
                pid = self.workspace.pages[row].page_id
                self._rendering_page_ids.discard(pid)
                self._failed_page_ids.pop(pid, None)
            self._thumb_cache.pop(row, None)

    def invalidate_rows(self, rows: List[int]):
        if not rows:
            return

        unique_rows = sorted(set(rows))
        self.clear_thumbnail_state(unique_rows)

        for row in unique_rows:
            idx = self.index(row)
            if idx.isValid():
                self.dataChanged.emit(
                    idx,
                    idx,
                    [Qt.DecorationRole, THUMB_STATE_ROLE, THUMB_ERROR_ROLE, PAGE_ROLE],
                )

    def refresh_all(self):
        self.beginResetModel()
        self.clear_thumbnail_state()
        self.endResetModel()

    def flags(self, index):
        base = Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsDropEnabled
        if not index.isValid():
            return base
        return base | Qt.ItemIsDragEnabled

    def mimeTypes(self):
        return ["application/x-pagemove"]

    def mimeData(self, indexes):
        mime_data = QMimeData()
        rows = sorted({index.row() for index in indexes if index.isValid()})
        mime_data.setData("application/x-pagemove", str(rows).encode())
        return mime_data


class PageCardDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        page = index.data(PAGE_ROLE)
        pixmap = index.data(Qt.DecorationRole)
        thumb_state = index.data(THUMB_STATE_ROLE)
        thumb_error = index.data(THUMB_ERROR_ROLE)

        if not page:
            return

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        rect = option.rect.adjusted(6, 6, -6, -6)
        thumb_area = rect.adjusted(10, 10, -10, -50)
        is_selected = bool(option.state & QStyle.State_Selected)

        if is_selected:
            painter.setPen(QPen(QColor(UiStyles.PRIMARY), 3))
            painter.setBrush(QColor(UiStyles.PRIMARY_SOFT))
        else:
            painter.setPen(QPen(QColor(UiStyles.CARD_BORDER), 1))
            painter.setBrush(Qt.white)

        painter.drawRoundedRect(rect, 8, 8)

        if pixmap and not pixmap.isNull():
            scaled = pixmap.scaled(
                thumb_area.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
            x = thumb_area.x() + (thumb_area.width() - scaled.width()) // 2
            y = thumb_area.y() + (thumb_area.height() - scaled.height()) // 2
            painter.drawPixmap(x, y, scaled)
        else:
            placeholder_rect = thumb_area.adjusted(8, 8, -8, -8)
            painter.setPen(QPen(QColor("#dbeafe"), 1))
            painter.setBrush(QColor("#f8fbff"))
            painter.drawRoundedRect(placeholder_rect, 6, 6)

            painter.setPen(QColor(UiStyles.TEXT_LIGHT))
            status_text = "載入中..."
            if thumb_state == ThumbState.FAILED:
                status_text = "縮圖失敗"
            painter.drawText(placeholder_rect, Qt.AlignCenter, status_text)

        painter.setPen(QColor(UiStyles.TEXT_MUTED))
        font = painter.font()
        font.setBold(False)
        font.setPointSize(10)
        painter.setFont(font)
        painter.drawText(
            rect.adjusted(0, rect.height() - 45, 0, -22),
            Qt.AlignCenter,
            f"第 {index.row() + 1} 頁",
        )

        font.setPointSize(9)
        painter.setFont(font)
        info = f"{page.source_page_label} | {page.effective_rotation}°"
        if thumb_state == ThumbState.FAILED and thumb_error:
            info = f"{info} | 縮圖失敗"
        painter.drawText(
            rect.adjusted(5, rect.height() - 22, -5, -5),
            Qt.AlignCenter | Qt.TextSingleLine,
            info,
        )

        painter.restore()

    def sizeHint(self, option, index):
        return QSize(200, 280)


class PageListView(QListView):
    pages_reordered = Signal(list, int)
    pdf_files_dropped = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setViewMode(QListView.ListMode)
        self.setFlow(QListView.LeftToRight)
        self.setWrapping(True)
        self.setResizeMode(QListView.Adjust)
        self.setSpacing(20)
        self.setGridSize(QSize(210, 290))
        self.setMovement(QListView.Static)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(False)
        self.setDragDropMode(QAbstractItemView.DragDrop)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setSelectionRectVisible(True)

        self._drop_index = -1
        self._drop_rect = QRect()

    def _reset_drop_indicator(self):
        self._drop_index = -1
        self._drop_rect = QRect()
        self.viewport().update()

    def _get_target_drop_info(self, pos: QPoint):
        model = self.model()
        if model is None:
            return -1, QRect()

        count = model.rowCount()
        if count == 0:
            return 0, QRect(15, 15, 6, 280)

        index = self.indexAt(pos)
        first_idx = model.index(0, 0)
        last_idx = model.index(count - 1, 0)

        first_rect = self.visualRect(first_idx)
        last_rect = self.visualRect(last_idx)

        if (
            pos.x() < (first_rect.left() + first_rect.width() // 2)
            and pos.y() < (first_rect.bottom() + 10)
        ):
            return 0, QRect(
                first_rect.left() - 15,
                first_rect.top() + 6,
                6,
                first_rect.height() - 12,
            )

        if not index.isValid():
            if pos.y() > last_rect.bottom() or (
                pos.x() > last_rect.right() and pos.y() > last_rect.top()
            ):
                return count, QRect(
                    last_rect.right() + 6,
                    last_rect.top() + 6,
                    6,
                    last_rect.height() - 12,
                )
            return -1, QRect()

        rect = self.visualRect(index)
        if pos.x() < rect.center().x():
            return index.row(), QRect(
                rect.left() - 12,
                rect.top() + 6,
                6,
                rect.height() - 12,
            )

        return index.row() + 1, QRect(
            rect.right() + 4,
            rect.top() + 6,
            6,
            rect.height() - 12,
        )

    def dragEnterEvent(self, event: QDragEnterEvent):
        mime = event.mimeData()
        if mime.hasFormat("application/x-pagemove") or mime.hasUrls():
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event: QDragMoveEvent):
        mime = event.mimeData()

        if mime.hasUrls():
            event.acceptProposedAction()
            return

        if mime.hasFormat("application/x-pagemove"):
            idx, rect = self._get_target_drop_info(event.position().toPoint())
            self._drop_index = idx
            self._drop_rect = rect
            event.acceptProposedAction()
            self.viewport().update()
            return

        super().dragMoveEvent(event)

    def dragLeaveEvent(self, event):
        self._reset_drop_indicator()
        super().dragLeaveEvent(event)

    def dropEvent(self, event: QDropEvent):
        mime = event.mimeData()

        if mime.hasUrls():
            files = [
                url.toLocalFile()
                for url in mime.urls()
                if url.toLocalFile().lower().endswith(".pdf")
            ]
            if files:
                self.pdf_files_dropped.emit(files)
                event.acceptProposedAction()
            else:
                event.ignore()
            self._reset_drop_indicator()
            return

        if mime.hasFormat("application/x-pagemove"):
            target = self._drop_index
            if target != -1:
                try:
                    raw_data = mime.data("application/x-pagemove")
                    source_rows = ast.literal_eval(bytes(raw_data).decode())
                    if isinstance(source_rows, list) and source_rows:
                        self.pages_reordered.emit(source_rows, target)
                        event.acceptProposedAction()
                    else:
                        event.ignore()
                except Exception as e:
                    logger.exception("頁面拖放解析失敗")
                    QMessageBox.critical(self, "移動失敗", str(e))
                    event.ignore()
            else:
                event.ignore()

            self._reset_drop_indicator()
            return

        super().dropEvent(event)

    def paintEvent(self, event):
        super().paintEvent(event)

        if self._drop_index == -1 or self._drop_rect.isNull():
            return

        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QColor(UiStyles.PRIMARY))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(self._drop_rect, 3, 3)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PDF排列哥 Pro")
        self.resize(1300, 800)
        self.setAcceptDrops(True)

        self.thumb_path = Path("./.thumbnails")
        self.thumb_path.mkdir(exist_ok=True)

        self.backend = PyMuPdfBackend()
        self.workspace = WorkspaceManager(self.backend, self.thumb_path)
        self.thumb_service = ThumbnailService(self.workspace)
        self.export_service = ExportService(self.workspace)

        self.thread_pool = QThreadPool.globalInstance()
        self.history = SnapshotHistory(max_entries=20)

        self._build_ui()
        self._connect_signals()
        self._setup_shortcuts()
        self._update_history_buttons()
        self.update_status()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        header = self._build_header()
        main_layout.addWidget(header)

        self.model = PdfPageModel(self.workspace, self.thumb_service)
        self.view = PageListView()
        self.view.setModel(self.model)
        self.view.setItemDelegate(PageCardDelegate())
        self.view.setStyleSheet(UiStyles.LIST_VIEW)
        main_layout.addWidget(self.view)

        self.footer = QLabel(
            " 辦公室合併：可批次加入資料夾內 PDF | Ctrl+A 全選 | Del 刪除 | "
            "Ctrl+Shift+E 匯出選取 | 雙擊預覽 | 拖曳排序"
        )
        self.footer.setFixedHeight(32)
        self.footer.setStyleSheet(UiStyles.FOOTER)
        main_layout.addWidget(self.footer)

    def _build_header(self):
        header = QFrame()
        header.setFixedHeight(62)
        header.setStyleSheet(
            f"background-color: {UiStyles.HEADER_BG}; "
            f"border-bottom: 1px solid {UiStyles.PANEL_BORDER};"
        )

        layout = QHBoxLayout(header)
        layout.setContentsMargins(15, 0, 15, 0)
        layout.setSpacing(10)

        title_label = QLabel("PDF排列哥")
        title_label.setStyleSheet(
            "font-weight: 900; font-size: 24pt; color: #1e40af; min-width: 160px;"
        )
        layout.addWidget(title_label)

        btn_w, btn_h = 88, 32

        self.btn_add = self._make_button("開啟檔案", btn_w, btn_h)
        self.btn_add_folder = self._make_button("開啟資料夾", 96, btn_h)
        layout.addWidget(self.btn_add)
        layout.addWidget(self.btn_add_folder)
        layout.addWidget(self._make_separator())

        self.btn_undo = self._make_button("復原", btn_w, btn_h)
        self.btn_redo = self._make_button("重做", btn_w, btn_h)
        layout.addWidget(self.btn_undo)
        layout.addWidget(self.btn_redo)
        layout.addWidget(self._make_separator())

        self.btn_rot_l = self._make_button("左轉 90°", btn_w, btn_h)
        self.btn_rot_180 = self._make_button("轉 180°", btn_w, btn_h)
        self.btn_rot_r = self._make_button("右轉 90°", btn_w, btn_h)
        self.btn_delete = self._make_button("刪除頁面", btn_w, btn_h, variant="danger")

        layout.addWidget(self.btn_rot_l)
        layout.addWidget(self.btn_rot_180)
        layout.addWidget(self.btn_rot_r)
        layout.addWidget(self.btn_delete)

        layout.addStretch()

        self.btn_export_sel = self._make_button("匯出選取", 96, 38)
        self.btn_export = self._make_button("匯出結果", 100, 38, variant="primary")
        layout.addWidget(self.btn_export_sel)
        layout.addWidget(self.btn_export)

        return header

    def _make_button(self, text: str, width: int, height: int, variant: str = "base"):
        btn = QPushButton(text)
        btn.setFixedSize(width, height)

        if variant == "danger":
            btn.setStyleSheet(UiStyles.DANGER_BUTTON)
        elif variant == "primary":
            btn.setStyleSheet(UiStyles.PRIMARY_BUTTON)
        else:
            btn.setStyleSheet(UiStyles.BASE_BUTTON)

        return btn

    def _make_separator(self):
        line = QFrame()
        line.setFrameShape(QFrame.VLine)
        line.setFixedHeight(24)
        line.setStyleSheet(f"color: {UiStyles.PANEL_BORDER};")
        return line

    def _connect_signals(self):
        self.btn_add.clicked.connect(self.on_add_pdf)
        self.btn_add_folder.clicked.connect(self.on_add_folder)
        self.btn_undo.clicked.connect(self.undo)
        self.btn_redo.clicked.connect(self.redo)
        self.btn_rot_l.clicked.connect(lambda: self.on_rotate_pages(-90))
        self.btn_rot_180.clicked.connect(lambda: self.on_rotate_pages(180))
        self.btn_rot_r.clicked.connect(lambda: self.on_rotate_pages(90))
        self.btn_delete.clicked.connect(self.on_delete_pages)
        self.btn_export_sel.clicked.connect(self.on_export_selected_pdf)
        self.btn_export.clicked.connect(self.on_export_pdf)

        self.view.doubleClicked.connect(self.on_page_double_clicked)
        self.view.pages_reordered.connect(self.on_pages_reordered)
        self.view.pdf_files_dropped.connect(self.load_pdfs)

        selection_model = self.view.selectionModel()
        if selection_model is not None:
            selection_model.selectionChanged.connect(self.update_status)

    def _setup_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+Z"), self, activated=self.undo)
        QShortcut(QKeySequence("Ctrl+Y"), self, activated=self.redo)
        QShortcut(
            QKeySequence(QKeySequence.StandardKey.SelectAll),
            self.view,
            activated=self.view.selectAll,
        )
        QShortcut(
            QKeySequence(QKeySequence.StandardKey.Delete),
            self.view,
            activated=self.on_delete_pages,
        )
        QShortcut(
            QKeySequence("Ctrl+Shift+E"),
            self,
            activated=self.on_export_selected_pdf,
        )

    def _selected_rows(self) -> List[int]:
        selection_model = self.view.selectionModel()
        if selection_model is None:
            return []
        return sorted({idx.row() for idx in selection_model.selectedIndexes() if idx.isValid()})

    def _capture_before_change(self):
        return copy.deepcopy(self.workspace.pages)

    def _commit_history(self, before_snapshot: list):
        self.history.push_snapshot(before_snapshot)
        self._update_history_buttons()

    def _restore_pages(self, restored_pages: Optional[list]):
        if restored_pages is None:
            return
        self.workspace.pages = restored_pages
        self.model.refresh_all()
        self.update_status()
        self._update_history_buttons()

    def _update_history_buttons(self):
        self.btn_undo.setEnabled(self.history.can_undo())
        self.btn_redo.setEnabled(self.history.can_redo())

    def _update_action_buttons(self):
        has_pages = self.model.rowCount() > 0
        has_selection = bool(self._selected_rows())

        self.btn_rot_l.setEnabled(has_selection)
        self.btn_rot_180.setEnabled(has_selection)
        self.btn_rot_r.setEnabled(has_selection)
        self.btn_delete.setEnabled(has_selection)
        self.btn_export_sel.setEnabled(has_selection)
        self.btn_export.setEnabled(has_pages)

    def _show_error(self, title: str, error: Exception | str):
        QMessageBox.critical(self, title, str(error))

    def update_status(self, *args):
        total = self.model.rowCount()
        selected = len(self._selected_rows())
        self.footer.setText(f" 總計 {total} 頁 | 已選取 {selected} 頁")
        self._update_action_buttons()

    def load_pdfs(self, files: List[str]):
        files = [f for f in files if f.lower().endswith(".pdf")]
        if not files:
            return

        before = self._capture_before_change()
        try:
            self.workspace.open_pdfs(files)
        except Exception as e:
            self._show_error("開啟 PDF 失敗", e)
            return

        self._commit_history(before)
        self.model.refresh_all()
        self.update_status()

    def on_add_pdf(self):
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "開啟 PDF",
            "",
            "PDF 檔案 (*.pdf)",
        )
        if files:
            self.load_pdfs(files)

    def on_add_folder(self):
        directory = QFileDialog.getExistingDirectory(self, "選擇含 PDF 的資料夾", "")
        if not directory:
            return
        root = Path(directory)
        files = sorted(
            str(p) for p in root.iterdir() if p.is_file() and p.suffix.lower() == ".pdf"
        )
        if not files:
            QMessageBox.information(
                self,
                "開啟資料夾",
                "此資料夾內沒有找到 PDF 檔案（僅掃描一層目錄，不含子資料夾）。",
            )
            return
        self.load_pdfs(files)

    def on_pages_reordered(self, source_rows: List[int], target: int):
        if not source_rows:
            return

        before = self._capture_before_change()
        try:
            self.workspace.move_pages(source_rows, target)
        except Exception as e:
            self._show_error("移動頁面失敗", e)
            return

        self._commit_history(before)
        self.model.refresh_all()
        self.update_status()

    def on_page_double_clicked(self, index: QModelIndex):
        page = index.data(PAGE_ROLE)
        if page is None:
            return

        dialog = PreviewDialog(self)
        worker = HighResWorker(self.backend, page, f"第 {index.row() + 1} 頁")
        worker.signals.preview_ready.connect(dialog.update_image)
        worker.signals.preview_error.connect(dialog.show_error)
        self.thread_pool.start(worker)
        dialog.exec()

    def on_rotate_pages(self, angle: int):
        rows = self._selected_rows()
        if not rows:
            return

        before = self._capture_before_change()
        try:
            self.workspace.rotate_pages(rows, angle)
        except Exception as e:
            self._show_error("旋轉頁面失敗", e)
            return

        self._commit_history(before)
        self.model.invalidate_rows(rows)

        for row in rows:
            self.model.start_thumbnail_worker(row)

        self.update_status()

    def on_delete_pages(self):
        rows = self._selected_rows()
        if not rows:
            return

        before = self._capture_before_change()
        try:
            self.workspace.remove_pages(rows)
        except Exception as e:
            self._show_error("刪除頁面失敗", e)
            return

        self._commit_history(before)
        self.model.refresh_all()
        self.update_status()

    def _confirm_encrypted_sources(self, page_indices: Optional[List[int]]) -> bool:
        enc = self.workspace.encrypted_used_sources(page_indices)
        if not enc:
            return True
        names = "\n".join(f"• {s.path.name}" for s in enc)
        answer = QMessageBox.warning(
            self,
            "偵測到加密或需密碼的來源",
            "下列來源在編目時標示為加密文件。若未事先以密碼解鎖，合併結果可能不完整或匯出失敗：\n\n"
            f"{names}\n\n仍要繼續匯出？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes

    def on_export_pdf(self):
        if not self.workspace.pages:
            return

        dlg = ExportPdfDialog(self, export_subset=False)
        if dlg.exec() != QDialog.Accepted:
            return
        options = dlg.export_options()

        path, _ = QFileDialog.getSaveFileName(
            self,
            "匯出 PDF",
            "合併結果.pdf",
            "PDF 檔案 (*.pdf)",
        )
        if not path:
            return

        if not self._confirm_encrypted_sources(None):
            return

        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            self.export_service.export(path, options)
            QMessageBox.information(self, "成功", f"匯出成功至：\n{path}")
        except Exception as e:
            self._show_error("匯出失敗", e)
        finally:
            QApplication.restoreOverrideCursor()

    def on_export_selected_pdf(self):
        rows = self._selected_rows()
        if not rows:
            QMessageBox.information(
                self,
                "匯出選取",
                "請先在縮圖區選取至少一頁，再使用「匯出選取」或 Ctrl+Shift+E。",
            )
            return

        dlg = ExportPdfDialog(self, export_subset=True)
        if dlg.exec() != QDialog.Accepted:
            return
        options = dlg.export_options()

        path, _ = QFileDialog.getSaveFileName(
            self,
            "匯出選取的頁面",
            "選取頁面.pdf",
            "PDF 檔案 (*.pdf)",
        )
        if not path:
            return

        if not self._confirm_encrypted_sources(rows):
            return

        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            self.export_service.export_selected(rows, path, options)
            QMessageBox.information(self, "成功", f"已匯出 {len(rows)} 頁至：\n{path}")
        except Exception as e:
            self._show_error("匯出失敗", e)
        finally:
            QApplication.restoreOverrideCursor()

    def undo(self):
        restored_pages = self.history.undo(self.workspace.pages)
        self._restore_pages(restored_pages)

    def redo(self):
        restored_pages = self.history.redo(self.workspace.pages)
        self._restore_pages(restored_pages)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dropEvent(self, event: QDropEvent):
        if event.mimeData().hasUrls():
            files = [
                url.toLocalFile()
                for url in event.mimeData().urls()
                if url.toLocalFile().lower().endswith(".pdf")
            ]
            if files:
                self.load_pdfs(files)
                event.acceptProposedAction()
            else:
                event.ignore()
            return

        super().dropEvent(event)

    def closeEvent(self, event):
        try:
            if self.thumb_path.exists():
                shutil.rmtree(self.thumb_path, ignore_errors=True)
        except Exception:
            logger.exception("清除縮圖目錄失敗")
        event.accept()


def main():
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    default_font = QFont("Microsoft JhengHei", 10)
    default_font.setStyleStrategy(QFont.PreferAntialias)
    app.setFont(default_font)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
# 視圖元件模組 — PageCardDelegate（縮圖繪製）與 PageListView（拖放清單）
import ast
import logging

from PySide6.QtWidgets import (
    QListView,
    QStyledItemDelegate,
    QStyle,
    QAbstractItemView,
    QMessageBox,
    QMenu,
)
from PySide6.QtCore import (
    Qt,
    QSize,
    QPoint,
    QRect,
    Signal,
    QMimeData,
)
from PySide6.QtGui import (
    QPainter,
    QColor,
    QPen,
    QDragMoveEvent,
    QDropEvent,
    QDragEnterEvent,
)

from gui.models import PAGE_ROLE, THUMB_STATE_ROLE, THUMB_ERROR_ROLE, ThumbState
from gui.styles import UiStyles, SOURCE_COLORS

logger = logging.getLogger("gui.views")

# 全域來源 PDF → 色帶顏色對應表
_source_color_cache: dict[str, str] = {}


def _get_source_color(source_pdf: str) -> str:
    """依來源 PDF 路徑分配固定顏色（最多 12 色循環）。"""
    if source_pdf not in _source_color_cache:
        idx = len(_source_color_cache) % len(SOURCE_COLORS)
        _source_color_cache[source_pdf] = SOURCE_COLORS[idx]
    return _source_color_cache[source_pdf]


def clear_source_colors() -> None:
    """清除色帶對應表（重新載入 PDF 時呼叫）。"""
    _source_color_cache.clear()


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
        thumb_area = rect.adjusted(10, 14, -10, -50)  # 上移 4px 為色帶留空間
        is_selected = bool(option.state & QStyle.State_Selected)

        if is_selected:
            painter.setPen(QPen(QColor(UiStyles.PRIMARY), 3))
            painter.setBrush(QColor(UiStyles.PRIMARY_SOFT))
        else:
            painter.setPen(QPen(QColor(UiStyles.CARD_BORDER), 1))
            painter.setBrush(Qt.white)

        painter.drawRoundedRect(rect, 8, 8)

        # ── 來源色帶（頂部 5px）──────────────────────────────────
        source_pdf = getattr(page, "source_pdf", "") or ""
        if source_pdf:
            band_color = _get_source_color(source_pdf)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(band_color))
            band_rect = QRect(rect.x() + 1, rect.y() + 1, rect.width() - 2, 5)
            painter.drawRoundedRect(band_rect, 3, 3)

        # ── 縮圖區域 ─────────────────────────────────────────────
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

            if thumb_state == ThumbState.FAILED:
                painter.setPen(QPen(QColor("#fca5a5"), 1))
                painter.setBrush(QColor("#fff1f2"))
                painter.drawRoundedRect(placeholder_rect, 6, 6)

                painter.setPen(QColor("#dc2626"))
                font = painter.font()
                font.setBold(True)
                font.setPointSize(9)
                painter.setFont(font)
                painter.drawText(placeholder_rect, Qt.AlignCenter, "⚠ 縮圖失敗")
            else:
                painter.setPen(QPen(QColor("#dbeafe"), 1))
                painter.setBrush(QColor("#f8fbff"))
                painter.drawRoundedRect(placeholder_rect, 6, 6)

                painter.setPen(QColor(UiStyles.TEXT_LIGHT))
                font = painter.font()
                font.setBold(False)
                font.setPointSize(10)
                painter.setFont(font)
                painter.drawText(placeholder_rect, Qt.AlignCenter, "載入中...")

        # ── 頁碼標示 ──────────────────────────────────────────────
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
        if thumb_state == ThumbState.FAILED:
            painter.setPen(QColor("#dc2626"))
            if thumb_error:
                short_err = thumb_error[:30] + "..." if len(thumb_error) > 30 else thumb_error
                info = f"{info} | {short_err}"
            else:
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
    # 右鍵選單動作信號
    context_rotate_left = Signal()
    context_rotate_180 = Signal()
    context_rotate_right = Signal()
    context_delete = Signal()
    context_export_selected = Signal()

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

        # 啟用右鍵選單
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

        self._drop_index = -1
        self._drop_rect = QRect()

    def _show_context_menu(self, pos: QPoint) -> None:
        """顯示右鍵情境選單。"""
        # 若點擊位置無頁面，直接返回
        index = self.indexAt(pos)
        if not index.isValid():
            return

        has_selection = bool(self.selectionModel().selectedIndexes())
        if not has_selection:
            return

        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 6px;
                padding: 4px;
                font-size: 10pt;
            }
            QMenu::item {
                padding: 6px 24px;
                border-radius: 4px;
                color: #1e293b;
            }
            QMenu::item:selected {
                background-color: #eff6ff;
                color: #1e40af;
            }
            QMenu::separator {
                height: 1px;
                background-color: #e2e8f0;
                margin: 4px 8px;
            }
        """)

        act_rot_l = menu.addAction("↺  左轉 90°")
        act_rot_180 = menu.addAction("↕  轉 180°")
        act_rot_r = menu.addAction("↻  右轉 90°")
        menu.addSeparator()
        act_delete = menu.addAction("🗑  刪除頁面")
        act_delete.setEnabled(has_selection)
        menu.addSeparator()
        act_export_sel = menu.addAction("💾  匯出選取頁面")

        for act in (act_rot_l, act_rot_180, act_rot_r):
            act.setEnabled(has_selection)

        chosen = menu.exec(self.viewport().mapToGlobal(pos))
        if chosen == act_rot_l:
            self.context_rotate_left.emit()
        elif chosen == act_rot_180:
            self.context_rotate_180.emit()
        elif chosen == act_rot_r:
            self.context_rotate_right.emit()
        elif chosen == act_delete:
            self.context_delete.emit()
        elif chosen == act_export_sel:
            self.context_export_selected.emit()

    # ── 拖放輔助 ──────────────────────────────────────────────────

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

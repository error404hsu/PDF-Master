# 視圖元件模組 — PageCardDelegate（縮圖繪製）與 PageListView（拖放清單）
import ast
import logging

from PySide6.QtWidgets import (
    QListView,
    QStyledItemDelegate,
    QStyle,
    QAbstractItemView,
    QMessageBox,
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
from gui.styles import UiStyles

logger = logging.getLogger("gui.views")


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

            if thumb_state == ThumbState.FAILED:
                # 失敗狀態：紅色邊框 + 警告背景
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
                # 載入中：淡藍色佔位
                painter.setPen(QPen(QColor("#dbeafe"), 1))
                painter.setBrush(QColor("#f8fbff"))
                painter.drawRoundedRect(placeholder_rect, 6, 6)

                painter.setPen(QColor(UiStyles.TEXT_LIGHT))
                font = painter.font()
                font.setBold(False)
                font.setPointSize(10)
                painter.setFont(font)
                painter.drawText(placeholder_rect, Qt.AlignCenter, "載入中...")

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
            # 失敗時底部資訊也用紅色提示
            painter.setPen(QColor("#dc2626"))
            if thumb_error:
                # 擷取錯誤訊息前 30 字，避免卡片版面溢出
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

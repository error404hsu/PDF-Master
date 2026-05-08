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
)
from PySide6.QtGui import (
    QPainter,
    QColor,
    QPen,
    QPolygon,
    QBrush,
    QDragMoveEvent,
    QDropEvent,
    QDragEnterEvent,
)

from gui.models import PAGE_ROLE, THUMB_STATE_ROLE, THUMB_ERROR_ROLE, ThumbState
from gui.styles import UiStyles, SOURCE_COLORS

logger = logging.getLogger("gui.views")

_source_color_cache: dict[str, str] = {}

_LINE_COLOR = "#3b82f6"
_LINE_WIDTH = 2
_DIAMOND_R = 5
_INDICATOR_PADDING = 4  # 插入線距卡片上下邊緣的縮排 px

_HOVER_BORDER_COLOR = "#60a5fa"
_HOVER_FILL_COLOR = "#dbeafe"

_AUTO_SCROLL_MARGIN = 36
_AUTO_SCROLL_STEP = 28


def _get_source_color(source_pdf: str) -> str:
    if source_pdf not in _source_color_cache:
        idx = len(_source_color_cache) % len(SOURCE_COLORS)
        _source_color_cache[source_pdf] = SOURCE_COLORS[idx]
    return _source_color_cache[source_pdf]


def clear_source_colors() -> None:
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
        thumb_area = rect.adjusted(10, 14, -10, -50)
        is_selected = bool(option.state & QStyle.State_Selected)

        if is_selected:
            painter.setPen(QPen(QColor(UiStyles.PRIMARY), 3))
            painter.setBrush(QColor(UiStyles.PRIMARY_SOFT))
        else:
            painter.setPen(QPen(QColor(UiStyles.CARD_BORDER), 1))
            painter.setBrush(Qt.white)

        painter.drawRoundedRect(rect, 8, 8)

        source_pdf = getattr(page, "source_pdf", "") or ""
        if source_pdf:
            band_color = _get_source_color(source_pdf)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(band_color))
            band_rect = QRect(rect.x() + 1, rect.y() + 1, rect.width() - 2, 5)
            painter.drawRoundedRect(band_rect, 3, 3)

        if pixmap and not pixmap.isNull():
            scaled = pixmap.scaled(
                thumb_area.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation,
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
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

        self._drop_index: int = -1
        self._drop_x: int = -1
        self._drop_y_top: int = 0
        self._drop_y_bot: int = 0
        self._hover_row: int = -1

    # ── 右鍵選單 ───────────────────────────────────────────────────

    def _show_context_menu(self, pos: QPoint) -> None:
        if not self.indexAt(pos).isValid():
            return
        if not self.selectionModel().selectedIndexes():
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
        QMenu::item { padding: 6px 24px; border-radius: 4px; color: #1e293b; }
        QMenu::item:selected { background-color: #eff6ff; color: #1e40af; }
        QMenu::separator { height: 1px; background-color: #e2e8f0; margin: 4px 8px; }
        """)

        act_rot_l = menu.addAction("↺ 左轉 90°")
        act_rot_180 = menu.addAction("↕ 轉 180°")
        act_rot_r = menu.addAction("↻ 右轉 90°")
        menu.addSeparator()
        act_delete = menu.addAction("🗑 刪除頁面")
        menu.addSeparator()
        act_export = menu.addAction("💾 匯出選取頁面")

        chosen = menu.exec(self.viewport().mapToGlobal(pos))
        if chosen == act_rot_l:
            self.context_rotate_left.emit()
        elif chosen == act_rot_180:
            self.context_rotate_180.emit()
        elif chosen == act_rot_r:
            self.context_rotate_right.emit()
        elif chosen == act_delete:
            self.context_delete.emit()
        elif chosen == act_export:
            self.context_export_selected.emit()

    # ── 拖曳狀態 ───────────────────────────────────────────────────

    def _reset_drop_indicator(self) -> None:
        self._drop_index = -1
        self._drop_x = -1
        self._drop_y_top = 0
        self._drop_y_bot = 0
        self._hover_row = -1
        self.viewport().update()

    def _collect_visible_items(self) -> list[tuple[int, QRect]]:
        model = self.model()
        if model is None:
            return []

        items: list[tuple[int, QRect]] = []
        for row in range(model.rowCount()):
            rect = self.visualRect(model.index(row, 0))
            if rect.isValid():
                items.append((row, rect))
        return items

    def _build_visual_rows(self) -> list[dict]:
        items = self._collect_visible_items()
        if not items:
            return []

        rows: list[list[tuple[int, QRect]]] = []
        current: list[tuple[int, QRect]] = []
        current_top: int | None = None

        for row, rect in items:
            if not current:
                current = [(row, rect)]
                current_top = rect.top()
                continue

            tolerance = max(12, rect.height() // 3)
            if current_top is not None and abs(rect.top() - current_top) <= tolerance:
                current.append((row, rect))
            else:
                rows.append(current)
                current = [(row, rect)]
                current_top = rect.top()

        if current:
            rows.append(current)

        visual_rows: list[dict] = []
        for row_items in rows:
            row_items = sorted(row_items, key=lambda item: item[1].left())
            top = min(rect.top() for _, rect in row_items)
            bottom = max(rect.bottom() for _, rect in row_items)
            visual_rows.append({
                "items": row_items,
                "top": top,
                "bottom": bottom,
                "center_y": (top + bottom) // 2,
            })

        return visual_rows

    def _pick_visual_row(self, pos: QPoint, visual_rows: list[dict]) -> dict:
        best_row = visual_rows[0]
        best_dist = float("inf")

        for row_info in visual_rows:
            top = row_info["top"]
            bottom = row_info["bottom"]

            if top <= pos.y() <= bottom:
                dist = 0
            elif pos.y() < top:
                dist = top - pos.y()
            else:
                dist = pos.y() - bottom

            if dist < best_dist:
                best_dist = dist
                best_row = row_info

        return best_row

    def _get_target_drop_info(self, pos: QPoint) -> tuple[int, int, int, int, int]:
        """
        穩定版幾何策略：
        1. 先依 visualRect 的 top 分組成「視覺列」
        2. 用滑鼠 y 找到最接近的視覺列
        3. 為該列建立所有插槽（列首 / 卡片間 / 列尾）
        4. 用滑鼠 x 找最近插槽，回傳 target index 與插入線位置
        5. 同時回傳要高亮的目標卡片 row
        """
        model = self.model()
        if model is None:
            return -1, -1, 0, 0, -1

        count = model.rowCount()
        if count == 0:
            return 0, 20, 20, self.viewport().height() - 20, -1

        visual_rows = self._build_visual_rows()
        if not visual_rows:
            return 0, 20, 20, self.viewport().height() - 20, -1

        row_info = self._pick_visual_row(pos, visual_rows)
        items: list[tuple[int, QRect]] = row_info["items"]
        half_gap = self.spacing() // 2

        slots: list[tuple[int, int, int]] = []

        first_row, first_rect = items[0]
        slots.append((first_row, first_rect.left() - half_gap, first_row))

        for (left_row, left_rect), (right_row, right_rect) in zip(items, items[1:]):
            slot_x = (left_rect.right() + right_rect.left()) // 2
            slots.append((right_row, slot_x, right_row))

        last_row, last_rect = items[-1]
        slots.append((last_row + 1, last_rect.right() + half_gap, last_row))

        target_index, line_x, hover_row = min(
            slots,
            key=lambda item: abs(pos.x() - item[1]),
        )

        y_top = row_info["top"] + _INDICATOR_PADDING
        y_bot = row_info["bottom"] - _INDICATOR_PADDING
        return target_index, line_x, y_top, y_bot, hover_row

    # ── 拖曳輔助 ───────────────────────────────────────────────────

    def _maybe_auto_scroll(self, pos: QPoint) -> None:
        bar = self.verticalScrollBar()
        if bar is None:
            return

        y = pos.y()
        height = self.viewport().height()

        if y < _AUTO_SCROLL_MARGIN:
            bar.setValue(max(bar.minimum(), bar.value() - _AUTO_SCROLL_STEP))
        elif y > height - _AUTO_SCROLL_MARGIN:
            bar.setValue(min(bar.maximum(), bar.value() + _AUTO_SCROLL_STEP))

    # ── 插入線與高亮繪製 ───────────────────────────────────────────

    def _draw_hover_target(self, painter: QPainter) -> None:
        if self._hover_row < 0:
            return

        model = self.model()
        if model is None or self._hover_row >= model.rowCount():
            return

        rect = self.visualRect(model.index(self._hover_row, 0))
        if not rect.isValid():
            return

        rect = rect.adjusted(6, 6, -6, -6)

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)

        fill = QColor(_HOVER_FILL_COLOR)
        fill.setAlpha(55)
        painter.setBrush(QBrush(fill))
        painter.setPen(QPen(QColor(_HOVER_BORDER_COLOR), 2, Qt.DashLine))
        painter.drawRoundedRect(rect, 8, 8)

        painter.restore()

    def _draw_drop_indicator(self, painter: QPainter) -> None:
        if self._drop_index == -1 or self._drop_x < 0:
            return

        x = self._drop_x
        y1 = self._drop_y_top
        y2 = self._drop_y_bot
        r = _DIAMOND_R
        color = QColor(_LINE_COLOR)

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)

        pen = QPen(color, _LINE_WIDTH, Qt.SolidLine, Qt.RoundCap)
        painter.setPen(pen)
        painter.drawLine(x, y1 + r, x, y2 - r)

        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(color))

        painter.drawPolygon(QPolygon([
            QPoint(x, y1),
            QPoint(x + r, y1 + r),
            QPoint(x, y1 + r * 2),
            QPoint(x - r, y1 + r),
        ]))
        painter.drawPolygon(QPolygon([
            QPoint(x, y2 - r * 2),
            QPoint(x + r, y2 - r),
            QPoint(x, y2),
            QPoint(x - r, y2 - r),
        ]))

        painter.restore()

    # ── Qt 拖放事件 ────────────────────────────────────────────────

    def dragEnterEvent(self, event: QDragEnterEvent):
        mime = event.mimeData()
        if mime.hasFormat("application/x-pagemove") or mime.hasUrls():
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event: QDragMoveEvent):
        mime = event.mimeData()
        pos = event.position().toPoint()

        self._maybe_auto_scroll(pos)

        if mime.hasUrls():
            self._reset_drop_indicator()
            event.acceptProposedAction()
            return

        if mime.hasFormat("application/x-pagemove"):
            idx, x, yt, yb, hover_row = self._get_target_drop_info(pos)
            self._drop_index = idx
            self._drop_x = x
            self._drop_y_top = yt
            self._drop_y_bot = yb
            self._hover_row = hover_row
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
        self._reset_drop_indicator()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self.viewport())
        self._draw_hover_target(painter)
        self._draw_drop_indicator(painter)
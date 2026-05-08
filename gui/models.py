# 資料模型模組 — SnapshotHistory（復原/重做）與 PdfPageModel（Qt List Model）
import logging
from pathlib import Path
from typing import Dict, List, Optional

from PySide6.QtCore import (
    Qt,
    QSize,
    QAbstractListModel,
    QModelIndex,
    QThreadPool,
    Slot,
    QMimeData,
)
from PySide6.QtGui import QPixmap

from core.thumbnail_service import ThumbnailService
from gui.workers import ThumbnailWorker

logger = logging.getLogger("gui.models")

# Qt UserRole 常數
PAGE_ROLE = Qt.UserRole
THUMB_STATE_ROLE = Qt.UserRole + 1
THUMB_ERROR_ROLE = Qt.UserRole + 2


class ThumbState:
    IDLE = "idle"
    LOADING = "loading"
    READY = "ready"
    FAILED = "failed"


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
        import copy
        self.redo_stack.append(copy.deepcopy(current_pages))
        return self.undo_stack.pop()

    def redo(self, current_pages: list) -> Optional[list]:
        if not self.redo_stack:
            return None
        import copy
        self.undo_stack.append(copy.deepcopy(current_pages))
        return self.redo_stack.pop()


class PdfPageModel(QAbstractListModel):
    def __init__(self, workspace, thumb_service: ThumbnailService):
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

# 背景執行緒模組 — 縮圖與高解析預覽的 QRunnable Worker
import logging

from PySide6.QtCore import QRunnable, QObject, Signal, Slot
from PySide6.QtGui import QImage

from core.thumbnail_service import ThumbnailService

logger = logging.getLogger("gui.workers")


class WorkerSignals(QObject):
    thumbnail_finished = Signal(str, str, int)
    thumbnail_error = Signal(str, str, int)
    preview_ready = Signal(QImage, str)
    preview_error = Signal(str)


class ThumbnailWorker(QRunnable):
    """Renders off the UI thread; completion applies ``thumb_path`` on the main thread only."""

    def __init__(self, workspace, page, zoom: float):
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
    def __init__(self, backend, page_ref, label: str):
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

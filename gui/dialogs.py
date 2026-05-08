# 對話框模組 — PreviewDialog（高品質預覽）與 ExportPdfDialog（匯出選項）
from typing import Optional

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QLabel,
    QScrollArea,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QDialogButtonBox,
)
from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QPixmap, QImage, QResizeEvent

from core.models import ExportOptions
from gui.styles import UiStyles


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

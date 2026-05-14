"""gui/dialogs.py

對話框模組：
  - PreviewDialog    高品質預覽
  - SettingsDialog   應用程式設定（含輸出選項、介面偏好）

原 ExportPdfDialog 已移除：輸出選項改由 SettingsDialog 統一管理，
不再於每次輸出時彈出詢問視窗。
"""

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QImage, QPixmap, QResizeEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QVBoxLayout,
)

from gui.settings import AppSettings
from gui.styles import UiStyles


def _dialog_qss(is_dark: bool) -> str:
    if is_dark:
        return f"""
        QGroupBox {{
            color: {UiStyles.DARK_TEXT};
            border: 1px solid {UiStyles.DARK_BORDER};
            border-radius: 8px;
            margin-top: 12px;
            padding-top: 16px;
            font-weight: 600;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 12px;
            padding: 0 6px;
        }}
        QLineEdit, QComboBox, QDoubleSpinBox, QSpinBox {{
            background-color: {UiStyles.DARK_SURFACE};
            color: {UiStyles.DARK_TEXT};
            border: 1px solid {UiStyles.DARK_BORDER};
            border-radius: 6px;
            padding: 5px 8px;
        }}
        QCheckBox {{
            color: {UiStyles.DARK_TEXT};
        }}
        QLabel {{
            color: {UiStyles.DARK_TEXT};
        }}
        """
    return f"""
    QGroupBox {{
        border: 1px solid {UiStyles.PANEL_BORDER};
        border-radius: 8px;
        margin-top: 12px;
        padding-top: 16px;
        font-weight: 600;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 12px;
        padding: 0 6px;
    }}
    QLineEdit, QComboBox, QDoubleSpinBox, QSpinBox {{
        background-color: #ffffff;
        border: 1px solid {UiStyles.PANEL_BORDER};
        border-radius: 6px;
        padding: 5px 8px;
    }}
    """


class PreviewDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("高品質預覽")
        self.setMinimumSize(800, 900)

        self._is_dark = UiStyles.is_dark_mode()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setAlignment(Qt.AlignCenter)

        self.image_label = QLabel("正在渲染高品質影像...")
        self.image_label.setAlignment(Qt.AlignCenter)
        label_color = UiStyles.DARK_TEXT_MUTED if self._is_dark else UiStyles.TEXT_MUTED
        self.image_label.setStyleSheet(
            f"color: {label_color}; font-size: 10pt; font-weight: normal;"
        )

        self.scroll.setWidget(self.image_label)
        layout.addWidget(self.scroll)

        bg = UiStyles.DARK_BG if self._is_dark else "#ffffff"
        txt = UiStyles.DARK_TEXT if self._is_dark else UiStyles.TEXT_MAIN
        self.setStyleSheet(f"background-color: {bg}; color: {txt}; border: none;")
        self.full_pixmap: QPixmap | None = None

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


class SettingsDialog(QDialog):
    """應用程式設定視窗，包含「輸出設定」與「介面設定」兩個設定方塊。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("設定")
        self.setMinimumWidth(500)
        self.setModal(True)

        is_dark = UiStyles.is_dark_mode()
        self.setStyleSheet(_dialog_qss(is_dark))

        self._settings = AppSettings()
        outer = QVBoxLayout(self)
        outer.setSpacing(16)
        outer.setContentsMargins(20, 20, 20, 20)

        outer.addWidget(self._build_export_group())
        outer.addWidget(self._build_ui_group())

        bbox = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        bbox.accepted.connect(self._save_and_accept)
        bbox.rejected.connect(self.reject)
        outer.addWidget(bbox)

    # ------------------------------------------------------------------
    # 設定方塊：輸出
    # ------------------------------------------------------------------

    def _build_export_group(self) -> QGroupBox:
        grp = QGroupBox("輸出設定")
        form = QFormLayout(grp)
        form.setSpacing(10)

        # 寫入文件資訊
        self._chk_metadata = QCheckBox("寫入文件資訊（標題、作者等）")
        self._chk_metadata.setChecked(self._settings.keep_metadata)
        form.addRow(self._chk_metadata)

        # 內容資訊來源
        self._policy_combo = QComboBox()
        self._policy_combo.addItem("沿用順序第一份來源的內容資訊", "first_pdf")
        self._policy_combo.addItem("沿用順序最末份來源的內容資訊", "last_pdf")
        self._policy_combo.addItem("清空內容欄位（空白 metadata）", "empty")
        idx = self._policy_combo.findData(self._settings.metadata_policy)
        self._policy_combo.setCurrentIndex(max(idx, 0))
        form.addRow("內容資訊來源：", self._policy_combo)

        # 頁碼標籤
        self._chk_labels = QCheckBox("依目前頁序產生頁碼標籤（Page labels）")
        self._chk_labels.setChecked(self._settings.keep_page_labels)
        form.addRow(self._chk_labels)

        # 單頁檔名樣板
        self._edit_template = QLineEdit(self._settings.single_page_filename_template)
        self._edit_template.setPlaceholderText("page_{n:03d}")
        self._edit_template.setToolTip(
            "支援佔位符：\n"
            "  {n}      — 輸出序號（例：1, 2, 3）\n"
            "  {n:03d}  — 補零序號（例：001, 002, 003）\n"
            "  {source} — 來源檔名（不含副檔名）\n"
            "範例：{source}_p{n:03d}  →  report_p001.pdf"
        )
        form.addRow("單頁檔名樣板：", self._edit_template)

        # 輸出後自動開啟資料夾
        self._chk_open_folder = QCheckBox("輸出完成後自動開啟輸出資料夾")
        self._chk_open_folder.setChecked(self._settings.open_folder_after_export)
        form.addRow(self._chk_open_folder)

        # 輸出後顯示完成提示
        self._chk_confirm = QCheckBox("輸出完成後顯示成功提示")
        self._chk_confirm.setChecked(self._settings.show_export_confirm)
        form.addRow(self._chk_confirm)

        # PDF 壓縮等級
        compress_row = QHBoxLayout()
        self._slider_deflate = QSlider(Qt.Horizontal)
        self._slider_deflate.setRange(0, 9)
        self._slider_deflate.setValue(self._settings.deflate_level)
        self._slider_deflate.setTickInterval(1)
        self._slider_deflate.setTickPosition(QSlider.TicksBelow)
        self._slider_deflate.setFixedWidth(160)

        self._lbl_deflate = QLabel(self._deflate_hint(self._settings.deflate_level))
        self._lbl_deflate.setStyleSheet(f"color: {UiStyles.TEXT_MUTED}; font-size: 9pt;")
        self._slider_deflate.valueChanged.connect(
            lambda v: self._lbl_deflate.setText(self._deflate_hint(v))
        )
        compress_row.addWidget(self._slider_deflate)
        compress_row.addWidget(self._lbl_deflate)
        compress_row.addStretch()
        form.addRow("PDF 壓縮等級：", compress_row)

        self._chk_metadata.toggled.connect(
            lambda on: self._policy_combo.setEnabled(on)
        )
        self._policy_combo.setEnabled(self._settings.keep_metadata)

        return grp

    @staticmethod
    def _deflate_hint(level: int) -> str:
        if level == 0:
            return f"{level}  — 不壓縮（最快）"
        if level <= 3:
            return f"{level}  — 輕度壓縮"
        if level <= 6:
            return f"{level}  — 平衡（建議）"
        if level <= 8:
            return f"{level}  — 高壓縮"
        return f"{level}  — 最大壓縮（最慢）"

    # ------------------------------------------------------------------
    # 設定方塊：介面
    # ------------------------------------------------------------------

    def _build_ui_group(self) -> QGroupBox:
        grp = QGroupBox("介面設定")
        form = QFormLayout(grp)
        form.setSpacing(10)

        # 預設輸出資料夾
        dir_row = QHBoxLayout()
        self._edit_dir = QLineEdit(self._settings.default_output_dir)
        self._edit_dir.setPlaceholderText("（空白 = 使用上次開啟路徑）")
        self._edit_dir.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        btn_browse = QPushButton("瀏覽…")
        btn_browse.setFixedWidth(64)
        btn_browse.clicked.connect(self._browse_output_dir)
        dir_row.addWidget(self._edit_dir)
        dir_row.addWidget(btn_browse)
        form.addRow("預設輸出資料夾：", dir_row)

        # 縮圖縮放
        self._spin_zoom = QDoubleSpinBox()
        self._spin_zoom.setRange(0.2, 1.0)
        self._spin_zoom.setSingleStep(0.1)
        self._spin_zoom.setDecimals(1)
        self._spin_zoom.setValue(self._settings.thumbnail_zoom)
        self._spin_zoom.setToolTip("調整縮圖品質與大小（0.2 最小最快，1.0 最大最清晰）")
        form.addRow("縮圖縮放倍率：", self._spin_zoom)

        return grp

    # ------------------------------------------------------------------
    # 事件
    # ------------------------------------------------------------------

    def _browse_output_dir(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "選擇預設輸出資料夾", self._edit_dir.text())
        if d:
            self._edit_dir.setText(d)

    def _save_and_accept(self) -> None:
        s = self._settings
        s.keep_metadata = self._chk_metadata.isChecked()
        s.metadata_policy = self._policy_combo.currentData() or "first_pdf"
        s.keep_page_labels = self._chk_labels.isChecked()
        s.single_page_filename_template = self._edit_template.text()
        s.open_folder_after_export = self._chk_open_folder.isChecked()
        s.show_export_confirm = self._chk_confirm.isChecked()
        s.deflate_level = self._slider_deflate.value()
        s.default_output_dir = self._edit_dir.text().strip()
        s.thumbnail_zoom = self._spin_zoom.value()
        self.accept()

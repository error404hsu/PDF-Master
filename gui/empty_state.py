"""Empty State 引導元件 — 無頁面時顯示拖放提示。"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel


class EmptyStateOverlay(QWidget):
    """覆蓋於 PageListView 上方，無頁面時顯示引導提示。"""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(12)

        icon_label = QLabel("📄")
        icon_label.setAlignment(Qt.AlignCenter)
        icon_label.setStyleSheet("font-size: 64pt; background: transparent;")

        title_label = QLabel("拖放 PDF 至此處開始")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet(
            "font-size: 18pt; font-weight: bold; color: #64748b; background: transparent;"
        )

        hint_label = QLabel(
            "支援多檔同時拖入，或點擊上方「開啟檔案 / 開啟資料夾」按鈕"
        )
        hint_label.setAlignment(Qt.AlignCenter)
        hint_label.setStyleSheet(
            "font-size: 10pt; color: #94a3b8; background: transparent;"
        )

        layout.addWidget(icon_label)
        layout.addWidget(title_label)
        layout.addWidget(hint_label)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        pen = QPen(QColor("#cbd5e1"), 2, Qt.DashLine)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(self.rect().adjusted(30, 30, -30, -30), 16, 16)

    def resizeEvent(self, event) -> None:
        self.setGeometry(self.parent().rect())  # type: ignore[union-attr]
        super().resizeEvent(event)

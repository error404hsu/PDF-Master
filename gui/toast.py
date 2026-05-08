"""Toast 通知元件 — 非阻塞式、自動消失的底部提示條。

用法：
    Toast.show(parent_widget, "訊息內容", kind="info")  # kind: info / error / success
"""
from __future__ import annotations

from PySide6.QtCore import QPropertyAnimation, QEasingCurve, QTimer, QPoint, Qt
from PySide6.QtWidgets import QLabel, QWidget

from gui.styles import UiStyles

_DURATION_MS = 2500
_FADE_MS = 300


class _ToastLabel(QLabel):
    """單一 Toast 浮層。"""

    def __init__(self, parent: QWidget, text: str, kind: str) -> None:
        super().__init__(text, parent)
        self.setAlignment(Qt.AlignCenter)
        style_map = {
            "info": UiStyles.TOAST_INFO,
            "error": UiStyles.TOAST_ERROR,
            "success": UiStyles.TOAST_SUCCESS,
        }
        self.setStyleSheet(style_map.get(kind, UiStyles.TOAST_INFO))
        self.setWindowFlags(Qt.SubWindow)
        self.adjustSize()
        self._reposition()
        self.show()
        self.raise_()

        # 自動消失計時器
        QTimer.singleShot(_DURATION_MS, self._start_fade)

    def _reposition(self) -> None:
        if self.parent() is None:
            return
        p = self.parent()
        pw, ph = p.width(), p.height()
        w, h = max(self.width(), 260), max(self.height(), 40)
        self.setFixedSize(w, h)
        self.move((pw - w) // 2, ph - h - 48)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._reposition()

    def _start_fade(self) -> None:
        self._anim = QPropertyAnimation(self, b"windowOpacity")
        self._anim.setDuration(_FADE_MS)
        self._anim.setStartValue(1.0)
        self._anim.setEndValue(0.0)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.finished.connect(self.deleteLater)
        self._anim.start()


class Toast:
    """靜態工廠，呼叫 Toast.show() 即可顯示通知。"""

    @staticmethod
    def show(parent: QWidget, text: str, kind: str = "info") -> None:
        _ToastLabel(parent, text, kind)

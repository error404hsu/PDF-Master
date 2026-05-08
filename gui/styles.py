"""gui/styles.py — 集中管理所有 QSS 字串與色票

外觀現代化（2026-05-08）：
  - 建議一：全面升級圓角（8-12px）、字體跟隨 OS
  - 建議二：PageCardDelegate 卡片陰影繪製輔助常數
  - 建議四：深色模式 palette 偵測 + DARK_THEME QSS
"""
from __future__ import annotations

# 來源 PDF 群組色帶顏色（最多支援 12 個不同來源）
SOURCE_COLORS = [
    "#3b82f6",  # blue
    "#10b981",  # emerald
    "#f59e0b",  # amber
    "#8b5cf6",  # violet
    "#ef4444",  # red
    "#06b6d4",  # cyan
    "#f97316",  # orange
    "#84cc16",  # lime
    "#ec4899",  # pink
    "#14b8a6",  # teal
    "#a855f7",  # purple
    "#64748b",  # slate
]


class UiStyles:
    # ── 色票 ──────────────────────────────────────────────────────
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

    # ── 卡片陰影繪製參數（供 PageCardDelegate.paint() 使用）──────
    # 以 QPainter 手動繪製，不用 QGraphicsDropShadowEffect
    # （後者掛在 Delegate 上會造成整個 viewport 重繪效能問題）
    CARD_SHADOW_COLOR = (0, 0, 0, 22)   # RGBA tuple → QColor(r,g,b,a)
    CARD_SHADOW_OFFSET = (0, 2)          # (dx, dy)
    CARD_SHADOW_RADIUS = 6               # 模糊展開 px（以多層漸變矩形模擬）
    CARD_RADIUS = 10                     # 卡片圓角（統一升級至 10px）

    # ── 深色模式色票 ──────────────────────────────────────────────
    DARK_BG = "#0f172a"
    DARK_SURFACE = "#1e293b"
    DARK_BORDER = "#334155"
    DARK_TEXT = "#e2e8f0"
    DARK_TEXT_MUTED = "#94a3b8"
    DARK_PRIMARY = "#60a5fa"
    DARK_CARD_BG = "#1e293b"
    DARK_CARD_BORDER = "#334155"

    # ── QSS：一般按鈕 ─────────────────────────────────────────────
    BASE_BUTTON = """
    QPushButton {
        background-color: #f8fafc;
        color: #64748b;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        font-weight: normal;
        font-size: 10pt;
        padding: 4px 10px;
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
        border-radius: 8px;
        font-weight: normal;
        font-size: 10pt;
        padding: 4px 10px;
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
        border-radius: 8px;
        font-weight: 600;
        font-size: 10pt;
        padding: 5px 14px;
    }
    QPushButton:hover {
        background-color: #2563eb;
    }
    QPushButton:disabled {
        background-color: #93c5fd;
        color: #eff6ff;
    }
    """

    # ── QSS：清單視圖 ─────────────────────────────────────────────
    LIST_VIEW = """
    QListView {
        background-color: #f1f5f9;
        border: none;
        padding: 20px 20px 20px 50px;
        outline: none;
    }
    """

    # ── QSS：深色模式清單視圖 ─────────────────────────────────────
    LIST_VIEW_DARK = """
    QListView {
        background-color: #0f172a;
        border: none;
        padding: 20px 20px 20px 50px;
        outline: none;
    }
    """

    # ── QSS：Footer ───────────────────────────────────────────────
    FOOTER = """
    background-color: white;
    border-top: 1px solid #e2e8f0;
    color: #64748b;
    font-size: 10pt;
    padding-left: 20px;
    font-weight: normal;
    """

    FOOTER_HINT = """
    background-color: white;
    color: #94a3b8;
    font-size: 9pt;
    padding-right: 16px;
    """

    FOOTER_DARK = """
    background-color: #1e293b;
    border-top: 1px solid #334155;
    color: #94a3b8;
    font-size: 10pt;
    padding-left: 20px;
    font-weight: normal;
    """

    FOOTER_HINT_DARK = """
    background-color: #1e293b;
    color: #64748b;
    font-size: 9pt;
    padding-right: 16px;
    """

    # ── QSS：Progress Bar ─────────────────────────────────────────
    PROGRESS_BAR = """
    QProgressBar {
        border: none;
        background-color: #e2e8f0;
        border-radius: 2px;
        height: 4px;
        text-align: center;
    }
    QProgressBar::chunk {
        background-color: #3b82f6;
        border-radius: 2px;
    }
    """

    # ── QSS：Toast ────────────────────────────────────────────────
    TOAST_INFO = """
        background-color: #1e293b;
        color: white;
        border-radius: 10px;
        font-size: 10pt;
        padding: 10px 20px;
    """

    TOAST_ERROR = """
        background-color: #f43f5e;
        color: white;
        border-radius: 10px;
        font-size: 10pt;
        padding: 10px 20px;
    """

    TOAST_SUCCESS = """
        background-color: #10b981;
        color: white;
        border-radius: 10px;
        font-size: 10pt;
        padding: 10px 20px;
    """

    # ── QSS：QToolBar（淺色）────────────────────────────────────
    TOOLBAR = """
QToolBar {
    background-color: #ffffff;
    border-bottom: 1px solid #e2e8f0;
    padding: 4px 8px;
    spacing: 4px;
}
QToolButton {
    background: transparent;
    border: 1px solid transparent;
    border-radius: 8px;
    padding: 4px 8px;
    color: #475569;
    font-size: 9pt;
    min-width: 52px;
}
QToolButton:hover {
    background-color: #f1f5f9;
    border-color: #e2e8f0;
}
QToolButton:pressed {
    background-color: #e2e8f0;
}
QToolButton:disabled {
    color: #cbd5e1;
}
QToolBar::separator {
    width: 1px;
    background-color: #e2e8f0;
    margin: 6px 4px;
}
"""

    # ── QSS：QToolBar（深色）────────────────────────────────────
    TOOLBAR_DARK = """
QToolBar {
    background-color: #1e293b;
    border-bottom: 1px solid #334155;
    padding: 4px 8px;
    spacing: 4px;
}
QToolButton {
    background: transparent;
    border: 1px solid transparent;
    border-radius: 8px;
    padding: 4px 8px;
    color: #94a3b8;
    font-size: 9pt;
    min-width: 52px;
}
QToolButton:hover {
    background-color: #334155;
    border-color: #475569;
}
QToolButton:pressed {
    background-color: #475569;
}
QToolButton:disabled {
    color: #475569;
}
QToolBar::separator {
    width: 1px;
    background-color: #334155;
    margin: 6px 4px;
}
"""

    TOOLBAR_PRIMARY = """
QToolButton {
    background-color: #3b82f6;
    color: white;
    border: none;
    border-radius: 8px;
    padding: 6px 14px;
    font-size: 9pt;
    font-weight: 600;
    min-width: 72px;
}
QToolButton:hover { background-color: #2563eb; }
QToolButton:disabled { background-color: #93c5fd; }
"""

    # ── QSS：右鍵選單（深色）─────────────────────────────────────
    CONTEXT_MENU_DARK = """
    QMenu {
        background-color: #1e293b;
        border: 1px solid #334155;
        border-radius: 10px;
        padding: 4px;
        font-size: 10pt;
        color: #e2e8f0;
    }
    QMenu::item { padding: 6px 24px; border-radius: 6px; color: #e2e8f0; }
    QMenu::item:selected { background-color: #334155; color: #60a5fa; }
    QMenu::separator { height: 1px; background-color: #334155; margin: 4px 8px; }
    """

    @staticmethod
    def is_dark_mode() -> bool:
        """偵測系統是否處於深色模式（跨平台，不依賴 OS API）。"""
        from PySide6.QtWidgets import QApplication
        from PySide6.QtGui import QPalette
        app = QApplication.instance()
        if app is None:
            return False
        palette = app.palette()
        window_color = palette.color(QPalette.ColorRole.Window)
        return window_color.lightness() < 128

    @staticmethod
    def apply_theme(app) -> bool:  # type: ignore[type-arg]
        """依系統深淺色自動套用全局 QSS，回傳 is_dark。"""
        from PySide6.QtGui import QPalette, QColor
        is_dark = UiStyles.is_dark_mode()
        if is_dark:
            # 強制 Fusion dark palette
            palette = QPalette()
            bg = QColor(UiStyles.DARK_BG)
            surface = QColor(UiStyles.DARK_SURFACE)
            text = QColor(UiStyles.DARK_TEXT)
            muted = QColor(UiStyles.DARK_TEXT_MUTED)
            primary = QColor(UiStyles.DARK_PRIMARY)
            palette.setColor(QPalette.ColorRole.Window, bg)
            palette.setColor(QPalette.ColorRole.WindowText, text)
            palette.setColor(QPalette.ColorRole.Base, surface)
            palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#162032"))
            palette.setColor(QPalette.ColorRole.Text, text)
            palette.setColor(QPalette.ColorRole.Button, surface)
            palette.setColor(QPalette.ColorRole.ButtonText, text)
            palette.setColor(QPalette.ColorRole.Highlight, primary)
            palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
            palette.setColor(QPalette.ColorRole.PlaceholderText, muted)
            palette.setColor(QPalette.ColorRole.ToolTipBase, surface)
            palette.setColor(QPalette.ColorRole.ToolTipText, text)
            app.setPalette(palette)
        return is_dark

# 樣式常數模組 — 集中管理所有 QSS 字串與色票

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

    BASE_BUTTON = """
    QPushButton {
        background-color: #f8fafc;
        color: #64748b;
        border: 1px solid #e2e8f0;
        border-radius: 4px;
        font-weight: normal;
        font-size: 10pt;
        padding: 2px 8px;
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
        border-radius: 4px;
        font-weight: normal;
        font-size: 10pt;
        padding: 2px 8px;
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
        border-radius: 6px;
        font-weight: normal;
        font-size: 10pt;
        padding: 4px 12px;
    }
    QPushButton:hover {
        background-color: #2563eb;
    }
    QPushButton:disabled {
        background-color: #93c5fd;
        color: #eff6ff;
    }
    """

    LIST_VIEW = """
    QListView {
        background-color: #f8fafc;
        border: none;
        padding: 20px 20px 20px 50px;
        outline: none;
    }
    """

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

    TOAST_INFO = """
        background-color: #1e293b;
        color: white;
        border-radius: 8px;
        font-size: 10pt;
        padding: 10px 20px;
    """

    TOAST_ERROR = """
        background-color: #f43f5e;
        color: white;
        border-radius: 8px;
        font-size: 10pt;
        padding: 10px 20px;
    """

    TOAST_SUCCESS = """
        background-color: #10b981;
        color: white;
        border-radius: 8px;
        font-size: 10pt;
        padding: 10px 20px;
    """

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
    border-radius: 6px;
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

    TOOLBAR_PRIMARY = """
QToolButton {
    background-color: #3b82f6;
    color: white;
    border: none;
    border-radius: 6px;
    padding: 6px 14px;
    font-size: 9pt;
    font-weight: 600;
    min-width: 72px;
}
QToolButton:hover { background-color: #2563eb; }
QToolButton:disabled { background-color: #93c5fd; }
"""

# 樣式常數模組 — 集中管理所有 QSS 字串與色票


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

"""gui/icons.py — 統一圖示管理器

優先使用 Qt 內建 QStyle.StandardPixmap，
若平台不支援則 fallback 至嵌入的 base64 SVG。
"""
from __future__ import annotations

from functools import cache

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication, QStyle

# ---------------------------------------------------------------------------
# SVG 來源（16×16 viewBox，線條色用 currentColor → 替換為 #475569）
# ---------------------------------------------------------------------------

_SVG_FOLDER_OPEN = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="none">
  <path d="M1 3.5A1.5 1.5 0 0 1 2.5 2h3.379a1.5 1.5 0 0 1 1.06.44l.622.621A1.5 1.5 0 0 0 8.62 3.5H13.5A1.5 1.5 0 0 1 15 5v1H1V3.5Z"
        fill="#475569"/>
  <path d="M1 7h14l-1.447 6.724A1.5 1.5 0 0 1 12.083 15H3.917a1.5 1.5 0 0 1-1.47-1.276L1 7Z"
        fill="#475569" opacity="0.7"/>
</svg>
"""

_SVG_TRASH = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="none">
  <path d="M6 2h4a1 1 0 0 1 1 1H5a1 1 0 0 1 1-1Z" fill="#f43f5e"/>
  <rect x="2" y="4" width="12" height="1.5" rx="0.75" fill="#f43f5e"/>
  <path d="M3.5 6.5 4 14h8l.5-7.5H3.5Zm3 1h1v5h-1v-5Zm2 0h1l-.25 5h-1l.25-5Z"
        fill="#f43f5e" opacity="0.85"/>
</svg>
"""

_SVG_ROTATE_LEFT = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="none">
  <path d="M3.5 5.5A5 5 0 1 1 3 8" stroke="#475569" stroke-width="1.5"
        stroke-linecap="round" fill="none"/>
  <polyline points="1,4 3.5,5.5 5,3" stroke="#475569" stroke-width="1.5"
            stroke-linecap="round" stroke-linejoin="round" fill="none"/>
</svg>
"""

_SVG_ROTATE_180 = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="none">
  <path d="M2.5 4A5.5 5.5 0 0 1 13.5 4" stroke="#475569" stroke-width="1.5"
        stroke-linecap="round" fill="none"/>
  <polyline points="1,2.5 2.5,4 4,2.5" stroke="#475569" stroke-width="1.5"
            stroke-linecap="round" stroke-linejoin="round" fill="none"/>
  <path d="M13.5 12A5.5 5.5 0 0 1 2.5 12" stroke="#475569" stroke-width="1.5"
        stroke-linecap="round" fill="none"/>
  <polyline points="15,13.5 13.5,12 12,13.5" stroke="#475569" stroke-width="1.5"
            stroke-linecap="round" stroke-linejoin="round" fill="none"/>
</svg>
"""

_SVG_ROTATE_RIGHT = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="none">
  <path d="M12.5 5.5A5 5 0 1 0 13 8" stroke="#475569" stroke-width="1.5"
        stroke-linecap="round" fill="none"/>
  <polyline points="15,4 12.5,5.5 11,3" stroke="#475569" stroke-width="1.5"
            stroke-linecap="round" stroke-linejoin="round" fill="none"/>
</svg>
"""

_SVG_EXPORT_SINGLE = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="none">
  <rect x="2" y="2" width="9" height="12" rx="1.5" fill="#475569" opacity="0.18"/>
  <rect x="5" y="1.5" width="9" height="12" rx="1.5" fill="#475569"/>
  <path d="M9.5 5.5v4" stroke="white" stroke-width="1.4" stroke-linecap="round"/>
  <path d="M7.8 7.9 9.5 9.5l1.7-1.6" stroke="white" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/>
  <path d="M7.3 11.3h4.4" stroke="white" stroke-width="1.2" stroke-linecap="round"/>
</svg>
"""

_SVG_SETTINGS = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="none">
  <path d="M6.8 1.7h2.4l.35 1.55c.25.09.49.19.72.31l1.42-.7 1.7 1.7-.7 1.42c.12.23.22.47.31.72l1.55.35v2.4l-1.55.35c-.09.25-.19.49-.31.72l.7 1.42-1.7 1.7-1.42-.7c-.23.12-.47.22-.72.31l-.35 1.55H6.8l-.35-1.55a5.86 5.86 0 0 1-.72-.31l-1.42.7-1.7-1.7.7-1.42a5.86 5.86 0 0 1-.31-.72L1.45 9.5V7.1l1.55-.35c.09-.25.19-.49.31-.72l-.7-1.42 1.7-1.7 1.42.7c.23-.12.47-.22.72-.31L6.8 1.7Z"
        fill="#475569"/>
  <circle cx="8" cy="8.3" r="2.2" fill="white"/>
</svg>
"""

_SVG_EXPORT_SELECTED = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="none">
  <rect x="1.5" y="2" width="10" height="12" rx="1.5" fill="#3b82f6" opacity="0.2"/>
  <rect x="4" y="1.5" width="10" height="12" rx="1.5" fill="#475569"/>
  <path d="M9 6v4" stroke="white" stroke-width="1.4" stroke-linecap="round"/>
  <path d="M7.3 8.4 9 6.5l1.7 1.9" stroke="white" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/>
  <path d="M6.8 11.3h4.4" stroke="white" stroke-width="1.2" stroke-linecap="round"/>
  <circle cx="3" cy="3.5" r="1" fill="#f97316"/>
</svg>
"""

_SVG_EXPORT_ALL = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="none">
  <rect x="1" y="2.5" width="10" height="11" rx="1.5" fill="#3b82f6" opacity="0.2"/>
  <rect x="3" y="1" width="10" height="11" rx="1.5" fill="#475569"/>
  <path d="M8 5.5v5" stroke="white" stroke-width="1.4" stroke-linecap="round"/>
  <path d="M6.3 7.9 8 9.5l1.7-1.6" stroke="white" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/>
  <path d="M5.8 10.8h4.4" stroke="white" stroke-width="1.2" stroke-linecap="round"/>
  <rect x="8.5" y="3.5" width="7" height="8.5" rx="1.2" fill="#f97316" opacity="0.7"/>
</svg>
"""

_SVG_DOCUMENT = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none">
  <path d="M4 2h10l6 6v13a1.5 1.5 0 0 1-1.5 1.5h-13A1.5 1.5 0 0 1 4 21V2Z" fill="#3b82f6"/>
  <path d="M14 2v5.5a.5.5 0 0 0 .5.5H20" fill="#bfdbfe"/>
  <path d="M14 2v5.5a.5.5 0 0 0 .5.5H20L14 2Z" fill="#1e40af" opacity="0.3"/>
  <path d="M7 10h10M7 13h7M7 16h8" stroke="white" stroke-width="1.5" stroke-linecap="round" opacity="0.9"/>
</svg>
"""

_SVG_INFO = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="none">
  <circle cx="8" cy="8" r="7" fill="white" stroke="white" stroke-width="2"/>
  <path d="M8 7.5v4M8 5v.5" stroke="#475569" stroke-width="1.5" stroke-linecap="round"/>
</svg>
"""

_SVG_SUCCESS = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="none">
  <circle cx="8" cy="8" r="7" fill="white" stroke="white" stroke-width="2"/>
  <path d="M5.5 8.5 7 10l3.5-3.5" stroke="#10b981" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
</svg>
"""

_SVG_ERROR = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="none">
  <circle cx="8" cy="8" r="7" fill="white" stroke="white" stroke-width="2"/>
  <path d="m5.5 5.5 5 5M10.5 5.5l-5 5" stroke="#f43f5e" stroke-width="1.5" stroke-linecap="round"/>
</svg>
"""

# key → (StandardPixmap_attr_name, fallback_svg)
_ICON_MAP: dict[str, tuple[str, str]] = {
    "open_file":       ("SP_DialogOpenButton",       _SVG_FOLDER_OPEN),
    "open_folder":     ("SP_DirOpenIcon",            _SVG_FOLDER_OPEN),
    "undo":            ("SP_ArrowBack",              ""),
    "redo":            ("SP_ArrowForward",           ""),
    "rotate_left":     ("",                          _SVG_ROTATE_LEFT),
    "rotate_180":      ("",                          _SVG_ROTATE_180),
    "rotate_right":    ("",                          _SVG_ROTATE_RIGHT),
    "delete":          ("SP_TrashIcon",              _SVG_TRASH),
    "export_selected": ("SP_FileDialogDetailedView", _SVG_EXPORT_SELECTED),
    "export_single":   ("",                          _SVG_EXPORT_SINGLE),
    "export":          ("SP_DialogSaveButton",       _SVG_EXPORT_ALL),
    "settings":        ("SP_FileDialogContentsView", _SVG_SETTINGS),
    "document":        ("SP_FileIcon",               _SVG_DOCUMENT),
    "info":            ("SP_MessageBoxInformation",  _SVG_INFO),
    "success":         ("",                          _SVG_SUCCESS),
    "error_icon":      ("SP_MessageBoxCritical",     _SVG_ERROR),
}


class AppIcons:
    """集中式圖示工廠，優先使用平台 StandardPixmap，fallback 至內嵌 SVG。"""

    @staticmethod
    @cache
    def get(name: str) -> QIcon:
        """回傳對應 key 的 QIcon，優先 SP_*，fallback SVG。"""
        entry = _ICON_MAP.get(name)
        if entry is None:
            return QIcon()

        sp_attr, fallback_svg = entry

        if sp_attr:
            app = QApplication.instance()
            if app is not None:
                style = app.style()
                sp = getattr(QStyle.StandardPixmap, sp_attr, None)
                if sp is not None:
                    icon = style.standardIcon(sp)
                    if not icon.isNull():
                        return icon

        if fallback_svg:
            return AppIcons._from_svg(fallback_svg)

        return QIcon()

    @staticmethod
    def _from_svg(svg_str: str) -> QIcon:
        """將 SVG 字串轉為 QIcon（透過 QSvgRenderer + QPainter）。"""
        svg_bytes = QByteArray(svg_str.encode("utf-8"))
        renderer = QSvgRenderer(svg_bytes)
        size = 32
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        return QIcon(pixmap)

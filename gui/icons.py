"""gui/icons.py — 統一圖示管理器

優先使用 Qt 內建 QStyle.StandardPixmap，
若平台不支援則 fallback 至嵌入的 base64 SVG。
"""
from __future__ import annotations

import base64
from functools import lru_cache

from PySide6.QtCore import QByteArray, QSize, Qt
from PySide6.QtGui import QIcon, QImage, QPainter, QPixmap
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

# key → (StandardPixmap_attr_name, fallback_svg)
_ICON_MAP: dict[str, tuple[str, str]] = {
    "open_file":       ("SP_FileDialogStart",       _SVG_FOLDER_OPEN),
    "open_folder":     ("SP_DirOpenIcon",            _SVG_FOLDER_OPEN),
    "undo":            ("SP_ArrowBack",              ""),
    "redo":            ("SP_ArrowForward",           ""),
    "rotate_left":     ("",                          _SVG_ROTATE_LEFT),
    "rotate_180":      ("",                          _SVG_ROTATE_180),
    "rotate_right":    ("",                          _SVG_ROTATE_RIGHT),
    "delete":          ("SP_TrashIcon",              _SVG_TRASH),
    "export_selected": ("SP_FileDialogDetailedView", ""),
    "export":          ("SP_DialogSaveButton",       ""),
}


class AppIcons:
    """集中式圖示工廠，優先使用平台 StandardPixmap，fallback 至內嵌 SVG。"""

    @staticmethod
    @lru_cache(maxsize=None)
    def get(name: str) -> QIcon:
        """回傳對應 key 的 QIcon，優先 SP_*，fallback SVG。"""
        entry = _ICON_MAP.get(name)
        if entry is None:
            return QIcon()

        sp_attr, fallback_svg = entry

        # 嘗試 Qt 內建 StandardPixmap
        if sp_attr:
            app = QApplication.instance()
            if app is not None:
                style = app.style()
                sp = getattr(QStyle.StandardPixmap, sp_attr, None)
                if sp is not None:
                    icon = style.standardIcon(sp)
                    if not icon.isNull():
                        return icon

        # fallback：內嵌 SVG
        if fallback_svg:
            return AppIcons._from_svg(fallback_svg)

        return QIcon()

    @staticmethod
    def _from_svg(svg_str: str) -> QIcon:
        """將 SVG 字串轉為 QIcon（透過 QSvgRenderer + QPainter）。"""
        svg_bytes = QByteArray(svg_str.encode("utf-8"))
        renderer = QSvgRenderer(svg_bytes)
        size = 32  # 渲染為 32px，讓 Qt 自動縮放
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        return QIcon(pixmap)

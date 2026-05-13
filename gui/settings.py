"""gui/settings.py — AppSettings

以 QSettings 將使用者偏好持久化至作業系統標準位置。
所有輸出相關設定集中於此，SettingsDialog 負責 UI 讀寫。
"""
from __future__ import annotations

from PySide6.QtCore import QSettings

_ORG = "PDFMaster"
_APP = "PDFMasterApp"


class AppSettings:
    """存取應用程式設定的單一入口（非 Singleton，可多次實例化）。"""

    def __init__(self) -> None:
        self._s = QSettings(_ORG, _APP)

    # ------------------------------------------------------------------
    # 輸出：通用
    # ------------------------------------------------------------------

    @property
    def keep_metadata(self) -> bool:
        return self._s.value("export/keep_metadata", True, type=bool)  # type: ignore[return-value]

    @keep_metadata.setter
    def keep_metadata(self, v: bool) -> None:
        self._s.setValue("export/keep_metadata", v)

    @property
    def metadata_policy(self) -> str:
        return self._s.value("export/metadata_policy", "first_pdf", type=str)  # type: ignore[return-value]

    @metadata_policy.setter
    def metadata_policy(self, v: str) -> None:
        self._s.setValue("export/metadata_policy", v)

    @property
    def keep_page_labels(self) -> bool:
        return self._s.value("export/keep_page_labels", True, type=bool)  # type: ignore[return-value]

    @keep_page_labels.setter
    def keep_page_labels(self, v: bool) -> None:
        self._s.setValue("export/keep_page_labels", v)

    # ------------------------------------------------------------------
    # 輸出：單頁模式
    # ------------------------------------------------------------------

    @property
    def single_page_filename_template(self) -> str:
        """單頁輸出的檔名樣板，支援 {n}（序號）與 {source}（來源檔名）佔位符。

        預設：page_{n:03d}
        範例：{source}_p{n:03d}  →  report_p001.pdf
        """
        return self._s.value("export/single_page_template", "page_{n:03d}", type=str)  # type: ignore[return-value]

    @single_page_filename_template.setter
    def single_page_filename_template(self, v: str) -> None:
        self._s.setValue("export/single_page_template", v.strip() or "page_{n:03d}")

    # ------------------------------------------------------------------
    # 輸出：壓縮等級
    # ------------------------------------------------------------------

    @property
    def deflate_level(self) -> int:
        """zlib 壓縮等級（0 = 不壓縮，最快；9 = 最大壓縮，最慢）。預設 6。"""
        return int(self._s.value("export/deflate_level", 6))  # type: ignore[arg-type]

    @deflate_level.setter
    def deflate_level(self, v: int) -> None:
        self._s.setValue("export/deflate_level", max(0, min(9, int(v))))

    # ------------------------------------------------------------------
    # 介面
    # ------------------------------------------------------------------

    @property
    def show_export_confirm(self) -> bool:
        """輸出成功後是否顯示完成提示。"""
        return self._s.value("ui/show_export_confirm", True, type=bool)  # type: ignore[return-value]

    @show_export_confirm.setter
    def show_export_confirm(self, v: bool) -> None:
        self._s.setValue("ui/show_export_confirm", v)

    @property
    def open_folder_after_export(self) -> bool:
        """輸出完成後是否自動開啟輸出資料夾。"""
        return self._s.value("ui/open_folder_after_export", False, type=bool)  # type: ignore[return-value]

    @open_folder_after_export.setter
    def open_folder_after_export(self, v: bool) -> None:
        self._s.setValue("ui/open_folder_after_export", v)

    @property
    def default_output_dir(self) -> str:
        """預設輸出資料夾（空字串 = 使用上次路徑）。"""
        return self._s.value("ui/default_output_dir", "", type=str)  # type: ignore[return-value]

    @default_output_dir.setter
    def default_output_dir(self, v: str) -> None:
        self._s.setValue("ui/default_output_dir", v)

    @property
    def thumbnail_zoom(self) -> float:
        """縮圖縮放倍率（0.2 ~ 1.0）。"""
        return float(self._s.value("ui/thumbnail_zoom", 0.4))  # type: ignore[arg-type]

    @thumbnail_zoom.setter
    def thumbnail_zoom(self, v: float) -> None:
        self._s.setValue("ui/thumbnail_zoom", float(v))

    def export_options_dict(self) -> dict:
        """快速取得 ExportOptions 所需的 kwargs。"""
        return {
            "keep_metadata": self.keep_metadata,
            "keep_page_labels": self.keep_page_labels,
            "metadata_policy": self.metadata_policy,
            "deflate_level": self.deflate_level,
        }

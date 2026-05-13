from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from .workspace import WorkspaceManager


class ThumbnailService:
    """縮圖服務：管理縮圖目錄生命週期，並封裝所有縮圖產生邏輯。

    WorkspaceManager 本身不再持有 thumbnail_dir；
    縮圖路徑的決策（{thumbnail_dir}/{page_id}.png）完全由此服務負責。
    """

    # 格線縮圖預設縮放：~0.4 適合 200px 卡片於 96–144 DPI 螢幕
    DEFAULT_ZOOM = 0.4

    def __init__(self, workspace: WorkspaceManager, thumbnail_dir: Path):
        self.workspace = workspace
        self.thumbnail_dir = Path(thumbnail_dir)
        self.thumbnail_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # 公開 API
    # ------------------------------------------------------------------

    def render_one(self, index: int, zoom: float | None = None) -> Path:
        """渲染第 index 頁縮圖，更新 PageRef.thumb_path，並回傳路徑。"""
        self.workspace._validate_indices([index])
        page = self.workspace.pages[index]
        normalized_zoom = self._normalize_zoom(zoom)
        output_path = self.thumbnail_dir / f"{page.page_id}.png"

        rendered = self.workspace.render_thumbnail_to_disk(
            page_id=page.page_id,
            source_path=page.source_path,
            source_page_index=page.source_page_index,
            final_rotation=page.effective_rotation,
            zoom=normalized_zoom,
            output_path=output_path,
        )
        page.thumb_path = rendered
        return rendered

    def render_many(self, indices: Iterable[int], zoom: float | None = None) -> list[Path]:
        clean_indices = self._normalize_indices(indices)
        normalized_zoom = self._normalize_zoom(zoom)
        return [
            self.render_one(index, zoom=normalized_zoom)
            for index in clean_indices
        ]

    def rerender_one(self, index: int, zoom: float | None = None) -> Path:
        """強制清除舊縮圖後重新渲染。"""
        self.workspace._validate_indices([index])
        page = self.workspace.pages[index]

        if page.thumb_path and page.thumb_path.exists():
            page.thumb_path.unlink(missing_ok=True)
        page.clear_thumbnail()  # 透過 PageRef 公開介面清除

        return self.render_one(index=index, zoom=zoom)

    def rerender_many(self, indices: Iterable[int], zoom: float | None = None) -> list[Path]:
        clean_indices = self._normalize_indices(indices)
        for index in clean_indices:
            self.workspace._validate_indices([index])
            page = self.workspace.pages[index]
            if page.thumb_path and page.thumb_path.exists():
                page.thumb_path.unlink(missing_ok=True)
            page.clear_thumbnail()

        return self.render_many(clean_indices, zoom=zoom)

    def exists(self, index: int) -> bool:
        self.workspace._validate_indices([index])
        page = self.workspace.pages[index]
        return bool(page.thumb_path and page.thumb_path.exists())

    # ------------------------------------------------------------------
    # 私有輔助
    # ------------------------------------------------------------------

    def _normalize_zoom(self, zoom: float | None) -> float:
        value = self.DEFAULT_ZOOM if zoom is None else float(zoom)
        if value <= 0:
            raise ValueError("zoom must be greater than 0")
        return value

    def _normalize_indices(self, indices: Iterable[int]) -> list[int]:
        try:
            clean = sorted(set(int(index) for index in indices))
        except Exception as e:
            raise ValueError("indices must be an iterable of integers") from e

        if not clean:
            return []

        self.workspace._validate_indices(clean)
        return clean

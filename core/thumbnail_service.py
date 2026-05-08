from __future__ import annotations

from pathlib import Path
from typing import Iterable

from .workspace import WorkspaceManager


class ThumbnailService:
    # Grid thumbnails: higher = sharper (larger PNGs & more CPU). ~0.4 suits ~200px cards on 96–144 DPI.
    DEFAULT_ZOOM = 0.4

    def __init__(self, workspace: WorkspaceManager):
        self.workspace = workspace

    def render_one(self, index: int, zoom: float | None = None) -> Path:
        return self.workspace.render_thumbnail(
            index=index,
            zoom=self._normalize_zoom(zoom),
        )

    def render_many(self, indices: Iterable[int], zoom: float | None = None) -> list[Path]:
        clean_indices = self._normalize_indices(indices)
        normalized_zoom = self._normalize_zoom(zoom)
        return [
            self.workspace.render_thumbnail(index=index, zoom=normalized_zoom)
            for index in clean_indices
        ]

    def rerender_one(self, index: int, zoom: float | None = None) -> Path:
        self.workspace._validate_indices([index])
        page = self.workspace.pages[index]

        if page.thumb_path and page.thumb_path.exists():
            page.thumb_path.unlink(missing_ok=True)
            page.thumb_path = None

        return self.render_one(index=index, zoom=zoom)

    def rerender_many(self, indices: Iterable[int], zoom: float | None = None) -> list[Path]:
        clean_indices = self._normalize_indices(indices)
        for index in clean_indices:
            self.workspace._validate_indices([index])
            page = self.workspace.pages[index]
            if page.thumb_path and page.thumb_path.exists():
                page.thumb_path.unlink(missing_ok=True)
                page.thumb_path = None

        return self.render_many(clean_indices, zoom=zoom)

    def exists(self, index: int) -> bool:
        self.workspace._validate_indices([index])
        page = self.workspace.pages[index]
        return bool(page.thumb_path and page.thumb_path.exists())

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
from __future__ import annotations

from pathlib import Path

from .workspace import WorkspaceManager


class ThumbnailService:
    def __init__(self, workspace: WorkspaceManager):
        self.workspace = workspace

    def render_one(self, index: int, zoom: float = 0.2) -> Path:
        return self.workspace.render_thumbnail(index=index, zoom=zoom)

    def render_many(self, indices: list[int], zoom: float = 0.2) -> list[Path]:
        return [self.workspace.render_thumbnail(index, zoom=zoom) for index in indices]

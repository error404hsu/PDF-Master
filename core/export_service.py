from __future__ import annotations

from pathlib import Path

from .models import ExportOptions
from .workspace import WorkspaceManager


class ExportService:
    def __init__(self, workspace: WorkspaceManager):
        self.workspace = workspace

    def export(self, output_path: str | Path, options: ExportOptions | None = None) -> Path:
        return self.workspace.export_pdf(output_path=output_path, options=options)

from __future__ import annotations

from pathlib import Path

from .models import ExportOptions
from .workspace import WorkspaceManager


class ExportService:
    def __init__(self, workspace: WorkspaceManager):
        self.workspace = workspace

    def export(self, output_path: str | Path, options: ExportOptions | None = None) -> Path:
        normalized_path = Path(output_path)

        if normalized_path.suffix.lower() != ".pdf":
            normalized_path = normalized_path.with_suffix(".pdf")

        return self.workspace.export_pdf(
            output_path=normalized_path,
            options=options,
        )

    def can_export(self) -> bool:
        return bool(self.workspace.pages)

    def export_selected(
        self,
        indices: list[int],
        output_path: str | Path,
        options: ExportOptions | None = None,
    ) -> Path:
        if not indices:
            raise ValueError("no page indices selected for export")

        self.workspace.validate_page_indices(indices)

        normalized_path = Path(output_path)
        if normalized_path.suffix.lower() != ".pdf":
            normalized_path = normalized_path.with_suffix(".pdf")

        original_pages = list(self.workspace.pages)
        selected_pages = [self.workspace.pages[i] for i in sorted(set(indices))]

        try:
            self.workspace.replace_pages(selected_pages)
            return self.workspace.export_pdf(
                output_path=normalized_path,
                options=options,
            )
        finally:
            self.workspace.replace_pages(original_pages)
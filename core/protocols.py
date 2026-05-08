from __future__ import annotations

from pathlib import Path
from typing import Protocol

from .models import ExportOptions, ExportPage, ImageInspectionResult, PdfInspectionResult


class PdfBackend(Protocol):
    def inspect_pdf(self, path: Path) -> PdfInspectionResult: ...

    def inspect_image(self, path: Path) -> ImageInspectionResult:
        """回傳圖片基本資訊；多頁 TIFF 的 page_count > 1。"""
        ...

    def render_thumbnail(
        self,
        source_path: Path,
        page_index: int,
        final_rotation: int,
        output_path: Path,
        zoom: float = 0.4,
    ) -> Path: ...

    def export_pages(
        self,
        pages: list[ExportPage],
        output_path: Path,
        options: ExportOptions,
        source_info: list[PdfInspectionResult],
    ) -> Path: ...

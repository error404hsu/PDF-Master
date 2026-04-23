from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from core.exceptions import PdfBackendUnavailableError
from core.models import ExportOptions, ExportPage, PdfInspectionResult


class PyMuPdfBackend:
    def __init__(self):
        try:
            import fitz  # type: ignore
        except Exception as exc:
            raise PdfBackendUnavailableError(
                "PyMuPDF (fitz) is not installed. Install it with: pip install pymupdf"
            ) from exc
        self.fitz = fitz

    def inspect_pdf(self, path: Path) -> PdfInspectionResult:
        with self.fitz.open(path) as doc:
            attachments = []
            try:
                names = doc.embfile_names()
                attachments = list(names or [])
            except Exception:
                attachments = []

            forms_present = False
            try:
                forms_present = bool(doc.is_form_pdf)
            except Exception:
                forms_present = False

            page_rotations = [
                doc.load_page(i).rotation for i in range(doc.page_count)
            ]

            return PdfInspectionResult(
                path=Path(path),
                page_count=doc.page_count,
                metadata=dict(doc.metadata or {}),
                page_labels=doc.get_page_labels() or [],
                toc=[],
                attachments=attachments,
                forms_present=forms_present,
                encrypted=bool(doc.needs_pass),
                page_rotations=page_rotations,
            )

    def render_thumbnail(
        self,
        source_path: Path,
        page_index: int,
        final_rotation: int,
        output_path: Path,
        zoom: float = 0.2,
    ) -> Path:
        with self.fitz.open(source_path) as doc:
            page = doc.load_page(page_index)
            matrix = self.fitz.Matrix(zoom, zoom).prerotate(final_rotation)
            pix = page.get_pixmap(matrix=matrix, alpha=False)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            pix.save(output_path)
            return output_path

    def render_page_to_image(
        self,
        source_path: Path,
        page_index: int,
        zoom: float = 2.0,
        rotation: int = 0,
    ) -> bytes:
        with self.fitz.open(source_path) as doc:
            page = doc.load_page(page_index)
            matrix = self.fitz.Matrix(zoom, zoom).prerotate(rotation)
            pix = page.get_pixmap(matrix=matrix, alpha=False)
            return pix.tobytes("png")

    def export_pages(
        self,
        pages: list[ExportPage],
        output_path: Path,
        options: ExportOptions,
        source_info: list[PdfInspectionResult],
    ) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)

        out_doc = self.fitz.open()
        info_by_path = {info.path: info for info in source_info}
        groups: dict[Path, list[tuple[int, ExportPage]]] = defaultdict(list)

        for final_index, export_page in enumerate(pages):
            groups[export_page.source_path].append((final_index, export_page))

        sorted_pages: list[ExportPage | None] = [None] * len(pages)

        for source_path, entries in groups.items():
            entries = sorted(entries, key=lambda item: item[1].source_page_index)
            with self.fitz.open(source_path) as src:
                for final_index, export_page in entries:
                    out_doc.insert_pdf(
                        src,
                        from_page=export_page.source_page_index,
                        to_page=export_page.source_page_index,
                    )
                    sorted_pages[final_index] = export_page

        if any(item is None for item in sorted_pages):
            out_doc.close()
            raise RuntimeError("export assembly failed")

        if len(sorted_pages) != len(pages):
            out_doc.close()
            raise RuntimeError("unexpected page count in export")

        for final_index, export_page in enumerate(pages):
            page = out_doc.load_page(final_index)
            if page.rotation != export_page.final_rotation:
                page.set_rotation(export_page.final_rotation)

        primary = info_by_path.get(pages[0].source_path)
        if primary and options.keep_metadata:
            try:
                out_doc.set_metadata(primary.metadata)
            except Exception:
                pass

        if options.keep_page_labels:
            try:
                labels = []
                for page_index, export_page in enumerate(pages):
                    labels.append(
                        {
                            "startpage": page_index,
                            "prefix": export_page.source_page_label,
                            "style": "",
                            "firstpagenum": 1,
                        }
                    )
                out_doc.set_page_labels(labels)
            except Exception:
                pass

        # keep_bookmarks is intentionally off by default per project requirement.
        out_doc.save(output_path, garbage=3, deflate=True)
        out_doc.close()
        return output_path
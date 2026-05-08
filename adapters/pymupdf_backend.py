from __future__ import annotations

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
        pdf_path = Path(path)

        with self.fitz.open(pdf_path) as doc:
            attachments = self._extract_attachments(doc)
            forms_present = self._extract_forms_present(doc)
            toc = self._extract_toc(doc)
            page_labels = self._extract_page_labels(doc)
            page_rotations = self._page_rotations(doc)

            return PdfInspectionResult(
                path=pdf_path,
                page_count=doc.page_count,
                metadata=dict(doc.metadata or {}),
                page_labels=page_labels,
                toc=toc,
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
        zoom: float = 0.4,
    ) -> Path:
        if zoom <= 0:
            raise ValueError("zoom must be greater than 0")

        source_path = Path(source_path)
        output_path = Path(output_path)

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
        if zoom <= 0:
            raise ValueError("zoom must be greater than 0")

        with self.fitz.open(Path(source_path)) as doc:
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
        if not pages:
            raise ValueError("pages must not be empty")

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        out_doc = self.fitz.open()
        src_docs: dict[Path, object] = {}

        try:
            for export_page in pages:
                source_path = Path(export_page.source_path)
                src = src_docs.get(source_path)
                if src is None:
                    src = self.fitz.open(source_path)
                    src_docs[source_path] = src

                out_doc.insert_pdf(
                    src,
                    from_page=export_page.source_page_index,
                    to_page=export_page.source_page_index,
                )

            if out_doc.page_count != len(pages):
                raise RuntimeError("unexpected page count in export")

            for final_index, export_page in enumerate(pages):
                page = out_doc.load_page(final_index)
                if page.rotation != export_page.final_rotation:
                    page.set_rotation(export_page.final_rotation)

            info_by_path = {Path(info.path): info for info in source_info}

            # 直接使用 ExportOptions dataclass 屬性，移除不安全的 getattr()
            if options.keep_metadata:
                policy = options.metadata_policy
                if policy == "empty":
                    self._apply_metadata(out_doc, {})
                else:
                    anchor = (
                        Path(pages[0].source_path)
                        if policy == "first_pdf"
                        else Path(pages[-1].source_path)
                    )
                    picked = info_by_path.get(anchor)
                    if picked is not None:
                        self._apply_metadata(out_doc, dict(picked.metadata or {}))

            if options.keep_page_labels:
                self._apply_page_labels(out_doc, pages)

            out_doc.save(output_path, garbage=3, deflate=True)
            return output_path

        finally:
            for src in src_docs.values():
                try:
                    src.close()
                except Exception:
                    pass
            out_doc.close()

    def _page_rotations(self, doc) -> list[int]:
        # 使用列表推导式取代 N+1 load_page 迴圈
        return [page.rotation for page in doc]

    def _extract_attachments(self, doc) -> list[str]:
        try:
            names = doc.embfile_names()
            return list(names or [])
        except Exception:
            return []

    def _extract_forms_present(self, doc) -> bool:
        try:
            return bool(doc.is_form_pdf)
        except Exception:
            return False

    def _extract_toc(self, doc) -> list:
        try:
            return doc.get_toc() or []
        except Exception:
            return []

    def _extract_page_labels(self, doc) -> list[dict]:
        try:
            return doc.get_page_labels() or []
        except Exception:
            return []

    def _apply_metadata(self, out_doc, metadata: dict) -> None:
        try:
            out_doc.set_metadata(metadata)
        except Exception:
            pass

    def _apply_page_labels(self, out_doc, pages: list[ExportPage]) -> None:
        try:
            labels = [
                {
                    "startpage": page_index,
                    "prefix": export_page.source_page_label or "",
                    "style": "",
                    "firstpagenum": 1,
                }
                for page_index, export_page in enumerate(pages)
            ]
            out_doc.set_page_labels(labels)
        except Exception:
            pass

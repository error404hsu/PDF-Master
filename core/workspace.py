from __future__ import annotations

from pathlib import Path
from typing import Iterable

from .exceptions import InvalidMoveError, InvalidRotationError, WorkspaceError
from .models import (
    ExportOptions,
    ExportPage,
    PageRef,
    PdfInspectionResult,
    SourcePdf,
    WorkspaceSnapshot,
    new_id,
)
from .protocols import PdfBackend


class WorkspaceManager:
    def __init__(self, backend: PdfBackend, thumbnail_dir: Path):
        self.backend = backend
        self.thumbnail_dir = Path(thumbnail_dir)
        self.thumbnail_dir.mkdir(parents=True, exist_ok=True)
        self.source_pdfs: dict[str, SourcePdf] = {}
        self._inspection_cache: dict[str, PdfInspectionResult] = {}
        self.pages: list[PageRef] = []

    def open_pdfs(self, paths: Iterable[str | Path]) -> list[str]:
        added_doc_ids: list[str] = []
        for raw_path in paths:
            path = Path(raw_path)
            inspected = self.backend.inspect_pdf(path)
            doc_id = new_id()
            added_doc_ids.append(doc_id)
            self._inspection_cache[doc_id] = inspected
            self.source_pdfs[doc_id] = SourcePdf(
                doc_id=doc_id,
                path=path,
                page_count=inspected.page_count,
                metadata=inspected.metadata,
                page_labels=inspected.page_labels,
                toc=inspected.toc,
                attachments=inspected.attachments,
                forms_present=inspected.forms_present,
                encrypted=inspected.encrypted,
            )
            expanded_labels = self._expand_labels(inspected.page_count, inspected.page_labels)
            rotations = inspected.page_rotations or [0] * inspected.page_count
            for page_index in range(inspected.page_count):
                self.pages.append(
                    PageRef(
                        page_id=new_id(),
                        source_doc_id=doc_id,
                        source_path=path,
                        source_page_index=page_index,
                        source_page_label=expanded_labels[page_index],
                        base_rotation=rotations[page_index] if page_index < len(rotations) else 0,
                    )
                )
        return added_doc_ids

    def move_pages(self, indices: list[int], target_index: int) -> None:
        if not indices:
            return
        clean = sorted(set(indices))
        self._validate_indices(clean)
        if target_index < 0 or target_index > len(self.pages):
            raise InvalidMoveError("target index out of range")

        moving = [self.pages[i] for i in clean]
        remove_set = set(clean)
        remain = [page for idx, page in enumerate(self.pages) if idx not in remove_set]
        adjusted_target = target_index - sum(1 for idx in clean if idx < target_index)
        for offset, page in enumerate(moving):
            remain.insert(adjusted_target + offset, page)
        self.pages = remain

    def remove_pages(self, indices: list[int]) -> None:
        if not indices:
            return
        self._validate_indices(indices)
        remove_set = set(indices)
        for idx in sorted(remove_set):
            thumb = self.pages[idx].thumb_path
            if thumb and thumb.exists():
                thumb.unlink(missing_ok=True)
        self.pages = [page for idx, page in enumerate(self.pages) if idx not in remove_set]

    def rotate_pages(self, indices: list[int], angle: int) -> None:
        if angle % 90 != 0:
            raise InvalidRotationError("rotation angle must be a multiple of 90")
        self._validate_indices(indices)
        for idx in indices:
            page = self.pages[idx]
            page.rotation_delta = (page.rotation_delta + angle) % 360

    def render_thumbnail(self, index: int, zoom: float = 0.2) -> Path:
        self._validate_indices([index])
        page = self.pages[index]
        out_path = self.thumbnail_dir / f"{page.page_id}.png"
        rendered = self.backend.render_thumbnail(
            source_path=page.source_path,
            page_index=page.source_page_index,
            final_rotation=page.effective_rotation,
            output_path=out_path,
            zoom=zoom,
        )
        page.thumb_path = rendered
        return rendered

    def build_export_plan(self) -> list[ExportPage]:
        return [
            ExportPage(
                source_path=page.source_path,
                source_page_index=page.source_page_index,
                final_rotation=page.effective_rotation,
                source_doc_id=page.source_doc_id,
                source_page_label=page.source_page_label,
            )
            for page in self.pages
        ]

    def export_pdf(self, output_path: str | Path, options: ExportOptions | None = None) -> Path:
        if not self.pages:
            raise WorkspaceError("workspace is empty")
        export_options = options or ExportOptions()
        source_info = [self._inspection_cache[doc_id] for doc_id in self.source_pdfs]
        return self.backend.export_pages(
            pages=self.build_export_plan(),
            output_path=Path(output_path),
            options=export_options,
            source_info=source_info,
        )

    def snapshot(self) -> WorkspaceSnapshot:
        pages = []
        for index, page in enumerate(self.pages):
            pages.append(
                {
                    "index": index,
                    "page_id": page.page_id,
                    "source": page.source_path.name,
                    "source_page_index": page.source_page_index,
                    "label": page.source_page_label,
                    "effective_rotation": page.effective_rotation,
                }
            )
        return WorkspaceSnapshot(
            source_count=len(self.source_pdfs),
            page_count=len(self.pages),
            pages=pages,
        )

    def _validate_indices(self, indices: list[int]) -> None:
        if any(idx < 0 or idx >= len(self.pages) for idx in indices):
            raise WorkspaceError("page index out of range")

    @staticmethod
    def _expand_labels(page_count: int, label_rules: list[dict]) -> list[str]:
        if not label_rules:
            return [""] * page_count

        def roman(number: int, upper: bool) -> str:
            mapping = [
                (1000, "M"), (900, "CM"), (500, "D"), (400, "CD"),
                (100, "C"), (90, "XC"), (50, "L"), (40, "XL"),
                (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I"),
            ]
            result = []
            for value, symbol in mapping:
                while number >= value:
                    number -= value
                    result.append(symbol)
            text = "".join(result)
            return text if upper else text.lower()

        def alpha(number: int, upper: bool) -> str:
            chars = []
            while number > 0:
                number -= 1
                offset = 65 if upper else 97
                chars.append(chr(offset + (number % 26)))
                number //= 26
            return "".join(reversed(chars))

        labels = [""] * page_count
        ordered = sorted(label_rules, key=lambda item: item["startpage"])
        for idx, rule in enumerate(ordered):
            start = rule["startpage"]
            end = ordered[idx + 1]["startpage"] if idx + 1 < len(ordered) else page_count
            prefix = rule.get("prefix", "") or ""
            style = rule.get("style", "") or ""
            first = max(1, int(rule.get("firstpagenum", 1) or 1))
            for page_number in range(start, min(end, page_count)):
                serial = first + (page_number - start)
                if style == "D":
                    suffix = str(serial)
                elif style == "r":
                    suffix = roman(serial, upper=False)
                elif style == "R":
                    suffix = roman(serial, upper=True)
                elif style == "a":
                    suffix = alpha(serial, upper=False)
                elif style == "A":
                    suffix = alpha(serial, upper=True)
                else:
                    suffix = ""
                labels[page_number] = f"{prefix}{suffix}"
        return labels

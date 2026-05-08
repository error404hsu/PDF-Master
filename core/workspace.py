from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterable, Sequence

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

logger = logging.getLogger(__name__)


class WorkspaceManager:
    def __init__(self, backend: PdfBackend, thumbnail_dir: Path):
        self.backend = backend
        self.thumbnail_dir = Path(thumbnail_dir)
        self.thumbnail_dir.mkdir(parents=True, exist_ok=True)

        self.source_pdfs: dict[str, SourcePdf] = {}
        self._inspection_cache: dict[str, PdfInspectionResult] = {}
        self.pages: list[PageRef] = []

    def open_pdfs(
        self, paths: Iterable[str | Path]
    ) -> tuple[list[str], list[Path]]:
        """開啟多個 PDF 檔案。

        每個檔案獨立 try/except，單一損壞不中斷其餘批次。

        Returns:
            (added_doc_ids, failed_paths)
            - added_doc_ids: 成功載入的文件 ID 清單
            - failed_paths:  載入失敗的路徑清單（可用於 UI 提示）
        """
        added_doc_ids: list[str] = []
        failed_paths: list[Path] = []

        pending_source_pdfs: dict[str, SourcePdf] = {}
        pending_inspections: dict[str, PdfInspectionResult] = {}
        pending_pages: list[PageRef] = []

        for raw_path in paths:
            path = Path(raw_path)
            try:
                inspected = self.backend.inspect_pdf(path)
                doc_id = new_id()

                added_doc_ids.append(doc_id)
                pending_inspections[doc_id] = inspected
                pending_source_pdfs[doc_id] = SourcePdf(
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

                expanded_labels = self._expand_labels(
                    inspected.page_count,
                    inspected.page_labels or [],
                )
                rotations = list(inspected.page_rotations or [0] * inspected.page_count)

                for page_index in range(inspected.page_count):
                    pending_pages.append(
                        PageRef(
                            page_id=new_id(),
                            source_doc_id=doc_id,
                            source_path=path,
                            source_page_index=page_index,
                            source_page_label=expanded_labels[page_index],
                            base_rotation=rotations[page_index] if page_index < len(rotations) else 0,
                        )
                    )
            except Exception as exc:
                logger.warning("無法開啟 %s：%s", path, exc)
                failed_paths.append(path)

        self._inspection_cache.update(pending_inspections)
        self.source_pdfs.update(pending_source_pdfs)
        self.pages.extend(pending_pages)
        return added_doc_ids, failed_paths

    def move_pages(self, indices: list[int], target_index: int) -> None:
        if not indices:
            return

        clean = sorted(set(indices))
        self.validate_page_indices(clean)

        if target_index < 0 or target_index > len(self.pages):
            raise InvalidMoveError("target index out of range")

        moving = [self.pages[i] for i in clean]
        remove_set = set(clean)
        remaining = [page for idx, page in enumerate(self.pages) if idx not in remove_set]

        adjusted_target = target_index - sum(1 for idx in clean if idx < target_index)
        for offset, page in enumerate(moving):
            remaining.insert(adjusted_target + offset, page)

        self.pages = remaining

    def remove_pages(self, indices: list[int]) -> None:
        if not indices:
            return

        clean = sorted(set(indices))
        self.validate_page_indices(clean)
        remove_set = set(clean)

        thumb_paths = {
            page.thumb_path
            for idx, page in enumerate(self.pages)
            if idx in remove_set and page.thumb_path is not None
        }

        for thumb in thumb_paths:
            if thumb and thumb.exists():
                thumb.unlink(missing_ok=True)

        self.pages = [page for idx, page in enumerate(self.pages) if idx not in remove_set]

    def rotate_pages(self, indices: list[int], angle: int) -> None:
        if angle % 90 != 0:
            raise InvalidRotationError("rotation angle must be a multiple of 90")

        clean = sorted(set(indices))
        self.validate_page_indices(clean)

        for idx in clean:
            self.pages[idx].rotation_delta = (self.pages[idx].rotation_delta + angle) % 360

    def render_thumbnail_to_disk(
        self,
        *,
        page_id: str,
        source_path: Path | str,
        source_page_index: int,
        final_rotation: int,
        zoom: float,
    ) -> Path:
        """Write a thumbnail PNG without mutating any ``PageRef`` (thread-safe for callers)."""
        if zoom <= 0:
            raise ValueError("zoom must be greater than 0")

        output_path = self.thumbnail_dir / f"{page_id}.png"
        return self.backend.render_thumbnail(
            source_path=Path(source_path),
            page_index=source_page_index,
            final_rotation=final_rotation,
            output_path=output_path,
            zoom=zoom,
        )

    def render_thumbnail(self, index: int, zoom: float = 0.4) -> Path:
        self.validate_page_indices([index])

        if zoom <= 0:
            raise ValueError("zoom must be greater than 0")

        page = self.pages[index]
        rendered = self.render_thumbnail_to_disk(
            page_id=page.page_id,
            source_path=page.source_path,
            source_page_index=page.source_page_index,
            final_rotation=page.effective_rotation,
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
        used_doc_ids = self._collect_used_doc_ids()
        source_info = [
            self._inspection_cache[doc_id]
            for doc_id in used_doc_ids
            if doc_id in self._inspection_cache
        ]

        return self.backend.export_pages(
            pages=self.build_export_plan(),
            output_path=Path(output_path),
            options=export_options,
            source_info=source_info,
        )

    def replace_pages(self, pages: Sequence[PageRef]) -> None:
        self.pages = list(pages)

    def validate_page_indices(self, indices: list[int]) -> None:
        self._validate_indices(indices)

    def get_page(self, index: int) -> PageRef:
        self.validate_page_indices([index])
        return self.pages[index]

    def encrypted_used_sources(self, page_indices: list[int] | None = None) -> list[SourcePdf]:
        """Return sources marked ``encrypted`` among all pages, or only among ``page_indices`` rows."""
        doc_ids_ordered: list[str] = []
        seen_ids: set[str] = set()

        if page_indices is None:
            for page in self.pages:
                if page.source_doc_id not in seen_ids:
                    seen_ids.add(page.source_doc_id)
                    doc_ids_ordered.append(page.source_doc_id)
        else:
            for i in sorted(set(page_indices)):
                if 0 <= i < len(self.pages):
                    did = self.pages[i].source_doc_id
                    if did not in seen_ids:
                        seen_ids.add(did)
                        doc_ids_ordered.append(did)

        result: list[SourcePdf] = []
        for doc_id in doc_ids_ordered:
            src = self.source_pdfs.get(doc_id)
            if src is not None and src.encrypted:
                result.append(src)
        return result

    def compact_sources(self) -> None:
        used_doc_ids = set(self._collect_used_doc_ids())

        self.source_pdfs = {
            doc_id: source_pdf
            for doc_id, source_pdf in self.source_pdfs.items()
            if doc_id in used_doc_ids
        }
        self._inspection_cache = {
            doc_id: inspection
            for doc_id, inspection in self._inspection_cache.items()
            if doc_id in used_doc_ids
        }

    def snapshot(self) -> WorkspaceSnapshot:
        pages = []
        for index, page in enumerate(self.pages):
            pages.append(
                {
                    "index": index,
                    "page_id": page.page_id,
                    "source_doc_id": page.source_doc_id,
                    "source": page.source_path.name,
                    "source_page_index": page.source_page_index,
                    "label": page.source_page_label,
                    "base_rotation": page.base_rotation,
                    "rotation_delta": page.rotation_delta,
                    "effective_rotation": page.effective_rotation,
                    "thumb_path": str(page.thumb_path) if page.thumb_path else None,
                }
            )

        return WorkspaceSnapshot(
            source_count=len(self.source_pdfs),
            page_count=len(self.pages),
            pages=pages,
        )

    def _collect_used_doc_ids(self) -> list[str]:
        seen: set[str] = set()
        ordered: list[str] = []

        for page in self.pages:
            if page.source_doc_id not in seen:
                seen.add(page.source_doc_id)
                ordered.append(page.source_doc_id)

        return ordered

    def _validate_indices(self, indices: list[int]) -> None:
        if any(idx < 0 or idx >= len(self.pages) for idx in indices):
            raise WorkspaceError("page index out of range")

    @staticmethod
    def _expand_labels(page_count: int, label_rules: list[dict] | None) -> list[str]:
        if page_count <= 0:
            return []

        if not label_rules:
            return [""] * page_count

        def roman(number: int, upper: bool) -> str:
            mapping = [
                (1000, "M"), (900, "CM"), (500, "D"), (400, "CD"),
                (100, "C"), (90, "XC"), (50, "L"), (40, "XL"),
                (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I"),
            ]
            result: list[str] = []
            for value, symbol in mapping:
                while number >= value:
                    number -= value
                    result.append(symbol)
            text = "".join(result)
            return text if upper else text.lower()

        def alpha(number: int, upper: bool) -> str:
            chars: list[str] = []
            while number > 0:
                number -= 1
                offset = 65 if upper else 97
                chars.append(chr(offset + (number % 26)))
                number //= 26
            return "".join(reversed(chars))

        valid_rules: list[dict] = []
        for rule in label_rules:
            if "startpage" not in rule:
                continue
            start = int(rule["startpage"])
            if 0 <= start < page_count:
                valid_rules.append(rule)

        if not valid_rules:
            return [""] * page_count

        labels = [""] * page_count
        ordered = sorted(valid_rules, key=lambda item: int(item["startpage"]))

        for idx, rule in enumerate(ordered):
            start = int(rule["startpage"])
            end = int(ordered[idx + 1]["startpage"]) if idx + 1 < len(ordered) else page_count

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

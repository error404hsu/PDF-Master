from __future__ import annotations

import logging
from collections.abc import Iterable, Sequence
from pathlib import Path

from .exceptions import InvalidMoveError, InvalidRotationError, WorkspaceError
from .models import (
    ExportOptions,
    ExportPage,
    PageRef,
    PageSnapshot,
    PdfInspectionResult,
    SourcePdf,
    WorkspaceSnapshot,
    new_id,
)
from .protocols import PdfBackend

logger = logging.getLogger(__name__)

# 支援的圖片副檔名（小寫）
IMAGE_SUFFIXES = frozenset(
    {".jpg", ".jpeg", ".png", ".tiff", ".tif", ".bmp", ".webp", ".gif"}
)


class WorkspaceManager:
    """核心工作區管理員。

    職責：PDF／圖片頁面集合的增刪移轉，以及匯出計畫建構。
    縮圖目錄生命週期由 ThumbnailService 全權負責，
    本類別不再持有 thumbnail_dir，亦不自行建立資料夾。
    """

    def __init__(self, backend: PdfBackend):
        self.backend = backend
        self.source_pdfs: dict[str, SourcePdf] = {}
        self._inspection_cache: dict[str, PdfInspectionResult] = {}
        self.pages: list[PageRef] = []

    # ------------------------------------------------------------------
    # 開啟檔案（統一入口：自動路由 PDF 與圖片）
    # ------------------------------------------------------------------

    def open_files(
        self, paths: Iterable[str | Path]
    ) -> tuple[list[str], list[Path]]:
        """開啟多個 PDF 或圖片檔案。

        根據副檔名自動路由：圖片走 _open_image()，PDF 走 _open_pdf()。
        每個檔案獨立 try/except，單一損壞不中斷其餘批次。

        Returns:
            (added_doc_ids, failed_paths)
        """
        added_doc_ids: list[str] = []
        failed_paths: list[Path] = []

        for raw_path in paths:
            path = Path(raw_path)
            try:
                if path.suffix.lower() in IMAGE_SUFFIXES:
                    ids = self._open_image(path)
                else:
                    ids = self._open_pdf(path)
                added_doc_ids.extend(ids)
            except Exception as exc:
                logger.warning("無法開啟 %s：%s", path, exc)
                failed_paths.append(path)

        return added_doc_ids, failed_paths

    def open_pdfs(
        self, paths: Iterable[str | Path]
    ) -> tuple[list[str], list[Path]]:
        """開啟多個 PDF 檔案（向後相容入口，內部委派給 open_files()）。

        Returns:
            (added_doc_ids, failed_paths)
        """
        return self.open_files(paths)

    # ------------------------------------------------------------------
    # 內部開啟邏輯
    # ------------------------------------------------------------------

    def _open_pdf(
        self, path: Path
    ) -> list[str]:
        """開啟單一 PDF，回傳新增的 doc_id 清單（通常只有 1 個）。"""
        inspected = self.backend.inspect_pdf(path)
        doc_id = new_id()

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

        expanded_labels = self._expand_labels(
            inspected.page_count,
            inspected.page_labels or [],
        )
        rotations = list(inspected.page_rotations or [0] * inspected.page_count)

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

        return [doc_id]

    def _open_image(
        self, path: Path
    ) -> list[str]:
        """開啟圖片（含多頁 TIFF），每一幀對應一頁 PageRef。

        以虛擬 PdfInspectionResult 填充 _inspection_cache，
        讓 export_pdf() 的 source_info 查找路徑保持一致。
        """
        img_info = self.backend.inspect_image(path)
        doc_id = new_id()

        # 以虛擬 PdfInspectionResult 填入 cache（格式統一，供 export 取用）
        fake_inspection = PdfInspectionResult(
            path=path,
            page_count=img_info.page_count,
            encrypted=False,
        )
        self._inspection_cache[doc_id] = fake_inspection
        self.source_pdfs[doc_id] = SourcePdf(
            doc_id=doc_id,
            path=path,
            page_count=img_info.page_count,
            encrypted=False,
        )

        for frame_index in range(img_info.page_count):
            self.pages.append(
                PageRef(
                    page_id=new_id(),
                    source_doc_id=doc_id,
                    source_path=path,
                    source_page_index=frame_index,
                    source_page_label="",
                    base_rotation=0,
                )
            )

        return [doc_id]

    # ------------------------------------------------------------------
    # 頁面操作
    # ------------------------------------------------------------------

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
        output_path: Path,
    ) -> Path:
        """將縮圖渲染至指定路徑並回傳（不修改任何 PageRef）。

        output_path 由呼叫端（ThumbnailService）負責決定，
        WorkspaceManager 本身不持有縮圖目錄。
        """
        if zoom <= 0:
            raise ValueError("zoom must be greater than 0")

        return self.backend.render_thumbnail(
            source_path=Path(source_path),
            page_index=source_page_index,
            final_rotation=final_rotation,
            output_path=output_path,
            zoom=zoom,
        )

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
        pages: list[PageSnapshot] = [
            PageSnapshot(
                index=index,
                page_id=page.page_id,
                source_doc_id=page.source_doc_id,
                source=page.source_path.name,
                source_page_index=page.source_page_index,
                label=page.source_page_label,
                base_rotation=page.base_rotation,
                rotation_delta=page.rotation_delta,
                effective_rotation=page.effective_rotation,
                thumb_path=str(page.thumb_path) if page.thumb_path else None,
            )
            for index, page in enumerate(self.pages)
        ]

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
    def _expand_labels(page_count: int, label_rules: list[dict] | None) -> list[str]:  # type: ignore[type-arg]
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

        valid_rules: list[dict] = []  # type: ignore[type-arg]
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

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal
import uuid

MetadataPolicy = Literal["first_pdf", "last_pdf", "empty"]


def new_id() -> str:
    return str(uuid.uuid4())


def _normalize_rotation(value: int) -> int:
    return int(value) % 360


@dataclass(slots=True, frozen=True)
class SourcePdf:
    doc_id: str
    path: Path
    page_count: int
    metadata: dict[str, Any] = field(default_factory=dict)
    page_labels: list[dict[str, Any]] = field(default_factory=list)
    toc: list[Any] = field(default_factory=list)
    attachments: list[str] = field(default_factory=list)
    forms_present: bool = False
    encrypted: bool = False

    def __post_init__(self):
        object.__setattr__(self, "path", Path(self.path))
        if not self.doc_id:
            raise ValueError("doc_id must not be empty")
        if self.page_count < 0:
            raise ValueError("page_count must be >= 0")


@dataclass(slots=True)
class PageRef:
    page_id: str
    source_doc_id: str
    source_path: Path
    source_page_index: int
    source_page_label: str = ""
    base_rotation: int = 0
    rotation_delta: int = 0
    thumb_path: Path | None = None

    def __post_init__(self):
        self.source_path = Path(self.source_path)

        if self.thumb_path is not None:
            self.thumb_path = Path(self.thumb_path)

        if not self.page_id:
            raise ValueError("page_id must not be empty")
        if not self.source_doc_id:
            raise ValueError("source_doc_id must not be empty")
        if self.source_page_index < 0:
            raise ValueError("source_page_index must be >= 0")

        self.base_rotation = _normalize_rotation(self.base_rotation)
        self.rotation_delta = _normalize_rotation(self.rotation_delta)

    @property
    def effective_rotation(self) -> int:
        return (self.base_rotation + self.rotation_delta) % 360

    def clear_thumbnail(self) -> None:
        self.thumb_path = None

    def rotate(self, angle: int) -> None:
        if angle % 90 != 0:
            raise ValueError("rotation angle must be a multiple of 90")
        self.rotation_delta = (self.rotation_delta + angle) % 360


@dataclass(slots=True, frozen=True)
class PdfInspectionResult:
    path: Path
    page_count: int
    metadata: dict[str, Any] = field(default_factory=dict)
    page_labels: list[dict[str, Any]] = field(default_factory=list)
    toc: list[Any] = field(default_factory=list)
    attachments: list[str] = field(default_factory=list)
    forms_present: bool = False
    encrypted: bool = False
    page_rotations: list[int] = field(default_factory=list)

    def __post_init__(self):
        object.__setattr__(self, "path", Path(self.path))
        if self.page_count < 0:
            raise ValueError("page_count must be >= 0")
        normalized_rotations = [_normalize_rotation(value) for value in self.page_rotations]
        object.__setattr__(self, "page_rotations", normalized_rotations)


@dataclass(slots=True, frozen=True)
class ImageInspectionResult:
    """圖片檢查結果。單張圖片 page_count=1；多頁 TIFF 為幀數。"""

    path: Path
    page_count: int          # 單張圖片 = 1，多頁 TIFF = 幀數
    width_px: int
    height_px: int
    format: str              # "jpeg" / "png" / "tiff" 等
    encrypted: bool = False  # 圖片不加密，保留為統一介面

    def __post_init__(self):
        object.__setattr__(self, "path", Path(self.path))
        if self.page_count < 1:
            raise ValueError("page_count must be >= 1")


@dataclass(slots=True, frozen=True)
class ExportPage:
    source_path: Path
    source_page_index: int
    final_rotation: int
    source_doc_id: str
    source_page_label: str = ""

    def __post_init__(self):
        object.__setattr__(self, "source_path", Path(self.source_path))
        object.__setattr__(self, "final_rotation", _normalize_rotation(self.final_rotation))

        if not self.source_doc_id:
            raise ValueError("source_doc_id must not be empty")
        if self.source_page_index < 0:
            raise ValueError("source_page_index must be >= 0")


@dataclass(slots=True, frozen=True)
class ExportOptions:
    keep_metadata: bool = True
    keep_page_labels: bool = True
    keep_attachments: bool = True
    keep_forms: bool = True
    keep_bookmarks: bool = False
    metadata_policy: MetadataPolicy = "first_pdf"
    deflate_level: int = 6  # zlib 壓縮等級，0 = 不壓縮，9 = 最大壓縮

    def __post_init__(self):
        allowed = {"first_pdf", "last_pdf", "empty"}
        if self.metadata_policy not in allowed:
            raise ValueError(f"metadata_policy must be one of {sorted(allowed)}")
        if not (0 <= self.deflate_level <= 9):
            raise ValueError("deflate_level must be between 0 and 9")


@dataclass(slots=True, frozen=True)
class PageSnapshot:
    """強型別快照：對應 WorkspaceManager.snapshot() 中每一頁的輸出。"""

    index: int
    page_id: str
    source_doc_id: str
    source: str                    # source_path.name
    source_page_index: int
    label: str
    base_rotation: int
    rotation_delta: int
    effective_rotation: int
    thumb_path: str | None

    def __post_init__(self):
        if self.index < 0:
            raise ValueError("index must be >= 0")
        if self.source_page_index < 0:
            raise ValueError("source_page_index must be >= 0")

    def __getitem__(self, key: str) -> Any:  # 向後相容：允許 snapshot.pages[i]["label"]
        return getattr(self, key)


@dataclass(slots=True, frozen=True)
class WorkspaceSnapshot:
    source_count: int
    page_count: int
    pages: list[PageSnapshot]

    def __post_init__(self):
        if self.source_count < 0:
            raise ValueError("source_count must be >= 0")
        if self.page_count < 0:
            raise ValueError("page_count must be >= 0")

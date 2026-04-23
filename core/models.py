from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import uuid


@dataclass(slots=True)
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

    @property
    def effective_rotation(self) -> int:
        return (self.base_rotation + self.rotation_delta) % 360


@dataclass(slots=True)
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


@dataclass(slots=True)
class ExportPage:
    source_path: Path
    source_page_index: int
    final_rotation: int
    source_doc_id: str
    source_page_label: str = ""


@dataclass(slots=True)
class ExportOptions:
    keep_metadata: bool = True
    keep_page_labels: bool = True
    keep_attachments: bool = True
    keep_forms: bool = True
    keep_bookmarks: bool = False
    metadata_policy: str = "first_pdf"


@dataclass(slots=True)
class WorkspaceSnapshot:
    source_count: int
    page_count: int
    pages: list[dict[str, Any]]


def new_id() -> str:
    return str(uuid.uuid4())

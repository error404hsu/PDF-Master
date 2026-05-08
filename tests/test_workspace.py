from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from core.export_service import ExportService
from core.models import ExportOptions, PdfInspectionResult
from core.thumbnail_service import ThumbnailService
from core.workspace import WorkspaceManager


class FakeBackend:
    def __init__(self):
        self.render_calls = []
        self.export_calls = []
        self.catalog = {
            Path("A.pdf"): PdfInspectionResult(
                path=Path("A.pdf"),
                page_count=3,
                metadata={"title": "Doc A", "author": "Tester A"},
                page_labels=[{"startpage": 0, "prefix": "A-", "style": "D", "firstpagenum": 1}],
                page_rotations=[0, 0, 0],
            ),
            Path("B.pdf"): PdfInspectionResult(
                path=Path("B.pdf"),
                page_count=2,
                metadata={"title": "Doc B", "author": "Tester B"},
                page_labels=[{"startpage": 0, "prefix": "B-", "style": "D", "firstpagenum": 1}],
                page_rotations=[0, 90],
                encrypted=True,
            ),
        }

    def inspect_pdf(self, path: Path) -> PdfInspectionResult:
        return self.catalog[Path(path)]

    def render_thumbnail(self, source_path: Path, page_index: int, final_rotation: int, output_path: Path, zoom: float = 0.4) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps({
            "source_path": str(source_path),
            "page_index": page_index,
            "final_rotation": final_rotation,
            "zoom": zoom,
        }), encoding="utf-8")
        self.render_calls.append((source_path, page_index, final_rotation, output_path, zoom))
        return output_path

    def export_pages(self, pages, output_path: Path, options, source_info):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "pages": [
                {
                    "source": str(p.source_path),
                    "source_page_index": p.source_page_index,
                    "final_rotation": p.final_rotation,
                    "label": p.source_page_label,
                }
                for p in pages
            ],
            "options": {
                "keep_metadata": options.keep_metadata,
                "keep_page_labels": options.keep_page_labels,
                "keep_attachments": options.keep_attachments,
                "keep_forms": options.keep_forms,
                "keep_bookmarks": options.keep_bookmarks,
                "metadata_policy": options.metadata_policy,
            },
            "source_count": len(source_info),
        }
        output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        self.export_calls.append(payload)
        return output_path


class WorkspaceManagerTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.backend = FakeBackend()
        self.workspace = WorkspaceManager(self.backend, Path(self.temp_dir.name) / "thumbs")
        self.workspace.open_pdfs(["A.pdf", "B.pdf"])

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_open_pdfs_flattens_pages(self):
        snapshot = self.workspace.snapshot()
        self.assertEqual(snapshot.source_count, 2)
        self.assertEqual(snapshot.page_count, 5)
        self.assertEqual(snapshot.pages[0]["label"], "A-1")
        self.assertEqual(snapshot.pages[3]["label"], "B-1")
        self.assertEqual(snapshot.pages[4]["effective_rotation"], 90)

    def test_move_pages_cross_document(self):
        self.workspace.move_pages([3], 1)
        snapshot = self.workspace.snapshot()
        self.assertEqual(snapshot.pages[1]["source"], "B.pdf")
        self.assertEqual(snapshot.pages[1]["source_page_index"], 0)

    def test_remove_pages_is_hard_delete(self):
        self.workspace.remove_pages([1, 4])
        snapshot = self.workspace.snapshot()
        self.assertEqual(snapshot.page_count, 3)
        remaining = [(row["source"], row["source_page_index"]) for row in snapshot.pages]
        self.assertEqual(remaining, [("A.pdf", 0), ("A.pdf", 2), ("B.pdf", 0)])

    def test_rotate_pages_updates_effective_rotation(self):
        self.workspace.rotate_pages([1, 4], 90)
        snapshot = self.workspace.snapshot()
        self.assertEqual(snapshot.pages[1]["effective_rotation"], 90)
        self.assertEqual(snapshot.pages[4]["effective_rotation"], 180)

    def test_thumbnail_uses_current_rotation(self):
        self.workspace.rotate_pages([4], 180)
        service = ThumbnailService(self.workspace)
        out = service.render_one(4)
        data = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(data["final_rotation"], 270)

    def test_render_thumbnail_to_disk_leaves_thumb_path_unset(self):
        page = self.workspace.pages[0]
        self.assertIsNone(page.thumb_path)
        path = self.workspace.render_thumbnail_to_disk(
            page_id=page.page_id,
            source_path=page.source_path,
            source_page_index=page.source_page_index,
            final_rotation=page.effective_rotation,
            zoom=0.2,
        )
        self.assertTrue(path.exists())
        self.assertIsNone(page.thumb_path)

    def test_export_plan_follows_workspace_order(self):
        self.workspace.move_pages([3], 1)
        self.workspace.remove_pages([4])
        self.workspace.rotate_pages([1], 90)
        service = ExportService(self.workspace)
        out = service.export(Path(self.temp_dir.name) / "merged.json", ExportOptions(keep_bookmarks=False))
        payload = json.loads(out.read_text(encoding="utf-8"))
        ordered = [(row["source"], row["source_page_index"], row["final_rotation"]) for row in payload["pages"]]
        self.assertEqual(
            ordered,
            [("A.pdf", 0, 0), ("B.pdf", 0, 90), ("A.pdf", 1, 0), ("A.pdf", 2, 0)],
        )
        self.assertFalse(payload["options"]["keep_bookmarks"])

    def test_encrypted_used_sources_all_pages(self):
        enc = self.workspace.encrypted_used_sources()
        self.assertEqual(len(enc), 1)
        self.assertEqual(enc[0].path, Path("B.pdf"))

    def test_encrypted_used_sources_respects_row_subset(self):
        enc = self.workspace.encrypted_used_sources([0, 1, 2])
        self.assertEqual(enc, [])

    def test_export_metadata_policy_last_pdf_option(self):
        opts = ExportOptions(keep_metadata=True, metadata_policy="last_pdf", keep_bookmarks=False)
        service = ExportService(self.workspace)
        out = service.export(Path(self.temp_dir.name) / "meta.json", opts)
        payload = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(payload["options"]["metadata_policy"], "last_pdf")


if __name__ == "__main__":
    unittest.main()

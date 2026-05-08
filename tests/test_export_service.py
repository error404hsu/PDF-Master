"""tests/test_export_service.py

洪蓋 ExportService 所有公開方法與邊界條件。
使用 FakeBackend，不啟動真實 PyMuPDF 或 Qt。
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from core.export_service import ExportService
from core.models import ExportOptions, PdfInspectionResult
from core.workspace import WorkspaceManager


class FakeBackend:
    """FakeBackend 共用於本檔所有測試，不依賴 PyMuPDF。"""

    def __init__(self) -> None:
        self.export_calls: list[dict] = []
        self.catalog: dict[Path, PdfInspectionResult] = {
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
        if Path(path) not in self.catalog:
            raise FileNotFoundError(f"FakeBackend: 找不到 {path}")
        return self.catalog[Path(path)]

    def render_thumbnail(
        self,
        source_path: Path,
        page_index: int,
        final_rotation: int,
        output_path: Path,
        zoom: float = 0.4,
    ) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("", encoding="utf-8")
        return output_path

    def export_pages(
        self,
        pages: list,
        output_path: Path,
        options: ExportOptions,
        source_info: list,
    ) -> Path:
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
        output_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        self.export_calls.append(payload)
        return output_path


class ExportServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.backend = FakeBackend()
        self.workspace = WorkspaceManager(self.backend)
        self.workspace.open_pdfs(["A.pdf", "B.pdf"])
        self.service = ExportService(self.workspace)
        self.out_dir = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    # ------------------------------------------------------------------
    # export() 全頁匯出
    # ------------------------------------------------------------------

    def test_export_all_pages_count(self) -> None:
        out = self.service.export(self.out_dir / "all.json", ExportOptions())
        data = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(len(data["pages"]), 5)  # A(3) + B(2)

    def test_export_preserves_page_order(self) -> None:
        out = self.service.export(self.out_dir / "order.json", ExportOptions())
        data = json.loads(out.read_text(encoding="utf-8"))
        sources = [(p["source"], p["source_page_index"]) for p in data["pages"]]
        expected = [
            ("A.pdf", 0), ("A.pdf", 1), ("A.pdf", 2),
            ("B.pdf", 0), ("B.pdf", 1),
        ]
        # 路徑分隔符差異消彍：只比尾檔名
        result = [(Path(s).name, i) for s, i in sources]
        self.assertEqual(result, expected)

    def test_export_rotation_applied(self) -> None:
        # B.pdf 第二頁 base_rotation=90
        out = self.service.export(self.out_dir / "rot.json", ExportOptions())
        data = json.loads(out.read_text(encoding="utf-8"))
        b_second = data["pages"][4]  # index 4 = B.pdf page index 1
        self.assertEqual(b_second["final_rotation"], 90)

    def test_export_adds_pdf_suffix_if_missing(self) -> None:
        out = self.service.export(self.out_dir / "out", ExportOptions())
        self.assertEqual(out.suffix, ".pdf")

    def test_export_options_keep_bookmarks_false(self) -> None:
        opts = ExportOptions(keep_bookmarks=False)
        out = self.service.export(self.out_dir / "bk.json", opts)
        data = json.loads(out.read_text(encoding="utf-8"))
        self.assertFalse(data["options"]["keep_bookmarks"])

    def test_export_options_metadata_policy_last_pdf(self) -> None:
        opts = ExportOptions(metadata_policy="last_pdf")
        out = self.service.export(self.out_dir / "meta.json", opts)
        data = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(data["options"]["metadata_policy"], "last_pdf")

    def test_export_empty_workspace_raises(self) -> None:
        empty_ws = WorkspaceManager(self.backend)
        svc = ExportService(empty_ws)
        with self.assertRaises(Exception):
            svc.export(self.out_dir / "empty.json", ExportOptions())

    # ------------------------------------------------------------------
    # export_selected()
    # ------------------------------------------------------------------

    def test_export_selected_correct_pages(self) -> None:
        out = self.service.export_selected(
            [0, 2], self.out_dir / "sel.json", ExportOptions()
        )
        data = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(len(data["pages"]), 2)
        result = [(Path(p["source"]).name, p["source_page_index"]) for p in data["pages"]]
        self.assertEqual(result, [("A.pdf", 0), ("A.pdf", 2)])

    def test_export_selected_restores_workspace_after(self) -> None:
        original_count = len(self.workspace.pages)
        self.service.export_selected(
            [0, 1], self.out_dir / "sel2.json", ExportOptions()
        )
        self.assertEqual(len(self.workspace.pages), original_count)

    def test_export_selected_empty_indices_raises(self) -> None:
        with self.assertRaises(ValueError):
            self.service.export_selected([], self.out_dir / "none.json", ExportOptions())

    def test_export_selected_out_of_range_raises(self) -> None:
        with self.assertRaises(Exception):
            self.service.export_selected(
                [99], self.out_dir / "oor.json", ExportOptions()
            )

    # ------------------------------------------------------------------
    # can_export()
    # ------------------------------------------------------------------

    def test_can_export_true_when_pages_exist(self) -> None:
        self.assertTrue(self.service.can_export())

    def test_can_export_false_when_empty(self) -> None:
        empty_ws = WorkspaceManager(self.backend)
        svc = ExportService(empty_ws)
        self.assertFalse(svc.can_export())


class ExportOptionsValidationTests(unittest.TestCase):
    """洪蓋 ExportOptions 死角测試。"""

    def test_default_values(self) -> None:
        opts = ExportOptions()
        self.assertTrue(opts.keep_metadata)
        self.assertTrue(opts.keep_page_labels)
        self.assertTrue(opts.keep_attachments)
        self.assertTrue(opts.keep_forms)
        self.assertFalse(opts.keep_bookmarks)
        self.assertEqual(opts.metadata_policy, "first_pdf")

    def test_invalid_metadata_policy_raises(self) -> None:
        with self.assertRaises(ValueError):
            ExportOptions(metadata_policy="invalid")  # type: ignore[arg-type]

    def test_all_valid_policies(self) -> None:
        for policy in ("first_pdf", "last_pdf", "empty"):
            opts = ExportOptions(metadata_policy=policy)  # type: ignore[arg-type]
            self.assertEqual(opts.metadata_policy, policy)

    def test_keep_metadata_false(self) -> None:
        opts = ExportOptions(keep_metadata=False)
        self.assertFalse(opts.keep_metadata)

    def test_frozen_immutable(self) -> None:
        opts = ExportOptions()
        with self.assertRaises((AttributeError, TypeError)):
            opts.keep_metadata = False  # type: ignore[misc]


if __name__ == "__main__":
    unittest.main()

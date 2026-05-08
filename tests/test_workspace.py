"""tests/test_workspace.py

覆蓋 WorkspaceManager 各公開方法與邊界條件。
使用 FakeBackend，不啟動真實 PyMuPDF 或 Qt。
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from core.export_service import ExportService
from core.models import ExportOptions, ImageInspectionResult, PageSnapshot, PdfInspectionResult
from core.thumbnail_service import ThumbnailService
from core.workspace import WorkspaceManager


class FakeBackend:
    def __init__(self) -> None:
        self.render_calls: list = []
        self.export_calls: list = []
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
        self.image_catalog: dict[Path, ImageInspectionResult] = {
            Path("photo.jpg"): ImageInspectionResult(
                path=Path("photo.jpg"),
                page_count=1,
                width_px=1920,
                height_px=1080,
                format="jpeg",
            ),
            Path("scan.tiff"): ImageInspectionResult(
                path=Path("scan.tiff"),
                page_count=3,
                width_px=2480,
                height_px=3508,
                format="tiff",
            ),
        }

    def inspect_pdf(self, path: Path) -> PdfInspectionResult:
        p = Path(path)
        if p not in self.catalog:
            raise FileNotFoundError(f"FakeBackend: 找不到 {path}")
        return self.catalog[p]

    def inspect_image(self, path: Path) -> ImageInspectionResult:
        p = Path(path)
        if p not in self.image_catalog:
            raise FileNotFoundError(f"FakeBackend: 找不到圖片 {path}")
        return self.image_catalog[p]

    def render_thumbnail(
        self,
        source_path: Path,
        page_index: int,
        final_rotation: int,
        output_path: Path,
        zoom: float = 0.4,
    ) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps({
                "source_path": str(source_path),
                "page_index": page_index,
                "final_rotation": final_rotation,
                "zoom": zoom,
            }),
            encoding="utf-8",
        )
        self.render_calls.append((source_path, page_index, final_rotation, output_path, zoom))
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


class WorkspaceManagerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.backend = FakeBackend()
        # WorkspaceManager 不再接受 thumbnail_dir
        self.workspace = WorkspaceManager(self.backend)
        self.thumb_service = ThumbnailService(
            self.workspace, Path(self.temp_dir.name) / "thumbs"
        )
        self.workspace.open_pdfs(["A.pdf", "B.pdf"])

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    # ------------------------------------------------------------------
    # 基本快照與頁面清單
    # ------------------------------------------------------------------

    def test_open_pdfs_flattens_pages(self) -> None:
        snapshot = self.workspace.snapshot()
        self.assertEqual(snapshot.source_count, 2)
        self.assertEqual(snapshot.page_count, 5)
        self.assertEqual(snapshot.pages[0]["label"], "A-1")
        self.assertEqual(snapshot.pages[3]["label"], "B-1")
        self.assertEqual(snapshot.pages[4]["effective_rotation"], 90)

    def test_snapshot_pages_are_page_snapshot_instances(self) -> None:
        snap = self.workspace.snapshot()
        for page in snap.pages:
            self.assertIsInstance(page, PageSnapshot)

    def test_snapshot_page_snapshot_field_access(self) -> None:
        snap = self.workspace.snapshot()
        p = snap.pages[0]
        # 屬性存取
        self.assertEqual(p.label, "A-1")
        self.assertEqual(p.index, 0)
        self.assertEqual(p.source, "A.pdf")
        # __getitem__ 向後相容
        self.assertEqual(p["label"], "A-1")
        self.assertEqual(p["effective_rotation"], 0)

    # ------------------------------------------------------------------
    # open_pdfs / open_files 回傳元組
    # ------------------------------------------------------------------

    def test_open_pdfs_returns_tuple(self) -> None:
        ws = WorkspaceManager(self.backend)
        result = ws.open_pdfs(["A.pdf"])
        self.assertIsInstance(result, tuple)
        added, failed = result
        self.assertIsInstance(added, list)
        self.assertIsInstance(failed, list)

    def test_open_pdfs_all_success(self) -> None:
        ws = WorkspaceManager(self.backend)
        added, failed = ws.open_pdfs(["A.pdf", "B.pdf"])
        self.assertEqual(len(added), 2)
        self.assertEqual(failed, [])

    def test_open_pdfs_partial_failure(self) -> None:
        ws = WorkspaceManager(self.backend)
        added, failed = ws.open_pdfs(["A.pdf", "nonexistent.pdf"])
        self.assertEqual(len(added), 1)
        self.assertEqual(len(failed), 1)
        self.assertEqual(failed[0], Path("nonexistent.pdf"))

    def test_open_pdfs_all_fail(self) -> None:
        ws = WorkspaceManager(self.backend)
        added, failed = ws.open_pdfs(["bad1.pdf", "bad2.pdf"])
        self.assertEqual(added, [])
        self.assertEqual(len(failed), 2)
        self.assertEqual(ws.pages, [])

    def test_open_pdfs_empty_input(self) -> None:
        ws = WorkspaceManager(self.backend)
        added, failed = ws.open_pdfs([])
        self.assertEqual(added, [])
        self.assertEqual(failed, [])

    # ------------------------------------------------------------------
    # 圖片轉 PDF — open_files() 測試
    # ------------------------------------------------------------------

    def test_open_files_jpg_produces_one_page(self) -> None:
        """傳入 JPG 應正常產生一頁。"""
        ws = WorkspaceManager(self.backend)
        added, failed = ws.open_files(["photo.jpg"])
        self.assertEqual(len(added), 1)
        self.assertEqual(failed, [])
        self.assertEqual(len(ws.pages), 1)
        snap = ws.snapshot()
        self.assertEqual(snap.pages[0].source, "photo.jpg")
        self.assertEqual(snap.pages[0].source_page_index, 0)

    def test_open_files_multipage_tiff_produces_correct_page_count(self) -> None:
        """傳入多頁 TIFF 應產生對應幀數的頁面。"""
        ws = WorkspaceManager(self.backend)
        added, failed = ws.open_files(["scan.tiff"])
        self.assertEqual(len(added), 1)
        self.assertEqual(failed, [])
        self.assertEqual(len(ws.pages), 3)
        snap = ws.snapshot()
        # 確認每一幀都對應正確的 source_page_index
        for i in range(3):
            self.assertEqual(snap.pages[i].source_page_index, i)
            self.assertEqual(snap.pages[i].source, "scan.tiff")

    def test_open_files_mixed_pdf_and_image(self) -> None:
        """混入 PDF + JPG，頁序應和呼叫順序一致。"""
        ws = WorkspaceManager(self.backend)
        added, failed = ws.open_files(["A.pdf", "photo.jpg"])
        self.assertEqual(len(added), 2)  # 一個 PDF doc_id + 一個 image doc_id
        self.assertEqual(failed, [])
        # A.pdf 有 3 頁，photo.jpg 有 1 頁
        self.assertEqual(len(ws.pages), 4)
        snap = ws.snapshot()
        self.assertEqual(snap.pages[0].source, "A.pdf")
        self.assertEqual(snap.pages[3].source, "photo.jpg")

    def test_open_files_corrupted_image_listed_in_failed(self) -> None:
        """損壞圖片應列入 failed_paths，不中斷其餘對象。"""
        ws = WorkspaceManager(self.backend)
        # broken.png 不在 image_catalog 中，會拋出 FileNotFoundError
        added, failed = ws.open_files(["A.pdf", "broken.png"])
        self.assertEqual(len(added), 1)   # A.pdf 成功
        self.assertEqual(len(failed), 1)
        self.assertEqual(failed[0], Path("broken.png"))
        self.assertEqual(len(ws.pages), 3)  # 只有 A.pdf 的 3 頁

    def test_open_files_open_pdfs_backward_compat(self) -> None:
        """open_pdfs() 委派至 open_files()，行為不變。"""
        ws = WorkspaceManager(self.backend)
        added_via_open_files, _ = ws.open_files(["A.pdf"])

        ws2 = WorkspaceManager(self.backend)
        added_via_open_pdfs, _ = ws2.open_pdfs(["A.pdf"])

        self.assertEqual(len(added_via_open_files), len(added_via_open_pdfs))
        self.assertEqual(len(ws.pages), len(ws2.pages))

    # ------------------------------------------------------------------
    # 頁面操作
    # ------------------------------------------------------------------

    def test_move_pages_cross_document(self) -> None:
        self.workspace.move_pages([3], 1)
        snapshot = self.workspace.snapshot()
        self.assertEqual(snapshot.pages[1]["source"], "B.pdf")
        self.assertEqual(snapshot.pages[1]["source_page_index"], 0)

    def test_remove_pages_is_hard_delete(self) -> None:
        self.workspace.remove_pages([1, 4])
        snapshot = self.workspace.snapshot()
        self.assertEqual(snapshot.page_count, 3)
        remaining = [
            (row["source"], row["source_page_index"]) for row in snapshot.pages
        ]
        self.assertEqual(remaining, [("A.pdf", 0), ("A.pdf", 2), ("B.pdf", 0)])

    def test_rotate_pages_updates_effective_rotation(self) -> None:
        self.workspace.rotate_pages([1, 4], 90)
        snapshot = self.workspace.snapshot()
        self.assertEqual(snapshot.pages[1]["effective_rotation"], 90)
        self.assertEqual(snapshot.pages[4]["effective_rotation"], 180)

    def test_rotate_invalid_angle_raises(self) -> None:
        from core.exceptions import InvalidRotationError
        with self.assertRaises(InvalidRotationError):
            self.workspace.rotate_pages([0], 45)

    def test_move_pages_out_of_range_target_raises(self) -> None:
        from core.exceptions import InvalidMoveError
        with self.assertRaises(InvalidMoveError):
            self.workspace.move_pages([0], 999)

    def test_remove_pages_out_of_range_raises(self) -> None:
        from core.exceptions import WorkspaceError
        with self.assertRaises(WorkspaceError):
            self.workspace.remove_pages([99])

    def test_remove_pages_empty_noop(self) -> None:
        before = len(self.workspace.pages)
        self.workspace.remove_pages([])
        self.assertEqual(len(self.workspace.pages), before)

    def test_move_pages_empty_noop(self) -> None:
        before = [p.page_id for p in self.workspace.pages]
        self.workspace.move_pages([], 0)
        after = [p.page_id for p in self.workspace.pages]
        self.assertEqual(before, after)

    # ------------------------------------------------------------------
    # 縮圖服務（透過 ThumbnailService）
    # ------------------------------------------------------------------

    def test_thumbnail_uses_current_rotation(self) -> None:
        self.workspace.rotate_pages([4], 180)
        out = self.thumb_service.render_one(4)
        data = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(data["final_rotation"], 270)

    def test_render_thumbnail_to_disk_leaves_thumb_path_unset(self) -> None:
        page = self.workspace.pages[0]
        self.assertIsNone(page.thumb_path)
        thumb_dir = Path(self.temp_dir.name) / "thumbs"
        path = self.workspace.render_thumbnail_to_disk(
            page_id=page.page_id,
            source_path=page.source_path,
            source_page_index=page.source_page_index,
            final_rotation=page.effective_rotation,
            zoom=0.2,
            output_path=thumb_dir / f"{page.page_id}.png",
        )
        self.assertTrue(path.exists())
        self.assertIsNone(page.thumb_path)  # 不應被修改

    # ------------------------------------------------------------------
    # 匯出計畫
    # ------------------------------------------------------------------

    def test_export_plan_follows_workspace_order(self) -> None:
        self.workspace.move_pages([3], 1)
        self.workspace.remove_pages([4])
        self.workspace.rotate_pages([1], 90)
        service = ExportService(self.workspace)
        out = service.export(
            Path(self.temp_dir.name) / "merged.json", ExportOptions(keep_bookmarks=False)
        )
        payload = json.loads(out.read_text(encoding="utf-8"))
        ordered = [
            (Path(row["source"]).name, row["source_page_index"], row["final_rotation"])
            for row in payload["pages"]
        ]
        self.assertEqual(
            ordered,
            [("A.pdf", 0, 0), ("B.pdf", 0, 90), ("A.pdf", 1, 0), ("A.pdf", 2, 0)],
        )
        self.assertFalse(payload["options"]["keep_bookmarks"])

    # ------------------------------------------------------------------
    # 加密來源
    # ------------------------------------------------------------------

    def test_encrypted_used_sources_all_pages(self) -> None:
        enc = self.workspace.encrypted_used_sources()
        self.assertEqual(len(enc), 1)
        self.assertEqual(enc[0].path, Path("B.pdf"))

    def test_encrypted_used_sources_respects_row_subset(self) -> None:
        enc = self.workspace.encrypted_used_sources([0, 1, 2])
        self.assertEqual(enc, [])

    def test_export_metadata_policy_last_pdf_option(self) -> None:
        opts = ExportOptions(keep_metadata=True, metadata_policy="last_pdf", keep_bookmarks=False)
        service = ExportService(self.workspace)
        out = service.export(Path(self.temp_dir.name) / "meta.json", opts)
        payload = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(payload["options"]["metadata_policy"], "last_pdf")


class ExpandLabelsTests(unittest.TestCase):
    """_expand_labels() 幾何構型全樣單元測試。"""

    def _expand(self, page_count: int, rules: list) -> list:
        return WorkspaceManager._expand_labels(page_count, rules)

    def test_empty_rules_returns_empty_strings(self) -> None:
        self.assertEqual(self._expand(3, []), ["", "", ""])

    def test_none_rules_returns_empty_strings(self) -> None:
        self.assertEqual(self._expand(3, None), ["", "", ""])  # type: ignore[arg-type]

    def test_zero_page_count_returns_empty(self) -> None:
        self.assertEqual(self._expand(0, [{"startpage": 0, "style": "D"}]), [])

    def test_decimal_style(self) -> None:
        result = self._expand(3, [{"startpage": 0, "style": "D", "firstpagenum": 1}])
        self.assertEqual(result, ["1", "2", "3"])

    def test_decimal_with_prefix(self) -> None:
        result = self._expand(3, [{"startpage": 0, "prefix": "p.", "style": "D", "firstpagenum": 1}])
        self.assertEqual(result, ["p.1", "p.2", "p.3"])

    def test_roman_upper(self) -> None:
        result = self._expand(4, [{"startpage": 0, "style": "R", "firstpagenum": 1}])
        self.assertEqual(result, ["I", "II", "III", "IV"])

    def test_roman_lower(self) -> None:
        result = self._expand(4, [{"startpage": 0, "style": "r", "firstpagenum": 1}])
        self.assertEqual(result, ["i", "ii", "iii", "iv"])

    def test_alpha_upper(self) -> None:
        result = self._expand(3, [{"startpage": 0, "style": "A", "firstpagenum": 1}])
        self.assertEqual(result, ["A", "B", "C"])

    def test_alpha_lower(self) -> None:
        result = self._expand(3, [{"startpage": 0, "style": "a", "firstpagenum": 1}])
        self.assertEqual(result, ["a", "b", "c"])

    def test_unknown_style_prefix_only(self) -> None:
        result = self._expand(2, [{"startpage": 0, "prefix": "Intro-", "style": ""}])
        self.assertEqual(result, ["Intro-", "Intro-"])

    def test_multiple_rules_segments(self) -> None:
        rules = [
            {"startpage": 0, "style": "r", "firstpagenum": 1},
            {"startpage": 3, "prefix": "p.", "style": "D", "firstpagenum": 1},
        ]
        result = self._expand(6, rules)
        self.assertEqual(result, ["i", "ii", "iii", "p.1", "p.2", "p.3"])

    def test_rule_missing_startpage_ignored(self) -> None:
        rules = [{"prefix": "X-", "style": "D"}]  # 缺少 startpage
        result = self._expand(3, rules)
        self.assertEqual(result, ["", "", ""])

    def test_startpage_out_of_range_ignored(self) -> None:
        rules = [{"startpage": 10, "style": "D", "firstpagenum": 1}]
        result = self._expand(3, rules)
        self.assertEqual(result, ["", "", ""])

    def test_firstpagenum_offset(self) -> None:
        result = self._expand(3, [{"startpage": 0, "style": "D", "firstpagenum": 5}])
        self.assertEqual(result, ["5", "6", "7"])


if __name__ == "__main__":
    unittest.main()

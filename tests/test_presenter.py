"""tests/test_presenter.py

Presenter 單元測試—不啟動 Qt GUI。
MockView 實作 IMainView Protocol，用 unittest.mock 模擬業務服務。
"""
from __future__ import annotations

import copy
from typing import List
from unittest.mock import MagicMock, call, patch

import pytest

from gui.interfaces import IMainView
from gui.models import SnapshotHistory


# ---------------------------------------------------------------------------
# MockView — 实作 IMainView，不依賴 QWidget
# ---------------------------------------------------------------------------

class MockView:
    """IMainView 的純 Python Mock 實作，不啟動 Qt。"""

    def __init__(self) -> None:
        self._selected_rows: list[int] = []
        self.errors: list[tuple[str, str]] = []
        self.statuses: list[str] = []
        self.refresh_count: int = 0

    # IMainView 介面
    def show_error(self, title: str, msg: str) -> None:
        self.errors.append((title, msg))

    def set_status(self, text: str) -> None:
        self.statuses.append(text)

    def refresh_view(self) -> None:
        self.refresh_count += 1

    def get_selected_rows(self) -> list[int]:
        return self._selected_rows

    # 測試輔助
    def set_selection(self, rows: list[int]) -> None:
        self._selected_rows = rows


assert isinstance(MockView(), IMainView), "MockView 必須满足 IMainView Protocol"


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_workspace():
    ws = MagicMock()
    ws.pages = []
    ws.encrypted_used_sources = MagicMock(return_value=[])
    return ws


@pytest.fixture
def mock_model():
    model = MagicMock()
    model.rowCount.return_value = 0
    return model


@pytest.fixture
def presenter(mock_workspace, mock_model):
    """?返回一組 (MockView, MainPresenter)。"""
    # 延遲 import presenter 以避免 Qt 對象建立
    from gui.presenter import MainPresenter

    view = MockView()
    history = SnapshotHistory(max_entries=20)
    backend = MagicMock()
    export_service = MagicMock()

    p = MainPresenter(
        view=view,
        workspace=mock_workspace,
        backend=backend,
        export_service=export_service,
        model=mock_model,
        history=history,
    )
    return view, p


# ---------------------------------------------------------------------------
# 測試情境
# ---------------------------------------------------------------------------

class TestLoadPdfs:
    def test_empty_list_is_noop(self, presenter):
        """load_pdfs([]) 不應觸發任何 workspace 操作。"""
        view, p = presenter
        p._workspace.open_pdfs = MagicMock()
        p.load_pdfs([])
        p._workspace.open_pdfs.assert_not_called()
        assert view.refresh_count == 0

    def test_non_pdf_files_filtered(self, presenter):
        """load_pdfs 應過濾掞 PDF 從檔案。"""
        view, p = presenter
        p._workspace.open_pdfs = MagicMock()
        p.load_pdfs(["image.png", "doc.txt"])
        p._workspace.open_pdfs.assert_not_called()

    def test_valid_pdf_list_calls_open_pdfs(self, presenter):
        """load_pdfs 傳入有效 PDF 清單時應呼叫 open_pdfs 並更新 view。"""
        view, p = presenter
        p._workspace.pages = []
        p._workspace.open_pdfs = MagicMock()
        p._model.refresh_all = MagicMock()

        p.load_pdfs(["a.pdf", "b.pdf"])

        p._workspace.open_pdfs.assert_called_once_with(["a.pdf", "b.pdf"])
        p._model.refresh_all.assert_called_once()
        assert view.refresh_count == 1

    def test_open_pdfs_exception_calls_show_error(self, presenter):
        """open_pdfs 將廣异常時，view.show_error 應被呼叫。"""
        view, p = presenter
        p._workspace.open_pdfs = MagicMock(side_effect=RuntimeError("文件損壞"))
        p.load_pdfs(["bad.pdf"])
        assert len(view.errors) == 1
        assert view.errors[0][0] == "開啟 PDF 失敗"


class TestOnRotatePages:
    def test_no_selection_is_noop(self, presenter):
        """on_rotate_pages 無選取時應為 no-op。"""
        view, p = presenter
        view.set_selection([])
        p._workspace.rotate_pages = MagicMock()
        p.on_rotate_pages(90)
        p._workspace.rotate_pages.assert_not_called()

    def test_with_selection_calls_rotate(self, presenter):
        """on_rotate_pages 有選取時應呼叫 workspace.rotate_pages。"""
        view, p = presenter
        view.set_selection([0, 2])
        p._workspace.pages = [MagicMock(), MagicMock(), MagicMock()]
        p._workspace.rotate_pages = MagicMock()
        p._model.invalidate_rows = MagicMock()
        p._model.start_thumbnail_worker = MagicMock()
        p.on_rotate_pages(90)
        p._workspace.rotate_pages.assert_called_once_with([0, 2], 90)


class TestUndo:
    def test_undo_empty_history_no_refresh(self, presenter):
        """undo 在空歷史時不應呼叫 refresh_view。"""
        view, p = presenter
        initial_refresh = view.refresh_count
        p.undo()
        assert view.refresh_count == initial_refresh

    def test_undo_with_history_calls_refresh(self, presenter):
        """undo 有歷史時應呼叫 refresh_view。"""
        view, p = presenter
        # 模擬一次操作以產生歷史
        p._workspace.pages = [MagicMock()]
        snapshot = copy.deepcopy(p._workspace.pages)
        p._history.push_snapshot(snapshot)
        p._workspace.pages = [MagicMock(), MagicMock()]  # 改變後狀態
        p._model.refresh_all = MagicMock()

        p.undo()

        p._model.refresh_all.assert_called_once()
        assert view.refresh_count >= 1


class TestRedo:
    def test_redo_empty_history_no_refresh(self, presenter):
        """redo 在空歷史時不應呼叫 refresh_view。"""
        view, p = presenter
        initial_refresh = view.refresh_count
        p.redo()
        assert view.refresh_count == initial_refresh

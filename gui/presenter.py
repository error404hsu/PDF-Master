"""gui/presenter.py — MainPresenter

Presenter 層：接受 IMainView、workspace、backend、export_service，
負責所有 on_* / load_pdfs / undo / redo 業務邏輯。

限制：本模組不得 import 任何 QWidget 子類別。
"""
from __future__ import annotations

import copy
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QModelIndex, QThreadPool
from PySide6.QtWidgets import QApplication, QDialog, QFileDialog, QMessageBox
from PySide6.QtCore import Qt

from gui.dialogs import ExportPdfDialog, PreviewDialog
from gui.interfaces import IMainView
from gui.models import PAGE_ROLE, SnapshotHistory
from gui.workers import HighResWorker

if TYPE_CHECKING:
    from core.workspace import WorkspaceManager
    from adapters.pymupdf_backend import PyMuPdfBackend
    from core.export_service import ExportService
    from gui.models import PdfPageModel

logger = logging.getLogger(__name__)


class MainPresenter:
    """MVP Presenter — 所有業務邏輯層。"""

    def __init__(
        self,
        view: IMainView,
        workspace: "WorkspaceManager",
        backend: "PyMuPdfBackend",
        export_service: "ExportService",
        model: "PdfPageModel",
        history: SnapshotHistory,
    ) -> None:
        self._view = view
        self._workspace = workspace
        self._backend = backend
        self._export_service = export_service
        self._model = model
        self._history = history
        self._thread_pool = QThreadPool.globalInstance()

    # ------------------------------------------------------------------
    # 內部輔助
    # ------------------------------------------------------------------

    def _capture_before_change(self) -> list:
        return copy.deepcopy(self._workspace.pages)

    def _commit_history(self, before_snapshot: list) -> None:
        self._history.push_snapshot(before_snapshot)
        self._view.set_status(self._status_text())
        # 通知 View 更新按鈕狀態（透過 refresh_view 們汻完成）

    def _restore_pages(self, restored_pages) -> None:
        if restored_pages is None:
            return
        self._workspace.pages = restored_pages
        self._model.refresh_all()
        self._view.set_status(self._status_text())
        self._view.refresh_view()

    def _status_text(self) -> str:
        total = self._model.rowCount()
        selected = len(self._view.get_selected_rows())
        return f" 總計 {total} 頁 | 已選取 {selected} 頁"

    def _confirm_encrypted_sources(self, page_indices=None) -> bool:
        enc = self._workspace.encrypted_used_sources(page_indices)
        if not enc:
            return True
        names = "\n".join(f"• {s.path.name}" for s in enc)
        answer = QMessageBox.warning(
            None,
            "偉測到加密或需密碼的來源",
            "下列來源在編目時標示為加密文件。若未事先以密碼解鎖，合併結果可能不完整或匯出失敗：\n\n"
            f"{names}\n\n付要繼續匯出？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes

    # ------------------------------------------------------------------
    # 公開 API（對應原 MainWindow on_* 方法）
    # ------------------------------------------------------------------

    def load_pdfs(self, files: list[str]) -> None:
        files = [f for f in files if f.lower().endswith(".pdf")]
        if not files:
            return
        before = self._capture_before_change()
        try:
            self._workspace.open_pdfs(files)
        except Exception as e:
            self._view.show_error("開啟 PDF 失敗", str(e))
            return
        self._commit_history(before)
        self._model.refresh_all()
        self._view.set_status(self._status_text())
        self._view.refresh_view()

    def on_add_pdf(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(None, "開啟 PDF", "", "PDF 檔案 (*.pdf)")
        if files:
            self.load_pdfs(files)

    def on_add_folder(self) -> None:
        directory = QFileDialog.getExistingDirectory(None, "選擇含 PDF 的資料夾", "")
        if not directory:
            return
        root = Path(directory)
        files = sorted(
            str(p) for p in root.iterdir() if p.is_file() and p.suffix.lower() == ".pdf"
        )
        if not files:
            QMessageBox.information(
                None,
                "開啟資料夾",
                "此資料夾內沒有找到 PDF 檔案（僅揃掃一層目錄，不含子資料夾）。",
            )
            return
        self.load_pdfs(files)

    def on_pages_reordered(self, source_rows: list[int], target: int) -> None:
        if not source_rows:
            return
        before = self._capture_before_change()
        try:
            self._workspace.move_pages(source_rows, target)
        except Exception as e:
            self._view.show_error("移動頁面失敗", str(e))
            return
        self._commit_history(before)
        self._model.refresh_all()
        self._view.set_status(self._status_text())

    def on_page_double_clicked(self, index: QModelIndex) -> None:
        page = index.data(PAGE_ROLE)
        if page is None:
            return
        dialog = PreviewDialog(None)
        worker = HighResWorker(self._backend, page, f"第 {index.row() + 1} 頁")
        worker.signals.preview_ready.connect(dialog.update_image)
        worker.signals.preview_error.connect(dialog.show_error)
        self._thread_pool.start(worker)
        dialog.exec()

    def on_rotate_pages(self, angle: int) -> None:
        rows = self._view.get_selected_rows()
        if not rows:
            return
        before = self._capture_before_change()
        try:
            self._workspace.rotate_pages(rows, angle)
        except Exception as e:
            self._view.show_error("旋轉頁面失敗", str(e))
            return
        self._commit_history(before)
        self._model.invalidate_rows(rows)
        for row in rows:
            self._model.start_thumbnail_worker(row)
        self._view.set_status(self._status_text())

    def on_delete_pages(self) -> None:
        rows = self._view.get_selected_rows()
        if not rows:
            return
        before = self._capture_before_change()
        try:
            self._workspace.remove_pages(rows)
        except Exception as e:
            self._view.show_error("刪除頁面失敗", str(e))
            return
        self._commit_history(before)
        self._model.refresh_all()
        self._view.set_status(self._status_text())
        self._view.refresh_view()

    def on_export_pdf(self) -> None:
        if not self._workspace.pages:
            return
        dlg = ExportPdfDialog(None, export_subset=False)
        if dlg.exec() != QDialog.Accepted:
            return
        options = dlg.export_options()
        path, _ = QFileDialog.getSaveFileName(None, "匯出 PDF", "合併結果.pdf", "PDF 檔案 (*.pdf)")
        if not path:
            return
        if not self._confirm_encrypted_sources(None):
            return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            self._export_service.export(path, options)
            QMessageBox.information(None, "成功", f"匯出成功至：\n{path}")
        except Exception as e:
            self._view.show_error("匯出失敗", str(e))
        finally:
            QApplication.restoreOverrideCursor()

    def on_export_selected_pdf(self) -> None:
        rows = self._view.get_selected_rows()
        if not rows:
            QMessageBox.information(
                None,
                "匯出選取",
                "請先在縮圖區選取至少一頁，再使用「匯出選取」或 Ctrl+Shift+E。",
            )
            return
        dlg = ExportPdfDialog(None, export_subset=True)
        if dlg.exec() != QDialog.Accepted:
            return
        options = dlg.export_options()
        path, _ = QFileDialog.getSaveFileName(None, "匯出選取的頁面", "選取頁面.pdf", "PDF 檔案 (*.pdf)")
        if not path:
            return
        if not self._confirm_encrypted_sources(rows):
            return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            self._export_service.export_selected(rows, path, options)
            QMessageBox.information(None, "成功", f"已匯出 {len(rows)} 頁至：\n{path}")
        except Exception as e:
            self._view.show_error("匯出失敗", str(e))
        finally:
            QApplication.restoreOverrideCursor()

    def undo(self) -> None:
        restored_pages = self._history.undo(self._workspace.pages)
        self._restore_pages(restored_pages)

    def redo(self) -> None:
        restored_pages = self._history.redo(self._workspace.pages)
        self._restore_pages(restored_pages)

    # ------------------------------------------------------------------
    # 改變後更新按鈕可用狀態（由 View 實作預算）
    # ------------------------------------------------------------------

    def can_undo(self) -> bool:
        return self._history.can_undo()

    def can_redo(self) -> bool:
        return self._history.can_redo()

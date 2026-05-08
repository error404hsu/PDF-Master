# 主程式入口 — 僅保留 MainWindow 骨架與 main() 入口點
import sys
import os
import copy
import shutil
import logging
from pathlib import Path
from typing import List, Optional

from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QFileDialog,
    QLabel,
    QFrame,
    QDialog,
    QMessageBox,
)
from PySide6.QtCore import (
    Qt,
    QModelIndex,
    QThreadPool,
    QKeySequence,
)
from PySide6.QtGui import (
    QKeySequence,
    QShortcut,
    QFont,
    QDragEnterEvent,
    QDropEvent,
    QResizeEvent,
)

try:
    from core.workspace import WorkspaceManager
    from adapters.pymupdf_backend import PyMuPdfBackend
    from core.thumbnail_service import ThumbnailService
    from core.export_service import ExportService
except ImportError as e:
    print(f"匯入核心邏輯失敗，請確保 gui_main.py 放在專案根目錄。錯誤: {e}")
    sys.exit(1)

from gui.styles import UiStyles
from gui.workers import HighResWorker
from gui.dialogs import PreviewDialog, ExportPdfDialog
from gui.models import PdfPageModel, PAGE_ROLE, SnapshotHistory
from gui.views import PageListView, PageCardDelegate

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger("gui_main")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PDF排列哥 Pro")
        self.resize(1300, 800)
        self.setAcceptDrops(True)

        self.thumb_path = Path("./.thumbnails")
        self.thumb_path.mkdir(exist_ok=True)

        self.backend = PyMuPdfBackend()
        self.workspace = WorkspaceManager(self.backend, self.thumb_path)
        self.thumb_service = ThumbnailService(self.workspace)
        self.export_service = ExportService(self.workspace)

        self.thread_pool = QThreadPool.globalInstance()
        self.history = SnapshotHistory(max_entries=20)

        self._build_ui()
        self._connect_signals()
        self._setup_shortcuts()
        self._update_history_buttons()
        self.update_status()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        header = self._build_header()
        main_layout.addWidget(header)

        self.model = PdfPageModel(self.workspace, self.thumb_service)
        self.view = PageListView()
        self.view.setModel(self.model)
        self.view.setItemDelegate(PageCardDelegate())
        self.view.setStyleSheet(UiStyles.LIST_VIEW)
        main_layout.addWidget(self.view)

        self.footer = QLabel(
            " 辦公室合併：可批次加入資料夾內 PDF | Ctrl+A 全選 | Del 刪除 | "
            "Ctrl+Shift+E 匯出選取 | 雙擊預覽 | 拖曳排序"
        )
        self.footer.setFixedHeight(32)
        self.footer.setStyleSheet(UiStyles.FOOTER)
        main_layout.addWidget(self.footer)

    def _build_header(self):
        header = QFrame()
        header.setFixedHeight(62)
        header.setStyleSheet(
            f"background-color: {UiStyles.HEADER_BG}; "
            f"border-bottom: 1px solid {UiStyles.PANEL_BORDER};"
        )

        layout = QHBoxLayout(header)
        layout.setContentsMargins(15, 0, 15, 0)
        layout.setSpacing(10)

        title_label = QLabel("PDF排列哥")
        title_label.setStyleSheet(
            "font-weight: 900; font-size: 24pt; color: #1e40af; min-width: 160px;"
        )
        layout.addWidget(title_label)

        btn_w, btn_h = 88, 32

        self.btn_add = self._make_button("開啟檔案", btn_w, btn_h)
        self.btn_add_folder = self._make_button("開啟資料夾", 96, btn_h)
        layout.addWidget(self.btn_add)
        layout.addWidget(self.btn_add_folder)
        layout.addWidget(self._make_separator())

        self.btn_undo = self._make_button("復原", btn_w, btn_h)
        self.btn_redo = self._make_button("重做", btn_w, btn_h)
        layout.addWidget(self.btn_undo)
        layout.addWidget(self.btn_redo)
        layout.addWidget(self._make_separator())

        self.btn_rot_l = self._make_button("左轉 90°", btn_w, btn_h)
        self.btn_rot_180 = self._make_button("轉 180°", btn_w, btn_h)
        self.btn_rot_r = self._make_button("右轉 90°", btn_w, btn_h)
        self.btn_delete = self._make_button("刪除頁面", btn_w, btn_h, variant="danger")

        layout.addWidget(self.btn_rot_l)
        layout.addWidget(self.btn_rot_180)
        layout.addWidget(self.btn_rot_r)
        layout.addWidget(self.btn_delete)

        layout.addStretch()

        self.btn_export_sel = self._make_button("匯出選取", 96, 38)
        self.btn_export = self._make_button("匯出結果", 100, 38, variant="primary")
        layout.addWidget(self.btn_export_sel)
        layout.addWidget(self.btn_export)

        return header

    def _make_button(self, text: str, width: int, height: int, variant: str = "base"):
        btn = QPushButton(text)
        btn.setFixedSize(width, height)
        if variant == "danger":
            btn.setStyleSheet(UiStyles.DANGER_BUTTON)
        elif variant == "primary":
            btn.setStyleSheet(UiStyles.PRIMARY_BUTTON)
        else:
            btn.setStyleSheet(UiStyles.BASE_BUTTON)
        return btn

    def _make_separator(self):
        line = QFrame()
        line.setFrameShape(QFrame.VLine)
        line.setFixedHeight(24)
        line.setStyleSheet(f"color: {UiStyles.PANEL_BORDER};")
        return line

    def _connect_signals(self):
        self.btn_add.clicked.connect(self.on_add_pdf)
        self.btn_add_folder.clicked.connect(self.on_add_folder)
        self.btn_undo.clicked.connect(self.undo)
        self.btn_redo.clicked.connect(self.redo)
        self.btn_rot_l.clicked.connect(lambda: self.on_rotate_pages(-90))
        self.btn_rot_180.clicked.connect(lambda: self.on_rotate_pages(180))
        self.btn_rot_r.clicked.connect(lambda: self.on_rotate_pages(90))
        self.btn_delete.clicked.connect(self.on_delete_pages)
        self.btn_export_sel.clicked.connect(self.on_export_selected_pdf)
        self.btn_export.clicked.connect(self.on_export_pdf)

        self.view.doubleClicked.connect(self.on_page_double_clicked)
        self.view.pages_reordered.connect(self.on_pages_reordered)
        self.view.pdf_files_dropped.connect(self.load_pdfs)

        selection_model = self.view.selectionModel()
        if selection_model is not None:
            selection_model.selectionChanged.connect(self.update_status)

    def _setup_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+Z"), self, activated=self.undo)
        QShortcut(QKeySequence("Ctrl+Y"), self, activated=self.redo)
        QShortcut(
            QKeySequence(QKeySequence.StandardKey.SelectAll),
            self.view,
            activated=self.view.selectAll,
        )
        QShortcut(
            QKeySequence(QKeySequence.StandardKey.Delete),
            self.view,
            activated=self.on_delete_pages,
        )
        QShortcut(
            QKeySequence("Ctrl+Shift+E"),
            self,
            activated=self.on_export_selected_pdf,
        )

    def _selected_rows(self) -> List[int]:
        selection_model = self.view.selectionModel()
        if selection_model is None:
            return []
        return sorted({idx.row() for idx in selection_model.selectedIndexes() if idx.isValid()})

    def _capture_before_change(self):
        return copy.deepcopy(self.workspace.pages)

    def _commit_history(self, before_snapshot: list):
        self.history.push_snapshot(before_snapshot)
        self._update_history_buttons()

    def _restore_pages(self, restored_pages: Optional[list]):
        if restored_pages is None:
            return
        self.workspace.pages = restored_pages
        self.model.refresh_all()
        self.update_status()
        self._update_history_buttons()

    def _update_history_buttons(self):
        self.btn_undo.setEnabled(self.history.can_undo())
        self.btn_redo.setEnabled(self.history.can_redo())

    def _update_action_buttons(self):
        has_pages = self.model.rowCount() > 0
        has_selection = bool(self._selected_rows())
        self.btn_rot_l.setEnabled(has_selection)
        self.btn_rot_180.setEnabled(has_selection)
        self.btn_rot_r.setEnabled(has_selection)
        self.btn_delete.setEnabled(has_selection)
        self.btn_export_sel.setEnabled(has_selection)
        self.btn_export.setEnabled(has_pages)

    def _show_error(self, title: str, error):
        QMessageBox.critical(self, title, str(error))

    def update_status(self, *args):
        total = self.model.rowCount()
        selected = len(self._selected_rows())
        self.footer.setText(f" 總計 {total} 頁 | 已選取 {selected} 頁")
        self._update_action_buttons()

    def load_pdfs(self, files: List[str]):
        files = [f for f in files if f.lower().endswith(".pdf")]
        if not files:
            return
        before = self._capture_before_change()
        try:
            self.workspace.open_pdfs(files)
        except Exception as e:
            self._show_error("開啟 PDF 失敗", e)
            return
        self._commit_history(before)
        self.model.refresh_all()
        self.update_status()

    def on_add_pdf(self):
        files, _ = QFileDialog.getOpenFileNames(self, "開啟 PDF", "", "PDF 檔案 (*.pdf)")
        if files:
            self.load_pdfs(files)

    def on_add_folder(self):
        directory = QFileDialog.getExistingDirectory(self, "選擇含 PDF 的資料夾", "")
        if not directory:
            return
        root = Path(directory)
        files = sorted(
            str(p) for p in root.iterdir() if p.is_file() and p.suffix.lower() == ".pdf"
        )
        if not files:
            QMessageBox.information(
                self, "開啟資料夾",
                "此資料夾內沒有找到 PDF 檔案（僅揃描一層目錄，不含子資料夾）。",
            )
            return
        self.load_pdfs(files)

    def on_pages_reordered(self, source_rows: List[int], target: int):
        if not source_rows:
            return
        before = self._capture_before_change()
        try:
            self.workspace.move_pages(source_rows, target)
        except Exception as e:
            self._show_error("移動頁面失敗", e)
            return
        self._commit_history(before)
        self.model.refresh_all()
        self.update_status()

    def on_page_double_clicked(self, index: QModelIndex):
        page = index.data(PAGE_ROLE)
        if page is None:
            return
        dialog = PreviewDialog(self)
        worker = HighResWorker(self.backend, page, f"第 {index.row() + 1} 頁")
        worker.signals.preview_ready.connect(dialog.update_image)
        worker.signals.preview_error.connect(dialog.show_error)
        self.thread_pool.start(worker)
        dialog.exec()

    def on_rotate_pages(self, angle: int):
        rows = self._selected_rows()
        if not rows:
            return
        before = self._capture_before_change()
        try:
            self.workspace.rotate_pages(rows, angle)
        except Exception as e:
            self._show_error("旋轉頁面失敗", e)
            return
        self._commit_history(before)
        self.model.invalidate_rows(rows)
        for row in rows:
            self.model.start_thumbnail_worker(row)
        self.update_status()

    def on_delete_pages(self):
        rows = self._selected_rows()
        if not rows:
            return
        before = self._capture_before_change()
        try:
            self.workspace.remove_pages(rows)
        except Exception as e:
            self._show_error("刪除頁面失敗", e)
            return
        self._commit_history(before)
        self.model.refresh_all()
        self.update_status()

    def _confirm_encrypted_sources(self, page_indices: Optional[List[int]]) -> bool:
        enc = self.workspace.encrypted_used_sources(page_indices)
        if not enc:
            return True
        names = "\n".join(f"• {s.path.name}" for s in enc)
        answer = QMessageBox.warning(
            self, "偵測到加密或需密碼的來源",
            "下列來源在編目時標示為加密文件。若未事先以密碼解鎖，合併結果可能不完整或匯出失敗：\n\n"
            f"{names}\n\n仍要繼續匯出？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes

    def on_export_pdf(self):
        if not self.workspace.pages:
            return
        dlg = ExportPdfDialog(self, export_subset=False)
        if dlg.exec() != QDialog.Accepted:
            return
        options = dlg.export_options()
        path, _ = QFileDialog.getSaveFileName(self, "匯出 PDF", "合併結果.pdf", "PDF 檔案 (*.pdf)")
        if not path:
            return
        if not self._confirm_encrypted_sources(None):
            return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            self.export_service.export(path, options)
            QMessageBox.information(self, "成功", f"匯出成功至：\n{path}")
        except Exception as e:
            self._show_error("匯出失敗", e)
        finally:
            QApplication.restoreOverrideCursor()

    def on_export_selected_pdf(self):
        rows = self._selected_rows()
        if not rows:
            QMessageBox.information(
                self, "匯出選取",
                "請先在縮圖區選取至少一頁，再使用「匯出選取」或 Ctrl+Shift+E。",
            )
            return
        dlg = ExportPdfDialog(self, export_subset=True)
        if dlg.exec() != QDialog.Accepted:
            return
        options = dlg.export_options()
        path, _ = QFileDialog.getSaveFileName(self, "匯出選取的頁面", "選取頁面.pdf", "PDF 檔案 (*.pdf)")
        if not path:
            return
        if not self._confirm_encrypted_sources(rows):
            return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            self.export_service.export_selected(rows, path, options)
            QMessageBox.information(self, "成功", f"已匯出 {len(rows)} 頁至：\n{path}")
        except Exception as e:
            self._show_error("匯出失敗", e)
        finally:
            QApplication.restoreOverrideCursor()

    def undo(self):
        restored_pages = self.history.undo(self.workspace.pages)
        self._restore_pages(restored_pages)

    def redo(self):
        restored_pages = self.history.redo(self.workspace.pages)
        self._restore_pages(restored_pages)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dropEvent(self, event: QDropEvent):
        if event.mimeData().hasUrls():
            files = [
                url.toLocalFile()
                for url in event.mimeData().urls()
                if url.toLocalFile().lower().endswith(".pdf")
            ]
            if files:
                self.load_pdfs(files)
                event.acceptProposedAction()
            else:
                event.ignore()
            return
        super().dropEvent(event)

    def closeEvent(self, event):
        try:
            if self.thumb_path.exists():
                shutil.rmtree(self.thumb_path, ignore_errors=True)
        except Exception:
            logger.exception("清除縮圖目錄失敗")
        event.accept()


def main():
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    default_font = QFont("Microsoft JhengHei", 10)
    default_font.setStyleStrategy(QFont.PreferAntialias)
    app.setFont(default_font)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

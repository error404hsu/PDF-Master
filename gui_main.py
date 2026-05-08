"""gui_main.py — MainWindow (View 層) + main() 入口

Phase 2 MVP 重構：
  - MainWindow 實作 IMainView Protocol
  - 所有按鈕 Signal 連接至 self.presenter.*
  - 本檔不含任何業務邏輯（無 workspace 操作）
"""
from __future__ import annotations

import logging
import os
import shutil
import sys
from pathlib import Path
from typing import List

from PySide6.QtCore import Qt, QModelIndex, QThreadPool
from PySide6.QtGui import QFont, QDragEnterEvent, QDropEvent, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

try:
    from core.workspace import WorkspaceManager
    from adapters.pymupdf_backend import PyMuPdfBackend
    from core.thumbnail_service import ThumbnailService
    from core.export_service import ExportService
except ImportError as e:
    print(f"匯入核心邏輯失敗，請確保 gui_main.py 放在專案根目錄。錯誤: {e}")
    sys.exit(1)

from gui.interfaces import IMainView
from gui.models import PdfPageModel, SnapshotHistory
from gui.presenter import MainPresenter
from gui.styles import UiStyles
from gui.views import PageCardDelegate, PageListView

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger("gui_main")


class MainWindow(QMainWindow):
    """MVP View 層—僅負責純 UI 建構與事件轉中。"""

    # ------------------------------------------------------------------
    # 初始化
    # ------------------------------------------------------------------

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("PDF排列哥 Pro")
        self.resize(1300, 800)
        self.setAcceptDrops(True)

        self.thumb_path = Path("./.thumbnails")
        self.thumb_path.mkdir(exist_ok=True)

        # 建立服務層對象
        self.backend = PyMuPdfBackend()
        self.workspace = WorkspaceManager(self.backend, self.thumb_path)
        self.thumb_service = ThumbnailService(self.workspace)
        self.export_service = ExportService(self.workspace)

        self.history = SnapshotHistory(max_entries=20)

        # 建立 Model（View 拥有，Presenter 需要取得其引用）
        self.model = PdfPageModel(self.workspace, self.thumb_service)

        # 建立 Presenter，將 self 作為 IMainView 傳入
        self.presenter = MainPresenter(
            view=self,
            workspace=self.workspace,
            backend=self.backend,
            export_service=self.export_service,
            model=self.model,
            history=self.history,
        )

        self._build_ui()
        self._connect_signals()
        self._setup_shortcuts()
        self._update_history_buttons()
        self.update_status()

    # ------------------------------------------------------------------
    # IMainView 實作
    # ------------------------------------------------------------------

    def show_error(self, title: str, msg: str) -> None:
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.critical(self, title, msg)

    def set_status(self, text: str) -> None:
        self.footer.setText(text)
        self._update_action_buttons()
        self._update_history_buttons()

    def refresh_view(self) -> None:
        """Presenter 要求重整縮圖時呼叫。"""
        self.update_status()

    def get_selected_rows(self) -> list[int]:
        selection_model = self.view.selectionModel()
        if selection_model is None:
            return []
        return sorted(
            {idx.row() for idx in selection_model.selectedIndexes() if idx.isValid()}
        )

    # ------------------------------------------------------------------
    # 純 UI 建構
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        header = self._build_header()
        main_layout.addWidget(header)

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

    def _build_header(self) -> QFrame:
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

    def _make_button(self, text: str, width: int, height: int, variant: str = "base") -> QPushButton:
        btn = QPushButton(text)
        btn.setFixedSize(width, height)
        if variant == "danger":
            btn.setStyleSheet(UiStyles.DANGER_BUTTON)
        elif variant == "primary":
            btn.setStyleSheet(UiStyles.PRIMARY_BUTTON)
        else:
            btn.setStyleSheet(UiStyles.BASE_BUTTON)
        return btn

    def _make_separator(self) -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.VLine)
        line.setFixedHeight(24)
        line.setStyleSheet(f"color: {UiStyles.PANEL_BORDER};")
        return line

    # ------------------------------------------------------------------
    # Signal 連接與快捷鍵
    # ------------------------------------------------------------------

    def _connect_signals(self) -> None:
        self.btn_add.clicked.connect(self.presenter.on_add_pdf)
        self.btn_add_folder.clicked.connect(self.presenter.on_add_folder)
        self.btn_undo.clicked.connect(self.presenter.undo)
        self.btn_redo.clicked.connect(self.presenter.redo)
        self.btn_rot_l.clicked.connect(lambda: self.presenter.on_rotate_pages(-90))
        self.btn_rot_180.clicked.connect(lambda: self.presenter.on_rotate_pages(180))
        self.btn_rot_r.clicked.connect(lambda: self.presenter.on_rotate_pages(90))
        self.btn_delete.clicked.connect(self.presenter.on_delete_pages)
        self.btn_export_sel.clicked.connect(self.presenter.on_export_selected_pdf)
        self.btn_export.clicked.connect(self.presenter.on_export_pdf)

        self.view.doubleClicked.connect(self.presenter.on_page_double_clicked)
        self.view.pages_reordered.connect(self.presenter.on_pages_reordered)
        self.view.pdf_files_dropped.connect(self.presenter.load_pdfs)

        selection_model = self.view.selectionModel()
        if selection_model is not None:
            selection_model.selectionChanged.connect(self.update_status)

    def _setup_shortcuts(self) -> None:
        QShortcut(QKeySequence("Ctrl+Z"), self, activated=self.presenter.undo)
        QShortcut(QKeySequence("Ctrl+Y"), self, activated=self.presenter.redo)
        QShortcut(
            QKeySequence(QKeySequence.StandardKey.SelectAll),
            self.view,
            activated=self.view.selectAll,
        )
        QShortcut(
            QKeySequence(QKeySequence.StandardKey.Delete),
            self.view,
            activated=self.presenter.on_delete_pages,
        )
        QShortcut(
            QKeySequence("Ctrl+Shift+E"),
            self,
            activated=self.presenter.on_export_selected_pdf,
        )

    # ------------------------------------------------------------------
    # 狀態與按鈕更新
    # ------------------------------------------------------------------

    def update_status(self, *args) -> None:
        total = self.model.rowCount()
        selected = len(self.get_selected_rows())
        self.footer.setText(f" 總計 {total} 頁 | 已選取 {selected} 頁")
        self._update_action_buttons()
        self._update_history_buttons()

    def _update_history_buttons(self) -> None:
        self.btn_undo.setEnabled(self.history.can_undo())
        self.btn_redo.setEnabled(self.history.can_redo())

    def _update_action_buttons(self) -> None:
        has_pages = self.model.rowCount() > 0
        has_selection = bool(self.get_selected_rows())
        self.btn_rot_l.setEnabled(has_selection)
        self.btn_rot_180.setEnabled(has_selection)
        self.btn_rot_r.setEnabled(has_selection)
        self.btn_delete.setEnabled(has_selection)
        self.btn_export_sel.setEnabled(has_selection)
        self.btn_export.setEnabled(has_pages)

    # ------------------------------------------------------------------
    # Qt 事件 override
    # ------------------------------------------------------------------

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:
        if event.mimeData().hasUrls():
            files = [
                url.toLocalFile()
                for url in event.mimeData().urls()
                if url.toLocalFile().lower().endswith(".pdf")
            ]
            if files:
                self.presenter.load_pdfs(files)
                event.acceptProposedAction()
            else:
                event.ignore()
            return
        super().dropEvent(event)

    def closeEvent(self, event) -> None:
        try:
            if self.thumb_path.exists():
                shutil.rmtree(self.thumb_path, ignore_errors=True)
        except Exception:
            logger.exception("清除縮圖目錄失敗")
        event.accept()


# ---------------------------------------------------------------------------
# 入口點
# ---------------------------------------------------------------------------

def main() -> None:
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

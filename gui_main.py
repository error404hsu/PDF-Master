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

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QAction, QDragEnterEvent, QDropEvent, QFont, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QToolBar,
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

from gui.icons import AppIcons
from gui.interfaces import IMainView
from gui.models import PdfPageModel, SnapshotHistory
from gui.presenter import MainPresenter
from gui.styles import UiStyles
from gui.views import PageCardDelegate, PageListView
from gui.toast import Toast
from gui.empty_state import EmptyStateOverlay

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger("gui_main")

_SUPPORTED_SUFFIXES = frozenset({
    ".pdf", ".jpg", ".jpeg", ".png",
    ".tiff", ".tif", ".bmp", ".webp", ".gif"
})


class MainWindow(QMainWindow):
    def __init__(self, is_dark: bool = False) -> None:
        super().__init__()
        self._is_dark = is_dark
        self.setWindowTitle("PDF排列哥 Pro")
        self.resize(1300, 800)
        self.setAcceptDrops(True)

        self.thumb_path = Path("./.thumbnails")

        self.backend = PyMuPdfBackend()
        self.workspace = WorkspaceManager(self.backend)
        self.thumb_service = ThumbnailService(self.workspace, self.thumb_path)
        self.export_service = ExportService(self.workspace)

        self.history = SnapshotHistory(max_entries=20)
        self.model = PdfPageModel(self.workspace, self.thumb_service)

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

    def show_error(self, title: str, msg: str) -> None:
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.critical(self, title, msg)

    def show_toast(self, msg: str, kind: str = "info") -> None:
        Toast.show(self, msg, kind)

    def set_status(self, text: str) -> None:
        self.footer_status.setText(text)
        self._update_action_buttons()
        self._update_history_buttons()

    def refresh_view(self) -> None:
        self.update_status()

    def get_selected_rows(self) -> list[int]:
        selection_model = self.view.selectionModel()
        if selection_model is None:
            return []
        return sorted({idx.row() for idx in selection_model.selectedIndexes() if idx.isValid()})

    def show_progress(self, value: int = 0, maximum: int = 0) -> None:
        self.progress_bar.setMaximum(maximum)
        self.progress_bar.setValue(value)
        self.progress_bar.setVisible(True)

    def hide_progress(self) -> None:
        self.progress_bar.setVisible(False)

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        if self._is_dark:
            central.setStyleSheet(f"background-color: {UiStyles.DARK_BG};")

        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self._build_toolbar()

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(4)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet(UiStyles.PROGRESS_BAR)
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)

        list_container = QWidget()
        list_container.setObjectName("list_container")
        list_layout = QVBoxLayout(list_container)
        list_layout.setContentsMargins(0, 0, 0, 0)

        self.view = PageListView(list_container)
        self.view.setModel(self.model)
        self.view.setItemDelegate(PageCardDelegate())
        self.view.setStyleSheet(UiStyles.LIST_VIEW_DARK if self._is_dark else UiStyles.LIST_VIEW)
        list_layout.addWidget(self.view)

        self.empty_overlay = EmptyStateOverlay(list_container)
        self.empty_overlay.setVisible(True)

        main_layout.addWidget(list_container, stretch=1)

        footer_widget = QWidget()
        footer_widget.setFixedHeight(32)
        if self._is_dark:
            footer_widget.setStyleSheet(
                f"background-color: {UiStyles.DARK_SURFACE};"
                f" border-top: 1px solid {UiStyles.DARK_BORDER};"
            )
        else:
            footer_widget.setStyleSheet("background-color: white; border-top: 1px solid #e2e8f0;")
        footer_layout = QHBoxLayout(footer_widget)
        footer_layout.setContentsMargins(16, 0, 16, 0)
        footer_layout.setSpacing(0)

        self.footer_status = QLabel(" 總計 0 頁")
        self.footer_status.setStyleSheet(UiStyles.FOOTER_DARK if self._is_dark else UiStyles.FOOTER)

        self.footer_hint = QLabel("Ctrl+A 全選 ｜ Del 刪除 ｜ Ctrl+Z 復原 ｜ 雙擊預覽 ｜ 拖曳排序")
        self.footer_hint.setStyleSheet(UiStyles.FOOTER_HINT_DARK if self._is_dark else UiStyles.FOOTER_HINT)

        footer_layout.addWidget(self.footer_status)
        footer_layout.addStretch()
        footer_layout.addWidget(self.footer_hint)
        main_layout.addWidget(footer_widget)

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("主工具列", self)
        toolbar.setIconSize(QSize(18, 18))
        toolbar.setMovable(False)
        toolbar.setFloatable(False)
        toolbar.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        toolbar.setStyleSheet(UiStyles.TOOLBAR_DARK if self._is_dark else UiStyles.TOOLBAR)

        self.act_open_file = QAction(AppIcons.get("open_file"), "開啟檔案", self)
        self.act_open_folder = QAction(AppIcons.get("open_folder"), "開啟資料夾", self)
        toolbar.addAction(self.act_open_file)
        toolbar.addAction(self.act_open_folder)
        toolbar.addSeparator()

        self.act_undo = QAction(AppIcons.get("undo"), "復原", self)
        self.act_redo = QAction(AppIcons.get("redo"), "重做", self)
        toolbar.addAction(self.act_undo)
        toolbar.addAction(self.act_redo)
        toolbar.addSeparator()

        self.act_rot_l = QAction(AppIcons.get("rotate_left"), "左轉 90°", self)
        self.act_rot_180 = QAction(AppIcons.get("rotate_180"), "轉 180°", self)
        self.act_rot_r = QAction(AppIcons.get("rotate_right"), "右轉 90°", self)
        self.act_delete = QAction(AppIcons.get("delete"), "刪除頁面", self)
        toolbar.addAction(self.act_rot_l)
        toolbar.addAction(self.act_rot_180)
        toolbar.addAction(self.act_rot_r)
        toolbar.addAction(self.act_delete)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        toolbar.addWidget(spacer)

        self.act_export_sel = QAction(AppIcons.get("export_selected"), "輸出選取", self)
        self.act_export_single = QAction(AppIcons.get("export_single"), "輸出單頁", self)
        self.act_export = QAction(AppIcons.get("export"), "輸出結果", self)
        toolbar.addAction(self.act_export_sel)
        toolbar.addAction(self.act_export_single)
        toolbar.addAction(self.act_export)
        toolbar.addSeparator()

        self.act_settings = QAction(AppIcons.get("settings"), "設定", self)
        toolbar.addAction(self.act_settings)

        self.addToolBar(Qt.TopToolBarArea, toolbar)
        self._toolbar = toolbar

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

    def _connect_signals(self) -> None:
        self.act_open_file.triggered.connect(self.presenter.on_add_pdf)
        self.act_open_folder.triggered.connect(self.presenter.on_add_folder)
        self.act_undo.triggered.connect(self.presenter.undo)
        self.act_redo.triggered.connect(self.presenter.redo)
        self.act_rot_l.triggered.connect(lambda: self.presenter.on_rotate_pages(-90))
        self.act_rot_180.triggered.connect(lambda: self.presenter.on_rotate_pages(180))
        self.act_rot_r.triggered.connect(lambda: self.presenter.on_rotate_pages(90))
        self.act_delete.triggered.connect(self.presenter.on_delete_pages)
        self.act_export_sel.triggered.connect(self.presenter.on_export_selected_pdf)
        self.act_export_single.triggered.connect(self.presenter.on_export_single_pages)
        self.act_export.triggered.connect(self.presenter.on_export_pdf)
        self.act_settings.triggered.connect(self.presenter.on_open_settings)

        self.view.doubleClicked.connect(self.presenter.on_page_double_clicked)
        self.view.pages_reordered.connect(self.presenter.on_pages_reordered)
        self.view.pdf_files_dropped.connect(self.presenter.load_files)

        self.view.context_rotate_left.connect(lambda: self.presenter.on_rotate_pages(-90))
        self.view.context_rotate_180.connect(lambda: self.presenter.on_rotate_pages(180))
        self.view.context_rotate_right.connect(lambda: self.presenter.on_rotate_pages(90))
        self.view.context_delete.connect(self.presenter.on_delete_pages)
        self.view.context_export_selected.connect(self.presenter.on_export_selected_pdf)

        selection_model = self.view.selectionModel()
        if selection_model is not None:
            selection_model.selectionChanged.connect(self.update_status)

    def _setup_shortcuts(self) -> None:
        QShortcut(QKeySequence("Ctrl+Z"), self, activated=self.presenter.undo)
        QShortcut(QKeySequence("Ctrl+Y"), self, activated=self.presenter.redo)
        QShortcut(QKeySequence(QKeySequence.StandardKey.SelectAll), self.view, activated=self.view.selectAll)
        QShortcut(QKeySequence(QKeySequence.StandardKey.Delete), self.view, activated=self.presenter.on_delete_pages)
        QShortcut(QKeySequence("Ctrl+Shift+E"), self, activated=self.presenter.on_export_selected_pdf)
        QShortcut(QKeySequence("Ctrl+,"), self, activated=self.presenter.on_open_settings)

    def update_status(self, *args: object) -> None:
        total = self.model.rowCount()
        selected = len(self.get_selected_rows())
        if total == 0:
            self.footer_status.setText(" 尚無頁面")
        else:
            self.footer_status.setText(f" 總計 {total} 頁 | 已選取 {selected} 頁")
        self.empty_overlay.setVisible(total == 0)
        self._update_action_buttons()
        self._update_history_buttons()

    def _update_history_buttons(self) -> None:
        self.act_undo.setEnabled(self.history.can_undo())
        self.act_redo.setEnabled(self.history.can_redo())

    def _update_action_buttons(self) -> None:
        has_pages = self.model.rowCount() > 0
        has_selection = bool(self.get_selected_rows())
        self.act_rot_l.setEnabled(has_selection)
        self.act_rot_180.setEnabled(has_selection)
        self.act_rot_r.setEnabled(has_selection)
        self.act_delete.setEnabled(has_selection)
        self.act_export_sel.setEnabled(has_selection)
        self.act_export_single.setEnabled(has_selection)
        self.act_export.setEnabled(has_pages)

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
                if Path(url.toLocalFile()).suffix.lower() in _SUPPORTED_SUFFIXES
            ]
            if files:
                self.presenter.load_files(files)
                event.acceptProposedAction()
            else:
                self.show_toast("不支援的檔案格式，請拖入 PDF 或圖片檔案。", "error")
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


def main() -> None:
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    font = app.font()
    font.setPointSize(10)
    font.setStyleStrategy(QFont.PreferAntialias)
    app.setFont(font)

    is_dark = UiStyles.apply_theme(app)

    window = MainWindow(is_dark=is_dark)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

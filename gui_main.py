import sys
import os
import ast
import copy
from pathlib import Path
from typing import Dict, List, Optional

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QListView, QPushButton, QFileDialog, QLabel, QFrame, 
    QAbstractItemView, QStyledItemDelegate, QStyle, QLineEdit,
    QDialog, QMessageBox, QScrollArea
)
from PySide6.QtCore import (
    Qt, QSize, QAbstractListModel, QModelIndex, QRunnable, 
    QThreadPool, Slot, Signal, QObject, QMimeData
)
from PySide6.QtGui import (
    QPixmap, QPainter, QColor, QPen, QCursor, QScreen, 
    QImage, QAction, QKeySequence, QShortcut, QResizeEvent
)

# 導入核心邏輯
try:
    from core.workspace import WorkspaceManager
    from adapters.pymupdf_backend import PyMuPdfBackend
    from core.thumbnail_service import ThumbnailService
    from core.export_service import ExportService
except ImportError as e:
    print(f"匯入核心邏輯失敗，請確保 gui_main.py 放在專案根目錄。錯誤: {e}")
    sys.exit(1)

# --- 訊號與 Worker ---

class WorkerSignals(QObject):
    finished = Signal(int)
    high_res_ready = Signal(QImage, str)
    error = Signal(str)

class ThumbnailWorker(QRunnable):
    """背景渲染縮圖"""
    def __init__(self, thumb_service: ThumbnailService, index: int):
        super().__init__()
        self.thumb_service = thumb_service
        self.index = index
        self.signals = WorkerSignals()

    @Slot()
    def run(self):
        try:
            self.thumb_service.render_one(self.index)
            self.signals.finished.emit(self.index)
        except Exception as e:
            print(f"縮圖渲染失敗 (索引 {self.index}): {e}")

class HighResWorker(QRunnable):
    """即時渲染高品質預覽圖"""
    def __init__(self, backend: PyMuPdfBackend, page_ref, label: str):
        super().__init__()
        self.backend = backend
        self.page_ref = page_ref
        self.label = label
        self.signals = WorkerSignals()

    @Slot()
    def run(self):
        try:
            # 使用高品質倍率渲染
            image_data = self.backend.render_page_to_image(
                self.page_ref.source_path,
                self.page_ref.source_page_index,
                zoom=4.0,
                rotation=self.page_ref.effective_rotation
            )
            qimg = QImage.fromData(image_data)
            if qimg.isNull():
                self.signals.error.emit("影像解析失敗")
            else:
                self.signals.high_res_ready.emit(qimg, self.label)
        except Exception as e:
            self.signals.error.emit(str(e))

# --- UI 元件 ---

class PreviewDialog(QDialog):
    """高品質預覽視窗 - 支援自動縮放整頁顯示"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("高品質預覽 (渲染中...)")
        self.setMinimumSize(700, 800)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 使用 ScrollArea 但設定為自動縮放模式
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setAlignment(Qt.AlignCenter)
        
        self.image_label = QLabel("正在渲染高品質影像，請稍候...")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setStyleSheet("color: #94a3b8; font-size: 16px;")
        
        self.scroll.setWidget(self.image_label)
        layout.addWidget(self.scroll)
        
        self.setStyleSheet("background-color: #0f172a; color: white; border: none;")
        
        self.full_pixmap = None # 儲存原始高品質圖案
        self.current_label = ""

    @Slot(QImage, str)
    def update_image(self, qimage: QImage, label: str):
        # 即使對話框已關閉，訊號仍可能傳回，故需檢查
        if not self.isVisible():
            return
            
        self.current_label = label
        self.setWindowTitle(f"高品質預覽 - {label}")
        self.full_pixmap = QPixmap.fromImage(qimage)
        self.update_display()

    def update_display(self):
        """根據目前視窗大小縮放圖片，確保整頁顯示"""
        if self.full_pixmap:
            # 獲取捲動區域的實際可用空間
            view_size = self.scroll.viewport().size()
            
            # 等比例縮放圖片以適應視窗大小
            scaled_pixmap = self.full_pixmap.scaled(
                view_size, 
                Qt.KeepAspectRatio, 
                Qt.SmoothTransformation
            )
            self.image_label.setPixmap(scaled_pixmap)

    def resizeEvent(self, event: QResizeEvent):
        """當使用者調整視窗大小時，即時更新圖片縮放"""
        super().resizeEvent(event)
        self.update_display()

    @Slot(str)
    def show_error(self, error_msg: str):
        if self.isVisible():
            self.image_label.setText(f"渲染失敗：\n{error_msg}")
            self.image_label.setStyleSheet("color: #ef4444; font-weight: bold;")

class PdfPageModel(QAbstractListModel):
    def __init__(self, workspace: WorkspaceManager, thumb_service: ThumbnailService):
        super().__init__()
        self.workspace = workspace
        self.thumb_service = thumb_service
        self.thread_pool = QThreadPool.globalInstance()
        self._thumb_cache: Dict[int, QPixmap] = {}

    def rowCount(self, parent=QModelIndex()):
        return len(self.workspace.pages)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or index.row() >= len(self.workspace.pages):
            return None
        
        page = self.workspace.pages[index.row()]
        if role == Qt.UserRole:
            return page
        
        if role == Qt.DecorationRole:
            if index.row() in self._thumb_cache:
                return self._thumb_cache[index.row()]
            
            if page.thumb_path and page.thumb_path.exists():
                pixmap = QPixmap(str(page.thumb_path))
                self._thumb_cache[index.row()] = pixmap
                return pixmap
            
            self.start_thumbnail_worker(index.row())
            return None
            
        return None

    def start_thumbnail_worker(self, row: int):
        worker = ThumbnailWorker(self.thumb_service, row)
        worker.signals.finished.connect(self._on_thumb_ready)
        self.thread_pool.start(worker)

    def _on_thumb_ready(self, row: int):
        if row in self._thumb_cache:
            del self._thumb_cache[row]
        idx = self.index(row)
        self.dataChanged.emit(idx, idx, [Qt.DecorationRole, Qt.UserRole])

    def supportedDropActions(self):
        return Qt.MoveAction

    def flags(self, index):
        if not index.isValid():
            return Qt.ItemIsDropEnabled
        return Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsDragEnabled | Qt.ItemIsDropEnabled

    def mimeData(self, indexes):
        mime_data = QMimeData()
        rows = [index.row() for index in indexes]
        mime_data.setData("application/x-pagemove", str(rows).encode())
        return mime_data

    def dropMimeData(self, data, action, row, column, parent):
        if not data.hasFormat("application/x-pagemove"):
            return False
        
        try:
            source_rows = ast.literal_eval(data.data("application/x-pagemove").decode())
        except:
            return False
            
        destination = row if row != -1 else self.rowCount()
        
        main_win = self.get_main_window()
        if main_win: main_win.save_history()

        self.beginResetModel()
        self.workspace.move_pages(source_rows, destination)
        self._thumb_cache.clear()
        self.endResetModel()
        return True

    def get_main_window(self):
        for widget in QApplication.topLevelWidgets():
            if isinstance(widget, QMainWindow):
                return widget
        return None

    def refresh_all(self):
        self.beginResetModel()
        self._thumb_cache.clear()
        self.endResetModel()

class PageDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        page = index.data(Qt.UserRole)
        pixmap = index.data(Qt.DecorationRole)
        if not page: return

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        rect = option.rect.adjusted(6, 6, -6, -6)
        is_selected = option.state & QStyle.State_Selected
        
        if is_selected:
            painter.setPen(QPen(QColor("#3b82f6"), 3))
            painter.setBrush(QColor("#eff6ff"))
        else:
            painter.setPen(QPen(QColor("#cbd5e1"), 1))
            painter.setBrush(Qt.white)
            
        painter.drawRoundedRect(rect, 8, 8)

        thumb_area = rect.adjusted(10, 10, -10, -50)
        if pixmap and not pixmap.isNull():
            scaled = pixmap.scaled(thumb_area.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            x = thumb_area.x() + (thumb_area.width() - scaled.width()) // 2
            y = thumb_area.y() + (thumb_area.height() - scaled.height()) // 2
            painter.drawPixmap(x, y, scaled)
        else:
            painter.setPen(QColor("#94a3b8"))
            painter.drawText(thumb_area, Qt.AlignCenter, "渲染中...")

        painter.setPen(QColor("#1e293b"))
        font = painter.font()
        font.setBold(True)
        font.setPixelSize(13)
        painter.setFont(font)
        painter.drawText(rect.adjusted(0, rect.height()-45, 0, -22), Qt.AlignCenter, f"第 {index.row() + 1} 頁")
        
        font.setBold(False)
        font.setPixelSize(11)
        painter.setFont(font)
        painter.setPen(QColor("#64748b"))
        info = f"{page.source_page_label} | {page.effective_rotation}°"
        painter.drawText(rect.adjusted(5, rect.height()-22, -5, -5), Qt.AlignCenter | Qt.TextSingleLine, info)

        painter.restore()

    def sizeHint(self, option, index):
        return QSize(180, 260)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PDF排列哥")
        self.resize(1200, 950)
        self.setAcceptDrops(True)

        self.backend = PyMuPdfBackend()
        thumb_path = Path("./.thumbnails")
        thumb_path.mkdir(exist_ok=True)
        
        self.workspace = WorkspaceManager(self.backend, thumb_path)
        self.thumb_service = ThumbnailService(self.workspace)
        self.export_service = ExportService(self.workspace)

        self.undo_stack = []
        self.redo_stack = []
        self.thread_pool = QThreadPool.globalInstance()

        self.setup_ui()
        self.setup_shortcuts()

    def setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # --- 頂部導覽列 ---
        header = QFrame()
        header.setFixedHeight(65)
        header.setStyleSheet("background-color: white; border-bottom: 1px solid #e2e8f0;")
        h_layout = QHBoxLayout(header)
        
        title_label = QLabel(" PDF排列哥")
        title_label.setStyleSheet("font-weight: 900; font-size: 26px; color: #2563eb; margin-left: 15px;")
        h_layout.addWidget(title_label)
        
        h_layout.addSpacing(20)
        
        self.btn_undo = QPushButton("返回 (Undo)")
        self.btn_redo = QPushButton("重做 (Redo)")
        for b in [self.btn_undo, self.btn_redo]:
            b.setFixedWidth(100)
            b.setEnabled(False)
            h_layout.addWidget(b)

        h_layout.addStretch()
        
        # 功能按鈕
        btn_add = QPushButton("開啟檔案")
        btn_rot_l = QPushButton("左轉 90°")
        btn_rot_180 = QPushButton("轉 180°")
        btn_rot_r = QPushButton("右轉 90°")
        btn_delete = QPushButton("刪除頁面")
        btn_export = QPushButton("匯出合併檔")
        
        # 設定按鈕樣式與游標
        for btn in [btn_add, btn_rot_l, btn_rot_180, btn_rot_r, btn_delete, btn_export]:
            btn.setCursor(QCursor(Qt.PointingHandCursor))
            btn.setMinimumHeight(40)
            h_layout.addWidget(btn)
            
        btn_export.setStyleSheet("""
            QPushButton {
                background-color: #2563eb; 
                color: white; 
                border-radius: 6px; 
                padding: 0 20px; 
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1d4ed8;
            }
        """)
        
        main_layout.addWidget(header)

        # --- 中央工作網格 ---
        self.model = PdfPageModel(self.workspace, self.thumb_service)
        self.view = QListView()
        self.view.setViewMode(QListView.IconMode)
        self.view.setResizeMode(QListView.Adjust)
        self.view.setSpacing(15)
        self.view.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.view.setDragEnabled(True)
        self.view.setAcceptDrops(True)
        self.view.setDropIndicatorShown(True)
        self.view.setDragDropMode(QListView.InternalMove)
        self.view.setModel(self.model)
        self.view.setItemDelegate(PageDelegate())
        self.view.setStyleSheet("""
            QListView {
                background-color: #f8fafc; 
                border: none; 
                padding: 15px;
            }
            QListView::item:selected {
                background: transparent;
            }
        """)

        main_layout.addWidget(self.view)

        # --- 底部狀態列 ---
        self.footer = QLabel(" 系統就緒 | 雙擊縮圖預覽細節 | 支持 Ctrl+Z 返回 (誤刪可救回)")
        self.footer.setFixedHeight(35)
        self.footer.setStyleSheet("background-color: white; border-top: 1px solid #e2e8f0; color: #475569; font-size: 13px; padding-left: 15px;")
        main_layout.addWidget(self.footer)

        # 事件連接
        btn_add.clicked.connect(self.on_add_pdf)
        btn_rot_l.clicked.connect(lambda: self.on_rotate_pages(-90))
        btn_rot_180.clicked.connect(lambda: self.on_rotate_pages(180))
        btn_rot_r.clicked.connect(lambda: self.on_rotate_pages(90))
        btn_delete.clicked.connect(self.on_delete_pages)
        btn_export.clicked.connect(self.on_export_pdf)
        self.btn_undo.clicked.connect(self.undo)
        self.btn_redo.clicked.connect(self.redo)
        self.view.doubleClicked.connect(self.on_page_double_clicked)
        self.view.selectionModel().selectionChanged.connect(self.update_status)

    def setup_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+Z"), self, self.undo)
        QShortcut(QKeySequence("Ctrl+Y"), self, self.redo)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        files = []
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path.lower().endswith('.pdf'):
                files.append(path)
        if files:
            self.save_history()
            self.workspace.open_pdfs(files)
            self.model.refresh_all()
            self.update_status()

    def save_history(self):
        snapshot = copy.deepcopy(self.workspace.pages)
        self.undo_stack.append(snapshot)
        self.redo_stack.clear()
        self.update_history_buttons()

    def undo(self):
        if not self.undo_stack: return
        self.redo_stack.append(copy.deepcopy(self.workspace.pages))
        self.workspace.pages = self.undo_stack.pop()
        self.model.refresh_all()
        self.update_history_buttons()
        self.footer.setText(" 已復原操作")

    def redo(self):
        if not self.redo_stack: return
        self.undo_stack.append(copy.deepcopy(self.workspace.pages))
        self.workspace.pages = self.redo_stack.pop()
        self.model.refresh_all()
        self.update_history_buttons()
        self.footer.setText(" 已重做操作")

    def update_history_buttons(self):
        self.btn_undo.setEnabled(len(self.undo_stack) > 0)
        self.btn_redo.setEnabled(len(self.redo_stack) > 0)

    def update_status(self):
        sel_count = len(self.view.selectionModel().selectedIndexes())
        self.footer.setText(f" 總計 {self.model.rowCount()} 頁 | 已選取 {sel_count} 頁")

    def on_add_pdf(self):
        files, _ = QFileDialog.getOpenFileNames(self, "開啟 PDF", "", "PDF 檔案 (*.pdf)")
        if files:
            self.save_history()
            self.workspace.open_pdfs(files)
            self.model.refresh_all()
            self.update_status()

    def on_page_double_clicked(self, index):
        """處理雙擊縮圖：高品質預覽"""
        page = index.data(Qt.UserRole)
        label = f"第 {index.row() + 1} 頁 ({page.source_page_label})"
        
        dlg = PreviewDialog(self)
        
        # 啟動背景 Worker 渲染高品質影像
        worker = HighResWorker(self.backend, page, label)
        
        # 訊號連接到 Slot
        worker.signals.high_res_ready.connect(dlg.update_image)
        worker.signals.error.connect(dlg.show_error)
        
        self.thread_pool.start(worker)
        dlg.exec() # 使用 exec 啟動模態對話框

    def on_rotate_pages(self, angle: int):
        selection_model = self.view.selectionModel()
        selected_indexes = selection_model.selectedIndexes()
        if not selected_indexes: return
        
        indices = [idx.row() for idx in selected_indexes]
        self.save_history()
        self.workspace.rotate_pages(indices, angle)
        
        # 核心優化：保留選取狀態，僅更新受影響的項目
        for row in indices:
            self.model.start_thumbnail_worker(row)
            idx = self.model.index(row)
            self.model.dataChanged.emit(idx, idx, [Qt.DecorationRole, Qt.UserRole])
            
        self.update_status()

    def on_delete_pages(self):
        indices = [idx.row() for idx in self.view.selectionModel().selectedIndexes()]
        if not indices: return
        self.save_history()
        self.workspace.remove_pages(indices)
        self.model.refresh_all() 
        self.update_status()

    def on_export_pdf(self):
        if not self.workspace.pages: return
        path, _ = QFileDialog.getSaveFileName(self, "匯出 PDF", "合併結果.pdf", "PDF 檔案 (*.pdf)")
        if path:
            self.footer.setText(" 🚀 正在合成 PDF，請稍候...")
            QApplication.setOverrideCursor(Qt.WaitCursor)
            try:
                self.export_service.export(path)
                QMessageBox.information(self, "成功", f"文件已成功匯出至：\n{path}")
            except Exception as e:
                QMessageBox.critical(self, "錯誤", f"匯出失敗：{str(e)}")
            finally:
                QApplication.restoreOverrideCursor()
                self.update_status()

if __name__ == "__main__":
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
    os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"
    
    app = QApplication(sys.argv)
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app.setStyle("Fusion")
    
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
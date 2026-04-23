import sys
import os
import ast
import copy
import shutil
from pathlib import Path
from typing import Dict, List, Optional

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QListView, QPushButton, QFileDialog, QLabel, QFrame, 
    QAbstractItemView, QStyledItemDelegate, QStyle, QLineEdit,
    QDialog, QMessageBox, QScrollArea, QSizePolicy
)
from PySide6.QtCore import (
    Qt, QSize, QPoint, QRect, QAbstractListModel, QModelIndex, QRunnable, 
    QThreadPool, Slot, Signal, QObject, QMimeData
)
from PySide6.QtGui import (
    QPixmap, QPainter, QColor, QPen, QCursor, QScreen, 
    QImage, QAction, QKeySequence, QShortcut, QResizeEvent, QMouseEvent, QDragMoveEvent, QDropEvent, QFont
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
    def __init__(self, backend: PyMuPdfBackend, page_ref, label: str):
        super().__init__()
        self.backend = backend
        self.page_ref = page_ref
        self.label = label
        self.signals = WorkerSignals()

    @Slot()
    def run(self):
        try:
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
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("高品質預覽")
        self.setMinimumSize(800, 900)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setAlignment(Qt.AlignCenter)
        self.image_label = QLabel("正在渲染高品質影像...")
        self.image_label.setAlignment(Qt.AlignCenter)
        # 統一使用 10pt normal 渲染
        self.image_label.setStyleSheet("color: #94a3b8; font-size: 10pt; font-weight: normal;")
        self.scroll.setWidget(self.image_label)
        layout.addWidget(self.scroll)
        self.setStyleSheet("background-color: #0f172a; color: white; border: none;")
        self.full_pixmap = None 

    @Slot(QImage, str)
    def update_image(self, qimage: QImage, label: str):
        if not self.isVisible(): return
        self.setWindowTitle(f"高品質預覽 - {label}")
        self.full_pixmap = QPixmap.fromImage(qimage)
        self.update_display()

    def update_display(self):
        if self.full_pixmap:
            view_size = self.scroll.viewport().size()
            scaled = self.full_pixmap.scaled(view_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.image_label.setPixmap(scaled)

    def resizeEvent(self, event: QResizeEvent):
        super().resizeEvent(event)
        self.update_display()

    @Slot(str)
    def show_error(self, error_msg: str):
        if self.isVisible(): self.image_label.setText(f"渲染失敗：\n{error_msg}")

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
        if role == Qt.UserRole: return page
        if role == Qt.DecorationRole:
            if index.row() in self._thumb_cache: return self._thumb_cache[index.row()]
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
        if row in self._thumb_cache: del self._thumb_cache[row]
        idx = self.index(row)
        self.dataChanged.emit(idx, idx, [Qt.DecorationRole, Qt.UserRole])

    def flags(self, index):
        if not index.isValid(): return Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsDropEnabled
        return Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsDragEnabled | Qt.ItemIsDropEnabled

    def mimeTypes(self):
        return ["application/x-pagemove"]

    def mimeData(self, indexes):
        mime_data = QMimeData()
        rows = sorted([index.row() for index in indexes])
        mime_data.setData("application/x-pagemove", str(rows).encode())
        return mime_data

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
            
        # 頁碼與資訊套用狀態列樣式：10pt, normal, #64748b
        painter.setPen(QColor("#64748b"))
        font = painter.font()
        font.setBold(False); font.setPointSize(10); painter.setFont(font)
        painter.drawText(rect.adjusted(0, rect.height()-45, 0, -22), Qt.AlignCenter, f"第 {index.row() + 1} 頁")
        font.setPointSize(9); painter.setFont(font)
        info = f"{page.source_page_label} | {page.effective_rotation}°"
        painter.drawText(rect.adjusted(5, rect.height()-22, -5, -5), Qt.AlignCenter | Qt.TextSingleLine, info)
        painter.restore()

    def sizeHint(self, option, index):
        return QSize(200, 280)

class PageListView(QListView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setViewMode(QListView.ListMode)
        self.setFlow(QListView.LeftToRight)
        self.setWrapping(True)
        self.setResizeMode(QListView.Adjust)
        self.setSpacing(20)
        self.setGridSize(QSize(210, 290))
        self.setMovement(QListView.Static)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(False)
        self.setDragDropMode(QAbstractItemView.DragDrop)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setSelectionRectVisible(True)
        
        self._drop_index = -1
        self._drop_rect = QRect()

    def _get_target_drop_info(self, pos: QPoint):
        count = self.model().rowCount()
        if count == 0:
            return 0, QRect(15, 15, 6, 280)

        index = self.indexAt(pos)
        first_idx = self.model().index(0)
        first_rect = self.visualRect(first_idx)
        last_idx = self.model().index(count - 1)
        last_rect = self.visualRect(last_idx)

        # 加強第一頁之前的判定感應 (擴大至 50px 範圍)
        if pos.x() < (first_rect.left() + first_rect.width() // 2) and pos.y() < (first_rect.bottom() + 10):
            return 0, QRect(first_rect.left() - 15, first_rect.top() + 6, 6, first_rect.height() - 12)

        if not index.isValid():
            if pos.y() > last_rect.bottom() or (pos.x() > last_rect.right() and pos.y() > last_rect.top()):
                return count, QRect(last_rect.right() + 6, last_rect.top() + 6, 6, last_rect.height() - 12)
            return -1, QRect()

        rect = self.visualRect(index)
        if pos.x() < rect.center().x():
            return index.row(), QRect(rect.left() - 12, rect.top() + 6, 6, rect.height() - 12)
        else:
            return index.row() + 1, QRect(rect.right() + 4, rect.top() + 6, 6, rect.height() - 12)

    def dragMoveEvent(self, event: QDragMoveEvent):
        if event.mimeData().hasFormat("application/x-pagemove"):
            idx, rect = self._get_target_drop_info(event.position().toPoint())
            self._drop_index = idx
            self._drop_rect = rect
            event.acceptProposedAction()
            self.viewport().update()
        else:
            super().dragMoveEvent(event)

    def dragLeaveEvent(self, event):
        self._drop_index = -1
        self._drop_rect = QRect()
        self.viewport().update()
        super().dragLeaveEvent(event)

    def dropEvent(self, event: QDropEvent):
        if event.mimeData().hasFormat("application/x-pagemove"):
            target = self._drop_index
            if target != -1:
                try:
                    raw_data = event.mimeData().data("application/x-pagemove")
                    source_rows = ast.literal_eval(bytes(raw_data).decode())
                    main_win = self.get_main_window()
                    if main_win:
                        main_win.save_history()
                        self.model().beginResetModel()
                        main_win.workspace.move_pages(source_rows, target)
                        self.model()._thumb_cache.clear()
                        self.model().endResetModel()
                        event.acceptProposedAction()
                except Exception as e:
                    print(f"移動失敗: {e}")
            self._drop_index = -1
            self._drop_rect = QRect()
            self.viewport().update()
        else:
            super().dropEvent(event)

    def paintEvent(self, event):
        super().paintEvent(event)
        if self._drop_index != -1 and not self._drop_rect.isNull():
            painter = QPainter(self.viewport())
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setBrush(QColor("#3b82f6"))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(self._drop_rect, 3, 3)

    def get_main_window(self):
        ptr = self.parent()
        while ptr:
            if isinstance(ptr, QMainWindow): return ptr
            ptr = ptr.parent()
        return None

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PDF排列哥 Pro")
        # 針對 2560*1440 螢幕，預設大小設為約 2/3 (1700x1000)
        self.resize(1300, 800)
        self.setAcceptDrops(True)
        self.thumb_path = Path("./.thumbnails")
        self.thumb_path.mkdir(exist_ok=True)
        self.backend = PyMuPdfBackend()
        self.workspace = WorkspaceManager(self.backend, self.thumb_path)
        self.thumb_service = ThumbnailService(self.workspace)
        self.export_service = ExportService(self.workspace)
        self.undo_stack = []; self.redo_stack = []
        self.thread_pool = QThreadPool.globalInstance()
        self.setup_ui()
        self.setup_shortcuts()

    def setup_ui(self):
        central = QWidget(); self.setCentralWidget(central)
        main_layout = QVBoxLayout(central); main_layout.setContentsMargins(0, 0, 0, 0); main_layout.setSpacing(0)
        
        # --- 頂部導覽列 ---
        header = QFrame()
        header.setFixedHeight(62)
        header.setStyleSheet("background-color: #ffffff; border-bottom: 1px solid #e2e8f0;")
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(15, 0, 15, 0)
        h_layout.setSpacing(10)
        
        # 標題 (24pt 粗體)
        title_label = QLabel("PDF排列哥")
        title_label.setStyleSheet("font-weight: 900; font-size: 24pt; color: #1e40af; min-width: 160px;")
        h_layout.addWidget(title_label)
        
        # 按鈕基礎樣式：10pt, normal weight, #64748b 解決鋸齒與模糊
        base_btn_style = """
            QPushButton {
                background-color: #f8fafc;
                color: #64748b;
                border: 1px solid #e2e8f0;
                border-radius: 4px;
                font-weight: normal;
                font-size: 10pt;
                padding: 2px;
            }
            QPushButton:hover {
                background-color: #f1f5f9;
                border-color: #cbd5e1;
            }
            QPushButton:pressed {
                background-color: #e2e8f0;
            }
            QPushButton:disabled {
                color: #cbd5e1;
                background-color: #ffffff;
                border-color: #f1f5f9;
            }
        """
        
        btn_w, btn_h = 88, 32
        
        # 檔案區
        self.btn_add = QPushButton("開啟檔案")
        self.btn_add.setFixedSize(btn_w, btn_h)
        self.btn_add.setStyleSheet(base_btn_style)
        h_layout.addWidget(self.btn_add)
        
        v_line1 = QFrame(); v_line1.setFrameShape(QFrame.VLine); v_line1.setFixedHeight(24); v_line1.setStyleSheet("color: #e2e8f0;"); h_layout.addWidget(v_line1)
        
        # 歷史區
        self.btn_undo = QPushButton("復原")
        self.btn_redo = QPushButton("重做")
        for b in [self.btn_undo, self.btn_redo]:
            b.setFixedSize(btn_w, btn_h)
            b.setEnabled(False)
            b.setStyleSheet(base_btn_style)
            h_layout.addWidget(b)

        v_line2 = QFrame(); v_line2.setFrameShape(QFrame.VLine); v_line2.setFixedHeight(24); v_line2.setStyleSheet("color: #e2e8f0;"); h_layout.addWidget(v_line2)
        
        # 操作區
        self.btn_rot_l = QPushButton("左轉 90°")
        self.btn_rot_180 = QPushButton("轉 180°")
        self.btn_rot_r = QPushButton("右轉 90°")
        self.btn_delete = QPushButton("刪除頁面")
        
        for b in [self.btn_rot_l, self.btn_rot_180, self.btn_rot_r, self.btn_delete]:
            b.setFixedSize(btn_w, btn_h)
            if b == self.btn_delete:
                b.setStyleSheet("""
                    QPushButton {
                        color: #f43f5e; 
                        background-color: #fff1f2; 
                        border: 1px solid #fecdd3;
                        border-radius: 4px;
                        font-weight: normal;
                        font-size: 10pt;
                    }
                    QPushButton:hover { background-color: #ffe4e6; border-color: #fda4af; }
                """)
            else:
                b.setStyleSheet(base_btn_style)
            h_layout.addWidget(b)

        h_layout.addStretch()
        
        # 匯出區
        self.btn_export = QPushButton("匯出結果")
        self.btn_export.setFixedSize(100, 38)
        self.btn_export.setStyleSheet("""
            QPushButton {
                background-color: #3b82f6; 
                color: white; 
                border-radius: 6px; 
                font-weight: normal;
                font-size: 10pt;
            }
            QPushButton:hover { background-color: #2563eb; }
        """)
        h_layout.addWidget(self.btn_export)
        
        main_layout.addWidget(header)
        
        # --- 工作區 ---
        self.model = PdfPageModel(self.workspace, self.thumb_service)
        self.view = PageListView()
        self.view.setModel(self.model); self.view.setItemDelegate(PageDelegate())
        # 增加左側 Padding 至 50px 確保插入感應
        self.view.setStyleSheet("QListView { background-color: #f8fafc; border: none; padding: 20px 20px 20px 50px; outline: none; }")
        main_layout.addWidget(self.view)
        
        # --- 底部狀態列 ---
        self.footer = QLabel(" 系統就緒 | 雙擊預覽 | 支持拖曳排序與框選")
        self.footer.setFixedHeight(32)
        self.footer.setStyleSheet("background-color: white; border-top: 1px solid #e2e8f0; color: #64748b; font-size: 10pt; padding-left: 20px; font-weight: normal;")
        main_layout.addWidget(self.footer)
        
        # 事件連接
        self.btn_add.clicked.connect(self.on_add_pdf)
        self.btn_rot_l.clicked.connect(lambda: self.on_rotate_pages(-90))
        self.btn_rot_180.clicked.connect(lambda: self.on_rotate_pages(180))
        self.btn_rot_r.clicked.connect(lambda: self.on_rotate_pages(90))
        self.btn_delete.clicked.connect(self.on_delete_pages)
        self.btn_export.clicked.connect(self.on_export_pdf)
        self.btn_undo.clicked.connect(self.undo); self.btn_redo.clicked.connect(self.redo)
        self.view.doubleClicked.connect(self.on_page_double_clicked)
        self.view.selectionModel().selectionChanged.connect(self.update_status)

    def setup_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+Z"), self, self.undo)
        QShortcut(QKeySequence("Ctrl+Y"), self, self.redo)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls(): event.accept()
        else: super().dragEnterEvent(event)

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            files = [u.toLocalFile() for u in event.mimeData().urls() if u.toLocalFile().lower().endswith('.pdf')]
            if files: self.save_history(); self.workspace.open_pdfs(files); self.model.refresh_all(); self.update_status()
            event.accept()
        else: super().dropEvent(event)

    def closeEvent(self, event):
        try:
            if self.thumb_path.exists(): shutil.rmtree(self.thumb_path, ignore_errors=True)
        except: pass
        event.accept()

    def save_history(self):
        self.undo_stack.append(copy.deepcopy(self.workspace.pages))
        self.redo_stack.clear(); self.update_history_buttons()

    def undo(self):
        if not self.undo_stack: return
        self.redo_stack.append(copy.deepcopy(self.workspace.pages))
        self.workspace.pages = self.undo_stack.pop(); self.model.refresh_all(); self.update_history_buttons()

    def redo(self):
        if not self.redo_stack: return
        self.undo_stack.append(copy.deepcopy(self.workspace.pages))
        self.workspace.pages = self.redo_stack.pop(); self.model.refresh_all(); self.update_history_buttons()

    def update_history_buttons(self):
        self.btn_undo.setEnabled(len(self.undo_stack) > 0); self.btn_redo.setEnabled(len(self.redo_stack) > 0)

    def update_status(self):
        self.footer.setText(f" 總計 {self.model.rowCount()} 頁 | 已選取 {len(self.view.selectionModel().selectedIndexes())} 頁")

    def on_add_pdf(self):
        files, _ = QFileDialog.getOpenFileNames(self, "開啟 PDF", "", "PDF 檔案 (*.pdf)")
        if files: self.save_history(); self.workspace.open_pdfs(files); self.model.refresh_all(); self.update_status()

    def on_page_double_clicked(self, index):
        page = index.data(Qt.UserRole); dlg = PreviewDialog(self)
        worker = HighResWorker(self.backend, page, f"第 {index.row() + 1} 頁")
        worker.signals.high_res_ready.connect(dlg.update_image); worker.signals.error.connect(dlg.show_error)
        self.thread_pool.start(worker); dlg.exec()

    def on_rotate_pages(self, angle: int):
        sel = self.view.selectionModel().selectedIndexes()
        if not sel: return
        indices = sorted([idx.row() for idx in sel]); self.save_history(); self.workspace.rotate_pages(indices, angle)
        for r in indices: self.model.start_thumbnail_worker(r); idx = self.model.index(r); self.model.dataChanged.emit(idx, idx, [Qt.DecorationRole, Qt.UserRole])
        self.update_status()

    def on_delete_pages(self):
        sel = self.view.selectionModel().selectedIndexes()
        if not sel: return
        self.save_history(); self.workspace.remove_pages([idx.row() for idx in sel]); self.model.refresh_all(); self.update_status()

    def on_export_pdf(self):
        if not self.workspace.pages: return
        path, _ = QFileDialog.getSaveFileName(self, "匯出 PDF", "合併結果.pdf", "PDF 檔案 (*.pdf)")
        if path:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            try: self.export_service.export(path); QMessageBox.information(self, "成功", f"匯出成功至：\n{path}")
            except Exception as e: QMessageBox.critical(self, "錯誤", str(e))
            finally: QApplication.restoreOverrideCursor()

if __name__ == "__main__":
    # 強制使用系統縮放倍率，並確保渲染平滑
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    # 設置預設字體為微軟正黑體，取消加粗以獲得清晰邊緣
    default_font = QFont("Microsoft JhengHei", 10)
    default_font.setStyleStrategy(QFont.PreferAntialias) 
    app.setFont(default_font)
    
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
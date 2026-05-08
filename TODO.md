# PDF Master — 改善計畫與實作清單

標示說明：`✅ 已完成` / `🚧 進行中` / `📌 規劃中` / `💡 建議`

實作時請同步更新本檔與 README.md。

---

## 🖼️ 圖片轉 PDF（新功能）

> **背景**：辦公室常需將掃描圖片（JPG/TIFF）與現有 PDF 合併。PyMuPDF 原生支援讀入多種圖片格式，**無須新增任何相依套件**。

### 支援格式

| 格式 | 備註 |
|------|---------|
| `.jpg` / `.jpeg` | 最常見 |
| `.png` | 支援透明背景（轉為 PDF 時自動白底）|
| `.tiff` / `.tif` | 掃描文件常用格式；**支援多頁 TIFF**（每幀記為一頁）|
| `.bmp` | Windows 點陣圖 |
| `.webp` | 現代網頁圖片 |
| `.gif` | 取靜態幀轉換 |

### 實作狀態

- `✅ 已完成` **Step 1 — `core/models.py`：新增 `ImageInspectionResult`**
- `✅ 已完成` **Step 2 — `core/protocols.py`：`PdfBackend` 新增 `inspect_image()`**
- `✅ 已完成` **Step 3 — `adapters/pymupdf_backend.py`：實作 `inspect_image()`**
- `✅ 已完成` **Step 4 — `core/workspace.py`：`open_files()` 統一入口**
- `✅ 已完成` **Step 5 — `adapters/pymupdf_backend.py`：`_open_source_as_pdf()` 支援圖片**
- `✅ 已完成` **Step 6 — `gui/presenter.py`：檔案對話框加入圖片 filter**
- `✅ 已完成` **測試補齊 — `tests/test_workspace.py`**
  - commit: `feat(image-to-pdf): 完整實作圖片轉 PDF 功能`

---

## 🎨 GUI 外觀現代化

### 高優先度

- `✅ 已完成` **QToolBar 重構 + SVG 圖示系統（2026-05-08）**
  - `gui/icons.py` AppIcons 圖示管理器（QStyle SP_ + fallback SVG）
  - `gui/styles.py` TOOLBAR / TOOLBAR_PRIMARY QSS
  - `gui_main.py` `_build_toolbar()` 取代 `_build_header()`
  - commit: `feat(gui): QToolBar 重構 + SVG 圖示系統 + 圖片 drag-and-drop 支援`

- `✅ 已完成` **現代化外觀三連升級（2026-05-08）**
  - **建議一（圓角 + OS 字體）**：全面升級圓角至 8–10px；`main()` 改用 `app.font()` 跟隨 OS（Win11 Segoe UI Variable / macOS SF Pro）
  - **建議二（卡片陰影）**：`PageCardDelegate.paint()` 以多層低透明矩形繪製投影；新增 `_draw_card_shadow()` 輔助函式；縮圖加圓角 `QPainterPath` 剪裁
  - **建議四（深色模式）**：`UiStyles.is_dark_mode()` 靜態方法偵測 `QPalette.Window.lightness()`；`UiStyles.apply_theme()` 套用完整 Fusion Dark Palette；`MainWindow(is_dark=True/False)` 自動切換 Toolbar / Footer / ListView QSS
  - commit: `feat(gui): 現代化外觀 — 圓角升級 + 卡片陰影 + 深色模式自動偵測`

### 規劃中

- `📌 規劃中` **建議三：遷移至 PySide6-Fluent-Widgets（中期）**
  - 套件：`pip install PySide6-Fluent-Widgets`
  - 目標：Win11 Mica/Acrylic 毛玻璃背景、FluentToolBar / CommandBar、完整深淺色主題切換
  - 遷移範圍：`QToolBar` → `CommandBar`、`QPushButton` → `PushButton`、`QMenu` → `RoundMenu`
  - 預估影響：`gui_main.py` + `gui/views.py` + `gui/styles.py`（中規模重構）
  - 參考：https://qfluentwidgets.com/zh/

---

## 🔧 架構與代碼品質

### 高優先度

- `✅ 已完成` **錯誤隔離：`open_pdfs()` 批次處理改為逐檔 try/except**
- `✅ Phase 2 完成` **GUI 分層：MVP 介面解耦**
- `✅ 已完成` **版本鎖定：新增 `pyproject.toml`**
- `✅ 已完成` **`export_pages()` 中 `getattr()` 安全拆除**

### 中優先度

- `✅ 已完成` **`_page_rotations()` N+1 問題**
- `✅ 已完成` **`WorkspaceManager` 縮圖目錄職責拆分**
- `✅ 已完成` **`WorkspaceSnapshot.pages` 改為 `list[PageSnapshot]` dataclass**

---

## 🧪 測試覆蓋率提升

- `✅ 已完成` **`test_presenter.py`**
- `✅ 已完成` **`ExportOptions` 死角測試**
- `✅ 已完成` **`WorkspaceManager` 邊界條件測試**
- `✅ 已完成` **`_expand_labels()` 單元測試**
- `✅ 已完成` **新增 `test_export_service.py`**
- `✅ 已完成` **`open_pdfs()` tuple 回傳測試**
- `✅ 已完成` **圖片轉 PDF 測試**
- `📌 規劃中` **引入 `pytest` + `pytest-cov`，目標行覆蓋率 ≥ 80%**

---

## ⚙️ CI/CD 與 DevOps

- `✅ 已完成` **`.github/workflows/ci.yml`**
- `✅ 已完成` **`ruff` 規則：E / F / I / UP**
- `✅ 已完成` **`mypy` `core/` strict mode**

---

## 📦 匯出與文件結構

- `📌 規劃中` **保留書簽（TOC）**
- `📌 規劃中` **保留附件（`keep_attachments`）**
- `📌 規劃中` **保留互動表單（`keep_forms`）**
- `📌 規劃中` **子資料夾遞迴掃描**
- `📌 規劃中` **匯出前 Preflight 報告**

---

## ✏️ 編輯與工作階段

- `📌 規劃中` **工作階段存檔／還原（`.pdfmaster` 專案檔）**
- `📌 規劃中` **複製／貼上頁**
- `📌 規劃中` **插入空白頁／章節分隔頁**
- `📌 規劃中` **清單檢視模式**

---

## 🛡️ 安全性

- `📌 規劃中` **路徑遊走防護（Path Traversal）**
- `📌 規劃中` **輸出路徑禁止覆寫來源檔**

---

## ✨ 進階功能（選做）

- `📌 規劃中` **浮水印／頁碼 Stamp**
- `📌 規劃中` **裁切框（Crop Box）視覺編輯**
- `📌 規劃中` **監看資料夾／掃描佇列**
- `📌 規劃中` **多語言 i18n 支援**

---

## ✅ 已實作（封存記錄）

- 匯出選取頁、資料夾批次加入（單層）
- 匯出選項對話框（metadata 來源策略、頁碼標籤）
- `metadata_policy`：`first_pdf` / `last_pdf` / `empty` 於 PyMuPDF 匯出路徑
- 加密來源警示
- 快捷鍵 Ctrl+A / Delete / Ctrl+Shift+E
- `FakeBackend` + `test_workspace.py` 基礎測試套件
- DIP 架構：`core/protocols.py` PdfBackend Protocol
- **GUI 分層 Phase 1**：`gui/` 套件拆分（styles / workers / dialogs / models / views）
- **GUI 分層 Phase 2**：MVP 介面解耦（interfaces / presenter）+ Presenter 單元測試
- **修復** `gui_main.py` 重複 `QKeySequence` import
- **高優先度修復（2026-05-08）**：open_pdfs() 批次錯誤隔離、export_pages() 移除 getattr()、_page_rotations() N+1 修復、pyproject.toml 鎖定
- **中優先度完成（2026-05-08）**：ThumbnailService、PageSnapshot dataclass、CI/CD
- **圖片轉 PDF 完成（2026-05-08）**：ImageInspectionResult、inspect_image()、open_files()、_open_source_as_pdf()、load_files()、測試 ×5
- **QToolBar 重構（2026-05-08）**：AppIcons、TOOLBAR QSS、_build_toolbar()、圖片 drag-and-drop
- **現代化外觀（2026-05-08）**：圓角 10px、OS 字體、卡片陰影、深色模式自動偵測

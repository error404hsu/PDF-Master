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
  - **建議一（圓角 + OS 字體）**：全面升級圓角至 8–10px；`main()` 改用 `app.font()` 跟隨 OS
  - **建議二（卡片陰影）**：`PageCardDelegate.paint()` 多層低透明矩形繪製投影
  - **建議四（深色模式）**：`UiStyles.apply_theme()` 套用完整 Fusion Dark Palette
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

## ⚙️ 設定系統

- `✅ 已完成` **`gui/settings.py` — AppSettings（QSettings 持久化）**
  - 輸出偏好：metadata、頁碼標籤、metadata 來源策略
  - 單頁輸出模式（每頁獨立 PDF）
  - 單頁檔名樣板（支援 `{n}` / `{source}` 佔位符）
  - PDF 壓縮等級（deflate level 0–9，對應 `ExportOptions.deflate_level`）
  - 輸出後自動開啟資料夾（跨平台：Windows / macOS / Linux）
  - 輸出完成提示開關
  - 預設輸出資料夾
  - 縮圖縮放倍率

- `✅ 已完成` **`gui/dialogs.py` — SettingsDialog（統一設定視窗）**
  - 「輸出設定」方塊：含上述所有輸出選項
  - 「介面設定」方塊：預設輸出資料夾、縮圖倍率
  - 取代舊 `ExportPdfDialog`（不再每次輸出前彈窗詢問）
  - 快捷鍵 `Ctrl+,` 開啟設定

- `📌 規劃中` **復原步驟上限：可於設定調整（目前硬寫 20）**
- `📌 規劃中` **語言 / 顯示語言切換（預留 i18n 入口）**
- `📌 規劃中` **每列縮圖欄數（固定 2/3/4/自動）**

---

## 📦 輸出與文件結構

- `✅ 已完成` **合併後 PDF 頁碼依畫面排列順序重新連續編號（2026-05-13）**
  - 修正 `_apply_page_labels()`：改用 `style="D", startpage=0, firstpagenum=1`
  - 不再沿用 `source_page_label`（來源原始頁碼）
- `✅ 已完成` **PDF 壓縮等級可調（deflate_level 0–9）**
  - `ExportOptions.deflate_level` 欄位（預設 6）
  - `export_pages()` 的 `out_doc.save()` 使用 `deflate_level` 參數
- `📌 規劃中` **保留書簽（TOC）**
- `📌 規劃中` **保留附件（`keep_attachments`）**
- `📌 規劃中` **保留互動表單（`keep_forms`）**
- `📌 規劃中` **子資料夾遞迴掃描**
- `📌 規劃中` **輸出前 Preflight 報告**

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

- 輸出選取頁、資料夾批次加入（單層）
- 輸出選項對話框（metadata 來源策略、頁碼標籤）→ 已遷移至 SettingsDialog
- `metadata_policy`：`first_pdf` / `last_pdf` / `empty` 於 PyMuPDF 輸出路徑
- 加密來源警示
- 快捷鍵 Ctrl+A / Delete / Ctrl+Shift+E / Ctrl+,（設定）
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
- **設定系統 + 輸出改版（2026-05-13）**：AppSettings、SettingsDialog、「匯出」→「輸出」、輸出單頁模式、不再每次彈窗
- **輸出增強（2026-05-13）**：輸出後開資料夾、單頁檔名樣板、壓縮等級可調、ExportOptions.deflate_level
- **頁碼修正（2026-05-13）**：合併後 PDF 依畫面排列順序重新連續編號

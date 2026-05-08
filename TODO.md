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

### 實作指引

#### Step 1 — `core/models.py`：新增 `ImageInspectionResult`

```python
@dataclass(slots=True, frozen=True)
class ImageInspectionResult:
    path: Path
    page_count: int          # 單張圖片 = 1，多頁 TIFF = 幀數
    width_px: int
    height_px: int
    format: str              # "jpeg" / "png" / "tiff" 等
    encrypted: bool = False  # 圖片不加密，保留為統一介面

    def __post_init__(self):
        object.__setattr__(self, "path", Path(self.path))
        if self.page_count < 1:
            raise ValueError("page_count must be >= 1")
```

#### Step 2 — `core/protocols.py`：`PdfBackend` 新增 `inspect_image()`

```python
class PdfBackend(Protocol):
    def inspect_pdf(self, path: Path) -> PdfInspectionResult: ...

    def inspect_image(self, path: Path) -> ImageInspectionResult: ...
    # 回傳圖片基本資訊；多頁 TIFF 的 page_count > 1

    def render_thumbnail(self, ...) -> Path: ...
    def export_pages(self, ...) -> Path: ...
```

#### Step 3 — `adapters/pymupdf_backend.py`：實作 `inspect_image()`

```python
SUPPORTED_IMAGE_SUFFIXES = frozenset(
    {".jpg", ".jpeg", ".png", ".tiff", ".tif", ".bmp", ".webp", ".gif"}
)

def inspect_image(self, path: Path) -> ImageInspectionResult:
    import fitz
    path = Path(path)
    with fitz.open(path) as doc:
        page_count = doc.page_count
        first_page = doc.load_page(0)
        rect = first_page.rect
        return ImageInspectionResult(
            path=path,
            page_count=page_count,
            width_px=int(rect.width),
            height_px=int(rect.height),
            format=path.suffix.lstrip(".").lower(),
        )
```

#### Step 4 — `core/workspace.py`：`open_files()` 取代 `open_pdfs()`

```python
IMAGE_SUFFIXES = frozenset(
    {".jpg", ".jpeg", ".png", ".tiff", ".tif", ".bmp", ".webp", ".gif"}
)

def open_files(
    self, paths: Iterable[str | Path]
) -> tuple[list[str], list[Path]]:
    added_ids: list[str] = []
    failed: list[Path] = []
    for raw_path in paths:
        path = Path(raw_path)
        try:
            if path.suffix.lower() in IMAGE_SUFFIXES:
                ids = self._open_image(path)
            else:
                ids = self._open_pdf(path)
            added_ids.extend(ids)
        except Exception:
            failed.append(path)
    return added_ids, failed
```

#### Step 5 — `adapters/pymupdf_backend.py`：`export_pages()` 支援圖片路徑

```python
def _open_source_as_pdf(self, source_path: Path):
    suffix = source_path.suffix.lower()
    if suffix in SUPPORTED_IMAGE_SUFFIXES:
        img_doc = self.fitz.open(source_path)
        pdf_bytes = img_doc.convert_to_pdf()
        img_doc.close()
        return self.fitz.open("pdf", pdf_bytes)
    return self.fitz.open(source_path)
```

#### Step 6 — `gui/presenter.py`：`on_add_pdf` 檔案選擇加入圖片 filter

```python
filters = "All Supported Files (*.pdf *.jpg *.jpeg *.png *.tif *.tiff *.bmp *.webp *.gif);;PDF Files (*.pdf);;Image Files (*.jpg *.jpeg *.png *.tif *.tiff *.bmp *.webp *.gif)"
```

### 測試項目

- `open_files()` 傳入 JPG 應正常產生一頁
- `open_files()` 傳入多頁 TIFF 應產生對應頁數
- 混入 PDF + JPG 再匯出，頁序應和工作區順序一致
- 損壞圖片在 `open_files()` 中應列入 `failed_paths`，不中斷其餘對象

### 相關檔案

```
core/models.py           ← 新增 ImageInspectionResult
core/protocols.py        ← 新增 inspect_image()
core/workspace.py        ← open_files() 取代 open_pdfs()
adapters/pymupdf_backend.py  ← inspect_image() + _open_source_as_pdf()
gui/presenter.py         ← 檔案對話框 filter
tests/test_workspace.py  ← 圖片相關測試案例
```

---

## 🔧 架構與代碼品質

### 高優先度

- `✅ 已完成` **錯誤隔離：`open_pdfs()` 批次處理改為逐檔 try/except**
  - 每個檔案獨立 try/except，回傳 `(added_ids, failed_paths)` tuple
  - UI 層可根據 `failed_paths` 對用戶彈出具體提示
  - 相關檔案：`core/workspace.py` `open_pdfs()`
  - commit: fix(workspace): open_pdfs() 批次錯誤隔離

- `✅ Phase 2 完成` **GUI 分層：MVP 介面解耦**
  - **Phase 1 完成**（`gui/` 套件已創建）
    - `gui/styles.py` — 集中管理所有 QSS 樣式常數與色票
    - `gui/workers.py` — `ThumbnailWorker` / `HighResWorker` 背景執行緒
    - `gui/dialogs.py` — `PreviewDialog` / `ExportPdfDialog` 對話框
    - `gui/models.py`  — `SnapshotHistory` / `PdfPageModel` Qt 資料模型
    - `gui/views.py`   — `PageCardDelegate` / `PageListView` 視圖元件
    - `gui_main.py` 精簡化：僅保留 `MainWindow` 骨架與 `main()` 入口
  - **Phase 2 完成**：引入 `gui/interfaces.py`（Protocol）與 `gui/presenter.py`（MVP 分層）
    - `gui/interfaces.py` — `IMainView` / `IMainPresenter` `typing.Protocol` 定義
    - `gui/presenter.py` — `MainPresenter` 承載所有 `on_*` / `load_pdfs` / `undo` / `redo` 業務邏輯
    - `MainWindow` 實作 `IMainView`，僅保留純 UI 建構與 Signal 轉中
    - `tests/test_presenter.py` — `MockView` 不啟動 Qt 的單元測試
  - **MVP 架構說明**：View（MainWindow）實作 `IMainView` Protocol，僅負責 UI 建構與事件轉發；Presenter（MainPresenter）透過 `IMainView` 介面呼叫 View，不持有任何 `QWidget` 強引用，可在純 Python 環境下進行單元測試；Model（`PdfPageModel`）由 View 拥有，Presenter 透過構造子注入。兩者透過 `typing.Protocol` 完全解耦。
  - 目標結構：`views/`（純 UI 元件）、`controllers/`（業務橋接）
  - `core/` 保持完全無 PySide6 依賴

- `✅ 已完成` **版本鎖定：新增 `pyproject.toml`**
  - 新增 `pyproject.toml`，使用 `pymupdf>=1.24,<2.0`、`PySide6>=6.6,<7.0` 上下界限制
  - 包含 `[project.optional-dependencies]` dev 群組（pytest / ruff / mypy）
  - 建議後續用 `uv lock` 或 `pip-compile` 產生完整 lock file

- `✅ 已完成` **`export_pages()` 中 `getattr()` 安全拆除**
  - `ExportOptions` 已是 `dataclass(frozen=True)`，直接使用屬性名
  - 同步修復 `_page_rotations()` N+1 問題，改為列表推導式
  - commit: refactor(pymupdf): export_pages() 移除 getattr()

### 中優先度

- `✅ 已完成` **`_page_rotations()` N+1 問題**
  - 改為：`[page.rotation for page in doc]`

- `✅ 已完成` **`WorkspaceManager` 縮圖目錄職責拆分**
  - `ThumbnailService`（`core/thumbnail_service.py`）負責管理縮圖資料夾生命週期
  - `WorkspaceManager` 不再持有 `thumbnail_dir`，僅保留 `render_thumbnail_to_disk()` 低階接口
  - commit: refactor(core): 建立 ThumbnailService，WorkspaceManager 縮圖職責拆分

- `✅ 已完成` **`WorkspaceSnapshot.pages` 改為 `list[PageSnapshot]` dataclass**
  - `PageSnapshot` dataclass 包含全部欄位：index / page_id / source_doc_id / source / source_page_index / label / base_rotation / rotation_delta / effective_rotation / thumb_path
  - `__getitem__` 保持向後相容（允許 `snapshot.pages[i]["label"]`）
  - commit: feat(models): PageSnapshot dataclass + WorkspaceSnapshot 強型別化

---

## 🧪 測試覆蓋率提升

- `✅ 已完成` **`test_presenter.py`** — MockView 不啟動 Qt，覆蓋 load_pdfs / rotate / undo 邏輯
- `✅ 已完成` **`ExportOptions` 死角測試** — `test_export_service.py` `ExportOptionsValidationTests`
- `✅ 已完成` **`WorkspaceManager` 邊界條件測試** — 空輸入、越界索引、空操作等情境
- `✅ 已完成` **`_expand_labels()` 單元測試** — 羅馬字 R/r、字母 A/a、純前置、多段規則、缺 startpage、越界等 14 個案例
- `✅ 已完成` **新增 `test_export_service.py`** — ExportService / ExportOptions / export_selected / can_export 完整覆蓋
- `✅ 已完成` **`open_pdfs()` tuple 回傳測試** — 成功 / 部分失敗 / 全失敗 / 空輸入 四情境
- `📌 規劃中` **引入 `pytest` + `pytest-cov`，目標行覆蓋率 ≥ 80%**

---

## ⚙️ CI/CD 與 DevOps

- `✅ 已完成` **`.github/workflows/ci.yml`**
  - 觸發條件：push main / PR，Python matrix 3.11 + 3.12
  - 步驟：`pytest` → `ruff check` → `mypy`
  - 設定單一真實來源：`pyproject.toml`（無重複配置）
- `✅ 已完成` **`ruff` 規則：E / F / I / UP**（整合至 `pyproject.toml [tool.ruff.lint]`）
- `✅ 已完成` **`mypy` `core/` strict mode**（整合至 `pyproject.toml [tool.mypy]`）

---

## 📦 匯出與文件結構

- `📌 規劃中` **保留書簽（TOC）**— `ExportOptions.keep_bookmarks`
- `📌 規劃中` **保留附件（`keep_attachments`）**
- `📌 規劃中` **保留互動表單（`keep_forms`）**
- `📌 規劃中` **子資料夾遞迴掃描**
- `📌 規劃中` **匯出前 Preflight 報告**（缺字型、頁面尺寸不一致）

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
- **修復** `gui_main.py` 重複 `QKeySequence` import（`QtCore` 移除，保留 `QtGui`）
- **高優先度修復（2026-05-08）**：
  - `open_pdfs()` 批次錯誤隔離（逐檔 try/except + failed_paths 回傳）
  - `export_pages()` 移除 `getattr()`，改用 ExportOptions 直接屬性存取
  - `_page_rotations()` N+1 問題修復（列表推導式）
  - 新增 `pyproject.toml` 版本上下界鎖定 + dev 依賴群組
- **中優先度完成（2026-05-08）**：
  - `ThumbnailService` 建立，WorkspaceManager 縮圖職責拆分
  - `PageSnapshot` dataclass + `WorkspaceSnapshot` 強型別化
  - 全套測試補齊（ExportOptions / WorkspaceManager 邊界 / _expand_labels / test_export_service / open_pdfs tuple）
  - CI/CD（`.github/workflows/ci.yml`）：pytest + ruff + mypy，Python 3.11/3.12 matrix
  - 縮圖載入失敗顯示修正：FAILED 狀態改以紅色警告文字呈現

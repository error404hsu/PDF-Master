# PDF Master — 改善計畫與實作清單

標示說明：`✅ 已完成` / `🛧 進行中` / `📌 規劃中` / `💡 建議`

實作時請同步更新本檔與 README.md。

---

## 🖼️ 圖片轉 PDF（新功能）

> **背景**：辦公室常需將揃描圖片（JPG/TIFF）與現有 PDF 合併。PyMuPDF 原生支援讀入多種圖片格式，**無須新增任何相依套件**。

### 支援格式

| 格式 | 備註 |
|------|---------|
| `.jpg` / `.jpeg` | 最常見 |
| `.png` | 支援透明背景（轉為 PDF 時自動白底）|
| `.tiff` / `.tif` | 揃描文件常用格式；**支援多頁 TIFF**（每幀記為一頁）|
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
    # fitz.open() 可直接開啟圖片，多頁 TIFF 會自動展開多頁
    with fitz.open(path) as doc:
        page_count = doc.page_count  # 多頁 TIFF 為幀數
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
    """自動依副檔名將 PDF 或圖片加入工作區。
    回傳 (added_doc_ids, failed_paths)。
    """
    added_ids: list[str] = []
    failed: list[Path] = []

    for raw_path in paths:
        path = Path(raw_path)
        try:
            if path.suffix.lower() in IMAGE_SUFFIXES:
                ids = self._open_image(path)   # 圖片路徑
            else:
                ids = self._open_pdf(path)     # PDF 路徑（原邏輯）
            added_ids.extend(ids)
        except Exception:
            failed.append(path)

    return added_ids, failed

def _open_image(self, path: Path) -> list[str]:
    """將圖片檔轉為臨時 PDF bytes 再進入工作區。多頁 TIFF 會展開多頁。"""
    result = self.backend.inspect_image(path)
    doc_id = new_id()
    inspection = PdfInspectionResult(
        path=path,
        page_count=result.page_count,
        metadata={},
        page_rotations=[0] * result.page_count,
    )
    self._inspection_cache[doc_id] = inspection
    self.source_pdfs[doc_id] = SourcePdf(
        doc_id=doc_id,
        path=path,
        page_count=result.page_count,
    )
    for page_index in range(result.page_count):
        self.pages.append(
            PageRef(
                page_id=new_id(),
                source_doc_id=doc_id,
                source_path=path,
                source_page_index=page_index,
            )
        )
    return [doc_id]
```

#### Step 5 — `adapters/pymupdf_backend.py`：`export_pages()` 支援圖片路徑

`fitz.open()` 對圖片的字底識別即可直接讀入，選從 `insert_pdf` 前先轉為 PDF bytes：

```python
# 在 export_pages() 的圖片路徑中取代直接 fitz.open(source_path)
def _open_source_as_pdf(self, source_path: Path):
    """圖片或 PDF 都回傳可 insert_pdf 的 fitz.Document（統一介面）"""
    suffix = source_path.suffix.lower()
    if suffix in SUPPORTED_IMAGE_SUFFIXES:
        img_doc = self.fitz.open(source_path)     # 開啟圖片
        pdf_bytes = img_doc.convert_to_pdf()      # 轉為 PDF bytes
        img_doc.close()
        return self.fitz.open("pdf", pdf_bytes)   # 回傳 PDF 文件物件
    return self.fitz.open(source_path)            # 原生 PDF
```

將 `export_pages()` 中的 `self.fitz.open(source_path)` 替換為 `self._open_source_as_pdf(source_path)`，其餘邏輯不變。

#### Step 6 — `gui_main.py`：檔案選擇對話框加入圖片 filter

```python
# 原來的 PDF filter
filters = "PDF Files (*.pdf)"

# 改為
 filters = "All Supported Files (*.pdf *.jpg *.jpeg *.png *.tif *.tiff *.bmp *.webp *.gif);;PDF Files (*.pdf);;Image Files (*.jpg *.jpeg *.png *.tif *.tiff *.bmp *.webp *.gif)"
```

### 測試項目

- `open_files()` 傳入 JPG 应正常產生一頁
- `open_files()` 傳入多頁 TIFF 應產生對應頁數
- 混入 PDF + JPG 再匯出，頁序應和工作區順序一致
- 損壞圖片在 `open_files()` 中應列入 `failed_paths`，不中斷其餘對象

### 相關檔案

```
core/models.py           ← 新增 ImageInspectionResult
core/protocols.py        ← 新增 inspect_image()
core/workspace.py        ← open_files() 取代 open_pdfs()
adapters/pymupdf_backend.py  ← inspect_image() + _open_source_as_pdf()
gui_main.py              ← 檔案對話框 filter
tests/test_workspace.py  ← 圖片相關測試案例
```

---

## 🔧 架構與代碼品質

### 高優先度

- `📌 規劃中` **錯誤隔離：`open_pdfs()` 批次處理改為逐檔 try/except**
  - 目前任一 PDF 損壞就中斷整個批次
  - 建議回傳 `(added_ids, failed_paths)` tuple，UI 層再核對失敗清單對用戶提示
  - 相關檔案：`core/workspace.py` `open_pdfs()`

- `🛧 進行中` **GUI 分層：將 `gui_main.py`（40KB）拆分成 MVC/MVP**
  - **Phase 1 完成**（`gui/` 套件已創建）
    - `gui/styles.py` — 集中管理所有 QSS 樣式常數與色票
    - `gui/workers.py` — `ThumbnailWorker` / `HighResWorker` 背景執行緒
    - `gui/dialogs.py` — `PreviewDialog` / `ExportPdfDialog` 對話框
    - `gui/models.py`  — `SnapshotHistory` / `PdfPageModel` Qt 資料模型
    - `gui/views.py`   — `PageCardDelegate` / `PageListView` 視圖元件
    - `gui_main.py` 精簡化：僅保留 `MainWindow` 骨架與 `main()` 入口
  - **Phase 2 規劃中**：引入 `gui/interfaces.py`（Protocol）與 `gui/presenter.py`（MVP 分層）
  - 目標結構：`views/`（純 UI 元件）、`controllers/`（業務橋接）
  - `core/` 保持完全無 PySide6 依賴

- `📌 規劃中` **版本鎖定：新增 `requirements-lock.txt` 或改用 `pyproject.toml`**
  - 目前 `requirements.txt` 將 `pymupdf>=1.24`、`PySide6>=6.6` 定義為最小版本限制
  - 建議使用 `uv` 或 `pip-compile` 產生 lock file

- `📌 規劃中` **`export_pages()` 中 `getattr()` 安全拆除**
  - `ExportOptions` 已是 `dataclass(frozen=True)`，可直接使用屬性名

### 中優先度

- `📌 規劃中` **`_page_rotations()` N+1 問題**
  - 候選方案：`[page.rotation for page in doc]`

- `📌 規劃中` **`WorkspaceManager` 縮圖目錄職責拆分**
  - `ThumbnailService` 應負責管理資料夾生命週期

- `📌 規劃中` **`WorkspaceSnapshot.pages` 改為 `list[PageSnapshot]` dataclass**

---

## 🧪 測試覆蓋率提升

- `📌 規劃中` **`ExportOptions` 死角測試**
- `📌 規劃中` **`WorkspaceManager` 邊界條件測試**
- `📌 規劃中` **`_expand_labels()` 單元測試**（羅馬字 R/r、字母 A/a、純前置）
- `📌 規劃中` **新增 `test_export_service.py`**
- `📌 規劃中` **引入 `pytest` + `pytest-cov`，目標行覆蓋率 ≥ 80%**

---

## ⚙️ CI/CD 與 DevOps

- `📌 規劃中` **新增 GitHub Actions workflow `.github/workflows/ci.yml`**
  - 觸發條件：push main / PR，Python matrix 3.11 + 3.12
  - 步驟：`pytest` → `ruff check` → `mypy`
- `📌 規劃中` **`ruff.toml`：E / F / I / UP 規則**
- `📌 規劃中` **`mypy`：`core/` strict mode**

---

## 📦 匯出與文件結構

- `📌 規劃中` **保留書籤（TOC）**— `ExportOptions.keep_bookmarks`
- `📌 規劃中` **保留附件（`keep_attachments`）**
- `📌 規劃中` **保留互動表單（`keep_forms`）**
- `📌 規劃中` **子資料夾遞迴揃描**
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
- `📌 規劃中` **裁切框（Crop Box）視覚編輯**
- `📌 規劃中` **監看資料夾／揃描佇列**
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

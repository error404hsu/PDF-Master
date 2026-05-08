# PDF Master 📄

> 一套以 Python + PySide6 打造的桌面版 PDF 頁面編輯器，支援多檔合併、重新排序、旋轉與匯出。

---

## ✨ 功能一覽

| 功能 | 狀態 |
|------|---------|
| 開啟多個 PDF / 整個資料夾（單層）| ✅ |
| 縮圖預覽所有頁面 | ✅ |
| 拖放重新排序頁面 | ✅ |
| 旋轉頁面（90° 倍數）| ✅ |
| 刪除選取頁面（支援 Ctrl+A / Delete）| ✅ |
| 匯出選取或全部頁面為新 PDF | ✅ |
| Metadata 來源策略（first\_pdf / last\_pdf / empty）| ✅ |
| 頁碼標籤（Page Labels）保留 | ✅ |
| 加密 PDF 警示 | ✅ |
| 快捷鍵 Ctrl+A / Delete / Ctrl+Shift+E | ✅ |
| 復原 / 重做（Ctrl+Z / Ctrl+Y）| ✅ |
| MVP 介面解耦（Presenter + IMainView Protocol）| ✅ |
| 保留書簽（TOC）| 🚧 規劃中 |
| 工作階段存檔／還原 | 🚧 規劃中 |
| 子資料夾遞迴揃描 | 🚧 規劃中 |

---

## 🖥️ 環境需求

- Python **3.11+**
- [PyMuPDF](https://pymupdf.readthedocs.io/) `>= 1.24`
- [PySide6](https://doc.qt.io/qtforpython/) `>= 6.6`

---

## 🚀 安裝與執行

```bash
# 1. 複製專案
git clone https://github.com/error404hsu/PDFMaster.git
cd PDFMaster

# 2. （建議）建立虛擬環境
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate

# 3. 安裝相依套件
pip install -r requirements.txt

# 4. 啟動 GUI
python main.py
```

### 打包成單一執行檔（Windows）

本專案已附 `PDFMaster.spec`，可直接使用 PyInstaller 打包：

```bash
pip install pyinstaller
pyinstaller PDFMaster.spec
# 輸出位於 dist/ 資料夾
```

---

## 📂 專案結構

```
PDFMaster/
├── gui_main.py          # PySide6 主視窗（View 層）
├── main.py              # 应用程式入口
├── requirements.txt     # 相依套件
├── PDFMaster.spec       # PyInstaller 打包設定
├── PDF.ico              # 應用程式圖示
│
├── core/                # 核心業務邏輯（無 UI 相依）
│   ├── models.py        # 資料模型：PageRef、ExportOptions 等
│   ├── workspace.py     # WorkspaceManager：頁面狀態管理
│   ├── thumbnail_service.py  # 縮圖產生服務
│   ├── export_service.py     # 匯出服務
│   ├── protocols.py     # PdfBackend Protocol 介面定義
│   └── exceptions.py    # 自訂例外類別
│
├── gui/                 # GUI 套件（Phase 1 + Phase 2）
│   ├── interfaces.py    # IMainView / IMainPresenter Protocol 定義
│   ├── presenter.py     # MainPresenter — 所有業務邏輯
│   ├── styles.py        # QSS 樣式常數
│   ├── workers.py       # 背景執行緒
│   ├── dialogs.py       # 對話框元件
│   ├── models.py        # Qt 資料模型
│   └── views.py         # 視圖與委派元件
│
├── adapters/            # 後端實作（目前為 PyMuPDF）
│   └── pymupdf_backend.py
│
└── tests/               # 測試套件
    ├── test_workspace.py
    └── test_presenter.py  # Presenter 單元測試（不啟動 Qt）
```

### 架構說明

本專案採用 **MVP（Model-View-Presenter）+ 依賴反轉（DIP）** 雙層設計：

| 層級 | 模組 | 職責 |
|------|--------|------|
| **Model** | `core/` | 業務邏輯、資料結構，無任何 UI 相依 |
| **View** | `gui_main.MainWindow` | 純 UI 建構、Signal 轉發，實作 `IMainView` |
| **Presenter** | `gui/presenter.MainPresenter` | 所有業務操作，透過 `IMainView` 呼叫 View |
| **Backend** | `adapters/` | `PdfBackend` Protocol 實作，可替換 |

Presenter 不持有任何 `QWidget` 強引用，可在純 Python 環境下進行單元測試。

---

## ⌨️ 快捷鍵

| 按鍵 | 功能 |
|------|---------|
| `Ctrl+A` | 全選所有頁面 |
| `Delete` | 刪除選取頁面 |
| `Ctrl+Shift+E` | 匯出選取頁面 |
| `Ctrl+Z` | 復原 |
| `Ctrl+Y` | 重做 |

---

## 🗺️ 開發路線圖

詳見 [TODO.md](TODO.md)，主要規劃項目包含：

- 圖片轉 PDF 支援（JPG / PNG / TIFF 等）
- 工作階段存檔／還原（`*.pdfmaster` 專案檔）
- 保留書簽（TOC）與互動表單
- 子資料夾遞迴揃描
- 浮水印／頁碼 Stamp
- GitHub Actions CI（pytest + ruff + mypy）

---

## 📜 授權

本專案採用 [MIT License](LICENSE)。

---

## 🤝 貢獻

歡迎開 Issue 回報問題或提出功能建議。若要送 PR，請確保：

1. 核心邏輯放於 `core/`，UI 邏輯不進入 `core/`
2. `gui/presenter.py` 不得 import 任何 `QWidget` 子類別
3. 新增功能請附對應測試於 `tests/`
4. 遵循現有的 dataclass / Protocol 風格

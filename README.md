# PDF Master 📄

> 一套以 Python + PySide6 打造的桌面版 PDF 頁面編輯器，支援多檔合併、重新排序、旋轉與匯出。

---

## ✨ 功能一覽

| 功能 | 狀態 |
|------|------|
| 開啟多個 PDF / 整個資料夾（單層）| ✅ |
| 縮圖預覽所有頁面 | ✅ |
| 拖放重新排序頁面 | ✅ |
| 旋轉頁面（90° 倍數）| ✅ |
| 刪除選取頁面（支援 Ctrl+A / Delete）| ✅ |
| 匯出選取或全部頁面為新 PDF | ✅ |
| Metadata 來源策略（first_pdf / last_pdf / empty）| ✅ |
| 頁碼標籤（Page Labels）保留 | ✅ |
| 加密 PDF 警示 | ✅ |
| 快捷鍵 Ctrl+A / Delete / Ctrl+Shift+E | ✅ |
| 保留書籤（TOC）| 🚧 規劃中 |
| 工作階段存檔／還原 | 🚧 規劃中 |
| 子資料夾遞迴掃描 | 🚧 規劃中 |

---

## 🖥️ 環境需求

- Python **3.11+**
- [PyMuPDF](https://pymupdf.readthedocs.io/) `>= 1.24`
- [PySide6](https://doc.qt.io/qtforpython/) `>= 6.6`

---

## 🚀 安裝與執行

```bash
# 1. 複製專案
git clone https://github.com/error404hsu/PDF-Master.git
cd PDF-Master

# 2. （建議）建立虛擬環境
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate

# 3. 安裝相依套件
pip install -r requirements.txt

# 4. 啟動 GUI
python gui_main.py
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
PDF-Master/
├── gui_main.py          # PySide6 主視窗與 UI 邏輯
├── main.py              # 純 CLI 腳手架（測試用）
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
├── adapters/            # 後端實作（目前為 PyMuPDF）
│   └── ...
│
└── tests/               # 測試套件
```

### 架構說明

`core/` 與 `adapters/` 採用 **依賴反轉（DIP）** 設計：`core/protocols.py` 定義 `PdfBackend` Protocol，`adapters/` 提供具體實作。這使得日後替換或新增後端（如 pdfium、pikepdf）不需修改核心業務邏輯。

---

## ⌨️ 快捷鍵

| 按鍵 | 功能 |
|------|------|
| `Ctrl+A` | 全選所有頁面 |
| `Delete` | 刪除選取頁面 |
| `Ctrl+Shift+E` | 匯出選取頁面 |

---

## 🗺️ 開發路線圖

詳見 [TODO.md](TODO.md)，主要規劃項目包含：

- 工作階段存檔／還原（`*.pdfmaster` 專案檔）
- 保留書籤（TOC）與互動表單
- 子資料夾遞迴掃描
- 浮水印／頁碼 Stamp
- 清單模式（大量頁面適用）

---

## 📜 授權

本專案採用 [MIT License](LICENSE)。

---

## 🤝 貢獻

歡迎開 Issue 回報問題或提出功能建議。若要送 PR，請確保：

1. 核心邏輯放於 `core/`，UI 邏輯不進入 `core/`
2. 新增功能請附對應測試於 `tests/`
3. 遵循現有的 dataclass / Protocol 風格

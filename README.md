# PDF Page Editor Project

這是整理後的專案版，專注在 PDF 頁面編輯器的底層邏輯，之後可直接往 PySide6 GUI 延伸。

## 專案結構

- `main.py`：專案入口，建立 backend 與 workspace。
- `core/`：工作區、資料模型、縮圖與匯出服務。
- `adapters/`：PDF backend 實作，目前提供 PyMuPDF adapter。
- `tests/`：內部模擬測試。
- `requirements.txt`：基本依賴。
- `.gitignore`：Git 忽略設定。
- `LICENSE`：MIT 授權。

## 安裝

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Windows PowerShell：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 執行測試

```bash
python -m unittest discover -s tests -v
```

## GitHub 上傳

### 方法一：Git 指令

```bash
git init
git branch -M main
git add .
git commit -m "Initial commit: PDF page editor core project"
git remote add origin https://github.com/YOUR_ACCOUNT/YOUR_REPO.git
git push -u origin main
```

### 方法二：GitHub CLI

先登入：

```bash
gh auth login
```

建立並推送現有專案：

```bash
gh repo create YOUR_REPO --private --source=. --remote=origin --push
```

GitHub 官方文件也提供將現有本機專案加入 GitHub 的流程，以及使用 `gh repo create --source=. --push` 直接建立遠端 repo 並推送的方式。[web:34][web:41]

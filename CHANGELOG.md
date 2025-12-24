# CHANGELOG

日期: 2025-12-02

## 本次整理總覽
本次整理聚焦於專案可開發性、部署準備與前端易用性，採取低侵入性修改，便於本地開發與未來 CI/CD 部署。

## 主要變更（摘要）

### 文件與輔助檔
- 更新 `README.md`：加入快速啟動、Docker/環境變數、以及服務架構與部署建議。
- 新增 `CONTRIBUTING.md`：簡易貢獻流程與注意事項。
- 新增 `.env.example`：範本環境變數（不要提交真實金鑰）。
- 新增 `.dockerignore` 與 `.gitignore`：排除不必要檔案與本機資料。
- 新增 `CHANGELOG.md`（本檔）。

### 後端（`backEnd`）
- 精簡並更新 `backEnd/requirements.txt`（保留實際程式碼使用到的核心套件，移除冗餘項目）。
- 新增 `backEnd/requirements-prod.txt`：明確的生產依賴清單。
- 改善 `backEnd/Dockerfile`：
  - 使用 layer-caching 的 requirements 安裝流程。
  - 建立非 root 使用者 `appuser` 增加容器安全性。
  - 複製程式後將目錄權限轉給 `appuser`。
- 新增 `docker-compose.prod.yml`：production 範例（含 healthcheck、restart policy、可選 `kb-builder` 服務）。

### 前端（`frontEnd`）
- 新增 `frontEnd/README.md`：說明前端結構、測試方法與 API 根路徑設定。
- 在 `frontEnd/index.html` 新增 `meta[name="api-base"]` 以便切換後端 API 位址。
- 修改 `frontEnd/script.js`：從 meta 讀取 `API_BASE`（若不存在則使用 `location.origin`）。

### CI / 測試
- 新增 GitHub Actions workflow `.github/workflows/python-ci.yml`：執行輕量 pytest（避免在 CI 安裝 heavy system packages）。
- 新增基礎 pytest 測試 `tests/test_basic.py`：測試 `functions.tokenUsed` 與 `dbStoring.init_db`（不依賴外部系統套件）。
- 新增 `run-tests.bat`：Windows 下快速執行測試的批次檔。

### 其他輔助檔
- 新增 `run-backend.bat`、`run-frontend.bat`：開發時快速啟動用。

## 風險與注意事項
- 部分套件（例如 `faiss-cpu`, `pytesseract`, `poppler`）需要系統層級相依（apt 套件）才能在容器或主機上正常運作。Dockerfile 已包含 apt 安裝，但實際建置或在特定 runner（例如部分 CI）上可能需額外調整。
- 我移除了 `requirements.txt` 中部分看起來沒被程式直接引用的套件。若你在執行時發現缺少某個第三方套件（例如某些 langchain 插件或擴充套件），請告訴我我會把它加入 `requirements-prod.txt` 或 `requirements.txt`。

## 建議的 Git commit 與分支策略
- 建議用 feature branch：`feature/docs-and-docker-cleanup`
- 建議一次 commit（或分兩個 commit：文件與功能）：
  - Commit 1 (docs): "docs: update README, add CONTRIBUTING, .env.example, frontEnd README"
  - Commit 2 (infra): "chore(docker): improve Dockerfile, add prod compose, add requirements-prod; add CI and tests"

## 建議的下一步
- 在本機或 CI 中執行 `run-tests.bat` 或 `pytest`，確認測試通過。
- 若要把前端更靠近生產部署：將 API 呼叫改為相對路徑並在 Nginx 中做反向代理（我可以幫你新增 `nginx.conf` 範例與修改 `script.js`）。
- 若要在 CI 建置生產映像，建議建立一個帶 apt 安裝步驟的 runner job 或使用能支援 buildkit 的 Docker runner（我可以為 GitHub Actions 設計一個完整 build-and-push workflow）。

----

如需我把變更 commit、建立 PR 或進一步套用到 CI/CD，請告訴我你的首選（直接在 `main` commit，或建立 feature branch 與 PR）。

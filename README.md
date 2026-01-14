# Prompt Refine

## Goal

### Abstract

This is an feedback and scoring system using AI models, based on Double Prompt concept.
![image](https://github.com/user-attachments/assets/1567b6bc-12c0-4c19-bfaa-8c32033bf112)

## Developing history

### 20250312

- Created the repository and ready to construct the project.

### 20250314 Happy Valentine :P

- Added backEnd and frontEnd folder.
  - backEnd folder: Includes app.py (entrypoint) and promptList.
  - frontEnd folder: Includes public/index.html.
- The prompt example is just a demonstration of how to tell AI to give scores and feedback.
- For app.py the prompts can be modified and added into the system.
  - When changing the contents and the parameters in app.py, rememeber to add the same parameters in index.html.
- If wanna test out, please run app.py at first, then run index.html. (Both are local host, if wanna host with fixed IP need other stuffs.)
  - app.py's Environment API key requires openAI's API key to be set in the Environment. Thus, can not just execute then run.
  - Try run `$env:OPENAI_API_KEY = "your API key"` in your powershell, and you can use `echo $env:OPENAI_API_KEY` to check if the key is set.

### 20250402 (SSBhbSBzbyBmcmVha2luZyBzY3Jld2VkIGJ5IHNvbWVvbmUgSSB1c2VkIHRvIHRydXN0Lg==) 這串不是API KEY喔 不要用

- Construct the brief structure of the project.
- The project have to read PDF.
- The scoring history should be added into DB (currently using SQLite)
  - Data row: applicantStdn, applicantNo, applicantName, isPassed, aiFeedback, applyDate, applyTime
- services/ai_service.py:
  - 處理PDF資料轉換為字串給AI讀，然後回傳json格式
- db/dbStoring.py:
  - 處理獲得的json並儲存到DB內。
- utils/functions.py:
  - 一些基本函式
- tokenUsed.txt:
  - 紀錄目前的token總消耗

## 快速開始

進入PromptRefine檔案夾

以下提供三種本地啟動方式：透過 Docker、使用本機虛擬環境 (Windows cmd)，或僅開啟前端靜態頁面。

- **使用 Docker (建議)**：在專案根目錄執行：

  ```cmd
  docker compose up --build
  ```

  - 會建立兩個 service：
    - `backend`（對外 5000），從 `backEnd/Dockerfile` 建立
    - `frontend`（對外 8080），使用 nginx 提供 `frontEnd` 靜態檔
- **本機虛擬環境（Windows cmd）**：

  1. 啟用虛擬環境（若你使用 repo 的 `gaienv`）：

     ```cmd
     call gaienv\env\Scripts\activate.bat
     ```
  2. 進入後端資料夾並安裝相依套件：

     ```cmd
     cd backEnd
     pip install -r requirements.txt
     set OPENAI_API_KEY=your_api_key_here
     python app.py
     ```
  3. 前端可直接用瀏覽器開啟 `frontEnd\public\index.html`，或將其透過簡單伺服器提供。
- **僅開啟前端（快速測試 UI）**：

  - 直接在檔案管理器或使用命令：

    ```cmd
    start "" frontEnd\public\index.html
    ```

## Docker & 環境變數

- 專案的 `docker-compose.yml` 會讀 `./.env`（若存在）。請避免在版本控制放置真實金鑰。
- 已新增 `.env.example` 供參考，請複製為 `.env` 並填入你的金鑰。

## 本次整理項目

- 新增 `.env.example`、`.dockerignore`、簡易啟動批次檔 `run-backend.bat`、`run-frontend.bat`。
- 建議後續可清理 `requirements.txt` 或以 `pip-tools`/`poetry` 管理相依。

## 建議下一步

- 若需我幫你：
  - 清理並精簡 `requirements.txt`（移除重複或未使用套件）
  - 加入 `.gitignore`、CI 設定或自動化測試腳本
  - 將專案拆成更明確的服務模組（若需要部署至生產）

## 服務架構（建議）

- `backend`：Flask API，處理檔案上傳、OCR、AI 互動、資料庫儲存。可透過 `backEnd/Dockerfile` 建置為獨立容器。
- `frontend`：靜態網站（HTML/CSS/JS），由 Nginx 提供內容，已在 `frontEnd`。
- `kb-builder`（可選）：離線或定期執行的向量資料庫建置服務，用於處理大量 PDF 並建立 `vectorstores/knowledge_base`。

建議部署方式：

- 使用 `docker-compose.prod.yml` 作為生產部署範例（已加入 healthcheck、restart policy 與 kb-builder 範本）。
- 在生產環境安裝必要的系統套件（如 `tesseract`, `poppler`），或在 CI/CD pipeline 中建置包含這些系統依賴的映像。
- 不要在版本庫內放置 `.env`，改用 `secrets` 或 CI/CD 的 secret 管理功能。

若要我代為執行：

- 幫你建立一個 `docker hub`／`GHCR` workflow，自動建置並推送映像
- 把 `kb-builder` 改成 CronJob（或 Kubernetes Job）格式，並產出相應的 `k8s` 部署範例

請告訴我你要我先做哪一步，我就開始處理。

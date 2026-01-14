# frontEnd

說明：這個資料夾包含專案的前端靜態頁面（純 HTML/CSS/JS），由 Nginx 或任何靜態伺服器提供。

目錄
- `index.html`：主介面，含上傳表單與 AI 回饋視窗。
- `teacher.html`, `login.html`, `register.html`：其他頁面（若存在）。
- `review.css`, `teacher.css`：樣式檔。
- `script.js`, `teacher.js`：前端行為，`script.js` 為主要入口。

快速本地測試

1) 直接用瀏覽器開啟（不會有後端互動）

```cmd
start "" frontEnd\index.html
```

2) 使用簡單 HTTP 伺服器（推薦，用於模擬在 Nginx/Server 的情境）

```cmd
python -m http.server --directory frontEnd 8000
```
然後在瀏覽器開啟 `http://127.0.0.1:8000`。

設定後端 API 根路徑

- `script.js` 會優先讀取 `index.html` head 中的 meta 標籤：

```html
<meta name="api-base" content="http://127.0.0.1:5000">
```

- 若 meta 未設定，預設會使用 `location.origin`（同源）。

部署注意事項

- 若前端與後端分別由不同 host/port 提供（例如 Nginx 與 Flask），請確保後端有啟用 CORS，或將 Nginx 設為反向代理以避免跨域問題。
- 在 Docker Compose 生產範例中，Nginx 提供前端（`frontend` 服務），後端為 `backend`（5000）。生產時可把 `meta[name=api-base]` 改為後端的內部 URL（或使用 Nginx 反向代理 `/api` 路徑至後端）。

建議

- 若你要在生產環境使用 Nginx 反向代理，建議把前端的 API 呼叫改為相對路徑（例如 `/api/...`），再由 Nginx 轉送到 `http://backend:5000`，這樣前端不需切換 `api-base`。

如果你要我：
- 把 `index.html` 的 API 呼叫改成相對路徑並新增 Nginx sample config，我可以幫你加入（會修改 `script.js` 和新增 `nginx.conf` 範例）。
- 或我可以把前端打包到 Docker image（用 nginx），並示範如何在 `docker-compose.prod.yml` 中替換為使用內部網路代理。

請告訴我要不要進一步處理上述其中一項。

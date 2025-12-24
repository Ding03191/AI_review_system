@echo off
REM 快速打開前端 index.html 或啟動簡易 HTTP 伺服器
IF EXIST frontEnd\index.html (
  start "" frontEnd\index.html
  echo 如果需要以 HTTP 伺服器提供前端，請執行：
  echo python -m http.server --directory frontEnd 8000
) ELSE (
  echo 找不到 frontEnd\index.html
)
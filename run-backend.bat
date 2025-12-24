@echo off
REM 啟動後端（Windows cmd）
IF EXIST gaienv\env\Scripts\activate.bat (
  call gaienv\env\Scripts\activate.bat
) ELSE (
  echo 虛擬環境不存在，請先建立或啟用你的 Python 環境。
)
set FLASK_ENV=development
REM 請先設定環境變數 OPENAI_API_KEY 或在 .env 中設定
cd backEnd
python app.py
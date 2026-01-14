FROM python:3.11-slim

# 環境變數設定
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    TESSERACT_CMD=/usr/bin/tesseract \
    PYTHONPATH=/app/src

# Install system packages required for OCR and PDF processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-chi-tra \
    poppler-utils \
    build-essential \
    libglib2.0-0 \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

# 建立非 root 使用者以提高容器安全性
RUN useradd --create-home --shell /bin/bash appuser

WORKDIR /app

# 先複製 requirements 並安裝（利用 layer cache 加速重 build）
COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir --disable-pip-version-check -r requirements.txt

# 複製程式碼並設定權限
COPY . /app
RUN mkdir -p /app/db
RUN chown -R appuser:appuser /app

USER appuser

# Flask 預設 port
EXPOSE 5000

# 啟動指令（依你的 app.py 為主）
CMD ["python", "app.py"]

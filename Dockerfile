# 單一服務同時提供 FastAPI 後端與 index/ 前端靜態檔。
# 只有一個網域、一組 HTTPS，因此沒有 CORS 也沒有混合內容問題。
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# 先只複製依賴清單，讓 Docker 能快取這一層
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

COPY backend /app/backend
COPY index /app/index

WORKDIR /app/backend

# 平台通常用 $PORT 指定要監聽的埠；本機測試時預設 8000。
# 啟動前先跑 migration，資料表才會跟程式碼同步。
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]

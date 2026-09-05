import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from time import monotonic
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.routes import router
from app.config import get_settings
from app.database import SessionLocal, create_schema
from app.exceptions import DomainError
from app.services.content_seed import seed_content

settings = get_settings()
logger = logging.getLogger("companion.api")


class RequestGuardMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: FastAPI, requests_per_minute: int):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.buckets: dict[str, list[float]] = {}

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid4()))[:64]
        now = monotonic()
        identity = request.client.host if request.client else "unknown"
        timestamps = [value for value in self.buckets.get(identity, []) if now - value < 60]
        if len(timestamps) >= self.requests_per_minute:
            return JSONResponse(
                status_code=429,
                content={"code": "RATE_LIMITED", "message": "操作太頻繁，請稍候再試。"},
                headers={"X-Request-ID": request_id},
            )
        timestamps.append(now)
        self.buckets[identity] = timestamps
        started = monotonic()
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        logger.info(
            json.dumps(
                {
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status": response.status_code,
                    "latency_ms": round((monotonic() - started) * 1000),
                },
                ensure_ascii=False,
            )
        )
        return response


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    if (
        settings.environment.lower() in {"production", "staging"}
        and settings.app_secret_key.get_secret_value() == "development-only-change-me"
    ):
        raise RuntimeError("正式環境必須設定 APP_SECRET_KEY。")
    if settings.auto_create_schema:
        create_schema()
    if settings.seed_demo_content:
        with SessionLocal() as db:
            seed_content(db)
    yield


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="6–8 歲兒童教機器人朗讀的後端 MVP。",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_origins.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(
    RequestGuardMiddleware,
    requests_per_minute=settings.requests_per_minute,
)
app.include_router(router, prefix=settings.api_prefix)

# 部署時由後端一併提供前端靜態檔：只有一個網域、一組 HTTPS，
# 因此沒有 CORS 也沒有 HTTPS 頁面呼叫 HTTP API 的混合內容問題。
# 一定要掛在 include_router 之後，否則 "/" 會把 /v1 的路由吃掉。
# 本機開發時前端仍可用 python -m http.server 單獨跑，不受影響。
FRONTEND_DIR = Path(__file__).resolve().parents[2] / "index"
if FRONTEND_DIR.is_dir():
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")


@app.exception_handler(DomainError)
async def handle_domain_error(_request: Request, exc: DomainError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.code, "message": exc.message},
    )

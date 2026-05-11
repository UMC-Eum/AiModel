import logging

from fastapi import FastAPI, Request
from sqlalchemy import text

from app import database
from app.api.v1 import club, health, onboarding, recommendation
from app.core.exceptions import register_exception_handlers
from app.core.response import success_response

app = FastAPI(title="AI Voice Service", version="0.1.0")
register_exception_handlers(app)

app.include_router(health.router, prefix="/api")
app.include_router(onboarding.router, prefix="/api")
app.include_router(recommendation.router, prefix="/api")
app.include_router(club.router, prefix="/api")

logger = logging.getLogger(__name__)


@app.get("/health")
async def health(request: Request):
    return success_response(request, {"status": "ok"})


@app.on_event("startup")
async def ensure_db_connection() -> None:
    """앱 기동 시 DB 연결 상태를 1회 점검한다."""
    try:
        async with database.engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:
        logger.exception("DB 연결 확인 실패")
        raise

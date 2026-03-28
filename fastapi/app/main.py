import logging

from fastapi import FastAPI
from sqlalchemy import text

from app import database
from app.api.v1 import health, matches, onboarding, recommendation

app = FastAPI(title="AI Voice Service", version="0.1.0")

app.include_router(health.router, prefix="/api")
app.include_router(onboarding.router, prefix="/api")
app.include_router(matches.router, prefix="/api")
app.include_router(recommendation.router, prefix="/api")

logger = logging.getLogger(__name__)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.on_event("startup")
async def ensure_db_connection() -> None:
    """앱 기동 시 DB 연결 상태를 1회 점검한다."""
    try:
        async with database.engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:
        logger.exception("DB 연결 확인 실패")
        raise

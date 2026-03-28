import os

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import get_settings


# DATABASE_URL 우선, 없으면 기존 mysql_dsn을 fallback으로 사용
DATABASE_URL = os.getenv("DATABASE_URL") or get_settings().mysql_dsn

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL 또는 mysql_dsn 환경변수가 설정되어야 합니다.")

engine = create_async_engine(DATABASE_URL, echo=False, pool_pre_ping=True, future=True)
AsyncSessionLocal = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
Base = declarative_base()


async def get_db():
    """요청 단위 세션 제공 (비동기)."""
    async with AsyncSessionLocal() as session:
        yield session

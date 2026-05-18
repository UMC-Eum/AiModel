import os
from urllib.parse import urlparse

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import get_settings


def _normalize_postgres_url(url: str) -> str:
    if url.startswith("postgres://"):
        return "postgresql+asyncpg://" + url.removeprefix("postgres://")
    if url.startswith("postgresql://"):
        return "postgresql+asyncpg://" + url.removeprefix("postgresql://")
    return url


# DATABASE_URL 우선, 없으면 postgres_dsn을 fallback으로 사용
DATABASE_URL = _normalize_postgres_url(os.getenv("DATABASE_URL") or get_settings().postgres_dsn)

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL 또는 postgres_dsn 환경변수가 설정되어야 합니다.")

parsed_url = urlparse(DATABASE_URL)
if parsed_url.scheme not in {"postgresql+asyncpg"}:
    raise RuntimeError("PostgreSQL async DSN을 사용해야 합니다. 예: postgresql+asyncpg://user:pass@host:5432/dbname")

engine = create_async_engine(DATABASE_URL, echo=False, pool_pre_ping=True, future=True)
AsyncSessionLocal = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
Base = declarative_base()


async def get_db():
    """요청 단위 세션 제공 (비동기)."""
    async with AsyncSessionLocal() as session:
        yield session

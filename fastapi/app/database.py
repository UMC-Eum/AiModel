import os
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import get_settings


def _normalize_postgres_url(url: str) -> str:
    if url.startswith("postgres://"):
        return "postgresql+asyncpg://" + url.removeprefix("postgres://")
    if url.startswith("postgresql://"):
        return "postgresql+asyncpg://" + url.removeprefix("postgresql://")
    return url


def _prepare_asyncpg_url(url: str) -> tuple[str, dict]:
    parsed = urlparse(url)
    query_items = parse_qsl(parsed.query, keep_blank_values=True)
    schema = ""
    sanitized_query_items = []

    for key, value in query_items:
        if key == "schema":
            schema = value
            continue
        sanitized_query_items.append((key, value))

    sanitized_url = urlunparse(parsed._replace(query=urlencode(sanitized_query_items)))
    connect_args = {}
    if schema:
        connect_args["server_settings"] = {"search_path": schema}
    return sanitized_url, connect_args


settings = get_settings()

# OS 환경변수 DATABASE_URL 우선, 없으면 .env의 DATABASE_URL/postgres_dsn을 fallback으로 사용
DATABASE_URL = _normalize_postgres_url(
    os.getenv("DATABASE_URL") or settings.database_url or settings.postgres_dsn
)

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL 또는 postgres_dsn 환경변수가 설정되어야 합니다.")

parsed_url = urlparse(DATABASE_URL)
if parsed_url.scheme not in {"postgresql+asyncpg"}:
    raise RuntimeError("PostgreSQL async DSN을 사용해야 합니다. 예: postgresql+asyncpg://user:pass@host:5432/dbname")

DATABASE_URL, CONNECT_ARGS = _prepare_asyncpg_url(DATABASE_URL)
engine = create_async_engine(DATABASE_URL, echo=False, pool_pre_ping=True, future=True, connect_args=CONNECT_ARGS)
AsyncSessionLocal = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
Base = declarative_base()


async def get_db():
    """요청 단위 세션 제공 (비동기)."""
    async with AsyncSessionLocal() as session:
        yield session

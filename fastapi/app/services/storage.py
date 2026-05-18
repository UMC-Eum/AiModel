from __future__ import annotations

import json
import logging
from typing import Any, Dict, Iterable, List, Optional

import httpx
from sqlalchemy import text

from app.core.config import get_settings
from app.database import DATABASE_URL, engine


class PersistenceError(Exception):
    """저장 단계에서 발생하는 예외."""


async def save_vibe_vector(vector: List[float], user_id: Optional[int]) -> str:
    """User.vibeVector 컬럼에 벡터를 저장하고 user_id를 반환한다."""
    if user_id is None:
        raise PersistenceError("user_id가 없어 벡터를 저장할 수 없습니다.")

    settings = get_settings()
    dsn = DATABASE_URL
    endpoint = settings.postgres_api_endpoint or ""

    # 1) DSN 직결
    if dsn:
        try:
            async with engine.begin() as conn:
                await conn.execute(
                    text(
                        """
                        UPDATE "User"
                        SET "vibeVector" = CAST(:vibe_vector AS JSON),
                            "updatedAt" = CURRENT_TIMESTAMP
                        WHERE id = :user_id
                        """
                    ),
                    {"vibe_vector": json.dumps(vector), "user_id": user_id},
                )
        except Exception as exc:
            raise PersistenceError(f"User.vibeVector 저장 실패(PostgreSQL): {exc}") from exc
        return str(user_id)

    # 2) HTTP 프록시
    if endpoint:
        payload = {"userId": user_id, "vibeVector": vector}
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(endpoint, json=payload)
                resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise PersistenceError(f"User.vibeVector 저장 실패(HTTP): {exc}") from exc
        return str(user_id)

    logging.warning("postgres_dsn/postgres_api_endpoint 미설정 - 벡터 저장 생략 (user_id=%s)", user_id)
    return str(user_id)


async def save_user_keywords(vector_id: str, user_id: Optional[int], keywords: Iterable[dict]) -> None:
    """매칭된 키워드를 user_keywords 테이블에 저장한다."""
    settings = get_settings()
    dsn = DATABASE_URL
    endpoint = settings.postgres_api_endpoint or ""
    keywords_list = list(keywords)

    if not keywords_list:
        return

    # 1) DSN 직결
    if dsn:
        try:
            async with engine.begin() as conn:
                for item in keywords_list:
                    await conn.execute(
                        text(
                            """
                            INSERT INTO user_keywords ("userId", "vectorId", "keywordId", keyword, category, score)
                            VALUES (:user_id, :vector_id, :keyword_id, :keyword, :category, :score)
                            ON CONFLICT ("userId", "keywordId")
                            DO UPDATE SET score = EXCLUDED.score
                            """
                        ),
                        {
                            "user_id": user_id,
                            "vector_id": vector_id,
                            "keyword_id": item.get("id"),
                            "keyword": item.get("keyword"),
                            "category": item.get("category"),
                            "score": item.get("score"),
                        },
                    )
        except Exception as exc:
            raise PersistenceError(f"user_keywords 저장 실패(PostgreSQL): {exc}") from exc
        return

    # 2) HTTP 프록시
    if endpoint:
        payload = {
            "vectorId": vector_id,
            "userId": user_id,
            "keywords": keywords_list,
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(endpoint, json=payload)
                resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise PersistenceError(f"user_keywords 저장 실패(HTTP): {exc}") from exc
        return

    logging.warning("postgres_dsn/postgres_api_endpoint 미설정 - 키워드 저장 생략")


async def check_postgres_health() -> Dict[str, Any]:
    """Check PostgreSQL connectivity using the configured DSN."""
    dsn = DATABASE_URL

    if not dsn:
        return {"status": "skipped", "reason": "DATABASE_URL/postgres_dsn not configured"}

    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:
        return {"status": "error", "reason": str(exc)}

    return {"status": "ok"}

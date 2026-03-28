from __future__ import annotations

import json
import logging
from typing import Iterable, List, Optional
from urllib.parse import urlparse

import httpx
import aiomysql

from app.core.config import get_settings


class PersistenceError(Exception):
    """저장 단계에서 발생하는 예외."""


def _parse_mysql_dsn(dsn: str) -> dict:
    parsed = urlparse(dsn)
    if parsed.scheme not in {"mysql", "mysql+aiomysql"}:
        raise PersistenceError(f"지원하지 않는 DSN 스킴입니다: {parsed.scheme}")
    if not parsed.hostname or not parsed.path:
        raise PersistenceError("MySQL DSN에 host 또는 DB명이 없습니다.")
    return {
        "host": parsed.hostname,
        "port": parsed.port or 3306,
        "user": parsed.username,
        "password": parsed.password,
        "db": parsed.path.lstrip("/"),
        "charset": "utf8mb4",
        "autocommit": True,
    }


async def save_vibe_vector(vector: List[float], user_id: Optional[int]) -> str:
    """User.vibeVector 컬럼에 벡터를 저장하고 user_id를 반환한다."""
    if user_id is None:
        raise PersistenceError("user_id가 없어 벡터를 저장할 수 없습니다.")

    settings = get_settings()
    dsn = settings.mysql_dsn or ""
    endpoint = settings.mysql_api_endpoint or ""

    # 1) DSN 직결
    if dsn:
        cfg = _parse_mysql_dsn(dsn)
        try:
            conn = await aiomysql.connect(**cfg)
            async with conn.cursor() as cur:
                await cur.execute(
                    "UPDATE User SET vibeVector=%s, updatedAt=NOW(6) WHERE id=%s",
                    (json.dumps(vector), user_id),
                )
        except Exception as exc:
            raise PersistenceError(f"User.vibeVector 저장 실패(MySQL): {exc}") from exc
        finally:
            try:
                conn.close()
            except Exception:
                pass
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

    logging.warning("mysql_dsn/mysql_api_endpoint 미설정 - 벡터 저장 생략 (user_id=%s)", user_id)
    return str(user_id)


async def save_user_keywords(vector_id: str, user_id: Optional[int], keywords: Iterable[dict]) -> None:
    """매칭된 키워드를 user_keywords 테이블에 저장한다."""
    settings = get_settings()
    dsn = settings.mysql_dsn or ""
    endpoint = settings.mysql_api_endpoint or ""
    keywords_list = list(keywords)

    if not keywords_list:
        return

    # 1) DSN 직결
    if dsn:
        cfg = _parse_mysql_dsn(dsn)
        try:
            conn = await aiomysql.connect(**cfg)
            async with conn.cursor() as cur:
                sql = (
                    "INSERT INTO user_keywords (userId, vectorId, keywordId, keyword, category, score) "
                    "VALUES (%s, %s, %s, %s, %s, %s) "
                    "ON DUPLICATE KEY UPDATE score=VALUES(score)"
                )
                rows = [
                    (
                        user_id,
                        vector_id,
                        item.get("id"),
                        item.get("keyword"),
                        item.get("category"),
                        item.get("score"),
                    )
                    for item in keywords_list
                ]
                await cur.executemany(sql, rows)
        except Exception as exc:
            raise PersistenceError(f"user_keywords 저장 실패(MySQL): {exc}") from exc
        finally:
            try:
                conn.close()
            except Exception:
                pass
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

    logging.warning("mysql_dsn/mysql_api_endpoint 미설정 - 키워드 저장 생략")

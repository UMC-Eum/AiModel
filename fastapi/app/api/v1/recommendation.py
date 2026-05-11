from __future__ import annotations

import base64
import binascii
import json
import logging
from typing import Any, Dict, List, Tuple

import numpy as np
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.core.response import success_response
from app.database import get_db
from app.models.user import User, UserStatus

router = APIRouter(tags=["recommendation"])

logger = logging.getLogger(__name__)

SIMILARITY_THRESHOLD = 0.3
MAX_RESULTS = 20
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 50


def _cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:

    if len(vec_a) != len(vec_b):
        raise ValueError(f"vector length mismatch: {len(vec_a)} != {len(vec_b)}")
    a = np.array(vec_a, dtype=float)
    b = np.array(vec_b, dtype=float)
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0.0:
        return 0.0
    return float(np.dot(a, b) / denom)


def _to_vector(raw) -> List[float] | None:
    """JSON 컬럼 값을 float 리스트로 변환."""
    if raw is None:
        return None
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return None
    if not isinstance(raw, (list, tuple)):
        return None
    try:
        return [float(x) for x in raw]
    except (TypeError, ValueError):
        return None


def _encode_cursor(item: Dict[str, Any]) -> str:
    payload = {"similarityScore": item["similarityScore"], "userId": item["userId"]}
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii")


def _decode_cursor(cursor: str) -> Tuple[float, int]:
    try:
        payload = json.loads(base64.urlsafe_b64decode(cursor.encode("ascii")).decode("utf-8"))
        return float(payload["similarityScore"]), int(payload["userId"])
    except (binascii.Error, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise AppException(code="RECOMMENDATION-005", message="cursor 값이 올바르지 않습니다.", status_code=400) from exc


def _is_after_cursor(item: Dict[str, Any], cursor_score: float, cursor_user_id: int) -> bool:
    item_score = item["similarityScore"]
    item_user_id = item["userId"]
    return item_score < cursor_score or (item_score == cursor_score and item_user_id > cursor_user_id)


async def _build_scored_recommendations(user_id: int, db: AsyncSession) -> List[Dict[str, Any]]:
    # 1) 요청 유저 조회
    try:
        requester_row = await db.execute(select(User).where(User.id == user_id))
        requester = requester_row.scalar_one_or_none()
    except Exception as exc:
        logger.exception("requester fetch failed", extra={"userId": user_id})
        raise AppException(code="RECOMMENDATION-001", message=f"DB 조회 실패: {exc}", status_code=500) from exc

    if requester is None:
        logger.warning("requester not found", extra={"userId": user_id})
        raise AppException(code="RECOMMENDATION-002", message="userId가 존재하지 않습니다.", status_code=404)

    requester_vector = _to_vector(requester.vibeVector)
    if not requester_vector:
        logger.warning(
            "requester vector missing",
            extra={"userId": user_id, "sex": requester.sex, "status": requester.status.name},
        )
        raise AppException(code="RECOMMENDATION-003", message="요청 유저의 vibeVector가 없습니다.", status_code=400)

    requester_sex = requester.sex
    logger.info(
        "requester loaded",
        extra={
            "userId": user_id,
            "sex": requester_sex.value if requester_sex else None,
            "vector_len": len(requester_vector),
        },
    )

    # 2) 후보군 조회 (조건 필터)
    try:
        candidates_row = await db.execute(
            select(User).where(
                User.status == UserStatus.ACTIVE,
                User.deletedAt.is_(None),
                User.id != user_id,
                User.sex != requester_sex,
                User.vibeVector.is_not(None),
            )
        )
        candidates = candidates_row.scalars().all()
    except Exception as exc:
        logger.exception("candidate fetch failed", extra={"userId": user_id})
        raise AppException(code="RECOMMENDATION-004", message=f"후보군 조회 실패: {exc}", status_code=500) from exc

    logger.info(
        "candidates fetched",
        extra={"userId": user_id, "candidate_count": len(candidates)},
    )

    # 3) 유사도 계산 및 정렬
    scored = []
    requester_dim = len(requester_vector)
    for candidate in candidates:
        candidate_vec = _to_vector(candidate.vibeVector)
        if not candidate_vec:
            logger.debug("skip candidate without vector", extra={"candidateId": candidate.id})
            continue
        if len(candidate_vec) != requester_dim:
            logger.warning(
                "skip candidate with mismatched vector dimension",
                extra={
                    "candidateId": candidate.id,
                    "requesterId": user_id,
                    "requester_dim": requester_dim,
                    "candidate_dim": len(candidate_vec),
                },
            )
            continue
        score = _cosine_similarity(requester_vector, candidate_vec)
        if score < SIMILARITY_THRESHOLD:
            logger.debug(
                "skip candidate below threshold",
                extra={"candidateId": candidate.id, "score": score, "threshold": SIMILARITY_THRESHOLD},
            )
            continue
        scored.append(
            {
                "userId": candidate.id,
                "nickname": candidate.nickname,
                "age": candidate.age,
                "profileImageUrl": candidate.profileImageUrl,
                "introText": candidate.introText,
                "similarityScore": round(score, 4),
            }
        )

    logger.info(
        "scoring done",
        extra={"userId": user_id, "scored_count": len(scored), "threshold": SIMILARITY_THRESHOLD},
    )

    scored.sort(key=lambda x: (-x["similarityScore"], x["userId"]))
    return scored


@router.get("/v1/recommendation/users")
async def recommend_users(
    request: Request,
    userId: int = Query(..., description="NestJS가 전달한 사용자 ID"),
    db: AsyncSession = Depends(get_db),
):
    scored = await _build_scored_recommendations(userId, db)
    top_n = scored[:MAX_RESULTS]

    return success_response(request, top_n)


@router.get("/v1/onboarding/matches/recommend")
async def recommend_onboarding_matches(
    request: Request,
    userId: int = Query(..., description="추천 기준 사용자 ID"),
    cursor: str | None = Query(default=None, description="이전 응답의 nextCursor"),
    size: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE, description="페이지 크기, 최대 50"),
    db: AsyncSession = Depends(get_db),
):
    scored = await _build_scored_recommendations(userId, db)

    if cursor:
        cursor_score, cursor_user_id = _decode_cursor(cursor)
        scored = [item for item in scored if _is_after_cursor(item, cursor_score, cursor_user_id)]

    page_items = scored[: size + 1]
    has_next = len(page_items) > size
    items = page_items[:size]
    next_cursor = _encode_cursor(items[-1]) if has_next and items else None

    return success_response(
        request,
        {
            "items": items,
            "page": {
                "size": size,
                "hasNext": has_next,
                "nextCursor": next_cursor,
            },
        },
    )

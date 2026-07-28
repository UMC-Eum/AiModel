from __future__ import annotations

import base64
import binascii
import json
import logging
from typing import Any, Dict, List, Tuple

import numpy as np
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.core.response import success_response
from app.database import get_db
from app.models.user import SexEnum, User, UserIdealPersonality, UserPersonality, UserStatus

router = APIRouter(tags=["recommendation"])

logger = logging.getLogger(__name__)

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 50
KEYWORD_WEIGHT = 0.7
VECTOR_WEIGHT = 0.3
VECTOR_ONLY_THRESHOLD = 0.3
OPPOSITE_SEX = {
    SexEnum.M: SexEnum.F,
    SexEnum.F: SexEnum.M,
}


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
    payload = {
        "hasKeywordMatch": item.get("_hasKeywordMatch", False),
        "similarityScore": item["similarityScore"],
        "vectorScore": item.get("_vectorScore", 0.0),
        "userId": item["userId"],
    }
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii")


def _decode_cursor(cursor: str) -> Dict[str, Any]:
    try:
        payload = json.loads(base64.urlsafe_b64decode(cursor.encode("ascii")).decode("utf-8"))
        return {
            "hasKeywordMatch": bool(payload.get("hasKeywordMatch", False)),
            "similarityScore": float(payload["similarityScore"]),
            "vectorScore": float(payload.get("vectorScore", 0.0)),
            "userId": int(payload["userId"]),
        }
    except (binascii.Error, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise AppException(code="RECOMMENDATION-005", message="cursor 값이 올바르지 않습니다.", status_code=400) from exc


def _opposite_sex(sex: SexEnum | None) -> SexEnum:
    if sex not in OPPOSITE_SEX:
        raise AppException(code="RECOMMENDATION-006", message="요청 유저의 sex 값이 올바르지 않습니다.", status_code=400)
    return OPPOSITE_SEX[sex]


def _sort_key(item: Dict[str, Any]) -> Tuple[int, float, float, int]:
    return (
        -int(item.get("_hasKeywordMatch", False)),
        -float(item["similarityScore"]),
        -float(item.get("_vectorScore", 0.0)),
        int(item["userId"]),
    )


def _cursor_sort_key(payload: Dict[str, Any]) -> Tuple[int, float, float, int]:
    return (
        -int(payload["hasKeywordMatch"]),
        -float(payload["similarityScore"]),
        -float(payload["vectorScore"]),
        int(payload["userId"]),
    )


def _is_after_cursor(item: Dict[str, Any], cursor_payload: Dict[str, Any]) -> bool:
    return _sort_key(item) > _cursor_sort_key(cursor_payload)


def _public_item(item: Dict[str, Any]) -> Dict[str, Any]:
    return {key: value for key, value in item.items() if not key.startswith("_")}


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

    requester_sex = requester.sex
    target_sex = _opposite_sex(requester_sex)
    requester_vector = _to_vector(requester.vibeVector)
    logger.info(
        "requester loaded",
        extra={
            "userId": user_id,
            "sex": requester_sex.value if requester_sex else None,
            "target_sex": target_sex.value,
            "vector_len": len(requester_vector) if requester_vector else None,
        },
    )

    # 2) 요청 유저의 이상형 성격 키워드 조회
    try:
        ideals_row = await db.execute(
            select(UserIdealPersonality.personalityId).where(UserIdealPersonality.userId == user_id)
        )
        ideal_personality_ids = sorted({int(personality_id) for personality_id in ideals_row.scalars().all()})
    except Exception as exc:
        logger.exception("ideal personality fetch failed", extra={"userId": user_id})
        raise AppException(code="RECOMMENDATION-004", message=f"이상형 키워드 조회 실패: {exc}", status_code=500) from exc

    if not ideal_personality_ids:
        logger.warning("requester ideal personality missing", extra={"userId": user_id})
        raise AppException(
            code="RECOMMENDATION-007",
            message="이상형 녹음을 먼저 진행해주세요",
            status_code=404,
        )

    logger.info(
        "ideal personalities loaded",
        extra={"userId": user_id, "ideal_personality_count": len(ideal_personality_ids)},
    )

    # 3) 후보군 조회 (이성 후보군 전체 + 이상형 성격 키워드 매칭 개수)
    try:
        matched_counts = (
            select(
                UserPersonality.userId.label("candidate_user_id"),
                func.count(func.distinct(UserPersonality.personalityId)).label("matched_count"),
            )
            .where(UserPersonality.personalityId.in_(ideal_personality_ids))
            .group_by(UserPersonality.userId)
            .subquery()
        )
        candidates_row = await db.execute(
            select(User, matched_counts.c.matched_count)
            .outerjoin(matched_counts, User.id == matched_counts.c.candidate_user_id)
            .where(
                User.status == UserStatus.ACTIVE,
                User.deletedAt.is_(None),
                User.id != user_id,
                User.sex == target_sex,
            )
        )
        candidates = candidates_row.all()
    except Exception as exc:
        logger.exception("candidate fetch failed", extra={"userId": user_id})
        raise AppException(code="RECOMMENDATION-004", message=f"후보군 조회 실패: {exc}", status_code=500) from exc

    logger.info(
        "candidates fetched",
        extra={"userId": user_id, "target_sex": target_sex.value, "candidate_count": len(candidates)},
    )

    # 4) 키워드 우선 + 벡터 보충 점수 계산 및 정렬
    scored = []
    ideal_count = len(ideal_personality_ids)
    for candidate, matched_count in candidates:
        matched_count = int(matched_count or 0)
        keyword_score = matched_count / ideal_count
        has_keyword_match = matched_count > 0
        vector_score = 0.0
        candidate_vector = _to_vector(candidate.vibeVector)
        if requester_vector and candidate_vector and len(requester_vector) == len(candidate_vector):
            vector_score = max(0.0, _cosine_similarity(requester_vector, candidate_vector))
        if not has_keyword_match and vector_score < VECTOR_ONLY_THRESHOLD:
            continue
        score = (KEYWORD_WEIGHT * keyword_score) + (VECTOR_WEIGHT * vector_score)
        scored.append(
            {
                "userId": candidate.id,
                "nickname": candidate.nickname,
                "age": candidate.age,
                "profileImageUrl": candidate.profileImageUrl,
                "introText": candidate.introText,
                "similarityScore": round(score, 4),
                "_matchedCount": matched_count,
                "_hasKeywordMatch": has_keyword_match,
                "_keywordScore": round(keyword_score, 4),
                "_vectorScore": round(vector_score, 4),
            }
        )

    logger.info(
        "scoring done",
        extra={
            "userId": user_id,
            "scored_count": len(scored),
            "ideal_personality_count": ideal_count,
            "vector_only_threshold": VECTOR_ONLY_THRESHOLD,
        },
    )

    scored.sort(key=_sort_key)
    return scored


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
        cursor_payload = _decode_cursor(cursor)
        scored = [item for item in scored if _is_after_cursor(item, cursor_payload)]

    page_items = scored[: size + 1]
    has_next = len(page_items) > size
    items = page_items[:size]
    next_cursor = _encode_cursor(items[-1]) if has_next and items else None
    response_items = [_public_item(item) for item in items]

    return success_response(
        request,
        {
            "items": response_items,
            "page": {
                "size": size,
                "hasNext": has_next,
                "nextCursor": next_cursor,
            },
        },
    )

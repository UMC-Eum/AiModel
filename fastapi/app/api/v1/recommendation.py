from __future__ import annotations

import json
import logging
from typing import List

import numpy as np
from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User, UserStatus

router = APIRouter(tags=["recommendation"])

logger = logging.getLogger(__name__)

SIMILARITY_THRESHOLD = 0.3
MAX_RESULTS = 20


def _cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
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


def _fail(status_code: int, message: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"resultType": "FAIL", "error": {"message": message}})


@router.get("/v1/recommendation/users")
async def recommend_users(userId: int = Query(..., description="NestJS가 전달한 사용자 ID"), db: AsyncSession = Depends(get_db)):
    # 1) 요청 유저 조회
    try:
        requester_row = await db.execute(select(User).where(User.id == userId))
        requester = requester_row.scalar_one_or_none()
    except Exception as exc:  # DB 오류를 500으로 보고
        logger.exception("requester fetch failed", extra={"userId": userId})
        return _fail(500, f"DB 조회 실패: {exc}")

    if requester is None:
        logger.warning("requester not found", extra={"userId": userId})
        return _fail(404, "userId가 존재하지 않습니다.")

    requester_vector = _to_vector(requester.vibeVector)
    if not requester_vector:
        logger.warning(
            "requester vector missing",
            extra={"userId": userId, "sex": requester.sex, "status": requester.status.name},
        )
        return _fail(400, "요청 유저의 vibeVector가 없습니다.")

    requester_sex = requester.sex
    logger.info(
        "requester loaded",
        extra={
            "userId": userId,
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
                User.id != userId,
                User.sex != requester_sex,
                User.vibeVector.is_not(None),
            )
        )
        candidates = candidates_row.scalars().all()
    except Exception as exc:
        logger.exception("candidate fetch failed", extra={"userId": userId})
        return _fail(500, f"후보군 조회 실패: {exc}")

    logger.info(
        "candidates fetched",
        extra={"userId": userId, "candidate_count": len(candidates)},
    )

    # 3) 유사도 계산 및 정렬
    scored = []
    for candidate in candidates:
        candidate_vec = _to_vector(candidate.vibeVector)
        if not candidate_vec:
            logger.debug("skip candidate without vector", extra={"candidateId": candidate.id})
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
        extra={"userId": userId, "scored_count": len(scored), "threshold": SIMILARITY_THRESHOLD},
    )

    scored.sort(key=lambda x: x["similarityScore"], reverse=True)
    top_n = scored[:MAX_RESULTS]

    return {"resultType": "SUCCESS", "success": {"data": top_n}, "error": None}

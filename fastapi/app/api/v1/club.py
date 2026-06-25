from __future__ import annotations

import base64
import binascii
import json
import logging
from typing import Any, Dict, Optional, Tuple

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.core.response import success_response
from app.database import get_db
from app.services.llm import analyze_voice_profile, summarize_transcript
from app.services.stt import transcribe_local_audio

router = APIRouter(tags=["club"])

logger = logging.getLogger(__name__)

CLUB_SIMILARITY_THRESHOLD = 0.3
DEFAULT_CLUB_PAGE_SIZE = 20
MAX_CLUB_PAGE_SIZE = 50


class AnalyzeClubVibeRequest(BaseModel):
    clubId: Optional[int] = None
    club_id: Optional[int] = None
    transcript: Optional[str] = None
    local_audio_path: Optional[str] = None
    analysis_type: Optional[str] = "profile"


class ClubRecommendationItem(BaseModel):
    clubId: int = Field(description="추천 클럽 ID", examples=[7])
    name: str = Field(description="클럽 이름", examples=["즉흥 여행 맛집 탐방"])
    category: str = Field(description="클럽 카테고리", examples=["CULTURE"])
    addressCode: str = Field(description="클럽 주소 코드", examples=["1159010800"])
    addressName: str = Field(description="클럽 주소 전체 이름", examples=["서울특별시 동작구 대방동"])
    sidoCode: str = Field(description="클럽 시도 코드", examples=["11"])
    sigunguCode: str = Field(description="클럽 시군구 코드", examples=["590"])
    introText: str | None = Field(default=None, description="클럽 소개 문구")
    thumbnailUrl: str | None = Field(default=None, description="클럽 썸네일 URL")
    capacity: int = Field(description="클럽 정원", examples=[24])
    likes: int = Field(description="클럽 좋아요 수", examples=[55])
    similarityScore: float = Field(description="User.vibeVector와 Club.vibeVector의 cosine similarity", examples=[0.3185])


class CursorPage(BaseModel):
    size: int = Field(description="요청한 페이지 크기", examples=[20])
    hasNext: bool = Field(description="다음 페이지 존재 여부", examples=[False])
    nextCursor: str | None = Field(default=None, description="다음 페이지 조회용 cursor")


class ClubRecommendationData(BaseModel):
    items: list[ClubRecommendationItem] = Field(description="추천 클럽 목록")
    page: CursorPage


class ApiMetaDoc(BaseModel):
    timestamp: str = Field(description="UTC 응답 생성 시각", examples=["2026-06-25T05:32:12.922Z"])
    path: str = Field(description="요청 path", examples=["/api/v1/recommendation/clubs"])


class ClubRecommendationSuccessBody(BaseModel):
    data: ClubRecommendationData


class ClubRecommendationResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "resultType": "SUCCESS",
                "success": {
                    "data": {
                        "items": [
                            {
                                "clubId": 7,
                                "name": "즉흥 여행 맛집 탐방",
                                "category": "CULTURE",
                                "addressCode": "1159010800",
                                "addressName": "서울특별시 동작구 대방동",
                                "sidoCode": "11",
                                "sigunguCode": "590",
                                "introText": "주말에 갑자기 바다를 보러 가거나 새로운 맛집을 찾아다니는 즉흥 여행 동호회입니다.",
                                "thumbnailUrl": "https://cdn.example.com/clubs/dummy-remaining-2.jpg",
                                "capacity": 24,
                                "likes": 55,
                                "similarityScore": 0.3185,
                            }
                        ],
                        "page": {
                            "size": 20,
                            "hasNext": False,
                            "nextCursor": None,
                        },
                    }
                },
                "error": None,
                "meta": {
                    "timestamp": "2026-06-25T05:32:12.922Z",
                    "path": "/api/v1/recommendation/clubs",
                },
            }
        }
    )

    resultType: str = Field(examples=["SUCCESS"])
    success: ClubRecommendationSuccessBody
    error: None = None
    meta: ApiMetaDoc


class ApiErrorDoc(BaseModel):
    code: str = Field(description="서비스 에러 코드", examples=["CLUB-003"])
    message: str = Field(description="에러 메시지", examples=["cursor 값이 올바르지 않습니다."])


class ErrorResponse(BaseModel):
    resultType: str = Field(examples=["FAIL"])
    success: None = None
    error: ApiErrorDoc
    meta: ApiMetaDoc


def _encode_club_cursor(item: Dict[str, Any]) -> str:
    payload = {"similarityScore": item["similarityScore"], "clubId": item["clubId"]}
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii")


def _decode_club_cursor(cursor: str) -> Tuple[float, int]:
    try:
        payload = json.loads(base64.urlsafe_b64decode(cursor.encode("ascii")).decode("utf-8"))
        return float(payload["similarityScore"]), int(payload["clubId"])
    except (binascii.Error, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise AppException(code="CLUB-003", message="cursor 값이 올바르지 않습니다.", status_code=400) from exc


@router.get(
    "/v1/recommendation/clubs",
    response_model=ClubRecommendationResponse,
    summary="유저 맞춤 클럽 추천",
    description=(
        "요청 유저의 `User.vibeVector`와 각 `Club.vibeVector`를 PostgreSQL pgvector cosine similarity로 비교해 "
        "유사도가 높은 클럽을 추천합니다. 유저와 같은 시도/시군구에 속한 클럽만 대상으로 하며, "
        "이미 가입했거나 가입 대기 중인 클럽은 제외합니다."
    ),
    responses={
        400: {
            "model": ErrorResponse,
            "description": "잘못된 cursor 값",
            "content": {
                "application/json": {
                    "example": {
                        "resultType": "FAIL",
                        "success": None,
                        "error": {"code": "CLUB-003", "message": "cursor 값이 올바르지 않습니다."},
                        "meta": {
                            "timestamp": "2026-06-25T05:33:19.079Z",
                            "path": "/api/v1/recommendation/clubs",
                        },
                    }
                }
            },
        },
        404: {
            "model": ErrorResponse,
            "description": "사용자가 없거나 vibeVector가 없는 경우",
            "content": {
                "application/json": {
                    "example": {
                        "resultType": "FAIL",
                        "success": None,
                        "error": {"code": "CLUB-004", "message": "userId가 존재하지 않거나 vibeVector가 없습니다."},
                        "meta": {
                            "timestamp": "2026-06-25T05:33:18.728Z",
                            "path": "/api/v1/recommendation/clubs",
                        },
                    }
                }
            },
        },
        500: {
            "model": ErrorResponse,
            "description": "클럽 추천 조회 실패",
        },
    },
)
async def recommend_clubs(
    request: Request,
    userId: int = Query(..., description="추천 기준 사용자 ID", examples=[9]),
    cursor: str | None = Query(
        default=None,
        description="이전 응답의 page.nextCursor. 첫 페이지 조회 시 생략합니다.",
        examples=["eyJzaW1pbGFyaXR5U2NvcmUiOjAuMzE4NSwiY2x1YklkIjo3fQ=="],
    ),
    size: int = Query(
        default=DEFAULT_CLUB_PAGE_SIZE,
        ge=1,
        le=MAX_CLUB_PAGE_SIZE,
        description="페이지 크기. 최대 50개까지 요청할 수 있습니다.",
        examples=[20],
    ),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    try:
        user_row = await db.execute(
            text(
                """
                SELECT id
                FROM "User" u
                JOIN "Address" ua ON ua.code = u.code
                WHERE u.id = :user_id
                  AND u."deletedAt" IS NULL
                  AND u."vibeVector" IS NOT NULL
                  AND ua."sidoCode" IS NOT NULL
                  AND ua."sigunguCode" IS NOT NULL
                """
            ),
            {"user_id": userId},
        )
        if user_row.mappings().first() is None:
            raise AppException(code="CLUB-004", message="userId가 존재하지 않거나 주소/vibeVector가 없습니다.", status_code=404)

        cursor_score = None
        cursor_club_id = None
        if cursor:
            cursor_score, cursor_club_id = _decode_club_cursor(cursor)

        params = {
            "user_id": userId,
            "threshold": CLUB_SIMILARITY_THRESHOLD,
            "limit": size + 1,
            "cursor_score": cursor_score,
            "cursor_club_id": cursor_club_id,
        }
        rows = await db.execute(
            text(
                """
                WITH requester AS (
                    SELECT
                        u."vibeVector",
                        ua."sidoCode",
                        ua."sigunguCode"
                    FROM "User" u
                    JOIN "Address" ua ON ua.code = u.code
                    WHERE u.id = :user_id
                      AND u."deletedAt" IS NULL
                      AND u."vibeVector" IS NOT NULL
                ),
                scored AS (
                    SELECT
                        c.id AS "clubId",
                        c.name,
                        c.category::text AS category,
                        c.code AS "addressCode",
                        ca."fullName" AS "addressName",
                        ca."sidoCode" AS "sidoCode",
                        ca."sigunguCode" AS "sigunguCode",
                        c."introText",
                        c."thumbnailUrl",
                        c.capacity,
                        c.likes,
                        ROUND((1 - (c."vibeVector" <=> requester."vibeVector"))::numeric, 4)::float AS "similarityScore"
                    FROM "Club" c
                    JOIN "Address" ca ON ca.code = c.code
                    CROSS JOIN requester
                    WHERE c."deletedAt" IS NULL
                      AND c."vibeVector" IS NOT NULL
                      AND ca."sidoCode" = requester."sidoCode"
                      AND ca."sigunguCode" = requester."sigunguCode"
                      AND NOT EXISTS (
                          SELECT 1
                          FROM "ClubUser" cu
                          WHERE cu."clubId" = c.id
                            AND cu."userId" = :user_id
                            AND cu."leftAt" IS NULL
                            AND cu.status IN ('ACTIVE'::"ClubUserStatus", 'PENDING'::"ClubUserStatus")
                      )
                )
                SELECT *
                FROM scored
                WHERE "similarityScore" >= :threshold
                  AND (
                      CAST(:cursor_score AS double precision) IS NULL
                      OR "similarityScore" < CAST(:cursor_score AS double precision)
                      OR (
                          "similarityScore" = CAST(:cursor_score AS double precision)
                          AND "clubId" > CAST(:cursor_club_id AS bigint)
                      )
                  )
                ORDER BY "similarityScore" DESC, "clubId" ASC
                LIMIT :limit
                """
            ),
            params,
        )
    except AppException:
        raise
    except Exception as exc:
        logger.exception("club recommendation failed", extra={"userId": userId})
        raise AppException(code="CLUB-005", message=f"클럽 추천 조회 실패: {exc}", status_code=500) from exc

    page_items = [dict(row) for row in rows.mappings().all()]
    has_next = len(page_items) > size
    items = page_items[:size]
    next_cursor = _encode_club_cursor(items[-1]) if has_next and items else None

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


@router.post("/v1/onboarding/club-vibe/analyze")
async def analyze_club_vibe(payload: AnalyzeClubVibeRequest, request: Request) -> Dict[str, Any]:
    club_id = payload.clubId if payload.clubId is not None else payload.club_id

    if club_id is None:
        raise AppException(
            code="CLUB-001",
            message="clubId(또는 club_id)가 필요합니다.",
            status_code=400,
        )

    transcript_text = payload.transcript

    if not transcript_text and payload.local_audio_path:
        stt_result = transcribe_local_audio(payload.local_audio_path)
        transcript_text = stt_result.get("transcript", "")

    if not transcript_text:
        raise AppException(
            code="CLUB-002",
            message="transcript 또는 local_audio_path가 필요합니다.",
            status_code=400,
        )

    summary = await summarize_transcript(transcript_text)
    vector_id, matched_keywords, vibe_vector = await analyze_voice_profile(
        transcript_text,
        club_id,
    )

    if payload.analysis_type != "profile":
        vibe_vector = None
        vector_id = None

    return success_response(
        request,
        {
            "clubId": club_id,
            "transcript": transcript_text,
            "summary": summary,
            "vectorId": vector_id,
            "matchedKeywords": matched_keywords,
            "vibeVector": vibe_vector,
        },
    )

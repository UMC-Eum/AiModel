from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Query, Request

from app.core.response import success_response

router = APIRouter(tags=["matches"])


@router.get("/v1/matches/recommendations")
async def list_recommendations(
    request: Request,
    cursor: Optional[str] = Query(default=None),
    limit: Optional[int] = Query(default=None),
) -> Dict[str, Any]:
    # TODO: Implement similarity scoring (vibe vectors + keywords) and pagination.
    return success_response(
        request,
        {
            "nextCursor": (cursor + "_next") if cursor else "opaque_cursor",
            "items": [
                {
                    "userId": 9,
                    "nickname": "루씨",
                    "age": 53,
                    "areaName": "동작구",
                    "keywords": ["뜨개질", "문화생활"],
                    "introText": "서로를 알아가는 첫 이야기...",
                    "introAudioUrl": "https://cdn.example.com/files/u9_intro.m4a",
                    "profileImageUrl": "https://cdn.example.com/files/u9_profile.jpg",
                    "matchScore": 0.87,
                    "matchReasons": ["관심사 유사", "목소리 톤 유사"],
                    "isLiked": True,
                    "likedHeartId": 1,
                }
            ],
            "limit": limit,
        },
    )

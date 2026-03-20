from datetime import datetime
from fastapi import APIRouter, Query

router = APIRouter(tags=["matches"])


@router.get("/v1/matches/recommendations")
async def list_recommendations(cursor: str | None = Query(default=None), limit: int | None = Query(default=None)) -> dict:
  # TODO: Implement similarity scoring (vibe vectors + keywords) and pagination.
    now = datetime.utcnow().isoformat() + "Z"
    return {
        "resultType": "SUCCESS",
        "success": {
            "data": {
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
            }
        },
        "error": None,
        "meta": {
            "timestamp": now,
            "path": "/api/v1/matches/recommendations",
        },
    }

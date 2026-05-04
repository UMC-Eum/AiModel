from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.services.llm import analyze_voice_profile, summarize_transcript
from app.services.stt import transcribe_local_audio

router = APIRouter(tags=["club"])


class AnalyzeClubVibeRequest(BaseModel):
    clubId: int
    transcript: Optional[str] = None
    local_audio_path: Optional[str] = None
    analysis_type: Optional[str] = "profile"


@router.get("/v1/recommendation/clubs")
async def recommend_clubs(userId: int = Query(..., description="추천 기준 사용자 ID")) -> Dict[str, Any]:
    now = datetime.utcnow().isoformat() + "Z"
    return {
        "resultType": "SUCCESS",
        "success": {
            "data": {
                "userId": userId,
                "items": [],
            }
        },
        "error": None,
        "meta": {
            "timestamp": now,
            "path": "/api/v1/recommendation/clubs",
        },
    }


@router.post("/v1/onboarding/club-vibe/analyze")
async def analyze_club_vibe(payload: AnalyzeClubVibeRequest) -> Dict[str, Any]:
    now = datetime.utcnow().isoformat() + "Z"

    transcript_text = payload.transcript

    if not transcript_text and payload.local_audio_path:
        stt_result = transcribe_local_audio(payload.local_audio_path)
        transcript_text = stt_result.get("transcript", "")

    if not transcript_text:
        return {
            "resultType": "FAIL",
            "error": {"message": "transcript 또는 local_audio_path가 필요합니다."},
            "success": None,
            "meta": {
                "timestamp": now,
                "path": "/api/v1/onboarding/club-vibe/analyze",
            },
        }

    try:
        summary = await summarize_transcript(transcript_text)
        vector_id, matched_keywords, vibe_vector = await analyze_voice_profile(
            transcript_text,
            payload.clubId,
        )
    except Exception as exc:
        return {
            "resultType": "FAIL",
            "error": {"message": str(exc)},
            "success": None,
            "meta": {
                "timestamp": now,
                "path": "/api/v1/onboarding/club-vibe/analyze",
            },
        }

    if payload.analysis_type != "profile":
        vibe_vector = None
        vector_id = None

    return {
        "resultType": "SUCCESS",
        "success": {
            "data": {
                "clubId": payload.clubId,
                "transcript": transcript_text,
                "summary": summary,
                "vectorId": vector_id,
                "matchedKeywords": matched_keywords,
                "vibeVector": vibe_vector,
            }
        },
        "error": None,
        "meta": {
            "timestamp": now,
            "path": "/api/v1/onboarding/club-vibe/analyze",
        },
    }

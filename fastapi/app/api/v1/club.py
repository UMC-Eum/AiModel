from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel

from app.core.exceptions import AppException
from app.core.response import success_response
from app.services.llm import analyze_voice_profile, summarize_transcript
from app.services.stt import transcribe_local_audio

router = APIRouter(tags=["club"])


class AnalyzeClubVibeRequest(BaseModel):
    clubId: Optional[int] = None
    club_id: Optional[int] = None
    transcript: Optional[str] = None
    local_audio_path: Optional[str] = None
    analysis_type: Optional[str] = "profile"


@router.get("/v1/recommendation/clubs")
async def recommend_clubs(request: Request, userId: int = Query(..., description="추천 기준 사용자 ID")) -> Dict[str, Any]:
    return success_response(
        request,
        {
            "userId": userId,
            "items": [],
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

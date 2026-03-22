from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from app.services.llm import analyze_keywords, summarize_transcript
from app.services.stt import transcribe_local_audio

router = APIRouter(tags=["onboarding"])


class AnalyzeVoiceProfileRequest(BaseModel):
    transcript: Optional[str] = None
    local_audio_path: Optional[str] = None
    analysis_type: Optional[str] = "profile"
    user_id: Optional[int] = None


@router.post("/v1/onboarding/voice-profile/analyze")
async def analyze(payload: AnalyzeVoiceProfileRequest) -> Dict[str, Any]:
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
            "meta": {"timestamp": now, "path": "/api/v1/onboarding/voice-profile/analyze"},
        }

    summary = summarize_transcript(transcript_text)
    keyword_candidates, vibe_vector = analyze_keywords(transcript_text)
    if payload.analysis_type != "profile":
        vibe_vector = None

    return {
        "resultType": "SUCCESS",
        "success": {
            "data": {
                "transcript": transcript_text,
                "summary": summary,
                "keywordCandidates": keyword_candidates,
                "vibeVector": vibe_vector,
            }
        },
        "error": None,
        "meta": {
            "timestamp": now,
            "path": "/api/v1/onboarding/voice-profile/analyze",
        },
    }

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, Field

from app.core.exceptions import AppException
from app.core.response import success_response
from app.services.llm import analyze_voice_profile, summarize_transcript
from app.services.stt import AudioDownloadError, transcribe_audio_url, transcribe_local_audio

router = APIRouter(tags=["onboarding"])


class AnalyzeVoiceProfileRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    transcript: Optional[str] = None
    audio_url: Optional[str] = Field(default=None, alias="audioUrl")
    local_audio_path: Optional[str] = None
    analysis_type: Optional[str] = "profile"
    user_id: Optional[int] = None


@router.post("/v1/onboarding/voice-profile/analyze")
async def analyze(payload: AnalyzeVoiceProfileRequest, request: Request) -> Dict[str, Any]:
    transcript_text = payload.transcript

    if not transcript_text:
        try:
            if payload.audio_url:
                stt_result = await transcribe_audio_url(payload.audio_url)
                transcript_text = stt_result.get("transcript", "")
            elif payload.local_audio_path:
                stt_result = transcribe_local_audio(payload.local_audio_path)
                transcript_text = stt_result.get("transcript", "")
        except AudioDownloadError as exc:
            raise AppException(code="ONBOARDING-002", message=str(exc), status_code=400) from exc
        except FileNotFoundError as exc:
            raise AppException(code="ONBOARDING-003", message=str(exc), status_code=400) from exc

    if not transcript_text:
        raise AppException(
            code="ONBOARDING-001",
            message="transcript, audioUrl 또는 local_audio_path가 필요합니다.",
            status_code=400,
        )

    summary = await summarize_transcript(transcript_text)
    vector_id, matched_keywords, vibe_vector = await analyze_voice_profile(transcript_text, payload.user_id)

    if payload.analysis_type != "profile":
        vibe_vector = None
        vector_id = None

    return success_response(
        request,
        {
            "transcript": transcript_text,
            "summary": summary,
            "vectorId": vector_id,
            "matchedKeywords": matched_keywords,
            "vibeVector": vibe_vector,
        },
    )

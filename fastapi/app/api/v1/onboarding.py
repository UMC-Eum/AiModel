from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, Field

from app.core.exceptions import AppException
from app.core.response import success_response
from app.services.llm import analyze_voice_profile, summarize_transcript
from app.services.stt import AudioDownloadError, transcribe_audio_url

router = APIRouter(tags=["onboarding"])


class AnalyzeVoiceProfileRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    transcript: Optional[str] = Field(
        default=None,
        description="사용자 음성 전사 텍스트. audioUrl이 없으면 필수입니다.",
        examples=["저는 조용한 카페에서 책 읽는 걸 좋아하고, 주말에는 가볍게 산책하는 편입니다."],
    )
    audio_url: Optional[str] = Field(
        default=None,
        alias="audioUrl",
        description="S3 presigned GET URL. transcript가 없을 때 STT 분석에 사용합니다.",
        examples=["https://example-bucket.s3.ap-northeast-2.amazonaws.com/audio/user-voice.wav?..."],
    )
    analysis_type: Optional[str] = Field(
        default="profile",
        description="profile이면 vibeVector/vectorId를 포함하고, 다른 값이면 요약/키워드만 반환합니다.",
        examples=["profile"],
    )
    user_id: Optional[int] = Field(default=None, description="분석 대상 사용자 ID", examples=[9])


class AnalyzeVoiceProfileData(BaseModel):
    transcript: str = Field(
        description="분석에 사용된 전사 텍스트",
        examples=["저는 조용한 카페에서 책 읽는 걸 좋아하고, 주말에는 가볍게 산책하는 편입니다."],
    )
    summary: str = Field(description="전사 텍스트 요약", examples=["조용한 공간에서 독서와 산책을 즐기는 차분한 성향입니다."])
    vectorId: str | None = Field(default=None, description="생성된 벡터 식별자. analysis_type이 profile이 아니면 null입니다.", examples=["9"])
    matchedKeywords: list[Dict[str, Any]] = Field(
        description="전사 텍스트에서 추출/매칭된 키워드 목록입니다. 각 항목은 키워드 ID, 이름, 카테고리, 점수를 포함합니다.",
        examples=[[{"id": 21, "keyword": "차분함", "category": "PERSONALITY", "score": 0.86}]],
    )
    vibeVector: list[float] | None = Field(
        default=None,
        description="생성된 사용자 vibe vector입니다. analysis_type이 profile이 아니면 null입니다.",
        examples=[[0.12, -0.04, 0.31]],
    )


class AnalyzeVoiceProfileSuccessBody(BaseModel):
    data: AnalyzeVoiceProfileData


class ApiMetaDoc(BaseModel):
    timestamp: str = Field(description="UTC 응답 생성 시각", examples=["2026-06-30T05:32:12.922Z"])
    path: str = Field(description="요청 path", examples=["/api/v1/onboarding/voice-profile/analyze"])


class ApiErrorDoc(BaseModel):
    code: str = Field(description="서비스 에러 코드", examples=["ONBOARDING-001"])
    message: str = Field(description="에러 메시지", examples=["transcript 또는 audioUrl이 필요합니다."])


class AnalyzeVoiceProfileResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "resultType": "SUCCESS",
                "success": {
                    "data": {
                        "transcript": "저는 조용한 카페에서 책 읽는 걸 좋아하고, 주말에는 가볍게 산책하는 편입니다.",
                        "summary": "조용한 공간에서 독서와 산책을 즐기는 차분한 성향입니다.",
                        "vectorId": "9",
                        "matchedKeywords": [{"id": 21, "keyword": "차분함", "category": "PERSONALITY", "score": 0.86}],
                        "vibeVector": [0.12, -0.04, 0.31],
                    }
                },
                "error": None,
                "meta": {
                    "timestamp": "2026-06-30T05:32:12.922Z",
                    "path": "/api/v1/onboarding/voice-profile/analyze",
                },
            }
        }
    )

    resultType: str = Field(examples=["SUCCESS"])
    success: AnalyzeVoiceProfileSuccessBody
    error: None = None
    meta: ApiMetaDoc


class ErrorResponse(BaseModel):
    resultType: str = Field(examples=["FAIL"])
    success: None = None
    error: ApiErrorDoc
    meta: ApiMetaDoc


@router.post(
    "/v1/onboarding/voice-profile/analyze",
    response_model=AnalyzeVoiceProfileResponse,
    summary="사용자 voice profile 분석",
    description=(
        "사용자 음성 또는 전사 텍스트를 분석해 요약, 매칭 키워드, vibe vector를 반환합니다. "
        "`transcript`가 없고 `audioUrl`이 있으면 STT로 전사한 뒤 분석합니다. "
        "현재 생성된 `vibeVector`와 `matchedKeywords`는 응답으로 반환되며 DB에 직접 저장하지 않습니다."
    ),
    responses={
        400: {
            "model": ErrorResponse,
            "description": "분석 입력값 누락 또는 audioUrl 다운로드 실패",
            "content": {
                "application/json": {
                    "examples": {
                        "missingInput": {
                            "summary": "분석 입력값 누락",
                            "value": {
                                "resultType": "FAIL",
                                "success": None,
                                "error": {
                                    "code": "ONBOARDING-001",
                                    "message": "transcript 또는 audioUrl이 필요합니다.",
                                },
                                "meta": {
                                    "timestamp": "2026-06-30T05:32:12.922Z",
                                    "path": "/api/v1/onboarding/voice-profile/analyze",
                                },
                            },
                        },
                        "audioDownloadFailed": {
                            "summary": "audioUrl 다운로드 실패",
                            "value": {
                                "resultType": "FAIL",
                                "success": None,
                                "error": {
                                    "code": "ONBOARDING-002",
                                    "message": "audioUrl 다운로드 실패(status=403)",
                                },
                                "meta": {
                                    "timestamp": "2026-06-30T05:32:12.922Z",
                                    "path": "/api/v1/onboarding/voice-profile/analyze",
                                },
                            },
                        },
                    }
                }
            },
        },
        422: {
            "model": ErrorResponse,
            "description": "요청 본문 형식 오류",
        },
    },
)
async def analyze(payload: AnalyzeVoiceProfileRequest, request: Request) -> Dict[str, Any]:
    transcript_text = payload.transcript

    if not transcript_text:
        try:
            if payload.audio_url:
                stt_result = await transcribe_audio_url(payload.audio_url)
                transcript_text = stt_result.get("transcript", "")
        except AudioDownloadError as exc:
            raise AppException(code="ONBOARDING-002", message=str(exc), status_code=400) from exc

    if not transcript_text:
        raise AppException(
            code="ONBOARDING-001",
            message="transcript 또는 audioUrl이 필요합니다.",
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

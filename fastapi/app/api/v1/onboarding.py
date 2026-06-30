from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Any, Dict

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, Field

from app.core.exceptions import AppException
from app.core.response import success_response
from app.services.llm import analyze_voice_profile, summarize_transcript
from app.services.stt import AudioDownloadError, transcribe_audio_url

router = APIRouter(tags=["onboarding"])


class Sex(str, Enum):
    M = "M"
    F = "F"


def _calculate_age(birthdate: date, today: date | None = None) -> int:
    today = today or date.today()
    age = today.year - birthdate.year
    if (today.month, today.day) < (birthdate.month, birthdate.day):
        age -= 1
    return age


def _build_vibe_vector_input(transcript: str, age: int, sex: Sex) -> str:
    return "\n".join(
        [
            "사용자 소개 전사:",
            transcript,
            "",
            "사용자 기본 정보:",
            f"- 나이: {age}세",
            f"- 성별: {sex.value}",
        ]
    )


class AnalyzeVoiceProfileRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "introAudioUrl": "https://example-bucket.s3.ap-northeast-2.amazonaws.com/audio/user-voice.wav?...",
                    "birthdate": "1969-05-14",
                    "sex": "F",
                }
            ]
        },
    )

    intro_audio_url: str = Field(
        alias="introAudioUrl",
        description="사용자 소개 음성 파일의 S3 presigned GET URL입니다.",
        examples=["https://example-bucket.s3.ap-northeast-2.amazonaws.com/audio/user-voice.wav?..."],
    )
    birthdate: date = Field(description="사용자 생년월일입니다. 만 나이 계산에 사용합니다.", examples=["1969-05-14"])
    sex: Sex = Field(description="사용자 성별입니다. vibe vector 생성 입력에 포함합니다.", examples=["F"])


class AnalyzeVoiceProfileData(BaseModel):
    transcript: str = Field(
        description="분석에 사용된 전사 텍스트",
        examples=["저는 조용한 카페에서 책 읽는 걸 좋아하고, 주말에는 가볍게 산책하는 편입니다."],
    )
    summary: str = Field(description="전사 텍스트 요약", examples=["조용한 공간에서 독서와 산책을 즐기는 차분한 성향입니다."])
    vectorId: str | None = Field(default=None, description="생성된 벡터 식별자입니다. 현재 DB 저장을 하지 않으므로 null입니다.", examples=[None])
    matchedKeywords: list[Dict[str, Any]] = Field(
        description="전사 텍스트에서 추출/매칭된 키워드 목록입니다. 각 항목은 키워드 ID, 이름, 카테고리, 점수를 포함합니다.",
        examples=[[{"id": 21, "keyword": "차분함", "category": "PERSONALITY", "score": 0.86}]],
    )
    vibeVector: list[float] | None = Field(
        default=None,
        description="생성된 사용자 vibe vector입니다.",
        examples=[[0.12, -0.04, 0.31]],
    )


class AnalyzeVoiceProfileSuccessBody(BaseModel):
    data: AnalyzeVoiceProfileData


class ApiMetaDoc(BaseModel):
    timestamp: str = Field(description="UTC 응답 생성 시각", examples=["2026-06-30T05:32:12.922Z"])
    path: str = Field(description="요청 path", examples=["/api/v1/onboarding/voice-profile/analyze"])


class ApiErrorDoc(BaseModel):
    code: str = Field(description="서비스 에러 코드", examples=["ONBOARDING-001"])
    message: str = Field(description="에러 메시지", examples=["introAudioUrl, birthdate, sex가 필요합니다."])


class AnalyzeVoiceProfileResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "resultType": "SUCCESS",
                "success": {
                    "data": {
                        "transcript": "저는 조용한 카페에서 책 읽는 걸 좋아하고, 주말에는 가볍게 산책하는 편입니다.",
                        "summary": "조용한 공간에서 독서와 산책을 즐기는 차분한 성향입니다.",
                        "vectorId": None,
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
        "`introAudioUrl`의 사용자 소개 음성을 STT로 전사한 뒤, 전사 텍스트와 birthdate로 계산한 나이, sex를 함께 사용해 vibe vector를 생성합니다. "
        "현재 생성된 `vibeVector`와 `matchedKeywords`는 응답으로 반환되며 DB에 직접 저장하지 않습니다."
    ),
    responses={
        400: {
            "model": ErrorResponse,
            "description": "필수 입력값 누락, birthdate 오류 또는 다운로드 실패",
            "content": {
                "application/json": {
                    "examples": {
                        "missingInput": {
                            "summary": "필수 입력값 누락",
                            "value": {
                                "resultType": "FAIL",
                                "success": None,
                                "error": {
                                    "code": "ONBOARDING-001",
                                    "message": "introAudioUrl, birthdate, sex가 필요합니다.",
                                },
                                "meta": {
                                    "timestamp": "2026-06-30T05:32:12.922Z",
                                    "path": "/api/v1/onboarding/voice-profile/analyze",
                                },
                            },
                        },
                        "audioDownloadFailed": {
                            "summary": "introAudioUrl 다운로드 실패",
                            "value": {
                                "resultType": "FAIL",
                                "success": None,
                                "error": {
                                    "code": "ONBOARDING-002",
                                    "message": "introAudioUrl 다운로드 실패(status=403)",
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
    if not payload.intro_audio_url:
        raise AppException(
            code="ONBOARDING-001",
            message="introAudioUrl, birthdate, sex가 필요합니다.",
            status_code=400,
        )

    age = _calculate_age(payload.birthdate)
    if age < 0:
        raise AppException(
            code="ONBOARDING-003",
            message="birthdate는 미래 날짜일 수 없습니다.",
            status_code=400,
        )

    try:
        stt_result = await transcribe_audio_url(payload.intro_audio_url)
        transcript_text = stt_result.get("transcript", "")
    except AudioDownloadError as exc:
        raise AppException(code="ONBOARDING-002", message=str(exc).replace("audioUrl", "introAudioUrl"), status_code=400) from exc

    if not transcript_text:
        raise AppException(
            code="ONBOARDING-001",
            message="introAudioUrl에서 전사 텍스트를 추출할 수 없습니다.",
            status_code=400,
        )

    summary = await summarize_transcript(transcript_text)
    vector_input = _build_vibe_vector_input(transcript_text, age, payload.sex)
    vector_id, matched_keywords, vibe_vector = await analyze_voice_profile(
        transcript_text,
        embedding_input=vector_input,
    )

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

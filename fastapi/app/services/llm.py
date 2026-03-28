"""LLM 기반 요약/키워드/벡터 헬퍼."""

import asyncio
import json
from typing import Any, Dict, List, Optional, Tuple

from openai import AsyncOpenAI, OpenAIError

from app.core.config import get_settings
from app.services.keywords import KEYWORD_SYSTEM_PROMPT
# 저장은 비활성화 모드이므로 스토리지 모듈을 불러오지 않습니다.
from app.services.vibe import normalize_vector


def _client() -> AsyncOpenAI:
    settings = get_settings()
    if not settings.openai_api_key:
        raise ValueError("OPENAI_API_KEY가 설정되지 않았습니다 (.env에 추가).")
    return AsyncOpenAI(api_key=settings.openai_api_key)


async def _extract_keywords(transcript: str) -> List[Dict[str, Any]]:
    """GPT-4o-mini로 키워드를 추출한다 (JSON 스키마 준수)."""
    client = _client()
    try:
        resp = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": KEYWORD_SYSTEM_PROMPT},
                {"role": "user", "content": transcript},
            ],
            max_tokens=600,
            temperature=0.1,
        )
    except OpenAIError as exc:
        raise RuntimeError(f"키워드 추출 실패: {exc}") from exc

    content = resp.choices[0].message.content or "{}"
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        # 비정형 응답 대응
        raise RuntimeError("키워드 응답이 JSON 형식이 아닙니다.")

    matched_raw = parsed.get("matched") or []
    results: List[Dict[str, Any]] = []
    for item in matched_raw:
        try:
            results.append(
                {
                    "id": int(item.get("id")),
                    "keyword": str(item.get("keyword")),
                    "category": str(item.get("category")),
                    "score": float(item.get("score")),
                }
            )
        except (TypeError, ValueError):
            continue
        if len(results) >= 15:
            break
    return results


async def summarize_transcript(transcript: str) -> str:
    client = _client()
    try:
        resp = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "주요 사실과 관심사를 2문장 이내로 요약해 주세요."},
                {"role": "user", "content": transcript},
            ],
            max_tokens=120,
            temperature=0.2,
        )
    except OpenAIError as exc:
        raise RuntimeError(f"요약 생성 실패: {exc}") from exc
    return (resp.choices[0].message.content or "").strip()


async def _generate_semantic_embedding(transcript: str) -> List[float]:
    """text-embedding-3-large로 1536차원 임베딩을 생성한다."""
    client = _client()
    try:
        resp = await client.embeddings.create(model="text-embedding-3-large", input=transcript)
    except OpenAIError as exc:
        raise RuntimeError(f"임베딩 생성 실패: {exc}") from exc

    embedding = resp.data[0].embedding
    return normalize_vector(embedding)


async def analyze_voice_profile(transcript: str, user_id: Optional[int] = None) -> Tuple[str, List[Dict[str, Any]], List[float]]:
    """전사문을 임베딩하고 키워드를 추출해 반환한다 (DB 저장 없음)."""
    embed_task = asyncio.create_task(_generate_semantic_embedding(transcript))
    keyword_task = asyncio.create_task(_extract_keywords(transcript))

    vector, matched_keywords = await asyncio.gather(embed_task, keyword_task)

    # DB는 read-only이므로 저장하지 않고, user_id만 그대로 반환 식별자로 사용한다.
    vector_id = str(user_id) if user_id is not None else None

    return vector_id, matched_keywords, vector

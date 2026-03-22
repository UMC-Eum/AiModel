"""LLM 기반 요약/키워드/벡터 헬퍼 (로컬 테스트용).

- 요약: gpt-4o-mini
- 키워드/벡터: 제공된 카테고리·키워드 집합을 기준으로 매칭 후 벡터화
"""

import re
from typing import Dict, List, Tuple

from openai import OpenAI

from app.core.config import get_settings
from app.services.keywords import KEYWORDS, KEYWORD_INDEX, KeywordEntry
from app.services.vibe import normalize_vector


def _client() -> OpenAI:
    settings = get_settings()
    if not settings.openai_api_key:
        raise ValueError("OPENAI_API_KEY가 설정되지 않았습니다 (.env에 추가).")
    return OpenAI(api_key=settings.openai_api_key)


def summarize_transcript(transcript: str) -> str:
    client = _client()
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "주요 사실과 관심사를 2문장 이내로 요약해 주세요."},
            {"role": "user", "content": transcript},
        ],
        max_tokens=120,
        temperature=0.2,
    )
    return resp.choices[0].message.content.strip()


def analyze_keywords(transcript: str) -> Tuple[Dict[str, List[dict]], List[float]]:
    """텍스트에서 고정 키워드를 카테고리 단위로 매칭하고, 벡터를 생성합니다."""
    lowered = transcript.lower()
    normalized_ws_transcript = re.sub(r"\s+", "", lowered)
    normalized_plain_transcript = re.sub(r"[^0-9a-zA-Zㄱ-ㅎ가-힣]+", "", lowered)

    vector = [0.0 for _ in KEYWORDS]
    grouped: Dict[str, List[dict]] = {}

    for entry in KEYWORDS:
        if not entry.text:
            continue
        hit = False
        text_lower = entry.text.lower()

        # 1) 그대로 포함 여부
        if text_lower in lowered:
            hit = True
        # 2) 공백 제거 매칭
        elif entry.normalized_ws and entry.normalized_ws in normalized_ws_transcript:
            hit = True
        # 3) 이모지/기호 제거 후 매칭 (예: "🥾 등산" → "등산")
        elif entry.normalized_plain and entry.normalized_plain in normalized_plain_transcript:
            hit = True

        if hit:
            score = 1.0
            grouped.setdefault(entry.category, []).append({"text": entry.text, "score": score})
            idx = KEYWORD_INDEX.get((entry.category, entry.text))
            if idx is not None:
                vector[idx] = max(vector[idx], score)

    vibe_vector = normalize_vector(vector) if any(vector) else vector
    return grouped, vibe_vector


def extract_keywords(transcript: str) -> Dict[str, List[dict]]:
    grouped, _ = analyze_keywords(transcript)
    return grouped


def generate_vibe_vector(transcript: str) -> List[float]:
    _, vector = analyze_keywords(transcript)
    return vector

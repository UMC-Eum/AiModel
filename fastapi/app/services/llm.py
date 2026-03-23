"""LLM 기반 요약/키워드/벡터 헬퍼 (로컬 테스트용).

- 요약: gpt-4o-mini
- 키워드/벡터: 제공된 카테고리·키워드 집합을 기준으로 매칭 후 벡터화
"""

import json
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


def llm_suggest_keywords(transcript: str, max_count: int = 10) -> List[Tuple[str, str]]:
    """LLM에게 고정 키워드 집합 중 맥락상 맞는 키워드를 제안받는다.

    반환: [(카테고리, 키워드), ...]
    """
    client = _client()

    keyword_list = [f"{k.category}:{k.text}" for k in KEYWORDS]
    system_prompt = (
        "다음은 고정 키워드 목록입니다. 전사 텍스트의 맥락에 맞는 키워드를 최대 "
        f"{max_count}개 선택하세요. 출력은 JSON 배열 형태로, 각 항목은 {{'category': '...', 'text': '...'}}입니다."
    )

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"전사 텍스트: {transcript}\n키워드 목록: {', '.join(keyword_list)}"},
        ],
        max_tokens=400,
        temperature=0.2,
    )

    content = resp.choices[0].message.content or "[]"
    try:
        data = json.loads(content)
    except Exception:
        # 콤마/줄바꿈 분리 대응
        items = []
        for line in content.splitlines():
            line = line.strip()
            if not line:
                continue
            if ":" in line:
                parts = line.split(":", 1)
                items.append({"category": parts[0].strip(), "text": parts[1].strip()})
        data = items

    results: List[Tuple[str, str]] = []
    for item in data:
        cat = (item.get("category") or "").strip()
        text = (item.get("text") or "").strip()
        if cat and text:
            results.append((cat, text))
        if len(results) >= max_count:
            break
    return results


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

    # 2차 보강: 최소 5개 이상 되도록 토큰 매칭으로 추가
    total_hits = sum(len(v) for v in grouped.values())
    if total_hits < 5:
        tokens = re.findall(r"[0-9a-zA-Zㄱ-ㅎ가-힣]+", lowered)
        remaining = 5 - total_hits
        seen_keys = {(c, item["text"]) for c, items in grouped.items() for item in items}

        for entry in KEYWORDS:
            if remaining <= 0:
                break
            key = (entry.category, entry.text)
            if key in seen_keys:
                continue
            if not entry.normalized_plain:
                continue
            if entry.normalized_plain in normalized_plain_transcript or entry.normalized_plain in tokens:
                score = 0.7
                grouped.setdefault(entry.category, []).append({"text": entry.text, "score": score})
                idx = KEYWORD_INDEX.get(key)
                if idx is not None:
                    vector[idx] = max(vector[idx], score)
                seen_keys.add(key)
                remaining -= 1

        # 3차: LLM 기반 맥락 매칭 (최대 10개, 최소 5개 보장)
        total_hits = sum(len(v) for v in grouped.values())
        if total_hits < 10:
            suggested = llm_suggest_keywords(transcript, max_count=10)
            seen_keys = {(c, item["text"]) for c, items in grouped.items() for item in items}
            for cat, text in suggested:
                key = (cat, text)
                if key in seen_keys:
                    continue
                # 검증: 실제 키워드 목록에 존재하는지 확인
                if key not in KEYWORD_INDEX:
                    continue
                score = 0.8
                grouped.setdefault(cat, []).append({"text": text, "score": score})
                idx = KEYWORD_INDEX.get(key)
                if idx is not None:
                    vector[idx] = max(vector[idx], score)
                seen_keys.add(key)
                total_hits += 1
                if total_hits >= 10:
                    break

    vibe_vector = normalize_vector(vector) if any(vector) else vector
    return grouped, vibe_vector


def extract_keywords(transcript: str) -> Dict[str, List[dict]]:
    grouped, _ = analyze_keywords(transcript)
    return grouped


def generate_vibe_vector(transcript: str) -> List[float]:
    _, vector = analyze_keywords(transcript)
    return vector

# Vibe Vector 메모

## 개요
- 입력: 사용자 전사문 텍스트
- 모델: OpenAI `text-embedding-3-large`
- 결과: 1536차원 float 벡터 → L2 정규화되어 코사인 유사도 계산 가능
- 상태: 현재 코드는 DB에 쓰지 않고, API 응답으로만 반환합니다 (read-only 모드).

## 생성 흐름
1) 전사문 확보 (직접 입력 또는 STT 결과).
2) 임베딩 생성: `text-embedding-3-large` → 1536차원 → L2 정규화.
3) 키워드 추출: GPT-4o-mini, 고정 380개 키워드 리스트 기반 JSON 응답.
4) 비동기 처리: 임베딩 생성과 키워드 추출을 `asyncio.gather()`로 병렬 수행.
5) 반환: `vectorId`(user_id 문자열 또는 None), `matchedKeywords`, `vibeVector`.

## 유사도 계산 (코사인)
```python
import numpy as np

def cosine_similarity(a, b):
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
```
- 1.0: 동일 의미
- 0.8~: 매우 유사 (추천 대상)
- 0.5~: 어느 정도 유사
- 0.0: 무관

## 차원/크기 가이드
- 1536 (기본, `text-embedding-3-large`): 정확도 최고, JSON 저장 시 ≈12KB/명
- 512 (`text-embedding-3-small`): 정확도 좋음, ≈4KB/명
- 256 (`text-embedding-3-small` 축소): 무난, ≈2KB/명

## API 사용
- 엔드포인트: `POST /api/v1/onboarding/voice-profile/analyze`
- 요청 예시:
```json
{
  "transcript": "저는 등산하고 독서를 좋아해요",
  "user_id": 123
}
```
- 응답 예시(요약):
```json
{
  "resultType": "SUCCESS",
  "success": {
    "data": {
      "transcript": "...",
      "summary": "...",
      "vectorId": "123",      // 저장은 안 하지만 식별자로 반환
      "matchedKeywords": [...],
      "vibeVector": [0.025076, -0.014549, ...] // 길이 1536
    }
  },
  "error": null,
  "meta": {...}
}
```

## 환경 변수
- 필수: `OPENAI_API_KEY`
- 선택: `MYSQL_DSN`, `MYSQL_API_ENDPOINT` (현재 코드는 저장 호출을 하지 않음)

## 코드 위치
- 임베딩/키워드 파이프라인: `app/services/llm.py`
- 키워드 프롬프트 상수: `app/services/keywords.py`
- 온보딩 API: `app/api/v1/onboarding.py`
- (비활성화된) 저장 헬퍼: `app/services/storage.py`

## 현재 저장 동작
- `analyze_voice_profile`에서 저장 함수를 호출하지 않으므로 DB에 쓰지 않습니다.
- 저장을 복원하려면 `llm.py`에서 `save_vibe_vector`, `save_user_keywords` 호출을 다시 연결하고 `.env`에 DSN 또는 HTTP 엔드포인트를 설정하세요.

## 주의/할 일
- 매칭 계산 시 코사인 유사도 사용을 전제합니다. (벡터는 이미 L2 정규화)
- user_keywords 스키마가 다르면 `storage.py`의 INSERT 문을 맞춰야 합니다(저장 복원 시).

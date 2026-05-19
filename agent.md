# agent.md

이 문서는 이 저장소에서 작업하는 AI 코딩 에이전트(Copilot/Claude 등)의 **실행 가이드라인**입니다.  
`CLAUDE.md`의 원칙을 따르되, 이 프로젝트의 실제 구조와 운영 맥락에 맞게 구체화합니다.

## 1) 프로젝트 컨텍스트 (필수 이해)

- 이 저장소의 핵심은 **NestJS 백엔드가 호출하는 FastAPI 기반 AI 서비스**입니다.
- 현재 주요 역할:
  1. 온보딩 음성/텍스트 분석 (`POST /api/v1/onboarding/voice-profile/analyze`)
  2. 유사도 기반 사용자 추천 (`GET /api/v1/onboarding/matches/recommend?userId=...`)
- AI 파이프라인은 OpenAI를 사용합니다.
  - STT: `gpt-4o-mini-transcribe`
  - 요약/키워드: `gpt-4o-mini`
  - 임베딩: `text-embedding-3-large` (3072d, L2 정규화)
- DB는 비동기 PostgreSQL(SQLAlchemy + asyncpg)이며, `User` 모델은 NestJS 스키마와의 정합성을 우선합니다.
- 현재 온보딩 분석 파이프라인은 **read-only 모드**로 동작하며 DB 저장 호출은 비활성화되어 있습니다.

## 2) 작업 원칙 (CLAUDE.md 확장)

1. **가정 금지**
   - 요구사항이 애매하면 먼저 질문한다.
   - 가능한 해석이 여러 개면 명시적으로 선택지를 제시한다.
2. **단순성 우선**
   - 요청받지 않은 추상화/확장성/옵션화는 추가하지 않는다.
   - "최소 코드로 정확히 해결"을 기본값으로 한다.
3. **외과적 수정**
   - 요청과 직접 관련된 파일/라인만 변경한다.
   - 내 변경으로 생긴 미사용 코드만 정리한다.
4. **검증 가능한 완료 기준**
   - 변경 전후 동작 차이를 명확히 설명할 수 있어야 한다.
   - 실패 케이스/에러 메시지/응답 포맷이 의도대로 유지되어야 한다.

## 3) 이 프로젝트에서 특히 지킬 규칙

- **응답 봉투 포맷 유지**
  - 기본 형태:  
    `{ "resultType": "SUCCESS|FAIL", "success": ..., "error": ... }`
  - 신규/수정 엔드포인트도 기존 계약을 깨지 않는다.
- **모델/스키마 일관성 유지**
  - `User` ORM 필드명(camelCase 포함)과 기존 DB 스키마 정합성을 우선한다.
- **벡터 처리 규칙 유지**
  - 코사인 유사도 전제(L2 정규화)를 깨는 변경을 임의로 도입하지 않는다.
- **키워드 체계 존중**
  - 키워드 레지스트리는 `app/services/keywords.py`의 고정 TSV 기반이다.
  - 구조 변경은 명시 요청이 있을 때만 수행한다.
- **환경 변수 로딩 규칙 존중**
  - `.env` 탐색은 `fastapi/.env`와 상위 `../.env`를 모두 고려한다.

## 4) 구현 절차 (권장 실행 순서)

1. 요구사항을 한 문장으로 재정의하고 성공 조건을 명확히 한다.
2. 영향 파일을 먼저 찾고, 필요한 코드만 읽는다.
3. 최소 범위로 수정한다.
4. 관련 실행/점검을 통해 변경 영향이 없는지 확인한다.
5. 무엇이 바뀌었는지, 왜 그렇게 했는지 짧고 명확하게 전달한다.

## 5) 로컬 작업 기준 명령어

```bash
# 초기 설정
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 서버 실행 (fastapi 디렉터리에서)
cd fastapi
uvicorn app.main:app --reload
```

- API 문서: `http://localhost:8000/docs`
- 필수 환경 변수: `OPENAI_API_KEY`
- DB 연결: `DATABASE_URL` 우선, 없으면 설정의 `postgres_dsn` 사용

## 6) 금지/주의 사항

- 요청 없는 대규모 리팩터링 금지
- 성공처럼 보이게 하는 침묵 처리(silent fallback) 금지
- 근거 없는 모델 교체/임계값 변경 금지
- 보안 민감 정보(API 키, DSN) 하드코딩 금지

## 7) 완료 정의 (Definition of Done)

- 변경 사항이 요청과 직접 연결된다.
- 기존 API 계약(응답 구조/핵심 필드)을 깨지 않는다.
- 프로젝트 컨텍스트(NestJS 연동, read-only 모드, 벡터/키워드 규칙)와 충돌하지 않는다.

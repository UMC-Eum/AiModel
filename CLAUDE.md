# CLAUDE.md

이 파일은 Claude Code(claude.ai/code)가 이 저장소에서 작업할 때 참고하는 안내 문서입니다.

## 명령어

### 초기 설정

```bash
# 가상환경 생성 및 활성화
python -m venv .venv
source .venv/bin/activate

# 의존성 설치
pip install -r requirements.txt
```

### 서버 실행

```bash
# fastapi/ 디렉터리에서 실행
cd fastapi
uvicorn app.main:app --reload
```

서버는 `http://localhost:8000`에서 시작되며, `/docs`에서 대화형 API 문서를 확인할 수 있습니다.

### 환경 변수

`fastapi/` 디렉터리 또는 저장소 루트에 `.env` 파일을 생성합니다 (두 위치 모두 탐색됨):

```
OPENAI_API_KEY=sk-...
DATABASE_URL=mysql+aiomysql://user:pass@host:3306/dbname
```

`DATABASE_URL`이 설정의 `mysql_dsn`보다 우선 적용됩니다. 둘 다 없으면 앱이 시작되지 않습니다.

## 아키텍처

NestJS 백엔드와 함께 동작하는 FastAPI AI 서비스입니다. NestJS 백엔드가 음성 분석·추천 등 AI 연산이 필요한 작업을 이 서비스에 요청합니다.

### 응답 공통 포맷

모든 엔드포인트는 동일한 응답 봉투를 반환합니다:
```json
{ "resultType": "SUCCESS" | "FAIL", "success": { "data": ... } | null, "error": { "message": "..." } | null }
```

### 핵심 파이프라인: 음성 프로필 분석

`POST /api/v1/onboarding/voice-profile/analyze`

1. 입력: `transcript`(텍스트 직접 입력) 또는 `local_audio_path`(OpenAI `gpt-4o-mini-transcribe`로 STT 처리)
2. `asyncio.gather()`로 병렬 처리:
   - **임베딩**: `text-embedding-3-large` → 1536차원 벡터 → L2 정규화
   - **키워드**: GPT-4o-mini가 고정 380개 키워드 레지스트리(`app/services/keywords.py`) 기반으로 추출 → `{"matched": [{id, keyword, category, score}]}` JSON 반환
3. 출력: `summary`, `vibeVector`(1536 floats), `matchedKeywords`, `vectorId`

현재 **읽기 전용 모드**: 파이프라인이 DB에 쓰지 않습니다. 저장을 복원하려면 `app/services/llm.py`에서 `save_vibe_vector` / `save_user_keywords` 호출을 다시 연결하세요.

### 추천 엔진

`GET /api/v1/recommendation/users?userId=<id>`

MySQL에서 요청 유저의 `vibeVector`를 조회한 뒤, `status=ACTIVE`, `deletedAt IS NULL`, 반대 성별, `vibeVector` 비어있지 않은 후보군을 가져와 코사인 유사도를 계산합니다. `similarityScore >= 0.3`인 상위 20명을 반환합니다.

### 데이터베이스

- SQLAlchemy + `aiomysql` 기반 비동기 MySQL
- ORM 모델: `app/models/user.py` → `User` 테이블 (NestJS 스키마와 일치하는 camelCase 컬럼명)
- 세션 의존성: `app/database.py`의 `get_db()`
- `vibeVector`는 float 배열을 담는 JSON 컬럼으로 저장됨

### 서비스 레이어

| 파일 | 역할 |
|---|---|
| `app/services/llm.py` | 비동기 OpenAI 호출: 임베딩 생성, 키워드 추출, 요약 |
| `app/services/stt.py` | 로컬 오디오 파일을 OpenAI(`gpt-4o-mini-transcribe`)로 STT 처리 (동기) |
| `app/services/keywords.py` | 고정 380개 키워드 레지스트리 + GPT-4o-mini용 `KEYWORD_SYSTEM_PROMPT` |
| `app/services/vibe.py` | 순수 수학 유틸: `normalize_vector`, `score_similarity`(코사인) |
| `app/services/storage.py` | MySQL 헬스체크 + (비활성화된) 쓰기 헬퍼 |

### 주요 설계 결정

- 키워드 레지스트리(`keywords.py`)는 모듈 로드 시 파싱되는 하드코딩 TSV입니다. 변경 시 `RAW_KEYWORDS_TSV`를 직접 수정해야 합니다.
- `app/core/config.py`는 `pydantic-settings`를 사용하며, 서버 시작 시 현재 작업 디렉터리의 `.env`와 상위 디렉터리의 `.env`를 모두 탐색합니다.
- `User` 모델은 NestJS/MySQL 스키마와 정확히 일치시키기 위해 `id`에 `BigInteger`, 타임스탬프에 `DATETIME(fsp=6)`을 사용합니다.

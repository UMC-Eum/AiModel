# FastAPI AI Service

STT 연동, LLM 프롬프트 파이프라인, 키워드 매핑, vibe vector 생성을 담당하는 AI 전용 서비스입니다. 기존 NestJS 백엔드가 소비할 버전드 API를 제공합니다.

## 예정된 엔드포인트
- `POST /api/v1/onboarding/voice-profile/analyze`: `introAudioUrl`의 S3 presigned 오디오 URL을 분석해 요약, 키워드 후보, vibe vector 반환.
- `GET /api/v1/onboarding/matches/recommend`: 커서 페이지네이션 기반 추천, Nest 측 응답 계약에 맞춰 제공.

## 다음 단계
1. 의존성 관리(`poetry`/`pip`)로 FastAPI, Pydantic, AWS HTTP 클라이언트 추가.
2. `app/services/*`에서 STT, LLM, 벡터 연산을 구현.
3. 프롬프트 출력과 전사본 고정 픽스처 기반 테스트 작성.
4. NestJS ↔ FastAPI 간 인증/서명, 시크릿 관리, 레이트 리밋으로 보안 강화.

## 구조
- `app/main.py`: FastAPI 앱 및 라우터 등록.
- `app/api/v1/onboarding.py`: 온보딩 분석 엔드포인트/스키마.
- `app/api/v1/recommendation.py`: 커서 페이지네이션 기반 추천 엔드포인트.
- `app/services/*`: STT, LLM, 키워드, 벡터 헬퍼.
- `app/core/config.py`: 설정 플레이스홀더.

## DB 설정
- PostgreSQL async DSN을 사용합니다.
- 권장 환경 변수: `DATABASE_URL=postgresql+asyncpg://user:password@host:5432/dbname`
- `DATABASE_URL`이 없으면 `POSTGRES_DSN`/`postgres_dsn` 설정을 사용합니다.

## 오디오 입력
- 사용자 voice profile 분석 API는 `introAudioUrl`(S3 presigned GET URL), `birthdate`, `sex`를 입력으로 받습니다.
- `introAudioUrl`을 다운로드해 STT를 수행합니다.
- STT로 생성한 전사 텍스트와 `birthdate`로 계산한 만 나이, `sex`를 함께 사용해 vibe vector를 생성합니다.
- URL 다운로드 제한은 `MAX_AUDIO_DOWNLOAD_MB`, `AUDIO_DOWNLOAD_TIMEOUT_SECONDS`로 조정합니다.

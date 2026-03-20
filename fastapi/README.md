# FastAPI AI Service

STT 연동, LLM 프롬프트 파이프라인, 키워드 매핑, vibe vector 생성을 담당하는 AI 전용 서비스입니다. 기존 NestJS 백엔드가 소비할 버전드 API를 제공합니다.

## 예정된 엔드포인트
- `POST /api/v1/onboarding/voice-profile/analyze`: 전사본/오디오를 분석해 요약, 키워드 후보, vibe vector 반환.
- `GET /api/v1/matches/recommendations`: 추천 목업(실험용), Nest 측 응답 계약에 맞춰 제공.

## 다음 단계
1. 의존성 관리(`poetry`/`pip`)로 FastAPI, Pydantic, AWS HTTP 클라이언트 추가.
2. `app/services/*`에서 STT(AWS), LLM, 벡터 연산을 구현.
3. 프롬프트 출력과 전사본 고정 픽스처 기반 테스트 작성.
4. NestJS ↔ FastAPI 간 인증/서명, 시크릿 관리, 레이트 리밋으로 보안 강화.

## 구조
- `app/main.py`: FastAPI 앱 및 라우터 등록.
- `app/api/v1/onboarding.py`: 온보딩 분석 엔드포인트/스키마.
- `app/api/v1/matches.py`: 추천 엔드포인트 스텁.
- `app/services/*`: STT, LLM, 키워드, 벡터 헬퍼.
- `app/core/config.py`: 설정 플레이스홀더.

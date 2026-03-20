# AiModel

음성 기반 온보딩 분석과 매칭을 위한 FastAPI AI 서비스 스캐폴드입니다.

## 포함된 내용
- STT 기반 온보딩/매칭 전달용 마일스톤 계획.
- FastAPI AI 서비스 골격: STT, 프롬프트 엔지니어링, 키워드 추출, 벡터 연산용 스텁.

## 리포지토리 구조
- docs/milestones.md — 단계별 일정과 체크리스트.
- fastapi/ — AI 서비스 스캐폴드.
	- app/main.py — FastAPI 앱 및 라우터 등록.
	- app/api/v1/onboarding.py — 온보딩 분석 엔드포인트 스텁.
	- app/api/v1/matches.py — 추천 엔드포인트 스텁.
	- app/services/* — STT, LLM, 키워드, 벡터 헬퍼 스텁.
	- app/core/config.py — 설정 플레이스홀더.

## 다음 단계
1. Python 가상환경/poetry 세팅 후 FastAPI 의존성 고정.
2. FastAPI에서 STT+LLM 플로우 구현 및 응답 계약 고정.
3. 기존 NestJS 백엔드와의 연동 방식 확정(요청 서명/인증, 타임아웃, 재시도) 후 호출 어댑터 제공.
4. 테스트, 로깅/트레이싱, 보안(레이트 리밋/서명 검증)을 추가해 안정화.

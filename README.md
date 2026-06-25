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
	- app/api/v1/recommendation.py — 커서 페이지네이션 기반 추천 엔드포인트.
	- app/services/* — STT, LLM, 키워드, 벡터 헬퍼 스텁.
	- app/core/config.py — 설정 플레이스홀더.

## 실행 방법
최초 1회만 가상환경을 만들고 의존성을 설치합니다.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

이후에는 재설치 없이 가상환경의 `uvicorn`으로 바로 실행합니다.

```bash
cd fastapi
../.venv/bin/uvicorn app.main:app --reload
```

서버 상태 확인:

```bash
curl http://127.0.0.1:8000/health
```

- 기본 서버 주소: `http://127.0.0.1:8000`
- FastAPI 앱 엔트리포인트: `fastapi/app/main.py`
- 의존성 재설치는 `requirements.txt`가 변경됐을 때만 실행합니다.
- 앱 시작 시 DB 연결을 확인하므로 `.env`에 `DATABASE_URL=postgresql+asyncpg://user:password@host:5432/dbname` 형식의 값이 필요합니다.

## 다음 단계
1. Python 가상환경/poetry 세팅 후 FastAPI 의존성 고정.
2. FastAPI에서 STT+LLM 플로우 구현 및 응답 계약 고정.
3. 기존 NestJS 백엔드와의 연동 방식 확정(요청 서명/인증, 타임아웃, 재시도) 후 호출 어댑터 제공.
4. 테스트, 로깅/트레이싱, 보안(레이트 리밋/서명 검증)을 추가해 안정화.

## DB
- FastAPI 서비스는 PostgreSQL async 연결을 사용합니다.
- `.env`에는 `DATABASE_URL=postgresql+asyncpg://user:password@host:5432/dbname` 형식으로 설정합니다.

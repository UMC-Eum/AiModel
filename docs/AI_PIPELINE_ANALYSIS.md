# 이음(EUM) AI 파이프라인 아키텍처 분석 문서

> 5060 시니어 데이팅 앱 · AI 음성 분석 & 매칭 시스템
> 분석 기준일: 2026-04-02
> 시각화 파일: `docs/architecture-diagrams.html` (브라우저에서 열기)

---

## 목차

1. [프로젝트 개요](#1-프로젝트-개요)
2. [전체 시스템 아키텍처](#2-전체-시스템-아키텍처)
3. [핵심 파이프라인: 음성 프로필 분석](#3-핵심-파이프라인-음성-프로필-분석)
4. [매칭 추천 엔진](#4-매칭-추천-엔진)
5. [키워드 레지스트리 시스템](#5-키워드-레지스트리-시스템)
6. [벡터 임베딩 & 유사도 수학](#6-벡터-임베딩--유사도-수학)
7. [데이터 모델](#7-데이터-모델)
8. [서비스 레이어 구조](#8-서비스-레이어-구조)
9. [API 명세 요약](#9-api-명세-요약)
10. [현재 구현 상태 & Known Issues](#10-현재-구현-상태--known-issues)
11. [발전 방향성](#11-발전-방향성)

---

## 1. 프로젝트 개요

**이음(EUM)**은 50~60대 시니어를 대상으로 하는 데이팅 앱으로, 음성 기반 프로필을 AI로 분석하여 가치관·성향이 유사한 이성을 매칭해주는 서비스다. 본 레포지토리는 그 AI 서비스 계층(FastAPI)으로, NestJS 메인 백엔드와 독립적으로 운영된다.

### 기술 스택 요약

| 영역 | 기술 |
|------|------|
| Web Framework | FastAPI 0.128.8 |
| ASGI Server | Uvicorn 0.39.0 |
| ORM | SQLAlchemy 2.0 (Async) |
| DB Driver | aiomysql 0.2.0 |
| AI/LLM | OpenAI SDK 2.29.0 |
| Validation | Pydantic 2.12.5 |
| Vector Math | NumPy 2.1.3 |
| Config | pydantic-settings 2.11.0 |

---

## 2. 전체 시스템 아키텍처

```
┌─────────────────────────────────────────────────────────────────┐
│                    클라이언트 레이어                              │
│              📱 앱  ←→  NestJS API Gateway                       │
└──────────────────────────┬──────────────────────────────────────┘
                           │ HTTP
┌──────────────────────────▼──────────────────────────────────────┐
│                   FastAPI AI 서비스                               │
│  ┌──────────┐  ┌───────────────────┐  ┌──────────────────────┐  │
│  │  /health │  │ /onboarding       │  │ /recommendation      │  │
│  │  DB 상태  │  │ 음성 프로필 분석   │  │ 매칭 추천 엔진       │  │
│  └──────────┘  └────────┬──────────┘  └──────────┬───────────┘  │
└───────────────────────┬─┘────────────────────────┼──────────────┘
                        │                          │
         ┌──────────────▼──────┐       ┌───────────▼──────────┐
         │   OpenAI API        │       │   MySQL Database      │
         │ • gpt-4o-mini       │       │ • User (vibeVector)  │
         │ • gpt-4o-mini-      │       │ • user_keywords      │
         │   transcribe        │       └──────────────────────┘
         │ • text-embedding-   │
         │   3-large           │
         └─────────────────────┘
```

### 설계 철학

- **AI-First 프로필**: 텍스트 입력 대신 목소리로 성격을 표현 → 시니어 친화적 UX
- **비동기 병렬 처리**: 임베딩 생성 + 키워드 추출을 `asyncio.gather()`로 동시 실행
- **벡터 기반 매칭**: 키워드 규칙 대신 의미론적 벡터 유사도로 매칭 → 더 자연스러운 연결
- **보수적 배포**: DB 쓰기는 현재 비활성화(read-only mode) → 안전한 테스트 환경

---

## 3. 핵심 파이프라인: 음성 프로필 분석

**엔드포인트:** `POST /api/v1/onboarding/voice-profile/analyze`

### 처리 흐름

```
[사용자 요청]
     │
     ├── transcript 있음? ──────────────────────────┐
     │                                              │
     └── local_audio_path 있음?                     │
              │                                    │
              ▼                                    ▼
    [STT: gpt-4o-mini-transcribe]         [텍스트 직접 사용]
    ⚠️ 동기 처리 (블로킹)                          │
              │                                    │
              └──────────────┬─────────────────────┘
                             │
                    [트랜스크립트 확보]
                             │
               ┌─────────────┼─────────────┐
               │             │             │
               ▼             ▼             ▼
    [임베딩 생성]    [키워드 추출]    [요약 생성]
    text-embedding-  gpt-4o-mini     gpt-4o-mini
    3-large          temp=0.1        temp=0.2
    1536차원         380개 레지스트리  2문장 이내
    L2 정규화        최대 15개 추출
               │             │             │
               └─────────────┼─────────────┘
                             │
                    [응답 반환]
                    • transcript
                    • summary
                    • vibeVector [1536차원]
                    • matchedKeywords
                             │
                    (선택: DB 저장 ← 현재 비활성)
```

### 주요 LLM 호출 설정

| 단계 | 모델 | Temperature | Max Tokens | 비고 |
|------|------|-------------|------------|------|
| STT | gpt-4o-mini-transcribe | - | - | 동기 처리 |
| 임베딩 | text-embedding-3-large | - | - | 1536차원 |
| 키워드 추출 | gpt-4o-mini | 0.1 | 600 | JSON 강제 출력 |
| 요약 | gpt-4o-mini | 0.2 | - | 2문장 제한 |

### 응답 포맷 (표준 Envelope)

```json
{
  "resultType": "SUCCESS",
  "success": {
    "data": {
      "transcript": "저는 아침에 일찍 일어나서 산책을 즐겨요...",
      "summary": "아침형 인간으로 규칙적인 생활을 즐기며 자연과 교감을 중요시합니다.",
      "vectorId": "42",
      "matchedKeywords": [
        {"id": 1, "keyword": "아침형", "category": "생활·일상", "score": 0.95},
        {"id": 7, "keyword": "규칙적", "category": "생활·일상", "score": 0.88}
      ],
      "vibeVector": [0.025076, -0.014549, 0.067823, ...]
    }
  },
  "error": null,
  "meta": {
    "timestamp": "2026-04-02T09:00:00Z",
    "path": "/api/v1/onboarding/voice-profile/analyze"
  }
}
```

---

## 4. 매칭 추천 엔진

**엔드포인트:** `GET /api/v1/recommendation/users?userId=<id>`

### 알고리즘 흐름

```
1. 요청자(userId) 로드
   └── vibeVector, sex 추출

2. 후보군 DB 쿼리
   SELECT * FROM User WHERE
     status = 'ACTIVE'
     AND deletedAt IS NULL
     AND id ≠ userId
     AND sex ≠ requester.sex       ← 이성만
     AND vibeVector IS NOT NULL

3. 각 후보자에 대해 코사인 유사도 계산
   similarity = A · B              ← L2 정규화된 벡터이므로 내적 = 코사인 유사도

4. 필터링: score < 0.3 제외

5. 내림차순 정렬 → 상위 20명 반환
```

### 유사도 임계값 해석

| 점수 범위 | 의미 |
|-----------|------|
| 0.8 ~ 1.0 | 매우 유사한 성향/가치관 |
| 0.6 ~ 0.8 | 유사한 라이프스타일 |
| 0.3 ~ 0.6 | 어느 정도 공통점 있음 |
| 0.0 ~ 0.3 | 성향 차이 큼 → **제외** |

---

## 5. 키워드 레지스트리 시스템

총 **380개 키워드**가 5개 카테고리로 분류되어 소스코드(`keywords.py`)에 TSV 형태로 내장되어 있다.

### 카테고리 분포

```
성향·기질     ████████████████████ 102개  (26.8%)
가치관·태도   ████████████████     81개  (21.3%)
취미·관심사   ███████████████      77개  (20.3%)
생활·일상     ██████████████       73개  (19.2%)
소통·관계     █████████            47개  (12.4%)
```

### 카테고리별 예시 키워드

| 카테고리 | 예시 키워드 |
|---------|------------|
| 성향·기질 | 차분함, 활발함, 신중함, 열정적, 낙천적, 섬세함 |
| 가치관·태도 | 가족중심, 워라밸, 환경의식, 성장지향, 안정추구 |
| 생활·일상 | 아침형, 운동루틴, 규칙적, 미식탐방, 집순이/돌이 |
| 취미·관심사 | 📚독서, 🎬영화감상, ✈️여행, 🎮게임, 🎵음악감상 |
| 소통·관계 | 경청중심, 공감형, 갈등조율, 솔직함, 배려심 |

### 키워드 추출 프롬프트 설계

- GPT-4o-mini에게 380개 키워드 목록을 시스템 프롬프트로 제공
- 트랜스크립트에서 **3~15개** 키워드 추출 강제
- 각 키워드에 **관련도 점수 (0.0~1.0)** 부여
- temperature=0.1로 결정론적 출력 유도
- JSON 형식 강제 (`{"matched": [...]}`)

---

## 6. 벡터 임베딩 & 유사도 수학

### 임베딩 생성

```
트랜스크립트(텍스트)
       │
       ▼
text-embedding-3-large
       │
       ▼
원시 벡터 v ∈ ℝ¹⁵³⁶
       │
       ▼
L2 정규화: v' = v / ‖v‖
       │
       ▼
정규화된 벡터 v' ∈ ℝ¹⁵³⁶  (‖v'‖ = 1)
```

### 코사인 유사도 계산

```
similarity(A, B) = (A · B) / (‖A‖ × ‖B‖)

L2 정규화 후: ‖A‖ = ‖B‖ = 1

∴ similarity(A, B) = A · B = Σᵢ(aᵢ × bᵢ)
```

정규화를 미리 해두면 **저장 시 추가 연산 없이** 내적만으로 유사도를 계산할 수 있어 추천 엔진 속도가 향상된다.

### 벡터 저장 방식

- **DB 컬럼:** `User.vibeVector` (MySQL JSON 타입)
- **직렬화:** `[0.025076, -0.014549, ...]` (배열 형태)
- **크기:** 약 12KB/유저
- **인덱스:** 현재 없음 (→ 전체 스캔, 개선 필요)

---

## 7. 데이터 모델

### User 테이블

```
User
├── id              BigInt PK (auto-increment)
├── email           String(255)
├── nickname        String(20)
├── code            String(10)
├── birthdate       DateTime
├── age             Integer (default=50)
├── sex             Enum(M | F)
├── introText       String(255)
├── introVoiceUrl   String(512)       ← 자기소개 음성 URL
├── idealVoiceUrl   String(512)?      ← 이상형 음성 URL
├── profileImageUrl String(512)
├── vibeVector      JSON              ← AI 분석 결과 [1536차원]
├── status          Enum(ACTIVE | INACTIVE)
├── provider        Enum(KAKAO)?
├── providerUserId  String(64)?
├── createdAt       DateTime
├── updatedAt       DateTime
└── deletedAt       DateTime?         ← Soft delete
```

### user_keywords 테이블

```
user_keywords
├── id          BigInt PK
├── userId      BigInt FK → User.id
├── vectorId    String    ← user_id의 문자열 표현
├── keywordId   Integer   ← keywords.py의 id
├── keyword     String    ← 키워드 텍스트
├── category    String    ← 카테고리명
└── score       Float     ← 관련도 점수 (0~1)
```

---

## 8. 서비스 레이어 구조

```
fastapi/app/
├── main.py              ← FastAPI 앱 초기화, 라우터 등록, DB 헬스체크
├── database.py          ← AsyncSessionLocal (aiomysql)
├── core/
│   └── config.py        ← Pydantic Settings (환경변수 로드)
├── models/
│   └── user.py          ← SQLAlchemy ORM User 모델
├── api/v1/
│   ├── health.py        ← GET /health, GET /api/v1/health/db
│   ├── onboarding.py    ← POST /api/v1/onboarding/voice-profile/analyze
│   ├── recommendation.py← GET /api/v1/recommendation/users
│   └── matches.py       ← GET /api/v1/matches/recommendations (Mock)
└── services/
    ├── llm.py           ← OpenAI 통합 (임베딩, 키워드, 요약)
    ├── stt.py           ← STT 트랜스크립션
    ├── keywords.py      ← 380개 키워드 레지스트리 + 시스템 프롬프트
    ├── vibe.py          ← normalize_vector(), score_similarity()
    └── storage.py       ← MySQL/HTTP 영속성 (현재 비활성)
```

### 서비스 간 의존성

```
onboarding.py
    ├── llm.py
    │     ├── keywords.py  (KEYWORD_SYSTEM_PROMPT)
    │     ├── vibe.py      (normalize_vector)
    │     └── OpenAI API
    └── stt.py
          └── OpenAI API

recommendation.py
    ├── database.py       (AsyncSession)
    └── vibe.py           (score_similarity)

health.py
    └── storage.py        (check_mysql_health)
```

---

## 9. API 명세 요약

| Method | Path | 설명 | 상태 |
|--------|------|------|------|
| GET | `/health` | 기본 헬스체크 | ✅ 운영중 |
| GET | `/api/v1/health/db` | MySQL 연결 확인 | ✅ 운영중 |
| POST | `/api/v1/onboarding/voice-profile/analyze` | 음성→임베딩+키워드+요약 | ✅ 운영중 |
| GET | `/api/v1/recommendation/users?userId=` | 코사인 유사도 기반 추천 | ✅ 운영중 |
| GET | `/api/v1/matches/recommendations` | Mock 추천 (스텁) | ⚙️ 개발중 |

---

## 10. 현재 구현 상태 & Known Issues

### ✅ 완료된 기능
- OpenAI 비동기 API 연동 (임베딩, 키워드, 요약)
- 코사인 유사도 기반 추천 엔진
- 380개 키워드 레지스트리 및 프롬프트 설계
- L2 정규화 벡터 연산
- 표준 응답 Envelope 구조

### ⚠️ 현재 제한사항

| 이슈 | 위치 | 설명 |
|------|------|------|
| DB 쓰기 비활성화 | `llm.py` | `save_vibe_vector()`, `save_user_keywords()` 주석처리됨 |
| STT 동기 처리 | `stt.py` | `transcribe_local_audio()` 가 blocking → 응답 지연 |
| 벡터 인덱스 없음 | MySQL | 전체 테이블 스캔으로 유사도 계산 → 사용자 증가 시 성능 저하 |
| 나이 필터 없음 | `recommendation.py` | 성별 필터만 있고 나이 범위 필터 미구현 |
| idealVoiceUrl 미사용 | `user.py` | 이상형 음성 분석 파이프라인 미구현 |

---

## 11. 발전 방향성

### Phase A. 단기 (1~2주): 안정화

#### A-1. DB 쓰기 활성화
```python
# llm.py의 주석 해제
await save_vibe_vector(vector, user_id)
await save_user_keywords(vector_id, user_id, keywords)
```
현재 분석 기능은 완성되어 있으나 결과가 DB에 저장되지 않음. 즉시 활성화 가능.

#### A-2. STT 비동기 전환
```python
# 현재 (동기/블로킹)
def transcribe_local_audio(file_path: str) -> dict

# 개선 (비동기)
async def transcribe_local_audio(file_path: str) -> dict
    # asyncio.to_thread() 또는 AsyncOpenAI 사용
```
동기 처리는 FastAPI의 이벤트 루프를 블로킹하여 동시 요청 처리 성능을 저하시킴.

#### A-3. 나이/지역 필터 추가
```python
# 추천 쿼리에 추가
.where(User.age.between(requester.age - 10, requester.age + 10))
.where(User.region == requester.region)  # 지역 컬럼 추가 필요
```

---

### Phase B. 중기 (1~2개월): 매칭 고도화

#### B-1. 이상형 음성 분석 파이프라인
현재 `idealVoiceUrl`이 DB에 존재하지만 분석 파이프라인이 없음.

```
이상형 음성 → STT → 이상형 임베딩 (idealVector)
                    ↓
         매칭 시 자기소개 벡터(vibeVector)와 이상형 벡터(idealVector) 복합 점수 계산

hybrid_score = α × cosine(A.vibeVector, B.vibeVector)   # 성향 유사도
             + β × cosine(A.idealVector, B.vibeVector)   # A의 이상형 ↔ B의 실제
             + γ × cosine(B.idealVector, A.vibeVector)   # B의 이상형 ↔ A의 실제
```

#### B-2. 키워드 기반 부스팅
벡터 유사도에 공유 키워드 가중치를 더해 해석 가능성(explainability) 확보.

```python
keyword_boost = len(shared_keywords) * 0.02
final_score = cosine_similarity + keyword_boost
```
"취미·관심사가 일치해서 추천됐어요" 같은 설명도 가능해짐.

#### B-3. ANN(근사 최근접 이웃) 도입
사용자가 1만 명 이상 되면 전체 스캔이 병목. 벡터 DB 도입 권장.

| 옵션 | 특징 | 비용 |
|------|------|------|
| **pgvector** | PostgreSQL 확장, 마이그레이션 최소화 | 낮음 |
| **Pinecone** | 완전 관리형 서비스, 빠른 도입 | 중간 |
| **Weaviate** | 오픈소스, 키워드+벡터 하이브리드 검색 | 낮음 |
| **Qdrant** | 고성능 Rust 기반, 필터링 강력 | 낮음 |

MySQL JSON 컬럼 기반 전체 스캔은 ~1,000명 이하에서만 실용적.

---

### Phase C. 중장기 (2~4개월): 개인화 & 피드백 루프

#### C-1. 매칭 결과 피드백 수집
좋아요/싫어요 반응을 수집하여 매칭 품질 측정 지표 확보.

```
User A → "좋아요" → User B
             ↓
     [Feedback 테이블 저장]
             ↓
  매칭 품질 메트릭 계산:
  • 상호 좋아요율 (mutual_like_rate)
  • 대화 전환율 (chat_conversion_rate)
  • 임계값(0.3)의 적절성 검증
```

#### C-2. 키워드 레지스트리 동적화
현재 380개 키워드가 소스코드에 하드코딩되어 있어 변경 시 배포 필요.

```
현재: keywords.py (하드코딩)
개선: DB 테이블(keywords) ← 관리자 페이지에서 동적 관리
     └── 시니어 트렌드 반영한 키워드 추가/수정/삭제
         (예: 손주육아, 황혼재혼, 건강관리, 종교활동 등)
```

#### C-3. 다중 음성 분석 (재녹음 평균화)
단일 녹음의 노이즈를 줄이기 위해 여러 번 녹음 후 벡터 평균화.

```python
# 3번 녹음 후 벡터 평균
vectors = [v1, v2, v3]
avg_vector = normalize(sum(vectors) / len(vectors))
```

---

### Phase D. 장기 (4개월+): 프리미엄 기능

#### D-1. 대화 스타일 분석
매칭 후 채팅 메시지 패턴을 분석하여 "대화 궁합" 점수 추가.
- 메시지 길이·응답 속도·이모지 사용 패턴 등
- 실제 대화 만족도와의 상관관계 분석

#### D-2. 음성 감정 분석
STT 텍스트 외에 음성 톤·속도·억양에서 감성 정보 추출.
- OpenAI Audio API 또는 별도 감정 분석 모델 활용
- "따뜻한 목소리" 등 비언어적 요소 반영

#### D-3. 계절·상황 맞춤 추천
봄 나들이 시즌 → 야외 활동 키워드 가중치 상향 등 컨텍스트 인식 추천.

#### D-4. 안전성 강화 (시니어 특화)
- 보이스피싱/사기 패턴 감지 (이상한 금전 언급 등)
- 욕설·성희롱 필터링
- 가입 시 신분증 인증과 연동된 실명 매칭

---

### 우선순위 로드맵 요약

```
즉시 (이번 주)
├── DB 쓰기 활성화 (주석 2줄 해제)
└── STT 비동기 전환

단기 (이번 달)
├── 나이/지역 필터
├── 응답 시간 모니터링 (CloudWatch / Datadog)
└── 에러 로그 구조화 (JSON 형식)

중기 (다음 분기)
├── 이상형 음성 분석 파이프라인
├── ANN 벡터 DB 도입 검토
└── 키워드 부스팅 + 추천 이유 설명

장기 (6개월 이후)
├── 피드백 루프 → 모델 파인튜닝
├── 대화 스타일 분석
└── 시니어 특화 안전망
```

---

*문서 작성: Claude Sonnet 4.6 · 2026-04-02*
*시각화: `docs/architecture-diagrams.html` 참조*

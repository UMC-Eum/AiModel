# AI Voice Matching 마일스톤

## Phase 0: 범위·계약 정리 (Week 0)
- 기존 NestJS 백엔드와 FastAPI 간 응답 envelope, 에러 코드, 인증/서명 방식을 확정.
- `v1/onboarding/voice-profile/analyze`, `v1/matches/recommendations` 요청/응답 스키마와 페이지네이션 규칙 고정.
- STT 제공자(AWS Transcribe/Bedrock 등)와 오디오 제약(포맷, 길이, 샘플레이트) 확정.

## Phase 1: AI 파이프라인 프로토타입 (Week 1)
- FastAPI 뼈대(헬스체크, 버전 라우팅) 준비.
- STT 플로우: S3 URL/프리사인 URL 입력 → 오디오 fetch → STT 호출 → 전사본 확보.
- LLM 프롬프트 설계: 요약, 키워드 추출(고정 500 키워드 매핑), vibe vector 생성; 평가 메모 남기기.
- 오프라인 반복 테스트용 전사본 픽스처 추가.

## Phase 2: 데이터/저장소 준비 (Week 1-2)
- 기존 MySQL 스키마에서 `User.vibeVector`, 키워드, 프로필 속성 매핑과 매칭용 인덱스 점검.
- 키워드/벡터 샘플 데이터 시드 생성해 추천 알고리즘 평가 준비.

## Phase 3: 서비스 연동 (Week 2-3)
- FastAPI에서 분석/추천 목업 응답을 계약에 맞게 제공.
- NestJS 백엔드가 FastAPI를 호출할 수 있도록 HTTP 클라이언트/요청 서명 규약 정의 및 어댑터 제공.
- 응답 정규화 후 전사본/요약/키워드/vibeVector를 User에 저장하는 흐름 합의.

## Phase 4: 매칭 엔진 (Week 3)
- vibe vector 유사도(cosine/Euclidean)와 키워드 가중치 결합 방식 정의.
- 추천 서비스: 페이지네이션(`nextCursor`), 제외 규칙(차단, 본인, 삭제)을 반영한 추천 목록 생성.
- 알고리즘 변형/실험용 플래그와 A/B 버킷 설계.

## Phase 5: 품질·관측·보안 (Week 3-4)
- 구조적 로깅/트레이싱/메트릭: STT, LLM, 벡터 DB/ MySQL 경로별 지연 측정.
- 입력 검증, 레이트 리밋, NestJS↔FastAPI 요청 서명/인증 추가.
- 단위/계약 테스트와 프롬프트 골든 테스트 작성.

## Phase 6: 하드닝·출시 (Week 4)
- 실제 길이·동시성으로 STT+LLM 부하 테스트.
- 기존 사용자에 대한 vibe vector 백필, 오프라인 매칭 평가 및 가중치 튜닝.
- 런북(알람, 온콜, 롤백)과 스테이징→프로드 전환 체크리스트 작성.

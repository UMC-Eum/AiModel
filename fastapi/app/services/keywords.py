"""고정 키워드 레지스트리.

- RAW_PERSONALITY_CSV: PERSONALITY 키워드 원본 데이터 fallback.
- RAW_INTEREST_CSV: INTEREST 키워드 원본 데이터 fallback.
- KEYWORDS: KeywordEntry 리스트.
- KEYWORD_INDEX: (카테고리, 키워드) -> 벡터 인덱스 매핑.
- keywords_by_category(): 카테고리별 그룹핑 반환.
"""

from __future__ import annotations

import re
import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

PERSONALITY_CATEGORY = "PERSONALITY"
INTEREST_CATEGORY = "INTEREST"
CATEGORIES = [PERSONALITY_CATEGORY, INTEREST_CATEGORY]

RAW_PERSONALITY_CSV = """1,차분함
2,활발함
3,신중함
4,즉흥성
5,계획성
6,내향성
7,외향성
8,감성적
9,이성적
10,낙천적
11,현실적
12,대담함
13,소극적
14,유연함
15,고집있음
16,온화함
17,냉철함
18,낯가림
19,친화력
20,독립적
21,의존적
22,집중형
23,분산형
24,인내심
25,추진력
26,안정적
27,모험적
28,침착함
29,열정적
30,조용함
31,표현적
32,관찰형
33,주도형
34,반응형
35,민감함
36,둔감함
37,단순함
38,복합적
39,즉답형
40,숙고형
41,완벽주의
42,대충주의
43,감정기복
44,일관성
45,호기심
46,보수성
47,개방성
48,결단력
49,우유부단
50,끈기
51,회복탄력성
52,자기통제
53,몰입력
54,산만함
55,집요함
56,낙관주의
57,비관주의
58,차가움
59,따뜻함
60,솔직담백
61,신중발언
62,에너지넘침
63,에너지절약
64,조심성
65,대범함
66,예민함
67,무던함
68,침묵형
69,수다형
70,관대함
71,엄격함
72,정서안정
73,정서민감
74,즉각반응
75,지연반응
76,자기주도
77,의견수용
78,비판적
79,수용적
80,분석적
81,직관적
82,논리중심
83,감정중심
84,집중지속
85,전환빠름
86,자기객관화
87,자기확신
88,가족중심
89,개인중심
90,자기계발
91,워라밸
92,안정추구
93,성장지향
94,경험중시
95,의미중시
96,결과중심
97,과정중심
98,전통중시
99,변화수용
100,도전정신
101,실용주의
102,이상주의
103,책임감
104,자율성
105,성실함
106,신뢰중요
107,약속중시
108,꾸준함
109,효율중시
110,여유지향
111,몰입지향
112,균형중시
113,미래지향
114,현재중시
115,장기시야
116,단기집중
117,자기성찰
118,타인존중
119,공정의식
120,윤리중시
121,현실타협
122,원칙중시
123,개방적사고
124,보수적사고
125,자아실현
126,소확행
127,만족지향
128,자기표현
129,자기보호
130,성취욕구
131,안전의식
132,리스크감수
133,책임회피
134,성장욕
135,안정욕
136,경쟁지향
137,협력지향
138,자기효능감
139,공동체의식
140,사회적책임
141,환경의식
142,지속가능성
143,평등중시
144,공감중시
145,존중중시
146,자기존중
147,타인배려
148,실패수용
149,도전수용
150,학습지향
151,배움욕구
152,정체회피
153,변화추구
154,만족추구
155,행복중시
156,의미추구
157,효과중시
158,속도중시
159,완성도중시
160,타협중시
161,원칙우선
162,유연대응
163,책임수행
164,역할중시
165,자율결정
166,타인의견존중
167,자기판단중시
168,신중한선택
169,아침형
170,저녁형
171,규칙적
172,불규칙적
173,바쁜일상
174,여유있는일상
175,집중생활
176,활동중심
177,집순이
178,외출선호
179,혼자시간중시
180,함께시간중시
181,정리정돈형
182,자유분방형
183,미니멀
184,소유중시
185,자연친화
186,도시취향
187,반려동물
188,반려식물
189,산책습관
190,운동루틴
191,카페생활
192,집밥위주
193,외식위주
194,느린페이스
195,빠른페이스
196,계획소비
197,즉흥소비
198,절약형
199,소비형
200,취미몰입
201,휴식중시
202,일중심
203,삶중심
204,주말외출
205,주말휴식
206,혼밥익숙
207,공유생활
208,독립생활
209,야행성
210,조기기상
211,일정관리
212,시간여유
213,시간부족
214,멀티태스킹
215,단일집중
216,정돈습관
217,청결중시
218,위생중시
219,건강관리
220,수면중시
221,야식빈도
222,카페인선호
223,무카페인
224,운동선호
225,비운동
226,스트레칭
227,홈트
228,야외활동
229,실내활동
230,일기작성
231,기록습관
232,플래너사용
233,즉흥계획
234,계획변경
235,혼행
236,동행선호
237,장거리이동
238,근거리선호
239,대중교통
240,자차이용
241,대화중시
242,경청중심
243,말수적음
244,말수많음
245,질문형
246,설명형
247,공감형
248,해결형
249,조언형
250,반응중심
251,리액션풍부
252,진지대화
253,가벼운대화
254,유머사용
255,직설표현
256,완곡표현
257,솔직함
258,신중한표현
259,연락자주
260,연락자유
261,꾸준한연락
262,필요시연락
263,갈등회피
264,갈등조율
265,배려표현
266,감정공유
267,감정절제
268,신뢰중시
269,속도맞춤
270,주도대화
271,흐름대화
272,깊은관계선호
273,가벼운관계
274,장기관계
275,천천히친해짐
276,빠른친밀감
277,안정적관계
278,자유로운관계
279,관계유지
280,의사표현
281,의견조율
282,피드백수용
283,피드백제공
284,논쟁회피
285,건설적토론
286,경계존중
287,거리유지
288,친밀지향
289,독립존중
290,의존회피
291,비언어소통
292,표정풍부
293,톤안정
294,톤활기
295,공감반응
296,요약반응
297,질문확장
298,경청유지
299,신뢰형성
300,관계관리
301,갈등관리
302,감정케어
303,카페탐방
304,SNS활발
305,함께시간선호"""

RAW_INTEREST_CSV = """1,독서
2,글쓰기
3,영화감상
4,드라마시청
5,음악감상
6,공연관람
7,전시관람
8,사진촬영
9,영상편집
10,그림그리기
11,악기연주
12,노래부르기
13,요리
14,베이킹
15,커피
16,와인
17,운동
18,요가
19,필라테스
20,헬스
21,러닝
22,등산
23,여행
24,캠핑
25,드라이브
26,게임
27,보드게임
28,퍼즐
29,공예
30,DIY
31,식물키우기
32,반려동물케어
33,공부취미
34,외국어
35,재테크
36,콘텐츠제작
37,SNS
38,봉사활동
39,전통문화
40,신기술
41,IT트렌드
42,AI관심
43,UX관심
44,디자인
45,기획
46,마케팅
47,데이터
48,통계
49,사진편집
50,영상촬영
51,브이로그
52,블로그
53,글쓰기연습
54,악기감상
55,클래식
56,재즈
57,힙합
58,팝
59,인디음악
60,전시
61,문화탐방
62,역사탐방
63,미술사
64,문학
65,철학
66,심리학
67,경제
68,과학
69,환경
70,정치
71,사회이슈
72,언어학
73,교육
74,멘토링
75,튜터링
76,강의시청
77,온라인강의"""


@dataclass(frozen=True)
class KeywordEntry:
    id: int
    category: str
    text: str
    normalized_ws: str  # 공백 제거
    normalized_plain: str  # 공백 + 기호/이모지 제거


def _normalize_ws(text: str) -> str:
    return re.sub(r"\s+", "", text.lower())


def _normalize_plain(text: str) -> str:
    # 한글/영문/숫자만 남기고 나머지 제거 (이모지/기호 제거)
    return re.sub(r"[^0-9a-zA-Zㄱ-ㅎ가-힣]+", "", text.lower())


def _read_keyword_csv(filename: str, fallback: str) -> str:
    current = Path(__file__).resolve()
    candidates = [Path.cwd() / filename, *(parent / filename for parent in current.parents)]
    for path in candidates:
        if path.is_file():
            return path.read_text(encoding="utf-8-sig")
    return fallback


def _parse_category_csv(raw: str, category: str, id_offset: int = 0) -> List[KeywordEntry]:
    entries: List[KeywordEntry] = []
    seen: set[Tuple[str, str]] = set()
    for row in csv.reader(raw.splitlines()):
        if not row:
            continue
        raw_id = row[0].strip()
        text = row[1].strip() if len(row) > 1 else raw_id
        text = text.strip()
        if not text:
            continue
        try:
            keyword_id = int(raw_id) + id_offset
        except ValueError:
            keyword_id = len(entries) + 1 + id_offset
        key = (category, text)
        if key in seen:
            continue
        seen.add(key)
        entries.append(
            KeywordEntry(
                id=keyword_id,
                category=category,
                text=text,
                normalized_ws=_normalize_ws(text),
                normalized_plain=_normalize_plain(text),
            )
        )
    return entries


def _build_keywords() -> List[KeywordEntry]:
    personality = _parse_category_csv(
        _read_keyword_csv("personality.csv", RAW_PERSONALITY_CSV),
        PERSONALITY_CATEGORY,
    )
    interest_id_offset = max((entry.id for entry in personality), default=0)
    interest = _parse_category_csv(
        _read_keyword_csv("interest.csv", RAW_INTEREST_CSV),
        INTEREST_CATEGORY,
        interest_id_offset,
    )
    return [
        *personality,
        *interest,
    ]


KEYWORDS: List[KeywordEntry] = _build_keywords()
KEYWORD_INDEX: Dict[Tuple[str, str], int] = {
    (k.category, k.text): idx for idx, k in enumerate(KEYWORDS)
}


def keywords_by_category() -> Dict[str, List[KeywordEntry]]:
    grouped: Dict[str, List[KeywordEntry]] = {}
    for entry in KEYWORDS:
        grouped.setdefault(entry.category, []).append(entry)
    return grouped


def _format_keyword_section(category: str) -> str:
    entries = [entry for entry in KEYWORDS if entry.category == category]
    items = ", ".join(
        f"{entry.id}:{entry.text}" for entry in entries
    )
    return f"## {category}\n{items}"


def _build_keyword_system_prompt() -> str:
    personality_count = len(keywords_by_category().get(PERSONALITY_CATEGORY, []))
    interest_count = len(keywords_by_category().get(INTEREST_CATEGORY, []))
    total_count = len(KEYWORDS)
    return f"""당신은 시니어 데이팅 앱의 사용자 음성 전사문을 분석하는 전문가입니다.
아래 키워드 목록은 두 부류로 분류된 {total_count}개의 키워드입니다.
- PERSONALITY: 인성/성향 키워드 {personality_count}개
- INTEREST: 관심사 키워드 {interest_count}개
사용자의 전사문을 읽고, 이 목록에서 실제로 관련 있는 키워드만 골라주세요.

[키워드 목록]
{_format_keyword_section(PERSONALITY_CATEGORY)}

{_format_keyword_section(INTEREST_CATEGORY)}
[키워드 목록 끝]

출력 규칙:
- 반드시 JSON 형식만 반환하세요. 설명, 마크다운, 코드블록 없이 순수 JSON만 반환합니다.
- 전사문에서 명확하게 유추되는 키워드만 포함하세요. 억측하지 마세요.
- 관련도(score)는 0.0~1.0 사이 소수점 한 자리로 표현하세요.
- 최소 3개, 최대 15개를 반환하세요.
- category는 반드시 PERSONALITY 또는 INTEREST 중 하나만 사용하세요.
- id는 위 키워드 목록에 표시된 번호를 그대로 사용하세요.
- 아래 형식을 정확히 따르세요:
{{"matched": [{{"id": 1, "keyword": "차분함", "category": "PERSONALITY", "score": 0.9}}]}}
"""


# 키워드 추출용 시스템 프롬프트는 서버 시작 시 1회 로드해 전역으로 유지한다.
KEYWORD_SYSTEM_PROMPT = _build_keyword_system_prompt()

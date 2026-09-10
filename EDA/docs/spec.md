# 자연어 향수 추천 시스템 설계

| | |
|---|---|
| 대상 요구사항 | **NLR-01** 자연어 추천 입력 (P1), **NLR-07** 추천 이유 제공 (P1) |
| 작성일 | 2026-09-10 |
| 상태 | 초안 — 아래 "선행 작업" 완료 전에는 성능 목표를 확정하지 않는다 |
| 근거 | 요구사항 정의서(최종), ERD v1.1, EDA 01~24 |

---

## 0. 이 문서의 범위

### 다루는 것

사용자가 한국어 문장으로 원하는 향을 설명하면 향수 3~5개와 각각의 추천 이유를 돌려주는 기능의 구조, 처리 흐름, 정책.

### 다루지 않는 것

- REC-12 개인화 추천, REC-13 신규 사용자 추천 — 별도 문서
- MAP-09 추천 결과 지도 표시 — 인터페이스만 언급하고 상세는 향 지도 문서
- API 엔드포인트 상세 명세, 프론트엔드 화면 설계
- 향 지도 좌표 생성 (MAP 폴더에서 별도 진행 중)

### 확정된 설계 결정

| 항목 | 결정 |
|---|---|
| 검색 대상 | Fragrantica 전체 **131,930개** |
| 파이프라인 | **2단 구조** — 조건 구조화와 향 변환을 분리 |
| 추천 이유 | 규칙이 근거를 계산하고 LLM이 문장으로 바꿈 |
| 결과 수 부족 시 | 조건을 단계적으로 완화해 **항상 3~5개** 채움 |
| 인증 | **비회원 허용** (호출량 제한 필요) |
| 실행 위치 | **하이브리드** — 검색은 Spring+PostgreSQL, LLM·언어처리는 Python |
| Domain Lexicon | **CSV 파일**, 서버 기동 시 메모리 적재 |
| ERD | 현재 ERD를 바꾸지 않고 설계. 미스매치는 §6에 제약으로 기록 |
| 응답 시간 | **미정** — §7의 측정 후 결정 |

---

## 1. 무엇을 만드는가

사용자는 향수 이름도, `woody` 같은 데이터 용어도 모른 채 자기 말로 원하는 향을 씁니다.

> "여름에 쓸 건데 포근하고 깨끗한 느낌이면 좋겠어. 머스크는 빼줘."

시스템은 이 문장을 데이터가 이해하는 조건으로 바꾸고, 13만 개 중에서 3~5개를 골라, 각 향수가 **어느 조건에 어떻게 맞았는지**를 함께 보여줍니다.

핵심 난점은 **"포근한"과 "깨끗한"이 Fragrantica 데이터에 없는 말**이라는 것입니다. 데이터에 있는 건 `powdery`, `soapy`, `aquatic` 같은 92개의 accord와 note 목록뿐입니다. 이 간극을 메우는 것이 이 시스템의 실질적 과제입니다.

---

## 2. 전체 구조

```
                    ┌──────────────────────────────────────┐
   [Frontend]       │            Spring Boot               │
       │            │                                      │
       └──POST──────▶  ① 입력 검증 · 호출량 제한            │
                    │                                      │
                    │  ②─────HTTP────▶ [Python 추천 서버]   │
                    │      조건 구조화 + 향 변환             │
                    │  ◀────────────── 조건 + accord 후보   │
                    │                                      │
                    │  ③ SQL 검색 · 점수 · 조건 완화         │
                    │      │                               │
                    │      ▼                               │
                    │  [PostgreSQL]                        │
                    │                                      │
                    │  ④ 추천 근거 계산 (규칙)               │
                    │                                      │
                    │  ⑤─────HTTP────▶ [Python 추천 서버]   │
                    │      근거 → 자연어 문장               │
                    │  ◀────────────── 추천 이유 텍스트      │
       ┌────응답─────  ⑥ 결과 조립                          │
       ▼            └──────────────────────────────────────┘
   [Frontend]
```

### 왜 이 구조인가

이 기능이 하는 일은 성격이 둘로 갈립니다.

**언어를 다루는 일** — LLM 호출, 한국어 형태소 분석("우디한" → "우디"), 렉시콘 조회.
한국어 형태소 분석은 Python 생태계가 압도적으로 낫습니다. `kiwipiepy`는 설치가 한 줄이고 불규칙 활용을 처리합니다. Java에는 동급 선택지가 없습니다.

**데이터를 다루는 일** — 13만 개 향수를 accord로 거르고, 점수 매기고, 정렬.
이건 SQL이 잘하는 일입니다. Python으로 끌어와 pandas로 거르면 메모리와 시간이 낭비됩니다.

그래서 둘을 나눕니다. 대신 **Python 서버는 데이터베이스에 접근하지 않습니다.** 문자열을 받아 조건과 accord 후보를 돌려주는, 거의 순수 함수에 가까운 서버입니다.

이 제약이 중요한 이유는, 두 서버가 같은 DB 스키마를 알고 있으면 DB 담당자가 컬럼 하나를 바꿀 때 양쪽을 고쳐야 하기 때문입니다. 6인 팀에서 이런 종류의 결합은 사고를 만듭니다. Python이 DB를 모르면 그 위험이 사라지고, 입력→출력만 보면 되니 테스트와 실험도 쉬워집니다.

**대가**: 서버가 2개가 되고, Spring↔Python 왕복이 2번 생깁니다. 왕복 자체는 수십 ms 수준이라 §7의 LLM 지연에 비하면 작습니다.

---

## 3. 처리 흐름

예시 입력을 끝까지 따라가겠습니다.

> **"여름에 쓸 건데 포근하고 깨끗한 느낌이면 좋겠어. 머스크는 빼줘."**

### ① 입력 검증 · 호출량 제한 (Spring)

- 길이 제한 (제안: 500자). 초과 시 거절
- 비회원은 세션 기준, 회원은 user_id 기준으로 호출량 제한
- 빈 문자열, 공백만 있는 입력 거절

호출량 제한이 필요한 이유는 비회원을 허용하기 때문입니다. LLM 호출이 요청당 3회이므로 무제한으로 열어두면 비용이 통제되지 않습니다. 구체적 수치는 팀이 정합니다 (제안: 비회원 세션당 5회, 회원 시간당 30회).

### ② 조건 구조화 + 향 변환 (Python)

이 단계 안에서 LLM을 2번 호출합니다. **밖에서 보면 한 번의 요청**이지만, 안에서는 책임이 나뉩니다.

#### ②-a. 조건 구조화 (LLM 호출 1)

사람 말을 코드가 쓸 수 있는 형태로 바꿉니다.

```json
{
  "scent_preference": [],
  "context":  { "season": ["summer"], "daypart": [], "gender": [] },
  "performance": { "intensity": "", "longevity": "" },
  "avoid": ["머스크"],
  "additional_requirements": ["포근하고", "깨끗한 느낌"]
}
```

**이 단계는 향을 추론하지 않습니다.** "포근한"과 "깨끗한"은 원문 그대로 `additional_requirements`에 보존됩니다.

이 규칙이 있는 이유는 두 가지입니다. 첫째, 현재 Stage 1 프롬프트(`15_stage1_llm_prompt_v1.txt`)와 200개 Golden Set이 이 정책으로 만들어져 있어서, 여기서 향을 추론하면 기존 평가 자산을 전부 다시 만들어야 합니다. 둘째, "말한 것"과 "추론한 것"이 섞이면 나중에 추천 이유를 설명할 때 근거를 구분할 수 없습니다.

#### ②-b. 향 변환 (Domain Lexicon 조회 + LLM 호출 2)

보존된 표현을 accord 후보로 바꿉니다.

**먼저 렉시콘에서 후보를 꺼냅니다.** 형태소 분석으로 "포근하고" → "포근한", "깨끗한 느낌" → "깨끗한"으로 정규화한 뒤 조회합니다.

```
포근한 →  powdery  (이불·아기·파우더 문맥)        향수 62,885개
          vanilla  (달콤함·겨울 문맥)             향수 34,562개
          musky    ⚠ 단독 사용 금지               향수 41,154개

깨끗한 →  soapy         (비누·세탁 문맥)          향수  1,720개
          aquatic+fresh (물·공기 문맥)            향수  4,963개
```

**그 다음 LLM이 이 문맥에서 어느 것인지 고릅니다.**

- "여름"이 있으므로 "깨끗한"은 비누보다 물 쪽 → `fresh`, `aquatic`
- **사용자가 머스크를 거부했으므로** "포근한"의 `musky` 후보는 제외 → `powdery`, `vanilla`

두 번째 판단이 이 호출이 필요한 이유입니다. 회피 조건이 선호 조건의 후보와 충돌할 때 어느 쪽을 접을지는 표에 미리 다 적어둘 수 없습니다.

**Python 서버의 응답:**

```json
{
  "conditions": { ...①의 구조화 결과... },
  "scent_targets": [
    { "type": "ACCORD", "name": "powdery", "weight": 1.0, "required": true,
      "from": "포근한", "evidence": "lexicon:kr.pogeunhan#powdery" },
    { "type": "ACCORD", "name": "vanilla", "weight": 0.7, "required": false,
      "from": "포근한", "evidence": "lexicon:kr.pogeunhan#vanilla" },
    { "type": "ACCORD", "name": "fresh",   "weight": 1.0, "required": true,
      "from": "깨끗한", "evidence": "lexicon:kr.kkaekkeuthan#fresh(water-context)" },
    { "type": "ACCORD", "name": "aquatic", "weight": 0.7, "required": false,
      "from": "깨끗한", "evidence": "lexicon:kr.kkaekkeuthan#aquatic(water-context)" }
  ],
  "excluded_by_avoid": [
    { "name": "musky", "from": "포근한", "reason": "avoid:머스크" }
  ]
}
```

`from`과 `evidence`를 함께 돌려주는 이유는 ④의 추천 이유 계산에서 "이 accord가 사용자의 어느 말에서 나왔는지"를 알아야 하기 때문입니다.

### ③ 검색 · 점수 · 조건 완화 (Spring + PostgreSQL)

#### 검색

`perfumes` × `perfume_accords` × `perfume_notes`를 대상으로 SQL 검색합니다.

- **회피 조건은 하드 필터**입니다. `avoid`에 걸린 accord/note를 가진 향수는 `NOT EXISTS`로 아예 제외합니다
- `required: true`인 target은 모두 만족해야 후보에 들어옵니다
- `required: false`는 점수에만 기여합니다

#### 점수

`perfume_accords.weight`(Fragrantica의 accord strength 0~100)와 target weight를 곱해 합산하고, note 매칭을 IDF 가중으로 더합니다.

> **주의 — 이 점수 식은 아직 검증되지 않았습니다.**
> EDA 04~09에서 검증한 Accord 0.5 / Note 0.5 결합과 Note IDF는 **향수↔향수 유사도** 실험의 결과입니다. 지금 문제는 **쿼리→향수** 검색이라 다른 문제입니다. 11번 rule baseline의 category score 방식을 출발점으로 삼되, §7에서 별도로 측정해야 합니다.

#### 조건 완화

NLR-01이 "3~5개"를 요구하므로, 결과가 3개 미만이면 조건을 단계적으로 뗍니다.

| 순서 | 완화 대상 | 근거 |
|---|---|---|
| 1 | `required: false` accord 제거 | 렉시콘이 보조 후보로 표시한 것 |
| 2 | context (계절·시간대) 제거 | 향 자체가 아닌 상황 조건 |
| 3 | performance (강도·지속력) 제거 | 명시 빈도가 낮고 데이터 신뢰도가 낮음 |
| 4 | `required: true` accord를 AND에서 OR로 | 향 조건의 강도만 낮춤 |
| 5 | 브릿지로 추론한 accord 제거 (직접 언급한 것만 유지) | 추론보다 명시가 우선 |
| **—** | **`avoid`는 어떤 단계에서도 완화하지 않는다** | **사용자가 명시적으로 거부한 것** |

원칙은 **"시스템이 추론한 것을 먼저 떼고, 사용자가 말한 것은 나중에 뗀다"** 입니다. 회피 조건은 사용자가 가장 강하게 말한 것이므로 예외 없이 지킵니다.

완화가 일어나면 **어느 조건을 뗐는지 기록**하고, ④를 거쳐 추천 이유에 반영합니다. 사용자가 조건이 지켜졌다고 오해하면 안 됩니다.

### ④ 추천 근거 계산 (Spring, 규칙)

선정된 3~5개 각각에 대해 **사실만** 계산합니다. LLM은 이 단계에 없습니다.

```
향수 A
  ├ 충족: powdery(strength 68) ← "포근하고"
  ├ 충족: vanilla(strength 52) ← "포근하고"
  ├ 충족: fresh(strength 31)   ← "깨끗한 느낌"
  ├ 회피 확인: musky 없음      ← "머스크는 빼줘"
  └ 완화된 조건: 없음
```

이 구조가 NLR-07("어떤 부분에서 일치하여 추천되었는지")의 실질입니다. **LLM이 지어낼 수 없는 형태로 근거를 먼저 확정**하는 것이 목적입니다.

### ⑤ 문장화 (Python, LLM 호출 3)

④의 근거를 자연스러운 한국어로 바꿉니다. 3~5개를 **한 번의 호출로** 처리합니다.

> 파우더리한 질감에 바닐라의 단맛이 은은하게 깔려 포근한 인상을 주고, 프레시 노트가 여름에도 무겁지 않게 잡아줍니다. 요청하신 머스크는 들어있지 않습니다.

**LLM에게 주는 것은 ④의 근거뿐입니다.** 향수의 전체 정보를 주지 않습니다. 근거에 없는 내용을 쓸 재료 자체를 주지 않는 것이 지어내기를 막는 방법입니다.

### ⑥ 결과 조립 (Spring)

향수 정보 + 추천 이유 + 완화 안내를 합쳐 응답합니다. MAP-09 연동을 위해 각 향수의 `perfume_map_points` 좌표를 함께 내려줍니다 (좌표가 없는 향수는 `null`).

---

## 4. 컴포넌트별 책임

### 4.1 Spring Boot

- 입력 검증, 인증, 호출량 제한
- Python 서버 호출과 실패 처리
- SQL 검색, 점수 계산, 조건 완화
- 추천 근거 계산 (규칙)
- 응답 조립

**DB에 접근하는 유일한 주체입니다.**

### 4.2 Python 추천 서버

두 개의 내부 엔드포인트를 가집니다.

| 엔드포인트 | 입력 | 하는 일 | 출력 |
|---|---|---|---|
| `/nlr/understand` | 사용자 원문 | LLM 1회(구조화) + 렉시콘 조회 + LLM 1회(향 변환) | 조건 + accord 후보 |
| `/nlr/explain` | 조건 + 근거 목록 | LLM 1회 | 향수별 이유 문장 |

**DB에 접근하지 않습니다.** 필요한 데이터는 전부 요청에 담겨 옵니다.

내부에 가지는 것: Domain Lexicon(메모리), 형태소 분석기(kiwipiepy), 프롬프트 템플릿, 출력 스키마 검증기.

### 4.3 Domain Lexicon

`EDA/data/scent_knowledge/domain_lexicon_v1.csv`

CSV 파일로 관리하고 Python 서버 기동 시 메모리에 적재합니다. 200줄 규모면 메모리 부담이 없고 조회가 빠릅니다.

**파일로 두는 이유**: git에 이력이 남습니다. "왜 머스크를 `musky` 단독으로 매핑하지 않기로 했는가" 같은 판단이 커밋 메시지에 기록되고 PR로 검수됩니다. 렉시콘은 데이터라기보다 코드에 가까운 지식이라 이 성질이 중요합니다.

**DB 대신 파일이어도 안전한 이유**: 기동 시 렉시콘의 모든 accord/note 이름이 `accords`/`notes` 테이블에 존재하는지 검사하고, 하나라도 없으면 에러를 내고 기동을 중단합니다. FK와 같은 효과를 냅니다.

#### 파일 스키마

| 컬럼 | 설명 |
|---|---|
| `entry_id` | 안정적인 ASCII 식별자 (`kr.pogeunhan`). 한글 표기가 바뀌어도 유지 |
| `expression` | 대표 한국어 표현 (포근한) |
| `aliases` | 표기 변형을 `\|`로 구분 (포근하고\|포근함\|폭닥한) |
| `expression_type` | 24번 노트북의 10종 재사용 (SENSORY / SCENE / SOURCE / IMAGE / DIRECT_SCENT …) |
| `target_field` | `STAGE1_DIRECT` (표기 정규화) / `STAGE2_BRIDGE` (향 추론) / `NO_MAPPING` |
| `candidate_type` | `ACCORD` 또는 `NOTE` |
| `candidate_name` | accord/note 이름. `accords`/`notes` 테이블에 존재해야 함 |
| `rank` | 후보 순서 |
| `required` | `core`(필수) / `optional`(보조) |
| `scope_note` | 이 매핑이 적용되는 문맥 (한 줄) |
| `caution` | 하면 안 되는 매핑 |
| `corpus_support` | 이 accord를 가진 향수 수 (스크립트로 자동 갱신) |
| `evidence` | 근거 출처 |
| `standardness` | `standard` / `dialect` / `loanword` / `non_dictionary` |
| `status` | `candidate` / `active` / `retired` |
| `source_query_ids` | 어느 Golden Set 쿼리에서 나왔는지 — **평가 시 leakage 판별용** |

한 표현이 후보를 여러 개 가지면 **여러 줄**이 됩니다. 후보마다 `scope_note`와 `corpus_support`가 다르기 때문입니다.

`corpus_support`가 필수인 이유는 §8에 기록된 실측 때문입니다. 의미가 맞아도 검색이 안 되는 매핑이 존재합니다.

#### 항목 구성 방침

| 층 | 예 | 작업 성격 |
|---|---|---|
| 외래어 | 우디, 시트러스, 파우더리, 머스크 | accord와 거의 1:1. 단 **머스크는 확인된 예외** |
| 고유어·출처 복합어 | 포근한, 깨끗한, 빨래향, 비 온 뒤 숲 | 다대다. 수작업. **여기가 실질 작업량** |
| 평가어 전용 | 향긋한, 좋은 향, 고급스러운 | **accord를 붙이지 않음** (`NO_MAPPING`) |

세 번째 층에 accord를 붙이지 않는 이유는, "향긋하다"의 사전 정의가 "은근히 향기로운 느낌이 있다"로 묘사 내용이 없기 때문입니다. 근거 없이 매핑을 만드는 것은 프로젝트 규칙 위반입니다.

초기 규모는 **30~50개 항목**을 목표로 합니다. 10번 노트북이 `evidence_level=D`로 남긴 13개(고급스러운, 깨끗한, 도시적인, 비 오는 숲, 빨래, 섹시한, 이불, 자연스러운, 차가운, 촉촉한, 포근한, 호텔, 휴양지)가 출발점입니다.

---

## 5. 정책

### 5.1 실패 처리 — 모든 LLM 호출에 비-LLM 대안이 있다

| 실패 지점 | 대체 동작 | 품질 손실 |
|---|---|---|
| LLM 호출 1 (구조화) | 11번 `rule_lexicon.csv` 기반 규칙 파서 | 조건 인식률 41.5% → 15.5% |
| LLM 호출 2 (향 변환) | 렉시콘 조회 결과에서 `rank` 1위만 사용 | 문맥 분기·회피 충돌 해소 불가 |
| LLM 호출 3 (문장화) | 템플릿 문장 | 문장이 딱딱해짐 |

LLM 호출 하나가 죽어도 기능 전체가 죽지 않습니다. Python 서버 자체가 응답하지 않으면 규칙 파서 + 렉시콘 조회 + 템플릿으로 동작합니다(품질은 낮지만 결과는 나옵니다).

타임아웃은 각 호출마다 설정합니다 (제안: 8초). 재시도는 스키마 검증 실패와 네트워크 오류에만 적용하고, 결과가 마음에 안 든다는 이유로는 재호출하지 않습니다.

### 5.2 출력 검증

LLM이 돌려준 accord/note 이름은 **반드시 허용 목록과 대조**합니다. 목록에 없으면 버리고, 버린 개수를 로그에 남깁니다.

LLM에게 최종 이름을 자유롭게 생성시키지 않고 JSON Schema의 enum으로 제약합니다. 다만 enum으로 막아도 목록 밖의 정답을 놓치는 부작용이 있으므로, **버려진 값의 개수를 지표로 관리**합니다.

### 5.3 부적절 입력과 프롬프트 인젝션

- 사용자 입력은 시스템 프롬프트와 명확히 분리된 위치에 넣습니다
- 사용자 입력 안의 지시문("앞의 지시를 무시하고…")은 데이터로 취급합니다
- 출력이 고정 스키마이고 accord 이름이 enum이므로, 인젝션이 성공해도 스키마 검증에서 걸립니다
- 자연어 추천 결과는 공개되지 않으므로 CMT-13(게시글 검수)만큼의 정책은 필요하지 않습니다

### 5.4 비회원

MAP-16(비회원 임시 탐색)과 결이 맞습니다. 비회원도 추천을 받을 수 있고, 결과는 저장하지 않습니다.

회원과의 차이는 호출량 제한뿐입니다. 이번 범위에서는 로그인 여부가 추천 결과에 영향을 주지 않습니다(개인화는 REC-12/13 범위).

---

## 6. 데이터 — 현재 ERD로 가능한 것과 아닌 것

### 사용하는 테이블

| 테이블 | 용도 |
|---|---|
| `perfumes` | 기본 정보. `is_active=true`만 검색 |
| `perfume_accords` | **핵심.** `weight`가 Fragrantica accord strength |
| `perfume_notes` | note 매칭. `note_type`으로 tier 구분 |
| `accords`, `notes` | 허용 목록 검증 |
| `perfume_map_points` | MAP-09 연동용 좌표 |
| `perfume_prices` | 가격 조건이 있을 때 |

### 제약 4건 — 현재 ERD를 바꾸지 않는 대신 기록한다

#### 제약 1. 계절·시간대 커뮤니티 투표가 없다

EDA 07~09번은 Fragrantica의 계절·시간대 **투표수**로 재정렬해 NDCG@10을 0.271 → 0.322로 올렸습니다. 그런데 ERD의 계절 데이터는 `perfume_review_seasons`, 즉 **우리 서비스 사용자가 후기에 남긴 계절**입니다. 서비스 초기에는 0건입니다.

**결과**: "여름에 쓸 향수" 같은 계절 조건을 데이터로 걸 수 없습니다. §3의 완화 순서에서 계절을 2순위로 둔 이유이기도 합니다.
**대응**: 계절 조건은 accord와의 상관으로 간접 반영하는 것을 검토합니다(`10_accord_season_bridge.csv`에 관계 데이터가 있습니다). 다만 이는 검증되지 않은 우회이므로 §7에서 측정합니다.

#### 제약 2. 추천 이력을 저장할 테이블이 없다

쿼리 원문, 구조화 결과, 추천 향수, 추천 이유를 담을 테이블이 ERD에 없습니다.

**결과**: 같은 질문을 다시 하면 처음부터 다시 계산합니다. 추천 품질을 사후 분석할 데이터가 남지 않습니다.
**대응**: 이번 범위에서는 저장하지 않습니다. REC-13(신규 사용자 추천)이 자연어 입력 결과를 쓰려면 필요해지므로, 부록 A에 제안을 남깁니다.

#### 제약 3. `perfume_notes` PK가 `(perfume_id, note_id)`다

같은 note가 top과 base에 동시에 들어갈 수 없습니다. **실측: tiered note를 가진 향수 93,166개 중 4,935개(5.3%)가 이 경우입니다.**

**결과**: 적재 시 5.3%에서 tier 정보가 일부 손실됩니다.
**대응**: 적재 시 `top > middle > base` 우선순위로 하나만 남깁니다. EDA 06번에서 tier가 유효한 추가 정보가 아니라고 판정됐으므로(개선 fold 0/5) 현재 검색 품질에 미치는 영향은 작을 것으로 봅니다. 다만 이는 향수↔향수 실험의 결론이라 쿼리→향수에서도 같은지는 확인되지 않았습니다.

#### 제약 4. `perfumes.description`이 `VARCHAR(500)`이다

**실측: Fragrantica description의 평균 길이가 505자이고, 500자를 넘는 것이 50,575개(38.3%)입니다.**

**결과**: 그대로 적재하면 38.3%가 잘립니다.
**대응**: 이번 범위에서 description을 검색이나 추천 이유 생성에 쓰지 않으므로 기능에는 영향이 없습니다. 다만 **적재 시 잘림이 발생한다는 사실을 DB 담당자와 공유해야 합니다.** 부록 A에 컬럼 타입 변경을 제안합니다.

### 미확인 항목

- **`perfumes.name_ko`**: Fragrantica 데이터에는 한국어 이름이 없습니다. 어디서 채울지 정해지지 않았습니다.
- **`perfumes.concentration`**: Fragrantica dump에 해당 필드가 없습니다. 출처 확인 필요.
- **적재 규모**: 검색 대상은 131,930개로 정했으나, 실제로 DB에 전량 적재하는지는 DB 담당자와 확인이 필요합니다.

---

## 7. 성능 측정 · 평가 계획

응답 시간 목표를 아직 정하지 않은 이유는 **측정된 값이 하나뿐이기 때문**입니다.

### 7.1 응답 시간

| 구간 | 현재 상태 |
|---|---|
| LLM 호출 1 (구조화) | **실측 완료** — mean 1.96초 / median 1.74초 / p95 3.19초 (200개, GMS `gpt-5.4-nano`) |
| LLM 호출 2 (향 변환) | **미측정** — 23번 파일럿은 12건만 실행, 지연 기록 없음 |
| SQL 검색 (13만 개) | **미측정** |
| LLM 호출 3 (문장화) | **미측정** |

**먼저 할 일**: 호출 2·3과 검색의 실측 지연을 확보합니다. 20~30개 쿼리로 각 구간을 개별 계측하고 p50/p95를 냅니다.

그 결과를 보고 아래 중에서 선택합니다.

| 선택지 | 예상 | 대가 |
|---|---|---|
| 3회 유지 + 로딩 UI | 6초 내외 | 없음. 구현 단순 |
| 결과 먼저, 이유는 나중에 스트리밍 | 체감 4초 | FE·BE 작업량 증가 |
| 호출 2를 렉시콘 조회로 대체 | 4초 | 문맥 분기·회피 충돌 해소 불가 |

### 7.2 추천 품질

**baseline은 렉시콘 없이 LLM만 쓴 결과입니다.** 규칙 baseline과 비교하면 오해를 만듭니다.

| 조건 | 무엇을 분리하는가 |
|---|---|
| 0 | 현재 프롬프트 그대로 (baseline) |
| 1 | + accord enum 제약 |
| 2 | + 렉시콘에서 검색된 항목만 프롬프트에 주입 |
| 3 | + 후처리 정규화 |
| 4 | 렉시콘 전체를 프롬프트에 덤프 (2와 비교) |
| **5** | **크기는 같고 내용을 무작위로 섞은 렉시콘 (통제군)** |

조건 5가 결과를 정직하게 만듭니다. 틀린 렉시콘으로도 같은 이득이 나오면, 측정된 것은 도메인 지식이 아니라 프롬프트가 길어진 효과입니다.

**leakage 주의**: 현재 `korean_scent_lexicon_v0_1.csv`는 Golden Set 200개에서 추출됐고 `query_ids` 컬럼에 출처가 기록돼 있습니다. 같은 200개로 평가하면 암기를 측정하게 됩니다.
→ `source_query_ids`로 **seen / unseen을 나눠 따로 보고**합니다. 가능하면 새 쿼리 60~100개를 수집해 동결하고 거기서는 항목을 뽑지 않습니다.

**지표**: 필드별 F1(paired, n=200)을 주 지표로, Overall Exact Match는 보조로만 씁니다. EM 6.00%는 200개 중 12개라 3%p 변동이 6개 쿼리입니다.

---

## 8. 선행 작업과 미해결 과제

### 구현 전에 끝내야 하는 것

| # | 작업 | 이유 | 비용 |
|---|---|---|---|
| 1 | **채점 기준 재정의** | 현재 avoid F1 0.000의 실체는 `머스크` vs `musk` 표기 차이. 정규화만 적용하면 0.507. 자가 틀어진 채로 최적화하면 안 됨 | 반나절 |
| 2 | **16번 Golden Set QA 60건 판정** | 0/60 미검토. gold 오류인지 표기 불일치인지 가리려고 만든 파일 | 반나절~하루 |
| 3 | **저장된 LLM 출력으로 재채점** | `15_llm_stage1_checkpoint.csv`에 200개 응답이 있어 API 재호출 불필요 | 1시간, 비용 0 |
| 4 | **22번 사람 평가 70건** | 0/70 미기입. accord 92개로 부족한지(TARGET_SPACE_LIMITATION) LLM이 못 찾는지(MAPPING_FAILURE)를 가름 | 하루 |

4번의 결과가 렉시콘 설계를 바꿀 수 있습니다. accord target space 자체가 부족하다는 결론이 나오면, 렉시콘이 accord만 겨냥하는 현재 설계를 재검토해야 합니다.

### 이번 범위 밖의 열린 문제

- **Fragrantica 데이터 출처** — `robots.txt`에 `ai-train=no`와 EU 저작권 지침 제4조 권리유보가 명시돼 있음(직접 확인). 이용약관 §5.7의 정확한 문구와 시행일은 미확인(페이지가 403). 팀·SSAFY 차원의 확인 필요
- `name_ko`, `concentration`의 출처
- 계절 조건을 accord 상관으로 대체하는 방식의 유효성
- 쿼리→향수 점수 식 (향수↔향수 결과를 그대로 쓸 수 없음)

---

## 부록 A. ERD 변경 제안

본문은 현재 ERD 기준으로 작성했습니다. 아래는 **바꾸면 무엇이 좋아지는지**이며, DB 담당자와 협의가 필요합니다.

### A-1. `perfumes.description` 타입 변경 (우선순위 높음)

```sql
ALTER TABLE perfumes ALTER COLUMN description TYPE TEXT;
```

**이유**: 현재 `VARCHAR(500)`에서 50,575개(38.3%)가 잘립니다. 자연어 추천에는 영향이 없지만 DTL-01(향수 기본 정보 조회)에서 설명이 중간에 끊깁니다.

### A-2. 계절·시간대 커뮤니티 데이터 캐시

```sql
CREATE TABLE perfume_community_stats (
    perfume_id   BIGINT PRIMARY KEY REFERENCES perfumes(perfume_id) ON DELETE CASCADE,
    winter_votes INTEGER, spring_votes INTEGER,
    summer_votes INTEGER, autumn_votes INTEGER,
    day_votes    INTEGER, night_votes  INTEGER,
    total_voters INTEGER,
    collected_at TIMESTAMPTZ
);
```

**이유**: EDA 07번에서 NDCG@10을 0.271 → 0.322로 올린 신호입니다. 현재 ERD에는 이 데이터를 둘 곳이 없습니다.
**주의**: 이 데이터는 Fragrantica 출처이므로 §8의 출처 문제와 함께 판단해야 합니다.

### A-3. 추천 이력 저장

```sql
CREATE TABLE nlr_requests (
    request_id    BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    user_id       BIGINT REFERENCES users(user_id) ON DELETE SET NULL,  -- 비회원 NULL
    query_text    TEXT NOT NULL,
    conditions    JSONB,          -- 구조화 결과
    scent_targets JSONB,          -- accord 후보
    relaxed_steps JSONB,          -- 완화된 조건
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE nlr_results (
    request_id  BIGINT NOT NULL REFERENCES nlr_requests(request_id) ON DELETE CASCADE,
    perfume_id  BIGINT NOT NULL REFERENCES perfumes(perfume_id) ON DELETE CASCADE,
    rank        INTEGER NOT NULL,
    score       NUMERIC(10,6),
    match_evidence JSONB,         -- 규칙이 계산한 근거
    reason_text TEXT,             -- LLM이 만든 문장
    PRIMARY KEY (request_id, perfume_id)
);
```

**이유**: REC-13(신규 사용자 추천)이 "자연어 입력 결과를 기반으로" 추천한다고 정의돼 있는데, 그 결과가 어디에도 남지 않습니다. 추천 품질 사후 분석에도 필요합니다.

### A-4. `perfume_notes` PK 변경

```sql
-- 현재: PRIMARY KEY (perfume_id, note_id)
-- 제안: PRIMARY KEY (perfume_id, note_id, note_type)
```

**이유**: 같은 note가 여러 tier에 등장하는 경우가 4,935개(5.3%)입니다.
**우선순위 낮음**: EDA 06번에서 tier가 유효한 추가 정보가 아니라고 판정돼(개선 fold 0/5) 현재 검색에는 영향이 작습니다. DTL-02(향조 정보 조회)의 표시 정확도 문제입니다.

---

## 관련 문서

- `EDA/docs/nlr_engineering_notes.md` — 측정 결과와 트러블슈팅 기록
- `EDA/docs/plans/SEMANTIC_BRIDGE_PILOT_PLAN.md` — 22번 파일럿 사전등록
- `EDA/PROJECT_ANALYSIS_AUDIT.md` — 01~20번 분석 감사
- `EDA/SCHEMA.md` — Fragrantica dump 스키마

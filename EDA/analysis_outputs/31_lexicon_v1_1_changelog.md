# Domain Lexicon v1 → v1.1 변경 기록

`ai_summary` 배수 측정(노트북 30)을 사전에 반영했다. 근거와 한계는 `DECISIONS.md` N4,
측정은 `nlr_engineering_notes.md` 10번.

## 적용한 판정 기준 — 사용자 승인 2026-09-11

| # | 질문 | 결정 |
|---|---|---|
| 1 | 팀 문서와 데이터가 엇갈리면 | **역할 분리.** 팀 문서는 표현의 존재, `ai_summary` 는 accord 지정 |
| 2 | 배수 문턱 | **1.4.** 통제군 최대 배수가 1.38이므로 그 이하는 잡음과 구별되지 않는다 |
| 3 | 문턱 미달이면 | **`core` → `optional`, 근거 칸에 기록.** 삭제·교체하지 않는다 |
| 4 | `core` 가 2개 미만이면 | **`NO_MAPPING` 으로 돌린다** |

## 노트북 30의 판정을 그대로 쓰지 않은 부분

노트북 30의 `min_support = 30` 은 **희귀 accord 를 구조적으로 차별한다.**
`반증 — 해당군에 지지도 없음` 3건을 원자료로 다시 셌다.

| 표현 | accord | 해당군 | 보유 | 배수 | 재판정 |
|---|---:|---:|---:|---:|---|
| 머스크 | `soapy` | 653 | 14 | **2.15x** | **문턱 통과** — 30개 미만이라 표에서 빠졌을 뿐 |
| 이불 | `soapy` | 112 | 2 | 1.79x | **표본 부족** — 2개로 낸 배수는 의미 없음 |
| 호텔 | `soapy` | 1,163 | 15 | 1.29x | 문턱 미달 (판정 유지) |

기계적으로 적용했다면 `머스크 → soapy` 를 잘못 강등할 뻔했다.
이 매핑은 `nlr_engineering_notes.md` 2번이 코퍼스로 확인한 한국어 드리프트 항목이다.

## 바뀐 행 7개

| entry_id | 표현 | accord | required | target_field |
|---|---|---|---|---|
| `kr.sens.cozy` | 포근한 | `powdery` | core → optional | STAGE2_BRIDGE → NO_MAPPING |
| `kr.sens.cozy` | 포근한 | `musky` | core → optional | STAGE2_BRIDGE → NO_MAPPING |
| `kr.sens.cozy` | 포근한 | `vanilla` | — | STAGE2_BRIDGE → NO_MAPPING |
| `kr.sens.cold` | 차가운 | `ozonic` | core → optional | STAGE2_BRIDGE → NO_MAPPING |
| `kr.sens.cold` | 차가운 | `fresh` | core → optional | STAGE2_BRIDGE → NO_MAPPING |
| `kr.scene.hotel` | 호텔 | `soapy` | core → optional | STAGE2_BRIDGE → NO_MAPPING |
| `kr.scene.hotel` | 호텔 | `white floral` | core → optional | STAGE2_BRIDGE → NO_MAPPING |

## `NO_MAPPING` 으로 돌린 갈래

| 표현 | 남은 core | 조건 |
|---|---:|---|
| 차가운 | 0 | `(기본)` |
| 포근한 | 0 | `(기본)` |
| 호텔 | 0 | `(기본)` |

`spec.md` §4.3 의 단독 매핑 금지 규칙은 측정으로 정해진 것이다 — `citrus` 단독은 후보
59,969개 중 17,736개가 강도 100으로 동점이라 순위가 나오지 않는다(`DECISIONS.md` N2).
따라서 `core` 가 1개여도 검색이 성립하지 않는다.

## 바뀌지 않은 것

- **행 44개, 컬럼 16개 그대로.** 행을 지우지 않았다
- **accord 를 교체하지 않았다.** 데이터가 가리키는 쪽으로 갈아끼우지 않았다
- `entry_id` · `expression` · `candidate_name` · `evidence_tier` · `corpus_support` ·
  `source_query_ids` **변경 0행**
- **`status` 는 전부 `candidate` 그대로.** 강등은 검색 동작을 안전하게 바꾼 것이지
  의미 판정이 끝났다는 뜻이 아니다
- `domain_lexicon_v1.csv` **원본을 덮어쓰지 않았다**

## 왜 교체가 아니라 강등인가

`포근한` 의 배수 1위는 `savory`(3.72x)다. 그런데 방향을 뒤집으면 다르다.

| accord | 보유 향수 | cozy 향수 중 비율 | 그 accord 중 cozy 비율 |
|---|---:|---:|---:|
| `savory` | 115 | 3.4% | **82.6%** |
| `powdery` | 6,291 | **68.2%** | 29.9% |

서비스는 **accord 로 향수를 골라 주는** 쪽이므로 오른쪽 열이 중요하다. `savory` 는 맞히면
잘 맞지만 줄 향수가 115개뿐이고, `savory+nutty+cacao` 조합은 13만 개 중 **5개**다
(측정 기록 1번의 `foresty` 문제와 같다).

**`powdery` 는 틀린 것이 아니라 필수로 걸기엔 너무 넓다.** `optional` 로 내리면 해결된다.

`savory` 는 넣지 않되 후보로 기록해 둔다 — 그 accord 를 가진 향수의 **82.6%** 가
cozy 로 불리므로 신호는 진짜이나 보유 향수가 115개뿐이다.

## 남은 문제

- **`spec.md` §3 의 워크드 예제가 `포근한 → powdery` 다.** 이 개정으로 사전에서는
  `NO_MAPPING` 이 됐으므로 문서 예제와 데이터가 어긋난다. spec 본문 수정은 별도 판단이다
- **근거가 `ai_summary` 하나다.** 커버리지 9.4%, 인기 향수 편향, Fragrantica 출처 문제가
  그대로 적용된다 (`DECISIONS.md` N4 의 Trade-off)
- **의미 판정은 여전히 없다.** 매핑 행이 전부 `candidate` 인 이유다

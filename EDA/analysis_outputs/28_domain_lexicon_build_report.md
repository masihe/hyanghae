# Domain Lexicon v1 빌드 리포트

`data/scent_knowledge/domain_lexicon_v1.csv` 를 만든 기록이다.

## 무엇을 만들었는가

| | |
|---|---:|
| 표현 | 26 |
| 행 | 44 |
| `VERIFIED` | 14 |
| `TEAM` | 23 |
| `LLM` (사람 검토 대기) | 7 |
| `NO_MAPPING` | 8 |
| `status=active` | 16 |
| `status=candidate` | 28 |

`spec.md` §4.3의 목표는 30~50개 항목이었다.

## 스키마 변경 1건

`candidate_type` 에 **`FIELD`** 를 추가했다. 우선순위 1번(향수 전문 용어, 실사용 18.1%)이
`탑노트 → notes.tiered.top` 처럼 Fragrantica 스키마 필드를 가리키는데
기존 `ACCORD` / `NOTE` 로는 담을 칸이 없었다. 사용자 승인 2026-09-10.

허용 필드는 `SCHEMA.md` 에 실제로 있는 것만 넣었다 — ['longevity', 'notes', 'notes.tiered.base', 'notes.tiered.middle', 'notes.tiered.top', 'sillage'].

**`부향률`은 매핑하지 않았다.** `SCHEMA.md` 를 확인한 결과 dump 에 `concentration` 필드가
없다. `spec.md` §6 의 미확인 항목과 같은 내용이다.

## 근거 등급을 매핑의 출처로 정의했다

| 등급 | 뜻 |
|---|---|
| `VERIFIED` | 스키마 필드 · accord/note 이름 동일성 · 코퍼스 측정값이 매핑을 결정 |
| `TEAM` | 팀 문서 `perfume_14families_korean_descriptors.md` 에 출처 행이 있다 |
| `LLM` | 출처 없이 AI 초안. 사람 검토 후 `TEAM` 으로 승격 |

`AGENTS.md` 의 *"Do not invent mappings such as an abstract phrase to scent features
without a defined evidence or modeling method"* 를 따라, 세 방법 밖의 매핑은 만들지 않고
근거가 없으면 `NO_MAPPING` 으로 뒀다.

## 검증 3건

1. **`candidate_name` 존재** — accord 92개 / note 2,523개 /
   허용 field 6개 마스터 목록과 대조. 전부 통과
2. **매핑 규칙** (`DECISIONS.md` N2) — 갈래 20개 전부
   `core` 2개 이상 + 검색 결과 3개 이상. 전부 통과
3. **leakage 추적** — `source_query_ids` 를 채워 seen/unseen 분리 가능하게 함

재현 게이트로 accord 92개 `perfume_count` 를 오차 0으로 재현한 뒤 계산했다.

## 갈래별 검색 성립성

`core` 로 필터하고 `core` + `optional` 로 점수를 매긴 결과다(`spec.md` §3).
`FIELD` 갈래 8개는 검색 조건이 아니므로 표에서 뺐다.

| 표현 | core accord | 갈래 조건 | 후보 | 5위 동점 |
|---|---|---|---:|---:|
| 머스크 | `musky+soapy+fresh` | (기본) | 400 | 5 |
| 깨끗한 | `soapy+fresh` | query_contains:비누,세탁,빨래,샤워,침구,이불,스킨,뽀송 | 1,049 | 6 |
| 깨끗한 | `aquatic+fresh` | query_contains:물,바다,여름,공기,수영,워터,시원 | 4,963 | 14 |
| 빨래 | `soapy+fresh` | (기본) | 1,049 | 6 |
| 포근한 | `powdery+musky+vanilla` | (기본) | 29,198 | 9 |
| 이불 | `powdery+soapy+musky` | (기본) | 519 | 5 |
| 비 오는 숲 | `mossy+earthy+green` | (기본) | 4,715 | 5 |
| 차가운 | `ozonic+fresh` | (기본) | 2,658 | 5 |
| 촉촉한 | `aquatic+green` | (기본) | 3,071 | 12 |
| 휴양지 | `tropical+coconut` | (기본) | 1,317 | 5 |
| 호텔 | `soapy+white floral` | (기본) | 1,494 | 5 |
| 달달 | `sweet+caramel` | (기본) | 3,745 | 7 |

## 사람 검토 대기 — `LLM` 등급 7행

출처 없이 AI 가 고른 후보다. `spec.md` §4.3 의 승격 경로대로 사람 검토를 거쳐
`TEAM` 으로 올린다.

| 표현 | 후보 | required | 코퍼스 |
|---|---|---|---:|
| 머스크 | `fresh` | optional | 33,478 |
| 깨끗한 | `fresh` | core | 33,478 |
| 이불 | `musky` | optional | 41,154 |
| 비 오는 숲 | `green` | optional | 29,755 |
| 휴양지 | `coconut` | core | 3,269 |
| 호텔 | `white floral` | core | 39,497 |
| 달달 | `caramel` | core | 4,008 |

## 매핑하지 않은 표현 8개

| 표현 | 근거 등급 |
|---|---|
| 부향률 | VERIFIED |
| 리니어 | VERIFIED |
| 향긋한 | VERIFIED |
| 무난한 | VERIFIED |
| 고급스러운 | TEAM |
| 도시적인 | TEAM |
| 섹시한 | TEAM |
| 자연스러운 | TEAM |

## 한계

- **`TEAM` 등급은 "팀 문서에 표현이 있다"까지만 보증한다.** 문서는 표현을 향 계열로
  정리한 것이고 accord 를 지정하지 않았다. 계열 → accord 단계는 이 노트북의 판단이다.
  문서 자신의 경고 — *"`포근한`, `깨끗한` 같은 단어는 패밀리를 단독 판별하는 단어가
  아니라 방향을 잡는 단어다."*
- **의미 판정을 받지 않았다.** 검색이 되는지는 계산했지만 `soapy+fresh` 가 `빨래` 의
  옳은 번역인지는 사람이 판정할 문제다. 매핑 행은 전부 `status=candidate` 다
- **질감층을 넣지 않았다.** `spec.md` §8 남은 작업 5번 미결정
- **은어·비유를 넣지 않았다.** `DECISIONS.md` N1 — 실사용 1.3%, 후순위
- **`잔향` 은 두 뜻이 겹친다.** 지속력인지 베이스노트인지 문맥으로 갈리므로 두 행으로 뒀다
- **`지속력`·`발향` 은 dump 필드에 대응하지만 ERD 컬럼이 확인되지 않았다**
- 커버리지를 측정하지 않았다. `spec.md` §4.3 이 인용한 8.2%/15.8% 는 다른 사전의 값이다

## 재현 방법

```bash
cd EDA
export PYTHONIOENCODING=utf-8
# 28_domain_lexicon_v1.ipynb 를 REPORT_ONLY=False 로 실행
# API 호출 0회. 검증 3건과 재현 게이트가 먼저 통과해야 저장된다
```

## 관련 자료

- `docs/spec.md` §4.3 — 사전 스키마와 우선순위
- `docs/DECISIONS.md` N1 — 방언·은어 후순위 / N2 — accord 조합 매핑
- `docs/nlr_engineering_notes.md` 1·2·8번 — 코퍼스 지지도, 머스크 드리프트, 단독 금지
- `27_bridge_accord_search_feasibility.ipynb` — 검색 성립성 계산 방법
- `analysis_outputs/25_stage1_scoring_alias_v1.csv` — 채점기용 별칭표 (복제하지 않음)
- `data/scent_knowledge/source/perfume_14families_korean_descriptors.md` — `TEAM` 등급의 출처

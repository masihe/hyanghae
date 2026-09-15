# 41. Domain Lexicon v1.2 → v1.3 변경 기록

근거: 외부 리서치(`도메인 사전 구축·운영 레퍼런스`) 검토 · `DECISIONS.md` N5 근거 3
작성: 2026-09-14

## 결론

- **컬럼 3개를 더했다. 기존 16개 컬럼과 44행은 한 글자도 바뀌지 않았다**
- `evidence_tier` 를 **지우지 않았다.** `nlr_engine._lexicon_lookup()` 이 이 컬럼을 읽는다
- 매핑의 승격·강등·삭제는 **하지 않았다.** 이번 변경은 기록 구조만 바꾼다

## 왜 바꾸는가

`evidence_tier` 한 칸이 **서로 다른 두 축을 섞고 있었다.**

| 값 | 실제로 무엇을 말하나 |
|---|---|
| `VERIFIED` | 출처(외부 자료·스키마) + 상태(검증됨) 두 개가 겹쳐 있다 |
| `TEAM` | 출처 |
| `LLM` | 출처 |

그래서 *"`TEAM` 매핑이 코퍼스 검증을 통과했는가"* 를 이 컬럼으로 물을 수 없었다.
실제로 44행이 전부 `status=candidate` 인 채로 서비스에 나가고 있다.

## 더한 컬럼 3개

### `source_type` — 이 매핑이 어디서 왔는가

| 값 | 판별 규칙 | 행 수 |
|---|---|---:|
| `FRAGRANTICA_SCHEMA` | `candidate_type == FIELD` | 8 |
| `LLM_PROPOSAL` | `evidence_tier == LLM` | 3 |
| `NAME_IDENTITY` | rationale 에 `이름 동일성` · `이름과 뜻이 같다` | 2 |
| `TEAM_JUDGMENT` | rationale 에 `출처 없이` | 4 |
| `TEAM_DOC` | rationale 에 `팀 문서` · `같은 절` · `같은 축` · `같은 계열` · `같은 문서` · `청결감 축` | 24 |
| `NO_MAPPING_DECISION` | `candidate_name` 이 비어 있음 | 3 |

### `verification_status` — 코퍼스 판정의 최종 결과

**판정의 권위는 `rationale` 이다. `30_lexicon_crosscheck.csv` 의 라벨을 쓰지 않았다.**

이유는 `DECISIONS.md` N5 근거 3 이다. 노트북 30 은 `min_support = 30` 때문에 판정 3건 중
**2건이 오판**이었고, 팀이 재판정해 뒤집었다. 그 재판정이 `rationale` 에 기록돼 있다.

| 표현 | accord | 노트북 30 라벨 | 팀 재판정 |
|---|---|---|---|
| 머스크 | `soapy` | 반증 | **문턱 통과** (2.15x. 653개 중 14개로 30 문턱에 걸렸을 뿐) |
| 이불 | `soapy` | 반증 | **표본 부족** (112개 중 2개. 배수가 의미 없음) |
| 호텔 | `soapy` | 반증 | 문턱 미달 (유지) |

crosscheck 라벨을 기계적으로 옮겼다면 **N5 가 명시적으로 되돌린 판정을 다시 집어넣었을 것이다.**

| 값 | 판별 규칙 (순서대로 적용) | 행 수 |
|---|---|---:|
| `SCHEMA_MATCHED` | `candidate_type == FIELD` | 8 |
| `NOT_APPLICABLE` | `candidate_name` 이 비어 있음 | 8 |
| `NAME_IDENTITY_EXEMPT` | `이름 동일성 매핑이므로 배수 근거가 필요 없다` | 1 |
| `INSUFFICIENT_SAMPLE` | `표본 부족` · `지지도 반증도 아니다` | 1 |
| `CIRCULAR_UNTESTABLE` | `검색어가 accord 이름과 같아 신호로 읽지 않음` · `(순환)` | 3 |
| `CORPUS_CONTRADICTED` | `전체보다 오히려 드물다` | 2 |
| `BELOW_THRESHOLD` | `문턱 미달` · `통제군 최대 1.38 보다 낮다` · `통제군 수준` | 5 |
| `CORPUS_SUPPORTED` | `문턱 1.4 통과` · `지지됨` · `배수는 문턱을 넘는다` · `문턱을 넘었다` | 16 |

규칙에 걸리지 않는 행이 하나라도 있으면 생성을 중단하도록 가드를 뒀다. 44행 전부 걸렸다.

### `relation_type` — 관계의 종류

| 값 | 판별 규칙 | 행 수 |
|---|---|---:|
| `NOT_RELATED` | `candidate_name` 이 비어 있음 (매핑하지 않기로 한 표현) | 8 |
| `PRODUCT_ATTRIBUTE` | `candidate_type == FIELD` (`탑노트 → notes.tiered.top`) | 8 |
| `EVOKES` | `expression_type` 이 `SCENE` · `SOURCE` (`호텔 → soapy`) | 12 |
| `ASSOCIATED_WITH` | 나머지 | 16 |

**`SYNONYM` 을 쓰지 않는다.** `nlr_engineering_notes.md` 2번이 *한국어 `머스크` ≠ 영어 `musk`*
를 코퍼스로 측정했다. 한국어 표현과 영어 accord 를 동의어로 부를 근거가 우리에게 없다.
`NAME_IDENTITY` 출처인 `머스크 → musky` 도 관계는 `ASSOCIATED_WITH` 다.

## 분해가 드러낸 것

### ① 반증된 매핑이 `core` 로 쓰이는 경우는 없다

`core` 인데 코퍼스 지지가 없는 4행은 **전부 "측정 불가"이지 반증이 아니다.**

| 표현 | accord | 상태 |
|---|---|---|
| 빨래 | `fresh` | `CIRCULAR_UNTESTABLE` |
| 휴양지 | `tropical` | `CIRCULAR_UNTESTABLE` |
| 달달 | `sweet` | `CIRCULAR_UNTESTABLE` |
| 이불 | `soapy` | `INSUFFICIENT_SAMPLE` |

순환 3건은 검색어가 accord 이름과 같아 이 방법으로는 측정할 수 없는 것이고,
`이불 → soapy` 는 표본이 2개라 배수가 의미 없는 것이다. **다른 방법이 필요하다는 뜻이지
틀렸다는 뜻이 아니다.**

### ② 출처별 지지율이 다르다

| 출처 | 지지 | 문턱 미달 | 반증 | 순환 | 표본 부족 |
|---|---:|---:|---:|---:|---:|
| `TEAM_DOC` | 11 | 3 | 2 | 2 | 1 |
| `TEAM_JUDGMENT` | **4** | 0 | 0 | 0 | 0 |
| `LLM_PROPOSAL` | 1 | 2 | 0 | 0 | 0 |

`TEAM_JUDGMENT`(rationale 에 *"출처 없이 고른 것이다"* 라고 적힌 4행)가 **전부 코퍼스 지지를
받았다.** 표본이 4개라 일반화할 수 없지만, *"출처가 없다"* 와 *"틀렸다"* 가 다르다는 것은 보여준다.

`LLM_PROPOSAL` 3행 중 지지는 1행이다.

## 하지 않은 것

| | 이유 |
|---|---|
| `evidence_tier` 삭제 | `nlr_engine` 이 읽는다. 호환을 깨지 않는다 |
| 매핑 승격·강등·삭제 | 이번 변경은 기록 구조만 바꾼다. 측정과 반영을 분리한다 (N4) |
| `concept_id` 추가 | `entry_id` 가 이미 concept id 이고 `aliases` 가 이미 alt-label 이다. 중복이 된다 |
| 테이블 분리 | 44행에서 정규화 이득이 git·PR 검수 손실보다 작다 |
| 팀 저장소 반영 | `ai/data/` 는 v1_2 그대로다. 전환은 별도 판단 |

## 재현

`rationale` 문자열 규칙으로 도출한다. 규칙은 위 표에 전부 적혀 있고,
하나라도 걸리지 않으면 중단한다. 생성 전후로 `domain_lexicon_v1_2.csv` 의 SHA-256 을 대조한다.

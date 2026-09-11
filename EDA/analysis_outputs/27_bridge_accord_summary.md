# bridge accord 의 검색 성립성

## 질문

노트북 23(v2)이 제안한 accord 로 실제 검색하면 향수가 몇 개 나오는가.
`spec.md` §8 남은 작업 1번(*"accord 92개로 표현을 담을 수 있는가"*)의 선행 확인이다.

## 왜 사람 판정만으로는 답이 안 나오는가

`22_pilot_human_evaluation.csv` 의 사람 판정은 **번역이 의미상 맞는가**를 묻는다.
`비 온 뒤의 숲 → foresty` 는 의미상 정확하고 채점하면 만점을 받는다.
그런데 `foresty` 보유 향수는 **1개**다. 사람 점수가 만점이어도 기능은 동작하지 않는다.

사전등록된 ABSTAIN 원인 분류 세 개는 모두 *"적절한 target 이 있는가"* 를 묻고,
*"그 target 이 변별력이 있는가"* 를 묻는 칸이 없다. 이 노트북은 그 축만 계산한다.

## 설계

- **API 호출 0회.** 노트북 23 의 저장된 매핑을 읽는다
- **사람 판정 0건**
- 점수 = target accord 의 strength 합 (`spec.md` §3 의 주의대로 미검증 형태)
- 재현 게이트 2개를 먼저 통과시킨다
  - accord 92개 `perfume_count` 재현 — 오차 0
  - 2개 조합 14건 `cooccurrence_count` 교차검증 — 오차 0
- 입력 129,161개 향수 (전체 131,930개 중 accord 없는 2,769개 제외)

## 결과

| | |
|---|---:|
| 쿼리 | 12 |
| v2 가 번역한 쿼리 | 10 |
| **검색 가능** | **7** |
| **검색 불가** | **3** |
| 번역 없음 (ABSTAIN) | 2 |

검색 불가의 원인은 전부 `foresty` 하나다. 보유 향수가 1개이므로
다른 accord 와 AND 로 묶으면 0이 된다. 그리고 이 accord 는 v2 가 번역한 10건 중
**3건**에 쓰였다 — 숲·자연 표현 전부다.

## 조합은 되고 단독은 안 된다

| accord | 보유 향수 | 중앙 강도 | 최대값 동점 | 단독 5위 동점 |
|---|---:|---:|---:|---:|
| `citrus` | 59,969 | 67 | 17,736 | 17,736 |
| `warm spicy` | 45,319 | 52 | 6,281 | 6,281 |
| `fresh` | 33,478 | 40 | 830 | 830 |
| `earthy` | 19,049 | 40 | 533 | 533 |
| `aquatic` | 8,872 | 41 | 609 | 609 |
| `soapy` | 1,720 | 20 | 18 | 18 |
| `foresty` | 1 | 44 | 1 | 1 |

넓은 accord 두 개를 AND 로 묶고 strength 합으로 정렬하면 순위가 생긴다.
단독으로 쓰면 같은 점수가 수천 개라 상위 5개가 제비뽑기가 된다.

전체 조건 기준 동점 구간 분포: {'실용 범위': 4, '후보 부족': 3, '완전 변별': 3, '': 1, '순위 임의성 큼': 1}

**사전 설계 규칙 하나가 여기서 나온다 — 한 표현은 accord 2개 이상으로 매핑한다.**
`spec.md` §4.3 의 `required` 컬럼(`core`/`optional`)이 이미 이것을 지원한다.

## 92개 안에 대안이 있다

| query | 구분 | 조합 | 후보 | 5위 동점 | 검색 가능 |
|---|---|---|---:|---:|---|
| SQ0061 | v2 원본 | `foresty+earthy` | 0 | 0 | 아니오 |
| SQ0061 | 대안 | `mossy+earthy` | 4,715 | 8 | 예 |
| SQ0061 | 대안 | `mossy+earthy+green` | 1,254 | 5 | 예 |
| SQ0032 | v2 원본 | `foresty` | 1 | 1 | 아니오 |
| SQ0032 | 대안 | `mossy+green` | 1,702 | 20 | 예 |
| SQ0032 | 대안 | `woody+green` | 17,714 | 121 | 예 |
| SQ0073 | v2 원본 | `woody+floral+fresh+foresty` | 0 | 0 | 아니오 |
| SQ0073 | 대안 | `woody+conifer+green` | 720 | 5 | 예 |
| SQ0073 | 대안 | `woody+conifer+fresh` | 459 | 5 | 예 |
| SQ0132 | v2 ABSTAIN → direct만 | `musky` | 41,154 | 4,010 | 예 |
| SQ0132 | spec §3 예시 | `musky+powdery+vanilla` | 8,007 | 9 | 예 |
| SQ0132 | spec §3 예시 bridge만 | `powdery+vanilla` | 22,600 | 34 | 예 |
| SQ0002 | v2 원본 | `citrus+fresh` | 18,826 | 25 | 예 |
| SQ0002 | 번역 실패 가정 | `citrus` | 59,969 | 17,736 | 예 |

`SQ0073` 의 사용자 표현은 **편백나무**이고 92개 안에 **`conifer`(침엽수)** 가 있다.
글자 그대로 대응하는데 v2 는 `foresty` 를 골랐다.
사전등록 §6.4 의 분류로는 `TARGET_SPACE_LIMITATION` 이 아니라 `MAPPING_FAILURE` 다.

**왜 못 찾았는지도 설명된다.** `foresty` 가 향수 1개라는 것은 우리 데이터 안에만 있는
사실이므로 LLM 이 알 방법이 없다. 측정 기록 1번의 문장이 그대로 적용된다 —
*"이 정보는 LLM 이 구조적으로 알 수 없다."*

## 그래서 원래 질문의 답

**accord 92개로 담을 수 있다. 조건 두 개를 지키면.**

1. **조합으로 쓴다.** 단독 매핑 금지 → `required` 컬럼이 이미 지원한다
2. **코퍼스 지지도로 죽은 accord 를 배제한다** → `corpus_support` 컬럼이 이미 필수다

두 조건 모두 `spec.md` §4.3 의 사전이 이미 하려던 일이다.
**따라서 사전이 accord 만 겨냥하는 설계를 재검토할 필요는 없다.**
canonical note 를 다시 넣지 않아도 된다(노트북 23 의 축소 판단은 유지된다).

## 한계

- **쿼리 12개다.** 노트북 22 의 사전등록 선정분이며 무작위 표본이 아니다.
  "숲 표현 3건이 전부 `foresty` 로 갔다"는 12건 중 3건의 이야기다
- **대안 조합은 검증된 매핑이 아니다.** 검색 개수만 확인했다.
  의미 판정은 B단계의 질문이며 이 노트북은 답하지 않는다
- 계절·시간대 조건을 넣지 않았다 (`spec.md` 제약 1 — 서비스 초기 0건)
- note 조건을 넣지 않았다. `SQ0051` 의 direct note `Peach` 는 표시만 했다
- 점수 식이 검증되지 않았다. strength 합이라는 가장 단순한 형태만 썼다
- 단일 실행이다

## 재현 방법

```bash
cd EDA
export PYTHONIOENCODING=utf-8
# 27_bridge_accord_search_feasibility.ipynb 를 REPORT_ONLY=False 로 실행
# API 호출 없음. 재현 게이트 2개가 먼저 통과해야 진행된다
```

## 관련 자료

- `23_semantic_bridge_accord_only_v2_comparison.csv` — v2 매핑 (입력)
- `22_semantic_bridge_pilot_checkpoint.json` — direct annotation (입력)
- `docs/nlr_engineering_notes.md` 1번 — `foresty` 코퍼스 지지도 문제의 최초 발견
- `docs/nlr_engineering_notes.md` 2번 — 단독 accord 의 변별력 문제 (`머스크 → musky`)
- `docs/spec.md` §4.3 — 사전 스키마의 `corpus_support` · `required`
- `docs/plans/SEMANTIC_BRIDGE_PILOT_PLAN.md` §6.4 — ABSTAIN 원인 분류

# Golden Set Errata 보고서

`13_stage1_golden_set_v1_200.xlsx`에서 발견한 라벨 문제를 기록한다.

**이 문서는 보고서다. 평가 데이터를 수정하지 않았다.**
`AGENTS.md`의 "Do not change evaluation data because a model disagrees with it /
Potential label issues should be reported separately"를 따른다.

- 출처: `evaluation_data/stage1/16_golden_set_quality_audit_reviewed.csv` (QA 60건 판정)
- 판정 방식: AI 1차 초안 + 사람 검토, 단일 평가자
- 작성일: 2026-09-10

---

## 요약

QA 후보 60건 중 **15건**이 `GOLD_ERROR`로 판정됐다. 두 유형이다.

| 유형 | 건수 | 내용 |
|---|---:|---|
| A. `avoid` 오분류 | 13 | 향이 아닌 조건이 `gold_avoid`에 들어감 |
| B. `scent` 누락 | 2 | 명시된 향료가 `gold_scent_preference`에 없음 |

유형 A가 특히 중요하다. **`gold_avoid`가 있는 36건 중 13건(36%)** 이 해당한다.

---

## 유형 A — `avoid`에 향이 아닌 조건이 들어감 (13건)

### 문제

`avoid`는 검색에서 **향 제외 필터**로 쓰인다. accord나 note로 번역할 수 없는 값은
필터가 될 수 없으므로 이 슬롯에 들어가면 안 된다.

아래 13건은 강도·분사 방식·인상에 대한 조건이지 향이 아니다.

| query_id | query_text | 현재 gold_avoid | 작성자 |
|---|---|---|---|
| UQ0010 | 케이크 같으면서도, 너무 느끼하지 않고, 딱 맡았을 때 공주처럼 느껴지는 향수  | `["너무 느끼"]` | 김경린 |
| UQ0016 | 여름에 뿌릴 향수 가지고 싶은데 향기 너무 많이 나면 코 아파서... 안 그런거 | `["향기 너무 많이 나면"]` | 김경린 |
| UQ0020 | 향수 분사 적당히 되는 거 없나? 입자가 너무 작은 건 싫은데. | `["입자가 너무 작은 건"]` | 김경린 |
| UQ0025 | 소개팅할 때 부담스럽지 않으면서 좋은 인상을 줄 수 있는 향수 추천해줘. | `["부담"]` | 김용석 |
| UQ0030 | 사람 많은 곳에서도 너무 강하게 느껴지지 않는 은은한 향수를 추천해줘. | `["강하게"]` | 김용석 |
| UQ0032 | 향수 냄새가 강하면 머리가 아파서 최대한 부드럽고 편안한 향을 찾고 있어. | `["강하면"]` | 김용석 |
| UQ0033 | 내가 20대 후반인데 너무 어려 보이지 않으면서 세련된 향수를 찾고 있어. | `["어려 보이지"]` | 김용석 |
| UQ0056 | 아로마 계열이면 다 좋은데 너무 진한 향 아니고 은은한 게 좋아 | `["너무 진한 향"]` | 송가연 |
| UQ0092 | 향이 너무 세지 않은 향수 추천해줘 | `["향이 너무 세"]` | 김재성 |
| UQ0116 | 달달하지만 너무 느끼하지 않은 향수 추천해줘 | `["느끼"]` | 김재성 |
| UQ0150 | 우디 향 좋아하는데 무겁거나 중후한 건 싫어. 추천 좀. | `["무겁거나","중후한"]` | 미기재 |
| UQ0185 | 산타마리아노벨라 시향했는데 너무 올드하더라. 젊은 느낌으로 추천해줄래? | `["올드"]` | 미기재 |
| UQ0196 | 우디 향 좋아하는데 너무 무겁거나 아저씨 같은 느낌은 싫어. | `["너무 무겁거나","아저씨 같은 느낌"]` | 미기재 |

### 왜 생겼는가 — `avoid`의 정의가 모호했다

처음에는 "`avoid` 예시를 채우려고 만든 문장 때문"이라고 추정했다. **측정해보니 반대였다.**

Golden Set 200건 중 54건은 `source_author`가 비어 있고 `source_no`도 없다.
`gold_avoid` 보유율 37%(기재분 11%), `gold_context` 보유율 3.7%(기재분 28.1%)로
`avoid` 필드를 겨냥해 만든 별도 배치로 보인다.

그런데 오분류는 그쪽에서 나오지 않았다.

| `gold_avoid` 보유 건의 출처 | 건수 | 오분류 | 오분류율 |
|---|---:|---:|---:|
| 팀원이 자연스럽게 쓴 문장 | 16 | 10 | **62%** |
| `avoid` 전용 배치 (미기재) | 20 | 3 | **15%** |

**`avoid` 전용 배치가 오히려 깨끗하다.** 그 배치는 "싫어하는 향"을 의도하고 썼기 때문에
`바닐라는 싫어`, `패출리 들어간 향은 싫어`, `초코 향이면 안돼` 같은 명확한 예시가 나왔다.

반대로 자연스러운 문장에는 **향이 아닌 부정 표현이 섞인다.**

```
"사람 많은 곳에서도 너무 강하게 느껴지지 않는 은은한 향수"      → 강도
"소개팅할 때 부담스럽지 않으면서"                            → 인상
"너무 어려 보이지 않으면서 세련된"                           → 나이
"입자가 너무 작은 건 싫은데"                                → 분사 방식
```

라벨링한 사람은 이것들을 성실하게 `avoid`에 넣었다. **문장에 실제로 있는 부정 표현이기 때문이다.**

즉 원인은 배치도 개인 실수도 아니라 **`avoid` 필드의 정의가 "부정 표현"인지 "회피할 향"인지
명시되지 않았던 것**이다. 자연스러운 문장일수록 향이 아닌 부정 표현이 많으니 오분류가 더 났다.

### 제안

`avoid`에서 제거하고 같은 span을 `gold_additional_requirements`로 옮긴다.
span이 원문의 부분 문자열이므로 `24_korean_scent_domain_lexicon.ipynb` cell 3의
불변식(`gold_avoid`·`gold_additional_requirements` 항목은 `query_text`의 부분 문자열)은 유지된다.

**개별 주의**

- `UQ0185` — `gold_additional_requirements`에 이미 `"산타마리아노벨라 시향했는데 너무 올드"`가 있어
  `올드`를 그대로 옮기면 중복된다. 개별 판단이 필요하다.
- `UQ0056` — `gold_scent_preference`에 `aromatic`, `additional`에 `아로마 계열`이 이미 있다.
  `너무 진한 향`만 옮기면 된다.

---

## 유형 B — 명시된 향료가 `scent`에 없음 (2건)

### 문제

같은 문형인데 라벨이 다르다.

| query_id | query_text | 현재 gold_scent | 현재 gold_additional |
|---|---|---|---|
| UQ0054 | 홍차향 같은 향수도 있나? 근데 너무 음식같은 느낌 안 났으면 좋곘음 | `[]` | `["홍차향"]` |
| UQ0164 | 장미 꽃 향기는 좋은데 인위적인 향기는 아니었으면 좋겠음. 추천 좀 | `[]` | `["장미 꽃 향기"]` |

비교 대상:

| query_id | query_text | gold_scent |
|---|---|---|
| UQ0005 | 난 바닐라 향기가 좋은데. 너무 단 건 싫어. | `["Vanilla"]` |
| UQ0169 | 딸기 향기가 났으면 좋겠어. ... | `["Strawberry"]` |

`바닐라 향기가 좋은데` → `Vanilla`, `딸기 향기가 났으면` → `Strawberry`인데
`장미 꽃 향기는 좋은데`와 `홍차향 같은 향수도 있나`는 `scent`가 비어 있다.
`Rose`와 `Black Tea`는 모두 Fragrantica에 실재하는 note다.

**이 두 건은 LLM이 오히려 맞혔다.** 각각 `Rose`, `black tea`를 `scent`에 넣었는데 0점을 받았다.

### 제안

`gold_scent_preference`에 각각 `Rose`, `Black Tea`를 추가한다.
`gold_additional_requirements`의 `장미 꽃 향기` / `홍차향`은 그대로 둔다 —
`UQ0169`가 `Strawberry`와 `싱싱한 딸기 향기`를 함께 갖고 있는 선례가 있다.

부분 문자열 불변식은 `gold_avoid`와 `gold_additional_requirements`에만 적용되므로
`gold_scent_preference`에 영어 canonical을 넣는 것은 제약에 걸리지 않는다.

---

## 적용했을 때의 영향 (진단용 가정 계산)

유형 A 13건의 `gold_avoid`를 비웠다고 가정하고 LLM 예측을 재채점했다.
노트북 25의 확정 규칙(모든 층 ON, `MAX_EXCESS_TOKENS=1`)을 사용했다.

| | avoid positive micro F1 | 대상 | TP | FP | FN |
|---|---:|---:|---:|---:|---:|
| ① 원래 채점 | 0.000 | 36 | — | — | — |
| ② 채점 규칙만 수정 (노트북 25) | 0.493 | 36 | 17 | 12 | 23 |
| ③ ② + 유형 A 보정 가정 | **0.653** | 23 | 16 | 8 | 9 |

③ 이후 남은 FN 9건 중 **8건이 번역·의역**이고, 예측이 비어 있는 것은
`UQ0170` (`남자 향수 냄새`) **1건**뿐이다.

즉 "LLM avoid F1 0% = 부정 표현을 이해하지 못함"이 아니라

```
36건 중
  13건  정답 라벨이 잘못됨
  22건  맞혔는데 표기가 달라 0점
   1건  진짜로 못함
```

---

## 재발 방지 — 라벨링 가이드 개정안

`16_golden_set_quality_audit_guide.md`와 향후 annotation 가이드에 다음을 명문화한다.

### `gold_avoid`에 넣는 것

> **accord 또는 note로 번역할 수 있는 것만 넣는다.**
> `avoid`는 검색에서 향 제외 필터로 사용되므로, 번역할 수 없는 값은 필터가 될 수 없다.

| 넣는다 | 넣지 않는다 (→ `additional`) |
|---|---|
| 향료 이름 — 바닐라, 패출리, 복숭아, 바질 | 강도 — 강한, 진한, 센, 향기 많이 나는 |
| 향 계열 — 우디, 시트러스, 머스크, 인센스 | 무게·질감 — 무거운, 중후한, 느끼한 |
| 향 성격(accord 존재) — 달콤한, 파우더리, 비누 냄새 | 인상·나이 — 올드한, 어려 보이는, 부담스러운 |
| 특정 제품 — 조말론 블랙베리 | 분사 방식 — 입자가 작은 |

판단이 어려우면 **"이 값을 accord 목록 92개나 note 목록에서 찾을 수 있는가"** 로 묻는다.
찾을 수 없으면 `additional`이다.

### `gold_scent_preference`에 넣는 것

> 사용자가 **명시적으로 언급한 향료·향 계열**은 영어 canonical 표기로 넣는다.
> 같은 문형(`X 향기가 좋은데`, `X 향이 났으면`)은 항상 같게 처리한다.

감각 형용사(`달콤한`, `포근한`)는 향으로 바꾸지 않는다. 이건 현행 Stage 1 정책과 같다.

### 자연스러운 문장일수록 `avoid` 판정에 주의한다

위 오분류율(62% vs 15%)이 보여주는 것은 **자연스러운 문장에 부정 표현이 더 많이
섞인다**는 것이다. "강하지 않게", "부담스럽지 않게" 같은 표현은 문장에 실제로 있으므로
라벨링할 때 눈에 띄고, 기준이 없으면 `avoid`로 들어간다.

따라서 실사용 데이터(설문 155건 등)를 라벨링할 때 이 문제가 **더 자주** 나올 것으로 예상해야 한다.
`avoid` 후보를 발견할 때마다 위 판별 질문을 적용한다.

> 이 값을 accord 목록 92개나 note 목록에서 찾을 수 있는가?

---

## 적용하지 않은 이유

`AGENTS.md`에 따라 평가 데이터를 임의로 수정하지 않는다.

> Do not change evaluation data because a model disagrees with it.
> Potential label issues should be reported separately.

적용하려면 다음이 필요하다.

1. 팀이 위 라벨링 기준에 합의
2. `13_stage1_golden_set_v1_200.xlsx`를 v1.1로 개정하고 Audit 시트에 변경 이력 기록
3. 영향받는 산출물 재생성 — `13`·`14`·`15` 평가 파일,
   `24_korean_scent_domain_lexicon.ipynb`의 `korean_scent_lexicon_v0_1.csv`
   (이 사전은 gold span에서 직접 추출됐다)
4. `15_stage1_llm_evaluation.ipynb`와 `16_...ipynb`의 SHA-256 guard 갱신

**개정 없이 현행 유지도 선택지다.** 그 경우 이 문서를 근거로
"avoid 지표는 라벨 문제 13건을 포함한다"를 항상 함께 보고해야 한다.

---

## 재현 방법

```bash
cd EDA
./venv/Scripts/python.exe - <<'PY'
import pandas as pd
qa = pd.read_csv('evaluation_data/stage1/16_golden_set_quality_audit_reviewed.csv',
                 keep_default_na=False, dtype=str)
err = qa[qa.manual_decision == 'GOLD_ERROR']
print(err.manual_issue_type.value_counts().to_string())
print(err[['query_id', 'gold_avoid', 'manual_comment']].to_string(index=False))
PY
```

③의 재채점은 노트북 25의 규칙 함수를 사용한다. API 호출은 없다.

---

## 관련 자료

- `evaluation_data/stage1/16_golden_set_quality_audit_reviewed.csv` — 판정 원본 60건
- `analysis_outputs/16_golden_set_quality_audit_guide.md` — 기존 판정 가이드
- `analysis_outputs/25_stage1_rescoring_match_detail.csv` — 항목 단위 매칭 근거
- `docs/DECISIONS.md` — 자연어 추천 의사결정 기록

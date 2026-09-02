# Stage 1 Extended Rule Evaluation

## 실험 목적

일반화 가능한 명시적 Rule만 확장했을 때 실제 사용자 자연어 200개를 어디까지 구조화할 수 있는지 측정했다.

## Extended Rule 범위

- Gender
- Intensity
- Longevity
- Avoid
- Direct Scent 일부

감성·장면·직업·상황 표현과 Additional Requirements는 임의 Feature로 변환하지 않았다.

## Baseline 비교

| Metric | Current Rule | Extended Rule | Difference |
|---|---:|---:|---:|
| Overall Exact Match | 1.50% | 4.50% | +3.00%p |
| Coverage (13번 scent/context 정의) | 15.50% | 33.00% | +17.50%p |
| Scent Positive-only Micro F1 | 45.90% | 53.12% | +7.22%p |
| Gender Positive-only Micro F1 | 0.00% | 91.89% | +91.89%p |
| Intensity Positive-only Accuracy | 0.00% | 58.33% | +58.33%p |
| Longevity Positive-only Accuracy | 0.00% | 83.33% | +83.33%p |
| Avoid Positive-only Micro F1 | 0.00% | 13.79% | +13.79%p |

Difference는 Extended Rule - Current Rule이며 `p`는 퍼센트포인트를 뜻한다.

## 주요 개선

- Overall Exact Match: 1.50% → 4.50%
- FIXED Query: 6개
- Gender Rule trigger: 39개
- Intensity Rule trigger: 8개
- Longevity Rule trigger: 5개
- Avoid Rule trigger: 21개

## 주요 Regression

- REGRESSED Query: 0개

- 없음

### Field별 변화

| Field | Improved | Regressed | Same Correct | Same Wrong |
|---|---:|---:|---:|---:|
| scent | 5 | 1 | 167 | 27 |
| gender | 31 | 5 | 159 | 5 |
| intensity | 7 | 1 | 187 | 5 |
| longevity | 5 | 0 | 194 | 1 |
| avoid | 3 | 4 | 160 | 33 |

## 오류 변화

| Error | Before | After | Difference |
|---|---:|---:|---:|
| MISSED_GENDER | 36 | 5 | -31 |
| MISSED_AVOID | 36 | 33 | -3 |
| MISSED_SCENT | 25 | 23 | -2 |
| MISSED_INTENSITY | 12 | 5 | -7 |
| MISSED_LONGEVITY | 6 | 1 | -5 |
| MISSED_ADDITIONAL | 170 | 170 | +0 |
| EXTRA_SCENT | 4 | 3 | -1 |
| WRONG_SCENT | 3 | 2 | -1 |

## Rule로 해결되지 않은 영역

- MISSED_ADDITIONAL은 170개 남았다.
- Additional Requirements를 점수 개선을 위해 감성·장면·가격·나이 등의 임의 Rule로 변환하지 않았다.
- Trigger가 작동한 Query의 정답 여부는 `14_rule_trigger_diagnostics.csv`에서 Rule별로 분리했다.

## 결론

Rule 확장으로 해결된 영역과 여전히 해결되지 않은 영역을 분리했다. 이 결과만으로 특정 후속 방식을 확정하지 않으며, 같은 평가 정의와 별도 외부 Query를 사용한 비교가 필요하다.

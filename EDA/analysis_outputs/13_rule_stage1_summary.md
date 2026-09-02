# Stage 1 Rule Baseline Evaluation

## 실험 목적

기존 11번 Rule Parser를 변경하지 않고, 실제 사용자 자연어 200개 Golden Set에서 Stage 1 Query Understanding 성능을 측정했다.

## 데이터

- Golden Set: 200 Queries
- Golden Set Version: stage1-v1.0
- 고유 query_id: 200개
- 고유 query_text: 200개

## Baseline

- 기존 11번 Rule Parser 및 고정된 11번 Rule Lexicon 사용
- 새로운 Rule, Lexicon, 동의어 매핑 추가 없음
- LLM, embedding, 외부 API, 향수 ranking 사용 없음

## 주요 결과

- 전체 Exact Match: 3/200 (1.50%)
- Parser 오류: 0개
- 하나 이상의 조건을 예측한 Coverage: 15.50%

## Field별 결과

- scent_preference Exact Match: 84.00%
- context Exact Match: 80.50%
- performance Exact Match: 91.50%
- avoid Exact Match: 82.00%
- additional_requirements Exact Match: 15.00%
- scent Positive-only Micro F1: 45.90% (Gold positive 39개)

## 주요 실패 유형

- MISSED_ADDITIONAL: 170개
- MISSED_GENDER: 36개
- MISSED_AVOID: 36개
- MISSED_SCENT: 25개
- MISSED_INTENSITY: 12개
- MISSED_LONGEVITY: 6개
- EXTRA_SCENT: 4개
- WRONG_SCENT: 3개

## 관찰

- 현재 Parser의 출력 구조는 scent, season, daypart를 지원하고 gender, performance, avoid, additional_requirements는 지원하지 않는다.
- 지원하지 않는 필드의 전체 Exact Match에는 Gold와 Prediction이 모두 빈 Query가 포함되므로, Positive-only 지표를 함께 해석해야 한다.
- Coverage는 값을 추출했는지만 나타내며, 추출한 값의 정답 여부는 Precision/Recall/F1 및 Exact Match로 별도 확인해야 한다.

## 결론

이 결과는 Golden Set을 보고 규칙을 보완하지 않은 고정 Baseline이다. 이후 확장 Rule Parser와 LLM Parser는 동일한 Golden Set, 동일한 normalization, 동일한 metric으로 비교해야 한다.

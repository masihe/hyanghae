# Stage 1 LLM Evaluation

## 실험 목적

동일한 실제 사용자 자연어 200개에서 Current Rule, Extended Rule, GMS `gpt-5.4-nano`의 Stage 1 구조화 성능을 같은 정의로 비교했다. 향수 Ranking은 실행하지 않았다.

## 실험 환경

- Gateway: SSAFY GMS
- Model: gpt-5.4-nano
- Prompt Version: stage1_llm_v1
- Prompt SHA256: 4f0a368d98b413384935d4bb54d36d19b60895904d16733d526a1a82737cc493
- Golden Set: 200개
- Run Timestamp: 2026-09-01T00:32:31+09:00
- Retry: 최초 1회 + 최대 2회
- FORCE_RERUN: False

API Key는 기록하지 않았다.

## API 안정성

- 성공 Query: 199/200
- 실패 Query: 1/200
- First-attempt success rate: 99.00%
- Retry Query / Total Retry: 2 / 3
- API / JSON / Validation failure attempts: 0 / 0 / 4
- Mean / Median / p95 latency: 1.960s / 1.739s / 3.194s
- Prompt / Completion / Total tokens: 127,493 / 17,840 / 145,333

## LLM 성능

- Overall Exact Match: 6.00%
- Coverage: 41.50%
- Scent Positive F1: 64.20%
- Additional Positive F1: 12.36%

## Current Rule vs Extended Rule vs LLM

| Metric | Current Rule | Extended Rule | LLM |
|---|---:|---:|---:|
| Overall Exact Match | 1.50% | 4.50% | 6.00% |
| Coverage | 15.50% | 33.00% | 41.50% |
| Scent Positive F1 | 45.90% | 53.12% | 64.20% |
| Gender Positive F1 | 0.00% | 91.89% | 91.43% |
| Intensity Positive Accuracy | 0.00% | 58.33% | 75.00% |
| Longevity Positive Accuracy | 0.00% | 83.33% | 100.00% |
| Avoid Positive F1 | 0.00% | 13.79% | 0.00% |
| Additional Positive F1 | 0.00% | 0.00% | 12.36% |

## Field별 비교

- Scent Positive F1: 64.20%
- Gender Positive F1: 91.43%
- Intensity Positive Accuracy: 75.00%
- Longevity Positive Accuracy: 100.00%
- Avoid Positive F1: 0.00%
- Additional Positive F1: 12.36%

## 주요 개선

- LLM_FIXED: 8개
- Extended의 MISSED_ADDITIONAL 170개 대비 LLM은 163개였다.

## LLM이 더 나빴던 Query

LLM_REGRESSED: 5개

- UQ0005: 난 바닐라 향기가 좋은데. 너무 단 건 싫어.
- UQ0015: 여름에 뿌릴 향수 추천 좀.
- UQ0087: 가을에 잘 어울리는 우디 향수 추천해줘
- UQ0111: 남자가 쓰기 좋은 파우더리 향수 추천해줘
- UQ0140: 중성적인 향수에는 뭐가 있을까?

## 주요 오류

- MISSED_ADDITIONAL: 163개
- MISSED_AVOID: 36개
- EXTRA_ADDITIONAL: 18개
- MISSED_SCENT: 12개
- EXTRA_SCENT: 10개
- WRONG_SCENT: 8개
- EXTRA_DAYPART: 7개
- MISSED_GENDER: 4개
- EXTRA_SEASON: 4개
- MISSED_INTENSITY: 3개

`semantic_over_inference_candidate`는 자동 확정 판정이 아니라 사람이 검토할 후보 표시다.

## 비용 / 운영 관점

응답이 제공한 실제 Token Usage만 합산했다. 비용 단가가 제공되지 않아 금액 비용은 계산하지 않았다. Median은 가운데 Query 완료시간, p95는 95%의 Query가 그 시간 이하에 완료됐다는 뜻이다. Checkpoint와 resume으로 성공 Query 재호출을 방지한다.

## 결론

LLM의 상대 성능과 운영 특성은 위 실제 측정값으로 판단해야 한다. 특정 최종 방식을 결과와 무관하게 미리 확정하지 않는다.

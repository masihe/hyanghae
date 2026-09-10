# Stage 1 Rescoring Rule v2

## 질문

Stage 1의 `avoid` micro-F1 0.000과 `additional` 0.118 중 얼마가 채점 규칙의 문제인가.

## 방법

기존 Prediction을 그대로 사용하고 채점 규칙만 층으로 분해했다. **API 호출 없음. 모델 재실행 없음.**
Notebook 13/14/15/16과 Golden Set은 수정하지 않았다.

- 규칙 버전: `stage1_rescore_v2`
- `MAX_EXCESS_TOKENS = 1` (사전 등록)
- 별칭 항목 40개 (그중 검증 불가한 `SENSORY` tier 5개)

## 재현 게이트

모든 층을 끈 상태에서 published 지표 **174개를 대조해 불일치 0개**.
새 채점기는 기존 채점기의 상위 집합이다.

## 정규화기 대조

13/14번은 NFKC를 적용하고 15번은 하지 않는다. 라벨 문자열 639개 중
**차이를 만드는 것은 0개**였다.

## Positive-only micro F1 (전 → 후)

| field | rule_before | rule_after | extended_rule_before | extended_rule_after | llm_before | llm_after |
|---|---|---|---|---|---|---|
| avoid | 0.0000 | 0.0000 | 0.1379 | 0.3103 | 0.0000 | 0.4928 |
| additional | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.1236 | 0.3371 |
| scent | 0.4590 | 0.4590 | 0.5312 | 0.5312 | 0.6420 | 0.7160 |

## 매칭 알고리즘

greedy 1:1 매칭이 최대 매칭과 다른 경우 **0건**.

## 한계

- 이 숫자는 채점 규칙 변경분이다. **모델 성능이 좋아진 것이 아니다.**
- `SENSORY` tier는 Fragrantica 어휘로 검증할 수 없다. 기여도를 별도 행으로 보고했다.
- 1:1 매칭은 하나의 prediction이 여러 gold를 덮는 경우 recall을 구조적으로 제한한다.
- `rule`과 `extended_rule`은 `additional`을 200/200 빈 값으로 예측하므로 어떤 규칙에서도 0이다.
- 별칭표는 Golden Set 200개를 보고 골랐다. Unseen 평가에는 사용할 수 없다.

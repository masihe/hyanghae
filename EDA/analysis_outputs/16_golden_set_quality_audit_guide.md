# Stage 1 Golden Set Quality Audit

## 목적

Golden Set을 재구축하기 위한 작업이 아니라, 일부 낮은 평가가 Annotation 또는 표현 방식 문제에서 발생했는지 빠르게 확인하기 위한 표본 QA다.

## 검토 대상

- LLM_REGRESSED: 5개
- Avoid mismatch: 36개
- Additional sample: 20개
- 중복 제거 후 최종 QA Query: 60개

## 판단 기준

### GOLD_OK

현재 Gold가 Annotation 원칙에 맞고 Prediction이 틀린 경우

### SURFACE_MISMATCH

핵심 의미는 유사해 보이지만 표현 형식 차이 때문에 Strict 평가에서 실패한 경우

### GOLD_ERROR

현재 Gold 자체가 명확하게 잘못된 경우

### UNCERTAIN

판단이 어려운 경우

## manual_issue_type 후보

- NONE
- AVOID_SPAN: 부정 범위 표현 차이
- ADDITIONAL_SEGMENTATION: 표현 분할 방식 차이
- WORDING_VARIATION: 문자열 표현 차이
- SCENT_CANONICALIZATION: 향 표준명 표현 문제
- CONTEXT_LABEL: Gender / Season / Daypart Annotation 문제
- PERFORMANCE_LABEL: Intensity / Longevity Annotation 문제
- OTHER_GOLD_ERROR
- UNCERTAIN

## 중요 원칙

- LLM Prediction을 정답으로 간주하지 않는다.
- 모델 결과에 맞춰 Gold를 수정하지 않는다.
- 명백한 반복 패턴이 발견될 때만 후속 Golden Set 개정 필요성을 검토한다.
- `manual_decision`, `manual_issue_type`, `manual_comment`는 사람이 입력한다.
- 자동 정규화 일치는 lowercase, strip, 중복 제거, 순서 무시만 반영하며 의미 동일 판정이 아니다.

## 검토 순서

1. `selection_reason`과 Query 원문을 확인한다.
2. Gold, Extended, LLM 값을 나란히 비교한다.
3. `manual_decision`에 GOLD_OK / SURFACE_MISMATCH / GOLD_ERROR / UNCERTAIN 중 하나를 입력한다.
4. `manual_issue_type`을 위 후보에서 선택하고 필요하면 `manual_comment`를 작성한다.

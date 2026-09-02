# Survey Natural Language Queries

## Source

2026년 8월 향수 추천 사용자 설문조사

원본:

`data/survey/raw/향수 설문조사.xlsx`

추출 문항:

> AI에게 향수를 추천받는다고 생각하고, 실제로 질문하듯 원하는 향수를 자유롭게 작성해주세요.

## Purpose

향수 자연어 추천 시스템의 개발 및 평가에 활용하기 위해 설문의 자연어 자유응답을 별도의 데이터셋으로 보존한다.

## Files

### survey_nlp_queries_raw.csv

설문 자연어 응답을 원문에 가깝게 보존한 파일이다.

원본 문장을 수정하지 않는다. `source_row`는 원본 Excel의 실제 행 번호다.

### survey_nlp_queries_candidates.csv

자연어 처리 실험에서 사용할 후보 Query 데이터다.

각 Query에 SQ 형식의 ID를 부여했으며, 현재는 Annotation 및 Dataset Split을 수행하지 않은 상태다. 완전히 동일한 문장도 삭제하지 않았다.

## Current Status

`review_status = UNREVIEWED`

`split_status = UNASSIGNED`

현재 기존 Stage 1 Golden Set과 병합하지 않는다.

향후 필요에 따라 다음 용도로 사용할 수 있다.

- Rule Parser 개발
- LLM Parser 개발
- Annotation
- Validation
- External Holdout

## Extraction Summary

- Survey response rows: 155
- Natural language response cells: 155
- Blank responses removed from candidates: 0
- Candidate queries: 155
- Exact duplicate extra rows: 5
- Rows belonging to duplicate groups: 8
- Unique query texts: 150

## Data Handling Rules

- 원본 Excel과 기존 Golden Set을 수정하지 않는다.
- 개인정보 Column을 추출 파일에 포함하지 않는다.
- Query 의미 분석, Annotation, Feature Mapping을 수행하지 않는다.
- Candidate에는 앞뒤 공백 제거와 연속 공백·줄바꿈 정리만 적용한다.
- 중복 Query는 원본 데이터의 특성으로 보고 그대로 보존한다.

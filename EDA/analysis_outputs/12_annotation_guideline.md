# Query Understanding Annotation Guideline

## 목적

이 데이터는 자연어 Query를 Accord, Note, Season, Daypart, unresolved expression으로 구조화하는 Stage 1만 평가합니다.
향수 추천 결과나 Ranking의 정답을 만들지 않습니다.

## Evaluation Leakage 방지

Query 작성자는 11_rule_lexicon.csv, 11차 Parser 코드, Rule 목록, 11_parser_test_results.csv를 보지 않습니다.
기존 Synthetic Query를 복사하거나 변형해 새 Query로 사용하지 않습니다.

## 작업 순서

1. 블라인드 Query 작성자가 12_query_annotation_template.csv의 query_text만 자유롭게 작성합니다.
2. Annotator는 직접 언급된 Feature와 unresolved 표현을 JSON array 형식으로 기록합니다.
3. 두 명 이상이 독립적으로 작업할 때는 12_query_annotations_long.csv에 실제 annotator_id와 label을 추가합니다.
4. Agreement를 계산하되 자동 다수결로 Gold를 확정하지 않습니다.
5. 사람이 의견 차이를 검토한 뒤 12_query_goldset.csv를 작성하고 READY / MANUAL_REVIEW / EXCLUDED를 표시합니다.

## Query Type

- DIRECT: Accord 또는 Note를 직접 언급
- CONTEXT: Season 또는 Daypart를 명시
- SENSORY: 감각적 형용사 중심
- SCENE_ABSTRACT: 장면 또는 분위기 중심
- MIXED: 직접 해석 가능한 표현과 어려운 표현이 함께 있음

## Label 원칙

- 사용자가 직접 말한 구조 Feature만 Gold로 기록합니다.
- 계절과 day/night는 문장에 명시된 경우만 기록합니다.
- 데이트, 출근, 파티를 day/night로 변환하지 않습니다.
- 비 오는 숲을 woody, green 등으로 변환하지 않습니다.
- Accord와 Note가 모두 가능한 표현은 annotator_comment에 모호성을 기록하고 Manual Review로 보냅니다.

## JSON array 형식

- 하나: ["citrus"]
- 복수: ["citrus", "woody"]
- 없음: []
- 빈 문자열은 아직 Annotation하지 않았다는 뜻이므로 []와 다릅니다.

## Resolution Status

- FULLY_RESOLVABLE: 구조 Feature가 있고 unresolved 표현이 없음
- PARTIALLY_RESOLVABLE: 구조 Feature와 unresolved 표현이 모두 있음
- UNRESOLVABLE: 구조 Feature가 없고 unresolved 표현이 있음

## Confidence

- HIGH: 직접 대응이 명확함
- MEDIUM: Accord/Note 선택 등 제한적인 모호성이 있음
- LOW: 표현 범위 또는 label 판단이 매우 애매함

## 예시

- 여름에 쓰기 좋은 citrus 향 → accords=["citrus"], seasons=["summer"], unresolved=[]
- 여름에 쓰기 좋은 상큼한 향 → seasons=["summer"], unresolved=["상큼한"]
- 비 오는 숲 같은 향 → 모든 Feature=[], unresolved=["비 오는 숲"]
- 데이트할 때 좋은 향 → 모든 Feature=[], unresolved=["데이트할 때"]

## Gold 확정

Agreement가 높아도 완전 자동 다수결로 확정하지 않습니다. Adjudicator가 원문과 모든 Annotation을 확인한 뒤
최종 label을 기록합니다. 낮은 Agreement, 낮은 confidence, 애매한 Direct 표현은 반드시 Manual Review합니다.

## Stage 2 금지

이 Query Understanding Goldset에는 정답 향수 ID나 추천 적합도를 넣지 않습니다. 추천 Golden Set은 별도의
독립적인 Human relevance 평가로 구축해야 합니다.

## Circular Evaluation 방지

현재 DB Feature를 이용해 추천 향수의 relevance 정답까지 자동 생성하지 않습니다.
모델이 쓰는 기준으로 정답까지 만들면 같은 기준을 다시 맞히는 Circular Evaluation이 됩니다.

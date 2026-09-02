# Semantic Bridge Pilot Plan

## 1. 결론

Semantic Bridge가 해결해야 하는 문제는 모든 `additional_requirements`를 향으로 바꾸는 것이 아니다. 정확한 범위는 다음과 같다.

> Stage 1이 직접 Accord, Note, Season, Daypart로 확정하지 못한 표현 중 **향을 묘사하려는 감각·재질·환경 장면 표현**만 골라, 실제 Fragrantica 검색에 사용할 수 있는 제한된 Accord 또는 Canonical Note 후보로 변환할 수 있는지 검증한다.

현재 프로젝트는 검색 가능한 feature vocabulary와 Retrieval은 갖고 있지만, `비 온 뒤의 숲`, `깨끗한 빨래`, `포근한 이불` 같은 표현의 정답 mapping은 갖고 있지 않다. IFRA와 v0.3도 ingredient/descriptor/concept 관계를 제공할 뿐 한국어 장면 표현의 의미 label은 제공하지 않는다. 따라서 기존 데이터 관계만으로 장면 mapping을 자동 생성하면 근거 없는 scent inference가 된다.

가장 작은 타당한 Pilot은 다음과 같다.

1. 기존 survey에서 **12개 Query**만 고정한다.
2. 6개는 indirect 표현만으로 향을 찾는 Query, 6개는 direct Accord/Note가 있으면서 indirect 표현이 추가된 Query로 구성한다.
3. 별도 학습이나 ontology 구축 없이, 고정된 한 LLM을 **candidate proposer**로만 사용한다.
4. 출력 대상은 기존 자산에서 만든 닫힌 집합인 **Accord 92개 + Stage 20 strict 기준 Canonical Note concept 178개**로 제한한다.
5. LLM 제안을 향 지식의 사실로 간주하지 않고, vocabulary·relation·canonicalization 규칙으로 자동 검증한다.
6. 검증된 target만 기존 11번 Retrieval 입력으로 넣는다. Note는 21번 원칙에 따라 `CANONICAL`/`SAME_CONCEPT` raw Note로만 확장한다.
7. 동일 Query에서 **Direct-only Baseline**과 **Direct + Semantic Bridge**를 비교하고, 두 명의 사람이 concept 적합성과 추천 결과를 블라인드 평가한다.

이 Pilot의 목적은 완성된 Bridge 정확도를 주장하는 것이 아니라 다음 두 질문에 답하는 것이다.

- 닫힌 기존 향 vocabulary 안에서 indirect 표현을 사람이 납득할 만한 concept 후보로 제안할 수 있는가?
- 그 후보를 고정된 Retrieval에 추가했을 때 direct 조건만 사용한 결과보다 실제 Query 적합도가 좋아지는가?

이번 계획 작성 중에는 LLM/API 호출, Notebook 생성, 데이터 수정, 새 mapping 생성, Retrieval 실행을 하지 않는다.

## 2. 조사한 기존 자산

### 2.1 자연어와 데이터 feature 경계

`10_query_feature_bridge.ipynb`와 산출물은 이미 현재 문제의 경계를 명확히 나눴다.

| 자산 | 실제 내용 | Pilot에서의 역할 |
| --- | --- | --- |
| `10_query_feature_bridge.csv` | Level A 2,621, B 7,360, C 550, D 13 | Direct/data/context 관계와 외부 의미 해석을 분리하는 기준 |
| `10_accord_dictionary.csv` | Accord 92개와 perfume coverage/strength | 닫힌 Accord target vocabulary |
| `10_note_dictionary.csv` | Raw Note 2,523개와 frequency/IDF | 검색 가능성과 frequency 확인 |
| `10_accord_context_profile.csv` | Accord별 대표 Note와 Season/Daypart profile | 결과 설명용 보조 정보. 장면 mapping 정답으로 사용하지 않음 |
| `10_external_mapping_inventory.csv` | 포근한, 차가운, 깨끗한, 비 오는 숲, 휴양지, 빨래, 이불 등 13개가 `EXTERNAL_MAPPING_REQUIRED` | Pilot 대상 표현의 출발점 |

10번은 `비 오는 숲`, `휴양지`, `빨래`, `이불` 등에 점수나 임의 feature를 부여하지 않았다. 이 판단은 유지한다.

### 2.2 기존 Query Retrieval

`11_rule_based_query_retrieval_baseline.ipynb`는 다음 입력을 이미 처리한다.

- 명시적 Accord
- 명시적 Note
- Season
- Daypart

점수는 Accord strength, Note presence, reliable Season share, reliable Daypart share를 category별로 계산한 뒤, 사용 가능한 category 평균에 evidence coverage를 곱한다. 해결된 feature가 하나도 없으면 Retrieval하지 않는다.

Pilot에서는 이 점수 함수를 고정한 채 Bridge target을 Accord/Note category에 추가한다. 새 similarity 함수, weight tuning, candidate pool 탐색은 하지 않는다. 이는 Semantic mapping의 효과와 Retrieval 변경 효과를 섞지 않기 위해서다.

11번 synthetic parser의 100%는 구현 확인일 뿐 실제 추천 relevance의 근거가 아니다. 기존 결론대로 사람의 Query-to-perfume 평가가 필요하다.

### 2.3 Stage 1 결과

- 200개 Golden Set 중 `gold_additional_requirements`가 비어 있지 않은 Query는 170개다.
- Current Rule Overall Exact Match는 1.5%, Extended Rule은 4.5%, LLM은 6.0%였다.
- LLM의 Additional Positive F1은 12.36%였다.
- 16번의 60개 QA 후보는 아직 수동 판정되지 않았다.

Stage 1 Golden Set은 direct feature와 추가 요구를 분리하는 schema와 실제 표현 예시를 제공한다. 예를 들어 `UQ0001`은 `비가 온 뒤`, `숲`을 additional requirements로 보존했다.

하지만 이 Golden Set에는 additional phrase를 어떤 Accord/Note로 바꿔야 하는지에 대한 label이나 정답 향수 ID가 없다. 따라서 기존 Golden Set을 Semantic Bridge Ground Truth로 사용하거나, Bridge 결과에 맞춰 label을 수정하면 안 된다.

Pilot에서는 Stage 1 전체 성능을 다시 평가하지 않는다. Bridge 입력 phrase와 direct/context 조건을 사람이 사전에 분리해 고정하여 Stage 1 오류가 Bridge 평가에 섞이지 않게 한다.

### 2.4 향 지식과 canonicalization

| 자산 | 실제 상태 | 사용할 수 있는 것 | 사용할 수 없는 것 |
| --- | --- | --- | --- |
| `17_note_ifra_matching.csv` | Raw Note 2,523개 strict matching | 실제 Note의 IFRA strict 상태 확인 | 한국어 장면 의미 추론 |
| `17_accord_ifra_matching.csv` | Accord 92개 IFRA match 상태 | Accord의 descriptor 존재 확인 | 장면→Accord 정답 생성 |
| `17_ifra_descriptor_edges.csv` | 908개 primary-secondary relation | target 설명과 사후 진단 | phrase mapping Ground Truth |
| `scent_term_dictionary_v0.3.csv` | 197개: SAME_CONCEPT 26, FAMILY 49, RELATED 7, UNRESOLVED 115 | relation 구분과 strict concept 검증 | FAMILY/RELATED의 synonym 처리 |
| `scent_term_evidence_v0.3.csv` | 213개 공식 근거 record | 제안 target의 기존 provenance 확인 | LLM 제안을 공식 사실로 승격 |
| `fragrantica_note_canonical_map_v1.csv` | Raw 2,523 → Canonical 2,492; SAME_CONCEPT 48, REVIEW 7, NOT_SAME 7 | canonical 비교와 안전한 raw alias 검색 확장 | REVIEW/NOT_SAME 자동 merge |

21번에서 Stage 20 strict matched raw Note 185개는 canonical 기준 178개 concept로 정리됐다. 첫 Pilot은 Note 전체 2,492개가 아니라 이 178개만 allowed Note target으로 사용한다. 이는 의미 coverage를 최대화하려는 선택이 아니라, 현재 공식 근거와 canonicalization이 모두 있는 작은 target space에서 접근 가능성을 먼저 보는 선택이다.

### 2.5 실제 Query 후보

`data/survey/processed/survey_nlp_queries_candidates.csv`에는 개인정보를 제외한 실제 survey Query 155개가 있다. 모두 `UNREVIEWED`/`UNASSIGNED`이며 기존 Notebook에서 아직 평가 입력으로 사용되지 않았다. 이번 Pilot의 12개는 LLM 실행 전에 `evaluation_data/semantic_bridge/22_selected_pilot_queries.csv`에 사람이 사전 고정했으며, 원문은 이 파일의 `query_id`를 155개 survey candidate와 결합해 사용한다.

실제 파일에서 확인한 관련 예시는 다음과 같다.

- `SQ0061`: 비 온 뒤의 숲의 냄새
- `SQ0032`: 여름에 어울리는 숲 속에 온 듯한 향
- `SQ0136`: 강하지 않은 빨래향 같이 자연스러운 향
- `SQ0105`: 따뜻한 햇살을 받으며 침대 위에 누워있는 듯한 느낌
- `SQ0012`: 샤워하고 나온 듯한 따뜻하고 포근한 느낌
- `SQ0058`: 여름 바다가 생각나는 시원한 향
- `SQ0071`: 겨울 아침의 차갑고 상쾌한 향 + Musk/Woody direct 조건
- `SQ0051`: 세탁된 Cotton 같은 깨끗한 공기향 + Peach direct 조건
- `SQ0073`: 깨끗하고 시원한 자연 느낌 + Woody/Floral direct 조건

이 Query들은 기존 200개 개발 평가와 분리된 Pilot 후보로 적절하다. 다만 아직 annotation되지 않았으므로 자동 holdout이나 Ground Truth로 간주하지 않는다.

### 2.6 Retrieval 실험의 재사용 범위

04·05·07·09는 다음 설계 근거를 제공한다.

- Accord+Note가 Popularity보다 유효했다.
- Note IDF는 결합 시 유지 후보였다.
- Note tier는 별도 가치가 없었다.
- reliable Season/Daypart는 추가 ranking signal이었다.
- score calibration은 RAW보다 낫지 않았다.
- Final Holdout 300개는 사용되지 않았다.

그러나 04~09는 perfume seed와 `reminds_me_of` implicit relation을 평가한 Perfume-to-Perfume Retrieval이다. indirect phrase에서 seed perfume을 새로 만드는 것은 또 다른 설계가 된다. 따라서 첫 Semantic Bridge Pilot은 자연어 feature를 직접 받는 11번 Query Retrieval을 사용한다. 04~09의 전체 score를 억지로 재조합하지 않는다.

## 3. Pilot에서 검증할 정확한 문제

### 3.1 입력 범위

Pilot 입력은 Query 전체가 아니라 사전에 분리된 다음 세 부분이다.

```text
query_text
direct_features: 기존 Accord / Note / Season / Daypart 조건
bridge_phrase: 향을 묘사하려는 indirect 감각·재질·환경 장면 표현
```

원문은 그대로 보존하되, Bridge 평가에는 direct scent/context와 bridge phrase만 포함한 `bridge_evaluation_text`를 별도로 고정한다. 가격·성별·강도·회피·브랜드 같은 다른 요구는 기록만 하고 이번 scent-semantic relevance 판정에서는 숨긴다. 11번이 처리하지 않는 조건 때문에 Bridge 결과가 감점되는 것을 막아 mapping과 Retrieval 결합만 분리해 보기 위한 조치다.

예를 들면 다음처럼 분리한다.

```text
query_text: 여름에 어울리는 숲 속에 온 듯한 향
direct_features: season=[summer]
bridge_phrase: 숲 속에 온 듯한 향
```

이 분리는 모델 결과를 본 뒤 수정하지 않는다.

### 3.2 첫 Pilot에 포함할 표현

가장 적절한 시작 범위는 향과 연결하려는 의도가 비교적 분명한 세 유형이다.

1. **자연 환경/냄새 장면**: 비 온 뒤의 숲, 숲 속, 여름 바다
2. **세정·섬유·생활 냄새**: 샤워 후, 깨끗한 빨래, 세탁된 Cotton
3. **온도·촉감이 결합된 분위기**: 차갑고 상쾌한 겨울 아침, 따뜻하고 포근한 침대

첫 Pilot에서는 다음을 제외한다.

- 고급스러운, 섹시한, 도시적인, 금융맨 같은 사회적 이미지
- 가격, 연령, 직업, 브랜드, 구매 장소
- 소개팅, 면접, 회사처럼 향 의미보다 사용 상황이 중심인 표현
- 특정 향수와 비슷한 향 요청
- 부정/회피 표현 자체의 Semantic 변환
- 너무 넓어 합의 가능한 scent concept가 없는 표현

이 제외는 해당 요구가 중요하지 않다는 뜻이 아니다. 현재 질문인 “indirect olfactory imagery를 검색 신호로 바꿀 수 있는가”를 다른 추천 조건과 분리하기 위한 것이다.

## 4. Pilot Query 구성

총 12개면 첫 의사결정에 충분하다. 통계적 일반화를 주장하지 않고 명백한 가능성 또는 실패 신호를 보는 규모다.

이번 Pilot은 전체 survey 성능을 추정하는 Benchmark가 아니다. 따라서 155개 전체의 2인 Screening과 hash 자동 선정을 사용하지 않는다. 실제 survey의 대표 사례를 LLM 결과 확인 전에 사람이 목적 표집해 `evaluation_data/semantic_bridge/22_selected_pilot_queries.csv`에 고정했다. 이 선택으로 얻은 결과를 155개 전체나 일반 사용자 Query 성능으로 일반화하지 않는다.

실행 전에는 다음만 검증하고, 하나라도 실패하면 임의 교체 없이 중단한다.

1. selected CSV가 unique `query_id` 12개이며 `PURE` 6개와 `MIXED` 6개인지 확인한다.
2. 모든 `query_id`가 `survey_nlp_queries_candidates.csv`에 존재하는지 확인하고 원문은 survey 파일에서 가져온다.
3. Pure는 positive direct Accord/Canonical Note가 없고 indirect scent 표현이 있는지 확인한다. 명시적 Season/Daypart나 avoid 조건만 있는 경우는 Pure로 유지한다.
4. Mixed는 allowed vocabulary에 속하는 positive direct Accord 또는 Canonical Note가 최소 1개 있고 indirect scent 표현도 있는지 확인한다.
5. direct/context/avoid 조건과 원문의 exact-span `bridge_phrase`를 LLM 실행 전에 고정하고 preregistration에 기록한다.
6. 부적격 Query가 발견되면 대체 후보를 자동 선택하거나 사람이 임의 교체하지 않고 보고 후 중단한다.

세 표현 유형 `NATURAL_ENVIRONMENT`, `CLEAN_FABRIC_ROUTINE`, `TEMPERATURE_TEXTURE_ATMOSPHERE`는 사후 진단 tag로 유지하지만, 유형별 같은 수를 맞추는 선정 층이나 hash 순위로 사용하지 않는다.

### 4.1 Pure-indirect 6개

Direct Accord/Note 없이 bridge phrase와 필요한 명시적 context만 있는 Query다.

- 목적: 기존 시스템이 `UNRESOLVED`로 남기던 표현에 검색 가능한 scent signal을 만들 수 있는지 확인
- 평가: concept 적합성, Bridge TOP 5의 절대 relevance, 적절한 abstention

고정된 Pure Query는 `SQ0061`, `SQ0032`, `SQ0136`, `SQ0105`, `SQ0012`, `SQ0058`이다.

### 4.2 Anchored-mixed 6개

검증 가능한 direct Accord/Note/Context와 bridge phrase가 함께 있는 Query다.

- 목적: 동일 direct 조건에서 Bridge가 추가 정보를 제공해 ranking을 개선하는지 확인
- 평가: Direct-only Baseline과 Direct+Bridge의 블라인드 비교

고정된 Mixed Query는 `SQ0002`, `SQ0047`, `SQ0051`, `SQ0071`, `SQ0073`, `SQ0132`이다.

최종 12개는 Bridge 실행 전에 selected CSV와 preregistration에 고정한다. 예비 순번과 자동 교체 규칙은 두지 않는다.

### 4.3 사전 annotation

각 Query에서 다음을 LLM 실행 전에 기록한다.

- direct Accord/Note/Season/Daypart
- bridge phrase의 정확한 원문 span
- Bridge 대상이 아닌 avoid/performance/가격 등 기타 조건
- direct scent/context와 bridge phrase만 포함한 `bridge_evaluation_text`
- `bridge_applicability`: `YES`, `UNCERTAIN`, `NO`
- Pure/Mixed, primary/secondary expression type, eligibility와 제외·교체 사유
- selected CSV의 group과 selection reason

이 단계는 exhaustive scent Ground Truth를 만드는 작업이 아니다. 평가 대상을 분리하고 Stage 1 오류를 통제하기 위한 최소 annotation이다.

## 5. 핵심 가설

### H1. 제한된 concept 제안 가능성

간접 표현을 닫힌 target vocabulary에 제한하면, LLM이 제안한 최대 3개 concept 중 다수가 사람이 보기에 적어도 합리적인 검색 신호가 된다.

### H2. Retrieval의 추가 가치

Anchored-mixed Query에서 같은 direct/context 조건을 유지하고 Bridge concept만 추가했을 때, 사람 relevance 기준 TOP 5 ranking이 Direct-only보다 좋아진다.

### H3. 안전한 제한과 abstention

현재 근거로 target을 고르기 어려운 표현에서 억지 mapping보다 `ABSTAIN`/`REVIEW`를 반환할 수 있다. 높은 coverage 자체를 성공으로 간주하지 않는다.

## 6. 제안하는 최소 접근법

### 6.1 Target vocabulary 고정

허용 target은 다음 둘뿐이다.

1. `ACCORD`: `10_accord_dictionary.csv`의 92개
2. `CANONICAL_NOTE`: Stage 20 strict raw Note 185개를 21번 map으로 정리한 178개 canonical concept

Accord와 Note에서 같은 표면 이름이 있어도 type을 구분한다. FAMILY/RELATED/REVIEW/NOT_SAME은 allowed Note equivalence를 만드는 데 사용하지 않는다.

이 target 목록, 생성 규칙, 행 수와 SHA256을 run 전에 기록한다.

### 6.2 한 개의 constrained LLM proposer

Pilot에서는 Rule, Embedding, 여러 LLM을 동시에 비교하지 않는다. 기존 데이터에 phrase semantics가 없으므로 Rule은 사람이 기대 mapping을 미리 코딩하게 되고, Embedding은 새 model/dependency와 별도 validation 문제를 만든다.

LLM은 다음 역할만 맡는다.

- `bridge_phrase`를 읽는다.
- allowed vocabulary에서 최대 3개 target을 제안한다.
- 충분한 target이 없으면 `ABSTAIN`한다.
- 향수를 추천하거나 점수를 만들지 않는다.
- direct/context/avoid 조건을 바꾸지 않는다.

고정 JSON 출력 예시는 다음과 같다.

```json
{
  "bridge_status": "MAPPED",
  "targets": [
    {"target_type": "ACCORD", "target_feature": "..."},
    {"target_type": "CANONICAL_NOTE", "target_feature": "..."}
  ],
  "abstain_reason": ""
}
```

`bridge_status`는 `MAPPED`, `ABSTAIN`, `REVIEW`만 허용한다. LLM self-confidence와 임의 weight는 받지 않는다. 자연어 rationale은 사람이 그럴듯함에 설득되지 않도록 평가 전에 숨기며, 필요하면 오류 분석용으로만 짧게 기록한다.

구현 시 기존 15번의 checkpoint/resume와 prompt hash 기록 방식을 재사용할 수 있다. 15번 Stage 1 prompt는 추가 표현을 보존하도록 설계됐지 scent concept으로 바꾸도록 설계된 것이 아니므로 그대로 재사용하지는 않는다. 모델, prompt, temperature, retry 정책은 최초 실행 전에 고정하며 결과를 본 뒤 prompt를 수정해 같은 12개를 다시 평가하지 않는다.

### 6.3 자동 검증

LLM 출력은 다음 조건을 통과해야 Retrieval에 들어간다.

- target type과 이름이 allowed vocabulary에 exact match
- target 총수 1~3개
- 중복 target 없음
- Canonical Note는 178개 strict concept 중 하나
- raw Note 확장은 canonical map의 `CANONICAL`/`SAME_CONCEPT`만 사용
- `REVIEW`, `NOT_SAME`, FAMILY, RELATED로 target을 확장하지 않음
- explicit avoid와 동일한 target은 자동 적용하지 않고 `REVIEW`
- validation 실패 target을 가까운 문자열이나 LLM 추정으로 자동 교정하지 않음

검증 후 target이 0개면 `ABSTAIN`으로 처리한다.

### 6.4 ABSTAIN 원인 판정

`ABSTAIN`, `REVIEW` 또는 자동 검증 후 target 0개를 모두 같은 실패로 집계하지 않는다. Concept 평가자가 LLM의 `abstain_reason`을 보지 않은 상태에서 allowed vocabulary와 사전에 고정한 Feature 설명을 사용해 다음 원인 중 하나를 독립 판정하고, 불일치는 합의한다.

- `APPROPRIATE_ABSTENTION`: 표현 자체가 다의적이거나 향 검색 신호로 안정적으로 좁히기 어려워 Mapping하지 않는 것이 적절함
- `TARGET_SPACE_LIMITATION`: 관련 scent concept이 있을 가능성은 높지만 현재 Accord 92 + strict Canonical Note 178 안에는 적절한 target이 없음
- `MAPPING_FAILURE`: allowed vocabulary 안에 적절한 target이 하나 이상 있는데 proposer가 찾지 못했거나 validation을 통과시키지 못함

`TARGET_SPACE_LIMITATION` 판정에는 기존 전체 Canonical Note 2,492개 목록을 진단용으로만 참고할 수 있다. outside target 후보를 기록하더라도 이번 Retrieval에는 추가하지 않는다. 새로운 외부 정의나 LLM 설명은 사용하지 않는다. `MAPPING_FAILURE` 판정 시에는 놓친 allowed target을 하나 이상 기록해 target-space 문제와 proposer 문제를 구분한다.

JSON/schema 오류나 vocabulary exact-match 실패 같은 기계적 validation 원인은 별도 필드에 기록하되, 위 semantic 원인 판정을 대신하지 않는다. 두 평가자가 합의하지 못한 항목은 합의 review가 끝날 때까지 원인별 수치에서 제외하고 `REVIEW_PENDING`으로 둔다.

### 6.5 Retrieval 결합

두 시스템을 같은 Query에서 비교한다.

#### Baseline: Direct-only

- 사전 annotation의 direct Accord/Note/Season/Daypart만 사용
- 11번의 고정 score와 tie-break 사용
- Pure-indirect Query에 명시적 Season/Daypart가 있으면 context-only Retrieval을 하고, 어떤 resolved feature도 없으면 `NO_RETRIEVAL`이 정상 결과

#### Treatment: Direct + Semantic Bridge

- Baseline의 모든 direct/context 조건 유지
- 자동 검증을 통과한 Accord/Canonical Note만 추가
- Accord는 기존 strength score 사용
- Canonical Note는 해당 concept의 `CANONICAL`/`SAME_CONCEPT` raw Note 중 하나라도 있으면 match
- category 평균과 evidence coverage 계산은 11번 그대로 사용
- Bridge target별 weight, gamma, IDF, Note→Accord 확장은 추가하지 않음

첫 Pilot에서 Note–Accord 관계와 IFRA descriptor edge로 target을 연쇄 확장하지 않는다. `phrase → LLM target → relation expansion → perfume`처럼 inference 층을 늘리면 오류 원인을 분리할 수 없기 때문이다. 이 관계들은 결과 설명과 사후 오류 분석에만 사용한다.

## 7. 구성 요소별 역할

| 구성 요소 | 타당한 역할 | 맡기지 않을 역할 |
| --- | --- | --- |
| Stage 1 schema | direct/context와 bridge phrase 분리 | scene mapping 정답 제공 |
| LLM | 닫힌 vocabulary에서 후보 제안과 abstention | 사실 근거, 최종 정답, 향수 직접 추천 |
| 92 Accord | 넓고 실제 score 가능한 검색 신호 | scene 의미의 자동 Ground Truth |
| 178 strict Canonical Note | 근거가 비교적 명확한 세부 scent concept | 2,492개 전체 Note ontology 대표 |
| v0.3/evidence | identity/family/related 경계와 provenance | FAMILY/RELATED를 synonym으로 승격 |
| Canonical map | canonical 평가와 안전한 raw alias 검색 확장 | REVIEW/NOT_SAME merge |
| Note–Accord/IFRA 관계 | 설명과 오류 분석 | 첫 Pilot의 자동 다단 확장 |
| 11번 Retrieval | 고정 비교 가능한 candidate ranking | Bridge 의미 학습 또는 weight tuning |
| 사람 평가 | semantic relevance와 query-to-perfume relevance | 모델 결과에 맞춘 기존 Gold 수정 |

## 8. Ground Truth와 사람 평가

### 8.1 현재 자산으로 만들 수 없는 정답

다음은 기존 데이터만으로 정답화할 수 없다.

- `비 온 뒤의 숲 = Woody + Green + Aquatic`
- `깨끗한 빨래 = Aldehydic + Musky`
- `포근한 이불 = Powdery + Vanilla`

이러한 조합은 후보 가설일 수는 있지만 source fact가 아니다. IFRA descriptor, Fragrantica co-occurrence, LLM 기억 중 어느 것도 사용자 표현의 정답 label이 아니다.

따라서 사람 평가가 필요하다. 다만 12개에 대한 exhaustive 정답 concept set을 먼저 만들지 않고, 시스템이 제안한 후보와 pooled 추천 결과를 블라인드 판정하는 방식이 더 작고 현실적이다.

### 8.2 최소 평가 인원과 양

- 독립 평가자 2명. 향 용어 전문성을 전제로 점수를 해석하지 않고 8.3의 동일 glossary와 평가 guide를 제공
- 불일치 항목만 제3자 또는 합의 review
- Concept 판정: 최대 `12 Query × 3 target × 2명 = 72`건
- Retrieval 판정: Pure 6개의 Bridge TOP 5와 Mixed 6개의 Baseline/Treatment TOP 5 합집합, 최대 약 `90 candidate × 2명 = 180`건
- 전체 최대 약 252개의 짧은 등급 판정

이는 통계적 benchmark가 아니라 진행/수정/중단 결정을 위한 최소 규모다.

### 8.3 평가자용 고정 Feature 설명

Accord/Note 지식 차이 때문에 평가 결과가 달라지지 않도록 모든 평가자에게 동일한 Feature glossary를 제공한다. glossary는 Query 선정 후라도 **LLM 실행과 평가 결과 확인 전**에 생성·동결하고 version과 SHA256을 기록한다.

- Accord는 `10_accord_dictionary.csv`, `17_accord_ifra_matching.csv`, `ifra_primary_descriptor_definitions_2020.csv`의 기존 label과 검증된 정의를 우선 사용한다.
- Canonical Note는 `fragrantica_note_canonical_map_v1.csv`, v0.3 dictionary/evidence의 canonical label, 안전한 SAME_CONCEPT alias, 검증된 설명만 사용한다.
- 기존 프로젝트에 검증된 정의가 없는 Feature는 이름과 `ACCORD`/`CANONICAL_NOTE` type만 제시하고 설명을 새로 만들어 넣지 않는다.
- FAMILY/RELATED는 synonym 또는 정의처럼 제시하지 않는다.
- Query별로 유리한 설명을 추가하지 않고, 같은 Feature는 Concept 평가와 Retrieval 평가에서 항상 같은 설명을 사용한다.
- LLM이 glossary나 평가 중 설명을 생성하지 않는다.

Concept 평가에는 allowed 270개 전체 glossary를 참조할 수 있게 하고, Retrieval 평가 화면에는 candidate profile에 실제 표시된 Feature의 동일 glossary 설명만 제공한다.

### 8.4 Concept 판정

평가자는 Query와 target type/name만 보고 각 target을 평가한다. LLM rationale, confidence, Retrieval score는 보지 않는다.

- `2 = STRONG`: 표현을 검색하는 핵심 scent signal로 납득 가능
- `1 = PLAUSIBLE`: 관련은 있으나 여러 해석 중 하나이거나 보조 signal 수준
- `0 = WRONG/HARMFUL`: 무관하거나 stereotype/과도한 추론이며 검색을 왜곡할 가능성이 큼

`ABSTAIN`/`REVIEW`인 경우 6.4의 세 원인 중 하나를 별도 판정한다.

### 8.5 Retrieval 판정

Baseline과 Treatment TOP 5의 합집합을 perfume ID로 중복 제거하고, Query별 고정 seed로 순서를 섞은 뒤 익명 candidate ID를 부여한다. 평가 완료 전에는 다음을 숨긴다.

- 실제 perfume ID, 향수 이름, 브랜드
- Baseline/Treatment 포함 여부
- 원래 Rank와 Retrieval score
- popularity와 review 정보

평가자에게는 다음만 같은 형식으로 제공한다.

- 익명 candidate ID
- 사전에 고정한 `bridge_evaluation_text`
- 저장된 strength 기준 상위 Accord 5개
- 원본 tier/order 기준 Top/Middle/Base Note 각 최대 5개 또는 flat Note 최대 10개
- Query에 명시된 Season/Daypart가 있을 때 해당 candidate의 reliable share와 vote eligibility
- 8.3에서 고정한 해당 Feature 설명

동일 perfume이 두 시스템에 모두 있으면 pooled table에 한 번만 표시한다. 익명 candidate ID와 실제 perfume ID의 연결표는 평가가 끝날 때까지 평가자에게 공개하지 않고, 결과 분석 단계에서만 다시 연결한다. 원문의 가격·회피·성능 등 이번 Retrieval이 처리하지 않는 조건은 보여주지 않는다.

- `2 = HIGHLY_RELEVANT`
- `1 = PARTIALLY_RELEVANT`
- `0 = NOT_RELEVANT`

이 평가는 “현재 데이터 표현상 indirect scent 표현에 맞는가”를 보는 proxy다. 전체 요구 충족, 실제 시향이나 사용자 착향 만족을 대신하지 않는다. Pilot이 통과하더라도 최종 제품 relevance는 전체 조건을 포함한 별도 사용자/시향 평가가 필요하다.

## 9. Baseline과 최소 지표

### 9.1 Baseline이 필요한 이유

Bridge TOP 5가 그럴듯해 보이는 것만으로는 추가 가치가 입증되지 않는다. 동일한 direct/context 조건만 사용한 결과보다 좋아졌는지 비교해야 Bridge contribution을 분리할 수 있다.

Baseline은 새 Rule이나 Popularity 추천이 아니라 기존 11번 Direct-only Retrieval이다. Mixed Query에서는 공정한 A/B 비교가 가능하다. Pure Query는 명시적 context가 있으면 context-only 결과를 내고, resolved context도 없어서 `NO_RETRIEVAL`이면 그것이 기존 capability gap을 나타낸다.

### 9.2 핵심 의사결정 지표

GO/REVISE/STOP 판단에는 다음만 핵심 지표로 사용한다.

1. **Safe Resolution Rate**: 최소 한 target이 1점 이상인 Query 또는 `APPROPRIATE_ABSTENTION`으로 합의된 Query의 비율. `TARGET_SPACE_LIMITATION`과 `MAPPING_FAILURE`는 성공으로 세지 않는다.
2. **Graded Concept Precision@3**: 제안 target 점수 `0/1/2`를 `0/0.5/1`로 변환한 평균
3. **Wrong/Harmful Mapping Rate**: 제안 target 중 0점 비율
4. **Mixed Mean Δ Pooled Human NDCG@5와 Win 수**: Mixed 6개에서 Treatment - Baseline의 평균 차이와 양수인 Query 수
5. **Pure Query Strong Hit@5**: Bridge TOP 5에 2점 candidate가 하나 이상 있는 Pure Query 수

`Pooled Human NDCG@5`의 judgment universe는 각 Query에서 Baseline TOP 5와 Treatment TOP 5를 합쳐 중복 제거한 candidate뿐이다. 각 시스템의 TOP 5 DCG를 이 pooled set의 0/1/2 사람 label로 계산하고, 같은 pooled set에서 가장 높은 5개 relevance를 정렬한 값을 IDCG로 사용한다.

따라서 이 지표는 전체 131,930개 향수에 완전한 relevance judgment를 붙인 global NDCG가 아니다. 두 시스템이 실제로 제시한 작은 후보 pool 안에서의 **Pilot 상대 비교 지표**이며, 이름에도 `Pooled`를 유지한다.

### 9.3 진단 지표와 평가 신뢰도

다음은 GO 조건을 하나씩 추가하기 위한 지표가 아니라 실패 원인을 분리하기 위한 진단이다.

- **Supported Query Coverage**: 최소 한 target이 1점 이상인 Query 비율. Safe Resolution과 달리 appropriate abstention은 포함하지 않음
- 전체 및 표현 유형별 `ABSTAIN`/`REVIEW` 비율
- `APPROPRIATE_ABSTENTION`, `TARGET_SPACE_LIMITATION`, `MAPPING_FAILURE`의 Query 수와 비율
- JSON/schema/vocabulary validation 실패 수
- Accord/Canonical Note별 concept 점수와 0점 비율
- Pure/Mixed 및 세 expression type별 concept/Retrieval 결과
- Mixed Query Pooled Human NDCG@5의 Tie/Loss 수
- Context-only Baseline이 존재하는 Pure Query의 상대 결과

Concept와 Retrieval 등급의 평가자 exact agreement와 weighted Cohen's kappa는 **평가 신뢰도 지표**로 별도 보고한다. 이는 Bridge 성능 점수가 아니다. 사전 기준보다 낮으면 GO/STOP을 내리지 않고 평가 guide 또는 Feature 설명을 보완한 뒤 동일 raw judgment를 재검토한다.

Precision, Recall, F1을 위한 exhaustive concept Gold를 새로 만들지 않는다. `reminds_me_of`는 perfume similarity label이므로 scene relevance Ground Truth로 사용하지 않는다. Final Holdout도 사용하지 않는다.

## 10. 구현 전에 고정해 기록할 것

결과를 본 뒤 기준을 바꾸지 않도록 다음을 사전 등록한다.

- Pilot version과 실행 일시
- `22_selected_pilot_queries.csv`의 path, SHA256, 12개 unique ID와 selection reason
- 12개 ID의 survey 원문 존재 검증, Pure 6/Mixed 6 내용 검증 결과와 자동 교체 없음
- 12개 query_id, 원문, Pure/Mixed 구분, primary/secondary 표현 유형
- direct features, bridge phrase, 제외한 기타 조건
- allowed Accord 92개와 Canonical Note 178개의 생성 규칙, 수, hash
- 평가자용 Feature glossary의 source 규칙, version과 hash
- LLM model ID, prompt 전문과 hash, temperature, retry, abstention 규칙
- 출력 schema와 자동 validation 규칙
- Baseline/Treatment score 정의와 tie-break
- TOP K=5
- 세 ABSTAIN 원인의 판정 정의와 놓친/outside target 기록 방식
- 평가 guide, 평가자 수, 익명 candidate ID 규칙, 고정 shuffle seed, pooled candidate 생성 규칙
- 핵심 의사결정 지표, 진단 지표, Pooled Human NDCG@5 계산식과 평가 신뢰도 기준
- 아래 성공/수정/중단 기준
- Final Holdout과 기존 Golden Set을 수정하지 않는다는 확인

LLM 응답은 checkpoint로 한 번만 고정한다. schema/API 실패 재시도 외에, 낮은 점수를 이유로 재호출하거나 더 좋은 응답을 선택하지 않는다.

## 11. 성공·수정·중단 기준

12개는 작은 Pilot이므로 p-value나 복잡한 bootstrap보다 사전에 정한 효과 크기와 query 수로 판단한다.

먼저 평가 신뢰도 gate를 적용한다. Concept 또는 Retrieval 독립 평가의 weighted Cohen's kappa가 `0.40` 미만이면 Bridge의 GO/STOP 결론을 내리지 않고 `INCONCLUSIVE`로 둔다. 불일치 항목 합의는 진행하되, 낮은 독립 agreement 자체를 숨기지 않는다.

### GO: 다음 단계로 진행

아래를 모두 만족하면 제한된 범위에서 접근이 성립한다고 본다.

- Safe Resolution Rate가 `9/12` 이상
- Graded Concept Precision@3가 `0.67` 이상
- Wrong/Harmful Mapping Rate가 `20%` 이하
- Mixed 6개 중 Treatment의 Pooled Human NDCG@5가 Baseline보다 높은 Query가 `4개 이상`이고 평균 Δ Pooled Human NDCG@5가 양수
- Pure 6개 중 Strong Hit@5가 `4개 이상`
- 평가 신뢰도 gate 통과

`0.67`은 최대 3개 target 중 평균적으로 최소 2개 정도가 강한 검색 신호이거나, 강한/보조 signal의 조합이 유지되는 수준이다. 이 기준은 benchmark 주장이 아니라 3개 후보를 그대로 Retrieval에 넣어도 되는지 보는 안전 기준이다.

### REVISE: 의미 layer는 가능하지만 결합 방식 수정

다음 경우 Bridge 자체를 폐기하지 않고 원인을 분리한다.

- Concept 지표는 통과하지만 Mixed Retrieval이 개선되지 않음: target weighting 또는 11번 score 결합 문제
- Accord는 맞지만 Note가 자주 0점: 다음 Pilot을 Accord-only로 축소
- 구체적 냄새 장면은 성공하지만 추상 분위기는 실패: 지원 표현 범위를 구체적 odor scene으로 제한
- Bridge-only는 유효하지만 direct 조건이 있는 Query에서 regression: direct feature 우선순위와 Bridge 보조 weight를 다음 실험에서 한 요소만 검증
- 적절한 abstention은 많지만 harmful mapping은 낮음: coverage 확대보다 지원 범위 명시를 우선
- `TARGET_SPACE_LIMITATION`이 많고 mapped Query의 concept/Retrieval 지표는 양호함: proposer보다 270개 target 범위가 병목인지 별도 검토
- `MAPPING_FAILURE`가 많음: target vocabulary를 넓히기 전에 proposer prompt/model의 후보 탐색 문제를 우선 검토

### STOP 또는 접근법 변경

다음이면 현재의 constrained LLM-to-feature 접근을 확대하지 않는다.

- Safe Resolution Rate가 `6/12` 미만
- Graded Concept Precision@3가 `0.50` 미만
- Wrong/Harmful Mapping Rate가 `30%` 초과
- Concept가 그럴듯해도 Pure/Mixed Retrieval relevance가 모두 개선되지 않음
- 평가자 agreement가 낮아 같은 표현의 scent concept 자체에 합의하기 어려움
- 결과가 대부분 LLM stereotype이나 흔한 Woody/Fresh/Musky 조합으로 수렴

이 경우 더 많은 Note ontology나 외부 데이터를 즉시 수집하지 않는다. 먼저 target을 Accord-only로 줄이거나, 지원 범위를 `비누/빨래/숲`처럼 구체적 odor source에 한정하거나, Semantic Bridge 대신 사용자에게 직접 선호 확인 질문을 하는 방식이 더 적절한지 판단한다.

## 12. 현재 부족한 데이터와 근거

현재 자산만으로 부족한 것은 다음 세 가지다.

1. **Indirect phrase → scent concept 사람 판단**: 기존 파일에 없음
2. **Query → perfume human relevance**: 11번도 없다고 명시했고 현재 Stage 2 Golden Set이 없음
3. **실제 냄새 만족**: dataset metadata만으로는 검증 불가

첫 두 항목만 12개 Pilot의 소규모 사람 판정으로 보완한다. 세 번째는 이번 Pilot 범위 밖이다.

추가 외부 dataset이나 향 ontology는 첫 Pilot에 필요하지 않다. 현재 target space에서 concept precision이나 retrieval value가 확인되지 않은 상태로 자료를 더 수집하면 coverage만 늘고 제품 가치는 검증되지 않을 수 있다.

## 13. 구현한다면 적절한 범위

승인 후 구현 단계의 최대 범위는 다음 정도가 적절하다.

- 새 Notebook 하나: `22_semantic_bridge_pilot.ipynb`
- 기존 파일은 읽기만 함
- 외부 source 수집 없음
- 승인된 LLM 1개, prompt 1개, 12 Query 한 번 실행
- 단순 local validation 함수
- 11번 score 로직의 필요한 부분만 재사용
- 사람 평가용 단일 pilot table 1개
- LLM checkpoint와 평가 결과를 합친 분석 산출물 1개
- 결과 요약은 Notebook 마지막 결론에 남기고, 별도 summary가 후속 의사결정에 꼭 필요할 때만 1개 생성

새 package, class hierarchy, vector database, embedding index, ontology 관리 시스템, generic pipeline은 만들지 않는다.

사람 annotation은 기존 Golden Set을 수정하지 않고 별도 pilot evaluation data로 저장한다. LLM raw response/checkpoint는 재호출을 피하기 위해 보존하되 API key나 비밀정보는 저장하지 않는다.

## 14. 대안은 언제 검토할 것인가

첫 Pilot에서는 제안하지 않지만 결과에 따라 다음 하나만 후속으로 선택할 수 있다.

- **Accord-only Rule dictionary**: 소수의 구체적 표현에서 사람 합의가 매우 높고 반복 사용이 확인될 때
- **Embedding retrieval**: LLM proposal이 target 이름을 자주 놓치지만 사람 판단상 의미 근접성이 명확할 때
- **Human-curated phrase lexicon**: 지원할 표현 범위가 작고 안정적일 때
- **Clarifying question**: 표현이 본질적으로 다의적이고 평가자 합의도 낮을 때
- **별도 Stage 2 사용자 평가**: data-profile relevance가 통과한 뒤 실제 추천 만족을 검증할 때

여러 방법을 같은 12개에서 반복 비교하면 Pilot set에 맞춘 선택이 된다. 첫 결과에서 실패 원인을 분류한 뒤 필요한 대안 하나만 새 Query로 검증한다.

## 15. Pilot 이후 내릴 수 있는 결정

이 Pilot이 끝나면 다음 중 하나를 명확히 선택할 수 있어야 한다.

1. **제한적 개발 진행**: 구체적 sensory/scene 표현에서 constrained Bridge가 의미와 Retrieval 모두 개선
2. **범위 축소**: 숲·빨래·바다 같은 odor-source 표현만 지원하고 추상 이미지에는 abstain/질문
3. **Retrieval 결합 수정**: concept는 맞지만 direct feature와의 점수 결합에서 regression
4. **Accord-only 전환**: canonical Note가 과도하게 구체적이거나 불안정
5. **접근 중단**: 사람 합의와 추천 개선이 모두 부족하여 mapping보다 clarification이 타당

이 정도면 Semantic Bridge를 크게 구현하지 않고도 “현재 확보한 데이터와 향 지식 위에서 indirect 자연어를 검색 신호로 바꾸는 접근이 실제 향수 추천에 가치가 있는가?”를 판단할 수 있다.

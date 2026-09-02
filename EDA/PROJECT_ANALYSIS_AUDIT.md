# Project Analysis Audit

## 1. Executive Summary

이 프로젝트의 분석은 전반적으로 필요한 문제를 순서대로 다뤘다. 데이터 구조와 품질을 확인한 뒤 향수 간 Retrieval을 만들고, 자연어 입력을 구조화하는 Stage 1 평가로 전환했으며, 마지막에는 외부 향 지식을 보수적으로 정규화했다. 특히 `reminds_me_of`를 추천 점수에 넣지 않고 평가 label로만 사용한 점, Final Holdout을 계속 보호한 점, Note concept와 ingredient/FAMILY를 구분한 점은 설계 근거와 재현성 측면에서 유지 가치가 높다.

다만 분석량은 03, 08~09, 10의 다수 CSV, 12의 빈 산출물, 13~16의 중복 평가 파일에서 목적 대비 커졌다. 17~20의 Coverage 개선은 재사용 가능한 v0.3 사전을 만들었다는 점에서 의미가 있지만, 아직 Semantic Bridge나 최종 추천 품질을 검증하지 않은 상태에서 Coverage 확장에 세 단계가 쓰였다. Stage 20의 결론대로 이제는 사전 Coverage 확대를 멈추고 Pilot으로 이동하는 편이 타당하다.

현재 가장 중요한 결과는 다음 네 가지다.

1. 131,930개 향수의 기본 무결성과 Accord/Note/Community 데이터의 사용 조건이 확인됐다.
2. 향수 간 Retrieval에서는 Raw Accord Cosine + IDF Weighted Union Note Jaccard와 신뢰 가능한 Season/Daypart reranking이 Development에서 유효했다. 그러나 Final Holdout 300개는 아직 평가하지 않아 최종 모델은 아니다.
3. 자연어 Stage 1에서는 200개 Golden Set 기준 Current Rule 1.5%, Extended Rule 4.5%, LLM 6.0% Overall Exact Match였다. LLM이 상대적으로 우세했지만 Golden Set QA 60건이 미검토이고 외부 holdout 검증도 없다.
4. 향 지식은 `scent_term_dictionary_v0.3.csv`와 `scent_term_evidence_v0.3.csv`까지 구축됐다. strict vocabulary coverage는 7.33%, occurrence-weighted coverage는 62.06%지만 Semantic Bridge는 아직 구현되지 않았다.

따라서 프로젝트는 **데이터·후보 Retrieval·Stage 1 비교·향 지식 기반은 마련됐지만, Stage 1 확정과 Semantic Bridge, Stage 2 Human Relevance 평가, 최종 End-to-End 추천은 아직 남아 있는 상태**다.

## 2. 전체 분석 흐름

### 2.1 데이터 이해와 품질 확인 — 01~03

- 목적: CSV/JSONL 구조, 무결성, 결측 표현, Accord/Note/Community/유사 관계의 사용 가능성을 확인한다.
- 최종 결론: CSV와 JSONL은 131,930개로 일치하고 ID 중복이나 기본 필드 결측은 없다. 기존 발표 문서 기준 Accord는 약 97.9%, Note는 약 98.1%가 보유한다. JSONL의 `people=null` 10,405건은 CSV의 여러 vote 관련 0과 구분해야 한다.
- 불필요해진 중간 실험: 01의 구조 확인은 02와 `SCHEMA.md`로 거의 대체된다. 03의 Positive/Negative 분류는 Negative pair가 0건이라 AUC 질문에 답하지 못했고, 실제 설명력은 04 이후 Retrieval 평가가 대체했다.
- 반드시 보존할 결과: 02의 데이터 품질 판단과 03에서 확인한 Note–Accord 및 Accord–Season/Daypart 관계의 핵심 결론. 관계 테이블의 재사용 형태는 10에서 다시 정리됐다.

### 2.2 Perfume-to-Perfume Retrieval — 04~09

- 목적: 한 향수와 유사한 향수를 Accord/Note로 찾고, Note IDF, Note tier, Community reranking, candidate pool, score calibration을 한 요소씩 검증한다.
- 최종 결론: Popularity보다 Accord/Note가 크게 우수했고, Raw Accord와 Note를 결합한 방식이 단일 feature보다 좋았다. Note IDF는 결합 시 소폭 유효했고 Accord IDF와 Note tier는 채택 근거가 없었다. Reliable Season/Daypart는 Development에서 추가 ranking signal을 보였다. Calibration은 RAW보다 낮아 RAW score 유지가 권고됐다.
- 불필요해진 중간 실험: 06의 tier 세부 진단, 08의 광범위한 pool/gamma grid, 09의 여러 calibration 변환별 상세표는 최종 의사결정 문장만 남겨도 된다.
- 반드시 보존할 결과: 04의 baseline, 05의 Note IDF/동일 가중치 판단, 07의 Community signal, 09의 calibration 불필요 판단과 “Final Holdout 미사용” 상태.

### 2.3 자연어 Feature Bridge와 Rule Retrieval — 10~11

- 목적: 자연어가 현재 데이터의 Accord/Note/Season/Daypart로 어디까지 직접 표현되는지 구분하고, Level A direct rule로 실제 향수 검색까지 연결한다.
- 최종 결론: 직접 표현 가능한 canonical feature는 Accord 92개, Note 2,523개, Season 4개, Daypart 2개다. 감각·장면 표현은 데이터만으로 임의 매핑하지 않아야 한다. Rule Parser는 synthetic 126개에서 100%였지만 이는 구현 진단일 뿐 실제 자연어 정확도가 아니다.
- 불필요해진 중간 실험: 10에서 내보낸 관계별 CSV 대부분은 `10_query_feature_bridge.csv` 또는 context profile에 흡수됐고, 11의 대규모 추천 결과와 진단표는 이후 평가에 사용되지 않았다.
- 반드시 보존할 결과: `10_query_feature_bridge.csv`, Accord/Note dictionary, Accord context profile, `11_rule_lexicon.csv`, 그리고 “직접 근거와 외부 의미 해석을 분리한다”는 설계 원칙.

### 2.4 Query Understanding 평가 — 12~16

- 목적: Synthetic 평가의 한계를 벗어나 실제 사용자 Query 200개로 Current Rule, Extended Rule, LLM의 Stage 1 구조화 성능을 비교하고 Golden Set 품질 이슈를 표본 점검한다.
- 최종 결론: Current Rule 1.5%, Extended Rule 4.5%, LLM 6.0% Overall Exact Match였다. LLM은 scent와 일부 additional에서 개선했지만 avoid F1은 0%였고 5개 regression이 있었다. 60개 QA 후보는 전부 아직 미검토다.
- 불필요해진 중간 실험: 12가 만든 0-row annotation/gold CSV는 실제 `evaluation_data/stage1/13_stage1_golden_set_v1_200.xlsx`와 연결되지 않았다. 13~15의 predictions/evaluation/errors 파일에는 동일 필드가 반복 저장됐다.
- 반드시 보존할 결과: 실제 Golden Set, 동일 metric의 비교 결과, LLM prompt/checkpoint, 16 QA 후보와 guide.

### 2.5 향 지식과 용어 정규화 — 17~20

- 목적: IFRA 및 허용된 공식 자료로 Fragrantica Accord/Note를 보수적으로 연결하고, SAME_CONCEPT와 FAMILY/RELATED를 분리한 재사용 사전을 만든다.
- 최종 결론: IFRA는 ingredient/descriptor evidence layer로 유효하지만 Note ontology 전체를 대체하지 못한다. v0.3에서 strict matched Note 185개, vocabulary 7.33%, occurrence-weighted 62.06%, perfume-level 95.82%에 도달했다. FAMILY/RELATED는 strict 정답이 아니라 향후 Bridge feature 후보다.
- 불필요해진 중간 실험: Stage별 Coverage 비교표와 기여도 표가 18~20에서 반복됐다. v0.1/v0.2는 현재 runtime 데이터라기보다 재현성용 이력이다.
- 반드시 보존할 결과: IFRA 원본/가공본, v0.3 dictionary/evidence, Stage 20 summary, 그리고 남은 gap을 억지로 SAME_CONCEPT로 승격하지 않은 판정 기록.

## 3. Notebook Audit

| No | Notebook | 핵심 질문 / 주요 작업 | 핵심 결과 | 후속 활용과 중복 | 주요 산출물 | 판정 |
| -- | -------- | --------------------- | --------- | ---------------- | ----------- | ---- |
| 01 | `01_dataset_structure.ipynb` | CSV/JSONL/Schema의 실제 구조와 행 수가 일치하는가. 파일·컬럼·중첩 구조를 확인했다. | 두 데이터 모두 131,930건, CSV 59컬럼. 기준 파일을 “둘 다 가능”으로 적었으나 주요 중첩 필드 등 요약 일부는 미완성이다. | 02가 같은 파일 구조와 레코드 수를 다시 확인하고 더 깊게 분석했다. | 없음 | `REMOVE_CANDIDATE` |
| 02 | `02_data_quality.ipynb` | 추천에 쓸 수 있는 데이터 규모와 결측/0의 의미는 무엇인가. 무결성, Notes, Accords, votes, `reminds_me_of`를 점검했다. | ID 중복/기본 결측 없음. Accord 97.90%, Notes 없음 1.93%, `reminds_me_of` 692,729 directed relations. `people=null`이 CSV vote 0으로 저장되는 문제를 확인했다. | 이후 모든 분석의 데이터 사용 조건과 발표 수치의 근거다. 01을 사실상 포함한다. | 별도 파일 없음 | `KEEP` |
| 03 | `03_feature_relationship.ipynb` | Note–Accord, Accord–context, 구조 유사도가 사용자 유사 판단을 설명하는가. 관계·상관·AUC를 탐색했다. | 의미 있는 Note–Accord와 context 경향은 확인했으나 Negative 관계가 0건이라 Positive/Negative AUC는 `NaN`으로 핵심 비교가 성립하지 않았다. | 관계 분석은 10에서 재구성됐고 유사성 평가는 04의 Retrieval로 대체됐다. | 별도 파일 없음 | `MERGE_CANDIDATE` |
| 04 | `04_baseline_retrieval.ipynb` | Accord/Note가 Popularity보다 relevant perfume을 잘 찾는가. 700 Development/300 Final Holdout을 분리했다. | NDCG@10은 Popularity 0.0113, Accord 0.1688, Note 0.2345, 결합 0.2668. 결합이 가장 우수했다. | 05~09의 고정 baseline과 평가 framing을 제공했다. | Notebook 저장 출력만 존재 | `KEEP` |
| 05 | `05_retrieval_ablation.ipynb` | Accord/Note IDF와 결합 가중치가 개선되는가. Tuning/Internal Validation과 bootstrap을 수행했다. | Note IDF 후보 유지, Accord IDF 제외, Accord/Note 0.5/0.5 유지. Internal Validation NDCG@10 0.2760으로 baseline 대비 +0.0102. | 06~09의 base feature 정의로 사용됐다. | Notebook 저장 출력만 존재 | `KEEP` |
| 06 | `06_note_tier_ablation.ipynb` | Top/Middle/Base 위치가 Union Note보다 추가 정보를 주는가. beta CV와 bootstrap을 수행했다. | 선택 beta 0.0, 개선 fold 0/5. Tier 추가 정보는 제한적이고 우선순위가 낮다. | 이후 모델에서 tier를 쓰지 않는 근거지만 결과 한 문장으로 충분하다. | Notebook 저장 출력만 존재 | `ARCHIVE` |
| 07 | `07_community_perception_ablation.ipynb` | Reliable Season/Daypart가 구조 기반 ranking을 개선하는가. community reranking을 비교했다. | Season+Daypart, vote 20 이상, gamma 0.5 후보가 NDCG@10 0.3164로 base 0.2709를 개선했고 5/5 fold에서 개선됐다. | 08~09가 동일 signal의 안정성과 결합법을 좁혔다. | Notebook 저장 출력만 존재 | `KEEP` |
| 08 | `08_community_rerank_stability.ipynb` | candidate pool과 gamma 선택이 안정적인가. ceiling, grid, bootstrap을 분석했다. | Development global best는 pool 50/gamma 0.70, NDCG@10 0.3226. 다만 Recall@20과 검색 폭 trade-off가 남았다. | 07의 좁은 설정을 보완했지만 09는 pool 200을 다시 고정했다. 최종 Retrieval 결정 기록에 흡수 가능하다. | Notebook 저장 출력만 존재 | `MERGE_CANDIDATE` |
| 09 | `09_score_calibration_ablation.ipynb` | score scale 보정 뒤에도 Community 효과가 남고 calibration이 필요한가. | Community 효과는 유지됐지만 best calibrated NDCG@10 0.2965가 RAW 0.3218보다 낮았다. RAW gamma 0.7, pool 200 유지 권고. | 07~08과 함께 하나의 Community reranking 결정으로 정리 가능하다. | Notebook 저장 출력만 존재 | `MERGE_CANDIDATE` |
| 10 | `10_query_feature_bridge.ipynb` | 자연어를 현재 데이터 feature로 어디까지 근거 있게 표현할 수 있는가. 사전과 관계 bridge를 구축했다. | Level A 2,621, B 7,360, C 550, D 13. 감각·장면 표현은 외부 의미 지식 없이는 직접 매핑 불가다. | 11이 bridge의 Level A, Accord/Note dictionary, context profile을 직접 읽었다. 03의 관계 분석도 재구성했다. | `10_*` CSV 10개 | `KEEP` |
| 11 | `11_rule_based_query_retrieval_baseline.ipynb` | 명확한 자연어 조건을 실제 향수 검색까지 연결할 수 있는가. parser, score, 설명 template을 구현했다. | Synthetic parser 100%, 복합 조건 만족 96.17%. 실제 사용자 정확도는 Golden Set 부재로 판단 불가라고 명시했다. | `11_rule_lexicon.csv`를 13·14가 직접 재사용했다. 추천/진단 CSV는 후속 입력이 아니다. | `11_*` CSV 5개 | `KEEP` |
| 12 | `12_query_understanding_goldset_design.ipynb` | Stage 1 Gold와 Stage 2 relevance를 어떻게 분리하고 leakage를 막을 것인가. 빈 template과 평가 함수를 설계했다. | 작성 Query 0/120, annotator 0명, 평가 상태 `WAITING_FOR_HUMAN_ANNOTATION`. | 설계 원칙은 유효하지만 실제 200개 Golden Set은 별도 XLSX와 다른 schema로 구축됐다. 12의 빈 CSV는 사용되지 않았다. | guideline 1개, 빈 CSV 3개/slot template 1개 | `ARCHIVE` |
| 13 | `13_stage1_rule_baseline_evaluation.ipynb` | 고정 Rule Parser가 실제 사용자 Query 200개를 얼마나 구조화하는가. | Overall Exact 1.50%, coverage 15.50%, scent positive F1 45.90%. 197개 exact failure를 그대로 기록했다. | 14·15의 비교 baseline이며 outputs를 직접 읽는다. | prediction/evaluation/errors/metrics/summary | `KEEP` |
| 14 | `14_stage1_extended_rule_evaluation.ipynb` | 명시적 gender/intensity/longevity/avoid rule 확장만으로 얼마나 개선되는가. | Overall Exact 4.50%, coverage 33.00%, scent F1 53.12%; query-level regression 0건. Additional 170건은 여전히 미해결이다. | 15 비교와 16 QA의 직접 입력이다. | 9개 CSV와 summary | `KEEP` |
| 15 | `15_stage1_llm_evaluation.ipynb` | 동일 200개에서 LLM이 Rule보다 나은가, 운영 안정성은 어떤가. 저장된 API 결과를 평가했다. | LLM Exact 6.00%, coverage 41.50%, scent F1 64.20%. 199/200 성공, 5개 regression, avoid F1 0%. | 16 QA의 직접 입력이며 Stage 1 선택의 핵심 근거다. | prompt, checkpoint, prediction/evaluation/errors/metrics/comparison/summary | `KEEP` |
| 16 | `16_stage1_golden_set_quality_audit.ipynb` | 낮은 점수가 Gold 오류나 표면형 불일치에서 왔는지 작은 표본으로 QA할 수 있는가. | LLM regression 5, avoid mismatch 36, additional sample 20을 합쳐 60개 후보를 만들었다. 수동 판정은 60/60 미검토다. | 완료 전인 직접 다음 작업이다. Gold와 기존 metrics는 수정하지 않았다. | QA candidates CSV, guide MD | `KEEP` |
| 17 | `17_ifra_knowledge_coverage_analysis.ipynb` | IFRA ingredient/descriptor가 Accord/Note를 어느 정도 직접 설명하는가. PDF 추출과 strict matching을 수행했다. | Accord strict 52.2%, Note strict vocabulary 6.3%, occurrence-weighted 49.7%. IFRA는 보조 evidence이지 Note ontology는 아니다. | 18~20의 기준 데이터와 unmatched backlog를 제공했다. | processed IFRA 3개, `17_*` 13개 | `KEEP` |
| 18 | `18_scent_term_dictionary_validation.ipynb` | 고빈도 P0 8개를 공식 자료로 보수적으로 판정할 수 있는가. | SAME_CONCEPT 6, FAMILY 2. v0.1 strict occurrence coverage 52.61%. | v0.1이 19·20의 직접 입력이지만 현재 사전은 v0.3이다. P0 절차를 19에 흡수 가능하다. | v0.1 dictionary/evidence, decisions, summary | `MERGE_CANDIDATE` |
| 19 | `19_scent_term_dictionary_expansion.ipynb` | unmatched occurrence 80% 범위의 159개를 공식 근거로 확장할 가치가 있는가. | 신규 SAME_CONCEPT 15, FAMILY 37, RELATED 5, UNRESOLVED 102. v0.2 occurrence coverage 59.63%. | v0.2와 high-frequency unresolved가 20의 직접 입력이다. | v0.2 dictionary/evidence, 5개 분석 CSV, summary | `KEEP` |
| 20 | `20_external_scent_knowledge_validation.ipynb` | IFRA 밖 공식 자료가 남은 고빈도 gap을 보완하는가. 상위 30개를 판정했다. | SAME_CONCEPT 5, FAMILY 10, RELATED 2, UNRESOLVED 13. v0.3 occurrence coverage 62.06%; 추가 수집보다 Semantic Bridge Pilot 이동을 결정했다. | 최신 향 지식 상태이며 아직 후속 Pilot에서 사용되지 않았다. | v0.3 dictionary/evidence, 5개 분석 CSV, summary | `KEEP` |

번호 누락과 추가 Notebook은 없다. 프로젝트 루트의 분석 Notebook은 실제로 01부터 20까지 정확히 20개다.

## 4. 중복 / 과도한 분석 후보

### MERGE_CANDIDATE

- **03 → 02/04/10에 흡수**: 데이터 관계 탐색은 의미가 있으나 Negative pair가 없어 핵심 AUC 질문은 미해결이다. 데이터 품질은 02, Retrieval 설명력은 04, 관계 bridge는 10이 더 직접적인 최종 근거다.
- **08·09 → 07의 Community reranking 결정 기록에 통합**: 08은 pool/gamma 안정성, 09는 calibration만 추가 검증했다. 세 Notebook의 유지할 결론은 “Reliable Season/Daypart는 유효, gamma 0.7 후보, calibration은 불필요, pool은 최종 미확정”으로 짧게 합칠 수 있다.
- **18 → 19·20의 dictionary lineage에 통합**: P0 pilot은 후속 확장의 판정 규칙을 만들었으나 현재 소비 대상은 v0.3이다. v0.1 데이터는 재현성 이력으로 남기되 별도 핵심 Notebook으로 계속 노출할 필요는 낮다.

### ARCHIVE

- **06**: Note tier의 무효 결과는 재실험 방지 근거로 보존하되 현재 feature 흐름에는 들어가지 않는다.
- **12**: leakage 방지와 Stage 분리 원칙은 보존할 가치가 있지만, 실제 산출물은 0-row scaffold이고 현재 Golden Set schema와 다르다.

### REMOVE_CANDIDATE

- **01**: 구조 확인 결과가 02와 `SCHEMA.md`에 거의 완전히 포함되며 요약 template도 일부 미완성이다. 삭제하지 않고 후보로만 표시한다.

## 5. Output 파일 Audit

| 파일 또는 그룹 | 분류 | 근거 |
| -------------- | ---- | ---- |
| `10_query_feature_bridge.csv`, `10_accord_dictionary.csv`, `10_note_dictionary.csv`, `10_accord_context_profile.csv` | `NEXT_STEP_INPUT` | 11이 직접 읽은 현재 자연어→데이터 baseline 입력이다. Bridge는 향후 Pilot에서도 재사용 가능하다. |
| `10_note_accord_bridge.csv`, `10_accord_note_bridge.csv`, `10_accord_season_bridge.csv`, `10_accord_daypart_bridge.csv`, `10_accord_cooccurrence.csv` | `INTERMEDIATE` | 선택된 관계가 query bridge/context profile에 다시 들어갔고 후속 Notebook은 원본 관계 파일을 직접 읽지 않았다. |
| `10_query_examples.csv`, `10_external_mapping_inventory.csv` | `REPORT_ONLY` | 구현 입력보다 표현 가능/불가능 범위를 설명하는 작은 예시와 목록이다. |
| `11_rule_lexicon.csv` | `NEXT_STEP_INPUT` | 13·14가 직접 읽는 고정 Rule baseline의 실질적 입력이다. |
| `11_parser_test_results.csv`, `11_query_diagnostics.csv`, `11_rule_baseline_recommendations.csv`, `11_unresolved_queries.csv` | `REPORT_ONLY` | synthetic 동작과 추천 사례를 설명하지만 13 이후 실제 평가에는 사용되지 않았다. |
| `12_query_annotation_template.csv`, `12_query_annotations_long.csv`, `12_query_goldset.csv` | `DUPLICATE_CANDIDATE` | 비어 있거나 120-slot 설계이며 실제 200개 XLSX Golden Set으로 대체됐다. |
| `12_annotation_guideline.md` | `REPORT_ONLY` | leakage와 annotation 원칙의 기록이다. 실제 Golden Set과 schema 차이가 있으므로 실행 입력으로 간주하면 안 된다. |
| `13_*_metrics.csv`, `13_rule_stage1_summary.md` | `REPORT_ONLY` | 고정 Rule baseline의 요약 근거다. |
| `13_rule_stage1_evaluation.csv` | `NEXT_STEP_INPUT` | 14·15가 직접 비교에 사용했다. |
| `13_rule_stage1_predictions.csv`, `13_rule_stage1_errors.csv` | `INTERMEDIATE` | 평가표 생성과 오류 분석용이다. `errors`는 evaluation의 실패 subset이라 장기적으로 중복도가 높다. |
| `14_extended_rule_stage1_evaluation.csv`, `14_extended_rule_stage1_predictions.csv`, `14_rule_comparison.csv` | `NEXT_STEP_INPUT` | 15·16이 직접 읽는다. |
| 나머지 `14_*` CSV와 `14_extended_rule_summary.md` | `REPORT_ONLY` | 변화, trigger, 오류를 설명한다. evaluation/errors의 동일 필드 반복은 정리 후보지만 현재 재현성 기록으로는 남긴다. |
| `15_llm_stage1_predictions.csv`, `15_llm_stage1_evaluation.csv`, `15_llm_stage1_errors.csv`, `15_llm_vs_extended_query_changes.csv` | `NEXT_STEP_INPUT` | 16 QA가 직접 읽는 현재 입력이다. QA 완료 후에는 대부분 `INTERMEDIATE`로 낮출 수 있다. |
| `15_stage1_llm_prompt_v1.txt`, `15_llm_stage1_checkpoint.csv` | `REUSABLE_DATA` | prompt와 원 응답/운영 metadata를 보존해 LLM 결과를 다시 호출하지 않고 감사할 수 있다. |
| `15_llm_stage1_metrics.csv`, `15_llm_api_metrics.csv`, `15_stage1_model_comparison.csv`, `15_error_comparison.csv`, `15_llm_stage1_summary.md` | `REPORT_ONLY` | Stage 1 비교와 운영 결과를 요약한다. |
| `16_golden_set_quality_audit_candidates.csv` | `NEXT_STEP_INPUT` | 수동 검토가 아직 0/60이므로 현재 가장 직접적인 다음 작업 입력이다. |
| `16_golden_set_quality_audit_guide.md` | `REPORT_ONLY` | 사람 검토 절차와 허용 판정을 설명한다. |
| `data/external/ifra/raw/*`, `data/external/ifra/processed/*` | `REUSABLE_DATA` | 출처와 추출 결과가 분리되고 provenance/해석 규칙이 기록된 재사용 지식 원천이다. |
| `17_note_ifra_matching.csv`, `17_accord_ifra_matching.csv`, `17_ifra_descriptor_edges.csv`, `17_ifra_secondary_primary_profile.csv` | `NEXT_STEP_INPUT` | v0.3 사전 밖의 strict baseline과 descriptor 관계를 Semantic Bridge Pilot에서 근거 feature로 재사용할 수 있다. |
| 17의 vocabulary/distribution/extraction/coverage/top-unmatched 파일과 summary | `REPORT_ONLY` | IFRA 구조와 Coverage 결론을 설명한다. `17_top_unmatched_notes.csv`는 18~20에서 이미 사용됐다. |
| `18_scent_term_validation_decisions.csv`, `19_scent_term_expansion_decisions.csv`, `20_external_note_validation_decisions.csv` | `INTERMEDIATE` | 단계별 판정 추적에는 유용하지만 최신 dictionary/evidence와 summary가 현재 상태를 더 직접적으로 표현한다. |
| 19·20의 target/coverage/contribution/gap CSV | `REPORT_ONLY` | 대상 선정과 Coverage 변화의 분석 근거다. `20_remaining_high_frequency_gaps.csv`만 향후 수동 backlog로 재사용하면 `NEXT_STEP_INPUT`이 된다. |
| `data/scent_knowledge/scent_term_dictionary_v0.3.csv`, `scent_term_evidence_v0.3.csv` | `REUSABLE_DATA` | 현재 최신 strict/FAMILY/RELATED 관계와 provenance를 담은 핵심 향 지식이다. |
| v0.1/v0.2 dictionary/evidence | `INTERMEDIATE` | 현재 소비 버전은 아니지만 v0.3까지의 판정 이력을 재현하는 version snapshot이다. |
| 17~20 summary MD | `REPORT_ONLY` | 단계별 판단과 source 제한, Coverage 해석을 설명한다. 최신 운영 판단은 20 summary가 대표한다. |

그 밖의 주요 디렉터리는 다음처럼 판단한다.

- `evaluation_data/stage1/13_stage1_golden_set_v1_200.xlsx`: 수정 금지 source이자 Stage 1 비교의 핵심 평가 데이터다. 반드시 유지한다.
- `data/survey/processed/survey_nlp_queries_raw.csv`: 원 설문 응답의 개인정보 제외 추출본으로 재사용 가치가 있다.
- `data/survey/processed/survey_nlp_queries_candidates.csv`: 현재 `UNREVIEWED/UNASSIGNED`이며 Stage 1 외부 holdout 후보인 `NEXT_STEP_INPUT`이다. 어느 Notebook도 아직 읽지 않았다.
- `docs/presentation/natural_language_recommendation_ppt_final.md`: `REPORT_ONLY`다. 15의 비교 완료와 17~20의 향 지식 진행이 반영되지 않아 현재 상태 문서는 아니다.
- `docs/presentation/natural_language_recommendation_ppt.md`: final 버전과 내용이 크게 겹치는 `DUPLICATE_CANDIDATE`다.

## 6. 반드시 유지할 핵심 산출물

최소 유지 집합은 다음과 같다.

1. **Source와 schema**: `perfumes.csv`, `perfumes.jsonl`, `SCHEMA.md`, `evaluation_data/`, `data/**/raw/`.
2. **Retrieval 설계 근거**: 04, 05, 07, 09 Notebook. 별도 결과 파일이 없으므로 저장된 실행 결과 자체가 근거다.
3. **자연어 direct bridge**: `10_query_feature_bridge.csv`, `10_accord_dictionary.csv`, `10_note_dictionary.csv`, `10_accord_context_profile.csv`, `11_rule_lexicon.csv`.
4. **Stage 1 평가**: 실제 200개 Golden Set, 13~15의 summary/model comparison, `15_stage1_llm_prompt_v1.txt`, `15_llm_stage1_checkpoint.csv`, 16 QA candidates/guide.
5. **향 지식**: IFRA raw/processed 데이터, `scent_term_dictionary_v0.3.csv`, `scent_term_evidence_v0.3.csv`, `20_external_scent_knowledge_validation_summary.md`.

이 집합 밖의 분석표가 모두 불필요하다는 뜻은 아니다. 다만 현재 추천 시스템의 설계 근거, 재현성, 바로 다음 구현에 필요한 최소 집합은 위 수준으로 좁힐 수 있다.

## 7. Archive 후보

- Notebook: 06, 12.
- 통합 후 Archive 가능: 03, 08, 09, 18. 먼저 핵심 결론을 유지되는 결정 기록에 흡수해야 한다.
- Output: 10의 개별 관계 테이블, 11의 synthetic 추천/진단 파일, 13~15의 per-model errors subset과 중복 prediction view, v0.1/v0.2 dictionary/evidence.
- 문서: `natural_language_recommendation_ppt.md` 초안.
- Remove 후보: 01과 12의 빈 CSV 산출물. 이번 Audit에서는 삭제하지 않는다.

## 8. Over-engineering 평가

### 실제로 과도했다고 판단되는 부분

1. **03의 질문 범위와 평가 framing**: 한 Notebook에서 feature 관계, season/daypart 상관, 유사도 분류, AUC까지 다뤘지만 Negative label이 0건인 상태로 핵심 비교를 진행했다. 더 좁게 label 가능성부터 확인했으면 뒤 계산을 줄일 수 있었다.
2. **Retrieval 미세 튜닝의 시점**: 08은 candidate pool/gamma, 09는 여러 calibration을 상세히 탐색했지만 Final Holdout과 자연어 Stage 2 relevance는 아직 검증되지 않았다. 서로 다른 가설이므로 완전 중복은 아니지만 제품 불확실성 대비 Development metric 최적화가 길었다.
3. **10의 CSV 수**: 10개 CSV 중 후속 Notebook이 직접 읽은 것은 4개다. 개별 Note–Accord/Accord–Note/context/co-occurrence 표는 통합 bridge를 만든 뒤에는 Notebook 출력으로 충분했다.
4. **11의 synthetic 결과 저장**: 100% parser 결과는 규칙으로 생성한 Query를 같은 규칙으로 읽는 동작 확인이다. 추천 316KB와 여러 진단 CSV를 영구 출력으로 둘 필요는 낮다.
5. **12의 빈 pipeline scaffold**: 실제 annotation 없이 template, long-format, goldset, evaluation 함수까지 먼저 만들었고 이후 실제 Golden Set은 다른 XLSX schema로 등장했다. 현재 사용 흐름에 연결되지 않은 선행 구현이다.
6. **13~16의 평가 파일 중복**: 각 모델마다 predictions, evaluation, errors를 따로 저장했으며 errors는 evaluation의 실패 subset이고 evaluation은 prediction을 다시 포함한다. 재현성에 필요한 원 응답/최종 평가표와 요약만으로 더 작게 구성할 수 있었다.
7. **Coverage 중심 확장의 한계**: 17~20은 의미 구분을 훼손하지 않아 분석 자체는 건전했지만, 실제 Semantic Bridge나 추천 이득을 아직 검증하지 않은 채 Coverage 표와 기여도 표가 단계마다 반복됐다. Stage 20 이후 추가 Coverage 확장은 제품 목표보다 metric 자체를 좇는 작업이 될 가능성이 높다.

### 과도하지 않았다고 판단되는 부분

- 전체 N×N similarity matrix를 만들지 않고 query batch와 TOP candidate만 계산한 것은 필요한 효율화다.
- Final Holdout을 04~09에서 사용하지 않은 것은 과도한 절차가 아니라 leakage 방지에 필요한 통제다.
- Rule/LLM의 동일 Golden Set·동일 normalization 비교와 prompt/checkpoint 보존은 재현성에 필요하다.
- SAME_CONCEPT, FAMILY, RELATED, UNRESOLVED를 구분하고 strict Coverage를 보수적으로 계산한 것은 metric을 높이기 위한 의미 훼손을 막았다.
- 별도 framework, class hierarchy, generic pipeline을 만들지 않고 Notebook 안의 직접 코드로 유지한 점은 프로젝트 규모에 적절하다.

## 9. 현재 프로젝트 상태

| 영역 | 검증된 것 | 아직 구현·검증되지 않은 것 |
| ---- | --------- | -------------------------- |
| 데이터 | 131,930건 구조/무결성, Accord/Note 보유율, community 결측 표현, `reminds_me_of` 규모와 사용상 주의 | 운영 시 데이터 갱신, source 변화 대응, 최종 서비스용 전처리 artifact |
| Retrieval | Accord+Note가 Popularity보다 우수, Note IDF 후보, tier 제외 근거, Reliable Season/Daypart signal, calibration 불필요 판단 | Final Holdout 300개 단회 평가, candidate pool 최종 확정, production retrieval 구현 |
| 자연어 구조화 | 200개 Golden Set에서 Current/Extended/LLM 동일 metric 비교, LLM prompt와 운영 지표 보존 | 60개 QA 수동 판정, Gold revision 여부, 외부 holdout 일반화, 최종 Parser 선택 |
| 향 지식 | IFRA processed data, v0.3 dictionary/evidence, strict/FAMILY/RELATED 분리, 공식 source provenance | 남은 gap의 전면 ontology, expert review, 지식 갱신 운영 규칙 |
| Semantic Bridge | 10의 direct/data/context bridge와 20의 Pilot 이동 판단까지 준비됨 | 감각·장면 표현을 향 지식과 연결하는 Pilot, feature 조합 방식, 독립 정확도 평가 |
| 최종 추천 | 11에서 direct condition을 향수 Ranking으로 연결하는 설명 가능한 demo 존재 | 선택된 Stage 1과 Semantic Bridge의 통합, Stage 2 Human Relevance Golden Set, 사용자 만족/Ranking 평가, End-to-End 서비스 |

## 10. 다음 단계 권고

1. **16의 60개 QA를 사람이 완료하고 Stage 1 Gold를 동결한다.** 낮은 avoid/additional 점수가 모델 문제인지 표면형/annotation 문제인지 먼저 확정해야 Rule/LLM 선택이 의미가 있다. 기존 Golden Set, QA candidates, guide를 그대로 재사용할 수 있으며 새 Notebook은 필요 없다.
2. **설문 candidate를 독립 holdout으로 정리해 Stage 1 방식을 한 번만 최종 비교한다.** 현재 200개는 Extended Rule과 LLM을 비교한 개발 평가 성격이므로 일반화 확인이 필요하다. `data/survey/processed`와 13~15의 동일 metric/normalization을 재사용할 수 있다. 별도 실행 기록이 꼭 필요할 때만 하나의 최종 평가 Notebook을 만들고, 모델별 Notebook을 다시 나누지 않는다.
3. **사전 확장을 멈추고 하나의 최소 Semantic Bridge/Stage 2 Pilot으로 이동한다.** v0.3 dictionary/evidence, 10의 direct bridge, 04~09 Retrieval을 재사용해 소수의 실제 Query에서 구조화→candidate→사람 relevance 평가까지 연결해야 한다. 이 질문은 기존 Notebook에 없으므로 새 Notebook 하나가 정당화되지만, 추가 Coverage Notebook은 먼저 만들 필요가 없다.

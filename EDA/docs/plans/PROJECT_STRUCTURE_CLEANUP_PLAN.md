# Project Structure Cleanup Plan

## 1. 결론

현재 프로젝트에는 새 `notebooks/`, `archive/`, `artifacts/` 계층을 만드는 것보다 **기존 구조를 유지하면서 파일의 역할을 명확히 분류하는 방식**이 가장 적절하다.

권장안은 다음과 같다.

1. `01`~`21` Notebook은 현재 위치와 번호를 유지한다.
2. `analysis_outputs/`도 번호 prefix를 유지한 채 현재 위치에 둔다.
3. 현재 작업에 필요한 파일과 과거 실험 기록을 이 문서에서 논리적으로 구분하되, Archive 대상도 당장은 물리적으로 이동하지 않는다.
4. 승인 후 첫 정리에서는 실제 역할이 끝난 빈 scaffold와 문서 초안 등 소수의 명확한 후보만 제거한다.
5. 원본 데이터, 평가 데이터, 향 지식의 최신본과 버전 이력, 외부 근거 자료는 이동하거나 수정하지 않는다.

이 판단의 핵심 근거는 **21개 Notebook 전부가 실행 위치를 프로젝트 루트로 가정**한다는 점이다. `Path.cwd()`, `pathlib.Path.cwd()` 또는 `os.getcwd()`에서 `perfumes.csv`, `perfumes.jsonl`, `analysis_outputs/`, `data/`, `evaluation_data/`를 찾는다. 따라서 Notebook을 하위 Archive 폴더로 옮기면 경로 수정 없이 재실행할 수 없다. 파일 수를 줄이기 위해 21개 Notebook과 76개 분석 산출물의 경로를 모두 바꾸는 것은 현재 문제보다 큰 정리를 만드는 선택이다.

또한 `analysis_outputs/` 전체는 76개, 약 4.16 MB다. 파일 수는 많아 보이지만 용량이 작고 번호별 lineage가 명확하며 여러 후속 Notebook이 정확한 파일명을 참조한다. 물리적 재배치로 얻는 이득보다 의존성 파손 위험이 크다.

## 2. 조사 범위와 현재 상태

다음을 실제 파일에서 확인했다.

- 전역 `C:\Users\SSAFY\.codex\AGENTS.md`와 프로젝트 `AGENTS.md`
- `PROJECT_ANALYSIS_AUDIT.md`와 21번 요약
- `01`~`21` Notebook의 코드, 저장 출력, 파일 입출력 경로
- `analysis_outputs/` 76개 파일
- `data/` 15개 파일
- `evaluation_data/` 1개 파일
- `docs/` 2개 파일
- 프로젝트 루트의 원본 데이터, schema, 이미지, 로컬 환경 폴더

현재 확인된 주요 수치는 다음과 같다.

| 영역 | 파일 수 | 대략적 크기 | 판단 |
| --- | ---: | ---: | --- |
| Notebook | 21 | 6.19 MB | 실행 결과가 저장된 분석 기록 |
| `analysis_outputs/` | 76 | 4.16 MB | 번호별 산출물과 후속 입력이 혼재 |
| `data/` | 15 | 2.02 MB | 재사용 데이터와 버전 이력 |
| `evaluation_data/` | 1 | 0.04 MB | 보호해야 할 Golden Set |
| `docs/` | 2 | 0.02 MB | 발표 문서 초안과 최종본 |
| `venv/` | 약 28,438 | 약 629 MB | 프로젝트 자산이 아닌 로컬 실행 환경 |

`venv/`가 파일 수의 대부분을 차지하지만 이미 `.gitignore` 대상이다. 반면 의존성 manifest(`requirements.txt`, `pyproject.toml` 등)는 현재 없다. 따라서 `venv/`는 재현성 자산으로 간주할 수 없지만, 환경 목록을 별도로 확보하기 전에 바로 제거하는 것도 안전하지 않다. 이 항목은 분석 구조 정리와 분리해 다뤄야 한다.

현재 디렉터리에는 Git metadata가 없어 `git status`로 변경 이력을 확인하거나 삭제 파일을 복구할 수 없다. 실제 삭제를 승인받더라도 먼저 별도 백업 또는 복구 수단을 확인해야 한다.

## 3. 분류 기준

이 계획에서는 다음 네 상태를 사용한다.

- **CURRENT CORE**: Semantic Bridge Pilot 또는 현재 설계 판단에 직접 필요하다.
- **REPRODUCIBILITY ARCHIVE**: 현재 작업 입력은 아니지만 과거 결정, 실패 실험, 버전 lineage를 재현하는 데 필요하다. 현재 위치에 그대로 둔다.
- **REMOVE CANDIDATE**: 다른 파일로 대체됐고 후속 소비자가 없거나 내용이 비어 있다. 승인 후에만 제거한다.
- **PROTECTED**: 원본, 평가 데이터, 외부 근거 원본 또는 비밀정보다. 이동·수정·삭제하지 않는다.

`REPRODUCIBILITY ARCHIVE`는 이번 계획에서 **논리적 상태**다. 새 Archive 폴더로 옮긴다는 의미가 아니다.

## 4. 최소 변경 목표 구조

권장 구조는 현재 구조와 거의 같다.

```text
EDA/
├─ 01_...ipynb ~ 21_...ipynb     # 번호순 분석 기록, 현재 위치 유지
├─ perfumes.csv                   # PROTECTED
├─ perfumes.jsonl                 # PROTECTED
├─ SCHEMA.md                      # PROTECTED
├─ PROJECT_ANALYSIS_AUDIT.md
├─ PROJECT_STRUCTURE_CLEANUP_PLAN.md
├─ analysis_outputs/              # 번호 prefix 유지, 이동하지 않음
├─ data/
│  ├─ external/ifra/{raw,processed}/
│  ├─ scent_knowledge/
│  └─ survey/{raw,processed}/
├─ evaluation_data/stage1/        # PROTECTED
└─ docs/presentation/
```

새 `archive/`, `notebooks/active/`, `notebooks/archive/`, `artifacts/by_stage/` 폴더는 만들지 않는다. 현재 번호 prefix가 이미 분석 순서와 생성 Notebook을 표현하므로 별도 관리 체계의 이득이 작다.

## 5. 현재 핵심으로 유지할 파일

### 5.1 보호 대상

다음은 정리 대상에서 제외한다.

- `perfumes.csv`
- `perfumes.jsonl`
- `SCHEMA.md`
- `evaluation_data/` 전체
- `data/**/raw/` 전체
- `data/survey/processed/survey_nlp_queries_raw.csv`
- `.env`: 로컬 비밀정보이므로 계속 ignore하고 Archive나 보고서에 포함하지 않는다.

`perfumes.csv`와 `perfumes.jsonl`은 같은 행 수를 표현하더라도 단순 중복 파일이 아니다. Notebook에 따라 평면 컬럼과 중첩 구조를 각각 사용하므로 둘 다 유지한다.

### 5.2 CURRENT CORE Notebook

| 영역 | Notebook | 유지 근거 |
| --- | --- | --- |
| 데이터 사용 조건 | `02_data_quality.ipynb` | 원본 필드, 결측, vote와 JSONL 의미 차이의 기준 |
| Retrieval | `04_baseline_retrieval.ipynb` | Development/Final Holdout 분리와 baseline |
| Retrieval | `05_retrieval_ablation.ipynb` | Note IDF와 Accord/Note 결합 판단 |
| Retrieval | `07_community_perception_ablation.ipynb` | 신뢰 가능한 Season/Daypart signal 근거 |
| Retrieval | `09_score_calibration_ablation.ipynb` | 현재 가장 늦은 Retrieval 설정과 RAW score 유지 판단 |
| Direct Bridge | `10_query_feature_bridge.ipynb` | 자연어와 데이터 feature의 직접 연결 자산 생성 |
| Retrieval demo | `11_rule_based_query_retrieval_baseline.ipynb` | direct condition을 실제 perfume ranking으로 연결 |
| Stage 1 | `13_stage1_rule_baseline_evaluation.ipynb` | 고정 Rule baseline |
| Stage 1 | `14_stage1_extended_rule_evaluation.ipynb` | Extended Rule 비교와 16번 입력 |
| Stage 1 | `15_stage1_llm_evaluation.ipynb` | LLM 비교, prompt, checkpoint와 운영 결과 |
| Stage 1 QA | `16_stage1_golden_set_quality_audit.ipynb` | 60건 수동 QA가 아직 미완료 |
| 향 지식 | `17_ifra_knowledge_coverage_analysis.ipynb` | IFRA 가공, vocabulary, descriptor 관계의 생성 근거 |
| 향 지식 | `20_external_scent_knowledge_validation.ipynb` | 최신 v0.3과 Pilot 이동 판단 |
| Canonicalization | `21_fragrantica_note_canonicalization_audit.ipynb` | Pilot에서 사용할 canonical lookup 생성 근거 |

기존 Audit에서 09는 통합 후 Archive 가능 후보이기도 했지만, 실제 프로젝트에는 07~09 결론을 대체하는 실행 가능한 통합 Notebook이 없다. 09에는 현재 Retrieval의 가장 늦은 설정과 calibration을 채택하지 않은 근거가 저장돼 있으므로 이번 정리에서는 CURRENT CORE로 유지한다.

### 5.3 Semantic Bridge Pilot의 직접 입력

#### Direct feature와 Retrieval

- `analysis_outputs/10_query_feature_bridge.csv`
- `analysis_outputs/10_accord_dictionary.csv`
- `analysis_outputs/10_note_dictionary.csv`
- `analysis_outputs/10_accord_context_profile.csv`
- `analysis_outputs/11_rule_lexicon.csv`
- Retrieval 구현과 저장 결과가 있는 04, 05, 07, 09, 11 Notebook

#### Stage 1과 평가

- `evaluation_data/stage1/13_stage1_golden_set_v1_200.xlsx`
- `analysis_outputs/13_rule_stage1_evaluation.csv`
- `analysis_outputs/13_rule_stage1_metrics.csv`
- `analysis_outputs/14_extended_rule_stage1_predictions.csv`
- `analysis_outputs/14_extended_rule_stage1_evaluation.csv`
- `analysis_outputs/14_rule_comparison.csv`
- `analysis_outputs/15_stage1_llm_prompt_v1.txt`
- `analysis_outputs/15_llm_stage1_checkpoint.csv`
- `analysis_outputs/15_llm_stage1_predictions.csv`
- `analysis_outputs/15_llm_stage1_evaluation.csv`
- `analysis_outputs/15_llm_stage1_errors.csv`
- `analysis_outputs/15_llm_vs_extended_query_changes.csv`
- `analysis_outputs/15_stage1_model_comparison.csv`
- `analysis_outputs/16_golden_set_quality_audit_candidates.csv`
- `analysis_outputs/16_golden_set_quality_audit_guide.md`

특히 `15_llm_stage1_checkpoint.csv`는 외부 API 호출을 다시 하지 않고 15번 결과를 감사할 수 있는 원 기록이므로 제거하거나 단순 summary로 대체하면 안 된다.

#### 향 지식과 canonicalization

- `data/external/ifra/raw/ifra-fragrance-ingredient-glossary-april-2020.pdf`
- `data/external/ifra/processed/` 전체와 README
- `data/scent_knowledge/scent_term_dictionary_v0.3.csv`
- `data/scent_knowledge/scent_term_evidence_v0.3.csv`
- `data/scent_knowledge/fragrantica_note_canonical_map_v1.csv`
- `analysis_outputs/17_fragrantica_note_vocabulary.csv`
- `analysis_outputs/17_note_ifra_matching.csv`
- `analysis_outputs/17_accord_ifra_matching.csv`
- `analysis_outputs/17_ifra_descriptor_edges.csv`
- `analysis_outputs/17_ifra_secondary_primary_profile.csv`
- `analysis_outputs/20_external_note_validation_decisions.csv`
- `analysis_outputs/20_remaining_high_frequency_gaps.csv`
- `analysis_outputs/20_external_scent_knowledge_validation_summary.md`
- `analysis_outputs/21_fragrantica_note_canonicalization_summary.md`

Pilot에서는 v0.3의 `SAME_CONCEPT`와 canonical map의 `CANONICAL`/`SAME_CONCEPT`만 equivalence로 사용한다. `FAMILY`와 `RELATED`는 별도 evidence feature이며 정답이나 동의어로 합치지 않는다. `REVIEW`와 `NOT_SAME`도 자동 확장하지 않는다.

#### 실제 자연어 후보

- `data/survey/processed/survey_nlp_queries_candidates.csv`
- `data/survey/processed/survey_nlp_queries_raw.csv`
- `data/survey/processed/README.md`

후보 155건은 아직 `UNREVIEWED`/`UNASSIGNED`다. 기존 200개 Golden Set에 병합하거나 holdout label로 간주하지 않고, Pilot 입력 또는 향후 독립 평가 후보로만 유지한다.

## 6. Notebook 분류

| No | 분류 | 판단과 실제 조치 |
| ---: | --- | --- |
| 01 | REMOVE CANDIDATE | 02와 `SCHEMA.md`로 대체됨. 첫 정리에서는 유지하고 별도 삭제 승인 시에만 제거 |
| 02 | CURRENT CORE | 데이터 사용 조건의 기준 |
| 03 | REPRODUCIBILITY ARCHIVE | 관계 탐색 기록. Negative pair가 없어 AUC 질문은 성립하지 않았고 04·10이 후속 판단을 대체 |
| 04 | CURRENT CORE | Retrieval baseline과 holdout 통제 |
| 05 | CURRENT CORE | 채택 feature/weight 근거 |
| 06 | REPRODUCIBILITY ARCHIVE | Note tier가 개선되지 않은 실패 실험 |
| 07 | CURRENT CORE | Community signal 채택 근거 |
| 08 | REPRODUCIBILITY ARCHIVE | pool/gamma 안정성 탐색. 09의 최종 판단을 보조 |
| 09 | CURRENT CORE | 현재 가장 늦은 Retrieval 설정과 calibration 불필요 판단 |
| 10 | CURRENT CORE | Direct/data/context bridge 생성 |
| 11 | CURRENT CORE | Rule lexicon과 실제 retrieval 연결 |
| 12 | REPRODUCIBILITY ARCHIVE | Annotation 원칙은 유효하지만 실제 Golden Set과 다른 120-slot scaffold |
| 13 | CURRENT CORE | Current Rule 기준선 |
| 14 | CURRENT CORE | Extended Rule 및 16번 의존 입력 |
| 15 | CURRENT CORE | LLM 결과, prompt, checkpoint |
| 16 | CURRENT CORE | 60건 QA가 진행 전인 현재 작업 |
| 17 | CURRENT CORE | IFRA 가공과 향 지식 baseline |
| 18 | REPRODUCIBILITY ARCHIVE | v0.1 pilot과 최초 수동 판정 기록 |
| 19 | REPRODUCIBILITY ARCHIVE | v0.2 확장과 v0.3 이전 lineage. 20 재현 시 필요 |
| 20 | CURRENT CORE | 최신 scent knowledge 판단과 v0.3 |
| 21 | CURRENT CORE | 최신 canonicalization과 Pilot 원칙 |

Archive 대상 Notebook도 위치를 바꾸지 않는다. 번호순으로 남아 있는 편이 실험 계보를 가장 단순하게 보여주며, 이동 시 모든 Notebook의 루트 경로 가정을 수정해야 한다.

## 7. 분석 산출물과 데이터의 Archive 판단

### 7.1 현재 위치에 유지할 REPRODUCIBILITY ARCHIVE

다음은 현재 Pilot의 직접 입력은 아니지만 삭제하거나 이동하지 않는다.

- 10번의 개별 관계·co-occurrence 파일:
  - `10_note_accord_bridge.csv`
  - `10_accord_note_bridge.csv`
  - `10_accord_season_bridge.csv`
  - `10_accord_daypart_bridge.csv`
  - `10_accord_cooccurrence.csv`
- 11번의 synthetic 동작 기록과 추천 예시:
  - `11_parser_test_results.csv`
  - `11_query_diagnostics.csv`
  - `11_rule_baseline_recommendations.csv`
  - `11_unresolved_queries.csv`
- 13~15의 오류 subset, trigger, delta, 상세 comparison 파일 중 16번이 직접 읽지 않는 파일
- 17번의 extraction quality, descriptor 분포, coverage와 top-unmatched 보고 파일
- 18·19번의 decision, target, coverage contribution, summary 파일
- `data/scent_knowledge/scent_term_dictionary_v0.1.csv`
- `data/scent_knowledge/scent_term_dictionary_v0.2.csv`
- `data/scent_knowledge/scent_term_evidence_v0.1.csv`
- `data/scent_knowledge/scent_term_evidence_v0.2.csv`
- `analysis_outputs/12_annotation_guideline.md`

v0.1의 8개 term과 v0.2의 167개 term은 모두 v0.3에 포함된다. 하지만 19번은 v0.1을, 20번은 v0.1/v0.2와 18·19 산출물을 명시적으로 읽는다. 따라서 최신 runtime 입력은 아니어도 이전 판정이 최신본으로 누적되는 과정을 재현하려면 남겨야 한다.

13~15의 `errors` 파일은 대체로 `evaluation`의 실패 subset이어서 의미상 중복도가 높지만 exact byte duplicate는 아니다. 더구나 `13_rule_stage1_errors.csv`는 14번이, `15_llm_stage1_errors.csv`는 16번이 직접 읽는다. 그룹 단위로 일괄 삭제하면 안 된다.

### 7.2 REMOVE CANDIDATE

승인 후 제거할 수 있는 우선 후보는 다음 네 파일이다.

| 파일 | 근거 | 위험도 |
| --- | --- | --- |
| `analysis_outputs/12_query_annotations_long.csv` | 0 row이고 실제 Golden Set에 사용되지 않음 | 낮음 |
| `analysis_outputs/12_query_goldset.csv` | 0 row이고 XLSX Golden Set으로 대체됨 | 낮음 |
| `analysis_outputs/12_query_annotation_template.csv` | 120-slot scaffold이며 현재 200개 Golden Set schema와 연결되지 않음 | 낮음. 단 12번 재실행 시 다시 생성됨 |
| `docs/presentation/natural_language_recommendation_ppt.md` | `_final.md`로 개정된 초안이며 Notebook 의존 없음 | 낮음 |

이 네 파일은 실제 삭제 전 마지막으로 경로 검색을 다시 수행한다. 12번 Notebook은 해당 CSV를 생성하므로 파일이 없어도 과거 로직은 보존되지만, 12번을 다시 실행하면 다시 생긴다는 점을 문서화한다.

다음은 후보이지만 첫 정리에서는 제거하지 않는다.

- `01_dataset_structure.ipynb`: 02와 schema로 대체됐지만 59 KB에 불과하고 최초 구조 확인 기록이라는 최소 가치가 있다.
- `kaggle_dataset_image.png`: Notebook 참조는 없지만 데이터 출처 또는 발표 provenance 자료인지 파일명만으로 확정할 수 없다. 용도를 사용자가 확인하기 전에는 유지한다.
- `venv/`: 로컬 환경이고 `pyvenv.cfg`에 과거 위치(`Desktop\archive\venv`)가 남아 있어 이식 가능한 자산은 아니다. 그러나 dependency manifest가 없으므로 환경 목록을 확보하기 전에는 삭제하지 않는다.

`__pycache__/`는 현재 비어 있다. 승인 후 빈 디렉터리를 제거하고 `.gitignore`에 `__pycache__/`와 `.ipynb_checkpoints/`만 추가하는 것은 안전한 로컬 정리다.

## 8. 이동·삭제 전에 주의할 의존성

### 8.1 파일 의존 흐름

주요 산출물 흐름은 다음과 같다.

```text
perfumes.jsonl
  └─ 10 direct bridge outputs
       └─ 11 rule lexicon / retrieval demo
            └─ 13 Rule evaluation
                 └─ 14 Extended Rule evaluation
                      └─ 15 LLM comparison
                           └─ 16 Golden Set QA

perfumes.csv/jsonl + IFRA raw
  └─ 17 IFRA processed data / vocabulary / matching
       └─ 18 v0.1
            └─ 19 v0.2
                 └─ 20 v0.3
                      └─ 21 canonical map

evaluation_data/stage1/13_stage1_golden_set_v1_200.xlsx
  └─ 13, 14, 15, 16, 21
```

04~09는 별도 CSV를 이어받지 않고 각각 원본 JSONL을 읽지만, 실험 설계와 선택 결과는 순차적으로 이어진다. 저장된 Notebook 출력이 유일한 결과 기록이므로 이 그룹의 Notebook을 단순히 제거하면 Retrieval 판단 근거도 함께 사라진다.

### 8.2 경로 의존성

- 01~21 전부 프로젝트 루트 실행을 전제로 한다.
- 10~21은 `analysis_outputs/`, `data/`, `evaluation_data/`의 정확한 상대 경로와 파일명을 사용한다.
- 19와 20은 이전 dictionary/evidence 버전을 직접 읽는다.
- 21은 17번 vocabulary/matching, v0.3, 20번 decisions, Stage 1 Golden Set을 직접 읽는다.
- 따라서 Notebook 또는 output을 하위 Archive로 이동하려면 관련 Notebook 코드와 문서를 함께 수정하고 재실행 검증해야 한다. 현재는 그 비용을 정당화할 필요가 없다.

### 8.3 데이터와 평가 보호

- 원본과 Golden Set은 정리 편의를 위해 이동하거나 이름을 바꾸지 않는다.
- 16번 QA 결과가 나오기 전 기존 Golden Set label을 수정하지 않는다.
- Final Holdout 300개는 cleanup 검증이나 Pilot tuning에 사용하지 않는다.
- 향 지식에서 `SAME_CONCEPT`, `FAMILY`, `RELATED`, `REVIEW`, `NOT_SAME`을 폴더 정리 과정에서 합치거나 schema를 단순화하지 않는다.

### 8.4 복구와 환경

- Git repository가 아니므로 삭제 전에 별도 백업이 필요하다.
- `.env`는 읽거나 Archive하지 않는다.
- `venv/` 제거를 원한다면 먼저 현재 Notebook import에 필요한 최소 dependency와 Python 3.11 실행 조건을 별도 승인된 작업으로 기록한 뒤 새 환경에서 핵심 Notebook을 smoke test해야 한다.

## 9. 승인 후 수행할 최소 변경

### 1차 정리 권장 범위

사용자가 이 계획을 승인하면 다음만 수행한다.

1. 삭제 전 프로젝트 전체에서 네 REMOVE CANDIDATE의 참조를 다시 검색한다.
2. 복구 가능한 백업이 있음을 확인한다.
3. 다음 네 파일만 제거한다.
   - `analysis_outputs/12_query_annotations_long.csv`
   - `analysis_outputs/12_query_goldset.csv`
   - `analysis_outputs/12_query_annotation_template.csv`
   - `docs/presentation/natural_language_recommendation_ppt.md`
4. 빈 `__pycache__/`를 제거한다.
5. `.gitignore`에 `__pycache__/`와 `.ipynb_checkpoints/`만 추가한다.
6. 나머지 Notebook, output, data, evaluation, final presentation 문서는 이동하거나 수정하지 않는다.
7. 경로 검색과 파일 존재 확인으로 1차 정리를 검증한다. 분석을 재실행하거나 새로운 산출물을 만들지 않는다.

이 변경은 새 폴더를 만들지 않고, 분석 계보와 재현성을 보존하면서 역할이 끝난 파일만 정리한다.

### 별도 승인 없이는 하지 않을 작업

- Archive 폴더 생성
- Notebook 이동 또는 이름 변경
- `analysis_outputs/`의 번호별 하위 폴더화
- v0.1/v0.2 dictionary/evidence 삭제
- Stage 1 predictions/evaluation/errors 일괄 삭제
- `perfumes.csv`와 `perfumes.jsonl` 중 하나 제거
- `venv/` 삭제 또는 dependency manifest 생성
- Golden Set, survey 원본, 향 지식 relation 수정
- Notebook 병합이나 공통 pipeline/module 생성

## 10. Semantic Bridge Pilot 시작 가능 여부

**정리 후 바로 Pilot을 시작할 수 있다.** 사실 위의 최소 정리는 Pilot의 기술적 선행 조건이 아니므로, 정리 승인 전에도 필요한 자산은 이미 존재한다.

준비된 입력은 다음과 같다.

- Direct feature layer: 10번 bridge/dictionary/context
- Rule baseline과 retrieval 연결: 11번 lexicon과 demo
- Retrieval 선택 근거: 04, 05, 07, 09
- Stage 1 비교 결과: 13~15
- 현재 미완료 QA: 16번 60개 후보
- 향 지식 evidence layer: IFRA processed, v0.3 dictionary/evidence
- Canonical lookup: 21번 `fragrantica_note_canonical_map_v1.csv`
- 실제 자연어 후보: survey processed data

다만 Pilot 결과를 최종 시스템 성능으로 해석해서는 안 된다.

- 16번 QA가 미완료이므로 최종 Stage 1 parser와 Golden Set은 아직 동결되지 않았다.
- Retrieval Final Holdout은 아직 사용하지 않았다.
- FAMILY/RELATED의 Bridge feature 활용과 Human relevance는 아직 검증되지 않았다.
- Retrieval 코드는 재사용 모듈이 아니라 Notebook 안에 있다.

따라서 다음 작업은 기존 구조를 바꾸지 않고 **새 질문 하나만 답하는 Semantic Bridge Pilot Notebook 하나**로 시작하는 것이 적절하다. Pilot은 사용할 Stage 1 방식과 버전을 명시적으로 고정하고, 10·11·17·20·21의 기존 자산을 읽으며, FAMILY/RELATED를 equivalence가 아닌 별도 feature로 다뤄야 한다. 공통 pipeline이나 새 관리 계층은 반복 사용 필요가 확인되기 전에는 만들지 않는다.

## 11. 완료 판단

이 계획에 따라 사용자가 승인해야 할 실질 변경은 다음처럼 좁혀진다.

- 현재 구조와 01~21 번호 체계는 유지한다.
- Archive는 우선 논리적 분류로만 적용한다.
- 명백히 역할이 끝난 세 개의 12번 scaffold CSV와 발표 초안 한 개만 제거한다.
- 빈 cache와 ignore 규칙만 정리한다.
- 모든 원본·평가 데이터, 최신 Pilot 입력, 버전 lineage, 실패 실험은 보존한다.

이보다 큰 물리적 재구성은 현재 Semantic Bridge Pilot을 더 쉽게 시작하게 하지 않으며, 오히려 21개 Notebook의 경로 수정과 재검증을 요구한다. 따라서 위 최소 변경안을 1차 정리안으로 채택하는 것이 적절하다.

# MAP — 향 지도 데이터 작업 공간

향해의 향 지도에 쓸 좌표·유사도 데이터를 만드는 곳이다. **제품 UI는 만들지 않는다.**

모든 명령은 **`MAP/` 에서** 실행한다. 인터프리터는 `venv/Scripts/python.exe` 다 (EDA venv와 분리돼 있다 — `docs/DECISIONS.md` D7).

```bash
venv/Scripts/python.exe src/map/review_k.py
```

---

## 폴더

| 경로 | 역할 |
|---|---|
| `docs/` | 계획·의사결정·스키마 문서 |
| `src/common/` | 여러 단계가 공유하는 로직 (유사도, 캐시 생성) |
| `src/korea/` | 국내 인기 데이터 수집 → 범위 판정 → Commercial Identity → 국내 지도 |
| `src/matching/` | 국내 상품 ↔ Fragrantica 매칭 방법 실험 (DEV 평가) |
| `src/map/` | 글로벌 1,000개 향 지도 생성과 검증 |
| `viewer/` | 좌표가 말이 되는지 눈으로 보는 검증용 뷰어. **전달 산출물 아님** |
| `data/` | 국내 인기 데이터와 평가용 Gold Set. `data/**/raw/` 는 원본 스냅샷 |
| `output/` | 백엔드 전달 대상 JSON |
| `results/` | 실험 비교표 (CSV) |
| `cache/` | `perfumes.jsonl` 등에서 재생성 가능한 파생 데이터 |
| `archive/` | 완료된 작업 기록. 현재 코드 경로가 아니다 |

`AGENTS.md` 는 MAP 루트에 있어야 규약으로 로드된다. 옮기지 말 것.

`perfumes.csv`(127MB) / `perfumes.jsonl`(510MB) 는 gitignore 대상 원본이다. **수정하지 않는다.**

---

## 파이프라인

### ① 국내 인기 데이터 수집 (`src/korea/`)

| 실행 | 입력 → 산출 |
|---|---|
| `extract_korea_rankings.py` | `data/korea_popularity/raw/*.har` (무신사·올리브영·롯데) → `korea_perfume_ranking_raw.csv` (999행) |
| `extract_hwahae_ranking.py` | `raw/hwahae_*.har` → `hwahae_perfume_top100_raw.csv`, `_extraction.md` |

HAR은 로컬 스냅샷이다. 추가 네트워크 요청을 하지 않는다.

### ② Personal Fragrance 범위 판정 (`src/korea/`)

| 실행 | 산출 |
|---|---|
| `analyze_korea_rankings.py` | `korea_perfume_ranking_audit.csv`, `korea_perfume_ranking_analysis.md` |
| `classify_korea_rankings.py` | `korea_perfume_ranking_first_pass.csv` |
| `review_korea_rankings.py` | `korea_perfume_ranking_second_pass_review.csv`, `korea_perfume_manual_check_queue.csv` |
| `analyze_personal_fragrance_scope.py` | `korea_personal_fragrance_purchase_candidates.csv`, `hwahae_personal_fragrance_overlap.csv` |
| `analyze_identity_preserving_mixed.py` | `korea_personal_fragrance_mixed_*` (현재 파이프라인이 쓰는 판정본) |
| `analyze_hwahae_purchase_overlap.py` | `hwahae_purchase_keep_overlap.csv/.md` |

### ③ Identity + 국내 지도 (`src/korea/`)

| 실행 | 산출 |
|---|---|
| `build_korea_popularity_map.py` | `korea_commercial_identities.csv`, `korea_commercial_identity_members.csv`, `korea_candidate_families.csv`, `korea_map_identities.csv`, `korea_representative_perfumes_top200.csv`, `_reserve20.csv`, `_report.md`, `results/korea_layout_comparison.csv`, `results/korea_cluster_comparison.csv`, `output/korea_scent_map_v1.json` |

이 스크립트의 Fragrantica 매칭은 **fuzzy 문자열 점수 기반 구 matcher**다. 산출된 Top200은 잠정본이며 최종 데이터가 아니다 — `docs/FRONTEND_MAP_DATA_WORKFLOW.md` §1.5.

### ④ 매칭 방법 실험 (`src/matching/`) — DEV 전용

순서대로 앞 단계의 산출물을 입력으로 쓴다.

| 실행 | 산출 (`data/korea_popularity/evaluation/`) |
|---|---|
| `evaluate_fragrantica_matcher_dev.py` | `fragrantica_matcher_baseline_dev_*` |
| `evaluate_fragrantica_method1_dev.py` | `fragrantica_method1_dev_*` (다국어 임베딩 — 기각) |
| `evaluate_fragrantica_method2_dev.py` | `fragrantica_method2_dev_*` (uroman + 전용 EN→KO 음역) |
| `evaluate_fragrantica_method3_dev.py` | `fragrantica_method3_dev_*` (LLM 이름 표현. 현재 최고) |
| `build_brand_mapping.py` | `../brand_mapping_reviewed.csv` (사람 검토 브랜드 32건) |
| `evaluate_brand_mapping_dev.py` | `fragrantica_brand_mapping_dev_*` (브랜드 매핑 적용 전/후 비교) |

**`gold_set_test.csv` 는 어떤 단계에서도 열지 않는다.** 방법 선택은 DEV에서만 한다.

`evaluate_brand_mapping_dev.py` 는 실행 시 (a) 기존 method3 기록값 재현을 5개 방법 4자리까지 검증하고, (b) 보호 대상 8개 산출물의 SHA-256 불변을 검증한다. **경로·환경이 깨졌는지 확인하는 가장 빠른 수단이다** (약 20초).

### ⑤ 글로벌 향 지도 (`src/map/`, `src/common/`)

| 실행 | 산출 |
|---|---|
| `src/common/prepare_data.py` | `perfumes.jsonl` → `cache/reminds_edges.csv`, `also_liked_edges.csv`, `people.csv` |
| `src/map/build_map.py` | `output/scent_map_v1.json`, `output/diagnostic_edges.json`, `results/layout_comparison.csv`, `results/selection_comparison.csv` |
| `src/map/build_map.py --experiment-b` | `results/supervised_umap_comparison.csv` (반지도 UMAP — 기각) |
| `src/map/check_edges.py` | `results/edge_robustness.csv`, `results/human_check_pairs.csv` (D10 재현) |
| `src/map/review_k.py` | 출력만. 클러스터 k 선택 근거 (D4) 재현 |
| `src/map/verify_similarity.py` | 출력만. EDA 04 Development 700 평가 재현 (D1) |
| `src/map/plot_regions.py` | `results/region_coloring.png` |
| `src/map/build_korea_scent_map_v2.py` | `output/korea_scent_map_v1.json` + 국내 선정 CSV → `output/korea_scent_map_v2.json` (프론트 전달 스키마. 좌표 정규화, 좌표 재계산 없음) |
| `src/map/compare_korea_map_population.py` | `results/korea_population_comparison.csv` (배치 모집단 A/B × 시드 5 — D11) |
| `src/map/sweep_korea_terrain.py` | `results/korea_terrain_comparison.csv` (지형 방법 2 × 대역폭 5 × 임계 8 — D12) |
| `src/map/build_korea_terrain.py` | `korea_scent_map_v2.json` 의 `terrain`/`regions`/`contours`/`points[].region` 채움 |
| `src/map/check_korea_terrain.py` | `results/korea_terrain_check.png` + 바다에 빠진 향수·먼 정답 간선 목록 |

`src/common/scent_map.py` 는 모듈이다. 직접 실행하지 않는다.

### 뷰어

```bash
venv/Scripts/python.exe -m http.server 8000
# → localhost:8000/viewer/map_preview.html
```

`viewer/map_preview.html` 은 `../output/*.json` 을 읽는다. `file://` 로 열면 CORS로 막힌다.
`viewer/scent_family_decision.html` 은 자체 완결형이라 그냥 열면 된다 (웹폰트만 외부).

---

## 전달 산출물

| 파일 | 용도 |
|---|---|
| `output/scent_map_v1.json` | 글로벌 1,000개 좌표 + display 200 + 클러스터 + 고차원 이웃 10개. **백엔드 전달 대상** |
| **`output/korea_scent_map_v2.json`** | **국내 200개 프론트 전달본** (0.78 MB). 좌표 [0,1] 정규화(x·y 동일 배율), 밀도 지형 격자 128×136, 영역 4개 + lift 라벨, 해안선 폴리곤, 고차원 이웃 10개. `dataset_status: PROVISIONAL` |
| `output/korea_scent_map_v1.json` | v2 의 좌표 원본. raw UMAP 값이고 스키마가 다르다. **보존용** |
| `output/diagnostic_edges.json` | 뷰어 전용 |
| `results/*.csv` | 실험 비교표. 수치의 출처 |

다음 작업 계획과 스키마 v2 초안은 `docs/FRONTEND_MAP_DATA_WORKFLOW.md` 에 있다.

---

## 이동 기록 (2026-09-07)

최상위에 39개 항목이 평평하게 쌓여 있어 역할별로 나눴다. **로직은 바꾸지 않았다** — 경로 상수와 `sys.path` 만 고쳤다.

| 이전 | 현재 |
|---|---|
| `MAP/*.py` (22개) | `src/common/`, `src/korea/`, `src/matching/`, `src/map/` |
| `PLAN.md` `DECISIONS.md` `SCHEMA.md` `kaggle_dataset_image.png` | `docs/` |
| `map_preview.html` `scent_family_decision.html` | `viewer/` |
| `review_scratch/` | `archive/review_scratch/` |

검증한 것:
- 22개 모듈 전부 import 성공, 모듈 레벨 경로 상수 전부 존재 확인
- `review_k.py` 출력이 이동 전과 바이트 동일
- `check_edges.py` 산출물 2개가 이동 전 해시와 바이트 동일
- `evaluate_brand_mapping_dev.py` 전체 실행 통과 (5개 방법 재현 게이트 + 보호 파일 해시 불변)
- `data/` `output/` `results/` 78개 파일 해시 전부 불변

### 알려진 흠 4가지

**① 기존 평가 리포트에 기록된 `.py` SHA-256 은 이제 디스크의 스크립트와 다르다.**
경로 줄을 고쳤으므로 당연한 결과다. 9a-4 에서 `matcher_baseline` `method2` `method3` `brand_mapping` 4개는 재실행해 갱신했다(지표 불변 확인). **`method1` 리포트만 아직 옛 해시를 담고 있다.** 실측: `fragrantica_matcher_baseline_dev_report.md` 를 스크래치로 리다이렉트 재생성해 비교한 결과 **80줄 중 1줄**(`build_korea_popularity_map.py` 의 해시)만 달랐고 `_results.csv` 는 바이트 동일했다. **즉 지표는 그대로고 코드 해시만 어긋난다.**

이 때문에 **리포트 `.md` 는 바이트 비교로 검증하면 안 된다.** `method1`~`method3` 은 리포트에 `path.relative_to(ROOT)` 를 인쇄하므로 경로 접두사(`src/...`)까지 달라진다. `_results.csv` / `_metrics.csv` / `.json` 만 바이트 비교하고, 리포트는 digest 값과 지표 표만 비교할 것.

**② 리포트 본문의 실행 안내 문구**가 `venv/Scripts/python.exe <파일명>` 형태여서 하위 폴더를 반영하지 않는다. 리포트 생성 코드를 건드려야 해서 제외했다. 실제 명령은 위 표를 따를 것.

**③ `evaluate_fragrantica_method2_dev.py` 의 입력 해시 수집은 `if p.is_file()` 로 없는 경로를 조용히 버린다.**
경로가 틀려도 크래시가 아니라 *해시가 빠진 불완전 리포트*가 나온다. 이번 이동에서는 올바르게 수정됐음을 확인했지만, 앞으로 경로를 또 옮긴다면 리포트의 입력 해시 **줄 수와 digest 집합**을 비교해 검출해야 한다.

**④ `evaluate_fragrantica_method2_dev.py` 는 실행할 때마다 자기 리포트를 통째로 다시 써서, 사람이 손으로 덧붙인 절을 조용히 지운다.**
2026-09-07 9a-4 게이트 재앵커링 중 실제로 발생했다. `fragrantica_method2_dev_report.md` 에서 스크립트가 만들지 않는 두 절 — `## 실측 결론과 음역 품질 수동 검토`(40행), `## 캐시 재실행 검증`(6행) — 이 사라졌고 백업에서 복원했다. 지표 줄은 하나도 바뀌지 않았다.

`method2` 만의 문제다. 실측으로 확인했다 — `matcher_baseline` `method1` `brand_mapping` 리포트는 `##` 제목이 전부 생성 코드 안에 있고, `method3` 은 재실행 후에도 558행 그대로였다.

**평가 리포트를 재실행하기 전에는 `data/korea_popularity/evaluation/` 을 먼저 백업할 것.** 재실행 후 산문 줄이 사라졌는지 확인하는 방법:

```bash
diff <백업>/fragrantica_method2_dev_report.md data/korea_popularity/evaluation/fragrantica_method2_dev_report.md | grep '^[<>]' | grep -v -E 'seconds|sha256|`'
```

이 명령이 아무것도 출력하지 않아야 정상이다(타이밍·해시·경로만 달라진 상태).

**같은 세션에서 두 번 지워졌으므로 사본을 따로 뒀다** — `data/korea_popularity/evaluation/fragrantica_method2_dev_manual_review.md`. 어떤 스크립트도 이 파일을 쓰지 않는다. 리포트에서 절이 사라졌으면 여기서 되살린다. 근본 수정(리포트 생성 코드가 사람 서술을 보존하게 하거나 서술을 완전히 분리)은 팀원 산출물의 구조 변경이라 이번 범위에서 하지 않았다.

> `src/map/review_k.py` 는 자체 `sys.path` 수정이 없고 `build_map.py` 의 insert 에 전이 의존한다. 현재는 `build_map` 의 insert 가 자신의 `import scent_map` 앞에 있어 정상이다. `build_map` 의 import 순서를 바꾸면 `review_k` 가 깨진다.

---

## `archive/review_scratch/`

2026-09-05 시점 외부 검증 기록이다 (`REVIEW.md` 가 본문). 현재 코드 경로가 아니다.

재실행하려면 **`reproduce.py` 를 먼저 돌려야 한다.** `experiments.py` 는 `baseline_check.json` 에 기록된 경로 키로 해시를 확인하는데, 그 키가 이동 전 경로라서 먼저 재생성하지 않으면 `FileNotFoundError` 로 죽는다.

```bash
venv/Scripts/python.exe -B -u archive/review_scratch/reproduce.py
venv/Scripts/python.exe -B -u archive/review_scratch/experiments.py
```

`reproduce.py` `experiments.py` `frontend_check.py` 는 **같은 폴더에 함께 있어야 한다** — `frontend_check.py` 가 `experiments.py` 의 소스 텍스트를 읽어 일부를 `exec` 한다.

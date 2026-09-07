# 향 지도 프론트 전달 데이터 — 작업 방침과 워크플로우

> 목적: 국내 인기 향수 200개를 프론트엔드/디자이너가 지도로 렌더링할 수 있는 데이터로 만드는 작업의 **방침**과 **Claude Code 워크플로우 실행 프롬프트**를 정의한다.
>
> 표기: **[측정]** 이 문서를 쓰면서 직접 실행/확인한 값 · **[기록]** 기존 산출물 파일에 남아 있는 값 · **[제안]** 판단(확정 아님)

---

## 0. 한 줄 결론

**지금 데이터에서 하드 군집(cluster)은 지도의 1차 시각 언어가 될 수 없다.** silhouette이 0.09 수준이고, 사람이 "닮았다"고 투표한 쌍의 21~41%가 영역 경계를 넘는다. 그래서 **연속 밀도장(높이맵)을 1차 레이어**로, **영역 경계·지명을 2차 오버레이**로 산출한다. 사용자가 말한 "밀도, 높낮이" 방향과 데이터가 실제로 지지하는 방향이 일치한다.

---

## 1. 현재 상태 — 조사로 확인한 사실

### 1.1 이미 존재하는 두 개의 지도 산출물

| 파일 | 대상 | 좌표 | 스키마 키 | 상태 |
|---|---|---|---|---|
| `output/scent_map_v1.json` | 글로벌 인기 1,000개 (display 200) | **[0,1] 정규화, x·y 동일 배율** | `version/similarity/layout/groups/clusters/perfumes[]` | 검증 완료 (D1~D10) |
| `output/korea_scent_map_v1.json` | **국내 인기 200개** | **raw UMAP 좌표 (x 3.01~8.73 / y 3.00~9.12)** [측정] | `schema_version/selection/layout/cluster_count/cluster_labels/points[]` | 잠정본 |

**두 파일의 스키마가 서로 다르다.** 글로벌은 `perfumes[]` / `id` / `neighbors[{id,sim}]` / `seasons` / `daypart`를 갖고, 한국판은 `points[]` / `fragrantica_id` / `neighbors[int]`이며 정규화도 안 돼 있다. 지금 상태로 프론트가 둘 다 쓰려면 파서가 두 벌 필요하다. → **스키마 통일이 이번 작업의 산출물 중 하나다.**

### 1.2 국내 200개 지도의 측정값

[기록] `results/korea_layout_comparison.csv`

| layout | trust@10 | trust@20 | kNN overlap@10 |
|---|---|---|---|
| pca | 0.6589 | 0.6600 | 0.1330 |
| **umap nn=10 md=0.1 (채택)** | **0.9194** | 0.8971 | **0.4910** |
| umap nn=15 md=0.1 | 0.9225 | 0.9050 | 0.4670 |
| umap nn=30 md=0.3 | 0.8902 | 0.8861 | 0.4425 |

배치 자체는 나쁘지 않다. PCA 대비 kNN overlap이 3.7배이고, nn 6개 조합에서 trust 0.89~0.92로 일관적이다.

### 1.3 군집이 안 되는 것은 실패가 아니라 데이터의 성질이다

[기록] `results/korea_cluster_comparison.csv` — k=2~15를 전부 실행한 결과

| k | silhouette | 최대 클러스터 비중 |
|---|---|---|
| 2 | 0.1101 | 0.545 |
| 3 | 0.0972 | 0.545 |
| **4 (채택)** | **0.0911** | 0.445 |
| 8 | 0.0745 | 0.350 |
| 15 | 0.0676 | 0.330 |

**최댓값이 0.11이다.** silhouette은 1에 가까울수록 군집이 뚜렷하고 0이면 경계가 없다는 뜻인데, 어떤 k를 골라도 0.11을 못 넘는다. 글로벌 1,000개에서도 같았다(약 0.09).

이 결과를 뒷받침하는 독립적인 측정이 이미 3개 더 있다.

- [기록] `DECISIONS.md` D9 — 클러스터 라벨로 좌표를 끌어당긴 반지도 UMAP(실험 B)은 섬을 실제로 갈랐지만(silhouette 0.05→0.84), **사람이 닮았다고 투표한 쌍 중 영역이 다른 306쌍이 무작위(0.5)보다 멀어져서(0.363→0.52~0.56) 기각**됐다.
- [기록] `DECISIONS.md` D10 / `results/edge_robustness.csv` — 간선 채택 기준을 어떻게 조여도, 같은 브랜드 효과를 통제해도 **정답 쌍의 16~41%가 영역을 넘는다.**
- [기록] 4대 향 계열(Floral/Amber/Woody/Fresh) 라벨로 재배치하는 안(C)도 **정답 쌍의 50.1%가 계열 간**이라 이미 기각됐다.

→ 향수는 accord를 동시에 8개까지 갖는다. 자연적으로 분리된 덩어리가 없는 것이 정상이고, **경계를 강제하면 정답과 어긋난다는 것이 세 번 측정됐다.**

### 1.4 국내 200개만으로는 배치 품질을 정답 데이터로 검증할 수 없다

[측정] `cache/reminds_edges.csv`(692,729 directed)를 현재 `korea_scent_map_v1.json`의 200개 안으로 제한한 결과:

| 항목 | 값 |
|---|---|
| 200개 내부 reminds_me_of 간선 (방향 포함) | **117** |
| 신뢰 간선 (찬성≥3 & 찬성>반대) | **40** |
| 신뢰 간선을 하나라도 가진 향수 | **44 / 200 (22%)** |
| 200개 내부 also_liked 간선 (진단용) | 564 |

글로벌 1,000개에서는 신뢰 간선 872개 / 보유 노드 467개였다. **200개 집합은 정답 밀도가 20분의 1 수준이다.** 즉 "국내 200개만 따로 배치"하면 그 배치가 맞는지 판정할 근거가 거의 없다. → §2 P2의 근거.

### 1.5 현재 200개는 **잠정 데이터**다 — 최종본이 아니다

[기록] `data/korea_popularity/korea_representative_perfumes_report.md`

- 구매 상품 행 828 · 화해 100 → Commercial Identity 683 → Fragrantica MATCH 기반 Map Identity **230** → TOP200 + reserve 20
- `fragrantica_match_status`: MATCH 252 / MATCH_REVIEW 36 / NO_MATCH 324
- **이 MATCH는 fuzzy 문자열 점수 기반 자동 매칭이다.** 인수인계 문서(§17)가 기록한 실제 오매칭 사례: `Clean Cool Cotton → Warm Cotton`, `Versace Eros Energy → Eros Najim`, `Miss Dior EDP → 1947 Miss Dior`.
- [기록] Method 3(LLM 이름 표현) DEV 결과 — 이름 후보 검색은 크게 개선됐다.

  | 방법 | R@1 | R@3 | R@5 | R@10 | MRR |
  |---|---:|---:|---:|---:|---:|
  | baseline lexical | 0.3115 | 0.5082 | 0.5902 | 0.6721 | 0.4451 |
  | dedicated EN→KO | 0.4590 | 0.6230 | 0.6721 | 0.7377 | 0.5590 |
  | **LLM KO→Latin** | **0.5410** | **0.7869** | 0.7869 | 0.7869 | **0.6569** |
  | LLM Latin→KO | 0.5410 | 0.7705 | 0.7869 | **0.8033** | 0.6543 |

- [측정] 사람이 검토한 브랜드 리뷰 `data/korea_popularity/evaluation/fragrantica_unresolved_brand_review.xlsx`의 `내 검토 결과` 열은 **MATCH 32 / NOT_IN_FRAGRANTICA 42**로 인수인계 문서와 일치한다. **아직 matcher에 반영되지 않았다.**
- Retrieval(후보 찾기)은 좋아졌지만 **Verification(후보 중 정확히 하나 확정)은 아직 구현되지 않았다.** R@5 0.79는 "정답이 5개 안에 있다"는 뜻이지 "1개를 맞혔다"가 아니다.

→ **결론: 프론트에 넘길 데이터의 "형태"는 지금 확정할 수 있지만, "내용(어떤 향수 200개인가)"은 아직 확정할 수 없다.** 이것이 워크플로우를 두 트랙으로 나누는 이유다(§5).

### 1.6 EDA에 있는 재사용 자산

| 파일 | 용도 |
|---|---|
| `EDA/analysis_outputs/10_note_dictionary.csv` | note 2,523종의 IDF. `scent_map.py`가 이미 로드해서 씀 |
| `EDA/analysis_outputs/10_accord_dictionary.csv` | accord 92종의 코퍼스 전체 빈도 → **영역 라벨 lift 계산의 분모** |
| `EDA/analysis_outputs/10_accord_season_bridge.csv` | accord별 계절 편향 → 필터/카드 표시 후보 |
| `EDA/analysis_outputs/10_accord_cooccurrence.csv` | accord 동시출현 jaccard/lift |
| `EDA/data/scent_knowledge/scent_term_dictionary_v0.3.csv` | 향 용어 표준화(197행, 근거 포함) |
| `EDA/data/scent_knowledge/korean_scent_lexicon_v0_1.csv` | 실제 사용자 질의에서 나온 한국어 표현 346종 |
| `EDA/data/scent_knowledge/source/perfume_14families_korean_descriptors.md` | 14개 패밀리별 한국어 묘사 어휘(웹 검증 9회 판본) |

→ **한국어 지명/영역 이름은 데이터 담당이 만들지 않는다.** 위 3개 파일을 근거 후보로 기획에 넘긴다(§2 P5).

---

## 2. 작업 방침 (P0~P7)

### P0. 이 작업은 "빅데이터 문제"가 아니다 — 규모를 두 층으로 분리한다

| 층 | 규모 | 성격 | 필요한 것 |
|---|---|---|---|
| 상류: 유사도 | 131,930 향수 × (accord 92 + note 2,523) | 희소 행렬. **여기가 유일한 대규모 구간** | 이미 EDA에서 해결됨. sparse CSR + IDF. **재구현 금지** |
| 하류: 지도 배치 | **200 (확장 시 1,000~2,000)** | dense 거리행렬이 즉시 계산됨 | 근사·분산 알고리즘 **불필요** |

200×200 거리행렬은 40,000셀이다. 1,000×1,000이라도 8MB다.

**임계값 방침 [제안]** — 나중에 규모를 키울 때만 알고리즘을 바꾼다.

- N ≤ 2,000: `metric='precomputed'` dense UMAP (정확·재현 가능). 2,000² float64 = 32MB
- 2,000 < N ≤ 10,000: dense도 가능하나(800MB) 메모리 주의. feature 공간 UMAP + `pynndescent` ANN 권장
- N > 10,000: **거리행렬을 만들지 않는다.** sparse feature → `pynndescent`(umap-learn 의존성으로 이미 설치됨)로 kNN 그래프만 만들어 UMAP에 넣는다

**"빅데이터니까 Spark/벡터DB/GPU"는 이 프로젝트의 문제를 하나도 풀지 않는다.** 도입 근거가 생기는 조건은 위 임계값뿐이다.

### P1. 하드 군집을 1차 시각 언어로 쓰지 않는다

근거는 §1.3의 4개 측정. 대신:

1. **1차 레이어 = 연속 밀도장** — 점이 몰린 곳이 육지/고지대, 빈 곳이 바다. 분류 라벨을 전혀 쓰지 않는다.
2. **2차 레이어 = 영역 경계 + 지명** — 벽이 아니라 지명으로 쓴다. 경계를 넘는 이웃이 정상이라는 것을 UX 문구에 반영.
3. **정확한 "비슷한 향수"는 2D 거리가 아니라 고차원 `neighbors` 배열** — 기존 결정 유지.

### P2. 밀도장은 "표시 200개"가 아니라 "레이아웃 모집단"에서 만든다 [제안 — 실험으로 확정]

200개 점으로 KDE를 하면 지형이 200개의 우연한 배치를 그린다. 게다가 §1.4대로 200개만으로는 검증이 안 된다.

두 안을 **측정으로 비교한다.**

| 안 | 내용 | 기대 이득 | 비용 |
|---|---|---|---|
| **A. 200-only** | 현재 방식 유지 | 단순. 좌표가 200개에 최적화 | 지형이 얇음. 정답 간선 40개뿐 → 검증 불가. 향수 추가 시 전체 재배치 |
| **B. 확장 모집단 + display 200** | 한국 map-ready 후보 + 글로벌 인기 풀로 N을 1,000 내외까지 키우고 200개만 `display=true` | 지형이 두꺼워짐. 정답 간선 확보 → 검증 가능. 줌인 노출 여유분. 향후 확장 시 좌표 안정 | 200개 배치가 200-only만큼 최적은 아닐 수 있음 |

**비교 지표(모두 200개 부분집합 기준):** trust@10, kNN overlap@10, 200개 내부 정답 간선의 2D 거리 백분위, **시드 5개 재실행 시 밀도 격자의 상관계수**(지형 안정성).

> 글로벌 `scent_map_v1.json`이 이미 B 구조(1,000 좌표 + display 200)다. 재사용하면 새 개념을 만들지 않아도 된다.

### P3. 좌표는 프론트가 바로 쓸 수 있는 형태로 고정한다

- **[0,1] 정규화, x·y 동일 배율**(글로벌 결정 D5와 동일). 현재 한국판 raw 좌표는 반드시 고친다.
- JSON에 `bounds`를 명시하고 **프론트는 문서가 아니라 JSON의 값을 읽는다.** 어느 축이 1.0을 채우는지는 재생성마다 바뀔 수 있다(D5에서 실제로 바뀜).
- `distance_is_metric: false`와 실측 `trust@10` / `knn_overlap@10`을 함께 실어, "지도상 거리 = 유사도"라는 오해를 데이터 자체가 막는다.

### P4. 영역 라벨은 빈도가 아니라 두드러짐(lift)으로 만든다

[기록] 빈도 상위 3개로 이름을 붙였더니 9개 영역 중 4개 이름에 `woody`가 들어갔다. woody는 전체 향수의 61.7%에 있는 배경이라 어느 무리에서든 상위에 온다.

**규칙 [제안]**: 클러스터 내 **coverage ≥ 0.30**인 accord만 후보로 두고(희귀 accord 우연 방지), `클러스터 내 보유율 ÷ 코퍼스 전체 보유율` 상위 3개를 라벨로 쓴다. 분모는 `EDA/analysis_outputs/10_accord_dictionary.csv`의 `perfume_share`.

효과 예시 [기록]: `powdery·woody·musky` → **`iris (6.9×) · musky (3.9×) · powdery (3.4×)`**. 기존 FE 논의 스케치는 향수당 상위 accord 5개로 계산한 근사값이므로 **파이프라인에서는 8개 전체로 다시 계산한다.**

> 유사도 계산에서는 IDF(흔한 것 감점)를 적용하면 성능이 떨어져 쓰지 않았다(D1). 이름 붙이기에서는 반대로 흔한 것을 빼야 한다. **"두 향수가 비슷한가"와 "이 무리가 무엇이 다른가"는 다른 질문이라 다른 가중치가 맞다.** 이 비대칭을 문서에 남긴다.

### P5. 한국어 이름은 데이터가 정하지 않는다

accord 근거(이름, lift, coverage)만 산출하고 한국어 지명은 기획이 결정한다. CLAUDE.md의 "근거 없는 scent inference 금지". 단 §1.6의 3개 한국어 자산을 **후보 어휘 근거로 함께 전달**해 기획이 맨손으로 시작하지 않게 한다.

### P6. 매칭 미확정 상태를 데이터에 정직하게 표시한다

§1.5대로 현재 200개는 구 fuzzy matcher 산출이다. 프론트/디자인 작업을 막지 않으면서 거짓말도 하지 않는 방법은 하나다 — **필드로 드러낸다.**

- 최상위 `dataset_status: "PROVISIONAL" | "VERIFIED"`
- 향수별 `match.status` / `match.basis` / `match.verification_status`
- **`fragrantica_id`와 `map_identity_id`를 안정 키로 고정**해서, 내용이 교체돼도 프론트 코드가 안 바뀌게 한다.

### P7. 기존 결과 파일을 덮어쓰지 않는다

`korea_scent_map_v1.json`은 그대로 두고 `korea_scent_map_v2.json`을 새로 만든다. 원본 `perfumes.csv` / `perfumes.jsonl` / `EDA/**` / 사람 검토 파일은 읽기 전용. `gold_set_test.csv`는 **어떤 단계에서도 열지 않는다.**

---

## 3. 알고리즘 선택 — 목적별 정리

| 목적 | 후보 | **선택** | 근거 |
|---|---|---|---|
| 향수 간 유사도 | 재사용 / 텍스트 임베딩 / 그래프 거리 | **재사용 고정** `0.5·cos(accord L2) + 0.5·IDF Jaccard(note)` | D1에서 EDA 04 재현이 소수점 4자리까지 일치. 다국어 의미 임베딩은 이름 매칭에서 이미 기각(Method 1, R@5 0.33) |
| 2D 배치 | UMAP / t-SNE / MDS / PCA | **UMAP `precomputed`, nn=10, md=0.1, seed 고정** | 한국 200 기준 kNN overlap 0.491 vs PCA 0.133 [기록]. t-SNE는 클러스터 간 거리에 의미가 없어 **지형을 만들 수 없다.** MDS는 글로벌에서 overlap 0.0835로 PCA와 사실상 동급 |
| 좌표 안정성 | 단일 실행 / 다중 시드 | **시드 5개 재실행 후 지표·밀도격자 상관 확인** | 소규모 N에서 UMAP이 가짜 클러스터를 만드는 알려진 위험. `review_scratch`에 시드 5개 확인 선례 있음 |
| 군집 | k-means / Agglomerative(precomputed) / HDBSCAN | **Agglomerative average linkage, precomputed 유지 + k는 라벨 용도로만** | 배치에 쓴 것과 같은 거리를 써야 일관됨. k-means는 유클리드 가정이라 부적합. HDBSCAN은 silhouette 0.09 데이터에서 대부분을 noise로 던질 위험이 크고 그 결과는 §1.3이 이미 예측함 |
| **높이/밀도장** | 2D Gaussian KDE / 히스토그램+블러 / 거리기반 보간 | **KDE(기본) + 히스토그램+블러(비교군)** | KDE는 표준적이고 bandwidth 하나로 조절된다. 비교군을 같이 만들어 "지형이 방법에 따라 안 바뀐다"를 보인다 |
| KDE bandwidth | Scott / Silverman / 수동 스윕 | **Scott 기본 + 0.5×·2× 스윕** | 스윕 결과의 육지 개수와 격자 상관을 기록. **"보기 좋은 값"을 근거 없이 고르지 않는다** |
| 영역 경계 | 클러스터별 밀도 우세 격자 / Voronoi / convex hull | **클러스터별 밀도 우세 격자 → 등고선 폴리곤화** | 월경지(다른 영역 안의 작은 구역)를 **보존**할 수 있는 유일한 방식. convex hull은 형태를 왜곡하고 서로 겹친다 |
| 지명 위치 | 무게중심 / 최대밀도점 | **영역 내 KDE 최댓값 격자점** | 오목한 영역에서 무게중심은 영역 밖으로 나갈 수 있다 |
| 라벨 겹침 | 서버에서 해결 / FE LOD | **FE 몫. 대신 `display_priority` 제공** | 200개 라벨 동시 표시는 불가능. 우선순위는 한국 인기 랭크(RRF)로 데이터가 주고, 실제 배치는 화면 크기를 아는 FE가 결정 |

**밀도장을 인기도로 만들지 않는다 [제안].** 높이 = "향의 공간에서 얼마나 붐비는가"이고, 인기도는 별도 채널(점 크기 / `display_priority`)로 준다. 두 개를 한 축에 섞으면 "높은 곳"이 무슨 뜻인지 아무도 설명할 수 없게 된다.

---

## 4. 산출 스키마 v2 (초안)

한국판과 글로벌판 스키마를 통일한다. 파일: `output/korea_scent_map_v2.json`.

```jsonc
{
  "schema_version": 2,
  "dataset_status": "PROVISIONAL",        // P6. VERIFIED 전까지 PROVISIONAL
  "generated_at": "2026-09-07T00:00:00Z",
  "source": {
    "perfumes_csv_sha256": "...",         // 재현성. 기존 INPUT_HASHES 방식 재사용
    "selection_source": "korea_representative_perfumes_top200.csv",
    "matcher_version": "..."
  },
  "similarity": { "accord_weight": 0.5, "note_weight": 0.5,
                  "note_weighting": "idf", "source": "EDA 04-06" },
  "layout": {
    "method": "umap", "n_neighbors": 10, "min_dist": 0.1, "random_state": 42,
    "population": 1000, "display_count": 200,      // P2 실험 결과에 따라
    "normalization": "[0,1], uniform scale on x and y",
    "distance_is_metric": false,
    "metrics": { "trust_at_10": 0.0, "knn_overlap_at_10": 0.0,
                 "reminds_pct": 0.0, "seed_stability_corr": 0.0 }   // 실측 기입
  },
  "bounds": { "x_min": 0.0, "x_max": 0.8476, "y_min": 0.0, "y_max": 1.0 },

  "terrain": {                                   // ★ 밀도/높이 레이어
    "method": "gaussian_kde", "bandwidth": "scott", "bandwidth_value": 0.0,
    "grid_width": 128, "grid_height": 150,       // bounds 종횡비에 맞춤
    "value_range": [0, 255],                     // uint8 양자화 (파일 크기)
    "encoding": "row_major_uint8_array",
    "values": [],                                // grid_width * grid_height
    "sea_level": 0.55,                           // 밀도 백분위. FE 조정 가능 파라미터
    "sea_level_basis": "percentile_of_grid_values"
  },
  "contours": [                                  // 2D 렌더용 등고선 (선택)
    { "level": 0.55, "polygons": [] }
  ],

  "regions": [
    { "id": 0, "size": 62,
      "label_accords": [ { "name": "iris", "lift": 6.9, "coverage": 0.41 } ],  // P4
      "name_ko": null,                            // P5. 기획이 채운다
      "polygon": [],                              // MultiPolygon — 월경지 보존
      "label_anchor": { "x": 0.0, "y": 0.0 } }
  ],

  "points": [
    { "map_identity_id": "fragrantica:65738",
      "fragrantica_id": 65738,
      "brand": "Diptyque", "name": "Orpheon Eau de Parfum", "year": 2021,
      "x": 0.12, "y": 0.44,
      "display": true,
      "display_priority": 1,                      // = selection_rank
      "region": 0,

      "korea": {                                  // 한국 인기 신호 (글로벌 인기 아님)
        "selection_rank": 1, "selection_basis": "HWAHAE_MAP_READY_INCLUSION",
        "has_purchase_signal": false, "has_hwahae_signal": true,
        "best_hwahae_rank": 7, "purchase_rrf_k60": 0.0 },

      "match": {                                  // P6
        "status": "MATCH", "basis": "...", "verification_status": "UNVERIFIED" },

      "top_accords": [ { "name": "powdery", "strength": 100 } ],   // 8개 전체
      "seasons": { "winter": 0.14, "spring": 0.33, "summer": 0.27, "autumn": 0.26 },
      "daypart": { "day": 0.66, "night": 0.34 },
      "neighbors": [ { "id": 637, "sim": 0.71 } ]  // 고차원 기준. 2D 거리 아님
    }
  ]
}
```

**설계 의도**

- `terrain.values`를 uint8로 양자화 — 128×150 격자가 19,200바이트. 좌표 200개보다 작다.
- `sea_level`을 **값이 아니라 파라미터로 노출** — 기존 스케치의 "하위 55%"는 임의 기준이므로 FE가 화면 보고 조정할 수 있어야 한다.
- `regions[].polygon`은 MultiPolygon — 월경지는 데이터에 실제로 있는 무리이므로 지우지 않는다.
- `seasons` / `daypart`는 **좌표 계산에 쓰지 않고 필터·카드 표시용으로만** 싣는다(기존 결정 유지).
- `neighbors`가 정답 경로다. 2D 거리로 "비슷한 향수"를 계산하지 말라는 것을 FE 전달 문서에 명시한다.

---

## 5. 워크플로우 — 두 트랙

작업은 **정확성 트랙(데이터 확정)** 과 **속도 트랙(FE 전달)** 으로 나뉜다. 두 트랙은 만드는 것이 다르다 — **정확성 트랙은 "어떤 향수 200개인가(내용)"를, 속도 트랙은 "어떤 형태로 넘기는가(스키마)"를 만든다.**

### 확정된 실행 순서 (2026-09-07 사용자 결정)

**정확성 트랙 먼저.** 매칭이 확정된 데이터 위에서 지도를 한 번만 만든다.

```
Phase 0   인벤토리 + 폴더 전체 재구성            [선행]
   |
Phase B1  Brand Mapping 적용 -> Method 3 DEV 재평가 (단일 변수)
Phase B2  Verification 설계·구현 -> 최종 Fragrantica ID 확정
Phase B3  최종 대표 200 재선정
   |
Phase A1  스키마 v2 + 좌표 정규화                (확정된 200개로)
Phase A2  밀도장/영역/등고선 산출 + 뷰어 확인
Phase A3  FE 전달 문서                           -> dataset_status: VERIFIED
```

- 이 순서에서는 **Phase B4가 필요 없다.** Phase A가 처음부터 최종 데이터 위에서 돌기 때문이다.
- 대신 **FE/디자인이 Phase B가 끝날 때까지 대기한다.** 이 대기 비용을 줄이려면 Phase A1의 스키마 초안(§4)만 먼저 프론트에 공유해 렌더링 설계를 병행하게 할 수 있다 — 데이터 없이 형태만 공유하는 것이므로 Phase B와 충돌하지 않는다.
- Phase B가 예상보다 길어지면 그때 속도 트랙을 먼저 돌리는 판단으로 되돌릴 수 있다. 그 경우 Phase A 산출물에 `dataset_status: "PROVISIONAL"`을 쓰고, 나중에 Phase A를 최종 데이터로 재실행한다(원래의 Phase B4).

**핵심 제약: Phase A는 스키마를, Phase B는 내용을 만든다. Phase A 도중에 매칭 로직을 손대면 두 트랙이 섞여 원인 분리가 불가능해진다.**

### Phase별 정의

| Phase | 입력 | 절대 바꾸지 않을 것 | 산출물 | 합격 기준 |
|---|---|---|---|---|
| **0** ✅ 완료 (2026-09-07) | MAP 전체 | 스크립트 **동작** | 새 폴더 구조, `MAP/README.md` 인덱스 | 이동한 스크립트가 전부 import·실행되고, 재실행 가능한 스크립트는 산출물이 **바이트 동일** |
| **A1** ✅ 완료 (2026-09-07) | `korea_scent_map_v1.json`, `korea_representative_perfumes_top200.csv` | 좌표의 **상대 배치**, 유사도, 선정 결과 | `korea_scent_map_v2.json` (좌표 정규화 + 스키마 v2, terrain 없음) | 200개 전부 [0,1] 범위, x·y 배율 동일, NaN 0건, 모든 `neighbors[].id`가 파일 안에 존재 |
| **A2** ✅ 완료 (2026-09-07) | A1 산출물 + 거리행렬 | A1의 좌표 | `terrain`, `regions`, `contours` 추가 + `results/korea_terrain_comparison.csv` | KDE bandwidth 3개 · 방법 2종 · 시드 5개에서 **밀도 격자 상관 ≥ 0.9**, 육지 덩어리 개수가 흔들리지 않음. 흔들리면 그대로 기록 |
| **A3** | A2 산출물 | 데이터 | `docs/FRONTEND_HANDOFF.md`, 뷰어 확인 결과 | FE가 스키마만 보고 렌더 가능. 오해 방지 문구(거리≠유사도, sea_level은 조정값, PROVISIONAL) 포함 |
| **B1** | 브랜드 리뷰 xlsx의 MATCH 32건 | Gold/DEV split, LLM 출력, 이름 정규화, 유사도, 후보 랭킹, 농도/형태 필터 | `data/korea_popularity/brand_mapping_reviewed.csv`(하드코딩 금지) + Method 3 재평가 metrics | 기존 Method 3 **재현 먼저 확인**(수치 동일). 그 후 R@1/3/5/10·MRR·BRAND_BLOCKED 7건 변화를 전/후로 기록 |
| **B2** | B1 Top-K 후보 | B1 결과 | Verification 로직 + DEV 정확도 | **fuzzy 점수 하나로 확정 금지.** 브랜드/농도/형태/flanker/출시연도 근거를 각각 기록. 근거 부족은 UNRESOLVED 유지 |
| **B3** | B2 확정 ID | 한국 인기 신호 정의 | 새 Top200 + reserve | 향 계열 quota 없음. Fragrantica 글로벌 인기 미사용. 같은 Fragrantica ID 중복 점 0건 |
| **B4** ※ | B3 + Phase A 파이프라인 | **스키마** | `korea_scent_map_v2.json` 갱신, `dataset_status: VERIFIED` | v1 대비 교체된 향수 목록과 사유를 표로 남김 |

※ B4는 **속도 트랙을 먼저 돌렸을 때만** 필요하다. 확정된 순서(정확성 트랙 선행)에서는 Phase A가 이미 최종 데이터 위에서 돌므로 실행하지 않는다. Phase A1의 `dataset_status`도 처음부터 `VERIFIED`로 쓴다.

### Phase 0 폴더 구조 [제안]

```text
MAP/
├─ README.md                     # ★ 신규. "무엇이 어디에" 인덱스 한 장
├─ AGENTS.md                     # 위치 유지 (MAP 루트에서 읽히는 규약)
├─ docs/
│  ├─ PLAN.md  DECISIONS.md  SCHEMA.md
│  ├─ FRONTEND_MAP_DATA_WORKFLOW.md   # 이 문서
│  └─ FRONTEND_HANDOFF.md             # Phase A3 산출
├─ src/
│  ├─ common/        scent_map.py  prepare_data.py
│  ├─ korea/         extract_korea_rankings.py  extract_hwahae_ranking.py
│  │                 classify_korea_rankings.py  review_korea_rankings.py
│  │                 analyze_korea_rankings.py  analyze_hwahae_purchase_overlap.py
│  │                 analyze_personal_fragrance_scope.py
│  │                 analyze_identity_preserving_mixed.py
│  │                 build_korea_popularity_map.py
│  ├─ matching/      evaluate_fragrantica_matcher_dev.py
│  │                 evaluate_fragrantica_method1_dev.py
│  │                 evaluate_fragrantica_method2_dev.py
│  │                 evaluate_fragrantica_method3_dev.py
│  └─ map/           build_map.py  check_edges.py  review_k.py
│                    verify_similarity.py  plot_regions.py
├─ data/            (현행 유지: korea_popularity/, korea_popularity/raw/, evaluation/)
├─ output/  results/  cache/
├─ viewer/           map_preview.html  scent_family_decision.html
└─ archive/          review_scratch/
```

**Phase 0의 유일한 위험과 대응**

스크립트가 `ROOT = Path(__file__).resolve().parent`와 `import scent_map as sm`를 쓴다. 폴더를 파면 둘 다 깨진다. → 각 파일에 **두 줄만** 추가한다.

```python
ROOT = Path(__file__).resolve().parents[2]      # MAP/
sys.path.insert(0, str(ROOT / "src" / "common"))
```

새 추상화(경로 모듈, 설정 시스템, 패키지화)를 만들지 않는다. 이 두 줄 이상을 고치고 있다면 범위를 벗어난 것이다.

> **대안(더 안전, 시인성은 낮음)**: `.py`는 루트에 그대로 두고 문서·뷰어·스크래치만 폴더로 옮긴 뒤 `README.md` 표로 분류를 보여준다. 실행 경로가 하나도 안 바뀐다. **Phase 0 시작 전에 두 안 중 하나를 선택할 것.**

---

## 6. 워크플로우 실행 프롬프트

### 6.1 마스터 프롬프트 (공통 헤더 — 각 Phase 프롬프트 앞에 붙인다)

```text
너는 향해 프로젝트의 향 지도 데이터 작업을 진행한다.

[먼저 읽을 것]
1. 루트 CLAUDE.md
2. MAP/AGENTS.md
3. MAP/docs/FRONTEND_MAP_DATA_WORKFLOW.md   <- 이 작업의 방침 문서
4. MAP/DECISIONS.md 의 D1~D10
5. 해당 Phase가 지정한 파일

[불변 규칙]
- 실제 실행 결과로 확인하지 않은 수치를 쓰지 않는다. 추정치를 결과처럼 쓰지 않는다.
- 기존 결과 파일을 덮어쓰지 않는다. 새 파일은 _v2 등으로 구분한다.
- perfumes.csv / perfumes.jsonl / EDA/** / 사람이 검토한 파일은 읽기 전용이다.
- MAP/data/korea_popularity/evaluation/gold_set_test.csv 는 어떤 이유로도 열지 않는다.
- 한 Phase에서는 주요 변경을 하나만 한다. 성능이 변했을 때 원인을 하나로 지목할 수 있어야 한다.
- 사람이 검토·확정한 결과를 코드가 자동으로 뒤집지 않는다.
- row 수 / marketplace SKU 수 / Commercial Identity 수 / Map Identity 수를 혼동하지 않는다.
- 새 추상화·프레임워크·설정 시스템을 만들지 않는다. 단일 스크립트로 충분하다.
- 실패하거나 기대에 못 미친 결과를 숨기거나 좋게 표현하지 않는다.

[보고 형식] 각 Phase 종료 시 반드시 남긴다.
- 실행한 명령
- 입력 행 수 / 출력 행 수 / 제외·오류 건수
- 측정 지표 (변경 전 -> 변경 후)
- 검증한 방법
- 미해결 REVIEW / MANUAL_CHECK 항목
- 다음 결정에 영향을 주는 한계
```

### 6.2 Phase 0 — 인벤토리와 폴더 정리

```text
[Phase 0] MAP 폴더 인벤토리 및 재구성

1. 조사 (수정 금지)
   - MAP 아래 모든 .py / .md / .json / .csv / .html 을 목록화한다
     (venv, cache/model, __pycache__, numba_cache 제외).
   - 각 .py 의 (a) 입력 파일, (b) 출력 파일, (c) import 관계, (d) 마지막 실행 흔적을 표로 만든다.
   - 어떤 스크립트가 현재 산출물을 만들었는지, 재실행 가능한지(입력이 남아 있는지) 판정한다.
   - git 추적 여부(tracked / untracked)를 함께 표시한다.

2. 결정 확인
   - 2026-09-07 확정: **전체 재구성**. 방침 문서 5장 Phase 0 의 트리를 그대로 따른다.

3. 실행
   - tracked 파일은 git mv 를 사용한다. untracked 는 일반 이동.
   - 이동한 스크립트에는 경로 두 줄만 수정한다. 로직은 한 줄도 바꾸지 않는다.
   - MAP/README.md 를 새로 만든다:
     폴더별 역할 1줄 + 주요 산출물 파일 표 + "무엇을 다시 만들려면 무엇을 실행하는가" 표.

4. 검증 (필수)
   - 이동한 모든 .py 에 대해 import 스모크 테스트를 실행한다.
   - 재실행이 저렴한 스크립트(review_k.py, check_edges.py, verify_similarity.py 등)는 실제로 재실행해
     기존 산출물과 바이트 동일한지 확인한다. 다르면 즉시 되돌리고 원인을 보고한다.
   - 재실행이 비싼 스크립트는 그 사실과 미검증 상태를 명시한다.

[산출] 재구성된 트리, MAP/README.md, 이동 전후 경로 대응표, 검증 결과
[금지] 스크립트 로직 수정, 파일 삭제, 데이터 이동, 리팩터링
```

### 6.3 Phase A1 — 스키마 v2와 좌표 정규화

> **완료 (2026-09-07).** `src/map/build_korea_scent_map_v2.py` → `output/korea_scent_map_v2.json` (0.40 MB).
>
> | 합격 기준 | 실측 |
> |---|---|
> | points 200 / 중복 id 0 / NaN 0 / 이웃 미해결 0 | 통과 |
> | x·y 동일 배율 | 공통 배율 **6.121255**. raw 폭 x 5.7225 / y 6.1213 → 정규화 폭 x **0.9348** / y **1.0000** |
> | 종횡비 보존 | 0.934851 → 0.934850 (오차 1e-6) |
> | **v1 이웃 집합 재현** | **200/200 일치** — 유사도 재구현이 맞다는 증거 |
> | v1 파일 무변경 | SHA 불변 확인 |
>
> 부수 실측: `seasons` 194/200 · `daypart` 191/200 (나머지는 투표 20 미만이라 `null`. `build_map.season_block` 을 그대로 재사용해 글로벌판과 같은 기준). accord 8개 198건 / 7개 2건. `match.status` 전부 MATCH.
>
> **§4 스키마 초안에서 바꾼 것 4가지**
> - `terrain` / `contours` / `regions` 를 키만 두고 `null` — Phase A2 산출물이다. 키를 아예 빼지 않은 이유는 프론트가 최종 키 집합에 맞춰 코딩할 수 있게 하려는 것이다.
> - `points[].region` 도 같은 이유로 `null`.
> - **v1 의 `cluster` / `cluster_label`(k=4, silhouette 0.09) 을 일부러 옮기지 않았다.** 빈도 기반 라벨이라 A2 에서 두드러짐(lift) 기반으로 대체하는데, 그대로 실으면 프론트가 약한 군집을 1차 시각 언어로 쓰게 된다(P1·P4).
> - `layout.metrics` 에 `trusted_reminds_edges_in_set: 40` / `perfumes_with_trusted_reminds_edge: 44` 를 추가. 프론트·기획이 "이 지도가 얼마나 검증됐는지"를 데이터에서 바로 알 수 있어야 한다. `reminds_distance_percentile` 은 A2 에서 측정한다.
>
> `gender` 도 글로벌판과 맞추려고 추가했다.

```text
[Phase A1] 프론트 전달 스키마 v2 생성 (좌표 정규화)

[입력]
- MAP/output/korea_scent_map_v1.json (200개, raw UMAP 좌표)
- MAP/data/korea_popularity/korea_representative_perfumes_top200.csv
- MAP/data/korea_popularity/korea_map_identities.csv
- MAP/output/scent_map_v1.json (스키마 참조용. 수정 금지)

[작업]
1. 방침 문서 4장의 스키마 v2 로 korea_scent_map_v2.json 을 만든다.
   이번 단계에서는 terrain / regions / contours 를 제외하고 나머지를 채운다.
2. 좌표를 [0,1] 로 정규화하되 x 와 y 에 같은 배율을 적용한다.
   축별 정규화 금지 - 종횡비가 깨지면 UMAP 거리 구조가 왜곡된다.
3. bounds 를 계산해 싣는다.
4. top_accords 는 상위 5개가 아니라 향수가 가진 accord 8개 전체를 strength 와 함께 싣는다.
5. seasons / daypart 를 perfumes.csv 에서 가져와 싣는다. 좌표 계산에는 쓰지 않는다.
   people = null 인 향수의 0 값을 실제 0표로 오해하지 않도록 처리하고, 처리 방법을 보고한다.
6. neighbors 를 {id, sim} 형태로 바꾼다. sim 은 고차원 base similarity 값이다.
7. match / korea 블록을 채운다. dataset_status = "PROVISIONAL".
8. layout.metrics 에 results/korea_layout_comparison.csv 의 실측값을 그대로 옮긴다. 새로 지어내지 않는다.

[합격 기준 - 전부 실행으로 확인]
- points 200개, 중복 fragrantica_id 0건
- x, y 에 NaN/null 0건, 전부 [0,1]
- 정규화 전후 x/y 종횡비 동일 (배율이 같은지 수치로 확인)
- 모든 neighbors[].id 가 파일 안에 존재
- 파일 크기 기록

[금지] 좌표 재계산, 유사도 변경, 선정 결과 변경, v1 파일 수정
```

### 6.4 Phase A2 — 밀도장 · 영역 · 등고선

> **완료 (2026-09-07).** 근거는 `DECISIONS.md` **D11**(모집단) · **D12**(지형 파라미터).
>
> **모집단 결정 — 확장 기각 (D11).** 예상과 반대 결과였다. 시드 5개 평균에서 확장안(1,140개)이
> trust@10 0.9173→0.8975, kNN overlap 0.4864→0.4076, 정답 간선 거리 백분위 0.1869→0.2376 으로
> 모두 열세였고, 결정적으로 **시드 간 밀도 격자 상관이 0.9374→0.7661** 로 떨어져 사전 합격선 0.9를
> 만족하지 못했다. 점을 늘리면 지형이 안정될 것으로 봤으나 반대였다.
>
> **지형 (D12).** Gaussian KDE, scott ×0.5, sea_level 하위 60 백분위(uint8 97), 격자 128×136.
> 방법 의존성 없음(히스토그램+블러와 상관 0.9841). 육지 3개 전부 향수 5개 이상, 육지 위 향수 184/200.
>
> **영역 (D12).** k=4, lift 라벨. **라벨에 `woody` 가 하나도 없다** — 규칙이 의도대로 작동했다.
> `leather(5.70×)`, `musky(2.89×)`, `aromatic(2.42×)`, `fruity(2.09×)` 가 각 영역의 첫 라벨이다.
>
> **검증.** 신뢰 간선 40개의 2D 거리 중앙값 0.1749 vs 전체 쌍 0.4671. 영역 횡단 15/40(37.5%).
> 진단 이미지 `results/korea_terrain_check.png`.
>
> **초안에서 바꾼 것** — `regions` 를 배열이 아니라 `{cluster_method, silhouette, label_rule, grid, items[]}`
> 객체로 만들고 **region 격자(uint8, 255=바다)** 를 함께 실었다. 폴리곤만 주면 월경지 렌더링이
> 프론트 몫이 되는데, 격자를 주면 정확하고 즉시 쓸 수 있다. 폴리곤도 같이 넣었다.
>
> **남은 이상 사례 2건** — ① 향수 16개가 바다에 있다(인기 5위 `Le Labo / Another 13` 포함).
> ② 가장 먼 정답 쌍 `Eclat d'Arpege` ↔ `Light Blue` d=0.761. 둘 다 D12 Trade-off 에 기록했다.

```text
[Phase A2] 밀도 지형과 영역 오버레이 산출

[먼저 결정할 것 - 측정으로]
방침 문서 2장 P2 의 A안(200-only)과 B안(확장 모집단 + display 200)을 비교한다.
- 비교 지표는 모두 "표시 200개 부분집합" 기준으로 계산한다:
  trust@10, kNN overlap@10,
  200개 내부 정답 간선(reminds_me_of, 찬성>=3 & 찬성>반대)의 2D 거리 백분위,
  시드 5개 재실행 시 밀도 격자의 상관계수.
- 참고 측정값: 현재 200개 안의 신뢰 간선은 40개, 보유 노드 44/200 이다.
  정답 밀도가 낮다는 점을 결과 해석에 반영한다.
- 결과를 results/korea_population_comparison.csv 에 남기고, 어느 안을 왜 골랐는지
  DECISIONS.md 형식(문제 -> 검토한 방법 -> 결정 -> 근거 -> 결과 -> Trade-off)으로 기록한다.

[밀도장]
1. 채택 좌표 위에 2D Gaussian KDE 를 계산한다. 격자는 bounds 종횡비에 맞춘다 (예: 128 x 150).
2. bandwidth: scott 기본 + 0.5배 + 2배 스윕. 방법 비교군으로 "히스토그램 + 가우시안 블러"도 만든다.
3. 각 조합에서 (a) 격자 값 상관, (b) sea_level 임계에서의 육지 덩어리 개수를 기록한다.
   결과를 results/korea_terrain_comparison.csv 에 남긴다.
4. 값을 0~255 uint8 로 양자화해 JSON 에 싣는다.
   sea_level 은 고정값이 아니라 백분위 파라미터로 노출한다.

[영역]
5. 클러스터는 배치에 쓴 것과 같은 고차원 거리로 Agglomerative(average, precomputed) 를 쓴다.
   k 는 여러 값을 실행하고 선택 근거를 남긴다.
   silhouette 이 낮게 나오면 그대로 기록한다 - 낮은 것이 이 데이터의 사실이다.
6. 영역 라벨은 빈도가 아니라 두드러짐으로 만든다:
   클러스터 내 coverage >= 0.30 인 accord 중, (클러스터 내 보유율 / 코퍼스 전체 보유율) 상위 3개.
   분모는 EDA/analysis_outputs/10_accord_dictionary.csv 의 perfume_share 를 쓴다.
   향수당 accord 8개 전체로 계산한다 (상위 5개 근사 금지).
7. 경계는 "격자마다 어느 클러스터의 밀도가 가장 높은가"로 만들고 폴리곤화한다.
   월경지(다른 영역 안의 작은 구역)는 MultiPolygon 으로 보존한다. 지우지 않는다.
8. label_anchor 는 영역 내 KDE 최댓값 격자점으로 한다.
9. 한국어 이름은 붙이지 않는다. name_ko 는 null 로 두고 accord 근거만 싣는다.

[검증]
- MAP/viewer/map_preview.html (또는 동등한 확인 수단)으로 실제 지형을 눈으로 확인한다.
- "잘 나온다"로 보고하지 않는다. 발견한 이상(한 점에 뭉침, 정반대 향 인접, 빈 영역)을 목록으로 남긴다.
- 200개 내부 신뢰 간선 40개 중 2D 거리가 먼 상위 10쌍을 뽑아 원인을 기록한다.

[금지]
- 클러스터 라벨로 좌표를 끌어당기는 반지도 UMAP (실험 B에서 측정으로 기각됨)
- 4대 향 계열 라벨 기반 재배치 (안 C에서 기각됨)
- 밀도장에 인기도 섞기
```

### 6.5 Phase A3 — 프론트 전달

```text
[Phase A3] 프론트엔드 전달 문서 작성

MAP/docs/FRONTEND_HANDOFF.md 를 만든다.
대상 독자는 이 데이터를 처음 보는 프론트 개발자와 디자이너다.

반드시 포함할 것:
1. 파일 위치와 스키마 표 (필드명, 타입, 의미, 예시값)
2. 좌표 사용법 - 범위는 문서가 아니라 JSON 의 bounds 를 읽을 것.
   재생성마다 어느 축이 1.0을 채우는지 바뀔 수 있음.
3. 경고: 지도상 거리는 유사도가 아니다 (distance_is_metric: false).
   "비슷한 향수"는 반드시 neighbors 배열을 쓸 것. 실측 trust@10 / knn_overlap@10 을 함께 제시.
4. terrain 사용법 - 격자 해석 방법, sea_level 은 FE 가 조정하는 파라미터라는 점, 2D/3D 사용 예.
5. regions 사용법 - 경계는 벽이 아니라 지명이다.
   정답 쌍의 21~41%가 영역을 넘는 것이 정상이며, 사용자 취향이 두 영역에 걸치는 것은 오류가 아니다.
6. name_ko 가 비어 있는 이유와, 기획이 이름을 붙일 때 쓸 근거 자료 경로
   (EDA/data/scent_knowledge/source/perfume_14families_korean_descriptors.md,
    EDA/data/scent_knowledge/korean_scent_lexicon_v0_1.csv,
    EDA/data/scent_knowledge/scent_term_dictionary_v0.3.csv)
7. dataset_status = PROVISIONAL 의 의미 - 향수 목록은 교체될 수 있고 스키마는 바뀌지 않는다.
   안정 키는 fragrantica_id / map_identity_id.
8. 아직 정해지지 않은 것과 프론트가 결정할 것
   (라벨 LOD, sea_level, 월경지 표현, 200개만 표시할지 줌 단계로 더 보일지)

수치는 전부 실제 산출물에서 읽어 쓴다. 문서에 있는 옛 수치를 그대로 옮기지 않는다.
```

### 6.6 Phase B1 — Brand Mapping 적용 (정확성 트랙의 시작)

> **B1a·B1b 완료 (2026-09-07).** 아래 원본 프롬프트는 하나로 묶여 있었으나, 실행하면서
> 측정이 섞이는 것을 막기 위해 셋으로 나눴다.
>
> | 단계 | 상태 | 산출물 |
> |---|---|---|
> | **B1a** 매핑 파일 구축 + 카탈로그 대조 | 완료 | `build_brand_mapping.py` → `data/korea_popularity/brand_mapping_reviewed.csv` (32행, 사용 가능 29) |
> | **B1b** 매핑만 적용해 DEV 재측정 | 완료 | `evaluate_brand_mapping_dev.py` → `evaluation/fragrantica_brand_mapping_dev_{results,metrics,comparison}.csv` + `_report.md` |
> | **B1c** D018 비비앙 alias 오염 점검 | 미착수 | Gold를 보지 않고 raw 상품 근거로만 판정 |
>
> 핵심 결과 (Gold MATCH 61건, ALL_GOLD_MATCH / OVERALL). **BRAND_BLOCKED 7 → 1.**
>
> | 방법 | R@1 | R@5 | R@10 | MRR |
> |---|---|---|---|---|
> | baseline_lexical | .3115 → .3770 | .5902 → .6721 | .6721 → .7541 | .4451 → .5161 |
> | uroman | .3443 → .4098 | .6066 → .6885 | .6885 → .7705 | .4665 → .5376 |
> | enko_transliteration | .4590 → .5246 | .6721 → .7377 | .7377 → .8197 | .5590 → .6264 |
> | llm_ko_to_latin | .5410 → **.6066** | .7869 → **.8689** | .7869 → .8689 | .6569 → **.7265** |
> | llm_latin_to_ko | .5410 → **.6066** | .7869 → **.8689** | .8033 → **.8852** | .6543 → .7240 |
>
> 실행 전에 못박은 R@5 상한 0.8852를 넘지 않았고(실측 0.8689), 순위 회귀 0건,
> 질의 문자열 변경 0건이다. 상세와 한계는 `_report.md` 참조.
>
> **B1b에서 확정된 실행 규칙 세 가지**
> - 매핑은 **평가 경로의 후보 풀 선택 지점에서만** 적용한다. 본 파이프라인에 넣으면
>   `canonical_brand`가 `commercial_identity_id` 해시 입력이라 ID가 바뀌고 Gold 조인이 깨진다.
>   → **Phase B3에서 ID 재매핑 표가 필요하다.**
> - `llm_latin_to_ko`는 새 후보 56 core의 LLM 음역을 사람이 기존 방식으로 만들어 넣은 뒤
>   포함했다(`llm_latin_to_ko_outputs_brand_mapping.csv`, OK 51 / UNCERTAIN 5).
>   고정본 2,450행은 수정하지 않는다. 요청 목록·지시문은 `llm_latin_to_ko_pending_brand_mapping.md`.
> - **변경 전(before) 실행은 고정본만 사용**해야 method3 기록값과 같은 조건이 된다.
>   이 게이트에서 5개 방법 전부 4자리까지 일치했다.

```text
[Phase B1] 사람이 검토한 Brand Mapping 만 적용해 Method 3 DEV 재평가

[먼저 확인]
1. MAP/data/korea_popularity/evaluation/fragrantica_unresolved_brand_review.xlsx 의
   '내 검토 결과' 열이 MATCH 32 / NOT_IN_FRAGRANTICA 42 인지 실제로 세어 확인한다.
2. 토스 -> Tous, 킨포크노츠 -> KINFOLK NOTES 등 최종 수정이 반영돼 있는지 확인한다.
3. 기존 Method 3 산출물과 LLM output 파일이 변경되지 않았는지 확인한다.
4. gold_set_test.csv 를 읽지 않는 실행 경로인지 확인한다.

[작업]
1. MATCH 32건만 추출해 재사용 가능한 데이터 파일로 만든다.
   코드에 하드코딩하지 않는다. NOT_IN_FRAGRANTICA 42건은 자동 매핑하지 않는다.
2. 이 Brand Mapping 만 브랜드 해석 과정에 적용한다.
3. 다음은 한 줄도 바꾸지 않는다:
   Gold Set, DEV split, LLM KO->Latin / Latin->KO 출력, 이름 normalization,
   문자열 유사도 방식, 후보 ranking 방식, 농도/제품형태 필터.
4. 적용 전에 기존 Method 3 를 먼저 재현해 수치가 동일한지 확인한다.
   다르면 거기서 멈추고 원인을 보고한다.
   기준값: LLM KO->Latin R@1 0.5410 / R@3 0.7869 / R@5 0.7869 / R@10 0.7869 / MRR 0.6569
5. 같은 DEV Gold 로 적용 후 재평가한다.
6. 기존 BRAND_BLOCKED 7건이 어떻게 바뀌는지 개별 추적한다.
7. 적용 전/후 R@1/3/5/10, MRR, candidate 상태 분포를 한 표로 남긴다.

[별도 리스크 - 자동으로 고치지 말 것]
D018 '비비앙' 은 기존 alias 가 Vivienne Westwood 로 잘못 연결돼 있고 Gold 는 BiBiANG / Echloe 다.
Gold 를 보고 전역 규칙을 바꾸면 DEV overfitting 이다.
이번 실험에서 자동으로 고치지 말고, 실제 raw 상품/브랜드 근거로 독립 검증이 필요한 항목으로 별도 보고한다.

[이 실험이 답해야 할 질문]
다른 것을 전부 고정한 채 사람이 검토한 Brand Mapping 만 적용하면
candidate coverage 와 Method 3 retrieval 성능이 얼마나 좋아지는가.

[금지] 새 fuzzy brand matching, LLM brand 추론, 예외적인 향수명 규칙을 동시에 넣는 것. TEST 사용.
```

### 6.7 Phase B2~B4 (요약 프롬프트)

```text
[Phase B2] Verification - Top-K 후보 중 정확히 하나를 확정
- Retrieval 의 R@5 0.79 는 "정답이 5개 안에 있다"이지 "1개를 맞혔다"가 아니다.
  이 차이를 보고에서 혼동하지 않는다.
- fuzzy score 하나로 auto-MATCH 하지 않는다.
  브랜드 / 향수명 / flanker / 농도 / 제품 형태 / 출시 버전을 각각 독립 근거로 기록하고,
  근거가 부족하면 UNRESOLVED 로 남긴다.
- 과거 오매칭 사례(Clean Cool Cotton->Warm Cotton, Eros Energy->Eros Najim,
  Miss Dior EDP->1947, Le Sel d'Issey EDP/EDT 병합)를 회귀 테스트 케이스로 쓴다.
- DEV 에서만 튜닝한다. TEST 는 최종 1회만, 보고 나서 튜닝하지 않는다.

[Phase B3] 최종 대표 200 재선정
- 향 계열별 50개 quota 없음. Fragrantica 글로벌 인기도를 한국 인기 점수에 쓰지 않는다.
- Hwahae map-ready 우선 포함 -> 나머지는 구매 채널 popularity RRF.
  overlap 은 한 자리만. reserve 20 유지.
- 같은 Fragrantica ID 를 두 개의 지도 점으로 만들지 않는다.
- v1 대비 교체된 향수와 교체 사유를 표로 남긴다.

[Phase B4] 최종 데이터 생성
- Phase A1/A2 파이프라인을 그대로 재실행한다. 스키마를 바꾸지 않는다.
  바꿔야 한다면 Phase A 설계가 틀린 것이므로 먼저 보고한다.
- dataset_status 를 VERIFIED 로 바꾼다.
- Phase A 시점 대비 좌표·영역·지형이 얼마나 달라졌는지 측정해 기록한다.
- PLAN.md Step 6 의 Final Holdout 300 확인은 모든 튜닝이 끝난 뒤 1회만 실행한다.
```

---

## 7. 아직 정해지지 않은 것 (사람이 결정할 것)

### 결정된 것 (2026-09-07)

| # | 질문 | **결정** |
|---|---|---|
| 1 | Phase 0 폴더 재구성 범위 | **전체 재구성.** `src/{common,korea,matching,map}` + `docs/` + `viewer/` + `archive/`. 스크립트 수정은 경로 2줄로 제한하고 재실행 바이트 비교로 검증 |
| 2 | 트랙 실행 순서 | **정확성 트랙 먼저** (Phase 0 → B1 → B2 → B3 → A1 → A2 → A3). Phase B4는 불필요 |

### 남은 것

| # | 질문 | 데이터 쪽 의견 |
|---|---|---|
| 3 | 레이아웃 모집단 200 vs 확장 | Phase A2 측정으로 결정. 현재 200개 안의 신뢰 간선이 40개뿐이라 확장 쪽이 유리할 가능성이 높다 [측정] |
| 4 | 3D 높이맵인가 2D 등고선인가 | 데이터는 동일한 격자 하나로 둘 다 지원한다. FE 렌더링 역량에 따라 결정 |
| 5 | 표시 200개 vs 줌 단계로 더 노출 | 확장 모집단을 택하면 `display` 플래그로 둘 다 지원됨 |
| 6 | 영역 한국어 이름 | 기획 결정. 데이터는 accord 근거(lift, coverage)와 한국어 어휘 자산 경로만 제공 |

---

## 8. 이 문서가 근거로 삼은 실행

- 국내 200개 내부 정답 간선 수 (§1.4): `cache/reminds_edges.csv`를 `output/korea_scent_map_v1.json`의 `fragrantica_id` 200개로 제한 후 `up_votes>=3 & up_votes>down_votes` 집계 → 117 / 40 / 44
- 좌표 범위 (§1.1): `output/korea_scent_map_v1.json`의 x·y 최소·최대 직접 집계
- 브랜드 리뷰 집계 (§1.5): `fragrantica_unresolved_brand_review.xlsx`의 `내 검토 결과` value_counts
- Method 3 지표 (§1.5): `fragrantica_method3_dev_metrics.csv`의 `scope=ALL_GOLD_MATCH & level=OVERALL` 행
- 배치·군집 지표 (§1.2, §1.3): `results/korea_layout_comparison.csv`, `results/korea_cluster_comparison.csv`

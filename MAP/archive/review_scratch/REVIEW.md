# 향 지도 외부 검증 보고서

검증일: 2026-09-05. 경로는 저장소 루트(`C:/Users/SSAFY/Desktop/hyanghae`) 기준이다. `scratch`는 `MAP/review_scratch`, `첨부 HTML`은 `C:/Users/SSAFY/Downloads/향지도_영역표현_프론트논의.html`이다. 아래 수치는 별도 표시가 없으면 이번 실행 결과이며, 문서에만 있는 수치는 출처를 따로 명시했다. 첨부 문서의 구현 제안은 검토 대상으로만 읽었다.

## 1. 요약

- 버그 **1건**: 응집도 무작위 기준값의 자기 자신 제외 누락. 해석 오류 **5건**: 정확도 명칭, MDS 목적함수 설명, 선정 규칙 문서 드리프트, 노드/간선 혼동, 첨부 문서의 횡단 비율 적용 범위(§2 B1·I1~I5).
- 개선 여지 **4건**: 평가 독립성 구분, 8개 accord 라벨 확정, 경계 방식 선택, 추가 향수 투영의 별도 품질 관리(§2 G1~G4). 실제 사용자 경험 개선은 미측정이다.
- 시드 42 baseline CSV·JSON은 **바이트 일치**. nn10의 이웃 겹침 우위는 5개 시드 모두 유지됐고, 낮은 감독 가중치도 실험 B 합격선을 넘었다(§2 V1·V2·V5).
- 두 선정 대안에서 동일한 accord·브랜드 다양성을 유지하는 개선은 없었다. complete는 열세, single은 989개짜리 거대 클러스터가 생겨 추천하지 않는다(§2 V4).
- 원본 파이프라인·결과·결정 문서는 변경하지 않았다. Final Holdout 파일을 열거나 평가하지 않았다. 재현 자료와 이 보고서를 위해 scratch는 **남긴다**(§4·§5).

## 2. 발견 사항

### B1. [버그 / 낮음] region_cohesion의 무작위 기대값은 분포를 반영하지만 자기 자신을 포함한다 — A3

**방법·어디:** `MAP/build_map.py:240`의 원함수를 그대로 사용하고, `:249`의 자기 자신 제외와 `:253`의 기대값을 비교했다. 실행 근거: `MAP/review_scratch/measurements.json:2600`.

- 관측값은 자신을 제외한 이웃 10개의 동일 라벨 비율이다.
- 코드의 기대값은 `Σ(n_c/N)²`. 큰 라벨의 높은 우연 일치 확률을 반영하므로 **라벨 균등 분포를 가정한 오류는 없다**.
- 정확한 비복원 무작위 기대값은 `Σ n_c(n_c−1) / [N(N−1)]`이다.
- 원본 12라벨: 코드 **0.174998**, 정확값 **0.174172**. D9 병합 10라벨: 코드 **0.175280**, 정확값 **0.174454**.

**결론·권고:** 기대값 계산의 작은 통계 오류다. 좌표·관측 응집도·클러스터 선택을 뒤집는 근거는 아니다. 후속 수정에서는 기대값만 자기 제외 기준으로 맞추고, 과거 표의 정의를 함께 기록한다. 이번 검증에서는 지표 구현을 바꾸지 않았다.

### I1. [해석 오류 / 높음] trust@10 = 0.939는 이웃 정확도 93.9%가 아니다 — A1

**방법·어디:** `MAP/build_map.py:19,166`에서 sklearn `trustworthiness(..., metric="precomputed")` 호출을 확인했다. 실제 수식·구현은 `MAP/venv/Lib/site-packages/sklearn/manifold/_t_sne.py:456,550`. 잘못 읽히는 설명은 `MAP/scent_family_decision.html:514,520`, 첨부 HTML `:79`, `MAP/PLAN.md:307`이다.

`T(k) = 1 − 2·Σ_i Σ_{j∈2D-kNN(i)} max(r_high(i,j)−k, 0) / [N·k·(2N−3k−1)]`.

2D 이웃이 원공간의 10위 밖에 있으면 **원공간 순위 초과량**만큼 벌점을 주고 전체 가능한 벌점으로 정규화한다. 11위와 900위 침입은 다르게 벌점 처리한다. 반면 `knn_overlap@10`은 정확히 같은 이웃 집합에 속하는지 세는 비율이다(`MAP/build_map.py:141`). 따라서 두 값의 큰 차이는 계산 충돌이 아니다.

재현된 채택 좌표는 trust **0.938708**, overlap **0.388800**, 평균 보존 이웃 **3.888/10**이다(`MAP/review_scratch/baseline/results/layout_comparison.csv:5`, `measurements.json:2600`).

**결론·권고:** “원공간 상위 10개 이웃을 얼마나 그대로 보여주는가”는 overlap이 직접 뒷받침한다. trust는 아주 먼 원공간 점의 이웃 침입이 얼마나 억제됐는지 보완한다. 어느 쪽도 “옆에 있는 향수는 실제로 비슷하다”라는 모든 점에 대한 감각적 보증을 제공하지 않는다. 문구를 **“원공간 이웃 10개 중 평균 3.89개 보존, 순위 기반 trustworthiness 0.939”**로 구분하고, 고차원 `neighbors`를 이용하는 기존 설계는 유지한다(`MAP/build_map.py:324`).

### I2. [해석 오류] 제곱거리 합을 MDS stress 질량·최적화 노력으로 등치했다

**방법·어디:** `MAP/DECISIONS.md:57,59,88`, `MAP/PLAN.md:217,219,228`의 주장을 설치된 MDS 목적함수와 대조했다. `MAP/venv/Lib/site-packages/sklearn/manifold/_mds.py:179`는 `Σ(d_2D−disparity)² / 2`를 계산한다.

**근거:** 입력 거리의 제곱합 `ΣD²`는 **잔차 제곱합 `Σ(d_2D−D)²`도, 최적화 연산량도 아니다**. 따라서 문서의 “1.24% → 최적화 노력 98.8%”는 수식에서 나오지 않는다. 종합 성능이 낮다는 결과만으로 “note가 버려지고 accord가 지배했다”는 성분별 원인까지 입증되지 않는다. 성분별 손실 기여는 이번에 미측정이다.

**결론·권고:** 거리 집중 진단과 인과적 설명을 구분한다. MDS overlap **0.0835** 대 UMAP **0.3888**, reminds **0.245248** 대 **0.176585**는 재현됐다(`scratch/baseline/results/layout_comparison.csv:4,5`). **UMAP 채택은 유지할 근거가 있다. MDS 재도입을 제안하지 않는다.**

### I3. [해석 오류] D3의 수치 표는 맞지만 실행 규칙 설명과 PLAN은 남아 있다 — D9

**방법·어디:** `MAP/DECISIONS.md:120,134,145`, `MAP/PLAN.md:279,297,331,340`, `MAP/scent_map.py:160,205,220,233` 대조. 선정 CSV 바이트 재현 및 JSON에서 표시 대상 accord 수를 집계했다(`scratch/summary_numbers.json`).

- D3의 현재 A/B 표는 **42→58 accord, 182→223 브랜드, 915→872 간선, 손실 4.699454%**로 맞다.
- 그러나 결정문은 하한 5 / 상한 60이라고 한다. 현재 호출은 `_allocate(..., floor=1, cap=None)` 기본값으로 **그룹→accord 2단계**를 수행한다. 실제 그룹×accord 셀 크기는 **1~25개**다.
- 표시 200개는 같은 2단계가 아니라 **그룹 정원→그룹 내 인기순**이다. 실제 표시 대상의 dominant accord는 **28종**, 전체는 **58종**이다. “화면 200개도 같은 규칙”은 정확하지 않다.
- D3의 `people>=200` 비교문은 “883으로 더 줄고”라고 하지만 현 기준은 872다. 이 문장은 과거 기준과 현재 기준을 섞었다. 200 하한 대안은 이번에 재실행하지 않았으므로 현 규칙에서의 값은 **미측정**이다.
- PLAN `:340`의 Development700 재현 목표 0.2688은 D1의 채택 조합 Development700 기록 0.2709와 다르다. EDA05에서 0.2688은 Tuning 단계 기록이다(`EDA/05_retrieval_ablation.ipynb`, cell29; `MAP/DECISIONS.md:32`). 이 차이를 새 구현 오류 판정선으로 사용하면 안 된다.

**결론·권고:** 현재 산출물을 잘못됐다고 단정할 근거는 없다. 결정 설명·표시 규칙·과거 실험의 모집단을 실제 코드와 맞추는 문서 정정이 필요하다. 설정을 문서에 맞추려고 파이프라인을 바꾸지는 않는다.

### I4. [해석 오류] HTML이 정답 간선 보유 노드 수를 정답 쌍 수로 썼다

**방법·어디:** `MAP/scent_family_decision.html:500,501`은 top200→top1000의 “닮았다 투표 쌍”을 70→483으로 쓴다. 원 출처 `MAP/DECISIONS.md:124` 표와 `MAP/PLAN.md:100` 주변 규모별 표를 대조했다.

**근거:** 그 값은 **신뢰 간선 보유 노드 수**다. 같은 옛 후보 풀에서 신뢰 간선 수는 **94→943**이라고 원문 표에 기록돼 있다. 이 규모별 표 자체는 이번에 재계산하지 않았다. 현재 같은-pool top1000의 신뢰 간선은 **915**, 간선 보유 노드는 **508**로 재현됐다(`scratch/baseline/results/selection_comparison.csv:2`).

**결론·권고:** 노드와 관계를 다른 단위로 명시한다. 또한 이 HTML의 36% 같은 브랜드·16% 장거리 본문 드리프트는 이미 D10에서 지적됐으므로 새로운 발견으로 세지 않는다(`MAP/DECISIONS.md:382`).

### I5. [해석 오류] 첨부 HTML의 “어떤 기준에도 21~41% 횡단”은 조건·라벨이 생략됐다

**방법·어디:** 첨부 HTML `:51,56,81,120`과 `MAP/DECISIONS.md:335,337`, `MAP/results/edge_robustness.csv:8,9`를 대조하고 첨부의 2D 중심 병합을 재현했다(`scratch/frontend_check.py:17`, `frontend_check.json:2`).

**근거:** D10의 엄격한 D 기준은 **34/207 = 16.4%**, 같은 브랜드 제외 D′가 **16/76 = 21.1%**다. 21~41%는 **브랜드를 제외한 조건들의 범위**이며 모든 조건의 하한이 아니다. 또한 D10은 병합 **10라벨**, 첨부 그림은 **9영역**이다. 첨부 방식으로 원본 12개 중 크기 10 미만의 9점을 기존 큰 클러스터의 2D 중심에 배정하자 영역 크기가 문서와 모두 일치했고, 현재 A 간선 횡단은 **302/872**로 D10의 **306/872**와 달랐다(§4의 첨부 간선 점검 명령).

**결론·권고:** “브랜드 제외, D9의 10라벨 기준 21~41%”로 조건을 보존한다. 9영역 그림의 횡단 수치로 직접 인용하려면 그 라벨로 재계산한다. D10의 투표 수·브랜드 통제 결과 자체를 기각하는 내용은 아니다.

### G1. [개선 여지] 정답을 직접 써서 대상을 고르지는 않지만 지도 평가는 Development와 완전히 독립적이지 않다 — C7·C8

**방법·어디:** `MAP/scent_map.py:191,205,219`의 입력과 `MAP/build_map.py:64,67` 호출 순서를 확인했다. 선정은 특징 보유·설명문 그룹·vote_count를 사용하고 **reminds 투표는 선정 완료 후** 평가에 읽는다. 직접적인 정답 기반 대상 선정은 확인되지 않았다. `vote_count`와 `people`도 `reminds_me_of.up_votes`와는 다른 필드다(`MAP/SCHEMA.md:78` 주변 필드 표).

Development 중복은 `MAP/verify_similarity.py:35`와 동일한 양방향 합산 정답 기준·eligible 정렬·시드 42 추출·permutation으로 **Development700 부분만** 재구성했다. Holdout 파일·Holdout 슬라이스는 읽거나 평가하지 않았다. 기준의 출처는 `EDA/04_baseline_retrieval.ipynb` cell11·18, `EDA/05_retrieval_ablation.ipynb` cell6·8·29이다. MAP 간선 기준은 방향별 up≥3 & up>down여서 EDA 정답 기준과 같지 않다(`MAP/build_map.py:48`).

실행 결과(`scratch/measurements.json:427`):

| 대조 집합 | 지도에 포함된 query | MAP 간선 중 src가 해당 query | 같은 방향의 EDA relevance와 중복 | 방향을 무시한 관계가 중복된 MAP 간선 | 중복 고유 무방향 쌍 |
|---|---:|---:|---:|---:|---:|
| Development700 | 78 | 120 | 30 | 56 | 30 |
| Tuning500 | 56 | 87 | 17 | 35 | 19 |
| Internal Validation200 | 22 | 33 | 13 | 23 | 12 |

MAP의 872건은 **485개 고유 무방향 쌍**이다. Development와 같은 방향 relevance 중복은 **30/872=3.44%**, 방향 없는 관계 기준으로 가중된 MAP 중복은 **56/872=6.42%**, 고유 쌍 기준은 **30/485=6.19%**다. Tuning·Validation의 무방향 중복은 서로도 겹치므로 합산하지 않는다. 출발 query가 겹친 120건을 모두 동일 정답으로 세는 것은 과대계산이다.

**결론·권고:** feature/가중치 선택에 사용한 관계가 일부 재평가된다. 다만 **중복률은 성능 낙관 편향의 크기가 아니다. 영향 크기는 미측정**이다. MAP 평가는 투영의 진단이라고 명시하고, 다음 검증은 Development query와 양쪽 endpoint가 겹치지 않는 관계/겹치는 관계를 나눠 동일 좌표·동일 후보 집합에서 기존 `edge_distance_percentile`로 비교한다. 신뢰구간을 붙일 경우 872개를 독립 표본으로 간주하지 않고 src 또는 고유 쌍 단위로 재표집한다. Final Holdout을 이 검토의 튜닝에 사용하지 않는다.

### G2. [개선 여지] 첨부 9영역의 lift 라벨은 5→8 accord에서 6곳, 임계값에서 7곳 바뀐다 — E12

**방법·어디:** 첨부 HTML `:60,63,74,120,122`의 **9영역**을 재현했다. 전체 기준은 **지도 1,000개 평균**, 미기록 accord는 0, lift는 클러스터 평균 raw strength / 지도 평균 raw strength, coverage는 양의 strength를 기록한 향수 비율이다. 출력 라벨은 lift 내림차순 상위 3개. 기존 라벨은 단순 출현 횟수가 아니라 **strength 합 순위**다(`MAP/build_map.py:330`); 첨부의 “빈도”도 이 차이를 밝혀야 한다.

상위5 근사의 9영역 라벨과 표의 배수는 표시 정밀도에서 재현됐다(예: iris **6.91×**, anis **55.74×**). 전체8 재계산은 다음과 같다(`scratch/frontend_check.json:60`).

| 원 cluster / 9영역 크기 | 상위5, coverage≥30% | 전체8, coverage≥30% |
|---|---|---|
| c0 / 148 | warm spicy · amber · woody | **leather · warm spicy · amber** |
| c1 / 285 | aromatic · fresh spicy · citrus | **aromatic · fresh spicy · green** |
| c3 / 201 | sweet · vanilla · fruity | **vanilla · sweet · fruity** |
| c4 / 128 | iris · musky · powdery | **iris · violet · musky** |
| c5 / 29 | ozonic · aquatic · fresh | 동일 |
| c6 / 15 | anis · soft spicy · sweet | 동일 |
| c7 / 48 | rose · floral · fresh | 동일 |
| c8 / 122 | white floral · floral · citrus | **white floral · floral · green** |
| c10 / 24 | lactonic · coconut · sweet | **lactonic · coconut · tropical** |

순서를 포함하면 **6/9**, 단어 집합만 보면 **5/9** 변경이다. c0 leather는 **lift 3.4757, coverage 32.43%**, c4 violet은 **5.0704, 36.72%**이므로 40% 컷에서는 빠진다. 전체8의 20/30/40% 비교:

| cluster | 20% | 30% | 40% |
|---|---|---|---|
| c0 | cinnamon · smoky · leather | leather · warm spicy · amber | warm spicy · amber · woody |
| c1 | lavender · aromatic · fresh spicy | aromatic · fresh spicy · green | aromatic · fresh spicy · citrus |
| c4 | iris · violet · musky | iris · violet · musky | iris · musky · powdery |
| c6 | anis · soft spicy · tobacco | anis · soft spicy · sweet | anis · soft spicy · sweet |
| c7 | rose · floral · patchouli | rose · floral · fresh | rose · floral · musky |
| c8 | tuberose · yellow floral · white floral | white floral · floral · green | white floral · floral · green |
| c10 | savory · lactonic · coconut | lactonic · coconut · tropical | lactonic · coconut · sweet |

c3·c5만 세 임계값에서 그대로다. 원본 12클러스터로도 별도로 계산했으며 5→8에서 순서 포함 **8/12**, 단어 집합 **7/12**, 임계값 변경 **8/12**였다(`scratch/measurements.json:456`, `summary_numbers.json`).

**결론·권고:** 첨부가 근사라고 밝힌 것은 맞지만 “순위가 조금 다를 수 있다”보다 변화 범위가 크다. 명명 전 전체8 기준과 cutoff를 고정하고 lift·coverage를 함께 남긴다. **lift가 사람에게 더 정확한 이름이라는 효과는 미측정**이다. 좌표와 라벨 소속을 유지하는 이름 변경으로 trust·overlap·reminds·cohesion 개선을 주장할 수 없다.

### G3. [개선 여지] 볼록 껍질의 혼입이 크다. 밀도 우세·alpha shape는 서로 다른 비용이 있다 — E13

**방법·어디:** 좌표는 저장된 JSON 그대로 사용했다. 원본 12라벨과 첨부 방식 9영역 각각에서 같은 계산을 실행했다(`scratch/experiments.py:166`, `frontend_check.py:45`). 첨부 HTML `:121`에는 밀도 우세라고만 되어 있고 bandwidth·커널·격자 생성 코드는 없어 **첨부 경계 자체의 정확한 재현은 불가능**했다. 아래는 명세를 고정한 리뷰 실험이다.

기존 지표는 좌표의 이웃·정답 관계를 재고 경계 다각형을 입력받지 않는다. 경계만 바꾸면 기존 지표가 동일하므로, 요청한 경계 평가를 위해 **타 라벨 점-영역 소속 수 / 전체 점-영역 소속 수**를 혼입률로 추가했다. 여러 경계에 들어가는 점은 경계마다 센다. 제외로 유리해지는 것을 막기 위해 **자기 영역 내 포함률**과 **어느 영역에든 포함된 점 수**를 함께 기록했다. 실제 경계 내부 판정이며 단순 외접 사각형 판정이 아니다.

- 공통 척도 `h` = 각 점의 10번째 이웃 거리의 중앙값 = **0.03895709**(정규화 JSON 좌표).
- Convex hull: 각 라벨 점의 볼록 껍질. 3점 미만은 면적 경계를 만들지 않는다.
- Alpha shape: 라벨별 Delaunay 삼각형 중 외접원 반지름 ≤ `h`, `2h`, `4h`인 삼각형의 합집합. 여기서 alpha 관례는 `1/반지름`이며 반지름으로 직접 명시했다.
- 밀도 우세: 등방 Gaussian kernel의 **라벨별 합**이 최대인 라벨을 할당한다. 라벨 크기 사전확률이 반영되며 라벨별 단위질량 정규화가 아니다. bandwidth는 `0.5h`, `h`, `2h`. 바다 임계값은 적용하지 않았다.

**첨부 9영역 결과**(`scratch/frontend_check.json:1056`):

| 방법 | 타 라벨 / 전체 소속 | 혼입률 | 자기 영역 내 포함률 | 어느 영역에든 포함된 점 |
|---|---:|---:|---:|---:|
| Convex hull | 2,492 / 3,492 | **71.36%** | 100.0% | 1,000 |
| Alpha, 반지름 h | 68 / 999 | **6.81%** | 93.1% | 966 |
| Alpha, 반지름 2h | 257 / 1,223 | 21.01% | 96.6% | 997 |
| Alpha, 반지름 4h | 1,068 / 2,056 | 51.95% | 98.8% | 999 |
| 밀도 우세, 0.5h | 94 / 1,000 | **9.40%** | 90.6% | 1,000 |
| 밀도 우세, h | 131 / 1,000 | 13.10% | 86.9% | 1,000 |
| 밀도 우세, 2h | 191 / 1,000 | 19.10% | 80.9% | 1,000 |

밀도에서 평가 점 자신의 kernel 기여를 제거한 leave-one-out 진단은 0.5h / h / 2h에서 **12.6% / 14.4% / 19.3%** 혼입이다. 이 값은 하나의 고정 경계의 혼입률이 아니라 self-influence 민감도이므로 위 표의 고정 경계 값과 구분한다. 원본 12라벨에서도 convex **71.84%**, alpha(h) **7.34%**, KDE(0.5h) **9.90%**였다(`scratch/measurements.json:1775`).

**결론·권고:** 이 데이터에서는 단일 볼록 껍질을 일반적인 영역선으로 쓰지 않는 근거가 있다. **전 점에 한 영역을 부여할 경우** 밀도 우세 0.5h가 비교한 bandwidth 중 혼입이 가장 적었다. **경계 밖 점과 여러 조각을 허용할 경우** alpha(h)는 혼입이 더 낮았지만 34점은 어떤 경계에도 포함되지 않았다. 서로 분모·겹침·포함 범위가 달라 혼입 하나만으로 승자를 정하지 않는다. 첨부의 바다 하위55%를 함께 쓰는 완성 경계와 실제 다각형 격자화 오차는 미측정이다.

### G4. [개선 여지 / 확장 검증] transform은 실행되지만 추가 향수의 정답 근접도는 더 낮다 — E14

**방법·어디:** 시드 42로 재현한 nn10/md0.1 UMAP에 **신규×학습 6,815×1,000 거리행렬**을 넣어 `transform`했다. 유사도는 기존 accord·note 행렬 생성 함수와 같은 계산이며 원본과 같은 IDF를 사용했다(`scratch/experiments.py:239`, `MAP/scent_map.py:250,269,282`). 설치된 transform의 precomputed 계약은 `MAP/venv/Lib/site-packages/umap/umap_.py:3016`이다. 학습된 점을 재배치하지 않았고 신규끼리의 거리를 학습 입력으로 넣지 않았다.

JSONL people≥500은 **7,823개**, accord·note 보유는 **7,815개**, 지도 밖 투영은 **6,815개**다. 이 중 설명문 group 결측 **513개**도 요청의 확장 풀에 포함했다. 좌표 비유한값은 **0개**였다(`scratch/measurements.json:2615`).

백분위 후보 분모가 달라지는 교란을 피하기 위해 아래는 모두 **같은 7,815개 좌표**에서 기존 `edge_distance_percentile`로 평가했다.

| 관계 방향 | 간선 수 | 정답을 가진 src 수 | reminds_pct |
|---|---:|---:|---:|
| 학습→학습 | 872 | 432 | **0.179709** |
| 신규→전체 | 16,791 | 5,085 | **0.214374** |
| 신규→학습 | 4,076 | 2,514 | 0.217805 |
| 신규→신규 | 12,715 | 4,726 | 0.213275 |

학습 1,000개만 후보로 둔 원래 점수는 **0.176585**다. 동일 후보군에서 신규와 학습의 차이는 **+0.034666**(낮을수록 좋음)이다(`scratch/summary_numbers.json`).

**결론·권고:** 투영 확장은 동작하며 신규 관계에도 무작위 수준보다 낮은 백분위가 나온다. 그러나 학습과 동일한 품질이라고 부르면 안 된다. 대상의 인기·브랜드·정답 관계 분포가 달라 이 차이를 **transform 자체의 인과적 손실**로 확정할 수 없다. 신규 **1,730개**는 이 평가 후보군에 신뢰 outgoing 간선이 없어 src 품질을 확인하지 못했다. 확대 시 학습/신규 지표를 나누어 유지하고, 동일 신규 표본에 대한 대조 실험 없이는 전면 재학습보다 유리하다고 주장하지 않는다.

### V1. 확인함, 문제 없음 — baseline 및 원자료 캐시 재현, B4

출력 경로 상수만 scratch로 바꾸어 원본 `build_map.main()` 전체를 실행했다(`scratch/reproduce.py:49`). 실행 시간 **44.324초**, `random_state=42`. CSV는 파싱 비교가 아니라 원본 bytes 비교다. 결과: `scratch/baseline_check.json:15`.

| 산출물 | 바이트 일치 | 원본과 재생성 공통 SHA-256 |
|---|---|---|
| layout_comparison.csv | 예 | `0b5be35bd5be01a64bf06d78e3798ab1099dd4146e9f2e1fed4f44a14c68216b` |
| scent_map_v1.json | 예 | `fe9259335b0c4ea06fffbe99706ada49854a339cfde2651a71bc8f21e860d7e6` |
| selection_comparison.csv | 예 | `6c009e94b9616cf412720b78961dad41239a159f46f040656372de1d33ff58b9` |

추가로 원본 JSONL **131,930행**을 스트리밍해 people 캐시 불일치 **0**, reminds 간선 **692,729건**의 순서·값 전체 일치를 확인했다(`scratch/measurements.json:2609`). 유사도 0.5/0.5와 note IDF의 출처는 EDA05 Tuning·Validation 기록과 일치한다. Note Canonicalization 노트북은 매핑 감사이며 ranking 성능을 측정한 노트북이 아니다(`EDA/21_fragrantica_note_canonicalization_audit.ipynb:20`). 이를 별도 유사도 개선 실적으로 인용하지 않는다.

### V2. 확인함, 문제 없음 — 이웃 겹침을 기준으로 한 nn10 선택은 5시드에서 유지, B5

**방법:** nn10과 nn15를 각각 시드 **0,1,2,3,42**, min_dist=0.1로 실행했다. 원함수 `evaluate_layout` 사용. 평균±**표본 표준편차(ddof=1)**이며 표준오차가 아니다(`scratch/measurements.json:21`).

| 설정 | trust@10 | knn_overlap@10 | reminds_pct |
|---|---:|---:|---:|
| nn10 | 0.936835 ± 0.001816 | **0.388520 ± 0.003939** | 0.168836 ± 0.007530 |
| nn15 | 0.932420 ± 0.003078 | 0.367420 ± 0.003360 | **0.163667 ± 0.005179** |
| 동일 시드 nn10−nn15 | +0.004416 ± 0.004406 | **+0.021100 ± 0.002747** | +0.005168 ± 0.010742 |

nn10 개별 결과:

| 시드 | trust@10 | overlap@10 | reminds_pct |
|---|---:|---:|---:|
| 0 | 0.938012 | 0.3921 | 0.162856 |
| 1 | 0.937244 | 0.3826 | 0.167513 |
| 2 | 0.936143 | 0.3871 | 0.176648 |
| 3 | 0.934068 | 0.3920 | 0.160578 |
| 42 | 0.938708 | 0.3888 | 0.176585 |

시드42 설정 차이는 trust **+0.004753**, overlap **+0.020200**, reminds **+0.019577**였다. 반복한 overlap 차이는 시드별 변동보다 크고 **5/5회 nn10 우위**다. 실제 자동 채택 기준도 overlap 최대다(`MAP/build_map.py:223`). trust는 시드3에서 nn15가 높고, reminds 평균 차이는 paired 변동보다 작아 일관된 우열이라고 할 수 없다. **nn10이 세 지표 모두 최적이라는 해석은 하지 않는다.**

### V3. 확인함, 문제 없음 — 원본 k=12 클러스터는 시드와 무관, B6

동일 D·행 순서에서 numpy 시드를 0/1/2/3/42로 바꾸고 average/precomputed clustering을 반복했다. **5/5회 JSON의 1,000개 라벨 배열과 완전 일치**했다(`scratch/measurements.json:182`, `MAP/build_map.py:266`). 입력 순서 변경이나 패키지 버전 변경까지의 불변성을 검증한 것은 아니다.

### V4. 확인함, 문제 없음 — 제한된 대안에서 D3/D4를 바꿀 근거 없음, D9·D10

**선정 방법:** 현재 usable_pool·1,000개를 고정. 정답 간선을 보지 않고 ① accord별 인기1개 확보 후 인기순 채우기 ② 브랜드당 최대20개 후 인기순, 두 규칙만 측정했다. 동률은 id 오름차순으로 고정했다(`scratch/experiments.py`, selection 블록; `scratch/measurements.json:361`).

| 선정 | accord | 브랜드 | 신뢰 간선 | 상위10 브랜드 점유율 |
|---|---:|---:|---:|---:|
| 인기순 | 42 | 182 | 915 | 29.6% |
| 채택 규칙 | **58** | **223** | 872 | 25.3% |
| accord당1 + 인기순 | **58** | 186 | **901** | 29.3% |
| 브랜드 상한20 | 42 | 202 | 808 | **20.0%** |

accord만 같게 유지하면 29간선을 더 남길 수 있지만 브랜드 다양성이 37개 줄어 **같은 다양성에서의 개선이 아니다**. 두 조건을 모두 만족하는 간선 손실 개선은 발견하지 못했다. D3의 채택 trade-off 자체는 재현된다.

**클러스터 방법:** 같은 고차원 D·k=12·고정 JSON 좌표에서 average와 complete/single을 비교했다. Ward는 이 혼합 precomputed D에 그대로 적용하지 않았다(`scratch/measurements.json:182`).

| linkage | 응집도 | 무작위 기준(기존 함수) | 횡단 / 872 | 최대 크기 | 응집도<0.35 라벨 |
|---|---:|---:|---:|---:|---:|
| average | **0.7622** | 0.174998 | **306** | 281 | 3 |
| complete | 0.5796 | 0.113346 | 390 | 224 | 1 |
| single | 0.9798 | 0.978132 | 11 | **989** | **11** |

complete는 요청한 두 핵심 지표 모두 열세다. single은 두 원점수는 높지만 무작위 기대값부터 0.978132이며 989+단일점11개로 사실상 한 영역이다. D4가 거대 영역을 배제한 제약(`MAP/DECISIONS.md:172`)을 위반하므로 추천하지 않는다. **응집도·횡단 두 값 동시 개선은 필요조건일 뿐 충분조건이 아니라는 반례**다.

### V5. 확인함, 문제 없음 — 낮은 w도 실험 B 기각을 뒤집지 못함, D11

**방법·어디:** 같은 시드42·D·채택 파라미터·D9 병합10라벨에서 w=0.05와 0.1을 각각 **1회만** 실행했다. 원 `experiment_metrics`를 사용했다(`scratch/measurements.json:319`).

| w | trust@10 | overlap@10 | reminds 전체 | reminds cross | sil2d | cohesion |
|---|---:|---:|---:|---:|---:|---:|
| y 없음, 재현 | 0.938708 | 0.3888 | 0.176585 | 0.363026¹ | 0.054227¹ | 0.7644¹ |
| 0.05 | 0.951547 | 0.3893 | 0.203504 | **0.525830** | 0.733025 | 0.9856 |
| 0.1 | 0.952259 | 0.3902 | 0.195622 | **0.504328** | 0.764778 | 0.9896 |
| 0.2, 기존 기록¹ | 0.950367 | 0.3921 | 0.202574 | **0.523291** | 0.781021 | 0.9879 |

¹ `MAP/results/supervised_umap_comparison.csv:2,3`의 기록. 이번 baseline은 주요 layout 지표·JSON을 바이트 재현했으며 이 표의 w=0.2를 재실행하지는 않았다.

두 낮은 w 모두 기존 합격선 **0.413026**(baseline cross+0.05)을 넘는다. 무작위에 대한 통계적 유의성 검정 없이 “0.5043은 무작위보다 유의하게 나쁘다”라고까지 말하지 않는다. 기존 합격 기준에서의 탈락은 분명하다.

설치 코드 `MAP/venv/Lib/site-packages/umap/umap_.py:2692,2707`은 categorical y가 있으면 `far_dist=2.5/(1−w)`를 쓰고, `:658`에서 다른 라벨 간 graph weight에 `exp(−far_dist)`를 곱한다. w=0.05에서 배수 **0.071965**, w=0.1에서 **0.062177**이다. **w→0도 far_dist→2.5이지 0이 아니다.** 따라서 낮은 target_weight를 “거의 비감독”으로 읽으면 틀린다. 이 배수는 후속 graph 재정규화 전 값으로 최종 거리 변화량과 같지 않다.

“w=0.2에서 이미 비용 포화”라는 정확한 문장은 확인한 D9·두 HTML에서는 찾지 못했다. 검증 질문의 가설로 검토한 결과, **작은 w에서도 큰 비용이라는 관측은 지지되지만 수학적으로 완전히 일정하거나 0.2가 포화 시작점이라는 뜻은 아니다**. 추가 저가중치 스윕이나 실험 B 재채택을 추천하지 않는다.

### V6. 확인함, 문제 없음 — reminds_pct는 출발점별 거리 순위 평균; 0.5는 근사, A2

**방법·어디:** `MAP/build_map.py:149` 원함수와 `scratch/measurements.json:2600` 대조. 각 방향 간선 i→j에 대해 자기 자신을 제외하고 j보다 **엄격하게 더 가까운** 점 수를 센 뒤 `(N−1)`로 나누어 간선별 평균한다. 전역 pairwise 거리의 CDF도, 원거리 단위의 비율도 아니다. src가 간선을 많이 가지면 그만큼 가중된다.

동률 없는 N=1000에서 가능한 rank는 0~998이고, 균등 무작위 파트너 기대값은 실행 계산상 **0.4994995**다. 그러므로 “무작위 약0.5”는 맞지만 **정확히0.5는 아니다**. 동률은 strict `<` 때문에 추가로 내려갈 수 있다. D9의 cross 지표도 “다른 라벨 파트너만 뽑는 조건부 무작위”에 보정된 통계량은 아니다. 기존 전체 파트너 기준 백분위와 사전 확정된 baseline+margin 판정으로 읽는다.

재현된 random 좌표의 실현값 **0.505819**, 채택 UMAP **0.176585**는 이 정의와 일치한다(`scratch/baseline/results/layout_comparison.csv:2,5`). 0.1766을 “17.66%만 닮았다” 또는 “82.34% 정확하다”로 바꾸어 읽으면 안 된다.

## 3. 개선 제안

아래 구현 시간은 **계획 추정**이며 측정된 성능·작업 시간이 아니다. 원본 수정은 이번 요청 범위 밖이므로 실행하지 않았다.

| 제안 | 푸는 문제 | 효과·한계 | 구현 시간 추정 | 검증 |
|---|---|---|---|---|
| 지표·규칙 설명 정정, 기대값 자기 제외 보정 | B1·I1~I5의 잘못된 해석 전파 | 기대값 0.174998→0.174172. 좌표 품질 개선은 해당 없음 | 1~2시간 | 원 `evaluate_layout` 값 유지, 고정 라벨의 유한모집단 기대값 대조, 문서/코드 조건 일치 |
| Development 중복 여부별 평가 분리 | G1의 평가 독립성 혼동 | 중복 관계 56/872 확인. 낙관 편향 감소량은 **미측정** | 2~4시간 | 같은 후보군·좌표에서 기존 `edge_distance_percentile`; src 단위 재표집, Holdout 사용 금지 |
| 명명 전 전체8 lift·coverage 고정 | G2의 5개 근사와 임계값 민감도 | 9영역 중 6곳 순위 변경 확인. 명명 이해도 개선은 **미측정** | 1~2시간 | 입력 라벨·좌표를 고정해 기존 `evaluate_layout`·`region_cohesion` 불변 확인; 20/30/40% 라벨 차이는 별도 표기 |
| 밀도 우세 또는 alpha 경계를 명시적 포함 정책과 함께 선택 | G3의 경계 내부 혼입 | 9영역 convex 71.36%, KDE(0.5h) 9.40%, alpha(h) 6.81%. alpha는 34점 미포함 | 0.5~1일 | 기존 좌표 지표 불변 + 이번 혼입/포함 지표; 격자화 후 실제 다각형으로 재검증 |
| 신규 투영 품질을 학습과 분리 관리 | G4의 확장 시 동일 품질 가정 | 6,815개 투영 실행, 신규 reminds 0.214374 대 학습 0.179709. 사용자 탐색 효과·배포 성능은 **미측정** | 0.5~1일 | 같은 후보 분모의 기존 `edge_distance_percentile`, 신규 데이터 반복 seed/동일 표본 대조 |

선정 방식·clustering·감독 UMAP의 교체는 제안하지 않는다. 이번 두 대안 비교와 저가중치 실험이 교체의 근거를 만들지 못했다(§2 V4·V5).

## 4. 실행한 명령과 소요 시간

작업 디렉터리: `C:/Users/SSAFY/Desktop/hyanghae/MAP`. 기존 `venv/Scripts/python.exe` 사용. Python **3.11.9**, numpy **2.4.6**, pandas **3.0.5**, scipy **1.17.1**, sklearn **1.9.0**, umap-learn **0.5.12**, numba **0.67.0**, llvmlite **0.49.0**(`scratch/baseline_check.json:2`). 설치·업그레이드는 하지 않았다.

주 실행 명령(PowerShell):

```powershell
.\venv\Scripts\python.exe -B -u review_scratch\reproduce.py *> review_scratch\baseline.log
.\venv\Scripts\python.exe -B -u review_scratch\experiments.py *> review_scratch\experiments.log
.\venv\Scripts\python.exe -B -u review_scratch\experiments.py --resume-boundaries *> review_scratch\continuation.log
.\venv\Scripts\python.exe -B -u review_scratch\frontend_check.py *> review_scratch\frontend_check.log
```

- 첫 명령: 원본 main 전체, 출력 상수만 변경, **44.324초**. baseline 불일치면 다른 실험을 못 돌리도록 scratch 스크립트에서 확인한다.
- 둘째 명령: 경계 직전까지 **25.480초**의 완료 단계를 저장했다. SciPy/Qhull이 임시파일을 scratch 밖에 만들려 하여 리뷰용 쓰기 보호에서 실패했다. **원본 파이프라인의 실패가 아니다.**
- scratch의 `TMPDIR/TEMP/TMP`만 지정한 뒤 셋째 명령으로 남은 단계를 이어 실행했다. 완료된 시드·선정·저가중치 실험은 반복하지 않았다. 이어 실행하기 위해 prepare와 seed42 좌표만 재생성했다. 재개 overhead를 포함해 기록된 누적 실험 구간은 **49.347초**이며, 초기 실패 지점 이후 예외 처리 시간은 포함하지 않는다(`scratch/measurements.json:20`). 현재 수정된 scratch 스크립트는 둘째 명령만으로도 경계 이후까지 실행할 수 있다.
- 넷째 명령: 첨부9영역 재현·동일 라벨/경계 계산, 내부 측정 **0.932초**(Python import 시간 제외; `scratch/frontend_check.json:1055`).

성공 단계별 내부 시간(`scratch/measurements.json:2`):

| 단계 | 초 |
|---|---:|
| prepare, 재개 실행 | 4.414 |
| nn10/15 × 5시드, 평가 포함 | 18.075 |
| 클러스터 결정성·complete/single | 0.158 |
| 낮은 감독 가중치 2회 | 2.195 |
| 선정 대안 2개 | 0.110 |
| Development 중복 | 0.184 |
| 원본12 라벨 계산 | 0.006 |
| 원본12 경계 비교 | 0.409 |
| 무작위 기대값 확인 | 0.022 |
| JSONL↔캐시 점검 | 5.360 |
| 확장 거리·transform·평가 | 4.813 |

읽기 점검은 `Get-Content`, `rg -n`, `rg --files`로 지정한 문서·소스·CSV를 확인하고, `json.loads`로 **04/05/21 세 노트북의 source와 저장된 설명**을 확인했다. 노트북을 실행하지 않았다. HTML 검색 때 embedded base64 이미지 때문에 출력이 잘려, 이후에는 `<img>`만 출력에서 제외한 본문·줄 번호를 다시 읽었다. 이미지에서 새로운 수치를 추출하지 않았다. 파일 조회·보고서 작성의 전체 벽시계 시간은 따로 계측하지 않았다.

첨부의 추가 간선 검증은 다음 읽기 전용 Python 계산으로 실행했다(측정 **0.0117초**). 9영역 top3 이웃 횡단 **548/3000**, 표시점 수는 c0/c1/c3/c4/c5/c6/c7/c8/c10 순 **24/74/42/17/4/2/6/29/2**, 모두 양수여서 첨부 HTML `:52,55`는 확인함, 문제 없음.

```python
import json
from pathlib import Path
f = json.loads(Path('review_scratch/frontend_check.json').read_text(encoding='utf-8'))
p = json.loads(Path('output/scent_map_v1.json').read_text(encoding='utf-8'))['perfumes']
lab = {r['id']: r['cluster'] for r in p}
for r in f['moves']:
    lab[r['id']] = r['to']
e = json.loads(Path('output/diagnostic_edges.json').read_text())['reminds_confident']
print(sum(lab[a] != lab[b] for a, b in e), len(e))
print(sum(lab[r['id']] != lab[b['id']] for r in p for b in r['neighbors'][:3]))
print({c: sum(r['display'] and lab[r['id']] == c for r in p)
       for c in sorted(set(lab.values()))})
```

보존: `scratch/reproduce.py:20`은 Holdout 경로 열기와 scratch 밖 파일 쓰기를 거부하는 Python audit hook을 설치한다. 파이프라인4개·DECISIONS·results의 모든 CSV·output 파일은 실행 전후 SHA-256이 동일했다(`scratch/baseline_check.json:36`, `scratch/measurements.json:2650`). `git status --short`의 작업 관련 추가물은 `review_scratch/`이며, 별도 `../.claude/` 미추적 항목은 건드리지 않았다.

**scratch는 남긴다.** 이 보고서 1개가 최종 리뷰 문서다. 같은 디렉터리의 실행 스크립트·로그·JSON 측정값·baseline 비교용 복사본·라이브러리 캐시는 재현 증거이며, 원본 `MAP/output/` 또는 `MAP/results/`의 새 산출물이 아니다.

## 5. 하지 않은 것

- **Final Holdout300 파일 열람·평가·튜닝: 하지 않음.** Development700은 원자료와 공개된 분할 코드의 앞700 부분만 재구성했다(§2 G1).
- EDA의 전체 후보 대상 Development retrieval 점수 재실행: 하지 않음. 이번 baseline은 요청한 지도 전체 파이프라인 재현이며 유사도 출처는 노트북·코드를 읽어 확인했다(§2 V1).
- 첨부 경계의 정확한 bandwidth·바다55%·격자 해상도 재현, 3D 렌더링·사람 평가: 미측정. 첨부는 관련 생성 코드를 포함하지 않아 같은 좌표·라벨 위의 명시적 비교 조건을 사용했다(§2 G3).
- 첨부의 9영역에 대해 D10 모든 엄격성/브랜드 통제 조합을 재계산: 하지 않음. A 기준 302/872와 top3 548/3000만 추가 확인했다(§2 I5, §4).
- 신규 투영의 반복시드·전체 재학습 대비 같은 신규 표본 대조, 인기·브랜드 매칭 이후 품질 차이, 응답속도·메모리 프로파일: 미측정(§2 G4).
- HDBSCAN·Ward, 더 많은 선정 규칙, 추가 감독 가중치: 실행하지 않음. 요청한 1~2개 대안 범위에서 complete/single, 선정2개, w2개로 제한했다(§2 V4·V5).
- 클러스터 row-order 민감도, 이름의 의미적 정확성·사용성, 경계의 사용자 이해도: 미측정. 이번 수치로 그런 개선을 주장하지 않는다(§2 V3·G2·G3).

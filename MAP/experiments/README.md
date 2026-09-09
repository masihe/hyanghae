# `experiments/` — 향 지도 실험 산출물

향 지도 실험 캠페인(`SCENT_MAP_EXPERIMENT_DESIGN_v4.md`)의 산출물을 실험 단위로 격리해 둔다.

**실험 코드는 여기 두지 않는다.** 기존 관례를 따라 `src/map/experiment_*.py` 에 두고,
`main()` 첫 줄에서 `os.chdir(MAP_DIR)` 한 뒤 이 폴더로 산출물을 쓴다.

```bash
venv/Scripts/python.exe src/map/experiment_phase0_snapshot.py
```

---

## 실험 ID 규칙

| 형태 | 예 |
|---|---|
| Phase 0 | `phase0` (단일 폴더) |
| Phase 1 이후 | `P<phase><실험ID>_<SHORT_NAME>` — `P1_A8_NOTE_COOCCURRENCE`, `P3B_C8A_PERCEPTION_ONLY` |

대문자 스네이크. 실험 ID(`A8`, `C8a`)는 설계서의 표기를 그대로 쓴다.

---

## 폴더 구조

```
experiments/<experiment_id>/
├─ manifest.json        # 무엇을 어떤 입력으로 돌렸는가 (필수)
├─ metrics.json         # 측정값 (필수)
├─ cases.csv            # rescue / regression 사례 (해당 시)
├─ coordinates.csv      # 지도 실험인 경우
├─ intermediates/       # 대형 중간물 (커밋 안 함)
└─ review.html          # KEEP / REVIEW 후보만
```

Phase 단위 검토는 `experiments/phase<N>/summary.html` 에서 한다.
개별 `review.html` 은 KEEP·REVIEW·최종 비교에 남은 후보에만 만든다.
명백한 DROP 은 `metrics.json` + summary 의 한 줄 결론으로 충분하다.

HTML 은 실험 코드가 직접 쓰지 않는다. `_report_template/render_report.py` 가
`manifest.json` / `metrics.json` / `cases.csv` 를 읽어 생성한다.

---

## `manifest.json` 스키마

```
experiment_id · phase · status(NEW|EXISTING|OPTIONAL|DROP)
hypothesis · user_meaning · changed_variable
population(dev700|global1000|korea200) · snapshot_hash
feature_version · family_mapping_version · family_score_version
projection · parameters · seeds
primary_metrics · guardrail_metrics · baseline_reference
output_files · reproduction_gate_result · limitations · recommendation
```

`changed_variable` 은 **한 줄에 한 가지**여야 한다. 두 가지를 동시에 바꾼 실험은
대조군을 함께 기록한다 (예: A8 은 `note IDF-cosine, PPMI 없음` 대조군을 함께 낸다).

---

## 채점 기준의 분리

| 질문 | 쓰는 지표 | 쓰면 안 되는 지표 |
|---|---|---|
| 유사도 정의가 사람 감각과 맞는가 (Phase 1) | Dev 700 `ndcg@10`, 신뢰 파트너 `top10` 포함률 | **kNN overlap** — feature 가 원본 공간을 바꾸므로 자기 채점이 된다 |
| 유사도를 2D로 잘 옮겼는가 (Phase 2) | `kNN overlap@K`, `trustworthiness@K`, `continuity@K`, 전역 거리 순위 상관 | — |

### 고정 시험지 — Neighbor Explainability

어떤 feature 를 실험하든 **기준을 바꾸지 않는다.**

1. 원본 note 문자열의 공통 개수
2. 원본 accord 중 코퍼스 보유율 30% 미만인 것의 공통 개수

A7(note 집계) · A8(공동출현) 도 자기 feature 표현으로 재정의하지 않는다.

---

## 게이트 판정 규칙

```
판정 = 시드 5개(42, 1, 2, 3, 4)의 평균과 최소값
최소값이 게이트에서 0.01 이내면 자동 판정 금지 → REVIEW

Gate A  cross-family trusted-pair 근접도 <= baseline + 0.05   (Global 1,000)
Gate B  trustworthiness@10 >= 0.90                            (모집단을 manifest 에 명시)
```

**시드별 통과 개수도 함께 본다** (D23 에서 추가). 위 규칙은 평균과 최소값만 보므로,
"평균은 통과인데 일부 시드가 게이트를 넘는" 경우를 잡지 못한다. 게이트를 시드마다
따로 적용해 **전부 통과 PASS · 일부만 통과 REVIEW · 전부 실패 DROP** 으로 판정한다.
D23 의 계열 0.35 단독이 그 사례다 — 평균 0.3056 · 최소 0.2920 이라 위 규칙만으로는
통과인데, 최대 0.3147 이 합격선 0.3115 를 넘어 **3/5 REVIEW** 다.

**후보 간 순위를 매길 때는 시드 표준편차와 비교한다.** 간격이 시드 표준편차보다 작으면
서열화하지 않는다. D23 에서 C8b · 계열 0.10 · 계열 0.20 · C1 네 후보의 Gate A 간격이
0.0015~0.0086 이고 시드 표준편차가 0.0093 이라 **구별 불가**로 판정했다.

Gate B 의 baseline 은 모집단마다 다르다 — Korea 200 `0.9213 ± 0.0013`,
Global 1,000 `0.9387`. 어느 모집단에서 쟀는지 적지 않은 값은 쓸 수 없다.

`overlap >= 0.30` 은 D2 의 UMAP 스윕 최저값에서 나온 기준이므로
**다른 투영 알고리즘의 자동 탈락선으로 쓰지 않는다** (Phase 2 는 baseline 대비 상대 + Pareto).

---

## 지도 시각 비교 정렬

`src/map/compare_korea_map_population.py` 의 `align()` (`scipy.linalg.orthogonal_procrustes`) 을 재사용한다.

- 허용: 회전, 반사
- 금지: 스케일 변경, 비선형 warping
- HTML 표기 필수: "시각 비교를 위해 회전/반사 정렬했습니다. 스케일은 변경하지 않았습니다."
- **지표는 정렬 전 좌표로 계산한다.**

---

## 확정 후보 구조 (D24)

| 역할 | 후보 | 구성 |
|---|---|---|
| **메인** | **C8b** | Base 0.50 + Family 0.35 + Perception 0.15 |
| Final challenger | Family 0.50 + Perception 0.075 | Base 0.425 + Family 0.50 + Perception 0.075 — **Gate A REVIEW** (15시드 최악 여유 +0.0076) |
| 안전 대안 | Family 0.20 | Base 0.80 + Family 0.20 |
| Baseline | C1 | Base 1.00 (현재 출하 좌표) |

혼합 거리 정의 — `D_blend = (1-wf-wp)·D + wf·Df + wp·Dp`
(`D` Base Similarity · `Df` 계열 프로파일 코사인 · `Dp` 사용자 투표 인식 축)

**종료된 후보** — `C3 semi w=0.35`(실험 기록만 보존) · `Perception 0.30` 계열 · `TriMap-dist` 전환 · `C2 supervised` 전 가중 · `C4` · `C5` · `C6`

### 후보 선택 우선순위 (D24)

향 지도는 "원래 이웃을 정확히 복원하는 지도"가 아니라 **"향 계열을 공간적으로 이해하고 탐색하는 지도"**로 정의한다.

1. 향 계열 Territory 가 명확하게 읽히는가 (`cohesion ratio` **와** `fragments` 를 함께 본다 — D24 에서 두 값이 반대로 움직였다)
2. 경계 향수가 다른 계열로 넘어가는 탐색 경로를 만드는가 (`boundary_gap`)
3. Gate A · Gate B 를 **안정적으로** 지키는가 (통과 개수 + 최악값 여유)
4. 위를 만족한 뒤 `kNN overlap@10` 손실이 작은 쪽

**overlap 최대화보다 영역 가독성을 우선하되, 보호 지표를 통과하는 범위 안에서만 허용한다.**

---

## 기준값 (Phase 0 에서 실측 고정)

| 모집단 | 지표 | 값 |
|---|---|---|
| Korea 200 | 신뢰 간선 / 보유 향수 | 44쌍 / 46개 |
| Korea 200 | trust@10 (seed 42 / 5시드) | 0.9191 / 0.9213 ± 0.0013 |
| Korea 200 | kNN overlap@10 (seed 42) | 0.4875 |
| Korea 200 | Set B 영역 응집도 ratio (seed 42 / 5시드) | 3.264 / 3.205 ± 0.043 |
| Korea 200 | trusted-edge 근접도 (5시드) | 0.1672 ± 0.0118 |
| Global 1,000 | 신뢰 간선 | 872쌍 |
| Global 1,000 | cross-family 쌍 (Set B `reviewed-1` 9계열) | **412쌍** |
| Global 1,000 | cross-family 쌍 (`draft-1` 9계열 · 동결) | 435쌍 |
| Global 1,000 | cross-family 근접도 (seed 42 / 5시드) | 0.2615 / **0.2492 ± 0.0093** |
| Global 1,000 | Gate A 합격선 (seed 42 baseline + 0.05) | **0.3115** |
| Global 1,000 | Set B 영역 응집도 ratio (seed 42 / 5시드) | 4.187 / 4.234 ± 0.045 |
| Global 1,000 | trust@10 / kNN overlap@10 | 0.9387 / 0.3888 |
| Global 1,000 | 신뢰 파트너 top10 포함률 | 0.4464 |
| Global 1,000 | 대조군 note IDF-cosine (PPMI 없음) | 0.4501 |
| Dev 700 | ndcg@10 | 0.2709 |

---

## 금지 사항

- `output/` 덮어쓰기 (백엔드 전달 대상). 특히 `korea_scent_map_v2.json`
- `results/` 기존 CSV 13개 덮어쓰기 (README 가 "수치의 출처"로 명시)
- `data/korea_popularity/evaluation/gold_set_test.csv` 열기 — Holdout 이므로 어떤 단계에서도 열지 않는다
- `verify_similarity.build_eval_set()` 이 나누는 Holdout 300 질의 사용
- `perfumes.csv` / `perfumes.jsonl` 수정

### 재현 게이트

Phase 시작 전과 종료 시 `src/matching/evaluate_brand_mapping_dev.py` 를 돌려
5개 방법 4자리 재현 + 보호 산출물 8개 SHA-256 불변을 확인한다. 실패하면 다음 Phase 로 넘어가지 않는다.

**이 스크립트는 자기 리포트를 다시 쓴다.** 실행 전 `data/korea_popularity/evaluation/` 을 백업할 것
(README "알려진 흠 ④" — method2 리포트에서 사람이 쓴 절이 지워진 사고가 있었다).

---

## 커밋 정책

| 커밋한다 | 커밋하지 않는다 (`.gitignore`) |
|---|---|
| 실험 코드, 공통 renderer/template | `intermediates/` 대형 중간 행렬 |
| `manifest.json`, `metrics.json` | `*.npz` embedding 캐시 |
| 작은 `cases.csv` | `coordinates_seed*.csv` 재생성 가능한 대형 좌표 |
| Family mapping 검토 파일 | |
| Phase `summary.html`, KEEP/REVIEW 의 `review.html` | |

`experiments/` 전체를 무시하지 않는다. summary HTML 은 가능하면 SVG/PNG 를 내부에 embed 해
파일 하나로 공유할 수 있게 만든다.

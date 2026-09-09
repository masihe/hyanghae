# 향 지도 인계 묶음

국내 대표 향수 **200개**를 향이 비슷한 것끼리 가까이 놓은 평면 지도입니다.
지도는 시트러스 · 플로럴 · 우디 같은 **향 계열 9개** 구역으로 나뉩니다.

이 폴더는 **밖으로 넘기려고 모아둔 것**이고, 전부 하나의 원본
(`experiments/phase6/korea_scent_map_v3.json`)에서 형태만 바꿔 만들었습니다.

## 표기 규약

문서와 주석에서 두 가지를 구분해 두었습니다.

- **[측정]** — 실제 데이터에서 확인한 값입니다. 여기에 맞지 않게 만들면 데이터가
  들어가지 않으니 그대로 지켜야 합니다.
- **[제안]** — 저희 판단일 뿐입니다. **참고만 하시고 실제 설계는 담당자분이
  정하시면 됩니다.** 그대로 구현하지 않아도 괜찮습니다.

테이블 구성 · DDL · 엔드포인트 모양 · 그리는 순서는 전부 [제안]입니다.

## 누구에게 어느 폴더를 주면 되나

**폴더 하나를 그대로 전달하면 됩니다.** 각 폴더 안에 그 담당자가 필요한 것이 다
들어 있고, 맨 앞에 `README.md` 와 인계 문서 HTML 이 있습니다.

| 담당 | 줄 폴더 | 안에 든 것 |
|---|---|---|
| **DB** | `for_db/` | 인계 문서 · 시드 CSV 6개 · DDL 제안 |
| **백엔드** | `for_backend/` | 인계 문서 · 응답 예시 · 목업용 데이터 |
| **프론트** | `for_frontend/` | 인계 문서 · 지도 데이터 · 지도 배경 · 타입 정의 |

인계 문서는 **단독 HTML** 이라 브라우저로 바로 열립니다. 프론트 문서는 문서 안에서
그 폴더의 파일만으로 지도를 실제로 그려 보여줍니다.

```
for_db/
  README.md
  handoff_db.html
  scent_map_proposal.sql              CREATE / ALTER 제안
  seed/accords.csv                       60행   향 특성 이름
  seed/scent_families.csv                 9행   향 계열 9개 (이름 · 영역 · 라벨 위치)
  seed/perfume_map_points.csv           200행   향수 좌표
  seed/perfume_map_families.csv         303행   향수 <-> 계열   <- 지금 ERD 에 없는 표
  seed/perfume_map_neighbors.csv       2000행   닮은 향수 (향수당 10개)
  seed/perfume_map_accords.csv         1598행   향수의 향 특성 (향수당 7~8개)

for_backend/
  README.md
  handoff_backend.html
  example_map_response.json           응답 예시
  scent_map.json                      적재 전 목업용

for_frontend/
  README.md
  handoff_frontend.html
  scent_map.json                      향수 200개 + 향 계열 9개
  scent_map_terrain.json              지도 배경 — 런타임 정적 자산
  scent-map.d.ts                      TypeScript 타입

verification.json                     검증 결과 (내부 기록. 전달하지 않아도 된다)
```

`scent_map.json` 이 백엔드·프론트 양쪽에 있습니다. **같은 파일**이고, 폴더 하나만
전달해도 되도록 일부러 넣어 둔 것입니다.

CSV 는 UTF-8(BOM) 이라 Excel 로 바로 열립니다. 향수는 전부 `fragrantica_id` 로
되어 있습니다 — **DB 의 향수 식별 방법이 정해지면 그 키로 다시 내보내 드립니다.**

## 특히 주의할 것 3가지

1. **닮은 향수를 좌표 거리로 계산하면 안 됩니다.** 미리 계산된 목록
   (`neighbors`)이 정답입니다. 좌표는 200개를 평면에 눌러 담은 결과라 가까운
   관계만 우선 보존합니다.
2. **계열 가중치에 `>= 0.24` 제약을 걸면 안 됩니다.** 계열을 뽑는 기준은 0.24
   지만 가장 큰 계열은 기준에 못 미쳐도 반드시 넣기 때문에, 실측 최솟값은
   **0.20** 입니다.
3. **좌표계가 두 개입니다.** 향수 점은 `[0,1]`, 계열 폴리곤 · 해안선 · 라벨
   위치는 여백이 붙은 더 넓은 좌표계라 **음수가 나옵니다.**

## 이 폴더를 다시 만들기

원본 v3 가 이미 있으면 두 줄이면 됩니다. 표준 라이브러리만 씁니다.

```
venv/Scripts/python.exe src/delivery/build_delivery.py
venv/Scripts/python.exe src/delivery/build_handoff_docs.py
venv/Scripts/python.exe src/delivery/verify_delivery.py     # 검증
```

## 원본 v3 자체를 다시 만들기

지도를 다시 생성해야 할 때만 필요합니다. **numpy · scipy · umap-learn 과 원본
데이터 121 MB 가 필요하고, 파생 캐시를 먼저 만들어야 합니다.**

```
1. MAP/perfumes.jsonl (486 MB) 과 MAP/perfumes.csv (121 MB) 를 둔다
   -> perfumes.csv 의 SHA-256 이 cec1ea0b...345cc055 여야 한다 (스크립트가 검사)

2. venv/Scripts/python.exe src/common/prepare_data.py
   -> cache/people.csv · cache/reminds_edges.csv · cache/also_liked_edges.csv

3. ../EDA/analysis_outputs/10_note_dictionary.csv 와 10_accord_dictionary.csv 가
   있어야 한다 (EDA 쪽 산출물이며 MAP 이 만들지 않는다)

4. output/korea_scent_map_v2.json 이 있어야 한다 (향수 200개 집합의 정의)

5. venv/Scripts/python.exe src/map/build_korea_scent_map_v3.py
   -> experiments/phase6/korea_scent_map_v3.json   검증 17개를 통과해야 한다
```

지도를 다시 만들면 **향수 200개의 좌표와 계열 영역이 전부 바뀝니다.** 일부만
바뀌는 일이 없으므로, DB 갱신은 행 단위 수정보다 비우고 다시 넣는 쪽이 안전합니다.

## 아직 정하지 않은 것

- **향수를 무엇으로 식별할지** — DB 담당자 확인 필요. 나머지가 여기 달려 있습니다.
- **`scent_regions` 에 기존 행이 있는지** — 있으면 향 계열 9개를 어디에 둘지 정해야
  합니다.
- **좁은 화면의 계열 이름** — 375px 에서 3개가 가장자리에 걸립니다 (768px 이상은
  9개 전부 정상). 범례로 빼기 / 줌 후 표시 / 짧은 이름 중 미결.
- **향수별 계절 · 시간대 투표** — 데이터는 있는데(200개 중 185 · 181개) 담을 표가
  없어 이번 CSV 에서 뺐습니다.

## 원본의 상태

`korea_scent_map_v3.json` 은 `dataset_status: "DRAFT"` 입니다. 검증 17개를 전부
통과했지만 **아직 프로덕션(`output/`)으로 옮기지 않았습니다** — 프론트가 형태를
확인한 뒤 옮기는 것이 팀 결정이었습니다. 이 폴더의 데이터는 그 초안에서 나온
것입니다.

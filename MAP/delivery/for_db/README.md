# DB 담당자용 — 향 지도

이 폴더만 있으면 됩니다. **`handoff_db.html` 을 브라우저로 먼저 열어 주세요.**
무엇을 어떤 표에 넣으면 되는지, 넣을 때 걸리기 쉬운 곳이 정리돼 있습니다.

## 이 폴더의 파일

```
handoff_db.html            <- 먼저 읽어 주세요
seed/accords.csv                     60행   향 특성 이름
seed/scent_families.csv               9행   향 계열 9개 (이름 · 영역 · 라벨 위치)
seed/perfume_map_points.csv         200행   향수 좌표
seed/perfume_map_families.csv       303행   향수 <-> 계열   <- 지금 ERD 에 없는 표
seed/perfume_map_neighbors.csv     2000행   닮은 향수 (향수당 10개)
seed/perfume_map_accords.csv       1598행   향수의 향 특성 (향수당 7~8개)
scent_map_proposal.sql     CREATE / ALTER 제안 (제안입니다 — 그대로 실행하지 마세요)
```

CSV 는 UTF-8(BOM) 이라 Excel 로 바로 열립니다.

## 지금 확인이 필요한 것

**향수를 무엇으로 식별할지** 정해 주세요. CSV 는 전부 Fragrantica 의 id 로 되어
있는데, 현재 `perfumes` 테이블에는 그걸 담는 컬럼이 없습니다. **다른 키를 쓰기로
하시면 CSV 를 그 키로 다시 만들어 드립니다.**

그리고 `scent_regions` 테이블에 지금 행이 들어 있는지 알려 주세요. 있으면 향 계열
9개를 같은 테이블에 넣을지 새 테이블로 나눌지 정해야 합니다.

## 표기

문서에서 **[측정]** 은 실제 데이터에서 확인한 값이라 그대로 지켜야 하고,
**[제안]** 은 저희 판단일 뿐이니 참고만 하시면 됩니다. 테이블 구성과 DDL 은
전부 제안입니다.

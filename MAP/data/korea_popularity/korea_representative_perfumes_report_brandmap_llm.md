# 한국 인기 신호 기반 대표 향수 선정 및 향 지도 생성

## 입력과 identity

- 구매 판매상품 행: 828
- 화해 행: 100
- Commercial Identity: 684
- Candidate Family: 669
- Fragrantica MATCH 기반 Map Identity: 225
- map-ready Map Identity: 225

## 독립 상태 집계

### purchase_overlap_status (화해 100개)

- MATCH: 30
- MATCH_REVIEW: 2
- NO_MATCH: 68

### fragrantica_match_status (시도한 Commercial Identity)

- MATCH: 246
- MATCH_REVIEW: 34
- NO_MATCH: 231
- fragrantica_attempted_identity_count: 511
- fragrantica_skipped_identity_count: 173
- fragrantica_skipped_ratio: 0.2529
- fragrantica_elapsed_time: 2.987 seconds
- attempted Candidate Family: 498 / queue 669

## 선정

- TOP200: 200
- reserve: 20
- 화해 map-ready inclusion: 68
- 화해 rank와 구매 rank는 직접 합산하지 않았다.
- 브랜드·향 계열·군집 quota 및 Fragrantica 글로벌 인기도를 사용하지 않았다.

### RRF 민감도 (기준 k=60 TOP200과 비교)

| 조건 | 공통 identity | Jaccard |
|---|---:|---:|
| RRF k=20 | 200 | 1.0000 |
| RRF k=100 | 200 | 1.0000 |
| leave out musinsa | 182 | 0.8349 |
| leave out oliveyoung | 181 | 0.8265 |
| leave out lotte | 187 | 0.8779 |

## 남은 검토

- purchase_overlap_status=MATCH_REVIEW: 2
- fragrantica_match_status=MATCH_REVIEW: 34
- Fragrantica MATCH_REVIEW는 fuzzy 후보 탐색 결과일 뿐 자동 확정하지 않았다.
- 점진적 매칭 결과 map-ready 220개 미만이면 TOP200/reserve를 완성하지 않고 실제 수만 기록한다.

## 지도

- TOP200이 200개일 때만 accord·note 기반 UMAP과 사후 군집 검증을 생성한다.
- 군집 수는 2~15를 평가해 silhouette와 크기 조건으로 선택하며 사전에 4개로 고정하지 않는다.

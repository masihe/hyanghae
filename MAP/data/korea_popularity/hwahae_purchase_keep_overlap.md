# 화해 TOP100과 구매 KEEP 제품 overlap

화해 향수 TOP100을 상품명과 현재 로컬 근거만으로 최소 정제하고, 국내 판매 랭킹의 확정 KEEP 행과 브랜드·향수 정체성 기준으로 비교했다. 외부 요청, fuzzy threshold, SKU 통합, Fragrantica 매칭, 인기 점수 산출은 하지 않았다.

## 측정 결과

| 항목 | 건수 |
|---|---:|
| 화해 KEEP | 98 |
| 화해 EXCLUDE_NON_PERFUME | 0 |
| 화해 REVIEW | 2 |
| 구매 확정 KEEP | 790 |
| MATCH | 30 |
| NO_MATCH | 66 |
| MATCH_REVIEW | 2 |

엄격 overlap 비율은 `MATCH / 화해 KEEP` = `30 / 98` = **30.6%**다. MATCH_REVIEW는 분자에서 제외했다.
구매 확정 KEEP 790건은 판매상품 행 수다. SKU 또는 고유 향수 수로 통합하지 않았다.

## 화해 최소 정제

상품명에 피부용 일반 액상 향수로 볼 수 있는 향수·농도·코롱 표현이 있고 범위 밖 제형이 없으면 KEEP했다. 상품명만으로 제형을 확인할 수 없는 항목은 REVIEW로 유지했다.

- REVIEW 5위 `다니엘트루스 / 시그니처 밤쉘루스`: 상품명과 10ml 표기만으로 일반 액상 향수 제형을 확인할 수 없다.
- REVIEW 90위 `에디션드퍼퓸프레데릭말 / 포트레이트 오브 어 레이디`: 고유 제품명만 있고 상품명에 일반 액상 향수 제형 또는 농도 표현이 없다.

## 대표 사례

화해에만 확인된 대표 향수:

- 1위 `멈칫 / 스테이퍼퓸 [밤쉘]` — NO_MATCH
- 2위 `딥티크 / 오 드 퍼퓸 오르페옹` — NO_MATCH
- 4위 `조말론 / 우드 세이지 앤 씨 솔트 코롱` — NO_MATCH
- 8위 `르라보 / 어나더 13 EDP` — NO_MATCH
- 15위 `디올 / 미스 디올 오 드 퍼퓸` — NO_MATCH
- 26위 `바이레도 / 발 다프리크 오 드 퍼퓸` — NO_MATCH
- 46위 `입생로랑뷰티 / 리브르 오 드 빠르펭` — NO_MATCH
- 53위 `르라보 / 상탈 33 EDP` — NO_MATCH

구매 데이터와 겹친 대표 향수:

- 6위 `랑방 / 에끌라 드 아르페쥬 EDP` ↔ `oliveyoung:197 랑방 에끌라 드 아르페쥬 EDP 30ml`
- 12위 `메종 마르지엘라 / 레이지 선데이 모닝 EDT` ↔ `musinsa:27 레플리카 레이지 선데이 모닝 EDT 30ML`
- 19위 `포맨트 / 시그니처 퍼퓸 [코튼허그]` ↔ `musinsa:5 시그니처 퍼퓸  코튼허그 50ml`
- 27위 `제니퍼로페즈 / 글로우 바이 제이로 EDT` ↔ `oliveyoung:76 제니퍼로페즈 글로우 바이제이로 EDT 30ml`
- 52위 `지미추 / 블러썸 EDP` ↔ `oliveyoung:188 지미추 블러썸 EDP 40ml`
- 97위 `몽블랑 / 익스플로러 오 드 퍼퓸` ↔ `oliveyoung:123 몽블랑 익스플로러 EDP 100ml`

화해 추가로 보완되는 브랜드·제품 사례:

- `딥티크`: 오 드 퍼퓸 오르페옹
- `조말론`: 우드 세이지 앤 씨 솔트 코롱
- `르라보`: 어나더 13 EDP
- `디올`: 미스 디올 오 드 퍼퓸
- `바이레도`: 발 다프리크 오 드 퍼퓸
- `입생로랑뷰티`: 리브르 오 드 빠르펭

## 매칭 원칙

- 비교용 값에서 대소문자, 공백, 용량, 명시적 판촉 문구를 정규화했지만 Raw 값은 별도 컬럼에 그대로 유지했다.
- 최종 연결은 snapshot-specific MATCHES에 명시한 확인된 행만 사용했다. 문자열 유사도나 fuzzy 임계값은 사용하지 않았다.
- 양쪽에 농도가 있으면 동일해야 한다. 한쪽 농도가 없거나 상품 정체성 표현이 축약된 2건은 MATCH_REVIEW로 남겼다.
- 구매의 MANUAL_CHECK와 그 밖의 비확정 행은 비교 대상과 매칭 참조에서 제외했다.

MATCH_REVIEW:

- 화해 3위 `엘리자베스아덴 / 그린티 센트 스프레이` ↔ `musinsa:109` — brand_exact + identity_exact; purchase specifies EDC while Hwahae omits concentration
- 화해 80위 `코치 / EDT` ↔ `musinsa:176` — brand_alias + EDT_exact; Hwahae identity is abbreviated while purchase says women

## 검증

- 실행: `venv/Scripts/python.exe -B analyze_hwahae_purchase_overlap.py` (동일 명령 2회 실행).
- 화해 입력 100행, 순위 1~100 연속, source_product_id 100개 고유를 검사했다.
- 화해 Raw 모든 컬럼과 행 순서를 정제 CSV에 그대로 보존하고 상태 합계 100을 검사했다.
- 구매 1차 999행과 2차 128행을 다시 합성해 확정 KEEP 790행을 검사했다.
- MATCH + NO_MATCH + MATCH_REVIEW = 30 + 66 + 2 = 98를 검사했다.
- 모든 MATCH/MATCH_REVIEW가 생성된 구매 KEEP CSV의 실제 source:rank와 product_id를 참조하는지 검사했다.
- 양쪽에 농도 표현이 있는 매칭에서 농도 집합이 같은지 검사해 EDP/EDT 등 충돌을 차단했다.
- 세 CSV를 다시 읽어 필드·값 round-trip 일치를 검사했다.
- 네 입력 파일의 고정 SHA256을 실행 전 확인하고, 실행 후 바이트가 동일한지 검사했다.

- `hwahae_perfume_top100_raw.csv`: `7fc5930d5fb54d912de0c24bbb7ac989c1e20b9efa865929905ce656eadb65cc`
- `hwahae_perfume_top100_extraction.md`: `bf729d41920b7bf2c81f9652b38ad7af6eb5b3d03fa611743d1bdb7985ef013a`
- `korea_perfume_ranking_first_pass.csv`: `0775e32f757b42f832a5ac858e7b0aecc020ba5e40f5a0ae8ea33b306dbe10fd`
- `korea_perfume_ranking_second_pass_review.csv`: `5e203e10dc52725b0a99253c6ce1b4645fec67b4c409eb9083d5bca700ba01fc`

## 남은 문제

- 화해 REVIEW 2건은 상세 상품 정보 없이 일반 액상 향수 제형을 확정할 수 없다.
- MATCH_REVIEW 2건은 농도 누락 1건과 축약된 제품 정체성 1건이다.
- 다음 단계 전에 REVIEW/MATCH_REVIEW의 상세 제품 근거를 확인할 수 있다. 이번 결과에서는 임의 해결하지 않았다.
- 구매 KEEP 790행은 SKU 통합 전 판매상품 행이므로 최종 고유 향수 수로 해석하면 안 된다.

# Personal Fragrance 범위 재검토와 화해 overlap

기존 구매 데이터의 EXCLUDE_NON_PERFUME 69행만 frozen 상품명과 기존 옵션 판정으로 다시 검토했다. 외부 수집, SKU 통합, Fragrantica 매칭, 최종 후보 선정은 하지 않았다.

## 69행 범위 재검토

| 범위 | 건수 |
|---|---:|
| PERSONAL_FRAGRANCE | 56 |
| HOME_FRAGRANCE | 7 |
| UNRESOLVED | 6 |
| 합계 | 69 |

Personal Fragrance에는 헤어퍼퓸, 헤어·바디 미스트, 고체향수, 퍼퓸밤·젤·스틱을 포함했다. 룸·섬유·디퓨저·캔들·속옷 사용 제품은 Home Fragrance로 유지했다. 세정·보습·애프터쉐이브 제품과 Y존/속옷 적용 대상이 불명확한 항목은 UNRESOLVED로 남겼다.

## 구매 후보 변화

| 판정 | 건수 |
|---|---:|
| 후보 복귀 | 36 |
| Home Fragrance 제외 | 7 |
| 범위 unresolved | 6 |
| 다향 선택 제외 | 11 |
| 혼합 옵션 제외 | 5 |
| 옵션 미확인 | 4 |
| 합계 | 69 |

구매 후보는 **790행에서 826행으로 36행 증가**했다. 이는 판매상품 행 수이며 SKU 또는 고유 제품 수가 아니다.

복귀 사례:

- `musinsa:59` 포뷰트 / 시그니처 헤어퍼퓸 애프터 선셋 남자향수 50ml
- `musinsa:103` 슬로우허밍 / 릴리프 퍼퓸밤
- `musinsa:246` 돌체앤가바나 / 라이트 블루 하이드레이팅 퍼퓸 젤 30ml
- `oliveyoung:32` 클린 / 클린 헤어&바디 퍼퓸 미스트 휩드바닐라 88ml/236ml
- `oliveyoung:100` 포맨트 / [박지훈 PICK/거울키링증정] 포맨트 시그니처 헤어 퍼퓸 코튼메모리 30ml (포켓몬 에디션)
- `oliveyoung:278` 슬로우허밍 / 슬로우허밍 플라워너리 릴리프 퍼퓸밤 플레르베일

## 화해 TOP100 overlap

이번 비교는 요청에 따라 화해 100개 전체를 분모로 사용했다.

| 항목 | 기존 결과 | Personal Fragrance 결과 | 변화 |
|---|---:|---:|---:|
| 화해 비교 행 | 98 | 100 | +2 |
| MATCH | 30 | 30 | +0 |
| NO_MATCH | 66 | 68 | +2 |
| MATCH_REVIEW | 2 | 2 | +0 |
| MATCH 비율 | 30.6% | 30.0% | -0.6%p |

새롭게 MATCH된 화해 상품은 **0건**이다. 기존 98개와 같은 분모로 비교하면 MATCH/NO_MATCH/MATCH_REVIEW는 모두 변하지 않았다. 새 결과의 NO_MATCH +2와 비율 -0.6%p는 이전 REVIEW 2개를 포함해 화해 100개 전체를 사용한 데서 발생했다.

복귀 상품 중 화해와 브랜드가 같은 모든 조합을 확인했다. 포맨트 코튼메모리 헤어퍼퓸처럼 향 이름이 같아도 일반 퍼퓸과 제품 제형이 다르면 같은 제품으로 연결하지 않았다.

## 사람이 확인할 항목

범위 또는 옵션 확인이 필요한 행은 10건이다.

- `musinsa:46` 에이딕트 / 솔리드 퍼퓸 30ml (선택) — 선택 항목이 향·용량·구성 중 무엇인지 확인이 필요하다.
- `musinsa:66` 포엘리에 / Y존향수 이너퍼퓸 5ml 택1 — Personal Fragrance 포함 여부를 상품명만으로 확정하지 않는다.
- `musinsa:185` 아디다스 향수 / 아디다스 바이브 샤워젤 400ml (6종 택 1) — Personal Fragrance 포함 여부를 상품명만으로 확정하지 않는다.
- `musinsa:204` 몽블랑 퍼퓸 / 레전드 애프터쉐이브 밤 150ML (남성용로션) — Personal Fragrance 포함 여부를 상품명만으로 확정하지 않는다.
- `musinsa:234` 비비앙 / [기프트세트] 핸드크림 2개 듀오세트 — Personal Fragrance 포함 여부를 상품명만으로 확정하지 않는다.
- `musinsa:250` 바디판타지 / 바디판타지 X 포차코 바디스프레이 50ml (택1) — 선택 항목이 향·용량·구성 중 무엇인지 확인이 필요하다.
- `oliveyoung:55` 캘빈클라인 / 캘빈클라인 CK ONE 모이스처라이저 250ml — Personal Fragrance 포함 여부를 상품명만으로 확정하지 않는다.
- `oliveyoung:143` 슬로우허밍 / [단독기획] 슬로우허밍 헤어 퍼퓸 미스트 80ml 2종 — 선택 항목이 향·용량·구성 중 무엇인지 확인이 필요하다.
- `oliveyoung:283` 벨벳바니 / 벨벳바니 퍼퓸 샤워시트 3종 [옐로우 팝/화이트 클래식/핑크 블롬] — Personal Fragrance 포함 여부를 상품명만으로 확정하지 않는다.
- `oliveyoung:291` 메모 / 메모 헤어퍼퓸 3종  80ml — 선택 항목이 향·용량·구성 중 무엇인지 확인이 필요하다.

## 검증

- 실행: `venv/Scripts/python.exe -B analyze_personal_fragrance_scope.py`.
- 기존 EXCLUDE_NON_PERFUME 69행을 56/7/6으로 빠짐없이 분류했다.
- 기존 구매 KEEP 790행을 전부 보존하고 복귀 36행만 추가해 826행인지 검사했다.
- Personal Fragrance라도 SCENT 11, MIXED 5, UNKNOWN 4는 후보로 복귀하지 않았는지 검사했다.
- 화해 입력 순위 1~100, product_id 고유성, overlap 100행과 30/68/2 합계를 검사했다.
- 기존 overlap 98행의 모든 원래 컬럼과 상태가 그대로 유지됐는지 검사했다.
- 모든 MATCH/MATCH_REVIEW가 새 구매 후보의 실제 행·product_id를 참조하고 농도 충돌이 없는지 검사했다.
- 복귀 36행과 화해 TOP100의 같은 브랜드 조합 15개를 모두 명시적으로 검토했는지 검사했다.
- 세 CSV round-trip과 입력·기존 결과 파일의 실행 전후 바이트 불변을 검사했다.

- `korea_perfume_ranking_first_pass.csv`: `0775e32f757b42f832a5ac858e7b0aecc020ba5e40f5a0ae8ea33b306dbe10fd`
- `korea_perfume_ranking_second_pass_review.csv`: `5e203e10dc52725b0a99253c6ce1b4645fec67b4c409eb9083d5bca700ba01fc`
- `hwahae_perfume_top100_raw.csv`: `7fc5930d5fb54d912de0c24bbb7ac989c1e20b9efa865929905ce656eadb65cc`
- `korea_perfume_ranking_confirmed_keep.csv`: `7088e217cd23eff9d8cec29d7adbdd63abc9f8a80ac7dcdcfb77be7691583251`
- `hwahae_purchase_keep_overlap.csv`: `fec918ba9c59ef16323edeaa075c643f378aa0e8b0c6971ead5ad4e52040eab3`

## 남은 문제

- UNRESOLVED 6행은 향이 주목적인 제품인지 또는 피부에 직접 쓰는지 확인이 필요하다.
- Personal Fragrance 중 UNKNOWN 옵션 4행은 실제 옵션명이 향·용량·구성 중 무엇인지 확인이 필요하다.
- 기존 MANUAL_CHECK 60행은 이번 69행 재검토 범위에 포함하지 않았고 구매 후보에서도 제외했다.
- 후보 826행은 SKU 통합 전 판매상품 행 수다.

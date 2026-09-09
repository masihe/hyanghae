# 화해 향수 TOP100 Raw 추출

입력 HAR 응답만 사용했다. 외부 요청, 상품 정제, 기존 판매 데이터 매칭, SKU 통합은 수행하지 않았다.

## 확인한 구조

- 최초 HTML entry 2의 `__NEXT_DATA__`에 page 1 상품 20개가 있다.
- `/v14/rankings/95/details` JSON 응답 page 2~5에 각각 20개가 있다.
- 페이지 provenance: page 1=entry 2, page 2=entry 96, page 3=entry 122, page 4=entry 146, page 5=entry 170.
- 랭킹 경로: `카테고리별 랭킹 > 향수 > 전체`. CSV `ranking_basis`는 HAR 원문 `카테고리별 랭킹`이다.
- 랭킹 업데이트: `2026-09-03T05:00:00` (`2026.09.03. 업데이트`). 모든 페이지에서 동일하다.
- HAR 페이지 수집 시각: `2026-09-06T05:09:01.529Z`. `collected_at`에는 HAR에 있는 날짜 `2026-09-06`를 기록했다.
- 상품별 rank 필드는 없으므로 검증된 page/page_size와 응답 배열 순서로 1~100위를 복원했다.

## 검증 결과

- 행 수: 100
- 순위: 1~100 연속, 누락 0, 중복 0
- 고유 source_product_id: 100
- 중복 product_id 값: 0; 첫 행 이후 중복 행: 0
- is_rank_new: true 2, false 98

| 필드 | 결측 수 |
|---|---:|
| source | 0 |
| source_rank | 0 |
| ranking_basis | 0 |
| ranking_updated_at | 0 |
| source_product_id | 0 |
| brand_raw | 0 |
| product_name_raw | 0 |
| package_info_raw | 2 |
| price_raw | 5 |
| commerce_price_raw | 91 |
| review_count | 0 |
| review_rating | 0 |
| is_rank_new | 0 |
| rank_delta | 0 |
| collected_at | 0 |
| source_file | 0 |
| har_entry_index | 0 |

## Raw 필드 주의사항

- `price_raw`는 `product.price`, `commerce_price_raw`는 `goods.price`를 그대로 저장했다. 두 값 중 하나를 임의로 선택하지 않았다.
- `price_raw` 결측 5건, `commerce_price_raw` 결측 91건이다. 값 0은 결측으로 바꾸지 않았다.
- `package_info_raw` 결측 2건이다. 브랜드·상품명·review_count·review_rating은 결측이 없다.
- boolean은 CSV에서 `true`/`false`로 직렬화했다. 상품명·브랜드·용량·가격 값은 정규화하거나 보정하지 않았다.
- 요청 헤더, 쿠키, 사용자 식별값, 상품 이미지와 리뷰 주제는 내보내지 않았다.

## 재현

- 실행: `venv/Scripts/python.exe -B extract_hwahae_ranking.py`.
- 스크립트는 HTML/API 페이지 구조, 총 100개, page 1~5, 순위 연속성, ID 고유성, 메타데이터 일치와 CSV round-trip을 검사한다.
- 입력 HAR SHA256: `a085a63aa2c928799423b6dc7e78824cd25852bc426ade0ee5c74f8f7d74812d`. 처리 전후 바이트가 동일함을 검사한다.
- 저장소 `.gitignore`에는 이미 `*.har`와 `*.har.gz`가 있어 수정하지 않았다. `git check-ignore`로 이 HAR가 제외됨을 확인했다.

## 다음 단계 전 확인

- 가격 필드 둘의 의미와 후속 단계에서 사용할 가격을 결정해야 한다.
- package_info/price 결측은 상세 상품 데이터가 필요할 때만 별도로 확인한다.
- 이 CSV는 화해 향수 카테고리의 Raw 랭킹이다. 향수 범위 정제와 기존 구매 랭킹 매칭은 미수행이다.

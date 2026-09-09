# identity-preserving MIXED 재검토와 화해 overlap

최근 Personal Fragrance 재검토에서 `EXCLUDE_MIXED_OPTION`이었던 5행만 frozen 상품명과 기존 옵션 판정 근거로 다시 확인했다. 외부 데이터 수집, SKU 통합, Fragrantica 매칭, 최종 Top200 선정은 하지 않았다.

## MIXED 5행 판정

| 구매 행 | 브랜드 | 상품 | MIXED 판정 | 후보 처리 | 근거 |
|---|---|---|---|---|---|
| `oliveyoung:21` | 캘빈클라인 | [NEW] CK 캘빈클라인 헤어&바디 퍼퓸 미스트 100ml/236ml 6종 | IDENTITY_CHANGING | KEEP_EXCLUDED | 헤어&바디 퍼퓸 미스트 6종과 100ml/236ml 선택이 함께 있어 향수 정체성이 달라질 수 있다. |
| `oliveyoung:28` | 투크 | [OY 단독 기획] 투크 실루엣 헤어 퍼퓸 68ml 3종 택1 (단품/기획) | IDENTITY_CHANGING | KEEP_EXCLUDED | 헤어 퍼퓸 3종 택1과 단품/기획 선택이 함께 있어 향수 정체성이 달라질 수 있다. |
| `oliveyoung:75` | 클린 | 클린 헤어&바디 퍼퓸 미스트 파파야 파라다이스 88ml,236ml (단품/기획) | IDENTITY_PRESERVING | RETURN_TO_CANDIDATES | 파파야 파라다이스 한 향수에서 88ml/236ml 및 단품/기획 구성만 달라진다. |
| `oliveyoung:118` | 스침 | 스침 헤어 우유 퍼퓸 50ml 기획 (+스크런치) / 단품 5종 택 1 | IDENTITY_CHANGING | KEEP_EXCLUDED | 헤어 우유 퍼퓸 5종 택1과 단품/기획 선택이 함께 있어 향수 정체성이 달라질 수 있다. |
| `oliveyoung:217` | 클린 | 클린 헤어&바디 퍼퓸 미스트 로즈올데이 88ml,236ml (단품/기획) | IDENTITY_PRESERVING | RETURN_TO_CANDIDATES | 로즈올데이 한 향수에서 88ml/236ml 및 단품/기획 구성만 달라진다. |

identity-preserving은 **2건**, identity-changing은 **3건**이다. identity-preserving 2건만 구매 후보로 복귀했다.

## 구매 후보 변화

구매 후보는 **826행에서 828행으로 2행 증가**했다. 새 복귀 상품은 클린 헤어&바디 퍼퓸 미스트 `파파야 파라다이스`와 `로즈올데이`다. 이 수치는 SKU 통합 전 판매상품 행 수다.

## 화해 TOP100 overlap

| 상태 | 변경 전 | 변경 후 | 변화 |
|---|---:|---:|---:|
| MATCH | 30 | 30 | +0 |
| NO_MATCH | 68 | 68 | +0 |
| MATCH_REVIEW | 2 | 2 | +0 |
| MATCH 비율 | 30.0% | 30.0% | +0.0%p |

이번 수정으로 새롭게 MATCH된 화해 상품은 **0건**이다. 복귀한 두 상품과 화해의 클린 상품(62위 퓨어솝, 88위 쿨코튼)은 브랜드만 같고 향수 정체성이 달라 연결하지 않았다.

## 검증

- 실행: `venv/Scripts/python.exe -B analyze_identity_preserving_mixed.py`.
- 이전 MIXED 집합이 정확히 5행이며 2/3으로 빠짐없이 분류되는지 검사했다.
- 기존 구매 후보 826행을 모두 보존하고 지정한 2행만 추가해 828행인지 검사했다.
- 화해 입력 100행과 1~100위 연속성, source_product_id 고유성을 검사했다.
- MATCH/NO_MATCH/MATCH_REVIEW 합계가 100이며 30/68/2인지 검사했다.
- 모든 MATCH와 MATCH_REVIEW가 갱신 후보의 실제 source/rank와 product_id를 참조하는지 검사했다.
- 기존 overlap 컬럼과 상태가 모두 그대로인지, 새 복귀 행이 약한 근거로 연결되지 않았는지 검사했다.
- 세 CSV round-trip과 입력·이전 결과 파일의 실행 전후 바이트 불변을 검사했다.

보호 입력 SHA-256:

- `korea_non_perfume_personal_fragrance_review.csv`: `e81bf425b096a221b014b02db43f0064dfb5c68bce594fe087313b27f224071b`
- `korea_personal_fragrance_purchase_candidates.csv`: `97b5bf6db8fc327db126957d0cfdbfd9e9bb5abdb56b08b9873c3c695d76b292`
- `hwahae_personal_fragrance_overlap.csv`: `ebdf037f10e320159477fe6d39a50d0a1dd156fb9528b7830d5708ba2d33f1c7`
- `hwahae_perfume_top100_raw.csv`: `7fc5930d5fb54d912de0c24bbb7ac989c1e20b9efa865929905ce656eadb65cc`
- `korea_personal_fragrance_scope_overlap.md`: `2849dbbee18237ba8dd9d4eef479e604496acdb3029edfdcc518a5ae32d35957`

## 남은 문제

- identity-changing 3행은 여러 향 선택이 포함되어 계속 제외한다.
- 이번 5행에는 추가 unresolved가 없다.
- 이전 Personal Fragrance 검토의 UNRESOLVED 6행, UNKNOWN 옵션 4행과 기존 MANUAL_CHECK는 이번 범위에서 손대지 않았다.
- 향수 SKU 통합과 외부 정체성 매칭은 다음 단계 전까지 보류한다.

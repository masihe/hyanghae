# 국내 판매 랭킹 REVIEW 2차 검토

1차 REVIEW 128건만 로컬 상품명·audit 근거·다른 로컬 판매행으로 재검토했다. 상품 페이지와 외부 API는 열지 않았다.
2차 판정은 정제 기준 검증용이다. 원본/1차 판정 수정, 행 삭제, SKU 통합, 농도·단위 보정은 하지 않았다.

## 결과

| 2차 판정 | musinsa | oliveyoung | lotte | 전체 |
|---|---:|---:|---:|---:|
| KEEP | 3 | 22 | 3 | 28 |
| EXCLUDE_NON_PERFUME | 3 | 7 | 0 | 10 |
| EXCLUDE_DISCOVERY | 0 | 0 | 0 | 0 |
| EXCLUDE_SCENT_OPTION | 6 | 24 | 0 | 30 |
| MANUAL_CHECK | 41 | 19 | 0 | 60 |
| 합계 | 53 | 72 | 3 | 128 |

자동 재판정 68건, MANUAL_CHECK 60건이다.

1차 확정 871건과 합치면 현재 전체 999건은 KEEP 790, EXCLUDE_NON_PERFUME 69, EXCLUDE_DISCOVERY 8, EXCLUDE_SCENT_OPTION 72, MANUAL_CHECK 60이다. 이는 행 기준이며 고유 향수 수가 아니다.

## 기존 REVIEW 사유별 변화

| 기존 cleaning_rule | 입력 | KEEP | 비향수 제외 | discovery 제외 | 향 선택 제외 | MANUAL_CHECK |
|---|---:|---:|---:|---:|---:|---:|
| concentration_unclear | 2 | 2 | 0 | 0 | 0 | 0 |
| identity_unclear | 14 | 0 | 0 | 0 | 0 | 14 |
| mixed_product_types | 6 | 0 | 0 | 0 | 0 | 6 |
| option_mixed | 41 | 18 | 5 | 0 | 17 | 1 |
| option_unknown | 30 | 1 | 5 | 0 | 13 | 11 |
| product_type_unconfirmed | 21 | 6 | 0 | 0 | 0 | 15 |
| unclear_use | 13 | 0 | 0 | 0 | 0 | 13 |
| unit_typo | 1 | 1 | 0 | 0 | 0 | 0 |

## 재판정 근거

- SIZE+PACKAGE 18건은 상품명에 하나의 향수와 농도가 유지되고 용량·단품/기획만 달라 KEEP했다.
- 여러 향과 용량/구성이 한 판매행에 함께 있는 17건, 단일 용량의 N종 향수 12건, KEYTH 교차 확인 1건은 EXCLUDE_SCENT_OPTION으로 이동했다.
- 헤어·바디·고체·이너 제품 10건은 옵션 세부사항과 무관하게 모든 주상품이 서비스 범위 밖이어서 EXCLUDE_NON_PERFUME으로 이동했다.
- 상품 유형이 생략된 6건은 다른 로컬 행에서 같은 상품의 퍼퓸/EDT 표현을 확인해 KEEP했다.
- 100m/40m 및 EXDP는 값을 보정하지 않았다. 해당 4개 판매행은 개별 향수명이 명확해 정제 상태만 KEEP하고 원문을 유지했다.
- 1차 REVIEW 중 EXCLUDE_DISCOVERY로 새로 이동한 상품은 0건이다. discovery 주상품 8건은 이미 1차에서 제외됐다.

## MANUAL_CHECK 유형

| 유형 | 건수 | 사람이 확인할 핵심 질문 |
|---|---:|---|
| identity_unclear | 14 | 정확한 향수명과 농도는 무엇이며, 한 상품 ID에 서로 다른 향 선택이 포함되는가? |
| mixed_product_types | 6 | 선택 가능한 모든 옵션과 각 옵션의 제품 유형·향수명을 확인하고, 판매순위를 개별 액상 향수에 귀속할 근거가 있는가? |
| option_mixed | 1 | 선택 가능한 모든 옵션과 각 옵션의 제품 유형·향수명을 확인하고, 판매순위를 개별 액상 향수에 귀속할 근거가 있는가? |
| option_unknown | 11 | 상세 옵션명이 향, 용량, 단품/기획 중 무엇이며 모든 옵션에서 동일한 향수 정체성이 유지되는가? |
| product_type_unconfirmed | 15 | 상품 유형과 사용 부위는 무엇이며 EDP/EDT/Parfum 등 일반 액상 향수인가? |
| unclear_use | 13 | 사용 부위가 피부인가, 공간/섬유인가? 제품 제형이 일반 액상 향수에 해당하는가? |

대표 사례:

- **oliveyoung:9 / KEEP** (ID `A000000176516`): 랑방 에끌라 드 아르페쥬 EDP 30ml/50ml (단품/기획) — 상품명에 하나의 향수명이 있고 선택지는 용량과 단품/기획 구성뿐이다. 농도와 단위 원문은 고치지 않는다.
- **oliveyoung:40 / KEEP** (ID `A000000245613`): [NEW] 나르시소 로드리게즈 포 허 퓨어 머스크 블랑 EDPI (30ml/50ml/기획) — 상품명에 하나의 향수명이 있고 선택지는 용량과 단품/기획 구성뿐이다. 농도와 단위 원문은 고치지 않는다.
- **oliveyoung:21 / EXCLUDE_NON_PERFUME** (ID `A000000241764`): [NEW] CK 캘빈클라인 헤어&바디 퍼퓸 미스트 100ml/236ml 6종 — 용량/구성/향 선택이 섞였지만 모든 주상품이 헤어·바디 향 제품이므로 서비스 범위 밖임은 명확하다.
- **musinsa:2 / EXCLUDE_SCENT_OPTION** (ID `5335796`): 912 엑스트레 드 퍼퓸 40ml (6종) EXT / 지속력, 발향력 강화 버전 — 한 용량의 향수 N종을 한 판매상품으로 제시하며 세트/다개입 표기가 없어 서로 다른 향 선택 상품으로 판정했다.
- **oliveyoung:160 / EXCLUDE_SCENT_OPTION** (ID `A000000207725`): [NEW/스크런치 증정 기획] KEYTH 키스 오드뚜왈렛 50ml 택 1 — 같은 KEYTH 50ml 상품이 무신사 270위에서 5종 택1로 확인되어 향 선택 상품으로 판정했다.
- **musinsa:189 / KEEP** (ID `6095042`): 아뜰리에페이 마이스킨벗베터 30ml — 같은 브랜드·근사 동일 상품명이 올리브영에서 퍼퓸 30ml로 확인된다. 철자 차이는 원문 그대로 둔다.
- **lotte:31 / KEEP** (ID `LE1208156089`): 베르두콜렉션 그랑크뤼 아쌈 오브 인디아 EDP 100m — 그랑크뤼 아쌈 오브 인디아 EDP라는 향수 정체성은 명확하다. 100m은 보정하지 않고 원문으로 유지한다.
- **lotte:34 / KEEP** (ID `PD63589929`): [만세라] 인텐스 세드라 부아제 EXDP 120ml (바이알 3종) — 인텐스 세드라 부아제라는 향수 정체성은 두 로컬 행에서 동일하다. EXDP 의미는 추정하지 않고 농도 원문을 유지한다.
- **oliveyoung:12 / MANUAL_CHECK** (ID `A000000237852`): [원필PICK] 애프터블로우 솔리드/오 드 퍼퓸 20종 택1 (단품/기획) — 일반 액상 향수와 다른 제품/옵션의 대응 관계가 상품명만으로 분리되지 않는다.
- **musinsa:31 / MANUAL_CHECK** (ID `4469595`): 마이 핸디 롤온 퍼퓸 (택1) — 택1/N종/묶음 표기는 있으나 향·용량·구성 중 무엇을 선택하는지 확정할 수 없다.
- **musinsa:57 / MANUAL_CHECK** (ID `6257933`): 오 드 퍼퓸 30mL — 상품명에 개별 향수명 또는 판매 옵션별 향수명이 부족하다.
- **musinsa:67 / MANUAL_CHECK** (ID `6282382`): 무드 퍼퓸 스프레이 300ml — 퍼퓸 스프레이·멀티 프래그런스·미스트만으로 인체용 일반 향수인지 공간/섬유용인지 구별할 수 없다.
- **musinsa:22 / MANUAL_CHECK** (ID `6210284`): 이노센트 타임 50ml — 제품명과 용량만으로 일반 액상 향수임을 확인할 수 없고 같은 상품의 로컬 보강 근거도 없다.

## 검증

- 실행: `venv/Scripts/python.exe -B review_korea_rankings.py`.
- 입력 REVIEW=128, 자동 재판정+MANUAL_CHECK=128, 판매처 53/72/3을 검사한다.
- 결과 128행에 1차 CSV의 모든 값과 순서를 보존하고, manual queue의 URL·이유·질문을 검사한다.
- 입력 네 파일은 고정 SHA256과 처리 전후 바이트를 확인한다.

- `korea_perfume_ranking_raw.csv` SHA256: `820e2a3ab0bea1076a21a8b9e98e037a6c5d0b5fc87eb1dfa709ab00aac51576`
- `korea_perfume_ranking_audit.csv` SHA256: `b6ba913938b9fb65fd68759a79308c2d3c2c6232d321b102b27231d0e8c07e15`
- `korea_perfume_ranking_first_pass.csv` SHA256: `0775e32f757b42f832a5ac858e7b0aecc020ba5e40f5a0ae8ea33b306dbe10fd`
- `korea_perfume_ranking_first_pass.md` SHA256: `57931ca4021ac66c7df82452661c41cdce19217365c4bfd913ad54c629450db9`

# External Scent Knowledge Validation

## 결과 요약

### 결론

- 검증 Note 수: **30**
- 신규 SAME_CONCEPT: **5**
- FAMILY: **10**
- RELATED: **2**
- UNRESOLVED: **13**
- SOURCE_UNAVAILABLE: **0**
- Stage 19 → 20 occurrence-weighted coverage: **59.63% → 62.06% (+2.43%p)**
- 외부 공식 Source는 strict mapping 5개와 material/category 관계 12개를 보강해 실제로 도움이 됐다. 특히 IFF가 가장 넓은 범위를 지원했고, dsm-firmenich와 PubChem은 각각 Muguet와 Ambroxan의 결정적 명칭 근거를 제공했다.

## 핵심 수치

| stage | strict_matched_note_count | vocabulary_coverage | occurrence_weighted_coverage | perfume_level_coverage | matched_occurrence_count | total_note_types | total_occurrence_count | total_perfumes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Stage 17 | 159 | 6.30% | 49.70% | 92.31% | 545863 | 2523 | 1098223 | 131930 |
| Stage 18 | 165 | 6.54% | 52.61% | 94.27% | 577745 | 2523 | 1098223 | 131930 |
| Stage 19 | 180 | 7.13% | 59.63% | 95.57% | 654910 | 2523 | 1098223 | 131930 |
| Stage 20 | 185 | 7.33% | 62.06% | 95.82% | 681598 | 2523 | 1098223 | 131930 |

## 상세

### 1. 분석 목적

Stage 19에서 IFRA만으로 해결하지 못한 고빈도 Note를 허용된 공식 업계 자료로 검증하고, strict mapping과 비동일 관계를 분리해 향 지식 DB의 핵심 빈틈을 보완했다. Semantic Bridge나 embedding은 구현하지 않았다.

### 2. 검증 대상 선정 기준

`19_high_frequency_unresolved_notes.csv`에서 Stage 19 relation이 RELATED 또는 UNRESOLVED인 항목을 occurrence_count 내림차순으로 정렬해 상위 30개를 선택했다. 요청된 대표 10개는 모두 실제 상위 30개에 포함됐다.

### 3. 추가한 공식 Source

- IFRA 로컬 PDF/처리 CSV: Mint material family와 기존 descriptor 관계 재확인
- Givaudan 공식 Natural Ingredients: Neroli/Orange Blossom의 material 차이, Virginia cedarwood 확인
- IFF Fragrance Ingredients 및 LMR Compendium: Leather category, Cashmeran, natural material 및 marine/mossy 관계 확인
- dsm-firmenich Perfumery & Beauty Ingredients: Muguet–Lily-of-the-Valley 직접 명칭 관계와 Pink Pepper extract 확인
- PubChem: Ambroxan–Ambroxide chemical synonym만 확인
- 검색 snippet, 비공식 사이트, 브랜드 마케팅 설명은 Evidence로 저장하지 않았다.

### 4. Note Type 분석

| note_type | count |
| --- | --- |
| CATEGORY_NOTE | 1 |
| NATURAL_MATERIAL_NOTE | 10 |
| RECONSTRUCTED_NOTE | 2 |
| OLFACTIVE_EFFECT_NOTE | 2 |
| UNRESOLVED_TYPE | 15 |

Natural material 계열이 10개였지만 특정 oil/extract와 Note를 동일시할 수 없어 FAMILY가 됐다. 15개는 공식 근거 부족 또는 허용 taxonomy에 synthetic-ingredient type이 없어 UNRESOLVED_TYPE으로 남았다.

### 5. Relation 판정 결과

| relation_type | count |
| --- | --- |
| SAME_CONCEPT | 5 |
| FAMILY | 10 |
| RELATED | 2 |
| UNRESOLVED | 13 |
| SOURCE_UNAVAILABLE | 0 |

### 6. 신규 SAME_CONCEPT

| note | candidate_term | note_type | confidence | evidence_sources |
| --- | --- | --- | --- | --- |
| Leather | Leather | OLFACTIVE_EFFECT_NOTE | HIGH | IFF |
| Lily-of-the-Valley | Muguet | RECONSTRUCTED_NOTE | HIGH | dsm-firmenich |
| Lily of the Valley | Muguet | RECONSTRUCTED_NOTE | HIGH | dsm-firmenich |
| Ambroxan | Ambroxide | UNRESOLVED_TYPE | HIGH | PubChem |
| Cashmeran | Cashmeran | UNRESOLVED_TYPE | HIGH | IFF |

이 5개만 Stage 20 strict coverage에 추가했다. FAMILY/RELATED는 제외했다.

### 7. 주요 FAMILY / RELATED 관계

| note | candidate_term | parent_term | relation_type | note_type |
| --- | --- | --- | --- | --- |
| Mandarin Orange | Mandarin Oil Green Italy | Mandarin material family | FAMILY | NATURAL_MATERIAL_NOTE |
| Orange Blossom | Orange Flower Absolute \| Neroli Oil | Bitter orange flower material family | FAMILY | NATURAL_MATERIAL_NOTE |
| Pink Pepper | Pink Pepper CO2 | Pink pepper material family | FAMILY | NATURAL_MATERIAL_NOTE |
| Black Pepper | Black Pepper Oil Madagascar | Black pepper material family | FAMILY | NATURAL_MATERIAL_NOTE |
| Mint | Mentha material forms | Mint material family | FAMILY | NATURAL_MATERIAL_NOTE |
| Moss | Mossy | Mossy | RELATED | OLFACTIVE_EFFECT_NOTE |
| Virginia Cedar | Cedarwood Virginia Oil USA | Virginia cedarwood material family | FAMILY | NATURAL_MATERIAL_NOTE |
| Sea Notes | Marine | Marine | RELATED | CATEGORY_NOTE |
| Orris Root | Orris Natural | Orris rhizome material family | FAMILY | NATURAL_MATERIAL_NOTE |
| Bulgarian Rose | Rose Oil Bulgaria | Bulgarian Rosa damascena material family | FAMILY | NATURAL_MATERIAL_NOTE |
| Turkish Rose | Rose Oil Isparta | Turkish Rosa damascena material family | FAMILY | NATURAL_MATERIAL_NOTE |
| Bitter Orange | Orange Oil CP Bitter Egypt | Bitter orange material family | FAMILY | NATURAL_MATERIAL_NOTE |

Orange Blossom과 Neroli는 extraction/material 차이가 공식적으로 확인돼 SAME_CONCEPT로 합치지 않았다. Mint/Peppermint/Spearmint, Moss/Oakmoss, natural note/oil 관계도 동일한 보수 원칙을 적용했다.

### 8. Coverage 변화

- Strict matched Note: **180 → 185**
- Vocabulary coverage: **7.13% → 7.33%**
- Occurrence-weighted coverage: **59.63% → 62.06%**
- Perfume-level coverage: **95.57% → 95.82% (+0.25%p)**
- Top 100 vocabulary coverage: **68.00% → 73.00%**
- Top 200 vocabulary coverage: **53.50% → 56.00%**

### 9. Coverage 기여도가 높은 Mapping

| term | canonical_term | occurrence_count | coverage_contribution_percentage_point | cumulative_contribution |
| --- | --- | --- | --- | --- |
| Leather | Leather | 10754 | 0.9792182462031847 | 0.9792182462031847 |
| Lily-of-the-Valley | Muguet | 7366 | 0.6707198811170408 | 1.6499381273202256 |
| Lily of the Valley | Muguet | 3118 | 0.2839131943148159 | 1.9338513216350415 |
| Ambroxan | Ambroxide | 3062 | 0.2788140477844664 | 2.2126653694195078 |
| Cashmeran | Cashmeran | 2388 | 0.21744217704418867 | 2.4301075464636965 |

### 10. Source별 활용도

| source_group | evidence_count | supported_term_count | same_concept_count | family_count | related_count |
| --- | --- | --- | --- | --- | --- |
| IFRA | 16 | 16 | 0 | 1 | 2 |
| Givaudan | 2 | 2 | 0 | 2 | 0 |
| IFF | 25 | 25 | 2 | 8 | 2 |
| dsm-firmenich | 3 | 3 | 2 | 1 | 0 |
| PubChem | 1 | 1 | 1 | 0 | 0 |
| Multiple Sources | 34 | 17 | 0 | 2 | 2 |

`IFF`가 final relation을 지원한 범위가 가장 넓었다. dsm-firmenich는 두 Lily 표기의 SAME_CONCEPT를, PubChem은 Ambroxan의 화학 동의어를 좁고 결정적으로 확인했다. Multiple Sources는 같은 term에 둘 이상의 공식 기관 근거가 있는 경우다.

### 11. 아직 남은 고빈도 Gap

| note | perfume_count | occurrence_count | relation_type | note_type |
| --- | --- | --- | --- | --- |
| Freesia | 5683 | 5696 | UNRESOLVED | UNRESOLVED_TYPE |
| Moss | 4302 | 4310 | RELATED | OLFACTIVE_EFFECT_NOTE |
| Woodsy Notes | 3240 | 3250 | UNRESOLVED | UNRESOLVED_TYPE |
| Orchid | 2814 | 2824 | UNRESOLVED | UNRESOLVED_TYPE |
| Cashmere Wood | 2688 | 2691 | UNRESOLVED | UNRESOLVED_TYPE |
| White Flowers | 2317 | 2323 | UNRESOLVED | UNRESOLVED_TYPE |
| Sea Notes | 2183 | 2193 | RELATED | CATEGORY_NOTE |
| Praline | 2164 | 2171 | UNRESOLVED | UNRESOLVED_TYPE |
| Sugar | 2094 | 2116 | UNRESOLVED | UNRESOLVED_TYPE |
| Vanille | 2033 | 2037 | UNRESOLVED | UNRESOLVED_TYPE |
| Fig | 1810 | 1846 | UNRESOLVED | UNRESOLVED_TYPE |
| Lotus | 1771 | 1781 | UNRESOLVED | UNRESOLVED_TYPE |
| Amberwood | 1757 | 1761 | UNRESOLVED | UNRESOLVED_TYPE |

### 12. IFRA만으로 해결되지 않았던 이유

- Fragrantica Note가 특정 ingredient가 아니라 넓은 natural-material family인 경우가 많았다.
- Leather, Sea Notes, Moss처럼 olfactive category/effect와 ingredient identity가 다른 항목이 있었다.
- Lily-of-the-Valley처럼 공식 업계의 reconstructed terminology가 IFRA principal-name strict match와 다른 층위에 있었다.
- Ambroxan/Cashmeran처럼 synthetic ingredient name은 이번 Note Type 선택지에 별도 유형이 없었다.

### 13. 이번 분석에서 검증된 것

- 실제 공식 페이지를 근거로 5개 HIGH SAME_CONCEPT를 strict mapping에 추가할 수 있다.
- 10개 natural-material Note는 특정 원료와 동일시하지 않고 FAMILY로 구조화할 수 있다.
- Orange Blossom/Neroli 및 broad note/specific extract를 분리해야 coverage가 과대평가되지 않는다.

### 14. 아직 검증되지 않은 것

- Freesia, Orchid, Lotus 등 꽃 Note의 natural/reconstructed 경계
- Cashmere Wood, Amberwood, Suede 등 상업적·효과 중심 표현의 공식 taxonomy
- Vanille의 공식 alternative naming과 Fig의 fruit/leaf/material 구분
- 추천 Query를 descriptor로 변환하는 Semantic Bridge 성능

### 15. Semantic Bridge 진행 여부 판단

**추가 일반 소스를 넓게 수집하기보다 Semantic Bridge Pilot으로 이동한다. Stage 20은 Leather, 두 Lily-of-the-Valley 표기, Ambroxan, Cashmeran을 strict mapping으로 확정했고, Mandarin Orange·Orange Blossom·Pink/Black Pepper·Mint·지역 Rose·Orris·Bitter Orange는 과대 동일시 없이 FAMILY 구조로 확보했다. 남은 Freesia, Woodsy Notes, Orchid, Cashmere Wood 등은 단순 자료 누락만이 아니라 재구성 향·카테고리·마케팅형 Note 경계 문제이므로, FAMILY/RELATED를 특징으로 활용하는 Pilot이 다음 검증에 더 직접적이다. 다만 남은 고빈도 Gap은 별도 수동 검토 백로그로 유지한다.**

이 판단은 임의 coverage threshold가 아니라 occurrence-weighted 및 Top 100/200 변화, 해결된 고빈도 Note, FAMILY/RELATED로 확보된 구조, 남은 gap의 성격을 함께 고려했다.

### 16. 다음 단계

1. Stage 20의 HIGH SAME_CONCEPT 5개만 strict lookup에 반영한다.
2. FAMILY/RELATED는 정답 label이 아닌 Semantic Bridge feature로 사용하는 Pilot을 설계한다.
3. Freesia, Woodsy Notes, Orchid, Cashmere Wood를 우선 수동 검토 백로그로 유지한다.
4. synthetic ingredient를 명시할 별도 Note Type 추가 여부를 다음 dictionary schema revision에서 검토한다.

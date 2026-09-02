# Scent Term Dictionary Expansion

## 결과 요약

### 결론

- 검증 Note 수: **159**
- SAME_CONCEPT: **15**
- FAMILY: **37**
- RELATED: **5**
- UNRESOLVED: **102**
- Stage 18 → Stage 19 occurrence-weighted coverage: **52.61% → 59.63% (+7.03%p)**
- Stage 18 → Stage 19 perfume-level coverage: **94.27% → 95.57% (+1.30%p)**
- 향 용어 사전 확장은 공식 근거가 있는 15개 신규 SAME_CONCEPT에 한해 Strict Coverage를 높였다.

## 핵심 수치

| stage | strict_matched_note_count | vocabulary_coverage | occurrence_weighted_coverage | perfume_level_coverage | matched_occurrence_count | total_note_types | total_occurrence_count | total_perfumes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Stage 17 | 159 | 0.06302021403091558 | 0.4970420397314571 | 0.923110740544228 | 545863 | 2523 | 1098223 | 131930 |
| Stage 18 | 165 | 0.06539833531510107 | 0.5260725736029932 | 0.9427196240430531 | 577745 | 2523 | 1098223 | 131930 |
| Stage 19 | 180 | 0.0713436385255648 | 0.5963360811055678 | 0.9557492609717274 | 654910 | 2523 | 1098223 | 131930 |

## 상세

### 1. 분석 목적

Stage 17의 고빈도 unmatched Note를 공식 향 지식으로 검증해 v0.2 사전을 만들고, 추가 사전 확장과 Semantic Bridge 중 다음 단계를 판단했다.

### 2. 검증 대상 선정 기준

- Stage 17 strict match와 Stage 18 P0 8개를 제외했다.
- perfume_count 내림차순으로 정렬한 뒤 occurrence 누적 80%에 필요한 159개와 최대 200개 중 작은 **159개**를 선택했다.
- 선택된 대상은 제외 후 unmatched occurrence의 **80.01%**를 설명한다.

### 3. 사용한 공식 자료

- IFRA Fragrance Ingredient Glossary April 2020 로컬 PDF 및 그 가공 CSV
- Givaudan 공식 Natural Ingredients 페이지
- IFF 공식 Fragrance Ingredients Compendium
- PubChem은 화학적 동일성 검증에만 허용했으며, 이번 신규 판정에는 사용할 필요가 없었다.
- 검색 snippet, Wikipedia, 커뮤니티, 블로그, 판매 사이트는 Evidence로 사용하지 않았다.

### 4. Relation 판정 결과

| relation_type | count | share |
| --- | --- | --- |
| UNRESOLVED | 102 | 0.6415094339622641 |
| FAMILY | 37 | 0.23270440251572327 |
| SAME_CONCEPT | 15 | 0.09433962264150944 |
| RELATED | 5 | 0.031446540880503145 |

Confidence 분포:

| confidence | count | share |
| --- | --- | --- |
| LOW | 102 | 0.6415094339622641 |
| MEDIUM | 42 | 0.2641509433962264 |
| HIGH | 15 | 0.09433962264150944 |

### 5. 주요 SAME_CONCEPT

| note | candidate_term | confidence | decision_reason |
| --- | --- | --- | --- |
| Musk | Musk-Like | HIGH | OFFICIAL_CATEGORY_EQUIVALENCE: official evidence supports a canonical term-level equivalence. |
| Agarwood (Oud) | Agarwood | HIGH | OFFICIAL_PAIRED_NAMING: official evidence supports a canonical term-level equivalence. |
| Aldehydes | Aldehydic | HIGH | OFFICIAL_GRAMMATICAL_EQUIVALENCE: official evidence supports a canonical term-level equivalence. |
| Spices | Spicy | HIGH | OFFICIAL_CATEGORY_EQUIVALENCE: official evidence supports a canonical term-level equivalence. |
| Fruity Notes | Fruity | HIGH | NOTES_SUFFIX_DESCRIPTOR: official evidence supports a canonical term-level equivalence. |
| Cloves | Clove | HIGH | PLURAL_DESCRIPTOR: official evidence supports a canonical term-level equivalence. |
| Spicy Notes | Spicy | HIGH | NOTES_SUFFIX_DESCRIPTOR: official evidence supports a canonical term-level equivalence. |
| Powdery Notes | Powdery | HIGH | NOTES_SUFFIX_DESCRIPTOR: official evidence supports a canonical term-level equivalence. |
| Smoke | Smoky | HIGH | OFFICIAL_GRAMMATICAL_EQUIVALENCE: official evidence supports a canonical term-level equivalence. |
| Sweet Notes | Sweet | HIGH | NOTES_SUFFIX_DESCRIPTOR: official evidence supports a canonical term-level equivalence. |
| Ozonic notes | Ozonic | HIGH | NOTES_SUFFIX_DESCRIPTOR: official evidence supports a canonical term-level equivalence. |
| Watery Notes | Watery | HIGH | NOTES_SUFFIX_DESCRIPTOR: official evidence supports a canonical term-level equivalence. |
| Herbal Notes | Herbal | HIGH | NOTES_SUFFIX_DESCRIPTOR: official evidence supports a canonical term-level equivalence. |
| Marine notes | Marine | HIGH | NOTES_SUFFIX_DESCRIPTOR: official evidence supports a canonical term-level equivalence. |
| Dried Fruits | Dried-Fruit | HIGH | PLURAL_DESCRIPTOR: official evidence supports a canonical term-level equivalence. |

### 6. FAMILY / RELATED 사례

FAMILY는 IFRA의 실제 oil/absolute/extract 등과의 관계만 의미하고 note concept 동일성을 뜻하지 않는다. RELATED도 descriptor 근접성만 기록한다. 두 유형 모두 Strict Coverage에서 제외했다.

### 7. Coverage 변화

- Strict matched Note: 165 → 180
- Vocabulary: 6.54% → 7.13%
- Occurrence-weighted: 52.61% → 59.63%
- Perfume-level: 94.27% → 95.57%
- Top 100 vocabulary coverage: 68.00%
- Top 200 vocabulary coverage: 53.50%

### 8. Coverage 개선 기여도가 높은 Mapping

| term | canonical_term | occurrence_count | coverage_contribution_percentage_point | cumulative_contribution |
| --- | --- | --- | --- | --- |
| Musk | Musk-Like | 49571 | 4.513746297427754 | 4.513746297427754 |
| Agarwood (Oud) | Agarwood | 6134 | 0.5585386574493523 | 5.072284954877106 |
| Aldehydes | Aldehydic | 3024 | 0.2753539126388721 | 5.347638867515978 |
| Spices | Spicy | 2899 | 0.2639718891336277 | 5.611610756649606 |
| Fruity Notes | Fruity | 2493 | 0.22700307678859394 | 5.8386138334382 |
| Cloves | Clove | 2390 | 0.2176242894202726 | 6.056238122858472 |
| Spicy Notes | Spicy | 2240 | 0.2039658612139793 | 6.260203984072452 |
| Powdery Notes | Powdery | 1604 | 0.1460541256192959 | 6.4062581096917475 |
| Smoke | Smoky | 1236 | 0.11254544841985643 | 6.518803558111604 |
| Sweet Notes | Sweet | 1225 | 0.11154383035139492 | 6.630347388462999 |

### 9. 아직 해결되지 않은 고빈도 Note

| note | perfume_count | occurrence_count | relation_type |
| --- | --- | --- | --- |
| Mandarin Orange | 11646 | 11652 | UNRESOLVED |
| Orange Blossom | 11479 | 11545 | UNRESOLVED |
| Leather | 10626 | 10754 | RELATED |
| Pink Pepper | 10387 | 10395 | UNRESOLVED |
| Lily-of-the-Valley | 7339 | 7366 | UNRESOLVED |
| Freesia | 5683 | 5696 | UNRESOLVED |
| Black Pepper | 4795 | 4807 | UNRESOLVED |
| Mint | 4605 | 4627 | UNRESOLVED |
| Moss | 4302 | 4310 | RELATED |
| Woodsy Notes | 3240 | 3250 | UNRESOLVED |

### 10. Source별 효용

| source_group | evidence_count | supported_term_count | same_concept_support_count | family_support_count | resolved_or_candidate_count |
| --- | --- | --- | --- | --- | --- |
| IFRA only | 156 | 156 | 13 | 36 | 54 |
| Givaudan | 2 | 2 | 1 | 1 | 2 |
| IFF | 1 | 1 | 1 | 0 | 1 |
| PubChem | 0 | 0 | 0 | 0 | 0 |
| Multiple Sources | 6 | 3 | 2 | 1 | 3 |

IFRA는 모든 신규 대상의 1차 감사 기준과 descriptor/material 후보를 제공했다. Givaudan과 IFF는 일부 핵심 용어의 공식 업계 용례를 보강했다. PubChem은 이번 대상에서 화학적 identity가 필요한 안전한 SAME_CONCEPT 사례가 없어 사용하지 않았다.

### 11. 이번 분석에서 검증된 것

- 표기·문법 차이와 공식 category 문구가 함께 있는 15개 Note는 HIGH SAME_CONCEPT로 자동 활용 가능하다.
- 원료 형태 일치는 Note concept 동일성이 아니며 FAMILY로 분리해야 한다.
- 공식 근거가 없는 고빈도 Note를 억지로 canonicalize하지 않아도 Coverage 증가분을 정직하게 측정할 수 있다.

### 12. 아직 검증되지 않은 것

- 향수 데이터셋의 복합 note concept와 IFRA descriptor 사이의 광범위한 의미 대응
- Orange Blossom/Neroli, Mint/Peppermint, Moss/Oakmoss 같은 개념-원료 관계
- 브랜드·지역·품종이 붙은 원료형 note의 표준 canonicalization

### 13. Semantic Bridge 준비 판단

**Stage 19가 occurrence-weighted coverage를 7.03%p 높였지만 Top 100/200 vocabulary coverage가 각각 68.00%/53.50%이고, Leather·Orange Blossom·Pink Pepper·Freesia처럼 고빈도 핵심 Note가 남아 있다. 따라서 즉시 전면 Semantic Bridge로 이동하기보다 이 Note들을 다루는 보완 Knowledge Source를 한 차례 더 확장한 뒤 Semantic Bridge 파일럿으로 이동한다. FAMILY/RELATED는 Strict Coverage에 넣지 않는다.**

판단은 vocabulary만이 아니라 occurrence-weighted coverage, Top 100/200 coverage, 고빈도 unresolved의 사업 중요도를 함께 반영했다.

### 14. 다음 단계

1. 고빈도 unresolved에 대해 공식 원료 카탈로그/표준 taxonomy를 추가 검증한다.
2. 다음 확장에서도 HIGH SAME_CONCEPT만 strict mapping으로 승격한다.
3. 별도 Semantic Bridge 파일럿에서는 FAMILY/RELATED를 특징으로 활용하되 정답 label로 간주하지 않는다.

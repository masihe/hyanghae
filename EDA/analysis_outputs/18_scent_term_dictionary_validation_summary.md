# Scent Term Dictionary Validation

## 결과 요약

### 결론

P0 8개 공식자료 검증 결과:

- SAME_CONCEPT: 6개
- FAMILY: 2개
- RELATED: 0개
- UNRESOLVED: 0개

확정된 HIGH-confidence SAME_CONCEPT 6개만 Stage 18 strict mapping에 추가했다. FAMILY인 White Musk와 Cedar는 Coverage에 포함하지 않았다.

## 상세

### 1. 분석 목적

17번의 고빈도 unmatched / alias 후보 중 P0 8개를 IFRA, Givaudan, IFF 공식 자료로만 검증하고 canonical scent term과 ingredient family를 분리한 사전 v0.1을 구축했다.

### 2. 검증 대상

Woody Notes, Green Notes, Floral Notes, Citruses, Black Currant, White Musk, Oud, Cedar

### 3. 사용한 공식 Source

- IFRA Fragrance Ingredient Glossary, April 2020: `data/external/ifra/raw/ifra-fragrance-ingredient-glossary-april-2020.pdf`
- Givaudan Agarwood Oil Thailand: https://www.givaudan.com/fragrance-beauty/fragrance-ingredients-business/natural-ingredients/agarwood-oil-thailand
- Givaudan Cedarwood Virginia Oil USA: https://www.givaudan.com/fragrance-beauty/fragrance-ingredients-business/natural-ingredients/cedarwood-virginia-oil-usa
- IFF Fragrance Ingredients Compendium: https://www.iff.com/scent/ingredients-compendium/
- IFF Damascone Delta: https://www.iff.com/scent/ingredients-compendium/damascone-delta/
- IFF LMR Compendium: https://www.iff.com/scent/lmr-compendium/
- IFF Edenolide: https://www.iff.com/scent/ingredients-compendium/edenolide/
- IFF Cedarwood Oil Extra: https://www.iff.com/scent/ingredients-compendium/cedarwood-oil-extra/

지정 URL 7개는 2026-09-01에 모두 접근 가능했다. 검색 snippet이나 대체 출처는 사용하지 않았다.

### 4. 용어별 판정 결과

- **Woody Notes -> Woody**: `SAME_CONCEPT` / `HIGH` - IFRA itself defines Woody using the phrase woody notes, and IFF uses Woody as an olfactive family.
- **Green Notes -> Green**: `SAME_CONCEPT` / `HIGH` - IFRA defines Green as a broad descriptor and explicitly refers to green notes.
- **Floral Notes -> Floral**: `SAME_CONCEPT` / `HIGH` - IFRA explicitly defines floral notes as belonging to the floral family; IFF uses Floral as an olfactive family.
- **Citruses -> Citrus**: `SAME_CONCEPT` / `HIGH` - The P0 plural label and IFRA's Citrus-notes category refer to the same citrus-family scent category.
- **Black Currant -> Blackcurrant**: `SAME_CONCEPT` / `HIGH` - This is an orthographic canonicalization; IFF explicitly pairs Blackcurrant with cassis, and IFRA links Cassis materials to Blackcurrant descriptors.
- **White Musk -> Musk-Like**: `FAMILY` / `MEDIUM` - IFF supports white musk as a specific soft/powdery musk profile, while IFRA Musk-Like covers a wider set of materials and facets.
- **Oud -> Agarwood**: `SAME_CONCEPT` / `HIGH` - Givaudan uses oud in the official Agarwood Oil material context; IFRA shows that Agarwood maps to multiple ingredient variants, so only term-level equivalence is confirmed.
- **Cedar -> Cedarwood**: `FAMILY` / `MEDIUM` - Official sources document cedarwood materials from Juniperus, Cupressus and Cedrus with different CAS/species; collapsing Cedar to one ingredient or full synonym is unsafe.

### 5. SAME_CONCEPT 결과

- Woody Notes -> Woody
- Green Notes -> Green
- Floral Notes -> Floral
- Citruses -> Citrus
- Black Currant -> Blackcurrant
- Oud -> Agarwood

이는 향 용어 canonicalization이며 특정 ingredient 하나와의 동일성을 뜻하지 않는다.

### 6. FAMILY 결과

- White Musk -> Musk-Like: IFF supports white musk as a specific soft/powdery musk profile, while IFRA Musk-Like covers a wider set of materials and facets.
- Cedar -> Cedarwood: Official sources document cedarwood materials from Juniperus, Cupressus and Cedrus with different CAS/species; collapsing Cedar to one ingredient or full synonym is unsafe.

White Musk는 IFRA Musk-Like 전체보다 구체적인 profile로, Cedar는 여러 식물 종과 CAS의 Cedarwood material을 포괄하는 상위 note concept로 유지했다.

### 7. RELATED / UNRESOLVED 결과

이번 P0에서는 RELATED와 UNRESOLVED가 없었다. 이는 모든 후보를 강제로 연결한 결과가 아니라, 6개는 공식 정의/직접 표현이 충분했고 나머지 2개는 SAME_CONCEPT로 올리지 않고 FAMILY로 보존한 결과다.

### 8. Coverage 변화

- Strict matched Note: 159 -> 165 (+6)
- Vocabulary coverage: 6.30% -> 6.54% (+0.24 percentage points)
- Occurrence-weighted coverage: 49.70% -> 52.61% (+2.90 percentage points)
- Perfume-level coverage: 92.31% -> 94.27% (+1.96 percentage points)

Coverage는 판정 이후에 계산했으며 FAMILY / RELATED는 strict에 포함하지 않았다.

### 9. 향 용어 사전 구조

`scent_term_dictionary_v0.1.csv`는 term, canonical term, relation, parent, IFRA mapping, confidence와 version을 보존한다. `scent_term_evidence_v0.1.csv`는 각 판정을 공식 Source URL과 Evidence 요약으로 추적한다.

### 10. 이번 분석에서 검증된 것

- category label의 표현 차이와 canonical form
- Blackcurrant / Cassis의 공식 향 표현 관계
- Oud / Agarwood의 향수 용어 관계와 복수 ingredient family의 분리
- White Musk와 Cedar를 broader class/material family와 구분해야 한다는 점

### 11. 아직 검증되지 않은 것

- P0 이외 unmatched Note
- 각 canonical scent concept를 모든 실제 ingredient에 연결하는 완전한 ontology
- 향 강도, 배합 비율, 추천 ranking score
- 자연어 semantic bridge

### 12. 다음 단계

1. MEDIUM-confidence FAMILY 두 건을 향료 전문가가 검토한다.
2. 다음 고빈도 unmatched 묶음을 같은 공식 Source 제한으로 확장한다.
3. 검증된 SAME_CONCEPT만 versioned dictionary에 추가하고 Coverage와 추천 평가는 분리한다.

# Fragrantica Note Canonicalization Audit

## 결과 요약

- 원래 Note 수: **2,523**
- Canonical Note 수: **2,492**
- SAME_CONCEPT로 통합된 raw Note 수: **48**
- SAME_CONCEPT cluster 수: **30**
- REVIEW 후보 수: **7**
- 가장 중요한 결론: Fragrantica 내부에는 확실한 중복 표현이 존재하지만 전체 vocabulary의 작은 일부다. v0.3의 검증된 alias와 명확한 표기/철자/문법 차이만 통합하고, Vanilla/Vanille처럼 기존 근거가 부족한 언어 변형은 REVIEW로 남겼다.

## 상세

### 1. 분석 목적

Fragrantica Note Vocabulary 내부에서 같은 향 개념이 표기, 철자, 문법 또는 이미 검증된 alias 때문에 여러 raw Note로 저장됐는지 확인하고, 추천/검색에서 재사용할 최소 canonical lookup을 만들었다. 새로운 향 지식이나 Coverage mapping은 추가하지 않았다.

### 2. 후보 탐색 방식

2,523개 전체 Note에 casefold, 공백/hyphen/punctuation 제거, note/notes 접미사 제거, 보수적 singular/plural key를 적용했다. 추가로 정규화 문자열 길이 차이 2 이하이고 SequenceMatcher 0.94 이상인 pair를 후보로 만들었다. 문자열 유사도는 후보 생성에만 사용했고 최종 판정은 명시적 rule/decision table로 제한했다.

### 3. 기존 Evidence 재사용

- analysis_outputs/17_fragrantica_note_vocabulary.csv
- analysis_outputs/17_note_ifra_matching.csv
- data/scent_knowledge/scent_term_dictionary_v0.3.csv
- data/scent_knowledge/scent_term_evidence_v0.3.csv
- analysis_outputs/20_external_note_validation_decisions.csv

v0.3의 HIGH SAME_CONCEPT를 그대로 우선 적용했다. perfumes.csv/jsonl, 외부 웹, LLM, embedding은 사용하지 않았다.

### 4. SAME_CONCEPT 주요 사례

- Musk → Musk-Like (perfume_count 49,244)
- Woody Notes → Woody (perfume_count 8,278)
- Lily-of-the-Valley → Muguet (perfume_count 7,339)
- Agarwood (Oud) → Agarwood (perfume_count 5,939)
- Black Currant → Blackcurrant (perfume_count 5,560)
- Citruses → Citrus (perfume_count 4,982)
- Green Notes → Green (perfume_count 4,529)
- Floral Notes → Floral (perfume_count 4,436)
- Oud → Agarwood (perfume_count 3,780)
- Lily of the Valley → Muguet (perfume_count 3,105)

Lily-of-the-Valley와 Lily of the Valley는 기존 dsm-firmenich evidence에 따라 Muguet로, Black Currant는 기존 v0.3 canonical term인 Blackcurrant로 통합했다. Oakmoss/oak moss, Ylang-Ylang/Ylang Ylang 같은 내부 표기 차이는 기존 raw label 중 명확한 대표 표기로 통합했다.

### 5. REVIEW / NOT_SAME 주요 사례

- Vanille: REVIEW — Vanilla/Vanille is a plausible language variant, but existing v0.3 evidence explicitly left Vanille unresolved.
- Californian Orange: REVIEW — California/Californian wording is plausible but is not a pure spelling rule.
- Virginian Cedar: REVIEW — Virginia/Virginian wording is plausible but existing evidence does not confirm identity.
- Woodsy Notes: REVIEW — Existing v0.3 evidence explicitly did not equate Woodsy Notes with Woody.
- White Wood: REVIEW — White Wood/White Woods may be grammatical variants, but existing evidence is unresolved.
- Cep: REVIEW — Cep/Cepes may be a language/plural variant, but existing evidence is absent.
- Gaiac Wood: REVIEW — Gaiac/Guaiac may be a spelling or language variant, but existing project evidence does not explicitly confirm alias identity.

- Peppermint: NOT_SAME — Mint is broader and existing v0.3 evidence separates Mentha material forms.
- Moss: NOT_SAME — Moss is RELATED to Mossy and must not be collapsed with Oakmoss.
- Neroli: NOT_SAME — Orange Blossom and Neroli are distinct bitter-orange flower materials in Stage 20 evidence.
- Pine needles: NOT_SAME — Pine and Pine Needle material are not automatically identical concepts.
- White Musk: NOT_SAME — Existing v0.3 relation to Musk-Like is FAMILY, not SAME_CONCEPT.
- Water Notes: NOT_SAME — Existing v0.3 relation to Watery is RELATED, not SAME_CONCEPT.
- Bearberry: NOT_SAME — Barberry and Bearberry are only string-similar and are different labels.

Mint/Peppermint, Moss/Oakmoss, Orange Blossom/Neroli, Pine/Pine Needle, White Musk/Musk-Like는 FAMILY/RELATED 또는 별도 concept 가능성을 보존하고 통합하지 않았다.

### 6. Canonicalization 전후 Note Vocabulary 변화

- raw unique Note: **2,523**
- canonical unique concept: **2,492**
- 감소: **31 concepts**
- SAME_CONCEPT raw mapping: **48**
- 실제 중복 cluster: **30**

전체 2,523개 lookup을 저장했으며 변경 없는 Note는 raw_note=canonical_note, relation=CANONICAL이다.

### 7. Stage 20 결과 해석에 미치는 영향

- Stage 20 strict matched raw Note: **185**
- canonical 기준 strict matched concept: **178**

Canonicalization은 vocabulary 분모와 strict matched raw Note를 concept 단위로 함께 중복 제거한다. 이는 Stage 20의 occurrence-weighted/perfume-level Coverage를 다시 최적화하거나 기존 결론을 뒤집는 분석이 아니다.

### 8. Annotation에 미치는 영향

현재 200개 Golden Set에서 SAME_CONCEPT alias raw label이 직접 사용된 Query는 **1개**였다. Vanilla label은 1개 Query에 존재하고 Vanille label은 없었다. 현재 파일을 수정하지 않았다.

**향 의미가 동일한 표현은 Annotation에서 Canonical Term 하나로 평가하고, 실제 Fragrantica 검색에서는 동일 Canonical Concept에 속한 raw Note를 모두 확장 검색한다.**

단, Vanille은 현재 REVIEW이므로 추가 근거 없이 Vanilla로 자동 정답화하지 않는다.

### 9. 이번 분석에서 검증된 것

- v0.3 HIGH SAME_CONCEPT와 명확한 내부 표기/철자/문법 중복을 안전하게 canonical lookup으로 만들 수 있다.
- canonical lookup은 모든 2,523개 raw Note를 손실 없이 보존하면서 검색 시 alias 확장을 가능하게 한다.
- 문자열 유사 후보 중 일부는 실제로 NOT_SAME 또는 REVIEW이며 자동 merge하면 안 된다.

### 10. 아직 검증되지 않은 것

- REVIEW 7개의 의미 동일성
- 공식 근거가 없는 번역/언어 alias 전반
- FAMILY/RELATED를 Semantic Bridge feature로 쓰는 방식
- Canonicalization 이후 향수 ranking 또는 사용자 만족 변화

### 11. Semantic Bridge Pilot에 사용할 Canonicalization 원칙

1. 입력과 Annotation은 canonical_note 하나로 비교한다.
2. 실제 Fragrantica 검색은 canonical_note에 속한 모든 SAME_CONCEPT raw_note로 확장한다.
3. REVIEW와 NOT_SAME은 identity mapping으로 유지하고 자동 확장하지 않는다.
4. FAMILY/RELATED는 canonical equivalence가 아닌 별도 feature/evidence layer로만 다룬다.
5. 새로운 alias는 기존 공식 evidence 또는 명확한 표기 규칙이 생길 때만 map version을 올려 추가한다.

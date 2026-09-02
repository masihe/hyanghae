# IFRA Knowledge Coverage Analysis

## 결과 요약

IFRA 2020 Glossary에서 3,119개 ingredient 행, 27개 Primary descriptor, 228개 Secondary descriptor를 추출했다. Fragrantica의 92개 Accord 중 strict vocabulary coverage는 52.2%, occurrence-weighted coverage는 74.1%였다. 2,523개 Note 중 strict vocabulary coverage는 6.3%, occurrence-weighted coverage는 49.7%, perfume-level coverage는 92.3%였다.

### 결론

IFRA는 **향의 저수준 olfactory descriptor와 ingredient 근거를 제공하는 보조 지식원**으로 가치가 있다. 다만 Fragrantica Note와 IFRA Ingredient는 다른 개념이므로 IFRA만으로 Note ontology를 완성했다고 볼 수 없다. strict match와 사람이 검토해야 할 material-family/alias candidate를 분리해야 하며, 추천 점수나 자연어 의미 변환에는 이 결과를 직접 사용하면 안 된다.

---

## 1. IFRA 데이터 구조

- Rows: 3,119
- Unique CAS: 2,588
- Unique Principal Names: 3,094
- Primary Descriptor: 27
- Secondary Descriptor: 228

## 2. IFRA Descriptor 구조

Primary descriptor는 27개 정의와 표의 vocabulary가 일치했다. Secondary descriptor는 훨씬 세분화된 재료·향조 표현을 포함한다. Primary-Secondary edge와 profile은 같은 ingredient 행에서의 동시 등장 근거이며 인과나 강도를 뜻하지 않는다.

## 3. Fragrantica Accord Coverage

- Strict: 48/92 (52.2%)
- Potential (alias candidate 포함): 55.4%
- Occurrence-weighted strict: 74.1%
- Primary match: 17
- Secondary-only match: 31

Secondary-only match가 31개이므로 Primary 27개만 사용하는 것보다 Secondary descriptor를 함께 보존하는 편이 직접 연결 범위를 넓힌다.

## 4. Fragrantica Note Coverage

- Vocabulary strict: 159/2,523 (6.3%)
- Potential (material family / alias candidate 포함): 10.3%
- Occurrence-weighted strict: 49.7%
- Perfume-level strict: 121,786/131,930 (92.3%)

Potential coverage는 검증된 coverage가 아니라 사람이 검토할 수 있는 상한 후보이다.

## 5. 고빈도 Note Coverage

- Top 20: 11/20 (55.0%); occurrence-weighted 60.7%
- Top 50: 30/50 (60.0%); occurrence-weighted 61.7%
- Top 100: 55/100 (55.0%); occurrence-weighted 59.6%
- Top 200: 88/200 (44.0%); occurrence-weighted 56.1%
- Top 500: 115/500 (23.0%); occurrence-weighted 51.5%

## 6. 대표 Matching 사례

대표 사례는 `17_note_ifra_matching.csv`의 strict level, material-family candidate, alias candidate를 분리해 기록했다. `Pine -> Pine needle oil`, `Oud -> Agarwood`, `Cedar -> Cedarwood`, `Musk -> Musk Like` 같은 관계는 자동 정답이 아니라 수동 검토 후보이다.

## 7. 주요 Unmatched Note

- Mandarin Orange: 11,646 perfumes, 11,652 occurrences
- Orange Blossom: 11,479 perfumes, 11,545 occurrences
- Leather: 10,626 perfumes, 10,754 occurrences
- Pink Pepper: 10,387 perfumes, 10,395 occurrences
- White Musk: 8,339 perfumes, 8,371 occurrences
- Woody Notes: 8,278 perfumes, 8,385 occurrences
- Lily-of-the-Valley: 7,339 perfumes, 7,366 occurrences
- Freesia: 5,683 perfumes, 5,696 occurrences
- Black Currant: 5,560 perfumes, 5,566 occurrences
- Citruses: 4,982 perfumes, 4,993 occurrences
- Black Pepper: 4,795 perfumes, 4,807 occurrences
- Mint: 4,605 perfumes, 4,627 occurrences
- Green Notes: 4,529 perfumes, 4,538 occurrences
- Floral Notes: 4,436 perfumes, 4,505 occurrences
- Moss: 4,302 perfumes, 4,310 occurrences

## 8. IFRA의 장점

- 출처와 descriptor 정의가 명시된 ingredient-level olfactory vocabulary를 제공한다.
- Primary-Secondary 동시 등장 profile을 evidence로 보존할 수 있다.
- 고빈도 feature의 실제 사용 빈도와 결합하면 vocabulary coverage와 서비스 체감 coverage를 분리해 볼 수 있다.

## 9. IFRA의 한계

- Fragrantica Note concept와 IFRA ingredient는 동일하지 않다.
- Descriptor는 향수 ranking score나 배합 비율, 강도를 제공하지 않는다.
- Strict unmatched는 잘못된 Note라는 뜻이 아니라 IFRA에서 직접 연결 근거를 찾지 못했다는 뜻이다.
- Alias 및 material family 후보는 수동 검증 전 확정 mapping으로 사용할 수 없다.

## 10. Semantic Bridge 활용 가능성

이번 노트북은 Semantic Bridge를 구현하지 않았다. IFRA는 `ingredient -> primary/secondary descriptor` evidence layer로는 활용할 수 있지만, `비 오는 숲 -> woody/green/earthy` 같은 추상 자연어 mapping을 직접 보장하지 않는다. 향후 bridge에서는 IFRA edge를 하나의 근거로 사용하되 별도 자연어·전문 ontology 자료와 사람이 검증한 alias를 결합해야 한다.

## 11. 다음 단계 제안

1. `17_top_unmatched_notes.csv`의 고빈도 항목부터 외부 권위 자료(dsm-firmenich, IFF, Givaudan 등)의 보완 범위를 정한다.
2. `17_ifra_alias_candidates.csv`와 material-family candidate를 사람이 검토해 versioned mapping으로 분리한다.
3. 검증된 mapping만 이용해 별도 Semantic Bridge 실험을 설계하고, 추천 점수에는 독립적인 평가를 거친 뒤 사용한다.

# Fragrantica matcher Gold DEV baseline

## 평가 범위

- Gold DEV: 80개
- 평가 대상: 77개
- Gold MATCH: 61개
- Gold NO_MATCH: 16개
- UNRESOLVED 제외: 3개
- progressive stopping을 사용하지 않고 평가 대상 전체를 match_one에 직접 전달했다.
- Candidate Retrieval은 현재 matcher의 브랜드 범위, 형태·농도 필터와 fuzzy 정렬을 그대로 재현했다.
- Match Confirmation에는 현재 matcher에 이미 존재하던 snapshot manual override도 포함된다: 1개.
- gold_set_test.csv는 읽거나 사용하지 않았다.

## 전체 baseline

- Recall@1: 0.3115
- Recall@3: 0.5082
- Recall@5: 0.5902
- MRR: 0.4451
- Top5 retrieval miss: 25개
- Auto-MATCH: 24개
- Correct Auto-MATCH: 17개
- False Auto-MATCH: 7개
- Auto-MATCH Precision: 0.7083
- Auto-MATCH Recall: 0.2787
- MATCH_REVIEW: 8개
- NO_MATCH: 45개
- Gold MATCH를 NO_MATCH로 판정: 29개
- Gold NO_MATCH를 MATCH로 잘못 확정: 0개

## Representative와 Challenge

- Representative: 47개, R@5 0.5455, Precision 1.0000, Recall 0.3333
- Challenge: 30개, R@5 0.6429, Precision 0.4615, Recall 0.2143

### 상세 breakdown

| 구분 | 대상 | Gold MATCH | R@1 | R@3 | R@5 | MRR | Auto MATCH | 정답 Auto | 오탐 | Precision | Recall | REVIEW | NO_MATCH |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| ALL | 77 | 61 | 0.3115 | 0.5082 | 0.5902 | 0.4451 | 24 | 17 | 7 | 0.7083 | 0.2787 | 8 | 45 |
| REPRESENTATIVE | 47 | 33 | 0.3333 | 0.5152 | 0.5455 | 0.4473 | 11 | 11 | 0 | 1.0000 | 0.3333 | 2 | 34 |
| CHALLENGE | 30 | 28 | 0.2857 | 0.5000 | 0.6429 | 0.4424 | 13 | 6 | 7 | 0.4615 | 0.2143 | 6 | 11 |
| FAMILY_VARIANT_RISK | 4 | 4 | 0.5000 | 0.5000 | 0.5000 | 0.5417 | 3 | 2 | 1 | 0.6667 | 0.5000 | 0 | 1 |
| FUZZY_AUTO_MATCH_RISK | 10 | 10 | 0.4000 | 0.8000 | 0.8000 | 0.5957 | 10 | 4 | 6 | 0.4000 | 0.4000 | 0 | 0 |
| MATCH_REVIEW | 6 | 6 | 0.0000 | 0.1667 | 0.5000 | 0.2049 | 0 | 0 | 0 | - | 0.0000 | 6 | 0 |
| NORMALIZATION_RISK | 4 | 2 | 0.5000 | 0.5000 | 0.5000 | 0.5000 | 0 | 0 | 0 | - | 0.0000 | 0 | 4 |
| NO_MATCH_CROSSLINGUAL | 6 | 6 | 0.1667 | 0.3333 | 0.6667 | 0.3390 | 0 | 0 | 0 | - | 0.0000 | 0 | 6 |

## False Auto-MATCH 사례

| DEV ID | 상품 | Gold | Gold ID | 현재 판정 | 현재 ID | 후보 Top5 |
|---|---|---|---:|---|---:|---|
| D016 | 미스 디올 오 드 퍼퓸 | MATCH | 68905 | MATCH | 223 | Miss Dior / Miss Dioramour / Miss Dior Essence / Diorama / Miss Dior Le Parfum |
| D022 | 르셀디세이 오 드 퍼퓸 100ml / 르셀디세이 오 드 퍼퓸 50ml / 이세이미야케 르 셀 디세이 EDP (50ml/100ml) | MATCH | 106577 | MATCH | 95642 | Le Sel d’Issey / Soleil d'Issey / Lumière d’Issey / L'eau d'Issey / L'Eau Majeure d'Issey |
| D031 | 블랙베리 앤 베이 코롱 | MATCH | 15134 | MATCH | 66881 | Blackberry & Bay Cologne / Blackberry & Bay / Birch & Black Pepper / Silk Blossom Cologne / Violet & Amber Absolu |
| D047 | 미스 디올 블루밍 부케 오 드 뚜왈렛 | MATCH | 78945 | MATCH | 23280 | Miss Dior Blooming Bouquet / Miss Dior Blooming Bouquet Roller Pearl / Miss Dior Blooming Bouquet (2023) / Miss Dior Blooming Bouquet Couture Edition / Miss Dior Cherie Blooming Bouquet 2011 |
| D059 | 우먼 EDT 40ML | MATCH | 14109 | MATCH | 25977 | Jimmy Choo Man / Jimmy Choo Man Aqua / Jimmy Choo Man Ice / Jimmy Choo Man Blue / Jimmy Choo Man Intense |
| D062 | [베르사체] 에로스 에너지 EDP 100ml (미니어처 1종) / [베르사체] 에로스 에너지 EDP 50ml (미니어처 1종) / [베르사체] 에로스 에너지 오드퍼퓸 100ml (+ 미니어처 1종) / [베르사체] 에로스 에너지 오드퍼퓸 50ml (+ 미니어처 1종) | MATCH | 92647 | MATCH | 99116 | Eros Najim / Eros Energy / Versus Donna / Green Jeans / Baby Rose Jeans |
| D078 | 클래식 쿨 코튼 EDP 60ML / 쿨 코튼 오 드 퍼퓸 | MATCH | 23032 | MATCH | 71221 | Clean Classic Warm Cotton / Cool Cotton / Clean Classic Summer Day / Clean Warm Cotton / Clean Classic Beach Vibes |

## Candidate Retrieval Top5 miss 사례

| DEV ID | 상품 | Gold | Gold ID | 현재 판정 | 현재 ID | 후보 Top5 |
|---|---|---|---:|---|---:|---|
| D001 | 피렌체 1221 에디션 오드코롱 [프리지아] | MATCH | 11467 | NO_MATCH |  | Opoponax / Rosa Novella / Alba di Seoul / Acqua di Sicilia / Patchouli |
| D002 | [단독기획] 제니퍼로페즈 글로우 바이제이로 EDT 100ml 기획(+프로미스 바디로션) | MATCH | 869 | NO_MATCH |  |  |
| D007 | 레드 로즈 코롱 | MATCH | 5484 | MATCH_REVIEW |  | Darjeeling Tea / Red Roses Cologne / Lavender & Coriander / Dark Amber & Ginger Lily / Lavender & Coriander Cologne |
| D013 | 오 드 퍼퓸 [블랑쉬] | MATCH | 6686 | MATCH_REVIEW |  | Bullion / Mumbai Noise  / Young Rose / Belle de Tanger / Blanche Absolu |
| D016 | 미스 디올 오 드 퍼퓸 | MATCH | 68905 | MATCH | 223 | Miss Dior / Miss Dioramour / Miss Dior Essence / Diorama / Miss Dior Le Parfum |
| D018 | [보이넥스트도어 PICK] 에끌로에 오 드 퍼퓸 EDP 50ml | MATCH | 124072 | NO_MATCH |  | Boudoir / Boudoir Jouy / Mon Boudoir / Boudoir 2025 / Boudoir Sin Garden |
| D021 | 리브르 오 드 빠르펭 | MATCH | 56077 | NO_MATCH |  | Libre L'Absolu Platine / Libre Le Parfum / Libre Eau de Toilette / Libre L’Eau Nue / In Love Again Edition Fleur De La Passion |
| D022 | 르셀디세이 오 드 퍼퓸 100ml / 르셀디세이 오 드 퍼퓸 50ml / 이세이미야케 르 셀 디세이 EDP (50ml/100ml) | MATCH | 106577 | MATCH | 95642 | Le Sel d’Issey / Soleil d'Issey / Lumière d’Issey / L'eau d'Issey / L'Eau Majeure d'Issey |

## 재현 정보

- gold_set_dev.csv SHA-256: `41d5b84b30289dd24d3822c552cc100890d009600aa8a310234b2160ec37ad2f`
- build_korea_popularity_map.py SHA-256: `b5b4466e1a7f959634854fa0cd4459ca56cf104ffa06016e76a5efb51d4bcfef`
- korea_commercial_identities.csv SHA-256: `069a30ca2c053ba0222f66aa529996b61ede12df8bb97f743f8c3a2718787588`
- perfumes.csv SHA-256: `cec1ea0b498853032bcf44d33ad52ac83e2ed2896b67d5a2765d90a0345cc055`

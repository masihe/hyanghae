# 자동 확정 취소분 사람 검토 큐 (10d)

Verification(10b, 기준 E)이 확정을 취소한 **89건** 중 인기 상위 **50건**이다 (상한 50건, 사용자 결정).

## 왜 검토가 필요한가

규칙은 DEV 에서 precision 을 0.8049 → 0.9200 으로 올렸다. 대신 정답 확정 10건을 함께 잃었고,
취소된 89건에 **화해 순위 보유 향수 15건**이 들어 있다. 규칙이 인기 상위 구간에서 뭉툭하다.

예: 화해 30위 `CK One` 이 "기본명에 카탈로그 변형 40개" 로 취소됐지만 국내 이름이 정확히 `CK One` 이다.

## 판정 방법

`confirmation_review_queue.csv` 의 빈 3열을 채운다.

| 열 | 값 |
|---|---|
| `human_decision` | `CONFIRM` (취소를 되돌려 확정) / `REJECT` (지도에서 제외) / `OTHER` (다른 후보가 정답) |
| `human_fragrantica_id` | `CONFIRM` 이면 비워도 된다(`refused_fragrantica_id` 를 쓴다). `OTHER` 면 정답 ID 를 적는다 |
| `human_note` | 판단 근거. 나중에 규칙을 고칠 때 쓴다 |

- **`candidate_names` 는 상위 5개뿐이다.** 정답이 그 밖에 있을 수 있다
  (DEV 오확정 7건 중 5건은 정답이 8~22위였다). 확신이 없으면 `REJECT` 가 안전하다.
- 사람이 확정한 결과는 코드가 뒤집지 못하게 고정한다. 되돌리지 않는다.

## 취소 사유별 분포 (전체 89건)

| 사유 | 건수 | 의미 |
|---|---:|---|
| `phonetic key only` | 68 | 모음을 지운 음성 키만으로 이겼다. `우먼`(woman)과 `Man` 이 같은 키가 되는 붕괴 |
| `base name with N catalog variants` | 21 | 고른 이름을 접두사로 갖는 카탈로그 변형이 5개 이상이다 |

## 검토 대상 50건

| # | 화해 | 브랜드 | 국내 이름 | 농도 | 취소된 판정 | 취소 사유 |
|---:|---:|---|---|---|---|---|
| 1 | 15 | Dior | 미스 | EDP | Miss Dior (1947) | phonetic key only |
| 2 | 16 | Dior | 미스 블루밍 부케 | EDT | Miss Dior Blooming Bouquet (2014) | phonetic key only |
| 3 | 29 | Dashu | 아쿠아 다이브 | PARFUM_UNSPECIFIED | Acqua Dive (2021) | phonetic key only |
| 4 | 30 | Calvin Klein | CK One | EDT | CK One (1994) | base name with 40 catalog variants |
| 5 | 40 | Chanel | 코코 마드모아 오 드 빠르펭 | UNSPECIFIED | Coco Mademoiselle (2001) | base name with 9 catalog variants |
| 6 | 42 | Lancôme | 미라클 | EDP | Miracle (2000) | base name with 12 catalog variants |
| 7 | 46 | Yves Saint Laurent | 리브르 오 드 빠르펭 | UNSPECIFIED | Libre (2019) | base name with 16 catalog variants |
| 8 | 52 | Jimmy Choo | 블러썸 | EDP | Jimmy Choo Blossom (2015) | base name with 6 catalog variants |
| 9 | 59 | Lanvin | 잔느 | EDP | Jeanne Lanvin (2008) | phonetic key only |
| 10 | 64 | Gucci | 블룸 | EDP | Gucci Bloom (2017) | base name with 10 catalog variants |
| 11 | 69 | Yves Saint Laurent | 몽 파리 오 드 빠르펭 | UNSPECIFIED | Mon Paris (2016) | base name with 15 catalog variants |
| 12 | 85 | Burberry | 마이 | EDP | My Burberry (2014) | phonetic key only |
| 13 | 88 | Clean | 클래식 쿨 코튼 | EDP | Clean Classic Warm Cotton (2019) | phonetic key only |
| 14 | 93 | Dior | 옴므 코롱 | UNSPECIFIED | Dior Homme (2011) | base name with 18 catalog variants |
| 15 | 98 | Prada | 캔디 | EDP | Prada Candy (2011) | base name with 7 catalog variants |
| 16 |  | John Varvatos | 아티산 | EDT | Artisan (2009) | base name with 6 catalog variants |
| 17 |  | Clean | 클리어 애플 블로썸 | EDP | Apple Blossom (2023) | phonetic key only |
| 18 |  | Dolce&Gabbana | 라이트 블루 리뉴얼 | EDT | Light Blue (2001) | base name with 32 catalog variants |
| 19 |  | Versace | 에로스 | EDT | Eros (2012) | base name with 7 catalog variants |
| 20 |  | Ralph Lauren | 폴로 | EDT | Polo (1978) | base name with 40 catalog variants |
| 21 |  | John Varvatos | XX 아티산 틸 | EDT | XX Artisan Teal (2022) | phonetic key only |
| 22 |  | Lanvin | 모던 프린세스 | EDP | Modern Princess (2016) | phonetic key only |
| 23 |  | Jimmy Choo | 우먼 | EDT | Jimmy Choo Man (2014) | phonetic key only |
| 24 |  | SW19 | Midnight 오일 | PARFUM_UNSPECIFIED | Midnight | phonetic key only |
| 25 |  | Youssoful | 엠포리아코튼 니치 | UNSPECIFIED | Emporia Cotton | phonetic key only |
| 26 |  | Elizabeth Arden | 그린티 넥타린 블러썸 | EDT | Green Tea Nectarine Blossom (2016) | phonetic key only |
| 27 |  | Hotel Dawson | 미드소마 | EDP | Midsommar (2023) | phonetic key only |
| 28 |  | KINFOLK NOTES | 캡틴스 바 | EDP | Captain's Bar | phonetic key only |
| 29 |  | Ex Nihilo | 러스트 인 파라다이스 | EDP | Lust in Paradise (2019) | phonetic key only |
| 30 |  | Versace | 레드진 | EDT | Red Jeans (1994) | phonetic key only |
| 31 |  | Ariana Grande | 땡큐 넥스트 2 0 | EDP | Thank U Next 2.0 (2021) | phonetic key only |
| 32 |  | Sennok | 슬리핑로즈 | PARFUM_UNSPECIFIED | Sleeping Rose (2025) | phonetic key only |
| 33 |  | Elizabeth Arden | 화이트티 | EDP | White Tea (2017) | phonetic key only |
| 34 |  | Elizabeth Arden | 그린티 코코넛브리즈 | EDT | Green Tea Coconut Breeze (2024) | phonetic key only |
| 35 |  | Versace | 뿌르옴므 딜런블루 | EDT | Versace Pour Homme Dylan Blue (2016) | phonetic key only |
| 36 |  | ANILLO | 엠버528 | EDP | Amber 528 | phonetic key only |
| 37 |  | Montblanc | 익스플로러 익스트림 | PARFUM_UNSPECIFIED | Explorer Extreme (2025) | phonetic key only |
| 38 |  | Philosophy | 원지안 어메이징 그레이스 60ml | EDT | Amazing Grace (1996) | base name with 10 catalog variants |
| 39 |  | Montblanc | 레전드 중 | EDT | Legend (2011) | base name with 13 catalog variants |
| 40 |  | Ralph Lauren | 폴로 랄프 중 | EDT | Ralph (2000) | base name with 12 catalog variants |
| 41 |  | Calvin Klein | CK One 어워즈 한정 | EDT | CK One (1994) | base name with 40 catalog variants |
| 42 |  | Dolce&Gabbana | 베스트 리뉴얼 라이트블루 | EDT | Light Blue (2001) | base name with 32 catalog variants |
| 43 |  | Chloé | 노마드 | EDP | Nomade (2018) | base name with 8 catalog variants |
| 44 |  | Mercedes-Benz | 맨 | EDT | Mercedes-Benz Woman (2016) | phonetic key only |
| 45 |  | Addct | 보이드 우드 | EDP | Void Wood | phonetic key only |
| 46 |  | Issey Miyake | 뤼미에르 디세이 | EDP | Lumière d’Issey (2026) | phonetic key only |
| 47 |  | Montblanc | 레전드 스피릿 | EDT | Legend Spirit (2016) | phonetic key only |
| 48 |  | Narciso Rodriguez | 포 허 | EDT | Narciso Rodriguez For Her (2003) | base name with 19 catalog variants |
| 49 |  | Holibanum | 썸머 브레이크 | EDT | Summer Break (2021) | phonetic key only |
| 50 |  | Narciso Rodriguez | 올 오브 미 인텐스 | EDP | All Of Me Intense (2024) | phonetic key only |

## 상품명 원문과 후보 목록

**1. Dior / 미스** (EDP, LIQUID_PERFUME, 화해 15위)

- 국내 상품명: 미스 디올 오 드 퍼퓸
- 취소된 판정: `223` Miss Dior (1947)
- 취소 사유: phonetic key only (score 1.0, margin 0.285714)
- 후보 상위 5: Miss Dior (1947) | Diorissimo (1956) | Miss Dioramour (2026) | Miss Dior Essence (2025) | Diorama (1948)

**2. Dior / 미스 블루밍 부케** (EDT, LIQUID_PERFUME, 화해 16위)

- 국내 상품명: 미스 디올 블루밍 부케 오 드 뚜왈렛
- 취소된 판정: `23280` Miss Dior Blooming Bouquet (2014)
- 취소 사유: phonetic key only (score 0.947368, margin 0.121281)
- 후보 상위 5: Miss Dior Blooming Bouquet (2014) | Miss Dior Blooming Bouquet (2023) (2023) | Miss Dior Blooming Bouquet Roller Pearl (2018) | Miss Dior Cherie Blooming Bouquet 2011 (2011) | Miss Dior Cherie Blooming Bouquet 2007 (2008)

**3. Dashu / 아쿠아 다이브** (PARFUM_UNSPECIFIED, LIQUID_PERFUME, 화해 29위)

- 국내 상품명: 아쿠아 다이브 퍼퓸 50ml | 아쿠아 다이브 퍼퓸
- 취소된 판정: `68919` Acqua Dive (2021)
- 취소 사유: phonetic key only (score 1.0, margin 0.714286)
- 후보 상위 5: Acqua Dive (2021) | Botanik Leaf (2021) | Sunday Cotton (2021)

**4. Calvin Klein / CK One** (EDT, LIQUID_PERFUME, 화해 30위)

- 국내 상품명: 캘빈클라인 CK One EDT 단품/기획 | 원 EDT
- 취소된 판정: `276` CK One (1994)
- 취소 사유: base name with 40 catalog variants (score 1.0, margin 0.285714)
- 후보 상위 5: CK One (1994) | CK One Gold (2016) | CK One Scene (2005) | CK be (1996) | Calvin (1981)

**5. Chanel / 코코 마드모아 오 드 빠르펭** (UNSPECIFIED, LIQUID_PERFUME, 화해 40위)

- 국내 상품명: 코코 마드모아젤 오 드 빠르펭
- 취소된 판정: `611` Coco Mademoiselle (2001)
- 취소 사유: base name with 9 catalog variants (score 1.0, margin 0.111111)
- 후보 상위 5: Coco Mademoiselle (2001) | Coco Mademoiselle L'Eau (2021) | Coco Mademoiselle Parfum | Coco Mademoiselle Intense (2018) | Coco Mademoiselle L’Extrait (2012)

**6. Lancôme / 미라클** (EDP, LIQUID_PERFUME, 화해 42위)

- 국내 상품명: 미라클 오 드 퍼퓸
- 취소된 판정: `184` Miracle (2000)
- 취소 사유: base name with 12 catalog variants (score 1.0, margin 0.2)
- 후보 상위 5: Miracle (2000) | Miracle Homme (2001) | Marrakech (1946) | Miracle Summer (2003) | Miracle Secret (2017)

**7. Yves Saint Laurent / 리브르 오 드 빠르펭** (UNSPECIFIED, LIQUID_PERFUME, 화해 46위)

- 국내 상품명: 리브르 오 드 빠르펭
- 취소된 판정: `56077` Libre (2019)
- 취소 사유: base name with 16 catalog variants (score 1.0, margin 0.230769)
- 후보 상위 5: Libre (2019) | Eau Libre (1975) | Libre L'Absolu Platine (2023) | Libre Le Parfum (2022) | Libre Eau de Toilette (2021)

**8. Jimmy Choo / 블러썸** (EDP, LIQUID_PERFUME, 화해 52위)

- 국내 상품명: 블러썸 EDP 40ML | 지미추 블러썸 EDP (40ml/60ml) | 지미추 블러썸 EDP 40ml | 블러썸 EDP
- 취소된 판정: `29165` Jimmy Choo Blossom (2015)
- 취소 사유: base name with 6 catalog variants (score 1.0, margin 0.333333)
- 후보 상위 5: Jimmy Choo Blossom (2015) | Amber Kiss (2020) | Jimmy Choo Fever (2018) | Radiant Tuberose (2020) | Vanilla Love (2020)

**9. Lanvin / 잔느** (EDP, LIQUID_PERFUME, 화해 59위)

- 국내 상품명: 랑방 잔느 EDP 30ml | 랑방 잔느 EDP 50ml | 잔느 EDP
- 취소된 판정: `3779` Jeanne Lanvin (2008)
- 취소 사유: phonetic key only (score 1.0, margin 0.304348)
- 후보 상위 5: Jeanne Lanvin (2008) | Jeanne Lanvin My Sin (1924) | Jeanne La Rose (2010) | Jeanne Lanvin Scandal (2016) | Jeanne La Plume (2011)

**10. Gucci / 블룸** (EDP, LIQUID_PERFUME, 화해 64위)

- 국내 상품명: 블룸 오 드 퍼퓸
- 취소된 판정: `44894` Gucci Bloom (2017)
- 취소 사유: base name with 10 catalog variants (score 1.0, margin 0.25)
- 후보 상위 5: Gucci Bloom (2017) | Rosa Sublime (2025) | Gucci Bamboo (2015) | Gucci by Gucci Eau de Parfum (2007) | Gucci Nobile (1988)

**11. Yves Saint Laurent / 몽 파리 오 드 빠르펭** (UNSPECIFIED, LIQUID_PERFUME, 화해 69위)

- 국내 상품명: 몽 파리 오 드 빠르펭
- 취소된 판정: `38914` Mon Paris (2016)
- 취소 사유: base name with 15 catalog variants (score 1.0, margin 0.230769)
- 후보 상위 5: Mon Paris (2016) | Paris (1983) | Mon Paris Lumière (2022) | Mon Paris Couture (2018) | Mon Paris Eau de Toilette (2017)

**12. Burberry / 마이** (EDP, LIQUID_PERFUME, 화해 85위)

- 국내 상품명: 마이 버버리 오드퍼퓸
- 취소된 판정: `25836` My Burberry (2014)
- 취소 사유: phonetic key only (score 1.0, margin 0.333333)
- 후보 상위 5: My Burberry (2014) | Burberry Women (1995) | Burberry Men (1995) | Burberry Summer (2007) | My Burberry Blush (2017)

**13. Clean / 클래식 쿨 코튼** (EDP, LIQUID_PERFUME, 화해 88위)

- 국내 상품명: 클래식 쿨 코튼 EDP 60ML | 쿨 코튼 오 드 퍼퓸
- 취소된 판정: `71221` Clean Classic Warm Cotton (2019)
- 취소 사유: phonetic key only (score 0.941176, margin 0.171946)
- 후보 상위 5: Clean Classic Warm Cotton (2019) | Cool Cotton (2013) | Clean Classic Summer Day (2020) | Clean Warm Cotton (2007) | Clean Classic Beach Vibes (2023)

**14. Dior / 옴므 코롱** (UNSPECIFIED, LIQUID_PERFUME, 화해 93위)

- 국내 상품명: 옴므 코롱
- 취소된 판정: `13015` Dior Homme (2011)
- 취소 사유: base name with 18 catalog variants (score 1.0, margin 0.2)
- 후보 상위 5: Dior Homme (2011) | Cuir Cannage (2014) | Diorling (1963) | Dior Homme Cologne (2007) | Dior Homme 2020 (2020)

**15. Prada / 캔디** (EDP, LIQUID_PERFUME, 화해 98위)

- 국내 상품명: 캔디 EDP
- 취소된 판정: `12426` Prada Candy (2011)
- 취소 사유: base name with 7 catalog variants (score 1.0, margin 0.25)
- 후보 상위 5: Prada Candy (2011) | Prada Candy Kiss (2016) | Prada Candy Night (2019) | Prada Candy Sugar Pop (2018) | Prada Tendre (2006)

**16. John Varvatos / 아티산** (EDT, LIQUID_PERFUME)

- 국내 상품명: 아티산 EDT 75ML | 아티산 EDT 125ML
- 취소된 판정: `5534` Artisan (2009)
- 취소 사유: base name with 6 catalog variants (score 1.0, margin 0.125)
- 후보 상위 5: Artisan (2009) | XX Artisan (2020) | Artisan Blu (2016) | Artisan Pure (2017) | Artisan Acqua (2013)

**17. Clean / 클리어 애플 블로썸** (EDP, LIQUID_PERFUME)

- 국내 상품명: 클리어 애플 블로썸 EDP 30ML | 클리어 애플 블로썸 EDP 60ML
- 취소된 판정: `82586` Apple Blossom (2023)
- 취소 사유: phonetic key only (score 0.857143, margin 0.190476)
- 후보 상위 5: Apple Blossom (2023) | Clean Blossom (2016) | Spring Breeze (2024) | Solar Bloom (2019) | Clean Lovegrass (2017)

**18. Dolce&Gabbana / 라이트 블루 리뉴얼** (EDT, LIQUID_PERFUME)

- 국내 상품명: 라이트 블루 오 드 뚜왈렛 30ml (리뉴얼) | 라이트 블루 오 드 뚜왈렛 10ml (리뉴얼) | 라이트 블루 오 드 뚜왈렛 100ml (리뉴얼)
- 취소된 판정: `485` Light Blue (2001)
- 취소 사유: base name with 32 catalog variants (score 1.0, margin 0.142857)
- 후보 상위 5: Light Blue (2001) | Light Blue Sun (2019) | Light Blue Forever (2021) | Light Blue Italian Love (2022) | Light Blue Love in Capri (2016)

**19. Versace / 에로스** (EDT, LIQUID_PERFUME)

- 국내 상품명: 에로스 EDT 100ML + 에로스 미니어처 [선물박스] | 에로스 EDT 30ML + 에로스미니어처 [선물박스] | 에로스 EDT 50ML + 에로스 미니어처 [선물박스] | 베르사체 에로스 EDT 30ml
- 취소된 판정: `16657` Eros (2012)
- 취소 사유: base name with 7 catalog variants (score 1.0, margin 0.2)
- 후보 상위 5: Eros (2012) | Versus (2010) | Yellow Jeans (1996) | Versus Uomo (1991) | Eros Parfum (2021)

**20. Ralph Lauren / 폴로** (EDT, LIQUID_PERFUME)

- 국내 상품명: 폴로 EDT 125ML
- 취소된 판정: `890` Polo (1978)
- 취소 사유: base name with 40 catalog variants (score 1.0, margin 0.2)
- 후보 상위 5: Polo (1978) | Polo 67 (2024) | Polo Oud (2023) | Polo Red (2013) | Polo Earth (2022)

**21. John Varvatos / XX 아티산 틸** (EDT, LIQUID_PERFUME)

- 국내 상품명: XX 아티산 틸 EDT 125ML
- 취소된 판정: `73336` XX Artisan Teal (2022)
- 취소 사유: phonetic key only (score 0.947368, margin 0.123839)
- 후보 상위 5: XX Artisan Teal (2022) | XX Artisan (2020) | John Varvatos XX Elixir (2025) | John Varvatos XX Intense (2024) | Artisan Blu (2016)

**22. Lanvin / 모던 프린세스** (EDP, LIQUID_PERFUME)

- 국내 상품명: 모던 프린세스 EDP 30ML | 모던 프린세스 EDP 60ML | 모던 프린세스 EDP 90ML(+샘플 2ML 3종)
- 취소된 판정: `38890` Modern Princess (2016)
- 취소 사유: phonetic key only (score 0.875, margin 0.175)
- 후보 상위 5: Modern Princess (2016) | Modern Princess in Jeans (2024) | Modern Princess Blooming (2020) | Oud & Rose (2011) | Jeanne La Rose (2010)

**23. Jimmy Choo / 우먼** (EDT, LIQUID_PERFUME)

- 국내 상품명: 우먼 EDT 40ML
- 취소된 판정: `25977` Jimmy Choo Man (2014)
- 취소 사유: phonetic key only (score 1.0, margin 0.2)
- 후보 상위 5: Jimmy Choo Man (2014) | Jimmy Choo Man Aqua (2022) | Jimmy Choo Man Ice (2017) | Jimmy Choo Man Blue (2018) | Jimmy Choo Man Intense (2016)

**24. SW19 / Midnight 오일** (PARFUM_UNSPECIFIED, LIQUID_PERFUME)

- 국내 상품명: SW19 Midnight 오일 퍼퓸 10ml
- 취소된 판정: `93865` Midnight
- 취소 사유: phonetic key only (score 0.923077, margin 0.396761)
- 후보 상위 5: Midnight | Twilight (2024) | Noon (2024) | 8am (2025) | 6am (2024)

**25. Youssoful / 엠포리아코튼 니치** (UNSPECIFIED, LIQUID_PERFUME)

- 국내 상품명: 엠포리아코튼 니치향수
- 취소된 판정: `118435` Emporia Cotton
- 취소 사유: phonetic key only (score 0.857143, margin 0.285714)
- 후보 상위 5: Emporia Cotton | Puglia ostuni | Hyperion | Dimanche à Paris | Milan Fever

**26. Elizabeth Arden / 그린티 넥타린 블러썸** (EDT, LIQUID_PERFUME)

- 국내 상품명: 그린티 넥타린 블러썸 EDT 100ml +향수 공병 증정
- 취소된 판정: `35971` Green Tea Nectarine Blossom (2016)
- 취소 사유: phonetic key only (score 1.0, margin 0.166667)
- 후보 상위 5: Green Tea Nectarine Blossom (2016) | Green Tea Citron Freesia (2023) | Green Tea Sakura Blossom (2021) | Green Tea Cherry Blossom (2012) | Green Tea Coconut Breeze (2024)

**27. Hotel Dawson / 미드소마** (EDP, LIQUID_PERFUME)

- 국내 상품명: 오드퍼퓸 20ml 미드소마
- 취소된 판정: `94832` Midsommar (2023)
- 취소 사유: phonetic key only (score 0.888889, margin 0.488889)
- 후보 상위 5: Midsommar (2023) | Missed & Burnt (2023) | Self Bloom (2024) | Salute To You (2023) | Roll The Dice (2023)

**28. KINFOLK NOTES / 캡틴스 바** (EDP, LIQUID_PERFUME)

- 국내 상품명: 오 드 퍼퓸 캡틴스 바 - 30ml
- 취소된 판정: `123290` Captain's Bar
- 취소 사유: phonetic key only (score 0.923077, margin 0.323077)
- 후보 상위 5: Captain's Bar | Captain's Bar Special Edition | Scent of Muse (2024) | Lin Blanc Special Edition | Garden Shower

**29. Ex Nihilo / 러스트 인 파라다이스** (EDP, LIQUID_PERFUME)

- 국내 상품명: 러스트 인 파라다이스 오드퍼퓸 10ml
- 취소된 판정: `53588` Lust in Paradise (2019)
- 취소 사유: phonetic key only (score 1.0, margin 0.304348)
- 후보 상위 5: Lust in Paradise (2019) | Lust In Paradise par Reine Paradis (2019) | Scarlet Sands (2024) |  In Paradise Riviera (2022) | Generation(s) (2025)

**30. Versace / 레드진** (EDT, LIQUID_PERFUME)

- 국내 상품명: 레드진 EDT 75ml
- 취소된 판정: `638` Red Jeans (1994)
- 취소 사유: phonetic key only (score 0.888889, margin 0.138889)
- 후보 상위 5: Red Jeans (1994) | Yellow Jeans (1996) | Yellow Diamond (2011) | Versus Donna (1992) | Blue Jeans (1994)

**31. Ariana Grande / 땡큐 넥스트 2 0** (EDP, LIQUID_PERFUME)

- 국내 상품명: 땡큐 넥스트 2.0 EDP 30ML
- 취소된 판정: `68367` Thank U Next 2.0 (2021)
- 취소 사유: phonetic key only (score 0.9, margin 0.122222)
- 후보 상위 5: Thank U Next 2.0 (2021) | Thank U, Next (2019) | Angels Kiss (2024) | Pink Woods (2024) | Cloud Pink (2023)

**32. Sennok / 슬리핑로즈** (PARFUM_UNSPECIFIED, LIQUID_PERFUME)

- 국내 상품명: 퍼퓸 슬리핑로즈 50ml
- 취소된 판정: `123063` Sleeping Rose (2025)
- 취소 사유: phonetic key only (score 0.857143, margin 0.32381)
- 후보 상위 5: Sleeping Rose (2025) | Slow September (2023) | Soap Clean Soap | Linen Citrus (2025) | Baby Blusher (2024)

**33. Elizabeth Arden / 화이트티** (EDP, LIQUID_PERFUME)

- 국내 상품명: 화이트티 EDP 100ml
- 취소된 판정: `42439` White Tea (2017)
- 취소 사유: phonetic key only (score 1.0, margin 0.333333)
- 후보 상위 5: White Tea (2017) | White Tea Eau Lilac (2025) | Pretty Hot (2011) | Night and Day (1935) | White Tea Eau Fraiche (2023)

**34. Elizabeth Arden / 그린티 코코넛브리즈** (EDT, LIQUID_PERFUME)

- 국내 상품명: 그린티 코코넛브리즈 EDT 100ml
- 취소된 판정: `91712` Green Tea Coconut Breeze (2024)
- 취소 사유: phonetic key only (score 0.9, margin 0.122222)
- 후보 상위 5: Green Tea Coconut Breeze (2024) | Green Tea Cucumber (2015) | Green Tea Camellia (2011) | Green Tea Nectarine Blossom (2016) | Green Tea Citron Freesia (2023)

**35. Versace / 뿌르옴므 딜런블루** (EDT, LIQUID_PERFUME)

- 국내 상품명: 뿌르옴므 딜런블루 EDT 100ml
- 취소된 판정: `40031` Versace Pour Homme Dylan Blue (2016)
- 취소 사유: phonetic key only (score 0.941176, margin 0.204334)
- 후보 상위 5: Versace Pour Homme Dylan Blue (2016) | Versace Pour Femme Dylan Purple (2022) | Versace Pour Femme Dylan Turquoise (2020) | Versace Pour Femme Dylan Blush Pink (2025) | Versace Pour Homme Oud Noir (2013)

**36. ANILLO / 엠버528** (EDP, LIQUID_PERFUME)

- 국내 상품명: 엠버528 오 드 퍼퓸 50ml
- 취소된 판정: `121752` Amber 528
- 취소 사유: phonetic key only (score 0.909091, margin 0.575758)
- 후보 상위 5: Amber 528 | Shower Time | Neroli Wood (2025) | Black Tea | Lime Sunday (2025)

**37. Montblanc / 익스플로러 익스트림** (PARFUM_UNSPECIFIED, LIQUID_PERFUME)

- 국내 상품명: 익스플로러 익스트림 퍼퓸 60ML
- 취소된 판정: `106403` Explorer Extreme (2025)
- 취소 사유: phonetic key only (score 1.0, margin 0.263158)
- 후보 상위 5: Explorer Extreme (2025) | Starwalker Extreme (2021) | Explorer Ultra Blue (2021) | Explorer Platinum (2023) | Explorer (2019)

**38. Philosophy / 원지안 어메이징 그레이스 60ml** (EDT, LIQUID_PERFUME)

- 국내 상품명: [원지안PICK] 필로소피 어메이징 그레이스 EDT 15ml/60ml/60ml기획
- 취소된 판정: `4849` Amazing Grace (1996)
- 취소 사유: base name with 10 catalog variants (score 1.0, margin 0.225806)
- 후보 상위 5: Amazing Grace (1996) | Amazing Grace Jasmine (2021) | Amazing Grace Lavender (2022) | Amazing Grace Bergamot (2019) | Amazing Grace Magnolia (2019)

**39. Montblanc / 레전드 중** (EDT, LIQUID_PERFUME)

- 국내 상품명: 몽블랑 레전드 EDT 30ml/50ml 중 택1
- 취소된 판정: `11784` Legend (2011)
- 취소 사유: base name with 13 catalog variants (score 1.0, margin 0.2)
- 후보 상위 5: Legend (2011) | Legend Red (2022) | Legend Elixir (2026) | Legend Spirit (2016) | Legend Intense (2013)

**40. Ralph Lauren / 폴로 랄프 중** (EDT, LIQUID_PERFUME)

- 국내 상품명: 랄프로렌 폴로 랄프 EDT 30ml,50ml 단품/기획 중 택 1
- 취소된 판정: `826` Ralph (2000)
- 취소 사유: base name with 12 catalog variants (score 1.0, margin 0.230769)
- 후보 상위 5: Ralph (2000) | Ralph Hot (2006) | Ralph Love (2016) | Ralph Wild (2008) | Ralph Cool (2004)

**41. Calvin Klein / CK One 어워즈 한정** (EDT, LIQUID_PERFUME)

- 국내 상품명: CK 캘빈클라인 One EDT 어워즈 한정기획 (200ml)
- 취소된 판정: `276` CK One (1994)
- 취소 사유: base name with 40 catalog variants (score 1.0, margin 0.285714)
- 후보 상위 5: CK One (1994) | CK One Gold (2016) | CK One Scene (2005) | CK be (1996) | CK One Summer (2004)

**42. Dolce&Gabbana / 베스트 리뉴얼 라이트블루** (EDT, LIQUID_PERFUME)

- 국내 상품명: [베스트/리뉴얼] 돌체앤가바나 라이트블루 EDT 50ml
- 취소된 판정: `485` Light Blue (2001)
- 취소 사유: base name with 32 catalog variants (score 1.0, margin 0.142857)
- 후보 상위 5: Light Blue (2001) | Light Blue Sun (2019) | Light Blue Forever (2021) | Light Blue pour Homme (2007) | Light Blue Perfume Gel (2026)

**43. Chloé / 노마드** (EDP, LIQUID_PERFUME)

- 국내 상품명: 끌로에 노마드 EDP 30ml/50ml/50ml 기획
- 취소된 판정: `48434` Nomade (2018)
- 취소 사유: base name with 8 catalog variants (score 1.0, margin 0.333333)
- 후보 상위 5: Nomade (2018) | Nomade Eau de Toilette (2019) | Nomade Nuit d’Egypte (2024) | Lavanda (2019) | Nomade Jasmin Naturel (2023)

**44. Mercedes-Benz / 맨** (EDT, LIQUID_PERFUME)

- 국내 상품명: 메르세데스 벤츠 맨 EDT 100ml 기획 (+벤츠 맨 10ml) | 메르세데스 벤츠 맨 EDT 30ml/50ml/100ml 3종 택1 | 메르세데스 벤츠 맨 EDT 50ml
- 취소된 판정: `41338` Mercedes-Benz Woman (2016)
- 취소 사유: phonetic key only (score 1.0, margin 0.333333)
- 후보 상위 5: Mercedes-Benz Woman (2016) | Mercedes-Benz Woman In Red (2021) | Mercedes-Benz Man Fresh (2020) | Mercedes-Benz Ultimate (2022) | Mercedes-Benz Woman Eau de Toilette (2016)

**45. Addct / 보이드 우드** (EDP, LIQUID_PERFUME)

- 국내 상품명: 에이딕트 오 드 퍼퓸 보이드 우드 50ml
- 취소된 판정: `131211` Void Wood
- 취소 사유: phonetic key only (score 1.0, margin 0.545455)
- 후보 상위 5: Void Wood | Before Sunset | Lily Veil (2025) | Blanc de Bloom | Verbena Rain (2025)

**46. Issey Miyake / 뤼미에르 디세이** (EDP, LIQUID_PERFUME)

- 국내 상품명: 이세이미야케 뤼미에르 디세이 EDP (30ml/50ml)
- 취소된 판정: `125424` Lumière d’Issey (2026)
- 취소 사유: phonetic key only (score 1.0, margin 0.090909)
- 후보 상위 5: Lumière d’Issey (2026) | L'Eau Majeure d'Issey (2017) | Le Sel d’Issey (2024) | L'eau d'Issey (1992) | L'Eau Majeure d'Issey Shade of Sea (2019)

**47. Montblanc / 레전드 스피릿** (EDT, LIQUID_PERFUME)

- 국내 상품명: 몽블랑 레전드 스피릿 EDT 50ml | 몽블랑 레전드 스피릿 EDT 30ml
- 취소된 판정: `33443` Legend Spirit (2016)
- 취소 사유: phonetic key only (score 0.875, margin 0.25)
- 후보 상위 5: Legend Spirit (2016) | Legend Elixir (2026) | Legend Special Edition 2014 (2014) | Legend Special Edition 2013 (2013) | Legend Special Edition 2012 (2012)

**48. Narciso Rodriguez / 포 허** (EDT, LIQUID_PERFUME)

- 국내 상품명: 나르시소 로드리게즈 포 허 EDT (30ml/50ml)
- 취소된 판정: `209` Narciso Rodriguez For Her (2003)
- 취소 사유: base name with 19 catalog variants (score 1.0, margin 0.25)
- 후보 상위 5: Narciso Rodriguez For Her (2003) | Narciso Rodriguez L'Eau For Her (2013) | Narciso Rodriguez Musc for Her (2007) | Narciso Rodriguez for Him (2007) | Narciso Rodriguez For Her Intense (2025)

**49. Holibanum / 썸머 브레이크** (EDT, LIQUID_PERFUME)

- 국내 상품명: 홀리바넘 오 드 뚜왈렛 30ml 썸머 브레이크
- 취소된 판정: `110365` Summer Break (2021)
- 취소 사유: phonetic key only (score 0.909091, margin 0.409091)
- 후보 상위 5: Summer Break (2021) | Strawberry Haze (2025) | Rosy Blossom (2023) | Cedar Cottage (2022) | Bedtime Bath (2022)

**50. Narciso Rodriguez / 올 오브 미 인텐스** (EDP, LIQUID_PERFUME)

- 국내 상품명: 나르시소 로드리게즈 올 오브 미 인텐스 EDP (30ml/50ml/기획)
- 취소된 판정: `96021` All Of Me Intense (2024)
- 취소 사유: phonetic key only (score 0.857143, margin 0.190476)
- 후보 상위 5: All Of Me Intense (2024) | Narciso Rodriguez For Her Intense (2025) | Narciso Rodriguez For Him Eau de Parfum Intense (2012) | Radiant Magnolia (2024) | Narciso Rodriguez for Her Musc Eau de Parfum Intense (2009)


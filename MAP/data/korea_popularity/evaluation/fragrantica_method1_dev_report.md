# Method 1: DEV retrieval comparison

## 범위와 방법

- 평가 가능 DEV 77개: MATCH 61, NO_MATCH 16. UNRESOLVED 3개 제외. TEST는 읽지 않았다.
- Recall/MRR 분모는 Gold MATCH 61개. NO_MATCH에는 정답 후보가 없어 해당 지표에서 제외하며, 후보를 생성해도 MATCH 판정으로 간주하지 않는다.
- matcher/Verification/threshold/manual override, Raw, Commercial Identity, Candidate Family, Gold, baseline 파일을 수정하지 않았다. match_one도 호출하지 않는다.
- baseline은 기존 evaluate_fragrantica_matcher_dev.retrieve_candidates를 재사용해 전체 순위를 재실행했다. 77개 모두 저장된 Top5와 Gold rank가 정확히 일치해야 결과를 저장한다.
- 입력은 Commercial Identity와 연결된 원본 member 상품명·브랜드·브랜드 근거뿐이다. Candidate Family는 기존 관계 검증에만 사용하며 다른 identity의 상품이나 정답을 합치지 않는다.
- 정규화는 원문, 브랜드, core, 농도, 형태, 제외 문구를 별도로 보존한다. 증정/프로모션 괄호를 먼저 제거한다. 단어 경계로 속성을 분리하고 내부 브랜드/variant token은 유지한다.
- 명시적 raw brand가 완전한 접두어일 때만 core view에서 생략하고 identity_text에 남긴다. 브랜드로 시작하는 동명 제품의 모호성은 이 규칙의 한계다.
- 기존 canonical/alias와 철자 정규화 일치를 우선 후보군에 넣고, 기존 romanize/phonetic 기반 브랜드 후보를 보완한다. 기존 alias를 새로 검증했다고 가정하지 않으며 잘못된 alias를 수정하지 않는다.
- 브랜드 최대 3개. exact가 있으면 raw 브랜드 유사도 0.75 이상만 추가, 없으면 상위 3개로 제한 fallback. 향수 전체를 대상으로 query embedding 검색하지 않는다.
- 브랜드당 최대 300개. 초과 시 기존 lexical 점수로 선별하므로 한 query 후보군은 최대 900개. 이 cap은 semantic 채널의 잠재 recall을 제한할 수 있다.
- 농도·형태 비교 함수는 기존 것을 그대로 사용한다. 개선 경로에서만 프로모션을 먼저 분리한 원문으로 query 속성을 다시 추출하며, 명시된 속성 충돌은 복수 값을 유지한다. 후보 description에서 농도를 추정하는 기존 한계도 유지된다.
- 모델: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`, revision `e8f8c211226b894fcb81acc59f3b34ba3efd5f42`. 한국어·영어를 포함하는 다국어 모델이며 짧은 이름의 의미 비교를 낮은 복잡도로 추가하기 위해 384차원 MiniLM을 선택했다.
  [공식 model card](https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2) / [공식 multilingual 모델 설명](https://sbert.net/docs/sentence_transformer/pretrained_models.html)
- CPU float32, 모델 기본 mean pooling/최대 길이 128, L2 정규화 후 cosine. query는 core name, candidate는 원래 Fragrantica name. 여러 member core는 채널별 최대 유사도로 집계한다. 설명문·Gold name·Gold ID는 embedding 입력에 쓰지 않는다.
- 두 채널 동등 RRF: sum(1/(60+rank)), 동점은 ID 내림차순. 유사도 raw score 가중합 없음. MRR 비교를 위해 Top100 절단 대신 제한된 pool의 전체 ranking을 융합했다. 출력은 Top10.
- 별도 fine-tuning, DEV threshold sweep, 제품별 예외, Gold ID alias는 없다. 설정은 첫 DEV 평가 전 고정했다. baseline_multilingual은 기존 query/brand/filter/lexical 순위를 유지한 채 semantic 채널만 추가한다.
- MRR은 각 실험의 전체 허용 pool 순위(미검색=0), MRR@10은 10위 밖=0. pool 범위 자체가 방법의 일부이므로 MRR@10도 함께 비교한다.

## 전체 및 ablation

| method | group | gold_match | gold_no_match | recall_at_1 | recall_at_3 | recall_at_5 | recall_at_10 | mrr | mrr_at_10 | top5_miss | top10_miss |
|---|---|---|---|---|---|---|---|---|---|---|---|
| baseline_lexical | ALL | 61 | 16 | 0.3115 | 0.5082 | 0.5902 | 0.6721 | 0.4451 | 0.4361 | 25 | 20 |
| improved_lexical | ALL | 61 | 16 | 0.3934 | 0.5082 | 0.5574 | 0.6557 | 0.4786 | 0.4710 | 27 | 21 |
| baseline_multilingual | ALL | 61 | 16 | 0.2295 | 0.3279 | 0.3770 | 0.5410 | 0.3192 | 0.3025 | 38 | 28 |
| method1_full | ALL | 61 | 16 | 0.2295 | 0.2951 | 0.3279 | 0.4590 | 0.3052 | 0.2842 | 41 | 33 |

## Representative / Challenge

| method | group | gold_match | gold_no_match | recall_at_1 | recall_at_3 | recall_at_5 | recall_at_10 | mrr | mrr_at_10 | top5_miss | top10_miss |
|---|---|---|---|---|---|---|---|---|---|---|---|
| baseline_lexical | CHALLENGE | 28 | 2 | 0.2857 | 0.5000 | 0.6429 | 0.7143 | 0.4424 | 0.4310 | 10 | 8 |
| baseline_lexical | REPRESENTATIVE | 33 | 14 | 0.3333 | 0.5152 | 0.5455 | 0.6364 | 0.4473 | 0.4405 | 15 | 12 |
| improved_lexical | CHALLENGE | 28 | 2 | 0.4286 | 0.5714 | 0.6429 | 0.7857 | 0.5329 | 0.5278 | 10 | 6 |
| improved_lexical | REPRESENTATIVE | 33 | 14 | 0.3636 | 0.4545 | 0.4848 | 0.5455 | 0.4325 | 0.4227 | 17 | 15 |
| baseline_multilingual | CHALLENGE | 28 | 2 | 0.2500 | 0.3929 | 0.4286 | 0.6429 | 0.3679 | 0.3536 | 16 | 10 |
| baseline_multilingual | REPRESENTATIVE | 33 | 14 | 0.2121 | 0.2727 | 0.3333 | 0.4545 | 0.2778 | 0.2591 | 22 | 18 |
| method1_full | CHALLENGE | 28 | 2 | 0.2857 | 0.3571 | 0.3929 | 0.5714 | 0.3750 | 0.3533 | 17 | 12 |
| method1_full | REPRESENTATIVE | 33 | 14 | 0.1818 | 0.2424 | 0.2727 | 0.3636 | 0.2461 | 0.2255 | 24 | 21 |

## Challenge 유형별

| method | group | gold_match | gold_no_match | recall_at_1 | recall_at_3 | recall_at_5 | recall_at_10 | mrr | mrr_at_10 | top5_miss | top10_miss |
|---|---|---|---|---|---|---|---|---|---|---|---|
| baseline_lexical | FAMILY_VARIANT_RISK | 4 | 0 | 0.5000 | 0.5000 | 0.5000 | 0.7500 | 0.5417 | 0.5417 | 2 | 1 |
| baseline_lexical | FUZZY_AUTO_MATCH_RISK | 10 | 0 | 0.4000 | 0.8000 | 0.8000 | 0.8000 | 0.5957 | 0.5833 | 2 | 2 |
| baseline_lexical | MATCH_REVIEW | 6 | 0 | 0.0000 | 0.1667 | 0.5000 | 0.6667 | 0.2049 | 0.1861 | 3 | 2 |
| baseline_lexical | NORMALIZATION_RISK | 2 | 2 | 0.5000 | 0.5000 | 0.5000 | 0.5000 | 0.5000 | 0.5000 | 1 | 1 |
| baseline_lexical | NO_MATCH_CROSSLINGUAL | 6 | 0 | 0.1667 | 0.3333 | 0.6667 | 0.6667 | 0.3390 | 0.3250 | 2 | 2 |
| improved_lexical | FAMILY_VARIANT_RISK | 4 | 0 | 0.5000 | 0.5000 | 0.7500 | 1.0000 | 0.5857 | 0.5857 | 1 | 0 |
| improved_lexical | FUZZY_AUTO_MATCH_RISK | 10 | 0 | 0.6000 | 0.7000 | 0.7000 | 0.7000 | 0.6408 | 0.6333 | 3 | 3 |
| improved_lexical | MATCH_REVIEW | 6 | 0 | 0.1667 | 0.3333 | 0.5000 | 0.8333 | 0.3399 | 0.3319 | 3 | 1 |
| improved_lexical | NORMALIZATION_RISK | 2 | 2 | 0.5000 | 0.5000 | 0.5000 | 0.5000 | 0.5000 | 0.5000 | 1 | 1 |
| improved_lexical | NO_MATCH_CROSSLINGUAL | 6 | 0 | 0.3333 | 0.6667 | 0.6667 | 0.8333 | 0.5216 | 0.5185 | 2 | 1 |
| baseline_multilingual | FAMILY_VARIANT_RISK | 4 | 0 | 0.5000 | 0.5000 | 0.5000 | 0.7500 | 0.5357 | 0.5357 | 2 | 1 |
| baseline_multilingual | FUZZY_AUTO_MATCH_RISK | 10 | 0 | 0.4000 | 0.5000 | 0.5000 | 0.6000 | 0.4931 | 0.4667 | 5 | 4 |
| baseline_multilingual | MATCH_REVIEW | 6 | 0 | 0.0000 | 0.0000 | 0.1667 | 0.6667 | 0.1162 | 0.1056 | 5 | 2 |
| baseline_multilingual | NORMALIZATION_RISK | 2 | 2 | 0.0000 | 0.5000 | 0.5000 | 0.5000 | 0.1667 | 0.1667 | 1 | 1 |
| baseline_multilingual | NO_MATCH_CROSSLINGUAL | 6 | 0 | 0.1667 | 0.5000 | 0.5000 | 0.6667 | 0.3663 | 0.3542 | 3 | 2 |
| method1_full | FAMILY_VARIANT_RISK | 4 | 0 | 0.5000 | 0.5000 | 0.5000 | 1.0000 | 0.5833 | 0.5833 | 2 | 0 |
| method1_full | FUZZY_AUTO_MATCH_RISK | 10 | 0 | 0.3000 | 0.4000 | 0.4000 | 0.5000 | 0.3773 | 0.3500 | 6 | 5 |
| method1_full | MATCH_REVIEW | 6 | 0 | 0.1667 | 0.1667 | 0.1667 | 0.5000 | 0.2422 | 0.2183 | 5 | 3 |
| method1_full | NORMALIZATION_RISK | 2 | 2 | 0.0000 | 0.5000 | 0.5000 | 0.5000 | 0.2500 | 0.2500 | 1 | 1 |
| method1_full | NO_MATCH_CROSSLINGUAL | 6 | 0 | 0.3333 | 0.3333 | 0.5000 | 0.5000 | 0.4066 | 0.3750 | 3 | 3 |

## 변화와 관찰

- R@1 0.3115 → 0.2295, R@5 0.5902 → 0.3279, R@10 0.6721 → 0.4590, MRR 0.4451 → 0.3052.
- Top5 miss 25 → 41; Top10 miss 20 → 33. 새 Top5 적중 5개, 기존 Top5 적중 상실 21개.
- improved_lexical: baseline 대비 ΔR@5=-0.0328, ΔMRR=+0.0335.
- baseline_multilingual: baseline 대비 ΔR@5=-0.2131, ΔMRR=-0.1259.
- 개선 lexical에 semantic 추가 효과: ΔR@5=-0.2295, ΔMRR=-0.1733. 정규화와 브랜드 효과는 이 실험에서 묶여 있으므로 각각의 인과 기여로 분리할 수 없다.
- 개선 pool의 semantic 단독 R@5는 0.2459. 개선 lexical의 Top5 적중 중 16개가 RRF 후 Top5에서 탈락했다. rank fusion은 점수 스케일을 맞추지만 부정확한 채널의 영향을 자동으로 억제하지 않는다.
- 브랜드 soft score는 기존 match_score의 자음 중심 phonetic 최대값도 사용한다. Clean에 Aquolina/Caron이 1.0으로 추가되는 등 짧은 이름의 충돌이 관찰됐다. 따라서 0.75 cutoff는 검증된 브랜드 확신도로 해석할 수 없다. 기존 alias 우선 포함만으로는 distractor 순위 상승을 막지 못했다.
- D018 에끌로에: 기존 Vivienne Westwood pool에서 정답이 없었으나 raw 브랜드 음역으로 BiBiANG이 추가되어 lexical/full 모두 2위. D002 Glow: 증정 바디로션을 제거한 뒤 본품 형태가 BODY_FRAGRANCE에서 LIQUID_PERFUME으로 복구되어 lexical 5위/full 6위.
- D007 Red Roses: 농도를 분리한 core로 lexical 34→1위, full 1위. D001 Fresia는 lexical 24위지만 semantic 4위 덕분에 full 5위로 개선됐다.
- D078 Cool Cotton: 쿨 token은 보존되어 개선 lexical 1위지만 semantic 188위, full 14위로 회귀했다. token 보존 자체와 multilingual 순위 개선은 별개다.

### Top5 개선 사례

| queue_id | raw_product_names | gold_fragrantica_name | baseline_rank | method1_rank |
|---|---|---|---|---|
| D001 | 피렌체 1221 에디션 오드코롱 [프리지아] | Fresia | 22.0000 | 5.0000 |
| D007 | 레드 로즈 코롱 | Red Roses | 34.0000 | 1.0000 |
| D018 | [보이넥스트도어 PICK] 에끌로에 오 드 퍼퓸 EDP 50ml | Echloe | — | 2.0000 |
| D021 | 리브르 오 드 빠르펭 | Libre | 16.0000 | 4.0000 |
| D072 | [니샤네] 하지밧 엑스트레 드 퍼퓸 50ml (바이알3종) | Hacivat | 7.0000 | 1.0000 |

### Top5 회귀 사례 (전체)

| queue_id | raw_product_names | gold_fragrantica_name | baseline_rank | method1_rank |
|---|---|---|---|---|
| D004 | 클래식 소프트 런드리 EDP 30ML | Soft Laundry | 2.0000 | 22.0000 |
| D008 | 나르시소 로드리게즈 포 허 EDT (30ml/50ml) | Narciso Rodriguez For Her | 1.0000 | 25.0000 |
| D009 | [박지훈 포카증정] 포맨트 시그니처 퍼퓸 코튼메모리 50ml 단품/기획  /  시그니처 퍼퓸 [코튼메모리]  /  헬로키티 에디션 시그니처 퍼퓸 [코튼메모리] | Cotton Memory | 1.0000 | 11.0000 |
| D011 | 랑방 레 플레르 드 랑방 워터 릴리 EDT 90ml  /  랑방 레 플레르 드 랑방 워터 릴리 EDT 50ml  /  레 플레르 드 EDT [워터릴리] | Water Lily | 5.0000 | 12.0000 |
| D014 | [프레쉬로즈향] 나르시소 로드리게즈 나르시소 크리스탈 EDP (30ml/50m/기획) | Narciso Eau de Parfum Cristal | 3.0000 | 7.0000 |
| D020 | 글로우 바이 제이로 EDT 30ML  /  글로우 바이 제이로 EDT 50ML  /  제니퍼로페즈 글로우 바이제이로 EDT 30ml  /  제니퍼로페즈 글로우 바이제이로 EDT 50ml  /  글로우 바이 제이로 EDT | Glow | 5.0000 | 6.0000 |
| D024 | 쟈도르 오 드 퍼퓸 | J'adore | 2.0000 | 11.0000 |
| D025 | 샹스 오 비브 오 드 뚜왈렛 | Chance Eau Vive | 4.0000 | 13.0000 |
| D032 | 리플레이 소스 오브 라이프 포 맨 오드뚜왈렛 30ml  /  [리플레이] 소스 오브 라이프 포 맨 오드뚜왈렛 100ml | Source of Life Man | 2.0000 | 34.0000 |
| D047 | 미스 디올 블루밍 부케 오 드 뚜왈렛 | Miss Dior Blooming Bouquet 2023 | 3.0000 | 14.0000 |
| D053 | 피렌체 1221 에디션 로사 가데니아 오드코롱 | Rosa Gardenia | 2.0000 | 11.0000 |
| D062 | [베르사체] 에로스 에너지 EDP 100ml (미니어처 1종)  /  [베르사체] 에로스 에너지 EDP 50ml (미니어처 1종)  /  [베르사체] 에로스 에너지 오드퍼퓸 100ml (+ 미니어처 1종)  /  [베르사체] 에로스 에너지 오드퍼퓸 50ml (+ 미니어처 1종) | Eros Energy | 2.0000 | 6.0000 |
| D063 | [몽탈] 머스크 투 머스크 오드퍼퓸 100ml (바이알 3종) | Musk to Musk | 1.0000 | 11.0000 |
| D064 | [니샤네] 헌드레드사일런트 웨이즈 엑스트레 드 퍼퓸 100ml (바이알3종) | Hundred Silent Ways | 2.0000 | 10.0000 |
| D066 | 익스플로러 EDP 100ML  /  익스플로러 EDP 30ML  /  익스플로러 EDP 60ML  /  몽블랑 익스플로러 EDP (30ml/60ml/100ml)  /  몽블랑 익스플로러 EDP 100ml  /  몽블랑 익스플로러 EDP 30ml  /  익스플로러 오 드 퍼퓸 | Explorer | 1.0000 | 18.0000 |
| D071 | [만세라] 프렌치 리비에라 오드퍼퓸 120ml (바이알 3종) | French Riviera | 1.0000 | 27.0000 |
| D073 | 쟈도르 퍼퓸 도 | J'adore Parfum d'Eau | 4.0000 | 28.0000 |
| D075 | 퓨어솝 EDP 60ML  /  퓨어솝 EDP 30ML  /  퓨어솝 EDP | Pure Soap | 1.0000 | 20.0000 |
| D076 | 리플레이 탱크 플레이트 포 우먼 오드뚜왈렛 100ml | #Tank Plate for Her | 2.0000 | 6.0000 |
| D077 | [재규어] 이어러 리로디드 오드퍼퓸 100ml | Jaguar Era Reloaded | 1.0000 | 17.0000 |
| D078 | 클래식 쿨 코튼 EDP 60ML  /  쿨 코튼 오 드 퍼퓸 | Cool Cotton | 2.0000 | 14.0000 |

## Method 1 Top10 miss (전체)

브랜드/필터 배제는 실행 경로로 확인했다. CROSS_LINGUAL_RETRIEVAL은 한국어 query가 있는 순위 실패의 잠정 분류이며, 음역·variant·연도 구분·정규화 잔여 noise 중 무엇이 주원인인지는 MANUAL_CHECK가 필요하다.

| queue_id | raw_product_names | core_queries | gold_name | method1_rank | lexical_rank | semantic_rank | cause | evidence | secondary_review |
|---|---|---|---|---|---|---|---|---|---|
| D004 | 클래식 소프트 런드리 EDP 30ML | ["클래식 소프트 런드리"] | Soft Laundry | 22.0000 | 1.0000 | 249.0000 | CROSS_LINGUAL_RETRIEVAL | Gold survives pool/filters; lexical and semantic fusion rank remains >10 (ranking cause provisional) |  |
| D008 | 나르시소 로드리게즈 포 허 EDT (30ml/50ml) | ["포 허"] | Narciso Rodriguez For Her | 25.0000 | 15.0000 | 36.0000 | CROSS_LINGUAL_RETRIEVAL | Gold survives pool/filters; lexical and semantic fusion rank remains >10 (ranking cause provisional) |  |
| D009 | [박지훈 포카증정] 포맨트 시그니처 퍼퓸 코튼메모리 50ml 단품/기획  /  시그니처 퍼퓸 [코튼메모리]  /  헬로키티 에디션 시그니처 퍼퓸 [코튼메모리] | ["시그니처 코튼메모리", "헬로키티 에디션 시그니처 코튼메모리"] | Cotton Memory | 11.0000 | 1.0000 | 30.0000 | CROSS_LINGUAL_RETRIEVAL | Gold survives pool/filters; lexical and semantic fusion rank remains >10 (ranking cause provisional) |  |
| D011 | 랑방 레 플레르 드 랑방 워터 릴리 EDT 90ml  /  랑방 레 플레르 드 랑방 워터 릴리 EDT 50ml  /  레 플레르 드 EDT [워터릴리] | ["레 플레르 드 랑방 워터 릴리", "레 플레르 드 워터릴리"] | Water Lily | 12.0000 | 9.0000 | 30.0000 | CROSS_LINGUAL_RETRIEVAL | Gold survives pool/filters; lexical and semantic fusion rank remains >10 (ranking cause provisional) |  |
| D016 | 미스 디올 오 드 퍼퓸 | ["미스 디올"] | Miss Dior Eau de Parfum (2021) | 46.0000 | 38.0000 | 63.0000 | CROSS_LINGUAL_RETRIEVAL | Gold survives pool/filters; lexical and semantic fusion rank remains >10 (ranking cause provisional) | OTHER: gold distinguishes a year absent from raw product names |
| D024 | 쟈도르 오 드 퍼퓸 | ["쟈도르"] | J'adore | 11.0000 | 2.0000 | 71.0000 | CROSS_LINGUAL_RETRIEVAL | Gold survives pool/filters; lexical and semantic fusion rank remains >10 (ranking cause provisional) |  |
| D025 | 샹스 오 비브 오 드 뚜왈렛 | ["샹스 오 비브"] | Chance Eau Vive | 13.0000 | 4.0000 | 50.0000 | CROSS_LINGUAL_RETRIEVAL | Gold survives pool/filters; lexical and semantic fusion rank remains >10 (ranking cause provisional) |  |
| D026 | 오 드 퍼퓸 페더 10ml | ["페더"] | Feather | — | — | — | BRAND_RESOLUTION | Gold brand outside bounded brand pool |  |
| D028 | 옴므 코롱 | ["옴므"] | Dior Homme Cologne 2022 | 58.0000 | 21.0000 | 168.0000 | CROSS_LINGUAL_RETRIEVAL | Gold survives pool/filters; lexical and semantic fusion rank remains >10 (ranking cause provisional) | OTHER: gold distinguishes a year absent from raw product names |
| D029 | 시그니처 EDP | ["시그니처"] | Chloé Eau de Parfum | 37.0000 | 52.0000 | 25.0000 | CROSS_LINGUAL_RETRIEVAL | Gold survives pool/filters; lexical and semantic fusion rank remains >10 (ranking cause provisional) |  |
| D030 | 랄프로렌 폴로 랄프 EDT 30ml,50ml 단품/기획 중 택 1 | ["폴로 랄프 , / 중"] | Polo | 33.0000 | 16.0000 | 78.0000 | CROSS_LINGUAL_RETRIEVAL | Gold survives pool/filters; lexical and semantic fusion rank remains >10 (ranking cause provisional) | NORMALIZATION: possible unparsed concentration/package residue in core |
| D032 | 리플레이 소스 오브 라이프 포 맨 오드뚜왈렛 30ml  /  [리플레이] 소스 오브 라이프 포 맨 오드뚜왈렛 100ml | ["리플레이 소스 오브 라이프 포 맨"] | Source of Life Man | 34.0000 | 34.0000 | 32.0000 | CROSS_LINGUAL_RETRIEVAL | Gold survives pool/filters; lexical and semantic fusion rank remains >10 (ranking cause provisional) |  |
| D037 | [엔믹스규진PICK] 에틀리에 오 드 퍼퓸 트와일라잇블룸 30ml/10ml | ["트와일라잇블룸"] | Etlee Twilight Bloom | — | — | — | OTHER | Gold ID absent from local catalog |  |
| D038 | 피코 디 아말피 오 드 뜨왈렛 | ["피코 디 아말피 오 드 뜨왈렛"] | Acqua di Parma Blu Mediterraneo - Fico di Amalfi | 65.0000 | 54.0000 | 55.0000 | CROSS_LINGUAL_RETRIEVAL | Gold survives pool/filters; lexical and semantic fusion rank remains >10 (ranking cause provisional) | NORMALIZATION: possible unparsed concentration/package residue in core |
| D039 | 끌로에 나츄렐 EDP 30ml/50ml | ["나츄렐"] | Chloé Eau de Parfum Naturelle | 55.0000 | 36.0000 | 65.0000 | CROSS_LINGUAL_RETRIEVAL | Gold survives pool/filters; lexical and semantic fusion rank remains >10 (ranking cause provisional) |  |
| D042 | 퍼퓸 솝클린솝 50ml | ["솝클린솝"] | Soap Clean Soap | — | — | — | BRAND_RESOLUTION | Gold brand outside bounded brand pool |  |
| D043 | 오리지널 머스크 향수 | ["오리지널 머스크"] | Original Musk | — | — | — | BRAND_RESOLUTION | Gold brand outside bounded brand pool |  |
| D045 | [기획] 알보우 케이스 스터디 EDP 30ml 상탈 블루 (+핸드크림) | ["케이스 스터디 상탈 블루"] | Santal Bleu | — | — | — | BRAND_RESOLUTION | Gold brand outside bounded brand pool |  |
| D047 | 미스 디올 블루밍 부케 오 드 뚜왈렛 | ["미스 디올 블루밍 부케"] | Miss Dior Blooming Bouquet 2023 | 14.0000 | 3.0000 | 140.0000 | CROSS_LINGUAL_RETRIEVAL | Gold survives pool/filters; lexical and semantic fusion rank remains >10 (ranking cause provisional) | OTHER: gold distinguishes a year absent from raw product names |
| D051 | [베르사체] 에로스플레임 오드퍼퓸 100ml (미니어처1종 랜덤증정) | ["베르사체 에로스플레임"] | Eros Flame | 37.0000 | 26.0000 | 46.0000 | CROSS_LINGUAL_RETRIEVAL | Gold survives pool/filters; lexical and semantic fusion rank remains >10 (ranking cause provisional) |  |
| D053 | 피렌체 1221 에디션 로사 가데니아 오드코롱 | ["피렌체 1221 에디션 로사 가데니아"] | Rosa Gardenia | 11.0000 | 2.0000 | 43.0000 | CROSS_LINGUAL_RETRIEVAL | Gold survives pool/filters; lexical and semantic fusion rank remains >10 (ranking cause provisional) |  |
| D054 | [NEW/기획] 아뜰리에페이 퍼퓸 30ml 데이오프  /  데이 오프 | ["데이 오프", "데이오프"] | Day Off | — | — | — | OTHER | Gold ID absent from local catalog |  |
| D056 | [에탄올 FREE] 에이딕트 헤어 퍼퓸 30ml 버베나 레인 (단품/기획) | ["에탄올 FREE 에이딕트 버베나 레인"] | Verbena Rain | — | — | — | CONCENTRATION_OR_FORM_FILTER | FORM |  |
| D058 | 아쿠아 다이브 퍼퓸 50ml  /  아쿠아 다이브 퍼퓸 | ["아쿠아 다이브"] | Acqua Dive | — | — | — | BRAND_RESOLUTION | Gold brand outside bounded brand pool |  |
| D059 | 우먼 EDT 40ML | ["우먼"] | Jimmy Choo Eau de Toilette | 17.0000 | 40.0000 | 5.0000 | CROSS_LINGUAL_RETRIEVAL | Gold survives pool/filters; lexical and semantic fusion rank remains >10 (ranking cause provisional) |  |
| D061 | 레 플레르 드 랑방 블루 오키드 EDT 50ML  /  레 플레르 드 EDT [블루오키드] | ["레 플레르 드 랑방 블루 오키드", "레 플레르 드 블루오키드"] | Blue Orchid | 20.0000 | 2.0000 | 61.0000 | CROSS_LINGUAL_RETRIEVAL | Gold survives pool/filters; lexical and semantic fusion rank remains >10 (ranking cause provisional) |  |
| D063 | [몽탈] 머스크 투 머스크 오드퍼퓸 100ml (바이알 3종) | ["몽탈 머스크 투 머스크"] | Musk to Musk | 11.0000 | 1.0000 | 133.0000 | CROSS_LINGUAL_RETRIEVAL | Gold survives pool/filters; lexical and semantic fusion rank remains >10 (ranking cause provisional) |  |
| D066 | 익스플로러 EDP 100ML  /  익스플로러 EDP 30ML  /  익스플로러 EDP 60ML  /  몽블랑 익스플로러 EDP (30ml/60ml/100ml)  /  몽블랑 익스플로러 EDP 100ml  /  몽블랑 익스플로러 EDP 30ml  /  익스플로러 오 드 퍼퓸 | ["익스플로러"] | Explorer | 18.0000 | 1.0000 | 95.0000 | CROSS_LINGUAL_RETRIEVAL | Gold survives pool/filters; lexical and semantic fusion rank remains >10 (ranking cause provisional) |  |
| D071 | [만세라] 프렌치 리비에라 오드퍼퓸 120ml (바이알 3종) | ["만세라 프렌치 리비에라"] | French Riviera | 27.0000 | 1.0000 | 196.0000 | CROSS_LINGUAL_RETRIEVAL | Gold survives pool/filters; lexical and semantic fusion rank remains >10 (ranking cause provisional) |  |
| D073 | 쟈도르 퍼퓸 도 | ["쟈도르 도"] | J'adore Parfum d'Eau | 28.0000 | 6.0000 | 166.0000 | CROSS_LINGUAL_RETRIEVAL | Gold survives pool/filters; lexical and semantic fusion rank remains >10 (ranking cause provisional) |  |
| D075 | 퓨어솝 EDP 60ML  /  퓨어솝 EDP 30ML  /  퓨어솝 EDP | ["퓨어솝"] | Pure Soap | 20.0000 | 1.0000 | 188.0000 | CROSS_LINGUAL_RETRIEVAL | Gold survives pool/filters; lexical and semantic fusion rank remains >10 (ranking cause provisional) |  |
| D077 | [재규어] 이어러 리로디드 오드퍼퓸 100ml | ["재규어 이어러 리로디드"] | Jaguar Era Reloaded | 17.0000 | 1.0000 | 64.0000 | CROSS_LINGUAL_RETRIEVAL | Gold survives pool/filters; lexical and semantic fusion rank remains >10 (ranking cause provisional) |  |
| D078 | 클래식 쿨 코튼 EDP 60ML  /  쿨 코튼 오 드 퍼퓸 | ["쿨 코튼", "클래식 쿨 코튼"] | Cool Cotton | 14.0000 | 1.0000 | 188.0000 | CROSS_LINGUAL_RETRIEVAL | Gold survives pool/filters; lexical and semantic fusion rank remains >10 (ranking cause provisional) |  |

원인별: CROSS_LINGUAL_RETRIEVAL=25, BRAND_RESOLUTION=5, OTHER=2, CONCENTRATION_OR_FORM_FILTER=1

추가 수동 검토 관찰:
- NORMALIZATION: D030에 `, / 중` 패키지 잔여 문구, D038에 `오 드 뜨왈렛` 미인식 농도 표현이 남는다. 초기 실험의 정규화 한계로 보존했으며 DEV를 보고 제품별 수정 규칙을 추가하지 않았다.
- NORMALIZATION: D008은 query에서 앞의 브랜드를 분리해 `포 허`가 되지만 candidate `Narciso Rodriguez For Her`에는 브랜드가 남아 lexical 1→15위로 악화했다. query/candidate 표기의 비대칭과 과도하게 짧은 core도 검토 대상이다.
- OTHER: D016/D028/D047의 Gold는 연도별 identity를 지정하지만 원문에는 해당 연도가 없다. 순위 실패를 cross-lingual 문제만으로 단정할 수 없다.
- BRAND_RESOLUTION: Tenui/Sennok/Kiehl's/RboW/Dashu는 로컬 catalog에 있지만 제한한 브랜드 pool에서 빠졌다. raw 음역 후보의 동점과 다른 철자 때문에 fallback이 정답 브랜드를 보장하지 못했다.
- CONCENTRATION_OR_FORM_FILTER: D056은 query가 HAIR_FRAGRANCE이고 catalog name 기반 판별은 LIQUID_PERFUME이라 기존 형태 필터에서 제외됐다. 형태 필터는 변경하지 않았다.
- OTHER: D037 Etlee Twilight Bloom과 D054 Day Off의 Gold ID는 perfumes.csv에 없다. 현 catalog만으로 이 2개는 retrieval 불가능하다. Gold 61개 분모는 baseline과 동일하게 유지했다.

## 결론 및 한계

DEV 기준 full Method 1은 baseline보다 주요 Recall과 MRR이 하락했다. 이번 전체 조합의 retrieval 개선은 확인되지 않았으며 baseline 교체를 권하지 않는다.
Top10 miss 33개는 MANUAL_CHECK로 남겼고 Gold UNRESOLVED 3개는 계속 제외했다. 구조화 member 중 attribute conflict 표시 0행.
DEV는 개발용 표본이며 일반화 성능이나 최종 MATCH Precision 개선을 입증하지 않는다. NO_MATCH 16개에 대한 거절 성능은 평가하지 않았다. Listwise / Identity-aware Verification은 구현하지 않았다.
일반 다국어 의미 모델은 고유명사 음역, 유사 flankers, 출시 연도와 리포뮬레이션 identity를 보장하지 않는다. 기존 별칭 오류, standalone 프로모션 단어와 실제 이름의 중복, description 농도 추출이 남아 있다.
다음 Verification 구현에 앞서 이번 결과를 검토해야 한다. 구조화 입력과 브랜드 fallback의 일부 복구 효과는 있으나, 현재 모델과 동등 RRF의 결합을 그대로 채택할 근거는 없다.

## 재현 및 검증

- 실행: `venv/Scripts/python.exe evaluate_fragrantica_method1_dev.py` (사전 다운로드 모델 필요, 실행은 offline).
- retrieval 준비/추론 실행시간: 28.23초 (캐시 여부에 따라 달라짐).
- synthetic normalization 보존 검사, DEV 구성/identity/family 관계 검사, baseline Top5/rank 전수 일치, candidate 중복 검사, 입력 파일 SHA-256 불변 검사를 실행했다.
- 실제 최대 query pool 309개; per-brand cap으로 제외된 member별 기록 합계 6개 (중복 member 포함).
- 모델 별도 sanity 실행: `장미 향기`↔`rose fragrance` cosine 0.897, `자동차 엔진`↔`car engine` 0.918. L2 norm 약 1, batch/단일 입력 embedding 일치(atol=1e-5). `쿨 코튼`↔`Cool Cotton`은 0.321로, `Or et Noir`와의 0.537보다 낮았다. 이는 이 샘플의 모델 표현 한계이며 설정 조정에 사용하지 않았다.
- 프로젝트 환경의 pip check: No broken requirements found.
- 새 의존성 sentence-transformers와 CPU torch를 프로젝트 venv에 설치했다. 모델·임베딩 캐시는 gitignore 대상 cache/method1에 둔다.
- sentence-transformers: 6.0.1
- transformers: 5.16.1
- torch: 2.14.0+cpu
- numpy: 2.4.6
- pandas: 3.0.5
- `data\korea_popularity\evaluation\gold_set_dev.csv` SHA-256: `41d5b84b30289dd24d3822c552cc100890d009600aa8a310234b2160ec37ad2f`
- `data\korea_popularity\korea_commercial_identities.csv` SHA-256: `069a30ca2c053ba0222f66aa529996b61ede12df8bb97f743f8c3a2718787588`
- `perfumes.csv` SHA-256: `cec1ea0b498853032bcf44d33ad52ac83e2ed2896b67d5a2765d90a0345cc055`
- `data\korea_popularity\evaluation\fragrantica_matcher_baseline_dev_results.csv` SHA-256: `d8dc3592a5797186349e161ba171d22b28aabdd5601ab5d2c56ab96e2adadb82`
- `data\korea_popularity\evaluation\fragrantica_matcher_baseline_dev_report.md` SHA-256: `ed641b163ff9e27b30cc6f252ddf3b877be02301dcf0650b31f7cdf886b0fe46`
- `build_korea_popularity_map.py` SHA-256: `1b5bd6521706aa9d0c9dfbc42bdd2c995ab308494554a18b43f9699c9581d1bf`
- `evaluate_fragrantica_method1_dev.py` SHA-256: `73c8a16b85714549dc11224a5adc89ee965e3fdd96eb7d75d6f5dadca67f4ce1`
- `evaluate_fragrantica_matcher_dev.py` SHA-256: `da62ca789c2bbbfde846a94e9f3aabed9ce3e0dbb4efd1272c68d9a9a49b2c97`
- `data\korea_popularity\korea_commercial_identity_members.csv` SHA-256: `b27d8c8accccb4afbe513c748a00ed1d1b3479595b054bf42992e7952d0bcf74`
- `data\korea_popularity\korea_candidate_families.csv` SHA-256: `b853a639e9d707ac03e25e012cb16cf184703f56fa27c1c5d475e828debf749d`

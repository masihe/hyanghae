# Method 2: independent pronunciation/transliteration DEV retrieval

## 실측 결론과 음역 품질 수동 검토

이 절은 고정 설정 실험이 끝난 뒤 결과를 읽고 작성한 해석이다. 아래 사례·ID·평가를 retrieval 규칙, 모델 입력 예외 또는 parameter 조정에 사용하지 않았다.

- en→ko는 전체 R@5 0.5902→0.6721, MRR 0.4451→0.5590으로 개선됐다. Top5 rescue 10개/회귀 5개, Top10 rescue 7개/회귀 3개다. 다음 단계의 **보완 후보 채널로 en→ko를 우선 검토할 근거가 있다.** baseline 자동 교체나 최종 MATCH 판정 채택의 근거로 확대하지 않는다.
- uroman은 R@5 0.6066, MRR 0.4665로 소폭 개선됐지만 Top5 rescue 7개/회귀 6개로 순증은 1개다. Representative R@5는 0.5455→0.4848로 악화했고, Challenge는 0.6429→0.7500으로 개선됐다. 전체 평균만으로 일괄 채택하기 어렵다.
- en→ko의 R@5는 Representative 0.5455→0.6667, Challenge 0.6429→0.6786으로 두 그룹에서 개선됐다. 다만 Challenge의 Top5 rescue 5개 중 4개가 다른 기존 적중의 회귀로 상쇄됐다.
- Top5 rescue 중 두 새 채널의 공통 사례는 5개다. uroman만 복구한 사례는 D016/D028 2개, en→ko만 복구한 사례는 D001/D038/D051/D061/D072 5개다. Top10에서는 uroman만 D028, en→ko만 D030을 복구했다. 이는 개별 채널의 rescue 집합 비교이며 결합 ranking이나 fusion 성능은 만들지 않았다.
- 공통 후보군 안에 정답이 있는 MATCH는 51개다. catalog에 있는 59개 중 7개는 브랜드 blocking, 1개는 기존 형태/농도 필터에서 빠진다. 따라서 catalog 기준 지표도 이 필터의 한계를 포함한다. CATALOG_MISSING 2개(D037 139311, D054 135133)는 Gold를 고치지 않고 별도 표시했다.

### 잘 맞은 출력과 잘못되거나 불완전한 출력

| DEV | 실제 candidate core | 실제 한국어 출력 | 국내 query core | baseline→enko 순위 | 관찰 |
|---|---|---|---|---|---|
| D078 | Cool Cotton | 쿨 코튼 | ["쿨 코튼", "클래식 쿨 코튼"] | 2→1 | 국내 core와 잘 일치 |
| D061 | Blue Orchid | 블루 오키드 | ["레 플레르 드 랑방 블루 오키드", "레 플레르 드 블루오키드"] | 7→1 | 국내 핵심 이름과 잘 일치 |
| D051 | Eros Flame | 에로스 플레임 | ["베르사체 에로스플레임"] | 6→1 | 국내 핵심 이름과 잘 일치 |
| D066 | Explorer | 익스플로러 | ["익스플로러"] | 1→1 | 국내 core와 잘 일치 |
| D004 | Soft Laundry | 소프트라이닝 | ["클래식 소프트 런드리"] | 2→9 | Laundry가 라이닝으로 변형 |
| D024 | J'adore | 조도어 | ["쟈도르"] | 2→16 | 국내 쟈도르와 다른 음역 |
| D075 | Pure Soap | 순수 소프 | ["퓨어솝"] | 1→24 | Pure를 음역하지 않고 순수로 의미 번역 |
| D073 | J'adore Parfum d'Eau | 바르퓌르 | ["쟈도르 도"] | 4→124 | J'adore 등 주요 이름이 출력에서 누락 |
| D028 | Homme 2022 | 호머윈드 | ["옴므"] | 12→73 | Homme와 연도 2022가 부정확한 문자열로 변형 |
| D038 | Blu Mediterraneo - Fico di Amalfi | 블루 미켈란젤로-피코 디알마드레 | ["피코 디 아말피 오 드 뜨왈렛"] | 46→3 | 이탈리아어 계열 긴 이름의 일부가 미켈란젤로/디알마드레로 변형 |
| D072 | Hacivat | 하시빗 | ["니샤네 하지밧 바이알3종"] | 7→4 | 국내 하지밧과 하시빗 차이; 부분 일치에도 4위 |

### 비영어권 이름과 생성 실패에서 관찰된 한계

- 프랑스어 계열 이름에서 J'adore, Homme, Naturelle 등의 원어 발음과 국내 표기가 영어 모델 출력과 어긋났다. Blanche→블랜치, Naturelle→네이텔처럼 국내 블랑쉬/나츄렐과 달라도 좁은 후보군에서는 각각 2위/1위가 될 수 있다. **좋은 retrieval rank가 올바른 음역을 보장하지 않는다.**
- 이탈리아어 계열 Blu Mediterraneo - Fico di Amalfi는 블루 미켈란젤로-피코 디알마드레로 왜곡됐지만 정답 순위가 46→3위로 개선됐다. 이 사례 역시 name 변환 품질과 후보 순위 개선을 구분해서 봐야 한다.
- 숫자/연도는 음역 과정에서 보존되지 않을 수 있다. Homme 2022→호머윈드, Miss Dior 2021→미스 디오르옹처럼 identity 구분 정보가 사라지거나 다른 음절로 바뀌었다. 원문 candidate ID·name·core는 결과에서 별도로 유지한다.
- Jimmy Choo Exotic (2015)의 core Exotic 2015는 반복 출력을 생성하며 길이 64에 도달했다. 해당 후보 ID 29880은 MAX_LENGTH_REACHED로 표시하고 출력 그대로 캐시·평가했다. 재생성하거나 더 좋은 출력을 골라 쓰지 않았다. 현재 전체 후보 ID 중 1개이며 수동 검토가 필요하다.
- uroman은 발음 사전이나 영어 철자 역변환기가 아니다. 쿨 코튼→kul koteun, 리브르→ribeureu처럼 공통 Latin 표기는 만들지만 Cool Cotton/Libre와 같은 철자를 보장하지 않는다. 또한 series/브랜드/패키지 잔여 문구가 긴 query에서는 전체 문자열 유사도가 약해질 수 있다.
- query에 남은 피렌체 1221 에디션, 바이알3종, 레 플레르 드 같은 표현과 원문에 없는 연도 정보 등은 이번 고정 normalizer의 한계로 남겼다. 이번 결과를 보고 제거 사전이나 제품별 예외를 추가하지 않았다.

### 검토 결론

en→ko는 이 DEV에서 baseline 실패를 독립적으로 보완할 가치가 확인됐고, uroman도 소수의 고유한 rescue를 제공했다. 다음 채널 선정에서는 en→ko를 우선 후보로 두되, 프랑스어/이탈리아어·숫자·부분 의미 번역에 대한 실패를 함께 고려해야 한다. 현재 단계에서는 어떤 fusion이나 Verification도 구현하지 않았다.


## 설계와 범위

- DEV 80행 중 eligible 77 identity를 실행했다. 지표는 Gold MATCH 61개만 평가하며 NO_MATCH 16개/UNRESOLVED 3개는 Recall·MRR 분모에서 제외했다. TEST는 열지 않았다.
- 전체 MATCH 61개와 catalog-retrievable 59개 두 분모를 보고한다. catalog-retrievable은 Gold ID가 perfumes.csv에 존재한다는 뜻이며 브랜드/필터를 통과한다는 뜻은 아니다.
- 세 방법의 후보 ID 집합은 각 identity마다 정확히 같다. 기존 exact brand blocking과 Commercial Identity의 기존 형태/농도 필터를 그대로 재사용한다. Method 1의 soft brand fallback은 사용하지 않는다. 후보 Top5로 미리 자르지 않는다.
- baseline은 기존 retrieve_candidates를 재실행해 저장된 77개 Top5와 Gold rank 전수 일치를 검증했다. baseline 문자열/점수식을 그대로 유지했다.
- B/C는 Method 1 structured normalize를 raw member query와 candidate name 양쪽에 적용한다. 같은 완전 접두 브랜드 제거·농도/형태/패키지 분리 규칙을 적용하고 원래 이름을 함께 보존한다. 검증된 원본 identity나 family는 수정/병합하지 않는다.
- B: uroman 기본 언어 자동 처리로 양쪽 core를 Latin 문자열로 변환한 후 casefold·공백/구두점 제외, SequenceMatcher ratio(autojunk=False) 하나로 정렬한다. 기존 phonetic 최대값이나 baseline ranking을 합치지 않는다.
- C: 후보 core 전체를 영어→한국어 모델에 입력한다. query는 한국어 core를 그대로 쓴다. 양쪽을 Unicode NFD 자모로 분해하고 알파벳/숫자/자모만 남긴 뒤 B와 동일한 문자열 비교식을 적용한다.
- 자모 단위를 선택한 이유: 한 음절의 모음/받침이 달라도 같은 초성 등 부분 일치를 반영할 수 있다. 표준 Unicode 분해만 쓰며 발음 동화·초종성 통합·추가 자모 라이브러리·음절 점수와의 혼합은 없다.
- 여러 member core는 채널 내부에서 최대 유사도를 사용한다. 동점은 Fragrantica ID 내림차순. ML 학습·threshold·제품명 예외·Gold alias·RRF·weighted fusion·DEV parameter sweep 없음.
- A 대비 B/C 차이에는 구조화 정규화와 점수식 차이도 포함된다. 순수 모델 효과만 분리한 ablation은 아니다. B와 C는 같은 core·pool·문자열 비교식에 기반하지만 representation이 다르다.
- MRR은 공통 전체 후보군 내 정답 순위 역수(미검색=0). MRR@10도 제공한다. rescue는 baseline 밖→새 방법 안, regression은 baseline 안→새 방법 밖이며 각 K에서 독립적으로 집계한다.

## 모델 및 실행 설정

- 모델 `feVeRin/enko-transliterator`, revision `24b55c9bb8ab1f8682f8d8300c57340e2e0bcd66`. 해당 snapshot의 Marian base 가중치와 LoRA adapter를 한 번씩 로드한다. adapter가 참조하는 다른 repo로 자동 이동하지 않는다. adapter 병합/학습 없음.
- 공개 wrapper의 beam 3, max_length 64를 사용하고 샘플링만 끈다(do_sample=False). CPU float32, seed 42, batch 16, threads 4, deterministic algorithms. sentence 전체 생성 1개만 사용하고 후보별 최적 출력 선택을 하지 않는다.
- 모델 API smoke test에서 공개 예제 `LORA IS ALL YOU NEED` → `로라 이즈 올 유 니드`가 실행됐다. 후보/Gold를 보고 decoding을 조정하지 않았다.
- 캐시는 exact core + 모델 revision + decoding 설정 + 라이브러리 버전으로 분리한다. 동일 core는 한 번만 생성한다. generation 실패/길이 한도/빈 출력은 보존·표시하며 원문으로 조용히 복구하지 않는다.
- 비ASCII/비영어 이름도 철자를 그대로 넣는다. uroman을 앞단에 붙이지 않는다. French/Italian/Turkish/조어의 원어 발음, 관용 한국어 표기, 혼합언어 query는 영어 전용 모델의 보장 범위가 아니다.
- [uroman 공식 문서](https://github.com/isi-nlp/uroman) · [enko 모델](https://huggingface.co/feVeRin/enko-transliterator) · [공개 추론 구현](https://github.com/feVeRin/enko_transliterator/blob/main/transliteration.py)

## ALL_GOLD_MATCH: 전체 성능

| method | group | gold_match | recall_at_1 | recall_at_3 | recall_at_5 | recall_at_10 | mrr | mrr_at_10 | top5_miss | top10_miss |
|---|---|---|---|---|---|---|---|---|---|---|
| baseline_lexical | ALL | 61 | 0.3115 | 0.5082 | 0.5902 | 0.6721 | 0.4451 | 0.4361 | 25 | 20 |
| uroman | ALL | 61 | 0.3443 | 0.5410 | 0.6066 | 0.6885 | 0.4665 | 0.4594 | 24 | 19 |
| enko_transliteration | ALL | 61 | 0.4590 | 0.6230 | 0.6721 | 0.7377 | 0.5590 | 0.5559 | 20 | 16 |

### Representative / Challenge

| method | group | gold_match | recall_at_1 | recall_at_3 | recall_at_5 | recall_at_10 | mrr | mrr_at_10 | top5_miss | top10_miss |
|---|---|---|---|---|---|---|---|---|---|---|
| baseline_lexical | CHALLENGE | 28 | 0.2857 | 0.5000 | 0.6429 | 0.7143 | 0.4424 | 0.4310 | 10 | 8 |
| baseline_lexical | REPRESENTATIVE | 33 | 0.3333 | 0.5152 | 0.5455 | 0.6364 | 0.4473 | 0.4405 | 15 | 12 |
| uroman | CHALLENGE | 28 | 0.3214 | 0.6071 | 0.7500 | 0.8571 | 0.4944 | 0.4908 | 7 | 4 |
| uroman | REPRESENTATIVE | 33 | 0.3636 | 0.4848 | 0.4848 | 0.5455 | 0.4429 | 0.4327 | 17 | 15 |
| enko_transliteration | CHALLENGE | 28 | 0.4286 | 0.6071 | 0.6786 | 0.7500 | 0.5452 | 0.5390 | 9 | 7 |
| enko_transliteration | REPRESENTATIVE | 33 | 0.4848 | 0.6364 | 0.6667 | 0.7273 | 0.5708 | 0.5703 | 11 | 9 |

### Rescue / Regression

| method | group | gold_match | baseline_top5_miss | rescue_at_5 | baseline_top5_hit | regression_at_5 | baseline_top10_miss | rescue_at_10 | baseline_top10_hit | regression_at_10 |
|---|---|---|---|---|---|---|---|---|---|---|
| baseline_lexical | ALL | 61 | 25 | 0 | 36 | 0 | 20 | 0 | 41 | 0 |
| baseline_lexical | CHALLENGE | 28 | 10 | 0 | 18 | 0 | 8 | 0 | 20 | 0 |
| baseline_lexical | REPRESENTATIVE | 33 | 15 | 0 | 18 | 0 | 12 | 0 | 21 | 0 |
| uroman | ALL | 61 | 25 | 7 | 36 | 6 | 20 | 7 | 41 | 6 |
| uroman | CHALLENGE | 28 | 10 | 6 | 18 | 3 | 8 | 5 | 20 | 1 |
| uroman | REPRESENTATIVE | 33 | 15 | 1 | 18 | 3 | 12 | 2 | 21 | 5 |
| enko_transliteration | ALL | 61 | 25 | 10 | 36 | 5 | 20 | 7 | 41 | 3 |
| enko_transliteration | CHALLENGE | 28 | 10 | 5 | 18 | 4 | 8 | 4 | 20 | 3 |
| enko_transliteration | REPRESENTATIVE | 33 | 15 | 5 | 18 | 1 | 12 | 3 | 21 | 0 |

### Challenge type별 성능

| method | group | gold_match | recall_at_1 | recall_at_3 | recall_at_5 | recall_at_10 | mrr | mrr_at_10 | top5_miss | top10_miss |
|---|---|---|---|---|---|---|---|---|---|---|
| baseline_lexical | FAMILY_VARIANT_RISK | 4 | 0.5000 | 0.5000 | 0.5000 | 0.7500 | 0.5417 | 0.5417 | 2 | 1 |
| baseline_lexical | FUZZY_AUTO_MATCH_RISK | 10 | 0.4000 | 0.8000 | 0.8000 | 0.8000 | 0.5957 | 0.5833 | 2 | 2 |
| baseline_lexical | MATCH_REVIEW | 6 | 0.0000 | 0.1667 | 0.5000 | 0.6667 | 0.2049 | 0.1861 | 3 | 2 |
| baseline_lexical | NORMALIZATION_RISK | 2 | 0.5000 | 0.5000 | 0.5000 | 0.5000 | 0.5000 | 0.5000 | 1 | 1 |
| baseline_lexical | NO_MATCH_CROSSLINGUAL | 6 | 0.1667 | 0.3333 | 0.6667 | 0.6667 | 0.3390 | 0.3250 | 2 | 2 |
| uroman | FAMILY_VARIANT_RISK | 4 | 0.5000 | 0.7500 | 0.7500 | 0.7500 | 0.6250 | 0.6250 | 1 | 1 |
| uroman | FUZZY_AUTO_MATCH_RISK | 10 | 0.4000 | 0.8000 | 0.9000 | 0.9000 | 0.5650 | 0.5583 | 1 | 1 |
| uroman | MATCH_REVIEW | 6 | 0.1667 | 0.3333 | 0.6667 | 1.0000 | 0.3849 | 0.3849 | 2 | 0 |
| uroman | NORMALIZATION_RISK | 2 | 0.0000 | 0.0000 | 0.5000 | 0.5000 | 0.1250 | 0.1250 | 1 | 1 |
| uroman | NO_MATCH_CROSSLINGUAL | 6 | 0.3333 | 0.6667 | 0.6667 | 0.8333 | 0.5222 | 0.5167 | 2 | 1 |
| enko_transliteration | FAMILY_VARIANT_RISK | 4 | 0.5000 | 0.7500 | 0.7500 | 0.7500 | 0.6250 | 0.6250 | 1 | 1 |
| enko_transliteration | FUZZY_AUTO_MATCH_RISK | 10 | 0.5000 | 0.6000 | 0.6000 | 0.8000 | 0.5897 | 0.5810 | 4 | 2 |
| enko_transliteration | MATCH_REVIEW | 6 | 0.0000 | 0.3333 | 0.5000 | 0.5000 | 0.2224 | 0.2083 | 3 | 3 |
| enko_transliteration | NORMALIZATION_RISK | 2 | 0.5000 | 0.5000 | 0.5000 | 0.5000 | 0.5000 | 0.5000 | 1 | 1 |
| enko_transliteration | NO_MATCH_CROSSLINGUAL | 6 | 0.6667 | 0.8333 | 1.0000 | 1.0000 | 0.7556 | 0.7556 | 0 | 0 |

### Challenge type별 Rescue / Regression

| method | group | gold_match | baseline_top5_miss | rescue_at_5 | baseline_top5_hit | regression_at_5 | baseline_top10_miss | rescue_at_10 | baseline_top10_hit | regression_at_10 |
|---|---|---|---|---|---|---|---|---|---|---|
| baseline_lexical | FAMILY_VARIANT_RISK | 4 | 2 | 0 | 2 | 0 | 1 | 0 | 3 | 0 |
| baseline_lexical | FUZZY_AUTO_MATCH_RISK | 10 | 2 | 0 | 8 | 0 | 2 | 0 | 8 | 0 |
| baseline_lexical | MATCH_REVIEW | 6 | 3 | 0 | 3 | 0 | 2 | 0 | 4 | 0 |
| baseline_lexical | NORMALIZATION_RISK | 2 | 1 | 0 | 1 | 0 | 1 | 0 | 1 | 0 |
| baseline_lexical | NO_MATCH_CROSSLINGUAL | 6 | 2 | 0 | 4 | 0 | 2 | 0 | 4 | 0 |
| uroman | FAMILY_VARIANT_RISK | 4 | 2 | 1 | 2 | 0 | 1 | 0 | 3 | 0 |
| uroman | FUZZY_AUTO_MATCH_RISK | 10 | 2 | 1 | 8 | 0 | 2 | 1 | 8 | 0 |
| uroman | MATCH_REVIEW | 6 | 3 | 3 | 3 | 2 | 2 | 2 | 4 | 0 |
| uroman | NORMALIZATION_RISK | 2 | 1 | 0 | 1 | 0 | 1 | 0 | 1 | 0 |
| uroman | NO_MATCH_CROSSLINGUAL | 6 | 2 | 1 | 4 | 1 | 2 | 2 | 4 | 1 |
| enko_transliteration | FAMILY_VARIANT_RISK | 4 | 2 | 1 | 2 | 0 | 1 | 0 | 3 | 0 |
| enko_transliteration | FUZZY_AUTO_MATCH_RISK | 10 | 2 | 0 | 8 | 2 | 2 | 1 | 8 | 1 |
| enko_transliteration | MATCH_REVIEW | 6 | 3 | 2 | 3 | 2 | 2 | 1 | 4 | 2 |
| enko_transliteration | NORMALIZATION_RISK | 2 | 1 | 0 | 1 | 0 | 1 | 0 | 1 | 0 |
| enko_transliteration | NO_MATCH_CROSSLINGUAL | 6 | 2 | 2 | 4 | 0 | 2 | 2 | 4 | 0 |

## CATALOG_RETRIEVABLE: 전체 성능

| method | group | gold_match | recall_at_1 | recall_at_3 | recall_at_5 | recall_at_10 | mrr | mrr_at_10 | top5_miss | top10_miss |
|---|---|---|---|---|---|---|---|---|---|---|
| baseline_lexical | ALL | 59 | 0.3220 | 0.5254 | 0.6102 | 0.6949 | 0.4601 | 0.4509 | 23 | 18 |
| uroman | ALL | 59 | 0.3559 | 0.5593 | 0.6271 | 0.7119 | 0.4824 | 0.4749 | 22 | 17 |
| enko_transliteration | ALL | 59 | 0.4746 | 0.6441 | 0.6949 | 0.7627 | 0.5780 | 0.5748 | 18 | 14 |

### Representative / Challenge

| method | group | gold_match | recall_at_1 | recall_at_3 | recall_at_5 | recall_at_10 | mrr | mrr_at_10 | top5_miss | top10_miss |
|---|---|---|---|---|---|---|---|---|---|---|
| baseline_lexical | CHALLENGE | 27 | 0.2963 | 0.5185 | 0.6667 | 0.7407 | 0.4588 | 0.4469 | 9 | 7 |
| baseline_lexical | REPRESENTATIVE | 32 | 0.3438 | 0.5312 | 0.5625 | 0.6562 | 0.4613 | 0.4542 | 14 | 11 |
| uroman | CHALLENGE | 27 | 0.3333 | 0.6296 | 0.7778 | 0.8889 | 0.5127 | 0.5090 | 6 | 3 |
| uroman | REPRESENTATIVE | 32 | 0.3750 | 0.5000 | 0.5000 | 0.5625 | 0.4568 | 0.4462 | 16 | 14 |
| enko_transliteration | CHALLENGE | 27 | 0.4444 | 0.6296 | 0.7037 | 0.7778 | 0.5653 | 0.5590 | 8 | 6 |
| enko_transliteration | REPRESENTATIVE | 32 | 0.5000 | 0.6562 | 0.6875 | 0.7500 | 0.5887 | 0.5881 | 10 | 8 |

### Rescue / Regression

| method | group | gold_match | baseline_top5_miss | rescue_at_5 | baseline_top5_hit | regression_at_5 | baseline_top10_miss | rescue_at_10 | baseline_top10_hit | regression_at_10 |
|---|---|---|---|---|---|---|---|---|---|---|
| baseline_lexical | ALL | 59 | 23 | 0 | 36 | 0 | 18 | 0 | 41 | 0 |
| baseline_lexical | CHALLENGE | 27 | 9 | 0 | 18 | 0 | 7 | 0 | 20 | 0 |
| baseline_lexical | REPRESENTATIVE | 32 | 14 | 0 | 18 | 0 | 11 | 0 | 21 | 0 |
| uroman | ALL | 59 | 23 | 7 | 36 | 6 | 18 | 7 | 41 | 6 |
| uroman | CHALLENGE | 27 | 9 | 6 | 18 | 3 | 7 | 5 | 20 | 1 |
| uroman | REPRESENTATIVE | 32 | 14 | 1 | 18 | 3 | 11 | 2 | 21 | 5 |
| enko_transliteration | ALL | 59 | 23 | 10 | 36 | 5 | 18 | 7 | 41 | 3 |
| enko_transliteration | CHALLENGE | 27 | 9 | 5 | 18 | 4 | 7 | 4 | 20 | 3 |
| enko_transliteration | REPRESENTATIVE | 32 | 14 | 5 | 18 | 1 | 11 | 3 | 21 | 0 |

### Challenge type별 성능

| method | group | gold_match | recall_at_1 | recall_at_3 | recall_at_5 | recall_at_10 | mrr | mrr_at_10 | top5_miss | top10_miss |
|---|---|---|---|---|---|---|---|---|---|---|
| baseline_lexical | FAMILY_VARIANT_RISK | 4 | 0.5000 | 0.5000 | 0.5000 | 0.7500 | 0.5417 | 0.5417 | 2 | 1 |
| baseline_lexical | FUZZY_AUTO_MATCH_RISK | 10 | 0.4000 | 0.8000 | 0.8000 | 0.8000 | 0.5957 | 0.5833 | 2 | 2 |
| baseline_lexical | MATCH_REVIEW | 6 | 0.0000 | 0.1667 | 0.5000 | 0.6667 | 0.2049 | 0.1861 | 3 | 2 |
| baseline_lexical | NORMALIZATION_RISK | 1 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0 | 0 |
| baseline_lexical | NO_MATCH_CROSSLINGUAL | 6 | 0.1667 | 0.3333 | 0.6667 | 0.6667 | 0.3390 | 0.3250 | 2 | 2 |
| uroman | FAMILY_VARIANT_RISK | 4 | 0.5000 | 0.7500 | 0.7500 | 0.7500 | 0.6250 | 0.6250 | 1 | 1 |
| uroman | FUZZY_AUTO_MATCH_RISK | 10 | 0.4000 | 0.8000 | 0.9000 | 0.9000 | 0.5650 | 0.5583 | 1 | 1 |
| uroman | MATCH_REVIEW | 6 | 0.1667 | 0.3333 | 0.6667 | 1.0000 | 0.3849 | 0.3849 | 2 | 0 |
| uroman | NORMALIZATION_RISK | 1 | 0.0000 | 0.0000 | 1.0000 | 1.0000 | 0.2500 | 0.2500 | 0 | 0 |
| uroman | NO_MATCH_CROSSLINGUAL | 6 | 0.3333 | 0.6667 | 0.6667 | 0.8333 | 0.5222 | 0.5167 | 2 | 1 |
| enko_transliteration | FAMILY_VARIANT_RISK | 4 | 0.5000 | 0.7500 | 0.7500 | 0.7500 | 0.6250 | 0.6250 | 1 | 1 |
| enko_transliteration | FUZZY_AUTO_MATCH_RISK | 10 | 0.5000 | 0.6000 | 0.6000 | 0.8000 | 0.5897 | 0.5810 | 4 | 2 |
| enko_transliteration | MATCH_REVIEW | 6 | 0.0000 | 0.3333 | 0.5000 | 0.5000 | 0.2224 | 0.2083 | 3 | 3 |
| enko_transliteration | NORMALIZATION_RISK | 1 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0 | 0 |
| enko_transliteration | NO_MATCH_CROSSLINGUAL | 6 | 0.6667 | 0.8333 | 1.0000 | 1.0000 | 0.7556 | 0.7556 | 0 | 0 |

### Challenge type별 Rescue / Regression

| method | group | gold_match | baseline_top5_miss | rescue_at_5 | baseline_top5_hit | regression_at_5 | baseline_top10_miss | rescue_at_10 | baseline_top10_hit | regression_at_10 |
|---|---|---|---|---|---|---|---|---|---|---|
| baseline_lexical | FAMILY_VARIANT_RISK | 4 | 2 | 0 | 2 | 0 | 1 | 0 | 3 | 0 |
| baseline_lexical | FUZZY_AUTO_MATCH_RISK | 10 | 2 | 0 | 8 | 0 | 2 | 0 | 8 | 0 |
| baseline_lexical | MATCH_REVIEW | 6 | 3 | 0 | 3 | 0 | 2 | 0 | 4 | 0 |
| baseline_lexical | NORMALIZATION_RISK | 1 | 0 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| baseline_lexical | NO_MATCH_CROSSLINGUAL | 6 | 2 | 0 | 4 | 0 | 2 | 0 | 4 | 0 |
| uroman | FAMILY_VARIANT_RISK | 4 | 2 | 1 | 2 | 0 | 1 | 0 | 3 | 0 |
| uroman | FUZZY_AUTO_MATCH_RISK | 10 | 2 | 1 | 8 | 0 | 2 | 1 | 8 | 0 |
| uroman | MATCH_REVIEW | 6 | 3 | 3 | 3 | 2 | 2 | 2 | 4 | 0 |
| uroman | NORMALIZATION_RISK | 1 | 0 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| uroman | NO_MATCH_CROSSLINGUAL | 6 | 2 | 1 | 4 | 1 | 2 | 2 | 4 | 1 |
| enko_transliteration | FAMILY_VARIANT_RISK | 4 | 2 | 1 | 2 | 0 | 1 | 0 | 3 | 0 |
| enko_transliteration | FUZZY_AUTO_MATCH_RISK | 10 | 2 | 0 | 8 | 2 | 2 | 1 | 8 | 1 |
| enko_transliteration | MATCH_REVIEW | 6 | 3 | 2 | 3 | 2 | 2 | 1 | 4 | 2 |
| enko_transliteration | NORMALIZATION_RISK | 1 | 0 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| enko_transliteration | NO_MATCH_CROSSLINGUAL | 6 | 2 | 2 | 4 | 0 | 2 | 2 | 4 | 0 |

## Catalog 및 공통 후보 범위 한계

| queue_id | gold_fragrantica_id | gold_fragrantica_name | catalog_status |
|---|---|---|---|
| D037 | 139311.0000 | Etlee Twilight Bloom | CATALOG_MISSING |
| D054 | 135133.0000 | Day Off | CATALOG_MISSING |

공통 pool 상태: IN_CANDIDATE_POOL=51, BRAND_BLOCKED=7, CATALOG_MISSING=2, CONCENTRATION_OR_FORM_FILTER=1
이 상태는 방법 간 동일하다. CATALOG_MISSING을 NO_MATCH로 재라벨링하지 않았으며, 브랜드/필터에서 빠진 정답은 이번 이름 ranking 실험으로 복구할 수 없다.

## uroman: 개선 사례

| queue_id | query_cores | gold_fragrantica_name | gold_uroman | gold_transliteration | baseline_rank | gold_candidate_rank |
|---|---|---|---|---|---|---|
| D038 | ["피코 디 아말피 오 드 뜨왈렛"] | Acqua di Parma Blu Mediterraneo - Fico di Amalfi | Blu Mediterraneo - Fico di Amalfi | 블루 미켈란젤로-피코 디알마드레 | 46.0000 | 10.0000 |
| D007 | ["레드 로즈"] | Red Roses | Red Roses | 레드로즈 | 34.0000 | 2.0000 |
| D016 | ["미스 디올"] | Miss Dior Eau de Parfum (2021) | Miss Dior 2021 | 미스 디오르옹 | 19.0000 | 3.0000 |
| D021 | ["리브르"] | Libre | Libre | 리브어 | 16.0000 | 2.0000 |
| D001 | ["피렌체 1221 에디션 프리지아"] | Fresia | Fresia | 프레시아 | 22.0000 | 9.0000 |
| D039 | ["나츄렐"] | Chloé Eau de Parfum Naturelle | Naturelle | 네이텔 | 13.0000 | 1.0000 |
| D028 | ["옴므"] | Dior Homme Cologne 2022 | Homme 2022 | 호머윈드 | 12.0000 | 4.0000 |
| D022 | ["르 셀 디세이", "르셀디세이"] | Le Sel D'Issey Eau de Parfum | Le Sel D'Issey | 르 셀 디세 | 6.0000 | 1.0000 |
| D013 | ["블랑쉬"] | Blanche | Blanche | 블랜치 | 6.0000 | 4.0000 |

### uroman: 회귀 사례

| queue_id | query_cores | gold_fragrantica_name | gold_uroman | gold_transliteration | baseline_rank | gold_candidate_rank |
|---|---|---|---|---|---|---|
| D061 | ["레 플레르 드 랑방 블루 오키드", "레 플레르 드 블루오키드"] | Blue Orchid | Blue Orchid | 블루 오키드 | 7.0000 | 47.0000 |
| D063 | ["몽탈 머스크 투 머스크"] | Musk to Musk | Musk to Musk | 머스크투머스 | 1.0000 | 34.0000 |
| D011 | ["레 플레르 드 랑방 워터 릴리", "레 플레르 드 워터릴리"] | Water Lily | Water Lily | 워터 릴리 | 5.0000 | 30.0000 |
| D004 | ["클래식 소프트 런드리"] | Soft Laundry | Soft Laundry | 소프트라이닝 | 2.0000 | 17.0000 |
| D051 | ["베르사체 에로스플레임"] | Eros Flame | Eros Flame | 에로스 플레임 | 6.0000 | 16.0000 |
| D032 | ["리플레이 소스 오브 라이프 포 맨"] | Source of Life Man | Source of Life Man | 소스오브라이프맨 | 2.0000 | 6.0000 |
| D072 | ["니샤네 하지밧 바이알3종"] | Hacivat | Hacivat | 하시빗 | 7.0000 | 11.0000 |
| D073 | ["쟈도르 도"] | J'adore Parfum d'Eau | J'adore Parfum d'Eau | 바르퓌르 | 4.0000 | 7.0000 |
| D020 | ["글로우 바이 제이로", "글로우 바이제이로"] | Glow | Glow | 글로 | 5.0000 | 6.0000 |

## enko_transliteration: 개선 사례

| queue_id | query_cores | gold_fragrantica_name | gold_uroman | gold_transliteration | baseline_rank | gold_candidate_rank |
|---|---|---|---|---|---|---|
| D038 | ["피코 디 아말피 오 드 뜨왈렛"] | Acqua di Parma Blu Mediterraneo - Fico di Amalfi | Blu Mediterraneo - Fico di Amalfi | 블루 미켈란젤로-피코 디알마드레 | 46.0000 | 3.0000 |
| D007 | ["레드 로즈"] | Red Roses | Red Roses | 레드로즈 | 34.0000 | 2.0000 |
| D001 | ["피렌체 1221 에디션 프리지아"] | Fresia | Fresia | 프레시아 | 22.0000 | 3.0000 |
| D016 | ["미스 디올"] | Miss Dior Eau de Parfum (2021) | Miss Dior 2021 | 미스 디오르옹 | 19.0000 | 7.0000 |
| D039 | ["나츄렐"] | Chloé Eau de Parfum Naturelle | Naturelle | 네이텔 | 13.0000 | 1.0000 |
| D021 | ["리브르"] | Libre | Libre | 리브어 | 16.0000 | 5.0000 |
| D061 | ["레 플레르 드 랑방 블루 오키드", "레 플레르 드 블루오키드"] | Blue Orchid | Blue Orchid | 블루 오키드 | 7.0000 | 1.0000 |
| D030 | ["폴로 랄프 , / 중"] | Polo | Polo | 폴로 | 14.0000 | 8.0000 |
| D051 | ["베르사체 에로스플레임"] | Eros Flame | Eros Flame | 에로스 플레임 | 6.0000 | 1.0000 |
| D022 | ["르 셀 디세이", "르셀디세이"] | Le Sel D'Issey Eau de Parfum | Le Sel D'Issey | 르 셀 디세 | 6.0000 | 1.0000 |

### enko_transliteration: 회귀 사례

| queue_id | query_cores | gold_fragrantica_name | gold_uroman | gold_transliteration | baseline_rank | gold_candidate_rank |
|---|---|---|---|---|---|---|
| D073 | ["쟈도르 도"] | J'adore Parfum d'Eau | J'adore Parfum d'Eau | 바르퓌르 | 4.0000 | 124.0000 |
| D075 | ["퓨어솝"] | Pure Soap | Pure Soap | 순수 소프 | 1.0000 | 24.0000 |
| D024 | ["쟈도르"] | J'adore | J'adore | 조도어 | 2.0000 | 16.0000 |
| D004 | ["클래식 소프트 런드리"] | Soft Laundry | Soft Laundry | 소프트라이닝 | 2.0000 | 9.0000 |
| D047 | ["미스 디올 블루밍 부케"] | Miss Dior Blooming Bouquet 2023 | Miss Dior Blooming Bouquet 2023 | 미스 디오르 블루밍 부아싯 어윈 | 3.0000 | 6.0000 |

## Transliteration 생성 예시와 품질

아래 출력은 모델이 실제 생성한 문자열이다. retrieval 적중은 언어학적 음역 정확성과 같지 않으므로, 성공/오류 해석은 원문과 국내 표기를 함께 봐야 한다.

### 상위 적중 출력

| queue_id | query_cores | gold_fragrantica_name | gold_uroman | gold_transliteration | baseline_rank | gold_candidate_rank |
|---|---|---|---|---|---|---|
| D001 | ["피렌체 1221 에디션 프리지아"] | Fresia | Fresia | 프레시아 | 22.0000 | 3.0000 |
| D005 | ["잉글리쉬 페어 앤 프리지아"] | English Pear & Freesia | English Pear & Freesia | 잉글리시피어 앤 프리시아 | 4.0000 | 1.0000 |
| D007 | ["레드 로즈"] | Red Roses | Red Roses | 레드로즈 | 34.0000 | 2.0000 |
| D008 | ["포 허"] | Narciso Rodriguez For Her | For Her | 포 허 | 1.0000 | 2.0000 |
| D009 | ["시그니처 코튼메모리", "헬로키티 에디션 시그니처 코튼메모리"] | Cotton Memory | Cotton Memory | 코튼메모리 | 1.0000 | 1.0000 |
| D010 | ["클라우드"] | Cloud | Cloud | 클라우드 | 1.0000 | 1.0000 |
| D011 | ["레 플레르 드 랑방 워터 릴리", "레 플레르 드 워터릴리"] | Water Lily | Water Lily | 워터 릴리 | 5.0000 | 1.0000 |
| D012 | ["르 셀 디세이", "르셀디세이"] | Le Sel d’Issey | Le Sel d’Issey | 르 셀 디세 | 1.0000 | 1.0000 |
| D013 | ["블랑쉬"] | Blanche | Blanche | 블랜치 | 6.0000 | 2.0000 |
| D014 | ["프레쉬로즈향 나르시소 로드리게즈 나르시소 크리스탈"] | Narciso Eau de Parfum Cristal | Narciso Cristal | 나르시소 크리스탈 | 3.0000 | 1.0000 |

### 순위 실패 출력

| queue_id | query_cores | gold_fragrantica_name | gold_uroman | gold_transliteration | baseline_rank | gold_candidate_rank |
|---|---|---|---|---|---|---|
| D024 | ["쟈도르"] | J'adore | J'adore | 조도어 | 2.0000 | 16.0000 |
| D028 | ["옴므"] | Dior Homme Cologne 2022 | Homme 2022 | 호머윈드 | 12.0000 | 73.0000 |
| D029 | ["시그니처"] | Chloé Eau de Parfum | Chloe | 클로에 | 32.0000 | 57.0000 |
| D059 | ["우먼"] | Jimmy Choo Eau de Toilette | Jimmy Choo | 지미 추 | 14.0000 | 22.0000 |
| D073 | ["쟈도르 도"] | J'adore Parfum d'Eau | J'adore Parfum d'Eau | 바르퓌르 | 4.0000 | 124.0000 |
| D075 | ["퓨어솝"] | Pure Soap | Pure Soap | 순수 소프 | 1.0000 | 24.0000 |

### 실제 비ASCII 후보 생성 예시

| fragrantica_id | name | core | korean_transliteration | generation_status |
|---|---|---|---|---|
| 6 | Arpège | Arpège | 아프제 | OK |
| 11 | Chanel N°19 | N°19 | 엔에이치에프 | OK |
| 92 | Cinéma | Cinéma | 신에마 | OK |
| 343 | Chloé (Parfums Chloé) | Parfums Chloé | 파툼스 클로에 | OK |
| 608 | Chanel N°5 (Vintage) | N°5 Vintage | 엔이디에이치에프 | OK |
| 831 | Présence d'une femme | Présence d'une femme | 프레센스 두누네펨 | OK |
| 936 | Gardénia | Gardénia | 가데니아 | OK |
| 977 | Opium Orchidée de Chine | Opium Orchidée de Chine | 오븀 오키드 데치네 | OK |
| 988 | Eclat d’Arpège | Eclat d’Arpège | 에스칼트 다르피제 | OK |
| 989 | Eclat d’Arpège Summer 2007 | Eclat d’Arpège Summer 2007 | 에스칼트 다르피제 서머 | OK |
| 1007 | Chanel N°22 | N°22 | 엔에이치에스 | OK |
| 1053 | L'Homme Eau d'Eté | L'Homme Eau d'Eté | 로돔오데테 | OK |

## 보완 가치와 판단

- uroman: baseline 대비 ΔR@5=+0.0164, ΔMRR=+0.0215; Top5 rescue 7, regression 6; Top10 rescue 7, regression 6.
- enko_transliteration: baseline 대비 ΔR@5=+0.0820, ΔMRR=+0.1140; Top5 rescue 10, regression 5; Top10 rescue 7, regression 3.
rescue가 있으면 baseline과 다른 오류 구조를 가진다는 증거이나, 자동 교체나 fusion 성능 향상을 입증하지 않는다. 두 새 채널을 합친 ranking이나 최종 MATCH Precision은 측정하지 않았다.
Gold DEV에서만 측정했으므로 미관측 데이터에 대한 일반화는 미확인이다. Verification과 다음 단계 구현은 진행하지 않았다.

## 실행시간 및 재현 검증

시간은 실제 실행의 wall-clock seconds이며 모델 다운로드·의존성 설치 시간은 제외한다. 캐시가 있는 재실행은 별도의 생성 시간을 만들지 않는다.
```json
{
  "baseline_and_query_normalization_seconds": 1.1790688999462873,
  "uroman_normalization_and_ranking_seconds": 3.3742052998859435,
  "transliteration_generation": {
    "cache_hits": 2450,
    "generated_cores": 0,
    "stage_seconds": 0.011160199996083975,
    "cached_generation_seconds": 96.42589190159924,
    "cache_path": "cache\\method2\\transliterations_f32eb198f42edb163d9824986abc1e074816cae09baa87f36435363aaf96a434.json",
    "cache_sha256": "659c3ea0d80e829b4d58575af7e7c225b02b6cd710f5a761fd8959bec010c626"
  },
  "enko_jamo_ranking_seconds": 0.14993179985322058,
  "total_before_report_seconds": 8.090382999973372
}
```
- catalog 후보 2570개 ID, core 2450개. 생성 상태: {'OK': 2569, 'MAX_LENGTH_REACHED': 1} (ID 기준).
- baseline 77개 Gold rank/Top5 일치, 모든 방법의 후보 ID 집합/길이 일치, rescue-regression 적중 수 항등식, structured normalization 검사, 입력 hash 불변 검사를 실행했다.
- Python 3.11.9, Unicode database 14.0.0.
- uroman: 1.3.1.1
- torch: 2.14.0+cpu
- transformers: 5.16.1
- peft: 0.20.0
- sentencepiece: 0.2.2
- sacremoses: 0.2.0
- pandas: 3.0.5
- 실행: `venv/Scripts/python.exe evaluate_fragrantica_method2_dev.py`
- 고정 설정: `fragrantica_method2_dev_settings.json`
- 입력 SHA-256:
  - `data\korea_popularity\evaluation\gold_set_dev.csv`: `41d5b84b30289dd24d3822c552cc100890d009600aa8a310234b2160ec37ad2f`
  - `data\korea_popularity\snapshot_pre_brand_mapping\korea_commercial_identities.csv`: `069a30ca2c053ba0222f66aa529996b61ede12df8bb97f743f8c3a2718787588`
  - `perfumes.csv`: `cec1ea0b498853032bcf44d33ad52ac83e2ed2896b67d5a2765d90a0345cc055`
  - `data\korea_popularity\evaluation\fragrantica_matcher_baseline_dev_results.csv`: `d8dc3592a5797186349e161ba171d22b28aabdd5601ab5d2c56ab96e2adadb82`
  - `data\korea_popularity\evaluation\fragrantica_matcher_baseline_dev_report.md`: `676583feff22347cc72380c732b29e90531d192ea1bb1b6ee5b9f56b64bb70e9`
  - `data\korea_popularity\snapshot_pre_brand_mapping\korea_commercial_identity_members.csv`: `b27d8c8accccb4afbe513c748a00ed1d1b3479595b054bf42992e7952d0bcf74`
  - `data\korea_popularity\snapshot_pre_brand_mapping\korea_candidate_families.csv`: `b853a639e9d707ac03e25e012cb16cf184703f56fa27c1c5d475e828debf749d`
  - `src\korea\build_korea_popularity_map.py`: `b5b4466e1a7f959634854fa0cd4459ca56cf104ffa06016e76a5efb51d4bcfef`
  - `src\matching\evaluate_fragrantica_matcher_dev.py`: `46989d4d0a7e5e4849b122c74305fcd65ea1421c0685c682f3a1757215f5ceb1`
  - `src\matching\evaluate_fragrantica_method1_dev.py`: `427560d701c93a8e512df5ca4509eaf0e16e8b10659f307abd40d98bcab8e96e`
  - `src\matching\evaluate_fragrantica_method2_dev.py`: `5c80ea67a5c041d4dd07995a746412d8b2d19206d91f3f542433e16d3b823fdd`
  - `data\korea_popularity\evaluation\fragrantica_method2_dev_settings.json`: `c9988941199d9336f04035ce3b2e45ed5f402ec8226e26ed6cc584ca5bcd912c`
  - `data\korea_popularity\evaluation\fragrantica_method1_dev_metrics.csv`: `585a712f279cb051d5ea19c817e5ae9b57abae2028cc147683e7db8a8d6d6e1f`
  - `data\korea_popularity\evaluation\fragrantica_method1_dev_normalization.json`: `db3482ae904b0820a2b41f3aa09210f2d7b4e36f37851c2cff85e6db1e311c7d`
  - `data\korea_popularity\evaluation\fragrantica_method1_dev_report.md`: `24a5a10d8b186ef985cea38ceb9e5c8055dc557b7768f71c4197ffc1092e0d37`
  - `data\korea_popularity\evaluation\fragrantica_method1_dev_results.csv`: `ebc133898a1efb45c2176786bd9a39a31bcb53606cbd9d2724932341d55b34d5`
  - `data\korea_popularity\evaluation\fragrantica_method1_dev_top10_misses.csv`: `d0ecf0cb7e6f695f4aeaae1fc9f482a5fb7f668dc53d2c95d33f1cb28e2e0b0e`
  - `cache\method2\model\models--feVeRin--enko-transliterator\snapshots\24b55c9bb8ab1f8682f8d8300c57340e2e0bcd66\adapter_config.json`: `8c5b5d757a15cf5ab06cd1cf765280aa817c86f30c31b8556463cd2a7139c01a`
  - `cache\method2\model\models--feVeRin--enko-transliterator\snapshots\24b55c9bb8ab1f8682f8d8300c57340e2e0bcd66\adapter_model.safetensors`: `82193cb04c9fda50d1596cfc55dcc6f263e4e9838fb44476ec9a89a5d25950a2`
  - `cache\method2\model\models--feVeRin--enko-transliterator\snapshots\24b55c9bb8ab1f8682f8d8300c57340e2e0bcd66\config.json`: `c00ec3d6d52c5ba3993c44336479f38e4f475dccdffd56fe2a938bae9673950f`
  - `cache\method2\model\models--feVeRin--enko-transliterator\snapshots\24b55c9bb8ab1f8682f8d8300c57340e2e0bcd66\generation_config.json`: `15425ec13c485bb0d1ec186dae3b1bbe9ac590e271da23250c441aa780dcd884`
  - `cache\method2\model\models--feVeRin--enko-transliterator\snapshots\24b55c9bb8ab1f8682f8d8300c57340e2e0bcd66\model.safetensors`: `cffa9848fdeda55160392845e28da4fcbcf1a1b923bc8938212639134fffa463`
  - `cache\method2\model\models--feVeRin--enko-transliterator\snapshots\24b55c9bb8ab1f8682f8d8300c57340e2e0bcd66\source.spm`: `f7ccc6d6432bbce3c85b598824abc1bfab35fcf81979c60ddb35c744c278cbd7`
  - `cache\method2\model\models--feVeRin--enko-transliterator\snapshots\24b55c9bb8ab1f8682f8d8300c57340e2e0bcd66\special_tokens_map.json`: `5e4d1f5e759d74cb1c2fe1d165cfc62b5237aa904de759380cd6f43042eec723`
  - `cache\method2\model\models--feVeRin--enko-transliterator\snapshots\24b55c9bb8ab1f8682f8d8300c57340e2e0bcd66\target.spm`: `f7ccc6d6432bbce3c85b598824abc1bfab35fcf81979c60ddb35c744c278cbd7`
  - `cache\method2\model\models--feVeRin--enko-transliterator\snapshots\24b55c9bb8ab1f8682f8d8300c57340e2e0bcd66\tokenizer_config.json`: `44e95ab0c6f4d874aef2fe11c2af37a792c14800ed6944425d69d1fa473e4f16`
  - `cache\method2\model\models--feVeRin--enko-transliterator\snapshots\24b55c9bb8ab1f8682f8d8300c57340e2e0bcd66\vocab.json`: `05bcfda7e8ffed4d1acbcbfa5072dbcb3f1c6cefddb7bc5322c8c7202ab7f6fa`

## 캐시 재실행 검증

- 77개 × 3 방법의 결과, 전체 지표, 후보 변환 테이블을 재실행해 저장된 값과 전수 일치했다.
- 새 음역 생성 0개, 캐시 재사용 2,450 core, 캐시와 고정 설정 hash 불변. 재실행 검증 wall-clock 7.215초. 위 최초 실행 시간과 구분한다.
- pip check: No broken requirements found.

# Method 3: fixed LLM name representations DEV retrieval

## 실험 범위

- DEV 80행 중 evaluation-eligible 77 identity를 실행했고, Gold MATCH 61개를 지표 분모로 사용했다. NO_MATCH 16개는 retrieval 지표에서 제외했다.
- Gold는 다섯 ranking이 모두 만들어진 뒤 평가에만 사용했다. TEST 입력은 코드 경로와 입력 목록에 없으며 열지 않았다.
- 다섯 방법은 identity별로 같은 Method 2 전체 candidate ID 집합과 같은 exact-brand blocking, concentration/form filter를 쓴다. 어떤 ranking도 fusion하지 않았다.
- baseline lexical, uroman, 전용 en→ko는 Method 2 구현을 직접 재실행했다. 저장된 Method 2 results 231행, metrics, candidate representations 전 항목이 일치했다.
- LLM KO→Latin은 고정 reconstructed_fragrance_latin 하나와 Method 2 structured-normalized Latin core를 NFKC/casefold/alphanumeric key로 바꿔 동일 SequenceMatcher ratio로 비교했다. reconstructed_brand_latin은 결과에 보존했지만 ranking에 쓰지 않았다.
- LLM Latin→KO는 고정 korean_transliteration을 exact latin_core로 연결했다. 국내 query는 Method 2 Korean core를 그대로 쓰고 양쪽 모두 같은 NFD Hangul jamo key와 같은 SequenceMatcher ratio를 썼다.
- reconstruction_status는 ranking/filter에 전혀 읽히지 않고 사후 분석에만 쓰였다. 출력 문자열 자체가 `UNKNOWN` 또는 빈 값이면 comparison key를 비워 score 0으로 유지했다. 원문 대체, 보정, threshold 조정, 예외 규칙, gating, Verification은 없다.
- MRR은 전체 공통 pool 순위, MRR@10은 10위 밖을 0으로 계산한다. CATALOG_RETRIEVABLE은 기존 Method 2 정의대로 Gold ID가 perfumes.csv에 존재한다는 뜻이며 pool 통과를 뜻하지 않는다.

## ALL_GOLD_MATCH: 전체 성능

| method | group | gold_match | recall_at_1 | recall_at_3 | recall_at_5 | recall_at_10 | mrr | mrr_at_10 | top5_miss | top10_miss |
|---|---|---|---|---|---|---|---|---|---|---|
| baseline_lexical | ALL | 61 | 0.3115 | 0.5082 | 0.5902 | 0.6721 | 0.4451 | 0.4361 | 25 | 20 |
| uroman | ALL | 61 | 0.3443 | 0.5410 | 0.6066 | 0.6885 | 0.4665 | 0.4594 | 24 | 19 |
| enko_transliteration | ALL | 61 | 0.4590 | 0.6230 | 0.6721 | 0.7377 | 0.5590 | 0.5559 | 20 | 16 |
| llm_ko_to_latin | ALL | 61 | 0.5410 | 0.7869 | 0.7869 | 0.7869 | 0.6569 | 0.6557 | 13 | 13 |
| llm_latin_to_ko | ALL | 61 | 0.5410 | 0.7705 | 0.7869 | 0.8033 | 0.6543 | 0.6532 | 13 | 12 |

### Representative / Challenge

| method | group | gold_match | recall_at_1 | recall_at_3 | recall_at_5 | recall_at_10 | mrr | mrr_at_10 | top5_miss | top10_miss |
|---|---|---|---|---|---|---|---|---|---|---|
| baseline_lexical | CHALLENGE | 28 | 0.2857 | 0.5000 | 0.6429 | 0.7143 | 0.4424 | 0.4310 | 10 | 8 |
| baseline_lexical | REPRESENTATIVE | 33 | 0.3333 | 0.5152 | 0.5455 | 0.6364 | 0.4473 | 0.4405 | 15 | 12 |
| uroman | CHALLENGE | 28 | 0.3214 | 0.6071 | 0.7500 | 0.8571 | 0.4944 | 0.4908 | 7 | 4 |
| uroman | REPRESENTATIVE | 33 | 0.3636 | 0.4848 | 0.4848 | 0.5455 | 0.4429 | 0.4327 | 17 | 15 |
| enko_transliteration | CHALLENGE | 28 | 0.4286 | 0.6071 | 0.6786 | 0.7500 | 0.5452 | 0.5390 | 9 | 7 |
| enko_transliteration | REPRESENTATIVE | 33 | 0.4848 | 0.6364 | 0.6667 | 0.7273 | 0.5708 | 0.5703 | 11 | 9 |
| llm_ko_to_latin | CHALLENGE | 28 | 0.5000 | 0.8929 | 0.8929 | 0.8929 | 0.6797 | 0.6786 | 3 | 3 |
| llm_ko_to_latin | REPRESENTATIVE | 33 | 0.5758 | 0.6970 | 0.6970 | 0.6970 | 0.6375 | 0.6364 | 10 | 10 |
| llm_latin_to_ko | CHALLENGE | 28 | 0.5357 | 0.8571 | 0.8929 | 0.8929 | 0.6876 | 0.6857 | 3 | 3 |
| llm_latin_to_ko | REPRESENTATIVE | 33 | 0.5455 | 0.6970 | 0.6970 | 0.7273 | 0.6261 | 0.6255 | 10 | 9 |

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
| llm_ko_to_latin | FAMILY_VARIANT_RISK | 4 | 0.5000 | 0.7500 | 0.7500 | 0.7500 | 0.6250 | 0.6250 | 1 | 1 |
| llm_ko_to_latin | FUZZY_AUTO_MATCH_RISK | 10 | 0.5000 | 0.9000 | 0.9000 | 0.9000 | 0.7031 | 0.7000 | 1 | 1 |
| llm_ko_to_latin | MATCH_REVIEW | 6 | 0.5000 | 1.0000 | 1.0000 | 1.0000 | 0.6944 | 0.6944 | 0 | 0 |
| llm_ko_to_latin | NORMALIZATION_RISK | 2 | 0.5000 | 0.5000 | 0.5000 | 0.5000 | 0.5000 | 0.5000 | 1 | 1 |
| llm_ko_to_latin | NO_MATCH_CROSSLINGUAL | 6 | 0.5000 | 1.0000 | 1.0000 | 1.0000 | 0.7222 | 0.7222 | 0 | 0 |
| llm_latin_to_ko | FAMILY_VARIANT_RISK | 4 | 0.5000 | 0.7500 | 0.7500 | 0.7500 | 0.6250 | 0.6250 | 1 | 1 |
| llm_latin_to_ko | FUZZY_AUTO_MATCH_RISK | 10 | 0.6000 | 0.9000 | 0.9000 | 0.9000 | 0.7553 | 0.7500 | 1 | 1 |
| llm_latin_to_ko | MATCH_REVIEW | 6 | 0.3333 | 0.8333 | 1.0000 | 1.0000 | 0.5611 | 0.5611 | 0 | 0 |
| llm_latin_to_ko | NORMALIZATION_RISK | 2 | 0.5000 | 0.5000 | 0.5000 | 0.5000 | 0.5000 | 0.5000 | 1 | 1 |
| llm_latin_to_ko | NO_MATCH_CROSSLINGUAL | 6 | 0.6667 | 1.0000 | 1.0000 | 1.0000 | 0.8056 | 0.8056 | 0 | 0 |

### Baseline 기준 Rescue / Regression

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
| llm_ko_to_latin | ALL | 61 | 25 | 12 | 36 | 0 | 20 | 7 | 41 | 0 |
| llm_ko_to_latin | CHALLENGE | 28 | 10 | 7 | 18 | 0 | 8 | 5 | 20 | 0 |
| llm_ko_to_latin | REPRESENTATIVE | 33 | 15 | 5 | 18 | 0 | 12 | 2 | 21 | 0 |
| llm_latin_to_ko | ALL | 61 | 25 | 12 | 36 | 0 | 20 | 8 | 41 | 0 |
| llm_latin_to_ko | CHALLENGE | 28 | 10 | 7 | 18 | 0 | 8 | 5 | 20 | 0 |
| llm_latin_to_ko | REPRESENTATIVE | 33 | 15 | 5 | 18 | 0 | 12 | 3 | 21 | 0 |

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
| llm_ko_to_latin | FAMILY_VARIANT_RISK | 4 | 2 | 1 | 2 | 0 | 1 | 0 | 3 | 0 |
| llm_ko_to_latin | FUZZY_AUTO_MATCH_RISK | 10 | 2 | 1 | 8 | 0 | 2 | 1 | 8 | 0 |
| llm_ko_to_latin | MATCH_REVIEW | 6 | 3 | 3 | 3 | 0 | 2 | 2 | 4 | 0 |
| llm_ko_to_latin | NORMALIZATION_RISK | 2 | 1 | 0 | 1 | 0 | 1 | 0 | 1 | 0 |
| llm_ko_to_latin | NO_MATCH_CROSSLINGUAL | 6 | 2 | 2 | 4 | 0 | 2 | 2 | 4 | 0 |
| llm_latin_to_ko | FAMILY_VARIANT_RISK | 4 | 2 | 1 | 2 | 0 | 1 | 0 | 3 | 0 |
| llm_latin_to_ko | FUZZY_AUTO_MATCH_RISK | 10 | 2 | 1 | 8 | 0 | 2 | 1 | 8 | 0 |
| llm_latin_to_ko | MATCH_REVIEW | 6 | 3 | 3 | 3 | 0 | 2 | 2 | 4 | 0 |
| llm_latin_to_ko | NORMALIZATION_RISK | 2 | 1 | 0 | 1 | 0 | 1 | 0 | 1 | 0 |
| llm_latin_to_ko | NO_MATCH_CROSSLINGUAL | 6 | 2 | 2 | 4 | 0 | 2 | 2 | 4 | 0 |

## CATALOG_RETRIEVABLE: 전체 성능

| method | group | gold_match | recall_at_1 | recall_at_3 | recall_at_5 | recall_at_10 | mrr | mrr_at_10 | top5_miss | top10_miss |
|---|---|---|---|---|---|---|---|---|---|---|
| baseline_lexical | ALL | 59 | 0.3220 | 0.5254 | 0.6102 | 0.6949 | 0.4601 | 0.4509 | 23 | 18 |
| uroman | ALL | 59 | 0.3559 | 0.5593 | 0.6271 | 0.7119 | 0.4824 | 0.4749 | 22 | 17 |
| enko_transliteration | ALL | 59 | 0.4746 | 0.6441 | 0.6949 | 0.7627 | 0.5780 | 0.5748 | 18 | 14 |
| llm_ko_to_latin | ALL | 59 | 0.5593 | 0.8136 | 0.8136 | 0.8136 | 0.6791 | 0.6780 | 11 | 11 |
| llm_latin_to_ko | ALL | 59 | 0.5593 | 0.7966 | 0.8136 | 0.8305 | 0.6765 | 0.6753 | 11 | 10 |

### Representative / Challenge

| method | group | gold_match | recall_at_1 | recall_at_3 | recall_at_5 | recall_at_10 | mrr | mrr_at_10 | top5_miss | top10_miss |
|---|---|---|---|---|---|---|---|---|---|---|
| baseline_lexical | CHALLENGE | 27 | 0.2963 | 0.5185 | 0.6667 | 0.7407 | 0.4588 | 0.4469 | 9 | 7 |
| baseline_lexical | REPRESENTATIVE | 32 | 0.3438 | 0.5312 | 0.5625 | 0.6562 | 0.4613 | 0.4542 | 14 | 11 |
| uroman | CHALLENGE | 27 | 0.3333 | 0.6296 | 0.7778 | 0.8889 | 0.5127 | 0.5090 | 6 | 3 |
| uroman | REPRESENTATIVE | 32 | 0.3750 | 0.5000 | 0.5000 | 0.5625 | 0.4568 | 0.4462 | 16 | 14 |
| enko_transliteration | CHALLENGE | 27 | 0.4444 | 0.6296 | 0.7037 | 0.7778 | 0.5653 | 0.5590 | 8 | 6 |
| enko_transliteration | REPRESENTATIVE | 32 | 0.5000 | 0.6562 | 0.6875 | 0.7500 | 0.5887 | 0.5881 | 10 | 8 |
| llm_ko_to_latin | CHALLENGE | 27 | 0.5185 | 0.9259 | 0.9259 | 0.9259 | 0.7049 | 0.7037 | 2 | 2 |
| llm_ko_to_latin | REPRESENTATIVE | 32 | 0.5938 | 0.7188 | 0.7188 | 0.7188 | 0.6574 | 0.6562 | 9 | 9 |
| llm_latin_to_ko | CHALLENGE | 27 | 0.5556 | 0.8889 | 0.9259 | 0.9259 | 0.7131 | 0.7111 | 2 | 2 |
| llm_latin_to_ko | REPRESENTATIVE | 32 | 0.5625 | 0.7188 | 0.7188 | 0.7500 | 0.6456 | 0.6451 | 9 | 8 |

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
| llm_ko_to_latin | FAMILY_VARIANT_RISK | 4 | 0.5000 | 0.7500 | 0.7500 | 0.7500 | 0.6250 | 0.6250 | 1 | 1 |
| llm_ko_to_latin | FUZZY_AUTO_MATCH_RISK | 10 | 0.5000 | 0.9000 | 0.9000 | 0.9000 | 0.7031 | 0.7000 | 1 | 1 |
| llm_ko_to_latin | MATCH_REVIEW | 6 | 0.5000 | 1.0000 | 1.0000 | 1.0000 | 0.6944 | 0.6944 | 0 | 0 |
| llm_ko_to_latin | NORMALIZATION_RISK | 1 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0 | 0 |
| llm_ko_to_latin | NO_MATCH_CROSSLINGUAL | 6 | 0.5000 | 1.0000 | 1.0000 | 1.0000 | 0.7222 | 0.7222 | 0 | 0 |
| llm_latin_to_ko | FAMILY_VARIANT_RISK | 4 | 0.5000 | 0.7500 | 0.7500 | 0.7500 | 0.6250 | 0.6250 | 1 | 1 |
| llm_latin_to_ko | FUZZY_AUTO_MATCH_RISK | 10 | 0.6000 | 0.9000 | 0.9000 | 0.9000 | 0.7553 | 0.7500 | 1 | 1 |
| llm_latin_to_ko | MATCH_REVIEW | 6 | 0.3333 | 0.8333 | 1.0000 | 1.0000 | 0.5611 | 0.5611 | 0 | 0 |
| llm_latin_to_ko | NORMALIZATION_RISK | 1 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0 | 0 |
| llm_latin_to_ko | NO_MATCH_CROSSLINGUAL | 6 | 0.6667 | 1.0000 | 1.0000 | 1.0000 | 0.8056 | 0.8056 | 0 | 0 |

### Baseline 기준 Rescue / Regression

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
| llm_ko_to_latin | ALL | 59 | 23 | 12 | 36 | 0 | 18 | 7 | 41 | 0 |
| llm_ko_to_latin | CHALLENGE | 27 | 9 | 7 | 18 | 0 | 7 | 5 | 20 | 0 |
| llm_ko_to_latin | REPRESENTATIVE | 32 | 14 | 5 | 18 | 0 | 11 | 2 | 21 | 0 |
| llm_latin_to_ko | ALL | 59 | 23 | 12 | 36 | 0 | 18 | 8 | 41 | 0 |
| llm_latin_to_ko | CHALLENGE | 27 | 9 | 7 | 18 | 0 | 7 | 5 | 20 | 0 |
| llm_latin_to_ko | REPRESENTATIVE | 32 | 14 | 5 | 18 | 0 | 11 | 3 | 21 | 0 |

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
| llm_ko_to_latin | FAMILY_VARIANT_RISK | 4 | 2 | 1 | 2 | 0 | 1 | 0 | 3 | 0 |
| llm_ko_to_latin | FUZZY_AUTO_MATCH_RISK | 10 | 2 | 1 | 8 | 0 | 2 | 1 | 8 | 0 |
| llm_ko_to_latin | MATCH_REVIEW | 6 | 3 | 3 | 3 | 0 | 2 | 2 | 4 | 0 |
| llm_ko_to_latin | NORMALIZATION_RISK | 1 | 0 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| llm_ko_to_latin | NO_MATCH_CROSSLINGUAL | 6 | 2 | 2 | 4 | 0 | 2 | 2 | 4 | 0 |
| llm_latin_to_ko | FAMILY_VARIANT_RISK | 4 | 2 | 1 | 2 | 0 | 1 | 0 | 3 | 0 |
| llm_latin_to_ko | FUZZY_AUTO_MATCH_RISK | 10 | 2 | 1 | 8 | 0 | 2 | 1 | 8 | 0 |
| llm_latin_to_ko | MATCH_REVIEW | 6 | 3 | 3 | 3 | 0 | 2 | 2 | 4 | 0 |
| llm_latin_to_ko | NORMALIZATION_RISK | 1 | 0 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| llm_latin_to_ko | NO_MATCH_CROSSLINGUAL | 6 | 2 | 2 | 4 | 0 | 2 | 2 | 4 | 0 |

## 두 LLM 방향의 Top-K 관계

아래 네 rescue 구분은 baseline miss를 분모로 한다. `neither_rescues`는 두 LLM 모두 해당 K에서 baseline miss를 구하지 못한 경우다.

| scope | k | baseline_miss | ko_to_latin_only_rescue | latin_to_ko_only_rescue | both_rescue | neither_rescues |
|---|---|---|---|---|---|---|
| ALL_GOLD_MATCH | 5 | 25 | 0 | 0 | 12 | 13 |
| ALL_GOLD_MATCH | 10 | 20 | 0 | 1 | 7 | 12 |
| CATALOG_RETRIEVABLE | 5 | 23 | 0 | 0 | 12 | 11 |
| CATALOG_RETRIEVABLE | 10 | 18 | 0 | 1 | 7 | 10 |

### Top5 실제 사례

**KO→Latin만 rescue (0)**

| queue_id | raw_product_names | reconstructed_fragrance_latin | gold_fragrantica_name | baseline_rank | ko_to_latin_rank | latin_to_ko_rank | catalog_status |
|---|---|---|---|---|---|---|---|
**Latin→KO만 rescue (0)**

| queue_id | raw_product_names | reconstructed_fragrance_latin | gold_fragrantica_name | baseline_rank | ko_to_latin_rank | latin_to_ko_rank | catalog_status |
|---|---|---|---|---|---|---|---|
**둘 다 rescue (12)**

| queue_id | raw_product_names | reconstructed_fragrance_latin | gold_fragrantica_name | baseline_rank | ko_to_latin_rank | latin_to_ko_rank | catalog_status |
|---|---|---|---|---|---|---|---|
| D001 | ["피렌체 1221 에디션 오드코롱 [프리지아]"] | Firenze 1221 Edition Fresia | Fresia | 22.0000 | 1.0000 | 1.0000 | IN_CANDIDATE_POOL |
| D007 | ["레드 로즈 코롱"] | Red Roses | Red Roses | 34.0000 | 2.0000 | 2.0000 | IN_CANDIDATE_POOL |
| D013 | ["오 드 퍼퓸 [블랑쉬]"] | Blanche | Blanche | 6.0000 | 1.0000 | 1.0000 | IN_CANDIDATE_POOL |
| D016 | ["미스 디올 오 드 퍼퓸"] | Miss Dior | Miss Dior Eau de Parfum (2021) | 19.0000 | 2.0000 | 2.0000 | IN_CANDIDATE_POOL |
| D021 | ["리브르 오 드 빠르펭"] | Libre | Libre | 16.0000 | 2.0000 | 2.0000 | IN_CANDIDATE_POOL |
| D022 | ["르셀디세이 오 드 퍼퓸 100ml", "르셀디세이 오 드 퍼퓸 50ml", "이세이미야케 르 셀 디세이 EDP (50ml/100ml)"] | Le Sel d'Issey | Le Sel D'Issey Eau de Parfum | 6.0000 | 1.0000 | 1.0000 | IN_CANDIDATE_POOL |
| D028 | ["옴므 코롱"] | Homme | Dior Homme Cologne 2022 | 12.0000 | 3.0000 | 3.0000 | IN_CANDIDATE_POOL |
| D038 | ["피코 디 아말피 오 드 뜨왈렛"] | Fico di Amalfi | Acqua di Parma Blu Mediterraneo - Fico di Amalfi | 46.0000 | 3.0000 | 3.0000 | IN_CANDIDATE_POOL |
| D039 | ["끌로에 나츄렐 EDP 30ml/50ml"] | Naturelle | Chloé Eau de Parfum Naturelle | 13.0000 | 1.0000 | 1.0000 | IN_CANDIDATE_POOL |
| D051 | ["[베르사체] 에로스플레임 오드퍼퓸 100ml (미니어처1종 랜덤증정)"] | Eros Flame | Eros Flame | 6.0000 | 1.0000 | 1.0000 | IN_CANDIDATE_POOL |
**둘 다 실패 (13)**

| queue_id | raw_product_names | reconstructed_fragrance_latin | gold_fragrantica_name | baseline_rank | ko_to_latin_rank | latin_to_ko_rank | catalog_status |
|---|---|---|---|---|---|---|---|
| D002 | ["[단독기획] 제니퍼로페즈 글로우 바이제이로 EDT 100ml 기획(+프로미스 바디로션)"] | Glow by JLo | Glow | — | — | — | CONCENTRATION_OR_FORM_FILTER |
| D018 | ["[보이넥스트도어 PICK] 에끌로에 오 드 퍼퓸 EDP 50ml"] | Ecloe | Echloe | — | — | — | BRAND_BLOCKED |
| D026 | ["오 드 퍼퓸 페더 10ml"] | Feather | Feather | — | — | — | BRAND_BLOCKED |
| D029 | ["시그니처 EDP"] | Signature | Chloé Eau de Parfum | 32.0000 | 68.0000 | 57.0000 | IN_CANDIDATE_POOL |
| D030 | ["랄프로렌 폴로 랄프 EDT 30ml,50ml 단품/기획 중 택 1"] | Ralph | Polo | 14.0000 | 43.0000 | 7.0000 | IN_CANDIDATE_POOL |
| D037 | ["[엔믹스규진PICK] 에틀리에 오 드 퍼퓸 트와일라잇블룸 30ml/10ml"] | Twilight Bloom | Etlee Twilight Bloom | — | — | — | CATALOG_MISSING |
| D042 | ["퍼퓸 솝클린솝 50ml"] | Soap Clean Soap | Soap Clean Soap | — | — | — | BRAND_BLOCKED |
| D043 | ["오리지널 머스크 향수"] | Original Musk | Original Musk | — | — | — | BRAND_BLOCKED |
| D045 | ["[기획] 알보우 케이스 스터디 EDP 30ml 상탈 블루 (+핸드크림)"] | Case Study Santal Blue | Santal Bleu | — | — | — | BRAND_BLOCKED |
| D054 | ["[NEW/기획] 아뜰리에페이 퍼퓸 30ml 데이오프", "데이 오프"] | Day Off | Day Off | — | — | — | CATALOG_MISSING |

### Top10 실제 사례

**KO→Latin만 rescue (0)**

| queue_id | raw_product_names | reconstructed_fragrance_latin | gold_fragrantica_name | baseline_rank | ko_to_latin_rank | latin_to_ko_rank | catalog_status |
|---|---|---|---|---|---|---|---|
**Latin→KO만 rescue (1)**

| queue_id | raw_product_names | reconstructed_fragrance_latin | gold_fragrantica_name | baseline_rank | ko_to_latin_rank | latin_to_ko_rank | catalog_status |
|---|---|---|---|---|---|---|---|
| D030 | ["랄프로렌 폴로 랄프 EDT 30ml,50ml 단품/기획 중 택 1"] | Ralph | Polo | 14.0000 | 43.0000 | 7.0000 | IN_CANDIDATE_POOL |
**둘 다 rescue (7)**

| queue_id | raw_product_names | reconstructed_fragrance_latin | gold_fragrantica_name | baseline_rank | ko_to_latin_rank | latin_to_ko_rank | catalog_status |
|---|---|---|---|---|---|---|---|
| D001 | ["피렌체 1221 에디션 오드코롱 [프리지아]"] | Firenze 1221 Edition Fresia | Fresia | 22.0000 | 1.0000 | 1.0000 | IN_CANDIDATE_POOL |
| D007 | ["레드 로즈 코롱"] | Red Roses | Red Roses | 34.0000 | 2.0000 | 2.0000 | IN_CANDIDATE_POOL |
| D016 | ["미스 디올 오 드 퍼퓸"] | Miss Dior | Miss Dior Eau de Parfum (2021) | 19.0000 | 2.0000 | 2.0000 | IN_CANDIDATE_POOL |
| D021 | ["리브르 오 드 빠르펭"] | Libre | Libre | 16.0000 | 2.0000 | 2.0000 | IN_CANDIDATE_POOL |
| D028 | ["옴므 코롱"] | Homme | Dior Homme Cologne 2022 | 12.0000 | 3.0000 | 3.0000 | IN_CANDIDATE_POOL |
| D038 | ["피코 디 아말피 오 드 뜨왈렛"] | Fico di Amalfi | Acqua di Parma Blu Mediterraneo - Fico di Amalfi | 46.0000 | 3.0000 | 3.0000 | IN_CANDIDATE_POOL |
| D039 | ["끌로에 나츄렐 EDP 30ml/50ml"] | Naturelle | Chloé Eau de Parfum Naturelle | 13.0000 | 1.0000 | 1.0000 | IN_CANDIDATE_POOL |
**둘 다 실패 (12)**

| queue_id | raw_product_names | reconstructed_fragrance_latin | gold_fragrantica_name | baseline_rank | ko_to_latin_rank | latin_to_ko_rank | catalog_status |
|---|---|---|---|---|---|---|---|
| D002 | ["[단독기획] 제니퍼로페즈 글로우 바이제이로 EDT 100ml 기획(+프로미스 바디로션)"] | Glow by JLo | Glow | — | — | — | CONCENTRATION_OR_FORM_FILTER |
| D018 | ["[보이넥스트도어 PICK] 에끌로에 오 드 퍼퓸 EDP 50ml"] | Ecloe | Echloe | — | — | — | BRAND_BLOCKED |
| D026 | ["오 드 퍼퓸 페더 10ml"] | Feather | Feather | — | — | — | BRAND_BLOCKED |
| D029 | ["시그니처 EDP"] | Signature | Chloé Eau de Parfum | 32.0000 | 68.0000 | 57.0000 | IN_CANDIDATE_POOL |
| D037 | ["[엔믹스규진PICK] 에틀리에 오 드 퍼퓸 트와일라잇블룸 30ml/10ml"] | Twilight Bloom | Etlee Twilight Bloom | — | — | — | CATALOG_MISSING |
| D042 | ["퍼퓸 솝클린솝 50ml"] | Soap Clean Soap | Soap Clean Soap | — | — | — | BRAND_BLOCKED |
| D043 | ["오리지널 머스크 향수"] | Original Musk | Original Musk | — | — | — | BRAND_BLOCKED |
| D045 | ["[기획] 알보우 케이스 스터디 EDP 30ml 상탈 블루 (+핸드크림)"] | Case Study Santal Blue | Santal Bleu | — | — | — | BRAND_BLOCKED |
| D054 | ["[NEW/기획] 아뜰리에페이 퍼퓸 30ml 데이오프", "데이 오프"] | Day Off | Day Off | — | — | — | CATALOG_MISSING |
| D056 | ["[에탄올 FREE] 에이딕트 헤어 퍼퓸 30ml 버베나 레인 (단품/기획)"] | Verbena Rain | Verbena Rain | — | — | — | BRAND_BLOCKED |

## LLM reconstruction_status 사후 분석

상태는 ranking/filter에 사용하지 않고 사후 slice에만 사용했다. KO→Latin은 query 행 상태, Latin→KO는 Gold candidate core에 연결된 출력 상태다. Gold가 Method 2 candidate core 집합에 없으면 별도 `NOT_IN_METHOD2_CANDIDATE_CORES`로 보존했다.

### ALL_GOLD_MATCH

| method | status | gold_match | recall_at_5 | recall_at_10 | mrr |
|---|---|---|---|---|---|
| llm_ko_to_latin | OK | 52 | 0.9038 | 0.9038 | 0.7509 |
| llm_ko_to_latin | UNCERTAIN | 9 | 0.1111 | 0.1111 | 0.1137 |
| llm_ko_to_latin | UNKNOWN | 0 | — | — | — |
| llm_latin_to_ko | OK | 42 | 0.9286 | 0.9524 | 0.7776 |
| llm_latin_to_ko | UNCERTAIN | 10 | 0.9000 | 0.9000 | 0.7253 |
| llm_latin_to_ko | UNKNOWN | 0 | — | — | — |
| llm_latin_to_ko | NOT_IN_METHOD2_CANDIDATE_CORES | 9 | 0.0000 | 0.0000 | 0.0000 |

### CATALOG_RETRIEVABLE

| method | status | gold_match | recall_at_5 | recall_at_10 | mrr |
|---|---|---|---|---|---|
| llm_ko_to_latin | OK | 51 | 0.9216 | 0.9216 | 0.7656 |
| llm_ko_to_latin | UNCERTAIN | 8 | 0.1250 | 0.1250 | 0.1279 |
| llm_ko_to_latin | UNKNOWN | 0 | — | — | — |
| llm_latin_to_ko | OK | 42 | 0.9286 | 0.9524 | 0.7776 |
| llm_latin_to_ko | UNCERTAIN | 10 | 0.9000 | 0.9000 | 0.7253 |
| llm_latin_to_ko | UNKNOWN | 0 | — | — | — |
| llm_latin_to_ko | NOT_IN_METHOD2_CANDIDATE_CORES | 7 | 0.0000 | 0.0000 | 0.0000 |

## 주요 개선·회귀 사례

### llm_ko_to_latin: 개선

| queue_id | raw_product_names | query_cores | reconstructed_fragrance_latin | gold_fragrantica_name | gold_enko_transliteration | gold_llm_korean_transliteration | baseline_rank | gold_candidate_rank | catalog_status |
|---|---|---|---|---|---|---|---|---|---|
| D038 | ["피코 디 아말피 오 드 뜨왈렛"] | ["피코 디 아말피 오 드 뜨왈렛"] | Fico di Amalfi | Acqua di Parma Blu Mediterraneo - Fico di Amalfi | 블루 미켈란젤로-피코 디알마드레 | 블루 메디테라네오 - 피코 디 아말피 | 46.0000 | 3.0000 | IN_CANDIDATE_POOL |
| D007 | ["레드 로즈 코롱"] | ["레드 로즈"] | Red Roses | Red Roses | 레드로즈 | 레드 로즈 | 34.0000 | 2.0000 | IN_CANDIDATE_POOL |
| D001 | ["피렌체 1221 에디션 오드코롱 [프리지아]"] | ["피렌체 1221 에디션 프리지아"] | Firenze 1221 Edition Fresia | Fresia | 프레시아 | 프레지아 | 22.0000 | 1.0000 | IN_CANDIDATE_POOL |
| D016 | ["미스 디올 오 드 퍼퓸"] | ["미스 디올"] | Miss Dior | Miss Dior Eau de Parfum (2021) | 미스 디오르옹 | 미스 디올 2021 | 19.0000 | 2.0000 | IN_CANDIDATE_POOL |
| D021 | ["리브르 오 드 빠르펭"] | ["리브르"] | Libre | Libre | 리브어 | 리브르 | 16.0000 | 2.0000 | IN_CANDIDATE_POOL |
| D039 | ["끌로에 나츄렐 EDP 30ml/50ml"] | ["나츄렐"] | Naturelle | Chloé Eau de Parfum Naturelle | 네이텔 | 나튀렐 | 13.0000 | 1.0000 | IN_CANDIDATE_POOL |
| D028 | ["옴므 코롱"] | ["옴므"] | Homme | Dior Homme Cologne 2022 | 호머윈드 | 옴므 2022 | 12.0000 | 3.0000 | IN_CANDIDATE_POOL |

### llm_ko_to_latin: 회귀

| queue_id | raw_product_names | query_cores | reconstructed_fragrance_latin | gold_fragrantica_name | gold_enko_transliteration | gold_llm_korean_transliteration | baseline_rank | gold_candidate_rank | catalog_status |
|---|---|---|---|---|---|---|---|---|---|
### llm_latin_to_ko: 개선

| queue_id | raw_product_names | query_cores | reconstructed_fragrance_latin | gold_fragrantica_name | gold_enko_transliteration | gold_llm_korean_transliteration | baseline_rank | gold_candidate_rank | catalog_status |
|---|---|---|---|---|---|---|---|---|---|
| D038 | ["피코 디 아말피 오 드 뜨왈렛"] | ["피코 디 아말피 오 드 뜨왈렛"] | Fico di Amalfi | Acqua di Parma Blu Mediterraneo - Fico di Amalfi | 블루 미켈란젤로-피코 디알마드레 | 블루 메디테라네오 - 피코 디 아말피 | 46.0000 | 3.0000 | IN_CANDIDATE_POOL |
| D007 | ["레드 로즈 코롱"] | ["레드 로즈"] | Red Roses | Red Roses | 레드로즈 | 레드 로즈 | 34.0000 | 2.0000 | IN_CANDIDATE_POOL |
| D001 | ["피렌체 1221 에디션 오드코롱 [프리지아]"] | ["피렌체 1221 에디션 프리지아"] | Firenze 1221 Edition Fresia | Fresia | 프레시아 | 프레지아 | 22.0000 | 1.0000 | IN_CANDIDATE_POOL |
| D016 | ["미스 디올 오 드 퍼퓸"] | ["미스 디올"] | Miss Dior | Miss Dior Eau de Parfum (2021) | 미스 디오르옹 | 미스 디올 2021 | 19.0000 | 2.0000 | IN_CANDIDATE_POOL |
| D021 | ["리브르 오 드 빠르펭"] | ["리브르"] | Libre | Libre | 리브어 | 리브르 | 16.0000 | 2.0000 | IN_CANDIDATE_POOL |
| D039 | ["끌로에 나츄렐 EDP 30ml/50ml"] | ["나츄렐"] | Naturelle | Chloé Eau de Parfum Naturelle | 네이텔 | 나튀렐 | 13.0000 | 1.0000 | IN_CANDIDATE_POOL |
| D028 | ["옴므 코롱"] | ["옴므"] | Homme | Dior Homme Cologne 2022 | 호머윈드 | 옴므 2022 | 12.0000 | 3.0000 | IN_CANDIDATE_POOL |
| D030 | ["랄프로렌 폴로 랄프 EDT 30ml,50ml 단품/기획 중 택 1"] | ["폴로 랄프 , / 중"] | Ralph | Polo | 폴로 | 폴로 | 14.0000 | 7.0000 | IN_CANDIDATE_POOL |

### llm_latin_to_ko: 회귀

| queue_id | raw_product_names | query_cores | reconstructed_fragrance_latin | gold_fragrantica_name | gold_enko_transliteration | gold_llm_korean_transliteration | baseline_rank | gold_candidate_rank | catalog_status |
|---|---|---|---|---|---|---|---|---|---|

## 실패 유형 구분

언어 표시는 사후 설명용 일반 marker다. French/Italian marker 또는 비ASCII 철자를 식별하며 점수나 후보 선택에는 쓰지 않았다. marker가 없다는 이유만으로 실제 어원을 영어로 단정하지 않는다.

### 이름 언어·숫자·variant·짧은 query 진단 (LLM rescue/regression 사례)

| queue_id | method | gold_fragrantica_name | language_signal | number_year_version | variant_flanker | query_information_limited | baseline_rank | gold_candidate_rank | catalog_status |
|---|---|---|---|---|---|---|---|---|---|
| D001 | llm_ko_to_latin | Fresia | NO_FRENCH_ITALIAN_MARKER | True | False | False | 22.0000 | 1.0000 | IN_CANDIDATE_POOL |
| D001 | llm_latin_to_ko | Fresia | NO_FRENCH_ITALIAN_MARKER | True | False | False | 22.0000 | 1.0000 | IN_CANDIDATE_POOL |
| D007 | llm_ko_to_latin | Red Roses | NO_FRENCH_ITALIAN_MARKER | False | False | False | 34.0000 | 2.0000 | IN_CANDIDATE_POOL |
| D007 | llm_latin_to_ko | Red Roses | NO_FRENCH_ITALIAN_MARKER | False | False | False | 34.0000 | 2.0000 | IN_CANDIDATE_POOL |
| D013 | llm_ko_to_latin | Blanche | NO_FRENCH_ITALIAN_MARKER | False | False | False | 6.0000 | 1.0000 | IN_CANDIDATE_POOL |
| D013 | llm_latin_to_ko | Blanche | NO_FRENCH_ITALIAN_MARKER | False | False | False | 6.0000 | 1.0000 | IN_CANDIDATE_POOL |
| D016 | llm_ko_to_latin | Miss Dior Eau de Parfum (2021) | FRENCH_MARKER | True | False | False | 19.0000 | 2.0000 | IN_CANDIDATE_POOL |
| D016 | llm_latin_to_ko | Miss Dior Eau de Parfum (2021) | FRENCH_MARKER | True | False | False | 19.0000 | 2.0000 | IN_CANDIDATE_POOL |
| D021 | llm_ko_to_latin | Libre | NO_FRENCH_ITALIAN_MARKER | False | False | False | 16.0000 | 2.0000 | IN_CANDIDATE_POOL |
| D021 | llm_latin_to_ko | Libre | NO_FRENCH_ITALIAN_MARKER | False | False | False | 16.0000 | 2.0000 | IN_CANDIDATE_POOL |
| D022 | llm_ko_to_latin | Le Sel D'Issey Eau de Parfum | FRENCH_MARKER | False | True | False | 6.0000 | 1.0000 | IN_CANDIDATE_POOL |
| D022 | llm_latin_to_ko | Le Sel D'Issey Eau de Parfum | FRENCH_MARKER | False | True | False | 6.0000 | 1.0000 | IN_CANDIDATE_POOL |
| D028 | llm_ko_to_latin | Dior Homme Cologne 2022 | FRENCH_MARKER | True | False | False | 12.0000 | 3.0000 | IN_CANDIDATE_POOL |
| D028 | llm_latin_to_ko | Dior Homme Cologne 2022 | FRENCH_MARKER | True | False | False | 12.0000 | 3.0000 | IN_CANDIDATE_POOL |
| D030 | llm_latin_to_ko | Polo | NO_FRENCH_ITALIAN_MARKER | False | False | False | 14.0000 | 7.0000 | IN_CANDIDATE_POOL |
| D038 | llm_ko_to_latin | Acqua di Parma Blu Mediterraneo - Fico di Amalfi | ITALIAN_MARKER | False | False | False | 46.0000 | 3.0000 | IN_CANDIDATE_POOL |
| D038 | llm_latin_to_ko | Acqua di Parma Blu Mediterraneo - Fico di Amalfi | ITALIAN_MARKER | False | False | False | 46.0000 | 3.0000 | IN_CANDIDATE_POOL |
| D039 | llm_ko_to_latin | Chloé Eau de Parfum Naturelle | FRENCH_MARKER | False | False | False | 13.0000 | 1.0000 | IN_CANDIDATE_POOL |
| D039 | llm_latin_to_ko | Chloé Eau de Parfum Naturelle | FRENCH_MARKER | False | False | False | 13.0000 | 1.0000 | IN_CANDIDATE_POOL |
| D051 | llm_ko_to_latin | Eros Flame | NO_FRENCH_ITALIAN_MARKER | False | False | False | 6.0000 | 1.0000 | IN_CANDIDATE_POOL |
| D051 | llm_latin_to_ko | Eros Flame | NO_FRENCH_ITALIAN_MARKER | False | False | False | 6.0000 | 1.0000 | IN_CANDIDATE_POOL |
| D061 | llm_ko_to_latin | Blue Orchid | NO_FRENCH_ITALIAN_MARKER | False | False | False | 7.0000 | 1.0000 | IN_CANDIDATE_POOL |
| D061 | llm_latin_to_ko | Blue Orchid | NO_FRENCH_ITALIAN_MARKER | False | False | False | 7.0000 | 1.0000 | IN_CANDIDATE_POOL |
| D072 | llm_ko_to_latin | Hacivat | NO_FRENCH_ITALIAN_MARKER | False | False | False | 7.0000 | 1.0000 | IN_CANDIDATE_POOL |
| D072 | llm_latin_to_ko | Hacivat | NO_FRENCH_ITALIAN_MARKER | False | False | False | 7.0000 | 2.0000 | IN_CANDIDATE_POOL |

### Candidate pool 내부 Top10 실패

| queue_id | method | raw_product_names | reconstructed_fragrance_latin | gold_fragrantica_name | baseline_rank | gold_candidate_rank |
|---|---|---|---|---|---|---|
| D029 | llm_ko_to_latin | ["시그니처 EDP"] | Signature | Chloé Eau de Parfum | 32.0000 | 68.0000 |
| D029 | llm_latin_to_ko | ["시그니처 EDP"] | Signature | Chloé Eau de Parfum | 32.0000 | 57.0000 |
| D030 | llm_ko_to_latin | ["랄프로렌 폴로 랄프 EDT 30ml,50ml 단품/기획 중 택 1"] | Ralph | Polo | 14.0000 | 43.0000 |
| D059 | llm_ko_to_latin | ["우먼 EDT 40ML"] | Woman | Jimmy Choo Eau de Toilette | 14.0000 | 32.0000 |
| D059 | llm_latin_to_ko | ["우먼 EDT 40ML"] | Woman | Jimmy Choo Eau de Toilette | 14.0000 | 19.0000 |

- 영어 이름에서는 `Red Roses`와 `Eros Flame`이 두 LLM 모두 Top5 rescue한 반면, 일반적인 국내 표기 `Signature`만으로 `Chloé Eau de Parfum`을, `Woman`만으로 `Jimmy Choo Eau de Toilette`를 특정하지 못해 두 방향 모두 Top10 밖이었다.
- French 계열 표기의 `Blanche`, `Libre`, `Le Sel d'Issey`, `Chloé ... Naturelle`은 두 LLM에서 모두 개선됐다. 이 사례들에서 고정 Latin→KO 출력은 국내 관용 표기에 전용 en→ko 출력보다 가까웠지만, 이 소표본만으로 언어 일반화를 주장하지 않는다.
- Italian 이름 `Fico di Amalfi`는 baseline 46위에서 두 LLM 모두 3위로 올랐다. 긴 Fragrantica core 속 핵심 이름을 KO→Latin reconstruction 또는 더 적합한 KO 음역이 보존한 사례다.
- 숫자/연도/버전에서는 `Firenze 1221 Edition Fresia`, `Miss Dior ... (2021)`, `Dior Homme Cologne 2022`가 rescue됐다. 다만 올바른 flanker 구분 능력은 별도 검증하지 않았고, 숫자가 있는 것 자체를 성공 원인으로 단정하지 않는다.
- variant/flanker에서는 `Le Sel d'Issey` EDT(D012)는 baseline부터 1위였고 EDP(D022)는 두 LLM이 1위로 rescue했다. 반면 `Glow`(D002)는 concentration/form filter에서 빠져 이름 representation으로 평가할 수 없었다.
- 국내 query 정보가 부족한 `Signature`(D029)와 `Woman`(D059)은 두 LLM 모두 실패했다. D030은 정규화 core에 상품 선택 문구가 남고 KO→Latin이 `Ralph`로 재구성해 Gold `Polo`와 어긋났지만, Latin→KO는 한국어 `폴로` 증거로 7위에 들어 유일한 Top10 단독 rescue가 됐다.

### CATALOG_MISSING (2)

| queue_id | raw_product_names | gold_fragrantica_name | catalog_status |
|---|---|---|---|
| D037 | ["[엔믹스규진PICK] 에틀리에 오 드 퍼퓸 트와일라잇블룸 30ml/10ml"] | Etlee Twilight Bloom | CATALOG_MISSING |
| D054 | ["[NEW/기획] 아뜰리에페이 퍼퓸 30ml 데이오프", "데이 오프"] | Day Off | CATALOG_MISSING |

### BRAND_BLOCKED (7)

| queue_id | raw_product_names | gold_fragrantica_name | catalog_status |
|---|---|---|---|
| D018 | ["[보이넥스트도어 PICK] 에끌로에 오 드 퍼퓸 EDP 50ml"] | Echloe | BRAND_BLOCKED |
| D026 | ["오 드 퍼퓸 페더 10ml"] | Feather | BRAND_BLOCKED |
| D042 | ["퍼퓸 솝클린솝 50ml"] | Soap Clean Soap | BRAND_BLOCKED |
| D043 | ["오리지널 머스크 향수"] | Original Musk | BRAND_BLOCKED |
| D045 | ["[기획] 알보우 케이스 스터디 EDP 30ml 상탈 블루 (+핸드크림)"] | Santal Bleu | BRAND_BLOCKED |
| D056 | ["[에탄올 FREE] 에이딕트 헤어 퍼퓸 30ml 버베나 레인 (단품/기획)"] | Verbena Rain | BRAND_BLOCKED |
| D058 | ["아쿠아 다이브 퍼퓸 50ml", "아쿠아 다이브 퍼퓸"] | Acqua Dive | BRAND_BLOCKED |

### CONCENTRATION_OR_FORM_FILTER (1)

| queue_id | raw_product_names | gold_fragrantica_name | catalog_status |
|---|---|---|---|
| D002 | ["[단독기획] 제니퍼로페즈 글로우 바이제이로 EDT 100ml 기획(+프로미스 바디로션)"] | Glow | CONCENTRATION_OR_FORM_FILTER |

위 세 pool 진단은 모든 방법에 공통이며 이름 ranking 실패로 해석하지 않는다. 특히 pool 밖 Gold는 어느 representation도 rescue할 수 없다. FAMILY_VARIANT_RISK는 variant/flanker 위험, SHORT_GENERIC_NAME은 국내 query 정보 부족의 사전 challenge label로만 사용했다.

## 판단

1. **LLM KO→Latin**: baseline 대비 ΔR@5=+0.1967, ΔR@10=+0.1148, ΔMRR=+0.2118. 전용 en→ko 대비 ΔR@5=+0.1148, ΔR@10=+0.0492, ΔMRR=+0.0978.
2. **LLM Latin→KO**: 전용 en→ko 대비 ΔR@5=+0.1148, ΔR@10=+0.0656, ΔMRR=+0.0953.
3. **실패 중첩/보완성**: baseline Top5 miss에서 KO→Latin만 0, Latin→KO만 0, 둘 다 12; Top10에서는 각각 0, 1, 7다. 방향별 단독 rescue가 있으면 오류 구조가 완전히 같지는 않다는 관찰 근거지만 fusion의 순효과는 측정하지 않았다.
4. **다음 단계**: 단일 채널 선택은 전체·challenge slice와 regression을 함께 보고 판단한다. KO→Latin UNCERTAIN Gold 9건 중 pool 내부는 2건뿐이라 낮은 status slice 성능에는 pool 부재가 크게 섞여 있다. 따라서 status별 차이나 방향별 단독 rescue를 이 DEV에서 새 gating 규칙의 근거로 사용하지 않았다. selective/gated retrieval은 별도 사전 규칙과 독립 평가셋을 둔 후 연구할 수 있는 후보일 뿐, 이번 결과에는 구현하지 않았다.

최고 수치만으로 결론내리지 않았으며, 61개 DEV MATCH의 표본 변동성과 candidate-pool 상한 때문에 일반화는 미확인이다.

## 재현성 및 입력 검증

```json
{
  "ko_to_latin_rows": 77,
  "ko_to_latin_duplicate_ids": 0,
  "ko_to_latin_missing_identity_ids": 0,
  "ko_to_latin_extra_identity_ids": 0,
  "ko_to_latin_status_counts": {
    "OK": 53,
    "UNCERTAIN": 23,
    "UNKNOWN": 1
  },
  "ko_to_latin_blank_outputs": 1,
  "latin_to_ko_rows": 2450,
  "latin_to_ko_unique_cores": 2450,
  "latin_to_ko_duplicate_core_ids": 0,
  "latin_to_ko_duplicate_latin_cores": 0,
  "latin_to_ko_missing_method2_cores": 0,
  "latin_to_ko_extra_cores": 0,
  "latin_to_ko_status_counts": {
    "OK": 1621,
    "UNCERTAIN": 829
  },
  "latin_to_ko_blank_outputs": 0,
  "candidate_rows": 2570,
  "candidate_unique_ids": 2570,
  "candidate_unique_cores": 2450,
  "core_id_sha256_prefix_valid": true
}
```

- 고정 LLM 파일 SHA-256은 제공값과 정확히 일치했다.
- KO→Latin ID는 eligible DEV 77개와 정확히 1:1이고 query_cores도 Method 2 runtime 값과 전수 일치했다.
- Latin→KO core_id는 `SHA256(latin_core)[:16]`과 전수 일치했고, 2,450 Latin core 집합은 Method 2 candidate unique core 집합과 정확히 같다. 2,570 candidate ID 모두 exact core로 연결됐다.
- 기존 Method 2 results 231행, metrics 전체, candidate representations 2,570행을 재실행 결과와 전수 비교했다.
- 실행 중 모든 입력 hash가 불변임을 종료 직전에 다시 확인했다.

### 실행 시간 (wall-clock seconds)

```json
{
  "method2_reproduction_seconds": 6.577482599997893,
  "method2_internal": {
    "baseline_and_query_normalization_seconds": 1.1511809001676738,
    "uroman_normalization_and_ranking_seconds": 3.512554000131786,
    "transliteration_generation": {
      "cache_hits": 2450,
      "generated_cores": 0,
      "stage_seconds": 0.0089069998357445,
      "cached_generation_seconds": 96.42589190159924,
      "cache_path": "cache\\method2\\transliterations_f32eb198f42edb163d9824986abc1e074816cae09baa87f36435363aaf96a434.json",
      "cache_sha256": "659c3ea0d80e829b4d58575af7e7c225b02b6cd710f5a761fd8959bec010c626"
    },
    "enko_jamo_ranking_seconds": 0.15194029989652336
  },
  "llm_validation_and_ranking_seconds": 0.2718752999790013,
  "evaluation_and_metrics_seconds": 0.29950099997222424,
  "total_before_report_seconds": 8.156196400057524
}
```
- Python 3.11.9, Unicode database 14.0.0, pandas 3.0.5, uroman 1.3.1.1.
- 실행: `venv/Scripts/python.exe evaluate_fragrantica_method3_dev.py`

### 입력 SHA-256

- `data\korea_popularity\evaluation\gold_set_dev.csv`: `41d5b84b30289dd24d3822c552cc100890d009600aa8a310234b2160ec37ad2f`
- `data\korea_popularity\snapshot_pre_brand_mapping\korea_commercial_identities.csv`: `069a30ca2c053ba0222f66aa529996b61ede12df8bb97f743f8c3a2718787588`
- `perfumes.csv`: `cec1ea0b498853032bcf44d33ad52ac83e2ed2896b67d5a2765d90a0345cc055`
- `data\korea_popularity\snapshot_pre_brand_mapping\korea_commercial_identity_members.csv`: `b27d8c8accccb4afbe513c748a00ed1d1b3479595b054bf42992e7952d0bcf74`
- `data\korea_popularity\snapshot_pre_brand_mapping\korea_candidate_families.csv`: `b853a639e9d707ac03e25e012cb16cf184703f56fa27c1c5d475e828debf749d`
- `data\korea_popularity\evaluation\fragrantica_matcher_baseline_dev_results.csv`: `d8dc3592a5797186349e161ba171d22b28aabdd5601ab5d2c56ab96e2adadb82`
- `data\korea_popularity\evaluation\fragrantica_matcher_baseline_dev_report.md`: `676583feff22347cc72380c732b29e90531d192ea1bb1b6ee5b9f56b64bb70e9`
- `data\korea_popularity\evaluation\fragrantica_method2_dev_results.csv`: `d15d31f22d3e1b2e50992d6b6b29a0950058438eee6c757c0575d1bc2daf3a34`
- `data\korea_popularity\evaluation\fragrantica_method2_dev_metrics.csv`: `9fecece93a539b7e7eb9feaf2f11cd93fcf00e8ffa88c0e157654ec3e9434bbb`
- `data\korea_popularity\evaluation\fragrantica_method2_dev_candidate_transliterations.csv`: `a4f4c39adccbf7a99b97f6cd01523114a3f90d8a3886abb9c107d8c137c5d1b6`
- `data\korea_popularity\evaluation\fragrantica_method2_dev_report.md`: `5187caea980fbd8539635ed3d915b38104f6eb81539c01705db59fd3fadb4c12`
- `data\korea_popularity\evaluation\fragrantica_method2_dev_settings.json`: `c9988941199d9336f04035ce3b2e45ed5f402ec8226e26ed6cc584ca5bcd912c`
- `data\korea_popularity\evaluation\llm_ko_to_latin_outputs.csv`: `8a4345e467ff6f2867f7cb512c555da95f10cc01ffc22e8e5a315e955ded20cb`
- `data\korea_popularity\evaluation\llm_latin_to_ko_outputs.csv`: `3b2082956f6f9de884790d5a8252eb02c8b4768fefef3842e01dfddb6279bc40`
- `src\korea\build_korea_popularity_map.py`: `b5b4466e1a7f959634854fa0cd4459ca56cf104ffa06016e76a5efb51d4bcfef`
- `src\matching\evaluate_fragrantica_matcher_dev.py`: `46989d4d0a7e5e4849b122c74305fcd65ea1421c0685c682f3a1757215f5ceb1`
- `src\matching\evaluate_fragrantica_method1_dev.py`: `427560d701c93a8e512df5ca4509eaf0e16e8b10659f307abd40d98bcab8e96e`
- `src\matching\evaluate_fragrantica_method2_dev.py`: `5c80ea67a5c041d4dd07995a746412d8b2d19206d91f3f542433e16d3b823fdd`
- `src\matching\evaluate_fragrantica_method3_dev.py`: `0541a2a421207c0680f09da8bc32078e3ada6bcaa4dad165bf5d46ab247cf33d`
- `data\korea_popularity\evaluation\fragrantica_method3_dev_settings.json`: `14db3e6ee6e92a8945bac9b0f4aa025f04a5805397d4fdea2f33c730de1e884a`
- `cache\method2\transliterations_f32eb198f42edb163d9824986abc1e074816cae09baa87f36435363aaf96a434.json`: `659c3ea0d80e829b4d58575af7e7c225b02b6cd710f5a761fd8959bec010c626`

### 생성 파일

- `data\korea_popularity\evaluation\fragrantica_method3_dev_settings.json`
- `data\korea_popularity\evaluation\fragrantica_method3_dev_results.csv`
- `data\korea_popularity\evaluation\fragrantica_method3_dev_metrics.csv`
- `data\korea_popularity\evaluation\fragrantica_method3_dev_llm_status_metrics.csv`
- `data\korea_popularity\evaluation\fragrantica_method3_dev_llm_direction_comparison.csv`
- `data\korea_popularity\evaluation\fragrantica_method3_dev_candidate_representations.csv`
- `data\korea_popularity\evaluation\fragrantica_method3_dev_report.md`

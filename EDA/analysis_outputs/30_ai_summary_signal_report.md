# `ai_summary` 로 본 표현↔accord 신호

## 질문

사람들이 특정 표현으로 부른 향수들이 **실제로 어떤 accord 를 갖는가.**
사전 매핑 28행이 전부 `status=candidate` 이고 의미 판정 근거가 없어서 측정했다.

## 입력 — 이번에 처음 쓰는 필드

`perfumes.jsonl` 의 `ai_summary.pros/cons`. `SCHEMA.md` 에 따르면
*"Fragrantica 의 AI-요약 의견; `up_votes`/`down_votes` = 동의/비동의한 사용자 수"* 다.

| | |
|---|---:|
| 향수 | 131,930 |
| `ai_summary` 보유 | 12,432 (9.4%) |
| 서술문 | 210,521 |
| accord 와 둘 다 보유 | 12,411 |

**`perfumes.csv` 에는 이 필드가 없다.** 59개 컬럼 중 서술 관련은 `description` 하나뿐이다.

## 커버리지 편향 — 먼저 읽어야 할 것

| 구분 | 향수 수 | 평가자 수 중앙값 | 인기도 중앙값 |
|---|---:|---:|---:|
| `ai_summary` 있음 | 12,432 | 628 | 3,290 |
| 없음 | 119,498 | 9 | 67 |

**이 필드는 평가자가 많은 향수에 붙는다.** 따라서 여기서 나온 신호는
'대중적으로 많이 쓰이는 향수에서의 표현↔accord 관계' 이고, 롱테일에는 적용을 보증할 수 없다.

## 통제군 — 방법이 신호를 만들어내지 않는가

표현과 무관하게 같은 크기로 무작위 추출한 집단에서 같은 계산을 했다.

| 통제군 | accord 수 | 최대 배수 | 배수 1.5 이상 |
|---|---:|---:|---:|
| n=500 | 29 | 1.17 | 0 |
| n=1000 | 42 | 1.38 | 0 |
| n=2500 | 52 | 1.14 | 0 |

무작위 집단의 최대 배수가 1.38 다. 아래 표현별 배수와 비교해 읽는다.

## 표현별 상위 accord

`*` 는 검색어가 accord 이름과 같아 순환인 항목이며 신호로 읽지 않는다.

| 표현 | 해당 향수 | 상위 accord (배수) | 비고 |
|---|---:|---|---|
| 포근한 | 2,756 | `savory` 3.72x · `nutty` 2.03x · `cacao` 2.01x · `lactonic` 2.00x · `almond` 1.81x | |
| 깨끗한 | 4,044 | `soapy` 2.18x · `aquatic` 1.77x · `aldehydic` 1.73x · `ozonic` 1.63x · `fresh` 1.61x | |
| 빨래 | 957 | `soapy` 4.50x · `aldehydic` 2.94x · `aquatic` 1.92x · `ozonic` 1.80x · `fresh`* 1.77x | |
| 이불 | 112 | `caramel` 7.36x · `powdery` 1.57x · `musky` 1.45x · `vanilla` 1.34x · `sweet` 1.31x | |
| 비 오는 숲 | 241 | `mossy` 3.63x · `ozonic` 3.16x · `earthy` 3.04x · `aquatic` 3.03x · `green` 2.00x | |
| 차가운 | 4,010 | `cinnamon` 1.74x · `chocolate` 1.52x · `rum` 1.51x · `tobacco` 1.51x · `metallic` 1.49x | |
| 촉촉한 | 368 | `aquatic` 3.30x · `ozonic` 2.86x · `rose` 2.26x · `green` 2.12x · `fresh` 1.93x | |
| 휴양지 | 1,211 | `coconut` 5.76x · `tropical`* 5.74x · `salty` 4.16x · `marine` 3.07x · `lactonic` 2.07x | |
| 호텔 | 1,163 | `Champagne` 6.96x · `aldehydic` 2.39x · `fresh` 1.52x · `herbal` 1.37x · `green` 1.33x | |
| 머스크 | 653 | `musky`* 2.19x · `iris` 1.46x · `violet` 1.43x · `powdery` 1.37x · `floral` 1.36x | |
| 달달 | 6,169 | `caramel` 1.61x · `nutty` 1.47x · `sour` 1.42x · `almond` 1.41x · `lactonic` 1.41x | |
| 무난한 | 6,217 | `camphor` 1.30x · `bitter` 1.27x · `salty` 1.27x · `marine` 1.25x · `lavender` 1.22x | |
| 고급스러운 | 6,966 | `iris` 1.38x · `tuberose` 1.27x · `violet` 1.24x · `oud` 1.22x · `yellow floral` 1.22x | |
| 도시적인 | 1,611 | `aldehydic` 2.29x · `mossy` 1.93x · `lavender` 1.80x · `earthy` 1.60x · `herbal` 1.40x | |
| 섹시한 | 1,645 | `rum` 1.73x · `cherry` 1.69x · `coffee` 1.58x · `patchouli` 1.54x · `cinnamon` 1.52x | |
| 자연스러운 | 1,830 | `conifer` 2.39x · `herbal` 2.00x · `green` 1.69x · `mossy` 1.38x · `fresh spicy` 1.35x | |
| 향긋한 | 18 | — | 표본 부족 |
| 무거운 | 5,666 | `caramel` 1.49x · `nutty` 1.38x · `savory` 1.37x · `chocolate` 1.35x · `almond` 1.34x | |
| 가벼운 | 2,721 | `soapy` 1.62x · `aquatic` 1.43x · `ozonic` 1.41x · `aldehydic` 1.34x · `floral` 1.30x | |

## 사전 대조

| entry_id | 표현 | accord | required | 등급 | 배수 | 판정 |
|---|---|---|---|---|---:|---|
| `kr.drift.musk` | 머스크 | `musky` | core | VERIFIED | 2.19 | 순환 — 신호로 읽지 않음 |
| `kr.drift.musk` | 머스크 | `soapy` | core | TEAM |  | 반증 — 해당군에 지지도 없음 |
| `kr.drift.musk` | 머스크 | `fresh` | optional | LLM | 1.27 | 약함 |
| `kr.ctx.clean` | 깨끗한 | `soapy` | core | TEAM | 2.18 | 지지 |
| `kr.ctx.clean` | 깨끗한 | `fresh` | core | LLM | 1.61 | 지지 |
| `kr.ctx.clean` | 깨끗한 | `aquatic` | core | TEAM | 1.77 | 지지 |
| `kr.ctx.clean` | 깨끗한 | `fresh` | core | TEAM | 1.61 | 지지 |
| `kr.scene.laundry` | 빨래 | `soapy` | core | TEAM | 4.50 | 지지 |
| `kr.scene.laundry` | 빨래 | `fresh` | core | TEAM | 1.77 | 순환 — 신호로 읽지 않음 |
| `kr.sens.cozy` | 포근한 | `powdery` | core | TEAM | 1.35 | 약함 |
| `kr.sens.cozy` | 포근한 | `musky` | core | TEAM | 1.12 | 약함 |
| `kr.sens.cozy` | 포근한 | `vanilla` | optional | TEAM | 1.56 | 지지 |
| `kr.scene.bedding` | 이불 | `powdery` | core | TEAM | 1.57 | 지지 |
| `kr.scene.bedding` | 이불 | `soapy` | core | TEAM |  | 반증 — 해당군에 지지도 없음 |
| `kr.scene.bedding` | 이불 | `musky` | optional | LLM | 1.45 | 약함 |
| `kr.scene.rainy_forest` | 비 오는 숲 | `mossy` | core | TEAM | 3.63 | 지지 |
| `kr.scene.rainy_forest` | 비 오는 숲 | `earthy` | core | TEAM | 3.04 | 지지 |
| `kr.scene.rainy_forest` | 비 오는 숲 | `green` | optional | LLM | 2.00 | 지지 |
| `kr.sens.cold` | 차가운 | `ozonic` | core | TEAM | 0.83 | 반증 — 전체보다 드물다 |
| `kr.sens.cold` | 차가운 | `fresh` | core | TEAM | 0.91 | 반증 — 전체보다 드물다 |
| `kr.sens.dewy` | 촉촉한 | `aquatic` | core | TEAM | 3.30 | 지지 |
| `kr.sens.dewy` | 촉촉한 | `green` | core | TEAM | 2.12 | 지지 |
| `kr.scene.resort` | 휴양지 | `tropical` | core | TEAM | 5.74 | 순환 — 신호로 읽지 않음 |
| `kr.scene.resort` | 휴양지 | `coconut` | core | LLM | 5.76 | 지지 |
| `kr.scene.hotel` | 호텔 | `soapy` | core | TEAM |  | 반증 — 해당군에 지지도 없음 |
| `kr.scene.hotel` | 호텔 | `white floral` | core | LLM | 1.10 | 약함 |
| `kr.dial.sweet` | 달달 | `sweet` | core | VERIFIED | 1.26 | 순환 — 신호로 읽지 않음 |
| `kr.dial.sweet` | 달달 | `caramel` | core | LLM | 1.61 | 지지 |

판정 집계: {'지지': 14, '약함': 5, '순환 — 신호로 읽지 않음': 4, '반증 — 해당군에 지지도 없음': 3, '반증 — 전체보다 드물다': 2}

## 한계

- **전문 조향사·공식 기관 근거가 아니다.** Fragrantica 의 AI 가 사용자 리뷰를 요약한 것이다.
  투표로 검증된 대중 의견이라는 점이 커뮤니티 글 1~2건보다 나을 뿐이다
- **출처가 Fragrantica 다.** `spec.md` §8 의 `ai-train=no` · EU 권리유보 문제가 그대로 적용된다.
  서비스에 쓰려면 그 판단이 선행돼야 한다
- **영어 서술이다.** `포근한 = cozy` 라는 번역 가정이 한 단계 들어간다.
  일반 번역이라 향 도메인 추론보다 약한 가정이지만 가정은 가정이다
- **커버리지가 9.4% 이고 인기 향수에 쏠려 있다** (위 표)
- **부분 문자열 검색이다.** `light` 가 `lighthearted` 에 걸리는 잡음을 제거하지 않았다
- **투표수를 쓰지 않았다.** 서술문의 존재 여부만 봤다. 동의 수를 가중하면 결과가 달라질 수 있다
- **6개 표현은 이 노트북 작성 전에 결과를 봤다** (`6개 표현(포근한·빨래·깨끗한·휴양지·무난한·고급스러운)은 이 노트북 작성 전에 탐색으로 결과를 봤다. 그때...`).
  영어 대응어를 바꾸지 않았고 보지 않은 표현도 전부 포함했다
- **인과가 아니다.** 배수가 높다는 것은 동반 출현이 잦다는 뜻이지
  그 accord 가 그 표현의 원인이라는 뜻이 아니다

## 재현 방법

```bash
cd EDA
export PYTHONIOENCODING=utf-8
# 30_ai_summary_expression_accord.ipynb 를 REPORT_ONLY=False 로 실행
# API 호출 0회. 재현 게이트(accord 92개 perfume_count)가 먼저 통과해야 진행된다
```

## 관련 자료

- `SCHEMA.md` — `ai_summary` 필드 정의
- `data/scent_knowledge/domain_lexicon_v1.csv` — 대조 대상
- `docs/nlr_engineering_notes.md` 9번 — 전문가 조사 (개별 표현 근거 0건)
- `docs/spec.md` §8 남은 작업 5번 — 질감층. `무거운`·`가벼운` 을 여기서 측정했다

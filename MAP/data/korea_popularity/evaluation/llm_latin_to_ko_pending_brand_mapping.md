# llm_latin_to_ko 추가 입력 요청 — 새 후보 Latin core

브랜드 매핑으로 후보 풀에 새로 들어온 향수 이름 **56종**이다.
이 표현이 없으면 `llm_latin_to_ko` 방향은 측정할 수 없다(없는 값을 코드가 만들지 않는다).

## 지켜야 할 조건

- 기존 2,450종을 만들 때와 **같은 방식**으로 만든다: 비개인화 Temporary Chat,
  Gold 정답·후보 목록·기존 결과를 보여주지 않는다.
- LLM에게 주는 것은 **Latin core 문자열뿐**이다. 브랜드도 주지 않는다.
  기존 2,450종이 그렇게 만들어졌고, 입력 정보를 늘리면 같은 방법이 아니게 된다.
- LLM은 이름 표기만 만든다. 어떤 향수가 정답인지 고르게 하지 않는다.
- 결과는 `llm_latin_to_ko_pending_brand_mapping.csv`의 빈 두 열을 채워
  `llm_latin_to_ko_outputs_brand_mapping.csv`로 저장한다.
  기존 `llm_latin_to_ko_outputs.csv`는 수정하지 않는다(method3가 해시로 고정).

## 붙여넣을 지시문

아래 규칙은 기존 `llm_latin_to_ko_outputs.csv` 2,450행에서 **실제로 관찰된 관례**다
(원본 프롬프트는 기록돼 있지 않아 출력 관례에서 역으로 정리했다 — §한계 참조).

```text
아래는 향수 이름의 라틴 문자 표기 목록이다.
각 줄을 한국 향수 소비자가 실제로 쓰는 한국어 음역으로 바꿔라.

규칙
- 의미를 번역하지 말고 발음을 한글로 적는다. (Cool Cotton -> 쿨 코튼)
- 프랑스어·이탈리아어 등 원어 발음을 따른다. (J'adore -> 쟈도르)
- 숫자·기호·알파벳만으로 된 표기는 그대로 둔다. (N°19 -> N°19, M7 -> M 7, XX -> XX)
- 표기에 이미 한글이 들어 있으면 그 한글을 그대로 쓴다. (Daenamu 대나무 -> 대나무)
- 확신이 없으면 추측을 적되 status를 UNCERTAIN으로 표시한다.
- 전혀 판단할 수 없으면 표기는 비우고 status를 UNKNOWN으로 표시한다.
- 어떤 향수가 무엇과 같은 제품인지 고르지 말고, 표기 변환만 한다.

출력 형식: 입력 순서 그대로, 줄마다 `원문<TAB>한국어 음역<TAB>OK|UNCERTAIN|UNKNOWN`
```

## 선례가 없는 케이스 — 표기에 한글이 이미 들어 있는 6종

기존 2,450행에는 `latin_core`에 한글이 있는 행이 **0건**이라 참고할 관례가 없다.
이번 입력에는 `Chwi 취` 브랜드에서 6종이 들어온다
(`Daenamu 대나무`, `Hwawon 화원`, `Odii 오디`, `Sachal 사찰`, `Ssook 쑥`, `Sumuk 수묵`).

위 지시문은 **이미 있는 한글을 쓰는 것**을 기본값으로 잡았다. 로마자 부분이 그 한글의
로마자 표기라 중복이기 때문이다. 이 판단은 지표에 영향을 주지 않는다 —
해당 Commercial Identity(D074)는 Gold NO_MATCH라 R@k·MRR 계산에 들어가지 않는다.
다른 규칙을 쓰고 싶으면 지시문을 바꾸고 그 사실을 기록하면 된다.

## 기존 파일에서 관찰된 사실 (참고)

- `reconstruction_status` 분포: OK 1,621 / UNCERTAIN 829. **UNKNOWN은 한 번도 쓰이지 않았다.**
- 빈 음역 0건.
- 음역에 한글이 없는 행 7건: `N°19`, `N°22`, `M7`→`M 7`, `154`, `352`, `XX`, `N°19 2023`.

## 한계

- **기존 2,450행을 만든 원본 프롬프트가 저장돼 있지 않다.** 그래서 이번 지시문은 같은
  프롬프트가 아니라 같은 *출력 관례*를 목표로 한 재구성이다. 두 방향 비교 결과를 읽을 때
  이 차이를 감안해야 한다. 이번 지시문은 이 파일에 남겨 다음부터는 재현 가능하게 한다.

## 입력 56줄

```text
160th Anniversary Limited Edition Original Musk Oil
ADE
Acqua Dive
After Bath
Aromatic Blends: Fig Leaf & Sage
Aromatic Blends: Nashi Blossom & Pink Grapefruit
Aromatic Blends: Orange Flower & Lychee
Aromatic Blends: Patchouli & Fresh Rose
Aromatic Blends: Vanilla & Cedarwood
Aromatic Blends: Vetiver & Black Tea
Baby Blusher
Bare
Bitter
Blush Princess
Botanik Leaf
Bronze Goddess
Case Study #11 Monsoon
Case Study #12 Dance and Balance
Case Study #16 Atelier Chai
Case Study #23 Amber Sanguine
Case Study #3 O.A.C
Case Study #4 Black Wood
Case Study #8 Lights on Objet
Case Study Untitled RboW X Eddie Kang Edition 500
Daenamu 대나무
Dark Kiss
Everyone
Feather
Forest Rain
Hwawon 화원
Lady in Red
Linen Citrus
Midnight Violet
NEUTRAL
Night Love
Odii 오디
Original Musk
Peony Dream
Pink Romance
Radiant Lily
Rosé Glamour
Sachal 사찰
Santal Bleu
Seduction Gold
Silver Queen
Sleeping Rose
Slow September
Soap Clean Soap
Ssook 쑥
Sumuk 수묵
Sun Kisses
Sunday Cotton
Sweet Heart
Tokyo Fig
Tokyo Stripe
Vanilla Passion
```

## 참고 — 어느 브랜드에서 들어온 이름인지 (LLM에게 주지 말 것)

| Latin core | 유입 브랜드 |
|---|---|
| 160th Anniversary Limited Edition Original Musk Oil | Kiehl's |
| ADE | Tenui |
| Acqua Dive | Dashu |
| After Bath | Sennok |
| Aromatic Blends: Fig Leaf & Sage | Kiehl's |
| Aromatic Blends: Nashi Blossom & Pink Grapefruit | Kiehl's |
| Aromatic Blends: Orange Flower & Lychee | Kiehl's |
| Aromatic Blends: Patchouli & Fresh Rose | Kiehl's |
| Aromatic Blends: Vanilla & Cedarwood | Kiehl's |
| Aromatic Blends: Vetiver & Black Tea | Kiehl's |
| Baby Blusher | Sennok |
| Bare | Tenui |
| Bitter | Tenui |
| Blush Princess | Kiss New York |
| Botanik Leaf | Dashu |
| Bronze Goddess | Kiss New York |
| Case Study #11 Monsoon | RboW |
| Case Study #12 Dance and Balance | RboW |
| Case Study #16 Atelier Chai | RboW |
| Case Study #23 Amber Sanguine | RboW |
| Case Study #3 O.A.C | RboW |
| Case Study #4 Black Wood | RboW |
| Case Study #8 Lights on Objet | RboW |
| Case Study Untitled RboW X Eddie Kang Edition 500 | RboW |
| Daenamu 대나무 | Chwi 취 |
| Dark Kiss | Kiss New York |
| Everyone | Tenui |
| Feather | Tenui |
| Forest Rain | Kiehl's |
| Hwawon 화원 | Chwi 취 |
| Lady in Red | Kiss New York |
| Linen Citrus | Sennok |
| Midnight Violet | Kiss New York |
| NEUTRAL | Tenui |
| Night Love | Kiss New York |
| Odii 오디 | Chwi 취 |
| Original Musk | Kiehl's |
| Peony Dream | Kiss New York |
| Pink Romance | Kiss New York |
| Radiant Lily | Kiss New York |
| Rosé Glamour | Kiss New York |
| Sachal 사찰 | Chwi 취 |
| Santal Bleu | RboW |
| Seduction Gold | Kiss New York |
| Silver Queen | Kiss New York |
| Sleeping Rose | Sennok |
| Slow September | Sennok |
| Soap Clean Soap | Sennok |
| Ssook 쑥 | Chwi 취 |
| Sumuk 수묵 | Chwi 취 |
| Sun Kisses | Kiss New York |
| Sunday Cotton | Dashu |
| Sweet Heart | Kiss New York |
| Tokyo Fig | RboW |
| Tokyo Stripe | RboW |
| Vanilla Passion | Kiss New York |

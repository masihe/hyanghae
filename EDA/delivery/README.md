# 자연어 향수 추천 인계 묶음

사용자가 **한국어 문장**으로 원하는 향을 쓰면 **향수 5개와 각각의 추천 근거**를 돌려주는 기능입니다.

```
"빨래 냄새 나는 향수 찾고 있어"
   -> Laundry (Ostrikov Beauty Publishing)   soapy=100 · fresh=93
      Exit The King (Etat Libre d'Orange)    soapy=100 · fresh=57
      ... 5개
   -> 각 향수가 '빨래'라는 표현의 어느 조건에 어떻게 맞았는지 함께
```

이 폴더는 **밖으로 넘기려고 모아둔 것**입니다. 분석 노트북과 실험 기록은 넘기지 않습니다.

## 표기 규약

- **[측정]** — 실제 데이터에서 확인한 값입니다. 여기에 맞지 않게 만들면 결과가 달라집니다.
- **[제안]** — 저희 판단일 뿐입니다. **참고만 하시고 실제 설계는 담당자분이 정하시면 됩니다.**

---

## 누구에게 무엇을 주면 되나

**`for_backend/` 폴더 하나를 그대로 전달하면 됩니다.**

```
for_backend/
  nlr_reference.py              돌아가는 참조 구현. 이게 규칙의 기준입니다
  app_example.py                FastAPI 예시. 그대로 쓰셔도, 참고만 하셔도 됩니다
  requirements.txt              의존성
  search_rules.md               같은 규칙을 글로. [측정]/[제안] 구분
  domain_lexicon_v1_2.csv       향 사전 44행 — 한국어 표현 -> accord
  10_accord_dictionary.csv      accord 92개 마스터 (검증용)
  example_response.json         장면 쿼리 7개의 실제 응답

verification.json               검증 기록 (내부용. 전달하지 않아도 됩니다)
build_delivery.py               이 폴더를 다시 만드는 스크립트
```

## 확인한 것과 못 한 것

| | 상태 |
|---|---|
| `nlr_reference.py` | **실행 검증 완료.** 장면 쿼리 7개 + 합성 평가셋 600건을 돌렸습니다. `verification.json` 참고 |
| `app_example.py` | **문법 검증만 했습니다.** FastAPI 와 uvicorn 을 분석 환경에 설치하지 않아 띄워보지 못했습니다 |

`app_example.py` 는 `nlr_reference.py` 를 감싸는 얇은 층이라 위험이 낮지만, **처음 띄우실 때 아래 두 가지를 확인해 주십시오.**

```bash
# 1. 기동되는가 — 인덱스 적재에 수십 초 걸립니다
curl localhost:8000/health
# -> {"status":"ok","perfume_count":131930,"accord_count":92,...}

# 2. 결과가 example_response.json 과 같은가
curl -X POST localhost:8000/nlr/recommend \
     -H 'Content-Type: application/json' \
     -d '{"text": "빨래 냄새 나는 향수 찾고 있어"}'
# -> results[0].name 이 "Laundry" 여야 합니다
```

**`perfumes.csv` 는 넣지 않았습니다** (127MB). 이미 갖고 계신 것을 쓰시면 됩니다.
SHA-256 앞자리가 `cec1ea0b49885303` 인 파일 기준으로 만들었습니다.

---

## 5분 만에 돌려보기

```bash
python nlr_reference.py \
    --perfumes   경로/perfumes.csv \
    --lexicon    domain_lexicon_v1_2.csv \
    --accords    10_accord_dictionary.csv \
    "빨래 냄새 나는 향수 찾고 있어"
```

코드에서 쓰실 때는 이렇게 됩니다.

```python
from nlr_reference import load_index, recommend

index = load_index("perfumes.csv", "domain_lexicon_v1_2.csv", "10_accord_dictionary.csv")
out = recommend(index, "빨래 냄새 나는 향수 찾고 있어")
```

`load_index()` 는 한 번만 부르고 재사용하십시오 (13만 건 × 92 accord 행렬을 만듭니다).
필요한 것은 **pandas, numpy** 뿐이고 나머지는 표준 라이브러리입니다.

---

## 지금 어느 정도 되는가 — 실측

합성 평가셋 600건과 장면 쿼리 7개로 잰 값입니다. `verification.json` 에 그대로 있습니다.

| | 결과가 나오는 비율 |
|---|---|
| **LLM 구조화 + 사전** | **466/600 = 77.7%** (갈래A 88.7% · 갈래B 66.7%) |
| **사전만 (LLM 없이)** | **214/600 = 35.7%** (갈래A 39.7% · 갈래B 31.7%) |
| 장면 쿼리 | **4/7** |

**[측정] LLM 구조화가 커버리지의 절반을 만듭니다.** 다만 없어도 돌아가므로 **API 가 죽어도 서비스를 내리지 마십시오.** `recommend()` 의 `conditions` 인자를 생략하면 자동으로 사전만 씁니다.

---

## 특히 주의할 것 4가지

### 1. 평점(`rating_avg`)으로 정렬하면 안 됩니다

평점 5.00 인 향수 8,410개 중 **99.8%가 평가자 10명 이하**입니다. 평점을 정렬에 넣으면 **평가자 1명짜리가 1위**가 됩니다.

대신 **동점일 때만 평가자 수로 깹니다.** 향 조건이 순위를 정하고, 인기도는 동점을 푸는 데만 씁니다.

### 2. 인기도를 점수에 곱하면 안 됩니다

`strength 합 × log(평가자 수)` 를 재봤더니 **인기가 향 조건을 이겼습니다.** `이불` 검색에 `soapy` 가 13밖에 안 되는 향수가 4위로 올라옵니다. 그러면 추천 이유에 *"soapy 13 이 맞았습니다"* 라고 써야 합니다.

### 3. 조건이 하나면 순위가 안 나옵니다

`citrus` 하나로 검색하면 **17,736개가 똑같이 강도 100** 입니다. 그래서 accord 를 **2개 이상** 모았을 때만 AND 검색을 합니다. 하나뿐이면 완화 경로로 갑니다 (`diagnostics.stage` 가 `RELAXED_OR`).

### 4. 결과를 못 내는 22.3%를 비워두면 안 됩니다

600건 중 **134건이 향 조건을 하나도 못 뽑습니다** (`status: "NO_CONDITION"`).
**이때 인기 향수를 대신 보여주지 마십시오** — 추천처럼 보이지만 근거가 없습니다.

응답의 `diagnostics.unmatched_hint` 에 안내 문구가 들어 있습니다.

---

## 아직 안 되는 것

| | 내용 |
|---|---|
| **장면 표현 3개** | `데이트`·`섹시한`·`호텔 라운지` 는 사전에 매핑이 없어 결과가 안 나옵니다 |
| **실사용은 더 어렵습니다** | 설문 155건에서 **48.4%가 조건 0개** 였습니다. 위 22.3%보다 나쁩니다 |
| **사전 44행이 전부 `candidate`** | 서비스에 써도 되는지 팀 판정이 아직 없습니다 |
| **추천 이유 문장화** | 근거(`matched[].rationale`)까지만 만듭니다. 문장으로 바꾸는 LLM 호출은 미구현입니다 |
| **점수 식 미검증** | `strength` 단순 합입니다. 쿼리→향수 점수 식은 검증된 적이 없습니다 |
| **한국어 형태소 분석** | `kiwipiepy` 미설치. 표기 변형은 사전의 `aliases` 나열에 의존합니다 |

---

## 이 폴더를 다시 만들기

사전이나 데이터가 바뀌면 다시 만들면 됩니다.

```bash
venv/Scripts/python.exe delivery/build_delivery.py
```

입력 4개의 해시를 찍고, 사전을 복사하고, 장면 쿼리 7개를 돌려 `example_response.json` 을,
합성 평가셋 600건을 돌려 `verification.json` 을 만듭니다. **원본은 읽기만 합니다.**

## 근거 문서 (개인 저장소에 있습니다)

| 문서 | 내용 |
|---|---|
| `EDA/docs/spec.md` | 설계 전체 |
| `EDA/docs/DECISIONS.md` | 의사결정 기록 N1~N8 |
| `EDA/docs/nlr_engineering_notes.md` | 측정 기록 11건 |

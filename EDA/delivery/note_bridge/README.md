# 노트 브리지 — 엔진 패치 인계

| | |
|---|---|
| 작성 | 2026-09-16 |
| 대상 | 팀 저장소 `ai/nlr_engine.py` |
| 적용 전 HEAD | `3ccd0f8` (develop) |
| 근거 | 측정 기록 **18번**(브리지 규칙 비교) · **19번**(설문 무효 응답) |

**표기** — **[측정]** 은 실제로 잰 값, **[제안]** 은 판단입니다.
`delivery/README.md` 와 같은 관례입니다.

---

## 1. 무엇을 고치나 — 한 줄

**①단계 LLM 이 `scent_preference` 에 넣은 노트(원료) 이름을 accord 로 바꿔 준다.**

```
지금    scent_preference: ["mint"]  ->  _normalize_accord 가 못 알아듣고 **버린다**
패치 후 scent_preference: ["mint"]  ->  aromatic · fresh spicy · green
```

`mint` 는 원료 이름이고 accord 92개 목록에 없습니다. 지금 엔진은 정확 일치·소문자화·
복수형 제거·`e→y` 추측만 하므로 통째로 버립니다. **합성 600문장에서 256회(31.8%)가
이렇게 버려지고 그중 111회(43.4%)가 노트 이름입니다** [측정].

---

## 2. 들어 있는 것

```
nlr_engine.patch              엔진 패치 (추가 99줄 · 삭제 1줄)
data/note_accord_bridge.csv   노트→accord 표 2,925행 · 97 KB
README.md                     이 문서
```

---

## 3. 적용 방법

```bash
cd <팀 저장소 루트>
git apply --check delivery/note_bridge/nlr_engine.patch   # 먼저 확인만
git apply delivery/note_bridge/nlr_engine.patch
cp delivery/note_bridge/data/note_accord_bridge.csv ai/data/
```

**`ai/data/note_accord_bridge.csv` 가 있어야 기능이 켜집니다.**
파일이 없으면 기동 로그에 경고가 남고 **패치 이전과 똑같이 동작합니다.**

```
WARNING 노트 브리지 파일이 없다: .../note_accord_bridge.csv.
        노트 이름(`mint` 등)은 해석하지 않는다. 엔진은 정상 동작하지만
        조건 추출이 이 기능을 얹기 전 수준으로 돌아간다
```

파일이 있으면 이렇게 남습니다.

```
INFO 노트 브리지 2925행 중 p>=0.50 · lift>=1.40 를 통과한 1938행 -> 노트 755개
```

### 되돌리는 법

```bash
git apply -R delivery/note_bridge/nlr_engine.patch
rm ai/data/note_accord_bridge.csv
```

데이터 파일만 지워도 기능은 꺼집니다. **원본 데이터와 사전은 건드리지 않습니다.**

---

## 4. 효과 [측정]

`67_field_assignment_defects.py` · 사전 v1.14 · 합성 600 · **GMS 호출 0회** ·
**엔진에 넣고 다시 확인한 값입니다** (측정 스크립트 결과와 소수점 6자리까지 일치).

| | 패치 전 | **패치 후** |
|---|---:|---:|
| 조건을 뽑은 문장 | 525 · 87.5% | **533 · 88.8%** |
| 평균 조건 수 | 2.52 | 2.79 |
| **NDCG@5** | 0.471540 | **0.496896 (+0.025357)** |
| `AND` (조건 전부 만족) | 397 | **417 (+20)** |
| `SINGLE_BROAD` (조건 1개) | 89 | **73 (−16)** |
| `RELAXED_OR` | 39 | 43 (+4) |
| `NO_CONDITION` (추천 불가) | 75 | **67 (−8)** |
| `NO_RESULT` | 0 | 0 |

짝지은 부트스트랩 20,000회 — **95% 구간 `[+0.016437, +0.035016]`. 0 을 포함하지
않습니다** [측정]. 표본을 다시 뽑아도 부호가 뒤집히지 않습니다.

실사용 설문 143건에서는 정답 라벨이 없어 NDCG 를 못 잽니다. 조건 추출이
60.1% → 60.8%, `AND` 는 57 → 56 입니다 [측정].

### 추가 비용 0

```
형태소 분석기 mecab   +0.0025    서버 메모리 +10MB           (도입 안 함 · N13)
임베딩 e5-base        +0.0347    서버 메모리 +2,022MB         (배포 불가 · N13)
**노트 브리지**        **+0.0254**   **CSV 97KB 를 기동 시 한 번 읽는다**
```

---

## 5. 무엇이 어떻게 바뀌나 — 코드

바뀐 곳은 **네 군데**이고, 동작을 바꾸는 것은 **`understand()` 한 곳**뿐입니다.

| 위치 | 바뀐 것 |
|---|---|
| 상수 | `DEFAULT_NOTE_BRIDGE` · `BRIDGE_P_MIN=0.5` · `BRIDGE_LIFT_MIN=1.4` 추가 |
| `load_index()` | 인자 `bridge_csv` · `bridge_p_min` · `bridge_lift_min` 추가. 전부 기본값이 있어 **기존 호출을 고칠 필요가 없습니다** |
| `_load_note_bridge()` | 새 함수. CSV 를 읽어 `index["note_bridge"]` 를 만듭니다 |
| `_bridge_lookup()` | 새 함수. 단어 하나 → accord 목록 |
| `understand()` | `_normalize_accord` 가 못 푼 값에 브리지를 한 번 더 봅니다 |

### 문턱 두 개를 왜 쓰나

```
p    그 노트를 가진 향수 중 이 accord 를 가진 비율
lift p 를 그 accord 의 기저율로 나눈 값. 1 이면 정보가 없다
```

`p` 만 쓰면 **흔한 accord 가 조건으로 섞입니다.** `woody` 는 전체 향수의 **63.1%** 가
갖고 있어 어떤 노트든 `p >= 0.5` 를 넘깁니다 [측정]. `peony → woody` 는 `p` 0.536 인데
`lift` 0.87 로, **작약이 있으면 오히려 덜 나온다**는 뜻입니다.

`p` 만 쓰면(`lift` 문턱 없음) NDCG 가 0.494445 이고 평균 조건이 2.98 입니다.
**`lift >= 1.4` 를 걸면 조건이 2.79 로 줄었는데 `AND` 가 408 → 417 로 늘었습니다** [측정].

### `1.4` 는 어디서 온 값인가

`DECISIONS.md` **N4** 의 통제군 값입니다. 표현과 무관하게 무작위 추출한 500·1,000·
2,500개 집단에서 배수가 1.17·1.38·1.14 로 **1.4 를 넘지 못했습니다** [측정].

`72_bridge_lift_threshold.py` 로 0~2.5 를 훑었습니다 [측정].

```
0 ~ 1.6   NDCG 가 서로 갈리지 않는다 (부트스트랩 95% 구간이 전부 0 을 포함)
1.7 이상  확실히 나빠진다 (구간이 0 을 넘지 않는다)
```

**평지 안에서 유일하게 근거가 있는 값이라 1.4 를 골랐습니다** [제안].
바꾸려면 `load_index(bridge_lift_min=...)` 인자만 주면 되고 데이터는 그대로입니다.

---

## 6. 팀이 정해야 할 것 — **이 패치에 넣지 않았습니다**

### 추천 근거(`evidence`)를 어떻게 표시할 것인가

브리지가 만든 accord 는 `matched[]` 에서 이렇게 나갑니다.

```json
{ "accord": "aromatic", "strength": 100, "from": null, "tier": null, "rationale": null }
```

`recommend()` 가 원래 `source` 가 없을 때 `null` 을 넣도록 짜여 있어 **코드를 고치지
않았고 응답 스키마도 그대로입니다.** 다만 **지금까지는 `tier` 가 실제로 `null` 이 된
적이 없습니다.**

근거를 붙이려면 `tier` 에 새 값이 필요한데, `docs/nlr_api_contract.md` 가
**`VERIFIED`/`TEAM`/`LLM` 세 값으로 적어 뒀습니다.** 브리지는 셋 중 어디에도 맞지
않습니다 — 정확 일치도, 팀 판단도, LLM 추측도 아니고 **코퍼스에서 잰 동시출현**입니다.

**새 값을 만드는 것은 계약 변경이라 팀이 정할 일입니다.** 정해지면 `understand()` 의
해당 자리에 `evidence.append(...)` 한 줄을 더하면 됩니다. 브리지 CSV 에 `p` 와 `lift`
가 들어 있어 *"민트를 가진 향수의 91% 가 aromatic 을 갖는다"* 같은 문장을 만들 수
있습니다.

### `DECISIONS.md` N14

아직 쓰지 않았습니다. **N2(단독 매핑 금지)와의 관계는 측정으로 확인했습니다** —
브리지는 단독 조건을 **89건 → 73건으로 16건 줄입니다** [측정]. 새로 생긴 단독 조건은
1건인데, 그것도 원래 `NO_CONDITION`(추천 불가)이던 문장이 올라온 것입니다.

---

## 7. 확인하지 못한 것

- **사전 버전이 어긋나 있습니다.** 위 숫자는 전부 **v1.14** 로 잰 것이고 팀 저장소
  기본값은 **v1_8** 입니다. v1_8 로 돌리면 절대값이 달라집니다. 이 패치는 사전
  기본값을 **바꾸지 않습니다** (`NLR_PREDEPLOY_DECISIONS.md` 「사전 버전이 어긋나
  있습니다」 참고)
- **설문 143건에 정답 라벨이 없습니다.** 실사용 NDCG 는 여전히 못 잽니다
- **`AND` 가 설문에서 57 → 56 으로 1건 줍니다.** 모든 브리지 규칙에서 같고, 라벨이
  없어 품질 하락인지 판정할 수 없습니다 [측정]
- **브리지 CSV 의 생성 절차를 확인하지 않았습니다.** `10_query_feature_bridge.ipynb`
  가 만든 표이고, 노트 이름 정규화 방식과 최소 빈도 컷을 모릅니다
- **노트 이름 매칭은 소문자 정확 일치뿐입니다.** `white flower`(단수)는 못 잡고
  `white flowers`(복수)만 잡습니다
- **`p >= 0.5` 의 0.5 는 부트스트랩으로 검정하지 않았습니다.** 표의 순서만 봤고
  0.4 와 0.5 의 NDCG 차이는 0.00004 였습니다 [측정]

---

## 8. 재현

```bash
cd EDA
export PYTHONIOENCODING=utf-8
./venv/Scripts/python.exe -W ignore 67_field_assignment_defects.py   # 규칙 비교
./venv/Scripts/python.exe -W ignore 72_bridge_lift_threshold.py      # 문턱 스윕
```

둘 다 **GMS 호출 0회**이고 파일을 만들지 않습니다. 저장된 ①단계 응답만 읽습니다.

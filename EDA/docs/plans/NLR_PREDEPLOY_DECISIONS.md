# 자연어 추천 — 배포 전 확정이 필요한 것

| | |
|---|---|
| 작성 | 2026-09-16 |
| 작성자 | AI (자연어 추천) |
| 목적 | **인프라 담당이 배포를 시작하기 전에** DB 스키마·적재 관련 결정을 마치기 위함 |
| 쓰는 법 | 이 문서를 놓고 팀 회의에서 안건 ①~④를 정한다. 인프라는 정해진 대로만 작업한다 |
| 근거 | 수동 테스트 DB(`hyanghae-manual-test`) 실측 · 측정 기록 15~17 · **19(설문 무효 응답 판정)** · `DECISIONS.md` N9·N13 |

**표기** — **[측정]** 은 실제로 잰 값, **[추정]** 은 판단, **[미확인]** 은 아직 모르는 것입니다.
`NLR_DEPLOY_HANDOFF.md` 와 같은 관례입니다.

---

## 0. 왜 지금 정해야 하는가 — 비용 구조

배포 후 작업이 다 비싼 것은 아닙니다. **무엇이 비싼지**를 먼저 맞춰야 논의가 됩니다.

```
싸다     ALTER TABLE ADD COLUMN              PostgreSQL 11+ 는 즉시 끝난다
         새 테이블 CREATE                     기존 데이터를 건드리지 않는다

비싸다   **값을 채우는 재적재**                perfumes 129,161행 · perfume_accords 100만행
         AI 서버 이미지 재빌드·재배포          의존성이 바뀌면 필요
         **서비스 오픈 후 놓친 데이터**         안 쌓인 로그는 되돌릴 수 없다
```

**컬럼을 나중에 추가하는 것 자체는 문제가 아닙니다. 그 컬럼에 13만 행 값을 채우는 재적재가
문제이고, 더 큰 문제는 안 쌓인 사용자 행동 데이터입니다.**

---

## 1. 그대로 가도 되는 것 — 결정 불필요

수동 테스트 DB에서 검증이 끝나 추가 논의가 필요 없는 항목입니다.

| | 상태 |
|---|---|
| Flyway 마이그레이션 `V1`~`V19` | 코드에 있고 **전부 `success = true`** [측정] |
| `perfumes.fragrantica_id` + UNIQUE | `V6__align_scent_map_schema_with_delivered_data.sql` ✓ |
| `perfumes.fragrantica_rating_count` | `V14__extend_brand_and_perfume_catalog.sql` ✓ (인계 문서의 `people`) |
| `uk_perfumes_brand_name` 제거 | `V14` ✓ |
| 적재 데이터 4종 | `ai/delivery/for_db/` 준비 완료 |
| AI 서버 배포 조건 | `NLR_DEPLOY_HANDOFF.md` 에 인계 완료 |

수동 테스트 DB 실측 [측정] — `perfumes 129,161 · accords 92 · brands 7,793 ·
perfume_accords 1,000,570`. 인계 문서의 목표치와 전부 일치합니다.

`fragrantica_rating_count` 값 범위가 **0 ~ 35,695** 로 인계 문서의 `people` 과 같습니다 [측정].

---

## 2. ⚠ 배포 작업 중에 반드시 해야 할 것

**결정이 아니라 절차입니다. 빠뜨리면 적재가 중간에 멈춥니다.**

### 2-1. `already_in_db` 열을 쓰지 않고 UPSERT 로 적재한다

`ai/delivery/for_db/perfumes.csv.gz` 에 `already_in_db` 열이 있습니다. **DB 에 접근할 수
없던 시절에 "무엇을 INSERT 하고 무엇을 UPDATE 할지" 를 미리 계산해 둔 것**입니다.

**이제 필요 없습니다.** 세 테이블 모두 유니크 제약이 있어 UPSERT 로 처리됩니다 [측정].

```
perfumes   uk_perfumes_fragrantica_id  UNIQUE (fragrantica_id)
accords    uk_accords_name             UNIQUE (name)
brands     uk_brands_name              UNIQUE (name)
```

```sql
-- INSERT/UPDATE 를 미리 가를 필요가 없다
INSERT INTO perfumes (fragrantica_id, name, brand_id, fragrantica_rating_count)
VALUES (...)
ON CONFLICT (fragrantica_id) DO UPDATE
   SET name = EXCLUDED.name,
       brand_id = EXCLUDED.brand_id,
       fragrantica_rating_count = EXCLUDED.fragrantica_rating_count;

INSERT INTO accords (name) VALUES (...) ON CONFLICT (name) DO NOTHING;
INSERT INTO brands  (name) VALUES (...) ON CONFLICT (name) DO NOTHING;
```

> **`ai/data/perfumes_already_in_db.csv`(201행)와 `accords_already_in_db.csv`(61행)는
> 적재 전 스냅샷이라 이미 낡았습니다.** UPSERT 를 쓰면 이 파일에 의존하지 않으므로
> 낡은 스냅샷으로 적재가 깨지는 위험이 사라집니다. `perfumes.csv.gz` 의 `already_in_db`
> 열은 무시하면 됩니다.

**담당: 백엔드**

### 2-2. 적재 순서

```
0. 마이그레이션 (V1~V19)
   ↓
1. brands            7,793      ON CONFLICT (name) DO NOTHING
   ↓
2. accords              92      ON CONFLICT (name) DO NOTHING
   ↓
3. perfumes        129,161      ON CONFLICT (fragrantica_id) DO UPDATE
   ↓
4. perfume_accords 1,000,570    COPY 권장 (.gz 는 풀어서)
```

**외래키 때문에 순서가 있습니다. 거꾸로 하면 실패합니다.**

3번을 `DO UPDATE` 로 하지 않고 그냥 INSERT 하면 향 지도용 향수가 두 번 생깁니다.

> 인계 문서 경고 — *"두 번 생기면 향 지도가 가리키는 향수와 추천이 가리키는 향수가
> 갈립니다. 같은 향수인데 상세 페이지가 두 개가 됩니다."*

### 2-3. 적재 후 확인

```sql
SELECT count(*) FROM perfumes;                                -- 129,161
SELECT count(*) FROM accords;                                 -- 92
SELECT count(*) FROM brands;                                  -- 7,793
SELECT count(*) FROM perfume_accords;                         -- 1,000,570
SELECT count(*) FROM perfumes WHERE fragrantica_id IS NULL;   -- 0
```

---

## 3. 회의에서 정할 것 — 안건 넷

### 안건 ① 강도 컬럼(`sillage_avg`·`longevity_avg`)을 넣을 것인가

> **⛔ 뒤집혔습니다 (2026-09-17) — 지금은 넣지 않습니다.**
>
> 2026-09-16 에는 *"컬럼만 미리 넣고 정렬 로직은 쓰지 않는다"* 로 결정했습니다.
> **사용자 결정(2026-09-17)으로 컬럼 추가도 하지 않습니다.**
>
> **아래 본문과 구현 명세는 그대로 둡니다.** 왜 "넣자" 였는지의 측정이 다 들어 있고,
> 다시 논의할 때 처음부터 재지 않기 위해서입니다. 되살릴 때는 이 절의 4단계를
> 그대로 따르면 됩니다.
>
> **뒤집은 근거** — 이 데이터는 Fragrantica 에서 오고 `ai/build_data.py` 가 원본에서
> 만들어 냅니다. **사용자가 만드는 데이터가 아니라 언제든 다시 채울 수 있습니다.**
> 미뤄서 잃는 것은 재적재 한 번의 수고이고 **되돌릴 수 없는 손실이 아닙니다**
> (0장의 비용 구분 · 안건 ② 와 다른 점). 팀 DB 에 이미 129,161행이 적재돼 있어
> 나중에는 `ALTER TABLE` + UPSERT 한 번입니다 [측정 2026-09-17 ·
> `docs/WORKING_NOTES.md` 6장].
>
> **엔진 동작은 지금도 앞으로도 바뀌지 않습니다.** 원래 결정도 *"정렬에 안 쓴다"* 였고
> 엔진은 `performance` 칸을 읽지 않습니다.

| | |
|---|---|
| 지금 넣으면 | 적재 한 번에 끝남. 데이터 파일 4.74MB → 5.28MB [측정] |
| 나중에 넣으면 | `ALTER TABLE` 은 즉시지만 **129,161행 값 채우기 재적재 필요** |
| 정렬 로직 | **지금은 안 씁니다.** `DECISIONS.md` N9 를 열지 않습니다 |

아래는 그 결정에 이른 측정입니다.

```
강도 정렬을 켜면 (합성 600건 중 추천 목록이 바뀐 26문장 · 추천 칸 130개) [측정]

   확산력 평균        2.32  →  2.79      의도대로 올라간다
   평가자 수 평균    6,255  →  **92**    98.5% 폭락
   평가자 수 중앙      143  →  **23**
   평가자 100명 미만  41.5% →  **79.2%**
```

원인이 데이터에 있습니다 [측정].

```
확산력 구간      향수 수    평가자 중앙   평가자 10명 미만
0.0 ~ 1.5       5,237          4        69.9%
2.0 ~ 2.5      46,940         28        31.0%     ← 평범한 구간
3.0 ~ 3.5      11,350          5        69.6%
3.5 ~ 4.0       3,799          2        **92.3%**
```

**확산력이 극단인 향수는 평가자가 거의 없습니다.** 인계 문서가 평점을 정렬에서 뺀 이유
(*"평점 5.00 인 향수 8,410개 중 99.8% 가 평가자 10명 이하"*)와 **같은 함정**입니다.

```
"가을겨울에 어울리는 진한 향…"
   끄고  Fendi · Oriza L. Legrand · Chloé
   켜고  Rasasi Somow Al Rasasi Wajaha · Brooks Brothers · Liaison de Parfum
         ↑ 강도는 맞았지만 아무도 모르는 향수가 된다
```

#### 정렬 방식 다섯 가지를 다시 쟀습니다 — `71_intensity_sort_variants.py`

위 부작용은 **강도를 어디에 끼우느냐** 때문이지 강도 자체 때문이 아닐 수 있습니다.
그래서 안 재본 방식들을 같이 쟀습니다 [측정] (합성 600건 · 강도 요구 67건).

| 방식 | 정렬 순서 | 목록 바뀜 | 평가자 평균 | 평가자 중앙 | **<100명** | NDCG vs A |
|---|---|---:|---:|---:|---:|---:|
| A 현행 | 점수 → 평가자 수 → id | 0 | 3,010 | 85 | 52.6% | — |
| B 강도 2순위 | 점수 → **강도** → 평가자 수 | 26 | **199** | 41 | **69.8%** | −0.000680 |
| C 강도 3순위 | 점수 → 평가자 수 → **강도** | **0** | 3,010 | 85 | 52.6% | ±0.000000 |
| **D 문턱100+강도** | `people>=100` 거른 뒤 B | 57 | **598** | **262** | **0.0%** | −0.000713 |
| E 문턱500+강도 | `people>=500` 거른 뒤 B | 57 | 2,254 | 1,082 | **0.0%** | −0.001365 |
| F 강도버킷 0.5 | 점수 → **강도구간** → 평가자 수 | 25 | 204 | 44 | 68.1% | −0.000637 |

**C 는 아무것도 바꾸지 않습니다(0건).** 평가자 수까지 동점인 경우가 사실상 없어 강도가
개입할 자리가 없습니다. **F 도 B 와 차이가 없습니다** — 구간으로 묶어도 최고 구간에
무명 향수만 들어가 부작용이 그대로입니다.

**D 가 부작용을 제거합니다.** 평가자 100명 미만 추천이 **52.6% → 0.0%** 이고, 오히려
현행보다 인지도가 높아집니다(중앙 85 → 262).

#### D 가 의도대로 동작하는가 — 방향을 나눠서 확인 [측정]

`HIGH` 와 `LOW` 는 반대 방향이라 섞어 보면 안 됩니다.

| 요구 | 추천 칸 | A 현행 | B | **D** |
|---|---:|---:|---:|---:|
| **지금 프롬프트** `HIGH` | 270 | 2.34 | 2.56 | **2.46** ↑ |
| **지금 프롬프트** `LOW` | 10 | 2.21 | 2.13 | **2.13** ↓ |
| **v4 프롬프트** `LOW` | 115 | 2.23 | 1.77 | **1.93** ↓ |

**둘 다 요구한 방향으로 움직입니다.** D 는 B 보다 폭이 작지만(2.46 vs 2.56) 부작용이
없습니다.

#### D 의 대가

```
status      OK 397 -> 395 (−2 / 600건)   ·  v4 에서는 26 -> 25 (−1 / 42건)
NDCG        −0.000713 (지금 프롬프트)     ·  −0.023 (v4 프롬프트)
후보 범위    강도 요구가 있을 때만 25,084개로 좁아진다 (전체 129,161 의 19.4%)
```

**⚠ 일관성 문제가 하나 남습니다.** D 는 강도 요구가 있을 때만 문턱을 올리므로, 같은
서비스에서 **어떤 요청은 25,084개 중에서, 어떤 요청은 69,376개 중에서** 고르게 됩니다.
*"왜 이 향수는 안 나왔지"* 를 설명하기 어려워집니다.

#### 그리고 여전히 증명할 수 없는 것

**강도 만족도를 잴 지표가 없습니다.** 정답 키 `C` 가 accord 집합이라 강도 정보가 없습니다.
위 표의 NDCG 하락은 *"accord 일치가 떨어졌다"* 는 뜻이지 *"추천이 나빠졌다"* 가 아니고,
확산력 상승은 *"요구한 방향으로 갔다"* 는 뜻이지 *"사용자가 만족한다"* 가 아닙니다.

**"넣으면 성능이 많이 올라가는가" 에 대한 정직한 답은 "모릅니다" 입니다.**
안건 ②(피드백 저장)가 있어야 처음으로 잴 수 있습니다.

#### ✅ 결정 — 컬럼만 미리 넣고 정렬 로직은 나중에 (2026-09-16)

```
정렬 로직   **지금은 쓰지 않는다.** N9 를 열지 않는다
컬럼        **지금 넣는다.** 나중에 129,161행 재적재를 피한다
```

**이유** — `D` 방식이 부작용 없이 동작하는 것은 확인했지만 **이득을 증명할 수단이
없습니다.** 안건 ②가 들어가면 실제 클릭 데이터로 판단할 수 있고, 그때 컬럼이 이미 있으면
**코드 몇 줄만 바꾸면 됩니다.** 컬럼 추가 비용(데이터 파일 +0.53MB)이 재적재 비용보다
훨씬 쌉니다.

#### 구현 명세 — 네 군데

**⚠ 결측을 `0` 이 아니라 `NULL` 로 넣어야 합니다.** 이게 가장 중요합니다.

```
sillage_avg == 0 인 22,164개   →  **100% 가 투표 0표** [측정]
longevity_avg == 0 인 23,284개 →  **100% 가 투표 0표** [측정]
```

**0 은 "확산력이 없다" 가 아니라 "평가가 없다" 입니다.** 0 으로 저장하면 나중에 이 컬럼을
쓰는 사람이 *"가장 약한 향수"* 로 오해합니다 — 실제로 측정 중에 그 함정에 한 번 빠졌습니다.

| | 무엇을 | 어떻게 |
|---|---|---|
| **1. DB 마이그레이션** | `perfumes` | `ADD COLUMN sillage_avg NUMERIC(10,6)`<br>`ADD COLUMN longevity_avg NUMERIC(10,6)`<br>**NULL 허용** (결측이 17% 다) |
| **2. `ai/build_data.py`** | `KEEP_COLUMNS` | `"sillage_avg", "longevity_avg"` 추가<br>**0 을 `NaN` 으로 바꿔 저장**<br>파일 4.74MB → 5.28MB [측정] |
| **3. `ai/build_load_files.py`** | `usecols` + `perfumes.csv.gz` 출력 | 두 컬럼을 읽어 그대로 내보낸다<br>**지금은 `usecols` 5개라 무시된다** |
| **4. 적재** | `perfumes` UPSERT | `DO UPDATE SET sillage_avg = EXCLUDED.sillage_avg, ...` |

```sql
-- 마이그레이션 예시
ALTER TABLE perfumes
    ADD COLUMN sillage_avg   NUMERIC(10,6),
    ADD COLUMN longevity_avg NUMERIC(10,6);

COMMENT ON COLUMN perfumes.sillage_avg IS
    'Fragrantica 확산력 평균 1.00~4.00. NULL 은 평가 없음(전체의 16.8%)';
COMMENT ON COLUMN perfumes.longevity_avg IS
    'Fragrantica 지속력 평균 1.00~5.00. NULL 은 평가 없음(전체의 17.7%)';
```

**타입을 `NUMERIC(10,6)` 으로 한 이유** — 소수 3자리 이상인 값이 **124,078개** 라
`NUMERIC(3,2)` 로 하면 반올림 손실이 생깁니다 [측정]. 그리고 `perfume_accords.weight` 가
이미 `NUMERIC(10,6)` 이라 타입이 일관됩니다.

**알려진 데이터 결함** — 평균은 있는데 구간 투표가 0표인 향수가 **204개** 있습니다 [측정].
원본(Fragrantica) 쪽 문제로 보이며 소수라 그대로 싣습니다.

#### 이 결정이 남기는 것

```
지금        컬럼은 있지만 엔진이 읽지 않는다. 추천 결과는 **하나도 안 바뀐다**
나중에      안건 ②의 클릭·설문 데이터로 D 방식의 이득을 잰다
            이득이 확인되면 N9 를 열고 코드 몇 줄을 바꾼다 — 재적재 없이
```

---

### 안건 ② 사용자 피드백 저장을 오픈 전에 넣을 것인가 — **가장 급합니다**

| | |
|---|---|
| **AI 의견** | **오픈 전에 넣는다** |
| 지금 넣으면 | 새 테이블이라 기존 데이터 영향 없음. 마이그레이션 1개(`V20`) |
| 나중에 넣으면 | 테이블 추가는 싸지만 **그때까지의 사용자 행동은 영영 못 모읍니다** |

#### 왜 "나중에 해도 된다"가 아닌가

```
미매칭 고유 표현 1,463개   ← 사전이 못 받는 말들 [측정]
현재 사전 표현 41개        ← 손으로 만든 것
그중 core accord 를 주는 것 15개

실사용 설문 143건에서 조건을 하나도 못 뽑는 문장이 **39.9%** [측정]
```

> **2026-09-16 정정** — 이전 판은 `155건 · 44.5%` 였습니다. 설문 155건 중 12건이 향수
> 요청이 아니라 동의 표현(`네`·`넵`·`예`)이어서 분모에서 뺐습니다. 못 뽑는 문장의
> **건수는 69건에서 57건으로 줄었고 분모가 143이 되어 39.9%** 입니다.
> 판정 근거는 측정 기록 19번입니다. **여전히 4할에 가깝고 안건의 근거는 그대로입니다.**

사전을 키울 근거가 지금은 `ai_summary`(대중 의견, 커버리지 9.4%)와 팀원 판단뿐입니다.
**사용자가 추천 중 무엇을 클릭했는지가 유일한 실사용 근거입니다.**

```
"은은한 꽃향" 을 사전이 못 받았다        ← 미매칭 로그
그 요청에서 사용자가 이 향수를 골랐다     ← 클릭 로그
       ↓
"은은한 꽃향" → 그 향수의 floral · white floral      **사전 확장 근거**
```

#### 설계안 — 테이블 넷 (`V20__add_nlr_feedback_tables.sql`)

설계 원칙 넷입니다.

```
1. 추천 요청 하나가 모든 것을 묶는 축이다      recommendation_id
2. 미매칭 로그의 기존 필드를 그대로 옮긴다     unmatched_log.py 와 1:1
3. **어느 버전에서 나온 로그인지 남긴다**      사전·프롬프트가 계속 바뀐다
4. 클릭은 순위와 함께 기록한다                "몇 위를 골랐나" 가 품질 신호다
```

3번이 중요합니다. 최근에도 사전이 v1.8 → v1.14, 프롬프트가 v1 → v4 로 움직였습니다.
**버전을 안 남기면 반년 뒤에 이 로그를 해석할 수 없습니다.**

```sql
-- 1. 추천 요청 1건
CREATE TABLE nlr_recommendations (
    recommendation_id  BIGINT       GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    user_id            BIGINT,                      -- 비로그인 허용이면 NULL
    raw_query          VARCHAR(500) NOT NULL,       -- API 계약의 500자 제한과 동일
    status             VARCHAR(20)  NOT NULL,       -- OK / OK_RELAXED / NO_CONDITION / NO_RESULT
    stage              VARCHAR(30),                 -- AND / SINGLE_BROAD / RELAXED_OR / ...
    source             VARCHAR(20),                 -- lexicon_only / llm+lexicon / llm_no_effect
    core_accords       VARCHAR(500),                -- 'soapy|fresh|green' 파이프 구분
    avoid_accords      VARCHAR(200),
    candidate_count    INTEGER,                     -- 조건에 맞은 향수 수
    lexicon_version    VARCHAR(20)  NOT NULL,       -- 'v1_14'
    prompt_sha256      VARCHAR(16),                 -- 기동 로그에 찍히는 값과 같은 것
    requested_at       TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT fk_nlr_recommendations_user
        FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE SET NULL,
    CONSTRAINT ck_nlr_recommendations_status
        CHECK (status IN ('OK', 'OK_RELAXED', 'NO_CONDITION', 'NO_RESULT'))
);

CREATE INDEX idx_nlr_recommendations_requested ON nlr_recommendations (requested_at);
CREATE INDEX idx_nlr_recommendations_status    ON nlr_recommendations (status);


-- 2. 결과 5개와 클릭
CREATE TABLE nlr_recommendation_items (
    recommendation_id  BIGINT   NOT NULL,
    rank               SMALLINT NOT NULL,        -- 1 ~ 5
    perfume_id         BIGINT   NOT NULL,
    clicked_at         TIMESTAMPTZ,              -- NULL 이면 안 눌렀다

    PRIMARY KEY (recommendation_id, rank),
    CONSTRAINT fk_nlr_items_recommendation
        FOREIGN KEY (recommendation_id) REFERENCES nlr_recommendations(recommendation_id)
        ON DELETE CASCADE,
    CONSTRAINT fk_nlr_items_perfume
        FOREIGN KEY (perfume_id) REFERENCES perfumes(perfume_id) ON DELETE CASCADE,
    CONSTRAINT ck_nlr_items_rank CHECK (rank BETWEEN 1 AND 5)
);

CREATE INDEX idx_nlr_items_perfume ON nlr_recommendation_items (perfume_id);
CREATE INDEX idx_nlr_items_clicked ON nlr_recommendation_items (clicked_at)
    WHERE clicked_at IS NOT NULL;


-- 3. 사전이 못 받은 표현
CREATE TABLE nlr_unmatched_expressions (
    unmatched_id       BIGINT       GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    recommendation_id  BIGINT       NOT NULL,
    expression         VARCHAR(200) NOT NULL,     -- '은은한 꽃향'
    normalized_key     VARCHAR(200) NOT NULL,     -- 소문자·공백 정규화한 것
    unmatch_reason     VARCHAR(30)  NOT NULL,
    entry_id           VARCHAR(50),               -- NOT_CORE 일 때 어느 사전 항목인지

    CONSTRAINT fk_nlr_unmatched_recommendation
        FOREIGN KEY (recommendation_id) REFERENCES nlr_recommendations(recommendation_id)
        ON DELETE CASCADE,
    CONSTRAINT ck_nlr_unmatched_reason
        CHECK (unmatch_reason IN ('NOT_IN_LEXICON', 'NOT_CORE', 'CONDITION_NOT_MET'))
);

CREATE INDEX idx_nlr_unmatched_key ON nlr_unmatched_expressions (normalized_key);


-- 4. 설문
CREATE TABLE nlr_feedbacks (
    recommendation_id  BIGINT      PRIMARY KEY,   -- 요청당 1개
    satisfied          SMALLINT    NOT NULL,      -- 1 ~ 5
    comment            VARCHAR(500),
    answered_at        TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT fk_nlr_feedbacks_recommendation
        FOREIGN KEY (recommendation_id) REFERENCES nlr_recommendations(recommendation_id)
        ON DELETE CASCADE,
    CONSTRAINT ck_nlr_feedbacks_satisfied CHECK (satisfied BETWEEN 1 AND 5)
);
```

`unmatch_reason` 세 값은 **지금 `unmatched_log.py` 가 쓰는 것 그대로**입니다. 셋을 구분하는
이유가 코드 주석에 있습니다.

```
NOT_IN_LEXICON     사전에 없다              -> 항목을 추가한다
CONDITION_NOT_MET  match_condition 이 탈락  -> 조건 토큰을 손본다
NOT_CORE           optional / NO_MAPPING    -> **판정 이력이 있다. 함부로 올리지 않는다**
```

**클릭을 전용 테이블에 두는 이유**는 순위가 같이 남기 때문입니다. `user_perfume_views` 에도
기록할 수 있지만 거기엔 "몇 위였나" 가 없습니다. **1위를 눌렀는가 5위를 눌렀는가는 추천
품질의 직접 신호입니다.**

#### 이 설계의 값어치 — 핵심 질의

```sql
-- 사전이 못 받은 표현 → 사용자가 실제로 고른 향수의 accord
-- = 사전 확장 후보를 실사용 행동에서 뽑는다
SELECT
    u.normalized_key                      AS 표현,
    a.name                                AS accord,
    count(*)                              AS 클릭수,
    round(avg(i.rank), 1)                 AS 평균순위
FROM nlr_unmatched_expressions u
JOIN nlr_recommendation_items  i ON i.recommendation_id = u.recommendation_id
JOIN perfume_accords          pa ON pa.perfume_id = i.perfume_id
JOIN accords                   a ON a.accord_id = pa.accord_id
WHERE i.clicked_at IS NOT NULL
  AND pa.weight >= 0.5                    -- 그 향수에서 뚜렷한 accord 만
GROUP BY 1, 2
HAVING count(*) >= 5                      -- 우연 제외
ORDER BY 3 DESC;
```

나오는 결과가 이런 모양입니다.

```
표현              accord         클릭수   평균순위
은은한 꽃향        floral           23      2.1
은은한 꽃향        white floral     19      2.3
따뜻한 향신료 느낌  warm spicy       17      1.8
보송한 분냄새      powdery          14      2.0
```

두 번째로 쓸모 있는 질의입니다.

```sql
-- OK_RELAXED("조건을 넓혀 찾았습니다")가 실제로 나쁜 추천인지 처음으로 확인한다
SELECT r.status,
       count(*)                                                   AS 요청수,
       count(*) FILTER (WHERE i.clicked_at IS NOT NULL)           AS 클릭발생,
       round(avg(f.satisfied), 2)                                 AS 평균만족도
FROM nlr_recommendations r
LEFT JOIN nlr_recommendation_items i ON i.recommendation_id = r.recommendation_id
LEFT JOIN nlr_feedbacks            f ON f.recommendation_id = r.recommendation_id
GROUP BY 1;
```

#### 크기 추정 [추정]

```
요청 1건당    recommendations 1행 + items 5행 + unmatched 평균 2.18행 + feedbacks 0~1행
             ≈ 8 ~ 9행

하루 1,000 요청 → 약 9,000행/일 → 연 330만 행
```

`perfume_accords` 가 이미 100만 행이므로 부담되는 규모가 아닙니다.

#### ⚠ 개인정보 — 같이 정해야 합니다

`raw_query` 에 **사용자가 입력한 원문**이 들어갑니다.

> `NLR_DEPLOY_HANDOFF.md` 경고 — *"실사용자 설문에서 건강·신분 관련 서술이 있었습니다."*

```
지금 (파일)   AI 컨테이너 볼륨 하나            접근 = AI 담당
DB 로 옮기면  백엔드 · 운영 · 백업이 다 접근
```

| 정할 것 | 선택지 |
|---|---|
| **보관 기간** | 30일 후 `raw_query` 만 `NULL` / 90일 / 무기한 |
| **익명화** | `user_id` 를 아예 안 남긴다 / 남기되 탈퇴 시 `NULL` |
| **접근 범위** | 운영 DB 직접 조회 / 별도 분석 계정 |

`unmatched_log.py` 에 *"30일 지난 원문을 비우는 함수가 있습니다. **자동 실행은 아직
없습니다**"* 라고 적혀 있습니다. DB 로 옮기면 배치나 파티션으로 만들어야 합니다.

#### 마이그레이션이 필요 없는 부분도 있습니다

`user_perfume_views.from_location_type` 은 `VARCHAR(50)` 이고 **`CHECK` 제약이 없습니다**
(`V10__expand_perfume_view_source_type.sql` 이 이미 넓혔습니다) [측정].
`'NLR_RECOMMENDATION'` 같은 값을 넣는 데 DB 변경이 필요 없고 **백엔드 enum 만 늘리면
됩니다.**

---

### 안건 ③ 미매칭 로그를 파일에 둘 것인가 DB로 옮길 것인가

**안건 ②를 채택하면 자동으로 정해집니다.**

| | 파일 (현재) | DB (안건 ② 채택 시) |
|---|---|---|
| 위치 | AI 컨테이너 `/app/logs/unmatched.jsonl` | `nlr_unmatched_expressions` |
| 인프라가 할 일 | **볼륨 1개 준비** | **볼륨 불필요** |
| 개인정보 | 볼륨 하나에만 | 백엔드·운영·백업이 다 접근 |

파일로 남긴다면 **`named volume` 을 권합니다** [추정]. `bind mount` 는 호스트 디렉터리
소유자를 컨테이너 사용자 `nlr` 과 맞춰야 하고, 안 맞으면 **조용히 기록만 사라집니다.**

#### 누가 기록할 것인가 — 여기서 구조가 갈립니다

지금 AI 서버는 DB 를 전혀 모릅니다(`NLR_DEPLOY_HANDOFF.md` *"DB 필요 없음"*).

| | 방법 | 영향 |
|---|---|---|
| **㉠** | **백엔드가 기록한다** | AI 서버는 그대로. 응답에 이미 `unmatched` 가 들어 있으니 백엔드가 받아서 INSERT |
| ㉡ | AI 서버가 직접 쓴다 | AI 서버에 DB 연결·드라이버 추가. **의존성 4개 → 5개** |

**㉠을 권합니다** [추정]. AI 서버의 "DB 없이 독립적으로 돈다" 는 성질을 지키고, 인프라가
인계받은 배포 조건이 안 바뀝니다.

---

## 안건 ③ 후속 — DB 담당자에게 드리는 테이블 명세 (2026-09-17)

> **정해진 것** — DB 담당자가 테이블을 만들고, **백엔드가 INSERT** 합니다(㉠).
> **AI 서버는 파일 로그를 계속 씁니다.** 파일은 **캐시**로 쓰이고 DB 는 **분석**용입니다.
> 중복이 아니라 역할 분담입니다 — `DECISIONS.md` N15 근거 3·5.

### 왜 파일을 없애지 않나

AI 서버가 **기동할 때 그 파일을 읽어 추정 캐시를 채웁니다.** 캐시가 없으면 같은 문장에
매번 다른 향수가 나옵니다 — **같은 설정으로 두 번 불러 5문장 중 5문장이 달랐습니다**
[측정 2026-09-17].

DB 에서 캐시를 받아오는 방법도 검토했으나 **AI 서버의 아웃바운드가 `gms.ssafy.io`
하나로 제한**돼 있어 막힙니다(`NLR_DEPLOY_HANDOFF.md` · 2026-09-15 인계 조건).

**인프라가 할 일은 안 바뀝니다** — AI 컨테이너의 로그 볼륨 1개가 그대로 필요합니다.

### 테이블 안 [제안]

AI 가 쓰는 로그 한 줄과 1:1 입니다. 이름과 타입은 팀 관례에 맞춰 바꾸셔도 됩니다.

```sql
CREATE TABLE nlr_unmatched_expressions (
    id              BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    occurred_at     TIMESTAMPTZ  NOT NULL,
    raw_text        VARCHAR(500),
    expression      VARCHAR(255) NOT NULL,
    normalized_key  VARCHAR(255) NOT NULL,
    unmatch_reason  VARCHAR(30)  NOT NULL,
    entry_id        VARCHAR(50),
    had_conditions  BOOLEAN      NOT NULL,
    llm_accords     TEXT[],
    llm_reasoning   TEXT,
    tier            VARCHAR(20),
    result_count    INTEGER
);

CREATE INDEX ix_nlr_unmatched_key  ON nlr_unmatched_expressions (normalized_key);
CREATE INDEX ix_nlr_unmatched_time ON nlr_unmatched_expressions (occurred_at);

COMMENT ON COLUMN nlr_unmatched_expressions.llm_accords IS
    '빈 배열 = LLM 이 향이 아니라고 판정 · NULL = 묻지 않음. 둘을 구분해야 한다';
```

| 컬럼 | 무엇 | 주의 |
|---|---|---|
| `occurred_at` | 기록 시각 | AI 가 ISO8601 문자열로 냅니다 |
| `raw_text` | **사용자 원문** | **500자까지만.** 개인정보 — 아래 보관 정책 |
| `expression` | ①단계 LLM 이 뽑은 표현 그대로 | `무겁지 않게` 처럼 문장 조각입니다 |
| `normalized_key` | 소문자·공백 정규화한 키 | **집계는 이걸로 합니다.** 인덱스 대상 |
| `unmatch_reason` | `NOT_IN_LEXICON` / `CONDITION_NOT_MET` / `NOT_CORE` | 셋은 고쳐야 할 곳이 다릅니다 |
| `entry_id` | 사전 항목 id | 사전에 있는데 조건이 안 맞은 경우만 |
| `had_conditions` | 조건을 뽑은 요청에서 나온 미매칭인가 | **조건 0건만 보면 안 보이는 미매칭이 합성 600 에서 1,339회였습니다** |
| `llm_accords` | LLM 이 추정한 accord 배열 | **아래 세 상태를 꼭 구분** |
| `llm_reasoning` | LLM 의 설명 | **사전의 `rationale` 과 같은 칸에 넣지 마세요.** 근거가 아니라 사후 해석입니다 |
| `tier` | `'LLM'` 또는 `NULL` | 사전 경로와 LLM 경로를 등급으로 가릅니다 |
| `result_count` | 그 요청이 낸 추천 개수 | 추정이 실제로 결과를 만들었는지 봅니다 |

### ⚠ `llm_accords` 는 **세 가지 상태**를 담습니다

```
['woody','green']   LLM 이 accord 를 골랐다
[]  (빈 배열)        **LLM 이 "향이 아니다" 라고 판정했다** — 가격·성별·지속력 같은 것
NULL                아직 묻지 않았다 (추정이 꺼져 있었거나 호출이 실패했다)
```

**`NOT NULL DEFAULT '{}'` 로 만들면 안 됩니다.** 세 가지가 두 가지로 뭉개져
*"다시 물어봐야 할 표현"* 을 골라낼 수 없습니다.

전체 표현의 **38% 가 빈 배열**입니다 [측정 · 369개 중 140개].

### 백엔드가 할 일 — **AI 응답에 칸을 더해야 합니다**

**지금 AI 응답의 `unmatched` 에는 칸이 4개뿐입니다.**

```
지금 나가는 것   expression · normalizedKey · unmatchReason · entryId
더 필요한 것     llmAccords · llmReasoning · tier · hadConditions · resultCount
```

**이건 API 계약 변경이라 AI·백엔드가 같이 움직여야 합니다.**
AI 쪽(`_camel_unmatched` 와 `nlr_api_contract.md`)은 합의되면 제가 고칩니다.

합의 전까지는 **DB 가 비어 있어도 서비스는 정상입니다** — 캐시는 파일로 돌고,
추천 품질은 DB 와 무관합니다.

### 아직 정해지지 않은 것

| | 내용 |
|---|---|
| **`raw_text` 보관 기간** | 파일에는 `purge_raw_text()` 가 30일 뒤 원문을 비웁니다. **DB 쪽은 누가 지울지 정해지지 않았습니다** |
| 개인정보 범위 | DB 로 가면 백엔드·운영·백업이 다 접근합니다(안건 ③ 원문) |
| 집계 시점 | 매 요청 누적인지 배치인지 (`NLR_UNMATCHED_LOG_DESIGN.md` 미결) |
| 승격 문턱 | `spec.md` 는 3회. 실사용 규모를 몰라 잠정입니다 |

---

### 안건 ④ `perfumes_nlr.csv.gz` 를 계속 쓸 것인가

AI 서버는 지금 DB 를 읽지 않고 이 파일(4.97MB)을 읽습니다. **그런데 `build_data.py` 에
이렇게 적혀 있습니다.**

> DB 에 향수 전체가 들어가면 이 파일은 필요 없어진다. **그때까지의 임시 조치다.**

**그 조건이 충족됐습니다.** 엔진이 쓰는 값이 전부 DB 에 있는 것을 확인했습니다 [측정].

```
DB   perfume_accords.weight  soapy 1.000000 · fresh 0.930000 · green 0.760000
엔진 strength                soapy 100.00   · fresh 93.00   · green 76.00
     → weight = strength ÷ 100. 같은 데이터다
```

| | |
|---|---|
| **AI 의견** | **이번 배포에서는 파일 유지** [추정] |
| 바꾸면 얻는 것 | 데이터가 한 곳에만 있음. 원본 갱신 시 한 번만 고치면 됨 |
| 바꾸면 잃는 것 | 인계 문서의 **"DB 필요 없음" 이 깨짐** · 의존성 4개 → 5개 · **DB 가 죽으면 AI 서버가 안 뜸** · 기동 2.4초 증가 · 이미지 재빌드 |

**지금 바꾸면 AI 서버 재빌드와 인계 문서 갱신이 배포 직전에 발생합니다.** 다음 배포로
미루는 편이 안전해 보입니다.

---

## 4. 담당별 정리

| 담당 | 배포 전 | 배포 중 | 배포 후 |
|---|---|---|---|
| **인프라** | 안건 ③ 결과에 따라 **볼륨 준비**<br>아웃바운드 `gms.ssafy.io` 443 허용<br>컨테이너 메모리 512MB [추정] | AI 컨테이너 기동<br>`/health` 의 `"llm": true` 확인 | — |
| **백엔드** | 안건 ②의 `V20` 마이그레이션 작성 여부 결정<br>피드백 기록 로직 (안건 ③ ㉠ 채택 시) | `V1`~`V19` 실행<br>**UPSERT 로 4단계 적재** | 적재 검증 쿼리 |
| **AI** | **사전 버전 확정** (아래)<br>**안건 ① — `build_data.py`·`build_load_files.py` 수정 후 데이터 재생성** (결측 → `NULL`) | — | 미매칭 로그 확인 |

### 사전 버전이 어긋나 있습니다

```
팀 저장소 기본값     domain_lexicon_v1_8.csv    (nlr_engine.py DEFAULT_LEXICON)
최근 측정 전부       domain_lexicon_v1_14.csv   (개인 저장소에만 있음)
```

**DB 와 무관하고 파일이라 배포 시 같이 올라갑니다.** 다만 어느 버전으로 배포할지는
정해야 하고, 안건 ②의 `lexicon_version` 컬럼에 그 값이 들어갑니다.

---

## 5. 결정 요약표

| 안건 | AI 의견 | 상태 | 배포 후로 미루면 |
|---|---|---|---|
| ① 강도 컬럼 | ~~컬럼만 넣고 정렬은 안 쓴다~~ → **지금은 넣지 않는다** | **⛔ 뒤집힘 (2026-09-17)** | 재적재 필요 (129,161행). **되돌릴 수 없는 손실은 아니다** |
| ② 피드백 저장 | **오픈 전에 넣는다** | 미결 | **그때까지 사용자 행동 영구 손실** |
| ③ 미매칭 로그 위치 | **DB 는 백엔드가 INSERT · AI 는 파일을 캐시로 계속 쓴다** | **✅ 결정 (2026-09-17)** · 테이블 명세 전달 | 개인정보 범위 재검토 필요 |
| ④ `perfumes_nlr.csv.gz` | 이번엔 파일 유지 | 미결 | 무방 (다음 배포로 미뤄도 됨) |

**②만 시급합니다.** 나머지 셋은 미뤄도 되돌릴 수 있습니다.

**①은 2026-09-17 에 "넣지 않는다" 로 뒤집혔습니다.** 이유가 위 문장과 같습니다 —
강도 데이터는 원본에서 언제든 다시 만들 수 있어 미뤄도 잃는 것이 없습니다.

---

## 6. 확인하지 못한 것

- **운영 서버 DB 의 현재 상태** [미확인]. 확인한 것은 `hyanghae-manual-test` 뿐입니다.
  `V1`~`V19` 중 어디까지 적용됐는지, `perfumes` 에 몇 행이 있는지 확인이 필요합니다
- **백엔드의 엔티티·리포지토리 구조** [미확인]. 위 DDL 의 테이블명·컬럼명이 팀 컨벤션과
  어긋날 수 있습니다
- **백엔드의 `from_location_type` enum 목록** [미확인]. DB 에는 `SEARCH` 만 있습니다
- **비로그인 사용자를 받을 것인가** [미확인]. `user_id NULL` 허용으로 설계했지만 기획 결정입니다
- **설문 UI 시점** [미확인]. 추천 직후인지 나중인지에 따라 `nlr_feedbacks` 응답률이 달라집니다
- **DB 에서 읽었을 때의 AI 서버 기동 시간** [미확인]. 안건 ④ 판단에 필요하지만 재지 않았습니다

**이 문서의 DDL 은 예시이며 실행하지 않았습니다.** 조사 과정에서 DB 와 코드를 수정하지
않았고 `SELECT` 와 스키마 조회만 사용했습니다.

---

## 관련 자료

- `docs/plans/NLR_DEPLOY_HANDOFF.md` — AI 서버 배포 조건 (의존성 4개 · 512MB · 아웃바운드)
- `ai/docs/perfume_load_handoff.md` — 향수 129,161개 DB 적재 인계
- `ai/docs/nlr_api_contract.md` — 연동 형식 (`status` 4종 · 응답 구조)
- `ai/docs/search_rules.md` — 정렬 규칙 (안건 ①의 배경)
- `DECISIONS.md` N9 — 정렬 규칙. 안건 ①이 여는 결정
- `DECISIONS.md` N13 — 구조화 방식. 분석기·임베딩을 넣지 않기로 한 것
- `docs/nlr_engineering_notes.md` 14번 — 파이프라인 손실 (미매칭 1,463개의 출처)
- `docs/nlr_engineering_notes.md` 17번 — 프롬프트 v4 · LLM 호출 잡음
- `MAP/delivery/for_db/scent_map_proposal.sql` — 향 지도 쪽 DB 제안 (`perfumes` 를 같이 건드림)

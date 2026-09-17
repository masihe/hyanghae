# 자연어 추천 — DB 테이블 생성 요청

| | |
|---|---|
| 작성 | 2026-09-17 |
| 작성자 | AI (자연어 추천) |
| 받는 사람 | **DB 담당** · 백엔드 담당 · 프론트엔드 담당(클릭·설문 UI) |
| 요청 | **새 테이블 4개.** 추천 요청 · 결과와 클릭 · 미매칭 표현 · **만족도** |
| 기존 영향 | **없습니다.** 새 테이블만 만들고 기존 테이블·컬럼·제약을 건드리지 않습니다 |
| 근거 | `NLR_PREDEPLOY_DECISIONS.md` 안건 ② · 안건 ③ 후속 · `DECISIONS.md` N15 · 수동 테스트 DB 실측 |
| 팀 결정 | **안건 ② "피드백 저장을 오픈 전에 넣는다" 로 확정** (2026-09-17). 이 문서는 그 결정을 실행하는 작업 지시입니다 |
| 개인정보 | **원문 보관 30일로 확정** (2026-09-17). 자세한 것은 10장 |

**표기** — **[측정]** 은 실제로 잰 값, **[제안]** 은 판단, **[미확인]** 은 아직 모르는 것입니다.
`NLR_PREDEPLOY_DECISIONS.md` 와 같은 관례입니다.

### 이 문서가 대는 근거의 위치 — 두 저장소가 섞여 있습니다

이 문서는 주장을 할 때마다 근거가 되는 파일을 함께 적습니다. **그 파일이 두 곳에
나뉘어 있습니다.**

| 경로가 이렇게 시작하면 | 어디에 있나 | 열 수 있나 |
|---|---|---|
| `ai/` · `backend/` · `compose.` · `build.gradle` | **팀 저장소** (GitLab) | **네, 바로 열 수 있습니다** |
| `docs/plans/` · `delivery/` · `DECISIONS.md` | **AI 분석 저장소** (팀 저장소에 없습니다) | 아니요 — 필요하면 AI 담당에게 요청하십시오 |

뒤쪽이 **19곳**입니다. 팀 저장소에 올라가지 않은 분석·실험 기록이라 그렇습니다.

**판단에 필요한 숫자와 SQL 은 이 문서 안에 인용해 두었습니다.** 근거를 더 깊이
확인하고 싶을 때만 요청하시면 됩니다.

---

## 0. 요청 한 줄

**추천 요청 하나를 축으로, 그 결과·클릭·미매칭 표현·만족도를 담을 표 넷을 만들어 주십시오.**

```
nlr_recommendations        추천 요청 1건        컬럼 12  ← 축
nlr_recommendation_items   결과 5개와 클릭       컬럼  4
nlr_unmatched_expressions  사전이 못 받은 표현   컬럼 12
nlr_feedbacks              **만족도**            컬럼  4

마이그레이션 1개 (V20) · 인덱스 6개 · 기존 테이블 변경 없음
```

**넣는 것은 백엔드입니다.** AI 서버는 이 표들을 읽지도 쓰지도 않습니다. 이유는 3장에 있습니다.

**⚠ 먼저 읽어 주십시오** — 6장에 *"백엔드가 지금 채울 수 없는 컬럼 둘"* 이 있습니다.
그중 하나는 원래 설계가 `NOT NULL` 이어서 **그대로 만들면 `INSERT` 가 전부 실패합니다.**

---

## 1. 지금 DB 상태 — 만들 자리가 비어 있습니다 [측정]

수동 테스트 DB(`hyanghae-manual-test`)를 직접 조회했습니다.

```sql
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public'
  AND (table_name LIKE '%nlr%'      OR table_name LIKE '%unmatched%'
    OR table_name LIKE '%feedback%' OR table_name LIKE '%recommend%');
```

```
결과 0행
```

```sql
SELECT max(version::numeric) FROM flyway_schema_history WHERE success;
-- 19
```

Flyway 이력이 `V19` 까지 성공이고 마이그레이션 파일도 `V19__align_users_with_auth_policy.sql`
까지 있습니다. **다음 번호는 `V20` 입니다.**

외래키로 가리킬 대상도 전부 있습니다 [측정].

```
users               user_id (bigint)
perfumes            perfume_id
perfume_accords     perfume_id · accord_id · rank · weight     ← 9장 질의가 씁니다
accords             accord_id · name                           ← 9장 질의가 씁니다
```

---

## 2. 표 넷이 무엇을 담는가

사용자가 `"은은한 꽃향이 나는 향수"` 라고 쓰면 AI 서버가 그 문장에서 향 특성
(accord — Fragrantica 가 향수마다 붙인 향 태그, 현재 92종)을 뽑아 향수를 찾습니다.
그 한 번의 요청에서 남는 것이 네 가지입니다.

```
        ┌──────────────────────────┐
        │  nlr_recommendations     │  "무엇을 물었고 어떻게 찾았나"
        │  raw_query · status      │  요청 1건 = 1행
        │  core_accords · stage    │
        └────────────┬─────────────┘
                     │ recommendation_id
     ┌───────────────┼───────────────────┐
     ↓               ↓                   ↓
┌──────────┐  ┌───────────────┐  ┌──────────────┐
│ items    │  │ unmatched     │  │ feedbacks    │
│ 결과 5개  │  │ 못 받은 표현   │  │ **만족도**    │
│ + 클릭   │  │ + LLM 추정     │  │ 3분류 · 한마디│
└──────────┘  └───────────────┘  └──────────────┘
  요청당 0~5행    요청당 평균 2.18행    요청당 0~1행
```

### 왜 만족도만 따로 만들 수 없나

`nlr_feedbacks.recommendation_id` 는 기본키이면서 `nlr_recommendations` 를 가리키는
외래키입니다. **축이 되는 표가 없으면 만족도를 어느 요청에 붙일지 알 수 없습니다.**
`satisfaction = 'SATISFIED'` 만 쌓여도 무엇에 만족했는지 모르면 쓸 수 없습니다.

### 왜 클릭을 전용 표에 두나

`user_perfume_views` 에도 조회 기록이 남습니다. 그런데 거기에는 **"몇 위를 눌렀나" 가
없습니다.** 1위를 눌렀는가 5위를 눌렀는가는 추천 품질의 직접 신호라서 `rank` 와 함께
남깁니다.

### 왜 지금 만들어야 하나

```
실사용 설문 143건 중 조건을 하나도 못 뽑는 문장이 39.9%    [측정]
미매칭 고유 표현 1,463개                                  [측정]
현재 사전 표현 41개 · 그중 core accord 를 주는 것 15개      [측정]
```

사전을 키울 근거가 지금은 팀원 판단뿐입니다. **사용자가 추천 중 무엇을 클릭했고 얼마나
만족했는지가 유일한 실사용 근거입니다.**

테이블을 나중에 추가하는 것은 쉽습니다. 그런데 **오픈 후 그때까지의 사용자 행동은 영영
못 모읍니다.** 안건 ②가 *"가장 급하다"* 로 적힌 이유입니다.

**팀이 2026-09-17 에 "오픈 전에 넣는다" 로 확정했습니다.** 이 문서는 그 결정을 실행하기
위한 작업 지시이고, 더 이상 검토 자료가 아닙니다.

---

## 3. AI 서버는 이 표들을 쓰지 않습니다 — 역할 분담입니다

미매칭 표현은 같은 내용이 파일에도 남습니다. 중복이 아니라 쓰는 쪽이 다릅니다.

```
파일  ai/logs/unmatched.jsonl    AI 서버가 씀. 기동할 때 읽어 **추정 캐시**로 씀
DB    이 표 넷                   백엔드가 씀. 사람이 **분석**할 때 읽음
```

### 파일을 없애지 않는 이유

AI 서버는 기동할 때 그 파일을 읽어 캐시를 채웁니다. 캐시가 없으면 같은 문장에 매번 다른
향수가 나옵니다 — **같은 설정으로 두 번 불러 5문장 중 5문장이 달랐습니다** [측정].

DB 에서 캐시를 받아오는 방법도 검토했지만 막힙니다. AI 서버의 아웃바운드가
`gms.ssafy.io` 하나로 제한돼 있습니다(`NLR_DEPLOY_HANDOFF.md` · 2026-09-15 인계 조건).
그래서 AI 서버에는 DB 연결을 넣지 않습니다.

### 인프라가 할 일은 바뀌지 않습니다

이 표들을 만들어도 **AI 컨테이너의 로그 볼륨 1개는 그대로 필요합니다.**

---

## 4. 마이그레이션

### 4-1. 파일을 둘 자리와 이름

```
backend/src/main/resources/db/migration/V20__add_nlr_feedback_tables.sql
```

`V19__align_users_with_auth_policy.sql` 이 있는 그 디렉터리입니다. Flyway 가 파일 이름의
`V20` 을 버전으로, `__` 뒤를 설명으로 읽습니다. **이미 적용된 파일은 절대 수정하지 마십시오** —
Flyway 가 체크섬을 비교해 기동을 막습니다.

**표를 만드는 순서가 있습니다.** 나머지 셋이 `nlr_recommendations` 를 외래키로 가리키므로
그것을 먼저 만듭니다. 거꾸로 하면 `relation "nlr_recommendations" does not exist` 로
멈춥니다.

### 4-2. 파일 내용 [제안]

주석은 `V14__extend_brand_and_perfume_catalog.sql` 의 방식(한국어 `--` 주석)을 따랐습니다.

```sql
-- 자연어 추천의 사용자 행동을 남깁니다. 추천 요청 하나가 네 표를 묶는 축입니다.
--
-- 왜 오픈 전에 만드나 — 표를 나중에 추가하는 것은 쉽지만 그때까지의 사용자 행동은
-- 영영 못 모읍니다. 실사용 설문 143건 중 39.9% 가 향 조건을 하나도 못 뽑는 문장이었고,
-- 무엇을 사전에 더할지 정하는 유일한 실사용 근거가 "사용자가 무엇을 골랐나" 입니다.
--
-- 넣는 것은 백엔드입니다. AI 서버는 이 표들을 읽지도 쓰지도 않습니다. AI 서버의
-- 아웃바운드가 gms.ssafy.io 하나로 제한돼 있어 DB 에 닿지 못합니다.
--
-- 기존 표를 건드리지 않습니다. 새 표 넷만 만듭니다.

-- ---------------------------------------------------------------------------
-- 1. 추천 요청 1건. 나머지 셋이 이 표를 가리키므로 먼저 만듭니다.
--
-- lexicon_version 과 prompt_sha256 을 남기는 이유가 있습니다. 최근에도 사전이
-- v1.8 -> v1.14, 프롬프트가 v1 -> v4 로 움직였습니다. 어느 버전에서 나온 로그인지
-- 안 남기면 반년 뒤에 이 기록을 해석할 수 없습니다.
--
-- ⚠ lexicon_version 을 NOT NULL 로 두지 않았습니다. 지금 AI 응답에 그 값이 없어서
--   NOT NULL 이면 INSERT 가 전부 실패합니다. 요청 문서 6장을 보십시오.
-- ---------------------------------------------------------------------------
CREATE TABLE nlr_recommendations (
    recommendation_id  BIGINT       GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,

    -- 비로그인 요청을 받으면 NULL 입니다. 탈퇴하면 NULL 이 되고 기록은 남습니다.
    user_id            BIGINT,

    -- 사용자가 쓴 문장. 개인정보입니다 — 10장의 보관 정책이 아직 정해지지 않았습니다.
    -- 500 은 API 가 받는 최대 길이입니다(1~500자를 벗어나면 400).
    raw_query          VARCHAR(500) NOT NULL,

    -- OK / OK_RELAXED / NO_CONDITION / NO_RESULT
    status             VARCHAR(20)  NOT NULL,

    -- AND / SINGLE_BROAD / RELAXED_OR / RELAXED_OR_NO_THRESHOLD / NO_CONDITION /
    -- NOT_ENOUGH. 가장 긴 것이 23자입니다.
    stage              VARCHAR(30),

    -- lexicon_only / llm+lexicon / llm_no_effect
    source             VARCHAR(20),

    -- 'floral|white floral' 처럼 파이프로 구분합니다. 조건 자체를 남겨야 나중에
    -- "이 조건에서 왜 이 향수가 나왔나" 를 다시 볼 수 있습니다.
    core_accords       VARCHAR(500),
    avoid_accords      VARCHAR(200),

    -- 조건에 맞은 향수 수. 5개를 고르기 전의 후보 규모입니다.
    candidate_count    INTEGER,

    -- 'v1_14'. 배포된 사전 버전입니다 — 6장을 먼저 읽어 주십시오.
    lexicon_version    VARCHAR(20),

    -- ①단계 프롬프트의 sha256 앞 16자. 정확히 16자입니다 — 6장을 먼저 읽어 주십시오.
    prompt_sha256      VARCHAR(16),

    requested_at       TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT fk_nlr_recommendations_user
        FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE SET NULL,
    CONSTRAINT ck_nlr_recommendations_status
        CHECK (status IN ('OK', 'OK_RELAXED', 'NO_CONDITION', 'NO_RESULT'))
);

-- 기간을 잘라 보는 질의가 기본입니다.
CREATE INDEX idx_nlr_recommendations_requested ON nlr_recommendations (requested_at);
-- 9장의 status 별 집계가 씁니다.
CREATE INDEX idx_nlr_recommendations_status    ON nlr_recommendations (status);


-- ---------------------------------------------------------------------------
-- 2. 결과 5개와 클릭.
--
-- 순위를 열쇠에 넣습니다. "몇 위를 눌렀나" 가 추천 품질의 직접 신호이고,
-- user_perfume_views 에는 그 값이 없습니다.
--
-- clicked_at 이 NULL 이면 안 누른 것입니다. 행 자체는 추천이 나간 순간 5행이 들어갑니다.
-- ---------------------------------------------------------------------------
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

-- "이 향수가 어떤 요청에서 나왔나" 를 거꾸로 봅니다.
CREATE INDEX idx_nlr_items_perfume ON nlr_recommendation_items (perfume_id);
-- 부분 인덱스입니다. 클릭은 전체의 일부라 NULL 을 색인하지 않습니다.
CREATE INDEX idx_nlr_items_clicked ON nlr_recommendation_items (clicked_at)
    WHERE clicked_at IS NOT NULL;


-- ---------------------------------------------------------------------------
-- 3. 사전이 받지 못한 표현.
--
-- AI 가 파일에 남기는 로그 한 줄과 1:1 입니다(ai/unmatched_log.py 102~114행).
-- 로그의 ts 가 여기서는 occurred_at 입니다.
--
-- 원문은 이 표에 두지 않습니다. 위 nlr_recommendations.raw_query 가 NOT NULL 이고
-- recommendation_id 도 NOT NULL 이라 조인으로 항상 닿습니다. 요청 1건당 미매칭이
-- 평균 2.18행이라 여기 두면 같은 원문이 그만큼 복사되고, 보관 기간이 지날 때
-- 두 곳을 지워야 합니다.
-- ---------------------------------------------------------------------------
CREATE TABLE nlr_unmatched_expressions (
    id                 BIGINT       GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    recommendation_id  BIGINT       NOT NULL,

    -- AI 가 ISO8601 문자열로 냅니다. 로그의 칸 이름은 ts 입니다.
    occurred_at        TIMESTAMPTZ  NOT NULL,

    -- ①단계 LLM 이 문장에서 뽑아낸 표현 그대로. '무겁지 않게' 처럼 문장 조각입니다.
    expression         VARCHAR(255) NOT NULL,

    -- 소문자·공백·유니코드를 정규화한 키. 집계는 이 칸으로 합니다.
    normalized_key     VARCHAR(255) NOT NULL,

    -- NOT_IN_LEXICON / CONDITION_NOT_MET / NOT_CORE. 셋은 고쳐야 할 곳이 다릅니다.
    unmatch_reason     VARCHAR(30)  NOT NULL,

    -- 사전에는 있는데 조건이 안 맞은 경우에만 그 사전 항목 id 가 들어갑니다.
    entry_id           VARCHAR(50),

    -- 조건을 뽑은 요청에서 나온 미매칭인가. 조건 0건만 보면 안 보이는 미매칭이
    -- 합성 600문장에서 1,339회였습니다.
    had_conditions     BOOLEAN      NOT NULL,

    -- LLM 이 추정한 accord 배열. 세 상태를 구분해야 합니다 — 아래 COMMENT 와 7장.
    llm_accords        TEXT[],

    -- LLM 의 설명. 사전의 rationale 과 같은 칸에 넣지 마십시오.
    -- 근거가 아니라 사후 해석입니다.
    llm_reasoning      TEXT,

    -- 'LLM' 또는 NULL. 사전 경로와 LLM 경로를 등급으로 가릅니다.
    tier               VARCHAR(20),

    -- 그 요청이 실제로 낸 추천 개수. 추정이 결과를 만들었는지 봅니다.
    result_count       INTEGER,

    CONSTRAINT fk_nlr_unmatched_recommendation
        FOREIGN KEY (recommendation_id) REFERENCES nlr_recommendations(recommendation_id)
        ON DELETE CASCADE
);

-- 집계가 normalized_key 로 묶습니다.
CREATE INDEX idx_nlr_unmatched_key  ON nlr_unmatched_expressions (normalized_key);
-- 기간을 잘라 보거나 보관 기간이 지난 줄을 찾을 때 씁니다.
CREATE INDEX idx_nlr_unmatched_time ON nlr_unmatched_expressions (occurred_at);


-- ---------------------------------------------------------------------------
-- 4. 만족도. 요청 1건에 1개입니다.
--
-- 점수가 아니라 세 분류입니다 — 만족 / 보통 / 불만족.
-- 점수(1~5)를 쓰지 않는 이유는 avg() 로 평균을 내면 "3.4점" 같은 수가 나오는데
-- 그 수가 무엇을 뜻하는지 설명할 수 없기 때문입니다. 세 분류는 "만족이 몇 건"
-- 으로만 읽히고, 그것이 실제로 쓰는 지표입니다.
--
-- 값은 팀 관례대로 대문자 영문으로 둡니다(status · from_location_type 과 같은 방식).
-- 화면에 보일 한국어 문구는 프론트엔드가 정합니다 — DB 에 한국어를 넣으면
-- 문구를 바꿀 때 데이터를 고쳐야 합니다.
--
-- recommendation_id 를 기본키로 둡니다. 같은 요청에 두 번 답하는 것을 DB 가 막습니다.
-- 다시 답하는 것을 허용할지는 기획 결정이고, 허용하려면 UPSERT 로 갱신하십시오.
-- ---------------------------------------------------------------------------
CREATE TABLE nlr_feedbacks (
    recommendation_id  BIGINT      PRIMARY KEY,

    -- SATISFIED / NEUTRAL / DISSATISFIED
    satisfaction       VARCHAR(20) NOT NULL,

    -- 함께 쓴 한마디. 사용자가 쓴 글이라 10장의 개인정보 대상입니다.
    comment            VARCHAR(500),

    answered_at        TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT fk_nlr_feedbacks_recommendation
        FOREIGN KEY (recommendation_id) REFERENCES nlr_recommendations(recommendation_id)
        ON DELETE CASCADE,
    CONSTRAINT ck_nlr_feedbacks_satisfaction
        CHECK (satisfaction IN ('SATISFIED', 'NEUTRAL', 'DISSATISFIED'))
);


COMMENT ON TABLE nlr_recommendations IS
    '자연어 추천 요청 1건. 나머지 nlr_* 표의 축. 백엔드가 INSERT · AI 서버는 접근하지 않는다';
COMMENT ON TABLE nlr_feedbacks IS
    '추천 만족도. 요청당 1개';
COMMENT ON COLUMN nlr_feedbacks.satisfaction IS
    '만족 SATISFIED / 보통 NEUTRAL / 불만족 DISSATISFIED. 점수가 아니라 분류다';
COMMENT ON COLUMN nlr_unmatched_expressions.llm_accords IS
    '빈 배열 = LLM 이 향이 아니라고 판정 · NULL = 묻지 않음. 둘을 구분해야 한다';
COMMENT ON COLUMN nlr_recommendations.lexicon_version IS
    '배포된 향 사전 버전. AI 응답에 이 값이 추가되면 NOT NULL 로 올릴 것';
```

인덱스 이름을 `idx_` 로 쓴 이유가 있습니다. 원래 명세 일부가 `ix_` 로 적었지만 **현재
DB 의 인덱스 16개가 `idx_` 이고 `ix_` 는 0개입니다** [측정]. 새 관례를 만들지 않았습니다.

### 4-3. 적용 방법

셋 중 하나를 쓰시면 됩니다. **팀이 문서로 정해 둔 방법은 ㉠입니다**
(`backend/db/seed/README.md` 320행 — *"애플리케이션을 한 번 띄우면 Flyway 가 적용합니다"*).

**㉠ 애플리케이션을 띄운다 — 권장**

`build.gradle` 30~31행에 `flyway-core` 와 `flyway-database-postgresql` 이 들어 있어
기동할 때 자동으로 적용됩니다. 파일을 두고 백엔드를 한 번 띄우면 끝입니다.

```bash
cd C:/Users/SSAFY/Desktop/S15P21E203
docker compose -f compose.manual-test.yaml up -d --build backend --wait
```

**㉡ 컨테이너의 psql 로 직접 넣는다**

애플리케이션을 띄울 수 없는 상황에서 씁니다. 이 경우 Flyway 이력에는 남지 않으므로
다음에 앱을 띄울 때 `V20` 이 이미 적용된 상태와 어긋납니다. **㉠이 가능하면 ㉠을 쓰십시오.**

```bash
cd C:/Users/SSAFY/Desktop/S15P21E203
docker compose -f compose.manual-test.yaml exec -T postgres \
  psql -U hyanghae -d hyanghae_test \
  -f - < backend/src/main/resources/db/migration/V20__add_nlr_feedback_tables.sql
```

**㉢ 로컬 psql 로 넣는다**

```bash
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 \
  -f backend/src/main/resources/db/migration/V20__add_nlr_feedback_tables.sql
```

### 4-4. 적용 후 확인

```bash
cd C:/Users/SSAFY/Desktop/S15P21E203
docker compose -f compose.manual-test.yaml exec -T postgres \
  psql -U hyanghae -d hyanghae_test -c "\dt nlr*"
```

```sql
-- 1. Flyway 이력에 V20 이 성공으로 남았는가 (㉠로 적용한 경우)
SELECT version, description, success FROM flyway_schema_history WHERE version = '20';

-- 2. 표 4개와 컬럼 수가 맞는가
SELECT table_name, count(*) AS 컬럼수
FROM information_schema.columns
WHERE table_schema = 'public' AND table_name LIKE 'nlr%'
GROUP BY 1 ORDER BY 1;

-- 3. 인덱스 6개 + 기본키 4개, 모두 10행이 나오는가
SELECT tablename, indexname FROM pg_indexes
WHERE tablename LIKE 'nlr%' ORDER BY 1, 2;

-- 4. 외래키가 제대로 걸렸는가
SELECT conname, pg_get_constraintdef(oid)
FROM pg_constraint
WHERE conrelid::regclass::text LIKE 'nlr%' AND contype = 'f'
ORDER BY 1;
```

기대하는 결과입니다.

```
1.  20 | add nlr feedback tables | t

2.  nlr_feedbacks               4
    nlr_recommendation_items    4
    nlr_recommendations        12
    nlr_unmatched_expressions  12

3.  nlr_feedbacks              nlr_feedbacks_pkey
    nlr_recommendation_items   idx_nlr_items_clicked
    nlr_recommendation_items   idx_nlr_items_perfume
    nlr_recommendation_items   nlr_recommendation_items_pkey
    nlr_recommendations        idx_nlr_recommendations_requested
    nlr_recommendations        idx_nlr_recommendations_status
    nlr_recommendations        nlr_recommendations_pkey
    nlr_unmatched_expressions  idx_nlr_unmatched_key
    nlr_unmatched_expressions  idx_nlr_unmatched_time
    nlr_unmatched_expressions  nlr_unmatched_expressions_pkey

4.  외래키 5개 (user · perfume · recommendation 3개)
```

**표가 비어 있는 것이 정상입니다.** 값이 들어오려면 11장의 백엔드·프론트엔드 작업이
필요합니다. **비어 있어도 서비스는 정상입니다** — 추천 품질은 이 표들과 무관하고
미매칭 캐시는 파일로 돕니다.

### 4-5. 이 DDL 은 실제로 통과합니다 [측정]

**위 4-2 의 코드 블록을 그대로 뽑아서** 수동 테스트 DB 에서 실행했습니다. 트랜잭션을 열고
실행한 뒤 `ROLLBACK` 했습니다. PostgreSQL 은 DDL 도 트랜잭션 안에서 처리하므로 DB 에는
아무것도 남지 않습니다.

4-4 의 확인 질의를 함께 돌려 **기대 결과와 실제가 일치하는 것**을 봤습니다 — 표 4개의
컬럼 수 `4 / 4 / 12 / 12`, 인덱스와 기본키 10행, 외래키 5개입니다.

```
BEGIN
CREATE TABLE  CREATE INDEX ×2      nlr_recommendations
CREATE TABLE  CREATE INDEX ×2      nlr_recommendation_items
CREATE TABLE  CREATE INDEX ×2      nlr_unmatched_expressions
CREATE TABLE                       nlr_feedbacks
INSERT 0 4 / 0 5 / 0 3 / 0 3       요청 4건 · 결과 5행 · 미매칭 3행 · 만족도 3건
ROLLBACK
leftover  0                        ← 롤백 뒤 nlr% 표가 0개임을 다시 확인
```

**외래키가 실제로 이어지는지** 확인했습니다. 존재하는 `perfume_id` 1~5 로 결과 행을
넣고, `user_id` 는 `NULL`(비로그인)로 넣어 통과했습니다.

**원문이 조인으로 닿는지** 확인했습니다 — 미매칭 표에서 `raw_text` 를 뺀 근거입니다.

```
 normalized_key |            raw_query
----------------+----------------------------------
 은은한 꽃향    | 은은한 꽃향이 나는 향수 추천해줘
 10만원 이하    | 은은한 꽃향이 나는 향수 추천해줘
```

7장의 **세 상태가 실제로 구분되는지** 세 행을 넣어 확인했습니다.

```
 expression  | is_null | is_empty | n
-------------+---------+----------+---
 은은한 꽃향 | f       | f        | 2     ← {floral,powdery}
 10만원 이하 | f       | t        | 0     ← {} 빈 배열
 무겁지 않게 | t       |          |       ← NULL
```

**만족도의 `CHECK` 가 잘못된 값을 막는지** 확인했습니다. 세 값(`SATISFIED` ·
`NEUTRAL` · `DISSATISFIED`)은 들어가고, 한국어 `'만족'` 을 넣으려 하니 막혔습니다.

```
=== CHECK 가 잘못된 값을 막는가 ===
NOTICE:  정상: CHECK 가 막았다
```

`comment` 를 `NULL` 로 둔 행도 통과했습니다 — **버튼만 누르고 한마디를 안 써도
됩니다.**

### 4-6. 되돌리기

Flyway 에는 자동 되돌리기가 없습니다. 손으로 지웁니다. **만드는 순서의 역순입니다.**

```sql
DROP TABLE IF EXISTS nlr_feedbacks;
DROP TABLE IF EXISTS nlr_unmatched_expressions;
DROP TABLE IF EXISTS nlr_recommendation_items;
DROP TABLE IF EXISTS nlr_recommendations;
DELETE FROM flyway_schema_history WHERE version = '20';
```

`nlr_recommendations` 를 먼저 지우려 하면 나머지 셋의 외래키가 막습니다.
`DROP TABLE nlr_recommendations CASCADE` 로 한 번에 지울 수도 있지만, **무엇이 함께
지워지는지 보이지 않아** 위 순서를 권합니다.

**기존 표를 참조만 하고 바꾸지 않으므로 지워도 다른 데이터에 영향이 없습니다.**
`users` 와 `perfumes` 는 가리키기만 합니다.

---

## 5. 컬럼 — 백엔드가 채울 수 있는가 [측정]

각 컬럼의 값이 지금 AI 응답에 있는지 대조했습니다. **`✓` 는 지금 받을 수 있는 것,
`✗` 는 못 받는 것입니다.**

### 5-1. `nlr_recommendations`

| 컬럼 | 값의 출처 | 지금 |
|---|---|---|
| `recommendation_id` | DB 가 만듭니다 | — |
| `user_id` | 백엔드 인증 | ✓ |
| `raw_query` | 백엔드가 받은 문장 | ✓ |
| `status` | 응답 `status` | ✓ |
| `stage` | 응답 `diagnostics.stage` | ✓ |
| `source` | 응답 `conditions.source` | ✓ |
| `core_accords` | 응답 `conditions` | ✓ |
| `avoid_accords` | 응답 `conditions` | ✓ |
| `candidate_count` | 응답 `diagnostics.candidateCount` | ✓ |
| `lexicon_version` | **없습니다** | **✗ 6장** |
| `prompt_sha256` | **기동 로그에만 있습니다** | **✗ 6장** |
| `requested_at` | 백엔드 시계 | ✓ |

값이 코드와 맞는지 확인했습니다 [측정].

```
status 4종      OK / OK_RELAXED / NO_CONDITION / NO_RESULT     nlr_api_contract.md 112~114행
source 3종      lexicon_only / llm+lexicon / llm_no_effect     nlr_engine.py 356·358행
raw_query 500   query 는 1~500자. 초과하면 400                  nlr_api_contract.md 70행
```

`stage` 는 실제 값이 **여섯 개**입니다 [측정]. `nlr_engine.py` 에서 직접 뽑았습니다.

```
AND (534행) · SINGLE_BROAD (524행) · RELAXED_OR (542행)
RELAXED_OR_NO_THRESHOLD (554행) · NOT_ENOUGH (554행) · NO_CONDITION (497행)
```

가장 긴 `RELAXED_OR_NO_THRESHOLD` 가 23자라 `VARCHAR(30)` 에 들어갑니다.
**`stage` 에 `CHECK` 를 걸지 않았습니다** — API 계약 275행이 다섯 개만 적어 두었고
`NOT_ENOUGH` 가 빠져 있어, 계약을 믿고 제약을 걸면 그 값이 들어올 때 `INSERT` 가 깨집니다.

### 5-2. `nlr_recommendation_items`

| 컬럼 | 값의 출처 | 지금 |
|---|---|---|
| `recommendation_id` | 위 표의 열쇠 | ✓ |
| `rank` | 응답 `results` 배열 순서 | ✓ |
| `perfume_id` | 응답 `results[].fragranticaId` → `perfumes.fragrantica_id` 로 조회 | ✓ |
| `clicked_at` | **프론트엔드가 클릭을 알려줘야 합니다** | **✗ 11장** |

`rank BETWEEN 1 AND 5` 의 근거는 `nlr_engine.py` 46행 `TOP_K = 5` 입니다 [측정].
**다만 그 값에 `[제안]` 이 붙어 있고 요구사항 NLR-01 은 "3~5개" 입니다.** 5보다 늘릴
계획이 생기면 이 `CHECK` 를 함께 고쳐야 합니다.

`perfume_id` 를 바로 받을 수 없다는 점에 주의하십시오. 응답이 주는 것은 Fragrantica
원본 번호이고, DB 의 `perfumes.perfume_id` 와 다릅니다. `perfumes.fragrantica_id` 로
찾아 바꿔 넣어야 합니다.

### 5-3. `nlr_unmatched_expressions` — 로그 한 줄과 1:1 [측정]

`ai/unmatched_log.py` 102~114행이 실제로 쓰는 JSON 칸입니다.

| 컬럼 | 로그의 칸 | 주의 |
|---|---|---|
| `id` | — | AI 가 내지 않습니다 |
| `recommendation_id` | — | 백엔드가 이어 붙입니다 |
| `occurred_at` | `ts` | **이름이 다릅니다** |
| `expression` | `expression` | `무겁지 않게` 처럼 문장 조각 |
| `normalized_key` | `normalized_key` | **집계는 이걸로 합니다.** 인덱스 대상 |
| `unmatch_reason` | `unmatch_reason` | 세 값. 아래 |
| `entry_id` | `entry_id` | 사전에 있는데 조건이 안 맞은 경우만 |
| `had_conditions` | `had_conditions` | `NOT NULL` 입니다 — 11장 |
| `llm_accords` | `llm_accords` | **세 상태를 구분** (7장) |
| `llm_reasoning` | `llm_reasoning` | 근거가 아니라 사후 해석 |
| `tier` | `tier` | `'LLM'` 또는 `NULL` |
| `result_count` | `result_count` | 추정이 결과를 만들었는지 |
| ~~`raw_text`~~ | `raw_text` | **뺐습니다.** `nlr_recommendations.raw_query` 로 갑니다 (8장) |

`unmatch_reason` 세 값은 고쳐야 할 곳이 다릅니다.

```
NOT_IN_LEXICON     사전에 없다                -> 사전에 항목을 추가한다
CONDITION_NOT_MET  match_condition 이 탈락    -> 조건 토큰을 손본다
NOT_CORE           optional / NO_MAPPING     -> 판정 이력이 있다. 함부로 올리지 않는다
```

### 5-4. `nlr_feedbacks` — 만족도

| 컬럼 | 값의 출처 | 지금 |
|---|---|---|
| `recommendation_id` | 위 표의 열쇠 | ✓ |
| `satisfaction` | **프론트엔드의 버튼 3개 중 사용자가 누른 것** | **✗ 11장** |
| `comment` | 같은 화면의 한마디 입력칸 (선택) | **✗ 11장** |
| `answered_at` | 백엔드 시계 | ✓ |

### 어떻게 채워지는가

**점수를 계산하지 않습니다. 사용자가 누른 것 하나를 그대로 한 칸에 넣습니다.**

```
1. 추천 결과 화면에 버튼 셋을 보여준다        만족  |  보통  |  불만족
2. 사용자가 하나를 누른다                     → "만족" 을 눌렀다
3. 프론트가 그 선택을 백엔드로 보낸다          satisfaction = "SATISFIED"
4. 백엔드가 그 요청의 recommendation_id 와    INSERT INTO nlr_feedbacks
   함께 한 행을 넣는다                        (recommendation_id, satisfaction)
                                             VALUES (8213, 'SATISFIED')
```

한 요청에 한 행이고, 값은 셋 중 하나입니다. 계산도 변환도 없습니다.

| 화면에 보이는 것 | DB 에 들어가는 값 |
|---|---|
| 만족 | `SATISFIED` |
| 보통 | `NEUTRAL` |
| 불만족 | `DISSATISFIED` |

**DB 에는 대문자 영문을 넣습니다.** 팀의 기존 관례와 같습니다(`status` 는 `OK`,
`from_location_type` 은 `SEARCH`). 화면 문구를 "좋아요 / 그냥 그래요 / 아쉬워요" 로
바꾸고 싶어지면 **프론트엔드만 고치면 되고 쌓인 데이터는 그대로 씁니다.** 한국어를
DB 에 넣으면 문구를 바꿀 때마다 기존 행을 고쳐야 하고, 옛 문구와 새 문구가 섞여
집계가 갈립니다.

`CHECK` 가 세 값만 받습니다. **실제로 한국어 `'만족'` 을 넣어 보니 막혔습니다**
[측정 · 4-5]. 프론트가 잘못된 값을 보내면 조용히 들어가지 않고 오류가 납니다.

### 세 분류로 정한 것의 결과 — 평균을 못 냅니다

점수가 아니므로 `avg()` 가 성립하지 않습니다. 대신 **분류별 개수**를 셉니다.
9장에 실제로 돌려 본 질의가 있습니다.

```
 status | 요청수 | 응답수 | 만족 | 보통 | 불만족
--------+--------+--------+------+------+--------
 OK     |      3 |      3 |    1 |    1 |      1
```

`1~5` 점이었다면 `3.4점` 같은 수가 나오는데, 그 수가 무엇을 뜻하는지 설명할 수
없습니다. **세 분류는 "만족이 몇 건" 으로만 읽히고 그게 실제로 쓰는 지표입니다.**

한 가지만 알아 두시면 됩니다. 나중에 **`보통` 을 없애고 두 분류로 바꾸거나 다섯
분류로 늘리면 `CHECK` 를 고치는 마이그레이션이 하나 더 필요합니다.** 쌓인 데이터는
남지만 새 값이 들어오기 전까지는 옛 분류로만 세어집니다.

### `comment` 는 선택 입력입니다

`comment VARCHAR(500)` 은 `raw_query` 와 같은 길이로 맞춘 것이고 [제안] 입니다.
`NULL` 허용이므로 **버튼만 누르고 아무것도 안 써도 됩니다.** 4-5 에서 `NULL` 로
넣어 통과하는 것을 확인했습니다.

**여기에도 사용자가 쓴 글이 들어가므로 10장의 개인정보 대상입니다.**

---

## 6. ⚠ 백엔드가 지금 채울 수 없는 컬럼 둘 [측정]

**이 문서에서 가장 먼저 처리해야 할 것입니다.**

### `lexicon_version` — 값이 아예 없습니다

```
grep "lexicon_version|lexiconVersion"  ai/ 전체  →  0건
```

AI 응답에도, `/health` 에도 없습니다. `/health` 가 돌려주는 것은 넷뿐입니다
(`ai/server.py` 271~272행).

```json
{"status": "ok", "perfumes": 129161, "accords": 92, "llm": true}
```

**안건 ②의 원설계는 이 컬럼을 `NOT NULL` 로 잡았습니다.** 그대로 만들면 백엔드가 넣을
값이 없어 **모든 `INSERT` 가 실패합니다.** 그래서 이 문서의 DDL 에서는 `NULL` 허용으로
바꿨습니다.

### ✅ ㉠ 으로 정했습니다 (2026-09-17)

**AI 응답에 `lexiconVersion` 칸을 더합니다. AI 담당이 작업합니다.**

검토한 세 방법과 그 근거를 남깁니다.

| 방법 | 얻는 것 | 잃는 것 | 결정 |
|---|---|---|---|
| **㉠ AI 응답에 칸을 더한다** | 실제 배포본이 정확히 들어갑니다 | API 계약 변경. AI·백엔드가 같이 움직여야 합니다 | **✅ 채택** |
| ㉡ `/health` 에 더한다 | 계약 변경이 작습니다 | 백엔드가 기동 때 한 번 읽어 캐시해야 하고, AI 재배포를 놓치면 낡습니다 | 기각 |
| ㉢ 백엔드 설정에 적어 둔다 | 지금 바로 가능합니다 | **AI 가 사전을 바꾸면 조용히 어긋납니다** | 기각 |

㉡·㉢을 기각한 이유가 같습니다. **둘 다 값이 낡을 수 있고, 낡았다는 것을 아무도
모릅니다.** 이 컬럼의 목적이 *"이 기록이 어느 사전에서 나왔는지"* 를 남기는 것이라,
틀린 값이 들어가면 컬럼이 없는 것보다 나쁩니다. 없으면 모른다는 것을 알지만, 틀리면
아는 줄 착각합니다.

**DB 담당자가 할 일은 없습니다.** DDL 의 `NULL` 허용을 그대로 두시면 됩니다.

### 언제 `NOT NULL` 로 올릴 것인가

㉠ 작업이 끝나 값이 들어오기 시작하면 `NOT NULL` 로 올리는 마이그레이션(`V21` 등)을
하나 더 넣는 편이 좋습니다. **다만 그때 기존 행을 먼저 채워야 합니다** — `NULL` 인 행이
하나라도 있으면 제약 추가가 실패합니다.

```sql
-- 계약 변경 전에 쌓인 행을 그때 배포본으로 메꾼 뒤에 제약을 건다
UPDATE nlr_recommendations SET lexicon_version = 'v1_8' WHERE lexicon_version IS NULL;
ALTER TABLE nlr_recommendations ALTER COLUMN lexicon_version SET NOT NULL;
```

**이 `UPDATE` 는 추측으로 메꾸는 것입니다.** 그 기간에 실제로 돌던 사전이 무엇인지
배포 기록으로 확인한 뒤에 쓰십시오. 확인이 안 되면 `NOT NULL` 로 올리지 않고 `NULL` 을
*"모른다"* 로 남겨 두는 편이 정확합니다.

### 왜 이 컬럼을 포기하면 안 되나

`EDA/delivery/lexicon_v1_14/README.md` 82행이 이 컬럼을 요구합니다.

> **`lexicon_version` 컬럼** — 안건 ②의 피드백 테이블에 실제 배포본 값이 들어가야 합니다

최근에도 사전이 v1.8 → v1.14, 프롬프트가 v1 → v4 로 움직였습니다. **버전을 안 남기면
반년 뒤에 이 기록을 해석할 수 없습니다.** "이 표현이 미매칭이었다" 가 어느 사전에서
미매칭이었는지 모르면 사전 확장 근거가 되지 않습니다.

### `prompt_sha256` — 기동 로그에만 있습니다

`llm_stage1.status()` 가 만들지만 그 값이 가는 곳은 로그 한 줄뿐입니다
(`ai/server.py` 107~109행).

```python
LOGGER.info("①단계 LLM 구조화 %s (model=%s prompt=%s)",
            "켜짐" if llm["enabled"] else "꺼짐 — GMS_API_KEY 가 없다",
            llm["model"], llm["prompt_sha256"])
```

`VARCHAR(16)` 은 정확한 크기입니다 — `hashlib.sha256(...).hexdigest()[:16]` 이라
언제나 16자입니다 [측정 · `ai/llm_stage1.py` 104·114행].

이 컬럼은 `NULL` 허용이므로 **비워 두고 시작해도 `INSERT` 가 깨지지 않습니다.**
`lexicon_version` 보다 급하지 않습니다.

---

## 7. ⚠ `llm_accords` 는 세 가지 상태를 담습니다

```
['woody','green']   LLM 이 accord 를 골랐다
[]  (빈 배열)        **LLM 이 "향이 아니다" 라고 판정했다** — 가격·성별·지속력 같은 것
NULL                아직 묻지 않았다 (추정이 꺼져 있었거나 호출이 실패했다)
```

**`NOT NULL DEFAULT '{}'` 로 만들지 마십시오.** 세 가지가 두 가지로 뭉개져서 *"다시
물어봐야 할 표현"* 을 골라낼 수 없습니다.

전체 표현의 **38% 가 빈 배열**입니다 [측정 · 369개 중 140개]. 작은 예외가 아닙니다.

4-5 에서 세 상태가 실제로 갈리는 것을 확인했습니다. `llm_accords IS NULL` 과
`llm_accords = '{}'` 로 구분됩니다.

### ✅ `TEXT[]` 로 정했습니다 (2026-09-17)

**이 DB 의 첫 배열 컬럼이라는 점은 알고 정했습니다** [측정].

```sql
SELECT table_name, column_name FROM information_schema.columns
WHERE table_schema = 'public' AND data_type = 'ARRAY';
-- 0행
```

검토한 세 방법과 결정 근거를 남깁니다.

| 선택 | 얻는 것 | 잃는 것 | 결정 |
|---|---|---|---|
| **`TEXT[]`** | SQL 에서 `unnest` 로 바로 풀림 | 이 DB 의 첫 배열 | **✅ 채택** |
| `JSONB` | Hibernate 매핑 관례가 흔함 | 집계 질의가 길어짐 | 기각 |
| 자식 테이블 | 정석. 인덱스가 자연스러움 | 표 5개가 됨 · **빈 배열과 `NULL` 구분 불가** | 기각 |

**채택 근거 둘입니다.**

첫째, **이 표를 JPA 엔티티로 읽을 일이 없습니다.** 백엔드는 `INSERT` 만 하고 읽는 것은
사람이 SQL 로 직접 합니다. `TEXT[]` 의 단점인 Hibernate 매핑 문제가 실제로는 발생하지
않습니다.

둘째, **팀이 이미 로그성 표를 `JdbcClient` 로 다루고 있습니다** [측정].

```
JdbcClient 를 쓰는 파일   7개   ExplorationLogRepository · PerfumeRankingRepository ·
                                ExplorationStateRepository · ScentMapRepository ...
@Entity 로 된 것         28개   그중 배열 컬럼을 쓰는 것은 0개
```

`ExplorationLogRepository` 가 이 표들과 성격이 가장 비슷합니다. `JdbcClient` 로는
배열을 그대로 넘길 수 있어 변환기가 필요 없습니다.

**자식 테이블을 기각한 이유는 따로 적어 둘 만합니다.** 관계형 DB 의 정석인데도 여기서는
맞지 않습니다. 자식 표에 행이 0개일 때 *"LLM 이 향이 아니라고 판정했다"* 인지 *"아직
안 물어봤다"* 인지 구분할 수 없습니다. 구분하려면 부모 표에 플래그 컬럼을 하나 더 둬야
하고, **정석을 따르려다 오히려 복잡해집니다.** 그리고 이건 드문 경우가 아닙니다 —
367건 중 140건(38.1%)이 "향이 아니다" 판정입니다.

### 집계는 이렇게 합니다

```sql
-- LLM 이 실제로 고른 accord 를 많이 나온 순으로
SELECT unnest(llm_accords) AS accord, count(*) AS 횟수
FROM nlr_unmatched_expressions
WHERE llm_accords IS NOT NULL AND cardinality(llm_accords) > 0
GROUP BY 1 ORDER BY 2 DESC;

-- 다시 물어봐야 할 표현 (아직 안 물어본 것만)
SELECT normalized_key, count(*)
FROM nlr_unmatched_expressions
WHERE llm_accords IS NULL
GROUP BY 1 ORDER BY 2 DESC;
```

두 번째 질의가 `TEXT[]` 를 고른 값어치입니다. `llm_accords IS NULL` 한 줄로 *"안
물어본 것"* 만 골라집니다.

**두 질의를 실제로 돌려 확인했습니다** [측정 · 4-5 와 같은 방식].

```
--- 질의 1 ---                      --- 질의 2 ---
    accord    | 횟수                  normalized_key | count
--------------+------                ----------------+-------
 citrus       |    1                  여성스러운     |     2
 floral       |    1
 fresh        |    1
 rose         |    1
 white floral |    1                 ← 공백이 들어간 이름도 제대로 나옵니다
```

### ⚠ accord 이름에 공백이 있습니다 — `INSERT` 할 때 주의

**92개 accord 중 10개에 공백이 있습니다** [측정 · `accords` 표 조회].

```
white floral · yellow floral · warm spicy · fresh spicy · soft spicy
hot iron · wet plaster · industrial glue · brown scotch tape · tennis ball
```

배열 리터럴에서는 그런 값을 따옴표로 감싸야 합니다.

```sql
'{floral,"white floral",rose}'     -- 맞음
'{floral,white floral,rose}'       -- 틀림. 값이 넷으로 쪼개집니다
```

**드라이버로 배열을 넘기면 이 문제가 없습니다.** `JdbcClient` 나 JDBC 의
`createArrayOf("text", ...)` 는 따옴표를 알아서 붙입니다. 문자열을 직접 조립할 때만
걸립니다.

---

## 8. 두 설계를 합쳤습니다 — 근거와 되돌리는 방법

`NLR_PREDEPLOY_DECISIONS.md` 에는 `nlr_unmatched_expressions` 가 **두 번, 서로 다른
모양으로** 설계돼 있었습니다. 표 이름이 같아 둘 다 만들 수 없습니다.

| | 안건 ② (문서 404행) | 안건 ③ 후속 (문서 569행) | **이 문서** |
|---|---|---|---|
| 컬럼 수 | 6 | 12 | **12** |
| `recommendation_id` | 있다 | 없다 | **있다** |
| `raw_text` | 없다 | 있다 | **없다** |
| `llm_accords` 등 5칸 | 없다 | 있다 | **있다** |
| 로그와 1:1 | ✗ | ✓ | **✓** |

### 왜 합쳤나

안건 ②가 스스로 적은 설계 원칙 2번이 이렇습니다.

> **미매칭 로그의 기존 필드를 그대로 옮긴다** — `unmatched_log.py` 와 1:1

**안건 ②의 DDL 은 그 원칙을 지키지 않습니다.** 로그가 11칸인데 DDL 은 6칸입니다.
안건 ③ 후속(더 나중에 작성)이 11칸으로 맞춘 것이 원칙을 실제로 지킨 판입니다.
그래서 칸 구성은 후속을 따르고, 요청과 묶는 `recommendation_id` 는 안건 ②에서
가져왔습니다.

### `raw_text` 를 뺀 것은 이 문서의 판단입니다 [제안]

원문이 `nlr_recommendations.raw_query` 에 `NOT NULL` 로 있고 `recommendation_id` 도
`NOT NULL` 이라 조인으로 항상 닿습니다(4-5 에서 확인). 남겨 두면 두 가지가 생깁니다.

```
중복      요청 1건당 미매칭 평균 2.18행. 같은 원문이 그만큼 복사된다
개인정보  30일 규칙이 지울 곳이 하나 늘어난다. 한 곳을 잊으면 원문이 남는다
```

10장의 30일 규칙은 지금 `UPDATE` **두 개**입니다(`raw_query` 와 `comment`).
`raw_text` 를 남겨 두면 **세 개**가 되고, 그중 가장 행이 많은 표를 대상으로 합니다.

**되돌리기는 한 줄입니다.** 원문을 이 표에도 두고 싶으시면 `occurred_at` 아래에
`raw_text VARCHAR(500),` 을 넣으시면 됩니다. 그 경우 10장에 `UPDATE` 를 하나 더
넣어야 합니다.

### 안건 ③ 후속의 "독립 표" 성질은 잃습니다

`recommendation_id NOT NULL` 이므로 **`nlr_recommendations` 행이 먼저 있어야 미매칭을
넣을 수 있습니다.** 안건 ③ 후속은 백엔드가 미매칭만 먼저 기록하는 경우를 염두에 두고
독립 표로 설계했습니다. 그 경로를 쓰시려면 `recommendation_id` 를 `NULL` 허용으로
바꾸십시오. 다만 그러면 9장의 핵심 질의가 그 행들을 못 씁니다.

---

## 9. 이 설계의 값어치 — 핵심 질의

### 사전 확장 후보를 실사용 행동에서 뽑는다

```sql
SELECT u.normalized_key            AS 표현,
       a.name                      AS accord,
       count(*)                    AS 클릭수,
       round(avg(i.rank), 1)       AS 평균순위
FROM nlr_unmatched_expressions u
JOIN nlr_recommendation_items  i ON i.recommendation_id = u.recommendation_id
JOIN perfume_accords          pa ON pa.perfume_id = i.perfume_id
JOIN accords                   a ON a.accord_id = pa.accord_id
WHERE i.clicked_at IS NOT NULL
  AND pa.weight >= 0.5              -- 그 향수에서 뚜렷한 accord 만
GROUP BY 1, 2
HAVING count(*) >= 5                -- 우연 제외
ORDER BY 3 DESC;
```

나오는 결과가 이런 모양입니다.

```
표현              accord         클릭수   평균순위
은은한 꽃향        floral           23      2.1
은은한 꽃향        white floral     19      2.3
따뜻한 향신료 느낌  warm spicy       17      1.8
```

**이 질의는 4-5 에서 실제로 돌려 확인했습니다** [측정]. 세 표를 조인해 결과가 나왔습니다.

### ⚠ 만족도 집계 질의에 결함이 있었습니다 [측정]

안건 ②가 적어 둔 만족도 질의를 **실제로 돌려 보니 수가 틀립니다.**

```sql
-- 안건 ② 원문 — 쓰지 마십시오
SELECT r.status, count(*) AS 요청수,
       round(avg(f.satisfied), 2) AS 평균만족도
FROM nlr_recommendations r
LEFT JOIN nlr_recommendation_items i ON i.recommendation_id = r.recommendation_id
LEFT JOIN nlr_feedbacks            f ON f.recommendation_id = r.recommendation_id
GROUP BY 1;
```

이 질의에는 문제가 **둘** 있습니다.

**첫째, `avg(f.satisfied)` 가 성립하지 않습니다.** 만족도는 이제 점수가 아니라
`SATISFIED` · `NEUTRAL` · `DISSATISFIED` 세 분류입니다. 문자열의 평균은 계산할 수
없습니다.

**둘째, 점수였다 해도 수가 틀립니다.** 실제로 돌려 확인했습니다.

요청 4건을 넣었습니다. `OK` 3건에 만족 1건 · 보통 1건 · 불만족 1건, `NO_CONDITION`
1건입니다. 그리고 **1번 요청만 결과가 3행이고** 나머지는 1행입니다.

```
안건 ② 형태 (items 를 그대로 조인)        사실
 status       | 요청수 | 만족            status       | 요청수 | 만족
--------------+--------+------           --------------+--------+------
 NO_CONDITION |      1 |    0            NO_CONDITION |      1 |    0
 OK           |      5 |    3            OK           |      3 |    1
```

**요청수가 3인데 5로, 만족이 1건인데 3건으로 세어집니다.**

원인은 **팬아웃**입니다. `nlr_recommendation_items` 를 조인하면 요청 1행이 결과 행
수만큼 불어납니다. 1번 요청은 결과가 3행이라 그 요청의 만족 1건이 **세 번** 세어집니다.
`3 + 1 + 1 = 5` 가 요청수로, 만족은 `3` 으로 나옵니다. **결과가 많이 나온 요청의
피드백에 가중치가 붙습니다.**

점수였을 때도 같은 일이 생깁니다. 4점(결과 3행)과 1점(결과 1행)이면
`(4+4+4+1)/4 = 3.25` 가 되는데 진짜 평균은 `2.50` 입니다 [측정].

### 고친 질의 — 분류별로 셉니다

자식 표를 미리 한 행으로 접어 팬아웃을 없애고, 평균 대신 분류별 개수를 셉니다.

```sql
SELECT r.status,
       count(*)                                                AS 요청수,
       count(f.recommendation_id)                              AS 응답수,
       count(*) FILTER (WHERE f.satisfaction = 'SATISFIED')     AS 만족,
       count(*) FILTER (WHERE f.satisfaction = 'NEUTRAL')       AS 보통,
       count(*) FILTER (WHERE f.satisfaction = 'DISSATISFIED')  AS 불만족,
       count(*) FILTER (WHERE it.clicked > 0)                   AS 클릭발생요청수
FROM nlr_recommendations r
LEFT JOIN (SELECT recommendation_id,
                  count(*) FILTER (WHERE clicked_at IS NOT NULL) AS clicked
           FROM nlr_recommendation_items GROUP BY 1) it
       ON it.recommendation_id = r.recommendation_id
LEFT JOIN nlr_feedbacks f ON f.recommendation_id = r.recommendation_id
GROUP BY 1
ORDER BY 1;
```

**실제로 돌려 사실과 일치하는 것을 확인했습니다** [측정].

```
    status    | 요청수 | 응답수 | 만족 | 보통 | 불만족 | 클릭발생요청수
--------------+--------+--------+------+------+--------+----------------
 NO_CONDITION |      1 |      0 |    0 |    0 |      0 |              0
 OK           |      3 |      3 |    1 |    1 |      1 |              2
```

`응답수` 를 따로 세는 이유가 있습니다. **버튼을 누르지 않은 요청이 있습니다.**
`요청수` 와 `응답수` 가 다르면 그 차이가 무응답이고, `만족 / 응답수` 가 아니라
`만족 / 요청수` 로 계산하면 응답률 변화가 만족도 변화처럼 보입니다.

`nlr_feedbacks` 는 `recommendation_id` 가 기본키라 요청당 1행이므로 그대로 조인해도
팬아웃이 없습니다. **`it` 만 접으면 됩니다.**

**표 설계 자체는 문제가 없습니다.** 예시 질의만 고쳐야 합니다. 다만 이 결함이
`NLR_PREDEPLOY_DECISIONS.md` 에 그대로 남아 있으니, 그 문서를 보고 지표를 만들면
같은 오차가 생깁니다.

### 이 질의가 처음으로 답하는 것

`OK_RELAXED`(*"조건을 넓혀 찾았습니다"*)가 **실제로 나쁜 추천인지** 지금은 모릅니다.
합성 평가셋으로는 잴 수 없고, 사용자가 그 결과를 눌렀는지와 몇 점을 줬는지가 있어야
답이 나옵니다.

---

## 10. ⚠ 개인정보 — 같이 정해야 합니다

사용자가 쓴 글이 **두 칸**에 들어갑니다.

```
nlr_recommendations.raw_query   추천을 요청한 문장        NOT NULL
nlr_feedbacks.comment           만족도에 함께 쓴 한마디    NULL 허용
```

> `NLR_DEPLOY_HANDOFF.md` 경고 — *"실사용자 설문에서 건강·신분 관련 서술이 있었습니다."*

```
지금 (파일)   AI 컨테이너 볼륨 하나        접근 = AI 담당
DB 로 옮기면  백엔드 · 운영 · 백업이 다 접근
```

| 정할 것 | 선택지 | 현재 |
|---|---|---|
| **보관 기간** | 30일 / 90일 / 무기한 | **✅ 30일로 확정** (2026-09-17) |
| **`comment` 도 대상인가** | `raw_query` 만 / 둘 다 | **둘 다** [제안] — 아래 |
| **지우는 주체** | 배치 / 파티션 / 손으로 | **미결 — 백엔드·인프라가 정해야 합니다** |
| 익명화 | `user_id` 를 안 남긴다 / 남기되 탈퇴 시 `NULL` | DDL 은 후자 |
| 접근 범위 | 운영 DB 직접 조회 / 별도 분석 계정 | **미결** |

### 30일 규칙 — 무엇을 지우는가

**행을 지우는 것이 아니라 원문 칸만 비웁니다.**

```sql
-- 30일이 지난 요청의 원문을 비웁니다. 행은 남습니다.
UPDATE nlr_recommendations
SET raw_query = ''
WHERE requested_at < now() - INTERVAL '30 days'
  AND raw_query <> '';

UPDATE nlr_feedbacks f
SET comment = NULL
FROM nlr_recommendations r
WHERE r.recommendation_id = f.recommendation_id
  AND r.requested_at < now() - INTERVAL '30 days'
  AND f.comment IS NOT NULL;
```

`raw_query` 는 `NOT NULL` 이라 `NULL` 이 아니라 빈 문자열로 비웁니다. 파일 쪽
`unmatched_log.purge_raw_text()` 도 같은 방식입니다 — 원문을 `""` 로 바꿉니다.

**행을 지우면 안 됩니다.** `nlr_recommendations` 를 지우면 `ON DELETE CASCADE` 로
결과·클릭·미매칭·만족도가 **모두 함께 사라집니다.** 사전을 키우는 데 필요한
`expression` 과 `normalized_key` 까지 없어집니다. 지울 것은 원문뿐입니다.

`comment` 도 함께 비우도록 적은 것은 [제안] 입니다. 사용자가 직접 쓴 글이라
`raw_query` 와 성질이 같고, 한쪽만 비우면 개인정보가 절반 남습니다.
**`raw_query` 만 비우기로 하시면 위 두 번째 `UPDATE` 를 빼십시오.**

`satisfaction` 은 비우지 않습니다. `SATISFIED` 같은 값에는 개인정보가 없고,
이것이 만족도 지표의 본체입니다.

**이 `UPDATE` 두 개를 실제로 돌려 확인했습니다** [측정]. 40일 전 요청과 10일 전 요청을
넣고 트랜잭션에서 실행한 뒤 `ROLLBACK` 했습니다.

```
--- 비우기 전 ---
 id |          raw_query          |    comment     | satisfaction
----+-----------------------------+----------------+--------------
  1 | 40일 전에 물어본 문장입니다 | 40일 전 한마디 | SATISFIED
  2 | 10일 전에 물어본 문장입니다 | 10일 전 한마디 | DISSATISFIED

--- 비운 뒤 ---
 id |          raw_query          |    comment     | satisfaction
----+-----------------------------+----------------+--------------
  1 |                             |                | SATISFIED      ← 원문만 비었다
  2 | 10일 전에 물어본 문장입니다 | 10일 전 한마디 | DISSATISFIED   ← 30일 안이라 그대로

--- 미매칭 표현은 남아 있는가 ---
 id | expression | normalized_key
----+------------+----------------
  1 | 여성스러운 | 여성스러운                                      ← 남았다
```

**30일이 지난 요청에서도 `satisfaction` 과 미매칭 표현은 그대로 남습니다.** 만족도 지표와
사전 확장 근거는 보관 기간과 무관하게 계속 쌓입니다.

### 30일 기준 시각은 `requested_at` 입니다

`nlr_feedbacks.answered_at` 이 아니라 **요청 시각**을 기준으로 잡았습니다. 설문을
나중에 답하는 경우 두 시각이 벌어지는데, 기준이 두 개면 같은 요청의 원문과 한마디가
다른 날 지워집니다.

### ⚠ 자동 실행을 누가 만들지 아직 정해지지 않았습니다

파일 쪽에는 `unmatched_log.purge_raw_text()` 가 있고 `RETENTION_DAYS = 30` 으로
이번 결정과 이미 같습니다. **다만 자동 실행이 없어 아무도 부르지 않으면 안 지워집니다.**

DB 쪽도 같은 위험이 있습니다. 위 `UPDATE` 두 개를 **누가 언제 돌릴지** 정해야 합니다.

```
배치         백엔드 스케줄러가 하루 한 번 돈다        ← 가장 단순합니다 [제안]
파티션       월 단위로 잘라 통째로 떨군다             ← 규모가 커지면
손으로       사람이 기억해서 돌린다                  ← 권하지 않습니다. 잊습니다
```

**"30일" 을 정한 것과 "30일이 지나면 실제로 지워지는 것" 은 다릅니다.** 돌리는 주체가
정해지기 전까지는 원문이 계속 쌓입니다.

**원문을 비워도 분석은 살아 있습니다.** `raw_query` 를 `NULL` 로 만들어도
`nlr_unmatched_expressions` 의 `expression` 과 `normalized_key` 는 남고, 사전을 키우는
데 필요한 것은 그 둘입니다. 원문은 표본을 눈으로 볼 때 쓰는 것입니다. **보관 기간을
짧게 잡아도 9장의 핵심 질의는 그대로 돕니다.**

`user_id` 는 `ON DELETE SET NULL` 입니다. 탈퇴하면 누구인지는 지워지고 기록은 남습니다.

---

## 11. 담당별로 해야 하는 것

| 담당 | 무엇 |
|---|---|
| **DB** | **`V20` 작성·적용.** 타입·컬럼은 다 정해졌습니다 — 4-2 를 그대로 쓰시면 됩니다 |
| **백엔드** | 네 표에 `INSERT`. `fragranticaId` → `perfume_id` 변환. 클릭·설문 API. **10장 30일 배치** |
| **프론트엔드** | 추천 결과 **클릭 전송** · **만족·보통·불만족 버튼 3개**와 그 선택 전송. 이게 없으면 두 표가 빈 채로 남습니다 |
| **AI** | **응답에 `lexiconVersion` 추가** (6장 ㉠ · 확정). 아래 계약 변경의 AI 쪽 |

### AI 응답에 칸을 더해야 합니다

**지금 AI 응답의 `unmatched` 에는 칸이 4개뿐입니다.**

```
지금 나가는 것   expression · normalizedKey · unmatchReason · entryId
더 필요한 것     llmAccords · llmReasoning · tier · hadConditions · resultCount
                 + lexiconVersion (6장)
```

이건 API 계약 변경이라 AI·백엔드가 같이 움직여야 합니다. AI 쪽
(`_camel_unmatched` 와 `nlr_api_contract.md`)은 합의되면 AI 담당이 고칩니다.

**표를 먼저 만들어도 됩니다.** 합의 전까지 4칸만 채우고 나머지를 `NULL` 로 두면 됩니다.
다만 두 칸이 걸립니다.

```
had_conditions   NOT NULL 이다. 계약에 함께 넣어야 한다.
                 미루시려면 NULL 허용으로 바꾸는 편이 INSERT 를 막지 않는다
lexicon_version  6장. NULL 허용으로 뒀으므로 INSERT 는 되지만 값이 빈다
```

### 마이그레이션이 필요 없는 것도 확인했습니다 [측정]

`user_perfume_views.from_location_type` 에 `'NLR_RECOMMENDATION'` 같은 값을 넣는 데는
**DB 변경이 필요 없습니다.** 제약을 전부 뽑아 보니 `CHECK` 가 하나도 없습니다.

```
user_perfume_views_pkey                 PRIMARY KEY (perfume_view_id)
fk_user_perfume_views_user              FOREIGN KEY (user_id) ...
fk_user_perfume_views_perfume           FOREIGN KEY (perfume_id) ...
fk_user_perfume_views_from_perfume      FOREIGN KEY (from_perfume_id) ...
```

`V10__expand_perfume_view_source_type.sql` 이 이미 넓혀 뒀습니다. **백엔드 enum 만
늘리면 됩니다.**

---

## 12. 크기 [추정]

```
요청 1건당   recommendations 1행 + items 5행 + unmatched 평균 2.18행 + feedbacks 0~1행
            ≈ 8 ~ 9행

하루 1,000 요청 → 약 9,000행/일 → 연 330만 행
```

`perfume_accords` 가 이미 100만 행이므로 부담되는 규모가 아닙니다.

---

## 13. 확인하지 못한 것

- **운영 서버 DB 의 현재 상태** [미확인]. 확인한 것은 `hyanghae-manual-test` 뿐입니다.
  운영에도 `V19` 까지 적용됐는지, `nlr_` 이름 표가 없는지 확인이 필요합니다
- **`V20` 파일로 Flyway 경로를 통과시켜 보지 않았습니다** [미확인]. 4-5 처럼
  트랜잭션에서 실행하고 롤백한 것이 전부입니다. **㉠(앱 기동)은 확인하지 않았습니다** —
  백엔드 이미지를 다시 빌드해야 하고 그것은 이 문서의 범위를 넘습니다.
  DB 는 조사 전후 상태가 같습니다
- **백엔드의 엔티티·리포지토리 구조** [미확인]. 표 이름·컬럼 이름이 팀 컨벤션과 어긋날 수
  있습니다. **이름과 타입은 팀 관례에 맞춰 바꾸셔도 됩니다** — AI 쪽 코드는 이 표들을
  참조하지 않으므로 바꿔도 AI 서버에 영향이 없습니다
- **`TEXT[]` 의 Hibernate 매핑** [미확인]. 이 DB 의 첫 배열 컬럼이라 선례가 없습니다.
  다만 이 표를 JPA 엔티티로 읽을 일이 없고 팀이 로그성 표를 `JdbcClient` 로 다루고 있어
  (7개 파일 · `ExplorationLogRepository` 등) 문제가 되지 않을 것으로 봅니다 [추정]
- **30일 규칙을 누가 돌릴 것인가** [미확인]. 기간은 확정됐지만 **실행 주체가 정해지지
  않았습니다.** 정해지기 전까지는 원문이 계속 쌓입니다 (10장)
- **화면에 보일 문구** [미확인]. DB 값은 `SATISFIED` · `NEUTRAL` · `DISSATISFIED` 로
  정했지만 버튼에 "만족 / 보통 / 불만족" 으로 쓸지 다른 문구로 쓸지는 디자인 결정입니다.
  **문구를 바꿔도 DB 는 안 바뀝니다** (5-4)
- **설문 UI 시점** [미확인]. 추천 직후인지 나중인지에 따라 `nlr_feedbacks` 응답률이
  달라집니다. 응답률은 9장의 `응답수` 로 볼 수 있습니다
- **비로그인 사용자를 받을 것인가** [미확인]. `user_id NULL` 허용으로 뒀지만 기획 결정입니다
- **같은 요청에 다시 답하는 것을 허용할 것인가** [미확인]. 지금 설계는 기본키로 막습니다
- **`perfumes` 를 실제로 지우는 경우** [미확인]. `items.perfume_id` 가
  `ON DELETE CASCADE` 라 향수를 하드 삭제하면 그 추천 기록이 함께 사라집니다.
  `perfumes.is_active` 로 내리는 운영이라면 문제가 없지만 확인하지 못했습니다

---

## 관련 자료

- `docs/plans/NLR_PREDEPLOY_DECISIONS.md` 안건 ② — 만족도·클릭 설계의 출처 (299~523행)
- `docs/plans/NLR_PREDEPLOY_DECISIONS.md` 안건 ③ 후속 — 미매칭 12칸의 출처 (551~646행)
- `delivery/lexicon_v1_14/README.md` 82행 — `lexicon_version` 컬럼을 요구하는 근거
- `docs/plans/NLR_DEPLOY_HANDOFF.md` — AI 서버 배포 조건 (아웃바운드 제한의 근거)
- `docs/plans/NLR_UNMATCHED_LOG_DESIGN.md` — 미매칭 로그 원설계
- `DECISIONS.md` N15 — ⑤단계 미매칭 추정 + 파일 캐시 (파일을 남기는 결정)
- `ai/unmatched_log.py` — 로그 11칸의 실제 구현
- `ai/docs/nlr_api_contract.md` — 응답 형식. 11장의 계약 변경 대상
- `backend/src/main/resources/db/migration/V14__extend_brand_and_perfume_catalog.sql`
  — 마이그레이션 주석 방식의 본보기

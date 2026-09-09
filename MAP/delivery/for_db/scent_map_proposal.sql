-- ==========================================================================
-- 향 지도 테이블 — 제안입니다.
--
-- 그대로 실행하지 마시고 팀 ERD 규약(네이밍 · is_active · 삭제 정책)에 맞게
-- 검토해 주세요. 저희가 아는 것은 "데이터가 이런 모양이다" 까지이고,
-- 어떤 테이블로 담을지는 DB 담당자분이 정하실 일입니다.
--
-- 대상 DB: PostgreSQL (ERD 문서 기준)
-- 이 파일은 실행해 본 적이 없습니다 — 작업 환경에 DB 가 없어 문법 검증을
-- 하지 못했습니다. 타입과 제약이 실제 데이터를 받는지는 파이썬으로 대조했습니다.
-- ==========================================================================


-- --------------------------------------------------------------------------
-- 0. 먼저 확인이 필요한 것 — 이게 없으면 아래가 전부 막힙니다
-- --------------------------------------------------------------------------
-- 저희 데이터는 향수를 Fragrantica 의 id 로 식별합니다. 그런데 현재 ERD 의
-- perfumes 에는 외부 id 컬럼이 없어서, 넘겨드리는 CSV 를 perfumes 행과
-- 이어붙일 방법이 없습니다.
--
-- 컬럼 추가가 어렵다면 매핑 테이블을 따로 두는 방법도 있습니다. 어느 쪽이든
-- 정해 주시면 CSV 를 그 키로 다시 내보내 드립니다.

ALTER TABLE perfumes
    ADD COLUMN fragrantica_id BIGINT,
    ADD CONSTRAINT uk_perfumes_fragrantica UNIQUE (fragrantica_id);


-- --------------------------------------------------------------------------
-- 1. 향 계열 마스터 — 9행
-- --------------------------------------------------------------------------
-- 현재 ERD 의 scent_regions 가 이 역할을 할 수 있는데, 두 가지가 다릅니다.
--   (1) scent_regions 는 min_x/min_y/max_x/max_y 사각형만 담습니다. 저희 영역은
--       폴리곤이라 사각형으로는 모양을 그릴 수 없습니다.
--   (2) scent_regions 가 지금 무엇을 담고 있는지 저희가 알 수 없습니다.
--       user_preference_regions 가 이 테이블을 참조하고 있어서, 기존 행이 있다면
--       의미가 바뀌는 문제가 생깁니다. 확인 부탁드립니다.
--
-- 그래서 별도 테이블을 제안하지만, scent_regions 에 컬럼을 추가하는 쪽이
-- 팀 구조에 맞다면 그래도 됩니다.

CREATE TABLE scent_families (
    family_key            VARCHAR(20)  PRIMARY KEY,   -- CITRUS FRUITY FLORAL GREEN
                                                      -- AQUATIC WOODY AMBER GOURMAND MUSK
    name_ko               VARCHAR(50)  NOT NULL,
    display_order         INTEGER      NOT NULL,
    perfume_count         INTEGER      NOT NULL,
    contributing_perfumes INTEGER      NOT NULL,
    area_share            NUMERIC(6,4) NOT NULL,
    largest_blob_share    NUMERIC(6,4) NOT NULL,
    weighted_coverage     NUMERIC(6,4) NOT NULL,
    anchor_x              DOUBLE PRECISION NOT NULL,  -- 지형 파일의 bounds 공간.
    anchor_y              DOUBLE PRECISION NOT NULL,  -- 음수가 나올 수 있습니다
    polygon               JSONB        NOT NULL,      -- 고리 배열. 고리 1~5개
    is_active             BOOLEAN      NOT NULL DEFAULT TRUE
);

-- family_key 를 PK 로 둔 이유: 저희 파일에는 0~8 정수 id 도 있지만 그건 배열
-- 위치값이라, 계열이 하나 빠지면 나머지 번호가 전부 밀립니다. 문자열 키는
-- 그런 일이 없습니다. display_order 에 그 정수를 넣어 두었습니다.


-- --------------------------------------------------------------------------
-- 2. 향수의 지도 위 좌표 — 200행
-- --------------------------------------------------------------------------
-- ERD 의 perfume_map_points 와 거의 같습니다. 다른 점은 scent_region_id 를
-- NOT NULL 로 하나만 두는 부분입니다 (아래 3번 참고).

CREATE TABLE perfume_map_points (
    perfume_id         BIGINT PRIMARY KEY,
    map_x              DOUBLE PRECISION NOT NULL,
    map_y              DOUBLE PRECISION NOT NULL,
    primary_family_key VARCHAR(20) NOT NULL,   -- 가중치가 가장 큰 계열
    CONSTRAINT fk_map_points_perfume
        FOREIGN KEY (perfume_id) REFERENCES perfumes (perfume_id) ON DELETE CASCADE,
    CONSTRAINT fk_map_points_family
        FOREIGN KEY (primary_family_key) REFERENCES scent_families (family_key)
        ON DELETE RESTRICT,
    CONSTRAINT ck_map_points_xy
        CHECK (map_x BETWEEN 0 AND 1 AND map_y BETWEEN 0 AND 1)
);

-- ck_map_points_xy 는 향수 좌표에만 걸어야 합니다. 계열 폴리곤과 앵커는
-- 여백이 붙은 다른 좌표 공간이라 -0.05 같은 값이 나옵니다.


-- --------------------------------------------------------------------------
-- 3. 향수 ↔ 향 계열 — 303행 (현재 ERD 로는 담을 수 없는 부분)
-- --------------------------------------------------------------------------
-- 향수 하나가 향 계열 여러 개에 걸칩니다. 200개 중 1개 계열이 105개,
-- 2개가 87개, 3개가 8개입니다. 현재 perfume_map_points.scent_region_id 는
-- 영역을 하나만 담을 수 있어서 이 정보가 들어가지 않습니다.

CREATE TABLE perfume_map_families (
    perfume_id BIGINT      NOT NULL,
    family_key VARCHAR(20) NOT NULL,
    weight     NUMERIC(6,4) NOT NULL,   -- 그 향수 안에서 계열이 차지하는 비중
    rank       INTEGER     NOT NULL,    -- 1 = 가장 큰 계열
    PRIMARY KEY (perfume_id, family_key),
    CONSTRAINT fk_map_families_perfume
        FOREIGN KEY (perfume_id) REFERENCES perfumes (perfume_id) ON DELETE CASCADE,
    CONSTRAINT fk_map_families_family
        FOREIGN KEY (family_key) REFERENCES scent_families (family_key) ON DELETE RESTRICT,
    CONSTRAINT ck_map_families_weight CHECK (weight > 0 AND weight <= 1)
);

-- weight 제약을 0.24 이상으로 걸지 마세요. 계열을 뽑는 기준은 0.24 지만
-- 가장 큰 계열은 기준에 못 미쳐도 반드시 넣기 때문에, 실제 최솟값은 0.20 입니다.
-- 0.24 로 걸면 향수 여러 개가 적재에 실패합니다.
--
-- 향수별 weight 합은 1.0 이 아닐 수 있습니다 (0.2 ~ 1.0). 비중을 다시
-- 정규화하지 않았기 때문이고, 1 - 합 은 "나머지 계열" 이라는 뜻이 아닙니다.


-- --------------------------------------------------------------------------
-- 4. 닮은 향수 — 2,000행 (향수당 10개 고정)
-- --------------------------------------------------------------------------
-- ERD 의 perfume_neighbors 에 순위와 유사도 컬럼을 더한 형태입니다.
-- 순서가 의미를 갖기 때문에 rank 없이는 목록이 무의미해집니다.

CREATE TABLE perfume_map_neighbors (
    perfume_id          BIGINT NOT NULL,
    neighbor_perfume_id BIGINT NOT NULL,
    similarity          NUMERIC(6,4) NOT NULL,
    rank                INTEGER NOT NULL,   -- 1 = 가장 닮은
    PRIMARY KEY (perfume_id, neighbor_perfume_id),
    CONSTRAINT fk_map_neighbors_perfume
        FOREIGN KEY (perfume_id) REFERENCES perfumes (perfume_id) ON DELETE CASCADE,
    CONSTRAINT fk_map_neighbors_neighbor
        FOREIGN KEY (neighbor_perfume_id) REFERENCES perfumes (perfume_id) ON DELETE CASCADE,
    CONSTRAINT ck_map_neighbors_not_self CHECK (perfume_id <> neighbor_perfume_id)
);

CREATE INDEX ix_map_neighbors_lookup ON perfume_map_neighbors (perfume_id, rank);

-- 2,000개 이웃이 전부 이 200개 안에 있습니다. 그래서 FK 를 NOT NULL 로 걸어도
-- 안전합니다. 다만 관계가 대칭이 아닙니다 — A 의 이웃 목록에 B 가 있어도
-- B 의 목록에 A 가 없을 수 있습니다 (각자 상위 10개만 담아서 그렇습니다).
--
-- 이 유사도는 향 성분으로 계산한 값이고 지도 위 거리가 아닙니다. 좌표가 전부
-- 바뀌어도 이 목록은 그대로입니다.


-- --------------------------------------------------------------------------
-- 5. 향수의 향 특성 — 1,598행
-- --------------------------------------------------------------------------
-- ERD 에 이미 accords / perfume_accords 가 있고 rank·weight 컬럼도 있어서
-- 그대로 쓰실 수 있습니다. 아래는 참고용입니다.
-- strength 는 0~100 정수입니다 (실측 3~100). 향수당 7개 또는 8개입니다.

-- CREATE TABLE accords (accord_id BIGSERIAL PRIMARY KEY, name VARCHAR(50), ...);
-- CREATE TABLE perfume_accords (perfume_id, accord_id, rank, weight, ...);


-- --------------------------------------------------------------------------
-- 6. 적재 순서
-- --------------------------------------------------------------------------
--   1) accords.csv                (또는 기존 accords 테이블 확인)
--   2) scent_families.csv         9행
--   3) perfumes 에 fragrantica_id 채우기
--   4) perfume_map_points.csv     200행
--   5) perfume_map_families.csv   303행
--   6) perfume_map_neighbors.csv  2,000행
--   7) perfume_map_accords.csv    1,598행
--
-- CSV 는 fragrantica_id 로 되어 있으니 perfumes 와 조인해 perfume_id 로
-- 바꿔 넣으시면 됩니다.
--
-- 지도를 다시 만들면 좌표와 영역이 전부 바뀌므로, 갱신은 행 단위 수정보다
-- 4~7번을 비우고 다시 넣는 쪽이 안전합니다.

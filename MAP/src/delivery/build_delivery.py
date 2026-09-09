"""향 지도 인계 묶음 — DB · BE · FE 에게 넘길 데이터 산출물을 만든다.

**새로 계산하는 것이 하나도 없다.** 검증을 통과한 `experiments/phase6/korea_scent_map_v3.json`
하나만 읽어 형태만 바꾼다. 그래서 의존성이 표준 라이브러리뿐이고, 실험 스크립트가
어떻게 바뀌어도 이 산출물은 영향받지 않는다.

v3 를 만드는 `build_korea_scent_map_v3.py` 는 실험 모듈 5개(family_systems ·
phase0_family_mapping · phase3b_territory · phase3c_blend_sweep · phase5_soft_territory)와
build_map · build_korea_terrain 을 import 하고 numpy/scipy/umap 과 121 MB `perfumes.csv`
가 필요하다. 그 체인은 건드리지 않는다. v3 재생성 절차는 delivery/README.md 에 적는다.

만드는 것::

    delivery/scent_map.json          향수 200 + 계열 9 (군집 7개와 파생 필드 제거)
    delivery/scent_map_terrain.json  격자 2장 + 해안선 (FE 정적 파일)
    delivery/seed/*.csv              DB 적재용 6개 (FK 의존 순)
    delivery/ddl/scent_map_proposal.sql
    delivery/api/example_map_response.json
    delivery/api/scent-map.d.ts

`output/` 과 `results/` 는 읽지도 쓰지도 않는다.

재현::

    venv/Scripts/python.exe src/delivery/build_delivery.py
"""

import csv
import io
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
MAP_DIR = os.path.abspath(os.path.join(HERE, "..", ".."))

V3 = os.path.join("experiments", "phase6", "korea_scent_map_v3.json")
OUT = "delivery"

# 담당자별 폴더. 폴더 하나만 전달해도 그 사람 일이 되도록 필요한 파일을 안에 넣는다.
# 그래서 scent_map.json 이 백엔드·프론트 양쪽에 들어간다 (같은 내용).
DB_DIR = os.path.join(OUT, "for_db")
BE_DIR = os.path.join(OUT, "for_backend")
FE_DIR = os.path.join(OUT, "for_frontend")

# 향수당 계열은 이 임계 이상 + argmax(항상 포함) 로 뽑혀 있다. argmax 예외 때문에
# 실측 최솟값은 임계보다 낮다 — 제약 조건으로 임계를 쓰면 안 된다.
FAMILY_THRESHOLD = 0.24

# v3 에서 빼고 넘기는 것.
#   regions           자동 군집 7개. 한글 이름이 없어 사용자에게 노출할 수 없다 (팀 결정)
#   map_identity_id   "fragrantica:" + fragrantica_id 로 완전히 파생된다
#   display_priority  korea.selection_rank 와 200/200 동일하다
#   display           200개 전부 true 라 정보가 없다
#   region            군집 id. regions 를 빼므로 함께 빠진다
DROP_POINT_FIELDS = ("map_identity_id", "display_priority", "display", "region")


def write_json(path, obj):
    with io.open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
        f.write("\n")
    return os.path.getsize(path)


def write_csv(path, header, rows):
    """UTF-8 BOM 으로 쓴다 — 담당자가 Excel 로 열어볼 가능성이 높다."""
    with io.open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)
    return len(rows)


# --------------------------------------------------------------------------
# 1. 프론트/백엔드가 읽는 JSON 2개
# --------------------------------------------------------------------------
def build_scent_map(d):
    """향수별 데이터 + 계열 마스터. 격자는 여기 없다 (별도 파일)."""
    fam = d["families"]
    items = [{k: v for k, v in it.items() if k != "polygon"} | {"polygon": it["polygon"]}
             for it in fam["items"]]
    points = []
    for p in d["points"]:
        q = {k: v for k, v in p.items() if k not in DROP_POINT_FIELDS}
        # 계열별 name_ko 는 마스터의 복사본이므로 뺀다. key 로 조인한다.
        q["families"] = [{"key": f["key"], "weight": f["weight"]} for f in p["families"]]
        points.append(q)
    return {
        "schema_version": d["schema_version"],
        "dataset_status": d["dataset_status"],
        "generated_at": d["generated_at"],
        "source": d["source"],
        "similarity": d["similarity"],
        "layout": d["layout"],
        "bounds": d["bounds"],
        "terrain_file": "scent_map_terrain.json",
        "families": {
            "status": fam["status"], "system": fam["system"], "count": fam["count"],
            "assignment": fam["assignment"], "territory_rule": fam["territory_rule"],
            "items": items,
        },
        "points": points,
        "notes": {
            "coordinate_spaces": (
                "points[].x,y 와 bounds 는 [0,1] 공간이다. families.items[].polygon 과 "
                "label_anchor 는 scent_map_terrain.json 의 bounds 공간이라 음수가 나올 수 있다."
            ),
            "neighbors": (
                "닮은 향수는 neighbors 를 쓴다. x,y 로 거리를 계산하면 안 된다 "
                "(layout.distance_is_metric: false). 좌표는 200개를 평면에 눌러 담은 것이라 "
                "이웃 관계만 우선 보존한다."
            ),
            "family_weight": (
                "가중치는 그 향수 안에서 계열이 차지하는 비중이고 재정규화하지 않았다. "
                "향수별 합이 1.0 미만일 수 있으므로 1 - 합 을 '기타' 로 읽으면 안 된다."
            ),
            "dropped_from_v3": (
                "자동 군집 7개(regions)와 파생 필드(map_identity_id · display_priority · "
                "display · region)를 뺐다. 계열 9개가 영역의 기준이다."
            ),
        },
    }


def build_terrain(d):
    """지도 배경 — 격자 2장과 해안선. 조회 조건이 없는 래스터라 DB 를 거치지 않는다."""
    t, fam = d["terrain"], d["families"]
    return {
        "schema_version": d["schema_version"],
        "generated_at": d["generated_at"],
        "grid_width": t["grid_width"],
        "grid_height": t["grid_height"],
        "bounds": t["bounds"],
        "row_order": t["row_order"],
        "density": {
            "encoding": t["encoding"], "value_range": t["value_range"],
            "sea_level": t["sea_level"], "sea_level_basis": t["sea_level_basis"],
            "land_area_share": t["land_area_share"], "values": t["values"],
        },
        "family_grid": {
            "encoding": fam["grid_encoding"], "sea_value": 255,
            "values": fam["grid"],
            "id_to_key": [it["key"] for it in fam["items"]],
        },
        "contours": d["contours"],
        "notes": {
            "grid_size": (
                "칸 수는 grid_width * grid_height 로 계산한다. 높이는 좌표에서 파생되는 값이라 "
                "지도를 다시 만들면 바뀐다 (이전 판은 78, 현재 108)."
            ),
            "row_order": (
                "row 0 이 y_min(아래)이다. 화면 y 가 아래로 증가하는 렌더러는 행을 뒤집어야 한다."
            ),
            "sea_value_255": (
                "family_grid 에서 255 는 바다다. density.values 에서 255 는 최대 밀도라는 "
                "정상값이다 — 같은 숫자가 두 격자에서 뜻이 다르다."
            ),
            "polygon_rings": (
                "contours 와 폴리곤의 고리는 닫혀 있지 않을 수 있다 (해안선 4개 중 3개가 열려 "
                "있다). 감기 방향과 구멍 플래그도 없으므로 렌더러가 직접 닫아야 한다."
            ),
            "coordinate_space": "이 파일의 모든 좌표는 위 bounds 공간이고 음수가 나올 수 있다.",
        },
    }


# --------------------------------------------------------------------------
# 2. DB 적재용 CSV 6개
# --------------------------------------------------------------------------
def build_seed(d, seed_dir):
    pts, fam = d["points"], d["families"]["items"]
    counts = {}

    accords = sorted({a["name"] for p in pts for a in p["top_accords"]})
    counts["accords.csv"] = write_csv(
        os.path.join(seed_dir, "accords.csv"), ["accord_name"], [[a] for a in accords])

    counts["scent_families.csv"] = write_csv(
        os.path.join(seed_dir, "scent_families.csv"),
        ["family_key", "name_ko", "display_order", "perfume_count", "contributing_perfumes",
         "area_share", "largest_blob_share", "weighted_coverage",
         "anchor_x", "anchor_y", "polygon_json"],
        [[it["key"], it["name_ko"], it["id"], it["perfume_count_argmax"],
          it["contributing_perfumes"], it["area_share"], it["largest_blob_share"],
          it["weighted_coverage"], it["label_anchor"]["x"], it["label_anchor"]["y"],
          json.dumps(it["polygon"], ensure_ascii=False, separators=(",", ":"))]
         for it in fam])

    counts["perfume_map_points.csv"] = write_csv(
        os.path.join(seed_dir, "perfume_map_points.csv"),
        ["fragrantica_id", "brand", "name", "year", "gender", "map_x", "map_y",
         "primary_family_key", "korea_selection_rank", "korea_selection_basis"],
        [[p["fragrantica_id"], p["brand"], p["name"], p["year"] if p["year"] else "",
          p["gender"], p["x"], p["y"], p["families"][0]["key"],
          p["korea"]["selection_rank"], p["korea"]["selection_basis"]] for p in pts])

    counts["perfume_map_families.csv"] = write_csv(
        os.path.join(seed_dir, "perfume_map_families.csv"),
        ["fragrantica_id", "family_key", "weight", "rank"],
        [[p["fragrantica_id"], f["key"], f["weight"], i + 1]
         for p in pts for i, f in enumerate(p["families"])])

    counts["perfume_map_neighbors.csv"] = write_csv(
        os.path.join(seed_dir, "perfume_map_neighbors.csv"),
        ["fragrantica_id", "neighbor_fragrantica_id", "similarity", "rank"],
        [[p["fragrantica_id"], n["id"], n["sim"], i + 1]
         for p in pts for i, n in enumerate(p["neighbors"])])

    counts["perfume_map_accords.csv"] = write_csv(
        os.path.join(seed_dir, "perfume_map_accords.csv"),
        ["fragrantica_id", "accord_name", "strength", "rank"],
        [[p["fragrantica_id"], a["name"], a["strength"], i + 1]
         for p in pts for i, a in enumerate(p["top_accords"])])
    return counts


# --------------------------------------------------------------------------
# 3. DDL 제안
# --------------------------------------------------------------------------
DDL = """\
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
"""


# --------------------------------------------------------------------------
# 4. API 응답 예시와 타입
# --------------------------------------------------------------------------
def build_api_example(d):
    """지도를 처음 열 때 돌려줄 응답의 모양. 향수는 2개만 넣어 형태만 보여준다."""
    fam = d["families"]["items"]
    pts = d["points"]
    sample = [pts[0], next(p for p in pts if len(p["families"]) == 3)]
    return {
        "_comment": [
            "지도를 처음 열 때(MAP-01) 돌려줄 응답의 예시입니다. 제안이고 형태만 보여줍니다.",
            "points 는 실제로 200개인데 여기서는 2개만 넣었습니다. 하나는 계열 1개,",
            "하나는 계열 3개인 향수입니다.",
            "지도 배경(격자 · 해안선)은 이 응답에 넣지 않고 정적 파일로 내려받게 하는 것을",
            "제안합니다 — 조회 조건이 없고 지도를 다시 만들 때만 바뀌기 때문입니다.",
        ],
        "mapVersion": d["generated_at"],
        "bounds": d["bounds"],
        "terrainUrl": "/static/scent-map/scent_map_terrain.json",
        "families": [
            {"key": it["key"], "nameKo": it["name_ko"], "displayOrder": it["id"],
             "perfumeCount": it["perfume_count_argmax"],
             "anchor": it["label_anchor"],
             "polygon": [["...고리 %d개. 정점 %s개..." % (len(it["polygon"]),
                                                     [len(r) for r in it["polygon"]])]]
             if it["key"] != "FRUITY" else it["polygon"]}
            for it in fam
        ],
        "points": [
            {"perfumeId": 0, "fragranticaId": p["fragrantica_id"],
             "brand": p["brand"], "name": p["name"],
             "x": p["x"], "y": p["y"],
             "families": [{"key": f["key"], "weight": f["weight"]} for f in p["families"]],
             "koreaRank": p["korea"]["selection_rank"]}
            for p in sample
        ],
    }


TYPES = """\
/**
 * 향 지도 데이터 타입 — 제안입니다.
 *
 * 실제 API 응답 모양은 백엔드 담당자분이 정하십니다. 이 파일은 "데이터에 어떤
 * 필드가 어떤 타입으로 들어 있는지" 를 보여드리려고 만든 것이니, 필드 이름이나
 * 구조는 프로젝트 규약에 맞게 바꿔 쓰셔도 됩니다.
 *
 * 값의 범위와 개수는 실제 데이터에서 확인한 것입니다.
 */

/** 향 계열 9개. 이 문자열이 안정적인 키다 (숫자 id 는 배열 위치라 밀릴 수 있다). */
export type FamilyKey =
  | 'CITRUS' | 'FRUITY' | 'FLORAL' | 'GREEN' | 'AQUATIC'
  | 'WOODY' | 'AMBER' | 'GOURMAND' | 'MUSK';

/**
 * 좌표. 두 가지 공간이 섞여 있으니 구분해야 한다.
 *  - 향수 좌표(MapPoint.x, y): 0 ~ 1
 *  - 폴리곤 · 해안선 · 라벨 앵커: 지형 파일의 bounds 공간. 음수가 나온다
 */
export interface Coord { x: number; y: number }

/** 폴리곤은 고리의 배열이다. 고리는 [x, y] 점의 배열. */
export type Ring = [number, number][];
export type Polygon = Ring[];

export interface ScentFamily {
  key: FamilyKey;
  nameKo: string;
  displayOrder: number;      // 0 ~ 8
  perfumeCount: number;      // 이 계열이 1순위인 향수 수. 합 200
  anchor: Coord;             // 라벨을 놓을 위치
  polygon: Polygon;          // 고리 1 ~ 5개
}

export interface PerfumeFamily {
  key: FamilyKey;
  /**
   * 그 향수 안에서 이 계열이 차지하는 비중. 실측 0.20 ~ 0.8224.
   * 향수별 합은 1.0 이 아닐 수 있다 (재정규화하지 않았다).
   * 1 - 합 을 "기타" 로 읽으면 안 된다.
   */
  weight: number;
}

export interface MapPoint {
  fragranticaId: number;
  brand: string;
  name: string;
  x: number;                 // 0 ~ 1
  y: number;                 // 0 ~ 0.83056. bounds 를 읽어 쓰고 하드코딩하지 말 것
  families: PerfumeFamily[]; // 1 ~ 3개. weight 내림차순
  koreaRank: number;         // 1 ~ 200
}

export interface Neighbor {
  fragranticaId: number;
  /** 향 성분으로 계산한 유사도. 지도 위 거리가 아니다. 실측 0.2021 ~ 0.7797 */
  similarity: number;
  rank: number;              // 1 = 가장 닮은
}

export interface Bounds { x_min: number; x_max: number; y_min: number; y_max: number }

export interface ScentMap {
  mapVersion: string;
  bounds: Bounds;
  terrainUrl: string;
  families: ScentFamily[];   // 9개
  points: MapPoint[];        // 200개
}

/** 지도 배경. 정적 파일로 한 번 받아 캐시하면 된다. */
export interface ScentMapTerrain {
  gridWidth: number;         // 128 (상수)
  gridHeight: number;        // 108. 좌표에서 파생되므로 하드코딩하지 말 것
  bounds: Bounds;            // 향수 좌표보다 넓다. 음수 포함
  density: {
    /** gridWidth * gridHeight 개. row 0 이 y_min(아래)이다 */
    values: number[];
    /** 이 값보다 큰 칸이 땅이다 */
    seaLevel: number;
    valueRange: [number, number];   // [0, 255]. 여기서 255 는 최대 밀도지 바다가 아니다
  };
  familyGrid: {
    /** gridWidth * gridHeight 개. 값은 idToKey 의 인덱스, 255 는 바다 */
    values: number[];
    seaValue: 255;
    idToKey: FamilyKey[];
  };
  contours: { level: number; polygons: Polygon }[];
}
"""


README = """\
# 향 지도 인계 묶음

국내 대표 향수 **200개**를 향이 비슷한 것끼리 가까이 놓은 평면 지도입니다.
지도는 시트러스 · 플로럴 · 우디 같은 **향 계열 9개** 구역으로 나뉩니다.

이 폴더는 **밖으로 넘기려고 모아둔 것**이고, 전부 하나의 원본
(`experiments/phase6/korea_scent_map_v3.json`)에서 형태만 바꿔 만들었습니다.

## 표기 규약

문서와 주석에서 두 가지를 구분해 두었습니다.

- **[측정]** — 실제 데이터에서 확인한 값입니다. 여기에 맞지 않게 만들면 데이터가
  들어가지 않으니 그대로 지켜야 합니다.
- **[제안]** — 저희 판단일 뿐입니다. **참고만 하시고 실제 설계는 담당자분이
  정하시면 됩니다.** 그대로 구현하지 않아도 괜찮습니다.

테이블 구성 · DDL · 엔드포인트 모양 · 그리는 순서는 전부 [제안]입니다.

## 누구에게 어느 폴더를 주면 되나

**폴더 하나를 그대로 전달하면 됩니다.** 각 폴더 안에 그 담당자가 필요한 것이 다
들어 있고, 맨 앞에 `README.md` 와 인계 문서 HTML 이 있습니다.

| 담당 | 줄 폴더 | 안에 든 것 |
|---|---|---|
| **DB** | `for_db/` | 인계 문서 · 시드 CSV 6개 · DDL 제안 |
| **백엔드** | `for_backend/` | 인계 문서 · 응답 예시 · 목업용 데이터 |
| **프론트** | `for_frontend/` | 인계 문서 · 지도 데이터 · 지도 배경 · 타입 정의 |

인계 문서는 **단독 HTML** 이라 브라우저로 바로 열립니다. 프론트 문서는 문서 안에서
그 폴더의 파일만으로 지도를 실제로 그려 보여줍니다.

```
for_db/
  README.md
  handoff_db.html
  scent_map_proposal.sql              CREATE / ALTER 제안
  seed/accords.csv                    __N_AC__행   향 특성 이름
  seed/scent_families.csv             __N_FAM__행   향 계열 9개 (이름 · 영역 · 라벨 위치)
  seed/perfume_map_points.csv         __N_PT__행   향수 좌표
  seed/perfume_map_families.csv       __N_PF__행   향수 <-> 계열   <- 지금 ERD 에 없는 표
  seed/perfume_map_neighbors.csv      __N_NB__행   닮은 향수 (향수당 10개)
  seed/perfume_map_accords.csv        __N_PA__행   향수의 향 특성 (향수당 7~8개)

for_backend/
  README.md
  handoff_backend.html
  example_map_response.json           응답 예시
  scent_map.json                      적재 전 목업용

for_frontend/
  README.md
  handoff_frontend.html
  scent_map.json                      향수 200개 + 향 계열 9개
  scent_map_terrain.json              지도 배경 — 런타임 정적 자산
  scent-map.d.ts                      TypeScript 타입

verification.json                     검증 결과 (내부 기록. 전달하지 않아도 된다)
```

`scent_map.json` 이 백엔드·프론트 양쪽에 있습니다. **같은 파일**이고, 폴더 하나만
전달해도 되도록 일부러 넣어 둔 것입니다.

CSV 는 UTF-8(BOM) 이라 Excel 로 바로 열립니다. 향수는 전부 `fragrantica_id` 로
되어 있습니다 — **DB 의 향수 식별 방법이 정해지면 그 키로 다시 내보내 드립니다.**

## 특히 주의할 것 3가지

1. **닮은 향수를 좌표 거리로 계산하면 안 됩니다.** 미리 계산된 목록
   (`neighbors`)이 정답입니다. 좌표는 200개를 평면에 눌러 담은 결과라 가까운
   관계만 우선 보존합니다.
2. **계열 가중치에 `>= 0.24` 제약을 걸면 안 됩니다.** 계열을 뽑는 기준은 0.24
   지만 가장 큰 계열은 기준에 못 미쳐도 반드시 넣기 때문에, 실측 최솟값은
   **0.20** 입니다.
3. **좌표계가 두 개입니다.** 향수 점은 `[0,1]`, 계열 폴리곤 · 해안선 · 라벨
   위치는 여백이 붙은 더 넓은 좌표계라 **음수가 나옵니다.**

## 이 폴더를 다시 만들기

원본 v3 가 이미 있으면 두 줄이면 됩니다. 표준 라이브러리만 씁니다.

```
venv/Scripts/python.exe src/delivery/build_delivery.py
venv/Scripts/python.exe src/delivery/build_handoff_docs.py
venv/Scripts/python.exe src/delivery/verify_delivery.py     # 검증
```

## 원본 v3 자체를 다시 만들기

지도를 다시 생성해야 할 때만 필요합니다. **numpy · scipy · umap-learn 과 원본
데이터 121 MB 가 필요하고, 파생 캐시를 먼저 만들어야 합니다.**

```
1. MAP/perfumes.jsonl (486 MB) 과 MAP/perfumes.csv (121 MB) 를 둔다
   -> perfumes.csv 의 SHA-256 이 cec1ea0b...345cc055 여야 한다 (스크립트가 검사)

2. venv/Scripts/python.exe src/common/prepare_data.py
   -> cache/people.csv · cache/reminds_edges.csv · cache/also_liked_edges.csv

3. ../EDA/analysis_outputs/10_note_dictionary.csv 와 10_accord_dictionary.csv 가
   있어야 한다 (EDA 쪽 산출물이며 MAP 이 만들지 않는다)

4. output/korea_scent_map_v2.json 이 있어야 한다 (향수 200개 집합의 정의)

5. venv/Scripts/python.exe src/map/build_korea_scent_map_v3.py
   -> experiments/phase6/korea_scent_map_v3.json   검증 17개를 통과해야 한다
```

지도를 다시 만들면 **향수 200개의 좌표와 계열 영역이 전부 바뀝니다.** 일부만
바뀌는 일이 없으므로, DB 갱신은 행 단위 수정보다 비우고 다시 넣는 쪽이 안전합니다.

## 아직 정하지 않은 것

- **향수를 무엇으로 식별할지** — DB 담당자 확인 필요. 나머지가 여기 달려 있습니다.
- **`scent_regions` 에 기존 행이 있는지** — 있으면 향 계열 9개를 어디에 둘지 정해야
  합니다.
- **좁은 화면의 계열 이름** — 375px 에서 3개가 가장자리에 걸립니다 (768px 이상은
  9개 전부 정상). 범례로 빼기 / 줌 후 표시 / 짧은 이름 중 미결.
- **향수별 계절 · 시간대 투표** — 데이터는 있는데(200개 중 185 · 181개) 담을 표가
  없어 이번 CSV 에서 뺐습니다.

## 원본의 상태

`korea_scent_map_v3.json` 은 `dataset_status: "DRAFT"` 입니다. 검증 17개를 전부
통과했지만 **아직 프로덕션(`output/`)으로 옮기지 않았습니다** — 프론트가 형태를
확인한 뒤 옮기는 것이 팀 결정이었습니다. 이 폴더의 데이터는 그 초안에서 나온
것입니다.
"""


DB_NOTE = """\
# DB 담당자용 — 향 지도

이 폴더만 있으면 됩니다. **`handoff_db.html` 을 브라우저로 먼저 열어 주세요.**
무엇을 어떤 표에 넣으면 되는지, 넣을 때 걸리기 쉬운 곳이 정리돼 있습니다.

## 이 폴더의 파일

```
handoff_db.html            <- 먼저 읽어 주세요
seed/accords.csv                  __N_AC__행   향 특성 이름
seed/scent_families.csv           __N_FAM__행   향 계열 9개 (이름 · 영역 · 라벨 위치)
seed/perfume_map_points.csv       __N_PT__행   향수 좌표
seed/perfume_map_families.csv     __N_PF__행   향수 <-> 계열   <- 지금 ERD 에 없는 표
seed/perfume_map_neighbors.csv    __N_NB__행   닮은 향수 (향수당 10개)
seed/perfume_map_accords.csv      __N_PA__행   향수의 향 특성 (향수당 7~8개)
scent_map_proposal.sql     CREATE / ALTER 제안 (제안입니다 — 그대로 실행하지 마세요)
```

CSV 는 UTF-8(BOM) 이라 Excel 로 바로 열립니다.

## 지금 확인이 필요한 것

**향수를 무엇으로 식별할지** 정해 주세요. CSV 는 전부 Fragrantica 의 id 로 되어
있는데, 현재 `perfumes` 테이블에는 그걸 담는 컬럼이 없습니다. **다른 키를 쓰기로
하시면 CSV 를 그 키로 다시 만들어 드립니다.**

그리고 `scent_regions` 테이블에 지금 행이 들어 있는지 알려 주세요. 있으면 향 계열
9개를 같은 테이블에 넣을지 새 테이블로 나눌지 정해야 합니다.

## 표기

문서에서 **[측정]** 은 실제 데이터에서 확인한 값이라 그대로 지켜야 하고,
**[제안]** 은 저희 판단일 뿐이니 참고만 하시면 됩니다. 테이블 구성과 DDL 은
전부 제안입니다.
"""

BE_NOTE = """\
# 백엔드 담당자용 — 향 지도

이 폴더만 있으면 됩니다. **`handoff_backend.html` 을 브라우저로 먼저 열어 주세요.**
기능별로 무엇을 조회해 무엇을 돌려주면 되는지 정리돼 있습니다.

## 이 폴더의 파일

```
handoff_backend.html         <- 먼저 읽어 주세요
example_map_response.json    지도를 처음 열 때의 응답 예시
scent_map.json               DB 적재를 기다리지 않고 목업을 띄울 때 쓰세요
```

`scent_map.json` 은 DB 에 들어갈 데이터의 원본입니다. 실제로는 DB 에서 읽으시게
되지만, **적재가 끝나기 전에 먼저 API 를 만들려면** 이 파일을 그대로 내려주는
목업으로 쓸 수 있습니다.

## 특히 주의할 것

1. **닮은 향수를 좌표 거리로 계산하지 마세요.** 미리 계산된 목록이 있습니다.
   좌표는 향수 200개를 평면에 눌러 담은 결과라 가까운 관계만 우선 보존합니다.
2. **계열 가중치의 합을 1.0 으로 가정하지 마세요.** 향수별 합이 0.20 ~ 1.00 입니다.
3. **지도 배경(땅 · 바다 · 색면 · 해안선)은 DB 를 거치지 않는 것을 제안합니다.**
   프론트 담당자에게 정적 파일로 따로 드렸습니다.

## 표기

문서에서 **[측정]** 은 실제 데이터에서 확인한 값이고, **[제안]** 은 저희 판단일
뿐입니다. 엔드포인트 구성과 응답 모양은 전부 제안이니 참고만 하시면 됩니다.
"""

FE_NOTE = """\
# 프론트 담당자용 — 향 지도

이 폴더만 있으면 됩니다. **`handoff_frontend.html` 을 브라우저로 먼저 열어 주세요.**
그리는 순서가 5단계로 정리돼 있고, **문서 안에서 이 폴더의 파일만으로 지도를 실제로
그려 보여줍니다.**

## 이 폴더의 파일

```
handoff_frontend.html      <- 먼저 읽어 주세요 (지도 렌더 예시 포함)
scent_map_terrain.json     지도 배경. 런타임에도 계속 쓰는 정적 자산입니다
scent_map.json             향수 200개 + 향 계열 9개. API 가 준비되기 전 목업용
scent-map.d.ts             TypeScript 타입
```

`scent_map_terrain.json` 은 **백엔드를 거치지 않습니다.** 지도를 다시 만들 때만
바뀌므로 프로젝트의 정적 폴더에 넣고 한 번 받아 캐시하면 됩니다.

## 가장 중요한 것 하나

**"닮은 향수" 를 좌표 거리로 계산하면 안 됩니다.** 향수마다 미리 계산된 목록
(`neighbors`)이 붙어 있으니 그걸 쓰세요.

좌표는 향수 200개를 평면에 눌러 담은 결과입니다. 가까운 것끼리 가깝게 놓는 것은
지켜지지만 **거리 값 자체가 향의 차이를 뜻하지는 않습니다.**

## 그다음 주의할 것

- **좌표계가 두 개입니다.** 향수 점은 0~1, 계열 색면 · 해안선 · 라벨 위치는 여백이
  붙은 더 넓은 좌표계라 음수가 나옵니다.
- **지형 격자는 위아래가 뒤집혀 있습니다.** 첫 행이 아래쪽입니다.
- **폴리곤 고리가 닫혀 있지 않습니다.** 직접 닫아야 합니다.

전부 문서에 단계별로 설명해 두었습니다.

## 표기

문서에서 **[측정]** 은 실제 데이터에서 확인한 값이고, **[제안]** 은 저희 판단일
뿐입니다. 그리는 순서와 색은 제안이니 디자인에 맞게 바꾸시면 됩니다.
"""


def fill(txt, counts):
    for k, name in (("__N_AC__", "accords.csv"), ("__N_FAM__", "scent_families.csv"),
                    ("__N_PT__", "perfume_map_points.csv"),
                    ("__N_PF__", "perfume_map_families.csv"),
                    ("__N_NB__", "perfume_map_neighbors.csv"),
                    ("__N_PA__", "perfume_map_accords.csv")):
        txt = txt.replace(k, f"{counts[name]:>5}")
    return txt


def write_text(path, txt):
    io.open(path, "w", encoding="utf-8", newline="\n").write(txt)
    return os.path.getsize(path)


def main() -> None:
    os.chdir(MAP_DIR)
    d = json.load(io.open(V3, encoding="utf-8"))
    assert d["schema_version"] == 3 and len(d["points"]) == 200, "v3 가 아니다"

    for p in (os.path.join(DB_DIR, "seed"), BE_DIR, FE_DIR):
        os.makedirs(p, exist_ok=True)

    print("=" * 74)
    print("향 지도 인계 묶음 생성 — v3 를 읽어 형태만 바꾼다 (재계산 없음)")
    print("=" * 74)
    print(f"입력  {V3}  ({os.path.getsize(V3) / 1024:.0f} KB)")
    print(f"      향수 {len(d['points'])}개 · 계열 {d['families']['count']}개 · "
          f"격자 {d['terrain']['grid_width']}x{d['terrain']['grid_height']}")
    print()

    counts = build_seed(d, os.path.join(DB_DIR, "seed"))
    ddl = write_text(os.path.join(DB_DIR, "scent_map_proposal.sql"), DDL)
    print("for_db/")
    for name, n in counts.items():
        print(f"  seed/{name:<30} {n:>6} 행")
    print(f"  scent_map_proposal.sql           {ddl / 1024:>6.0f} KB")
    print()

    # scent_map.json 은 BE(목업용)와 FE(목업용) 양쪽이 쓴다. 같은 내용을 각 폴더에
    # 넣어 폴더 하나만 전달해도 되게 한다.
    smap = build_scent_map(d)
    b_be = write_json(os.path.join(BE_DIR, "scent_map.json"), smap)
    ex = write_json(os.path.join(BE_DIR, "example_map_response.json"),
                    build_api_example(d))
    print("for_backend/")
    print(f"  scent_map.json                   {b_be / 1024:>6.0f} KB   향수 200 + 계열 9")
    print(f"  example_map_response.json        {ex / 1024:>6.0f} KB   응답 예시")
    print()

    b_fe = write_json(os.path.join(FE_DIR, "scent_map.json"), smap)
    ter = write_json(os.path.join(FE_DIR, "scent_map_terrain.json"), build_terrain(d))
    ts = write_text(os.path.join(FE_DIR, "scent-map.d.ts"), TYPES)
    print("for_frontend/")
    print(f"  scent_map.json                   {b_fe / 1024:>6.0f} KB   향수 200 + 계열 9")
    print(f"  scent_map_terrain.json           {ter / 1024:>6.0f} KB   격자 2장 + 해안선")
    print(f"  scent-map.d.ts                   {ts / 1024:>6.0f} KB   타입 정의")
    print()

    write_text(os.path.join(DB_DIR, "README.md"), fill(DB_NOTE, counts))
    write_text(os.path.join(BE_DIR, "README.md"), BE_NOTE)
    write_text(os.path.join(FE_DIR, "README.md"), FE_NOTE)
    idx = write_text(os.path.join(OUT, "README.md"), fill(README, counts))
    print(f"  폴더별 README.md 3개 · delivery/README.md ({idx / 1024:.0f} KB)")
    print()
    print("인계 문서 HTML 은 build_handoff_docs.py 가 각 폴더에 넣는다.")
    print("output/ 과 results/ 는 읽지도 쓰지도 않았다.")


if __name__ == "__main__":
    main()

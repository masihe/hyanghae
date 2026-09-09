"""인계 묶음 검증 — 산출물이 v3 와 정말 같은지, 보호 파일이 그대로인지 확인한다.

`build_delivery.py` 가 v3 를 읽어 형태만 바꾸므로, 검증도 "산출물 ↔ v3 대조" 로 끝난다.
따로 계산하지 않고 값을 되돌려 맞춘다.

**기존 스크립트의 검증 하나를 여기서 제대로 한다.** `build_korea_scent_map_v3.py:393`
의 17번 검증은 `v2b.sha256(V2_PATH) == v2b.sha256(V2_PATH)` 로 같은 경로를 두 번
해싱해 비교하므로 항상 통과하고 아무것도 검증하지 않는다. 여기서는 기록된 해시
상수와 대조한다. 기존 파일은 손대지 않았다.

재현::

    venv/Scripts/python.exe src/delivery/verify_delivery.py
"""

import csv
import hashlib
import io
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
MAP_DIR = os.path.abspath(os.path.join(HERE, "..", ".."))

V3 = os.path.join("experiments", "phase6", "korea_scent_map_v3.json")
V2 = os.path.join("output", "korea_scent_map_v2.json")
OUT = "delivery"
DB_DIR = os.path.join(OUT, "for_db")
BE_DIR = os.path.join(OUT, "for_backend")
FE_DIR = os.path.join(OUT, "for_frontend")

# 2026-09-09 에 기록. 이 값이 달라지면 v2 가 수정됐다는 뜻이다.
V2_SHA256 = "9dee6b6b5794e2ae97ba917d094312e91a5d6075a19755da40e00c7953e54cdb"

FAMILY_KEYS = {"CITRUS", "FRUITY", "FLORAL", "GREEN", "AQUATIC",
               "WOODY", "AMBER", "GOURMAND", "MUSK"}

# 제안 DDL 이 선언한 제약. 실제 데이터가 이 안에 들어가는지 대조한다.
# (Postgres 문법 자체는 실행하지 않는다 — 이 작업 환경에 DB 가 없다.)
DDL_SPEC = {
    "scent_families.csv": {
        "family_key": ("varchar", 20), "name_ko": ("varchar", 50),
        "area_share": ("numeric", 6, 4), "largest_blob_share": ("numeric", 6, 4),
        "weighted_coverage": ("numeric", 6, 4),
    },
    "perfume_map_points.csv": {
        "primary_family_key": ("varchar", 20),
    },
    "perfume_map_families.csv": {
        "family_key": ("varchar", 20), "weight": ("numeric", 6, 4),
    },
    "perfume_map_neighbors.csv": {
        "similarity": ("numeric", 6, 4),
    },
    "accords.csv": {"accord_name": ("varchar", 50)},
    "perfume_map_accords.csv": {"accord_name": ("varchar", 50)},
}

RESULTS = []


def chk(name, ok, detail=""):
    RESULTS.append({"check": name, "ok": bool(ok), "detail": detail})


def sha256(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def read_seed(name):
    with io.open(os.path.join(DB_DIR, "seed", name), encoding="utf-8-sig",
                 newline="") as f:
        return list(csv.DictReader(f))


def fits_numeric(text, precision, scale):
    """NUMERIC(p,s) 가 이 값을 받을 수 있는지."""
    if text == "":
        return True
    s = text.lstrip("-")
    whole, _, frac = s.partition(".")
    return len(frac) <= scale and len(whole.lstrip("0") or "0") <= precision - scale


def main() -> None:
    os.chdir(MAP_DIR)
    v3 = json.load(io.open(V3, encoding="utf-8"))
    sm = json.load(io.open(os.path.join(FE_DIR, "scent_map.json"), encoding="utf-8"))
    tr = json.load(io.open(os.path.join(FE_DIR, "scent_map_terrain.json"),
                           encoding="utf-8"))

    pts3 = {p["fragrantica_id"]: p for p in v3["points"]}
    fam3 = {it["key"]: it for it in v3["families"]["items"]}

    print("=" * 74)
    print("인계 묶음 검증")
    print("=" * 74)

    # ---- 1. 행 수 ----
    seeds = {n: read_seed(n) for n in (
        "accords.csv", "scent_families.csv", "perfume_map_points.csv",
        "perfume_map_families.csv", "perfume_map_neighbors.csv",
        "perfume_map_accords.csv")}
    expect = {
        "accords.csv": len({a["name"] for p in v3["points"] for a in p["top_accords"]}),
        "scent_families.csv": v3["families"]["count"],
        "perfume_map_points.csv": len(v3["points"]),
        "perfume_map_families.csv": sum(len(p["families"]) for p in v3["points"]),
        "perfume_map_neighbors.csv": sum(len(p["neighbors"]) for p in v3["points"]),
        "perfume_map_accords.csv": sum(len(p["top_accords"]) for p in v3["points"]),
    }
    for n, rows in seeds.items():
        chk(f"행 수 {n}", len(rows) == expect[n], f"{len(rows)} == {expect[n]}")

    # ---- 2. 값 왕복 — 좌표 ----
    bad = [r["fragrantica_id"] for r in seeds["perfume_map_points.csv"]
           if (float(r["map_x"]), float(r["map_y"]))
           != (pts3[int(r["fragrantica_id"])]["x"], pts3[int(r["fragrantica_id"])]["y"])]
    chk("좌표가 v3 와 동일", not bad, f"불일치 {len(bad)}개")

    # ---- 3. 값 왕복 — 계열 소속 ----
    mism = []
    for r in seeds["perfume_map_families.csv"]:
        src = pts3[int(r["fragrantica_id"])]["families"][int(r["rank"]) - 1]
        if src["key"] != r["family_key"] or src["weight"] != float(r["weight"]):
            mism.append(r["fragrantica_id"])
    chk("계열 소속·가중치가 v3 와 동일", not mism, f"불일치 {len(mism)}개")

    # ---- 4. 값 왕복 — 이웃 ----
    mism = []
    for r in seeds["perfume_map_neighbors.csv"]:
        src = pts3[int(r["fragrantica_id"])]["neighbors"][int(r["rank"]) - 1]
        if src["id"] != int(r["neighbor_fragrantica_id"]) \
                or src["sim"] != float(r["similarity"]):
            mism.append(r["fragrantica_id"])
    chk("이웃·유사도가 v3 와 동일", not mism, f"불일치 {len(mism)}개")

    # ---- 5. 값 왕복 — accord ----
    mism = []
    for r in seeds["perfume_map_accords.csv"]:
        src = pts3[int(r["fragrantica_id"])]["top_accords"][int(r["rank"]) - 1]
        if src["name"] != r["accord_name"] or src["strength"] != int(r["strength"]):
            mism.append(r["fragrantica_id"])
    chk("accord·세기가 v3 와 동일", not mism, f"불일치 {len(mism)}개")

    # ---- 6. 값 왕복 — 계열 마스터 폴리곤 ----
    mism = [r["family_key"] for r in seeds["scent_families.csv"]
            if json.loads(r["polygon_json"]) != fam3[r["family_key"]]["polygon"]]
    chk("계열 폴리곤이 v3 와 동일", not mism, f"불일치 {len(mism)}개")

    # ---- 7. 좌표 범위 ----
    xs = [p["x"] for p in sm["points"]]
    ys = [p["y"] for p in sm["points"]]
    chk("향수 좌표가 [0,1] 안", min(xs) >= 0 and max(xs) <= 1
        and min(ys) >= 0 and max(ys) <= 1,
        f"x {min(xs)}~{max(xs)} · y {min(ys)}~{max(ys)}")

    # 폴리곤·앵커는 여백이 붙은 다른 공간이라 음수가 나온다. 그 사실을 확인해 둔다.
    ring_y = [pt[1] for it in sm["families"]["items"] for r in it["polygon"] for pt in r]
    chk("폴리곤은 지형 bounds 공간 (음수 존재)", min(ring_y) < 0,
        f"최소 y {min(ring_y)} — 향수 좌표와 다른 공간이다")

    # ---- 8. 가중치 규칙 ----
    ws = [float(r["weight"]) for r in seeds["perfume_map_families.csv"]]
    chk("가중치 > 0", min(ws) > 0, f"최소 {min(ws)}")
    chk("가중치 최솟값이 임계 0.24 미만 (argmax 예외)", min(ws) < 0.24,
        f"최소 {min(ws)} — DDL 에 weight >= 0.24 를 걸면 안 되는 이유")
    sums = {}
    for r in seeds["perfume_map_families.csv"]:
        sums[r["fragrantica_id"]] = sums.get(r["fragrantica_id"], 0) + float(r["weight"])
    chk("향수별 가중치 합 <= 1.0001", max(sums.values()) <= 1.0001,
        f"최대 {max(sums.values()):.4f} · 최소 {min(sums.values()):.4f}")

    # ---- 9. rank 1 이 항상 가장 큰 계열 ----
    bad = []
    for p in v3["points"]:
        top = max(p["families"], key=lambda f: f["weight"])
        if p["families"][0]["key"] != top["key"]:
            bad.append(p["fragrantica_id"])
    chk("rank 1 이 항상 가중치 최대 계열", not bad, f"위반 {len(bad)}개")

    # ---- 10. 격자 길이 ----
    n = tr["grid_width"] * tr["grid_height"]
    chk("밀도 격자 길이 = 폭 x 높이", len(tr["density"]["values"]) == n,
        f"{len(tr['density']['values'])} == {tr['grid_width']}x{tr['grid_height']} = {n}")
    chk("계열 격자 길이 = 폭 x 높이", len(tr["family_grid"]["values"]) == n, "")
    chk("격자 2장이 v3 와 동일",
        tr["density"]["values"] == v3["terrain"]["values"]
        and tr["family_grid"]["values"] == v3["families"]["grid"], "")

    # ---- 11. 참조 정합성 ----
    ids = {p["fragrantica_id"] for p in v3["points"]}
    nb = {int(r["neighbor_fragrantica_id"]) for r in seeds["perfume_map_neighbors.csv"]}
    chk("모든 이웃 id 가 200개 안에 있다", nb <= ids,
        f"바깥 {len(nb - ids)}개 — NOT NULL FK 안전")
    fk = {r["family_key"] for r in seeds["perfume_map_families.csv"]} \
        | {r["primary_family_key"] for r in seeds["perfume_map_points.csv"]} \
        | {r["family_key"] for r in seeds["scent_families.csv"]}
    chk("모든 계열 키가 9개 enum 안에 있다", fk == FAMILY_KEYS, f"{len(fk)}종")
    am = {r["accord_name"] for r in seeds["accords.csv"]}
    au = {r["accord_name"] for r in seeds["perfume_map_accords.csv"]}
    chk("모든 accord 가 마스터에 있다", au <= am, f"마스터 밖 {len(au - am)}개")
    fid = {int(r["fragrantica_id"]) for r in seeds["perfume_map_points.csv"]}
    chk("자식 CSV 의 향수 id 가 전부 부모에 있다",
        all({int(r["fragrantica_id"]) for r in seeds[k]} <= fid
            for k in ("perfume_map_families.csv", "perfume_map_neighbors.csv",
                      "perfume_map_accords.csv")), "")

    # ---- 12. 자기 자신을 이웃으로 갖지 않는다 (DDL CHECK) ----
    self_edge = [r for r in seeds["perfume_map_neighbors.csv"]
                 if r["fragrantica_id"] == r["neighbor_fragrantica_id"]]
    chk("이웃에 자기 자신이 없다", not self_edge, f"{len(self_edge)}건")

    # ---- 13. 제안 DDL 의 타입·길이 제약이 실제 데이터를 받는가 ----
    over = []
    for name, spec in DDL_SPEC.items():
        for r in seeds[name]:
            for col, t in spec.items():
                v = r[col]
                if t[0] == "varchar" and len(v) > t[1]:
                    over.append(f"{name}.{col} {len(v)}자 > VARCHAR({t[1]})")
                elif t[0] == "numeric" and not fits_numeric(v, t[1], t[2]):
                    over.append(f"{name}.{col} {v} > NUMERIC({t[1]},{t[2]})")
    chk("제안 DDL 의 타입·길이가 실제 값을 받는다", not over,
        "; ".join(sorted(set(over))[:3]) or "위반 0건 (Postgres 문법은 미실행)")

    # ---- 14. 인계 묶음에서 빼기로 한 것이 실제로 빠졌는가 ----
    chk("군집 7개(regions)가 빠졌다", "regions" not in sm, "")
    chk("파생 필드가 빠졌다",
        all(k not in sm["points"][0]
            for k in ("map_identity_id", "display_priority", "display", "region")), "")
    chk("계열별 name_ko 중복이 빠졌다",
        all("name_ko" not in f for p in sm["points"] for f in p["families"]),
        "마스터에서 key 로 조인한다")

    # ---- 15. 담당자별 폴더가 갖춰졌는가 ----
    want = {
        DB_DIR: ["README.md", "handoff_db.html", "scent_map_proposal.sql",
                 os.path.join("seed", "accords.csv"),
                 os.path.join("seed", "scent_families.csv"),
                 os.path.join("seed", "perfume_map_points.csv"),
                 os.path.join("seed", "perfume_map_families.csv"),
                 os.path.join("seed", "perfume_map_neighbors.csv"),
                 os.path.join("seed", "perfume_map_accords.csv")],
        BE_DIR: ["README.md", "handoff_backend.html", "example_map_response.json",
                 "scent_map.json"],
        FE_DIR: ["README.md", "handoff_frontend.html", "scent_map.json",
                 "scent_map_terrain.json", "scent-map.d.ts"],
    }
    for d0, files in want.items():
        miss = [f for f in files if not os.path.exists(os.path.join(d0, f))]
        chk(f"{os.path.basename(d0)}/ 파일 {len(files)}개", not miss,
            f"없음 {miss}" if miss else "")
    chk("백엔드·프론트의 scent_map.json 이 같은 파일",
        sha256(os.path.join(BE_DIR, "scent_map.json"))
        == sha256(os.path.join(FE_DIR, "scent_map.json")), "")

    # ---- 16. 보호 파일 불변 ----
    chk("v2 파일 불변 (기록된 해시와 대조)", sha256(V2) == V2_SHA256,
        f"{sha256(V2)[:16]}...")
    base = os.path.join(HERE, "protected_baseline.json")
    if os.path.exists(base):
        want = json.load(io.open(base, encoding="utf-8"))
        now = {p: sha256(p) for p in want}
        diff = [p for p in want if want[p] != now[p]]
        chk(f"보호 파일 {len(want)}개 불변", not diff,
            f"변경 {len(diff)}개" + (f" — {diff[:2]}" if diff else ""))
    else:
        rec = {}
        for d0 in ("output", "results", os.path.join("data", "korea_popularity",
                                                     "evaluation")):
            for f in sorted(os.listdir(d0)):
                p = os.path.join(d0, f)
                if os.path.isfile(p):
                    rec[p] = sha256(p)
        json.dump(rec, io.open(base, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        chk(f"보호 파일 {len(rec)}개 기준 해시 기록", True, "다음 실행부터 대조한다")

    # ---- 출력 ----
    for r in RESULTS:
        mark = "PASS" if r["ok"] else "FAIL"
        print(f"  [{mark}] {r['check']}" + (f"  —  {r['detail']}" if r["detail"] else ""))
    ok = sum(1 for r in RESULTS if r["ok"])
    print()
    print(f"{ok} / {len(RESULTS)} 통과")
    json.dump({"pass": ok, "total": len(RESULTS), "checks": RESULTS},
              io.open(os.path.join(OUT, "verification.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    if ok != len(RESULTS):
        raise SystemExit("검증 실패 — 인계 묶음을 넘기지 말 것")


if __name__ == "__main__":
    main()

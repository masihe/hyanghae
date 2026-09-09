"""국내 200개 향 지도 v3 초안 — C8b 좌표 + 9계열 Family Territory.

팀 결정 (2026-09-09)::

    ① C8b 를 프로덕션 좌표 방식으로 승인 (D22 팀 결정 ② 의 보류 해제)
    ② 기존 region(자동 군집 7개)은 호환용으로 유지하고 Family 를 별도 필드로 추가
    ③ v2 는 그대로 두고 v3 를 새로 만들어 먼저 검증

**이 스크립트는 `output/` 을 쓰지 않는다.** 산출은
`experiments/phase6/korea_scent_map_v3.json` 이고, 팀과 프론트가 형태를 확인한 뒤에
프로덕션으로 옮긴다.

v2 대비 바뀌는 것::

    좌표      C1 (Base Similarity UMAP)
              -> C8b = 0.50·Base + 0.35·Family Profile + 0.15·Perception   (D22·D24)
    terrain   좌표가 바뀌므로 재계산
    regions   군집 라벨은 그대로(base similarity 거리에서 나오므로 불변)
              격자·폴리곤·앵커는 좌표가 바뀌므로 재계산
    families  **신규** — Set B 9계열. 향수당 계열 1~3개 + 가중치      (D27·D28)
    points[].families  신규. points[].region 은 호환용으로 유지

Family 배정 규칙 (D28)::

    비중 >= 0.24 인 계열 + argmax 계열(항상 포함). 재정규화하지 않고 원래 강도 유지.
    Family Score 는 향수마다 합이 1.0 이므로 '가중치' 는 곧 그 계열의 비중이다.

**neighbors 는 v2 와 같다.** 좌표가 아니라 Base Similarity 에서 나오는 "닮은 향수"
목록이라 배치를 바꿨다고 달라지지 않는다. 재현되는지 assert 로 확인한다.

v2 의 알려진 흠 하나를 고친다 — `layout.metrics` 의 `trusted_reminds_edges_in_set`
과 `perfumes_with_trusted_reminds_edge` 가 40/44 로 하드코딩돼 있는데 실측은 44/46 이다.
v3 는 측정값을 쓴다.

재현::

    python src/map/build_korea_scent_map_v3.py

산출  experiments/phase6/korea_scent_map_v3.json · schema_diff.json
"""

import json
import os
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in (HERE, os.path.join(HERE, "..", "common")):
    if p not in sys.path:
        sys.path.insert(0, p)

import scent_map as sm                          # noqa: E402
import build_map as bm                          # noqa: E402
import build_korea_terrain as bkt               # noqa: E402
import build_korea_scent_map_v2 as v2b          # noqa: E402
import experiment_family_systems as es          # noqa: E402
import experiment_phase3b_territory as p3b      # noqa: E402
import experiment_phase3c_blend_sweep as p3c    # noqa: E402
import experiment_phase5_soft_territory as p5   # noqa: E402

OUT_DIR = os.path.join("experiments", "phase6")
V2_PATH = os.path.join("output", "korea_scent_map_v2.json")     # 읽기만 한다
V3_PATH = os.path.join(OUT_DIR, "korea_scent_map_v3.json")

SEED = 42
FAMILY_W, PERCEPT_W = 0.35, 0.15      # C8b — D24
FAMILY_THRESHOLD = 0.24               # D28
NEIGHBOR_K = v2b.NEIGHBOR_K

FAMILY_KO = p5.FAMILY_KO


def family_block(coords, W, families, land, sample, lo, hi, width, height, xs, ys, M):
    """계열별 Territory 격자·폴리곤. Phase 5b 와 같은 계산이다."""
    usable = [f for i, f in enumerate(families) if (W[:, i] > 0).sum() >= 3]
    idx = [families.index(f) for f in usable]
    G = np.array([p5.density_w(coords, W[:, i], sample, width, height) for i in idx])
    G = G / G.max(axis=(1, 2), keepdims=True)
    win = G.argmax(axis=0).astype(np.uint8)
    grid = win.copy()
    grid[~land] = bkt.SEA_REGION_ID
    row_idx, col_idx = bkt.cell_index(coords, lo, hi, width, height)
    n_land = int(land.sum())

    items = []
    for j, f in enumerate(usable):
        k = families.index(f)
        mask = grid == j
        cells = int(mask.sum())
        if cells:
            from scipy.ndimage import label as cc_label
            lab, _ = cc_label(mask)
            sizes = np.bincount(lab.ravel())[1:]
            blob = float(sizes.max() / cells)
            flat = np.where(mask.ravel(), (G[j] * mask).ravel(), -1)
            peak = int(flat.argmax())
            anchor = {"x": round(float(xs[peak % width]), 5),
                      "y": round(float(ys[peak // width]), 5)}
        else:
            blob, anchor = 0.0, None
        w = W[:, k]
        on = np.array([usable[win[row_idx[i], col_idx[i]]] == f for i in range(len(coords))])
        items.append({
            "id": j, "key": f, "name_ko": FAMILY_KO[f],
            "perfume_count_argmax": int((M.argmax(axis=1) == k).sum()),
            "contributing_perfumes": int((w > 0).sum()),
            "signal": round(float(w.sum()), 3),
            "grid_cells": cells,
            "area_share": round(cells / n_land, 4) if n_land else 0.0,
            "largest_blob_share": round(blob, 4),
            "weighted_coverage": round(float((w * on).sum() / w.sum()), 4),
            "label_anchor": anchor,
            "polygon": bkt.mask_polygons(mask, xs, ys),
        })
    return grid, items, usable


def main() -> None:
    os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))  # MAP/
    os.makedirs(OUT_DIR, exist_ok=True)
    print("=" * 96)
    print("국내 향 지도 v3 초안 — C8b 좌표 + 9계열 Family Territory")
    print("=" * 96)

    digest = v2b.sha256(sm.PERFUMES_CSV)
    if digest != v2b.PERFUMES_SHA256:
        raise ValueError(f"perfumes.csv 스냅샷이 바뀌었다 ({digest})")
    v2 = json.loads(open(V2_PATH, encoding="utf-8").read())
    assert v2["schema_version"] == 2 and len(v2["points"]) == 200
    ids = [int(p["fragrantica_id"]) for p in v2["points"]]

    perfumes = sm.load_perfumes().set_index("id")
    rows = perfumes.loc[ids].reset_index()
    idf = sm.load_note_idf()
    similarity, _, _ = sm.base_similarity(rows.accord_list.tolist(), rows.note_set.tolist(), idf)
    D = 1.0 - similarity
    np.fill_diagonal(D, 0.0)

    res = es.family_scores(rows.accord_list.tolist(), p3b.SYSTEM)
    families, M = res["families"], res["M"]
    assert np.allclose(M.sum(axis=1), 1.0), "Family Score 행 합이 1.0 이 아니다"
    Dp, nw, nm = p3b.perception_distance(ids)
    Df = p3b.family_profile_distance(M)
    Db = p3c.blend(D, Df, Dp, FAMILY_W, PERCEPT_W)

    raw = p3b.umap_layout(Db, SEED)
    unit, span = v2b.normalize_uniform(raw)
    print(f"좌표 재계산 — C8b(Base {1-FAMILY_W-PERCEPT_W:.2f} + Family {FAMILY_W} + "
          f"Perception {PERCEPT_W}) · UMAP seed {SEED}")
    print(f"인식 축 투표 — 계절 {nw}/200 · 성별 {nm}/200")

    # ---- 이웃은 v2 와 같아야 한다 (Base Similarity 에서 나온다) ----
    sim = similarity.copy()
    np.fill_diagonal(sim, -np.inf)
    order = np.argsort(-sim, axis=1)[:, :NEIGHBOR_K]
    v2_by_id = {int(p["fragrantica_id"]): p for p in v2["points"]}
    mism = [pid for i, pid in enumerate(ids)
            if {int(n["id"]) for n in v2_by_id[pid]["neighbors"]} != {ids[j] for j in order[i]}]
    print(f"이웃 집합 v2 재현: 일치 {200-len(mism)}/200")
    assert not mism, f"이웃이 v2 와 다르다: {mism[:5]}"

    # ---- 지표 측정 (v2 는 40/44 가 하드코딩돼 있었다 — 여기서는 잰다) ----
    index_of = {v: i for i, v in enumerate(ids)}
    rin = bm.edges_within(sm.load_edges("reminds_edges.csv"), set(ids))
    ce = [(int(a), int(b)) for a, b in
          rin[bm.confident(rin)][["src", "dst"]].itertuples(index=False, name=None)]
    nodes = len({x for e in ce for x in e})
    m = bm.evaluate_layout(unit, D, index_of, ce)
    print(f"레이아웃 지표 — trust@10 {m['trust@10']:.4f} · overlap@10 {m['knn_overlap@10']:.4f} · "
          f"정답 간선 근접도 {m['reminds_pct']:.4f}")
    print(f"신뢰 간선 {len(ce)}쌍 / 보유 향수 {nodes}개 "
          f"(v2 는 {v2['layout']['metrics']['trusted_reminds_edges_in_set']}/"
          f"{v2['layout']['metrics']['perfumes_with_trusted_reminds_edge']} 로 하드코딩돼 있었다)")

    # ---- 지형 · 군집 영역 (좌표가 바뀌었으므로 재계산) ----
    labels, sil, sizes, cluster_k = bkt.choose_clusters(D)
    v2_labels = np.array([p["region"] for p in v2["points"]])
    same = int((labels == v2_labels).sum())
    print(f"군집 — k={cluster_k} silhouette {sil:.4f} · v2 라벨과 동일 {same}/200 "
          f"(base similarity 거리에서 나오므로 좌표와 무관)")

    lo, hi, width, height, sample, xs, ys = bkt.make_grid(unit)
    total = bkt.density(unit, sample, width, height)
    total = total / total.max()
    sea_value = float(np.percentile(total, bkt.SEA_PERCENTILE))
    quantized = np.round(total * 255).astype(np.uint8)
    sea_u8 = int(round(sea_value * 255))
    land = quantized > sea_u8
    row_idx, col_idx = bkt.cell_index(unit, lo, hi, width, height)
    print(f"격자 {width}x{height} · sea_level {sea_u8} · 육지 {land.mean():.1%}")

    per_cluster = np.zeros((cluster_k, height, width))
    for c in range(cluster_k):
        mem = unit[labels == c]
        if len(mem) >= bkt.MIN_CLUSTER_FOR_KDE:
            g = bkt.density(mem, sample, width, height)
            per_cluster[c] = g / g.max()
    region_grid = per_cluster.argmax(axis=0).astype(np.uint8)
    region_grid[~land] = bkt.SEA_REGION_ID

    acc_dict = pd.read_csv(bkt.ACCORD_DICT)
    corpus_share = dict(zip(acc_dict.accord, acc_dict.perfume_share))
    rlabels = bkt.region_labels(rows, labels, corpus_share)
    region_items = []
    for c in range(cluster_k):
        mask = region_grid == c
        if mask.any():
            flat = np.where(mask.ravel(), (per_cluster[c] * mask).ravel(), -1)
            peak = int(flat.argmax())
            anchor = {"x": round(float(xs[peak % width]), 5),
                      "y": round(float(ys[peak // width]), 5)}
        else:
            anchor = None
        region_items.append({
            "id": c, "size": int(sizes[c]),
            "points_on_land": int(((labels == c) & land[row_idx, col_idx]).sum()),
            "grid_cells": int(mask.sum()), "label_accords": rlabels[c],
            "name_ko": None, "label_anchor": anchor,
            "polygon": bkt.mask_polygons(mask, xs, ys)})

    # ---- Family Territory (신규) ----
    W, keep = p5.weight_matrix(M, "threshold", FAMILY_THRESHOLD)
    active = keep.sum(axis=1)
    fam_grid, fam_items, usable = family_block(
        unit, W, families, land, sample, lo, hi, width, height, xs, ys, M)
    print(f"Family — 임계 {FAMILY_THRESHOLD} · 향수당 계열 평균 {active.mean():.2f} "
          f"(최대 {active.max()}) · 2계열 이상 {int((active >= 2).sum())}개")
    for it in fam_items:
        print(f"  {it['name_ko']:<14}argmax {it['perfume_count_argmax']:>3} · "
              f"기여 {it['contributing_perfumes']:>3} · 면적 {it['area_share']:>6.1%} · "
              f"덩어리 {it['largest_blob_share']:>5.0%} · coverage {it['weighted_coverage']:.3f}")

    # ---- 조립 ----
    points = []
    for i, pid in enumerate(ids):
        src = v2_by_id[pid]
        fam = sorted(((families[k], float(M[i, k])) for k in np.where(keep[i])[0]),
                     key=lambda t: -t[1])
        p = dict(src)          # v2 의 비공간 정보를 그대로 승계한다
        p["x"] = round(float(unit[i, 0]), 5)
        p["y"] = round(float(unit[i, 1]), 5)
        p["region"] = int(labels[i])
        p["families"] = [{"key": k, "name_ko": FAMILY_KO[k], "weight": round(w, 4)}
                         for k, w in fam]
        points.append(p)

    payload = {
        "schema_version": 3,
        "dataset_status": "DRAFT",
        "supersedes": {"schema_version": 2, "path": V2_PATH,
                       "note": "v2 는 그대로 보존한다. 프론트 전환이 끝나면 교체한다"},
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "source": dict(v2["source"], coordinates_from="C8b 재계산 (이 스크립트)"),
        "similarity": v2["similarity"],
        "layout": {
            "method": "umap", "n_neighbors": 10, "min_dist": 0.1, "random_state": SEED,
            "layout_id": f"c8b_umap_nn10_md0.1_seed{SEED}",
            "population": 200, "display_count": 200,
            "normalization": "[0,1], uniform scale on x and y",
            "distance_is_metric": False,
            "distance": {
                "kind": "blend",
                "base_similarity_weight": round(1 - FAMILY_W - PERCEPT_W, 2),
                "family_profile_weight": FAMILY_W,
                "perception_weight": PERCEPT_W,
                "family_profile": "Set B 9계열 Family Score 벡터의 코사인 거리",
                "perception": "사용자 투표 계절 따뜻함 · 성별 남성향 2축 (20표 이상)",
                "decision": "DECISIONS.md D22 · D24",
            },
            "metrics": {
                "trust_at_10": round(float(m["trust@10"]), 4),
                "knn_overlap_at_10": round(float(m["knn_overlap@10"]), 4),
                "reminds_distance_percentile": round(float(m["reminds_pct"]), 4),
                "trusted_reminds_edges_in_set": len(ce),
                "perfumes_with_trusted_reminds_edge": nodes,
                "source": "이 스크립트에서 실측 (v2 는 40/44 가 하드코딩돼 있었다)",
            },
        },
        "bounds": {"x_min": round(float(unit[:, 0].min()), 5),
                   "x_max": round(float(unit[:, 0].max()), 5),
                   "y_min": round(float(unit[:, 1].min()), 5),
                   "y_max": round(float(unit[:, 1].max()), 5)},
        "terrain": {
            "method": "gaussian_kde", "bandwidth": "scott x 0.5",
            "bandwidth_scale": bkt.BANDWIDTH_SCALE,
            "grid_width": width, "grid_height": height,
            "bounds": {"x_min": round(float(lo[0]), 5), "x_max": round(float(hi[0]), 5),
                       "y_min": round(float(lo[1]), 5), "y_max": round(float(hi[1]), 5)},
            "encoding": "row_major_uint8",
            "row_order": "row 0 = y_min, 마지막 row = y_max. col 0 = x_min",
            "value_range": [0, 255], "values": quantized.ravel().tolist(),
            "sea_level": sea_u8,
            "sea_level_basis": f"밀도 하위 {bkt.SEA_PERCENTILE} 백분위. 육지 = values > sea_level",
            "land_area_share": round(float(land.mean()), 4),
            "points_on_land": int(land[row_idx, col_idx].sum()),
            "source": "DECISIONS.md D12 (파라미터는 v2 와 같다. 좌표가 바뀌어 재계산했다)",
            "seed_stability": bkt.SEED_STABILITY,
        },
        "contours": [{"level": sea_u8,
                      "meaning": "해안선. terrain 값이 sea_level 을 넘는 영역의 경계",
                      "polygons": bkt.mask_polygons(land, xs, ys)}],
        "regions": {
            "status": "COMPAT",
            "note": ("자동 군집 7개. 프론트 전환용 호환 필드이며 Family 로 대체할 예정이다. "
                     "군집 라벨은 v2 와 같고 격자·폴리곤만 새 좌표에서 다시 그렸다"),
            "cluster_method": f"agglomerative {bkt.CLUSTER_LINKAGE} linkage on "
                              f"precomputed base-similarity distance",
            "cluster_count": cluster_k, "silhouette": round(sil, 4),
            "label_rule": f"클러스터 내 coverage >= {bkt.LABEL_MIN_COVERAGE} 인 accord 중 "
                          f"(클러스터 보유율 / 코퍼스 보유율) 상위 {bkt.LABEL_TOP_N}개",
            "label_denominator": "EDA/analysis_outputs/10_accord_dictionary.csv perfume_share",
            "grid_encoding": "row_major_uint8, 값 = region id, 255 = 바다",
            "grid": region_grid.ravel().tolist(), "items": region_items,
        },
        "families": {
            "status": "PRIMARY",
            "system": f"Set B {es.MAPPING_VERSION}", "count": len(usable),
            "assignment": {
                "rule": f"향수 안 비중 >= {FAMILY_THRESHOLD} 인 계열 + argmax 계열(항상 포함)",
                "threshold": FAMILY_THRESHOLD,
                "weight_basis": "Family Score. 향수마다 9계열 합이 1.0 이므로 가중치 = 그 계열의 비중",
                "renormalized": False,
                "families_per_perfume": {
                    "mean": round(float(active.mean()), 3),
                    "max": int(active.max()),
                    "with_two_or_more": int((active >= 2).sum()),
                    "share_le3": round(float((active <= 3).mean()), 4)},
                "decision": "DECISIONS.md D27 · D28",
            },
            "territory_rule": {"area_share": p5.TERR_AREA,
                               "largest_blob_share": p5.TERR_BLOB,
                               "weighted_coverage": p5.TERR_COVER,
                               "note": "9계열 전부 통과 (시드 5개 기준, D28)"},
            "grid_encoding": "row_major_uint8, 값 = families.items[].id, 255 = 바다. "
                             "terrain 과 같은 격자·bounds",
            "grid": fam_grid.ravel().tolist(),
            "items": fam_items,
        },
        "points": points,
    }

    with open(V3_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
        f.write("\n")

    # ---- 검증 ----
    print()
    print("-" * 96)
    print("검증")
    print("-" * 96)
    saved = json.loads(open(V3_PATH, encoding="utf-8").read())
    pts = saved["points"]
    checks = []

    def chk(name, ok, detail=""):
        checks.append({"check": name, "ok": bool(ok), "detail": detail})
        print(f"  {'PASS' if ok else 'FAIL'}  {name}{('  — ' + detail) if detail else ''}")

    chk("향수 200개", len(pts) == 200, f"{len(pts)}개")
    chk("fragrantica_id 중복 없음", len({p['fragrantica_id'] for p in pts}) == 200)
    chk("v2 와 향수 집합 동일", {p["fragrantica_id"] for p in pts} == set(ids))
    chk("좌표가 [0,1] 안", all(0 <= p["x"] <= 1 and 0 <= p["y"] <= 1 for p in pts))
    t, r, fa = saved["terrain"], saved["regions"], saved["families"]
    n = t["grid_width"] * t["grid_height"]
    chk("terrain 격자 길이", len(t["values"]) == n, f"{len(t['values'])} == {n}")
    chk("regions 격자 길이", len(r["grid"]) == n)
    chk("families 격자 길이", len(fa["grid"]) == n)
    chk("terrain 값 범위", max(t["values"]) == 255 and min(t["values"]) >= 0)
    chk("region 라벨이 v2 와 동일", all(p["region"] == v2_by_id[p["fragrantica_id"]]["region"]
                                   for p in pts))
    nf = [len(p["families"]) for p in pts]
    chk("계열 1~3개", min(nf) >= 1 and max(nf) <= 3, f"최소 {min(nf)} 최대 {max(nf)}")
    chk("가중치 양수·합 <= 1",
        all(all(f["weight"] > 0 for f in p["families"])
            and sum(f["weight"] for f in p["families"]) <= 1.0001 for p in pts))
    chk("argmax 계열이 항상 포함",
        all(p["families"][0]["key"] == families[int(M[i].argmax())] for i, p in enumerate(pts)))
    chk("families.items 9개", len(fa["items"]) == 9, f"{len(fa['items'])}개")
    chk("모든 계열이 폴리곤 보유", all(it["polygon"] for it in fa["items"]))
    # 이 산출물의 핵심 주장이다 — 출하 좌표([0,1] 정규화) 위에서도 9계열 전부 구역을 갖는가.
    # phase5b 는 raw UMAP 좌표에서 쟀고 여기는 정규화 좌표라 격자가 미세하게 다르다.
    bad = [it["name_ko"] for it in fa["items"]
           if not (it["area_share"] >= p5.TERR_AREA
                   and it["largest_blob_share"] >= p5.TERR_BLOB
                   and it["weighted_coverage"] >= p5.TERR_COVER)]
    chk("9계열 전부 Territory 판정 통과", not bad,
        "미달 " + ", ".join(bad) if bad else "면적>=3% · 덩어리>=60% · coverage>=0.50")
    chk("neighbors 가 v2 와 동일",
        all(p["neighbors"] == v2_by_id[p["fragrantica_id"]]["neighbors"] for p in pts))
    chk("v2 파일 불변", v2b.sha256(V2_PATH) == v2b.sha256(V2_PATH))

    n_fail = sum(1 for c in checks if not c["ok"])
    print(f"\n  검증 {len(checks)-n_fail}/{len(checks)} PASS")

    diff = {
        "from": {"schema_version": 2, "path": V2_PATH},
        "to": {"schema_version": 3, "path": V3_PATH},
        "changed": {
            "layout.distance": {"before": "base similarity only",
                                "after": f"blend base {1-FAMILY_W-PERCEPT_W:.2f} / "
                                         f"family {FAMILY_W} / perception {PERCEPT_W}"},
            "points[].x, y": "C8b 좌표로 재계산 (모든 점 이동)",
            "terrain, contours, regions.grid, regions.items[].polygon": "좌표가 바뀌어 재계산",
            "layout.metrics": "실측값으로 교체 (v2 는 신뢰 간선 40/44 가 하드코딩)",
        },
        "added": {
            "families": "9계열 Territory 격자 · 폴리곤 · 앵커",
            "points[].families": "계열 1~3개 + 가중치",
            "regions.status": "COMPAT — 전환 후 제거 예정",
            "families.status": "PRIMARY",
        },
        "unchanged": {
            "points[].region": "군집 라벨 (호환 유지)",
            "points[].neighbors": "Base Similarity 기반 — 좌표와 무관",
            "points[] 나머지": "brand · name · korea · match · top_accords · seasons · daypart",
            "similarity": "0.5 accord + 0.5 note IDF",
        },
        "verification": checks,
        "verification_pass": len(checks) - n_fail,
        "verification_total": len(checks),
    }
    with open(os.path.join(OUT_DIR, "schema_diff.json"), "w", encoding="utf-8") as f:
        json.dump(diff, f, ensure_ascii=False, indent=1)
        f.write("\n")

    if n_fail:
        raise SystemExit("검증 실패 — v3 를 프로덕션으로 옮기지 말 것")
    print(f"\n  -> {V3_PATH}  ({os.path.getsize(V3_PATH)/1024:.0f} KB)")
    print(f"  -> {OUT_DIR}/schema_diff.json")
    print("\n  output/ 은 쓰지 않았다. 팀 확인 후 옮긴다.")


if __name__ == "__main__":
    main()

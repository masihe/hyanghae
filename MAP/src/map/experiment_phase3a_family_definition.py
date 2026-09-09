"""Phase 3a — 어떤 Family 정의로 Phase 3b 를 진행할지 고른다.

Run with venv/Scripts/python.exe src/map/experiment_phase3a_family_definition.py

**기준 투영은 UMAP seed 42 다** (팀 결정). 근거는 "UMAP 이 모든 지표에서 최고" 가 아니라
국소/전역 균형과 안정성, 그리고 기존 지도 파이프라인과의 연결이다. TriMap-dist 는
사람 유사성 지표가 우수하므로 최종 후보 지도에서 재검증한다.

**안정성은 Hard Gate 가 아니다** (팀 결정). 시드 5개에서 구조가 크게 무너지지 않는지만
확인하고 기록 지표로 둔다. 최종 서비스는 스냅샷·파라미터·시드·좌표를 고정한다.

**계열 수가 다르면 응집도 절대값을 비교할 수 없다.** 계열이 적으면 무작위로 칠해도 같은
색이 자주 걸린다. 비교는 `observed / random_expected` 비율로 한다 (v4 10).

**세 정의를 같은 좌표에서 비교한다.**

    Set A  Fragrantica 설명문 계열 -> 휠 4대 그룹. Korea 200 에서 16개 결측 -> UNCLASSIFIED
    Set B  사람 검토 accord 기반 9계열 (reviewed-1). 결측 0
    Set C  Data-driven 계층 군집. EXISTING_RESULT — 현재 유사도에서 자연 계열로 주장하기 어렵다

Set B 내부의 계열 수(7 / 8A / 8B / 9)는 별도 실험에서 이미 비교했다 —
experiments/phase0_family_count_comparison/. 여기서는 정의 3종 사이를 고른다.

산출: experiments/phase3a/
"""
import json
import os
import sys
import time

import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "common")))
import scent_map as sm
import build_map as bm
import experiment_phase0_family_mapping as fm
import experiment_family_systems as es

OUT_DIR = os.path.join("experiments", "phase3a")
FC_DIR = os.path.join("experiments", "phase0_family_count_comparison")
TOP200 = os.path.join("data", "korea_popularity", "korea_representative_perfumes_top200.csv")
V2_JSON = os.path.join("output", "korea_scent_map_v2.json")   # 읽기만 한다
SEEDS = (42, 1, 2, 3, 4)
UNCLASSIFIED = "UNCLASSIFIED"
NEIGHBOR_K = 10

# 기준 투영 (팀 결정)
PROJECTION = "umap n_neighbors=10 min_dist=0.1 metric=precomputed seed=42"


def sha256(path):
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def cohesion(coords, labels, drop=UNCLASSIFIED):
    labels = np.asarray(labels, dtype=object)
    coords = np.asarray(coords, float)
    total = len(labels)
    keep = labels != drop
    obs, exp, per = bm.region_cohesion(coords[keep], labels[keep], k=NEIGHBOR_K)
    sizes = pd.Series(labels[keep]).value_counts()
    return {"coverage": round(float(keep.mean()), 4),
            "n_classified": int(keep.sum()), "n_total": total,
            "family_count": int(len(sizes)),
            "observed_cohesion": round(float(obs), 4),
            "random_expected_cohesion": round(float(exp), 4),
            "cohesion_ratio": round(float(obs / exp), 3),
            "size_max": int(sizes.max()), "size_min": int(sizes.min()),
            "size_max_share": round(float(sizes.max() / keep.sum()), 4),
            "per_family_cohesion": per,
            "sizes": {str(k): int(v) for k, v in sizes.items()}}


def neighborhood_purity(coords, labels, drop=UNCLASSIFIED):
    import collections
    from scipy.spatial.distance import squareform, pdist
    labels = np.asarray(labels, dtype=object)
    coords = np.asarray(coords, float)
    keep = labels != drop
    L, C = labels[keep], coords[keep]
    D = squareform(pdist(C))
    np.fill_diagonal(D, np.inf)
    nn = np.argsort(D, axis=1)[:, :NEIGHBOR_K]
    shares = np.array([collections.Counter(L[r]).most_common(1)[0][1] / NEIGHBOR_K
                       for r in nn])
    own = np.array([L[i] == collections.Counter(L[nn[i]]).most_common(1)[0][0]
                    for i in range(len(L))])
    return {"mean_top_family_share": round(float(shares.mean()), 4),
            "own_is_local_majority": round(float(own.mean()), 4),
            "share_ge_0.6": int((shares >= 0.6).sum()),
            "share_ge_0.7": int((shares >= 0.7).sum())}


def cross_family(coords, index_of, edges, labels, ids, drop=UNCLASSIFIED):
    pos = {int(v): i for i, v in enumerate(ids)}
    lab = np.asarray(labels, dtype=object)
    same, cross, skipped = [], [], 0
    for a, b in edges:
        la, lb = lab[pos[a]], lab[pos[b]]
        if la == drop or lb == drop:
            skipped += 1
            continue
        (same if la == lb else cross).append((a, b))
    out = {"trusted_edges": len(edges), "skipped_unclassified": skipped,
           "same_family": len(same), "cross_family": len(cross)}
    if cross:
        out["cross_family_proximity"] = round(
            bm.edge_distance_percentile(coords, index_of, cross)[0], 4)
    if same:
        out["same_family_proximity"] = round(
            bm.edge_distance_percentile(coords, index_of, same)[0], 4)
    return out


def set_c_labels(distance):
    """Data-driven. D12 의 선택 규칙(최소 3, 최대 비중 0.5, 그중 silhouette 최대)을 재적용."""
    from sklearn.cluster import AgglomerativeClustering
    from sklearn.metrics import silhouette_score
    best = None
    for k in range(2, 13):
        lab = AgglomerativeClustering(n_clusters=k, metric="precomputed",
                                      linkage="average").fit_predict(distance)
        sil = float(silhouette_score(distance, lab, metric="precomputed"))
        sizes = np.bincount(lab, minlength=k)
        if sizes.min() >= 3 and sizes.max() / len(lab) <= 0.5:
            if best is None or sil > best[1]:
                best = (k, sil, lab)
    if best is None:
        return None, None, None
    k, sil, lab = best
    return np.array([f"c{x}" for x in lab], dtype=object), k, round(sil, 4)


def main() -> None:
    os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))  # MAP/
    os.makedirs(OUT_DIR, exist_ok=True)
    t0 = time.time()

    print("=" * 78)
    print("Phase 3a — Family 정의 선택 (기준 투영: UMAP seed 42)")
    print("=" * 78)

    df, targets, idf_map, _S, D_g, index_of_g, ce_g, _ae = bm.prepare(
        with_selection_comparison=False)
    korea_ids = pd.read_csv(TOP200).fragrantica_id.astype(int).tolist()
    korea = df.set_index("id").loc[korea_ids].reset_index()
    index_of_k = {int(v): i for i, v in enumerate(korea_ids)}
    S_k, _, _ = sm.base_similarity(korea.accord_list.tolist(), korea.note_set.tolist(), idf_map)
    D_k = 1.0 - S_k
    np.fill_diagonal(D_k, 0.0)
    rin = bm.edges_within(sm.load_edges("reminds_edges.csv"), set(korea_ids))
    ce_k = [(int(a), int(b)) for a, b in rin[bm.confident(rin)][["src", "dst"]].itertuples(
        index=False, name=None)]

    # ---- 기준 좌표: 출하 중인 UMAP seed 42 (Korea) / 재계산 (Global) ----
    doc = json.loads(open(V2_JSON, encoding="utf-8").read())
    by_id = {p["fragrantica_id"]: (p["x"], p["y"]) for p in doc["points"]}
    coords_k = {42: np.array([by_id[i] for i in korea_ids], dtype=float)}
    import umap
    coords_g = {42: np.asarray(umap.UMAP(n_neighbors=10, min_dist=0.1,
                                         metric="precomputed",
                                         random_state=42).fit_transform(D_g), dtype=float)}
    print(f"Korea 200 좌표: {V2_JSON} (읽기 전용, layout {doc['layout']['layout_id']})")
    print(f"Global 1,000 좌표: UMAP seed 42 재계산")
    # 시드 4개 추가 (구조 검증용. Hard Gate 아님 — 팀 결정)
    for s in SEEDS[1:]:
        coords_k[s] = np.asarray(umap.UMAP(n_neighbors=10, min_dist=0.1,
                                           metric="precomputed",
                                           random_state=s).fit_transform(D_k), dtype=float)

    # ---- 세 정의의 라벨 ----
    Mk, fams = es.family_scores(korea.accord_list.tolist(), "S9")["M"], None
    resk = es.family_scores(korea.accord_list.tolist(), "S9")
    resg = es.family_scores(targets.accord_list.tolist(), "S9")
    labels = {
        "korea200": {
            "SetA": np.array(korea["group"].fillna(UNCLASSIFIED).astype(str).tolist(),
                             dtype=object),
            "SetB": resk["argmax"],
        },
        "global1000": {
            "SetA": np.array(targets["group"].fillna(UNCLASSIFIED).astype(str).tolist(),
                             dtype=object),
            "SetB": resg["argmax"],
        },
    }
    lab_c_k, k_c, sil_c = set_c_labels(D_k)
    labels["korea200"]["SetC"] = lab_c_k
    lab_c_g, k_cg, sil_cg = set_c_labels(D_g)
    labels["global1000"]["SetC"] = lab_c_g
    print(f"Set C 재적용 — Korea k={k_c} silhouette {sil_c} · Global k={k_cg} "
          f"silhouette {sil_cg}")
    print(f"매핑 {es.MAPPING_VERSION} (draft-1 해시 {fm.mapping_digest()[:12]}... 불변)")

    # ---- 평가 ----
    out = {}
    print()
    print(f"  {'정의':<7}{'모집단':<12}{'계열':>4}{'coverage':>10}{'obs':>8}{'exp':>8}"
          f"{'ratio':>8}{'이웃최다':>9}{'최대비중':>9}{'횡단쌍':>7}{'횡단근접':>9}")
    for pop, coords_map, index_of, edges, ids in (
            ("korea200", coords_k, index_of_k, ce_k, korea_ids),
            ("global1000", coords_g, index_of_g, ce_g, targets.id.astype(int).tolist())):
        out[pop] = {}
        for sname in ("SetA", "SetB", "SetC"):
            lab = labels[pop][sname]
            if lab is None:
                out[pop][sname] = {"ok": False, "note": "규칙을 통과하는 k 가 없다"}
                continue
            c42 = coords_map[42]
            blk = {"ok": True, **cohesion(c42, lab),
                   "neighborhood_purity": neighborhood_purity(c42, lab),
                   "cross_family": cross_family(c42, index_of, edges, lab, ids)}
            # 시드 검증 (Korea 만 — 기록 지표)
            if pop == "korea200" and len(coords_map) > 1:
                ratios = [cohesion(coords_map[s], lab)["cohesion_ratio"] for s in SEEDS]
                blk["seed_check"] = {
                    "seeds": list(SEEDS), "ratios": ratios,
                    "mean": round(float(np.mean(ratios)), 3),
                    "std": round(float(np.std(ratios)), 3),
                    "min": round(float(np.min(ratios)), 3),
                    "collapsed": bool(np.min(ratios) < 0.7 * np.mean(ratios)),
                }
            out[pop][sname] = blk
            cf = blk["cross_family"]
            print(f"  {sname:<7}{pop:<12}{blk['family_count']:>4}{blk['coverage']:>10.1%}"
                  f"{blk['observed_cohesion']:>8.3f}{blk['random_expected_cohesion']:>8.3f}"
                  f"{blk['cohesion_ratio']:>8.3f}"
                  f"{blk['neighborhood_purity']['mean_top_family_share']:>9.3f}"
                  f"{blk['size_max_share']:>9.1%}{cf['cross_family']:>7}"
                  f"{cf.get('cross_family_proximity', float('nan')):>9.4f}")

    print()
    print("시드 검증 (Korea 200 · cohesion ratio · Hard Gate 아님)")
    for sname in ("SetA", "SetB", "SetC"):
        sc = out["korea200"][sname].get("seed_check")
        if sc:
            print(f"  {sname:<7} {sc['mean']:.3f} ± {sc['std']:.3f} (최소 {sc['min']:.3f}) · "
                  f"구조 붕괴 {'있음' if sc['collapsed'] else '없음'}")

    # ---- Set B 내부 계열 수는 별도 실험 결과를 인용 ----
    fc = json.loads(open(os.path.join(FC_DIR, "metrics.json"), encoding="utf-8").read())
    fc_ref = {v["short"]: {"cohesion_ratio_korea": v["cohesion_ratio"]}
              for v in fc["korea200"].values()}
    for s, v in fc["global1000"].items():
        fc_ref[v["short"]]["cohesion_ratio_global"] = v["cohesion_ratio"]
    print()
    print("Set B 내부 계열 수 (phase0_family_count_comparison 인용)")
    for s in ("9", "8A", "8B", "7"):
        r = fc_ref[s]
        print(f"  {s:<4} Korea {r['cohesion_ratio_korea']:.3f} · "
              f"Global {r['cohesion_ratio_global']:.3f}")

    # ---- 선택 ----
    ranked = sorted(("SetA", "SetB", "SetC"),
                    key=lambda s: -(out["global1000"][s].get("cohesion_ratio", 0)))
    choice = ranked[0]
    print()
    print(f"Global 1,000 정규화 응집도 순위: "
          + " > ".join(f"{s}({out['global1000'][s].get('cohesion_ratio')})" for s in ranked))
    print(f"Phase 3b 기본 Family 정의 제안: {choice} "
          f"(최종 선택은 팀)")

    labs = pd.DataFrame({
        "fragrantica_id": korea_ids,
        "brand": korea.brand.values, "name": korea["name"].values,
        "SetA": labels["korea200"]["SetA"], "SetB": labels["korea200"]["SetB"],
        "SetC": labels["korea200"]["SetC"],
    })
    labs.to_csv(os.path.join(OUT_DIR, "labels_korea200.csv"), index=False,
                encoding="utf-8-sig")

    out["_meta"] = {
        "projection": PROJECTION,
        "projection_decision": ("팀 결정 — UMAP 이 모든 지표에서 최고이기 때문이 아니라 "
                                "국소/전역 균형과 안정성, 기존 파이프라인 연결 때문이다. "
                                "TriMap-dist 는 최종 후보 지도에서 재검증한다"),
        "coordinate_source": {"korea200": f"{V2_JSON} (읽기 전용)",
                              "global1000": "UMAP seed 42 재계산"},
        "mapping_version": es.MAPPING_VERSION,
        "base_mapping_sha256": fm.mapping_digest(),
        "cohesion_rule": "비교는 observed / random_expected 비율. 절대값 비교 금지",
        "stability_policy": ("팀 결정 — 안정성은 Hard Gate 가 아니라 기록/검토 지표다. "
                             "시드 5개에서 구조가 크게 무너지지 않는지만 확인한다"),
        "set_b_family_count_reference": fc_ref,
        "recommended_definition": choice,
        "set_c_status": "EXISTING_RESULT — 현재 유사도에서 자연 계열로 주장하기 어렵다",
    }
    with open(os.path.join(OUT_DIR, "metrics.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
        f.write("\n")
    manifest = {
        "experiment_id": "phase3a", "phase": 3, "status": "NEW",
        "hypothesis": "Family 정의에 따라 지도에서 영역이 읽히는 정도가 달라진다",
        "user_meaning": "사용자가 '여기가 어느 향 구역인가' 를 읽을 수 있는가",
        "changed_variable": "Family 정의 (좌표·유사도·스냅샷 고정)",
        "population": ["korea200", "global1000"],
        "snapshot_hash": {"perfumes_csv": sha256(sm.PERFUMES_CSV),
                          "korea_top200_csv": sha256(TOP200)},
        "projection": PROJECTION,
        "family_mapping_version": es.MAPPING_VERSION,
        "seeds": list(SEEDS),
        "primary_metrics": ["cohesion_ratio", "coverage", "neighborhood_purity"],
        "guardrail_metrics": ["cross_family_proximity (Global 1,000)"],
        "recommendation": choice,
        "elapsed_sec": round(time.time() - t0, 1),
    }
    with open(os.path.join(OUT_DIR, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print()
    print(f"총 소요 {time.time()-t0:.0f}초")
    print(f"  -> {OUT_DIR}/ (metrics.json, manifest.json, labels_korea200.csv)")


if __name__ == "__main__":
    main()

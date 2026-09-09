"""Phase 2 — 고정된 유사도를 어떤 2D 투영이 가장 잘 보존하는가.

Run with venv/Scripts/python.exe src/map/experiment_phase2_projection.py

**입력이 하나다.** Phase 1 의 A8 / A7 / A2 가 전부 baseline 을 넘지 못했으므로
(신규 후보 0개) 유사도는 현재 방식으로 고정한다 —
`0.5 x accord 코사인(raw strength, L2) + 0.5 x note IDF 가중 Jaccard`.
모든 투영이 같은 원본 공간을 공유하므로 kNN overlap 계열 지표를 **공정하게** 쓸 수 있다.

**절대 탈락선을 쓰지 않는다.** 기존 `overlap >= 0.30` 은 D2 의 UMAP 스윕 최저값에서 나온
값이므로 t-SNE / TriMap 에 자동 탈락선으로 적용하면 "UMAP 계열이 아니면 탈락" 이 된다.
baseline(UMAP) 대비 상대 변화와 Pareto 로 판단한다 (v4 20).

**PaCMAP 만 입력이 다르다.** Phase 0 의 의존성 확인에서 실행으로 확인했다 —
`distance="precomputed"` 가 `NotImplementedError` 로 거부된다 (허용: euclidean / dot /
angular / manhattan / hamming). 그래서 PaCMAP 은 accord+note 특징행렬을 받는다.
**투영 방식 차이와 입력 표현 차이가 섞이므로** 대조 조건으로 명시해야 한다.
같은 자리를 재기 위해 TriMap 은 거리행렬·특징행렬 두 경로를 모두 돌린다.

**Continuity@K 는 직접 구현한다** (scikit-learn 에 없다). v4 21 이 고정한 표준식:

    C(k) = 1 - [2 / (n k (2n - 3k - 1))] * sum_i sum_{j in V_k(i)} (r_hat(i,j) - k)
    V_k(i)      원본에서는 i 의 kNN 이지만 임베딩에서는 kNN 이 아닌 점
    r_hat(i,j)  임베딩 공간에서 j 의 순위 (가장 가까운 것이 1)

산출: experiments/phase2/
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
import compare_korea_map_population as ckp

OUT_DIR = os.path.join("experiments", "phase2")
PHASE0 = os.path.join("experiments", "phase0")
TOP200 = os.path.join("data", "korea_popularity", "korea_representative_perfumes_top200.csv")
SEEDS = (42, 1, 2, 3, 4)
K_LEVELS = (5, 10, 20)

# Phase 0 이 실측 고정한 baseline (UMAP nn=10 min_dist=0.1 seed 42)
BASELINE = {
    "global1000": {"trust@10": 0.9387, "knn_overlap@10": 0.3888},
    "korea200": {"trust@10": 0.9191, "knn_overlap@10": 0.4875},
}
TOL = 0.0015


def sha256(path):
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


# --------------------------------------------------------------------------
# 지표
# --------------------------------------------------------------------------
def rank_matrix(D):
    """R[i, j] = i 기준 j 의 순위. 자기 자신이 0, 가장 가까운 이웃이 1."""
    n = len(D)
    idx = np.argsort(D, axis=1, kind="stable")
    R = np.empty((n, n), dtype=np.int32)
    rows = np.arange(n)[:, None]
    R[rows, idx] = np.arange(n, dtype=np.int32)[None, :]
    return R


def continuity(R_high, R_low, k):
    """v4 21 의 표준 rank-based continuity. R 은 rank_matrix 결과."""
    n = R_high.shape[0]
    assert k < n / 2, "정규화 상수가 k < n/2 에서만 유효하다"
    total = 0.0
    for i in range(n):
        # 원본에서는 kNN 인데 임베딩에서는 밀려난 점
        mask = (R_high[i] >= 1) & (R_high[i] <= k) & (R_low[i] > k)
        total += float((R_low[i][mask] - k).sum())
    return 1.0 - (2.0 / (n * k * (2 * n - 3 * k - 1))) * total


def layout_metrics(coords, D_high, R_high, index_of, conf_edges, also_edges):
    from scipy.spatial.distance import squareform, pdist
    from scipy.stats import spearmanr
    from sklearn.manifold import trustworthiness
    coords = np.asarray(coords, dtype=float)
    D_low = squareform(pdist(coords))
    R_low = rank_matrix(D_low)
    iu = np.triu_indices(len(coords), 1)
    out = {}
    for k in K_LEVELS:
        out[f"trust@{k}"] = float(trustworthiness(D_high, coords, n_neighbors=k,
                                                  metric="precomputed"))
        out[f"knn_overlap@{k}"] = float(bm.knn_overlap(D_high, coords, k=k))
        out[f"continuity@{k}"] = float(continuity(R_high, R_low, k))
    out["distance_rank_corr"] = float(spearmanr(D_high[iu], D_low[iu])[0])
    out["reminds_pct"] = float(bm.edge_distance_percentile(coords, index_of, conf_edges)[0])
    out["also_liked_pct"] = float(bm.edge_distance_percentile(coords, index_of, also_edges)[0])
    return out


def neighbor_stability(coord_list, k=10):
    """시드 간 이웃 집합이 얼마나 겹치는가. 정합이 필요 없는 지표다."""
    from scipy.spatial.distance import squareform, pdist
    sets = []
    for c in coord_list:
        D = squareform(pdist(np.asarray(c, float)))
        np.fill_diagonal(D, np.inf)
        sets.append(np.argsort(D, axis=1)[:, :k])
    vals = []
    for a in range(len(sets)):
        for b in range(a + 1, len(sets)):
            vals.append(np.mean([len(set(sets[a][i]) & set(sets[b][i])) / k
                                 for i in range(len(sets[a]))]))
    return {"mean": float(np.mean(vals)), "min": float(np.min(vals)),
            "pairs": len(vals)}


def coordinate_stability(coord_list):
    """Procrustes(회전·반사) 정합 후 잔차. compare_korea_map_population.align 재사용."""
    ref = np.asarray(coord_list[0], float)
    res = []
    for c in coord_list[1:]:
        aligned = ckp.align(np.asarray(c, float), ref)
        a = aligned - aligned.mean(axis=0)
        r = ref - ref.mean(axis=0)
        a = a / (np.linalg.norm(a) or 1.0)
        r = r / (np.linalg.norm(r) or 1.0)
        res.append(float(np.linalg.norm(a - r) / np.sqrt(len(r))))
    return {"mean_residual": float(np.mean(res)), "max_residual": float(np.max(res))}


# --------------------------------------------------------------------------
# 투영
# --------------------------------------------------------------------------
def make_layouts():
    """(이름, 종류, 입력, 함수). 함수는 (D, features, seed) -> coords."""
    def umap_fn(D, F, seed):
        import umap
        return umap.UMAP(n_neighbors=10, min_dist=0.1, metric="precomputed",
                         random_state=seed).fit_transform(D)

    def tsne_fn(D, F, seed):
        from sklearn.manifold import TSNE
        return TSNE(n_components=2, metric="precomputed", init="random",
                    perplexity=30, learning_rate="auto",
                    random_state=seed).fit_transform(D)

    def pacmap_fn(D, F, seed):
        import pacmap
        return pacmap.PaCMAP(n_components=2, n_neighbors=10,
                             random_state=seed).fit_transform(F)

    def trimap_dist_fn(D, F, seed):
        import trimap
        return trimap.TorchTRIMAP(n_dims=2, n_inliers=10, n_outliers=5, n_random=5,
                                  use_dist_matrix=True, apply_pca=False,
                                  random_state=seed, verbose=False
                                  ).fit_transform(D).cpu().numpy()

    def trimap_feat_fn(D, F, seed):
        import trimap
        return trimap.TorchTRIMAP(n_dims=2, n_inliers=10, n_outliers=5, n_random=5,
                                  random_state=seed, verbose=False
                                  ).fit_transform(F).cpu().numpy()

    def knn_force_fn(D, F, seed):
        import networkx as nx
        n = len(D)
        Dm = D.copy()
        np.fill_diagonal(Dm, np.inf)
        nn = np.argsort(Dm, axis=1)[:, :10]
        G = nx.Graph()
        G.add_nodes_from(range(n))
        for i in range(n):
            for j in nn[i]:
                w = max(1.0 - float(D[i, j]), 1e-6)   # 유사도를 끌어당기는 힘으로
                if G.has_edge(i, int(j)):
                    G[i][int(j)]["weight"] = max(G[i][int(j)]["weight"], w)
                else:
                    G.add_edge(i, int(j), weight=w)
        pos = nx.spring_layout(G, weight="weight", seed=seed, iterations=60)
        return np.array([pos[i] for i in range(n)])

    def pca_fn(D, F, seed):
        from sklearn.decomposition import PCA
        return PCA(n_components=2, random_state=0).fit_transform(F)

    return [
        ("UMAP", "stochastic", "distance", umap_fn),
        ("t-SNE", "stochastic", "distance", tsne_fn),
        ("PaCMAP", "stochastic", "features", pacmap_fn),
        ("TriMap-dist", "stochastic", "distance", trimap_dist_fn),
        ("TriMap-feat", "stochastic", "features", trimap_feat_fn),
        ("kNN graph + force", "stochastic", "distance", knn_force_fn),
        ("PCA", "deterministic", "features", pca_fn),
    ]


def build_features(rows, idf_map):
    """build_map.main() 과 같은 방식. accord L2 정규화 + note IDF 행 정규화를 이어붙인다."""
    A, _ = sm.build_accord_matrix(list(rows["accord_list"]))
    B, w, _v, _m = sm.build_note_matrix(list(rows["note_set"]), idf_map)
    Bn = B * w
    norm = np.linalg.norm(Bn, axis=1, keepdims=True)
    norm[norm == 0] = 1.0
    return np.hstack([A, Bn / norm])


def run_population(name, rows, D, index_of, conf_edges, also_edges, idf_map, out_dir):
    print()
    print("=" * 78)
    print(f"{name} (n={len(rows)}) — 투영 비교")
    print("=" * 78)
    F = build_features(rows, idf_map)
    R_high = rank_matrix(D)
    print(f"특징행렬 {F.shape} (PaCMAP·TriMap-feat·PCA 입력) · 거리행렬 {D.shape}")

    results = {}
    coords_store = {}
    for lname, kind, inp, fn in make_layouts():
        seeds = SEEDS if kind == "stochastic" else (0,)
        per_seed, coord_list = [], []
        t0 = time.time()
        for s in seeds:
            try:
                c = np.asarray(fn(D, F, s), dtype=float)
            except Exception as e:
                print(f"  {lname:<20} 실패 — {type(e).__name__}: {e}")
                per_seed = None
                break
            coord_list.append(c)
            per_seed.append({"seed": s, **layout_metrics(c, D, R_high, index_of,
                                                         conf_edges, also_edges)})
        if per_seed is None:
            results[lname] = {"ok": False}
            continue
        frame = pd.DataFrame(per_seed)
        agg = {}
        for col in frame.columns:
            if col == "seed":
                continue
            agg[col] = {"mean": round(float(frame[col].mean()), 4),
                        "std": round(float(frame[col].std(ddof=0)), 4),
                        "min": round(float(frame[col].min()), 4),
                        "max": round(float(frame[col].max()), 4)}
        blk = {"ok": True, "kind": kind, "input": inp, "seeds": list(seeds),
               "elapsed_sec": round(time.time() - t0, 1), "per_seed": per_seed,
               "agg": agg}
        if len(coord_list) > 1:
            blk["neighbor_stability@10"] = neighbor_stability(coord_list)
            blk["coordinate_stability"] = coordinate_stability(coord_list)
        results[lname] = blk
        coords_store[lname] = coord_list[0]
        ns = blk.get("neighbor_stability@10", {}).get("mean")
        print(f"  {lname:<20} trust@10 {agg['trust@10']['mean']:.4f}±{agg['trust@10']['std']:.4f}"
              f" · overlap@10 {agg['knn_overlap@10']['mean']:.4f}"
              f" · cont@10 {agg['continuity@10']['mean']:.4f}"
              f" · 거리순위 {agg['distance_rank_corr']['mean']:+.3f}"
              f" · 정답간선 {agg['reminds_pct']['mean']:.4f}"
              f" · 이웃안정 {ns if ns is None else f'{ns:.3f}'}"
              f" ({blk['elapsed_sec']}s)")

    # baseline 재현 확인 (UMAP seed 42)
    u42 = next(r for r in results["UMAP"]["per_seed"] if r["seed"] == 42)
    exp = BASELINE[name]
    ok = all(abs(u42[k] - v) <= TOL for k, v in exp.items())
    print()
    print(f"UMAP seed 42 재현 — trust@10 {u42['trust@10']:.4f} (기대 {exp['trust@10']}) · "
          f"overlap@10 {u42['knn_overlap@10']:.4f} (기대 {exp['knn_overlap@10']}) "
          f"{'OK' if ok else '** 차이 **'}")

    # 좌표 저장 (seed 42 / 첫 시드)
    frames = []
    for lname, c in coords_store.items():
        frames.append(pd.DataFrame({"layout": lname,
                                    "fragrantica_id": rows.id.astype(int).values,
                                    "x": c[:, 0], "y": c[:, 1]}))
    pd.concat(frames).to_csv(os.path.join(out_dir, f"coordinates_{name}.csv"),
                             index=False, encoding="utf-8-sig")
    return results, ok


def pareto_front(rows_):
    """(local, global, stability) 세 축에서 비지배 후보. local·global·stability 모두 클수록 좋다."""
    front = []
    for a in rows_:
        dominated = False
        for b in rows_:
            if b["layout"] == a["layout"]:
                continue
            if (b["local"] >= a["local"] and b["global"] >= a["global"]
                    and b["stability"] >= a["stability"]
                    and (b["local"] > a["local"] or b["global"] > a["global"]
                         or b["stability"] > a["stability"])):
                dominated = True
                break
        if not dominated:
            front.append(a["layout"])
    return front


def main() -> None:
    os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))  # MAP/
    os.makedirs(OUT_DIR, exist_ok=True)
    t0 = time.time()

    print("=" * 78)
    print("Phase 2 — 투영 비교. 유사도는 Phase 1 결과대로 baseline 고정")
    print("=" * 78)

    df, targets, idf_map, S_g, D_g, index_of_g, ce_g, ae_g = bm.prepare(
        with_selection_comparison=False)
    korea_ids = pd.read_csv(TOP200).fragrantica_id.astype(int).tolist()
    korea = df.set_index("id").loc[korea_ids].reset_index()
    S_k, _, _ = sm.base_similarity(korea.accord_list.tolist(), korea.note_set.tolist(), idf_map)
    D_k = 1.0 - S_k
    np.fill_diagonal(D_k, 0.0)
    index_of_k = {int(v): i for i, v in enumerate(korea_ids)}
    rin = bm.edges_within(sm.load_edges("reminds_edges.csv"), set(korea_ids))
    ce_k = [(int(a), int(b)) for a, b in rin[bm.confident(rin)][["src", "dst"]].itertuples(
        index=False, name=None)]
    ain = bm.edges_within(sm.load_edges("also_liked_edges.csv"), set(korea_ids))
    ae_k = [(int(a), int(b)) for a, b in ain[["src", "dst"]].itertuples(index=False, name=None)]

    res_g, ok_g = run_population("global1000", targets, D_g, index_of_g, ce_g, ae_g,
                                 idf_map, OUT_DIR)
    res_k, ok_k = run_population("korea200", korea, D_k, index_of_k, ce_k, ae_k,
                                 idf_map, OUT_DIR)

    # ---- 상대 비교와 Pareto ----
    print()
    print("=" * 78)
    print("baseline(UMAP) 대비 상대 비교 — Global 1,000")
    print("=" * 78)
    base = res_g["UMAP"]["agg"]
    print(f"  {'투영':<20}{'입력':<10}{'local Δ':>10}{'global Δ':>10}{'정답간선 Δ':>12}"
          f"{'이웃안정':>10}")
    table = []
    for lname, blk in res_g.items():
        if not blk.get("ok"):
            continue
        a = blk["agg"]
        loc = np.mean([a[f"knn_overlap@{k}"]["mean"] for k in K_LEVELS])
        loc_b = np.mean([base[f"knn_overlap@{k}"]["mean"] for k in K_LEVELS])
        glo = a["distance_rank_corr"]["mean"]
        glo_b = base["distance_rank_corr"]["mean"]
        rem = a["reminds_pct"]["mean"]
        stab = blk.get("neighbor_stability@10", {}).get("mean", 1.0)
        table.append({"layout": lname, "input": blk["input"], "local": loc, "global": glo,
                      "reminds": rem, "stability": stab,
                      "local_delta": loc - loc_b, "global_delta": glo - glo_b,
                      "reminds_delta": rem - base["reminds_pct"]["mean"]})
        print(f"  {lname:<20}{blk['input']:<10}{loc - loc_b:>+10.4f}{glo - glo_b:>+10.4f}"
              f"{rem - base['reminds_pct']['mean']:>+12.4f}{stab:>10.3f}")
    front = pareto_front(table)
    print()
    print(f"Pareto 비지배 후보 (local · global · 시드 안정성): {front}")
    print("  절대 탈락선을 쓰지 않았다 — overlap>=0.30 은 UMAP 스윕에서 나온 값이므로")
    print("  다른 알고리즘의 자동 탈락선으로 쓰지 않는다 (v4 20)")

    metrics = {
        "similarity": ("0.5 x accord 코사인(raw strength, L2) + 0.5 x note IDF 가중 Jaccard "
                       "— Phase 1 에 신규 후보가 없어 baseline 고정"),
        "global1000": res_g, "korea200": res_k,
        "relative_to_umap_global1000": table,
        "pareto_front_global1000": front,
        "baseline_reproduction_ok": {"global1000": bool(ok_g), "korea200": bool(ok_k)},
        "pacmap_confound": ("PaCMAP 은 precomputed 거리행렬을 받지 못해 특징행렬 입력이다. "
                            "투영 차이와 입력 표현 차이가 섞이므로 TriMap 을 거리·특징 두 경로로 "
                            "돌려 같은 자리를 비교할 수 있게 했다"),
        "continuity_definition": ("Venna & Kaski 표준식. v4 21 에 고정. "
                                  "C(k)=1-[2/(n k (2n-3k-1))] sum (r_hat - k)"),
    }
    with open(os.path.join(OUT_DIR, "metrics.json"), "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=1)
        f.write("\n")

    flat = []
    for pop, res in (("global1000", res_g), ("korea200", res_k)):
        for lname, blk in res.items():
            if not blk.get("ok"):
                continue
            row = {"population": pop, "layout": lname, "input": blk["input"],
                   "kind": blk["kind"], "elapsed_sec": blk["elapsed_sec"]}
            for m, v in blk["agg"].items():
                row[f"{m}_mean"] = v["mean"]
                row[f"{m}_std"] = v["std"]
            ns = blk.get("neighbor_stability@10")
            cs = blk.get("coordinate_stability")
            row["neighbor_stability@10"] = None if not ns else round(ns["mean"], 4)
            row["coord_residual"] = None if not cs else round(cs["mean_residual"], 4)
            flat.append(row)
    pd.DataFrame(flat).to_csv(os.path.join(OUT_DIR, "layout_comparison.csv"),
                              index=False, encoding="utf-8-sig")

    manifest = {
        "experiment_id": "phase2", "phase": 2, "status": "NEW",
        "hypothesis": "고정된 유사도를 2D 로 옮기는 방식에 따라 이웃 보존과 전역 구조가 달라진다",
        "user_meaning": "옆에 있는 향수가 실제로 비슷한가, 그리고 멀리 있는 지역이 실제로 더 다른가",
        "changed_variable": "2D 투영 방법 (유사도·스냅샷·모집단은 고정)",
        "population": ["global1000", "korea200"],
        "snapshot_hash": {"perfumes_csv": sha256(sm.PERFUMES_CSV),
                          "phase0_manifest": sha256(os.path.join(PHASE0, "manifest.json"))},
        "feature_version": "baseline (Phase 1 결과)",
        "seeds": list(SEEDS),
        "parameters": {"umap": "n_neighbors=10 min_dist=0.1 metric=precomputed",
                       "tsne": "perplexity=30 init=random metric=precomputed",
                       "pacmap": "n_neighbors=10, 특징행렬 입력 (precomputed 미지원)",
                       "trimap": "TorchTRIMAP n_inliers=10 n_outliers=5 n_random=5",
                       "knn_force": "k=10 상호 kNN 그래프 + spring_layout(iterations=60)",
                       "k_levels": list(K_LEVELS)},
        "primary_metrics": ["knn_overlap@5/10/20", "trustworthiness@5/10/20",
                            "continuity@5/10/20", "distance_rank_corr"],
        "guardrail_metrics": ["reminds_pct (사람 투표 신뢰 간선의 2D 근접도)"],
        "baseline_reference": BASELINE,
        "no_absolute_cutoff": ("overlap>=0.30 은 D2 의 UMAP 스윕 최저값이다. 다른 알고리즘의 "
                               "자동 탈락선으로 쓰지 않고 baseline 대비 상대 + Pareto 로 본다"),
        "pareto_front_global1000": front,
        "elapsed_sec": round(time.time() - t0, 1),
    }
    with open(os.path.join(OUT_DIR, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print()
    print(f"총 소요 {time.time()-t0:.0f}초")
    print(f"  -> {OUT_DIR}/ (metrics.json, manifest.json, layout_comparison.csv, "
          f"coordinates_*.csv)")


if __name__ == "__main__":
    main()

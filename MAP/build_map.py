"""향 지도 좌표 생성 파이프라인.

    python build_map.py

PLAN.md의 Step 0 -> 4를 순서대로 실행하고, 각 단계마다 완료 확인 수치를 출력한다.
사전에 측정해 둔 기댓값과 어긋나면 그 자리에서 알 수 있게 함께 찍는다.

Step 1(유사도 재현 검증)은 전체 코퍼스가 필요해 verify_similarity.py로 분리했다.
"""
import json
import os
import sys
import time

import numpy as np
import pandas as pd
from sklearn.cluster import AgglomerativeClustering
from sklearn.decomposition import PCA
from sklearn.manifold import MDS, trustworthiness

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import scent_map as sm

SEED = 42
N_NEIGHBORS_OUT = 10          # JSON에 실을 이웃 개수
CLUSTER_K_CANDIDATES = (8, 12, 16)
# k=8은 최대 클러스터가 411개(41%)라 "이 영역이 무슨 향인가"에 답이 안 된다.
# k=16은 leather/rose/green을 더 갈라주지만 색으로 구분 가능한 범위를 넘고
# 2~3개짜리 클러스터가 늘어난다. k=12는 411을 woody/warm spicy(183)와
# aromatic/citrus(226)로 쪼개 최대 23%로 낮추면서 라벨 수는 감당 가능하다.
CLUSTER_K = 12
UMAP_N_NEIGHBORS = (10, 15, 30)
UMAP_MIN_DIST = (0.1, 0.3)
RELIABLE_VOTES = 20           # EDA 07의 reliable 기준

# PLAN.md §3.5에서 사전 측정한 값. 재현되지 않으면 선정 로직이 달라진 것이다.
EXPECTED = {"groups": 4, "accords": 58, "brands": 223, "confident_edges": 872}

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")


# ==========================================================================
# Step 0
# ==========================================================================
def confident(e):
    return (e["up_votes"] >= 3) & (e["up_votes"] > e["down_votes"])


def edges_within(edges, id_set):
    return edges[edges["src"].isin(id_set) & edges["dst"].isin(id_set)]


def step0():
    print("=" * 74)
    print("Step 0 — 데이터 로드 및 대상 선정")
    print("=" * 74)

    df = sm.load_perfumes()
    print(f"전체 향수 {len(df)} / id 중복 {df['id'].duplicated().sum()} / "
          f"people 결측(JSONL) {int(df['people'].isna().sum())}")

    targets, quota = sm.select_targets(df)
    targets["display"] = sm.mark_display(targets)

    reminds = sm.load_edges("reminds_edges.csv")
    also = sm.load_edges("also_liked_edges.csv")
    ids = set(targets["id"])
    r_in = edges_within(reminds, ids)
    r_conf = r_in[confident(r_in)]
    a_in = edges_within(also, ids)

    got = {"groups": targets["group"].nunique(),
           "accords": targets["dominant_accord"].nunique(),
           "brands": targets["brand"].nunique(),
           "confident_edges": len(r_conf)}

    print(f"그룹 분포: {targets['group'].value_counts().reindex(sm.GROUP_ORDER).to_dict()}")
    print(f"선정 {len(targets)} / display {int(targets['display'].sum())} / "
          f"accord·note 보유 {int(targets['accord_list'].str.len().gt(0).sum())}·"
          f"{int(targets['note_set'].str.len().gt(0).sum())}")
    print(f"vote_count 최소 {targets['vote_count'].min()} 중앙 {int(targets['vote_count'].median())} / "
          f"also_liked 간선(진단용) {len(a_in)}")
    print("PLAN.md §3.5 재현:", end=" ")
    ok = all(got[k] == v for k, v in EXPECTED.items())
    print(" ".join(f"{k}={got[k]}({'OK' if got[k]==v else f'기대 {v}'})" for k, v in EXPECTED.items()))
    if not ok:
        print("  -> 값이 다르다. 선정 로직이나 입력이 달라졌다는 뜻이므로 원인을 확인할 것.")
    return df, targets, r_conf, a_in, reminds


def selection_comparison(df, targets, reminds):
    """인기순 top1000과 계열별 할당을 같은 기준으로 비교해 기록으로 남긴다.

    계열 할당은 커버리지를 얻는 대신 정답 간선을 잃는다. 그 대가가 얼마인지
    수치로 남겨야 나중에 "왜 이렇게 골랐나"에 답할 수 있다.
    """
    pool = sm.usable_pool(df)
    popularity_only = pool.sort_values("vote_count", ascending=False).head(len(targets))

    rows = []
    for label, sub in [("A_popularity_top1000", popularity_only),
                       ("B_group_then_accord", targets)]:
        ids = set(sub["id"])
        r_in = edges_within(reminds, ids)
        r_conf = r_in[confident(r_in)]
        bc = sub["brand"].value_counts()
        rows.append({
            "selection": label,
            "n": len(sub),
            "groups": sub["group"].nunique(),
            "accords": sub["dominant_accord"].nunique(),
            "brands": sub["brand"].nunique(),
            "top10_brand_share": round(100 * bc.head(10).sum() / len(sub), 1),
            "vote_count_min": int(sub["vote_count"].min()),
            "vote_count_median": int(sub["vote_count"].median()),
            "reminds_edges": len(r_in),
            "confident_edges": len(r_conf),
            "nodes_with_confident_edge": len(set(r_conf["src"]) | set(r_conf["dst"])),
        })
    out = pd.DataFrame(rows)
    os.makedirs(RESULTS_DIR, exist_ok=True)
    out.to_csv(os.path.join(RESULTS_DIR, "selection_comparison.csv"), index=False)
    print()
    print(out.to_string(index=False))
    print("  -> results/selection_comparison.csv 저장")


# ==========================================================================
# Step 2 — 2D 배치와 지표
# ==========================================================================
def knn_from_distance(D, k):
    """자기 자신을 뺀 최근접 k개의 인덱스."""
    Dm = D.copy()
    np.fill_diagonal(Dm, np.inf)
    return np.argpartition(Dm, kth=k, axis=1)[:, :k]


def knn_overlap(D_high, coords, k=10):
    from scipy.spatial.distance import squareform, pdist
    D_low = squareform(pdist(coords))
    a = knn_from_distance(D_high, k)
    b = knn_from_distance(D_low, k)
    return float(np.mean([len(set(x) & set(y)) / k for x, y in zip(a, b)]))


def edge_distance_percentile(coords, index_of, edges):
    """정답 간선 파트너가 2D에서 얼마나 가까운지 (0=가장 가까움, 0.5=무작위)."""
    from scipy.spatial.distance import squareform, pdist
    D_low = squareform(pdist(coords))
    n = len(coords)
    pcts = []
    for src, dst in edges:
        i, j = index_of[src], index_of[dst]
        if i == j:
            continue
        row = D_low[i].copy()
        row[i] = np.inf
        rank = int((row < D_low[i, j]).sum())
        pcts.append(rank / (n - 1))
    return float(np.mean(pcts)), len(pcts)


def evaluate_layout(coords, D_high, index_of, conf_edges):
    t10 = trustworthiness(D_high, coords, n_neighbors=10, metric="precomputed")
    t20 = trustworthiness(D_high, coords, n_neighbors=20, metric="precomputed")
    ov = knn_overlap(D_high, coords, k=10)
    pct, n_used = edge_distance_percentile(coords, index_of, conf_edges)
    return {"trust@10": t10, "trust@20": t20, "knn_overlap@10": ov,
            "reminds_pct": pct, "n_edges": n_used}


def step2(D, index_of, conf_edges, also_edges, features):
    print()
    print("=" * 74)
    print("Step 2 — 2D 배치")
    print("=" * 74)
    import umap

    layouts = {}
    rng = np.random.default_rng(SEED)
    layouts["random"] = rng.random((len(D), 2))
    layouts["pca"] = PCA(n_components=2, random_state=SEED).fit_transform(features)

    t = time.time()
    layouts["mds"] = MDS(n_components=2, dissimilarity="precomputed", random_state=SEED,
                         n_init=1, max_iter=300, normalized_stress=False).fit_transform(D)
    print(f"  mds 완료 ({time.time()-t:.0f}s)")

    for nn in UMAP_N_NEIGHBORS:
        for md in UMAP_MIN_DIST:
            t = time.time()
            reducer = umap.UMAP(n_components=2, metric="precomputed", n_neighbors=nn,
                                min_dist=md, random_state=SEED)
            layouts[f"umap_nn{nn}_md{md}"] = reducer.fit_transform(D)
            print(f"  umap nn={nn} min_dist={md} 완료 ({time.time()-t:.0f}s)")

    rows = []
    for name, coords in layouts.items():
        m = evaluate_layout(np.asarray(coords, dtype=float), D, index_of, conf_edges)
        m["layout"] = name
        rows.append(m)
    res = pd.DataFrame(rows)[["layout", "trust@10", "trust@20", "knn_overlap@10",
                              "reminds_pct", "n_edges"]]

    print()
    print("  trust@k: 2D에서 가까운 점이 실제로도 가까운가 (1에 가까울수록 좋음)")
    print("  knn_overlap@10: 고차원 이웃 10개 중 2D 이웃 10개와 겹치는 비율")
    print("  reminds_pct: 정답 간선 파트너의 2D 거리 백분위 (낮을수록 좋음, 0.5=무작위)")
    print()
    print(res.to_string(index=False, float_format=lambda v: f"{v:.4f}"))

    # 진단용 (합격 판정에는 쓰지 않는다)
    print()
    print("  [진단] also_liked 기준 reminds_pct — 정답 라벨이 아니라 방향성 확인용")
    diag = {name: edge_distance_percentile(np.asarray(c, float), index_of, also_edges)[0]
            for name, c in layouts.items()}
    print("  " + "  ".join(f"{k}={v:.4f}" for k, v in diag.items()))
    res["also_liked_pct"] = res["layout"].map(diag)

    umap_rows = res[res["layout"].str.startswith("umap")]
    best = umap_rows.loc[umap_rows["knn_overlap@10"].idxmax(), "layout"]
    print()
    print(f"  채택: {best}")
    baseline = res.set_index("layout")
    for ref in ["random", "pca"]:
        won = (baseline.loc[best, "trust@10"] > baseline.loc[ref, "trust@10"]
               and baseline.loc[best, "knn_overlap@10"] > baseline.loc[ref, "knn_overlap@10"]
               and baseline.loc[best, "reminds_pct"] < baseline.loc[ref, "reminds_pct"])
        print(f"  {ref} 대비 세 지표 모두 우위: {'예' if won else '아니오 — 개선을 주장하지 말 것'}")

    return layouts, best, res


# ==========================================================================
# Step 3 — 클러스터
# ==========================================================================
def region_cohesion(coords, labels, k=10):
    """2D에서 최근접 k개 중 같은 라벨인 비율. 라벨이 실제 '영역'을 이루는지 본다.

    무작위 기대값은 라벨 크기 비율의 제곱합이다. 그보다 충분히 높아야
    프론트가 색으로 영역을 칠하는 게 의미가 있다.
    """
    from scipy.spatial.distance import squareform, pdist
    labels = np.asarray(labels)
    Dl = squareform(pdist(np.asarray(coords, float)))
    np.fill_diagonal(Dl, np.inf)
    nn = np.argpartition(Dl, k, axis=1)[:, :k]
    observed = float((labels[nn] == labels[:, None]).mean())
    _, counts = np.unique(labels, return_counts=True)
    expected = float(((counts / len(labels)) ** 2).sum())
    per = {}
    for v in np.unique(labels):
        idx = np.flatnonzero(labels == v)
        per[str(v)] = round(float((labels[nn[idx]] == v).mean()), 3)
    return observed, expected, per


def step3(D, targets, S):
    print()
    print("=" * 74)
    print("Step 3 — 클러스터 라벨")
    print("=" * 74)
    chosen = {}
    for k in CLUSTER_K_CANDIDATES:
        labels = AgglomerativeClustering(n_clusters=k, metric="precomputed",
                                         linkage="average").fit_predict(D)
        sizes = np.bincount(labels)
        print(f"\n  k={k}  크기 {sorted(sizes.tolist(), reverse=True)}")
        for c in range(k):
            idx = np.flatnonzero(labels == c)
            acc = {}
            for i in idx:
                for name, strength in targets.iloc[i]["accord_list"]:
                    acc[name] = acc.get(name, 0.0) + strength
            top = sorted(acc.items(), key=lambda x: -x[1])[:3]
            print(f"    c{c:<2} n={len(idx):<4} {[t[0] for t in top]}")
        chosen[k] = labels
    return chosen


# ==========================================================================
# Step 4 — JSON 산출
# ==========================================================================
def normalize_uniform(coords):
    """[0,1]로 줄이되 x·y에 같은 배율을 쓴다.

    축별로 따로 정규화하면 종횡비가 깨져 UMAP이 만든 거리 구조가 왜곡된다.
    """
    c = np.asarray(coords, dtype=float)
    c = c - c.min(axis=0)
    scale = c.max()
    if scale > 0:
        c = c / scale
    return c


def season_block(row):
    s = {k: float(row[k]) for k in ["winter", "spring", "summer", "autumn"]}
    total = sum(s.values())
    if pd.isna(row["people"]) or total < RELIABLE_VOTES:
        return None
    return {k: round(v / total, 4) for k, v in s.items()}


def daypart_block(row):
    d = {k: float(row[k]) for k in ["day", "night"]}
    total = sum(d.values())
    if pd.isna(row["people"]) or total < RELIABLE_VOTES:
        return None
    return {k: round(v / total, 4) for k, v in d.items()}


def step4(targets, coords, labels, S, metrics, layout_name, conf_edge_pairs):
    print()
    print("=" * 74)
    print("Step 4 — 이웃 목록 및 JSON 산출")
    print("=" * 74)
    os.makedirs(OUT_DIR, exist_ok=True)
    xy = normalize_uniform(coords)

    # neighbors는 2D 거리가 아니라 고차원 유사도로 만든다.
    Sm = S.copy()
    np.fill_diagonal(Sm, -np.inf)
    top = np.argpartition(-Sm, kth=N_NEIGHBORS_OUT, axis=1)[:, :N_NEIGHBORS_OUT]
    ids = targets["id"].to_numpy()

    clusters = []
    for c in sorted(set(labels.tolist())):
        idx = np.flatnonzero(labels == c)
        acc = {}
        for i in idx:
            for name, strength in targets.iloc[i]["accord_list"]:
                acc[name] = acc.get(name, 0.0) + strength
        clusters.append({"id": int(c), "size": int(len(idx)),
                         "top_accords": [t[0] for t in sorted(acc.items(), key=lambda x: -x[1])[:3]]})

    perfumes = []
    for i in range(len(targets)):
        r = targets.iloc[i]
        order = top[i][np.argsort(-Sm[i, top[i]])]
        perfumes.append({
            "id": int(r["id"]),
            "name": r["name"],
            "brand": r["brand"],
            "year": None if pd.isna(r["year"]) else int(r["year"]),
            "gender": r["gender"],
            "x": round(float(xy[i, 0]), 5),
            "y": round(float(xy[i, 1]), 5),
            "cluster": int(labels[i]),
            "group": r["group"],
            "family": r["family"],
            "dominant_accord": r["dominant_accord"],
            "display": bool(r["display"]),
            "top_accords": [{"name": n, "strength": int(s)} for n, s in r["accord_list"][:5]],
            "seasons": season_block(r),
            "daypart": daypart_block(r),
            "neighbors": [{"id": int(ids[j]), "sim": round(float(Sm[i, j]), 4)} for j in order],
        })

    groups = [{"id": g, "size": int((targets["group"] == g).sum())}
              for g in sm.GROUP_ORDER if (targets["group"] == g).any()]

    doc = {
        "version": "v1",
        "similarity": {"accord_weight": 0.5, "note_weight": 0.5,
                       "note_weighting": "idf", "source": "EDA 04-06"},
        "layout": {"method": layout_name, "random_state": SEED,
                   "normalization": "[0,1], uniform scale on x and y",
                   "trustworthiness_at_10": round(float(metrics["trust@10"]), 4),
                   "knn_overlap_at_10": round(float(metrics["knn_overlap@10"]), 4),
                   "distance_is_metric": False},
        "groups": groups,
        "clusters": clusters,
        "perfumes": perfumes,
    }
    path = os.path.join(OUT_DIR, "scent_map_v1.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))

    # 검증 뷰어(map_preview.html) 전용. 백엔드 전달 대상이 아니다.
    diag_path = os.path.join(OUT_DIR, "diagnostic_edges.json")
    with open(diag_path, "w", encoding="utf-8") as f:
        json.dump({"reminds_confident": [[int(a), int(b)] for a, b in conf_edge_pairs]},
                  f, separators=(",", ":"))

    size_mb = os.path.getsize(path) / 1024 / 1024
    all_ids = {p["id"] for p in perfumes}
    print(f"  파일 {path}  ({size_mb:.2f} MB)")
    print(f"  엔트리 {len(perfumes)} / display {sum(p['display'] for p in perfumes)}")
    print(f"  x,y 범위 [{xy.min():.4f}, {xy.max():.4f}] / NaN {int(np.isnan(xy).sum())}")
    print(f"  종횡비 유지: x폭 {xy[:,0].max()-xy[:,0].min():.4f}, y폭 {xy[:,1].max()-xy[:,1].min():.4f} "
          f"(한쪽만 1.0이어야 정상)")
    dangling = sum(1 for p in perfumes for nb in p["neighbors"] if nb["id"] not in all_ids)
    print(f"  파일 밖을 가리키는 neighbor: {dangling}")
    print(f"  진단용 간선 파일 {diag_path}")
    print(f"  그룹 분포 {[(g['id'], g['size']) for g in groups]}")
    print(f"  seasons 있는 향수 {sum(p['seasons'] is not None for p in perfumes)} / "
          f"daypart {sum(p['daypart'] is not None for p in perfumes)}")
    return path


def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    df, targets, conf_edges, also_edges, reminds = step0()
    selection_comparison(df, targets, reminds)

    idf_map = sm.load_note_idf()
    S, s_acc, s_note = sm.base_similarity(list(targets["accord_list"]),
                                          list(targets["note_set"]), idf_map)
    D = 1.0 - S
    np.fill_diagonal(D, 0.0)
    index_of = {int(v): i for i, v in enumerate(targets["id"])}

    A, _ = sm.build_accord_matrix(list(targets["accord_list"]))
    B, w, _, _ = sm.build_note_matrix(list(targets["note_set"]), idf_map)
    Bn = B * w
    norm = np.linalg.norm(Bn, axis=1, keepdims=True); norm[norm == 0] = 1
    features = np.hstack([A, Bn / norm])

    ce = [(int(a), int(b)) for a, b in conf_edges[["src", "dst"]].itertuples(index=False, name=None)]
    ae = [(int(a), int(b)) for a, b in also_edges[["src", "dst"]].itertuples(index=False, name=None)]

    layouts, best, res = step2(D, index_of, ce, ae, features)

    os.makedirs(RESULTS_DIR, exist_ok=True)
    res.to_csv(os.path.join(RESULTS_DIR, "layout_comparison.csv"), index=False)
    print(f"\n  -> results/layout_comparison.csv 저장")

    cluster_labels = step3(D, targets, S)
    print(f"\n  채택: k={CLUSTER_K} (선택 근거는 build_map.py 상단 주석과 DECISIONS.md 참조)")

    # 가장 중요한 확인 — 4대 그룹이 유사도 기반 지도 위에서 실제로 영역을 이루는가.
    # 이루지 않으면 프론트가 색으로 4개 영역을 칠하는 것 자체가 성립하지 않는다.
    coords = np.asarray(layouts[best], dtype=float)
    print()
    print("  [라벨이 지도에서 영역을 이루는가]  응집도 = 2D 최근접 10개 중 같은 라벨 비율")
    for name, lab in [("4대 그룹", targets["group"].to_numpy()),
                      (f"클러스터 k={CLUSTER_K}", cluster_labels[CLUSTER_K])]:
        obs, exp, per = region_cohesion(coords, lab)
        print(f"    {name:<14} {obs:.3f}  (무작위 {exp:.3f} → {obs/exp:.1f}배)")
        print(f"    {'':14}   {per}")

    metrics = res.set_index("layout").loc[best]
    step4(targets, layouts[best], cluster_labels[CLUSTER_K], S, metrics, best, ce)


if __name__ == "__main__":
    main()

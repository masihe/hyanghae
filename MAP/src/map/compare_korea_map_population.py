"""국내 지도의 레이아웃 모집단을 A/B로 비교한다 (Phase A2 선행 결정).

Run with venv/Scripts/python.exe src/map/compare_korea_map_population.py

문제: 밀도 지형(높이맵)을 200개 점으로 만들면 지형이 200개의 우연한 배치를 그린다.
게다가 200개 안에는 사람이 "닮았다"고 투표한 신뢰 간선이 40개뿐이라 배치가 맞는지
판정할 근거가 거의 없다.

A안 = 국내 200개만으로 배치 (현재 방식)
B안 = 국내 200개 ∪ 글로벌 대상 1,000개(= 1,140개)로 배치하고 200개만 display

바꾸는 것은 배치 모집단 하나다. 유사도 정의, UMAP 파라미터(nn=10, md=0.1),
표시 대상 200개는 양쪽 모두 같다.

지표는 전부 "표시 200개"를 기준으로 재서 두 안을 같은 조건에서 비교한다.
시드를 5개 돌려 한 번의 우연이 아닌지 본다.
"""
import json
import os
import sys

import numpy as np
import pandas as pd
from scipy.linalg import orthogonal_procrustes
from scipy.ndimage import label as cc_label
from scipy.spatial.distance import pdist, squareform
from scipy.stats import gaussian_kde
from sklearn.manifold import trustworthiness

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "common")))
import scent_map as sm

MAP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))  # MAP/
V2_PATH = os.path.join(MAP_DIR, "output", "korea_scent_map_v2.json")
GLOBAL_PATH = os.path.join(MAP_DIR, "output", "scent_map_v1.json")
OUT_CSV = os.path.join(MAP_DIR, "results", "korea_population_comparison.csv")

SEEDS = (42, 1, 2, 3, 4)
N_NEIGHBORS = 10
MIN_DIST = 0.1
GRID = 128           # 밀도 격자 한 변
SEA_PERCENTILE = 55  # 육지/바다 임계. 임의값이며 프론트 조정 대상이다


def base_distance(rows, idf):
    similarity, _, _ = sm.base_similarity(rows.accord_list.tolist(), rows.note_set.tolist(), idf)
    d = 1.0 - similarity
    np.fill_diagonal(d, 0.0)
    return d


def knn_sets(distance, k):
    d = distance.copy()
    np.fill_diagonal(d, np.inf)
    return [set(row) for row in np.argpartition(d, kth=k, axis=1)[:, :k]]


def knn_overlap(high, coords, k):
    low = squareform(pdist(coords))
    a, b = knn_sets(high, k), knn_sets(low, k)
    return float(np.mean([len(x & y) / k for x, y in zip(a, b)]))


def reminds_percentile(coords, index_of, edges):
    """정답 쌍의 2D 거리가 그 향수 기준 몇 번째 백분위인지. 낮을수록 좋다. 무작위 0.5."""
    low = squareform(pdist(coords))
    np.fill_diagonal(low, np.inf)
    values = []
    for src, dst in edges:
        i, j = index_of[src], index_of[dst]
        row = low[i]
        rank = int((row < row[j]).sum())
        values.append(rank / (len(row) - 1))
    return float(np.mean(values)) if values else float("nan")


def align(coords, reference):
    """Procrustes 정합. UMAP 좌표는 시드마다 회전·반사가 달라 그냥 비교할 수 없다."""
    a = coords - coords.mean(axis=0)
    b = reference - reference.mean(axis=0)
    a = a / np.linalg.norm(a)
    b = b / np.linalg.norm(b)
    r, _ = orthogonal_procrustes(a, b)
    return a @ r


def density_grid(coords, bounds):
    """가우시안 KDE 격자. bounds 를 고정해 시드 간 같은 프레임에서 비교한다."""
    (x0, x1), (y0, y1) = bounds
    gx, gy = np.mgrid[x0:x1:complex(0, GRID), y0:y1:complex(0, GRID)]
    kde = gaussian_kde(coords.T)  # bandwidth 는 scott 기본값
    values = kde(np.vstack([gx.ravel(), gy.ravel()])).reshape(GRID, GRID)
    return values / values.max()


def land_components(grid):
    threshold = np.percentile(grid, SEA_PERCENTILE)
    _, count = cc_label(grid > threshold)
    return int(count)


def main():
    korea = json.loads(open(V2_PATH, encoding="utf-8").read())
    display_ids = [p["fragrantica_id"] for p in korea["points"]]
    global_ids = [p["id"] for p in json.loads(open(GLOBAL_PATH, encoding="utf-8").read())["perfumes"]]
    union_ids = display_ids + [i for i in global_ids if i not in set(display_ids)]

    edges = sm.load_edges("reminds_edges.csv")
    trusted = edges[(edges.up_votes >= 3) & (edges.up_votes > edges.down_votes)]

    perfumes = sm.load_perfumes().set_index("id")
    idf = sm.load_note_idf()

    arms = {"A_display_only": display_ids, "B_union_with_global": union_ids}
    display_set = set(display_ids)
    rows_out = []

    for arm, ids in arms.items():
        pos = {pid: i for i, pid in enumerate(ids)}
        rows = perfumes.loc[ids].reset_index()
        distance = base_distance(rows, idf)

        # 표시 200개 부분집합의 고차원 거리 — 두 안을 같은 조건으로 재기 위한 기준
        sub = np.array([pos[p] for p in display_ids])
        d_sub = distance[np.ix_(sub, sub)]
        sub_index = {pid: i for i, pid in enumerate(display_ids)}

        in_arm = trusted[trusted.src.isin(pos) & trusted.dst.isin(pos)]
        internal = [(s, d) for s, d in zip(in_arm.src, in_arm.dst)
                    if s in display_set and d in display_set]
        incident = [(s, d) for s, d in zip(in_arm.src, in_arm.dst)
                    if s in display_set or d in display_set]
        nodes_with_edge = len({n for e in incident for n in e} & display_set)
        print(f"[{arm}] n={len(ids)} 신뢰간선 내부={len(internal)} 인접={len(incident)} "
              f"간선보유 표시향수={nodes_with_edge}/200", flush=True)

        import umap
        reference = None
        for seed in SEEDS:
            coords = umap.UMAP(n_components=2, metric="precomputed", n_neighbors=N_NEIGHBORS,
                               min_dist=MIN_DIST, random_state=seed).fit_transform(distance)
            coords = np.asarray(coords, dtype=float)
            disp = coords[sub]

            aligned = align(coords, coords if reference is None else reference)
            if reference is None:
                reference = coords
                ref_grid = None
            bounds = ((aligned[:, 0].min(), aligned[:, 0].max()),
                      (aligned[:, 1].min(), aligned[:, 1].max()))
            grid = density_grid(aligned, bounds)
            if seed == SEEDS[0]:
                ref_grid = grid
            corr = float(np.corrcoef(ref_grid.ravel(), grid.ravel())[0, 1])

            rows_out.append({
                "arm": arm, "n_points": len(ids), "seed": seed,
                "trust_at_10_display": trustworthiness(d_sub, disp, n_neighbors=10, metric="precomputed"),
                "trust_at_20_display": trustworthiness(d_sub, disp, n_neighbors=20, metric="precomputed"),
                "knn_overlap_at_10_display": knn_overlap(d_sub, disp, 10),
                "reminds_pct_internal": reminds_percentile(disp, sub_index, internal),
                "reminds_pct_incident_arm": reminds_percentile(coords, pos, incident),
                "trusted_internal": len(internal),
                "trusted_incident": len(incident),
                "display_nodes_with_edge": nodes_with_edge,
                "land_components": land_components(grid),
                "grid_corr_vs_first_seed": corr,
            })
            print(f"   seed {seed}: trust@10 {rows_out[-1]['trust_at_10_display']:.4f} "
                  f"overlap {rows_out[-1]['knn_overlap_at_10_display']:.4f} "
                  f"reminds {rows_out[-1]['reminds_pct_internal']:.4f} "
                  f"육지 {rows_out[-1]['land_components']} 격자상관 {corr:.4f}", flush=True)

    out = pd.DataFrame(rows_out)
    out.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")

    print()
    print("=== 시드 5개 요약 (표시 200개 기준) ===")
    agg = out.groupby("arm").agg(
        trust10_mean=("trust_at_10_display", "mean"), trust10_std=("trust_at_10_display", "std"),
        overlap_mean=("knn_overlap_at_10_display", "mean"), overlap_std=("knn_overlap_at_10_display", "std"),
        reminds_internal_mean=("reminds_pct_internal", "mean"),
        reminds_incident_mean=("reminds_pct_incident_arm", "mean"),
        land_min=("land_components", "min"), land_max=("land_components", "max"),
        grid_corr_min=("grid_corr_vs_first_seed", "min"),
        edges_internal=("trusted_internal", "first"), edges_incident=("trusted_incident", "first"),
        nodes_with_edge=("display_nodes_with_edge", "first"))
    print(agg.round(4).to_string())
    print()
    print(OUT_CSV)


if __name__ == "__main__":
    main()

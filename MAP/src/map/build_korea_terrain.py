"""국내 200개 지도에 밀도 지형·영역·등고선을 채운다 (Phase A2 산출).

Run with venv/Scripts/python.exe src/map/build_korea_terrain.py

좌표는 건드리지 않는다. korea_scent_map_v2.json 의 terrain / regions / contours /
points[].region 만 채워 같은 파일에 다시 쓴다.

파라미터 근거는 results/korea_terrain_comparison.csv 스윕과 DECISIONS.md D12 다.
  - 방법: Gaussian KDE (비교군 히스토그램+블러와 격자 상관 0.9841 — 방법 의존성 없음)
  - bandwidth: scott x 0.5
  - sea_level: 밀도 하위 60 백분위
  - 클러스터: Agglomerative(average, precomputed) k=4
    (기존 선택 규칙 재사용 — 최소 군집 >= 3, 최대 비중 <= 0.5, 그중 silhouette 최대)

영역 라벨은 빈도가 아니라 두드러짐(lift)으로 만든다. woody 는 전체 향수의 61.7%에
있는 배경이라 빈도로 뽑으면 어느 무리에서든 상위에 온다.
"""
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import gaussian_kde
from sklearn.cluster import AgglomerativeClustering
from sklearn.metrics import silhouette_score

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "common")))
import scent_map as sm

MAP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))  # MAP/
V2_PATH = os.path.join(MAP_DIR, "output", "korea_scent_map_v2.json")
ACCORD_DICT = os.path.join(os.path.dirname(MAP_DIR), "EDA", "analysis_outputs", "10_accord_dictionary.csv")

GRID_WIDTH = 128
MARGIN = 0.05
BANDWIDTH_SCALE = 0.5
SEA_PERCENTILE = 60
# 군집 수는 규칙으로 고른다. 상수로 굳히면 대표 200개가 바뀔 때 조용히 썩는다 —
# 실제로 그렇게 됐다: 잠정 200개에서 고른 k=4 가 새 200개에서 [176,15,5,4] 로 무너졌고
# (최대 비중 0.88) D12 가 기록한 "최대 비중 <= 0.5" 규칙을 위반한 채 통과했다.
CLUSTER_K_RANGE = range(2, 13)
CLUSTER_MIN_SIZE = 3      # 이보다 작은 군집이 있으면 탈락
CLUSTER_MAX_SHARE = 0.5   # 한 군집이 이 비중을 넘으면 탈락
EXPECTED_CLUSTER_K = 7    # 규칙이 고른 값. 달라지면 조용히 넘기지 않고 보고한다.

# 군집 간 거리를 무엇으로 재는가. 값을 갈아끼워 실험할 수 있게 상수로 둔다.
# average = 평균, complete = 최댓값. 어느 쪽이 나은지는 아직 결정되지 않았다.
CLUSTER_LINKAGE = "average"
LABEL_MIN_COVERAGE = 0.30
LABEL_TOP_N = 3
SEA_REGION_ID = 255
MIN_CLUSTER_FOR_KDE = 3

# 이 지형은 UMAP 시드에 흔들린다. 실측(2026-09-07): 같은 200개·같은 파라미터로 시드 5개를
# 돌려 Procrustes 정합 후 비교하면 섬 수가 2~5 로 변하고 밀도 격자 상관이 최소 0.45 다.
# 반면 좌표의 이웃 구조는 안정적이다 (trust@10 표준편차 0.0015, kNN overlap 0.0035).
#
# 즉 **해안선과 섬 개수는 향수에 대한 발견이 아니라 레이아웃 시드에 따른 렌더링 결과다.**
# 프론트는 이걸 밀도 표현의 재료로 쓰되 "향 계열 경계" 로 해석해서는 안 된다.
# 영역(regions) 은 좌표가 아니라 원공간 유사도로 나눈 것이므로 시드와 무관하다.
SEED_STABILITY = {
    "measured_at": "2026-09-07",
    "seeds": [42, 1, 2, 3, 4],
    "alignment": "orthogonal Procrustes (UMAP 좌표는 시드마다 회전·반사가 달라 정합 없이 비교 불가)",
    "island_count_range": [2, 5],
    "density_grid_correlation": {"min": 0.4513, "median": 0.5457, "max": 0.7842},
    "layout_neighbor_stability": {"trust_at_10_std": 0.0015, "knn_overlap_at_10_std": 0.0035},
    "reading": ("좌표와 이웃 관계는 시드에 안정적이다. 해안선·섬 개수는 아니다. "
                "sea_level 을 조정해 표현을 바꾸는 것은 안전하지만, 섬의 개수나 "
                "경계를 향 계열의 구분으로 설명하면 안 된다"),
    "note": "regions 블록은 2D 좌표가 아니라 원공간 유사도 군집이라 이 불안정성에 해당하지 않는다",
}  # KDE는 점이 최소 3개 필요하다


def choose_clusters(distance):
    """D12 의 선택 규칙을 매 실행마다 다시 적용한다.

    최소 군집 >= CLUSTER_MIN_SIZE, 최대 비중 <= CLUSTER_MAX_SHARE 를 만족하는 k 중
    silhouette 이 가장 큰 것. 통과하는 k 가 없으면 그 자리에서 멈춘다 —
    규칙을 만족하지 못하는 군집을 지도 영역으로 내보내지 않는다.
    """
    rows, best = [], None
    for k in CLUSTER_K_RANGE:
        labels = AgglomerativeClustering(n_clusters=k, metric="precomputed",
                                         linkage=CLUSTER_LINKAGE).fit_predict(distance)
        sil = float(silhouette_score(distance, labels, metric="precomputed"))
        sizes = np.bincount(labels, minlength=k)
        passes = sizes.min() >= CLUSTER_MIN_SIZE and sizes.max() / len(labels) <= CLUSTER_MAX_SHARE
        rows.append((k, sil, int(sizes.min()), sizes.max() / len(labels), passes))
        if passes and (best is None or sil > best[1]):
            best = (k, sil, sizes, labels)
    print("클러스터 수 선택 (최소 군집 >= "
          f"{CLUSTER_MIN_SIZE}, 최대 비중 <= {CLUSTER_MAX_SHARE}, 그중 silhouette 최대)")
    for k, sil, lo, share, passes in rows:
        print(f"  k={k:<3} silhouette {sil:.4f}  최소 {lo:<4} 최대 비중 {share:.4f}  "
              f"{'통과' if passes else '탈락'}")
    if best is None:
        raise RuntimeError("규칙을 통과하는 k 가 없다. 규칙 자체를 재검토할 것")
    k, sil, sizes, labels = best
    print(f"  -> k={k} 채택 (silhouette {sil:.4f}, 크기 {sorted(sizes.tolist(), reverse=True)})")
    if k != EXPECTED_CLUSTER_K:
        print(f"  ** 기대값 k={EXPECTED_CLUSTER_K} 와 다르다. 대표 향수 구성이 바뀐 것이므로 확인할 것 **")
    return labels, sil, sizes, k


def make_grid(coords):
    lo = coords.min(axis=0) - MARGIN
    hi = coords.max(axis=0) + MARGIN
    height = int(round(GRID_WIDTH * (hi[1] - lo[1]) / (hi[0] - lo[0])))
    xs = np.linspace(lo[0], hi[0], GRID_WIDTH)
    ys = np.linspace(lo[1], hi[1], height)
    gx, gy = np.meshgrid(xs, ys)  # row = y, col = x
    return lo, hi, GRID_WIDTH, height, np.vstack([gx.ravel(), gy.ravel()]), xs, ys


def density(points, sample, width, height):
    kde = gaussian_kde(points.T)
    kde.set_bandwidth(kde.factor * BANDWIDTH_SCALE)
    return kde(sample).reshape(height, width)


def cell_index(coords, lo, hi, width, height):
    col = np.clip(((coords[:, 0] - lo[0]) / (hi[0] - lo[0]) * (width - 1)).round().astype(int), 0, width - 1)
    row = np.clip(((coords[:, 1] - lo[1]) / (hi[1] - lo[1]) * (height - 1)).round().astype(int), 0, height - 1)
    return row, col


def region_labels(rows, labels, corpus_share):
    """클러스터별 두드러짐(lift) 상위 accord. 향수당 accord 8개 전체를 쓴다."""
    out = {}
    for c in sorted(set(labels)):
        members = rows.loc[labels == c, "accord_list"]
        n = len(members)
        counts = {}
        for lst in members:
            for name, _ in lst:
                counts[name] = counts.get(name, 0) + 1
        scored = []
        for name, hits in counts.items():
            coverage = hits / n
            share = corpus_share.get(name)
            if coverage < LABEL_MIN_COVERAGE or not share:
                continue
            scored.append({"name": name, "lift": round(coverage / share, 2),
                           "coverage": round(coverage, 4)})
        scored.sort(key=lambda d: -d["lift"])
        out[int(c)] = scored[:LABEL_TOP_N]
    return out


def mask_polygons(mask, xs, ys):
    """마스크 경계를 등고선으로 뽑는다. 월경지(내부 구멍·분리 조각)가 그대로 보존된다."""
    fig, ax = plt.subplots()
    cs = ax.contour(xs, ys, mask.astype(float), levels=[0.5])
    polygons = []
    for path in cs.get_paths():
        for poly in path.to_polygons(closed_only=False):
            if len(poly) >= 4:
                polygons.append([[round(float(x), 5), round(float(y), 5)] for x, y in poly])
    plt.close(fig)
    return polygons


def main():
    doc = json.loads(open(V2_PATH, encoding="utf-8").read())
    ids = [p["fragrantica_id"] for p in doc["points"]]
    coords = np.array([[p["x"], p["y"]] for p in doc["points"]], dtype=float)
    assert len(ids) == 200

    perfumes = sm.load_perfumes().set_index("id")
    rows = perfumes.loc[ids].reset_index()
    idf = sm.load_note_idf()
    similarity, _, _ = sm.base_similarity(rows.accord_list.tolist(), rows.note_set.tolist(), idf)
    distance = 1.0 - similarity
    np.fill_diagonal(distance, 0.0)

    labels, sil, sizes, cluster_k = choose_clusters(distance)

    lo, hi, width, height, sample, xs, ys = make_grid(coords)
    total = density(coords, sample, width, height)
    total = total / total.max()
    sea_value = float(np.percentile(total, SEA_PERCENTILE))

    # 출하하는 것은 uint8 격자다. 그래서 육지 판정도 그 격자로 한다.
    # float 마스크를 기준으로 삼으면 프론트가 격자로 계산한 육지와 어긋난다(실측 186 vs 184).
    # 양자화가 lossy 해서 경계 셀들이 같은 값으로 뭉치므로 float 마스크의 정확한 재현은
    # 원리적으로 불가능하다. 그러니 격자를 진실로 두고 통계를 거기서 뽑는다.
    quantized = np.round(total * 255).astype(np.uint8)
    sea_level_u8 = int(round(sea_value * 255))
    land = quantized > sea_level_u8
    float_land = total > sea_value
    shifted = int((land != float_land).sum())
    print(f"격자 {width}x{height} | sea_level {sea_value:.4f} -> uint8 {sea_level_u8} | 육지 {land.mean():.1%}")
    print(f"양자화로 판정이 바뀐 셀 {shifted}/{land.size} ({shifted/land.size:.2%}) — 격자 기준으로 통일한다")

    per_cluster = np.zeros((cluster_k, height, width))
    for c in range(cluster_k):
        member = coords[labels == c]
        if len(member) >= MIN_CLUSTER_FOR_KDE:
            g = density(member, sample, width, height)
            per_cluster[c] = g / g.max()
    region_grid = per_cluster.argmax(axis=0).astype(np.uint8)
    region_grid[~land] = SEA_REGION_ID

    accord_dict = pd.read_csv(ACCORD_DICT)
    corpus_share = dict(zip(accord_dict.accord, accord_dict.perfume_share))
    labels_by_region = region_labels(rows, labels, corpus_share)

    row_idx, col_idx = cell_index(coords, lo, hi, width, height)
    regions = []
    for c in range(cluster_k):
        mask = region_grid == c
        if mask.any():
            flat = np.where(mask.ravel(), (per_cluster[c] * mask).ravel(), -1)
            peak = int(flat.argmax())
            anchor = {"x": round(float(xs[peak % width]), 5), "y": round(float(ys[peak // width]), 5)}
        else:
            anchor = None
        regions.append({
            "id": c,
            "size": int(sizes[c]),
            "points_on_land": int(((labels == c) & land[row_idx, col_idx]).sum()),
            "grid_cells": int(mask.sum()),
            "label_accords": labels_by_region[c],
            "name_ko": None,
            "label_anchor": anchor,
            "polygon": mask_polygons(mask, xs, ys),
        })
        acc = " · ".join(f"{a['name']}({a['lift']}x)" for a in labels_by_region[c])
        print(f"  region {c}: 향수 {sizes[c]:>3} 격자 {mask.sum():>5}  {acc}")

    doc["terrain"] = {
        "method": "gaussian_kde",
        "bandwidth": "scott x 0.5",
        "bandwidth_scale": BANDWIDTH_SCALE,
        "grid_width": width,
        "grid_height": height,
        "bounds": {"x_min": round(float(lo[0]), 5), "x_max": round(float(hi[0]), 5),
                   "y_min": round(float(lo[1]), 5), "y_max": round(float(hi[1]), 5)},
        "encoding": "row_major_uint8",
        "row_order": "row 0 = y_min, 마지막 row = y_max. col 0 = x_min",
        "value_range": [0, 255],
        "values": quantized.ravel().tolist(),
        "sea_level": sea_level_u8,
        "sea_level_basis": f"밀도 하위 {SEA_PERCENTILE} 백분위. 육지 = values > sea_level. "
                           f"프론트가 조정하는 값이다",
        "land_area_share": round(float(land.mean()), 4),
        "points_on_land": int(land[row_idx, col_idx].sum()),
        "quantization_note": f"육지 판정은 이 uint8 격자 기준이다. float 밀도 대비 "
                             f"판정이 바뀐 셀 {shifted}개 ({shifted / land.size:.2%})",
        "source": "results/korea_terrain_comparison.csv (파라미터 스윕), DECISIONS.md D12",
        "seed_stability": SEED_STABILITY,
    }
    doc["regions"] = {
        "cluster_method": f"agglomerative {CLUSTER_LINKAGE} linkage on precomputed base-similarity distance",
        "cluster_count": cluster_k,
        "silhouette": round(sil, 4),
        "label_rule": f"클러스터 내 coverage >= {LABEL_MIN_COVERAGE} 인 accord 중 "
                      f"(클러스터 보유율 / 코퍼스 보유율) 상위 {LABEL_TOP_N}개",
        "label_denominator": "EDA/analysis_outputs/10_accord_dictionary.csv perfume_share",
        "grid_encoding": "row_major_uint8, 값 = region id, 255 = 바다. terrain 과 같은 격자·bounds",
        "grid": region_grid.ravel().tolist(),
        "items": regions,
    }
    doc["contours"] = [{
        "level": sea_level_u8,
        "meaning": "해안선. terrain 값이 sea_level 을 넘는 영역의 경계",
        "polygons": mask_polygons(land, xs, ys),
    }]
    for point, region in zip(doc["points"], labels):
        point["region"] = int(region)

    with open(V2_PATH, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
        f.write("\n")

    saved = json.loads(open(V2_PATH, encoding="utf-8").read())
    t, r = saved["terrain"], saved["regions"]
    assert len(t["values"]) == t["grid_width"] * t["grid_height"]
    assert len(r["grid"]) == len(t["values"])
    assert max(t["values"]) == 255 and min(t["values"]) >= 0
    assert {p["region"] for p in saved["points"]} == set(range(cluster_k))
    assert len(saved["points"]) == 200
    size = os.path.getsize(V2_PATH)
    print()
    print(f"terrain 격자 {len(t['values']):,}칸 | region 격자 동일 | 육지 위 향수 {t['points_on_land']}/200")
    print(f"해안선 폴리곤 {len(saved['contours'][0]['polygons'])}개, "
          f"영역 폴리곤 {[len(x['polygon']) for x in r['items']]}")
    print(f"파일 크기 {size:,} bytes ({size/1024/1024:.2f} MB)")
    print(V2_PATH)


if __name__ == "__main__":
    main()

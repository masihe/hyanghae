"""국내 200개 지도의 밀도 지형 파라미터를 스윕한다 (Phase A2).

Run with venv/Scripts/python.exe src/map/sweep_korea_terrain.py

좌표는 D11에서 채택한 A안(korea_scent_map_v2.json 의 정규화 좌표)을 그대로 쓴다.
여기서는 지형을 만드는 방법과 파라미터만 바꾼다.

스윕하는 것
  - 방법 2종: Gaussian KDE / 히스토그램 + 가우시안 블러 (비교군)
  - bandwidth 3종: scott 기본, 0.5배, 2배
  - 바다 임계 6종: 밀도 하위 40/50/55/60/70/80 백분위

임계값이 스윕 대상인 이유는 D11 측정이다 — 하위 55%를 바다로 두면 육지 덩어리가
1~2개뿐이다. 글로벌 1,000개 지도의 "대륙 4~5개"는 200개에서 나타나지 않는다.
섬을 여러 개 보여주려면 임계를 올려야 하고, 그때 무엇이 드러나고 무엇이 잘리는지
프론트가 알아야 한다.

'보기 좋은 값'을 근거 없이 고르지 않는다. 이 스크립트는 표를 만들고, 선택 근거는
DECISIONS.md 에 남긴다.
"""
import json
import os
import sys

import numpy as np
import pandas as pd
from scipy.ndimage import gaussian_filter, label as cc_label
from scipy.stats import gaussian_kde

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

MAP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))  # MAP/
V2_PATH = os.path.join(MAP_DIR, "output", "korea_scent_map_v2.json")
OUT_CSV = os.path.join(MAP_DIR, "results", "korea_terrain_comparison.csv")

GRID_WIDTH = 128
MARGIN = 0.05          # 정규화 단위. 최외곽 점 바깥에 해안선이 생기도록 여백을 둔다
BANDWIDTH_SCALES = (0.35, 0.5, 0.7, 1.0, 2.0)
THRESHOLDS = (40, 50, 55, 60, 65, 70, 75, 80)
MIN_ISLAND_POINTS = 5  # 이보다 적은 향수가 올라간 육지는 탐색 대상이 못 된다


def terrain_bounds(coords):
    lo = coords.min(axis=0) - MARGIN
    hi = coords.max(axis=0) + MARGIN
    return lo, hi


def grid_shape(lo, hi):
    """격자를 bounds 종횡비에 맞춘다. x 방향 GRID_WIDTH 칸."""
    span = hi - lo
    height = int(round(GRID_WIDTH * span[1] / span[0]))
    return GRID_WIDTH, height


def kde_grid(coords, lo, hi, width, height, scale):
    kde = gaussian_kde(coords.T)
    kde.set_bandwidth(kde.factor * scale)
    xs = np.linspace(lo[0], hi[0], width)
    ys = np.linspace(lo[1], hi[1], height)
    gx, gy = np.meshgrid(xs, ys)  # row = y, col = x
    values = kde(np.vstack([gx.ravel(), gy.ravel()])).reshape(height, width)
    return values / values.max(), float(kde.factor)


def blur_grid(coords, lo, hi, width, height, scale):
    """비교군. KDE 와 다른 방법으로도 같은 지형이 나오는지 본다."""
    xedges = np.linspace(lo[0], hi[0], width + 1)
    yedges = np.linspace(lo[1], hi[1], height + 1)
    hist, _, _ = np.histogram2d(coords[:, 0], coords[:, 1], bins=[xedges, yedges])
    hist = hist.T  # row = y
    # KDE scott 대역폭을 격자 칸 수로 환산해 같은 스케일에서 비교한다.
    sigma_units = gaussian_kde(coords.T).factor * coords.std(axis=0).mean() * scale
    sigma_cells = sigma_units * width / (hi[0] - lo[0])
    values = gaussian_filter(hist, sigma=sigma_cells, mode="constant")
    return values / values.max(), float(sigma_cells)


def cell_of(coords, lo, hi, width, height):
    col = np.clip(((coords[:, 0] - lo[0]) / (hi[0] - lo[0]) * (width - 1)).round().astype(int), 0, width - 1)
    row = np.clip(((coords[:, 1] - lo[1]) / (hi[1] - lo[1]) * (height - 1)).round().astype(int), 0, height - 1)
    return row, col


def main():
    doc = json.loads(open(V2_PATH, encoding="utf-8").read())
    coords = np.array([[p["x"], p["y"]] for p in doc["points"]], dtype=float)
    assert len(coords) == 200

    lo, hi = terrain_bounds(coords)
    width, height = grid_shape(lo, hi)
    row, col = cell_of(coords, lo, hi, width, height)
    print(f"좌표 {len(coords)}개 | terrain bounds x [{lo[0]:.4f}, {hi[0]:.4f}] "
          f"y [{lo[1]:.4f}, {hi[1]:.4f}] | 격자 {width} x {height}")

    grids, rows_out = {}, []
    for method, fn in (("gaussian_kde", kde_grid), ("hist_blur", blur_grid)):
        for scale in BANDWIDTH_SCALES:
            grid, param = fn(coords, lo, hi, width, height, scale)
            grids[(method, scale)] = grid
            at_points = grid[row, col]
            for pct in THRESHOLDS:
                threshold = float(np.percentile(grid, pct))
                mask = grid > threshold
                labels, count = cc_label(mask)
                sizes = np.bincount(labels.ravel())[1:] if count else np.array([0])
                # 각 육지에 향수가 몇 개 올라가는가. 향수 없는 육지는 가짜 섬이다.
                point_label = labels[row, col]
                per_island = np.bincount(point_label, minlength=count + 1)[1:] if count else np.array([0])
                rows_out.append({
                    "method": method, "bandwidth_scale": scale, "bandwidth_param": round(param, 4),
                    "threshold_pct": pct, "threshold_value": round(threshold, 6),
                    "land_components": int(count),
                    "islands_with_points": int((per_island > 0).sum()),
                    "islands_ge5_points": int((per_island >= MIN_ISLAND_POINTS).sum()),
                    "largest_island_points": int(per_island.max()) if count else 0,
                    "largest_component_share": round(float(sizes.max() / mask.sum()) if mask.sum() else 0.0, 4),
                    "land_area_share": round(float(mask.mean()), 4),
                    "points_on_land": int((at_points > threshold).sum()),
                })

    reference = grids[("gaussian_kde", 1.0)].ravel()
    corr = {key: float(np.corrcoef(reference, g.ravel())[0, 1]) for key, g in grids.items()}
    out = pd.DataFrame(rows_out)
    out["corr_vs_kde_scott"] = [round(corr[(m, s)], 4) for m, s in zip(out.method, out.bandwidth_scale)]
    out.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")

    print()
    print("=== 방법·대역폭별 격자 상관 (기준: gaussian_kde scott) ===")
    for key in sorted(corr, key=lambda k: (k[0], k[1])):
        print(f"  {key[0]:14s} x{key[1]:<4} corr {corr[key]:.4f}")

    print()
    print("=== 임계값별 지형 (gaussian_kde) ===")
    print("  bw    임계  육지수  향수있는육지  향수>=5육지  최대섬향수  육지위향수/200")
    for scale in BANDWIDTH_SCALES:
        for pct in THRESHOLDS:
            r = out[(out.method == "gaussian_kde") & (out.bandwidth_scale == scale)
                    & (out.threshold_pct == pct)].iloc[0]
            print(f"  x{scale:<5} {pct:>3}%  {r.land_components:>5}  {r.islands_with_points:>11}"
                  f"  {r.islands_ge5_points:>10}  {r.largest_island_points:>10}  {r.points_on_land:>13}")

    print()
    print("=== 두 방법이 같은 육지 수를 주는가 (bw x1.0) ===")
    for pct in THRESHOLDS:
        a = out[(out.method == "gaussian_kde") & (out.bandwidth_scale == 1.0) & (out.threshold_pct == pct)].iloc[0]
        b = out[(out.method == "hist_blur") & (out.bandwidth_scale == 1.0) & (out.threshold_pct == pct)].iloc[0]
        print(f"  {pct:>3}%  kde {a.land_components:>3} / blur {b.land_components:>3}"
              f"  | 향수 {a.points_on_land:>3} / {b.points_on_land:>3}")
    print()
    print(OUT_CSV)


if __name__ == "__main__":
    main()

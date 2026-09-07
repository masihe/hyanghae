"""지형·영역을 눈으로 확인하고 이상 사례를 목록화한다 (Phase A2 검증).

Run with venv/Scripts/python.exe src/map/check_korea_terrain.py

수치 지표가 못 잡는 문제를 찾는 것이 목적이다 — 한 점에 뭉침, 정반대 향이 인접,
빈 영역, 바다에 빠진 향수. "잘 나온다"로 보고하지 않고 발견한 것을 그대로 남긴다.
"""
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.spatial.distance import pdist, squareform

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "common")))
import scent_map as sm

MAP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))  # MAP/
V2_PATH = os.path.join(MAP_DIR, "output", "korea_scent_map_v2.json")
PNG_PATH = os.path.join(MAP_DIR, "results", "korea_terrain_check.png")

REGION_COLORS = ["#2f6f4f", "#8c5a2b", "#7a3b5e", "#3f5d8c"]


def main():
    doc = json.loads(open(V2_PATH, encoding="utf-8").read())
    pts = doc["points"]
    t, r = doc["terrain"], doc["regions"]
    ids = [p["fragrantica_id"] for p in pts]
    coords = np.array([[p["x"], p["y"]] for p in pts])
    regions = np.array([p["region"] for p in pts])
    names = {p["fragrantica_id"]: f"{p['brand']} / {p['name']}" for p in pts}

    grid = np.array(t["values"], dtype=float).reshape(t["grid_height"], t["grid_width"])
    rgrid = np.array(r["grid"], dtype=int).reshape(t["grid_height"], t["grid_width"])
    b = t["bounds"]
    extent = [b["x_min"], b["x_max"], b["y_min"], b["y_max"]]
    land = grid > t["sea_level"]

    # 바다에 빠진 향수
    col = np.clip(((coords[:, 0] - b["x_min"]) / (b["x_max"] - b["x_min"]) * (t["grid_width"] - 1)).round().astype(int), 0, t["grid_width"] - 1)
    row = np.clip(((coords[:, 1] - b["y_min"]) / (b["y_max"] - b["y_min"]) * (t["grid_height"] - 1)).round().astype(int), 0, t["grid_height"] - 1)
    in_sea = ~land[row, col]

    # 정답 간선 (신뢰 간선) 중 2D 거리가 먼 것
    edges = sm.load_edges("reminds_edges.csv")
    trusted = edges[(edges.up_votes >= 3) & (edges.up_votes > edges.down_votes)]
    idset = set(ids)
    pairs = [(s, d) for s, d in zip(trusted.src, trusted.dst) if s in idset and d in idset]
    pos = {pid: i for i, pid in enumerate(ids)}
    low = squareform(pdist(coords))
    scored = sorted(({"src": s, "dst": d, "dist": float(low[pos[s], pos[d]]),
                      "same_region": bool(regions[pos[s]] == regions[pos[d]])}
                     for s, d in pairs), key=lambda e: -e["dist"])

    fig, ax = plt.subplots(figsize=(9, 9.6), dpi=110)
    ax.imshow(np.where(land, grid, np.nan), origin="lower", extent=extent,
              cmap="YlGn", vmin=0, vmax=255, interpolation="bilinear")
    ax.imshow(np.where(land, np.nan, grid), origin="lower", extent=extent,
              cmap="Blues_r", vmin=-120, vmax=t["sea_level"], interpolation="bilinear")
    for c in range(r["cluster_count"]):
        ax.contour(np.linspace(extent[0], extent[1], t["grid_width"]),
                   np.linspace(extent[2], extent[3], t["grid_height"]),
                   (rgrid == c).astype(float), levels=[0.5],
                   colors=[REGION_COLORS[c % len(REGION_COLORS)]], linewidths=1.2)
    for e in scored:
        i, j = pos[e["src"]], pos[e["dst"]]
        ax.plot(coords[[i, j], 0], coords[[i, j], 1],
                color="#c0392b" if not e["same_region"] else "#7f8c8d",
                lw=0.7, alpha=0.55, zorder=2)
    for c in range(r["cluster_count"]):
        m = regions == c
        ax.scatter(coords[m, 0], coords[m, 1], s=26, zorder=3,
                   color=REGION_COLORS[c % len(REGION_COLORS)], edgecolor="white", linewidth=0.6,
                   label=" · ".join(a["name"] for a in r["items"][c]["label_accords"]))
    ax.scatter(coords[in_sea, 0], coords[in_sea, 1], s=90, facecolor="none",
               edgecolor="#e74c3c", linewidth=1.6, zorder=4, label=f"in sea: {in_sea.sum()}")
    for item in r["items"]:
        if item["label_anchor"]:
            ax.annotate(" · ".join(a["name"] for a in item["label_accords"]),
                        (item["label_anchor"]["x"], item["label_anchor"]["y"]),
                        fontsize=8, ha="center", zorder=5,
                        bbox=dict(boxstyle="round,pad=0.25", fc="white", ec="none", alpha=0.75))
    ax.set_xlim(extent[0], extent[1]); ax.set_ylim(extent[2], extent[3])
    ax.set_title(f"korea_scent_map_v2 terrain check — KDE {t['bandwidth']}, "
                 f"sea_level {t['sea_level']}/255, region k={r['cluster_count']}", fontsize=9)
    ax.legend(loc="lower left", fontsize=7, framealpha=0.85)
    fig.tight_layout()
    fig.savefig(PNG_PATH)
    plt.close(fig)

    print(f"바다에 빠진 향수 {int(in_sea.sum())}개 / 200")
    for pid in np.array(ids)[in_sea]:
        p = pts[pos[pid]]
        print(f"   rank {p['display_priority']:>3}  region {p['region']}  {names[pid]}")
    print()
    print(f"신뢰 간선 {len(scored)}개 중 2D 거리 먼 상위 10쌍 (빨간 선 = 영역 횡단)")
    for e in scored[:10]:
        flag = "같은영역" if e["same_region"] else "영역횡단"
        print(f"   d={e['dist']:.3f} {flag}  {names[e['src']]}  <->  {names[e['dst']]}")
    cross = sum(1 for e in scored if not e["same_region"])
    print()
    print(f"영역 횡단 신뢰 간선 {cross}/{len(scored)} ({cross/len(scored):.1%})")
    print(f"신뢰 간선 2D 거리 중앙값 {np.median([e['dist'] for e in scored]):.4f} / "
          f"전체 쌍 중앙값 {np.median(low[np.triu_indices(len(ids), 1)]):.4f}")
    print(PNG_PATH)


if __name__ == "__main__":
    main()

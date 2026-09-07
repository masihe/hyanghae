"""4대 그룹과 데이터 기반 클러스터 중 무엇이 지도에서 영역을 이루는지 그린다.

    python plot_regions.py   ->  results/region_coloring.png

수치(응집도)만으로는 "색으로 영역을 칠할 수 있는가"가 잘 안 와닿아서 같이 그린다.
"""
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

# Windows 기본 한글 폰트. 없으면 한글이 네모로 나온다.
matplotlib.rcParams["font.family"] = "Malgun Gothic"
matplotlib.rcParams["axes.unicode_minus"] = False

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

MAP_DIR = os.path.dirname(os.path.abspath(__file__))
GROUP_COLORS = {"Floral": "#f08bb4", "Amber": "#f6bd16",
                "Woody": "#d97b3a", "Fresh": "#61ddaa"}
CLUSTER_PALETTE = ["#5b8ff9", "#61ddaa", "#f6bd16", "#f08bb4", "#7262fd", "#78d3f8",
                   "#d97b3a", "#9661bc", "#e8684a", "#6dc8ec", "#a7d64c", "#ff9d4d"]


def main():
    doc = json.load(open(os.path.join(MAP_DIR, "output", "scent_map_v1.json"),
                         encoding="utf-8"))
    P = doc["perfumes"]
    x = np.array([p["x"] for p in P])
    y = np.array([p["y"] for p in P])
    cluster_label = {c["id"]: " · ".join(c["top_accords"]) for c in doc["clusters"]}

    fig, axes = plt.subplots(1, 2, figsize=(15, 7.2), facecolor="white")

    ax = axes[0]
    for g, col in GROUP_COLORS.items():
        m = np.array([p["group"] == g for p in P])
        ax.scatter(x[m], y[m], s=11, c=col, label=f"{g} ({int(m.sum())})",
                   alpha=.85, linewidths=0)
    ax.set_title("Fragrantica 4대 그룹으로 칠했을 때\n"
                 "영역 응집도 0.387 (무작위 0.260 → 1.5배)", fontsize=11)
    ax.legend(loc="upper right", fontsize=8, framealpha=.9)

    ax = axes[1]
    for c in sorted({p["cluster"] for p in P}):
        m = np.array([p["cluster"] == c for p in P])
        if m.sum() < 5:
            continue
        ax.scatter(x[m], y[m], s=11, c=CLUSTER_PALETTE[c % len(CLUSTER_PALETTE)],
                   label=f"{cluster_label[c]} ({int(m.sum())})", alpha=.85, linewidths=0)
    ax.set_title("데이터 기반 클러스터(k=12)로 칠했을 때\n"
                 "영역 응집도 0.762 (무작위 0.175 → 4.4배)", fontsize=11)
    ax.legend(loc="upper right", fontsize=7, framealpha=.9)

    for ax in axes:
        ax.set_xticks([]); ax.set_yticks([])
        ax.set_aspect("equal")
        for s in ax.spines.values():
            s.set_color("#ccc")

    fig.suptitle("같은 좌표, 다른 색칠 기준", fontsize=13)
    fig.tight_layout()
    out = os.path.join(MAP_DIR, "results", "region_coloring.png")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    fig.savefig(out, dpi=130, facecolor="white")
    print("saved", out)


if __name__ == "__main__":
    main()

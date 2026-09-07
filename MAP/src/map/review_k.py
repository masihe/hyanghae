"""DECISIONS.md D4의 근거를 재현한다 — k=8/12/16이 채택 좌표 위에서 영역을 이루는가.

    python review_k.py

클러스터 개수 선택은 "최대 클러스터가 몇 %인가"만으로는 판단이 안 된다.
프론트가 색이나 경계로 영역을 그릴 수 있으려면 라벨이 2D에서 실제로 뭉쳐 있어야 하고,
그 대가로 "닮았다" 투표 쌍이 얼마나 갈라지는지도 함께 봐야 한다. 그 두 가지를 잰다.

좌표는 새로 만들지 않고 output/scent_map_v1.json의 채택 좌표를 그대로 읽는다.
build_map.py / scent_map.py는 수정하지 않고 호출만 한다.
"""
import json
import os
import sys

import numpy as np
from sklearn.cluster import AgglomerativeClustering
from sklearn.metrics import silhouette_score

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import build_map as bm

MAP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))  # MAP/
K_CANDIDATES = (8, 12, 16)
WEAK_COHESION = 0.35      # 이 아래면 경계를 그릴 수 없는 라벨로 본다


def main():
    _, targets, _, S, D, index_of, ce, _ = bm.prepare(with_selection_comparison=False)

    doc = json.load(open(os.path.join(MAP_DIR, "output", "scent_map_v1.json"),
                         encoding="utf-8"))
    P = doc["perfumes"]
    assert [p["id"] for p in P] == list(targets["id"]), "JSON과 targets의 순서가 다르다"
    coords = np.array([[p["x"], p["y"]] for p in P], dtype=float)
    print(f"채택 좌표 {doc['layout']['method']} / {len(P)}개 — targets와 순서 일치 확인\n")

    n = len(targets)
    for k in K_CANDIDATES:
        labels = AgglomerativeClustering(n_clusters=k, metric="precomputed",
                                         linkage="average").fit_predict(D)
        sizes = np.bincount(labels)
        obs, exp, per = bm.region_cohesion(coords, labels)
        sil = float(silhouette_score(coords, labels))

        # 신뢰 간선이 클러스터를 넘나드는 비율 — 라벨을 영역으로 쓸 때의 비용.
        # 실험 B(D9)에서 이 값이 영역 분리의 실질 비용임을 확인했다.
        cross = sum(1 for a, b in ce if labels[index_of[a]] != labels[index_of[b]])

        print(f"k={k:<3} 최대 {sizes.max()} ({100*sizes.max()/n:.1f}%) | "
              f"n<=3 클러스터 {(sizes <= 3).sum()}개 | n<=10 {(sizes <= 10).sum()}개")
        print(f"      응집도 {obs:.3f} (무작위 {exp:.3f} -> {obs/exp:.1f}배) | "
              f"2D silhouette {sil:.4f}")
        print(f"      신뢰 간선이 클러스터를 넘는 비율 {cross}/{len(ce)} ({100*cross/len(ce):.1f}%)")
        weak = {c: v for c, v in per.items() if v < WEAK_COHESION}
        print(f"      응집도 {WEAK_COHESION} 미만 클러스터 {len(weak)}개 {weak}")

        if k == 16:
            print("      [k=16 accord 구성]")
            for c in range(k):
                idx = np.flatnonzero(labels == c)
                acc = {}
                for i in idx:
                    for name, strength in targets.iloc[i]["accord_list"]:
                        acc[name] = acc.get(name, 0.0) + strength
                top = [t[0] for t in sorted(acc.items(), key=lambda x: -x[1])[:3]]
                print(f"        c{c:<2} n={len(idx):<4} 응집도 {per[str(c)]:<6} {top}")
        print()


if __name__ == "__main__":
    main()

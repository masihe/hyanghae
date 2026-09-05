"""정답 데이터(reminds_me_of)의 신뢰성 점검 — DECISIONS.md D10을 재현한다.

    python check_edges.py

D4/D9에서 나온 "신뢰 간선의 35.1%가 영역을 넘는다"가 지도 배치의 문제인지,
정답지 자체의 약점(적은 투표 수, 같은 브랜드 쌍 효과)인지 분리하기 위한 점검이다.
간선 채택 기준을 바꿔가며 횡단 비율이 흔들리는지 본다.

산출물: results/edge_robustness.csv, results/human_check_pairs.csv
build_map.py / scent_map.py는 수정하지 않고 호출만 한다.
"""
import os
import sys

import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import build_map as bm
import scent_map as sm

MAP_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(MAP_DIR, "results")
TOP_SHARE = 0.30       # 사람 점검용: vote_count 상위 30%
N_PER_SIDE = 10        # 같은 영역 10쌍 / 다른 영역 10쌍

# 기준 A는 build_map.confident()와 같아야 한다. 재현 확인용으로 여기서 다시 쓴다.
CRITERIA = {
    "A_up>=3_up>down":      lambda up, dn: (up >= 3) & (up > dn),
    "B_up>=5_ratio>=0.7":   lambda up, dn: (up >= 5) & (up / np.maximum(up + dn, 1) >= 0.7),
    "C_up>=10_ratio>=0.7":  lambda up, dn: (up >= 10) & (up / np.maximum(up + dn, 1) >= 0.7),
    "D_total>=20_ratio>=0.8": lambda up, dn: ((up + dn) >= 20) & (up / np.maximum(up + dn, 1) >= 0.8),
}


def main():
    _, targets, _, S, D, index_of, ce_prepare, _ = bm.prepare(with_selection_comparison=False)

    labels12 = bm.step3(D, targets, S)[bm.CLUSTER_K]
    merged, log = bm.merge_small_clusters(D, labels12)
    print(f"\n  라벨 병합 {len(np.unique(labels12))} -> {len(np.unique(merged))}개 "
          f"(이동 {len(log)}개) — D9와 동일")

    # baseline 좌표를 실험 B와 같은 방식으로 재생성한다 (y 없음).
    import umap
    coords = umap.UMAP(n_components=2, metric="precomputed", n_neighbors=10,
                       min_dist=0.1, random_state=bm.SEED).fit_transform(D)
    coords = np.asarray(coords, dtype=float)

    ids = set(targets["id"])
    brand_of = dict(zip(targets["id"], targets["brand"]))
    name_of = dict(zip(targets["id"], targets["name"]))
    edges = bm.edges_within(sm.load_edges("reminds_edges.csv"), ids).copy()
    edges["total"] = edges["up_votes"] + edges["down_votes"]
    edges["same_brand"] = [brand_of[a] == brand_of[b]
                           for a, b in zip(edges["src"], edges["dst"])]
    edges["cross"] = [merged[index_of[a]] != merged[index_of[b]]
                      for a, b in zip(edges["src"], edges["dst"])]
    print(f"  1,000개 내부 reminds 간선 {len(edges)}건 (방향 있는 관계 그대로)")

    # ------------------------------------------------------------------ 1
    rows = []
    for label, fn in CRITERIA.items():
        keep = fn(edges["up_votes"].to_numpy(), edges["down_votes"].to_numpy())
        for primed in (False, True):
            sub = edges[keep & (~edges["same_brand"] if primed else True)]
            pairs = [(int(a), int(b)) for a, b in
                     sub[["src", "dst"]].itertuples(index=False, name=None)]
            pct = bm.edge_distance_percentile(coords, index_of, pairs)[0] if pairs else float("nan")
            rows.append({
                "criterion": label + ("_no_same_brand" if primed else ""),
                "same_brand_excluded": primed,
                "n_edges": len(sub),
                "same_brand_share": round(float(sub["same_brand"].mean()), 4) if len(sub) else float("nan"),
                "cross_region_edges": int(sub["cross"].sum()),
                "cross_region_share": round(float(sub["cross"].mean()), 4) if len(sub) else float("nan"),
                "reminds_pct": round(pct, 4),
                "total_votes_median": int(sub["total"].median()) if len(sub) else 0,
            })
    res = pd.DataFrame(rows)
    os.makedirs(RESULTS_DIR, exist_ok=True)
    res.to_csv(os.path.join(RESULTS_DIR, "edge_robustness.csv"), index=False)

    print()
    print("  cross_region_share: 병합 라벨(10개) 기준 영역을 넘는 간선 비율")
    print("  reminds_pct: baseline 좌표에서 파트너의 2D 거리 백분위 (낮을수록 가까움, 0.5=무작위)")
    print()
    print(res.to_string(index=False))
    print(f"\n  -> results/edge_robustness.csv 저장")

    # ------------------------------------------------------------------ 검증
    a = res.iloc[0]
    ok_n, ok_cross = int(a["n_edges"]) == 872, int(a["cross_region_edges"]) == 306
    print()
    print(f"  [검증] 기준 A: 간선 {int(a['n_edges'])}({'OK' if ok_n else '기대 872'}) / "
          f"횡단 {int(a['cross_region_edges'])}({'OK' if ok_cross else '기대 306'}) / "
          f"{100*a['cross_region_share']:.1f}% (기대 35.1%)")
    print(f"          prepare()가 만든 간선 수 {len(ce_prepare)}건과 일치: "
          f"{len(ce_prepare) == int(a['n_edges'])}")
    print(f"          기준 A 같은 브랜드 비율 {100*a['same_brand_share']:.1f}%")

    # ------------------------------------------------------------------ 2
    keep_a = CRITERIA["A_up>=3_up>down"](edges["up_votes"].to_numpy(),
                                         edges["down_votes"].to_numpy())
    tv = edges[keep_a]["total"]
    q = tv.quantile([0.25, 0.5, 0.75])
    print()
    print(f"  [투표 수 분포] 기준 A {len(tv)}쌍의 총 표 수")
    print(f"    최소 {int(tv.min())} / 25% {int(q[0.25])} / 중앙 {int(q[0.5])} / "
          f"75% {int(q[0.75])} / 최대 {int(tv.max())} / 평균 {tv.mean():.1f}")
    for t in (5, 10, 20, 50):
        print(f"    총 표 {t} 이상: {int((tv >= t).sum())}쌍 ({100*(tv >= t).mean():.1f}%)")

    # ------------------------------------------------------------------ 3
    cut = targets["vote_count"].quantile(1 - TOP_SHARE)
    top_ids = set(targets[targets["vote_count"] >= cut]["id"])
    print()
    print(f"  [사람 점검용] vote_count 상위 {int(TOP_SHARE*100)}% 기준값 {int(cut)} / "
          f"해당 향수 {len(top_ids)}개")

    cand = edges[keep_a & edges["src"].isin(top_ids) & edges["dst"].isin(top_ids)].copy()
    # 방향이 반대인 같은 쌍이 두 번 나올 수 있다. 사람에게 같은 쌍을 두 번 묻지 않는다.
    cand["key"] = [tuple(sorted((int(a), int(b))))
                   for a, b in zip(cand["src"], cand["dst"])]
    cand = cand.sort_values("total", ascending=False).drop_duplicates("key")

    picked = []
    for is_cross, tag in [(False, "same"), (True, "cross")]:
        sub = cand[cand["cross"] == is_cross].head(N_PER_SIDE)
        print(f"    {tag}: 후보 {int((cand['cross'] == is_cross).sum())}쌍 중 {len(sub)}쌍 선정")
        picked.append(sub)
    sel = pd.concat(picked).reset_index(drop=True)

    out = pd.DataFrame({
        "pair_id": [f"P{i+1:02d}" for i in range(len(sel))],
        "perfume_1": [f"{name_of[a]} / {brand_of[a]}" for a in sel["src"]],
        "perfume_2": [f"{name_of[b]} / {brand_of[b]}" for b in sel["dst"]],
        "same_region": (~sel["cross"]).map({True: "Y", False: "N"}),
        "total_votes": sel["total"].astype(int),
        "up_votes": sel["up_votes"].astype(int),
        "down_votes": sel["down_votes"].astype(int),
        "team_agree_1": "", "team_agree_2": "", "team_agree_3": "",
    })
    out.to_csv(os.path.join(RESULTS_DIR, "human_check_pairs.csv"), index=False)
    print(f"    -> results/human_check_pairs.csv 저장 ({len(out)}쌍, 판정란 비움)")


if __name__ == "__main__":
    main()

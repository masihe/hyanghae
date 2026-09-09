"""Phase 3b 후속 — Gate 통과 후보를 v4 34 의 계층으로 좁힌다.

Run with venv/Scripts/python.exe src/map/experiment_phase3b_finalists.py

experiment_phase3b_territory.py 가 Gate A(계열 횡단 신뢰 쌍 근접도)로 13개 방식 중 7개를
남겼다. 그런데 **Gate A 만으로는 부족하다** — C5 wheel anchor 는 Gate A 를 통과하지만
trust@10 이 0.7068 로 "옆에 있는 게 비슷하다" 는 기본 약속을 못 지킨다.

그래서 v4 34 의 계층을 그대로 적용한다.

    통과 게이트   Gate A  cross-family trusted-pair 근접도 <= baseline + 0.05  (Global 1,000)
                 Gate B  trustworthiness@10 >= 0.90                          (모집단 명시)
    비교 축       1 영역 이해   normalized cohesion ratio
                 2 설명 가능성 고정 시험지 — 원본 note 문자열 / 원본 rare accord 공통 개수
                 3 방향성      회전 정렬 후 축과 사용자 투표의 상관
    기록 축       안정성 · 균형 · 구현 복잡도 (자동 순위에 쓰지 않는다)

**설명 가능성은 고정 시험지로 잰다.** 어떤 방식을 쓰든 기준을 바꾸지 않는다 —
원본 note 문자열과 원본 accord(보유율 < 0.30)의 공통 개수다.

**방향성은 회전으로 잰다.** 회전은 등거리 변환이라 지표를 바꾸지 않으므로, 각 후보 좌표를
따뜻함 축에 맞춰 돌린 뒤 상관을 본다 (Phase 0 축 회전과 같은 절차).

산출: experiments/phase3b/finalists.json, finalists.csv
"""
import json
import os
import sys
import time

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "common")))
import scent_map as sm
import build_map as bm
import experiment_phase0_family_mapping as fm
import experiment_family_systems as es
import experiment_phase3b_territory as p3b

OUT_DIR = os.path.join("experiments", "phase3b")
TOP200 = os.path.join("data", "korea_popularity", "korea_representative_perfumes_top200.csv")
V2_JSON = os.path.join("output", "korea_scent_map_v2.json")
ACCORD_DICT = os.path.join("..", "EDA", "analysis_outputs", "10_accord_dictionary.csv")
SEEDS = (42, 1, 2, 3, 4)
RARE_MAX_SHARE = 0.30
NEIGHBOR_K = 10
GATE_B = 0.90

# Gate A 를 통과한 방식 (experiment_phase3b_territory.py 결과)
CANDIDATES = ["C1 post-hoc", "C3 semi w=0.35", "C3 semi w=0.5", "C5 wheel anchor",
              "C8a perception b=0.15", "C8b family .35 + perc .15"]


def explainability(coords, note_sets, rare_sets):
    """고정 시험지. 2D 이웃 10개 쌍에서 원본 note / 원본 rare accord 공통 개수."""
    from scipy.spatial.distance import squareform, pdist
    D = squareform(pdist(np.asarray(coords, float)))
    np.fill_diagonal(D, np.inf)
    nn = np.argsort(D, axis=1)[:, :NEIGHBOR_K]
    sn, sr = [], []
    for i in range(len(coords)):
        for j in nn[i]:
            sn.append(len(note_sets[i] & note_sets[j]))
            sr.append(len(rare_sets[i] & rare_sets[j]))
    sn, sr = np.array(sn), np.array(sr)
    both_missing = sum(1 for i in range(len(coords))
                       if len(note_sets[i] & note_sets[nn[i][0]]) == 0
                       and len(rare_sets[i] & rare_sets[nn[i][0]]) == 0)
    return {"shared_note_ge1": round(float((sn >= 1).mean()), 4),
            "shared_rare_accord_ge1": round(float((sr >= 1).mean()), 4),
            "mean_shared_note": round(float(sn.mean()), 3),
            "nearest_neighbor_unexplained": int(both_missing)}


def axis_meaning(coords, warmth, masc):
    """회전 정렬 후 축 상관. 회전은 거리를 바꾸지 않으므로 지표에 영향이 없다."""
    c0 = np.asarray(coords, float)
    c0 = c0 - c0.mean(axis=0)
    ok = ~np.isnan(warmth)
    best = None
    for deg in range(180):
        th = np.deg2rad(deg)
        R = np.array([[np.cos(th), -np.sin(th)], [np.sin(th), np.cos(th)]])
        rr = c0 @ R.T
        rho, _ = spearmanr(rr[ok, 1], warmth[ok])
        if best is None or abs(rho) > abs(best[1]):
            best = (deg, float(rho))
    deg, rho = best
    th = np.deg2rad(deg)
    R = np.array([[np.cos(th), -np.sin(th)], [np.sin(th), np.cos(th)]])
    rot = c0 @ R.T
    if rho < 0:
        rot[:, 1] *= -1
    okm = ~np.isnan(masc)
    rx, _ = spearmanr(rot[okm, 0], masc[okm])
    return {"rotation_deg": int(deg), "y_warmth_rho": round(abs(rho), 4),
            "x_masculine_rho": round(abs(float(rx)), 4)}


def main() -> None:
    os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))  # MAP/
    t0 = time.time()
    print("=" * 78)
    print("Phase 3b 후속 — 후보 좁히기 (Gate → 비교축 → 기록축)")
    print("=" * 78)

    p3b_metrics = json.loads(open(os.path.join(OUT_DIR, "metrics.json"),
                                  encoding="utf-8").read())
    gate_line = p3b_metrics["gate_a"]["pass_line"]

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

    res_k = es.family_scores(korea.accord_list.tolist(), p3b.SYSTEM)
    families, lab_k, M_k = res_k["families"], res_k["argmax"], res_k["M"]
    fam_idx = {f: i for i, f in enumerate(families)}
    y_k = np.array([fam_idx[f] for f in lab_k])
    srt = np.sort(M_k, axis=1)
    y_semi = np.where(srt[:, -1] - srt[:, -2] >= p3b.C3_MARGIN, y_k, -1)
    Dp_k, _, _ = p3b.perception_distance(korea_ids)
    Df_k = p3b.family_profile_distance(M_k)

    doc = json.loads(open(V2_JSON, encoding="utf-8").read())
    by_id = {p["fragrantica_id"]: (p["x"], p["y"]) for p in doc["points"]}
    base_k = np.array([by_id[i] for i in korea_ids], dtype=float)

    # 고정 시험지 재료 (원본 note / 원본 rare accord)
    acc = pd.read_csv(ACCORD_DICT)
    share = dict(zip(acc.accord, acc.perfume_share))
    note_sets = [set(s) for s in korea.note_set]
    rare_sets = [{n for n, _ in lst if share.get(n, 1.0) < RARE_MAX_SHARE}
                 for lst in korea.accord_list]

    # 인식 축
    raw = pd.read_csv(sm.PERFUMES_CSV, low_memory=False,
                      usecols=p3b.VOTE_COLS).set_index("id").loc[korea_ids]
    seas = raw[["winter", "spring", "summer", "autumn"]].astype(float)
    st = seas.sum(axis=1)
    warmth = np.where(st >= p3b.MIN_VOTES,
                      ((seas.winter + seas.autumn) - (seas.summer + seas.spring))
                      / st.replace(0, np.nan), np.nan)
    g = raw[["perceived_female", "perceived_female_leaning", "perceived_unisex",
             "perceived_male_leaning", "perceived_male"]].astype(float)
    gt = g.sum(axis=1)
    masc = np.where(gt >= p3b.MIN_VOTES,
                    ((g.perceived_male + 0.5 * g.perceived_male_leaning)
                     - (g.perceived_female + 0.5 * g.perceived_female_leaning))
                    / gt.replace(0, np.nan), np.nan)

    builders = {
        "C1 post-hoc": lambda s: base_k,
        "C3 semi w=0.35": lambda s: p3b.umap_layout(D_k, s, y=y_semi, target_weight=0.35),
        "C3 semi w=0.5": lambda s: p3b.umap_layout(D_k, s, y=y_semi, target_weight=0.5),
        "C5 wheel anchor": lambda s: p3b.wheel_anchor(M_k, families, s),
        "C8a perception b=0.15": lambda s: p3b.umap_layout(0.85 * D_k + 0.15 * Dp_k, s),
        "C8b family .35 + perc .15": lambda s: p3b.umap_layout(
            0.5 * D_k + 0.35 * Df_k + 0.15 * Dp_k, s),
    }

    print()
    print(f"  {'후보':<26}{'GateA Δ':>9}{'GateB':>8}{'통과':>6}"
          f"{'영역이해':>9}{'공통note':>9}{'rare':>8}{'설명불가':>9}"
          f"{'y=계절':>8}{'x=성별':>8}")
    rows = []
    for name in CANDIDATES:
        pg = p3b_metrics["global1000"][name]
        pk = p3b_metrics["korea200"][name]
        gate_a_delta = pg["gate_a_delta"]
        trust_g = pg["layout"]["trust@10"]
        gate_a = pg["gate_a"] == "PASS"
        gate_b = trust_g >= GATE_B
        coords = [np.asarray(builders[name](s), float) for s in SEEDS]
        ex = explainability(coords[0], note_sets, rare_sets)
        ax = axis_meaning(coords[0], warmth, masc)
        ax_seeds = [axis_meaning(c, warmth, masc) for c in coords]
        ratios = pk["seed_check"]["ratios"]
        rows.append({
            "candidate": name, "description": pk["description"],
            "gate_a_delta": gate_a_delta, "gate_a": bool(gate_a),
            "gate_b_trust10_global": round(float(trust_g), 4), "gate_b": bool(gate_b),
            "passes_both": bool(gate_a and gate_b),
            "axis1_cohesion_ratio_korea": pk["readability_seed42"]["cohesion_ratio"],
            "axis1_cohesion_ratio_global": pg["readability"]["cohesion_ratio"],
            "axis2_shared_note_ge1": ex["shared_note_ge1"],
            "axis2_shared_rare_accord_ge1": ex["shared_rare_accord_ge1"],
            "axis2_nearest_unexplained": ex["nearest_neighbor_unexplained"],
            "axis3_y_warmth_rho": ax["y_warmth_rho"],
            "axis3_x_masculine_rho": ax["x_masculine_rho"],
            "axis3_y_warmth_rho_seedmean": round(
                float(np.mean([a["y_warmth_rho"] for a in ax_seeds])), 4),
            "axis3_x_masculine_rho_seedmean": round(
                float(np.mean([a["x_masculine_rho"] for a in ax_seeds])), 4),
            "rec_reminds_pct_korea": pk["layout"]["reminds_pct"],
            "rec_trust10_korea": pk["layout"]["trust@10"],
            "rec_seed_std": pk["seed_check"]["std"],
            "rec_collapsed": pk["seed_check"]["collapsed"],
            "rec_fragments": (pk["region_field"] or {}).get("fragments_total"),
            "rec_on_own_region": (pk["region_field"] or {}).get("on_own_region"),
        })
        print(f"  {name:<26}{gate_a_delta:>+9.4f}{trust_g:>8.4f}"
              f"{'○' if (gate_a and gate_b) else '✕':>6}"
              f"{pk['readability_seed42']['cohesion_ratio']:>9.3f}"
              f"{ex['shared_note_ge1']:>9.1%}{ex['shared_rare_accord_ge1']:>8.1%}"
              f"{ex['nearest_neighbor_unexplained']:>9}"
              f"{ax['y_warmth_rho']:>8.3f}{ax['x_masculine_rho']:>8.3f}")

    survivors = [r for r in rows if r["passes_both"]]
    print()
    print(f"두 게이트 모두 통과 {len(survivors)}/{len(rows)}: "
          f"{[r['candidate'] for r in survivors]}")
    dropped = [r["candidate"] for r in rows if not r["passes_both"]]
    if dropped:
        for r in rows:
            if not r["passes_both"]:
                why = []
                if not r["gate_a"]:
                    why.append(f"Gate A +{r['gate_a_delta']:.4f}")
                if not r["gate_b"]:
                    why.append(f"Gate B trust@10 {r['gate_b_trust10_global']:.4f}")
                print(f"  탈락 {r['candidate']} — {' · '.join(why)}")

    # 비교축 3개에서 Pareto
    def dominates(a, b):
        keys = ("axis1_cohesion_ratio_korea", "axis2_shared_rare_accord_ge1",
                "axis3_y_warmth_rho")
        ge = all(b[k] >= a[k] for k in keys)
        gt = any(b[k] > a[k] for k in keys)
        return ge and gt
    front = [r["candidate"] for r in survivors
             if not any(dominates(r, o) for o in survivors if o is not r)]
    print()
    print(f"비교축 3개(영역 이해 · 설명 가능성 · 방향성) Pareto: {front}")

    best = max(survivors, key=lambda r: r["axis1_cohesion_ratio_korea"]) if survivors else None
    out = {
        "gate_a": {"pass_line": gate_line, "population": "global1000",
                   "baseline": p3b_metrics["gate_a"]["baseline_cross_family_proximity"]},
        "gate_b": {"threshold": GATE_B, "metric": "trustworthiness@10",
                   "population": "global1000"},
        "comparison_axes": {
            "axis1": "영역 이해 — normalized cohesion ratio",
            "axis2": ("설명 가능성 — 고정 시험지. 원본 note 문자열 / 원본 accord(보유율<0.30) "
                      "공통 개수. feature·방식이 무엇이든 기준을 바꾸지 않는다"),
            "axis3": "방향성 — 회전 정렬 후 축과 사용자 투표의 상관 (회전은 지표 불변)",
        },
        "record_axes": "안정성 · 조각 수 · 정답간선 근접도 · 구현 복잡도 (자동 순위에 쓰지 않는다)",
        "candidates": rows,
        "survivors": [r["candidate"] for r in survivors],
        "dropped": dropped,
        "pareto_front": front,
        "top_by_region_understanding": None if best is None else best["candidate"],
    }
    with open(os.path.join(OUT_DIR, "finalists.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
        f.write("\n")
    pd.DataFrame(rows).to_csv(os.path.join(OUT_DIR, "finalists.csv"),
                              index=False, encoding="utf-8-sig")
    print()
    print(f"총 소요 {time.time()-t0:.0f}초")
    print(f"  -> {OUT_DIR}/finalists.json · finalists.csv")


if __name__ == "__main__":
    main()

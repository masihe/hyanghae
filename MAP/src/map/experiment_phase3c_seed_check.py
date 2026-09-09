"""Phase 3c 후속 — 최종 후보의 Global 게이트를 시드 5개에서 재확인.

혼합 가중 스윕(`experiment_phase3c_blend_sweep.py`)의 Global 지표는 **seed 42 한 번**만
쟀다. 그런데 스윕이 낸 Gate A Δ 차이는 0.002~0.03 수준이고, 계열 가중에 대해
단조롭지도 않았다 (wf=0.5 가 +0.0565 로 wf=0.65 의 +0.0365 보다 나빴다).

한 번의 측정으로 그 순서를 근거로 쓸 수 없다. 그래서 최종 후보만 시드 5개에서
다시 재고, **5개 중 몇 개가 게이트를 통과하는지**를 함께 본다. 게이트를 시드마다
따로 적용하는 것은 `experiments/README.md` 의 게이트 시드 규칙(5개 시드, 0.01 안이면
REVIEW)을 따른 것이다.

후보는 스윕 결과를 보고 고른 것이므로 **사후 선택**이고, 그 사실을 산출물에 적는다.
게이트 기준선(0.3115 / 0.90)은 Phase 3b 에서 확정한 값을 그대로 쓴다.

재현::

    python src/map/experiment_phase3c_seed_check.py

산출  experiments/phase3c/seed_check.json
"""

import json
import os
import sys
import time

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in (HERE, os.path.join(HERE, "..", "common")):
    if p not in sys.path:
        sys.path.insert(0, p)

import scent_map as sm                          # noqa: E402
import build_map as bm                          # noqa: E402
import experiment_family_systems as es          # noqa: E402
import experiment_phase3b_territory as p3b      # noqa: E402
import experiment_phase3c_blend_sweep as p3c    # noqa: E402

OUT_DIR = os.path.join("experiments", "phase3c")
P3B_DIR = os.path.join("experiments", "phase3b")
SEEDS = (42, 1, 2, 3, 4)
GATE_B = 0.90

# 스윕 결과를 보고 고른 후보 — 사후 선택임을 기록한다.
BLEND_POINTS = (
    (0.00, 0.00, "baseline (C1 재계산)"),
    (0.10, 0.00, "계열 0.10 — 손실 거의 없음"),
    (0.20, 0.00, "계열 0.20 — 손실 <= 0.02 중 최고 가독성"),
    (0.35, 0.00, "계열 0.35 — 손실 <= 0.04 중 최고 가독성"),
    (0.00, 0.15, "C8a — 인식 축만"),
    (0.10, 0.15, "계열 0.10 + 인식 0.15"),
    (0.20, 0.15, "계열 0.20 + 인식 0.15"),
    (0.35, 0.15, "C8b (Phase 3b 채택안)"),
)


def main() -> None:
    os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))  # MAP/
    t0 = time.time()
    print("=" * 92)
    print("Phase 3c 후속 — 최종 후보의 Global 게이트 시드 5개 재확인")
    print("=" * 92)

    ref = json.loads(open(os.path.join(P3B_DIR, "metrics.json"), encoding="utf-8").read())
    gate_line = ref["gate_a"]["pass_line"]
    base_cross = ref["gate_a"]["baseline_cross_family_proximity"]
    print(f"게이트 (Phase 3b 확정) — Gate A <= {gate_line} (baseline {base_cross}) · "
          f"Gate B trust@10 >= {GATE_B}")

    df, targets, idf_map, _S, D_g, index_of_g, ce_g, _ae = bm.prepare(
        with_selection_comparison=False)
    res_g = es.family_scores(targets.accord_list.tolist(), p3b.SYSTEM)
    families, lab_g, M_g = res_g["families"], res_g["argmax"], res_g["M"]
    fam_idx = {f: i for i, f in enumerate(families)}
    y_g = np.array([fam_idx[f] for f in lab_g])
    srt = np.sort(M_g, axis=1)
    y_semi = np.where(srt[:, -1] - srt[:, -2] >= p3b.C3_MARGIN, y_g, -1)
    Dp_g, _, _ = p3b.perception_distance(targets.id.astype(int).tolist())
    Df_g = p3b.family_profile_distance(M_g)
    g_ids = targets.id.astype(int).tolist()

    builders = [(f"wf={wf:.3g} wp={wp:.3g}", note, False,
                 (lambda s, wf=wf, wp=wp: p3b.umap_layout(
                     p3c.blend(D_g, Df_g, Dp_g, wf, wp), s)))
                for wf, wp, note in BLEND_POINTS]
    builders.append(("C3 semi w=0.35", "안전 대안 (팀 결정 ④)", True,
                     lambda s: p3b.umap_layout(D_g, s, y=y_semi, target_weight=0.35)))

    print()
    print(f"  {'후보':<24}{'횡단근접 평균±표준편차':>24}{'최소':>8}{'최대':>8}"
          f"{'GateA통과':>10}{'trust@10':>18}{'GateB통과':>10}{'overlap@10':>18}")
    rows = []
    for name, note, is_semi, fn in builders:
        recs = []
        for s in SEEDS:
            c = np.asarray(fn(s), dtype=float)
            gr = p3b.guardrail(c, index_of_g, ce_g, lab_g, g_ids)
            m = bm.evaluate_layout(c, D_g, index_of_g, ce_g)
            rd = p3b.readability(c, lab_g, families)
            recs.append({"seed": s,
                         "cross_family_proximity": gr["cross_family_proximity"],
                         "same_family_proximity": gr.get("same_family_proximity"),
                         "trust@10": round(float(m["trust@10"]), 4),
                         "knn_overlap@10": round(float(m["knn_overlap@10"]), 4),
                         "reminds_pct": round(float(m["reminds_pct"]), 4),
                         "cohesion_ratio": rd["cohesion_ratio"]})

        def agg(key):
            v = np.array([r[key] for r in recs], dtype=float)
            return {"mean": round(float(v.mean()), 4), "std": round(float(v.std()), 4),
                    "min": round(float(v.min()), 4), "max": round(float(v.max()), 4)}

        cross, trust, ov = agg("cross_family_proximity"), agg("trust@10"), agg("knn_overlap@10")
        a_pass = int(sum(1 for r in recs if r["cross_family_proximity"] <= gate_line))
        b_pass = int(sum(1 for r in recs if r["trust@10"] >= GATE_B))
        row = {"candidate": name, "note": note, "post_hoc_selection": True,
               "supervised": is_semi, "seeds": list(SEEDS), "per_seed": recs,
               "cross_family_proximity": cross,
               "gate_a_delta_mean": round(float(cross["mean"] - base_cross), 4),
               "gate_a_pass_seeds": a_pass,
               "trust@10": trust, "gate_b_pass_seeds": b_pass,
               "knn_overlap@10": ov,
               "reminds_pct": agg("reminds_pct"),
               "cohesion_ratio": agg("cohesion_ratio"),
               "gate_a_verdict": ("PASS" if a_pass == len(SEEDS)
                                  else ("DROP" if a_pass == 0 else "REVIEW")),
               "gate_b_verdict": ("PASS" if b_pass == len(SEEDS)
                                  else ("DROP" if b_pass == 0 else "REVIEW"))}
        rows.append(row)
        print(f"  {name:<24}{cross['mean']:>15.4f} ± {cross['std']:<6.4f}"
              f"{cross['min']:>8.4f}{cross['max']:>8.4f}"
              f"{a_pass:>7}/{len(SEEDS)}"
              f"{trust['mean']:>13.4f} ± {trust['std']:<4.4f}"
              f"{b_pass:>7}/{len(SEEDS)}"
              f"{ov['mean']:>13.4f} ± {ov['std']:<4.4f}")

    print()
    print(f"  {'후보':<24}{'GateA':>8}{'GateB':>8}{'ratio(G) 평균±편차':>22}"
          f"{'정답간선(G)':>16}")
    for r in rows:
        print(f"  {r['candidate']:<24}{r['gate_a_verdict']:>8}{r['gate_b_verdict']:>8}"
              f"{r['cohesion_ratio']['mean']:>13.3f} ± {r['cohesion_ratio']['std']:<6.3f}"
              f"{r['reminds_pct']['mean']:>10.4f} ± {r['reminds_pct']['std']:<5.4f}")

    # 시드 편차보다 후보 간 차이가 큰지 — 이 답이 '아니오' 면 순위를 쓸 수 없다
    print()
    print("  후보 간 Gate A 차이 vs 시드 표준편차")
    mx = max(r["cross_family_proximity"]["std"] for r in rows)
    order = sorted(rows, key=lambda r: r["cross_family_proximity"]["mean"])
    print(f"    시드 표준편차 최대 {mx:.4f}")
    for a, b in zip(order, order[1:]):
        gap = b["cross_family_proximity"]["mean"] - a["cross_family_proximity"]["mean"]
        verdict = "구별 가능" if gap > 2 * mx else ("경계" if gap > mx else "구별 불가")
        print(f"    {a['candidate']:<24} -> {b['candidate']:<24}"
              f"차이 {gap:+.4f}  {verdict}")

    out = {
        "question": ("스윕의 Global 지표는 seed 42 한 번이었다. 최종 후보만 시드 5개에서 "
                     "다시 재고, 게이트를 시드마다 적용해 통과 개수를 본다"),
        "gates": {"gate_a_pass_line": gate_line, "gate_a_baseline": base_cross,
                  "gate_b_threshold": GATE_B, "population": "global1000",
                  "seed_rule": ("experiments/README.md — 5개 시드. 전부 통과 PASS · "
                                "일부만 통과 REVIEW · 전부 실패 DROP")},
        "selection_note": ("후보는 스윕 결과를 보고 골랐다 (사후 선택). 게이트 기준선은 "
                           "Phase 3b 에서 실행 전에 확정한 값을 그대로 쓴다"),
        "seeds": list(SEEDS),
        "candidates": rows,
        "max_seed_std_cross_family": mx,
    }
    with open(os.path.join(OUT_DIR, "seed_check.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print()
    print(f"총 소요 {time.time()-t0:.0f}초")
    print(f"  -> {OUT_DIR}/seed_check.json")


if __name__ == "__main__":
    main()

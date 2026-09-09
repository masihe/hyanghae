"""Phase 3d — 최종 challenger 검증. Family 0.50 + Perception 0.075 vs C8b.

팀 결정으로 후보 구조가 확정됐고, 남은 질문이 **하나**다.

    Family 0.50 + Perception 0.075 가 5개 seed 에서도 Gate A / Gate B 를 안정적으로
    지키면서 C8b 보다 더 명확한 향 계열 Territory 를 만드는가?

Phase 3c 격자에서 이 조합은 seed 42 기준으로 C8b 보다 영역 응집도가 높았고
(Korea 4.162 vs 3.913) trustworthiness 도 유지했다(Global 0.9231). 그런데 Global
게이트는 seed 42 한 번만 쟀고, Gate A 여유가 C8b 보다 훨씬 작았다
(+0.0269 vs -0.0342 · 합격선 0.3115).

**추가 가중치 탐색은 하지 않는다** (팀 결정). 후보 4개만 5개 seed 에서 비교한다.

    C1              Base 1.00                                   baseline
    Family 0.20     Base 0.80 + Family 0.20                     안전 대안
    C8b             Base 0.50 + Family 0.35 + Perception 0.15    메인
    Challenger      Base 0.425 + Family 0.50 + Perception 0.075  최종 challenger

비교 지표는 팀이 지정한 8개다.

    Gate A 통과 여부 · Gate B 통과 여부 · Korea 200 normalized cohesion ratio ·
    자기 계열 영역 위 향수 비율 · 영역 fragmentation · boundary perfume 유지 정도 ·
    kNN overlap@10 · cross-family proximity

여기에 Phase 3b 가 확정한 **고정 시험지(설명 가능성)와 방향성**을 기록 축으로 함께
낸다. 판정에는 쓰지 않지만, 빼면 회귀를 놓친다.

게이트는 Phase 3 에서 확정한 값을 그대로 쓴다. 이번 실험에서 다시 고르지 않는다.

    Gate A  계열 횡단 신뢰 쌍 근접도 <= 0.3115   (Global 1,000 · 412쌍)
    Gate B  trustworthiness@10 >= 0.90           (Global 1,000)

게이트는 **시드마다 따로 적용**해 통과 개수를 센다 (전부 PASS · 일부 REVIEW ·
전무 DROP). `experiments/README.md` 게이트 시드 규칙.

재현::

    python src/map/experiment_phase3d_challenger.py

산출  experiments/phase3d/{manifest.json, metrics.json, candidates.csv, per_seed.csv}

프로덕션 파일은 읽기만 한다. output/ · results/ 를 쓰지 않는다.
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
import experiment_phase3b_finalists as p3f      # noqa: E402
import experiment_phase3c_blend_sweep as p3c    # noqa: E402

OUT_DIR = os.path.join("experiments", "phase3d")
P3B_DIR = os.path.join("experiments", "phase3b")
P3C_DIR = os.path.join("experiments", "phase3c")
TOP200 = os.path.join("data", "korea_popularity", "korea_representative_perfumes_top200.csv")
ACCORD_DICT = os.path.join("..", "EDA", "analysis_outputs", "10_accord_dictionary.csv")

SEEDS = (42, 1, 2, 3, 4)
# Gate A 여유가 좁은 후보를 가리기 위한 확장 시드 (메인·challenger 만).
# README 시드 규칙 — 최악값이 게이트에서 0.01 이내면 자동 판정 금지 → REVIEW
SEEDS_EXT = (42, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14)
REVIEW_BAND = 0.01
GATE_B = 0.90
RARE_MAX_SHARE = 0.30

# (표시 이름, family_w, perception_w, 역할)
CANDIDATES = (
    ("C1", 0.00, 0.000, "baseline"),
    ("Family 0.20", 0.20, 0.000, "안전 대안"),
    ("C8b", 0.35, 0.150, "메인"),
    ("Challenger F0.50+P0.075", 0.50, 0.075, "최종 challenger"),
)
MAIN = "C8b"
CHALLENGER = "Challenger F0.50+P0.075"


def agg(vals, nd=4):
    v = np.asarray(vals, dtype=float)
    return {"mean": round(float(v.mean()), nd), "std": round(float(v.std()), nd),
            "min": round(float(v.min()), nd), "max": round(float(v.max()), nd)}


def main() -> None:
    os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))  # MAP/
    os.makedirs(OUT_DIR, exist_ok=True)
    t0 = time.time()

    print("=" * 96)
    print("Phase 3d — 최종 challenger 검증 (Family 0.50 + Perception 0.075 vs C8b)")
    print("=" * 96)

    ref = json.loads(open(os.path.join(P3B_DIR, "metrics.json"), encoding="utf-8").read())
    gate_line = ref["gate_a"]["pass_line"]
    base_cross = ref["gate_a"]["baseline_cross_family_proximity"]
    print(f"게이트 (Phase 3 확정) — Gate A <= {gate_line} (baseline {base_cross}) · "
          f"Gate B trust@10 >= {GATE_B} · Global 1,000 {ref['gate_a']['cross_pairs']}쌍")

    # ---- 입력 (Phase 3b·3c 와 동일 경로) ----
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
    res_g = es.family_scores(targets.accord_list.tolist(), p3b.SYSTEM)
    families = res_k["families"]
    lab_k, lab_g = res_k["argmax"], res_g["argmax"]
    M_k, M_g = res_k["M"], res_g["M"]
    Dp_k, nw, nm = p3b.perception_distance(korea_ids)
    Dp_g, _, _ = p3b.perception_distance(targets.id.astype(int).tolist())
    Df_k, Df_g = p3b.family_profile_distance(M_k), p3b.family_profile_distance(M_g)
    g_ids = targets.id.astype(int).tolist()

    # 고정 시험지 (기록 축) — 원본 note 문자열 / 원본 accord 보유율 < 0.30
    acc = pd.read_csv(ACCORD_DICT)
    share = dict(zip(acc.accord, acc.perfume_share))
    note_sets = [set(s) for s in korea.note_set]
    rare_sets = [{n for n, _ in lst if share.get(n, 1.0) < RARE_MAX_SHARE}
                 for lst in korea.accord_list]
    raw = pd.read_csv(sm.PERFUMES_CSV, low_memory=False,
                      usecols=p3b.VOTE_COLS).set_index("id").loc[korea_ids]
    seas = raw[["winter", "spring", "summer", "autumn"]].astype(float)
    st = seas.sum(axis=1)
    warmth = np.where(st >= p3b.MIN_VOTES,
                      ((seas.winter + seas.autumn) - (seas.summer + seas.spring))
                      / st.replace(0, np.nan), np.nan)
    gg = raw[["perceived_female", "perceived_female_leaning", "perceived_unisex",
              "perceived_male_leaning", "perceived_male"]].astype(float)
    gt = gg.sum(axis=1)
    masc = np.where(gt >= p3b.MIN_VOTES,
                    ((gg.perceived_male + 0.5 * gg.perceived_male_leaning)
                     - (gg.perceived_female + 0.5 * gg.perceived_female_leaning))
                    / gt.replace(0, np.nan), np.nan)

    print(f"Set B {len(families)}계열 · Korea 200 (신뢰 간선 {len(ce_k)}쌍) / "
          f"Global {len(g_ids)} (신뢰 간선 {len(ce_g)}쌍)")
    print(f"인식 축 투표 — 계절 {nw}/200 · 성별 {nm}/200")

    # ---- 기준점 재현 확인 ----
    print()
    print("-" * 96)
    print("기준점 재현 확인 (Phase 3c 기록과 일치해야 진행)")
    print("-" * 96)
    p3c_m = json.loads(open(os.path.join(P3C_DIR, "metrics.json"), encoding="utf-8").read())
    by_label = {r["label"]: r for r in p3c_m["sweep"]}
    checks = []
    for name, wf, wp, _role in CANDIDATES:
        lbl = p3c.label(wf, wp)
        want = by_label[lbl]
        c = p3b.umap_layout(p3c.blend(D_k, Df_k, Dp_k, wf, wp), 42)
        got_ratio = p3b.readability(c, lab_k, families)["cohesion_ratio"]
        got_ov = round(float(bm.evaluate_layout(c, D_k, index_of_k, ce_k)["knn_overlap@10"]), 4)
        for key, got, exp in (("korea_cohesion_ratio", got_ratio, want["korea_cohesion_ratio"]),
                              ("korea_knn_overlap10", got_ov, want["korea_knn_overlap10"])):
            ok = abs(got - exp) <= 5e-3
            checks.append({"point": name, "metric": key, "got": got, "expected": exp,
                           "ok": bool(ok)})
            print(f"  {name:<26}{key:<22}측정 {got:<10.4f}기록 {exp:<10.4f}"
                  f"{'PASS' if ok else 'FAIL'}")
    n_fail = sum(1 for c in checks if not c["ok"])
    print(f"\n재현 확인 {len(checks)-n_fail}/{len(checks)} PASS")
    if n_fail:
        raise SystemExit("기준점이 재현되지 않았다 — 입력이 달라졌으므로 중단한다")

    # ---- 후보별 5시드 측정 ----
    print()
    print("=" * 96)
    print(f"후보 {len(CANDIDATES)}개 × 시드 {len(SEEDS)}개 — Korea 200 (영역·경계) + "
          f"Global 1,000 (게이트)")
    print("=" * 96)

    rows, per_seed = [], []
    for name, wf, wp, role in CANDIDATES:
        Dbk = p3c.blend(D_k, Df_k, Dp_k, wf, wp)
        Dbg = p3c.blend(D_g, Df_g, Dp_g, wf, wp)
        recs = []
        for s in SEEDS:
            ck = p3b.umap_layout(Dbk, s)
            cg = p3b.umap_layout(Dbg, s)
            rdk = p3b.readability(ck, lab_k, families)
            rfk = p3b.region_field(ck, lab_k, families)
            mk = bm.evaluate_layout(ck, D_k, index_of_k, ce_k)
            grk = p3b.guardrail(ck, index_of_k, ce_k, lab_k, korea_ids)
            bck = p3b.boundary_consistency(ck, lab_k, families, M_k)
            grg = p3b.guardrail(cg, index_of_g, ce_g, lab_g, g_ids)
            mg = bm.evaluate_layout(cg, D_g, index_of_g, ce_g)
            rdg = p3b.readability(cg, lab_g, families)
            ex = p3f.explainability(ck, note_sets, rare_sets)
            ax = p3f.axis_meaning(ck, warmth, masc)
            r = {
                "candidate": name, "seed": s,
                "korea_cohesion_ratio": rdk["cohesion_ratio"],
                "korea_on_own_region": rfk["on_own_region"],
                "korea_fragments_total": rfk["fragments_total"],
                "korea_fragments_max": rfk["fragments_max"],
                "korea_families_with_region": rfk["families_with_region"],
                "korea_knn_overlap10": round(float(mk["knn_overlap@10"]), 4),
                "korea_trust10": round(float(mk["trust@10"]), 4),
                "korea_reminds_pct": round(float(mk["reminds_pct"]), 4),
                "korea_cross_family_proximity": grk.get("cross_family_proximity"),
                "korea_same_family_proximity": grk.get("same_family_proximity"),
                "boundary_center_ratio": bck["center_ratio_boundary"],
                "clear_center_ratio": bck["center_ratio_clear"],
                "boundary_gap": round(float(bck["center_ratio_boundary"]
                                            - bck["center_ratio_clear"]), 4),
                "global_cross_family_proximity": grg["cross_family_proximity"],
                "global_trust10": round(float(mg["trust@10"]), 4),
                "global_knn_overlap10": round(float(mg["knn_overlap@10"]), 4),
                "global_cohesion_ratio": rdg["cohesion_ratio"],
                "global_reminds_pct": round(float(mg["reminds_pct"]), 4),
                "shared_rare_accord_ge1": ex["shared_rare_accord_ge1"],
                "nearest_neighbor_unexplained": ex["nearest_neighbor_unexplained"],
                "y_warmth_rho": ax["y_warmth_rho"],
                "x_masculine_rho": ax["x_masculine_rho"],
            }
            recs.append(r)
            per_seed.append(r)

        def A(k, nd=4):
            return agg([r[k] for r in recs], nd)

        a_pass = int(sum(1 for r in recs
                         if r["global_cross_family_proximity"] <= gate_line))
        b_pass = int(sum(1 for r in recs if r["global_trust10"] >= GATE_B))

        # README 게이트 시드 규칙 — 통과 개수 + 최악값이 게이트에서 0.01 이내면 REVIEW
        def verdict(n, headroom):
            if n == 0:
                return "DROP"
            if n < len(SEEDS) or headroom < REVIEW_BAND:
                return "REVIEW"
            return "PASS"

        head_a = float(gate_line - max(r["global_cross_family_proximity"] for r in recs))
        head_b = float(min(r["global_trust10"] for r in recs) - GATE_B)

        row = {
            "candidate": name, "role": role,
            "base_w": round(1.0 - wf - wp, 3), "family_w": wf, "perception_w": wp,
            "gate_a_pass_seeds": a_pass, "gate_a_verdict": verdict(a_pass, head_a),
            "gate_b_pass_seeds": b_pass, "gate_b_verdict": verdict(b_pass, head_b),
            "gate_b_headroom_worst": round(head_b, 4),
            "global_cross_family_proximity": A("global_cross_family_proximity"),
            "gate_a_delta_mean": round(
                float(np.mean([r["global_cross_family_proximity"] for r in recs])
                      - base_cross), 4),
            "gate_a_headroom_worst": round(head_a, 4),
            "global_trust10": A("global_trust10"),
            "global_knn_overlap10": A("global_knn_overlap10"),
            "global_cohesion_ratio": A("global_cohesion_ratio", 3),
            "global_reminds_pct": A("global_reminds_pct"),
            "korea_cohesion_ratio": A("korea_cohesion_ratio", 3),
            "korea_on_own_region": A("korea_on_own_region"),
            "korea_fragments_total": A("korea_fragments_total", 1),
            "korea_fragments_max": A("korea_fragments_max", 1),
            "korea_knn_overlap10": A("korea_knn_overlap10"),
            "korea_trust10": A("korea_trust10"),
            "korea_reminds_pct": A("korea_reminds_pct"),
            "korea_cross_family_proximity": A("korea_cross_family_proximity"),
            "boundary_center_ratio": A("boundary_center_ratio"),
            "clear_center_ratio": A("clear_center_ratio"),
            "boundary_gap": A("boundary_gap"),
            "record_shared_rare_accord_ge1": A("shared_rare_accord_ge1"),
            "record_nearest_unexplained": A("nearest_neighbor_unexplained", 1),
            "record_y_warmth_rho": A("y_warmth_rho"),
            "record_x_masculine_rho": A("x_masculine_rho"),
        }
        rows.append(row)

    by_name = {r["candidate"]: r for r in rows}
    seed_of = {}
    for r in per_seed:
        seed_of.setdefault(r["candidate"], {})[r["seed"]] = r

    # ---- 게이트 ----
    print()
    print("게이트 (시드마다 따로 적용)")
    print(f"  {'후보':<26}{'횡단근접 평균±편차':>22}{'최악':>8}{'여유':>9}{'GateA':>13}"
          f"{'trust@10':>18}{'GateB':>13}")
    for r in rows:
        cr, tr = r["global_cross_family_proximity"], r["global_trust10"]
        print(f"  {r['candidate']:<26}{cr['mean']:>13.4f} ± {cr['std']:<6.4f}"
              f"{cr['max']:>8.4f}{r['gate_a_headroom_worst']:>+9.4f}"
              f"{r['gate_a_pass_seeds']:>8}/5 {r['gate_a_verdict']:<4}"
              f"{tr['mean']:>11.4f} ± {tr['std']:<4.4f}"
              f"{r['gate_b_pass_seeds']:>8}/5 {r['gate_b_verdict']:<4}")

    # ---- 팀 지정 지표 8개 ----
    print()
    print("팀 지정 비교 지표 (Korea 200 = 영역·경계 · Global 1,000 = 보호)")
    print(f"  {'후보':<26}{'K ratio':>15}{'영역위':>15}{'조각':>13}{'경계차이':>15}"
          f"{'K ov@10':>15}{'G 횡단':>15}")
    for r in rows:
        f_ = r["korea_fragments_total"]
        print(f"  {r['candidate']:<26}"
              f"{r['korea_cohesion_ratio']['mean']:>8.3f}±{r['korea_cohesion_ratio']['std']:<6.3f}"
              f"{r['korea_on_own_region']['mean']:>8.3f}±{r['korea_on_own_region']['std']:<6.3f}"
              f"{f_['mean']:>7.1f}±{f_['std']:<5.1f}"
              f"{r['boundary_gap']['mean']:>8.4f}±{r['boundary_gap']['std']:<6.4f}"
              f"{r['korea_knn_overlap10']['mean']:>8.4f}±{r['korea_knn_overlap10']['std']:<6.4f}"
              f"{r['global_cross_family_proximity']['mean']:>8.4f}"
              f"±{r['global_cross_family_proximity']['std']:<6.4f}")

    # ---- 기록 축 ----
    print()
    print("기록 축 (판정에 쓰지 않는다 — Phase 3b 고정 시험지와 방향성)")
    print(f"  {'후보':<26}{'rare accord':>14}{'설명불가':>12}{'y=계절':>12}{'x=성별':>12}"
          f"{'G ratio':>12}{'G ov@10':>12}")
    for r in rows:
        print(f"  {r['candidate']:<26}{r['record_shared_rare_accord_ge1']['mean']:>13.1%}"
              f"{r['record_nearest_unexplained']['mean']:>12.1f}"
              f"{r['record_y_warmth_rho']['mean']:>12.3f}"
              f"{r['record_x_masculine_rho']['mean']:>12.3f}"
              f"{r['global_cohesion_ratio']['mean']:>12.3f}"
              f"{r['global_knn_overlap10']['mean']:>12.4f}")

    # ---- challenger vs C8b: 시드를 짝지은 차이 ----
    print()
    print("=" * 96)
    print(f"질문 판정 — {CHALLENGER} 가 C8b 보다 더 명확한 Territory 를 만드는가")
    print("=" * 96)
    keys = [("korea_cohesion_ratio", "Korea 영역 ratio", 3, +1),
            ("korea_on_own_region", "자기 계열 영역 위", 4, +1),
            ("korea_fragments_total", "영역 조각 수", 1, -1),
            ("boundary_gap", "경계 향수 분리도", 4, +1),
            ("korea_knn_overlap10", "Korea overlap@10", 4, +1),
            ("global_cross_family_proximity", "Global 계열 횡단 근접도", 4, -1),
            ("global_trust10", "Global trust@10", 4, +1),
            ("global_knn_overlap10", "Global overlap@10", 4, +1),
            ("global_cohesion_ratio", "Global 영역 ratio", 3, +1)]
    print(f"  {'지표':<24}{'C8b':>11}{'Challenger':>13}{'짝지은 차이':>20}"
          f"{'유의':>7}{'부호':>8}  방향")
    diffs = []
    for k, ko, nd, good in keys:
        a = np.array([seed_of[MAIN][s][k] for s in SEEDS], dtype=float)
        b = np.array([seed_of[CHALLENGER][s][k] for s in SEEDS], dtype=float)
        d = b - a
        sig = abs(d.mean()) > 2 * d.std() if d.std() > 0 else abs(d.mean()) > 0
        better = int((d * good > 0).sum())
        arrow = "challenger 우세" if d.mean() * good > 0 else "C8b 우세"
        if abs(d.mean()) < 1e-12:
            arrow = "동일"
        diffs.append({"metric": k, "label": ko, "c8b_mean": round(float(a.mean()), nd),
                      "challenger_mean": round(float(b.mean()), nd),
                      "diff_mean": round(float(d.mean()), nd + 1),
                      "diff_std": round(float(d.std()), nd + 1),
                      "significant": bool(sig),
                      "challenger_better_seeds": better,
                      "higher_is_better": good > 0, "reading": arrow})
        print(f"  {ko:<24}{a.mean():>11.{nd}f}{b.mean():>13.{nd}f}"
              f"{d.mean():>+13.{nd}f} ± {d.std():<5.{nd}f}"
              f"{'예' if sig else '아니오':>7}{better:>6}/5  {arrow}")

    ch = by_name[CHALLENGER]
    passes = ch["gate_a_verdict"] == "PASS" and ch["gate_b_verdict"] == "PASS"
    print(f"  판정 규칙 — 통과 개수 {len(SEEDS)}/{len(SEEDS)} 이고 최악값 여유가 "
          f"{REVIEW_BAND} 이상일 때만 PASS (README 게이트 시드 규칙)")
    terr = [d for d in diffs if d["metric"] in
            ("korea_cohesion_ratio", "korea_on_own_region", "korea_fragments_total",
             "global_cohesion_ratio")]
    terr_win = sum(1 for d in terr if d["reading"] == "challenger 우세")
    print()
    print(f"  게이트 — Gate A {ch['gate_a_verdict']} ({ch['gate_a_pass_seeds']}/5) · "
          f"Gate B {ch['gate_b_verdict']} ({ch['gate_b_pass_seeds']}/5) · "
          f"최악 시드 여유 {ch['gate_a_headroom_worst']:+.4f}")
    print(f"  Territory 지표 4개 중 challenger 우세 {terr_win}/4")
    print(f"  -> 질문의 답: 게이트 안정 유지 "
          f"{'예' if passes else '아니오 (' + ch['gate_a_verdict'] + ')'} · "
          f"Territory 개선 {'예' if terr_win >= 3 else ('부분' if terr_win >= 2 else '아니오')}")

    # ---- Gate A 확장 시드 (메인 · challenger) ----
    print()
    print("=" * 96)
    print(f"Gate A 확장 시드 {len(SEEDS_EXT)}개 — 여유가 좁은 후보를 가린다 "
          f"(README 규칙: 최악값이 게이트에서 {REVIEW_BAND} 이내면 REVIEW)")
    print("=" * 96)
    print(f"  {'후보':<26}{'평균±편차':>20}{'최악':>9}{'여유':>9}{'통과':>9}"
          f"{'trust 최악':>12}{'GateB':>9}  판정")
    ext = {}
    for name, wf, wp, _role in CANDIDATES:
        if name not in (MAIN, CHALLENGER):
            continue
        Dbg = p3c.blend(D_g, Df_g, Dp_g, wf, wp)
        cs, ts = [], []
        for s in SEEDS_EXT:
            cg = p3b.umap_layout(Dbg, s)
            cs.append(p3b.guardrail(cg, index_of_g, ce_g, lab_g, g_ids)["cross_family_proximity"])
            ts.append(round(float(bm.evaluate_layout(cg, D_g, index_of_g, ce_g)["trust@10"]), 4))
        cs, ts = np.array(cs, float), np.array(ts, float)
        head = float(gate_line - cs.max())
        npass = int((cs <= gate_line).sum())
        v = ("REVIEW" if head < REVIEW_BAND
             else ("PASS" if npass == len(SEEDS_EXT) else "DROP"))
        ext[name] = {"seeds": list(SEEDS_EXT),
                     "per_seed_cross_family": [round(float(x), 4) for x in cs],
                     "cross_family_proximity": agg(cs),
                     "worst": round(float(cs.max()), 4),
                     "headroom_worst": round(head, 4),
                     "gate_a_pass_seeds": npass,
                     "gate_a_verdict_with_review_band": v,
                     "trust_worst": round(float(ts.min()), 4),
                     "gate_b_pass_seeds": int((ts >= GATE_B).sum())}
        print(f"  {name:<26}{cs.mean():>11.4f} ± {cs.std():<6.4f}{cs.max():>9.4f}"
              f"{head:>+9.4f}{npass:>6}/{len(SEEDS_EXT)}{ts.min():>12.4f}"
              f"{int((ts >= GATE_B).sum()):>6}/{len(SEEDS_EXT)}  {v}")
    a = np.array(ext[MAIN]["per_seed_cross_family"], float)
    b = np.array(ext[CHALLENGER]["per_seed_cross_family"], float)
    d = b - a
    ext_paired = {"diff_mean": round(float(d.mean()), 4), "diff_std": round(float(d.std()), 4),
                  "challenger_worse_seeds": int((d > 0).sum()), "n_seeds": len(SEEDS_EXT),
                  "significant": bool(abs(d.mean()) > 2 * d.std())}
    print()
    print(f"  짝지은 차이 (challenger − {MAIN}) {d.mean():+.4f} ± {d.std():.4f} · "
          f"challenger 가 나쁜 시드 {int((d>0).sum())}/{len(SEEDS_EXT)} · "
          f"유의 {'예' if ext_paired['significant'] else '아니오'}")

    # ---- 기록 ----
    pd.DataFrame(per_seed).to_csv(os.path.join(OUT_DIR, "per_seed.csv"),
                                  index=False, encoding="utf-8-sig")
    flat = []
    for r in rows:
        f_ = {"candidate": r["candidate"], "role": r["role"], "base_w": r["base_w"],
              "family_w": r["family_w"], "perception_w": r["perception_w"],
              "gate_a": r["gate_a_verdict"], "gate_a_pass_seeds": r["gate_a_pass_seeds"],
              "gate_a_headroom_worst": r["gate_a_headroom_worst"],
              "gate_b": r["gate_b_verdict"], "gate_b_pass_seeds": r["gate_b_pass_seeds"]}
        for k, v in r.items():
            if isinstance(v, dict):
                f_[k + "_mean"] = v["mean"]
                f_[k + "_std"] = v["std"]
        flat.append(f_)
    pd.DataFrame(flat).to_csv(os.path.join(OUT_DIR, "candidates.csv"),
                              index=False, encoding="utf-8-sig")

    metrics = {
        "question": ("Family 0.50 + Perception 0.075 가 5개 seed 에서도 Gate A / Gate B 를 "
                     "안정적으로 지키면서 C8b 보다 더 명확한 향 계열 Territory 를 만드는가"),
        "scope_note": "팀 결정 — 추가적인 대규모 가중치 탐색은 하지 않는다. 후보 4개만 비교",
        "blend_definition": "D_blend = (1-wf-wp)·D + wf·Df + wp·Dp",
        "candidates": [{"name": n, "family_w": wf, "perception_w": wp,
                        "base_w": round(1 - wf - wp, 3), "role": ro}
                       for n, wf, wp, ro in CANDIDATES],
        "seeds": list(SEEDS),
        "gates": {"gate_a": {"metric": "계열 횡단 신뢰 쌍 2D 근접도", "pass_line": gate_line,
                             "baseline": base_cross, "population": "global1000",
                             "cross_pairs": ref["gate_a"]["cross_pairs"]},
                  "gate_b": {"metric": "trustworthiness@10", "threshold": GATE_B,
                             "population": "global1000"},
                  "declared_before_run": True,
                  "seed_rule": ("시드마다 따로 적용 — 전무 DROP · 일부 통과 REVIEW · "
                                "전부 통과이고 최악값 여유 >= 0.01 일 때만 PASS"),
                  "review_band": REVIEW_BAND},
        "team_metrics": ["gate_a", "gate_b", "korea_cohesion_ratio", "korea_on_own_region",
                         "korea_fragments_total", "boundary_gap", "korea_knn_overlap10",
                         "global_cross_family_proximity"],
        "record_metrics": ["shared_rare_accord_ge1", "nearest_neighbor_unexplained",
                           "y_warmth_rho", "x_masculine_rho"],
        "reproduction_checks": checks,
        "reproduction_pass": len(checks) - n_fail,
        "reproduction_total": len(checks),
        "results": rows,
        "challenger_vs_main": {"main": MAIN, "challenger": CHALLENGER, "paired": diffs,
                               "challenger_gates_pass_5seed": bool(passes),
                               "territory_wins_of_4": terr_win},
        "gate_a_extended": {"review_band": REVIEW_BAND, "seeds": list(SEEDS_EXT),
                            "candidates": ext, "paired": ext_paired,
                            "rule": ("experiments/README.md — 최악값이 게이트에서 "
                                     "0.01 이내면 자동 판정 금지 → REVIEW")},
        "notes": {
            "korea_gate_use": ("Korea 200 의 계열 횡단 신뢰 쌍은 25쌍뿐이라 판정에 쓰지 않는다. "
                               "게이트 판정은 Global 1,000 에서만 한다"),
            "boundary_gap": ("경계 향수(계열 점수 margin < 0.10)의 중심거리비 − 명확한 향수의 "
                             "중심거리비. 클수록 경계 향수가 두 영역 사이에 놓인다"),
            "explainability": ("고정 시험지 — 원본 note 문자열과 원본 accord(보유율<0.30). "
                               "방식이 무엇이든 기준을 바꾸지 않는다"),
            "axis_meaning": "회전 정렬 후 상관. 회전은 등거리 변환이라 다른 지표에 영향이 없다",
        },
    }
    with open(os.path.join(OUT_DIR, "metrics.json"), "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=1)
        f.write("\n")

    manifest = {
        "experiment": "P3D_CHALLENGER",
        "phase": "3d",
        "title": "최종 challenger 검증 — Family 0.50 + Perception 0.075 vs C8b",
        "family_system": f"Set B — {es.MAPPING_VERSION} {len(families)}계열",
        "families": families,
        "populations": {"korea200": len(korea_ids), "global1000": len(g_ids)},
        "confident_edges": {"korea200": len(ce_k), "global1000": len(ce_g)},
        "seeds": list(SEEDS),
        "candidates": len(CANDIDATES),
        "inputs": {
            "top200": {"path": TOP200, "sha256": p3b.sha256(TOP200)},
            "phase3b_metrics": {"path": os.path.join(P3B_DIR, "metrics.json"),
                                "sha256": p3b.sha256(os.path.join(P3B_DIR, "metrics.json"))},
            "phase3c_metrics": {"path": os.path.join(P3C_DIR, "metrics.json"),
                                "sha256": p3b.sha256(os.path.join(P3C_DIR, "metrics.json"))},
            "accord_dictionary": {"path": ACCORD_DICT, "sha256": p3b.sha256(ACCORD_DICT)},
        },
        "projection": {"umap": "n_neighbors=10 min_dist=0.1 metric=precomputed"},
        "holdout_untouched": "data/korea_popularity/evaluation/gold_set_test.csv — 열지 않았다",
        "seeds_extended_gate_a": list(SEEDS_EXT),
        "writes": ["experiments/phase3d/metrics.json", "experiments/phase3d/manifest.json",
                   "experiments/phase3d/candidates.csv", "experiments/phase3d/per_seed.csv"],
        "elapsed_sec": round(time.time() - t0, 1),
    }
    with open(os.path.join(OUT_DIR, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)
        f.write("\n")

    print()
    print(f"총 소요 {time.time()-t0:.0f}초")
    print(f"  -> {OUT_DIR}/metrics.json · manifest.json · candidates.csv · per_seed.csv")


if __name__ == "__main__":
    main()

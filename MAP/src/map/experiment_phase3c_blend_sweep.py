"""Phase 3c — C8b 혼합 가중 스윕 + TriMap-dist 재검증.

Phase 3b 는 C8b 를 (계열 0.35 · 인식 0.15) **한 점에서만** 쟀다. 그 점이 최적인지
확인한 적이 없고, 팀 결정 ④ 가 C3 semi w=0.35 를 대안으로 남긴 조건이
"C8b 의 local overlap 손실이 후속 실험에서도 해결되지 않을 경우" 다.

그래서 두 가지를 잰다.

  1. 혼합 가중 격자 — 지역 가독성을 얼마나 유지하면서 이웃 보존 손실을 줄일 수 있는가
  2. TriMap-dist 재검증 (팀 결정 ②) — 같은 혼합 거리를 다른 투영으로 만들면
     사람 유사성 지표가 더 좋아지는가

거리 정의::

    D_blend = (1 - wf - wp)·D + wf·Df + wp·Dp

    D  = Base Similarity 거리 (0.5·accord cosine + 0.5·note IDF Jaccard)  — D1
    Df = 계열 프로파일 코사인 거리 (Set B 9계열 Family Score)              — 팀 결정 ③
    Dp = 사용자 투표 인식 축 거리 (계절 따뜻함 · 성별 남성향)               — Phase 0 축

격자에 기준점 세 개가 들어 있다 — (0, 0) 재계산 baseline · (0, 0.15) C8a ·
(0.35, 0.15) C8b. 그 세 점이 Phase 3b 기록과 일치하는지 assert 로 먼저 확인하고
결과를 낸다. 일치하지 않으면 입력이 달라진 것이므로 중단한다.

게이트는 Phase 3b 와 동일하다. 실행 전에 확정했고 결과를 보고 바꾸지 않는다.

  Gate A  계열 횡단 신뢰 쌍 근접도 <= baseline + 0.05  (Global 1,000)
  Gate B  trustworthiness@10 >= 0.90                  (Global 1,000)

재현::

    python src/map/experiment_phase3c_blend_sweep.py

산출  experiments/phase3c/{manifest.json, metrics.json, sweep.csv, trimap.csv}

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

OUT_DIR = os.path.join("experiments", "phase3c")
P3B_DIR = os.path.join("experiments", "phase3b")
TOP200 = os.path.join("data", "korea_popularity", "korea_representative_perfumes_top200.csv")
V2_JSON = os.path.join("output", "korea_scent_map_v2.json")     # 읽기만 한다
ACCORD_DICT = os.path.join("..", "EDA", "analysis_outputs", "10_accord_dictionary.csv")

SEEDS = (42, 1, 2, 3, 4)
TRIMAP_SEEDS = (42, 1, 2)          # TriMap 은 느려서 3개만. 기록 축이지 게이트가 아니다
NEIGHBOR_K = 10
GATE_B = 0.90
RARE_MAX_SHARE = 0.30
TOL = 5e-4                         # 기준점 재현 허용 오차 (기록값이 소수 4자리)

# 혼합 가중 격자. wf + wp < 1 이어야 원본 거리 성분이 남는다.
FAMILY_W = (0.00, 0.10, 0.20, 0.35, 0.50, 0.65)
PERCEPT_W = (0.00, 0.075, 0.15, 0.30)

# TriMap 재검증 지점 — 실행 전에 고정한다 (스윕 결과를 보고 고르지 않는다).
TRIMAP_POINTS = ((0.00, 0.00), (0.00, 0.15), (0.20, 0.15), (0.35, 0.15))

# 지도 비교 그림용으로 Korea seed 42 좌표를 남기는 지점.
KEEP_COORDS = ((0.00, 0.00), (0.10, 0.00), (0.20, 0.00), (0.00, 0.15), (0.35, 0.15))


def label(wf, wp):
    return f"wf={wf:.3g} wp={wp:.3g}"


def blend(D, Df, Dp, wf, wp):
    base = 1.0 - wf - wp
    assert base > 0, "wf + wp < 1 이어야 한다"
    return base * D + wf * Df + wp * Dp


def trimap_dist(D, seed):
    import trimap
    return np.asarray(
        trimap.TorchTRIMAP(n_dims=2, n_inliers=10, n_outliers=5, n_random=5,
                           use_dist_matrix=True, apply_pca=False,
                           random_state=seed, verbose=False,
                           ).fit_transform(D).cpu().numpy(), dtype=float)


def main() -> None:
    os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))  # MAP/
    os.makedirs(OUT_DIR, exist_ok=True)
    t0 = time.time()

    print("=" * 84)
    print("Phase 3c — C8b 혼합 가중 스윕 + TriMap-dist 재검증")
    print("=" * 84)

    ref = json.loads(open(os.path.join(P3B_DIR, "metrics.json"), encoding="utf-8").read())
    gate_line = ref["gate_a"]["pass_line"]
    base_cross = ref["gate_a"]["baseline_cross_family_proximity"]
    C1_G = ref["global1000"]["C1 post-hoc"]
    C1_K = ref["korea200"]["C1 post-hoc"]
    C8A_G = ref["global1000"]["C8a perception b=0.15"]
    C8B_G = ref["global1000"]["C8b family .35 + perc .15"]
    C8B_K = ref["korea200"]["C8b family .35 + perc .15"]
    C3_G = ref["global1000"]["C3 semi w=0.35"]
    C3_K = ref["korea200"]["C3 semi w=0.35"]

    # ---- 입력 (Phase 3b 와 동일 경로) ----
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

    # 고정 시험지 재료 — 원본 note 문자열 / 원본 accord(보유율 < 0.30)
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
    g = raw[["perceived_female", "perceived_female_leaning", "perceived_unisex",
             "perceived_male_leaning", "perceived_male"]].astype(float)
    gt = g.sum(axis=1)
    masc = np.where(gt >= p3b.MIN_VOTES,
                    ((g.perceived_male + 0.5 * g.perceived_male_leaning)
                     - (g.perceived_female + 0.5 * g.perceived_female_leaning))
                    / gt.replace(0, np.nan), np.nan)

    print(f"Set B {len(families)}계열 · Korea 200 / Global {len(g_ids)} · "
          f"신뢰 간선 Korea {len(ce_k)} / Global {len(ce_g)}")
    print(f"인식 축 투표 — 계절 {nw}/200 · 성별 {nm}/200")
    print(f"기준값 (Phase 3b) — Gate A 합격선 {gate_line} (baseline {base_cross}) · "
          f"Gate B {GATE_B}")

    # ------------------------------------------------------------------
    # 1) 기준점 재현 확인 — 일치하지 않으면 중단
    # ------------------------------------------------------------------
    print()
    print("-" * 84)
    print("기준점 재현 확인 (Phase 3b 기록과 소수 4자리 일치해야 진행)")
    print("-" * 84)

    def global_block(coords):
        gr = p3b.guardrail(coords, index_of_g, ce_g, lab_g, g_ids)
        m = bm.evaluate_layout(coords, D_g, index_of_g, ce_g)
        rd = p3b.readability(coords, lab_g, families)
        return gr, {k: round(float(v), 4) for k, v in m.items()}, rd

    checks = []
    for (wf, wp), expect, tag in (
        ((0.00, 0.15), C8A_G, "C8a"),
        ((0.35, 0.15), C8B_G, "C8b"),
    ):
        c = p3b.umap_layout(blend(D_g, Df_g, Dp_g, wf, wp), 42)
        gr, m, rd = global_block(c)
        for key, got, want in (
            ("cross_family_proximity", gr["cross_family_proximity"],
             expect["guardrail"]["cross_family_proximity"]),
            ("trust@10", m["trust@10"], expect["layout"]["trust@10"]),
            ("knn_overlap@10", m["knn_overlap@10"], expect["layout"]["knn_overlap@10"]),
            ("cohesion_ratio", rd["cohesion_ratio"], expect["readability"]["cohesion_ratio"]),
        ):
            ok = abs(got - want) <= (TOL if key != "cohesion_ratio" else 5e-3)
            checks.append({"point": tag, "metric": key, "got": got, "expected": want,
                           "ok": bool(ok)})
            print(f"  {tag:<5}{key:<24}측정 {got:<10.4f}기록 {want:<10.4f}"
                  f"{'PASS' if ok else 'FAIL'}")

    # Korea (0,0) 재계산 = v2 json 좌표(균등 배율 정규화)와 지표가 같아야 한다
    doc = json.loads(open(V2_JSON, encoding="utf-8").read())
    by_id = {p["fragrantica_id"]: (p["x"], p["y"]) for p in doc["points"]}
    base_k_v2 = np.array([by_id[i] for i in korea_ids], dtype=float)
    c00_k = p3b.umap_layout(D_k, 42)
    m00 = bm.evaluate_layout(c00_k, D_k, index_of_k, ce_k)
    rd00 = p3b.readability(c00_k, lab_k, families)
    for key, got, want in (
        ("trust@10", round(float(m00["trust@10"]), 4), C1_K["layout"]["trust@10"]),
        ("knn_overlap@10", round(float(m00["knn_overlap@10"]), 4),
         C1_K["layout"]["knn_overlap@10"]),
        ("cohesion_ratio", rd00["cohesion_ratio"], C1_K["readability_seed42"]["cohesion_ratio"]),
    ):
        ok = abs(got - want) <= 5e-3
        checks.append({"point": "Korea (0,0) vs v2 C1", "metric": key, "got": got,
                       "expected": want, "ok": bool(ok)})
        print(f"  {'(0,0)':<5}{key:<24}측정 {got:<10.4f}기록 {want:<10.4f}"
              f"{'PASS' if ok else 'FAIL'}")

    n_fail = sum(1 for c in checks if not c["ok"])
    print(f"\n재현 확인 {len(checks) - n_fail}/{len(checks)} PASS")
    if n_fail:
        raise SystemExit("기준점이 재현되지 않았다 — 입력이 달라졌으므로 중단한다")

    # ------------------------------------------------------------------
    # 2) 혼합 가중 격자
    # ------------------------------------------------------------------
    grid = [(wf, wp) for wf in FAMILY_W for wp in PERCEPT_W if wf + wp < 1.0]
    print()
    print("=" * 84)
    print(f"혼합 가중 격자 {len(grid)}점 — Korea 200 (시드 {len(SEEDS)}개) · "
          f"Global 1,000 (seed 42)")
    print("=" * 84)
    print(f"  {'계열w':>6}{'인식w':>7}{'K ratio':>9}{'시드편차':>9}{'영역위':>8}{'조각':>6}"
          f"{'K ov':>8}{'G횡단':>8}{'GateAΔ':>9}{'G trust':>9}{'G ov':>8}"
          f"{'G ratio':>9}  판정")

    rows = []
    kept = {}
    for wf, wp in grid:
        ratios, coord_list = [], []
        for s in SEEDS:
            c = p3b.umap_layout(blend(D_k, Df_k, Dp_k, wf, wp), s)
            coord_list.append(c)
            ratios.append(p3b.readability(c, lab_k, families)["cohesion_ratio"])
        c42 = coord_list[0]
        if (wf, wp) in KEEP_COORDS:
            kept[label(wf, wp)] = c42
        rdk = p3b.readability(c42, lab_k, families)
        rfk = p3b.region_field(c42, lab_k, families)
        mk = bm.evaluate_layout(c42, D_k, index_of_k, ce_k)
        grk = p3b.guardrail(c42, index_of_k, ce_k, lab_k, korea_ids)
        ex = p3f.explainability(c42, note_sets, rare_sets)
        ax = p3f.axis_meaning(c42, warmth, masc)

        cg = p3b.umap_layout(blend(D_g, Df_g, Dp_g, wf, wp), 42)
        grg, mg, rdg = global_block(cg)
        prox = grg["cross_family_proximity"]
        delta = round(float(prox - base_cross), 4)
        gate_a = prox <= gate_line
        gate_b = mg["trust@10"] >= GATE_B

        rows.append({
            "family_w": wf, "perception_w": wp, "base_w": round(1.0 - wf - wp, 3),
            "label": label(wf, wp),
            "korea_cohesion_ratio": rdk["cohesion_ratio"],
            "korea_ratio_seed_mean": round(float(np.mean(ratios)), 3),
            "korea_ratio_seed_std": round(float(np.std(ratios)), 3),
            "korea_ratio_seed_min": round(float(np.min(ratios)), 3),
            "korea_seed_collapsed": bool(np.min(ratios) < 0.7 * np.mean(ratios)),
            "korea_neighborhood_top_family_share": rdk["neighborhood_top_family_share"],
            "korea_size_max_share": rdk["size_max_share"],
            "korea_on_own_region": (rfk or {}).get("on_own_region"),
            "korea_fragments_total": (rfk or {}).get("fragments_total"),
            "korea_trust10": mk["trust@10"],
            "korea_knn_overlap10": mk["knn_overlap@10"],
            "korea_reminds_pct": mk["reminds_pct"],
            "korea_cross_family_proximity": grk.get("cross_family_proximity"),
            "korea_same_family_proximity": grk.get("same_family_proximity"),
            "shared_note_ge1": ex["shared_note_ge1"],
            "shared_rare_accord_ge1": ex["shared_rare_accord_ge1"],
            "nearest_neighbor_unexplained": ex["nearest_neighbor_unexplained"],
            "y_warmth_rho": ax["y_warmth_rho"],
            "x_masculine_rho": ax["x_masculine_rho"],
            "global_cross_family_proximity": prox,
            "global_same_family_proximity": grg.get("same_family_proximity"),
            "gate_a_delta": delta,
            "gate_a": bool(gate_a),
            "global_trust10": mg["trust@10"],
            "gate_b": bool(gate_b),
            "global_knn_overlap10": mg["knn_overlap@10"],
            "global_reminds_pct": mg["reminds_pct"],
            "global_cohesion_ratio": rdg["cohesion_ratio"],
            "overlap_loss_vs_c1_global": round(
                float(C1_G["layout"]["knn_overlap@10"] - mg["knn_overlap@10"]), 4),
            "region_gain_vs_c1_korea": round(
                float(rdk["cohesion_ratio"] - C1_K["readability_seed42"]["cohesion_ratio"]), 3),
            "passes_both": bool(gate_a and gate_b),
        })
        r = rows[-1]
        print(f"  {wf:>6.2f}{wp:>7.3f}{r['korea_cohesion_ratio']:>9.3f}"
              f"{r['korea_ratio_seed_std']:>9.3f}"
              f"{(r['korea_on_own_region'] or float('nan')):>8.3f}"
              f"{(r['korea_fragments_total'] if r['korea_fragments_total'] is not None else -1):>6}"
              f"{r['korea_knn_overlap10']:>8.4f}{prox:>8.4f}{delta:>+9.4f}"
              f"{r['global_trust10']:>9.4f}{r['global_knn_overlap10']:>8.4f}"
              f"{r['global_cohesion_ratio']:>9.3f}  "
              f"{'○' if r['passes_both'] else ('A✕' if not gate_a else 'B✕')}")

    sweep = pd.DataFrame(rows)
    sweep.to_csv(os.path.join(OUT_DIR, "sweep.csv"), index=False, encoding="utf-8-sig")

    frames = [pd.DataFrame({"method": name, "fragrantica_id": korea_ids,
                            "x": c[:, 0], "y": c[:, 1], "family": lab_k})
              for name, c in kept.items()]
    pd.concat(frames).to_csv(os.path.join(OUT_DIR, "coordinates_korea200.csv"),
                             index=False, encoding="utf-8-sig")

    # ------------------------------------------------------------------
    # 3) 팀 결정 ④ 가 묻는 질문 — 이웃 보존을 지키면서 지역을 얻는 점이 있는가
    # ------------------------------------------------------------------
    ok = sweep[sweep.passes_both]
    print()
    print("=" * 84)
    print("팀 결정 ④ 판정 — C8b 계열 혼합으로 local overlap 손실을 줄일 수 있는가")
    print("=" * 84)
    c1_ov = C1_G["layout"]["knn_overlap@10"]
    c3_ov = C3_G["layout"]["knn_overlap@10"]
    c3_ratio_k = C3_K["readability_seed42"]["cohesion_ratio"]
    print(f"  기준 — C1 Global overlap@10 {c1_ov:.4f} · Korea ratio "
          f"{C1_K['readability_seed42']['cohesion_ratio']:.3f}")
    print(f"  대안 — C3 semi w=0.35 overlap@10 {c3_ov:.4f} (손실 {c1_ov-c3_ov:+.4f}) · "
          f"Korea ratio {c3_ratio_k:.3f} · Gate A {C3_G['gate_a_delta']:+.4f}")
    print(f"  현행 C8b — overlap@10 {C8B_G['layout']['knn_overlap@10']:.4f} "
          f"(손실 {c1_ov-C8B_G['layout']['knn_overlap@10']:+.4f}) · Korea ratio "
          f"{C8B_K['readability_seed42']['cohesion_ratio']:.3f} · "
          f"Gate A {C8B_G['gate_a_delta']:+.4f}")
    print()

    # Pareto — 지역 가독성(Korea ratio) 최대 · Global overlap@10 최대
    def dominated(r, others):
        return any((o.korea_cohesion_ratio >= r.korea_cohesion_ratio
                    and o.global_knn_overlap10 >= r.global_knn_overlap10
                    and (o.korea_cohesion_ratio > r.korea_cohesion_ratio
                         or o.global_knn_overlap10 > r.global_knn_overlap10))
                   for o in others)
    front = [r for r in ok.itertuples(index=False)
             if not dominated(r, [o for o in ok.itertuples(index=False) if o.label != r.label])]
    front = sorted(front, key=lambda r: -r.korea_cohesion_ratio)
    print("  Pareto (지역 가독성 × Global overlap@10, 두 게이트 통과 안에서)")
    print(f"    {'지점':<18}{'K ratio':>9}{'G ov':>8}{'손실':>8}{'GateAΔ':>9}{'G trust':>9}"
          f"{'rare':>8}{'y=계절':>8}")
    for r in front:
        print(f"    {r.label:<18}{r.korea_cohesion_ratio:>9.3f}"
              f"{r.global_knn_overlap10:>8.4f}{r.overlap_loss_vs_c1_global:>+8.4f}"
              f"{r.gate_a_delta:>+9.4f}{r.global_trust10:>9.4f}"
              f"{r.shared_rare_accord_ge1:>8.1%}{r.y_warmth_rho:>8.3f}")

    # 조건별 최선 — 임계는 기록값에서 나온다 (사후에 만든 숫자가 아니다)
    conditions = {
        "no_overlap_loss (>= C3 semi 0.35)": ok[ok.global_knn_overlap10 >= c3_ov],
        "loss <= 0.02": ok[ok.overlap_loss_vs_c1_global <= 0.02],
        "loss <= 0.04": ok[ok.overlap_loss_vs_c1_global <= 0.04],
        "any (게이트만)": ok,
    }
    print()
    print("  조건별 최고 지역 가독성")
    print(f"    {'조건':<34}{'n':>4}{'지점':>18}{'K ratio':>9}{'G ov':>8}{'GateAΔ':>9}")
    best_by_cond = {}
    for cond, sub in conditions.items():
        if len(sub) == 0:
            best_by_cond[cond] = None
            print(f"    {cond:<34}{0:>4}{'—':>18}")
            continue
        b = sub.loc[sub.korea_cohesion_ratio.idxmax()]
        best_by_cond[cond] = {"label": b.label, "family_w": float(b.family_w),
                              "perception_w": float(b.perception_w),
                              "korea_cohesion_ratio": float(b.korea_cohesion_ratio),
                              "global_knn_overlap10": float(b.global_knn_overlap10),
                              "gate_a_delta": float(b.gate_a_delta),
                              "global_trust10": float(b.global_trust10)}
        print(f"    {cond:<34}{len(sub):>4}{b.label:>18}{b.korea_cohesion_ratio:>9.3f}"
              f"{b.global_knn_overlap10:>8.4f}{b.gate_a_delta:>+9.4f}")

    # ------------------------------------------------------------------
    # 4) TriMap-dist 재검증 (팀 결정 ②)
    # ------------------------------------------------------------------
    print()
    print("=" * 84)
    print("TriMap-dist 재검증 — 같은 혼합 거리를 다른 투영으로 (팀 결정 ②)")
    print("=" * 84)
    print(f"  {'지점':<18}{'투영':<12}{'K ratio':>9}{'K ov':>8}{'K정답':>8}"
          f"{'G횡단':>8}{'GateAΔ':>9}{'G trust':>9}{'G ov':>8}{'G ratio':>9}  판정")

    tri_rows = []
    tri_points = list(TRIMAP_POINTS)
    pick = best_by_cond.get("any (게이트만)")
    if pick and (pick["family_w"], pick["perception_w"]) not in tri_points:
        tri_points.append((pick["family_w"], pick["perception_w"]))
    for wf, wp in tri_points:
        post_hoc = (wf, wp) not in TRIMAP_POINTS
        Dbk = blend(D_k, Df_k, Dp_k, wf, wp)
        Dbg = blend(D_g, Df_g, Dp_g, wf, wp)
        for proj in ("UMAP", "TriMap-dist"):
            if proj == "UMAP":
                ck = [p3b.umap_layout(Dbk, s) for s in TRIMAP_SEEDS]
                cg = p3b.umap_layout(Dbg, 42)
            else:
                ck = [trimap_dist(Dbk, s) for s in TRIMAP_SEEDS]
                cg = trimap_dist(Dbg, 42)
            ratios = [p3b.readability(c, lab_k, families)["cohesion_ratio"] for c in ck]
            rdk = p3b.readability(ck[0], lab_k, families)
            rfk = p3b.region_field(ck[0], lab_k, families)
            mk = bm.evaluate_layout(ck[0], D_k, index_of_k, ce_k)
            grk = p3b.guardrail(ck[0], index_of_k, ce_k, lab_k, korea_ids)
            ex = p3f.explainability(ck[0], note_sets, rare_sets)
            grg, mg, rdg = global_block(cg)
            prox = grg["cross_family_proximity"]
            delta = round(float(prox - base_cross), 4)
            gate_a = prox <= gate_line
            gate_b = mg["trust@10"] >= GATE_B
            tri_rows.append({
                "family_w": wf, "perception_w": wp, "label": label(wf, wp),
                "projection": proj, "point_predeclared": not post_hoc,
                "korea_cohesion_ratio": rdk["cohesion_ratio"],
                "korea_ratio_seed_mean": round(float(np.mean(ratios)), 3),
                "korea_ratio_seed_std": round(float(np.std(ratios)), 3),
                "korea_seeds": len(TRIMAP_SEEDS),
                "korea_on_own_region": (rfk or {}).get("on_own_region"),
                "korea_fragments_total": (rfk or {}).get("fragments_total"),
                "korea_trust10": mk["trust@10"],
                "korea_knn_overlap10": mk["knn_overlap@10"],
                "korea_reminds_pct": mk["reminds_pct"],
                "korea_cross_family_proximity": grk.get("cross_family_proximity"),
                "shared_rare_accord_ge1": ex["shared_rare_accord_ge1"],
                "nearest_neighbor_unexplained": ex["nearest_neighbor_unexplained"],
                "global_cross_family_proximity": prox,
                "gate_a_delta": delta, "gate_a": bool(gate_a),
                "global_trust10": mg["trust@10"], "gate_b": bool(gate_b),
                "global_knn_overlap10": mg["knn_overlap@10"],
                "global_reminds_pct": mg["reminds_pct"],
                "global_cohesion_ratio": rdg["cohesion_ratio"],
                "passes_both": bool(gate_a and gate_b),
            })
            r = tri_rows[-1]
            print(f"  {label(wf, wp):<18}{proj:<12}{r['korea_cohesion_ratio']:>9.3f}"
                  f"{r['korea_knn_overlap10']:>8.4f}{r['korea_reminds_pct']:>8.4f}"
                  f"{prox:>8.4f}{delta:>+9.4f}{r['global_trust10']:>9.4f}"
                  f"{r['global_knn_overlap10']:>8.4f}{r['global_cohesion_ratio']:>9.3f}  "
                  f"{'○' if r['passes_both'] else ('A✕' if not gate_a else 'B✕')}")

    tri = pd.DataFrame(tri_rows)
    tri.to_csv(os.path.join(OUT_DIR, "trimap.csv"), index=False, encoding="utf-8-sig")

    print()
    print("  같은 혼합 거리에서 투영만 바꾼 차이 (TriMap-dist − UMAP)")
    print(f"    {'지점':<18}{'ΔGateA':>9}{'ΔK ratio':>10}{'ΔK ov':>9}{'ΔG trust':>10}"
          f"{'ΔK정답':>9}")
    proj_delta = []
    for lb in tri.label.unique():
        u = tri[(tri.label == lb) & (tri.projection == "UMAP")].iloc[0]
        t = tri[(tri.label == lb) & (tri.projection == "TriMap-dist")].iloc[0]
        d = {"label": lb,
             "d_gate_a": round(float(t.gate_a_delta - u.gate_a_delta), 4),
             "d_korea_cohesion_ratio": round(float(t.korea_cohesion_ratio
                                                   - u.korea_cohesion_ratio), 3),
             "d_korea_knn_overlap10": round(float(t.korea_knn_overlap10
                                                  - u.korea_knn_overlap10), 4),
             "d_global_trust10": round(float(t.global_trust10 - u.global_trust10), 4),
             "d_korea_reminds_pct": round(float(t.korea_reminds_pct
                                                - u.korea_reminds_pct), 4)}
        proj_delta.append(d)
        print(f"    {lb:<18}{d['d_gate_a']:>+9.4f}{d['d_korea_cohesion_ratio']:>+10.3f}"
              f"{d['d_korea_knn_overlap10']:>+9.4f}{d['d_global_trust10']:>+10.4f}"
              f"{d['d_korea_reminds_pct']:>+9.4f}")

    # ------------------------------------------------------------------
    # 5) 기록
    # ------------------------------------------------------------------
    metrics = {
        "question": ("Phase 3b 가 C8b 를 한 점(계열 0.35 · 인식 0.15)에서만 쟀다. "
                     "가중을 바꾸면 이웃 보존 손실을 줄이면서 지역 가독성을 얻을 수 있는가. "
                     "그리고 같은 혼합 거리를 TriMap-dist 로 만들면 더 나아지는가"),
        "blend_definition": "D_blend = (1-wf-wp)·D + wf·Df + wp·Dp",
        "distance_components": {
            "D": "Base Similarity 거리 — 0.5·accord cosine(L2) + 0.5·note IDF Jaccard (D1)",
            "Df": f"계열 프로파일 코사인 거리 — Set B {len(families)}계열 Family Score (팀 결정 ③)",
            "Dp": "사용자 투표 인식 축 거리 — 계절 따뜻함 · 성별 남성향 (Phase 0)",
        },
        "grid": {"family_w": list(FAMILY_W), "perception_w": list(PERCEPT_W),
                 "points": len(grid), "constraint": "wf + wp < 1"},
        "seeds": {"umap": list(SEEDS), "trimap": list(TRIMAP_SEEDS),
                  "global_population": "seed 42 only"},
        "gates": {
            "gate_a": {"metric": "계열 횡단 신뢰 쌍 2D 근접도", "population": "global1000",
                       "baseline": base_cross, "margin": 0.05, "pass_line": gate_line,
                       "cross_pairs": ref["gate_a"]["cross_pairs"]},
            "gate_b": {"metric": "trustworthiness@10", "population": "global1000",
                       "threshold": GATE_B},
            "declared_before_run": True,
        },
        "reference_points": {
            "C1 post-hoc": {"global": C1_G["layout"], "korea_ratio":
                            C1_K["readability_seed42"]["cohesion_ratio"]},
            "C3 semi w=0.35": {"global": C3_G["layout"], "korea_ratio": c3_ratio_k,
                               "gate_a_delta": C3_G["gate_a_delta"]},
            "C8b family .35 + perc .15": {
                "global": C8B_G["layout"],
                "korea_ratio": C8B_K["readability_seed42"]["cohesion_ratio"],
                "gate_a_delta": C8B_G["gate_a_delta"]},
        },
        "reproduction_checks": checks,
        "reproduction_pass": len(checks) - n_fail,
        "reproduction_total": len(checks),
        "sweep": rows,
        "pareto_front": [r.label for r in front],
        "best_by_condition": best_by_cond,
        "trimap": tri_rows,
        "projection_delta": proj_delta,
        "trimap_points_predeclared": [list(p) for p in TRIMAP_POINTS],
        "notes": {
            "korea_gate_use": ("Korea 200 의 계열 횡단 신뢰 쌍은 표본이 작아 판정에 쓰지 않는다. "
                               "게이트 판정은 Global 1,000 에서만 한다"),
            "stability": "팀 결정 ④ — 안정성은 기록 축. 구조 붕괴 여부만 본다",
            "explainability": ("고정 시험지 — 원본 note 문자열과 원본 accord(보유율<0.30). "
                               "방식이 무엇이든 기준을 바꾸지 않는다"),
            "axis_meaning": "회전 정렬 후 상관. 회전은 등거리 변환이라 다른 지표에 영향이 없다",
        },
    }
    with open(os.path.join(OUT_DIR, "metrics.json"), "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=1)
        f.write("\n")

    manifest = {
        "experiment": "P3C_BLEND_SWEEP",
        "phase": "3c",
        "title": "C8b 혼합 가중 스윕 + TriMap-dist 재검증",
        "family_system": f"Set B — {es.MAPPING_VERSION} {len(families)}계열 (팀 결정 ③)",
        "families": families,
        "populations": {"korea200": len(korea_ids), "global1000": len(g_ids)},
        "confident_edges": {"korea200": len(ce_k), "global1000": len(ce_g)},
        "inputs": {
            "top200": {"path": TOP200, "sha256": p3b.sha256(TOP200)},
            "v2_json_readonly": {"path": V2_JSON, "sha256": p3b.sha256(V2_JSON)},
            "phase3b_metrics": {"path": os.path.join(P3B_DIR, "metrics.json"),
                                "sha256": p3b.sha256(os.path.join(P3B_DIR, "metrics.json"))},
            "accord_dictionary": {"path": ACCORD_DICT, "sha256": p3b.sha256(ACCORD_DICT)},
        },
        "projection": {"umap": "n_neighbors=10 min_dist=0.1 metric=precomputed",
                       "trimap": "TorchTRIMAP n_inliers=10 n_outliers=5 n_random=5 "
                                 "use_dist_matrix=True apply_pca=False"},
        "grid_points": len(grid),
        "trimap_runs": len(tri_rows),
        "holdout_untouched": "data/korea_popularity/evaluation/gold_set_test.csv — 열지 않았다",
        "writes": ["experiments/phase3c/metrics.json", "experiments/phase3c/manifest.json",
                   "experiments/phase3c/sweep.csv", "experiments/phase3c/trimap.csv",
                   "experiments/phase3c/coordinates_korea200.csv"],
        "coordinates_saved": [label(a, b) for a, b in KEEP_COORDS],
        "elapsed_sec": round(time.time() - t0, 1),
    }
    with open(os.path.join(OUT_DIR, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)
        f.write("\n")

    print()
    print(f"총 소요 {time.time()-t0:.0f}초")
    print(f"  -> {OUT_DIR}/metrics.json · manifest.json · sweep.csv · trimap.csv")


if __name__ == "__main__":
    main()

"""Phase 5b — soft Territory 임계 미세 조정. 0.20 ~ 0.30 구간을 채운다.

Phase 5 는 임계를 0.30(T1)과 0.20(T2) 두 점만 봤는데 그 사이에서 결과가 크게 갈렸다::

    0.30  구역 9.0계열 · 프루티 면적 4.0%
    0.20  구역 6.4계열 · 프루티 면적 7.1%     <- 프루티는 넓은데 다른 계열이 무너진다

**0.22 ~ 0.28 은 한 번도 보지 않았다.** 그 구간에 "9계열 유지 + 프루티 면적 최대"
지점이 있을 수 있다. 0.30 이 최적이라는 근거도 지금은 "격자의 한 점" 뿐이다.

바꾸는 것은 **임계값 하나**다. 향수 200개(D0) · 좌표 C8b · 계열 체계 Set B ·
시드 5개는 전부 Phase 5 와 동일하다. 계산 함수도 Phase 5 것을 그대로 import 한다.

게이트와 판정 규칙은 Phase 5 에서 확정한 값을 그대로 쓴다 (결과를 보고 바꾸지 않는다)::

    P5-A  구역 보유 계열 수 >= T0
    P5-B  프루티 구역 보유 (시드 3/5 이상)
    P5-C  향수당 평균 active Family <= 2.0

    Territory 판정 — 면적 >= 3% · 최대 연속 덩어리 >= 60% · weighted coverage >= 0.50

재현::

    python src/map/experiment_phase5b_threshold.py

산출  experiments/phase5b/{manifest,metrics}.json · territory.csv · per_seed.csv
      conditions.csv · field_seed42.npz (지도 뷰어용 · seed 42)

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
import experiment_phase3c_blend_sweep as p3c    # noqa: E402
import experiment_phase5_soft_territory as p5   # noqa: E402

OUT_DIR = os.path.join("experiments", "phase5b")
P5_DIR = os.path.join("experiments", "phase5")
TOP200 = os.path.join("data", "korea_popularity", "korea_representative_perfumes_top200.csv")

SEEDS = p5.SEEDS
FAMILY_W, PERCEPT_W = p5.FAMILY_W, p5.PERCEPT_W
FAMILY_KO, FOCUS = p5.FAMILY_KO, p5.FOCUS

# (표시 이름, 방식, 파라미터, Phase 5 대응 조건 · 없으면 None)
CONDITIONS = (
    ("T0 (1위만)", "argmax_hard", None, "T0"),
    ("T0w (1위·가중)", "argmax_weighted", None, "T0w"),
    ("0.30 (T1)", "threshold", 0.30, "T1"),
    ("0.28", "threshold", 0.28, None),
    ("0.26", "threshold", 0.26, None),
    ("0.24", "threshold", 0.24, None),
    ("0.22", "threshold", 0.22, None),
    ("0.20 (T2)", "threshold", 0.20, "T2"),
)


def main() -> None:
    os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))  # MAP/
    os.makedirs(OUT_DIR, exist_ok=True)
    t0 = time.time()
    print("=" * 100)
    print("Phase 5b — soft Territory 임계 미세 조정 (0.20 ~ 0.30)")
    print("=" * 100)

    df, _t, idf_map, *_ = bm.prepare(with_selection_comparison=False)
    ids = pd.read_csv(TOP200).fragrantica_id.astype(int).tolist()
    rows = df.set_index("id").loc[ids].reset_index()
    S, _, _ = sm.base_similarity(rows.accord_list.tolist(), rows.note_set.tolist(), idf_map)
    D = 1.0 - S
    np.fill_diagonal(D, 0.0)
    res = es.family_scores(rows.accord_list.tolist(), p3b.SYSTEM)
    families, M = res["families"], res["M"]
    Dp, nw, nm = p3b.perception_distance(ids)
    Df = p3b.family_profile_distance(M)
    Db = p3c.blend(D, Df, Dp, FAMILY_W, PERCEPT_W)
    coords = {s: p3b.umap_layout(Db, s) for s in SEEDS}

    print(f"D0 구성 {len(ids)}개 · Set B {len(families)}계열 · 좌표 C8b · 시드 {list(SEEDS)}")
    print(f"판정 — 면적 >= {p5.TERR_AREA} · 최대덩어리 >= {p5.TERR_BLOB} · "
          f"coverage >= {p5.TERR_COVER} · 시드 {p5.TERR_SEEDS}/{len(SEEDS)}")
    print(f"게이트 — P5-A 구역 >= T0 · P5-B 프루티 보유 · "
          f"P5-C 평균 계열 <= {p5.GATE_MAX_ACTIVE}")

    # ---- 조건별 측정 ----
    print()
    print("-" * 100)
    print("조건별 기여 구조")
    print("-" * 100)
    print(f"  {'조건':<16}{'평균 계열':>10}{'2계열 이상':>11}{'<=3계열':>10}"
          f"{'총 신호량':>11}{'P5-C':>7}")
    Ws, cond_rows = {}, []
    for name, mode, param, _ref in CONDITIONS:
        W, keep = p5.weight_matrix(M, mode, param)
        Ws[name] = W
        active = keep.sum(axis=1)
        ma = float(active.mean())
        cond_rows.append({"condition": name, "mode": mode, "param": param,
                          "mean_active_families": round(ma, 3),
                          "perfumes_multi_family": int((active >= 2).sum()),
                          "share_le3_families": round(float((active <= 3).mean()), 4),
                          "total_signal": round(float(W.sum()), 1),
                          "gate_c_ok": bool(ma <= p5.GATE_MAX_ACTIVE)})
        r = cond_rows[-1]
        print(f"  {name:<16}{ma:>10.2f}{r['perfumes_multi_family']:>11}"
              f"{r['share_le3_families']:>10.1%}{r['total_signal']:>11.1f}"
              f"{'○' if r['gate_c_ok'] else '✕':>7}")

    per_seed, terr_rows, fields = [], [], {}
    for name, _m, _p, _ref in CONDITIONS:
        W = Ws[name]
        for s in SEEDS:
            t = p5.territory(coords[s], W, families)
            if s == SEEDS[0]:
                key = name.split(" ")[0]
                fields[key] = t["win_grid"].astype(np.int8)
                fields[key + "_usable"] = np.array(t["usable"], dtype=object)
                fields[key + "_land"] = t["land"]
            fr = t["per_family"]["FRUITY"]
            per_seed.append({"condition": name, "seed": s,
                             "families_with_territory": t["families_with_territory"],
                             "fragments_total": t["fragments_total"],
                             "fruity_territory": bool(fr["has_territory"]),
                             "fruity_area": fr["area_share"],
                             "fruity_blob": fr["largest_blob_share"],
                             "fruity_coverage": fr["weighted_coverage"],
                             "mean_coverage": round(float(np.mean(
                                 [v["weighted_coverage"] for v in t["per_family"].values()])), 4)})
            for f, v in t["per_family"].items():
                terr_rows.append({"condition": name, "seed": s, "family": f,
                                  "family_ko": FAMILY_KO[f], **v})

    ps = pd.DataFrame(per_seed)
    tr = pd.DataFrame(terr_rows)

    def A(name, col, nd=3):
        v = ps.loc[ps.condition == name, col].to_numpy(float)
        return {"mean": round(float(v.mean()), nd), "std": round(float(v.std()), nd),
                "min": round(float(v.min()), nd), "max": round(float(v.max()), nd)}

    # ---- 재현 확인 ----
    print()
    print("-" * 100)
    print("재현 확인 — Phase 5 와 겹치는 조건 4개는 값이 같아야 한다")
    print("-" * 100)
    p5m = json.loads(open(os.path.join(P5_DIR, "metrics.json"), encoding="utf-8").read())
    checks = []
    for name, _m, _p, ref in CONDITIONS:
        if ref is None:
            continue
        for key, col, exp in (
            ("families_with_territory", "families_with_territory",
             p5m["seed_aggregates"][ref]["families_with_territory"]["mean"]),
            ("fruity_area", "fruity_area", p5m["seed_aggregates"][ref]["fruity_area"]["mean"]),
            ("mean_coverage", "mean_coverage",
             p5m["seed_aggregates"][ref]["mean_coverage"]["mean"]),
        ):
            got = A(name, col, 4)["mean"]
            ok = abs(got - exp) <= 5e-4
            checks.append({"condition": name, "phase5_ref": ref, "metric": key,
                           "got": got, "expected": exp, "ok": bool(ok)})
            mark = "PASS" if ok else "FAIL"
            print(f"  {name:<16}{ref:<5}{key:<26}측정 {got:<10.4f}Phase 5 {exp:<10.4f}{mark}")
    n_fail = sum(1 for c in checks if not c["ok"])
    print(f"\n  재현 확인 {len(checks)-n_fail}/{len(checks)} PASS")
    if n_fail:
        raise SystemExit("Phase 5 와 재현되지 않았다 — 중단한다")

    # ---- 임계 곡선 ----
    t0_terr = A("T0 (1위만)", "families_with_territory", 2)["mean"]
    print()
    print("임계 곡선")
    print(f"  {'조건':<16}{'구역 계열':>12}{'조각':>8}{'평균 coverage':>15}"
          f"{'프루티 보유':>12}{'프루티 면적':>12}{'프루티 덩어리':>14}{'프루티 coverage':>16}")
    for name, _m, _p, _r in CONDITIONS:
        t = A(name, "families_with_territory", 2)
        fr = int(ps.loc[ps.condition == name, "fruity_territory"].sum())
        print(f"  {name:<16}{t['mean']:>7.1f}±{t['std']:<4.1f}"
              f"{A(name,'fragments_total',1)['mean']:>8.1f}"
              f"{A(name,'mean_coverage',4)['mean']:>15.4f}"
              f"{fr:>9}/5{A(name,'fruity_area',4)['mean']:>12.1%}"
              f"{A(name,'fruity_blob',4)['mean']:>14.0%}"
              f"{A(name,'fruity_coverage',4)['mean']:>16.3f}")

    print()
    print("계열별 구역 보유 (시드 5개 중 통과 횟수)")
    print(f"  {'계열':<14}" + "".join(f"{n.split(' ')[0]:>10}" for n, _, _, _ in CONDITIONS))
    terr_summary = {}
    for f in families:
        line = f"  {FAMILY_KO[f]:<14}"
        for name, _m, _p, _r in CONDITIONS:
            sub = tr[(tr.condition == name) & (tr.family == f)]
            hs = int(sub.has_territory.sum())
            terr_summary.setdefault(name, {})[f] = {
                "area_share": round(float(sub.area_share.mean()), 4),
                "largest_blob_share": round(float(sub.largest_blob_share.mean()), 4),
                "weighted_coverage": round(float(sub.weighted_coverage.mean()), 4),
                "spread": round(float(sub.spread.mean()), 3),
                "has_territory_seeds": hs, "has_territory": bool(hs >= p5.TERR_SEEDS)}
            line += f"{('✓' if hs >= p5.TERR_SEEDS else ('~' if hs else '✕')):>10}"
        print(line)

    # ---- 게이트 ----
    print()
    print("=" * 100)
    print("게이트 판정 (Phase 5 확정 기준)")
    print("=" * 100)
    print(f"  {'조건':<16}{'P5-A 구역':>13}{'P5-B 프루티':>14}{'P5-C 평균계열':>16}{'판정':>8}")
    verdicts = {}
    for row in cond_rows:
        name = row["condition"]
        t = A(name, "families_with_territory", 2)["mean"]
        fr = int(ps.loc[ps.condition == name, "fruity_territory"].sum())
        a_ok, b_ok, c_ok = t >= t0_terr - 1e-9, fr >= p5.TERR_SEEDS, row["gate_c_ok"]
        ok = a_ok and b_ok and c_ok
        verdicts[name] = {"gate_a": bool(a_ok), "territory_families": t,
                          "gate_b": bool(b_ok), "fruity_seeds": fr,
                          "gate_c": bool(c_ok),
                          "mean_active_families": row["mean_active_families"],
                          "passes_all": bool(ok)}
        print(f"  {name:<16}{t:>8.1f} {'○' if a_ok else '✕':>4}"
              f"{fr:>9}/5 {'○' if b_ok else '✕':>3}"
              f"{row['mean_active_families']:>11.2f} {'○' if c_ok else '✕':>4}"
              f"{'통과' if ok else '탈락':>8}")
    passed = [n for n, v in verdicts.items() if v["passes_all"]]
    print()
    print(f"  통과 {len(passed)}/{len(CONDITIONS)}: {passed if passed else '없음'}")

    # ---- 최선 지점 ----
    best = None
    if passed:
        best = max(passed, key=lambda n: (A(n, "fruity_area", 4)["mean"],
                                          A(n, "families_with_territory", 2)["mean"]))
        bt = A(best, "families_with_territory", 2)["mean"]
        ba = A(best, "fruity_area", 4)["mean"]
        t1a = A("0.30 (T1)", "fruity_area", 4)["mean"]
        print()
        print(f"  게이트 통과 안에서 프루티 면적이 가장 넓은 지점: {best} "
              f"(구역 {bt:.1f}계열 · 프루티 {ba:.1%})")
        print(f"  T1(0.30) 대비 프루티 면적 {ba-t1a:+.1%}p · "
              f"구역 {bt - A('0.30 (T1)','families_with_territory',2)['mean']:+.1f}계열")

    # ---- 저장 ----
    np.savez_compressed(os.path.join(OUT_DIR, "field_seed42.npz"), **fields)
    ps.to_csv(os.path.join(OUT_DIR, "per_seed.csv"), index=False, encoding="utf-8-sig")
    tr.to_csv(os.path.join(OUT_DIR, "territory.csv"), index=False, encoding="utf-8-sig")
    pd.DataFrame(cond_rows).to_csv(os.path.join(OUT_DIR, "conditions.csv"),
                                   index=False, encoding="utf-8-sig")
    metrics = {
        "question": ("0.20 ~ 0.30 사이에 '9계열 유지 + 프루티 면적 최대' 지점이 있는가. "
                     "그리고 0.30 이 실제로 최적인가"),
        "changed_variable": "임계값 하나 (0.20 / 0.22 / 0.24 / 0.26 / 0.28 / 0.30)",
        "fixed": {"composition": "D0", "n": len(ids),
                  "projection": f"C8b — Family {FAMILY_W} + Perception {PERCEPT_W}",
                  "family_system": f"Set B {es.MAPPING_VERSION}", "seeds": list(SEEDS),
                  "note": "Phase 5 와 동일. 계산 함수도 Phase 5 것을 import 했다"},
        "gates": {"declared_before_run": True, "source": "Phase 5 확정값 그대로",
                  "P5-A": {"metric": "구역 보유 계열 수 >= T0", "t0_value": t0_terr},
                  "P5-B": {"metric": "프루티 구역 보유",
                           "threshold": f"시드 {p5.TERR_SEEDS}/{len(SEEDS)}"},
                  "P5-C": {"metric": "평균 active Family", "threshold": p5.GATE_MAX_ACTIVE},
                  "territory_rule": {"area_share": p5.TERR_AREA,
                                     "largest_blob_share": p5.TERR_BLOB,
                                     "weighted_coverage": p5.TERR_COVER}},
        "reproduction_checks": checks,
        "reproduction_pass": len(checks) - n_fail, "reproduction_total": len(checks),
        "conditions": cond_rows, "verdicts": verdicts, "passed": passed,
        "best_by_fruity_area": best,
        "territory_per_family": terr_summary,
        "seed_aggregates": {n: {c: A(n, c, 4) for c in
                                ("families_with_territory", "fragments_total",
                                 "mean_coverage", "fruity_area", "fruity_blob",
                                 "fruity_coverage")}
                            for n, _m, _p, _r in CONDITIONS},
        "notes": {"perception_missing_checked": (
            "인식 축 결측(계절 15 · 성별 21 · 둘 다 15)의 중앙값 채움이 지도에 인공 근접을 "
            "만드는지 확인했다. 결측 15개끼리의 2D 거리 백분위 0.487 vs 무작위 0.503(-0.015) "
            "인데 인식 축과 무관한 원본 거리에서 이미 -0.035 가까웠다. 지도에서는 오히려 "
            "덜 가깝다 — 인식 축이 거리의 15% 뿐이라 효과가 묻힌다. 별도 실험을 하지 않는다")},
    }
    with open(os.path.join(OUT_DIR, "metrics.json"), "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=1)
        f.write("\n")
    manifest = {
        "experiment": "P5B_THRESHOLD", "phase": "5b",
        "title": "soft Territory 임계 미세 조정 — 0.20 ~ 0.30",
        "hypothesis": "0.22~0.28 에 9계열을 유지하면서 프루티 면적이 더 넓은 지점이 있다",
        "user_meaning": "작은 계열의 탐색 구역을 얼마나 넓힐 수 있는가",
        "changed_variable": "임계값 (좌표·구성·계열 체계 불변)",
        "population": ["korea200"],
        "family_mapping_version": es.MAPPING_VERSION,
        "primary_metrics": ["families_with_territory", "fruity_area"],
        "guardrail_metrics": ["P5-A", "P5-B", "P5-C"],
        "inputs": {"top200": {"path": TOP200, "sha256": p3b.sha256(TOP200)},
                   "phase5_metrics": {"path": os.path.join(P5_DIR, "metrics.json"),
                                      "sha256": p3b.sha256(os.path.join(P5_DIR,
                                                                        "metrics.json"))}},
        "holdout_untouched": "data/korea_popularity/evaluation/gold_set_test.csv — 열지 않았다",
        "writes": [f"experiments/phase5b/{n}" for n in
                   ("metrics.json", "manifest.json", "per_seed.csv", "territory.csv",
                    "conditions.csv", "field_seed42.npz")],
        "elapsed_sec": round(time.time() - t0, 1),
    }
    with open(os.path.join(OUT_DIR, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print()
    print(f"총 소요 {time.time()-t0:.0f}초  ->  {OUT_DIR}/")


if __name__ == "__main__":
    main()

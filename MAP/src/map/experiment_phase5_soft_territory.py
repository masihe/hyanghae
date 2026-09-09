"""Phase 5 — soft / multi-family Territory. hard(T0) → soft(T6) 전 구간 스윕.

D26 결정 ⑤ — Fruity 문제를 향수 수가 아니라 **Family 표현 방식**으로 푼다.
argmax 로는 8개지만 fractional 로는 14.9개분의 Fruity 신호가 이미 지도에 있다.

**향수 200개도 좌표도 바꾸지 않는다.** D0 구성 · C8b 좌표 그대로다.
바뀌는 것은 **Territory 를 그릴 때 각 향수가 어느 계열에 얼마나 기여하는가** 뿐이다.

실행 전 실측 (D26 Trade-off ②) — Family Score 를 전부 그대로 쓰면 프루티 신호의
퍼짐이 0.147 → 0.653 으로 4.4배 나빠진다. 신호가 지도에 흩어져 있기 때문이다.
그래서 "soft 를 쓸까" 가 아니라 **"얼마나 soft 하게 할까"** 를 스윕한다.

조건 8개 — argmax 는 어떤 조건에서도 유지되므로 T0w ⊆ T1 ⊆ T2 ⊆ T3 ⊆ T6 이다
(hard → soft 단조 구간)::

    T0   argmax 만 · 가중 없음        Phase 4 와 동일한 방식. 재현 기준이자 대조군
    T0w  argmax 만 · 원래 강도 가중    '가중' 효과와 '다계열' 효과를 분리하는 통제 조건
    T1   비중 >= 0.30 인 계열 + argmax
    T2   비중 >= 0.20 인 계열 + argmax
    T3   비중 >= 0.15 인 계열 + argmax
    T4   상위 2계열
    T5   상위 3계열
    T6   전 계열                      D26 ⑤ 문자 그대로. 실패 예측되지만 끝점으로 필요

**팀 결정 — threshold 이후 재정규화하지 않는다.** 살아남은 계열은 Family Score 의
**원래 강도** 를 그대로 쓴다. Family Score 는 향수마다 합이 정확히 1.0 이므로(실측)
'원래 강도' 는 곧 **그 계열이 그 향수에서 차지하는 비중** 이다. 따라서 계열 소속이
뚜렷한 향수(1위 비중 0.82)가 흐릿한 향수(1위 비중 0.22)보다 크게 기여한다.

**팀 결정 — 자기 영역 위는 weighted coverage 로 잰다.**::

    coverage[f] = Σ_i W[i,f]·1{향수 i 가 선 칸을 f 가 차지} / Σ_i W[i,f]

    "지도에 있는 f 신호 중 몇 %가 f 의 땅 위에 있는가"

W 가 one-hot 이면 Phase 4 의 on_own 과 정확히 일치한다 (실측 확인, 9계열 전부).

Hard Gate 는 실행 전에 확정했고 결과를 보고 바꾸지 않는다::

    P5-A  Territory 보유 계열 수 >= T0
    P5-B  프루티가 Territory 를 가질 것 (시드 5개 중 3개 이상)   <- 이 실험의 목적
    P5-C  향수당 평균 active Family <= 2.0                     <- UX 제약

P5-C 는 통계적으로 유도한 값이 아니라 **한 향수가 지나치게 많은 Territory 에 영향을
주는 것을 막는 UX 제약**이다 (팀 결정 ③). 대부분의 향수가 3계열 이하에만 기여하는지도
함께 기록한다.

Territory 보유 판정은 Phase 4 와 동일하다 — 면적 >= 3% · 최대 연속 덩어리 >= 60% ·
weighted coverage >= 0.50, 시드 5개 중 3개 이상.

재현::

    python src/map/experiment_phase5_soft_territory.py

산출  experiments/phase5/{manifest,metrics}.json · territory.csv · conditions.csv
      field_seed42.npz

프로덕션 파일은 읽기만 한다. output/ · results/ 를 쓰지 않는다.
"""

import json
import os
import sys
import time

import numpy as np
import pandas as pd
from scipy.stats import gaussian_kde

HERE = os.path.dirname(os.path.abspath(__file__))
for p in (HERE, os.path.join(HERE, "..", "common")):
    if p not in sys.path:
        sys.path.insert(0, p)

import scent_map as sm                          # noqa: E402
import build_map as bm                          # noqa: E402
import build_korea_terrain as bkt               # noqa: E402
import experiment_family_systems as es          # noqa: E402
import experiment_phase3b_territory as p3b      # noqa: E402
import experiment_phase3c_blend_sweep as p3c    # noqa: E402

OUT_DIR = os.path.join("experiments", "phase5")
P4_DIR = os.path.join("experiments", "phase4")
TOP200 = os.path.join("data", "korea_popularity", "korea_representative_perfumes_top200.csv")

SEEDS = (42, 1, 2, 3, 4)
FAMILY_W, PERCEPT_W = 0.35, 0.15      # C8b — D24 확정, 변경 금지
# Territory 보유 판정 (Phase 4 와 동일)
TERR_AREA = 0.03
TERR_BLOB = 0.60
TERR_COVER = 0.50
TERR_SEEDS = 3
# Hard Gate
GATE_MAX_ACTIVE = 2.0

FAMILY_KO = {"CITRUS": "시트러스", "FRUITY": "프루티", "FLORAL": "플로럴",
             "GREEN": "그린·아로마틱", "AQUATIC": "아쿠아틱", "WOODY": "우디",
             "AMBER": "앰버·스파이시", "GOURMAND": "구르망", "MUSK": "머스크·파우더리"}
FOCUS = ("FRUITY", "AQUATIC", "MUSK")

# (이름, 방식, 파라미터, 설명)
CONDITIONS = (
    ("T0", "argmax_hard", None, "argmax 만 · 가중 없음 (Phase 4 방식 · 대조군)"),
    ("T0w", "argmax_weighted", None, "argmax 만 · 원래 강도 가중 (가중 효과 분리)"),
    ("T1", "threshold", 0.30, "비중 >= 0.30 + argmax"),
    ("T2", "threshold", 0.20, "비중 >= 0.20 + argmax"),
    ("T3", "threshold", 0.15, "비중 >= 0.15 + argmax"),
    ("T4", "topk", 2, "상위 2계열"),
    ("T5", "topk", 3, "상위 3계열"),
    ("T6", "all", None, "전 계열 (D26 ⑤ 문자 그대로)"),
)


def weight_matrix(M, mode, param):
    """조건별 기여 가중치. 재정규화하지 않고 원래 강도를 유지한다 (팀 결정).

    argmax 계열은 어떤 조건에서도 살아남는다 — 그래야 hard → soft 가 단조 구간이 된다.
    """
    n, k = M.shape
    total = np.maximum(M.sum(axis=1, keepdims=True), 1e-12)
    share = M / total
    am = M.argmax(axis=1)
    keep = np.zeros((n, k), dtype=bool)
    keep[np.arange(n), am] = True          # argmax 는 항상 유지

    if mode == "argmax_hard":
        W = keep.astype(float)             # 가중 없음 — 전부 1.0
        return W, keep
    if mode == "argmax_weighted":
        pass                               # keep 그대로
    elif mode == "threshold":
        keep |= share >= param
    elif mode == "topk":
        order = np.argsort(-M, axis=1)[:, :param]
        keep[np.arange(n)[:, None], order] = True
    elif mode == "all":
        keep |= M > 0
    else:
        raise ValueError(mode)
    return M * keep, keep


def density_w(XY, weights, sample, width, height):
    """가중 KDE. 가중이 one-hot 이면 부분집합 KDE 와 값이 같다 (실측 오차 0.00e+00)."""
    kde = gaussian_kde(XY.T, weights=weights)
    kde.set_bandwidth(kde.factor * bkt.BANDWIDTH_SCALE)
    return kde(sample).reshape(height, width)


def territory(XY, W, families, min_signal=1e-9):
    """조건별 계열 Territory. 면적·최대 덩어리·weighted coverage·가중 퍼짐."""
    from scipy.ndimage import label as cc_label
    lo, hi, width, height, sample, _xs, _ys = bkt.make_grid(XY)
    total = density_w(XY, np.ones(len(XY)), sample, width, height)
    land = total >= np.percentile(total, bkt.SEA_PERCENTILE)
    n_land = int(land.sum())

    usable = [f for i, f in enumerate(families) if W[:, i].sum() > min_signal
              and (W[:, i] > 0).sum() >= 3]
    idx = [families.index(f) for f in usable]
    G = np.array([density_w(XY, W[:, i], sample, width, height) for i in idx])
    G = G / G.max(axis=(1, 2), keepdims=True)
    win = G.argmax(axis=0)
    row, col = bkt.cell_index(XY, lo, hi, width, height)
    centre = XY.mean(axis=0)
    map_radius = float(np.linalg.norm(XY - centre, axis=1).mean())

    out = {}
    for j, f in enumerate(usable):
        w = W[:, families.index(f)]
        mask = (win == j) & land
        cells = int(mask.sum())
        if cells:
            lab_cc, _ = cc_label(mask)
            sizes = np.bincount(lab_cc.ravel())[1:]
            blob = float(sizes.max() / cells)
            pieces = int((sizes >= 5).sum())
        else:
            blob, pieces = 0.0, 0
        on = np.array([usable[win[row[i], col[i]]] == f for i in range(len(XY))])
        cover = float((w * on).sum() / w.sum())
        wn = w / w.sum()
        wc = (XY * wn[:, None]).sum(axis=0)
        spread = float((wn * np.linalg.norm(XY - wc, axis=1)).sum() / map_radius)
        area = cells / n_land if n_land else 0.0
        out[f] = {"signal": round(float(w.sum()), 2),
                  "contributors": int((w > 0).sum()),
                  "area_share": round(area, 4), "largest_blob_share": round(blob, 4),
                  "pieces": pieces, "weighted_coverage": round(cover, 4),
                  "spread": round(spread, 3),
                  "has_territory": bool(area >= TERR_AREA and blob >= TERR_BLOB
                                        and cover >= TERR_COVER)}
    for f in families:
        if f not in out:
            out[f] = {"signal": 0.0, "contributors": 0, "area_share": 0.0,
                      "largest_blob_share": 0.0, "pieces": 0, "weighted_coverage": 0.0,
                      "spread": float("nan"), "has_territory": False}
    return {"per_family": out, "land_cells": n_land, "grid": f"{width}x{height}",
            "fragments_total": int(sum(v["pieces"] for v in out.values())),
            "families_with_territory": int(sum(1 for v in out.values()
                                               if v["has_territory"])),
            "win_grid": win, "usable": usable, "land": land}


def main() -> None:
    os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))  # MAP/
    os.makedirs(OUT_DIR, exist_ok=True)
    t0 = time.time()
    print("=" * 100)
    print("Phase 5 — soft / multi-family Territory (D0 구성 · C8b 좌표 고정)")
    print("=" * 100)

    # ---- 입력: D0 구성 · C8b 좌표를 그대로 다시 만든다 ----
    df, _targets, idf_map, _S, _Dg, _iog, _ceg, _ae = bm.prepare(
        with_selection_comparison=False)
    ids = pd.read_csv(TOP200).fragrantica_id.astype(int).tolist()
    rows = df.set_index("id").loc[ids].reset_index()
    S, _, _ = sm.base_similarity(rows.accord_list.tolist(), rows.note_set.tolist(), idf_map)
    D = 1.0 - S
    np.fill_diagonal(D, 0.0)
    res = es.family_scores(rows.accord_list.tolist(), p3b.SYSTEM)
    families, lab, M = res["families"], res["argmax"], res["M"]
    Dp, nw, nm = p3b.perception_distance(ids)
    Df = p3b.family_profile_distance(M)
    Db = p3c.blend(D, Df, Dp, FAMILY_W, PERCEPT_W)
    share = M / np.maximum(M.sum(axis=1, keepdims=True), 1e-12)

    print(f"D0 구성 {len(ids)}개 · Set B {len(families)}계열 · "
          f"좌표 C8b(Family {FAMILY_W} + Perception {PERCEPT_W}) · 시드 {list(SEEDS)}")
    print(f"인식 축 투표 — 계절 {nw}/200 · 성별 {nm}/200")
    print(f"Territory 판정 — 면적 >= {TERR_AREA} · 최대덩어리 >= {TERR_BLOB} · "
          f"weighted coverage >= {TERR_COVER} · 시드 {TERR_SEEDS}/{len(SEEDS)}")
    print(f"Hard Gate — P5-A Territory >= T0 · P5-B 프루티 보유 · "
          f"P5-C 평균 active Family <= {GATE_MAX_ACTIVE}")

    coords = {s: p3b.umap_layout(Db, s) for s in SEEDS}

    # ---- 조건별 가중치와 겹침 ----
    print()
    print("-" * 100)
    print("조건별 기여 구조 (좌표와 무관 · 팀 결정 ③ 기록 항목 포함)")
    print("-" * 100)
    print(f"  {'조건':<5}{'설명':<34}{'평균 active':>12}{'중앙':>6}{'최대':>6}"
          f"{'<=3계열 비율':>13}{'P5-C':>7}{'총 신호':>10}")
    Ws, cond_rows = {}, []
    for name, mode, param, desc in CONDITIONS:
        W, keep = weight_matrix(M, mode, param)
        Ws[name] = W
        active = keep.sum(axis=1)
        mean_active = float(active.mean())
        le3 = float((active <= 3).mean())
        ok_c = mean_active <= GATE_MAX_ACTIVE
        cond_rows.append({
            "condition": name, "mode": mode, "param": param, "description": desc,
            "mean_active_families": round(mean_active, 3),
            "median_active_families": int(np.median(active)),
            "max_active_families": int(active.max()),
            "share_le3_families": round(le3, 4),
            "gate_c_ok": bool(ok_c),
            "total_signal": round(float(W.sum()), 1),
            "family_signal": {f: round(float(W[:, i].sum()), 2)
                              for i, f in enumerate(families)},
            "family_contributors": {f: int((W[:, i] > 0).sum())
                                    for i, f in enumerate(families)},
        })
        print(f"  {name:<5}{desc:<34}{mean_active:>12.2f}{int(np.median(active)):>6}"
              f"{int(active.max()):>6}{le3:>13.1%}"
              f"{'○' if ok_c else '✕':>7}{W.sum():>10.1f}")

    # ---- 조건 × 시드 측정 ----
    print()
    print("=" * 100)
    print(f"조건 {len(CONDITIONS)}개 × 시드 {len(SEEDS)}개")
    print("=" * 100)
    terr_rows, per_seed, fields = [], [], {}
    for name, mode, param, desc in CONDITIONS:
        W = Ws[name]
        for s in SEEDS:
            t = territory(coords[s], W, families)
            per_seed.append({"condition": name, "seed": s,
                             "families_with_territory": t["families_with_territory"],
                             "fragments_total": t["fragments_total"],
                             "fruity_territory": bool(t["per_family"]["FRUITY"]["has_territory"]),
                             "fruity_area": t["per_family"]["FRUITY"]["area_share"],
                             "fruity_blob": t["per_family"]["FRUITY"]["largest_blob_share"],
                             "fruity_coverage": t["per_family"]["FRUITY"]["weighted_coverage"],
                             "mean_coverage": round(float(np.mean(
                                 [v["weighted_coverage"] for v in t["per_family"].values()])), 4)})
            for f, v in t["per_family"].items():
                terr_rows.append({"condition": name, "seed": s, "family": f,
                                  "family_ko": FAMILY_KO[f], **v})
            if s == SEEDS[0]:
                fields[name] = t["win_grid"].astype(np.int8)
                fields[name + "_usable"] = np.array(t["usable"], dtype=object)
                fields[name + "_land"] = t["land"]

    ps = pd.DataFrame(per_seed)
    tr = pd.DataFrame(terr_rows)

    def A(name, col, nd=3):
        v = ps.loc[ps.condition == name, col].to_numpy(float)
        return {"mean": round(float(v.mean()), nd), "std": round(float(v.std()), nd),
                "min": round(float(v.min()), nd), "max": round(float(v.max()), nd)}

    # ---- 재현 확인: T0 == Phase 4 D0 ----
    print()
    print("-" * 100)
    print("재현 확인 — T0 는 Phase 4 의 D0 와 같은 방식이므로 값이 같아야 한다")
    print("-" * 100)
    p4 = json.loads(open(os.path.join(P4_DIR, "metrics.json"), encoding="utf-8").read())
    d0t = p4["territory_per_family"]["D0 현재"]
    checks = []
    got_n = A("T0", "families_with_territory", 2)["mean"]
    exp_n = p4["verdicts"]["D0 현재"]["territory_families"]
    ok = abs(got_n - exp_n) <= 1e-6
    checks.append({"metric": "families_with_territory", "got": got_n,
                   "expected": exp_n, "ok": bool(ok)})
    print(f"  {'families_with_territory':<28}측정 {got_n:<10.2f}Phase 4 {exp_n:<10.2f}"
          f"{'PASS' if ok else 'FAIL'}")
    for f in families:
        sub = tr[(tr.condition == "T0") & (tr.family == f)]
        for key, col, exp in (("area_share", "area_share", d0t[f]["area_share"]),
                              ("largest_blob_share", "largest_blob_share",
                               d0t[f]["largest_blob_share"]),
                              ("coverage/on_own", "weighted_coverage", d0t[f]["on_own"])):
            got = round(float(sub[col].mean()), 4)
            ok = abs(got - exp) <= 5e-3
            checks.append({"metric": f"{FAMILY_KO[f]}·{key}", "got": got,
                           "expected": exp, "ok": bool(ok)})
            if not ok:
                print(f"  {FAMILY_KO[f]:<12}{key:<20}측정 {got:<10.4f}"
                      f"Phase 4 {exp:<10.4f}FAIL")
    n_fail = sum(1 for c in checks if not c["ok"])
    print(f"  계열 9개 × 3지표 + 총합 = {len(checks)}건 · "
          f"{len(checks)-n_fail}건 PASS")
    if n_fail:
        raise SystemExit("T0 가 Phase 4 D0 와 재현되지 않았다 — 중단한다")

    # ---- 조건별 결과 ----
    t0_terr = A("T0", "families_with_territory", 2)["mean"]
    print()
    print("조건별 Territory")
    print(f"  {'조건':<5}{'Territory 계열':>14}{'조각 수':>10}{'평균 coverage':>15}"
          f"{'프루티 보유':>12}{'프루티 면적':>12}{'프루티 덩어리':>14}")
    for name, _m, _p, _d in CONDITIONS:
        t = A(name, "families_with_territory", 2)
        fr = int(ps.loc[ps.condition == name, "fruity_territory"].sum())
        print(f"  {name:<5}{t['mean']:>9.1f}±{t['std']:<4.1f}"
              f"{A(name,'fragments_total',1)['mean']:>10.1f}"
              f"{A(name,'mean_coverage',4)['mean']:>15.4f}"
              f"{fr:>9}/5{A(name,'fruity_area',4)['mean']:>12.1%}"
              f"{A(name,'fruity_blob',4)['mean']:>14.0%}")

    print()
    print("계열별 Territory 보유 (시드 5개 중 통과 횟수)")
    print(f"  {'계열':<14}" + "".join(f"{n:>6}" for n, _, _, _ in CONDITIONS))
    terr_summary = {}
    for f in families:
        line = f"  {FAMILY_KO[f]:<14}"
        for name, _m, _p, _d in CONDITIONS:
            sub = tr[(tr.condition == name) & (tr.family == f)]
            hs = int(sub.has_territory.sum())
            terr_summary.setdefault(name, {})[f] = {
                "signal": round(float(sub.signal.mean()), 2),
                "contributors": int(sub.contributors.mean()),
                "area_share": round(float(sub.area_share.mean()), 4),
                "largest_blob_share": round(float(sub.largest_blob_share.mean()), 4),
                "weighted_coverage": round(float(sub.weighted_coverage.mean()), 4),
                "spread": round(float(sub.spread.mean()), 3),
                "has_territory_seeds": hs,
                "has_territory": bool(hs >= TERR_SEEDS)}
            line += f"{('✓' if hs >= TERR_SEEDS else ('~' if hs else '✕')):>6}"
        print(line)

    print()
    print(f"주목 계열 {[FAMILY_KO[f] for f in FOCUS]}")
    print(f"  {'계열':<14}{'조건':<5}{'기여 향수':>10}{'신호량':>9}{'면적':>8}"
          f"{'덩어리':>8}{'coverage':>10}{'퍼짐':>8}{'판정':>7}")
    for f in FOCUS:
        for name, _m, _p, _d in CONDITIONS:
            v = terr_summary[name][f]
            print(f"  {FAMILY_KO[f]:<14}{name:<5}{v['contributors']:>10}"
                  f"{v['signal']:>9.1f}{v['area_share']:>8.1%}"
                  f"{v['largest_blob_share']:>8.0%}{v['weighted_coverage']:>10.3f}"
                  f"{v['spread']:>8.3f}{'보유' if v['has_territory'] else '없음':>7}")

    # ---- Hard Gate ----
    print()
    print("=" * 100)
    print("Hard Gate 판정 (실행 전 확정)")
    print("=" * 100)
    print(f"  P5-A baseline (T0) — Territory {t0_terr:.1f}계열")
    print(f"  {'조건':<5}{'P5-A Territory':>17}{'P5-B 프루티':>14}"
          f"{'P5-C 평균 active':>18}{'판정':>8}")
    verdicts = {}
    for row in cond_rows:
        name = row["condition"]
        t = A(name, "families_with_territory", 2)["mean"]
        fr = int(ps.loc[ps.condition == name, "fruity_territory"].sum())
        a_ok = t >= t0_terr - 1e-9
        b_ok = fr >= TERR_SEEDS
        c_ok = row["gate_c_ok"]
        ok = a_ok and b_ok and c_ok
        verdicts[name] = {"gate_a_territory": bool(a_ok), "territory_families": t,
                          "gate_b_fruity": bool(b_ok), "fruity_seeds": fr,
                          "gate_c_active": bool(c_ok),
                          "mean_active_families": row["mean_active_families"],
                          "passes_all": bool(ok)}
        print(f"  {name:<5}{t:>10.1f} {'○' if a_ok else '✕':>6}"
              f"{fr:>8}/5 {'○' if b_ok else '✕':>4}"
              f"{row['mean_active_families']:>12.2f} {'○' if c_ok else '✕':>5}"
              f"{'통과' if ok else '탈락':>8}")
    passed = [n for n, v in verdicts.items() if v["passes_all"]]
    print()
    print(f"  통과 {len(passed)}/{len(CONDITIONS)}: {passed if passed else '없음'}")

    # ---- 저장 ----
    ps.to_csv(os.path.join(OUT_DIR, "per_seed.csv"), index=False, encoding="utf-8-sig")
    tr.to_csv(os.path.join(OUT_DIR, "territory.csv"), index=False, encoding="utf-8-sig")
    pd.DataFrame([{k: (json.dumps(v, ensure_ascii=False) if isinstance(v, dict) else v)
                   for k, v in r.items()} for r in cond_rows]).to_csv(
        os.path.join(OUT_DIR, "conditions.csv"), index=False, encoding="utf-8-sig")
    np.savez_compressed(os.path.join(OUT_DIR, "field_seed42.npz"),
                        **{k: v for k, v in fields.items()})
    pd.DataFrame({"fragrantica_id": ids, "brand": rows.brand, "name": rows["name"],
                  "argmax_family": lab,
                  **{f"share_{f}": share[:, i].round(4) for i, f in enumerate(families)},
                  **{f"score_{f}": M[:, i].round(4) for i, f in enumerate(families)}}
                 ).to_csv(os.path.join(OUT_DIR, "family_scores.csv"),
                          index=False, encoding="utf-8-sig")

    metrics = {
        "question": ("Family Score 를 얼마나 soft 하게 쓰면 향수 구성을 바꾸지 않고도 "
                     "Fruity 가 탐색 가능한 Territory 를 갖는가"),
        "fixed": {"composition": "D0 (현재 출하 200개)", "n": len(ids),
                  "projection": f"C8b — Family {FAMILY_W} + Perception {PERCEPT_W}",
                  "family_system": f"Set B {es.MAPPING_VERSION}", "seeds": list(SEEDS)},
        "design": {
            "no_renormalization": ("팀 결정 — threshold 이후 재정규화하지 않고 Family Score 의 "
                                   "원래 강도를 유지한다. 임계는 향수 안 비중에 건다"),
            "argmax_always_kept": ("argmax 계열은 어떤 조건에서도 유지된다 — "
                                   "그래야 T0w ⊆ T1 ⊆ T2 ⊆ T3 ⊆ T6 로 hard→soft 가 단조 구간이 된다"),
            "t0w_rationale": ("T0w 는 argmax 만 쓰되 원래 강도로 가중한다. T0→T1 의 차이에서 "
                              "'가중' 효과와 '다계열' 효과를 분리하기 위한 통제 조건이다"),
            "weighted_coverage": ("coverage[f] = Σ W[i,f]·1{i 가 선 칸을 f 가 차지} / Σ W[i,f]. "
                                  "one-hot 이면 Phase 4 on_own 과 정확히 일치한다 (실측 확인)"),
        },
        "conditions": cond_rows,
        "gates": {"declared_before_run": True,
                  "P5-A": {"metric": "Territory 보유 계열 수 >= T0", "t0_value": t0_terr},
                  "P5-B": {"metric": "프루티 Territory 보유",
                           "threshold": f"시드 {TERR_SEEDS}/{len(SEEDS)} 이상"},
                  "P5-C": {"metric": "향수당 평균 active Family", "threshold": GATE_MAX_ACTIVE,
                           "note": ("통계적으로 유도한 값이 아니라 한 향수가 지나치게 많은 "
                                    "Territory 에 영향을 주는 것을 막는 UX 제약 (팀 결정 ③)")},
                  "territory_rule": {"area_share": TERR_AREA, "largest_blob_share": TERR_BLOB,
                                     "weighted_coverage": TERR_COVER,
                                     "seeds": f"{TERR_SEEDS}/{len(SEEDS)}"}},
        "reproduction_checks": checks,
        "reproduction_pass": len(checks) - n_fail, "reproduction_total": len(checks),
        "verdicts": verdicts, "passed": passed,
        "territory_per_family": terr_summary,
        "seed_aggregates": {n: {c: A(n, c, 4) for c in
                                ("families_with_territory", "fragments_total",
                                 "mean_coverage", "fruity_area", "fruity_blob",
                                 "fruity_coverage")}
                            for n, _m, _p, _d in CONDITIONS},
        "focus_families": list(FOCUS),
        "notes": {
            "no_map_change": "향수 200개와 좌표는 바뀌지 않는다. Territory 계산 방식만 바뀐다",
            "prior_measurement": ("실행 전 실측 — Family Score 전체를 쓰면 프루티 퍼짐이 "
                                  "0.147 → 0.653 으로 4.4배 나빠진다 (D26 Trade-off ②)"),
            "terrain_params": f"D12 고정값 — bandwidth scott×{bkt.BANDWIDTH_SCALE} · "
                              f"sea {bkt.SEA_PERCENTILE} 백분위",
        },
    }
    with open(os.path.join(OUT_DIR, "metrics.json"), "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=1)
        f.write("\n")
    manifest = {
        "experiment": "P5_SOFT_TERRITORY", "phase": "5",
        "title": "soft / multi-family Territory — hard(T0) → soft(T6) 스윕",
        "hypothesis": ("Family Score 전체를 쓰면 향수 구성을 바꾸지 않고도 Fruity 가 "
                       "Territory 를 갖는다 (D26 결정 ⑤)"),
        "user_meaning": "구성을 바꾸지 않고 작은 계열의 탐색 구역을 만들 수 있는가",
        "changed_variable": "Territory 계산 시 계열 기여 방식 (좌표·구성 불변)",
        "population": ["korea200"],
        "family_mapping_version": es.MAPPING_VERSION,
        "primary_metrics": ["families_with_territory", "fruity area/blob/coverage"],
        "guardrail_metrics": ["P5-A Territory >= T0", "P5-B 프루티 보유",
                              f"P5-C 평균 active <= {GATE_MAX_ACTIVE}"],
        "inputs": {"top200": {"path": TOP200, "sha256": p3b.sha256(TOP200)},
                   "phase4_metrics": {"path": os.path.join(P4_DIR, "metrics.json"),
                                      "sha256": p3b.sha256(os.path.join(P4_DIR,
                                                                        "metrics.json"))}},
        "holdout_untouched": "data/korea_popularity/evaluation/gold_set_test.csv — 열지 않았다",
        "writes": [f"experiments/phase5/{n}" for n in
                   ("metrics.json", "manifest.json", "per_seed.csv", "territory.csv",
                    "conditions.csv", "family_scores.csv", "field_seed42.npz")],
        "elapsed_sec": round(time.time() - t0, 1),
    }
    with open(os.path.join(OUT_DIR, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print()
    print(f"총 소요 {time.time()-t0:.0f}초")
    print(f"  -> {OUT_DIR}/ metrics.json · manifest.json · per_seed.csv · territory.csv · "
          f"conditions.csv · family_scores.csv · field_seed42.npz")


if __name__ == "__main__":
    main()

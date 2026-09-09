"""Phase 4 — 대표 향수 200개의 계열 균형. D0 / D1 cap30 / D2 최대균형.

팀 결정으로 전제가 고정됐다.

    좌표 방식   C8b (Base 0.50 + Family 0.35 + Perception 0.15) · UMAP seed 42~4
                Phase 4 에서는 바꾸지 않는다. 구성만 바꾼다
    개수        200개 유지
    후보 풀     286개 고정 (매칭 파이프라인 재실행 없음)
    계열 체계   Set B reviewed-1 9계열 (Phase 4 중 수정 금지)
    선정 순서   계열 안에서 국내 순위(selection_rank) 상위부터
                — 계열이 뭉치도록 구성원을 고르면 결과 지표로 선정을 최적화하는 순환이 된다

최종 질문 — "대표 향수 구성을 조정했을 때, 기존 향수의 대표성과 다양성을 크게
훼손하지 않으면서 9개 향 계열을 실제로 탐색 가능한 Territory 로 만들 수 있는가?"

Hard Gate 는 실행 전에 확정했고 결과를 보고 바꾸지 않는다.

    P4-A  국내 TOP50 유지 = 50/50
    P4-B  accord coverage >= 60 (D0 baseline)
    P4-C  Territory 보유 계열 수 >= D0  AND  관측 응집도(raw) >= D0

**P4-C 를 normalized cohesion ratio 로 걸지 않는다.** ratio 의 분모가 무작위 기대
Σp_f² 이고 Phase 4 는 계열 분포를 조작 변수로 삼는 실험이라 분모가 오염된다.
지도가 전혀 나아지지 않아도 D2 는 ratio 가 3.921 -> 5.411 로 오른다(실측 계산).
그래서 ratio 는 기록 축으로 내리고 **관측 / 무작위기대 / ratio 세 값을 병기**한다.
계열 개수 비교(7/8/9)에서는 같은 정규화가 필수였다 — 거기서는 계열 *개수*가
변수여서 교정이었고, 여기서는 계열 *분포*가 변수여서 버그가 된다.

Territory 보유 판정 (실행 전 확정)::

    계열 f 가 탐색 가능한 Territory 를 갖는다  <=>  세 조건 모두
      ① 면적 점유 >= 0.03          9계열 균등이 0.111 이므로 그 1/4 미만이면 못 찾는다
      ② 최대 연속 덩어리 >= 0.60   자기 면적 중 가장 큰 조각. 조각나면 '그 구역' 이 없다
      ③ 자기 영역 위 >= 0.50       구성원 절반 이상이 자기 영역 안에

Review Guardrail (자동 탈락 아님) — 신뢰간선 >= 38 · 계열횡단 >= 20

분포 지표는 **argmax 와 fractional 두 기준으로 병기**한다 (팀 §8). 선정은 argmax,
검증은 두 기준. 균형을 맞추려고 경계 향수를 부족한 계열로 재분류하지 않는다.

재현::

    python src/map/experiment_phase4_balance.py

산출  experiments/phase4/{manifest,metrics}.json · compositions.csv · territory.csv
      swaps.csv · coordinates_korea200.csv

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
import build_korea_terrain as bkt               # noqa: E402
import experiment_family_systems as es          # noqa: E402
import experiment_phase3b_territory as p3b      # noqa: E402
import experiment_phase3b_finalists as p3f      # noqa: E402
import experiment_phase3c_blend_sweep as p3c    # noqa: E402

OUT_DIR = os.path.join("experiments", "phase4")
P3D_DIR = os.path.join("experiments", "phase3d")
P3B_DIR = os.path.join("experiments", "phase3b")
POOL = os.path.join("data", "korea_popularity", "korea_map_identities.csv")
TOP200 = os.path.join("data", "korea_popularity", "korea_representative_perfumes_top200.csv")
ACCORD_DICT = os.path.join("..", "EDA", "analysis_outputs", "10_accord_dictionary.csv")

SEEDS = (42, 1, 2, 3, 4)
N_DISPLAY = 200
FAMILY_W, PERCEPT_W = 0.35, 0.15      # C8b — 팀 결정으로 고정
CAP_D1 = 30
RARE_MAX_SHARE = 0.30

# Hard Gate (실행 전 확정)
GATE_TOP50 = 50
GATE_ACCORD = 60
TERR_AREA = 0.03
TERR_BLOB = 0.60
TERR_ON_OWN = 0.50
# Review Guardrail
REVIEW_EDGES = 38
REVIEW_CROSS = 20

FAMILY_KO = {"CITRUS": "시트러스", "FRUITY": "프루티", "FLORAL": "플로럴",
             "GREEN": "그린·아로마틱", "AQUATIC": "아쿠아틱", "WOODY": "우디",
             "AMBER": "앰버·스파이시", "GOURMAND": "구르망", "MUSK": "머스크·파우더리"}
FOCUS = ("FRUITY", "AQUATIC", "MUSK")     # 팀 §10 — 별도 확인


# --------------------------------------------------------------------------
# 신설 — 계열별 Territory 면적과 연속성
# --------------------------------------------------------------------------
def territory_detail(coords, labels, families):
    """계열별 면적 점유·최대 연속 덩어리·퍼짐·자기영역위.

    격자와 KDE 파라미터는 D12 가 고정한 값을 그대로 쓴다
    (`BANDWIDTH_SCALE=0.5` · `SEA_PERCENTILE=60`). 이번 실험 변수가 아니다.
    면적은 **육지 셀 기준**이다 — 사용자가 보는 것이 육지이기 때문이다.
    """
    from scipy.ndimage import label as cc_label
    coords = np.asarray(coords, float)
    labels = np.asarray(labels, dtype=object)
    lo, hi, width, height, sample, _xs, _ys = bkt.make_grid(coords)
    total = bkt.density(coords, sample, width, height)
    land = total >= np.percentile(total, bkt.SEA_PERCENTILE)
    n_land = int(land.sum())

    usable = [f for f in families if (labels == f).sum() >= 3]
    G = np.zeros((len(usable), height, width))
    for i, f in enumerate(usable):
        g = bkt.density(coords[labels == f], sample, width, height)
        G[i] = g / g.max()
    win = G.argmax(axis=0)

    row, col = bkt.cell_index(coords, lo, hi, width, height)
    centre = coords.mean(axis=0)
    map_radius = float(np.linalg.norm(coords - centre, axis=1).mean())

    out = {}
    for i, f in enumerate(usable):
        mask = (win == i) & land
        cells = int(mask.sum())
        if cells:
            lab_cc, _ = cc_label(mask)
            sizes = np.bincount(lab_cc.ravel())[1:]
            blob = float(sizes.max() / cells) if sizes.size else 0.0
            pieces = int((sizes >= 5).sum())
        else:
            blob, pieces = 0.0, 0
        m = labels == f
        pts = coords[m]
        spread = float(np.linalg.norm(pts - pts.mean(axis=0), axis=1).mean() / map_radius)
        on_own = float(np.mean([usable[win[row[j], col[j]]] == f
                                for j in np.where(m)[0]]))
        area = cells / n_land if n_land else 0.0
        has = bool(area >= TERR_AREA and blob >= TERR_BLOB and on_own >= TERR_ON_OWN)
        out[f] = {"n": int(m.sum()), "area_share": round(area, 4),
                  "largest_blob_share": round(blob, 4), "pieces": pieces,
                  "spread": round(spread, 3), "on_own": round(on_own, 4),
                  "has_territory": has}
    return {"grid": f"{width}x{height}", "land_cells": n_land, "per_family": out,
            "families_with_territory": int(sum(1 for v in out.values()
                                               if v["has_territory"]))}


# --------------------------------------------------------------------------
# 구성 3안
# --------------------------------------------------------------------------
def build_compositions(ids, lab, families, rank, status):
    supply = {f: int((lab == f).sum()) for f in families}
    by_fam = {}
    for f in families:
        idx = [i for i, x in zip(ids, lab) if x == f]
        idx.sort(key=lambda i: rank[i])
        by_fam[f] = idx

    d0 = [i for i in ids if status[i] == "TOP200"]

    pool = []
    for f in families:
        pool += by_fam[f][:min(supply[f], CAP_D1)]
    pool.sort(key=lambda i: rank[i])
    d1 = pool[:N_DISPLAY]

    for level in range(1, 90):
        if sum(min(supply[f], level) for f in families) >= N_DISPLAY:
            break
    quota = {f: min(supply[f], level) for f in families}
    while sum(quota.values()) > N_DISPLAY:
        f = max((f for f in families if quota[f] > 1), key=lambda f: quota[f])
        quota[f] -= 1
    while sum(quota.values()) < N_DISPLAY:
        f = max(families, key=lambda f: supply[f] - quota[f])
        quota[f] += 1
    d2 = []
    for f in families:
        d2 += by_fam[f][:quota[f]]

    for tag, sel in (("D0", d0), ("D1", d1), ("D2", d2)):
        assert len(sel) == N_DISPLAY, (tag, len(sel))
        assert len(set(sel)) == N_DISPLAY, f"{tag} 중복"
        assert set(sel) <= set(ids), f"{tag} 후보 풀 밖"
    return {"D0 현재": d0, f"D1 cap{CAP_D1}": d1, "D2 최대균형": d2}, supply, quota


def main() -> None:
    os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))  # MAP/
    os.makedirs(OUT_DIR, exist_ok=True)
    t0 = time.time()
    print("=" * 100)
    print("Phase 4 — 대표 향수 200개의 계열 균형 (좌표 방식 C8b 고정)")
    print("=" * 100)

    # ---- 입력 ----
    pool_df = pd.read_csv(POOL)
    df_all, _targets, idf_map, _S, _Dg, _iog, _ceg, _ae = bm.prepare(
        with_selection_comparison=False)
    have = df_all.set_index("id")
    ids = pool_df.fragrantica_id.astype(int).tolist()
    assert all(i in have.index for i in ids), "후보가 perfumes.csv 에 없다"
    pool = have.loc[ids].reset_index()
    meta = pool_df.set_index("fragrantica_id")
    rank = meta.selection_rank.astype(int).to_dict()
    status = meta.selection_status.to_dict()

    res = es.family_scores(pool.accord_list.tolist(), p3b.SYSTEM)
    families, lab = res["families"], np.array(res["argmax"], dtype=object)
    M = res["M"]
    Mn = M / np.maximum(M.sum(axis=1, keepdims=True), 1e-12)
    pos_of = {i: k for k, i in enumerate(ids)}

    acc_dict = pd.read_csv(ACCORD_DICT)
    share = dict(zip(acc_dict.accord, acc_dict.perfume_share))
    edges_all = sm.load_edges("reminds_edges.csv")

    comps, supply, quota_d2 = build_compositions(ids, lab, families, rank, status)
    print(f"후보 풀 {len(ids)}개 (TOP200 {sum(1 for i in ids if status[i]=='TOP200')} · "
          f"RESERVE {sum(1 for i in ids if status[i]=='RESERVE')} · "
          f"미선정 {sum(1 for i in ids if status[i]=='NOT_SELECTED')})")
    print(f"Set B {len(families)}계열 · 후보 풀 계열 상한 "
          f"{ {FAMILY_KO[f]: supply[f] for f in families} }")
    print(f"좌표 방식 C8b — Base {1-FAMILY_W-PERCEPT_W:.3f} + Family {FAMILY_W} + "
          f"Perception {PERCEPT_W} · 시드 {list(SEEDS)}")
    print(f"Hard Gate — TOP50 {GATE_TOP50}/50 · accord >= {GATE_ACCORD} · "
          f"Territory 계열 수 >= D0 AND 관측 응집도 >= D0")
    print(f"Territory 보유 판정 — 면적 >= {TERR_AREA} · 최대덩어리 >= {TERR_BLOB} · "
          f"자기영역위 >= {TERR_ON_OWN}")

    # ---- 구성 단계 (좌표와 무관) ----
    print()
    print("-" * 100)
    print("구성 단계 — Gate P4-A · P4-B 와 Review Guardrail (좌표를 만들지 않고 나온다)")
    print("-" * 100)
    print(f"  {'안':<14}{'교체':>6}{'TOP50':>8}{'TOP100':>8}{'accord':>8}{'브랜드':>7}"
          f"{'신뢰간선':>9}{'계열횡단':>9}{'argmax CV':>11}{'frac CV':>9}"
          f"{'argmax 최대':>12}{'frac 최대':>10}")
    comp_rows, dist_rows, swap_rows = {}, [], []
    d0_ids = set(comps["D0 현재"])
    for tag, sel in comps.items():
        s = set(sel)
        posl = [pos_of[i] for i in sel]
        argc = np.array([sum(1 for i in sel if lab[pos_of[i]] == f) for f in families], float)
        frac = Mn[posl].sum(axis=0)
        e = bm.edges_within(edges_all, s)
        ce = e[bm.confident(e)]
        lmap = {i: lab[pos_of[i]] for i in sel}
        cross = sum(1 for a, b in ce[["src", "dst"]].itertuples(index=False, name=None)
                    if lmap[int(a)] != lmap[int(b)])
        accs, brands = set(), set()
        for i in sel:
            for a, _ in have.loc[i, "accord_list"]:
                accs.add(a)
            brands.add(have.loc[i, "brand"])
        top50 = sum(1 for i in ids if rank[i] <= 50 and i in s)
        top100 = sum(1 for i in ids if rank[i] <= 100 and i in s)
        dropped = sorted(d0_ids - s, key=lambda i: rank[i])
        added = sorted(s - d0_ids, key=lambda i: rank[i])
        comp_rows[tag] = {
            "n": len(sel), "swapped": len(added),
            "top50_kept": top50, "top100_kept": top100,
            "gate_a_top50": bool(top50 == GATE_TOP50),
            "accord_coverage": len(accs), "gate_b_accord": bool(len(accs) >= GATE_ACCORD),
            "brands": len(brands),
            "trusted_edges": int(len(ce)), "cross_family_edges": int(cross),
            "review_edges_ok": bool(len(ce) >= REVIEW_EDGES),
            "review_cross_ok": bool(cross >= REVIEW_CROSS),
            "argmax_counts": {f: int(argc[k]) for k, f in enumerate(families)},
            "fractional_counts": {f: round(float(frac[k]), 2) for k, f in enumerate(families)},
            "argmax_cv": round(float(argc.std() / argc.mean()), 3),
            "fractional_cv": round(float(frac.std() / frac.mean()), 3),
            "argmax_max_share": round(float(argc.max() / argc.sum()), 4),
            "fractional_max_share": round(float(frac.max() / frac.sum()), 4),
            "random_expected_cohesion": round(float(((argc / argc.sum()) ** 2).sum()), 4),
            "dropped_ranks": [rank[i] for i in dropped],
            "added_ranks": [rank[i] for i in added],
        }
        for k, f in enumerate(families):
            dist_rows.append({"composition": tag, "family": f, "family_ko": FAMILY_KO[f],
                              "argmax": int(argc[k]),
                              "fractional": round(float(frac[k]), 2),
                              "pool_supply": supply[f]})
        for i in dropped:
            swap_rows.append({"composition": tag, "direction": "빠짐", "fragrantica_id": i,
                              "brand": have.loc[i, "brand"], "name": have.loc[i, "name"],
                              "korea_rank": rank[i], "family": lab[pos_of[i]],
                              "family_ko": FAMILY_KO[lab[pos_of[i]]]})
        for i in added:
            swap_rows.append({"composition": tag, "direction": "들어옴", "fragrantica_id": i,
                              "brand": have.loc[i, "brand"], "name": have.loc[i, "name"],
                              "korea_rank": rank[i], "family": lab[pos_of[i]],
                              "family_ko": FAMILY_KO[lab[pos_of[i]]]})
        r = comp_rows[tag]
        print(f"  {tag:<14}{r['swapped']:>6}{r['top50_kept']:>6}/50"
              f"{r['top100_kept']:>6}/100{r['accord_coverage']:>8}{r['brands']:>7}"
              f"{r['trusted_edges']:>9}{r['cross_family_edges']:>9}"
              f"{r['argmax_cv']:>11.3f}{r['fractional_cv']:>9.3f}"
              f"{r['argmax_max_share']:>12.1%}{r['fractional_max_share']:>10.1%}")

    # ---- 좌표 생성과 측정 ----
    print()
    print("=" * 100)
    print(f"좌표 생성 — C8b · 시드 {len(SEEDS)}개 · 구성 3안")
    print("=" * 100)
    per_seed, terr_rows, coord_rows = [], [], []
    for tag, sel in comps.items():
        rows = have.loc[sel].reset_index()
        r = es.family_scores(rows.accord_list.tolist(), p3b.SYSTEM)
        lab_s, M_s = r["argmax"], r["M"]
        S, _, _ = sm.base_similarity(rows.accord_list.tolist(), rows.note_set.tolist(), idf_map)
        D = 1.0 - S
        np.fill_diagonal(D, 0.0)
        index_of = {int(v): i for i, v in enumerate(sel)}
        rin = bm.edges_within(edges_all, set(sel))
        ce = [(int(a), int(b)) for a, b in
              rin[bm.confident(rin)][["src", "dst"]].itertuples(index=False, name=None)]
        Dp, nw, nm = p3b.perception_distance(sel)
        Df = p3b.family_profile_distance(M_s)
        Db = p3c.blend(D, Df, Dp, FAMILY_W, PERCEPT_W)

        note_sets = [set(x) for x in rows.note_set]
        rare_sets = [{n for n, _ in lst if share.get(n, 1.0) < RARE_MAX_SHARE}
                     for lst in rows.accord_list]
        raw = pd.read_csv(sm.PERFUMES_CSV, low_memory=False,
                          usecols=p3b.VOTE_COLS).set_index("id").loc[sel]
        seas = raw[["winter", "spring", "summer", "autumn"]].astype(float)
        stt = seas.sum(axis=1)
        warmth = np.where(stt >= p3b.MIN_VOTES,
                          ((seas.winter + seas.autumn) - (seas.summer + seas.spring))
                          / stt.replace(0, np.nan), np.nan)
        gg = raw[["perceived_female", "perceived_female_leaning", "perceived_unisex",
                  "perceived_male_leaning", "perceived_male"]].astype(float)
        gt = gg.sum(axis=1)
        masc = np.where(gt >= p3b.MIN_VOTES,
                        ((gg.perceived_male + 0.5 * gg.perceived_male_leaning)
                         - (gg.perceived_female + 0.5 * gg.perceived_female_leaning))
                        / gt.replace(0, np.nan), np.nan)

        for s in SEEDS:
            c = p3b.umap_layout(Db, s)
            rd = p3b.readability(c, lab_s, families)
            td = territory_detail(c, lab_s, families)
            rf = p3b.region_field(c, lab_s, families)
            mk = bm.evaluate_layout(c, D, index_of, ce)
            gr = p3b.guardrail(c, index_of, ce, lab_s, sel)
            bc = p3b.boundary_consistency(c, lab_s, families, M_s)
            ex = p3f.explainability(c, note_sets, rare_sets)
            ax = p3f.axis_meaning(c, warmth, masc)
            rec = {"composition": tag, "seed": s,
                   "observed_cohesion": rd["observed_cohesion"],
                   "random_expected_cohesion": rd["random_expected_cohesion"],
                   "cohesion_ratio": rd["cohesion_ratio"],
                   "neighborhood_top_family_share": rd["neighborhood_top_family_share"],
                   "families_with_territory": td["families_with_territory"],
                   "on_own_region": rf["on_own_region"],
                   "fragments_total": rf["fragments_total"],
                   "trust10": round(float(mk["trust@10"]), 4),
                   "knn_overlap10": round(float(mk["knn_overlap@10"]), 4),
                   "reminds_pct": round(float(mk["reminds_pct"]), 4),
                   "cross_family_proximity": gr.get("cross_family_proximity"),
                   "same_family_proximity": gr.get("same_family_proximity"),
                   "boundary_gap": round(float(bc["center_ratio_boundary"]
                                               - bc["center_ratio_clear"]), 4),
                   "boundary_perfumes": bc["boundary_perfumes"],
                   "shared_rare_accord_ge1": ex["shared_rare_accord_ge1"],
                   "nearest_unexplained": ex["nearest_neighbor_unexplained"],
                   "y_warmth_rho": ax["y_warmth_rho"],
                   "x_masculine_rho": ax["x_masculine_rho"]}
            per_seed.append(rec)
            for f, v in td["per_family"].items():
                terr_rows.append({"composition": tag, "seed": s, "family": f,
                                  "family_ko": FAMILY_KO[f], **v})
            if s == SEEDS[0]:
                coord_rows += [{"composition": tag, "fragrantica_id": int(i),
                                "x": float(c[k, 0]), "y": float(c[k, 1]),
                                "family": lab_s[k], "korea_rank": rank[int(i)]}
                               for k, i in enumerate(sel)]
        print(f"  {tag:<14}인식 축 투표 계절 {nw}/200 · 성별 {nm}/200 · "
              f"신뢰 간선 {len(ce)}쌍")

    ps = pd.DataFrame(per_seed)
    tr = pd.DataFrame(terr_rows)

    def A(tag, col, nd=4):
        v = ps.loc[ps.composition == tag, col].to_numpy(float)
        return {"mean": round(float(v.mean()), nd), "std": round(float(v.std()), nd),
                "min": round(float(v.min()), nd), "max": round(float(v.max()), nd)}

    # ---- D0 재현 확인 (Phase 3d 의 C8b 와 같아야 한다) ----
    print()
    print("-" * 100)
    print("D0 재현 확인 — Phase 3d 의 C8b 기록과 일치해야 진행")
    print("-" * 100)
    p3d = json.loads(open(os.path.join(P3D_DIR, "metrics.json"), encoding="utf-8").read())
    c8b = next(r for r in p3d["results"] if r["candidate"] == "C8b")
    checks = []
    for key, col, exp, tol in (
        ("korea_cohesion_ratio", "cohesion_ratio", c8b["korea_cohesion_ratio"]["mean"], 5e-3),
        ("korea_on_own_region", "on_own_region", c8b["korea_on_own_region"]["mean"], 5e-3),
        ("korea_fragments_total", "fragments_total", c8b["korea_fragments_total"]["mean"], 0.2),
        ("korea_knn_overlap10", "knn_overlap10", c8b["korea_knn_overlap10"]["mean"], 5e-4),
        ("boundary_gap", "boundary_gap", c8b["boundary_gap"]["mean"], 5e-4),
    ):
        got = A("D0 현재", col, 4)["mean"]
        ok = abs(got - exp) <= tol
        checks.append({"metric": key, "got": got, "expected": exp, "ok": bool(ok)})
        print(f"  {key:<26}측정 {got:<10.4f}Phase 3d {exp:<10.4f}"
              f"{'PASS' if ok else 'FAIL'}")
    n_fail = sum(1 for c in checks if not c["ok"])
    print()
    print(f"  재현 확인 {len(checks)-n_fail}/{len(checks)} PASS")
    if n_fail:
        raise SystemExit("D0 가 Phase 3d 와 재현되지 않았다 — 입력이 달라졌으므로 중단한다")

    # ---- 응집도 3종 병기 ----
    print()
    print("응집도 3종 병기 — ratio 의 분모가 계열 분포에 의존하므로 관측값을 함께 본다")
    print(f"  {'안':<14}{'관측 응집도':>16}{'무작위 기대 Σp²':>17}{'ratio':>16}"
          f"{'분모 D0 대비':>13}")
    e0 = comp_rows["D0 현재"]["random_expected_cohesion"]
    for tag in comps:
        o, e, rr = A(tag, "observed_cohesion"), A(tag, "random_expected_cohesion"), \
            A(tag, "cohesion_ratio", 3)
        print(f"  {tag:<14}{o['mean']:>9.4f}±{o['std']:<6.4f}{e['mean']:>17.4f}"
              f"{rr['mean']:>9.3f}±{rr['std']:<6.3f}{e['mean']/e0:>13.3f}")

    # ---- Territory ----
    print()
    print("Territory 보유 계열 수 (면적 >= 0.03 · 최대덩어리 >= 0.60 · 자기영역위 >= 0.50)")
    print(f"  {'안':<14}{'보유 계열':>11}{'자기영역위':>12}{'조각 수':>10}"
          f"{'이웃 같은계열':>13}")
    for tag in comps:
        t, oo, fg, nb = (A(tag, "families_with_territory", 2), A(tag, "on_own_region"),
                         A(tag, "fragments_total", 1), A(tag, "neighborhood_top_family_share"))
        print(f"  {tag:<14}{t['mean']:>6.1f}±{t['std']:<4.1f}{oo['mean']:>7.3f}±{oo['std']:<4.3f}"
              f"{fg['mean']:>6.1f}±{fg['std']:<3.1f}{nb['mean']:>8.3f}±{nb['std']:<4.3f}")

    print()
    print("계열별 Territory (시드 5개 평균) — ✓ 는 보유 판정 통과")
    hdr = "".join(f"{t:>26}" for t in comps)
    print(f"  {'계열':<14}{hdr}")
    terr_summary = {}
    for f in families:
        line = f"  {FAMILY_KO[f]:<14}"
        for tag in comps:
            sub = tr[(tr.composition == tag) & (tr.family == f)]
            n = int(sub.n.mean())
            ar, bl, sp, oo = (sub.area_share.mean(), sub.largest_blob_share.mean(),
                              sub.spread.mean(), sub.on_own.mean())
            hs = int(sub.has_territory.sum())
            terr_summary.setdefault(tag, {})[f] = {
                "n": n, "area_share": round(float(ar), 4),
                "largest_blob_share": round(float(bl), 4), "spread": round(float(sp), 3),
                "on_own": round(float(oo), 4), "has_territory_seeds": hs,
                "has_territory": bool(hs >= 3)}
            mark = "✓" if hs >= 3 else ("~" if hs > 0 else "✕")
            line += f"{n:>5}개 면적{ar:>6.1%} 덩어리{bl:>5.0%} {mark:>2}"
        print(line)
    print("  (면적 = 육지 셀 점유율 · 덩어리 = 자기 면적 중 최대 연속 조각 · "
          "판정은 시드 5개 중 3개 이상 통과)")

    print()
    print(f"주목 계열 {[FAMILY_KO[f] for f in FOCUS]} — 팀 §10")
    print(f"  {'계열':<14}{'안':<14}{'개수':>6}{'면적':>8}{'덩어리':>8}{'퍼짐':>8}"
          f"{'자기영역위':>11}{'판정':>7}")
    for f in FOCUS:
        for tag in comps:
            v = terr_summary[tag][f]
            print(f"  {FAMILY_KO[f]:<14}{tag:<14}{v['n']:>6}{v['area_share']:>8.1%}"
                  f"{v['largest_blob_share']:>8.0%}{v['spread']:>8.3f}"
                  f"{v['on_own']:>11.3f}{'보유' if v['has_territory'] else '없음':>7}")

    # ---- Hard Gate 판정 ----
    print()
    print("=" * 100)
    print("Hard Gate 판정 (실행 전 확정 기준)")
    print("=" * 100)
    d0_terr = A("D0 현재", "families_with_territory", 2)["mean"]
    d0_obs = A("D0 현재", "observed_cohesion")["mean"]
    print(f"  P4-C baseline (D0) — Territory 보유 {d0_terr:.1f}계열 · "
          f"관측 응집도 {d0_obs:.4f}")
    print(f"  {'안':<14}{'P4-A':>8}{'P4-B':>8}{'P4-C Territory':>17}"
          f"{'P4-C 관측응집도':>17}{'판정':>8}  Review")
    verdicts = {}
    for tag in comps:
        cr = comp_rows[tag]
        t = A(tag, "families_with_territory", 2)["mean"]
        o = A(tag, "observed_cohesion")["mean"]
        c_terr = t >= d0_terr - 1e-9
        c_obs = o >= d0_obs - 1e-9
        ok = cr["gate_a_top50"] and cr["gate_b_accord"] and c_terr and c_obs
        rv = []
        if not cr["review_edges_ok"]:
            rv.append(f"신뢰간선 {cr['trusted_edges']}<{REVIEW_EDGES}")
        if not cr["review_cross_ok"]:
            rv.append(f"계열횡단 {cr['cross_family_edges']}<{REVIEW_CROSS}")
        if cr["trusted_edges"] == REVIEW_EDGES or cr["cross_family_edges"] == REVIEW_CROSS:
            rv.append("Guardrail 경계선")
        verdicts[tag] = {"gate_a": cr["gate_a_top50"], "gate_b": cr["gate_b_accord"],
                         "gate_c_territory": bool(c_terr), "gate_c_observed": bool(c_obs),
                         "territory_families": t, "observed_cohesion": o,
                         "passes_all": bool(ok), "review_flags": rv}
        print(f"  {tag:<14}{'○' if cr['gate_a_top50'] else '✕':>8}"
              f"{'○' if cr['gate_b_accord'] else '✕':>8}"
              f"{t:>10.1f} {'○' if c_terr else '✕':>5}"
              f"{o:>11.4f} {'○' if c_obs else '✕':>4}"
              f"{'통과' if ok else '탈락':>8}  {' · '.join(rv) if rv else '—'}")

    # ---- D0 대비 짝지은 차이 ----
    print()
    print("D0 대비 시드를 짝지은 차이")
    keys = [("families_with_territory", "Territory 보유 계열", 2),
            ("observed_cohesion", "관측 응집도", 4),
            ("cohesion_ratio", "ratio (분모 오염 주의)", 3),
            ("on_own_region", "자기 계열 영역 위", 4),
            ("fragments_total", "영역 조각 수", 1),
            ("boundary_gap", "경계 향수 분리도", 4),
            ("knn_overlap10", "Korea overlap@10", 4),
            ("reminds_pct", "정답 간선 근접도", 4),
            ("cross_family_proximity", "계열 횡단 근접도", 4)]
    paired = {}
    print(f"  {'지표':<24}" + "".join(f"{t:>22}" for t in list(comps)[1:]))
    for k, ko, nd in keys:
        base = ps.loc[ps.composition == "D0 현재"].set_index("seed")[k]
        line = f"  {ko:<24}"
        for tag in list(comps)[1:]:
            cur = ps.loc[ps.composition == tag].set_index("seed")[k]
            d = (cur - base).to_numpy(float)
            sig = abs(d.mean()) > 2 * d.std() if d.std() > 0 else abs(d.mean()) > 0
            paired.setdefault(tag, {})[k] = {
                "diff_mean": round(float(d.mean()), nd + 1),
                "diff_std": round(float(d.std()), nd + 1),
                "significant": bool(sig),
                "positive_seeds": int((d > 0).sum())}
            line += f"{d.mean():>+15.{nd}f}{'*' if sig else ' ':>2}{int((d>0).sum())}/5"
        print(line)
    print("  (* = |평균| > 2 × 시드 표준편차)")

    # ---- 기록 축 ----
    print()
    print("기록 축 (판정에 쓰지 않는다)")
    print(f"  {'안':<14}{'trust@10':>11}{'rare accord':>13}{'설명불가':>10}"
          f"{'y=계절':>10}{'x=성별':>10}")
    for tag in comps:
        print(f"  {tag:<14}{A(tag,'trust10')['mean']:>11.4f}"
              f"{A(tag,'shared_rare_accord_ge1')['mean']:>13.1%}"
              f"{A(tag,'nearest_unexplained',1)['mean']:>10.1f}"
              f"{A(tag,'y_warmth_rho')['mean']:>10.3f}"
              f"{A(tag,'x_masculine_rho')['mean']:>10.3f}")

    # ---- 저장 ----
    ps.to_csv(os.path.join(OUT_DIR, "per_seed.csv"), index=False, encoding="utf-8-sig")
    tr.to_csv(os.path.join(OUT_DIR, "territory.csv"), index=False, encoding="utf-8-sig")
    pd.DataFrame(swap_rows).to_csv(os.path.join(OUT_DIR, "swaps.csv"),
                                   index=False, encoding="utf-8-sig")
    pd.DataFrame(coord_rows).to_csv(os.path.join(OUT_DIR, "coordinates_korea200.csv"),
                                    index=False, encoding="utf-8-sig")
    memb = []
    for i in ids:
        memb.append({"fragrantica_id": i, "brand": have.loc[i, "brand"],
                     "name": have.loc[i, "name"], "korea_rank": rank[i],
                     "pool_status": status[i], "family": lab[pos_of[i]],
                     "family_ko": FAMILY_KO[lab[pos_of[i]]],
                     "family_top1": round(float(Mn[pos_of[i]].max()), 3),
                     **{f"in_{t}": bool(i in set(sel)) for t, sel in comps.items()}})
    pd.DataFrame(memb).to_csv(os.path.join(OUT_DIR, "compositions.csv"),
                              index=False, encoding="utf-8-sig")
    pd.DataFrame(dist_rows).to_csv(os.path.join(OUT_DIR, "distribution.csv"),
                                   index=False, encoding="utf-8-sig")

    metrics = {
        "question": ("대표 향수 구성을 조정했을 때, 기존 향수의 대표성과 다양성을 크게 "
                     "훼손하지 않으면서 9개 향 계열을 실제로 탐색 가능한 Territory 로 "
                     "만들 수 있는가"),
        "fixed": {"projection": f"C8b — Base {1-FAMILY_W-PERCEPT_W:.3f} + "
                                f"Family {FAMILY_W} + Perception {PERCEPT_W}, "
                                f"UMAP n_neighbors=10 min_dist=0.1 precomputed",
                  "n_display": N_DISPLAY, "pool": len(ids),
                  "family_system": f"Set B {es.MAPPING_VERSION} {len(families)}계열",
                  "within_family_order": "selection_rank (국내 인기) 상위부터",
                  "seeds": list(SEEDS)},
        "compositions": {t: {"ids": comps[t], **comp_rows[t]} for t in comps},
        "d2_quota": {f: quota_d2[f] for f in families},
        "pool_supply": {f: supply[f] for f in families},
        "gates": {
            "declared_before_run": True,
            "P4-A": {"metric": "국내 TOP50 유지", "threshold": f"{GATE_TOP50}/50"},
            "P4-B": {"metric": "accord coverage", "threshold": f">= {GATE_ACCORD}"},
            "P4-C": {"metric": "Territory 보유 계열 수 >= D0 AND 관측 응집도 >= D0",
                     "d0_territory_families": d0_terr, "d0_observed_cohesion": d0_obs,
                     "why_not_ratio": ("normalized cohesion ratio 의 분모는 무작위 기대 "
                                       "Σp_f² 이고 Phase 4 는 계열 분포를 조작 변수로 "
                                       "삼으므로 분모가 오염된다. 관측값이 그대로여도 "
                                       "D2 는 ratio 가 3.921 -> 5.411 로 오른다")},
            "territory_rule": {"area_share": TERR_AREA, "largest_blob_share": TERR_BLOB,
                               "on_own": TERR_ON_OWN,
                               "seed_rule": "시드 5개 중 3개 이상 통과하면 보유"},
            "review_guardrail": {"trusted_edges": REVIEW_EDGES,
                                 "cross_family_edges": REVIEW_CROSS,
                                 "note": "자동 탈락 아님. Korea 200 정답 밀도가 낮다"},
        },
        "reproduction_checks": checks,
        "reproduction_pass": len(checks) - n_fail,
        "reproduction_total": len(checks),
        "verdicts": verdicts,
        "cohesion_three_way": {t: {"observed": A(t, "observed_cohesion"),
                                   "random_expected": A(t, "random_expected_cohesion"),
                                   "ratio": A(t, "cohesion_ratio", 3)} for t in comps},
        "territory_per_family": terr_summary,
        "focus_families": list(FOCUS),
        "paired_vs_d0": paired,
        "seed_aggregates": {t: {k: A(t, k) for k, _ko, _nd in keys} for t in comps},
        "record_axes": {t: {"trust10": A(t, "trust10"),
                            "shared_rare_accord_ge1": A(t, "shared_rare_accord_ge1"),
                            "nearest_unexplained": A(t, "nearest_unexplained", 1),
                            "y_warmth_rho": A(t, "y_warmth_rho"),
                            "x_masculine_rho": A(t, "x_masculine_rho")} for t in comps},
        "notes": {
            "argmax_vs_fractional": ("선정은 argmax, 검증은 두 기준 병기 (팀 §8). "
                                     "균형을 맞추려고 경계 향수를 재분류하지 않았다"),
            "set_b_frozen": "Phase 4 중 Set B taxonomy 를 수정하지 않았다 (팀 §9)",
            "gates_global": ("Gate A · Gate B (Global 1,000) 는 Phase 4 가 건드리지 "
                             "않으므로 재측정하지 않았다"),
            "terrain_params": f"D12 고정값 — bandwidth scott×{bkt.BANDWIDTH_SCALE} · "
                              f"sea {bkt.SEA_PERCENTILE} 백분위. 이번 실험 변수가 아니다",
        },
    }
    with open(os.path.join(OUT_DIR, "metrics.json"), "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=1)
        f.write("\n")

    manifest = {
        "experiment": "P4_BALANCE", "phase": "4",
        "title": "대표 향수 200개의 계열 균형 — D0 / D1 cap30 / D2 최대균형",
        "hypothesis": ("계열별 향수 수를 고르게 만들면 작은 계열도 탐색 가능한 "
                       "Territory 가 된다"),
        "user_meaning": "사용자가 계열 영역을 보고 탐색 방향을 정할 수 있는가",
        "changed_variable": "대표 향수 200개의 구성 (좌표 방식은 C8b 고정)",
        "population": ["korea200"],
        "projection": metrics["fixed"]["projection"],
        "family_mapping_version": es.MAPPING_VERSION,
        "primary_metrics": ["families_with_territory", "observed_cohesion",
                            "per-family area_share / largest_blob_share / spread"],
        "guardrail_metrics": [f"TOP50 = {GATE_TOP50}", f"accord >= {GATE_ACCORD}",
                              "Territory 계열 수 >= D0", "관측 응집도 >= D0"],
        "inputs": {
            "pool": {"path": POOL, "sha256": p3b.sha256(POOL)},
            "top200": {"path": TOP200, "sha256": p3b.sha256(TOP200)},
            "phase3d_metrics": {"path": os.path.join(P3D_DIR, "metrics.json"),
                                "sha256": p3b.sha256(os.path.join(P3D_DIR, "metrics.json"))},
            "accord_dictionary": {"path": ACCORD_DICT, "sha256": p3b.sha256(ACCORD_DICT)},
        },
        "holdout_untouched": "data/korea_popularity/evaluation/gold_set_test.csv — 열지 않았다",
        "writes": [f"experiments/phase4/{n}" for n in
                   ("metrics.json", "manifest.json", "per_seed.csv", "territory.csv",
                    "swaps.csv", "coordinates_korea200.csv", "compositions.csv",
                    "distribution.csv")],
        "elapsed_sec": round(time.time() - t0, 1),
    }
    with open(os.path.join(OUT_DIR, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)
        f.write("\n")

    print()
    print(f"총 소요 {time.time()-t0:.0f}초")
    print(f"  -> {OUT_DIR}/ metrics.json · manifest.json · per_seed.csv · territory.csv · "
          f"swaps.csv · compositions.csv · distribution.csv · coordinates_korea200.csv")


if __name__ == "__main__":
    main()

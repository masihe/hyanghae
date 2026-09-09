"""Family 체계 7 / 8A / 8B / 9 를 같은 조건에서 비교한다.

Run with venv/Scripts/python.exe src/map/experiment_family_count_comparison.py

**왜 이 실험인가.** Phase 0 의 9계열은 PROVISIONAL 이고 9라는 숫자가 검증된 적이 없다.
목적은 응집도가 가장 높은 숫자를 고르는 것이 아니라 **각 체계가 무엇을 얻고 무엇을 잃는지**
같은 조건에서 수치와 사례로 보여주는 것이다. 최종 선택은 팀이 한다.

**모든 체계가 같은 좌표를 공유한다.** 계열 체계는 재라벨링이므로 좌표가 1픽셀도 움직이지
않는다. 따라서 Procrustes 정렬은 이 비교에서 no-op 이고 적용하지 않는다.

**계열 수가 다르면 응집도 절대값을 비교할 수 없다.** 계열이 적으면 무작위로 칠해도 같은
색이 자주 걸린다. 기본 비교 지표는 `observed / random_expected` 비율이다.

**정보 손실은 세 층으로 잰다.** 사전 측정에서 no-family-signal 이 거의 0 이고(7계열
Global 1,000 에서 1개) 손실이 **오배정** 으로 나타난다는 것을 확인했기 때문이다 —
Ariana Grande Cloud(sweet 100 / lactonic 49 / vanilla 43)는 7계열에서 남은 6% 신호로
GREEN 에 배정된다. 그래서 1순위 accord 가 배정된 계열에 속하는지도 함께 센다.

    ① no-family-signal      계열 점수 총량 0. argmax 가 없다
    ② low family-mass       family_mass_ratio 가 낮다 (0.20 / 0.30 / 0.50 세 지점)
    ③ 1순위 accord 미포함    가장 강한 accord 가 배정된 계열에 없다 = 배정 근거가 약하다

산출: experiments/phase0_family_count_comparison/
"""
import json
import os
import sys
import time

import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "common")))
import scent_map as sm
import build_map as bm
import build_korea_terrain as bkt
import experiment_phase0_family_mapping as fm
import experiment_family_systems as es

OUT_DIR = os.path.join("experiments", "phase0_family_count_comparison")
PHASE0 = os.path.join("experiments", "phase0")
TOP200 = os.path.join("data", "korea_popularity", "korea_representative_perfumes_top200.csv")
V2_JSON = os.path.join("output", "korea_scent_map_v2.json")   # 읽기만 한다
SEEDS = (42, 1, 2, 3, 4)
NEIGHBOR_K = 10
PURITY_LEVELS = (0.5, 0.6, 0.7)
REP_PER_FAMILY = 5
CASE_LIMIT = 40


def sha256(path):
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def dist_block(v):
    v = np.asarray(v, float)
    v = v[~np.isnan(v)]
    if not len(v):
        return None
    return {"p10": round(float(np.percentile(v, 10)), 4),
            "median": round(float(np.median(v)), 4),
            "p90": round(float(np.percentile(v, 90)), 4),
            "min": round(float(v.min()), 4), "max": round(float(v.max()), 4)}


def neighborhood_purity(coords, labels, k=NEIGHBOR_K):
    """이웃 k개의 최다 계열 점유율. '여기가 어느 구역인가' 를 읽을 수 있는지의 지표."""
    from scipy.spatial.distance import squareform, pdist
    import collections
    labels = np.asarray(labels, dtype=object)
    D = squareform(pdist(np.asarray(coords, float)))
    np.fill_diagonal(D, np.inf)
    nn = np.argsort(D, axis=1)[:, :k]
    shares = np.array([collections.Counter(labels[row]).most_common(1)[0][1] / k for row in nn])
    own = np.array([labels[i] == collections.Counter(labels[nn[i]]).most_common(1)[0][0]
                    for i in range(len(labels))])
    return {"mean_top_family_share": round(float(shares.mean()), 4),
            "own_is_local_majority": round(float(own.mean()), 4),
            **{f"share_ge_{t}": int((shares >= t).sum()) for t in PURITY_LEVELS}}


def region_purity(coords, labels, families):
    """계열별 KDE argmax 격자에서 자기 계열 영역 위에 있는 향수 비율.

    build_korea_terrain 의 격자·밀도 함수를 그대로 쓴다 (D12 파라미터 고정).
    해수면 임계는 쓰지 않는다 — 파라미터 의존을 줄이기 위해 argmax 만 본다.
    """
    coords = np.asarray(coords, float)
    labels = np.asarray(labels, dtype=object)
    lo, hi, width, height, sample, xs, ys = bkt.make_grid(coords)
    usable = [f for f in families if (labels == f).sum() >= bkt.MIN_CLUSTER_FOR_KDE]
    if len(usable) < 2:
        return None
    grids = np.zeros((len(usable), height, width))
    for i, f in enumerate(usable):
        g = bkt.density(coords[labels == f], sample, width, height)
        grids[i] = g / g.max()
    winner = grids.argmax(axis=0)
    row, col = bkt.cell_index(coords, lo, hi, width, height)
    on_own = 0
    counted = 0
    for i, f in enumerate(labels):
        if f not in usable:
            continue
        counted += 1
        if usable[winner[row[i], col[i]]] == f:
            on_own += 1
    return {"on_own_region": round(on_own / counted, 4), "counted": counted,
            "families_with_region": len(usable),
            "grid": f"{width}x{height}", "params": "bandwidth scott x0.5 (D12), 해수면 미적용"}


def cross_family(coords, index_of, edges, labels, ids):
    """사람이 닮았다고 한 쌍 중 계열을 넘는 것의 수와 2D 근접도."""
    pos = {int(v): i for i, v in enumerate(ids)}
    lab = np.asarray(labels, dtype=object)
    same, cross = [], []
    for a, b in edges:
        (same if lab[pos[a]] == lab[pos[b]] else cross).append((a, b))
    out = {"trusted_edges": len(edges), "same_family": len(same), "cross_family": len(cross),
           "cross_family_share": round(len(cross) / len(edges), 4) if edges else None}
    if cross:
        out["cross_family_proximity"] = round(
            bm.edge_distance_percentile(coords, index_of, cross)[0], 4)
    if same:
        out["same_family_proximity"] = round(
            bm.edge_distance_percentile(coords, index_of, same)[0], 4)
    return out


def evaluate(key, rows, coords, index_of, edges, population):
    """체계 하나 × 모집단 하나의 지표 전부."""
    res = es.family_scores(rows.accord_list.tolist(), key)
    fams = res["families"]
    argmax = res["argmax"]
    n = len(rows)
    ids = rows.id.astype(int).tolist()

    # ① 정보 손실 3층
    mr = res["family_mass_ratio"]
    top_accord = [lst[0][0] if lst else None for lst in rows.accord_list]
    assign, _f, modifiers = es.resolve_system(key)
    top_is_mod = np.array([a in modifiers for a in top_accord])
    top_in_family = np.array([assign.get(top_accord[i]) == argmax[i] for i in range(n)])

    counts = pd.Series(argmax[~res["no_signal"]]).value_counts()
    sizes = np.array([int(counts.get(f, 0)) for f in fams])
    small_t = es.SMALL_FAMILY_THRESHOLDS[population]

    # ② 응집도 — no-family-signal 은 제외하고 계산한다 (없는 계열을 만들지 않는다)
    keep = ~res["no_signal"]
    obs, exp, per = bm.region_cohesion(coords[keep], argmax[keep], k=NEIGHBOR_K)

    out = {
        "system": key, "short": es.SYSTEMS[key]["short"], "population": population,
        "n": n, "family_count": len(fams),
        "families": fams, "families_ko": [fm.FAMILY_DEF[f][0] for f in fams],
        "family_sizes": {f: int(counts.get(f, 0)) for f in fams},
        "family_sizes_ko": {fm.FAMILY_DEF[f][0]: int(counts.get(f, 0)) for f in fams},
        "size_max": int(sizes.max()), "size_min": int(sizes.min()),
        "size_max_share": round(float(sizes.max() / keep.sum()), 4),
        "size_cv": round(float(sizes.std(ddof=0) / sizes.mean()), 4),
        "small_families": {f"n_lt_{t}": int((sizes < t).sum()) for t in small_t},

        "modifier_accords": res["modifiers"],
        "modifier_count": len(res["modifiers"]),
        "no_family_signal": int(res["no_signal"].sum()),
        "coverage": round(float(keep.mean()), 4),
        "low_family_mass": {f"ratio_lt_{t}": int(np.nansum(mr < t))
                            for t in es.LOW_MASS_THRESHOLDS},
        "family_mass_ratio": dist_block(mr),
        "modifier_mass_ratio": dist_block(res["modifier_mass_ratio"]),
        "top_accord_is_modifier": int(top_is_mod.sum()),
        "top_accord_in_assigned_family": round(float(top_in_family.mean()), 4),

        "observed_cohesion": round(float(obs), 4),
        "random_expected_cohesion": round(float(exp), 4),
        "cohesion_ratio": round(float(obs / exp), 3),
        "per_family_cohesion": per,
        "neighborhood_purity": neighborhood_purity(coords[keep], argmax[keep]),
        "margin": {"top1": dist_block(res["top1"]), "margin": dist_block(res["margin"]),
                   **{f"margin_lt_{t}": int(np.nansum(res['margin'] < t))
                      for t in (0.02, 0.05, 0.10)}},
        "cross_family": cross_family(coords, index_of, edges, argmax, ids),
    }
    if population == "korea200":
        out["region_purity"] = region_purity(coords, argmax, fams)

    # 대표 향수
    reps = []
    M = res["M"]
    for i, f in enumerate(fams):
        idx = np.flatnonzero(argmax == f)
        for r in idx[np.argsort(-M[idx, i])][:REP_PER_FAMILY]:
            reps.append({"system": key, "short": es.SYSTEMS[key]["short"],
                         "population": population, "family": f,
                         "family_ko": fm.FAMILY_DEF[f][0],
                         "fragrantica_id": ids[r], "brand": rows.brand.iloc[r],
                         "name": rows["name"].iloc[r],
                         "top1": None if np.isnan(res["top1"][r]) else round(float(res["top1"][r]), 4),
                         "family_mass_ratio": round(float(mr[r]), 4)})
    return out, res, reps


def main() -> None:
    os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))  # MAP/
    os.makedirs(OUT_DIR, exist_ok=True)
    t0 = time.time()

    print("=" * 78)
    print("Family 체계 7 / 8A / 8B / 9 비교 (기본 4 + 민감도 3)")
    print("=" * 78)

    diff = es.mapping_diff()
    print(f"reviewed-1 이 draft-1 과 다른 항목 {len(diff)}건")
    for d in diff:
        print(f"  {d['accord']:<11} {d['draft_1']} -> {d['reviewed_1']}")
    assert len(diff) == 2, "팀이 결정한 변경은 aldehydic, fresh 2건뿐이어야 한다"
    pd.DataFrame(diff).to_csv(os.path.join(OUT_DIR, "mapping_diff.csv"),
                              index=False, encoding="utf-8-sig")

    # ---- 입력 ----
    df, targets, idf_map, _S, D_g, index_of_g, ce_g, _ae = bm.prepare(
        with_selection_comparison=False)
    korea_ids = pd.read_csv(TOP200).fragrantica_id.astype(int).tolist()
    korea = df.set_index("id").loc[korea_ids].reset_index()
    index_of_k = {int(v): i for i, v in enumerate(korea_ids)}
    rin = bm.edges_within(sm.load_edges("reminds_edges.csv"), set(korea_ids))
    ce_k = [(int(a), int(b)) for a, b in rin[bm.confident(rin)][["src", "dst"]].itertuples(
        index=False, name=None)]

    doc = json.loads(open(V2_JSON, encoding="utf-8").read())
    by_id = {p["fragrantica_id"]: (p["x"], p["y"]) for p in doc["points"]}
    coords_k = np.array([by_id[i] for i in korea_ids], dtype=float)
    import umap
    coords_g = np.asarray(umap.UMAP(n_neighbors=10, min_dist=0.1, metric="precomputed",
                                    random_state=42).fit_transform(D_g), dtype=float)
    print(f"\nKorea 200 좌표: {V2_JSON} (읽기 전용, seed 42) · 신뢰 간선 {len(ce_k)}쌍")
    print(f"Global 1,000 좌표: UMAP seed 42 재계산 · 신뢰 간선 {len(ce_g)}쌍")
    print("모든 체계가 이 좌표를 공유한다 — 재라벨링이므로 정렬 불필요")

    # ---- 체계 구성 ----
    systems = {k: es.system_summary(k) for k in es.SYSTEM_ORDER}
    print()
    print(f"  {'체계':<7}{'구분':<12}{'계열':>4}{'modifier':>10}  계열별 accord 수")
    for k in es.SYSTEM_ORDER:
        s = systems[k]
        print(f"  {s['short']:<7}{s['group']:<12}{s['family_count']:>4}{s['modifier_count']:>10}"
              f"  {list(s['accords_per_family'].values())}")

    # ---- 평가 ----
    metrics = {}
    all_reps = []
    assign_frames = {}
    cases = []
    for pop, rows, coords, index_of, edges in (
            ("korea200", korea, coords_k, index_of_k, ce_k),
            ("global1000", targets, coords_g, index_of_g, ce_g)):
        print()
        print(f"--- {pop} (n={len(rows)}) ---")
        print(f"  {'체계':<7}{'계열':>4}{'ratio':>8}{'obs':>8}{'exp':>8}{'no-sig':>8}"
              f"{'mass<0.5':>10}{'1순위≠계열':>11}{'cross':>7}{'근접도':>8}")
        per_pop = {}
        cols = {"fragrantica_id": rows.id.astype(int).values,
                "brand": rows.brand.values, "name": rows["name"].values}
        for k in es.SYSTEM_ORDER:
            out, res, reps = evaluate(k, rows, coords, index_of, edges, pop)
            per_pop[k] = out
            all_reps.extend(reps)
            cols[f"{out['short']}_family"] = res["argmax"]
            cols[f"{out['short']}_top1"] = np.round(res["top1"], 4)
            cols[f"{out['short']}_margin"] = np.round(res["margin"], 4)
            cols[f"{out['short']}_mass_ratio"] = np.round(res["family_mass_ratio"], 4)
            cf = out["cross_family"]
            print(f"  {out['short']:<7}{out['family_count']:>4}{out['cohesion_ratio']:>8.3f}"
                  f"{out['observed_cohesion']:>8.3f}{out['random_expected_cohesion']:>8.3f}"
                  f"{out['no_family_signal']:>8}{out['low_family_mass']['ratio_lt_0.5']:>10}"
                  f"{1 - out['top_accord_in_assigned_family']:>11.1%}"
                  f"{cf['cross_family']:>7}{cf.get('cross_family_proximity', float('nan')):>8.4f}")
        metrics[pop] = per_pop
        assign_frames[pop] = pd.DataFrame(cols)
        assign_frames[pop].to_csv(os.path.join(OUT_DIR, f"assignments_{pop}.csv"),
                                  index=False, encoding="utf-8-sig")

    # ---- 체계 간 배정 변경 행렬 ----
    print()
    print("체계 간 배정이 달라지는 향수 수 (Korea 200)")
    shorts = [es.SYSTEMS[k]["short"] for k in es.SYSTEM_ORDER]
    change = {}
    for pop in ("korea200", "global1000"):
        f = assign_frames[pop]
        mat = {}
        for a in shorts:
            mat[a] = {b: int((f[f"{a}_family"] != f[f"{b}_family"]).sum()) for b in shorts}
        change[pop] = mat
    hdr = "        " + "".join(f"{s:>7}" for s in shorts)
    print(hdr)
    for a in shorts:
        print(f"  {a:<6}" + "".join(f"{change['korea200'][a][b]:>7}" for b in shorts))

    # ---- 사례: 오배정과 신호 손실 ----
    f = assign_frames["korea200"]
    base9 = f["9_family"]
    for k in es.SYSTEM_ORDER:
        s = es.SYSTEMS[k]["short"]
        if s == "9":
            continue
        moved = f[(f[f"{s}_family"] != base9)]
        for _, r in moved.iterrows():
            i = korea_ids.index(int(r["fragrantica_id"]))
            accs = "|".join(f"{n}:{int(v)}" for n, v in korea.accord_list.iloc[i][:5])
            cases.append({
                "case_type": "assignment_change",
                "system": s, "population": "korea200",
                "fragrantica_id": int(r["fragrantica_id"]),
                "brand": r["brand"], "name": r["name"],
                "family_9": r["9_family"], "family_this": r[f"{s}_family"],
                "mass_ratio": r[f"{s}_mass_ratio"], "top_accords": accs,
            })
    # low family-mass 사례 (7계열 기준 최악)
    worst = f.assign(_m=f["7_mass_ratio"]).nsmallest(15, "_m")
    for _, r in worst.iterrows():
        i = korea_ids.index(int(r["fragrantica_id"]))
        accs = "|".join(f"{n}:{int(v)}" for n, v in korea.accord_list.iloc[i][:5])
        cases.append({"case_type": "low_family_mass_7", "system": "7",
                      "population": "korea200",
                      "fragrantica_id": int(r["fragrantica_id"]),
                      "brand": r["brand"], "name": r["name"],
                      "family_9": r["9_family"], "family_this": r["7_family"],
                      "mass_ratio": r["7_mass_ratio"], "top_accords": accs})
    case_frame = pd.DataFrame(cases)
    case_frame.to_csv(os.path.join(OUT_DIR, "cases.csv"), index=False, encoding="utf-8-sig")
    pd.DataFrame(all_reps).to_csv(os.path.join(OUT_DIR, "representatives.csv"),
                                  index=False, encoding="utf-8-sig")

    # ---- 시드 안정성 (Korea 200, cohesion ratio) ----
    print()
    print("시드 안정성 — Korea 200 cohesion ratio")
    D_k = 1.0 - sm.base_similarity(korea.accord_list.tolist(),
                                   korea.note_set.tolist(), idf_map)[0]
    np.fill_diagonal(D_k, 0.0)
    seed_coords = {42: coords_k}
    for s in SEEDS:
        if s == 42:
            continue
        seed_coords[s] = np.asarray(umap.UMAP(n_neighbors=10, min_dist=0.1,
                                              metric="precomputed",
                                              random_state=s).fit_transform(D_k), dtype=float)
    seed_stab = {}
    for k in es.SYSTEM_ORDER:
        res = es.family_scores(korea.accord_list.tolist(), k)
        keep = ~res["no_signal"]
        vals = []
        for s in SEEDS:
            obs, exp, _ = bm.region_cohesion(seed_coords[s][keep], res["argmax"][keep])
            vals.append(obs / exp)
        vals = np.array(vals)
        seed_stab[k] = {"mean": round(float(vals.mean()), 3),
                        "std": round(float(vals.std(ddof=0)), 3),
                        "min": round(float(vals.min()), 3),
                        "max": round(float(vals.max()), 3),
                        "seed42": round(float(vals[0]), 3)}
        print(f"  {es.SYSTEMS[k]['short']:<7} {vals.mean():.3f} ± {vals.std(ddof=0):.3f} "
              f"(최소 {vals.min():.3f} 최대 {vals.max():.3f})")

    # ---- 산출 ----
    with open(os.path.join(OUT_DIR, "systems.json"), "w", encoding="utf-8") as fp:
        json.dump({"mapping_version": es.MAPPING_VERSION,
                   "base_mapping_version": fm.MAPPING_VERSION,
                   "reviewed_overrides": {a: {"family": t, "reason": w}
                                          for a, (t, w) in es.REVIEWED_OVERRIDES.items()},
                   "musk_to_amber": list(es.MUSK_TO_AMBER),
                   "systems": systems}, fp, ensure_ascii=False, indent=1)
        fp.write("\n")

    metrics["seed_stability_korea200"] = seed_stab
    metrics["assignment_change"] = change
    with open(os.path.join(OUT_DIR, "metrics.json"), "w", encoding="utf-8") as fp:
        json.dump(metrics, fp, ensure_ascii=False, indent=1)
        fp.write("\n")

    manifest = {
        "experiment_id": "phase0_family_count_comparison",
        "phase": 0,
        "status": "NEW",
        "hypothesis": ("계열 개수(7/8A/8B/9)는 응집도만으로 고를 수 없다. 각 체계가 "
                       "무엇을 얻고 무엇을 잃는지 같은 조건에서 재면 팀이 선택할 수 있다"),
        "user_meaning": ("사용자가 '여기가 어느 향 구역인가' 를 읽을 수 있으려면 계열이 "
                         "몇 개여야 하고, 계열을 줄일 때 어떤 향수가 엉뚱한 구역으로 가는가"),
        "changed_variable": "Family 체계 (계열 수와 해체 정책). 좌표·유사도·스냅샷은 고정",
        "population": ["korea200", "global1000"],
        "snapshot_hash": {
            "perfumes_csv": sha256(sm.PERFUMES_CSV),
            "korea_top200_csv": sha256(TOP200),
            "phase0_manifest": sha256(os.path.join(PHASE0, "manifest.json")),
        },
        "family_mapping_version": es.MAPPING_VERSION,
        "base_mapping_version": fm.MAPPING_VERSION,
        "base_mapping_sha256": fm.mapping_digest(),
        "family_score_version": "FS1",
        "projection": "umap n_neighbors=10 min_dist=0.1 (Korea 200 은 출하 좌표 = seed 42)",
        "seeds": list(SEEDS),
        "coordinate_note": ("7개 체계가 같은 좌표를 공유한다 (재라벨링). Procrustes 정렬은 "
                            "no-op 이므로 적용하지 않았다"),
        "primary_metrics": ["cohesion_ratio", "coverage", "cross_family_proximity",
                            "top_accord_in_assigned_family"],
        "guardrail_metrics": ["cross_family_proximity"],
        "baseline_reference": {
            "draft_1_global_cross_family_edges": 435,
            "draft_1_korea200_setB_cohesion_ratio": 3.337,
            "note": "Phase 0 은 draft-1 기준이다. reviewed-1 값은 이 실험에서 새로 측정한다",
        },
        "region_purity_params": "build_korea_terrain 격자 (D12: bandwidth scott x0.5), 해수면 미적용",
        "limitations": [
            "Korea 200 의 cross-family 신뢰 간선은 체계마다 20~30쌍뿐이다. 보호 지표 판정은 "
            "Global 1,000 에서 한다",
            "계열 수가 다르면 응집도 절대값을 비교할 수 없다. cohesion_ratio 를 쓴다",
            "sweet 만 modifier 로 두는 절충안은 이번에 실행하지 않았다 (팀 결정)",
        ],
        "recommendation": "summary.html 의 마지막 절 참조. 최종 선택은 팀",
        "elapsed_sec": round(time.time() - t0, 1),
    }
    with open(os.path.join(OUT_DIR, "manifest.json"), "w", encoding="utf-8") as fp:
        json.dump(manifest, fp, ensure_ascii=False, indent=1)
        fp.write("\n")

    print()
    print(f"사례 {len(case_frame)}건 · 대표 향수 {len(all_reps)}건 · 소요 {time.time()-t0:.0f}초")
    print(f"  -> {OUT_DIR}/ (manifest.json, metrics.json, systems.json, "
          f"assignments_*.csv, cases.csv, representatives.csv, mapping_diff.csv)")


if __name__ == "__main__":
    main()

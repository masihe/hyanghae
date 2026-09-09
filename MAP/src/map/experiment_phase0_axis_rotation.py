"""현재 지도를 회전해 이미 존재하는 축 의미를 찾는다 (Phase 0-8).

Run with venv/Scripts/python.exe src/map/experiment_phase0_axis_rotation.py

**왜 이 실험인가.** 지금 지도의 위·아래·좌·우에는 이름이 없다. 그런데 UMAP 좌표계의
방향은 임의로 정해진 것이고, **2D 회전은 점 사이 거리를 하나도 바꾸지 않는다**(등거리
변환). 따라서 지표를 전혀 손상하지 않고 가장 설명 가능한 방향으로 좌표계를 돌릴 수 있다.

향수 문헌이 지목하는 향수 지도의 밑축(light/heavy, feminine/masculine, warm/cool,
day/night)이 우리 데이터에 **사용자 투표로 이미 들어 있다.** Korea 200 결측은
성별 인식 3개 / 계절 2개 / 낮밤 2개뿐이다.

**Perception Axis Blend(C8)와 다르다.** 이 실험은 좌표를 회전만 하고 거리는 건드리지
않는다. C8 은 거리 계산에 인식 축을 섞는 별개 실험이며 Phase 3b 에서 한다.

**한계.** 상관 0.4~0.75 는 경향이며 개별 향수 보장이 아니다. UI 는 "대체로" 로 말해야
한다. 이 실험은 그 예외 사례도 함께 산출한다.

산출: experiments/phase0/axis_rotation/
"""
import json
import os
import sys

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "common")))
import scent_map as sm
import build_map as bm

PHASE0 = os.path.join("experiments", "phase0")
OUT_DIR = os.path.join(PHASE0, "axis_rotation")
TOP200 = os.path.join("data", "korea_popularity", "korea_representative_perfumes_top200.csv")
V2_JSON = os.path.join("output", "korea_scent_map_v2.json")   # 읽기만 한다
SEEDS = (42, 1, 2, 3, 4)
MIN_VOTES = 20        # 축을 만들 최소 투표 수
N_EXTREME = 10

VOTE_COLS = ["id", "winter", "spring", "summer", "autumn", "day", "night",
             "perceived_female", "perceived_female_leaning", "perceived_unisex",
             "perceived_male_leaning", "perceived_male"]

# 기준값은 **결측 처리 방식에 따라 달라진다.**
#   투표 결측을 중앙값으로 채우고 200개 전체로 계산 : y-warmth 0.408 / x-masculine 0.746
#   투표가 MIN_VOTES 이상인 향수만 사용 (이 스크립트) : y-warmth 0.416 / x-masculine 0.753
# 없는 투표를 만들어 넣지 않는 쪽이 맞으므로 후자를 기준으로 쓴다.
EXPECTED = {"rotation_deg": 171, "y_warmth_rho": 0.4162, "x_masculine_rho": 0.7528}
# 시드 5개 평균. seed 42 단독값은 5개 중 가장 좋은 쪽이므로 그것만 인용하면 과대평가된다.
EXPECTED_SEED_MEAN = {"y_warmth_rho": 0.337, "x_masculine_rho": 0.705}


def perception_axes(raw):
    """사용자 투표에서 축 후보를 만든다. 투표가 적으면 NaN 으로 둔다."""
    seas = raw[["winter", "spring", "summer", "autumn"]].astype(float)
    st = seas.sum(axis=1)
    warmth = np.where(st >= MIN_VOTES,
                      ((seas.winter + seas.autumn) - (seas.summer + seas.spring))
                      / st.replace(0, np.nan), np.nan)
    day = raw[["day", "night"]].astype(float)
    dt = day.sum(axis=1)
    nightness = np.where(dt >= MIN_VOTES, (day.night - day.day) / dt.replace(0, np.nan), np.nan)
    g = raw[["perceived_female", "perceived_female_leaning", "perceived_unisex",
             "perceived_male_leaning", "perceived_male"]].astype(float)
    gt = g.sum(axis=1)
    masc = np.where(gt >= MIN_VOTES,
                    ((g.perceived_male + 0.5 * g.perceived_male_leaning)
                     - (g.perceived_female + 0.5 * g.perceived_female_leaning))
                    / gt.replace(0, np.nan), np.nan)
    return {"warmth": np.asarray(warmth, float), "nightness": np.asarray(nightness, float),
            "masculine": np.asarray(masc, float)}, {"season": st.to_numpy(),
                                                    "daypart": dt.to_numpy(),
                                                    "gender": gt.to_numpy()}


def best_rotation(coords, target):
    """y축이 target 과 가장 강하게 상관되는 회전각(1도 단위)을 찾는다."""
    c0 = coords - coords.mean(axis=0)
    ok = ~np.isnan(target)
    best = None
    for deg in range(180):
        th = np.deg2rad(deg)
        R = np.array([[np.cos(th), -np.sin(th)], [np.sin(th), np.cos(th)]])
        rr = c0 @ R.T
        rho, _ = spearmanr(rr[ok, 1], target[ok])
        if best is None or abs(rho) > abs(best[1]):
            best = (deg, float(rho))
    deg, rho = best
    th = np.deg2rad(deg)
    R = np.array([[np.cos(th), -np.sin(th)], [np.sin(th), np.cos(th)]])
    rot = c0 @ R.T
    if rho < 0:          # 부호는 표현 문제다. 위쪽이 '따뜻함' 이 되도록 뒤집는다
        rot[:, 1] *= -1
    return rot, deg, abs(rho)


def axis_corr(coords, axes):
    out = {}
    for name, v in axes.items():
        ok = ~np.isnan(v)
        rx, px = spearmanr(coords[ok, 0], v[ok])
        ry, py = spearmanr(coords[ok, 1], v[ok])
        out[name] = {"x_rho": round(float(rx), 4), "x_p": float(px),
                     "y_rho": round(float(ry), 4), "y_p": float(py),
                     "n": int(ok.sum())}
    return out


def main() -> None:
    os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))  # MAP/
    os.makedirs(OUT_DIR, exist_ok=True)

    print("=" * 78)
    print("Phase 0-8 — Axis Rotation baseline (회전은 거리를 바꾸지 않는다)")
    print("=" * 78)

    korea_ids = pd.read_csv(TOP200).fragrantica_id.astype(int).tolist()
    raw = pd.read_csv(sm.PERFUMES_CSV, low_memory=False, usecols=VOTE_COLS).set_index("id")
    raw = raw.loc[korea_ids]
    perf = sm.load_perfumes().set_index("id")
    rows = perf.loc[korea_ids].reset_index()

    doc = json.loads(open(V2_JSON, encoding="utf-8").read())
    by_id = {p["fragrantica_id"]: (p["x"], p["y"]) for p in doc["points"]}
    coords = np.array([by_id[i] for i in korea_ids], dtype=float)

    axes, vote_totals = perception_axes(raw)
    print("투표 가용성 (Korea 200)")
    for name, v in axes.items():
        print(f"  {name:<11} 사용 가능 {int((~np.isnan(v)).sum())}/200 · "
              f"범위 {np.nanmin(v):+.2f} ~ {np.nanmax(v):+.2f}")
    for name, t in vote_totals.items():
        print(f"  {name:<11} 투표 합계 중앙 {int(np.median(t)):>6} · "
              f"{MIN_VOTES}표 미만 {int((t < MIN_VOTES).sum())}개")

    # ---- 회전 ----
    rot, deg, rho_y = best_rotation(coords, axes["warmth"])
    print(f"\ny축을 warmth 에 맞추는 회전: {deg}도 · y-warmth rho {rho_y:.3f}")
    before = axis_corr(coords, axes)
    after = axis_corr(rot, axes)
    print("  회전 후 축 상관")
    for name in axes:
        print(f"    {name:<11} x {after[name]['x_rho']:+.3f}  y {after[name]['y_rho']:+.3f}"
              f"  (n={after[name]['n']})")

    # ---- 지표 불변 확인 ----
    S, _, _ = sm.base_similarity(rows.accord_list.tolist(), rows.note_set.tolist(),
                                 sm.load_note_idf())
    D = 1.0 - S
    np.fill_diagonal(D, 0.0)
    index_of = {int(v): i for i, v in enumerate(korea_ids)}
    rin = bm.edges_within(sm.load_edges("reminds_edges.csv"), set(korea_ids))
    ce = [(int(a), int(b)) for a, b in rin[bm.confident(rin)][["src", "dst"]].itertuples(
        index=False, name=None)]
    m_before = bm.evaluate_layout(coords, D, index_of, ce)
    m_after = bm.evaluate_layout(rot, D, index_of, ce)
    print("\n회전 전/후 지표 (같아야 정상)")
    invariant = True
    inv_rows = []
    for k in m_before:
        diff = abs(float(m_before[k]) - float(m_after[k]))
        invariant &= diff < 1e-9
        inv_rows.append({"metric": k, "before": float(m_before[k]),
                         "after": float(m_after[k]), "abs_diff": diff})
        print(f"  {k:<16} {float(m_before[k]):.6f} -> {float(m_after[k]):.6f}  차이 {diff:.2e}")
    assert invariant, "회전이 지표를 바꿨다. 등거리 변환이 아니므로 구현을 확인할 것"

    # ---- 축 양 끝과 예외 ----
    def extremes(vals, axis_name, target_name):
        order = np.argsort(-vals)
        recs = []
        for tag, idx in (("high", order[:N_EXTREME]), ("low", order[-N_EXTREME:])):
            for i in idx:
                t = axes[target_name][i]
                recs.append({"axis": axis_name, "end": tag,
                             "fragrantica_id": int(korea_ids[i]),
                             "brand": rows.brand.iloc[i], "name": rows["name"].iloc[i],
                             "axis_value": round(float(vals[i]), 4),
                             target_name: None if np.isnan(t) else round(float(t), 4)})
        return recs

    ext = extremes(rot[:, 1], "y", "warmth") + extremes(rot[:, 0], "x", "masculine")
    pd.DataFrame(ext).to_csv(os.path.join(OUT_DIR, "extremes.csv"),
                             index=False, encoding="utf-8-sig")
    print(f"\ny축 위쪽 끝 5개 (warmth 값)")
    for r in ext[:5]:
        print(f"  {r['brand']} {r['name']}  warmth {r['warmth']}")
    print(f"y축 아래쪽 끝 5개")
    for r in ext[N_EXTREME:N_EXTREME + 5]:
        print(f"  {r['brand']} {r['name']}  warmth {r['warmth']}")

    # 예외 = 축 상위 25% 에 있는데 target 이 하위 25% 인 향수 (반대도)
    exc = []
    for axis_name, vals, target_name in (("y", rot[:, 1], "warmth"),
                                         ("x", rot[:, 0], "masculine")):
        t = axes[target_name]
        ok = ~np.isnan(t)
        hi_axis = vals >= np.percentile(vals, 75)
        lo_t = np.full(len(t), False)
        lo_t[ok] = t[ok] <= np.percentile(t[ok], 25)
        for i in np.flatnonzero(hi_axis & lo_t):
            exc.append({"axis": axis_name, "case": "축은 상위인데 투표는 하위",
                        "fragrantica_id": int(korea_ids[i]),
                        "brand": rows.brand.iloc[i], "name": rows["name"].iloc[i],
                        "axis_value": round(float(vals[i]), 4),
                        "target": target_name, "target_value": round(float(t[i]), 4)})
    pd.DataFrame(exc).to_csv(os.path.join(OUT_DIR, "exceptions.csv"),
                             index=False, encoding="utf-8-sig")
    print(f"\n예외 사례 {len(exc)}건 (축 상위 25% 인데 투표 하위 25%)")
    for r in exc[:5]:
        print(f"  [{r['axis']}] {r['brand']} {r['name']} · {r['target']} {r['target_value']}")

    # ---- 시드 5개에서 축이 재현되는가 ----
    print(f"\n시드별 축 재현성 (같은 유사도, UMAP 시드만 변경)")
    import umap
    seed_rows = []
    for seed in SEEDS:
        c = umap.UMAP(n_neighbors=10, min_dist=0.1, metric="precomputed",
                      random_state=seed).fit_transform(D)
        r, d, ry = best_rotation(np.asarray(c, float), axes["warmth"])
        ok = ~np.isnan(axes["masculine"])
        rx, _ = spearmanr(r[ok, 0], axes["masculine"][ok])
        seed_rows.append({"seed": seed, "rotation_deg": d,
                          "y_warmth_rho": round(float(ry), 4),
                          "x_masculine_rho": round(abs(float(rx)), 4)})
        print(f"  seed {seed:<3} 회전 {d:>3}도 · y-warmth {ry:.3f} · x-masculine {abs(rx):.3f}")
    seed_frame = pd.DataFrame(seed_rows)
    print(f"  y-warmth {seed_frame.y_warmth_rho.mean():.3f} ± "
          f"{seed_frame.y_warmth_rho.std(ddof=0):.3f} · x-masculine "
          f"{seed_frame.x_masculine_rho.mean():.3f} ± "
          f"{seed_frame.x_masculine_rho.std(ddof=0):.3f}")

    # ---- 재현 확인 ----
    print("\n기준값 재현 확인 (seed 42 = 출하 좌표)")
    checks = [("rotation_deg", deg, EXPECTED["rotation_deg"], 2),
              ("y_warmth_rho", rho_y, EXPECTED["y_warmth_rho"], 0.005),
              ("x_masculine_rho", abs(after["masculine"]["x_rho"]),
               EXPECTED["x_masculine_rho"], 0.005)]
    ok_all = True
    for name, got, want, tol in checks:
        hit = abs(got - want) <= tol
        ok_all &= hit
        print(f"  {name:<18} 실측 {got:<9.4f} 기대 {want:<8} {'OK' if hit else '** 차이 **'}")

    np.savetxt(os.path.join(OUT_DIR, "coordinates_rotated.csv"),
               np.c_[np.array(korea_ids), rot], delimiter=",",
               header="fragrantica_id,x_rot,y_rot", comments="", fmt=["%d", "%.6f", "%.6f"])
    with open(os.path.join(OUT_DIR, "metrics.json"), "w", encoding="utf-8") as f:
        json.dump({
            "coordinate_source": "output/korea_scent_map_v2.json (읽기 전용)",
            "rotation_deg": int(deg),
            "axis_definition": {
                "warmth": "((winter+autumn)-(summer+spring)) / 계절 투표 합",
                "nightness": "(night-day) / 낮밤 투표 합",
                "masculine": "((male+0.5*male_leaning)-(female+0.5*female_leaning)) / 성별 투표 합",
                "min_votes": MIN_VOTES,
            },
            "vote_availability": {k: int((~np.isnan(v)).sum()) for k, v in axes.items()},
            "axis_correlation_before": before,
            "axis_correlation_after": after,
            "metric_invariance": inv_rows,
            "metric_invariant": bool(invariant),
            "seed_reproducibility": seed_rows,
            "reproduction_checks": [
                {"name": n, "measured": round(float(g), 4), "expected": w,
                 "tolerance": t, "ok": bool(abs(g - w) <= t)} for n, g, w, t in checks],
            "reproduction_ok": bool(ok_all),
            "limitation": ("상관 0.4~0.75 는 경향이며 개별 향수 보장이 아니다. "
                           "UI 는 '대체로' 로 표현해야 하고, exceptions.csv 가 반례 목록이다."),
            "not_the_same_as": ("Perception Axis Blend(C8)는 거리 계산에 인식 축을 섞는 "
                                "별개 실험이다. 이 실험은 회전만 하고 거리를 바꾸지 않는다."),
        }, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print(f"\n  -> {OUT_DIR}/metrics.json · extremes.csv · exceptions.csv · coordinates_rotated.csv")


if __name__ == "__main__":
    main()

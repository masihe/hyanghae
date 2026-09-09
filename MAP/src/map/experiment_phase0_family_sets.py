"""Family Set A/B/C 의 coverage 와 정규화 응집도를 낸다 (Phase 0-7).

Run with venv/Scripts/python.exe src/map/experiment_phase0_family_sets.py

**왜 정규화가 필요한가.** 응집도(2D 최근접 10개 중 같은 계열 비율)는 **계열 개수에
민감하다.** 계열이 적으면 아무렇게나 칠해도 같은 색이 자주 걸린다. 실측하면

    Set A (4그룹)  응집도 0.387 / 무작위 0.256  ->  1.5배
    Set B (9계열)  응집도 0.519 / 무작위 0.156  ->  3.3배

절대값만 보면 1.6배 차이로 보이지만 실제 차이는 3배에 가깝다. 그래서 비교는
`observed / random_expected` 비율로 한다 (SCENT_MAP_EXPERIMENT_DESIGN_v4.md 10).

무작위 기대값은 계열 비율의 제곱합이고, `build_map.region_cohesion()` 이 이미
(observed, expected, per_label) 를 함께 반환하므로 새로 구현하지 않는다.

**Set A 의 결측은 보간하지 않는다.** Korea 200 에서 Fragrantica 계열이 16개 결측인데
accord 로 추측해 채우지 않고 UNCLASSIFIED 로 둔다. 대신 coverage 를 따로 보고하고
응집도는 분류된 부분집합에서만 계산한다 — 무작위 기대값도 그 부분집합 비율로 낸다.

**좌표는 현재 프로덕션 것을 읽기만 한다.** Phase 3a 의 기준 좌표는 Phase 1 의 유사도와
Phase 2 의 투영으로 다시 만든다. 이 산출물은 Phase 0 시점의 baseline 이다.

산출: experiments/phase0/family_sets.json
"""
import json
import os
import sys

import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "common")))
import scent_map as sm
import build_map as bm
import experiment_phase0_family_mapping as fm
import experiment_phase0_family_score as fs

PHASE0 = os.path.join("experiments", "phase0")
OUT_JSON = os.path.join(PHASE0, "family_sets.json")
TOP200 = os.path.join("data", "korea_popularity", "korea_representative_perfumes_top200.csv")
V2_JSON = os.path.join("output", "korea_scent_map_v2.json")   # 읽기만 한다
UNCLASSIFIED = "UNCLASSIFIED"

# D12 / D21 에 기록된 Set C 실측값. 새로 돌린 값과 비교한다.
EXPECTED_SET_C = {
    "average_k7_silhouette": 0.0761,
    "average_k7_sizes": [70, 61, 27, 18, 15, 5, 4],
    "complete_k8_silhouette": 0.0801,
    "complete_k8_sizes": [51, 31, 30, 26, 19, 19, 14, 10],
}
# 기준값은 **모집단마다 다르다.** Set A 는 결측 처리 방식에 따라 또 달라진다.
#   Korea 200 · 결측을 UNCLASSIFIED 라벨로 두고 200개 전체 : 0.399 / 0.256
#   Korea 200 · 결측을 빼고 분류된 184개만 (v4 10 규칙)   : 아래 값
#   Global 1,000 · select_targets 가 group 결측을 이미 제외 : 0.387 / 0.256
# v4 10 이 요구하는 것은 두 번째다 — coverage 는 따로 보고하고 응집도는 부분집합에서 낸다.
EXPECTED_COHESION = {
    "korea200_setA_observed": 0.4783, "korea200_setA_random": 0.2954,
    "korea200_setB_observed": 0.519, "korea200_setB_random": 0.156,
    "global1000_setA_observed": 0.387, "global1000_setA_random": 0.256,
}


def cohesion_block(coords, labels, drop=None):
    """정규화 응집도. drop 라벨(예: UNCLASSIFIED)은 부분집합으로 빼고 계산한다."""
    labels = np.asarray(labels, dtype=object)
    coords = np.asarray(coords, dtype=float)
    total = len(labels)
    if drop is not None:
        keep = labels != drop
        coords, labels = coords[keep], labels[keep]
    obs, exp, per = bm.region_cohesion(coords, labels)
    return {
        "coverage": round(float(len(labels) / total), 4),
        "n_classified": int(len(labels)),
        "family_count": int(len(set(labels.tolist()))),
        "observed_cohesion": round(float(obs), 4),
        "random_expected_cohesion": round(float(exp), 4),
        "cohesion_ratio": round(float(obs / exp), 3),
        "per_family_cohesion": per,
        "sizes": {str(k): int(v) for k, v in pd.Series(labels).value_counts().items()},
    }


def set_c_recompute(distance):
    """Set C 는 EXISTING_RESULT 다. 규칙을 다시 적용해 기록값이 재현되는지만 본다."""
    from sklearn.cluster import AgglomerativeClustering
    from sklearn.metrics import silhouette_score
    out = {}
    for linkage in ("average", "complete"):
        best = None
        for k in range(2, 13):
            lab = AgglomerativeClustering(n_clusters=k, metric="precomputed",
                                          linkage=linkage).fit_predict(distance)
            sil = float(silhouette_score(distance, lab, metric="precomputed"))
            sizes = np.bincount(lab, minlength=k)
            passes = sizes.min() >= 3 and sizes.max() / len(lab) <= 0.5
            if passes and (best is None or sil > best[1]):
                best = (k, sil, sorted(sizes.tolist(), reverse=True), lab)
        if best is None:
            out[linkage] = {"note": "규칙(최소 3, 최대 비중 0.5)을 통과하는 k 가 없다"}
            continue
        k, sil, sizes, lab = best
        out[linkage] = {"k": k, "silhouette": round(sil, 4), "sizes": sizes,
                        "labels": lab.tolist()}
        print(f"  {linkage:<9} k={k} silhouette {sil:.4f} 크기 {sizes}")
    return out


def main() -> None:
    os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))  # MAP/
    os.makedirs(PHASE0, exist_ok=True)

    print("=" * 78)
    print("Phase 0-7 — Family Set A/B/C coverage 와 정규화 응집도")
    print("=" * 78)

    df, targets, idf_map, S_g, D_g, index_of_g, ce_g, _ae = bm.prepare(
        with_selection_comparison=False)
    korea_ids = pd.read_csv(TOP200).fragrantica_id.astype(int).tolist()
    korea_rows = df.set_index("id").loc[korea_ids].reset_index()

    doc = json.loads(open(V2_JSON, encoding="utf-8").read())
    by_id = {p["fragrantica_id"]: (p["x"], p["y"]) for p in doc["points"]}
    coords_k = np.array([by_id[i] for i in korea_ids], dtype=float)
    print(f"Korea 200 좌표: output/korea_scent_map_v2.json (읽기 전용, layout "
          f"{doc['layout']['layout_id']})")

    out = {"_meta": {
        "coordinate_source": "output/korea_scent_map_v2.json (Phase 0 baseline, 읽기 전용)",
        "phase3a_note": "Phase 3a 의 기준 좌표는 Phase 1 유사도 + Phase 2 투영으로 다시 만든다",
        "cohesion_rule": "비교는 observed / random_expected 비율로 한다. 절대값 비교 금지",
        "family_mapping_version": fm.MAPPING_VERSION,
        "family_score_version": fs.FS_DEFAULT,
    }}

    # ---- Set A — Fragrantica 설명문 계열 -> 4그룹 ----
    grp = korea_rows["group"].fillna(UNCLASSIFIED).astype(str).tolist()
    n_missing = sum(1 for g in grp if g == UNCLASSIFIED)
    print(f"\n--- Set A (외부 taxonomy, scent_map.FAMILY_GROUP) ---")
    print(f"  Korea 200 결측 {n_missing}개 -> UNCLASSIFIED (보간하지 않는다)")
    blk_a = cohesion_block(coords_k, grp, drop=UNCLASSIFIED)
    blk_a["basis"] = "Fragrantica 설명문의 계열 표기 7종을 Fragrance Wheel 4대 그룹으로 묶음"
    blk_a["unclassified"] = n_missing
    blk_a["unclassified_ids"] = [int(korea_rows.id.iloc[i]) for i, g in enumerate(grp)
                                 if g == UNCLASSIFIED]
    print(f"  coverage {blk_a['coverage']:.1%} · 계열 {blk_a['family_count']}개 · "
          f"응집도 {blk_a['observed_cohesion']:.3f} / 무작위 "
          f"{blk_a['random_expected_cohesion']:.3f} -> {blk_a['cohesion_ratio']}배")
    out["setA"] = {"korea200": blk_a}

    # ---- Set B — 사람 검토 accord 기반 (현재 PROVISIONAL) ----
    Mk, fams = fs.score_matrix(korea_rows.accord_list.tolist(), mode=fs.FS_DEFAULT)
    fam_k = np.array([fams[i] for i in Mk.argmax(axis=1)], dtype=object)
    print(f"\n--- Set B (accord 기반 {len(fams)}계열, {fm.MAPPING_VERSION} PROVISIONAL) ---")
    blk_b = cohesion_block(coords_k, fam_k)
    blk_b["basis"] = (f"accord -> 계열 매핑 {fm.MAPPING_VERSION} + Family Score {fs.FS_DEFAULT} "
                      f"의 argmax. 7계열은 Fragrance Wheel, 2계열(Gourmand/Musk)은 IFRA")
    blk_b["unclassified"] = 0
    print(f"  coverage {blk_b['coverage']:.1%} · 계열 {blk_b['family_count']}개 · "
          f"응집도 {blk_b['observed_cohesion']:.3f} / 무작위 "
          f"{blk_b['random_expected_cohesion']:.3f} -> {blk_b['cohesion_ratio']}배")
    out["setB"] = {"korea200": blk_b}

    # ---- Set C — Data-driven (EXISTING_RESULT) ----
    D_k = 1.0 - sm.base_similarity(korea_rows.accord_list.tolist(),
                                   korea_rows.note_set.tolist(), idf_map)[0]
    np.fill_diagonal(D_k, 0.0)
    print(f"\n--- Set C (Data-driven, EXISTING_RESULT) ---")
    set_c = set_c_recompute(D_k)
    out["setC"] = {"status": "EXISTING_RESULT", "recomputed": {
        k: {kk: vv for kk, vv in v.items() if kk != "labels"} for k, v in set_c.items()},
        "recorded_reference": EXPECTED_SET_C,
        "note": ("현재 유사도에서는 자연 계열로 주장하기 어렵다 (silhouette 0.08 수준). "
                 "Phase 1 에서 새 feature 가 채택된 경우에만 그 위에서 다시 실행한다."),
    }
    if "labels" in set_c.get("average", {}):
        blk_c = cohesion_block(coords_k, [f"c{x}" for x in set_c["average"]["labels"]])
        out["setC"]["korea200_average"] = blk_c
        print(f"  average 라벨 응집도 {blk_c['observed_cohesion']:.3f} / 무작위 "
              f"{blk_c['random_expected_cohesion']:.3f} -> {blk_c['cohesion_ratio']}배")

    # ---- Global 1,000 — cross-family 신뢰 간선과 응집도 ----
    print(f"\n--- Global 1,000 (보호 지표의 표본, 좌표는 seed 42 재계산) ---")
    Mg, _ = fs.score_matrix(targets.accord_list.tolist(), mode=fs.FS_DEFAULT)
    fam_g = np.array([fams[i] for i in Mg.argmax(axis=1)], dtype=object)
    grp_g = np.array(targets["group"].fillna(UNCLASSIFIED).astype(str).tolist(), dtype=object)
    import umap
    coords_g = umap.UMAP(n_neighbors=10, min_dist=0.1, metric="precomputed",
                         random_state=42).fit_transform(D_g)
    for name, lab in (("setA", grp_g), ("setB", fam_g)):
        cross = sum(1 for a, b in ce_g if lab[index_of_g[a]] != lab[index_of_g[b]])
        share = cross / len(ce_g)
        blk = cohesion_block(coords_g, lab, drop=UNCLASSIFIED)
        blk.update({"trusted_edges": len(ce_g), "cross_family": int(cross),
                    "cross_family_share": round(float(share), 4)})
        out[name]["global1000"] = blk
        print(f"  {name} cross-family {cross}/{len(ce_g)} ({share:.1%}) · "
              f"coverage {blk['coverage']:.1%} · 응집도 {blk['observed_cohesion']:.3f} / "
              f"무작위 {blk['random_expected_cohesion']:.3f} -> {blk['cohesion_ratio']}배")

    # ---- 재현 확인 ----
    E = EXPECTED_COHESION
    checks = [
        ("korea200 setA observed", blk_a["observed_cohesion"], E["korea200_setA_observed"], 0.005),
        ("korea200 setA random", blk_a["random_expected_cohesion"],
         E["korea200_setA_random"], 0.005),
        ("korea200 setB observed", blk_b["observed_cohesion"], E["korea200_setB_observed"], 0.005),
        ("korea200 setB random", blk_b["random_expected_cohesion"],
         E["korea200_setB_random"], 0.005),
        ("global1000 setA observed", out["setA"]["global1000"]["observed_cohesion"],
         E["global1000_setA_observed"], 0.005),
        ("global1000 setA random", out["setA"]["global1000"]["random_expected_cohesion"],
         E["global1000_setA_random"], 0.005),
        ("setC average silhouette", set_c["average"]["silhouette"],
         EXPECTED_SET_C["average_k7_silhouette"], 0.002),
        ("setC complete silhouette", set_c["complete"]["silhouette"],
         EXPECTED_SET_C["complete_k8_silhouette"], 0.002),
    ]
    print("\n기준값 재현 확인")
    ok = True
    for name, got, want, tol in checks:
        hit = abs(got - want) <= tol
        ok &= hit
        print(f"  {name:<26} 실측 {got:<8.4f} 기대 {want:<8} {'OK' if hit else '** 차이 **'}")
    out["_meta"]["reproduction_ok"] = bool(ok)
    out["_meta"]["reproduction_checks"] = [
        {"name": n, "measured": round(float(g), 4), "expected": w, "tolerance": t,
         "ok": bool(abs(g - w) <= t)} for n, g, w, t in checks]

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print(f"\n  -> {OUT_JSON}")


if __name__ == "__main__":
    main()

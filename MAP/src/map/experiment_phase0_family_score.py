"""Family Score 계산식 FS1/FS2 와 그 분포를 낸다 (Phase 0-6).

Run with venv/Scripts/python.exe src/map/experiment_phase0_family_score.py

**왜 이 산출물인가.** accord -> 계열 매핑표만으로는 "Woody 0.50 / Amber 0.30" 같은
*점수* 가 나오지 않는다. 그런데 Phase 3 의 C3(semi-supervised) · C5~C7(anchor·gradient)
와 Phase 4 의 D3(ambiguous-only balance) 이 전부 이 점수를 쓴다. 계산식이 결과를
크게 바꾸므로 Phase 0 의 실험 변수로 등록한다 — 예비 측정에서 argmax 계열의 2D 응집도가
FS1 0.519 / FS2 0.384 였다.

**FS1 을 기본값으로 고정하는 근거 2개.**
  1. 예비 응집도가 더 높다 (0.519 vs 0.384)
  2. accord 에 IDF 를 적용하는 방향은 EDA 05 에서 이미 기각됐다 (NDCG@10 0.2688 -> 0.2603)
FS2 는 채택 후보가 아니라 "FS1 의 결론이 accord 희귀도 가중에 얼마나 민감한가" 를 보는
민감도 분석이다. FS2 결과 때문에 Phase 3 를 멈추지 않는다.

**C3 임계값.** top1 >= 0.70 을 기본값으로 쓰지 않는다. Global 1,000 예비 분포에서
top1 >= 0.70 인 향수가 22/1000(2.2%)뿐이라 label 이 거의 없는 실험이 된다.
후보 3종(top1 / margin / 둘의 조합)의 coverage 와 계열 편중을 함께 내고,
C3 실행 전에 팀이 하나를 고정한다.

산출: experiments/phase0/family_score/
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

OUT_DIR = os.path.join("experiments", "phase0", "family_score")
ACCORD_DICT = os.path.join("..", "EDA", "analysis_outputs", "10_accord_dictionary.csv")

FS_DEFAULT = "FS1"
FS_VERSIONS = ("FS1", "FS2")

# C3 semi-supervised label 규칙 후보. 실행 전 팀이 하나를 고정한다.
C3_RULES = {
    "RuleA_top1_050": {"top1": 0.50, "margin": None},
    "RuleB_margin_010": {"top1": None, "margin": 0.10},
    "RuleC_top1_045_margin_008": {"top1": 0.45, "margin": 0.08},
}
TOP1_THRESHOLDS = (0.40, 0.50, 0.60, 0.70)
MARGIN_THRESHOLDS = (0.02, 0.05, 0.10)

# 예비 측정으로 확인한 값. 재현되지 않으면 입력이 달라진 것이므로 보고한다.
EXPECTED_GLOBAL_FS1 = {
    "top1_p10": 0.28, "top1_median": 0.39, "top1_p90": 0.55,
    "margin_median": 0.132, "margin_lt_010": 405,
    "top1_ge_070": 22, "top1_ge_050": 203,
}


def accord_idf(share_map: dict) -> dict:
    """accord 보유율에서 IDF 를 만든다 (FS2 전용). log(1/share)."""
    return {a: float(np.log(1.0 / max(s, 1e-6))) for a, s in share_map.items()}


def score_matrix(accord_lists, mode=FS_DEFAULT, idf=None):
    """FS1/FS2 Family Score 행렬. 반환값은 (M, families) 이고 행 합이 1 이다.

    FS1  raw_score(p,f) = sum(strength(p,a))          for a in family f
    FS2  raw_score(p,f) = sum(strength(p,a) * idf(a))
    둘 다 향수별 합 1 로 정규화한다. UNMAPPED accord 는 어느 계열에도 더하지 않는다.
    """
    assert mode in FS_VERSIONS, mode
    if mode == "FS2":
        assert idf is not None, "FS2 는 accord IDF 가 필요하다"
    fams = fm.FAMILY_ORDER
    index = {f: i for i, f in enumerate(fams)}
    M = np.zeros((len(accord_lists), len(fams)), dtype=np.float64)
    for r, lst in enumerate(accord_lists):
        for name, strength in lst:
            fam = fm.ACCORD_FAMILY.get(name, (fm.UNMAPPED, ""))[0]
            if fam == fm.UNMAPPED:
                continue
            w = 1.0 if mode == "FS1" else idf[name]
            M[r, index[fam]] += strength * w
    total = M.sum(axis=1, keepdims=True)
    empty = int((total.ravel() == 0).sum())
    if empty:
        print(f"  ** 계열 점수가 전부 0 인 향수 {empty}개 (UNMAPPED accord 만 가진 경우)")
    M = M / np.maximum(total, 1e-12)
    return M, fams


def describe(M, fams):
    """top1 / top2 / margin / argmax 요약."""
    srt = np.sort(M, axis=1)
    top1, top2 = srt[:, -1], srt[:, -2]
    argmax = np.array([fams[i] for i in M.argmax(axis=1)], dtype=object)
    return top1, top2, top1 - top2, argmax


def dist_block(v):
    return {
        "p10": round(float(np.percentile(v, 10)), 4),
        "median": round(float(np.median(v)), 4),
        "p90": round(float(np.percentile(v, 90)), 4),
        "min": round(float(v.min()), 4),
        "max": round(float(v.max()), 4),
    }


def label_coverage(top1, margin, argmax, fams):
    """threshold 후보별 label 비율과 계열 편중."""
    out = {"top1_thresholds": {}, "margin_thresholds": {}, "c3_rules": {}}
    n = len(top1)
    for t in TOP1_THRESHOLDS:
        out["top1_thresholds"][f">={t:.2f}"] = int((top1 >= t).sum())
    for t in MARGIN_THRESHOLDS:
        out["margin_thresholds"][f"<{t:.2f}"] = int((margin < t).sum())
    for name, rule in C3_RULES.items():
        mask = np.ones(n, dtype=bool)
        if rule["top1"] is not None:
            mask &= top1 >= rule["top1"]
        if rule["margin"] is not None:
            mask &= margin >= rule["margin"]
        per = pd.Series(argmax[mask]).value_counts()
        total = pd.Series(argmax).value_counts()
        skew = {f: round(float(per.get(f, 0) / total.get(f, 1)), 3) for f in fams
                if total.get(f, 0) > 0}
        out["c3_rules"][name] = {
            "labeled": int(mask.sum()),
            "labeled_share": round(float(mask.mean()), 4),
            "unlabeled": int((~mask).sum()),
            "per_family_label_rate": skew,
        }
    return out


def run_population(name, rows, share_map, idf, out):
    """한 모집단에서 FS1/FS2 를 계산하고 분포를 기록한다."""
    print()
    print(f"--- {name} (n={len(rows)}) ---")
    result = {}
    scores = {}
    for mode in FS_VERSIONS:
        M, fams = score_matrix(rows.accord_list.tolist(), mode=mode, idf=idf)
        top1, top2, margin, argmax = describe(M, fams)
        counts = pd.Series(argmax).value_counts()
        result[mode] = {
            "family_count": {f: int(counts.get(f, 0)) for f in fams},
            "family_count_ko": {fm.FAMILY_DEF[f][0]: int(counts.get(f, 0)) for f in fams},
            "top1": dist_block(top1),
            "top2": dist_block(top2),
            "margin": dist_block(margin),
            "coverage": label_coverage(top1, margin, argmax, fams),
        }
        scores[mode] = (M, top1, margin, argmax, fams)
        print(f"  {mode} argmax 분포 "
              f"{ {fm.FAMILY_DEF[f][0]: int(counts.get(f, 0)) for f in fams if counts.get(f, 0)} }")
        print(f"  {mode} top1  p10 {np.percentile(top1,10):.2f} 중앙 {np.median(top1):.2f} "
              f"p90 {np.percentile(top1,90):.2f} 최대 {top1.max():.2f}")
        print(f"  {mode} margin 중앙 {np.median(margin):.3f} / <0.10 인 향수 "
              f"{int((margin<0.10).sum())}/{len(rows)}")

    # FS1 <-> FS2 argmax 가 바뀌는 향수
    a1, a2 = scores["FS1"][3], scores["FS2"][3]
    diff = a1 != a2
    print(f"  FS1 -> FS2 로 argmax 가 바뀌는 향수 {int(diff.sum())}/{len(rows)} "
          f"({diff.mean():.1%})")
    result["fs1_fs2_argmax_diff_count"] = int(diff.sum())

    # 계열별 대표 향수 (FS1 top1 상위 5)
    M1, top1_1, margin_1, a1, fams = scores["FS1"]
    reps = []
    for i, f in enumerate(fams):
        sub = np.flatnonzero(a1 == f)
        if not len(sub):
            continue
        for r in sub[np.argsort(-M1[sub, i])][:5]:
            reps.append({"population": name, "family": f,
                         "family_ko": fm.FAMILY_DEF[f][0],
                         "fragrantica_id": int(rows.id.iloc[r]),
                         "brand": rows.brand.iloc[r], "name": rows["name"].iloc[r],
                         "top1": round(float(top1_1[r]), 4),
                         "margin": round(float(margin_1[r]), 4)})
    return result, scores, reps, diff


def main() -> None:
    os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))  # MAP/
    os.makedirs(OUT_DIR, exist_ok=True)

    print("=" * 78)
    print(f"Phase 0-6 — Family Score (기본값 {FS_DEFAULT}, FS2 는 민감도)")
    print("=" * 78)
    print(f"매핑 {fm.MAPPING_VERSION} / 해시 {fm.mapping_digest()[:16]}... (PROVISIONAL)")

    acc = pd.read_csv(ACCORD_DICT)
    share_map = dict(zip(acc.accord, acc.perfume_share))
    idf = accord_idf(share_map)

    # 두 모집단을 한 번의 perfumes.csv 로드로 처리한다
    df, targets, idf_map, _S, _D, _index_of, _ce, _ae = bm.prepare(with_selection_comparison=False)
    korea_ids = pd.read_csv(
        os.path.join("data", "korea_popularity", "korea_representative_perfumes_top200.csv")
    ).fragrantica_id.astype(int).tolist()
    korea_rows = df.set_index("id").loc[korea_ids].reset_index()

    out = {}
    all_reps = []
    all_diff = []
    for pop_name, rows in [("korea200", korea_rows), ("global1000", targets)]:
        res, scores, reps, diff = run_population(pop_name, rows, share_map, idf, out)
        out[pop_name] = res
        all_reps.extend(reps)
        M1, top1, margin, a1, fams = scores["FS1"]
        M2 = scores["FS2"][0]
        a2 = scores["FS2"][3]
        frame = pd.DataFrame({
            "fragrantica_id": rows.id.astype(int).values,
            "brand": rows.brand.values,
            "name": rows["name"].values,
            "fs1_argmax": a1, "fs1_top1": np.round(top1, 4), "fs1_margin": np.round(margin, 4),
            "fs2_argmax": a2,
        })
        for i, f in enumerate(fams):
            frame[f"fs1_{f}"] = np.round(M1[:, i], 4)
        frame.to_csv(os.path.join(OUT_DIR, f"scores_{pop_name}.csv"),
                     index=False, encoding="utf-8-sig")
        chg = frame.loc[a1 != a2, ["fragrantica_id", "brand", "name", "fs1_argmax", "fs2_argmax"]]
        chg = chg.assign(population=pop_name)
        all_diff.append(chg)

    pd.DataFrame(all_reps).to_csv(os.path.join(OUT_DIR, "family_representatives.csv"),
                                  index=False, encoding="utf-8-sig")
    pd.concat(all_diff).to_csv(os.path.join(OUT_DIR, "fs1_fs2_argmax_diff.csv"),
                               index=False, encoding="utf-8-sig")

    # ---- 예비 측정값 재현 확인 (Global 1,000 · FS1) ----
    g = out["global1000"]["FS1"]
    checks = {
        "top1_p10": (g["top1"]["p10"], EXPECTED_GLOBAL_FS1["top1_p10"], 0.02),
        "top1_median": (g["top1"]["median"], EXPECTED_GLOBAL_FS1["top1_median"], 0.02),
        "top1_p90": (g["top1"]["p90"], EXPECTED_GLOBAL_FS1["top1_p90"], 0.02),
        "margin_median": (g["margin"]["median"], EXPECTED_GLOBAL_FS1["margin_median"], 0.01),
        "margin_lt_010": (g["coverage"]["margin_thresholds"]["<0.10"],
                          EXPECTED_GLOBAL_FS1["margin_lt_010"], 15),
        "top1_ge_070": (g["coverage"]["top1_thresholds"][">=0.70"],
                        EXPECTED_GLOBAL_FS1["top1_ge_070"], 5),
        "top1_ge_050": (g["coverage"]["top1_thresholds"][">=0.50"],
                        EXPECTED_GLOBAL_FS1["top1_ge_050"], 15),
    }
    print()
    print("예비 측정값 재현 확인 (Global 1,000 · FS1)")
    ok = True
    for k, (got, want, tol) in checks.items():
        hit = abs(got - want) <= tol
        ok &= hit
        print(f"  {k:<16} 실측 {got:<8} 기대 {want:<8} 허용 ±{tol:<6} {'OK' if hit else '차이'}")
    if not ok:
        print("  -> 값이 다르다. 매핑이 바뀌었거나 대상 선정이 달라졌다는 뜻이므로 원인을 확인할 것.")

    print()
    print("C3 label 규칙 후보 (Global 1,000 · FS1)")
    for name, blk in g["coverage"]["c3_rules"].items():
        print(f"  {name:<26} label {blk['labeled']:>4}/1000 ({blk['labeled_share']:.1%})")
        skew = {fm.FAMILY_DEF[f][0]: v for f, v in blk["per_family_label_rate"].items()}
        print(f"  {'':26} 계열별 label 비율 {skew}")

    out["_meta"] = {
        "family_score_default": FS_DEFAULT,
        "fs1_basis": "raw accord strength sum, 향수별 합 1 정규화",
        "fs2_basis": "strength x log(1/perfume_share) 합, 동일 정규화. 민감도 분석 전용",
        "fs2_rejected_reference": "accord IDF 방향은 EDA 05 에서 NDCG 0.2688 -> 0.2603 로 기각",
        "mapping_version": fm.MAPPING_VERSION,
        "mapping_sha256": fm.mapping_digest(),
        "mapping_status": "PROVISIONAL",
        "c3_rules": C3_RULES,
        "expected_reproduction_ok": bool(ok),
    }
    with open(os.path.join("experiments", "phase0", "family_score", "distribution.json"),
              "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print()
    print(f"  -> {OUT_DIR}/scores_korea200.csv · scores_global1000.csv")
    print(f"  -> {OUT_DIR}/distribution.json · family_representatives.csv · fs1_fs2_argmax_diff.csv")


if __name__ == "__main__":
    main()

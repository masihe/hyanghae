"""accord 채널과 note 채널이 각각 무엇을 담는지 진단한다 (Phase 0-4).

Run with venv/Scripts/python.exe src/map/experiment_phase0_channel_diag.py

**왜 이 진단인가.** 설계서 v1 은 "Fragrantica 가 accord 를 note + 투표로 계산하므로
둘을 반반 합치면 같은 신호를 두 번 쓴다" 를 전제로 A1(accord only) / A3(note only)
실험을 세웠다. 그런데 실측하면 두 채널의 쌍별 상관이 0.30 이다 — 중복이 아니다.
원인은 우리가 가진 note 가 향수당 중앙 9개, 어휘 2,523종의 극히 일부 표본이기 때문일
것이다. 그래서 실험 질문을 "중복 제거" 에서 **"각 채널이 어떤 유사성을 담는가"** 로
바꾼다 (SCENT_MAP_EXPERIMENT_DESIGN_v4.md 7).

이 진단은 좌표를 만들지 않는다. 유사도 행렬만 본다.

산출: experiments/phase0/channel_diagnosis.json
"""
import json
import os
import sys

import numpy as np
import pandas as pd
from scipy.stats import pearsonr, spearmanr

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "common")))
import scent_map as sm
import build_map as bm

PHASE0 = os.path.join("experiments", "phase0")
OUT_JSON = os.path.join(PHASE0, "channel_diagnosis.json")
TOP200 = os.path.join("data", "korea_popularity", "korea_representative_perfumes_top200.csv")
ACCORD_DICT = os.path.join("..", "EDA", "analysis_outputs", "10_accord_dictionary.csv")

EXPECTED_KOREA_CORR = 0.307   # 이번 세션 실측 (pearson)


def channel_block(name, rows, idf_map):
    S, S_acc, S_note = sm.base_similarity(rows.accord_list.tolist(),
                                          rows.note_set.tolist(), idf_map)
    iu = np.triu_indices(len(rows), 1)
    a, n, t = S_acc[iu], S_note[iu], S[iu]
    pe = float(pearsonr(a, n)[0])
    sp = float(spearmanr(a, n)[0])
    print()
    print(f"--- {name} (n={len(rows)}, 쌍 {len(a):,}개) ---")
    print(f"  accord 코사인 vs note IDF-Jaccard   pearson {pe:+.3f} / spearman {sp:+.3f}")
    for label, v in (("accord 코사인", a), ("note IDF-Jaccard", n), ("합성(0.5:0.5)", t)):
        print(f"  {label:<18} 중앙 {np.median(v):.4f} p10 {np.percentile(v,10):.4f} "
              f"p90 {np.percentile(v,90):.4f} · 0인 쌍 {(v == 0).mean():.1%}")
    hi = a[n >= np.quantile(n, 0.9)]
    print(f"  note 상위 10% 쌍의 accord 유사도 평균 {hi.mean():.3f} (전체 {a.mean():.3f})")
    return {
        "n": int(len(rows)),
        "pairs": int(len(a)),
        "accord_note_pearson": round(pe, 4),
        "accord_note_spearman": round(sp, 4),
        "channels": {
            k: {"median": round(float(np.median(v)), 4),
                "p10": round(float(np.percentile(v, 10)), 4),
                "p90": round(float(np.percentile(v, 90)), 4),
                "mean": round(float(v.mean()), 4),
                "zero_pair_share": round(float((v == 0).mean()), 4)}
            for k, v in (("accord_cosine", a), ("note_idf_jaccard", n), ("blended", t))
        },
        "accord_sim_of_top10pct_note_pairs": round(float(hi.mean()), 4),
    }


def note_predicts_accord(rows, idf_map):
    """note 이진행렬로 accord 강도벡터를 선형 예측할 수 있는가. 참고용."""
    from sklearn.linear_model import Ridge
    from sklearn.model_selection import cross_val_score
    A, _ = sm.build_accord_matrix(rows.accord_list.tolist())
    B, _w, _v, _m = sm.build_note_matrix(rows.note_set.tolist(), idf_map)
    sc = cross_val_score(Ridge(alpha=1.0), B, A, cv=5, scoring="r2")
    print(f"  note -> accord 선형 예측 5-fold R2 평균 {sc.mean():+.3f} "
          f"(fold {np.round(sc, 3).tolist()})")
    print("    ** n 이 작고 차원이 커서 과적합 구간이다. 참고값으로만 읽는다.")
    return {"r2_mean": round(float(sc.mean()), 4), "r2_folds": [round(float(x), 4) for x in sc],
            "caveat": "note 차원이 표본보다 커서 과적합 구간. 중복 여부의 근거로는 상관계수를 쓴다"}


def main() -> None:
    os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))  # MAP/
    os.makedirs(PHASE0, exist_ok=True)

    print("=" * 78)
    print("Phase 0-4 — accord / note 채널 진단")
    print("=" * 78)

    df, targets, idf_map, _S, _D, _io, _ce, _ae = bm.prepare(with_selection_comparison=False)
    korea_ids = pd.read_csv(TOP200).fragrantica_id.astype(int).tolist()
    korea_rows = df.set_index("id").loc[korea_ids].reset_index()

    out = {}
    out["korea200"] = channel_block("Korea 200", korea_rows, idf_map)
    print()
    out["korea200"]["note_predicts_accord"] = note_predicts_accord(korea_rows, idf_map)
    out["global1000"] = channel_block("Global 1,000", targets, idf_map)

    # accord 보유율 상위 — 흔한 accord 가 배경이라는 근거
    acc = pd.read_csv(ACCORD_DICT).sort_values("perfume_share", ascending=False)
    top = acc.head(10)[["accord", "perfume_share"]]
    print()
    print("코퍼스 accord 보유율 상위 10 (배경 accord 확인)")
    print("  " + " · ".join(f"{r.accord} {r.perfume_share:.1%}" for r in top.itertuples()))
    out["corpus_accord_prevalence_top10"] = {
        r.accord: round(float(r.perfume_share), 4) for r in top.itertuples()
    }

    got = out["korea200"]["accord_note_pearson"]
    ok = abs(got - EXPECTED_KOREA_CORR) <= 0.005
    print()
    print(f"재현 확인 — Korea 200 accord↔note pearson 실측 {got:.4f} / "
          f"기대 {EXPECTED_KOREA_CORR} {'OK' if ok else '** 차이 **'}")

    out["_meta"] = {
        "conclusion": ("두 채널은 중복이 아니다 (Korea 200 pearson 0.30). "
                       "실험 질문은 중복 제거가 아니라 각 채널이 어떤 유사성을 담는지다."),
        "implication_for_a1_a3": ("A1(accord only) / A3(raw note) 의 동기를 '중복 제거' 에서 "
                                  "'채널 특성 확인' 으로 바꾼다. 기존 결과는 인용만 한다 "
                                  "— A1 ndcg 0.1688, A3 는 IDF 대비 열세."),
        "implication_for_note_weight": ("note 비중을 올리는 방향은 근거가 없다. 실측: note 단독은 "
                                        "이웃 유사도 0.364 -> 0.264, 공통 상위3 accord 없는 이웃 "
                                        "8.2% -> 38.2%."),
        "reproduction_ok": bool(ok),
    }
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print(f"  -> {OUT_JSON}")


if __name__ == "__main__":
    main()

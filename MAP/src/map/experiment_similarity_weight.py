"""accord : note 가중 비율을 정답 데이터로 스윕한다 (실험, 프로덕션 미반영).

Run with venv/Scripts/python.exe src/map/experiment_similarity_weight.py

**왜 이 실험인가.** 현재 유사도는 `0.5 × accord + 0.5 × IDF note` 다. D1 에 기록된
EDA 04~05 의 측정은 세 지점만 비교했다 — accord 만(w=1.0), note 만(w=0.0), 반반(w=0.5).
**그 사이 값은 한 번도 재지 않았다.** w=0.3 이나 w=0.7 이 더 나을 수 있는데 모른다.

**왜 이 평가 집합인가.** 지도의 200개 안에는 정답 간선이 44쌍뿐이다. 그걸로 가중치를
고르면 표본이 너무 작아 과적합한다. 대신 EDA 04 가 쓴 평가 집합을 그대로 쓴다 —
전체 코퍼스 131,930개에서 `reminds_me_of` 로 만든 정답 쌍, **Development 700 질의**.

`verify_similarity.py` 의 함수를 그대로 import 한다. 평가 절차를 재구현하지 않는다.
**Holdout 300 은 건드리지 않는다.** 최종 확인용으로 남긴다.

먼저 EDA 04 가 기록한 세 값을 4자리까지 재현하는지 확인한다. 재현이 안 되면
스윕 결과를 신뢰할 수 없으므로 그 자리에서 멈춘다.
"""
import os
import sys

import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "common")))
import scent_map as sm
import verify_similarity as vs

# 스윕 대상. 0.0 = note 만, 1.0 = accord 만, 0.5 = 현재 프로덕션.
WEIGHTS = [round(w, 2) for w in np.arange(0.0, 1.01, 0.05)]
OUT = os.path.join("results", "similarity_weight_sweep.csv")


def main() -> None:
    os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))  # MAP/
    df = sm.load_perfumes()
    idf_map = sm.load_note_idf()

    print("=" * 78)
    print("실험 — accord : note 가중 스윕 (Development 700, 프로덕션 미반영)")
    print("=" * 78)
    id_to_row, perfume_ids, relevant_by_query, development, holdout = vs.build_eval_set(df)
    print()
    X_a, X_n, X_nw, ncount, nwsum = vs.build_corpus_matrices(df, idf_map)

    # 재현 게이트용 3개 + 스윕 대상 (IDF 유/무 각각)
    gate = ["Accord Cosine", "Note Jaccard", "Accord + Note"]
    acc = {m: [] for m in gate}
    sweep = {("idf", w): [] for w in WEIGHTS}
    sweep.update({("plain", w): [] for w in WEIGHTS})

    dev_rows = np.array([id_to_row[int(q)] for q in development], dtype=np.int32)
    print(f"\nDevelopment {len(dev_rows)} query × 가중치 {len(WEIGHTS)}종 × IDF 2종 평가 중...")
    for start in range(0, len(dev_rows), vs.BATCH_SIZE):
        qr = dev_rows[start:start + vs.BATCH_SIZE]
        qid = development[start:start + vs.BATCH_SIZE]

        # 두 성분을 한 번만 계산한다. 가중치는 이 위에서 산술로만 섞는다.
        s_acc = (X_a[qr] @ X_a.T).toarray()
        inter = (X_n[qr] @ X_n.T).toarray()
        union = ncount[qr, None] + ncount[None, :] - inter
        s_note = np.zeros_like(inter); np.divide(inter, union, out=s_note, where=union > 0)
        winter = (X_nw[qr] @ X_n.T).toarray()
        wunion = nwsum[qr, None] + nwsum[None, :] - winter
        s_inote = np.zeros_like(winter); np.divide(winter, wunion, out=s_inote, where=wunion > 0)

        def evaluate(v, row, relevant):
            v = v.copy()
            v[row] = -np.inf
            cand = np.argpartition(-v, kth=vs.MAX_K - 1)[:vs.MAX_K]
            order = np.lexsort((perfume_ids[cand], -v[cand]))
            return vs.query_metrics(perfume_ids[cand[order]], relevant, k=10)

        for i, (q, row) in enumerate(zip(qid, qr)):
            relevant = relevant_by_query[int(q)]
            acc["Accord Cosine"].append(evaluate(s_acc[i], row, relevant))
            acc["Note Jaccard"].append(evaluate(s_note[i], row, relevant))
            acc["Accord + Note"].append(evaluate(0.5 * s_acc[i] + 0.5 * s_note[i], row, relevant))
            for w in WEIGHTS:
                sweep[("idf", w)].append(evaluate(w * s_acc[i] + (1 - w) * s_inote[i], row, relevant))
                sweep[("plain", w)].append(evaluate(w * s_acc[i] + (1 - w) * s_note[i], row, relevant))
        done = min(start + vs.BATCH_SIZE, len(dev_rows))
        print(f"  {done}/{len(dev_rows)}", end="\r", flush=True)

    # ---- 재현 게이트 ----
    print("\n")
    print("재현 게이트 — EDA 04 기록값을 4자리까지 재현하는가")
    failed = {}
    for m in gate:
        got = pd.DataFrame(acc[m]).mean()
        exp = vs.EDA_04_DEV700[m]
        row = {k: round(float(got[k]), 4) for k in ("recall", "hit_rate", "mrr", "ndcg")}
        ok = all(abs(row[k] - exp[k]) < 1e-4 for k in exp)
        print(f"  {m:<18}{'일치' if ok else '불일치':<6} recall {row['recall']:.4f} "
              f"ndcg {row['ndcg']:.4f}  (기록 recall {exp['recall']:.4f} ndcg {exp['ndcg']:.4f})")
        if not ok:
            failed[m] = (exp, row)
    if failed:
        raise RuntimeError(f"재현 실패. 스윕 결과를 신뢰할 수 없다: {failed}")

    # ---- 스윕 결과 ----
    rows = []
    for (kind, w), vals in sweep.items():
        r = pd.DataFrame(vals).mean()
        rows.append({"note_weighting": "idf" if kind == "idf" else "plain",
                     "accord_weight": w, "note_weight": round(1 - w, 2),
                     **{k: round(float(r[k]), 4) for k in ("recall", "hit_rate", "mrr", "ndcg")}})
    out = pd.DataFrame(rows).sort_values(["note_weighting", "accord_weight"])
    os.makedirs("results", exist_ok=True)
    out.to_csv(OUT, index=False, encoding="utf-8-sig")

    for kind in ("idf", "plain"):
        sub = out[out.note_weighting == kind]
        best = sub.loc[sub.ndcg.idxmax()]
        print()
        print(f"── note 가중 = {kind} " + "─" * 56)
        print(f"  {'accord:note':>12}{'recall@10':>11}{'hit@10':>9}{'mrr@10':>9}{'ndcg@10':>10}")
        for r in sub.itertuples(index=False):
            mark = ""
            if r.accord_weight == 0.5 and kind == "idf":
                mark = "  ← 현재 프로덕션"
            if r.accord_weight == best.accord_weight:
                mark += "  ★ 최고"
            print(f"  {r.accord_weight:>5.2f}:{r.note_weight:<6.2f}{r.recall:>11.4f}"
                  f"{r.hit_rate:>9.4f}{r.mrr:>9.4f}{r.ndcg:>10.4f}{mark}")

    cur = out[(out.note_weighting == "idf") & (out.accord_weight == 0.5)].iloc[0]
    best = out.loc[out.ndcg.idxmax()]
    print()
    print(f"현재 프로덕션 (idf, 0.5:0.5)  ndcg {cur.ndcg:.4f}  recall {cur.recall:.4f}")
    print(f"스윕 최고 ({best.note_weighting}, {best.accord_weight}:{best.note_weight})  "
          f"ndcg {best.ndcg:.4f}  recall {best.recall:.4f}")
    print(f"차이  ndcg {best.ndcg - cur.ndcg:+.4f}  recall {best.recall - cur.recall:+.4f}")
    print()
    print(f"Holdout {len(holdout)} 질의는 건드리지 않았다. 최종 확인용으로 남긴다.")
    print(f"  -> {OUT}")


if __name__ == "__main__":
    main()

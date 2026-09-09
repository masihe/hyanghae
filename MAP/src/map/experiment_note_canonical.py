"""note 표기 통일(canonical map)을 적용하면 유사도가 나아지는지 잰다 (실험, 프로덕션 미반영).

Run with venv/Scripts/python.exe src/map/experiment_note_canonical.py

**왜 이 실험인가.** D1 이 기록한 현재 유사도의 한계 중 하나가
"note 는 표층 문자열 기반이라 의미적 유사성(서로 다른 이름의 같은 원료)을 못 잡는다" 다.
`EDA/data/scent_knowledge/fragrantica_note_canonical_map_v1.csv` 가 바로 그걸 위한 표인데
**한 번도 적용해 보지 않았다**(PLAN.md §3.2).

**규모는 작다.** 2,523종 중 `SAME_CONCEPT` 48종만 이름이 바뀌어 어휘가 31종 줄어든다
(`Oud`+`Agarwood (Oud)` → `Agarwood` 등). `NOT_SAME` 7종과 `REVIEW` 7종은 합치지 않는다.
효과가 작을 것으로 예상하지만, 예상만으로 접지 않고 측정한다.

**IDF 를 다시 계산한다.** note 를 합치면 그 note 를 가진 향수 수가 달라지므로 IDF 도 달라진다.
공식은 `log((N+1)/(perfume_count+1)) + 1` 이고 사전값과 1.8e-15 까지 일치함을 확인했다.
합친 뒤의 perfume_count 는 **전체 코퍼스에서 다시 센다** — 두 raw note 를 모두 가진
향수가 있으므로 단순 합이 아니다.

평가는 `verify_similarity.py` 의 절차를 그대로 쓴다 (Development 700). Holdout 은 건드리지 않는다.
"""
import os
import sys

import numpy as np
import pandas as pd
from scipy import sparse

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "common")))
import scent_map as sm
import verify_similarity as vs

CANONICAL_MAP = os.path.join("..", "EDA", "data", "scent_knowledge",
                             "fragrantica_note_canonical_map_v1.csv")
MERGE_RELATIONS = {"SAME_CONCEPT"}   # NOT_SAME / REVIEW 는 합치지 않는다
ACCORD_WEIGHT = 0.5                  # 스윕에서 최적으로 확인된 값 (results/similarity_weight_sweep.csv)
OUT = os.path.join("results", "note_canonical_experiment.csv")


def load_map() -> dict[str, str]:
    frame = pd.read_csv(CANONICAL_MAP, keep_default_na=False)
    merge = frame[frame.relation.isin(MERGE_RELATIONS) & (frame.raw_note != frame.canonical_note)]
    print(f"통일 대상 {len(merge)}종 (relation 분포 {frame.relation.value_counts().to_dict()})")
    return dict(zip(merge.raw_note, merge.canonical_note))


def remap(note_sets: pd.Series, mapping: dict[str, str]) -> pd.Series:
    if not mapping:
        return note_sets
    return note_sets.map(lambda s: {mapping.get(n, n) for n in s})


def rebuild_idf(note_sets: pd.Series, base_idf: dict[str, float]) -> tuple[dict[str, float], int]:
    """합친 뒤의 문서빈도로 IDF 를 다시 계산한다. 안 합쳐진 note 는 사전값을 그대로 쓴다."""
    counts: dict[str, int] = {}
    for s in note_sets:
        for n in s:
            counts[n] = counts.get(n, 0) + 1
    idf = dict(base_idf)
    changed = 0
    for note, count in counts.items():
        recomputed = float(np.log((sm.N_TOTAL_CORPUS + 1) / (count + 1)) + 1)
        if note not in base_idf or abs(base_idf[note] - recomputed) > 1e-9:
            idf[note] = recomputed
            changed += 1
    return idf, changed


def evaluate(df: pd.DataFrame, note_sets: pd.Series, idf_map: dict[str, float],
             id_to_row, perfume_ids, relevant_by_query, development, label: str) -> dict:
    work = df.copy()
    work["note_set"] = note_sets
    X_a, X_n, X_nw, ncount, nwsum = vs.build_corpus_matrices(work, idf_map)
    rows = np.array([id_to_row[int(q)] for q in development], dtype=np.int32)
    acc = []
    print(f"  {label} 평가 중...", end="", flush=True)
    for start in range(0, len(rows), vs.BATCH_SIZE):
        qr = rows[start:start + vs.BATCH_SIZE]
        qid = development[start:start + vs.BATCH_SIZE]
        s_acc = (X_a[qr] @ X_a.T).toarray()
        winter = (X_nw[qr] @ X_n.T).toarray()
        wunion = nwsum[qr, None] + nwsum[None, :] - winter
        s_inote = np.zeros_like(winter); np.divide(winter, wunion, out=s_inote, where=wunion > 0)
        blended = ACCORD_WEIGHT * s_acc + (1 - ACCORD_WEIGHT) * s_inote
        for i, (q, row) in enumerate(zip(qid, qr)):
            v = blended[i].copy(); v[row] = -np.inf
            cand = np.argpartition(-v, kth=vs.MAX_K - 1)[:vs.MAX_K]
            order = np.lexsort((perfume_ids[cand], -v[cand]))
            acc.append(vs.query_metrics(perfume_ids[cand[order]], relevant_by_query[int(q)], k=10))
    r = pd.DataFrame(acc).mean()
    print(f" recall {r['recall']:.4f} ndcg {r['ndcg']:.4f}")
    return {"variant": label, **{k: round(float(r[k]), 4) for k in ("recall", "hit_rate", "mrr", "ndcg")}}


def main() -> None:
    os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))  # MAP/
    df = sm.load_perfumes()
    base_idf = sm.load_note_idf()

    print("=" * 78)
    print("실험 — note 표기 통일 적용 여부 (Development 700, 프로덕션 미반영)")
    print("=" * 78)
    id_to_row, perfume_ids, relevant_by_query, development, holdout = vs.build_eval_set(df)
    print()
    mapping = load_map()

    # 문서빈도 재계산이 옳은지 먼저 확인한다 — 합치지 않은 상태에서 사전값을 재현해야 한다.
    _, changed = rebuild_idf(df.note_set, base_idf)
    print(f"통일 없이 문서빈도를 다시 세면 사전값과 달라지는 note: {changed}종")
    print("  (0 이 아니면 코퍼스와 사전이 어긋난 것이므로 그 차이를 감안해 읽어야 한다)")
    print()

    results = [evaluate(df, df.note_set, base_idf, id_to_row, perfume_ids,
                        relevant_by_query, development, "통일 없음 (현재 프로덕션)")]

    merged_notes = remap(df.note_set, mapping)
    merged_idf, n_idf = rebuild_idf(merged_notes, base_idf)
    before = len({n for s in df.note_set for n in s})
    after = len({n for s in merged_notes for n in s})
    print(f"  어휘 {before} → {after} ({before - after}종 감소) · IDF 재계산 {n_idf}종")
    results.append(evaluate(df, merged_notes, merged_idf, id_to_row, perfume_ids,
                            relevant_by_query, development, "통일 적용"))

    out = pd.DataFrame(results)
    os.makedirs("results", exist_ok=True)
    out.to_csv(OUT, index=False, encoding="utf-8-sig")

    print()
    print(f"{'조건':<24}{'recall@10':>11}{'hit@10':>9}{'mrr@10':>9}{'ndcg@10':>10}")
    print("-" * 63)
    for r in out.itertuples(index=False):
        print(f"{r.variant:<24}{r.recall:>11.4f}{r.hit_rate:>9.4f}{r.mrr:>9.4f}{r.ndcg:>10.4f}")
    base, new = out.iloc[0], out.iloc[1]
    print()
    print(f"차이  recall {new.recall - base.recall:+.4f}  ndcg {new.ndcg - base.ndcg:+.4f}")
    print(f"Holdout {len(holdout)} 질의는 건드리지 않았다.")
    print(f"  -> {OUT}")


if __name__ == "__main__":
    main()

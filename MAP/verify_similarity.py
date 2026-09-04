"""Step 1 known-answer test — Base Similarity 재구현이 맞는지 확인한다.

EDA 04의 평가 절차(relevant pair 구축 -> eligible query -> seed 42 추출 ->
Development 700)를 그대로 재현하고, 04가 기록한 지표가 나오는지 본다.
값이 재현되지 않으면 이후 지도 좌표는 전부 의미가 없으므로 여기서 멈춰야 한다.

    python verify_similarity.py

전체 코퍼스(131,930) 대상이라 몇 분 걸린다.
"""
import os
import sys

import numpy as np
import pandas as pd
from scipy import sparse

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import scent_map as sm

SEED = 42
MAX_K = 50
BATCH_SIZE = 32

# EDA 04 노트북의 저장된 출력값 (Development 700)
EDA_04_DEV700 = {
    "Accord Cosine":  {"recall": 0.1868, "hit_rate": 0.4071, "mrr": 0.2564, "ndcg": 0.1688},
    "Note Jaccard":   {"recall": 0.2545, "hit_rate": 0.5029, "mrr": 0.3382, "ndcg": 0.2345},
    "Accord + Note":  {"recall": 0.2900, "hit_rate": 0.5500, "mrr": 0.3806, "ndcg": 0.2668},
}
EDA_04_COUNTS = {"relevant_query": 12150, "eligible_query": 3835}


def build_eval_set(df):
    """EDA 04 cell 6/8/11을 그대로 옮긴다."""
    ids = df["id"].to_numpy(dtype=np.int64)
    id_to_row = {int(v): i for i, v in enumerate(ids)}

    e = sm.load_edges("reminds_edges.csv")
    e = e[(e["src"] > 0) & (e["dst"] > 0) & (e["up_votes"] >= 0) & (e["down_votes"] >= 0)]
    low = np.minimum(e["src"], e["dst"])
    high = np.maximum(e["src"], e["dst"])
    pair = pd.DataFrame({"low": low, "high": high,
                         "up": e["up_votes"], "down": e["down_votes"]})
    pair = pair.groupby(["low", "high"], sort=False, as_index=False)[["up", "down"]].sum()
    pair["total"] = pair["up"] + pair["down"]
    ratio = np.divide(pair["up"], pair["total"],
                      out=np.full(len(pair), np.nan), where=pair["total"].to_numpy() > 0)
    pair["ratio"] = ratio

    rel_all = pair[(pair["low"] != pair["high"]) & (pair["total"] >= 20) & (pair["ratio"] >= 0.8)]
    inside = rel_all["low"].isin(id_to_row) & rel_all["high"].isin(id_to_row)
    rel = rel_all.loc[inside]

    relevant_by_query = {}
    for a, b in rel[["low", "high"]].itertuples(index=False, name=None):
        relevant_by_query.setdefault(int(a), set()).add(int(b))
        relevant_by_query.setdefault(int(b), set()).add(int(a))

    has_accord = df["accord_list"].str.len().gt(0).to_numpy()
    has_note = df["note_set"].str.len().gt(0).to_numpy()

    eligible = np.array(sorted(
        q for q, items in relevant_by_query.items()
        if len(items) >= 2 and has_accord[id_to_row[q]] and has_note[id_to_row[q]]
    ), dtype=np.int32)

    selection_rng = np.random.default_rng(SEED)
    selected = selection_rng.choice(eligible, size=1000, replace=False)
    split_rng = np.random.default_rng(SEED)
    selected = split_rng.permutation(selected)
    development = selected[:700]
    holdout = selected[700:]

    print(f"relevant item>=1 query : {len(relevant_by_query)}  (EDA 04: {EDA_04_COUNTS['relevant_query']})")
    print(f"eligible query         : {len(eligible)}  (EDA 04: {EDA_04_COUNTS['eligible_query']})")
    print(f"Development / Holdout  : {len(development)} / {len(holdout)}")
    return id_to_row, ids, relevant_by_query, development, holdout


def build_corpus_matrices(df, idf_map):
    accord_vocab = sorted({n for lst in df["accord_list"] for n, _ in lst})
    note_vocab = sorted({n for s in df["note_set"] for n in s})
    print(f"accord vocab {len(accord_vocab)} (EDA: 92) / note vocab {len(note_vocab)} (EDA: 2523)")

    ai = {a: i for i, a in enumerate(accord_vocab)}
    rows, cols, data = [], [], []
    for r, lst in enumerate(df["accord_list"]):
        for name, strength in lst:
            rows.append(r); cols.append(ai[name]); data.append(strength)
    X_accord = sparse.csr_matrix(
        (np.asarray(data, np.float32), (np.asarray(rows, np.int32), np.asarray(cols, np.int32))),
        shape=(len(df), len(accord_vocab)), dtype=np.float32)

    ni = {n: i for i, n in enumerate(note_vocab)}
    rows, cols = [], []
    for r, s in enumerate(df["note_set"]):
        for n in s:
            rows.append(r); cols.append(ni[n])
    X_notes = sparse.csr_matrix(
        (np.ones(len(rows), np.float32), (np.asarray(rows, np.int32), np.asarray(cols, np.int32))),
        shape=(len(df), len(note_vocab)), dtype=np.float32)

    norms = np.sqrt(X_accord.multiply(X_accord).sum(axis=1)).A1
    inv = np.zeros_like(norms, dtype=np.float32)
    np.divide(1.0, norms, out=inv, where=norms > 0)
    X_accord_n = X_accord.multiply(inv[:, None]).tocsr()

    fallback = np.log((sm.N_TOTAL_CORPUS + 1) / 1) + 1
    w = np.array([idf_map.get(n, fallback) for n in note_vocab], dtype=np.float32)
    X_notes_w = X_notes.multiply(w[None, :]).tocsr()

    note_counts = np.asarray(X_notes.sum(axis=1)).ravel().astype(np.float32)
    note_wsums = np.asarray(X_notes_w.sum(axis=1)).ravel().astype(np.float32)
    print(f"accord nnz {X_accord.nnz} (EDA: 1,000,570) / note nnz {X_notes.nnz} (EDA: 1,091,811)")
    return X_accord_n, X_notes, X_notes_w, note_counts, note_wsums


def query_metrics(recommended_ids, relevant, k=10):
    rec = recommended_ids[:k]
    rel = np.fromiter((int(c) in relevant for c in rec), dtype=np.int8, count=len(rec))
    hits = int(rel.sum())
    pos = np.flatnonzero(rel)
    disc = 1.0 / np.log2(np.arange(2, len(rel) + 2))
    dcg = float(np.dot(rel, disc))
    idcg = float(disc[:min(len(relevant), k)].sum())
    return {
        "recall": hits / len(relevant),
        "precision": hits / k,
        "hit_rate": float(hits > 0),
        "mrr": 1.0 / (pos[0] + 1) if pos.size else 0.0,
        "ndcg": dcg / idcg if idcg > 0 else 0.0,
    }


def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    df = sm.load_perfumes()
    idf_map = sm.load_note_idf()

    print("=" * 70)
    print("Step 1 — Base Similarity known-answer test (EDA 04 재현)")
    print("=" * 70)
    id_to_row, perfume_ids, relevant_by_query, development, holdout = build_eval_set(df)
    print()
    X_a, X_n, X_nw, ncount, nwsum = build_corpus_matrices(df, idf_map)

    models = ["Accord Cosine", "Note Jaccard", "Accord + Note", "IDF Note", "Accord + IDF Note"]
    acc = {m: [] for m in models}

    dev_rows = np.array([id_to_row[int(q)] for q in development], dtype=np.int32)
    print(f"\nDevelopment {len(dev_rows)} query 평가 중...")
    for start in range(0, len(dev_rows), BATCH_SIZE):
        qr = dev_rows[start:start + BATCH_SIZE]
        qid = development[start:start + BATCH_SIZE]

        s_acc = (X_a[qr] @ X_a.T).toarray()
        inter = (X_n[qr] @ X_n.T).toarray()
        union = ncount[qr, None] + ncount[None, :] - inter
        s_note = np.zeros_like(inter); np.divide(inter, union, out=s_note, where=union > 0)
        winter = (X_nw[qr] @ X_n.T).toarray()
        wunion = nwsum[qr, None] + nwsum[None, :] - winter
        s_inote = np.zeros_like(winter); np.divide(winter, wunion, out=s_inote, where=wunion > 0)

        scores = {
            "Accord Cosine": s_acc,
            "Note Jaccard": s_note,
            "Accord + Note": 0.5 * s_acc + 0.5 * s_note,
            "IDF Note": s_inote,
            "Accord + IDF Note": 0.5 * s_acc + 0.5 * s_inote,
        }
        for i, (q, row) in enumerate(zip(qid, qr)):
            relevant = relevant_by_query[int(q)]
            for m in models:
                v = scores[m][i].copy()
                v[row] = -np.inf
                cand = np.argpartition(-v, kth=MAX_K - 1)[:MAX_K]
                order = np.lexsort((perfume_ids[cand], -v[cand]))
                acc[m].append(query_metrics(perfume_ids[cand[order]], relevant, k=10))

    print()
    print(f"{'model':<20}{'recall@10':>11}{'hit@10':>9}{'mrr@10':>9}{'ndcg@10':>10}   EDA 04 대비")
    print("-" * 78)
    for m in models:
        r = pd.DataFrame(acc[m]).mean()
        exp = EDA_04_DEV700.get(m)
        if exp:
            d = r["ndcg"] - exp["ndcg"]
            note = f"ndcg {exp['ndcg']:.4f} (차이 {d:+.4f})"
        else:
            note = "(04에 없음 — 05에서 채택된 조합)"
        print(f"{m:<20}{r['recall']:>11.4f}{r['hit_rate']:>9.4f}{r['mrr']:>9.4f}{r['ndcg']:>10.4f}   {note}")


if __name__ == "__main__":
    main()

"""A2 — accord 순위/강도 표현을 바꿔본다 (Phase 1, 저비용 신규 후보).

Run with venv/Scripts/python.exe src/map/experiment_a2_accord_rank.py

**왜 이 실험인가.** 현재 accord 채널은 raw strength 를 그대로 쓰고 행 L2 정규화만 한다
(scent_map.build_accord_matrix). strength 는 1순위가 항상 100 이고 8순위가 중앙 26 이다.
상위 accord 의 의미를 더 강하게 반영하거나 순위만 쓰면 사람 유사성 평가가 나아질 수 있다.

**이미 기각된 것과 다르다.** EDA 05 가 기각한 것은 accord 에 **IDF** 를 적용하는 것이고
(NDCG 0.2688 -> 0.2603), 여기서 바꾸는 것은 **강도 표현** 이다.

**note 채널은 고정한다.** baseline 의 IDF-Jaccard 를 그대로 두고 accord 표현만 바꾼다 —
한 번에 한 가지만 바꾼다는 규약(manifest changed_variable) 때문이다.

**KEEP 기준 (v4 14).** ndcg@10 > 0.2709 AND 신뢰 파트너 top10 >= 0.4464.
한 지표만 개선하면 REVIEW. Holdout 300 은 건드리지 않는다.

산출: experiments/P1_A2_ACCORD_RANK/
"""
import json
import os
import sys
import time

import numpy as np
import pandas as pd
from scipy import sparse

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "common")))
import scent_map as sm
import build_map as bm
import verify_similarity as vs

OUT_DIR = os.path.join("experiments", "P1_A2_ACCORD_RANK")
PHASE0 = os.path.join("experiments", "phase0")
ACCORD_DICT = os.path.join("..", "EDA", "analysis_outputs", "10_accord_dictionary.csv")

ACCORD_WEIGHT = 0.5
RARE_ACCORD_MAX_SHARE = 0.30
TOP_K = 10
BASELINE = {"dev700_ndcg": 0.2709, "dev700_recall": 0.3010, "global_top10_hit": 0.4464}
TOL = 0.0015

# 강도 표현 변형. (이름, 설명, 변환 함수(strength, rank0) -> 가중)
VARIANTS = [
    ("baseline_strength", "raw strength (현재 프로덕션)", lambda s, r: s),
    ("sqrt_strength", "sqrt(strength) — 상위 우세를 누른다", lambda s, r: np.sqrt(s)),
    ("sq_strength", "strength^2 — 상위를 더 강조", lambda s, r: s * s),
    ("rank_linear", "순위만 사용: 8,7,...,1", lambda s, r: max(8 - r, 1)),
    ("rank_recip", "순위 역수: 1/(rank+1)", lambda s, r: 1.0 / (r + 1)),
    ("binary", "보유 여부만 (강도 무시)", lambda s, r: 1.0),
    ("top3_strength", "상위 3개만 raw strength", lambda s, r: s if r < 3 else 0.0),
    ("top5_strength", "상위 5개만 raw strength", lambda s, r: s if r < 5 else 0.0),
]


def sha256(path):
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def accord_matrix(accord_lists, fn, vocab=None):
    """변형 가중으로 accord 행렬을 만들고 행 L2 정규화한다 (baseline 과 같은 절차)."""
    if vocab is None:
        vocab = sorted({n for lst in accord_lists for n, _ in lst})
    index = {a: i for i, a in enumerate(vocab)}
    rows, cols, data = [], [], []
    for r, lst in enumerate(accord_lists):
        for rank, (name, strength) in enumerate(lst):
            w = fn(float(strength), rank)
            if w:
                rows.append(r)
                cols.append(index[name])
                data.append(w)
    X = sparse.csr_matrix((np.asarray(data, np.float32),
                           (np.asarray(rows, np.int32), np.asarray(cols, np.int32))),
                          shape=(len(accord_lists), len(vocab)), dtype=np.float32)
    nrm = np.sqrt(np.asarray(X.multiply(X).sum(axis=1))).ravel()
    inv = np.zeros_like(nrm)
    np.divide(1.0, nrm, out=inv, where=nrm > 0)
    return X.multiply(inv[:, None]).tocsr(), vocab


def evaluate_dev(X_acc_n, note_parts, id_to_row, perfume_ids, relevant_by_query,
                 development, label):
    X_n, X_nw, nwsum = note_parts
    rows = np.array([id_to_row[int(q)] for q in development], dtype=np.int32)
    acc = []
    print(f"  {label:<40}", end="", flush=True)
    t = time.time()
    for start in range(0, len(rows), vs.BATCH_SIZE):
        qr = rows[start:start + vs.BATCH_SIZE]
        qid = development[start:start + vs.BATCH_SIZE]
        s_acc = (X_acc_n[qr] @ X_acc_n.T).toarray()
        inter = (X_nw[qr] @ X_n.T).toarray()
        union = nwsum[qr, None] + nwsum[None, :] - inter
        s_note = np.zeros_like(inter)
        np.divide(inter, union, out=s_note, where=union > 0)
        blended = ACCORD_WEIGHT * s_acc + (1 - ACCORD_WEIGHT) * s_note
        for i, (q, row) in enumerate(zip(qid, qr)):
            v = blended[i].copy()
            v[row] = -np.inf
            cand = np.argpartition(-v, kth=vs.MAX_K - 1)[:vs.MAX_K]
            order = np.lexsort((perfume_ids[cand], -v[cand]))
            acc.append(vs.query_metrics(perfume_ids[cand[order]],
                                        relevant_by_query[int(q)], k=TOP_K))
    r = pd.DataFrame(acc).mean()
    print(f" recall {r['recall']:.4f}  ndcg {r['ndcg']:.4f}  ({time.time()-t:.0f}s)")
    return {k: round(float(r[k]), 4) for k in ("recall", "hit_rate", "mrr", "ndcg")}


def global_eval(S_acc, S_note, ids, index_of, edges, note_sets, rare_sets):
    import collections
    S = 0.5 * S_acc + 0.5 * S_note
    np.fill_diagonal(S, -np.inf)
    order = np.argsort(-S, axis=1)[:, :TOP_K]
    partners = collections.defaultdict(set)
    for a, b in edges:
        partners[a].add(b)
        partners[b].add(a)
    hits = [len({ids[j] for j in order[index_of[q]]} & ps) / len(ps)
            for q, ps in partners.items()]
    sn, sr = [], []
    for i in range(len(ids)):
        for j in order[i]:
            sn.append(len(note_sets[i] & note_sets[j]))
            sr.append(len(rare_sets[i] & rare_sets[j]))
    sn, sr = np.array(sn), np.array(sr)
    return {"top10_hit": round(float(np.mean(hits)), 4),
            "explain_shared_note_ge1": round(float((sn >= 1).mean()), 4),
            "explain_shared_rare_accord_ge1": round(float((sr >= 1).mean()), 4)}


def main() -> None:
    os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))  # MAP/
    os.makedirs(OUT_DIR, exist_ok=True)
    t0 = time.time()

    print("=" * 78)
    print("A2 — accord 순위/강도 표현. Phase 1")
    print("=" * 78)

    df, targets, idf_map, _S, _D, index_of_g, ce_g, _ae = bm.prepare(
        with_selection_comparison=False)
    id_to_row, perfume_ids, relevant_by_query, development, holdout = vs.build_eval_set(df)
    _Xa, X_notes, X_notes_w, _nc, nwsum = vs.build_corpus_matrices(df, idf_map)
    note_parts = (X_notes, X_notes_w, nwsum)
    accord_vocab = sorted({n for lst in df["accord_list"] for n, _ in lst})
    print(f"accord 어휘 {len(accord_vocab)}종 · Holdout {len(holdout)} 질의는 건드리지 않는다")

    # Global 1,000 준비 (note 채널은 baseline 고정)
    g = targets.reset_index(drop=True)
    g_ids = g.id.astype(int).tolist()
    B_g, w_g, _v, _m = sm.build_note_matrix(list(g.note_set), idf_map)
    Bw = B_g * w_g
    inter = Bw @ B_g.T
    rs = Bw.sum(axis=1)
    union = rs[:, None] + rs[None, :] - inter
    S_note_g = np.zeros_like(inter)
    np.divide(inter, union, out=S_note_g, where=union > 0)
    acc_dict = pd.read_csv(ACCORD_DICT)
    share = dict(zip(acc_dict.accord, acc_dict.perfume_share))
    note_sets_g = [set(s) for s in g.note_set]
    rare_g = [{n for n, _ in lst if share.get(n, 1.0) < RARE_ACCORD_MAX_SHARE}
              for lst in g.accord_list]

    print()
    print("강도 표현 변형 8종 (note 채널은 baseline 고정)")
    rows = []
    for name, desc, fn in VARIANTS:
        X_acc_n, _ = accord_matrix(df["accord_list"], fn, accord_vocab)
        dev = evaluate_dev(X_acc_n, note_parts, id_to_row, perfume_ids,
                           relevant_by_query, development, f"{name} — {desc}"[:40])
        Ag, _ = accord_matrix(list(g.accord_list), fn, accord_vocab)
        S_acc_g = np.asarray((Ag @ Ag.T).todense())
        glob = global_eval(S_acc_g, S_note_g, g_ids, index_of_g, ce_g, note_sets_g, rare_g)
        rows.append({"variant": name, "description": desc, **dev, **glob})
        print(f"  {'':40} top10 {glob['top10_hit']:.4f} · "
              f"공통note {glob['explain_shared_note_ge1']:.1%}")

    base = next(r for r in rows if r["variant"] == "baseline_strength")
    ok = (abs(base["ndcg"] - BASELINE["dev700_ndcg"]) <= TOL
          and abs(base["top10_hit"] - BASELINE["global_top10_hit"]) <= TOL)
    print()
    print(f"baseline 재현 — ndcg {base['ndcg']} (기대 {BASELINE['dev700_ndcg']}) · "
          f"top10 {base['top10_hit']} (기대 {BASELINE['global_top10_hit']}) "
          f"{'OK' if ok else '** 차이 **'}")
    assert ok, "baseline 재현 실패. 입력이 달라졌으므로 결과를 신뢰할 수 없다"

    print()
    print("=" * 78)
    print("KEEP 기준 판정")
    print("=" * 78)
    print(f"  {'변형':<20}{'ndcg@10':>10}{'Δ':>9}{'top10':>9}{'Δ':>9}  판정")
    verdicts = {}
    for r in sorted(rows, key=lambda x: -x["ndcg"]):
        d1 = r["ndcg"] - BASELINE["dev700_ndcg"]
        d2 = r["top10_hit"] - BASELINE["global_top10_hit"]
        if r["variant"] == "baseline_strength":
            v = "baseline"
        else:
            p1, p2 = r["ndcg"] > BASELINE["dev700_ndcg"], r["top10_hit"] >= BASELINE["global_top10_hit"]
            v = "KEEP" if (p1 and p2) else ("REVIEW" if (p1 or p2) else "DROP")
        verdicts[r["variant"]] = v
        print(f"  {r['variant']:<20}{r['ndcg']:>10.4f}{d1:>+9.4f}"
              f"{r['top10_hit']:>9.4f}{d2:>+9.4f}  {v}")

    pd.DataFrame(rows).to_csv(os.path.join(OUT_DIR, "variants.csv"),
                              index=False, encoding="utf-8-sig")
    best = max((r for r in rows if r["variant"] != "baseline_strength"),
               key=lambda r: (r["ndcg"], r["top10_hit"]))
    overall = "KEEP" if verdicts[best["variant"]] == "KEEP" else (
        "REVIEW" if any(v == "REVIEW" for k, v in verdicts.items()
                        if k != "baseline_strength") else "DROP")
    with open(os.path.join(OUT_DIR, "metrics.json"), "w", encoding="utf-8") as f:
        json.dump({"baseline_reference": BASELINE, "variants": rows,
                   "verdicts": verdicts, "best_non_baseline": best["variant"],
                   "overall_verdict": overall,
                   "note": ("EDA 05 가 기각한 accord IDF 와 다른 실험이다. 여기서 바꾼 것은 "
                            "강도 표현이고 note 채널은 baseline 고정이다")},
                  f, ensure_ascii=False, indent=1)
        f.write("\n")
    manifest = {
        "experiment_id": "P1_A2_ACCORD_RANK", "phase": 1, "status": "NEW",
        "hypothesis": "상위 accord 를 더 강하게 반영하거나 순위만 쓰면 사람 유사성이 개선된다",
        "user_meaning": "그 향수에서 가장 강하게 느껴지는 인상이 비슷한 향수가 가깝다",
        "changed_variable": "accord 채널의 강도 표현 (note 채널은 baseline 고정)",
        "population": ["dev700", "global1000"],
        "snapshot_hash": {"perfumes_csv": sha256(sm.PERFUMES_CSV),
                          "phase0_manifest": sha256(os.path.join(PHASE0, "manifest.json"))},
        "parameters": {"variants": [v[0] for v in VARIANTS], "accord_weight": ACCORD_WEIGHT},
        "primary_metrics": ["dev700 ndcg@10", "global1000 top10_hit"],
        "baseline_reference": BASELINE,
        "verdict": overall,
        "holdout": "Dev 700 만 사용. Holdout 300 은 건드리지 않았다",
        "elapsed_sec": round(time.time() - t0, 1),
    }
    with open(os.path.join(OUT_DIR, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print()
    print(f"판정 {overall} · 총 소요 {time.time()-t0:.0f}초")
    print(f"  -> {OUT_DIR}/ (metrics.json, manifest.json, variants.csv)")


if __name__ == "__main__":
    main()

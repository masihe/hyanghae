"""A8 — note 공동출현(PPMI + SVD)으로 note 채널을 대체한다 (Phase 1, PRIORITY 1).

Run with venv/Scripts/python.exe src/map/experiment_a8_note_cooccurrence.py

**왜 이 실험인가.** D21 이 "accord 8개 + note 표층 문자열의 천장" 이라고 기록한 한계를
넘으려는 시도다. 현재 note 채널은 IDF 가중 Jaccard 라서 **문자열이 같아야만 유사도가
생긴다.** Cedar 와 Sandalwood 는 이름이 다르므로 공통점이 0 이다. 실측하면 Global 1,000
쌍의 36.1% 가 note 유사도 0 이다.

A8 은 어휘를 합치지 않고 **note 사이의 관계를 더한다.** A7(세밀도 집계)과 달리 해상도를
버리지 않는다 — 사전 점검에서 9계열로 압축하면 신뢰 파트너 top10 포함률이
0.4464 -> 0.3114 로 무너졌다.

**계산 경로 (v4 16.2).** 전체 향수 간 dense 131,930 x 131,930 유사도를 만들지 않는다.

    1  note-note 공동출현      X 를 131,930 x 2,523 이진 sparse 로 두고 X^T X (대각 = 문서빈도)
    2  PPMI                   자주 함께 나오는 관계를 강조하고 흔해서 같이 보이는 관계를 낮춘다
    3  Truncated SVD          2,523 -> 64 또는 128 차원
    4  향수 벡터              그 향수 note 임베딩의 (IDF 가중) 평균
    5  유사도                 향수 벡터 사이 코사인

**대조군을 반드시 함께 낸다.** A8 은 note 채널을 두 군데 동시에 바꾼다 —
(a) note 사이 관계 추가 (b) 유사도 함수 Jaccard -> 코사인. Phase 0 에서 (b) 단독 효과를
미리 쟀다: 0.4464 -> 0.4501 (+0.0037). **A8 이 0.4501 보다 유의미하게 높아야 그 개선을
PPMI/SVD 에 귀속할 수 있다.**

**변형 격자.** PPMI 가 이미 흔한 note 를 깎으므로 거기에 IDF 를 또 곱하면 이중 가중이다.
그리고 SVD 코사인은 음수가 나올 수 있어 [0,1] 인 baseline 채널과 범위가 다르다.
둘 다 변형으로 두고 잰다 — 차원 2 x 가중 2 x 음수처리 2 = 8 조건.

**KEEP 기준 (v4 14).** ndcg@10 > 0.2709 AND 신뢰 파트너 top10 >= 0.4464.
한 지표만 개선하면 REVIEW. Holdout 300 은 건드리지 않는다.

산출: experiments/P1_A8_NOTE_COOCCURRENCE/
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

OUT_DIR = os.path.join("experiments", "P1_A8_NOTE_COOCCURRENCE")
PHASE0 = os.path.join("experiments", "phase0")
ACCORD_DICT = os.path.join("..", "EDA", "analysis_outputs", "10_accord_dictionary.csv")

SEED = 42
ACCORD_WEIGHT = 0.5          # D21 이 42조합 스윕으로 고정한 값
SVD_DIMS = (64, 128)
NOTE_WEIGHTS = ("idf", "plain")
NEG_MODES = ("clip0", "raw")
WEIGHT_SWEEP = (0.3, 0.4, 0.5, 0.6, 0.7)
RARE_ACCORD_MAX_SHARE = 0.30   # 고정 시험지: 이보다 흔한 accord 는 설명 근거로 쓰지 않는다
TOP_K = 10

# Phase 0 이 실측 고정한 기준값
BASELINE = {
    "dev700_ndcg": 0.2709,
    "dev700_recall": 0.3010,
    "global_top10_hit": 0.4464,
    "control_note_cosine_top10_hit": 0.4501,   # PPMI 없이 Jaccard -> 코사인만
}
TOL = 0.0015


def sha256(path):
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


# --------------------------------------------------------------------------
# Step 1~3 — 공동출현 -> PPMI -> SVD
# --------------------------------------------------------------------------
def cooccurrence(X_notes):
    """X^T X. 대각선은 문서빈도이므로 관계 행렬에서는 0 으로 둔다."""
    C = (X_notes.T @ X_notes).astype(np.float64)
    C = np.asarray(C.todense()) if sparse.issparse(C) else np.asarray(C)
    df_diag = np.diag(C).copy()
    np.fill_diagonal(C, 0.0)
    return C, df_diag


def ppmi(C):
    """Positive PMI. log(p_ij / (p_i p_j)) 의 음수를 0 으로 자른다."""
    total = C.sum()
    assert total > 0
    p_ij = C / total
    p_i = C.sum(axis=1) / total
    denom = np.outer(p_i, p_i)
    with np.errstate(divide="ignore", invalid="ignore"):
        M = np.log(np.divide(p_ij, denom, out=np.zeros_like(p_ij), where=denom > 0),
                   out=np.zeros_like(p_ij), where=(p_ij > 0) & (denom > 0))
    np.maximum(M, 0.0, out=M)
    return M


def note_embedding(M, k):
    from sklearn.decomposition import TruncatedSVD
    svd = TruncatedSVD(n_components=k, random_state=SEED)
    E = svd.fit_transform(M)
    return E, float(svd.explained_variance_ratio_.sum())


def perfume_vectors(X_notes, E, idf_vec, weighting, neg_mode):
    """Step 4~5. 향수 벡터 = note 임베딩의 (IDF) 가중 평균, L2 정규화."""
    W = X_notes.multiply(idf_vec[None, :]).tocsr() if weighting == "idf" else X_notes
    denom = np.asarray(W.sum(axis=1)).ravel()
    denom[denom == 0] = 1.0
    V = (W @ E) / denom[:, None]
    if neg_mode == "clip0":
        # baseline note 채널은 [0,1] 이다. 범위를 맞추려면 음수를 자른다.
        # raw 는 자르지 않은 조건 — 둘 다 재서 이 선택의 영향을 본다.
        pass  # 코사인 단계에서 자른다 (벡터를 자르면 방향이 바뀐다)
    nrm = np.linalg.norm(V, axis=1, keepdims=True)
    nrm[nrm == 0] = 1.0
    return (V / nrm).astype(np.float32)


# --------------------------------------------------------------------------
# 평가
# --------------------------------------------------------------------------
def note_sim_block(V, rows, neg_mode):
    s = V[rows] @ V.T
    return np.clip(s, 0.0, None) if neg_mode == "clip0" else s


def evaluate_dev(X_acc_n, V, id_to_row, perfume_ids, relevant_by_query, development,
                 label, neg_mode="clip0", accord_weight=ACCORD_WEIGHT, jaccard=None):
    """Dev 700 retrieval. verify_similarity 의 절차를 그대로 쓴다 (재구현하지 않는다)."""
    rows = np.array([id_to_row[int(q)] for q in development], dtype=np.int32)
    acc = []
    print(f"  {label:<46}", end="", flush=True)
    t = time.time()
    for start in range(0, len(rows), vs.BATCH_SIZE):
        qr = rows[start:start + vs.BATCH_SIZE]
        qid = development[start:start + vs.BATCH_SIZE]
        s_acc = (X_acc_n[qr] @ X_acc_n.T).toarray()
        if jaccard is not None:
            X_n, X_nw, nwsum = jaccard
            inter = (X_nw[qr] @ X_n.T).toarray()
            union = nwsum[qr, None] + nwsum[None, :] - inter
            s_note = np.zeros_like(inter)
            np.divide(inter, union, out=s_note, where=union > 0)
        else:
            s_note = note_sim_block(V, qr, neg_mode)
        blended = accord_weight * s_acc + (1 - accord_weight) * s_note
        for i, (q, row) in enumerate(zip(qid, qr)):
            v = blended[i].copy()
            v[row] = -np.inf
            cand = np.argpartition(-v, kth=vs.MAX_K - 1)[:vs.MAX_K]
            order = np.lexsort((perfume_ids[cand], -v[cand]))
            acc.append(vs.query_metrics(perfume_ids[cand[order]], relevant_by_query[int(q)],
                                        k=TOP_K))
    r = pd.DataFrame(acc).mean()
    print(f" recall {r['recall']:.4f}  ndcg {r['ndcg']:.4f}  ({time.time()-t:.0f}s)")
    return {k: round(float(r[k]), 4) for k in ("recall", "hit_rate", "mrr", "ndcg")}


def global_metrics(sim, ids, index_of, edges, note_sets, rare_sets):
    """신뢰 파트너 top10 포함률 + 고정 시험지 설명 가능성 + 이웃 목록."""
    import collections
    S = sim.copy()
    np.fill_diagonal(S, -np.inf)
    order = np.argsort(-S, axis=1)[:, :TOP_K]
    partners = collections.defaultdict(set)
    for a, b in edges:
        partners[a].add(b)
        partners[b].add(a)
    hits, in_top = [], {}
    for q, ps in partners.items():
        got = {ids[j] for j in order[index_of[q]]}
        hits.append(len(got & ps) / len(ps))
        in_top[q] = got & ps
    shared_note, shared_rare = [], []
    for i in range(len(ids)):
        for j in order[i]:
            shared_note.append(len(note_sets[i] & note_sets[j]))
            shared_rare.append(len(rare_sets[i] & rare_sets[j]))
    shared_note = np.array(shared_note)
    shared_rare = np.array(shared_rare)
    return {
        "top10_hit": round(float(np.mean(hits)), 4),
        "queries": len(partners),
        "explain_shared_note_ge1": round(float((shared_note >= 1).mean()), 4),
        "explain_shared_rare_accord_ge1": round(float((shared_rare >= 1).mean()), 4),
        "explain_mean_shared_note": round(float(shared_note.mean()), 3),
    }, order, in_top


def main() -> None:
    os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))  # MAP/
    os.makedirs(OUT_DIR, exist_ok=True)
    t0 = time.time()

    print("=" * 78)
    print("A8 — note 공동출현 (PPMI + Truncated SVD). Phase 1 / PRIORITY 1")
    print("=" * 78)

    # ---- 입력 ----
    df, targets, idf_map, _S, _D, index_of_g, ce_g, _ae = bm.prepare(
        with_selection_comparison=False)
    id_to_row, perfume_ids, relevant_by_query, development, holdout = vs.build_eval_set(df)
    X_acc_n, X_notes, X_notes_w, ncount, nwsum = vs.build_corpus_matrices(df, idf_map)
    note_vocab = sorted({n for s in df["note_set"] for n in s})
    vocab_index = {n: i for i, n in enumerate(note_vocab)}
    fallback = np.log((sm.N_TOTAL_CORPUS + 1) / 1) + 1
    idf_vec = np.array([idf_map.get(n, fallback) for n in note_vocab], dtype=np.float64)
    print(f"Holdout {len(holdout)} 질의는 건드리지 않는다")

    # ---- Step 1~2 ----
    print()
    print("Step 1 — note-note 공동출현 (X^T X)")
    t = time.time()
    C, df_diag = cooccurrence(X_notes)
    nz = int((C > 0).sum())
    print(f"  {C.shape[0]}x{C.shape[1]} · 0 이 아닌 칸 {nz:,} ({nz/C.size:.1%}) · "
          f"{time.time()-t:.0f}초")
    print(f"  문서빈도 상위: " + " · ".join(
        f"{note_vocab[i]} {int(df_diag[i]):,}" for i in np.argsort(-df_diag)[:6]))
    print("Step 2 — PPMI")
    P = ppmi(C)
    pnz = int((P > 0).sum())
    print(f"  0 이 아닌 칸 {pnz:,} ({pnz/P.size:.1%}) · 최댓값 {P.max():.2f}")
    # 진단: 이름이 다른데 관계가 강한 note 쌍
    pairs = []
    iu = np.triu_indices(len(note_vocab), 1)
    top = np.argsort(-P[iu])[:12]
    for t_ in top:
        i, j = iu[0][t_], iu[1][t_]
        pairs.append({"note_a": note_vocab[i], "note_b": note_vocab[j],
                      "ppmi": round(float(P[i, j]), 3),
                      "cooccur": int(C[i, j]), "df_a": int(df_diag[i]), "df_b": int(df_diag[j])})
    print("  PPMI 상위 쌍: " + " · ".join(f"{p['note_a']}~{p['note_b']}" for p in pairs[:5]))

    # 참조: Cedar 와 Sandalwood 처럼 실험 동기가 된 쌍
    probes = [("Cedar", "Sandalwood"), ("Oud", "Agarwood (Oud)"), ("Bergamot", "Lemon"),
              ("Jasmine", "Tuberose"), ("Vanilla", "Tonka Bean")]
    probe_rows = []
    for a, b in probes:
        if a in vocab_index and b in vocab_index:
            i, j = vocab_index[a], vocab_index[b]
            probe_rows.append({"note_a": a, "note_b": b, "cooccur": int(C[i, j]),
                               "ppmi": round(float(P[i, j]), 3),
                               "df_a": int(df_diag[i]), "df_b": int(df_diag[j])})
    print("  실험 동기 쌍:")
    for r in probe_rows:
        print(f"    {r['note_a']:<16} ~ {r['note_b']:<16} 동시출현 {r['cooccur']:>6,} "
              f"PPMI {r['ppmi']:.3f}")

    # ---- 기준값 재현 ----
    print()
    print("기준값 재현 (이게 맞아야 이후 결과를 신뢰할 수 있다)")
    base = evaluate_dev(X_acc_n, None, id_to_row, perfume_ids, relevant_by_query, development,
                        "baseline (accord 0.5 + note IDF-Jaccard)",
                        jaccard=(X_notes, X_notes_w, nwsum))
    ok_base = (abs(base["ndcg"] - BASELINE["dev700_ndcg"]) <= TOL
               and abs(base["recall"] - BASELINE["dev700_recall"]) <= TOL)
    print(f"  -> ndcg {base['ndcg']} (기대 {BASELINE['dev700_ndcg']}) "
          f"{'OK' if ok_base else '** 차이 **'}")
    assert ok_base, "baseline 재현 실패. 입력이 달라졌으므로 실험을 진행하지 않는다"

    # 대조군: PPMI 없이 note IDF 코사인
    nrm = np.sqrt(np.asarray(X_notes_w.multiply(X_notes_w).sum(axis=1))).ravel()
    nrm[nrm == 0] = 1.0
    V_ctrl = np.asarray(X_notes_w.multiply(1.0 / nrm[:, None]).todense(), dtype=np.float32) \
        if False else None   # 131,930 x 2,523 dense 는 만들지 않는다
    ctrl_sparse = X_notes_w.multiply(1.0 / nrm[:, None]).tocsr()

    def ctrl_note_block(rows):
        return np.asarray((ctrl_sparse[rows] @ ctrl_sparse.T).todense())

    # 대조군은 sparse 경로가 필요하므로 evaluate_dev 를 쓰지 않고 같은 절차를 인라인한다
    rows_dev = np.array([id_to_row[int(q)] for q in development], dtype=np.int32)
    accd = []
    print(f"  {'대조군 (accord 0.5 + note IDF-cosine, PPMI 없음)':<46}", end="", flush=True)
    t = time.time()
    for start in range(0, len(rows_dev), vs.BATCH_SIZE):
        qr = rows_dev[start:start + vs.BATCH_SIZE]
        qid = development[start:start + vs.BATCH_SIZE]
        blended = ACCORD_WEIGHT * (X_acc_n[qr] @ X_acc_n.T).toarray() \
            + (1 - ACCORD_WEIGHT) * ctrl_note_block(qr)
        for i, (q, row) in enumerate(zip(qid, qr)):
            v = blended[i].copy()
            v[row] = -np.inf
            cand = np.argpartition(-v, kth=vs.MAX_K - 1)[:vs.MAX_K]
            order = np.lexsort((perfume_ids[cand], -v[cand]))
            accd.append(vs.query_metrics(perfume_ids[cand[order]], relevant_by_query[int(q)],
                                         k=TOP_K))
    rc = pd.DataFrame(accd).mean()
    control = {k: round(float(rc[k]), 4) for k in ("recall", "hit_rate", "mrr", "ndcg")}
    print(f" recall {control['recall']:.4f}  ndcg {control['ndcg']:.4f}  ({time.time()-t:.0f}s)")

    # ---- Global 1,000 준비 ----
    g_rows = targets.reset_index(drop=True)
    g_ids = g_rows.id.astype(int).tolist()
    g_pos = np.array([id_to_row[i] for i in g_ids], dtype=np.int32)
    A_g, _ = sm.build_accord_matrix(list(g_rows.accord_list))
    S_acc_g = A_g @ A_g.T
    B_g, w_g, _, _ = sm.build_note_matrix(list(g_rows.note_set), idf_map)
    Bw = B_g * w_g
    inter = Bw @ B_g.T
    rs = Bw.sum(axis=1)
    union = rs[:, None] + rs[None, :] - inter
    S_jac_g = np.zeros_like(inter)
    np.divide(inter, union, out=S_jac_g, where=union > 0)
    acc_dict = pd.read_csv(ACCORD_DICT)
    share = dict(zip(acc_dict.accord, acc_dict.perfume_share))
    note_sets_g = [set(s) for s in g_rows.note_set]
    rare_g = [{n for n, _ in lst if share.get(n, 1.0) < RARE_ACCORD_MAX_SHARE}
              for lst in g_rows.accord_list]

    gm_base, order_base, intop_base = global_metrics(
        0.5 * S_acc_g + 0.5 * S_jac_g, g_ids, index_of_g, ce_g, note_sets_g, rare_g)
    print()
    print(f"Global 1,000 baseline — top10 포함률 {gm_base['top10_hit']} "
          f"(기대 {BASELINE['global_top10_hit']}) · 공통 note>=1 "
          f"{gm_base['explain_shared_note_ge1']:.1%} · 공통 드문 accord>=1 "
          f"{gm_base['explain_shared_rare_accord_ge1']:.1%}")
    assert abs(gm_base["top10_hit"] - BASELINE["global_top10_hit"]) <= TOL, "Global 재현 실패"

    # ---- A8 격자 ----
    print()
    print("Step 3~5 — SVD 차원 x note 가중 x 음수 처리 = 8 조건")
    results = []
    embeddings = {}
    for k in SVD_DIMS:
        E, evr = note_embedding(P, k)
        embeddings[k] = E
        print(f"  SVD k={k} · 설명 분산 {evr:.3f}")
        np.savez_compressed(os.path.join(OUT_DIR, f"note_embedding_k{k}.npz"),
                            E=E.astype(np.float32), vocab=np.array(note_vocab, dtype=object))
        for weighting in NOTE_WEIGHTS:
            V = perfume_vectors(X_notes, E, idf_vec, weighting, "raw")
            for neg in NEG_MODES:
                label = f"A8 k={k} {weighting} {neg}"
                dev = evaluate_dev(X_acc_n, V, id_to_row, perfume_ids, relevant_by_query,
                                   development, label, neg_mode=neg)
                Vg = V[g_pos]
                S_note_g = Vg @ Vg.T
                if neg == "clip0":
                    S_note_g = np.clip(S_note_g, 0.0, None)
                gm, order_a8, intop_a8 = global_metrics(
                    0.5 * S_acc_g + 0.5 * S_note_g, g_ids, index_of_g, ce_g,
                    note_sets_g, rare_g)
                results.append({"variant": label, "svd_dim": k, "note_weighting": weighting,
                                "negative": neg, **dev, **gm,
                                "_order": order_a8, "_intop": intop_a8})
                print(f"  {'':46} top10 {gm['top10_hit']:.4f} · "
                      f"공통note {gm['explain_shared_note_ge1']:.1%} · "
                      f"드문accord {gm['explain_shared_rare_accord_ge1']:.1%}")

    # ---- 진단: PPMI 없이 count 만 (v4 16.3 — 최종 평가 경로로 쓰지 않는다) ----
    print()
    print("진단 — PPMI 없이 log1p(count) 로 SVD (최종 평가 경로 아님)")
    E_cnt, evr_cnt = note_embedding(np.log1p(C), 128)
    V_cnt = perfume_vectors(X_notes, E_cnt, idf_vec, "idf", "raw")
    dev_cnt = evaluate_dev(X_acc_n, V_cnt, id_to_row, perfume_ids, relevant_by_query,
                           development, "진단 count-only k=128 idf clip0", neg_mode="clip0")
    Vg = V_cnt[g_pos]
    gm_cnt, _, _ = global_metrics(0.5 * S_acc_g + 0.5 * np.clip(Vg @ Vg.T, 0, None),
                                  g_ids, index_of_g, ce_g, note_sets_g, rare_g)

    # ---- 최고 변형에서 가중 스윕 ----
    best = max(results, key=lambda r: (r["ndcg"], r["top10_hit"]))
    print()
    print(f"가중 스윕 — 최고 변형 {best['variant']} 에서 accord:note 비율만 변경")
    E = embeddings[best["svd_dim"]]
    Vb = perfume_vectors(X_notes, E, idf_vec, best["note_weighting"], "raw")
    sweep = []
    for aw in WEIGHT_SWEEP:
        dev = evaluate_dev(X_acc_n, Vb, id_to_row, perfume_ids, relevant_by_query, development,
                           f"  accord {aw:.1f} : note {1-aw:.1f}",
                           neg_mode=best["negative"], accord_weight=aw)
        sweep.append({"accord_weight": aw, **dev})

    # ---- rescue / regression ----
    cases = []
    b_pos = {int(v): i for i, v in enumerate(g_ids)}
    for q, got in best["_intop"].items():
        was = intop_base.get(q, set())
        for p in sorted(got - was):
            cases.append({"case_type": "rescue", "query_id": q, "partner_id": p,
                          "query": f"{g_rows.brand.iloc[b_pos[q]]} {g_rows['name'].iloc[b_pos[q]]}",
                          "partner": f"{g_rows.brand.iloc[b_pos[p]]} {g_rows['name'].iloc[b_pos[p]]}",
                          "shared_notes": len(note_sets_g[b_pos[q]] & note_sets_g[b_pos[p]]),
                          "shared_note_list": "|".join(sorted(
                              note_sets_g[b_pos[q]] & note_sets_g[b_pos[p]])[:6])})
        for p in sorted(was - got):
            cases.append({"case_type": "regression", "query_id": q, "partner_id": p,
                          "query": f"{g_rows.brand.iloc[b_pos[q]]} {g_rows['name'].iloc[b_pos[q]]}",
                          "partner": f"{g_rows.brand.iloc[b_pos[p]]} {g_rows['name'].iloc[b_pos[p]]}",
                          "shared_notes": len(note_sets_g[b_pos[q]] & note_sets_g[b_pos[p]]),
                          "shared_note_list": "|".join(sorted(
                              note_sets_g[b_pos[q]] & note_sets_g[b_pos[p]])[:6])})
    n_res = sum(1 for c in cases if c["case_type"] == "rescue")
    n_reg = len(cases) - n_res
    print()
    print(f"rescue {n_res}건 · regression {n_reg}건 (최고 변형 기준, Global 1,000 신뢰 간선)")

    # ---- 판정 ----
    print()
    print("=" * 78)
    print("KEEP 기준 판정")
    print("=" * 78)
    print(f"  {'변형':<26}{'ndcg@10':>10}{'>0.2709':>9}{'top10':>9}{'>=0.4464':>10}"
          f"{'대조군 대비':>12}  판정")
    verdicts = {}
    for r in sorted(results, key=lambda x: -x["ndcg"]):
        p1 = r["ndcg"] > BASELINE["dev700_ndcg"]
        p2 = r["top10_hit"] >= BASELINE["global_top10_hit"]
        vs_ctrl = r["top10_hit"] - BASELINE["control_note_cosine_top10_hit"]
        v = "KEEP" if (p1 and p2) else ("REVIEW" if (p1 or p2) else "DROP")
        verdicts[r["variant"]] = v
        print(f"  {r['variant']:<26}{r['ndcg']:>10.4f}{'통과' if p1 else '미달':>9}"
              f"{r['top10_hit']:>9.4f}{'통과' if p2 else '미달':>10}{vs_ctrl:>+12.4f}  {v}")

    # ---- 산출 ----
    clean = [{k: v for k, v in r.items() if not k.startswith("_")} for r in results]
    pd.DataFrame(clean).to_csv(os.path.join(OUT_DIR, "variants.csv"),
                               index=False, encoding="utf-8-sig")
    pd.DataFrame(sweep).to_csv(os.path.join(OUT_DIR, "weight_sweep.csv"),
                               index=False, encoding="utf-8-sig")
    pd.DataFrame(cases).to_csv(os.path.join(OUT_DIR, "cases.csv"),
                               index=False, encoding="utf-8-sig")
    pd.DataFrame(pairs + probe_rows).to_csv(os.path.join(OUT_DIR, "note_relations.csv"),
                                            index=False, encoding="utf-8-sig")

    metrics = {
        "baseline": {"dev700": base, "global1000": gm_base},
        "control_note_cosine_no_ppmi": {"dev700": control},
        "a8_variants": clean,
        "diagnostic_count_only": {"dev700": dev_cnt, "global1000": gm_cnt,
                                  "explained_variance": round(evr_cnt, 4),
                                  "note": "PPMI 없이 log1p(count). v4 16.3 대로 최종 평가 경로로 쓰지 않는다"},
        "weight_sweep": sweep,
        "verdicts": verdicts,
        "best_variant": best["variant"],
        "rescue_count": n_res, "regression_count": n_reg,
        "cooccurrence": {"vocab": len(note_vocab), "nonzero_cells": nz,
                         "ppmi_nonzero_cells": pnz, "ppmi_max": round(float(P.max()), 3)},
    }
    with open(os.path.join(OUT_DIR, "metrics.json"), "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=1)
        f.write("\n")

    manifest = {
        "experiment_id": "P1_A8_NOTE_COOCCURRENCE",
        "phase": 1, "status": "NEW",
        "hypothesis": ("note 문자열을 합치지 않고 note 사이 관계를 더하면, 이름이 달라도 "
                       "향 구조상 가까운 향수를 더 잘 찾는다"),
        "user_meaning": ("좋아하는 향수와 흔한 Musk/Amber 만 공유하는 향수가 아니라, "
                         "재료 이름이 달라도 실제로 비슷한 향수를 옆에 놓는다"),
        "changed_variable": "note 채널을 IDF-Jaccard 에서 PPMI+SVD 임베딩 코사인으로 교체",
        "population": ["dev700", "global1000"],
        "snapshot_hash": {"perfumes_csv": sha256(sm.PERFUMES_CSV),
                          "phase0_manifest": sha256(os.path.join(PHASE0, "manifest.json"))},
        "feature_version": "A8 PPMI+SVD",
        "projection": "해당 없음 (Phase 1 은 좌표를 만들지 않는다)",
        "parameters": {"svd_dims": list(SVD_DIMS), "note_weighting": list(NOTE_WEIGHTS),
                       "negative_handling": list(NEG_MODES), "seed": SEED,
                       "accord_weight": ACCORD_WEIGHT,
                       "cooccurrence": "X^T X, 대각선(문서빈도) 0 처리",
                       "ppmi": "log(p_ij/(p_i p_j)), 음수 0 절단"},
        "primary_metrics": ["dev700 ndcg@10", "global1000 top10_hit"],
        "guardrail_metrics": ["control_note_cosine_no_ppmi top10_hit = 0.4501"],
        "baseline_reference": BASELINE,
        "explainability_fixed_criteria": ("원본 note 문자열 공통 개수, 원본 accord 중 "
                                          f"보유율 < {RARE_ACCORD_MAX_SHARE} 인 것의 공통 개수. "
                                          "feature 가 무엇이든 이 기준은 바꾸지 않는다"),
        "holdout": "Dev 700 만 사용. Holdout 300 은 건드리지 않았다",
        "elapsed_sec": round(time.time() - t0, 1),
    }
    with open(os.path.join(OUT_DIR, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)
        f.write("\n")

    print()
    print(f"총 소요 {time.time()-t0:.0f}초")
    print(f"  -> {OUT_DIR}/ (metrics.json, manifest.json, variants.csv, weight_sweep.csv, "
          f"cases.csv, note_relations.csv, note_embedding_k*.npz)")


if __name__ == "__main__":
    main()

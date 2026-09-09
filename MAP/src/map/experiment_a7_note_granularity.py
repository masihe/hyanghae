"""A7 — note 집계 세밀도 곡선 (Phase 1, PRIORITY 2).

Run with venv/Scripts/python.exe src/map/experiment_a7_note_granularity.py

**왜 이 실험인가.** note 를 어느 정도까지 묶어야 의미를 얻으면서 향수 구분력은 잃지
않는가. 양 끝은 이미 측정됐다.

    2,523종 (현재)                    ndcg 0.2709 · top10 포함률 0.4464
    2,492종 (D21 동의어 통일 48건)     ndcg -0.0007 · 사실상 변화 없음
    ??? (중간 원료군)                  <- 이 구간이 미측정이다
    9종 (사용자 계열)                  top10 0.4464 -> 0.3114 · 구별되는 집합 997 -> 315

**입력 두 가지를 비교한다.** 플랜은 A7 이 A8 의 PPMI+SVD 임베딩으로 note 를 묶는다고
했다. 그런데 A8 실행 결과 **공동출현은 대체 가능성이 아니라 함께 쓰임을 잰다** 는 것이
드러났다 — Oud 와 Agarwood (Oud) 는 같은 재료의 다른 이름이라 동시출현 6회, PPMI 0.000 이다.
A7 의 전제는 "Lemon / Bergamot / Lime -> Citrus" 처럼 **대체 가능한 재료를 묶는 것**이므로
입력이 어긋난다. 그래서 두 입력을 모두 돌려 비교한다.

    cooc   A8 의 PPMI+SVD 임베딩 (k=128). 함께 쓰임 신호. 2,523종 전부 커버
    accord note -> accord 프로파일 p(accord|note). 대체 가능성 신호.
           772종만 커버하지만 그 note 가 전체 등장의 98.3% 다. 나머지는 단독 그룹

**IDF 를 다시 계산한다.** note 를 합치면 문서빈도가 달라진다. experiment_note_canonical.py
의 rebuild_idf 를 그대로 쓴다 (전체 코퍼스에서 다시 센다).

**고정 시험지.** 설명 가능성은 어떤 feature 를 쓰든 **원본 note 문자열과 원본 accord** 로만
잰다. 합친 그룹으로 재정의하면 A7 이 자동으로 100% 가 되어 자기 채점이 된다.

**판정 형식은 3종이다** (플랜 결정). 곡선 실험은 대부분의 점이 기준을 넘지 못하고
곡선 자체가 산출물이기 때문이다.

    KEEP                중간점 하나가 KEEP 기준(ndcg > 0.2709 AND top10 >= 0.4464)을 넘었다
    EXISTING_KNOWLEDGE  넘는 점이 없지만 곡선을 기록해 같은 질문의 재발을 막는다
    DROP                곡선 자체가 해석 불가

산출: experiments/P1_A7_NOTE_GRANULARITY/
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
import verify_similarity as vs
import experiment_note_canonical as enc

OUT_DIR = os.path.join("experiments", "P1_A7_NOTE_GRANULARITY")
A8_DIR = os.path.join("experiments", "P1_A8_NOTE_COOCCURRENCE")
PHASE0 = os.path.join("experiments", "phase0")
BRIDGE = os.path.join("..", "EDA", "analysis_outputs", "10_note_accord_bridge.csv")
ACCORD_DICT = os.path.join("..", "EDA", "analysis_outputs", "10_accord_dictionary.csv")

SEED = 42
GRANULARITIES = (100, 200, 300, 600)
INPUTS = ("accord", "cooc")
RARE_ACCORD_MAX_SHARE = 0.30
TOP_K = 10

BASELINE = {"dev700_ndcg": 0.2709, "dev700_recall": 0.3010, "global_top10_hit": 0.4464}
KNOWN_ENDPOINTS = {
    "2523_raw": {"vocab": 2523, "ndcg": 0.2709, "top10_hit": 0.4464,
                 "source": "현재 프로덕션"},
    "2492_synonym": {"vocab": 2492, "ndcg": 0.2702,
                     "source": "D21 실험2 — 동의어 48건 통일. ndcg -0.0007"},
    "9_families": {"vocab": 9, "top10_hit": 0.3114,
                   "source": "Phase 0 사전 점검 — 구별되는 note 집합 997 -> 315"},
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
# 군집 입력 두 가지
# --------------------------------------------------------------------------
def accord_profile_groups(note_vocab, k):
    """note -> accord 프로파일로 묶는다. 대체 가능성 신호.

    bridge 에 없는 note (전체 등장의 1.7%) 는 단독 그룹으로 둔다 —
    프로파일이 없는 note 를 억지로 어딘가에 넣지 않는다.
    """
    from sklearn.cluster import AgglomerativeClustering
    b = pd.read_csv(BRIDGE)
    accords = sorted(b.accord.unique())
    ai = {a: i for i, a in enumerate(accords)}
    covered = sorted(set(b.note) & set(note_vocab))
    P = np.zeros((len(covered), len(accords)))
    ci = {n: i for i, n in enumerate(covered)}
    for r in b.itertuples(index=False):
        if r.note in ci:
            P[ci[r.note], ai[r.accord]] = r.p_accord_given_note
    nrm = np.linalg.norm(P, axis=1, keepdims=True)
    nrm[nrm == 0] = 1.0
    Pn = P / nrm
    kk = min(k, len(covered))
    labels = AgglomerativeClustering(n_clusters=kk, metric="cosine",
                                     linkage="average").fit_predict(Pn)
    out = {n: f"G{labels[i]:04d}" for n, i in ci.items()}
    for n in note_vocab:                      # bridge 밖 note 는 단독 그룹
        out.setdefault(n, f"S_{n}")
    return out, {"covered": len(covered), "clusters": kk,
                 "singletons": len(note_vocab) - len(covered)}


def cooc_groups(note_vocab, k):
    """A8 의 PPMI+SVD 임베딩으로 묶는다. 함께 쓰임 신호 (플랜이 지정한 입력)."""
    from sklearn.cluster import KMeans
    path = os.path.join(A8_DIR, "note_embedding_k128.npz")
    assert os.path.exists(path), "A8 을 먼저 실행해 note_embedding_k128.npz 를 만들어야 한다"
    z = np.load(path, allow_pickle=True)
    E, vocab = z["E"], list(z["vocab"])
    assert vocab == list(note_vocab), "A8 의 어휘 순서와 다르다"
    labels = KMeans(n_clusters=k, random_state=SEED, n_init=4).fit_predict(E)
    return {n: f"G{labels[i]:04d}" for i, n in enumerate(vocab)}, \
           {"covered": len(vocab), "clusters": k, "singletons": 0}


# --------------------------------------------------------------------------
def remap(note_sets, mapping):
    return note_sets.map(lambda s: {mapping[n] for n in s if n in mapping})


def representation_stats(note_sets):
    frozen = [frozenset(s) for s in note_sets]
    return {"unique_representations": len(set(frozen)),
            "mean_set_size": round(float(np.mean([len(s) for s in frozen])), 2)}


def pair_stats(g_note_sets, idf_map):
    """Global 1,000 쌍에서 note 유사도가 0 인 비율과 1 인 비율."""
    B, w, _v, _m = sm.build_note_matrix(list(g_note_sets), idf_map)
    Bw = B * w
    inter = Bw @ B.T
    rs = Bw.sum(axis=1)
    union = rs[:, None] + rs[None, :] - inter
    S = np.zeros_like(inter)
    np.divide(inter, union, out=S, where=union > 0)
    iu = np.triu_indices(len(g_note_sets), 1)
    v = S[iu]
    return S, {"zero_pair_share": round(float((v == 0).mean()), 4),
               "identical_pair_share": round(float((v >= 0.999).mean()), 4),
               "median_sim": round(float(np.median(v)), 4)}


def global_eval(S_acc, S_note, ids, index_of, edges, note_sets_orig, rare_sets):
    """신뢰 파트너 top10 포함률 + 고정 시험지 설명 가능성."""
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
            sn.append(len(note_sets_orig[i] & note_sets_orig[j]))
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
    print("A7 — note 집계 세밀도 곡선. Phase 1 / PRIORITY 2")
    print("=" * 78)

    df, targets, idf_map, _S, _D, index_of_g, ce_g, _ae = bm.prepare(
        with_selection_comparison=False)
    id_to_row, perfume_ids, relevant_by_query, development, holdout = vs.build_eval_set(df)
    note_vocab = sorted({n for s in df["note_set"] for n in s})
    print(f"note 어휘 {len(note_vocab):,}종 · Holdout {len(holdout)} 질의는 건드리지 않는다")

    # Global 1,000 준비 (원본 note·accord 는 고정 시험지용)
    g = targets.reset_index(drop=True)
    g_ids = g.id.astype(int).tolist()
    A_g, _ = sm.build_accord_matrix(list(g.accord_list))
    S_acc_g = A_g @ A_g.T
    acc_dict = pd.read_csv(ACCORD_DICT)
    share = dict(zip(acc_dict.accord, acc_dict.perfume_share))
    note_orig = [set(s) for s in g.note_set]
    rare_g = [{n for n, _ in lst if share.get(n, 1.0) < RARE_ACCORD_MAX_SHARE}
              for lst in g.accord_list]

    # ---- 기준값 재현 ----
    print()
    print("기준값 재현")
    base_dev = enc.evaluate(df, df.note_set, idf_map, id_to_row, perfume_ids,
                            relevant_by_query, development, "baseline 2,523종")
    assert abs(base_dev["ndcg"] - BASELINE["dev700_ndcg"]) <= TOL, "baseline 재현 실패"
    S_note_base, ps_base = pair_stats(g.note_set, idf_map)
    base_glob = global_eval(S_acc_g, S_note_base, g_ids, index_of_g, ce_g, note_orig, rare_g)
    rep_base = representation_stats(df.note_set)
    print(f"  ndcg {base_dev['ndcg']} · top10 {base_glob['top10_hit']} "
          f"(기대 {BASELINE['global_top10_hit']}) · 구별되는 집합 "
          f"{rep_base['unique_representations']:,}/{len(df):,}")
    assert abs(base_glob["top10_hit"] - BASELINE["global_top10_hit"]) <= TOL, "Global 재현 실패"

    rows = [{"input": "-", "granularity": len(note_vocab), "vocab": len(note_vocab),
             **rep_base, **base_dev, **base_glob, **ps_base,
             "clusters": None, "singletons": 0, "label": "baseline 2,523종"}]

    # ---- 세밀도 곡선 ----
    group_maps = {}
    for inp in INPUTS:
        print()
        print(f"--- 입력 {inp} "
              f"({'note->accord 프로파일 · 대체 가능성' if inp == 'accord' else 'A8 PPMI+SVD · 함께 쓰임'}) ---")
        for k in GRANULARITIES:
            t = time.time()
            mapping, info = (accord_profile_groups(note_vocab, k) if inp == "accord"
                             else cooc_groups(note_vocab, k))
            merged = remap(df.note_set, mapping)
            vocab_after = len({x for s in merged for x in s})
            new_idf, n_changed = enc.rebuild_idf(merged, idf_map)
            label = f"{inp} k={k}"
            dev = enc.evaluate(df, merged, new_idf, id_to_row, perfume_ids,
                               relevant_by_query, development, label)
            g_merged = remap(g.note_set, mapping)
            S_note, ps = pair_stats(g_merged, new_idf)
            glob = global_eval(S_acc_g, S_note, g_ids, index_of_g, ce_g, note_orig, rare_g)
            rep = representation_stats(merged)
            rows.append({"input": inp, "granularity": k, "vocab": vocab_after,
                         **rep, **dev, **glob, **ps, "clusters": info["clusters"],
                         "singletons": info["singletons"], "label": label})
            group_maps[label] = mapping
            print(f"  {label:<14} 어휘 {vocab_after:>5,} · 구별집합 {rep['unique_representations']:>6,}"
                  f" · top10 {glob['top10_hit']:.4f} · note0쌍 {ps['zero_pair_share']:.1%}"
                  f" · 공통note {glob['explain_shared_note_ge1']:.1%} ({time.time()-t:.0f}s)")

    frame = pd.DataFrame(rows)
    frame.to_csv(os.path.join(OUT_DIR, "granularity_curve.csv"),
                 index=False, encoding="utf-8-sig")

    # ---- 곡선 출력 ----
    print()
    print("=" * 78)
    print("세밀도 곡선 — 어느 지점에서 구분력이 무너지는가")
    print("=" * 78)
    print(f"  {'조건':<16}{'어휘':>7}{'구별집합':>9}{'ndcg':>8}{'top10':>8}"
          f"{'note0쌍':>9}{'동일쌍':>8}{'공통note':>9}")
    for r in rows:
        print(f"  {r['label']:<16}{r['vocab']:>7,}{r['unique_representations']:>9,}"
              f"{r['ndcg']:>8.4f}{r['top10_hit']:>8.4f}{r['zero_pair_share']:>9.1%}"
              f"{r['identical_pair_share']:>8.1%}{r['explain_shared_note_ge1']:>9.1%}")
    print(f"  {'9계열 (사전점검)':<16}{9:>7}{315:>9}{'—':>8}{0.3114:>8.4f}{1.9:>8.1f}%"
          f"{0.8:>7.1f}%{'—':>9}")

    # ---- 판정 ----
    passing = [r for r in rows[1:] if r["ndcg"] > BASELINE["dev700_ndcg"]
               and r["top10_hit"] >= BASELINE["global_top10_hit"]]
    best = max(rows[1:], key=lambda r: (r["ndcg"], r["top10_hit"]))
    verdict = "KEEP" if passing else "EXISTING_KNOWLEDGE"
    print()
    print(f"판정: {verdict}")
    if passing:
        print(f"  기준을 넘은 지점 {len(passing)}개: "
              f"{[p['label'] for p in passing]}")
    else:
        print(f"  기준을 넘은 지점 없음. 최고는 {best['label']} "
              f"(ndcg {best['ndcg']} · top10 {best['top10_hit']})")
        print("  -> 곡선을 기록해 같은 질문의 재발을 막는다 (D21 선례)")

    # ---- 대표 그룹 예시 (사람 표본 검토용) ----
    samples = []
    ndict = pd.read_csv(os.path.join("..", "EDA", "analysis_outputs", "10_note_dictionary.csv"))
    freq = dict(zip(ndict.note, ndict.perfume_count))
    for label in (f"accord k=200", f"cooc k=200"):
        m = group_maps.get(label)
        if not m:
            continue
        groups = {}
        for n, gg in m.items():
            groups.setdefault(gg, []).append(n)
        big = sorted((v for k_, v in groups.items() if len(v) >= 3),
                     key=lambda v: -sum(freq.get(x, 0) for x in v))[:8]
        for members in big:
            top = sorted(members, key=lambda x: -freq.get(x, 0))[:8]
            samples.append({"input_label": label, "group_size": len(members),
                            "total_perfumes": sum(freq.get(x, 0) for x in members),
                            "members_top8": " | ".join(top)})
    pd.DataFrame(samples).to_csv(os.path.join(OUT_DIR, "group_samples.csv"),
                                 index=False, encoding="utf-8-sig")
    print()
    print("사람 표본 검토용 그룹 예시 (k=200, 보유 향수 합 상위)")
    for s in samples[:6]:
        print(f"  [{s['input_label']}] {s['group_size']}종 · "
              f"{s['members_top8'][:88]}")

    # ---- 산출 ----
    metrics = {
        "baseline": {"dev700": base_dev, "global1000": base_glob,
                     "representation": rep_base, "pair_stats": ps_base},
        "known_endpoints": KNOWN_ENDPOINTS,
        "curve": rows,
        "verdict": verdict,
        "best_point": {k: v for k, v in best.items()},
        "inputs": {
            "accord": ("note -> accord 프로파일 p(accord|note) 위 계층 군집(cosine·average). "
                       "대체 가능성 신호. bridge 가 note 772종(30.6%)만 덮지만 그 note 가 "
                       "전체 등장의 98.3% 다. 나머지 1,751종은 단독 그룹"),
            "cooc": ("A8 의 PPMI+SVD 임베딩(k=128) 위 KMeans. 함께 쓰임 신호. "
                     "플랜이 지정한 입력이지만 A8 진단에서 대체 가능성과 어긋난다는 것이 "
                     "드러났다 — 그 한계를 안고 함께 잰다"),
        },
        "limitation_from_a8": ("cooc 입력의 원천인 A8 은 KEEP 기준에 미달했다(DROP). "
                               "임베딩을 군집 도구로만 쓰며, cooc 결과는 '입력이 사람 판단 "
                               "기준을 통과하지 못했음' 을 한계로 안고 읽어야 한다"),
    }
    with open(os.path.join(OUT_DIR, "metrics.json"), "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=1)
        f.write("\n")

    manifest = {
        "experiment_id": "P1_A7_NOTE_GRANULARITY", "phase": 1, "status": "NEW",
        "hypothesis": ("note 를 중간 세밀도(100~300 그룹)로 묶으면 표층 문자열의 한계를 "
                       "넘으면서 향수 구분력은 유지할 수 있다"),
        "user_meaning": ("정확히 같은 재료가 아니어도 같은 향 계열의 재료를 쓴 향수가 "
                         "옆에 놓인다"),
        "changed_variable": "note 어휘의 집계 세밀도 (입력 2종 x 그룹 수 4종)",
        "population": ["dev700", "global1000"],
        "snapshot_hash": {"perfumes_csv": sha256(sm.PERFUMES_CSV),
                          "phase0_manifest": sha256(os.path.join(PHASE0, "manifest.json"))},
        "feature_version": "A7 note aggregation",
        "parameters": {"granularities": list(GRANULARITIES), "inputs": list(INPUTS),
                       "seed": SEED, "idf": "합친 뒤 전체 코퍼스에서 문서빈도 재계산"},
        "primary_metrics": ["dev700 ndcg@10", "global1000 top10_hit"],
        "explainability_fixed_criteria": ("원본 note 문자열과 원본 accord(보유율<0.30)로만 잰다. "
                                          "합친 그룹으로 재정의하지 않는다"),
        "verdict_scheme": ["KEEP", "EXISTING_KNOWLEDGE", "DROP"],
        "verdict": verdict,
        "holdout": "Dev 700 만 사용. Holdout 300 은 건드리지 않았다",
        "elapsed_sec": round(time.time() - t0, 1),
    }
    with open(os.path.join(OUT_DIR, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)
        f.write("\n")

    print()
    print(f"총 소요 {time.time()-t0:.0f}초")
    print(f"  -> {OUT_DIR}/ (metrics.json, manifest.json, granularity_curve.csv, "
          f"group_samples.csv)")


if __name__ == "__main__":
    main()

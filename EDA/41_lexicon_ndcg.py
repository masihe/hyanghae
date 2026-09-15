"""사전 버전만 바꿔 추천 품질을 비교한다 (lexicon-only 비교).

    ./venv/Scripts/python.exe 41_lexicon_ndcg.py <사전A.csv> <사전B.csv>

추천 엔진·향수 데이터·평가셋을 고정하고 **사전만** 바꾼다. 그래야 차이를 사전 변경에
귀속시킬 수 있다. 인자를 하나만 주면 그 사전의 점수만 낸다.

등급형 적합도 = 그 향수가 정답 조건 C 중 몇 개를 만족하는가 (0..|C|).
노트북 35 의 P@5 가 이미 같은 값을 쓰지만 순위를 보지 않는다. NDCG 는 순위까지 본다.

노트북 35 와 다른 점: 여기서는 조건(c1/c2/c3)·검색(hard/soft) 을 나누지 않고
엔진의 기본 동작(완화 사다리 포함)을 그대로 잰다. 두 수치를 직접 비교하지 않는다.

입력  analysis_outputs/32_evalset_answer_key.csv   정답 향수와 조건 C
      analysis_outputs/34_evalset_stage1_checkpoint.csv  저장된 LLM 구조화 결과 (API 호출 없음)
출력  없음. 표준출력에만 쓴다
"""
import sys, json, ast, pathlib
import numpy as np, pandas as pd

sys.path.insert(0, "C:/Users/SSAFY/Desktop/S15P21E203/ai")
from nlr_engine import load_index, recommend

TOP_K = 5


def load_queries():
    """평가셋 600건을 (문장, 구조화결과, 정답향수id) 로 읽는다. list[tuple]."""
    ck = pd.read_csv("analysis_outputs/34_evalset_stage1_checkpoint.csv")
    out = []
    for r in ck.to_dict("records"):
        raw, obj = r["parsed"], None
        if isinstance(raw, str) and raw.strip():
            try:
                obj = json.loads(raw)
            except Exception:
                try:
                    obj = ast.literal_eval(raw)
                except Exception:
                    obj = None
        out.append((r["sentence"], obj, r["perfume_id"]))
    return out


def ndcg_at_k(gains, ideal_gain, k=TOP_K):
    """등급형 적합도 목록으로 NDCG@k 를 낸다. float.

    gains      : list[int]  추천 순서대로의 조건 충족 개수
    ideal_gain : int        이 쿼리에서 가능한 최대 충족 개수 (= len(C))
    """
    dcg = sum((2 ** g - 1) / np.log2(i + 2) for i, g in enumerate(gains[:k]))
    idcg = sum((2 ** ideal_gain - 1) / np.log2(i + 2) for i in range(k))
    return dcg / idcg if idcg > 0 else 0.0


def score(lexicon_path, queries, key):
    """사전 하나로 평가셋을 채점한다. DataFrame."""
    index = load_index(lexicon_csv=lexicon_path)
    pid_to_row = {int(p): i for i, p in enumerate(index["pid"])}
    rows = []
    for text, conditions, answer_pid in queries:
        C = [a for a in str(key.loc[answer_pid, "C"]).split("|") if a in index["aidx"]]
        if not C:
            continue
        cols = [index["aidx"][a] for a in C]
        out = recommend(index, text, conditions)
        gains = [int(index["has"][pid_to_row[it["perfume_id"]], cols].sum())
                 for it in out["results"]]
        rows.append({
            "family": key.loc[answer_pid, "family"],
            "status": out["status"],
            "n_results": len(gains),
            "ndcg5": ndcg_at_k(gains, len(C)),
            "gain_ratio": float(np.mean(gains)) / len(C) if gains else 0.0,
        })
    return pd.DataFrame(rows)


def main():
    paths = sys.argv[1:]
    if not paths:
        raise SystemExit(__doc__)
    key = pd.read_csv("analysis_outputs/32_evalset_answer_key.csv").set_index("perfume_id")
    queries = load_queries()

    results = {}
    for p in paths:
        df = score(p, queries, key)
        results[p] = df
        print(f"{pathlib.Path(p).name:28s} 쿼리 {len(df)} · "
              f"NDCG@5 {df['ndcg5'].mean():.4f} · 조건충족률 {df['gain_ratio'].mean():.4f}")

    if len(paths) == 2:
        a, b = (results[p]["ndcg5"].mean() for p in paths)
        print(f"{'차이':28s} NDCG@5 {b - a:+.4f}")

    last = results[paths[-1]]
    print("\n향 계열별 NDCG@5 — 낮은 순")
    g = last.groupby("family").agg(쿼리=("ndcg5", "size"), NDCG5=("ndcg5", "mean"),
                                   조건충족률=("gain_ratio", "mean"))
    print(g.sort_values("NDCG5").to_string())


if __name__ == "__main__":
    main()

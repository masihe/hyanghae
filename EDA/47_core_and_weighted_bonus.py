"""core 는 AND 로 두고, 나머지 accord 는 가중 가점으로만 쓴다.

    ./venv/Scripts/python.exe 47_core_and_weighted_bonus.py

API 호출 0회. 사전과 엔진을 건드리지 않는다.

왜 다시 하는가
--------------
46번에서 "accord 를 늘리고 AND 를 버리고 IDF 가중 점수로" 를 재봤더니 **나빠졌다.**

    빨래     현재 1위 Laundry        -> 확장+가중 1위 Snow Palace (soapy 가 0 인 향수)
    휴양지   현재 coconut=100 짜리들  -> 확장+가중 marine·salty 가 올라옴, 겹침 0/5

원인 셋 중 가장 큰 것은 **AND 를 통째로 버린 것**이다. "반드시 있어야 하는 조건" 이
사라지자 조연 accord 들이 합쳐서 주연을 이겼다. N2 가 *"조합이어야 변별력이 생긴다"* 로
하드 AND 를 정한 이유가 이것이었다.

그래서 이번에는 나눈다
----------------------
    필수   사전의 core          AND 로 반드시 요구한다        후보를 정한다
    가점   optional + 확장       순위에만 기여한다             후보를 안 바꾼다

**이 구조는 사전에 이미 있다.** `required` 칸의 core/optional 이 그것이고,
`search_rules.md` 도 *"optional 은 점수용"* 이라고 적어 뒀다. 그런데 엔진이 안 쓴다.

    if row["required"] != "core": continue      # nlr_engine.py

두 가지 강도로 본다
-------------------
H1  동점일 때만 가점이 개입한다. 1순위는 지금 그대로 core strength 합
    N9 가 "동점은 평가자 수로 푼다" 로 둔 자리를 가점이 먼저 쓴다

H2  가점을 점수에 더한다. 가중치 합이 1 이라 가점 최대가 100 —
    core accord 하나 분량을 넘지 않는다

재는 것
-------
1. 표현별 상위 5 가 어떻게 달라지는가 (46번과 같은 표현들)
2. 합성 600문장 NDCG@5 · 조건충족률 — 전체가 좋아지는가 나빠지는가

출력 없음. 표준출력에만 쓴다.
"""
import importlib.util
import math
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "C:/Users/SSAFY/Desktop/S15P21E203/ai")
import nlr_engine  # noqa: E402

LIFT = "analysis_outputs/30_expression_accord_lift.csv"
ANSWER_KEY = "analysis_outputs/32_evalset_answer_key.csv"


def bonus_table(index):
    """표현마다 가점 accord 목록. dict[str, list[str]].

    사전의 optional + 배수가 지지하는 accord(신호 True · 순환 아님). core 는 뺀다.
    """
    lex = pd.read_csv(nlr_engine.DEFAULT_LEXICON, keep_default_na=False, dtype=str)
    usable = lex[(lex["candidate_type"] == "ACCORD") & (lex["target_field"] != "NO_MAPPING")]
    core = {e: set(g[g["required"] == "core"]["candidate_name"])
            for e, g in usable.groupby("expression")}
    optional = {e: set(g[g["required"] != "core"]["candidate_name"])
                for e, g in usable.groupby("expression")}

    lift = pd.read_csv(LIFT)
    supported = lift[(lift["신호"] == True) & (lift["순환"] != True)]  # noqa: E712

    out = {}
    for expr in core:
        extra = set(supported[supported["표현"] == expr]["accord"])
        pool = (optional.get(expr, set()) | extra) - core[expr]
        pool &= set(index["aidx"])
        if pool:
            out[expr] = sorted(pool)
    return out


def idf_weights(index, accords):
    """IDF 를 정규화해 비중으로. dict[str, float]. 합이 1 이다."""
    total = index["n_perfumes"]
    raw = {a: math.log(total / max(int(index["has"][:, index["aidx"][a]].sum()), 1))
           for a in accords}
    scale = sum(raw.values()) or 1.0
    return {a: v / scale for a, v in raw.items()}


def bonus_score(index, accords):
    """가점 점수. ndarray. 가중치 합이 1 이라 최대 100 이다."""
    score = np.zeros(index["n_perfumes"], dtype=np.float32)
    if not accords:
        return score
    for accord, weight in idf_weights(index, accords).items():
        score += weight * index["strength"][:, index["aidx"][accord]]
    return score


def pick(index, core, bonus_accords, mode, top_k=nlr_engine.TOP_K):
    """core 로 AND 를 걸고 가점을 mode 대로 반영해 상위를 고른다. (rows, 후보 수).

    mode  "현재" 지금 엔진 / "H1" 동점일 때만 / "H2" 점수에 더함
    """
    mask = index["people"] >= nlr_engine.PEOPLE_MIN
    for accord in core:
        mask = mask & index["has"][:, index["aidx"][accord]]
    cols = [index["aidx"][a] for a in core]
    base = index["strength"][:, cols].sum(axis=1)
    extra = bonus_score(index, bonus_accords)

    idx = np.flatnonzero(mask)
    if idx.size == 0:
        return [], 0
    if mode == "현재":
        keys = (index["pid"][idx], -index["people"][idx], -base[idx])
    elif mode == "H1":                       # 동점 -> 가점 -> 평가자 수
        keys = (index["pid"][idx], -index["people"][idx], -extra[idx], -base[idx])
    else:                                    # H2 점수에 더한다
        keys = (index["pid"][idx], -index["people"][idx], -(base + extra)[idx])
    idx = idx[np.lexsort(keys)]

    rows, seen = [], {}
    for row in idx:
        brand = index["brand"][row]
        if nlr_engine.BRAND_CAP and seen.get(brand, 0) >= nlr_engine.BRAND_CAP:
            continue
        seen[brand] = seen.get(brand, 0) + 1
        rows.append(int(row))
        if len(rows) >= top_k:
            break
    return rows, int(idx.size)


def show_expressions(index, bonus):
    """표현별로 세 방식의 상위 5 를 비교한다. None."""
    lex = pd.read_csv(nlr_engine.DEFAULT_LEXICON, keep_default_na=False, dtype=str)
    core_map = {e: sorted(set(g[g["required"] == "core"]["candidate_name"]) & set(index["aidx"]))
                for e, g in lex[(lex["candidate_type"] == "ACCORD")
                                & (lex["target_field"] != "NO_MAPPING")].groupby("expression")}

    print("[1] 표현별 상위 5\n")
    for expr in ("빨래", "휴양지", "깨끗한", "이불", "촉촉한", "비 오는 숲"):
        core, extra = core_map.get(expr, []), bonus.get(expr, [])
        if not core or not extra:
            continue
        weights = idf_weights(index, extra)
        print(f"[{expr}]  필수(AND) {core}")
        print("      가점  " + " · ".join(f"{a} {weights[a]:.0%}"
                                          for a in sorted(weights, key=lambda a: -weights[a])))
        base_ids = None
        for mode in ("현재", "H1", "H2"):
            rows, n = pick(index, core, extra, mode)
            ids = [int(index["pid"][r]) for r in rows]
            if mode == "현재":
                base_ids = set(ids)
            overlap = f"  겹침 {len(set(ids) & base_ids)}/5" if mode != "현재" else ""
            print(f"      {mode:4s} 후보 {n:>6,}{overlap}")
            for rank, row in enumerate(rows, 1):
                shown = " ".join(
                    f"{a}={int(index['strength'][row, index['aidx'][a]])}"
                    for a in core + extra
                    if index["strength"][row, index["aidx"][a]] > 0)
                print(f"         {rank}. {str(index['name'][row])[:28]:30s} "
                      f"{str(index['brand'][row])[:16]:18s} {shown[:62]}")
        print()


def measure_evalset(index, bonus):
    """합성 600문장으로 세 방식의 NDCG@5 와 조건충족률. None."""
    spec = importlib.util.spec_from_file_location("ndcg41", "41_lexicon_ndcg.py")
    ndcg41 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ndcg41)
    queries = ndcg41.load_queries()
    key = pd.read_csv(ANSWER_KEY).set_index("perfume_id")
    pid_to_row = {int(p): i for i, p in enumerate(index["pid"])}

    print("[2] 합성 600문장")
    for mode in ("현재", "H1", "H2"):
        scores, gains_all, used = [], [], 0
        for text, conditions, answer_pid in queries:
            C = [a for a in str(key.loc[answer_pid, "C"]).split("|") if a in index["aidx"]]
            if not C:
                continue
            understood = nlr_engine.understand(index, text, conditions)
            core = understood["core"]
            if not core:
                scores.append(0.0)
                continue
            extra = sorted({a for e in understood["matched_expressions"]
                            for a in bonus.get(e, [])} - set(core))
            used += bool(extra)
            rows, _ = pick(index, core, extra, mode)
            cols = [index["aidx"][a] for a in C]
            gains = [int(index["has"][r, cols].sum()) for r in rows]
            scores.append(ndcg41.ndcg_at_k(gains, len(C)))
            gains_all += [g / len(C) for g in gains]
        print(f"    {mode:4s} NDCG@5 {np.mean(scores):.4f}  "
              f"조건충족률 {np.mean(gains_all):.4f}  가점이 붙은 문장 {used}")
    print()


def main():
    """가점 표를 만들고 두 측정을 돌린다. None."""
    index = nlr_engine.load_index()
    bonus = bonus_table(index)
    print(f"향수 {index['n_perfumes']:,} · 가점 accord 가 있는 표현 {len(bonus)}개\n")
    show_expressions(index, bonus)
    measure_evalset(index, bonus)


if __name__ == "__main__":
    main()

"""Q2 — 사전 경유로 잡은 회피를 하드로 뺄지 소프트로 감점할지 세 방식으로 잰다.

    ./venv/Scripts/python.exe 58_avoid_hard_vs_soft.py

API 호출 0회. 팀 저장소를 수정하지 않는다.

왜 필요한가
------------
57번에서 Q1(회피도 사전을 경유한다)을 재봤더니 도달이 7 -> 12회로 늘었지만 NDCG 가
-0.000856 내려갔고, 이유가 문장에 그대로 보였다.

    "달콤한 과일 향을 좋아하는데 단순한 사탕 냄새는 싫어"   회피 ['candy']
       현재      조건 ['caramel','citrus','fruity','sweet']   후보   309
       core 경유  조건 ['citrus','fruity']                    후보 3,539
                        ^ 사용자가 좋다고 한 단맛이 통째로 지워졌다

`spec.md` §8 11번이 걱정했던 그대로다 — *"회피가 사전 항목 전체를 쓰면 `빨래` 의
`soapy` 까지 지워져 선호가 통째로 사라진다."*

그래서 Q2 는 선택이 아니라 필수 후속 결정이 됐다.

세 방식
--------
    A 현재            `_normalize_accord` 로 잡은 것만 하드 제외. 지금 프로덕션
    B 경유+하드        사전 경유분도 똑같이 하드 제외 (57번에서 잰 것)
    C 경유+소프트      직접 지목한 accord 는 하드, **사전 경유분은 점수에서 감점**
                     (참고 조사의 Q2 권고 — component 삭제 대신 concept 억제)

C 의 규칙 — 왜 이렇게 정했나
------------------------------
    1. `_normalize_accord` 가 잡은 것(사용자가 accord 이름을 직접 말함)은 하드 제외
       조사의 Q2 사례 1 — "카라멜 싫어" 는 확실한 지목이다
    2. 사전 경유분은 core 에서 **빼지 않는다.** 선호가 살아남는다
    3. 사전 경유분을 후보 필터에도 걸지 않는다
    4. 대신 점수에서 `람다 x (해당 accord strength 합)` 을 뺀다

위 예문에서 2·3 덕분에 `caramel`·`sweet` 조건이 살아 후보가 309 로 유지되고, 4 때문에
그 안에서 가장 단 향수가 뒤로 밀린다. "단 과일 향은 좋은데 사탕 같은 건 싫다" 에 가깝다.

람다는 1.0 이다 — strength 와 같은 척도로 1:1 뺀다. **조정 근거는 없다**(48번과 같은 값).

복제본 검증이 선행한다
-----------------------
소프트는 점수에 개입해야 해서 `search()` 를 복제할 수밖에 없다. 47번에서 복제하다 완화
사다리를 빠뜨려 NDCG 가 0.4406 으로 나왔고 41번의 0.4688 과 비교 불가가 된 전례가 있다.

그래서 **복제본이 600문장 전부에서 진짜 `nlr_engine.search()` 와 같은 행·같은 단계·같은
후보 수를 내는지 먼저 확인하고, 통과해야만 세 방식을 잰다.**

출력 없음. 표준출력에만 쓴다.
"""
import collections
import importlib.util
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "C:/Users/SSAFY/Desktop/S15P21E203/ai")
import nlr_engine  # noqa: E402

LEXICON = "data/scent_knowledge/domain_lexicon_v1_14.csv"
ANSWER_KEY = "analysis_outputs/32_evalset_answer_key.csv"
LAMBDA = 1.0   # [제안] 소프트 감점 계수. strength 와 같은 척도. 조정 근거 없음


# ---------------------------------------------------------------------------
# search() 복제 — soft 인자만 더했다. 나머지는 nlr_engine 과 한 줄씩 같아야 한다
# ---------------------------------------------------------------------------
def _rank(index, mask, score, top_k, brand_cap):
    """nlr_engine._rank 와 동일."""
    idx = np.flatnonzero(mask)
    if idx.size == 0:
        return {"rows": [], "candidate_count": 0, "tie_at_last": 0}
    order = np.lexsort((index["pid"][idx], -index["people"][idx], -score[idx]))
    idx = idx[order]
    sorted_score = score[idx]
    cut = min(top_k, len(idx)) - 1
    tie = int((sorted_score == sorted_score[cut]).sum())
    rows, seen = [], {}
    for row in idx:
        brand = index["brand"][row]
        if brand_cap and seen.get(brand, 0) >= brand_cap:
            continue
        seen[brand] = seen.get(brand, 0) + 1
        rows.append(int(row))
        if len(rows) >= top_k:
            break
    return {"rows": rows, "candidate_count": int(idx.size), "tie_at_last": tie}


def search_copy(index, core, avoid=(), soft=(), top_k=nlr_engine.TOP_K,
                people_min=nlr_engine.PEOPLE_MIN, brand_cap=nlr_engine.BRAND_CAP,
                min_results=nlr_engine.MIN_RESULTS):
    """nlr_engine.search 의 복제. `soft` 만 추가됐다.

    soft 가 비면 원본과 완전히 같은 결과를 내야 한다 — 그것을 아래에서 검증한다.
    """
    cols = [index["aidx"][a] for a in core if a in index["aidx"]]
    if not cols:
        return {"rows": [], "stage": "NO_CONDITION", "candidate_count": 0,
                "tie_at_last": 0, "relaxed": []}
    min_results = min(min_results, top_k)

    base = index["people"] >= people_min
    for accord in avoid:
        col = index["aidx"].get(accord)
        if col is not None:
            base &= ~index["has"][:, col]

    score = index["strength"][:, cols].sum(axis=1)
    soft_cols = [index["aidx"][a] for a in soft if a in index["aidx"]]
    if soft_cols:                                  # <- 원본에 없는 유일한 부분
        score = score - LAMBDA * index["strength"][:, soft_cols].sum(axis=1)

    if len(cols) == 1:
        mask = base & index["has"][:, cols[0]]
        picked = _rank(index, mask, score, top_k, brand_cap)
        if len(picked["rows"]) >= min_results:
            picked["stage"] = "SINGLE_BROAD"
            picked["relaxed"] = ["향 조건이 accord 하나뿐이라 순위를 정하지 못한다"]
            return picked

    if len(cols) >= nlr_engine.MIN_CORE_FOR_AND:
        mask = base.copy()
        for col in cols:
            mask &= index["has"][:, col]
        picked = _rank(index, mask, score, top_k, brand_cap)
        if len(picked["rows"]) >= min_results:
            picked["stage"] = "AND"
            picked["relaxed"] = []
            return picked

    mask = base & index["has"][:, cols].any(axis=1)
    picked = _rank(index, mask, score, top_k, brand_cap)
    if len(picked["rows"]) >= min_results:
        picked["stage"] = "RELAXED_OR"
        picked["relaxed"] = ["core accord 를 AND 에서 OR 로"]
        return picked

    mask = np.ones(index["n_perfumes"], dtype=bool)
    for accord in avoid:
        col = index["aidx"].get(accord)
        if col is not None:
            mask &= ~index["has"][:, col]
    mask &= index["has"][:, cols].any(axis=1)
    picked = _rank(index, mask, score, top_k, brand_cap)
    picked["stage"] = "RELAXED_OR_NO_THRESHOLD" if picked["rows"] else "NOT_ENOUGH"
    picked["relaxed"] = ["core accord 를 AND 에서 OR 로", "평가자 문턱 해제"]
    return picked


# ---------------------------------------------------------------------------
# 회피 해석
# ---------------------------------------------------------------------------
def resolve(index, structured, mode):
    """회피 문구를 (하드 집합, 소프트 집합) 으로. (set, set).

    A 현재       직접 지목만 하드
    B 경유+하드   직접 지목 + 사전 경유(core 행) 를 모두 하드
    C 경유+소프트  직접 지목은 하드, 사전 경유는 소프트
    """
    hard, soft = set(), set()
    for raw in ((structured or {}).get("avoid") or []):
        term = str(raw)
        exact = nlr_engine._normalize_accord(index, term)
        if exact:
            hard.add(exact)
            continue
        if mode == "A 현재":
            continue
        hit = set()
        for form, expressions in index["lexicon_surface"].items():
            if form and form in term:
                hit |= expressions
        routed = {row["candidate_name"]
                  for name in hit
                  for row in index["lexicon_by_expression"].get(name, [])
                  if row["required"] == "core"}
        (hard if mode == "B 경유+하드" else soft).update(routed)
    known = set(index["aidx"])
    return hard & known, soft & known


def run_one(index, text, structured, mode):
    """한 문장을 한 방식으로. dict."""
    understood = nlr_engine.understand(index, text, structured)
    hard, soft = resolve(index, structured, mode)
    # 하드는 core 에서도 뺀다(지금 엔진과 같다). 소프트는 core 에 남긴다 — 선호를 지우지 않는다.
    core = [a for a in understood["core"] if a not in hard]
    found = search_copy(index, core, hard, soft)

    if found["stage"] == "NO_CONDITION":
        status = "NO_CONDITION"
    elif not found["rows"]:
        status = "NO_RESULT"
    elif found["stage"] == "AND":
        status = "OK"
    else:
        status = "OK_RELAXED"
    return {"core": core, "hard": sorted(hard), "soft": sorted(soft),
            "rows": found["rows"], "stage": found["stage"], "status": status,
            "candidates": found["candidate_count"]}


# ---------------------------------------------------------------------------
def verify_copy(index, queries):
    """복제본이 진짜 search() 와 같은 결과를 내는지 600문장으로 확인한다. bool."""
    bad = 0
    for text, structured, _ in queries:
        understood = nlr_engine.understand(index, text, structured)
        hard, _ = resolve(index, structured, "A 현재")
        core = [a for a in understood["core"] if a not in hard]
        real = nlr_engine.search(index, core, hard)
        mine = search_copy(index, core, hard)
        if (real["rows"] != mine["rows"] or real["stage"] != mine["stage"]
                or real["candidate_count"] != mine["candidate_count"]):
            bad += 1
            if bad <= 3:
                print(f"    불일치 \"{text[:40]}\"")
                print(f"       진짜  {real['stage']} 후보 {real['candidate_count']} {real['rows']}")
                print(f"       복제  {mine['stage']} 후보 {mine['candidate_count']} {mine['rows']}")
    print(f"    600문장 중 불일치 {bad}건")
    return bad == 0


def main():
    index = nlr_engine.load_index(lexicon_csv=LEXICON)
    spec = importlib.util.spec_from_file_location("ndcg41", "41_lexicon_ndcg.py")
    ndcg41 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ndcg41)
    queries = ndcg41.load_queries()
    key = pd.read_csv(ANSWER_KEY).set_index("perfume_id")

    print(f"사전 {LEXICON} · 쿼리 {len(queries)}건\n")
    print("[0] 복제본 검증 — 진짜 nlr_engine.search() 와 같은가")
    if not verify_copy(index, queries):
        raise SystemExit("복제본이 원본을 재현하지 못한다 — 측정을 진행하지 않는다")
    print("    통과. 이 복제본으로 세 방식을 잰다\n")

    modes = ("A 현재", "B 경유+하드", "C 경유+소프트")
    out = {}
    for mode in modes:
        status_c, stage_c = collections.Counter(), collections.Counter()
        ndcgs, reach, terms, applied, cand = [], 0, 0, 0, []
        for text, structured, answer_pid in queries:
            tlist = [str(t) for t in ((structured or {}).get("avoid") or [])]
            terms += len(tlist)
            for t in tlist:
                h, s = resolve(index, {"avoid": [t]}, mode)
                if h or s:
                    reach += 1
            r = run_one(index, text, structured, mode)
            status_c[r["status"]] += 1
            stage_c[r["stage"]] += 1
            if r["hard"] or r["soft"]:
                applied += 1
                cand.append(r["candidates"])
            C = [a for a in str(key.loc[answer_pid, "C"]).split("|") if a in index["aidx"]]
            if not C:
                continue
            cols = [index["aidx"][a] for a in C]
            ndcgs.append(ndcg41.ndcg_at_k(
                [int(index["has"][i, cols].sum()) for i in r["rows"]], len(C)))
        out[mode] = {"ndcg": float(np.mean(ndcgs)), "status": status_c, "stage": stage_c,
                     "reach": reach, "terms": terms, "applied": applied,
                     "cand": float(np.median(cand)) if cand else float("nan")}

    print("[1] 세 방식 비교")
    head = f"    {'':16s}" + "".join(f"{m:>14s}" for m in modes)
    print(head)
    print("    " + "-" * (16 + 14 * 3))
    a = out[modes[0]]
    print(f"    {'회피 도달':16s}" + "".join(f"{out[m]['reach']:>10d}/{out[m]['terms']:<3d}" for m in modes))
    print(f"    {'회피 걸린 문장':16s}" + "".join(f"{out[m]['applied']:>14d}" for m in modes))
    print(f"    {'NDCG@5':16s}" + "".join(f"{out[m]['ndcg']:>14.6f}" for m in modes))
    print(f"    {'  vs A':16s}" + "".join(f"{out[m]['ndcg'] - a['ndcg']:>+14.6f}" for m in modes))
    print(f"    {'후보 수 중앙':16s}" + "".join(f"{out[m]['cand']:>14,.0f}" for m in modes))
    print()
    print("    status 분포")
    for k in ("OK", "OK_RELAXED", "NO_CONDITION", "NO_RESULT"):
        print(f"      {k:14s}" + "".join(f"{out[m]['status'][k]:>14d}" for m in modes))
    print()
    print("    검색 단계 분포")
    for k in sorted(set().union(*(out[m]["stage"] for m in modes))):
        print(f"      {k:22s}" + "".join(f"{out[m]['stage'][k]:>10d}" for m in modes))

    print("\n[2] 회피가 걸린 문장 — 세 방식이 어떻게 다른가")
    shown = 0
    for text, structured, _ in queries:
        if shown >= 6:
            break
        rs = {m: run_one(index, text, structured, m) for m in modes}
        if rs["A 현재"]["core"] == rs["C 경유+소프트"]["core"] and not rs["C 경유+소프트"]["soft"]:
            continue
        print(f"\n  \"{text[:56]}\"")
        print(f"     회피 문구 {[str(t) for t in ((structured or {}).get('avoid') or [])]}")
        for m in modes:
            r = rs[m]
            print(f"     {m:12s} 조건 {r['core']}")
            print(f"     {'':12s} 하드 {r['hard']} 소프트 {r['soft']} · {r['status']} · 후보 {r['candidates']:,}")
        shown += 1


if __name__ == "__main__":
    main()

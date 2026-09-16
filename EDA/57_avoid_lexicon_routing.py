"""Q1 결정(회피도 사전을 경유한다)을 구현해 600문장으로 잰다.

    ./venv/Scripts/python.exe 57_avoid_lexicon_routing.py

API 호출 0회. 팀 저장소를 수정하지 않는다 — 이 파일 안에서만 대안 동작을 흉내낸다.

무엇이 결정됐나
----------------
Q1 (`NLR_NEXT_SESSION.md` 3장): **회피도 사전을 태운다.** 2026-09-16 사용자 결정.

지금 엔진은 회피를 `_normalize_accord` 로만 푼다 — accord 영어 이름과 (거의) 완전히
같을 때만 닿는다. 사전 경유 경로가 프로덕션에 아예 없다(48번의 발견).

무엇을 재는가 — 두 방식
------------------------
    현재        `_normalize_accord` 만. 지금 프로덕션
    core 경유    거기에 **사전의 core 행**을 더한다. Q1 을 켠 것

**Q2(하드로 뺄지 소프트로 감점할지)는 아직 결정 안 났다.** 그래서 이번에는 지금 엔진과
같은 하드 필터 방식으로만 잰다. 그래야 `nlr_engine.search()` 를 그대로 써서 완화 사다리를
포함한 진짜 프로덕션 의미로 비교할 수 있다. 소프트를 섞으면 search 를 다시 구현해야 하고
숫자가 41번과 비교 불가능해진다(47·48번이 겪은 문제).

왜 `core` 만인가 — `optional` 은 오탐이 더 많았다
--------------------------------------------------
사전 v1.14 로 미리 재보니 이렇다.

    core 만        도달 고유  9/46 (20%)  출현 12/59 (20%)
    core+optional  도달 고유 16/46 (35%)  출현 19/59 (32%)

늘어난 7개 중 4개가 오탐이고 **전부 `흔한` 항목에서 나온다.**

    O  Too flashy           -> tuberose
    O  artificial/인공적인 향  -> sour
    O  복잡하게 변하는 향       -> whiskey
    X  ordinary citrus      -> aquatic · marine · salty
    X  평범한 과일 향          -> aquatic · marine · salty
    X  평범한 꽃향            -> aquatic · marine · salty
    X  흔한 디저트 향          -> aquatic · marine · salty

50번의 코퍼스 측정이 말한 것은 *"흔하다고 평가된 향수들이 aquatic·marine·salty 인
경향이 있다"* 이고, 이건 **어떤 향수가 흔하다고 불리는가** 에 대한 집단 성질이지
`흔한` 이라는 말의 구성적 의미가 아니다. 사용자가 `평범한 꽃향` 이라고 할 때 `평범한` 은
`꽃향` 을 수식하는 말이지 "바다 향을 빼달라" 가 아니다.

재는 항목 — NDCG 만으로는 부족하다
-----------------------------------
회피를 세게 걸면 후보가 사라져 결과가 0개가 되거나 완화 사다리를 탄다. 참고 조사도
No-result rate 를 핵심 guardrail 로 꼽았다.

    1. 회피 도달        회피 문구가 accord 로 해석된 비율
    2. status 분포      OK / OK_RELAXED / NO_CONDITION / NO_RESULT
    3. 검색 단계 분포    AND / SINGLE_BROAD / RELAXED_OR / ...
    4. NDCG@5          선호 경로를 깨뜨리지 않았는지 (정답 키에 회피가 없어 회피 품질은 못 잰다)
    5. 후보 수          회피가 후보 풀을 얼마나 줄이는가

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
MODES = ("현재", "core 경유")


def resolve_avoid(index, structured, mode):
    """회피 문구를 accord 집합으로. set[str].

    현재      `_normalize_accord` 만 — accord 이름과 (거의) 완전히 같을 때만
    core 경유  거기에 사전의 **core 행**을 더한다 (Q1)

    `optional` 은 넣지 않는다. docstring 의 오탐 측정 참고.
    """
    avoid = set()
    for raw in ((structured or {}).get("avoid") or []):
        term = str(raw)
        exact = nlr_engine._normalize_accord(index, term)
        if exact:
            avoid.add(exact)
            continue
        if mode == "현재":
            continue
        hit = set()
        for form, expressions in index["lexicon_surface"].items():
            if form and form in term:
                hit |= expressions
        avoid |= {row["candidate_name"]
                  for name in hit
                  for row in index["lexicon_by_expression"].get(name, [])
                  if row["required"] == "core"}
    return avoid & set(index["aidx"])


def run_one(index, text, structured, mode, top_k=nlr_engine.TOP_K):
    """한 문장을 한 방식으로 돌린다. dict.

    `nlr_engine.understand()` 를 그대로 쓰되 avoid 만 바꿔 끼운다. 검색은 진짜
    `nlr_engine.search()` 라 완화 사다리까지 프로덕션과 같다.
    """
    understood = nlr_engine.understand(index, text, structured)
    avoid = resolve_avoid(index, structured, mode)
    # understand() 는 `현재` 기준으로 이미 core 에서 avoid 를 뺐다. 경유로 늘어난 몫을 더 뺀다.
    core = [a for a in understood["core"] if a not in avoid]
    found = nlr_engine.search(index, core, avoid, top_k=top_k)

    if found["stage"] == "NO_CONDITION":
        status = "NO_CONDITION"
    elif not found["rows"]:
        status = "NO_RESULT"
    elif found["stage"] == "AND":
        status = "OK"
    else:
        status = "OK_RELAXED"
    return {"core": core, "avoid": sorted(avoid), "rows": found["rows"],
            "stage": found["stage"], "status": status,
            "candidates": found["candidate_count"]}


def main():
    index = nlr_engine.load_index(lexicon_csv=LEXICON)
    spec = importlib.util.spec_from_file_location("ndcg41", "41_lexicon_ndcg.py")
    ndcg41 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ndcg41)
    queries = ndcg41.load_queries()
    key = pd.read_csv(ANSWER_KEY).set_index("perfume_id")
    pid_to_row = {int(p): i for i, p in enumerate(index["pid"])}

    print(f"사전 {LEXICON} · 쿼리 {len(queries)}건\n")

    out = {}
    for mode in MODES:
        status_c, stage_c = collections.Counter(), collections.Counter()
        ndcgs, avoid_terms, avoid_hit, applied, cand = [], 0, 0, 0, []
        for text, structured, answer_pid in queries:
            terms = [str(t) for t in ((structured or {}).get("avoid") or [])]
            avoid_terms += len(terms)
            r = run_one(index, text, structured, mode)
            status_c[r["status"]] += 1
            stage_c[r["stage"]] += 1
            if r["avoid"]:
                applied += 1
                cand.append(r["candidates"])
            # 회피 문구 단위 도달 — 이 문장에서 몇 개가 accord 로 풀렸나
            for t in terms:
                if resolve_avoid(index, {"avoid": [t]}, mode):
                    avoid_hit += 1

            C = [a for a in str(key.loc[answer_pid, "C"]).split("|") if a in index["aidx"]]
            if not C:
                continue
            cols = [index["aidx"][a] for a in C]
            gains = [int(index["has"][r_, cols].sum()) for r_ in r["rows"]]
            ndcgs.append(ndcg41.ndcg_at_k(gains, len(C)))

        out[mode] = {
            "ndcg": float(np.mean(ndcgs)), "status": status_c, "stage": stage_c,
            "reach": avoid_hit, "terms": avoid_terms, "applied": applied,
            "cand_median": float(np.median(cand)) if cand else float("nan"),
        }

    base = out[MODES[0]]
    print(f"{'':14s} {'현재':>12s} {'core 경유':>12s}   차이")
    print("-" * 56)
    a, b = out[MODES[0]], out[MODES[1]]
    print(f"{'회피 도달':14s} {a['reach']:>8d}/{a['terms']:<3d} {b['reach']:>8d}/{b['terms']:<3d}"
          f"   {b['reach'] - a['reach']:+d}회")
    print(f"{'회피가 걸린 문장':14s} {a['applied']:>12d} {b['applied']:>12d}"
          f"   {b['applied'] - a['applied']:+d}건")
    print(f"{'NDCG@5':14s} {a['ndcg']:>12.6f} {b['ndcg']:>12.6f}"
          f"   {b['ndcg'] - a['ndcg']:+.6f}")
    print(f"{'후보 수 중앙':14s} {a['cand_median']:>12,.0f} {b['cand_median']:>12,.0f}")
    print()
    print("status 분포")
    for k in ("OK", "OK_RELAXED", "NO_CONDITION", "NO_RESULT"):
        print(f"    {k:14s} {a['status'][k]:>12d} {b['status'][k]:>12d}"
              f"   {b['status'][k] - a['status'][k]:+d}")
    print()
    print("검색 단계 분포")
    for k in sorted(set(a["stage"]) | set(b["stage"])):
        print(f"    {k:22s} {a['stage'][k]:>4d} {b['stage'][k]:>4d}"
              f"   {b['stage'][k] - a['stage'][k]:+d}")

    print("\n조건이 달라진 문장")
    shown = 0
    for text, structured, _ in queries:
        if shown >= 6:
            break
        ra = run_one(index, text, structured, MODES[0])
        rb = run_one(index, text, structured, MODES[1])
        if ra["avoid"] == rb["avoid"]:
            continue
        terms = [str(t) for t in ((structured or {}).get("avoid") or [])]
        print(f"\n  \"{text[:54]}\"")
        print(f"     회피 문구 {terms}")
        print(f"     현재      회피 {ra['avoid']} · 조건 {ra['core']} · {ra['status']}"
              f" · 후보 {ra['candidates']:,}")
        print(f"     core 경유  회피 {rb['avoid']} · 조건 {rb['core']} · {rb['status']}"
              f" · 후보 {rb['candidates']:,}")
        shown += 1


if __name__ == "__main__":
    main()

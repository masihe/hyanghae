"""회피 문구를 accord 로 옮기는 매칭 방식 셋을 비교한다.

    ./venv/Scripts/python.exe 45_avoid_matching_modes.py

API 호출 0회. 원본 사전과 엔진을 건드리지 않는다 — 매칭기는 이 파일 안에만 있다.

무엇을 정하려는가
-----------------
43번 측정에서 회피 문구 59개 중 accord 에 닿는 것이 8개(14%)였다. 44번 실험에서
사전 경로를 태우거나 `relation_type` 을 손봐도 이 숫자가 안 변한다는 것을 확인했다.

남은 몫이 여기다.

    14개  accord 이름이 문구 안에 들어 있다   "too sweet" · "cloying floral"
    37개  사전에도 accord 목록에도 없는 말     "too heavy" · "유치한"

앞의 14개는 **어휘를 늘리지 않고** 살릴 수 있다. 어떻게 매칭할지만 정하면 된다.

매칭 방식 셋
------------
M0 완전 일치   지금 엔진(`_normalize_accord`)이 하는 것. "sweet" 만 잡는다
M1 단순 포함   accord 이름이 문자열 안에 있으면 잡는다. 많이 잡지만 위험하다
M2 경계+최장   단어 경계에서만, 긴 이름부터 잡고 잡은 자리는 다시 안 본다

M1 이 위험한 이유 — accord 92개 중 4개가 다른 accord 이름을 품는다.

    white floral  <- floral      yellow floral <- floral
    tuberose      <- rose        fresh spicy   <- fresh

"white floral 빼줘" 를 단순 포함으로 처리하면 `floral` 까지 걸려 모든 꽃 향이 사라진다.

재는 것
-------
1. 방식별 도달 개수와 실제로 잡은 내용
2. 의도보다 넓게 잡는 경우          "sweet orange" -> sweet
3. 회귀 — 600문장 NDCG@5 가 유지되는가

출력 없음. 표준출력에만 쓴다.
"""
import collections
import importlib.util
import re
import sys

import pandas as pd

sys.path.insert(0, "C:/Users/SSAFY/Desktop/S15P21E203/ai")
import llm_stage1  # noqa: E402
import nlr_engine  # noqa: E402

CHECKPOINT = "analysis_outputs/34_evalset_stage1_checkpoint.csv"
ANSWER_KEY = "analysis_outputs/32_evalset_answer_key.csv"

# 강도를 나타내는 수식어. 이게 붙어도 가리키는 개념은 그대로다 — "too sweet" 은 sweet 이다.
MODIFIERS = {"too", "very", "so", "overly", "quite", "much", "only", "not",
             "ordinary", "cloying", "rough", "artificial", "strong", "heavy",
             "light", "sharp", "plain", "typical", "common", "like", "a", "an", "the"}


def normalize(text):
    """매칭용으로 문구를 다듬는다. str. 앞뒤에 공백을 둬 단어 경계를 만든다."""
    return " " + re.sub(r"[^a-z0-9가-힣]+", " ", str(text).lower()).strip() + " "


def match_exact(accords, term):
    """M0 — 지금 엔진이 하는 것. list[str]."""
    index = {a: a for a in accords}
    got = nlr_engine._normalize_accord({"aidx": index}, term)
    return [got] if got else []


def match_substring(accords, term):
    """M1 — 문자열 안에 있으면 잡는다. list[str]."""
    low = str(term).lower()
    return sorted(a for a in accords if a in low)


def match_boundary(accords, term):
    """M2 — 단어 경계에서만, 긴 이름부터. 잡은 자리는 소비한다. list[str]."""
    text = normalize(term)
    found = []
    for accord in sorted(accords, key=len, reverse=True):
        pattern = " " + accord + " "
        if pattern in text:
            found.append(accord)
            text = text.replace(pattern, " ")   # 소비. 안에 든 짧은 이름은 다시 안 본다
    return sorted(found)


def avoid_terms():
    """저장된 구조화 결과의 avoid 항목. list[str]."""
    check = pd.read_csv(CHECKPOINT)
    terms = []
    for row in check.to_dict("records"):
        try:
            conditions = llm_stage1.validate(llm_stage1.parse_content(row["raw_response"]))
        except llm_stage1.Stage1Error:
            continue
        terms += [str(t) for t in (conditions.get("avoid") or [])]
    return terms


# ---------------------------------------------------------------------------
# 1. 방식별 도달
# ---------------------------------------------------------------------------
def measure_reach(accords, terms):
    """세 방식이 각각 몇 개를 잡는지. dict[str, dict[str, list]]."""
    modes = {"M0 완전 일치": match_exact,
             "M1 단순 포함": match_substring,
             "M2 경계+최장": match_boundary}
    result = {name: {t: fn(accords, t) for t in terms} for name, fn in modes.items()}

    print(f"[1] 회피 문구 {len(terms)}개가 accord 에 닿는 비율")
    for name, hits in result.items():
        reached = sum(1 for v in hits.values() if v)
        print(f"    {name:14s} {reached:2d}/{len(terms)} ({reached/len(terms):4.0%})")
    print()

    base = result["M0 완전 일치"]
    print("    M0 는 못 잡는데 M2 가 잡는 것")
    for term in sorted({t for t in terms if not base[t] and result["M2 경계+최장"][t]}):
        print(f"      {term:28s} -> {result['M2 경계+최장'][term]}")
    print()
    print("    M1 은 잡는데 M2 는 못 잡는 것 — 단어 경계에서 갈린다")
    for term in sorted({t for t in terms
                        if result["M1 단순 포함"][t] and not result["M2 경계+최장"][t]}):
        print(f"      {term:28s} M1 {result['M1 단순 포함'][term]}")
    print()
    return result


# ---------------------------------------------------------------------------
# 2. 의도보다 넓게 잡는 경우
# ---------------------------------------------------------------------------
def measure_overreach(terms, result):
    """잡은 accord 말고 다른 내용어가 남는 문구를 센다. None.

    "too sweet" 의 `too` 는 강도 수식어라 개념이 그대로다.
    "sweet orange" 의 `orange` 는 다른 개념을 가리키는 머리말이다.
    수식어 목록은 사람이 만든 것이라 **판정이 아니라 검토 후보**다.
    """
    print("[2] 의도보다 넓게 잡을 가능성 — 사람이 봐야 하는 것")
    flagged = []
    for term in sorted(set(terms)):
        hits = result["M2 경계+최장"][term]
        if not hits:
            continue
        rest = [w for w in normalize(term).split()
                if w not in MODIFIERS and not any(w in a.split() for a in hits)]
        if rest:
            flagged.append((term, hits, rest))
    if not flagged:
        print("    없음")
    for term, hits, rest in flagged:
        print(f"      {term:28s} -> {hits}   남은 말 {rest}")
    print()


# ---------------------------------------------------------------------------
# 3. 회귀 — 매칭을 넓혀도 추천이 안 깨지는가
# ---------------------------------------------------------------------------
def measure_regression(accords):
    """M0 와 M2 로 회피를 풀었을 때 600문장 NDCG@5 를 비교한다. None."""
    spec = importlib.util.spec_from_file_location("ndcg41", "41_lexicon_ndcg.py")
    ndcg41 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ndcg41)

    queries = ndcg41.load_queries()
    key = pd.read_csv(ANSWER_KEY).set_index("perfume_id")
    index = nlr_engine.load_index()
    pid_to_row = {int(p): i for i, p in enumerate(index["pid"])}

    print("[3] 회귀 — 회피를 더 많이 잡으면 추천이 깨지는가")
    for name, matcher in (("M0 완전 일치", match_exact), ("M2 경계+최장", match_boundary)):
        scores, stages, changed = [], collections.Counter(), 0
        for text, conditions, answer_pid in queries:
            C = [a for a in str(key.loc[answer_pid, "C"]).split("|") if a in index["aidx"]]
            if not C:
                continue
            # 회피를 이 매칭기로 다시 풀어 conditions 에 accord 이름으로 돌려 넣는다
            patched = dict(conditions or {})
            raw_avoid = [str(t) for t in (patched.get("avoid") or [])]
            resolved = sorted({a for t in raw_avoid for a in matcher(accords, t)})
            if resolved != sorted({a for t in raw_avoid
                                   for a in match_exact(accords, t)}):
                changed += 1
            patched["avoid"] = resolved
            out = nlr_engine.recommend(index, text, patched if conditions else None)
            stages[out["diagnostics"]["stage"]] += 1
            cols = [index["aidx"][a] for a in C]
            gains = [int(index["has"][pid_to_row[it["perfume_id"]], cols].sum())
                     for it in out["results"]]
            scores.append(ndcg41.ndcg_at_k(gains, len(C)))
        dist = " · ".join(f"{k} {v}" for k, v in sorted(stages.items()))
        print(f"    {name:14s} NDCG@5 {sum(scores)/len(scores):.4f}  "
              f"회피가 달라진 문장 {changed:2d}   {dist}")
    print()


def main():
    """세 측정을 차례로 돌린다. None."""
    accords = sorted(nlr_engine.load_index()["aidx"])
    terms = avoid_terms()
    print(f"accord {len(accords)}개 · 회피 문구 {len(terms)}개 "
          f"(고유 {len(set(terms))}개)")
    print()
    result = measure_reach(accords, terms)
    measure_overreach(terms, result)
    measure_regression(accords)


if __name__ == "__main__":
    main()

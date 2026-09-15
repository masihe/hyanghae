"""회피(avoid) 처리 규칙을 정하기 전에 지금 무슨 일이 일어나는지 센다.

    ./venv/Scripts/python.exe 43_avoid_rule_measurement.py

API 호출 0회. 저장된 LLM 구조화 결과 600건을 재사용한다.

왜 재는가
---------
`spec.md` §3 ②-d 주석과 §8 11번이 회피 규칙을 **미결**로 남겨 뒀다.

    "회피가 사전 항목 전체를 쓰면 `빨래`의 `soapy`까지 지워져 선호가 통째로
     사라진다. 위 예시는 회피가 이름 동일성만 쓴다고 **가정했다**."

254 가 머지되면서 ①단계 구조화가 붙었고, `avoid` 에 처음으로 값이 들어온다.
가정을 결정으로 바꿔야 하는데 후보 규칙들의 대가가 서로 다른 종류라 말로는 못 고른다.

향은 조합으로 인상이 정해진다 — 이것이 규칙 선택을 가른다
---------------------------------------------------------
`DECISIONS.md` N2 가 "한 표현은 accord 2개 이상. 단독 매핑을 금지한다" 로 정한 이유다.
조합을 깨면 "빼기" 가 아니라 **다른 검색**이 된다.

    ['soapy','fresh']    후보    518   5위 동점     1     <- 빨래
    ['fresh']            후보 18,334   5위 동점   406
    ['powdery','soapy']  후보    265   5위 동점     1     <- 이불
    ['powdery']          후보 34,357   5위 동점 2,236

재는 것 셋
----------
1. avoid 에 들어온 말이 accord 로 해석되는가        회피가 실제로 도는 비율
2. 부정으로 말한 표현이 긍정 조건으로 잡히는가        빼달라는 말이 조건이 되는가
3. 세 규칙의 결과 비교                             현재 · 표현 단위 · 근거 단위

세 규칙
-------
현재       core - avoid.  accord 이름 단위로만 뺀다
표현 단위   회피 accord 를 데려온 표현의 core accord 를 전부 뺀다
근거 단위   회피되지 않은 표현이 하나라도 요구한 accord 는 살린다

출력 없음. 표준출력에만 쓴다.
"""
import collections
import re
import sys

import pandas as pd

sys.path.insert(0, "C:/Users/SSAFY/Desktop/S15P21E203/ai")
import llm_stage1  # noqa: E402
import nlr_engine  # noqa: E402

CHECKPOINT = "analysis_outputs/34_evalset_stage1_checkpoint.csv"
HANGUL = re.compile(r"[가-힣]")


def load_structured():
    """저장된 ①단계 구조화 결과를 읽는다. list[tuple[str, dict]]."""
    check = pd.read_csv(CHECKPOINT)
    out = []
    for row in check.to_dict("records"):
        try:
            out.append((row["sentence"],
                        llm_stage1.validate(llm_stage1.parse_content(row["raw_response"]))))
        except llm_stage1.Stage1Error:
            continue
    return out


# ---------------------------------------------------------------------------
# 측정 1 — avoid 에 들어온 말이 accord 로 해석되는가
# ---------------------------------------------------------------------------
def measure_normalization(index, rows):
    """avoid 항목이 accord 로 해석되는 비율. dict."""
    terms = [(str(t), c) for _, c in rows for t in (c.get("avoid") or [])]
    resolved = [(t, nlr_engine._normalize_accord(index, t)) for t, _ in terms]

    ignored = [t for t, a in resolved if a is None]
    korean = [t for t, _ in resolved if HANGUL.search(t)]

    print("[1] avoid 에 들어온 말이 accord 로 해석되는가")
    print(f"    avoid 가 비어 있지 않은 문장  {sum(1 for _, c in rows if c.get('avoid'))}/{len(rows)}")
    print(f"    avoid 항목                  {len(terms)}개")
    print(f"      accord 로 해석됨           {len(terms) - len(ignored)}개")
    print(f"      무시됨                     {len(ignored)}개 ({len(ignored)/len(terms):.0%})")
    print(f"    그중 한국어                  {len(korean)}개 "
          f"(해석된 것 {sum(1 for t, a in resolved if a and HANGUL.search(t))}개)")
    print()
    print("    무시된 말이 어떻게 생겼나 — 수식어가 붙은 구가 대부분이다")
    for term in sorted(set(ignored))[:12]:
        print(f"      {term}")
    print()
    return {t for t, a in resolved if a is None}


# ---------------------------------------------------------------------------
# 측정 2 — 부정으로 말한 표현이 긍정 조건으로 잡히는가
# ---------------------------------------------------------------------------
def measure_polarity_leak(index, rows):
    """회피 문구 안의 말이 사전에 core 로 잡히는 문장을 센다. None."""
    leaked = []
    for text, conditions in rows:
        if not conditions.get("avoid"):
            continue
        avoid_text = " ".join(str(t) for t in conditions["avoid"])
        hit = set()
        for form, expressions in index["lexicon_surface"].items():
            if form and form in avoid_text:
                hit |= expressions
        if not hit:
            continue
        core = nlr_engine.understand(index, text, conditions)["core"]
        wanted = {row["candidate_name"]
                  for name in hit
                  for row in index["lexicon_by_expression"].get(name, [])
                  if row["required"] == "core"} & set(core)
        if wanted:
            leaked.append((text, conditions["avoid"], sorted(hit), sorted(wanted)))

    print("[2] 부정으로 말한 표현이 긍정 조건으로 잡히는가")
    print(f"    회피 문구가 사전 표현을 품고, 그 accord 가 조건에 남은 문장  {len(leaked)}건")
    for text, avoid, hit, wanted in leaked[:6]:
        print(f"      '{text[:40]}'")
        print(f"         avoid={avoid}  사전이 잡은 표현={hit}  조건에 남음={wanted}")
    print()


# ---------------------------------------------------------------------------
# 측정 3 — 세 규칙 비교
# ---------------------------------------------------------------------------
def apply_rules(index, text, conditions):
    """세 규칙의 core 를 각각 낸다. dict[str, list].

    현재      core - avoid
    표현 단위  회피 accord 를 데려온 표현의 core accord 를 전부 뺀다
    근거 단위  회피되지 않은 표현이 하나라도 요구한 accord 는 살린다
    """
    understood = nlr_engine.understand(index, text, conditions)
    avoided = set(understood["avoid"])
    evidence = understood["evidence"]

    # 회피된 accord 를 데려온 표현
    avoided_exprs = {e["from"] for e in evidence
                     if e["accord"] in avoided and e.get("from")}

    by_accord = collections.defaultdict(set)
    for e in evidence:
        if e.get("from"):
            by_accord[e["accord"]].add(e["from"])

    current = set(understood["core"])
    by_expression = {a for a in current if not (by_accord[a] & avoided_exprs)}
    by_evidence = {a for a in current if by_accord[a] - avoided_exprs}
    return {"현재": sorted(current),
            "표현 단위": sorted(by_expression),
            "근거 단위": sorted(by_evidence),
            "avoided_exprs": sorted(avoided_exprs),
            "by_accord": by_accord}


def measure_rules(index, rows):
    """규칙별로 조건과 검색 결과가 어떻게 달라지는지 센다. None."""
    stats = collections.Counter()
    changed = []
    for text, conditions in rows:
        out = apply_rules(index, text, conditions)
        if not out["avoided_exprs"]:
            continue
        stats["회피가 실제로 도는 문장"] += 1

        current, expr, evid = out["현재"], out["표현 단위"], out["근거 단위"]
        if expr != current:
            stats["표현 단위 — 조건이 줄어듦"] += 1
        if not expr:
            stats["표현 단위 — 조건이 0이 됨"] += 1
        if len(current) >= 2 and len(expr) < 2:
            stats["표현 단위 — 조합이 깨져 단독이 됨"] += 1
        if evid != current:
            stats["근거 단위 — 조건이 줄어듦"] += 1
        if not evid:
            stats["근거 단위 — 조건이 0이 됨"] += 1
        if len(current) >= 2 and len(evid) < 2:
            stats["근거 단위 — 조합이 깨져 단독이 됨"] += 1

        # 뺀 말이 근거로 남는가 (현재 규칙)
        leftover = [(e["from"], e["accord"]) for e in
                    nlr_engine.understand(index, text, conditions)["evidence"]
                    if e["accord"] in current and e.get("from") in out["avoided_exprs"]]
        if leftover:
            stats["현재 — 뺀 말이 근거로 남음"] += 1
        if current != expr or current != evid:
            changed.append((text, out, leftover))

    print("[3] 세 규칙 비교")
    for key, value in stats.most_common():
        print(f"    {key:34s} {value:3d}건")
    print()
    print("    달라지는 문장")
    for text, out, leftover in changed[:8]:
        print(f"      '{text[:44]}'")
        print(f"         회피된 표현 {out['avoided_exprs']}")
        print(f"         현재 {out['현재']}")
        print(f"         표현 단위 {out['표현 단위']}   근거 단위 {out['근거 단위']}")
        if leftover:
            print(f"         뺀 말이 근거로 남음 {leftover}")
    print()


def main():
    """세 측정을 차례로 돌린다. None."""
    index = nlr_engine.load_index()
    rows = load_structured()
    print(f"저장된 구조화 결과 {len(rows)}건 · 사전 {nlr_engine.DEFAULT_LEXICON.name}")
    print()
    measure_normalization(index, rows)
    measure_polarity_leak(index, rows)
    measure_rules(index, rows)


if __name__ == "__main__":
    main()

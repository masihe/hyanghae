"""실사용 설문 155건에서 ①단계 LLM 과 ②단계(사전·분석기)를 비교한다.

    ./venv/Scripts/python.exe 66_survey_holdout.py

API 호출 0회. `37_survey_stage1_checkpoint.csv` 에 ①단계 출력이 저장돼 있다.

왜 재는가
----------
65번이 합성 600문장에서 `① LLM 단독 0.3985 > ② 분석기+사전 단독 0.3286` 을 냈는데,
**그 평가셋은 정답 accord 집합에서 생성된 문장이라 LLM 에 유리한 구조다.**
LLM 이 `scent_preference` 에 영어 accord 이름을 뱉으면 생성 과정을 역으로 밟는 셈이다.

설문 155건은 진짜 일반인 응답이고 성격이 다르다(측정 기록 §7).

    평균 길이       합성 30자   설문 71자
    p90            42자        145자
    최대           58자        600자
    조건 수 평균     1.3개       2.7개
    향수 전문 용어    5.5%       18.1%

**무엇을 못 재는지 먼저 밝힌다 — 155건에 정답 라벨이 없다.**

    잴 수 있다   조건 추출률 · 평균 조건 · status 분포 · 회피 도달 · 미매칭
                 LLM 이 뽑은 조건을 ②가 얼마나 재현하는가
    잴 수 없다   NDCG@5 · 조건 충족률

그래서 "어느 쪽이 정확한가" 는 여전히 못 답한다. "어느 쪽이 실사용 문장에서 작동하는가"
까지만 답한다.

LLM 출력을 기준선으로 쓰는 것에 대하여
----------------------------------------
[3] 은 LLM 이 낸 조건을 기준으로 ②의 재현율을 잰다. **LLM 이 옳다고 가정하는 것이 아니다.**
"②가 ①의 일을 대신할 수 있는가" 를 보는 것이고, 재현율이 낮으면 대체가 불가능하다는 뜻이
된다. 재현율이 높아도 둘 다 틀렸을 수 있다 — 그건 이 측정이 답하지 못한다.

출력 없음. 표준출력에만 쓴다.
"""
import collections
import json
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "C:/Users/SSAFY/Desktop/S15P21E203/ai")
import nlr_engine  # noqa: E402

SURVEY = "analysis_outputs/37_survey_stage1_checkpoint.csv"
SYNTH = "analysis_outputs/34_evalset_stage1_checkpoint.csv"
LEXICON = "data/scent_knowledge/domain_lexicon_v1_14.csv"

CONTENT = {"NNG", "NNP", "NNB", "VA", "VV", "XR", "MAG", "SL", "SN", "SH"}


def _norm(form, tag):
    f = form.lower()
    base = tag.split("+")[0].split("-")[0]
    if base in {"VA", "VV"} and len(f) > 1 and f.endswith("하"):
        f = f[:-1]
    return f, base


class MecabKey:
    name = "mecab"

    def __init__(self):
        import mecab
        self.m = mecab.MeCab()
        self.m.parse("적재 확인")

    def __call__(self, text):
        out = []
        for w in self.m.parse(text):
            expr = getattr(w.feature, "expression", None)
            if expr:
                for part in expr.split("+"):
                    bits = part.split("/")
                    if len(bits) >= 2:
                        f, base = _norm(bits[0], bits[1])
                        if base in CONTENT:
                            out.append(f)
            else:
                f, base = _norm(w.surface, w.feature.pos)
                if base in CONTENT:
                    out.append(f)
        return tuple(out)


def build_keys(keyfn, lexicon_csv):
    lex = pd.read_csv(lexicon_csv, keep_default_na=False, dtype=str)
    keys = {}
    for row in lex.to_dict("records"):
        for f in [row["expression"]] + [a for a in row["aliases"].split("|") if a]:
            k = keyfn(f)
            if k:
                keys.setdefault(k, set()).add(row["expression"])
    return keys


def contains(hay, needle):
    n, m = len(hay), len(needle)
    return m > 0 and m <= n and any(hay[i:i + m] == needle for i in range(n - m + 1))


def lemma_core(index, keys, keyfn, haystack):
    hay = keyfn(haystack)
    hit = set()
    for k, expressions in keys.items():
        if contains(hay, k):
            hit |= expressions
    core = set()
    for expression in hit:
        for row in index["lexicon_by_expression"].get(expression, []):
            cond = row["match_condition"]
            if cond.startswith("query_contains:"):
                toks = [t for t in cond.split(":", 1)[1].split(",") if t]
                if not any(t in haystack for t in toks):
                    continue
            if row["required"] == "core" and row["candidate_name"] in index["aidx"]:
                core.add(row["candidate_name"])
    for ko, accord in nlr_engine.KOREAN_ACCORD.items():
        if ko in haystack and accord in index["aidx"]:
            core.add(accord)
    return core


def status_of(found):
    if found["stage"] == "NO_CONDITION":
        return "NO_CONDITION"
    if not len(found["rows"]):
        return "NO_RESULT"
    if found["stage"] == "AND":
        return "OK"
    return "OK_RELAXED"


def load_survey():
    """(문장, ①단계 dict, 지연초) 목록. list[tuple]."""
    d = pd.read_csv(SURVEY)
    out = []
    for r in d.to_dict("records"):
        try:
            o = json.loads(r["raw_response"])
        except Exception:
            o = None
        lat = r.get("latency_seconds")
        out.append((str(r["query_text"]), o if isinstance(o, dict) else None,
                    float(lat) if pd.notna(lat) else None))
    return out


def main():
    index = nlr_engine.load_index(lexicon_csv=LEXICON)
    mecab = MecabKey()
    keys = build_keys(mecab, LEXICON)
    rows = load_survey()
    n = len(rows)
    parsed = sum(1 for _, o, _ in rows if o)

    lens = [len(t) for t, _, _ in rows]
    synth_lens = [len(str(s)) for s in pd.read_csv(SYNTH)["sentence"]]
    print(f"설문 {n}건 · ①단계 파싱 성공 {parsed}건 · 사전 {LEXICON}")
    print(f"길이  설문 평균 {np.mean(lens):.0f}자 · 중앙 {np.median(lens):.0f} · 최대 {max(lens)}")
    print(f"      합성 평균 {np.mean(synth_lens):.0f}자 · 중앙 {np.median(synth_lens):.0f} "
          f"· 최대 {max(synth_lens)}")
    print("**정답 라벨이 없다. NDCG 는 못 잰다.**\n")

    def run(stage1, stage2):
        ncond, nonzero, avoid_hit, unmatched = [], 0, 0, 0
        statuses = collections.Counter()
        cores = []
        for text, o, _ in rows:
            parts = [text]
            if o and stage1 in ("add", "all"):
                parts += [str(v) for v in (o.get("additional_requirements") or [])]
            hay = " ".join(parts)
            if stage2 == "none":
                core = set()
            elif stage2 == "sub":
                core = nlr_engine._extract(index, hay)[0]
            else:
                core = lemma_core(index, keys, mecab, hay)
            if o and stage1 in ("pref", "all"):
                for raw in (o.get("scent_preference") or []):
                    a = nlr_engine._normalize_accord(index, raw)
                    if a:
                        core.add(a)
            avoid = set()
            if o and stage1 == "all":
                for raw in (o.get("avoid") or []):
                    a = nlr_engine._normalize_accord(index, raw)
                    if a:
                        avoid.add(a)
            avoid_hit += bool(avoid)
            if o:
                unmatched += len(nlr_engine.understand(index, text, o)["unmatched"])
            core = set(core) - avoid
            cores.append(core)
            ncond.append(len(core))
            nonzero += bool(core)
            statuses[status_of(nlr_engine.search(index, sorted(core), avoid))] += 1
        return {"nonzero": nonzero, "cond": float(np.mean(ncond)), "status": statuses,
                "avoid": avoid_hit, "cores": cores, "unmatched": unmatched}

    LABEL1 = {"none": "① 없음", "add": "① add 만", "pref": "① pref 만", "all": "① 전부"}
    LABEL2 = {"none": "② 없음", "sub": "② 부분문자열", "mecab": "② mecab"}

    table = {}
    for s2 in ("none", "sub", "mecab"):
        for s1 in ("none", "add", "pref", "all"):
            table[(s1, s2)] = run(s1, s2)

    print("=" * 92)
    print("[1] 실사용 설문 155건 — 12개 조합")
    print("=" * 92)
    print(f"    {'①단계':12s} {'②단계':14s} {'조건추출':>12s} {'평균조건':>8s} {'회피':>5s}")
    for s2 in ("none", "sub", "mecab"):
        for s1 in ("none", "add", "pref", "all"):
            r = table[(s1, s2)]
            print(f"    {LABEL1[s1]:12s} {LABEL2[s2]:14s} {r['nonzero']:>4d}/{n} "
                  f"{r['nonzero']/n:>5.1%} {r['cond']:>8.2f} {r['avoid']:>5d}")

    print()
    print("=" * 92)
    print("[2] 합성 600 과 나란히 — 조건 추출률")
    print("=" * 92)
    synth = {("all", "sub"): 87.5, ("none", "sub"): 76.8, ("none", "mecab"): 81.3,
             ("all", "mecab"): 89.7, ("all", "none"): 71.3}
    print(f"    {'조합':30s} {'합성 600':>10s} {'설문 155':>10s} {'차이':>10s}")
    for cell, sv in synth.items():
        r = table[cell]
        real = r["nonzero"] / n * 100
        label = f"{LABEL1[cell[0]]} · {LABEL2[cell[1]]}"
        print(f"    {label:30s} {sv:>9.1f}% {real:>9.1f}% {real-sv:>+9.1f}%p")

    print()
    print("=" * 92)
    print("[3] ②가 ①의 일을 얼마나 대신하는가 — LLM 조건을 기준으로")
    print("=" * 92)
    print("    LLM 이 옳다는 뜻이 아니다. 대체 가능성만 본다")
    llm = table[("all", "none")]["cores"]
    for s2 in ("sub", "mecab"):
        other = table[("none", s2)]["cores"]
        tp = sum(len(a & b) for a, b in zip(llm, other))
        n_llm = sum(len(a) for a in llm)
        n_oth = sum(len(b) for b in other)
        exact = sum(1 for a, b in zip(llm, other) if a and a == b)
        print(f"    {LABEL2[s2]:14s} 재현율 {tp}/{n_llm} = {tp/max(n_llm,1):>5.1%} · "
              f"정밀도 {tp}/{n_oth} = {tp/max(n_oth,1):>5.1%} · 완전일치 {exact}/{n}")

    print()
    print("=" * 92)
    print("[4] status 분포")
    print("=" * 92)
    order = ["OK", "OK_RELAXED", "NO_CONDITION", "NO_RESULT"]
    cur = table[("all", "sub")]["status"]
    print(f"    {'조합':30s} " + " ".join(f"{s:>13s}" for s in order))
    for s2 in ("none", "sub", "mecab"):
        for s1 in ("none", "add", "pref", "all"):
            r = table[(s1, s2)]
            label = f"{LABEL1[s1]} · {LABEL2[s2]}"
            if (s1, s2) == ("all", "sub"):
                print(f"    {label + ' (현행)':30s} " +
                      " ".join(f"{r['status'][s]:>13d}" for s in order))
            else:
                print(f"    {label:30s} " + " ".join(
                    f"{r['status'][s]:>6d}({r['status'][s]-cur[s]:+5d})" for s in order))

    print()
    print("=" * 92)
    print("[5] LLM 실측 지연 — 설문 155건")
    print("=" * 92)
    lat = [x for _, _, x in rows if x is not None]
    if lat:
        a = np.array(lat)
        print(f"    중앙 {np.median(a):.2f}초 · 평균 {a.mean():.2f}초 · "
              f"p90 {np.percentile(a, 90):.2f}초 · 최대 {a.max():.2f}초 (n={len(a)})")
        print(f"    5초 타임아웃을 넘긴 건수 {(a >= 5.0).sum()}")
    print(f"    비교 — mecab 1회 분석 0.21ms · 검색 3.4ms")
    print(f"    ②단계 미매칭 표현 {table[('all','sub')]['unmatched']:,}회 "
          f"(문장당 {table[('all','sub')]['unmatched']/max(parsed,1):.2f})")


if __name__ == "__main__":
    main()

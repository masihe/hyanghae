"""부정 처리로 분석기 셋을 가른다. 그리고 원형 매칭이 새 오탐을 만드는지 확인한다.

    ./venv/Scripts/python.exe 64_negation_handling.py

API 호출 0회. 팀 저장소를 수정하지 않는다.

왜 재는가
----------
15번이 "분석기는 바꿀 만하다" 까지 답했지만 셋을 정확도로 가르지 못했다(격차 2문장).
남은 후보가 부정 처리다. 14번이 찾은 가장 큰 결함이 여기 있다.

    원문에 부정 표현                                115 / 600
    `additional_requirements` 로 새는 문장            86       <- 틀린 칸
    `avoid` 가 채워진 문장                            54
    ②가 accord 로 바꾼 문장                            7

그리고 14번이 경고를 하나 남겼다.

    지금 오탐이 0인 것은 사전에 `달`·`무겁` 같은 어간이 없어서다
    **설계가 막은 것이 아니라 운이다**

**원형 매칭은 사전 키를 어간으로 바꾸므로 그 운이 깨진다.** 15번 측정에는 이 위험이
들어 있지 않다. 먼저 그것부터 확인한다.

    사전 `깨끗한` 별칭 깨끗하게·깨끗한·깨끗해    core aquatic·fresh·soapy
    "너무 깨끗하기만 하지 않기"
        부분 문자열   `깨끗하기만` 안에 별칭이 없다        안 걸린다
        원형 매칭     깨끗한 -> (깨끗,)  깨끗하기만 -> (깨끗,)  **걸린다**

부정 범위 규칙 — 임의로 만들지 않는다
--------------------------------------
평가셋의 부정 조각 88회는 거의 전부 한 구조다.

    <용언 어간> 지 않-      너무 달지 않게 · 무겁지 않게 · 평범하지 않은
    <어근> 하기만 하지 않-   너무 깨끗하기만 하지 않기

한국어에서 `-지 않다` 는 바로 앞 용언을 부정한다. 그래서 규칙은 이렇다.

    부정 표지(않/VX · 안/MAG · 못/MAG · 말/VX · 없/VA)를 만나면
    **뒤에서 앞으로 가장 가까운 내용 형태소**를 부정 대상으로 본다 (거리 6 이내)

`하/XSA` · `지/EC` · `기/ETN` · `만/JX` 는 내용 형태소가 아니라 건너뛴다.
**세 분석기에 같은 규칙을 적용한다.** 그래야 분석기 차이만 남는다.

무엇을 재는가
--------------
    [1] 부정 조각에서 오탐이 생기는가        현행 vs 분석기 셋
    [2] 부정 표지를 분석기가 주는가          탐지율
    [3] 부정 범위 규칙을 붙이면              오탐 제거 · 회피 도달
    [4] 파이프라인 지표                      조건추출 · NDCG · status
    [5] 셋이 갈리는 문장

출력 없음. 표준출력에만 쓴다.
"""
import collections
import importlib.util
import json
import re
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, "C:/Users/SSAFY/Desktop/S15P21E203/ai")
import nlr_engine  # noqa: E402

CHECKPOINT = "analysis_outputs/34_evalset_stage1_checkpoint.csv"
ANSWER_KEY = "analysis_outputs/32_evalset_answer_key.csv"
LEXICON = "data/scent_knowledge/domain_lexicon_v1_14.csv"

CONTENT = {"NNG", "NNP", "NNB", "VA", "VV", "XR", "MAG", "SL", "SN", "SH"}

# 부정 표지. (표면형, 태그) 로 판정한다 — `안` 은 MAG 일 때만 부정이다(`안방` 의 안이 아니다)
NEG_MARK = {("않", "VX"), ("안", "MAG"), ("못", "MAG"), ("말", "VX"),
            ("없", "VA"), ("않", "VV"), ("말", "VV")}
NEG_WINDOW = 6

NEG_RE = re.compile(r"싫|말고|빼|않았으면|없었으면|피하|제외|아닌|덜|지 않|안 ")


def _norm(form, tag):
    """어간 끝 `하` 를 뗀다. 세 분석기에 같게 적용한다. (str, str)."""
    f = form.lower()
    base = tag.split("+")[0].split("-")[0]
    if base in {"VA", "VV"} and len(f) > 1 and f.endswith("하"):
        f = f[:-1]
    return f, base


class KiwiKey:
    name = "kiwi"

    def __init__(self):
        from kiwipiepy import Kiwi
        t = time.time()
        self.k = Kiwi()
        self.k.tokenize("적재 확인")
        self.load_sec = time.time() - t

    def tokens(self, text):
        return [_norm(t.form, t.tag) for t in self.k.tokenize(text)]


class MecabKey:
    name = "mecab"

    def __init__(self):
        import mecab
        t = time.time()
        self.m = mecab.MeCab()
        self.m.parse("적재 확인")
        self.load_sec = time.time() - t

    def tokens(self, text):
        out = []
        for w in self.m.parse(text):
            expr = getattr(w.feature, "expression", None)
            if expr:
                for part in expr.split("+"):
                    bits = part.split("/")
                    if len(bits) >= 2:
                        out.append(_norm(bits[0], bits[1]))
            else:
                out.append(_norm(w.surface, w.feature.pos))
        return out


class PecabKey:
    name = "pecab"

    def __init__(self):
        from pecab import PeCab
        t = time.time()
        self.p = PeCab()
        self.p.pos("적재 확인")
        self.load_sec = time.time() - t

    def tokens(self, text):
        return [_norm(f, t) for f, t in self.p.pos(text)]


ANALYZERS = (KiwiKey, MecabKey, PecabKey)


def split_negation(toks):
    """토큰 열을 (긍정 키, 부정 키)로 가른다. (tuple, tuple).

    부정 표지를 만나면 뒤에서 앞으로 가장 가까운 내용 형태소를 부정 대상으로 본다.
    부정 대상은 긍정 열에서 빠지고 부정 열로 간다.

    깨질 수 있는 곳 — 이중 부정(`없지 않다`)과 긴 수식(`달지도 무겁지도 않게`)은
    이 규칙으로 못 푼다. 창 6을 넘어가면 아무것도 안 잡는다.
    """
    negated = set()
    for i, (form, tag) in enumerate(toks):
        if (form, tag) not in NEG_MARK:
            continue
        for j in range(i - 1, max(-1, i - 1 - NEG_WINDOW), -1):
            if toks[j][1] in CONTENT and j not in negated:
                negated.add(j)
                break
    pos, neg = [], []
    for i, (form, tag) in enumerate(toks):
        if tag not in CONTENT:
            continue
        (neg if i in negated else pos).append(form)
    return tuple(pos), tuple(neg)


def has_negation(toks):
    """부정 표지를 담고 있는가. bool."""
    return any((f, t) in NEG_MARK for f, t in toks)


def build_keys(analyzer, lexicon_csv):
    """사전 표면형 -> 원형 열. dict[tuple, set[str]]."""
    lex = pd.read_csv(lexicon_csv, keep_default_na=False, dtype=str)
    keys = {}
    for row in lex.to_dict("records"):
        for f in [row["expression"]] + [a for a in row["aliases"].split("|") if a]:
            k = tuple(form for form, tag in analyzer.tokens(f) if tag in CONTENT)
            if k:
                keys.setdefault(k, set()).add(row["expression"])
    return keys


def contains(hay, needle):
    n, m = len(hay), len(needle)
    return m > 0 and m <= n and any(hay[i:i + m] == needle for i in range(n - m + 1))


def hits_of(keys, hay):
    """원형 열에서 걸리는 사전 표현. set[str]."""
    out = set()
    for k, expressions in keys.items():
        if contains(hay, k):
            out |= expressions
    return out


def core_of(index, expressions, haystack):
    """사전 표현 집합이 주는 core accord. set[str]."""
    out = set()
    for expression in expressions:
        for row in index["lexicon_by_expression"].get(expression, []):
            cond = row["match_condition"]
            if cond.startswith("query_contains:"):
                toks = [t for t in cond.split(":", 1)[1].split(",") if t]
                if not any(t in haystack for t in toks):
                    continue
            if row["required"] == "core" and row["candidate_name"] in index["aidx"]:
                out.add(row["candidate_name"])
    return out


def status_of(found):
    if found["stage"] == "NO_CONDITION":
        return "NO_CONDITION"
    if not len(found["rows"]):
        return "NO_RESULT"
    if found["stage"] == "AND":
        return "OK"
    return "OK_RELAXED"


def load_queries():
    ck = pd.read_csv(CHECKPOINT)
    out = []
    for r in ck.to_dict("records"):
        try:
            o = json.loads(r["raw_response"])
        except Exception:
            o = None
        out.append((str(r["sentence"]), o, int(r["perfume_id"])))
    return out


def main():
    spec = importlib.util.spec_from_file_location("ndcg41", "41_lexicon_ndcg.py")
    ndcg41 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ndcg41)
    key = pd.read_csv(ANSWER_KEY).set_index("perfume_id")
    index = nlr_engine.load_index(lexicon_csv=LEXICON)
    queries = load_queries()

    analyzers = []
    for cls in ANALYZERS:
        try:
            analyzers.append(cls())
        except Exception as exc:
            print(f"  {cls.name} 사용 불가: {type(exc).__name__} {exc}")
    keysets = {a.name: build_keys(a, LEXICON) for a in analyzers}

    # 부정 조각 모으기 — ①단계가 additional_requirements 로 흘린 것
    frags = []
    for text, structured, _ in queries:
        for raw in ((structured or {}).get("additional_requirements") or []):
            s = str(raw)
            if NEG_RE.search(s):
                frags.append(s)
    print(f"문장 {len(queries)}건 · 부정 조각 {len(frags)}회 · 고유 {len(set(frags))}개\n")

    # ------------------------------------------------------------------
    print("=" * 92)
    print("[1] 부정 조각에서 오탐이 생기는가 — 부정인데 긍정 조건으로 들어가는 것")
    print("=" * 92)
    bad = {}
    sub_bad = []
    for s in frags:
        got = nlr_engine._extract(index, s)[0]
        if got:
            sub_bad.append((s, sorted(got)))
    print(f"    {'방식':16s} {'오탐 조각':>10s} {'비율':>7s}")
    print(f"    {'A 부분문자열':16s} {len(sub_bad):>10d} {len(sub_bad)/len(frags):>6.1%}")
    for a in analyzers:
        hits = []
        for s in frags:
            pos = tuple(f for f, t in a.tokens(s) if t in CONTENT)
            c = core_of(index, hits_of(keysets[a.name], pos), s)
            if c:
                hits.append((s, sorted(c)))
        bad[a.name] = hits
        print(f"    {a.name + ' 원형':16s} {len(hits):>10d} {len(hits)/len(frags):>6.1%}")

    print("\n    분석기가 새로 만든 오탐 (부분문자열은 안 잡던 것)")
    sub_set = {s for s, _ in sub_bad}
    shown = 0
    for a in analyzers:
        newly = [(s, c) for s, c in bad[a.name] if s not in sub_set]
        print(f"      {a.name} — {len(newly)}건")
        for s, c in newly[:5]:
            print(f"         \"{s[:44]}\"  ->  {c}")
        shown += 1

    # ------------------------------------------------------------------
    print()
    print("=" * 92)
    print("[2] 부정 표지를 분석기가 주는가")
    print("=" * 92)
    print(f"    {'분석기':10s} {'부정 탐지':>10s} {'비율':>7s}")
    for a in analyzers:
        n = sum(1 for s in frags if has_negation(a.tokens(s)))
        print(f"    {a.name:10s} {n:>10d} {n/len(frags):>6.1%}")

    # ------------------------------------------------------------------
    print()
    print("=" * 92)
    print("[3] 부정 범위 규칙을 붙이면 — 오탐이 사라지고 회피로 가는가")
    print("=" * 92)
    print(f"    {'분석기':10s} {'남은 오탐':>10s} {'회피로 간 조각':>14s} {'회피 accord':>12s}")
    for a in analyzers:
        left, to_avoid, acc = 0, 0, collections.Counter()
        for s in frags:
            pos, neg = split_negation(a.tokens(s))
            if core_of(index, hits_of(keysets[a.name], pos), s):
                left += 1
            av = core_of(index, hits_of(keysets[a.name], neg), s)
            if av:
                to_avoid += 1
                acc.update(av)
        print(f"    {a.name:10s} {left:>10d} {to_avoid:>14d} {len(acc):>12d}")

    # ------------------------------------------------------------------
    print()
    print("=" * 92)
    print("[4] 파이프라인 지표 — 부정 처리 끄고 / 켜고")
    print("=" * 92)
    order = ["OK", "OK_RELAXED", "NO_CONDITION", "NO_RESULT"]
    rows = []

    def run(analyzer, negation):
        ndcgs, ncond, nonzero, avoid_reach = [], [], 0, 0
        statuses = collections.Counter()
        for text, structured, pid in queries:
            parts = [text]
            if structured:
                parts += [str(v) for v in (structured.get("additional_requirements") or [])]
            hay = " ".join(parts)
            avoid = {x for raw in ((structured or {}).get("avoid") or [])
                     if (x := nlr_engine._normalize_accord(index, raw))}
            if analyzer is None:
                core = nlr_engine._extract(index, hay)[0]
            else:
                toks = analyzer.tokens(hay)
                if negation:
                    pos, neg = split_negation(toks)
                    core = core_of(index, hits_of(keysets[analyzer.name], pos), hay)
                    avoid |= core_of(index, hits_of(keysets[analyzer.name], neg), hay)
                else:
                    pos = tuple(f for f, t in toks if t in CONTENT)
                    core = core_of(index, hits_of(keysets[analyzer.name], pos), hay)
                for ko, accord in nlr_engine.KOREAN_ACCORD.items():
                    if ko in hay and accord in index["aidx"]:
                        core.add(accord)
            if structured:
                for raw in (structured.get("scent_preference") or []):
                    x = nlr_engine._normalize_accord(index, raw)
                    if x:
                        core.add(x)
            avoid_reach += bool(avoid)
            core = sorted(set(core) - avoid)
            ncond.append(len(core))
            nonzero += bool(core)
            found = nlr_engine.search(index, core, avoid)
            statuses[status_of(found)] += 1
            C = [x for x in str(key.loc[pid, "C"]).split("|") if x in index["aidx"]]
            if not C:
                continue
            cols = [index["aidx"][x] for x in C]
            ndcgs.append(ndcg41.ndcg_at_k(
                [int(index["has"][r, cols].sum()) for r in found["rows"]], len(C)))
        return {"nonzero": nonzero, "cond": float(np.mean(ncond)),
                "ndcg": float(np.mean(ndcgs)), "status": statuses,
                "avoid": avoid_reach}

    rows.append(("A 부분문자열", run(None, False)))
    for a in analyzers:
        rows.append((f"{a.name} 부정끄기", run(a, False)))
        rows.append((f"{a.name} 부정켜기", run(a, True)))

    b = rows[0][1]
    print(f"    {'방식':16s} {'조건추출':>11s} {'평균조건':>8s} {'회피':>6s} "
          f"{'NDCG@5':>10s} {'vs A':>11s}")
    for label, r in rows:
        print(f"    {label:16s} {r['nonzero']:>4d}/{len(queries)} "
              f"{r['nonzero']/len(queries):>5.1%} {r['cond']:>8.2f} {r['avoid']:>6d} "
              f"{r['ndcg']:>10.6f} {r['ndcg']-b['ndcg']:>+11.6f}")

    print(f"\n    status 분포")
    print(f"    {'방식':16s} " + " ".join(f"{s:>13s}" for s in order))
    for label, r in rows:
        if r is b:
            print(f"    {label:16s} " + " ".join(f"{r['status'][s]:>13d}" for s in order))
        else:
            print(f"    {label:16s} " + " ".join(
                f"{r['status'][s]:>6d}({r['status'][s]-b['status'][s]:+5d})" for s in order))

    # ------------------------------------------------------------------
    print()
    print("=" * 92)
    print("[5] 셋이 갈리는 부정 조각")
    print("=" * 92)
    shown = 0
    for s in sorted(set(frags)):
        res = {}
        for a in analyzers:
            pos, neg = split_negation(a.tokens(s))
            res[a.name] = (sorted(core_of(index, hits_of(keysets[a.name], pos), s)),
                           sorted(core_of(index, hits_of(keysets[a.name], neg), s)))
        if len({(tuple(p), tuple(n)) for p, n in res.values()}) == 1:
            continue
        print(f"\n    \"{s[:56]}\"")
        for name, (p, n) in res.items():
            print(f"       {name:8s} 긍정{p}  부정{n}")
        shown += 1
        if shown >= 8:
            break


if __name__ == "__main__":
    main()

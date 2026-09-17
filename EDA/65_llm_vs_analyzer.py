"""①단계 LLM 구조화와 ②단계 형태소 분석기가 각각 얼마나 기여하는지 가른다.

    ./venv/Scripts/python.exe 65_llm_vs_analyzer.py

API 호출 0회. 저장된 600문장 체크포인트의 ①단계 출력을 쓴다.

왜 재는가 — 둘은 대안이 아니다
--------------------------------
```
사용자 문장
  ① LLM 구조화    llm_stage1.py · gpt-5.4-nano     표현 조각을 뽑는다
  ② 사전 -> accord understand()                     표현을 accord 로 바꾼다  <- 분석기 자리
```

15번이 분석기를 쟀고 16번이 임베딩을 쟀지만 **①단계와 견준 적이 없다.** 배포 인계 문서에
`키 있음 86.7% / 키 없음 75.5%` 가 적혀 있는데 사전 v1.8 기준이고 지금과 조건이 다르다.
같은 조건에서 다시 잰다.

무엇을 조합하는가
------------------
①단계 출력을 **칸별로 쪼갠다.** 14번이 같은 단어라도 어느 칸에 들어가느냐로 해석이
갈린다는 것을 찾았기 때문이다.

    ① 없음      structured=None. 원문만 본다
    ① add 만    additional_requirements 를 건초더미에 더한다 (사전 표면형 매칭을 탄다)
    ① pref 만   scent_preference 를 `_normalize_accord` 로 푼다 (accord 이름 직접 해석)
    ① 전부      add + pref + avoid. 지금 프로덕션

    ② 부분문자열  지금 프로덕션
    ② mecab 원형  15번이 고른 후보

`avoid` 는 `① 전부` 에만 넣는다. 회피는 `structured` 에서만 오므로 ①이 없으면 0 이다.

출력 없음. 표준출력에만 쓴다.
"""
import collections
import importlib.util
import json
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

    mecab = MecabKey()
    keys = build_keys(mecab, LEXICON)

    parsed = sum(1 for _, o, _ in queries if isinstance(o, dict))
    print(f"문장 {len(queries)}건 · ①단계 파싱 성공 {parsed}건 · 사전 {LEXICON}")
    print("API 호출 0회 — 저장된 ①단계 출력을 쓴다\n")

    def run(stage1, stage2):
        """stage1: none|add|pref|all   stage2: sub|mecab"""
        ndcgs, ncond, nonzero, avoid_hit = [], [], 0, 0
        statuses = collections.Counter()
        for text, structured, pid in queries:
            o = structured if isinstance(structured, dict) else None
            parts = [text]
            if o and stage1 in ("add", "all"):
                parts += [str(v) for v in (o.get("additional_requirements") or [])]
            hay = " ".join(parts)

            if stage2 == "none":
                core = set()          # 사전 매칭을 아예 끈다. ①단계만 남는다
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

            core = sorted(set(core) - avoid)
            ncond.append(len(core))
            nonzero += bool(core)
            found = nlr_engine.search(index, core, avoid)
            statuses[status_of(found)] += 1
            C = [a for a in str(key.loc[pid, "C"]).split("|") if a in index["aidx"]]
            if not C:
                continue
            cols = [index["aidx"][a] for a in C]
            ndcgs.append(ndcg41.ndcg_at_k(
                [int(index["has"][r, cols].sum()) for r in found["rows"]], len(C)))
        return {"nonzero": nonzero, "cond": float(np.mean(ncond)),
                "ndcg": float(np.mean(ndcgs)), "status": statuses, "avoid": avoid_hit}

    LABEL1 = {"none": "① 없음", "add": "① add 만", "pref": "① pref 만", "all": "① 전부"}
    LABEL2 = {"none": "② 없음", "sub": "② 부분문자열", "mecab": "② mecab"}

    rows = []
    for s2 in ("none", "sub", "mecab"):
        for s1 in ("none", "add", "pref", "all"):
            rows.append(((s1, s2), run(s1, s2)))
    table = dict(rows)

    print("=" * 96)
    print("[1] 8개 조합")
    print("=" * 96)
    print(f"    {'①단계':12s} {'②단계':14s} {'조건추출':>11s} {'평균조건':>8s} "
          f"{'회피':>5s} {'NDCG@5':>10s}")
    for (s1, s2), r in rows:
        print(f"    {LABEL1[s1]:12s} {LABEL2[s2]:14s} {r['nonzero']:>4d}/600 "
              f"{r['nonzero']/600:>5.1%} {r['cond']:>8.2f} {r['avoid']:>5d} {r['ndcg']:>10.6f}")

    print()
    print("=" * 96)
    print("[2] 각 단계가 혼자 얼마나 기여하는가 — 아무것도 없는 상태에서 하나씩 켠다")
    print("=" * 96)
    base = table[("none", "sub")]
    print(f"    바닥 (① 없음 · ② 부분문자열)   조건추출 {base['nonzero']}/600 "
          f"({base['nonzero']/600:.1%}) · NDCG {base['ndcg']:.6f}")
    print()
    print(f"    {'켠 것':28s} {'조건추출':>12s} {'NDCG@5':>12s}")
    for label, cell in (("① LLM 만 켠다 (전부)", ("all", "sub")),
                        ("② mecab 만 켠다", ("none", "mecab")),
                        ("둘 다 켠다", ("all", "mecab"))):
        r = table[cell]
        print(f"    {label:28s} {r['nonzero']-base['nonzero']:>+7d}문장 "
              f"{(r['nonzero']-base['nonzero'])/600:>+6.1%} "
              f"{r['ndcg']-base['ndcg']:>+12.6f}")

    print()
    print("=" * 96)
    print("[3] ①단계의 어느 칸이 일하는가")
    print("=" * 96)
    for s2 in ("sub", "mecab"):
        b = table[("none", s2)]
        print(f"    {LABEL2[s2]} 위에서")
        for s1 in ("add", "pref", "all"):
            r = table[(s1, s2)]
            print(f"      {LABEL1[s1]:12s} 조건추출 {r['nonzero']-b['nonzero']:>+5d}문장 · "
                  f"NDCG {r['ndcg']-b['ndcg']:>+.6f}")
        print()

    print("=" * 96)
    print("[4] status 분포")
    print("=" * 96)
    order = ["OK", "OK_RELAXED", "NO_CONDITION", "NO_RESULT"]
    cur = table[("all", "sub")]["status"]
    print(f"    {'조합':28s} " + " ".join(f"{s:>13s}" for s in order))
    for (s1, s2), r in rows:
        label = f"{LABEL1[s1]} · {LABEL2[s2]}"
        if (s1, s2) == ("all", "sub"):
            print(f"    {label + ' (현행)':28s} " +
                  " ".join(f"{r['status'][s]:>13d}" for s in order))
        else:
            print(f"    {label:28s} " + " ".join(
                f"{r['status'][s]:>6d}({r['status'][s]-cur[s]:+5d})" for s in order))


if __name__ == "__main__":
    main()

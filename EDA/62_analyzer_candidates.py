"""분석기 후보를 넓히고, 61번이 빠뜨린 guardrail 두 개를 같이 잰다.

    ./venv/Scripts/python.exe 62_analyzer_candidates.py

API 호출 0회. 팀 저장소를 수정하지 않는다. 분석기는 개인 저장소 venv 에만 설치했다.

61번과 무엇이 다른가
---------------------
61번은 kiwi·mecab 둘만 쟀고 `status` 분포를 찍지 않았다. 그런데 평균 조건이
2.52 -> 2.72 로 늘었다. 엔진은 조건을 하드 AND 로 거므로(`MIN_CORE_FOR_AND = 2`)
조건이 늘면 후보가 좁아져 완화 사다리를 더 탈 수 있다. **조건을 더 뽑는 것과 추천이
좋아지는 것은 다른 이야기다.** 57번은 이 분포를 guardrail 로 먼저 확인하고 판정했는데
60·61번이 그 절차를 건너뛰었다. 여기서 되돌린다.

후보를 어떻게 넓혔나 — PyPI 에 직접 물어봤다
---------------------------------------------
`pip index versions` 와 PyPI JSON API 로 실물을 확인했다. 문서상 제약으로만 거르지 않는다.

    pecab       1.0.8   순수 파이썬 · mecab-ko-dic 기반       측정 O  <- 새로 넣는다
    soylemma    0.2.0   설치는 되지만 **문장을 쪼개지 못한다**  측정 X — 아래 근거
    khaiii              PyPI 에 배포 자체가 없다               측정 X
    konlpy      0.6.0   Okt·Komoran·Kkma 가 Java              측정 X — 컨테이너에 JVM
    koalanlp    2.1.7   같은 이유로 Java                       측정 X
    bareunpy    2.1.0   별도 라이선스 서버가 필요하다           측정 X
    kss         6.0.6   문장 분리기다. 품사 태거가 아니다        측정 X
    소스: 2026-09-16 조회

**soylemma 를 뺀 근거는 실행 결과다.** 용언만 다루는 단어 단위 도구라 문장 입력을 받지
못하고, 명사와 모르는 활용형에 빈 결과를 준다.

    깔끔하게 -> []              달콤한 -> []
    풀잎     -> []              어린   -> [('어리다','Verb'), ...]   이것만 된다

pecab 의 한계 — 숨기지 않고 잰다
---------------------------------
pecab 의 `pos()` 는 표면형과 결합 태그를 준다. **활용형의 원형을 풀어주지 않는다.**

    kiwi    어린 -> 어리/VA            원형
    mecab   쓸   -> 쓰/VV + ᆯ/ETM      원형 (feature.expression)
    pecab   쓸   -> 쓸/VV+ETM          표면형 그대로

어간이 XR 로 떨어지는 것(`달콤한` -> 달콤/XR)은 셋 다 같지만, 용언 활용에서는 pecab 이
불리하다. 이 차이가 숫자에 그대로 나오게 둔다.

속도 측정의 함정 둘 — 61번 숫자가 이것 때문에 틀렸다
------------------------------------------------------
61번은 **같은 문장을 200회** 돌려 1회 분석 시간을 냈다. 두 군데서 어긋난다.

    pecab 은 결과를 캐시한다     같은 문장 0.07ms · 다른 문장 200개 12.25ms
                                61번 방식이면 가장 빠른 분석기로 보인다. 실제로는 가장 느리다
    kiwi 는 지연 적재다          `Kiwi()` 생성은 326MB 에서 멈추고, **첫 분석 때** 516MB 로 뛴다
                                1회성 적재 비용이 200회에 나뉘어 5.68ms 로 찍혔다. 실제는 0.44ms

그래서 여기서는 **적재 시간에 첫 분석을 포함**하고, 속도는 **서로 다른 문장 200개**로 잰다.

무엇을 재는가
--------------
사전 v1.14 를 고정하고 매칭 방식만 바꾼다.

    A  부분 문자열   지금 프로덕션
    B  kiwi 원형
    D  mecab 원형
    E  pecab 원형

    [1] 속도        적재 · 1회 분석
    [2] 정확도      조건추출 · 평균조건 · NDCG@5 · **status 분포**  <- 분포가 새로 들어간다
    [3] 메모리      엔진만 올렸을 때 대비 분석기가 더 쓰는 양        <- 새로 들어간다

메모리는 분석기마다 **따로 프로세스를 띄워** 잰다. 한 프로세스에서 순서대로 올리면
앞서 올린 것의 할당이 뒤에 섞인다.

출력 없음. 표준출력에만 쓴다.
"""
import collections
import importlib.util
import json
import os
import subprocess
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

PROBE = [
    "빨래 냄새 나는 향수 찾고 있어. 너무 달지 않고 깔끔했으면 좋겠어",
    "어린이도 쓸 수 있는 은은한 꽃향을 원해. 평범하지 않았으면 해",
    "갓 뜯은 풀잎 같은 싱그러움과 나무통 느낌이 섞였으면 좋겠어",
]


def _norm(form, tag):
    """어간 끝 `하` 를 뗀다. 세 분석기에 같게 적용한다. (str, str).

    kiwi 가 문맥으로 품사를 판별해서 별칭 `달콤한`(홀로)과 문장 속 `달콤한` 이 다른 키가
    된다. 60번에서 이 결함으로 첫 측정이 무효가 됐다. `하` 를 떼면 둘 다 `달콤` 이 된다.
    """
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
        self.k.tokenize("적재 확인")     # kiwi 는 첫 분석 때 모델을 올린다. 아래 주석 참고
        self.load_sec = time.time() - t

    def __call__(self, text):
        out = []
        for t in self.k.tokenize(text):
            f, base = _norm(t.form, t.tag)
            if base in CONTENT:
                out.append(f)
        return tuple(out)


class MecabKey:
    name = "mecab"

    def __init__(self):
        import mecab
        t = time.time()
        self.m = mecab.MeCab()
        self.m.parse("적재 확인")
        self.load_sec = time.time() - t

    def __call__(self, text):
        out = []
        for w in self.m.parse(text):
            expr = getattr(w.feature, "expression", None)
            if expr:                      # 활용형 — 원형 분해가 들어 있다
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


class PecabKey:
    name = "pecab"

    def __init__(self):
        from pecab import PeCab
        t = time.time()
        self.p = PeCab()
        self.p.pos("적재 확인")          # 사전을 실제로 읽게 한다. 지연 적재라서다
        self.load_sec = time.time() - t

    def __call__(self, text):
        out = []
        for form, tag in self.p.pos(text):
            f, base = _norm(form, tag)
            if base in CONTENT:
                out.append(f)
        return tuple(out)


ANALYZER_CLASSES = (KiwiKey, MecabKey, PecabKey)
LABEL = {"kiwi": "B", "mecab": "D", "pecab": "E"}


def build_keys(keyfn, lexicon_csv):
    """사전 표면형 -> 원형 열. dict[tuple, set[str]].

    엔진의 `load_index` 가 `[expression] + aliases` 로 surface 를 만드는 것과 같게 맞춘다.
    다르면 A 와 비교가 성립하지 않는다.
    """
    lex = pd.read_csv(lexicon_csv, keep_default_na=False, dtype=str)
    keys = {}
    for row in lex.to_dict("records"):
        for f in [row["expression"]] + [a for a in row["aliases"].split("|") if a]:
            k = keyfn(f)
            if k:
                keys.setdefault(k, set()).add(row["expression"])
    return keys


def contains(hay, needle):
    """needle 이 hay 의 연속 부분열인가. bool."""
    n, m = len(hay), len(needle)
    return m > 0 and m <= n and any(hay[i:i + m] == needle for i in range(n - m + 1))


def lemma_core(index, keys, keyfn, haystack):
    """원형 매칭으로 core accord 를 찾는다. set[str]."""
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
    """`search()` 결과를 `recommend()` 와 같은 status 로 접는다. str.

    nlr_engine.py 의 recommend() 안에 있는 분기를 그대로 옮긴 것이다. 57번이 guardrail
    로 쓴 값과 같은 정의여야 비교가 된다.
    """
    if found["stage"] == "NO_CONDITION":
        return "NO_CONDITION"
    if not len(found["rows"]):
        return "NO_RESULT"
    if found["stage"] == "AND":
        return "OK"
    return "OK_RELAXED"


def load_queries():
    """(문장, ①단계 dict, 정답 향수 id) 목록. list[tuple]."""
    ck = pd.read_csv(CHECKPOINT)
    out = []
    for r in ck.to_dict("records"):
        try:
            o = json.loads(r["raw_response"])
        except Exception:
            o = None
        out.append((str(r["sentence"]), o, int(r["perfume_id"])))
    return out


def haystack_of(text, structured):
    """엔진이 보는 건초더미를 만든다. str."""
    parts = [text]
    if structured:
        parts += [str(v) for v in (structured.get("additional_requirements") or [])]
    return " ".join(parts)


def mem_probe(name):
    """분석기 하나가 엔진 위에 얼마를 더 쓰는지 잰다. 표준출력에 JSON 한 줄.

    별도 프로세스로 실행된다. 엔진 인덱스를 먼저 올려 기준선을 잡고, 그다음 분석기를
    올려 사전 키까지 만든 뒤 다시 잰다.
    """
    import psutil
    proc = psutil.Process()
    index = nlr_engine.load_index(lexicon_csv=LEXICON)
    base = proc.memory_info().rss
    cls = {c.name: c for c in ANALYZER_CLASSES}[name]
    analyzer = cls()
    keys = build_keys(analyzer, LEXICON)
    for s in PROBE:
        lemma_core(index, keys, analyzer, s)
    after = proc.memory_info().rss
    print(json.dumps({"name": name, "base": base, "after": after}))


def main():
    spec = importlib.util.spec_from_file_location("ndcg41", "41_lexicon_ndcg.py")
    ndcg41 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ndcg41)
    key = pd.read_csv(ANSWER_KEY).set_index("perfume_id")
    queries = load_queries()
    index = nlr_engine.load_index(lexicon_csv=LEXICON)

    analyzers = []
    for cls in ANALYZER_CLASSES:
        try:
            analyzers.append(cls())
        except Exception as exc:
            print(f"  {cls.name} 사용 불가: {type(exc).__name__} {exc}")
    print(f"쿼리 {len(queries)}건 · 사전 {LEXICON}\n")

    print("[1] 속도 — 서로 다른 문장 200개")
    print(f"    {'분석기':10s} {'적재':>9s} {'1회 분석':>10s}")
    probe_sents = [t for t, _, _ in queries[:200]]
    for a in analyzers:
        t = time.time()
        for s in probe_sents:
            a(s)
        print(f"    {a.name:10s} {a.load_sec:>8.2f}초 {(time.time()-t)*5:>9.2f}ms")

    print("\n[2] 조건 추출 · 추천 품질 · status 분포 (사전 v1.14 고정)")
    modes = [("A 부분문자열", None)]
    modes += [(f"{LABEL[a.name]} {a.name} 원형", a) for a in analyzers]

    rows = []
    for label, keyfn in modes:
        keys = build_keys(keyfn, LEXICON) if keyfn else None
        ndcgs, ncond, nonzero = [], [], 0
        statuses = collections.Counter()
        for text, structured, pid in queries:
            hay = haystack_of(text, structured)
            core = (lemma_core(index, keys, keyfn, hay) if keyfn
                    else nlr_engine._extract(index, hay)[0])
            if structured:
                for raw in (structured.get("scent_preference") or []):
                    a2 = nlr_engine._normalize_accord(index, raw)
                    if a2:
                        core.add(a2)
            avoid = {a2 for raw in ((structured or {}).get("avoid") or [])
                     if (a2 := nlr_engine._normalize_accord(index, raw))}
            core = sorted(core - avoid)
            ncond.append(len(core))
            nonzero += bool(core)
            found = nlr_engine.search(index, core, avoid)
            statuses[status_of(found)] += 1
            C = [a2 for a2 in str(key.loc[pid, "C"]).split("|") if a2 in index["aidx"]]
            if not C:
                continue
            cols = [index["aidx"][a2] for a2 in C]
            ndcgs.append(ndcg41.ndcg_at_k(
                [int(index["has"][r, cols].sum()) for r in found["rows"]], len(C)))
        rows.append({"방식": label, "nonzero": nonzero, "cond": float(np.mean(ncond)),
                     "ndcg": float(np.mean(ndcgs)), "status": statuses})

    base = rows[0]
    print(f"    {'방식':16s} {'조건추출':>11s} {'평균조건':>8s} {'NDCG@5':>10s} {'vs A':>11s}")
    for r in rows:
        print(f"    {r['방식']:16s} {r['nonzero']:>4d}/{len(queries)} "
              f"{r['nonzero']/len(queries):>5.1%} {r['cond']:>8.2f} {r['ndcg']:>10.6f} "
              f"{r['ndcg']-base['ndcg']:>+11.6f}")

    print(f"\n    status 분포 — 57번이 guardrail 로 쓴 값")
    order = ["OK", "OK_RELAXED", "NO_CONDITION", "NO_RESULT"]
    print(f"    {'방식':16s} " + " ".join(f"{s:>13s}" for s in order))
    for r in rows:
        cells = []
        for s in order:
            d = r["status"][s] - base["status"][s]
            cells.append(f"{r['status'][s]:>6d}({d:+5d})" if r is not base
                         else f"{r['status'][s]:>13d}")
        print(f"    {r['방식']:16s} " + " ".join(cells))

    print("\n[3] 메모리 — 엔진만 올렸을 때 대비 분석기가 더 쓰는 양")
    print("    분석기마다 프로세스를 따로 띄워 잰다")
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    print(f"    {'분석기':10s} {'엔진만':>10s} {'분석기 포함':>12s} {'증가':>10s}")
    for a in analyzers:
        out = subprocess.run([sys.executable, os.path.abspath(__file__), "--mem", a.name],
                             capture_output=True, text=True, encoding="utf-8", env=env)
        line = [x for x in out.stdout.strip().splitlines() if x.startswith("{")]
        if not line:
            print(f"    {a.name:10s} 측정 실패: {out.stderr.strip()[:70]}")
            continue
        d = json.loads(line[-1])
        mb = 1024 * 1024
        print(f"    {a.name:10s} {d['base']/mb:>9.0f}MB {d['after']/mb:>11.0f}MB "
              f"{(d['after']-d['base'])/mb:>+9.0f}MB")


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--mem":
        mem_probe(sys.argv[2])
    else:
        main()

"""한국어 형태소 분석기 후보를 같은 조건에서 비교한다.

    ./venv/Scripts/python.exe 61_analyzer_comparison.py

API 호출 0회. 팀 저장소를 수정하지 않는다. 분석기는 개인 저장소 venv 에만 설치했다.

후보를 어떻게 골랐나 — 배포 제약으로 먼저 걸렀다
--------------------------------------------------
`NLR_DEPLOY_HANDOFF.md` 로 인프라에 넘긴 조건이 "의존성 4개 · 컴파일 없음 · 휠로 설치 ·
메모리 162MB" 이고 **인프라는 아직 `docker build` 도 돌려보지 못했다.** 그래서 설치조차
어려운 후보를 재는 것은 낭비다.

    kiwipiepy        휠(abi3) 3.6MB + 모델 88MB       측정 O
    python-mecab-ko  휠 0.7MB + 사전 34.5MB           측정 O
    konlpy           휠 19.4MB 이지만 Okt·Komoran·Kkma·Hannanum 이 **Java** 다
                     컨테이너에 JVM 을 넣어야 한다                측정 X — 제약으로 탈락
    soynlp           순수 파이썬 0.4MB 이지만 **품사 태거가 아니다**
                     비지도 단어 추출기라 원형·품사·부정을 주지 않는다   측정 X — 용도가 다르다

**임베딩 모델(KoSBERT·KoSimCSE 등)은 이 비교에 넣지 않았다.** 푸는 문제가 다르다 —
형태소 분석기는 표면형(활용형·토큰 경계·부정)을, 임베딩은 의미(`은은한 꽃향` -> floral)를
다룬다. 그리고 `spec.md` 1장의 "추천 이유를 설명해야 한다" 와 부딪친다. 별건으로 다뤄야 한다.

무엇을 비교하는가
------------------
사전 v1.14 를 고정하고 **매칭 방식만** 바꾼다.

    A  부분 문자열      지금 프로덕션
    B  kiwi 원형
    D  mecab 원형

원형 키 만드는 법은 둘을 같게 맞췄다 — 내용 형태소만 남기고, 어간 끝 `하` 를 뗀다.
이걸 안 하면 같은 단어가 문맥에 따라 다른 키가 되어 매칭이 실패한다(60번에서 이 결함으로
첫 측정이 무효가 됐다).

    별칭 "달콤한" 홀로     kiwi 달콤하/VA · mecab 달콤/XR+하/XSA
    문장 "… 달콤한 과일 …"  kiwi 달콤/XR   · mecab 달콤/XR
    -> `하` 를 떼면 둘 다 `달콤` 으로 모인다

출력 없음. 표준출력에만 쓴다.
"""
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
    """어간 끝 `하` 를 뗀다. 두 분석기에 같게 적용한다."""
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


def build_keys(keyfn, lexicon_csv):
    """사전 표면형 -> 원형 열. dict[tuple, set[str]]."""
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
    queries = load_queries()
    index = nlr_engine.load_index(lexicon_csv=LEXICON)

    analyzers = []
    for cls in (KiwiKey, MecabKey):
        try:
            analyzers.append(cls())
        except Exception as exc:
            print(f"  {cls.name} 사용 불가: {exc}")
    print(f"쿼리 {len(queries)}건 · 사전 {LEXICON}\n")

    # 분석 속도 — 같은 문장 200회
    print("[1] 속도")
    probe = "빨래 냄새 나는 향수 찾고 있어. 너무 달지 않고 깔끔했으면 좋겠어"
    print(f"    {'분석기':10s} {'적재':>8s} {'1회 분석':>10s}")
    for a in analyzers:
        t = time.time()
        for _ in range(200):
            a(probe)
        print(f"    {a.name:10s} {a.load_sec:>7.2f}초 {(time.time()-t)*5:>9.2f}ms")

    # 정확도
    print("\n[2] 조건 추출과 추천 품질 (사전 v1.14 고정)")
    rows = []
    for label, keyfn in [("A 부분문자열", None)] + [(f"{'B' if a.name=='kiwi' else 'D'} {a.name} 원형", a)
                                                   for a in analyzers]:
        keys = build_keys(keyfn, LEXICON) if keyfn else None
        ndcgs, ncond, nonzero = [], [], 0
        for text, structured, pid in queries:
            parts = [text]
            if structured:
                parts += [str(v) for v in (structured.get("additional_requirements") or [])]
            hay = " ".join(parts)
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
            C = [a2 for a2 in str(key.loc[pid, "C"]).split("|") if a2 in index["aidx"]]
            if not C:
                continue
            cols = [index["aidx"][a2] for a2 in C]
            ndcgs.append(ndcg41.ndcg_at_k(
                [int(index["has"][r, cols].sum()) for r in found["rows"]], len(C)))
        rows.append({"방식": label, "조건추출": nonzero,
                     "비율": nonzero / len(queries), "평균조건": float(np.mean(ncond)),
                     "NDCG@5": float(np.mean(ndcgs))})

    base = rows[0]
    print(f"    {'방식':16s} {'조건추출':>10s} {'평균조건':>8s} {'NDCG@5':>10s} {'vs A':>11s}")
    for r in rows:
        print(f"    {r['방식']:16s} {r['조건추출']:>4d}/600 {r['비율']:>5.1%} "
              f"{r['평균조건']:>8.2f} {r['NDCG@5']:>10.6f} {r['NDCG@5']-base['NDCG@5']:>+11.6f}")

    # 두 분석기가 갈리는 문장
    if len(analyzers) == 2:
        print("\n[3] 두 분석기의 결과가 다른 문장")
        ks = [build_keys(a, LEXICON) for a in analyzers]
        shown = 0
        for text, structured, _ in queries:
            if shown >= 6:
                break
            parts = [text]
            if structured:
                parts += [str(v) for v in (structured.get("additional_requirements") or [])]
            hay = " ".join(parts)
            c0 = lemma_core(index, ks[0], analyzers[0], hay)
            c1 = lemma_core(index, ks[1], analyzers[1], hay)
            if c0 == c1:
                continue
            print(f"\n  \"{text[:52]}\"")
            print(f"     {analyzers[0].name} 만 {sorted(c0 - c1)}")
            print(f"     {analyzers[1].name} 만 {sorted(c1 - c0)}")
            shown += 1


if __name__ == "__main__":
    main()

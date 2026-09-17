"""형태소 분석기(kiwipiepy) 원형 매칭이 부분 문자열 매칭보다 나은지 잰다.

    ./venv/Scripts/python.exe 60_kiwi_lemma_matching.py

API 호출 0회. 팀 저장소를 수정하지 않는다. 개인 저장소 venv 에만 kiwipiepy 를 설치했다.

왜 재는가
----------
59번 감사에서 병목이 "표현 -> accord" 변환(16.3%)이라는 것을 확인했다. 그런데 손실의
상당 부분이 **의미 문제가 아니라 표면형 문제**로 보였다.

    어린   이 "어린이" 에 걸린다              부분 문자열 매칭에 토큰 경계가 없다
    평범   이 "평범하지 않은" 에 걸린다         부정을 구분하지 못한다
    깔끔하게·촉촉해·화려하게 …               활용형마다 별칭을 손으로 넣어야 한다 (69개 넣었다)

형태소 분석기를 쓰면 셋 다 구조적으로 사라진다. 실제로 확인했다.

    "어린이도 쓸 수 있는 향"    어린이/NNG          한 명사. `어린` 이 안 나온다
    "너무 어린 느낌은 싫어"     어리/VA + ᆫ/ETM     형용사로 구분
    "깔끔하게 정리된 향"        깔끔/NNG + 하/XSA    어간 분리
    "평범하지 않은 향"          평범/XR … 않/VX      부정이 명시적으로 태깅

무엇을 비교하는가
------------------
    A  v1.14 + 부분 문자열    지금 프로덕션
    B  v1.14 + kiwi 원형      같은 사전, 매칭만 바꾼다
    C  v1.8  + kiwi 원형      **이번 세션의 별칭 작업 69개 이전 사전**

C 가 핵심이다. C 가 A 를 따라잡으면 활용형 별칭 작업은 분석기가 없어서 돌아간 우회로였다는
뜻이 된다.

원형 매칭 방식
---------------
사전 표면형과 입력 문장을 **같은 방식으로** 내용 형태소 열로 바꾼 뒤, 사전 열이 문장 열의
**연속 부분열**인지 본다.

    사전 `깔끔한`   -> [깔끔]
    문장 "깔끔하고 시원한"  -> [깔끔, 시원]      -> 매칭 O
    사전 `어린`     -> [어리]
    문장 "어린이도"        -> [어린이]          -> 매칭 X  (부분 문자열이면 걸렸다)

연속 부분열로 좁힌 것은 정밀도 때문이다. 띄엄띄엄 허용하면 `비 오는 숲` 이 "비가 와서
습한 숲" 에도 걸린다. 그 대가로 구(句) 항목의 재현율을 일부 잃는다 — 결과에 같이 적는다.

**부정 처리는 이번 범위가 아니다.** 분석기가 `않/VX` 를 주므로 가능하지만, 그건 별도
설계(범위 판정)가 필요하다. 여기서는 매칭만 바꿔 효과를 분리해 본다.

출력 없음. 표준출력에만 쓴다.
"""
import collections
import importlib.util
import json
import sys
import time

import numpy as np
import pandas as pd
from kiwipiepy import Kiwi

sys.path.insert(0, "C:/Users/SSAFY/Desktop/S15P21E203/ai")
import nlr_engine  # noqa: E402

CHECKPOINT = "analysis_outputs/34_evalset_stage1_checkpoint.csv"
ANSWER_KEY = "analysis_outputs/32_evalset_answer_key.csv"
V114 = "data/scent_knowledge/domain_lexicon_v1_14.csv"
V18 = "data/scent_knowledge/domain_lexicon_v1_8.csv"

# 내용을 담는 태그만 남긴다. 조사(J*)·어미(E*)·접사(XS*)는 버린다.
CONTENT = {"NNG", "NNP", "NNB", "VA", "VV", "XR", "MAG", "SL", "SN", "SH"}


def content_key(kiwi, text):
    """문장을 내용 형태소 열로. tuple[str].

    **어간 끝 `하` 를 뗀다.** 이걸 안 하면 같은 단어가 문맥에 따라 다른 키가 되어
    매칭이 실패한다 — 첫 측정이 이 결함으로 무효가 됐다.

        별칭 "달콤한" 홀로     -> 달콤하/VA        key ('달콤하',)
        문장 "… 달콤한 과일 …"  -> 달콤/XR + 하/XSA  key ('달콤',)   <- 어긋난다
        별칭 "달달" 홀로       -> 달달/MAG         key ('달달',)
        문장 "달달하지만 …"     -> 달달하/VA        key ('달달하',)  <- 어긋난다

    kiwi 가 문맥으로 품사를 판별하기 때문이고, 별칭은 홀로 분석할 수밖에 없다.
    `하` 를 떼면 네 경우가 모두 `달콤`·`달달` 로 모인다.
    """
    out = []
    for t in kiwi.tokenize(text):
        tag = t.tag.split("-")[0]
        if tag not in CONTENT:
            continue
        form = t.form.lower()
        if tag in {"VA", "VV"} and len(form) > 1 and form.endswith("하"):
            form = form[:-1]
        out.append(form)
    return tuple(out)


def build_surface_keys(kiwi, lexicon_csv):
    """사전 표면형을 원형 열로. dict[tuple, set[str]]  (열 -> 표현 집합)."""
    lex = pd.read_csv(lexicon_csv, keep_default_na=False, dtype=str)
    keys = {}
    for row in lex.to_dict("records"):
        forms = [row["expression"]] + [a for a in row["aliases"].split("|") if a]
        for f in forms:
            k = content_key(kiwi, f)
            if k:
                keys.setdefault(k, set()).add(row["expression"])
    return keys


def contains(hay, needle):
    """needle 이 hay 의 연속 부분열인가. bool."""
    n, m = len(hay), len(needle)
    if m == 0 or m > n:
        return False
    return any(hay[i:i + m] == needle for i in range(n - m + 1))


def kiwi_lookup(index, keys, kiwi, haystack):
    """원형 매칭으로 core accord 를 찾는다. set[str]."""
    hay = content_key(kiwi, haystack)
    hit = set()
    for key, expressions in keys.items():
        if contains(hay, key):
            hit |= expressions
    core = set()
    for expression in hit:
        for row in index["lexicon_by_expression"].get(expression, []):
            cond = row["match_condition"]
            if cond.startswith("query_contains:"):
                tokens = [t for t in cond.split(":", 1)[1].split(",") if t]
                if not any(t in haystack for t in tokens):
                    continue
            if row["required"] != "core":
                continue
            if row["candidate_name"] in index["aidx"]:
                core.add(row["candidate_name"])
    # 한글 accord 음차는 엔진과 같게 유지한다
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
    t0 = time.time()
    kiwi = Kiwi()
    print(f"kiwi 적재 {time.time() - t0:.2f}초")

    spec = importlib.util.spec_from_file_location("ndcg41", "41_lexicon_ndcg.py")
    ndcg41 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ndcg41)
    key = pd.read_csv(ANSWER_KEY).set_index("perfume_id")
    queries = load_queries()
    print(f"쿼리 {len(queries)}건\n")

    modes = [
        ("A v1.14 + 부분문자열", V114, False),
        ("B v1.14 + kiwi 원형", V114, True),
        ("C v1.8  + kiwi 원형", V18, True),
    ]

    results = {}
    for label, lexicon, use_kiwi in modes:
        index = nlr_engine.load_index(lexicon_csv=lexicon)
        keys = build_surface_keys(kiwi, lexicon) if use_kiwi else None
        ndcgs, ncond, nonzero = [], [], 0
        t = time.time()
        for text, structured, pid in queries:
            parts = [text]
            if structured:
                parts += [str(v) for v in (structured.get("additional_requirements") or [])]
            hay = " ".join(parts)

            if use_kiwi:
                core = kiwi_lookup(index, keys, kiwi, hay)
            else:
                core, _ = nlr_engine._extract(index, hay)

            if structured:
                for raw in (structured.get("scent_preference") or []):
                    a = nlr_engine._normalize_accord(index, raw)
                    if a:
                        core.add(a)
            avoid = set()
            for raw in ((structured or {}).get("avoid") or []):
                a = nlr_engine._normalize_accord(index, raw)
                if a:
                    avoid.add(a)
            core = sorted(core - avoid)

            ncond.append(len(core))
            nonzero += bool(core)
            found = nlr_engine.search(index, core, avoid)
            C = [a for a in str(key.loc[pid, "C"]).split("|") if a in index["aidx"]]
            if not C:
                continue
            cols = [index["aidx"][a] for a in C]
            ndcgs.append(ndcg41.ndcg_at_k(
                [int(index["has"][r, cols].sum()) for r in found["rows"]], len(C)))
        results[label] = {
            "ndcg": float(np.mean(ndcgs)), "cond": float(np.mean(ncond)),
            "nonzero": nonzero, "sec": time.time() - t,
        }
        r = results[label]
        print(f"  {label:22s} 조건추출 {r['nonzero']:3d}/600 ({r['nonzero']/600:5.1%})  "
              f"평균 조건 {r['cond']:.2f}  NDCG@5 {r['ndcg']:.6f}  ({r['sec']:.0f}초)")

    a = results["A v1.14 + 부분문자열"]
    print()
    print("  A 대비")
    for label in ("B v1.14 + kiwi 원형", "C v1.8  + kiwi 원형"):
        r = results[label]
        print(f"    {label:22s} 조건추출 {r['nonzero'] - a['nonzero']:+4d}건  "
              f"NDCG {r['ndcg'] - a['ndcg']:+.6f}")

    # ------------------------------------------------------------------
    print("\n무엇이 달라졌나 — A 와 B 의 조건이 다른 문장")
    index = nlr_engine.load_index(lexicon_csv=V114)
    keys = build_surface_keys(kiwi, V114)
    shown = 0
    for text, structured, _ in queries:
        if shown >= 8:
            break
        parts = [text]
        if structured:
            parts += [str(v) for v in (structured.get("additional_requirements") or [])]
        hay = " ".join(parts)
        sub, _ = nlr_engine._extract(index, hay)
        lem = kiwi_lookup(index, keys, kiwi, hay)
        if sub == lem:
            continue
        only_sub = sorted(sub - lem)
        only_lem = sorted(lem - sub)
        print(f"\n  \"{text[:54]}\"")
        if only_lem:
            print(f"     kiwi 만 잡음   {only_lem}")
        if only_sub:
            print(f"     부분문자열만 잡음 {only_sub}")
        shown += 1


if __name__ == "__main__":
    main()

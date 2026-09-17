"""강도를 정렬에 쓰는 방식 다섯 가지를 비교한다. 70번이 부작용을 찾은 뒤의 후속이다.

    ./venv/Scripts/python.exe 71_intensity_sort_variants.py

GMS 호출 0회. 팀 저장소는 읽기만 한다.

왜 다시 재는가
---------------
70번이 "강도를 정렬 2차 키로" 를 쟀는데 부작용이 컸다.

    확산력 평균        2.32 -> 2.79      의도대로
    평가자 수 평균    6,255 -> **92**    98.5% 폭락
    평가자 100명 미만  41.5% -> 79.2%

원인 — 확산력이 극단인 향수는 평가자가 거의 없다.

    확산력 3.5~4.0 인 향수 3,799개 중 **92.3% 가 평가자 10명 미만**

이건 인계 문서가 평점을 정렬에서 뺀 이유(*"평점 5.00 인 향수의 99.8% 가 평가자
10명 이하"*)와 같은 함정이다. **그래서 "강도를 쓸 것인가" 가 아니라 "어떻게 쓰면
부작용이 작은가" 를 재야 한다.**

무엇을 못 재는지 먼저 밝힌다
------------------------------
**강도 만족도를 잴 지표가 없다.** 정답 키 `C` 는 accord 집합이라 강도 정보가 없다.
그래서 "좋아졌다" 는 증명할 수 없고, 아래 셋만 잴 수 있다.

    부작용   평가자 수가 얼마나 떨어지는가
    의도     확산력이 얼마나 올라가는가
    안전     status 분포가 흔들리는가 · NDCG 가 얼마나 내려가는가

다섯 방식
----------
`lexsort` 는 **마지막 원소가 1순위**다. 아래는 우선순위 순서로 적었다.

    A 현행        점수 -> 평가자 수 -> id
    B 강도 2순위   점수 -> 데이터유무 -> 강도 -> 평가자 수 -> id        70번이 잰 것
    C 강도 3순위   점수 -> 평가자 수 -> 데이터유무 -> 강도 -> id        **인기도를 지킨다**
    D 문턱 100    people >= 100 로 거른 뒤 B 와 같게 정렬              **하한을 보장한다**
    E 문턱 500    people >= 500 로 거른 뒤 B 와 같게
    F 강도 버킷    점수 -> 데이터유무 -> 강도구간(0.5) -> 평가자 수 -> id
                  **비슷한 강도끼리는 인기도가 정한다**

D·E 의 문턱은 **강도 요구가 있는 문장에만** 건다. 없으면 후보를 줄일 이유가 없다.

결측 처리는 70번과 같다 — `sillage_avg == 0` 은 "확산력 0" 이 아니라 **평가가 없어서 0**
(22,164개 · people 중앙값 1)이므로 `present` 키로 맨 뒤로 보낸다. 사용자 결정(2026-09-16).
`MEDIUM` 과 빈 문자열은 아무것도 하지 않는다.

출력 없음. 표준출력에만 쓴다.
"""
import collections
import importlib.util
import json
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "C:/Users/SSAFY/Desktop/S15P21E203/ai")
import nlr_engine  # noqa: E402

SYNTH = ("analysis_outputs/34_evalset_stage1_checkpoint.csv", "sentence")
ANSWER_KEY = "analysis_outputs/32_evalset_answer_key.csv"
LEXICON = "data/scent_knowledge/domain_lexicon_v1_14.csv"
PERFUMES = "perfumes.csv"
V4 = "analysis_outputs/69_prompt_v4_checkpoint.csv"

MODES = ["A", "B", "C", "D", "E", "F"]
LABEL = {
    "A": "A 현행",
    "B": "B 강도 2순위",
    "C": "C 강도 3순위",
    "D": "D 문턱100+강도",
    "E": "E 문턱500+강도",
    "F": "F 강도버킷0.5",
}
THRESHOLD = {"D": 100, "E": 500}
BUCKET = 0.5


def attach_strength(index):
    """`sillage_avg`·`longevity_avg` 를 인덱스 순서에 맞춰 붙인다. None."""
    d = pd.read_csv(PERFUMES, usecols=["id", "sillage_avg", "longevity_avg"],
                    low_memory=False).set_index("id")
    index["sillage"] = d["sillage_avg"].reindex(index["pid"]).fillna(0).to_numpy(np.float32)
    index["longevity"] = d["longevity_avg"].reindex(index["pid"]).fillna(0).to_numpy(np.float32)


def intensity_key(index, performance):
    """강도 요구를 (present, value) 로. 없으면 None.

    MEDIUM 과 빈 문자열은 None 이다 — 방향이 없어 순서를 정할 수 없다.
    """
    p = performance or {}
    for field, column in (("intensity", "sillage"), ("longevity", "longevity")):
        want = str(p.get(field) or "").strip().upper()
        if want in ("HIGH", "LOW"):
            col = index[column]
            return (col > 0).astype(np.float32), (col if want == "HIGH" else -col)
    return None


def build_keys(index, idx, score, key, mode):
    """`np.lexsort` 에 넘길 키 목록. **마지막 원소가 1순위다.** list[np.ndarray]."""
    pid = index["pid"][idx]
    people = -index["people"][idx]
    base = [pid, people, -score[idx]]
    if key is None or mode == "A":
        return base
    present, value = key
    if mode == "C":                       # 점수 -> 평가자 수 -> 데이터유무 -> 강도 -> id
        return [pid, -value[idx], -present[idx], people, -score[idx]]
    if mode == "F":                       # 강도를 구간으로 묶어 인기도에 자리를 남긴다
        bucket = np.floor(value[idx] / BUCKET)
        return [pid, people, -bucket, -present[idx], -score[idx]]
    # B · D · E — 점수 -> 데이터유무 -> 강도 -> 평가자 수 -> id
    return [pid, people, -value[idx], -present[idx], -score[idx]]


def rank(index, mask, score, key, mode, top_k=5, brand_cap=1):
    """엔진 `_rank` 복제 + 방식별 정렬. dict."""
    idx = np.flatnonzero(mask)
    if idx.size == 0:
        return {"rows": [], "candidate_count": 0}
    idx = idx[np.lexsort(tuple(build_keys(index, idx, score, key, mode)))]
    rows, seen = [], {}
    for row in idx:
        brand = index["brand"][row]
        if brand_cap and seen.get(brand, 0) >= brand_cap:
            continue
        seen[brand] = seen.get(brand, 0) + 1
        rows.append(int(row))
        if len(rows) >= top_k:
            break
    return {"rows": rows, "candidate_count": int(idx.size)}


def search(index, core, avoid, performance, mode,
           top_k=5, people_min=10, brand_cap=1, min_results=3):
    """엔진 `search` 복제 + 방식별 훅. dict."""
    key = intensity_key(index, performance) if mode != "A" else None
    cols = [index["aidx"][a] for a in core if a in index["aidx"]]
    if not cols:
        return {"rows": [], "stage": "NO_CONDITION", "candidate_count": 0}
    min_results = min(min_results, top_k)

    floor = people_min
    if key is not None and mode in THRESHOLD:     # 강도 요구가 있을 때만 문턱을 올린다
        floor = THRESHOLD[mode]
    base = index["people"] >= floor
    for accord in avoid:
        col = index["aidx"].get(accord)
        if col is not None:
            base &= ~index["has"][:, col]
    score = index["strength"][:, cols].sum(axis=1)

    if len(cols) == 1:
        picked = rank(index, base & index["has"][:, cols[0]], score, key, mode, top_k, brand_cap)
        if len(picked["rows"]) >= min_results:
            picked["stage"] = "SINGLE_BROAD"
            return picked
    if len(cols) >= nlr_engine.MIN_CORE_FOR_AND:
        mask = base.copy()
        for col in cols:
            mask &= index["has"][:, col]
        picked = rank(index, mask, score, key, mode, top_k, brand_cap)
        if len(picked["rows"]) >= min_results:
            picked["stage"] = "AND"
            return picked
    picked = rank(index, base & index["has"][:, cols].any(axis=1), score, key, mode,
                  top_k, brand_cap)
    if len(picked["rows"]) >= min_results:
        picked["stage"] = "RELAXED_OR"
        return picked
    mask = np.ones(index["n_perfumes"], dtype=bool)
    for accord in avoid:
        col = index["aidx"].get(accord)
        if col is not None:
            mask &= ~index["has"][:, col]
    mask &= index["has"][:, cols].any(axis=1)
    picked = rank(index, mask, score, key, mode, top_k, brand_cap)
    picked["stage"] = "RELAXED_OR_NO_THRESHOLD" if picked["rows"] else "NOT_ENOUGH"
    return picked


def status_of(found):
    if found["stage"] == "NO_CONDITION":
        return "NO_CONDITION"
    if not len(found["rows"]):
        return "NO_RESULT"
    if found["stage"] == "AND":
        return "OK"
    return "OK_RELAXED"


def conditions(index, text, o):
    parts = [text]
    if o:
        parts += [str(v) for v in (o.get("additional_requirements") or [])]
    hay = " ".join(parts)
    core = nlr_engine._extract(index, hay)[0]
    if o:
        for raw in (o.get("scent_preference") or []):
            a = nlr_engine._normalize_accord(index, raw)
            if a:
                core.add(a)
    avoid = {a for raw in ((o or {}).get("avoid") or [])
             if (a := nlr_engine._normalize_accord(index, raw))}
    return sorted(core - avoid), avoid, (o or {}).get("performance") or {}


def load_synth():
    d = pd.read_csv(SYNTH[0])
    out = []
    for r in d.to_dict("records"):
        try:
            o = json.loads(r["raw_response"])
        except Exception:
            o = None
        out.append((str(r[SYNTH[1]]), o if isinstance(o, dict) else None, int(r["perfume_id"])))
    return out


def load_v4(base_rows):
    """v4 프롬프트 출력으로 갈아끼운 합성 문장. list[tuple]."""
    v4 = pd.read_csv(V4)
    out = []
    for r in v4.to_dict("records"):
        if not r["ok"] or r["source"] != "합성":
            continue
        b = base_rows[int(r["row"])]
        out.append((str(r["sentence"]), json.loads(r["v2_response"]), b[2]))
    return out


def main():
    spec = importlib.util.spec_from_file_location("ndcg41", "41_lexicon_ndcg.py")
    ndcg41 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ndcg41)
    key = pd.read_csv(ANSWER_KEY).set_index("perfume_id")
    index = nlr_engine.load_index(lexicon_csv=LEXICON)
    attach_strength(index)
    rows = load_synth()
    v4rows = load_v4(rows)

    print(f"향수 {index['n_perfumes']:,}개")
    print(f"people >= 10 {int((index['people'] >= 10).sum()):,} · "
          f">= 100 {int((index['people'] >= 100).sum()):,} · "
          f">= 500 {int((index['people'] >= 500).sum()):,}")
    print("**강도 만족도를 잴 지표가 없다. 부작용과 안전만 잰다**\n")

    def run(recs, mode):
        st = collections.Counter()
        nd, peo, sil, moved, fired = [], [], [], 0, 0
        for text, o, pid in recs:
            core, avoid, perf = conditions(index, text, o)
            has_key = intensity_key(index, perf) is not None
            a = search(index, core, avoid, perf, "A")
            f = search(index, core, avoid, perf, mode)
            st[status_of(f)] += 1
            if has_key:
                fired += 1
                if a["rows"] != f["rows"]:
                    moved += 1
                peo += [index["people"][r] for r in f["rows"]]
                sil += [index["sillage"][r] for r in f["rows"]]
            C = [x for x in str(key.loc[pid, "C"]).split("|") if x in index["aidx"]]
            if C:
                cc = [index["aidx"][x] for x in C]
                nd.append(ndcg41.ndcg_at_k(
                    [int(index["has"][r, cc].sum()) for r in f["rows"]], len(C)))
        return {"status": st, "ndcg": float(np.mean(nd)), "moved": moved, "fired": fired,
                "people": float(np.mean(peo)) if peo else 0,
                "people_med": float(np.median(peo)) if peo else 0,
                "sillage": float(np.mean(sil)) if sil else 0,
                "low_pop": float(np.mean(np.array(peo) < 100)) if peo else 0}

    order = ["OK", "OK_RELAXED", "NO_CONDITION", "NO_RESULT"]
    for tag, recs in (("지금 프롬프트 · 합성 600", rows), ("v4 프롬프트 · 합성 42", v4rows)):
        print("=" * 100)
        print(f"[{tag}]")
        print("=" * 100)
        base = None
        print(f"    {'방식':16s} {'발동':>5s} {'바뀜':>5s} {'평가자평균':>10s} {'평가자중앙':>10s} "
              f"{'<100명':>7s} {'확산력':>7s} {'NDCG@5':>10s} {'vs A':>11s}")
        keep = {}
        for mode in MODES:
            r = run(recs, mode)
            if base is None:
                base = r
            keep[mode] = r
            print(f"    {LABEL[mode]:16s} {r['fired']:>5d} {r['moved']:>5d} "
                  f"{r['people']:>10.0f} {r['people_med']:>10.0f} {r['low_pop']:>6.1%} "
                  f"{r['sillage']:>7.2f} {r['ndcg']:>10.6f} {r['ndcg']-base['ndcg']:>+11.6f}")
        print()
        print(f"    status 분포")
        print(f"    {'방식':16s} " + " ".join(f"{s:>13s}" for s in order))
        for mode in MODES:
            r = keep[mode]
            if mode == "A":
                print(f"    {LABEL[mode]:16s} " + " ".join(f"{r['status'][s]:>13d}" for s in order))
            else:
                print(f"    {LABEL[mode]:16s} " + " ".join(
                    f"{r['status'][s]:>6d}({r['status'][s]-base['status'][s]:+5d})" for s in order))
        print()


if __name__ == "__main__":
    main()

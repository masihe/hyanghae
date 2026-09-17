"""`performance` 연결 패치를 개인 저장소에서 검증한다. 팀 저장소는 읽기만 한다.

    ./venv/Scripts/python.exe 70_performance_integration.py

GMS 호출 0회.

무엇을 검증하는가
------------------
68번이 "정렬 2차 키가 해를 안 끼친다" 까지 쟀지만 두 가지가 빠졌다.

    1. **강도 요구가 없는 문장에서 결과가 한 건도 안 바뀌는가**
       패치의 안전성 조건이다. 68번은 반대 방향(복제본이 원본과 같은가)을 봤다
    2. **v4 프롬프트 출력으로는 재본 적이 없다**
       지금 `performance` 가 11.2% 만 채워진 상태로 쟀다. v4 는 95% 를 채운다

조심할 것 — 정렬만 바꿔도 결과 **개수**가 바뀔 수 있다
--------------------------------------------------------
`_rank` 가 브랜드 상한(`BRAND_CAP = 1`)을 건다. 순서가 바뀌면 상한에 걸려 탈락하는
향수가 달라지고, 살아남는 개수가 `min_results` 아래로 내려가면 완화 사다리를 탄다.
68번에서 `status` 변화가 0 이었지만 그건 측정 결과이지 보장이 아니다. 다시 확인한다.

패치 규칙 — 사용자 결정(2026-09-16)
------------------------------------
    intensity=HIGH   sillage 높은 순을 2차 키로
    intensity=LOW    sillage 낮은 순을 2차 키로
    intensity=MEDIUM **아무것도 하지 않는다** (방향이 없어 순서를 정할 수 없다)
    빈 문자열        아무것도 하지 않는다
    intensity 가 없을 때만 longevity 를 같은 방식으로 본다

향 조건(점수)은 여전히 1순위다. 조건이 같은 향수들 사이에서만 강도가 순서를 정한다.

배포 관점
----------
팀 데이터 `perfumes_nlr.csv.gz` 에 `sillage_avg`·`longevity_avg` 가 없다. 여기서는
개인 저장소의 원본 `perfumes.csv` 에서 붙인다. 실제로 반영하려면 `build_data.py` 의
`KEEP_COLUMNS` 에 두 컬럼을 더해 데이터를 다시 만들어야 한다 — 4.74MB -> 5.28MB [측정].

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

SYNTH = ("합성 600", "analysis_outputs/34_evalset_stage1_checkpoint.csv", "sentence")
ANSWER_KEY = "analysis_outputs/32_evalset_answer_key.csv"
LEXICON = "data/scent_knowledge/domain_lexicon_v1_14.csv"
PERFUMES = "perfumes.csv"
V4 = "analysis_outputs/69_prompt_v4_checkpoint.csv"


def attach_strength(index):
    """`load_index` 가 컬럼 2개를 더 읽었을 때와 같은 상태로 만든다. None.

    실제 패치는 `usecols` 에 두 컬럼을 더하고 반환 dict 에 넣는다. 여기서는 원본
    `perfumes.csv` 에서 `pid` 순서에 맞춰 붙인다. 결과는 같다.
    """
    d = pd.read_csv(PERFUMES, usecols=["id", "sillage_avg", "longevity_avg"],
                    low_memory=False).set_index("id")
    index["sillage"] = d["sillage_avg"].reindex(index["pid"]).fillna(0).to_numpy(np.float32)
    index["longevity"] = d["longevity_avg"].reindex(index["pid"]).fillna(0).to_numpy(np.float32)


def performance_key(index, performance):
    """강도·지속력 요구를 정렬 키 둘로 바꾼다. (np.ndarray, np.ndarray) 또는 None.

    반환 `(present, value)`
        present  데이터가 있는가. **없는 것을 맨 뒤로 보낸다** — 사용자 결정(2026-09-16)
        value    정렬할 값. HIGH 면 그대로, LOW 면 부호를 뒤집는다

    **MEDIUM 과 빈 문자열은 None 이다** — 방향이 없어 순서를 정할 수 없다.
    None 이면 `rank` 가 원본과 완전히 같은 정렬을 한다.

    왜 `present` 가 필요한가 — `sillage_avg == 0` 은 "확산력이 0" 이 아니라 **평가가
    없어서 0** 이다(22,164개 · 16.8% · people 중앙값 1 · people>=10 비율 0.1%).
    이걸 그냥 값으로 쓰면 `LOW` 요구에서 데이터 없는 향수가 "가장 약한 향수" 로
    1등이 된다. 다만 엔진이 `people >= 10` 으로 이미 걸러서, 실제로 터지는 곳은
    평가자 문턱을 해제하는 마지막 완화 단계뿐이다.
    """
    p = performance or {}
    for field, column in (("intensity", "sillage"), ("longevity", "longevity")):
        want = str(p.get(field) or "").strip().upper()
        if want in ("HIGH", "LOW"):
            col = index[column]
            present = (col > 0).astype(np.float32)
            return present, (col if want == "HIGH" else -col)
    return None


def rank(index, mask, score, top_k, brand_cap, second=None):
    """엔진 `_rank` 복제 + 2차 키. dict.

    `second is None` 이면 `keys` 가 원본과 글자 그대로 같아진다.
    """
    idx = np.flatnonzero(mask)
    if idx.size == 0:
        return {"rows": [], "candidate_count": 0, "tie_at_last": 0}
    # lexsort 는 **마지막 원소가 1순위**다. 아래 순서가 그대로 우선순위가 된다.
    #   -score(1) · -present(2) · -value(3) · -people(4) · pid(5)
    keys = [index["pid"][idx], -index["people"][idx]]
    if second is not None:
        present, value = second
        keys.append(-value[idx])        # 3순위 — 강도 값
        keys.append(-present[idx])      # 2순위 — 데이터 있는 것을 먼저
    keys.append(-score[idx])            # 1순위 — 향 조건은 여전히 맨 위다
    idx = idx[np.lexsort(tuple(keys))]
    sorted_score = score[idx]
    cut = min(top_k, len(idx)) - 1
    tie = int((sorted_score == sorted_score[cut]).sum())
    rows, seen = [], {}
    for row in idx:
        brand = index["brand"][row]
        if brand_cap and seen.get(brand, 0) >= brand_cap:
            continue
        seen[brand] = seen.get(brand, 0) + 1
        rows.append(int(row))
        if len(rows) >= top_k:
            break
    return {"rows": rows, "candidate_count": int(idx.size), "tie_at_last": tie}


def search(index, core, avoid=(), top_k=5, people_min=10, brand_cap=1,
           min_results=3, performance=None):
    """엔진 `search` 복제 + performance 훅. dict."""
    second = performance_key(index, performance)
    cols = [index["aidx"][a] for a in core if a in index["aidx"]]
    if not cols:
        return {"rows": [], "stage": "NO_CONDITION", "candidate_count": 0,
                "tie_at_last": 0, "relaxed": []}
    min_results = min(min_results, top_k)
    base = index["people"] >= people_min
    for accord in avoid:
        col = index["aidx"].get(accord)
        if col is not None:
            base &= ~index["has"][:, col]
    score = index["strength"][:, cols].sum(axis=1)

    if len(cols) == 1:
        picked = rank(index, base & index["has"][:, cols[0]], score, top_k, brand_cap, second)
        if len(picked["rows"]) >= min_results:
            picked["stage"] = "SINGLE_BROAD"
            return picked
    if len(cols) >= nlr_engine.MIN_CORE_FOR_AND:
        mask = base.copy()
        for col in cols:
            mask &= index["has"][:, col]
        picked = rank(index, mask, score, top_k, brand_cap, second)
        if len(picked["rows"]) >= min_results:
            picked["stage"] = "AND"
            return picked
    picked = rank(index, base & index["has"][:, cols].any(axis=1), score,
                  top_k, brand_cap, second)
    if len(picked["rows"]) >= min_results:
        picked["stage"] = "RELAXED_OR"
        return picked
    mask = np.ones(index["n_perfumes"], dtype=bool)
    for accord in avoid:
        col = index["aidx"].get(accord)
        if col is not None:
            mask &= ~index["has"][:, col]
    mask &= index["has"][:, cols].any(axis=1)
    picked = rank(index, mask, score, top_k, brand_cap, second)
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
    """현행 파이프라인으로 조건을 만든다. (list, set, dict)."""
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
    avoid = set()
    for raw in ((o or {}).get("avoid") or []):
        a = nlr_engine._normalize_accord(index, raw)
        if a:
            avoid.add(a)
    return sorted(core - avoid), avoid, (o or {}).get("performance") or {}


def load_synth():
    d = pd.read_csv(SYNTH[1])
    out = []
    for r in d.to_dict("records"):
        try:
            o = json.loads(r["raw_response"])
        except Exception:
            o = None
        out.append((str(r[SYNTH[2]]), o if isinstance(o, dict) else None,
                    int(r["perfume_id"])))
    return out


def main():
    spec = importlib.util.spec_from_file_location("ndcg41", "41_lexicon_ndcg.py")
    ndcg41 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ndcg41)
    key = pd.read_csv(ANSWER_KEY).set_index("perfume_id")
    index = nlr_engine.load_index(lexicon_csv=LEXICON)
    attach_strength(index)
    rows = load_synth()
    print(f"향수 {index['n_perfumes']:,}개 · 문장 {len(rows)}건")
    print(f"sillage 결측 {int((index['sillage'] == 0).sum()):,} · "
          f"longevity 결측 {int((index['longevity'] == 0).sum()):,}\n")

    # ------------------------------------------------------------------
    print("=" * 88)
    print("[0] 안전성 — 강도 요구가 **없는** 문장에서 결과가 바뀌는가")
    print("=" * 88)
    no_perf = changed = 0
    for text, o, _ in rows:
        core, avoid, perf = conditions(index, text, o)
        if performance_key(index, perf) is not None:
            continue
        no_perf += 1
        a = nlr_engine.search(index, core, avoid)
        b = search(index, core, avoid, performance=perf)
        if a["rows"] != b["rows"] or a["stage"] != b["stage"]:
            changed += 1
    print(f"    강도 요구 없는 문장 {no_perf}/{len(rows)}건 중 결과가 바뀐 것 {changed}건"
          f"{'   ← 패치 불합격' if changed else '   OK'}")
    if changed:
        return

    # ------------------------------------------------------------------
    print()
    print("=" * 88)
    print("[1] 지금 프롬프트(v1) 출력으로 — 합성 600건")
    print("=" * 88)

    def run(recs, use_perf):
        st = collections.Counter()
        nd, moved, pk = [], 0, 0
        for text, o, pid in recs:
            core, avoid, perf = conditions(index, text, o)
            if performance_key(index, perf) is not None:
                pk += 1
            a = nlr_engine.search(index, core, avoid)
            b = search(index, core, avoid, performance=perf if use_perf else None)
            f = b if use_perf else a
            st[status_of(f)] += 1
            if use_perf and a["rows"] != b["rows"]:
                moved += 1
            if pid is not None:
                C = [x for x in str(key.loc[pid, "C"]).split("|") if x in index["aidx"]]
                if C:
                    cc = [index["aidx"][x] for x in C]
                    nd.append(ndcg41.ndcg_at_k(
                        [int(index["has"][r, cc].sum()) for r in f["rows"]], len(C)))
        return {"status": st, "ndcg": float(np.mean(nd)) if nd else None,
                "moved": moved, "keyed": pk}

    off = run(rows, False)
    on = run(rows, True)
    order = ["OK", "OK_RELAXED", "NO_CONDITION", "NO_RESULT"]
    print(f"    강도 키가 생기는 문장 {on['keyed']}/{len(rows)} ({on['keyed']/len(rows):.1%})")
    print(f"    추천 목록이 바뀐 문장 {on['moved']}건")
    print(f"    NDCG@5  {off['ndcg']:.6f} -> {on['ndcg']:.6f}  ({on['ndcg']-off['ndcg']:+.6f})")
    print(f"    {'':10s}" + " ".join(f"{s:>14s}" for s in order))
    print(f"    {'끄고':10s}" + " ".join(f"{off['status'][s]:>14d}" for s in order))
    print(f"    {'켜고':10s}" + " ".join(
        f"{on['status'][s]:>7d}({on['status'][s]-off['status'][s]:+5d})" for s in order))

    # ------------------------------------------------------------------
    print()
    print("=" * 88)
    print("[2] v4 프롬프트 출력으로 — 강도 부정 문장 65건")
    print("=" * 88)
    v4 = pd.read_csv(V4)
    recs = []
    synth_idx = {i: r for i, r in enumerate(rows)}
    for r in v4.to_dict("records"):
        if not r["ok"] or r["source"] != "합성":
            continue
        base = synth_idx.get(int(r["row"]))
        if base is None:
            continue
        recs.append((str(r["sentence"]), json.loads(r["v2_response"]), base[2]))
    v1recs = [(s, synth_idx[int(r['row'])][1], synth_idx[int(r['row'])][2])
              for s, r in zip([str(x["sentence"]) for x in v4.to_dict("records")
                               if x["ok"] and x["source"] == "합성"],
                              [x for x in v4.to_dict("records")
                               if x["ok"] and x["source"] == "합성"])]
    print(f"    합성 {len(recs)}건")
    for label, rr in (("v1 출력", v1recs), ("v4 출력", recs)):
        o1, o2 = run(rr, False), run(rr, True)
        print(f"    {label}  강도 키 {o2['keyed']:>2d}/{len(rr)} · 목록 바뀜 {o2['moved']:>2d}건 · "
              f"NDCG {o1['ndcg']:.6f} -> {o2['ndcg']:.6f} ({o2['ndcg']-o1['ndcg']:+.6f})")
        print(f"              status " + " ".join(
            f"{s}={o2['status'][s]}({o2['status'][s]-o1['status'][s]:+d})" for s in order))

    # ------------------------------------------------------------------
    print()
    print("=" * 88)
    print("[3] 결측 처리 — LOW 요구 결과에 데이터 없는 향수가 들어가는가")
    print("=" * 88)
    low_n = bad_rows = 0
    for text, o, _ in rows:
        core, avoid, perf = conditions(index, text, o)
        want = str((perf or {}).get("intensity") or "").strip().upper()
        if want != "LOW":
            continue
        low_n += 1
        f = search(index, core, avoid, performance=perf)
        bad_rows += sum(1 for r in f["rows"] if index["sillage"][r] == 0)
    print(f"    intensity=LOW 문장 {low_n}건 · 결과에 들어간 sillage==0 향수 {bad_rows}개"
          f"{'   ← 아직 샌다' if bad_rows else '   OK'}")
    print(f"    참고 — sillage==0 향수 {int((index['sillage'] == 0).sum()):,}개 중 "
          f"people>=10 인 것 "
          f"{int(((index['sillage'] == 0) & (index['people'] >= 10)).sum()):,}개")

    print()
    print("=" * 88)
    print("[4] 실제로 무엇이 바뀌나 — 5건")
    print("=" * 88)
    shown = 0
    for text, o, _ in rows:
        if shown >= 5:
            break
        core, avoid, perf = conditions(index, text, o)
        if performance_key(index, perf) is None:
            continue
        a = nlr_engine.search(index, core, avoid)
        b = search(index, core, avoid, performance=perf)
        if a["rows"] == b["rows"]:
            continue
        print(f"\n    \"{text[:50]}\"  {perf}")
        for tag, f in (("끄고", a), ("켜고", b)):
            names = [f"{index['brand'][r]} {index['name'][r]}"[:34] for r in f["rows"][:3]]
            sils = [f"{index['sillage'][r]:.1f}" for r in f["rows"][:3]]
            print(f"       {tag}  " + " · ".join(f"{n}({s})" for n, s in zip(names, sils)))
        shown += 1


if __name__ == "__main__":
    main()

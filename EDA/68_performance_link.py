"""①단계 `performance` 칸을 향수의 강도 데이터에 연결하면 무엇이 달라지는지 잰다.

    ./venv/Scripts/python.exe 68_performance_link.py

GMS 호출 0회. 팀 저장소를 수정하지 않는다.

왜 재는가
----------
14번이 결함 셋을 찾았는데 셋째를 아무도 안 봤다.

    칸                채워진 문장   엔진이 읽는가
    scent_preference      74.2%    읽음
    additional_requirements 98.5%   읽음
    avoid                  9.0%    읽음
    context                27.2%   **안 읽음**
    performance            11.2%   **안 읽음**

그리고 부정 문구를 파다가 이 칸이 왜 중요한지 드러났다. 부정 대상 88회 중 **70회(79.5%)가
사전에 없는 것**을 부정하는데, 그게 전부 강도·질감이다.

    무겁 13 · 가볍 9 · 답답 8 · 진 · 강 · 부담스럽 ...

**accord 92개에 `heavy` 도 `light` 도 `strong` 도 없다.** 향 계열 목록이지 강도 목록이
아니다. 그래서 사전에 넣을 수도 없고, 이 층위는 `performance` 로 풀어야 한다.

무엇을 못 재는지 먼저 밝힌다
------------------------------
**NDCG 로는 이 연결의 이득을 잴 수 없다.** 정답 키 `C` 가 accord 집합이라 강도 정보가
없다. N11 한계 2번·N12 Trade-off 와 같은 구조다.

그래서 재는 것은 "좋아졌는가" 가 아니라 이것이다.

    얼마나 많은 요청이 영향받는가
    해를 끼치지 않는가 — `status` 분포와 NDCG 가 guardrail 이다
    후보가 얼마나 줄어드는가

연결 방식 둘
-------------
    F  조건(필터)   intensity=HIGH 면 sillage_avg >= 문턱 인 향수만 본다
    R  정렬 2차 키  후보는 그대로 두고 순서에서 sillage 를 먼저 본다

**R 은 계수가 필요 없다.** `_rank` 가 `lexsort((pid, -people, -score))` 로 점수 -> 평가자
수 -> id 순서를 쓰는데, 거기에 sillage 를 끼워 넣기만 한다. N11·N12 가 계수를 정할 근거가
없다고 한 문제를 피한다. 다만 **N9(정렬 규칙)를 다시 여는 일**이다.

문턱을 하나로 정하지 않는다. sillage_avg 백분위 50·75·90 을 다 싣는다.

배포 관점 — 코드만 고치는 일이 아니다
---------------------------------------
`perfumes_nlr.csv.gz` 컬럼이 `id · name · brand · rating_avg · people · accords` 6개뿐이고
**sillage·longevity 가 없다.** 연결하려면 `build_load_files.py` 를 고쳐 데이터 파일을
다시 만들어야 한다.

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
SURVEY = ("설문 155", "analysis_outputs/37_survey_stage1_checkpoint.csv", "query_text")
ANSWER_KEY = "analysis_outputs/32_evalset_answer_key.csv"
LEXICON = "data/scent_knowledge/domain_lexicon_v1_14.csv"
PERFUMES = "perfumes.csv"


def load_strength(index):
    """향수별 sillage·longevity 를 엔진 인덱스 순서에 맞춘다. (np.ndarray, np.ndarray)."""
    d = pd.read_csv(PERFUMES, usecols=["id", "sillage_avg", "longevity_avg"],
                    low_memory=False).set_index("id")
    sil = d["sillage_avg"].reindex(index["pid"]).fillna(0).to_numpy(dtype=np.float32)
    lon = d["longevity_avg"].reindex(index["pid"]).fillna(0).to_numpy(dtype=np.float32)
    return sil, lon


def rank(index, mask, score, second, top_k=5, brand_cap=1):
    """엔진 `_rank` 복제. second 가 있으면 2차 키로 끼워 넣는다. dict.

    원본 순서 — 점수 내림 · 평가자 수 내림 · id 오름
    변형 순서 — 점수 내림 · **second 내림** · 평가자 수 내림 · id 오름
    """
    idx = np.flatnonzero(mask)
    if idx.size == 0:
        return {"rows": [], "candidate_count": 0}
    keys = [index["pid"][idx], -index["people"][idx]]
    if second is not None:
        keys.append(-second[idx])
    keys.append(-score[idx])
    idx = idx[np.lexsort(tuple(keys))]
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


def search(index, core, avoid=(), extra_mask=None, second=None,
           top_k=5, people_min=10, min_results=3):
    """엔진 `search` 복제 + 강도 필터·정렬 훅. dict.

    extra_mask : np.ndarray | None   후보를 더 좁히는 불린 마스크 (강도 필터)
    second     : np.ndarray | None   정렬 2차 키
    """
    cols = [index["aidx"][a] for a in core if a in index["aidx"]]
    if not cols:
        return {"rows": [], "stage": "NO_CONDITION", "candidate_count": 0}
    min_results = min(min_results, top_k)
    base = index["people"] >= people_min
    for accord in avoid:
        col = index["aidx"].get(accord)
        if col is not None:
            base &= ~index["has"][:, col]
    if extra_mask is not None:
        base = base & extra_mask
    score = index["strength"][:, cols].sum(axis=1)

    if len(cols) == 1:
        picked = rank(index, base & index["has"][:, cols[0]], score, second, top_k)
        if len(picked["rows"]) >= min_results:
            picked["stage"] = "SINGLE_BROAD"
            return picked
    if len(cols) >= 2:
        mask = base.copy()
        for col in cols:
            mask &= index["has"][:, col]
        picked = rank(index, mask, score, second, top_k)
        if len(picked["rows"]) >= min_results:
            picked["stage"] = "AND"
            return picked
    picked = rank(index, base & index["has"][:, cols].any(axis=1), score, second, top_k)
    if len(picked["rows"]) >= min_results:
        picked["stage"] = "RELAXED_OR"
        return picked
    mask = np.ones(index["n_perfumes"], dtype=bool)
    for accord in avoid:
        col = index["aidx"].get(accord)
        if col is not None:
            mask &= ~index["has"][:, col]
    if extra_mask is not None:
        mask &= extra_mask
    mask &= index["has"][:, cols].any(axis=1)
    picked = rank(index, mask, score, second, top_k)
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


def load(path, col):
    d = pd.read_csv(path)
    out = []
    for r in d.to_dict("records"):
        try:
            o = json.loads(r["raw_response"])
        except Exception:
            o = None
        pid = int(r["perfume_id"]) if "perfume_id" in r and pd.notna(r["perfume_id"]) else None
        out.append((str(r[col]), o if isinstance(o, dict) else None, pid))
    return out


def conditions(index, text, o):
    """현행 파이프라인으로 조건을 만든다. (list, set)."""
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
    return sorted(core - avoid), avoid


def main():
    spec = importlib.util.spec_from_file_location("ndcg41", "41_lexicon_ndcg.py")
    ndcg41 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ndcg41)
    key = pd.read_csv(ANSWER_KEY).set_index("perfume_id")
    index = nlr_engine.load_index(lexicon_csv=LEXICON)
    sil, lon = load_strength(index)

    ths = {q: float(np.percentile(sil[sil > 0], q)) for q in (50, 75, 90)}
    lths = {q: float(np.percentile(lon[lon > 0], q)) for q in (50, 75, 90)}
    print("sillage_avg 백분위  " + " · ".join(f"p{q}={v:.2f}" for q, v in ths.items()))
    print("longevity_avg 백분위 " + " · ".join(f"p{q}={v:.2f}" for q, v in lths.items()))
    print()

    # ------------------------------------------------------------------
    # 복제 검증 — 원본과 불일치가 0 이어야 비교가 성립한다 (58번 선례)
    rows = load(*SYNTH[1:])
    bad = 0
    for text, o, _ in rows:
        core, avoid = conditions(index, text, o)
        a = nlr_engine.search(index, core, avoid)
        b = search(index, core, avoid)
        if a["rows"] != b["rows"] or a["stage"] != b["stage"]:
            bad += 1
    print(f"[0] 복제 검증 — 원본 `search()` 와 불일치 {bad}/{len(rows)}건"
          f"{'  ← 비교 불가' if bad else '  OK'}\n")
    if bad:
        return

    VAR = [("A 현행", None, None)]
    for q in (50, 75, 90):
        VAR.append((f"F{q} 필터 p{q}", q, None))
    VAR.append(("R 정렬 2차키", None, "rank"))

    for name, path, col in (SYNTH, SURVEY):
        rows = load(path, col)
        n = len(rows)
        has_key = rows[0][2] is not None
        n_perf = sum(1 for _, o, _ in rows
                     if o and any((o.get("performance") or {}).get(k)
                                  for k in ("intensity", "longevity")))
        print("=" * 92)
        print(f"[{name}] {n}건 · `performance` 가 채워진 문장 {n_perf}건 ({n_perf/n:.1%})"
              + ("" if has_key else "  — 정답 라벨 없음"))
        print("=" * 92)

        base_status, base_ndcg = None, None
        print(f"    {'변형':16s} {'영향받은 문장':>12s} {'평균 후보':>11s} "
              f"{'NDCG@5':>10s} {'vs A':>11s}")
        results = []
        for label, q, mode in VAR:
            ndcgs, cands, touched = [], [], 0
            statuses = collections.Counter()
            for text, o, pid in rows:
                core, avoid = conditions(index, text, o)
                p = (o or {}).get("performance") or {}
                inten, longe = str(p.get("intensity") or ""), str(p.get("longevity") or "")
                extra, second = None, None
                if inten or longe:
                    if q is not None:
                        m = np.ones(index["n_perfumes"], dtype=bool)
                        if inten == "HIGH":
                            m &= sil >= ths[q]
                        elif inten == "LOW":
                            m &= (sil <= ths[50]) & (sil > 0)
                        if longe == "HIGH":
                            m &= lon >= lths[q]
                        elif longe == "LOW":
                            m &= (lon <= lths[50]) & (lon > 0)
                        extra = m
                        touched += 1
                    elif mode == "rank":
                        if inten == "HIGH" or longe == "HIGH":
                            second = sil if inten else lon
                            touched += 1
                        elif inten == "LOW" or longe == "LOW":
                            second = -(sil if inten else lon)
                            touched += 1
                found = search(index, core, avoid, extra, second)
                statuses[status_of(found)] += 1
                cands.append(found["candidate_count"])
                if has_key and pid is not None:
                    C = [a for a in str(key.loc[pid, "C"]).split("|") if a in index["aidx"]]
                    if C:
                        cc = [index["aidx"][a] for a in C]
                        ndcgs.append(ndcg41.ndcg_at_k(
                            [int(index["has"][r, cc].sum()) for r in found["rows"]], len(C)))
            nd = float(np.mean(ndcgs)) if ndcgs else None
            if base_ndcg is None:
                base_ndcg, base_status = nd, statuses
            print(f"    {label:16s} {touched:>12d} {np.mean(cands):>11.0f} "
                  f"{(f'{nd:.6f}' if nd is not None else '—'):>10s} "
                  f"{(f'{nd-base_ndcg:+.6f}' if nd is not None else '—'):>11s}")
            results.append((label, statuses))

        print()
        order = ["OK", "OK_RELAXED", "NO_CONDITION", "NO_RESULT"]
        print(f"    {'변형':16s} " + " ".join(f"{s:>13s}" for s in order))
        for label, st in results:
            if st is base_status:
                print(f"    {label:16s} " + " ".join(f"{st[s]:>13d}" for s in order))
            else:
                print(f"    {label:16s} " + " ".join(
                    f"{st[s]:>6d}({st[s]-base_status[s]:+5d})" for s in order))
        print()


if __name__ == "__main__":
    main()

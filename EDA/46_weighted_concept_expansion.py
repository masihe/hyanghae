"""표현을 accord 조합으로 넓히고 IDF 로 가중했을 때 추천이 어떻게 달라지는지 본다.

    ./venv/Scripts/python.exe 46_weighted_concept_expansion.py

API 호출 0회. 사전과 엔진을 건드리지 않는다 — 계산은 이 파일 안에서만 한다.

무엇을 보려는가
---------------
지금 사전은 한 표현에 accord 를 1~2개만 연결한다. 그런데 30번 측정에는 **사전에 없는
accord 중 신호가 잡힌 것**이 남아 있다. 예를 들어 `빨래` 는 2개인데 배수가 지지하는
accord 가 6개다(aldehydic · aquatic · musky · ozonic · white floral 이 빠져 있다).

왜 안 넣었나 — **하드 AND 때문이다.** 전부 가진 향수만 통과시키므로 accord 를 늘릴수록
후보가 곱으로 줄어 0 이 된다. 즉 사전이 작은 것은 지식이 부족해서가 아니라 검색 방식이
좁아서다. `rank` 컬럼(1·2·3)이 그 흔적이다 — 세기 차이를 알고 있었지만 적을 자리가 없었다.

그래서 셋을 비교한다
--------------------
현재        사전의 accord 로 하드 AND. strength 합으로 정렬        지금 서비스
확장+AND    지지받는 accord 를 전부 AND                          후보가 얼마나 죽는가
확장+가중    같은 accord 를 IDF 가중 점수로                       후보가 안 죽는가

가중치를 IDF 로 두는 이유
-------------------------
배수(lift)를 쓰려 했으나 구멍이 많았다 — 순환 4칸 · 반증 3칸 · 미측정 다수. 그리고
`ai_summary` 는 평가자 중앙 628명인 향수에만 붙어 **롱테일에 보증할 수 없다**(30번 본문).

IDF 는 향수 129,161개 전체로 계산되고 구멍이 없다. 뜻도 다르다.

    배수   "이 표현으로 불린 향수에 이 accord 가 유난히 많다"   -> 넣을지 말지
    IDF    "이 accord 가 드물어서 변별력이 있다"                -> 넣은 것들의 비중

향 지도가 이미 note IDF 자카드를 거리에 쓴다. 새 기법이 아니다.

**IDF 는 의미를 모른다.** 드물다는 것과 그 표현과 관련 있다는 것은 다르다. 그래서
넣을 accord 는 배수로 고르고 비중만 IDF 로 둔다.

출력 없음. 표준출력에만 쓴다.
"""
import math
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "C:/Users/SSAFY/Desktop/S15P21E203/ai")
import nlr_engine  # noqa: E402

LIFT = "analysis_outputs/30_expression_accord_lift.csv"
TOP_K = nlr_engine.TOP_K


def expansion_sets(index):
    """표현마다 (사전 accord, 확장 accord) 를 낸다. dict[str, tuple[list, list]].

    확장 = 사전 accord + 배수가 지지하는 accord(신호 True · 순환 아님)
    """
    lex = pd.read_csv(nlr_engine.DEFAULT_LEXICON, keep_default_na=False, dtype=str)
    core = lex[(lex["required"] == "core") & (lex["candidate_type"] == "ACCORD")
               & (lex["target_field"] != "NO_MAPPING")]
    current = {e: sorted(set(g["candidate_name"]) & set(index["aidx"]))
               for e, g in core.groupby("expression")}

    lift = pd.read_csv(LIFT)
    supported = lift[(lift["신호"] == True) & (lift["순환"] != True)]  # noqa: E712
    out = {}
    for expr, base in current.items():
        extra = sorted(set(supported[supported["표현"] == expr]["accord"]) & set(index["aidx"]))
        merged = sorted(set(base) | set(extra))
        if len(merged) > len(base):
            out[expr] = (base, merged)
    return out


def idf_weights(index, accords):
    """accord 별 IDF 를 정규화해 비중으로. dict[str, float]."""
    total_perfumes = index["n_perfumes"]
    raw = {}
    for accord in accords:
        have = int(index["has"][:, index["aidx"][accord]].sum())
        raw[accord] = math.log(total_perfumes / max(have, 1))
    scale = sum(raw.values())
    return {a: v / scale for a, v in raw.items()}


def rank_rows(index, mask, score, top_k=TOP_K, brand_cap=nlr_engine.BRAND_CAP):
    """엔진과 같은 순서로 상위를 고른다. (list[int], int).

    1순위 점수 · 2순위 평가자 수 · 3순위 id. 브랜드당 1개. search_rules.md ③ 그대로.
    """
    idx = np.flatnonzero(mask)
    if idx.size == 0:
        return [], 0
    order = np.lexsort((index["pid"][idx], -index["people"][idx], -score[idx]))
    idx = idx[order]
    rows, seen = [], {}
    for row in idx:
        brand = index["brand"][row]
        if brand_cap and seen.get(brand, 0) >= brand_cap:
            continue
        seen[brand] = seen.get(brand, 0) + 1
        rows.append(int(row))
        if len(rows) >= top_k:
            break
    return rows, int(idx.size)


def hard_and(index, accords):
    """하드 AND. (rows, 후보 수)."""
    mask = index["people"] >= nlr_engine.PEOPLE_MIN
    for accord in accords:
        mask = mask & index["has"][:, index["aidx"][accord]]
    cols = [index["aidx"][a] for a in accords]
    return rank_rows(index, mask, index["strength"][:, cols].sum(axis=1))


def weighted(index, accords):
    """IDF 가중 점수. AND 를 걸지 않는다. (rows, 후보 수)."""
    weights = idf_weights(index, accords)
    score = np.zeros(index["n_perfumes"], dtype=np.float32)
    for accord, weight in weights.items():
        score += weight * index["strength"][:, index["aidx"][accord]] / 100.0
    mask = (index["people"] >= nlr_engine.PEOPLE_MIN) & (score > 0)
    return rank_rows(index, mask, score)


def show(index, label, rows, candidates, weights=None):
    """상위 목록을 한 줄씩. None."""
    print(f"      {label:14s} 후보 {candidates:>7,}")
    for rank, row in enumerate(rows, 1):
        detail = ""
        if weights:
            parts = [(a, float(index["strength"][row, index["aidx"][a]])) for a in weights]
            detail = " ".join(f"{a}={int(v)}" for a, v in sorted(parts, key=lambda p: -p[1])[:4])
        print(f"         {rank}. {str(index['name'][row])[:30]:32s} "
              f"{str(index['brand'][row])[:18]:20s} 평가자 {int(index['people'][row]):>6,}  {detail}")


def main():
    """확장 대상 표현마다 세 방식을 비교한다. None."""
    index = nlr_engine.load_index()
    targets = expansion_sets(index)
    print(f"향수 {index['n_perfumes']:,} · 확장 근거가 있는 표현 {len(targets)}개\n")

    for expr, (base, merged) in targets.items():
        weights = idf_weights(index, merged)
        print(f"[{expr}]  사전 {base}  ->  확장 {merged}")
        print("      IDF 비중  " + " · ".join(
            f"{a} {weights[a]:.0%}" for a in sorted(weights, key=lambda a: -weights[a])))

        base_rows, base_n = hard_and(index, base)
        and_rows, and_n = hard_and(index, merged)
        w_rows, w_n = weighted(index, merged)

        show(index, "현재(AND)", base_rows, base_n, base)
        show(index, "확장+AND", and_rows, and_n, merged)
        show(index, "확장+가중", w_rows, w_n, merged)

        base_ids = {int(index["pid"][r]) for r in base_rows}
        print(f"      상위 5 겹침 — 확장+AND {len({int(index['pid'][r]) for r in and_rows} & base_ids)}/5"
              f" · 확장+가중 {len({int(index['pid'][r]) for r in w_rows} & base_ids)}/5")
        print()


if __name__ == "__main__":
    main()

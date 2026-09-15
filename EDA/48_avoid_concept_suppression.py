"""회피를 "직접 지목 accord 는 hard, 사전이 연결한 복합 표현은 concept 점수로 soft" 로 나눠 잰다.

    ./venv/Scripts/python.exe 48_avoid_concept_suppression.py

API 호출 0회. 저장된 LLM 구조화 결과 600건과 사전 v1.8 을 재사용한다. 사전·엔진 파일은
건드리지 않는다 — 이 파일 안에서만 대안 로직을 흉내낸다.

왜 다시 보는가
--------------
업로드된 레퍼런스 조사(`자연어 향수 추천의 회피 로직 설계`, 2026-09-15 외부 자료, ChatGPT
작성)가 Q1·Q2 에 이렇게 답했다.

    Q1  회피도 사전을 태운다. 단 relation 에 따라 hard/soft 를 가른다
    Q2  연결된 accord 를 전부 빼지 않는다. "표현이 데려온 개념" 자체를 억제한다
        (직접 지목한 accord/note 는 hard exclude, 여러 accord 가 모이는 감각 표현은
         concept score 를 억제)

지금 엔진은 이 둘 다 안 한다.

    1. `nlr_engine.understand()` 는 회피를 **accord 영어 이름 완전 일치로만** 푼다
       (`_normalize_accord`). 사전 경유 경로가 아예 없다 — 측정 기록 13 이 "가상 수치"라
       부른 8/59 가 프로덕션에는 없다는 뜻이다
    2. `nlr_engine.search()` 는 회피로 잡힌 accord 를 **무조건 전체 후보에서 제거**한다
       (`base &= ~has[:, col]`). 그 accord 가 아주 조금 있어도 통째로 빠진다.
       "전부 뺀다" 조차 아니고 "닿기만 해도 뺀다" 다

보고서의 권고를 실제로 켜려면 이 둘을 같이 만들어야 한다 — 사전 경유를 추가하고,
그중 복합 표현만 soft 로 바꾼다.

측정하는 것 셋
--------------
1. 59개 회피 문구를 HARD(직접 accord) / SOFT(사전이 연결한 복합 개념) / NO_MAP 으로 분류
2. SOFT 로 분류된 표현에서 "닿기만 해도 제거"(현재+사전경유를 하드로만 켰을 때)와
   "concept 점수로 감점"(soft) 이 실제 추천 결과를 어떻게 다르게 바꾸는가
3. 600문장 NDCG@5 — 현재 / 사전경유+전부하드(나이브 적용) / 사전경유+soft(보고서 권고)

출력 없음. 표준출력에만 쓴다.
"""
import importlib.util
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "C:/Users/SSAFY/Desktop/S15P21E203/ai")
import nlr_engine  # noqa: E402

CHECKPOINT = "analysis_outputs/34_evalset_stage1_checkpoint.csv"
ANSWER_KEY = "analysis_outputs/32_evalset_answer_key.csv"
LAMBDA = 1.0  # [제안] soft 감점 계수. strength 와 같은 척도로 1:1 빼는 값. 조정 근거 없음


# ---------------------------------------------------------------------------
# 1. 회피 표현 분류 — 보고서 Q1 결정 트리
# ---------------------------------------------------------------------------
def classify(index, term):
    """회피 문구 하나를 HARD/SOFT/NO_MAP 으로 가른다. (str, list[str]).

    HARD    사용자가 accord 이름을 직접 말함. 지금 엔진과 같은 경로
    SOFT    사전이 여러 accord 를 연결한 복합 표현. relation 이 EVOKES/ASSOCIATED_WITH
    HARD(사전) relation 이 PRODUCT_ATTRIBUTE — 보고서 표의 "조건부 O"
    NO_MAP  사전에도 accord 이름에도 닿지 않음
    """
    exact = nlr_engine._normalize_accord(index, term)
    if exact:
        return "HARD", [exact]

    hit = set()
    for form, expressions in index["lexicon_surface"].items():
        if form and form in term:
            hit |= expressions
    if not hit:
        return "NO_MAP", []

    rows = [row for name in hit
            for row in index["lexicon_by_expression"].get(name, [])
            if row["required"] == "core"]
    accords = sorted({row["candidate_name"] for row in rows})
    if not accords:
        return "NO_MAP", []
    relations = {row["relation_type"] for row in rows}
    if relations & {"PRODUCT_ATTRIBUTE"}:
        return "HARD", accords
    return "SOFT", accords


def avoid_terms_by_sentence():
    """저장된 구조화 결과에서 (문장, avoid 문구 리스트) 를 낸다. list[tuple]."""
    check = pd.read_csv(CHECKPOINT)
    out = []
    for row in check.to_dict("records"):
        try:
            conditions = nlr_engine_llm_validate(row["raw_response"])
        except Exception:
            continue
        out.append((row["sentence"], conditions))
    return out


def nlr_engine_llm_validate(raw_response):
    """43·44 번과 같은 방식으로 저장된 응답을 구조화 dict 로. dict."""
    import llm_stage1
    return llm_stage1.validate(llm_stage1.parse_content(raw_response))


def measure_classification(index):
    """59개 회피 문구의 분류 분포. dict[str, list[str]]."""
    rows = avoid_terms_by_sentence()
    terms = sorted({str(t) for _, c in rows for t in (c.get("avoid") or [])})
    by_label = {"HARD": [], "SOFT": [], "NO_MAP": []}
    detail = {}
    for term in terms:
        label, accords = classify(index, term)
        by_label[label].append(term)
        detail[term] = (label, accords)

    print(f"[1] 회피 문구 {len(terms)}개 분류 (보고서 Q1 결정 트리)")
    for label in ("HARD", "SOFT", "NO_MAP"):
        items = by_label[label]
        print(f"    {label:6s} {len(items):2d}개")
        if label != "NO_MAP":
            for t in items:
                print(f"        {t:20s} -> {detail[t][1]}")
    print()
    return detail


# ---------------------------------------------------------------------------
# 2·3. 대안 검색 — hard/soft 분리
# ---------------------------------------------------------------------------
def search_variant(index, core, hard_accords, soft_accords, mode, top_k=nlr_engine.TOP_K):
    """avoid 를 hard/soft 로 나눠 검색한다. (rows, 후보 수).

    mode  "현재"        지금 엔진과 동일 — hard_accords 만 쓴다 (soft 는 무시)
          "전부하드"     hard_accords + soft_accords 를 전부 하드로 제거 (나이브 적용)
          "soft"        hard_accords 는 제거, soft_accords 는 concept 점수로 감점

    core 는 이미 avoid 를 뺀 상태로 들어온다 (understand() 의 기존 동작 유지).
    완화 사다리는 없다 — 47번과 같은 이유로 41번 값과 직접 비교하지 않는다.
    """
    base = index["people"] >= nlr_engine.PEOPLE_MIN
    remove = list(hard_accords) if mode == "현재" else list(hard_accords) + (
        list(soft_accords) if mode == "전부하드" else [])
    for accord in remove:
        col = index["aidx"].get(accord)
        if col is not None:
            base &= ~index["has"][:, col]

    cols = [index["aidx"][a] for a in core if a in index["aidx"]]
    if not cols:
        return [], 0
    mask = base.copy()
    for col in cols:
        mask &= index["has"][:, col]

    score = index["strength"][:, cols].sum(axis=1)
    if mode == "soft" and soft_accords:
        penalty_cols = [index["aidx"][a] for a in soft_accords if a in index["aidx"]]
        if penalty_cols:
            score = score - LAMBDA * index["strength"][:, penalty_cols].sum(axis=1)

    idx = np.flatnonzero(mask)
    if idx.size == 0:
        return [], 0
    order = np.lexsort((index["pid"][idx], -index["people"][idx], -score[idx]))
    idx = idx[order]

    rows, seen = [], {}
    for row in idx:
        brand = index["brand"][row]
        if nlr_engine.BRAND_CAP and seen.get(brand, 0) >= nlr_engine.BRAND_CAP:
            continue
        seen[brand] = seen.get(brand, 0) + 1
        rows.append(int(row))
        if len(rows) >= top_k:
            break
    return rows, int(idx.size)


def split_avoid(index, detail, avoid_terms):
    """문장 하나의 avoid 문구들을 hard/soft accord 집합으로 나눈다. (set, set)."""
    hard, soft = set(), set()
    for term in avoid_terms:
        label, accords = detail.get(str(term), ("NO_MAP", []))
        if label == "HARD":
            hard.update(accords)
        elif label == "SOFT":
            soft.update(accords)
    return hard, soft


def show_examples(index, detail):
    """SOFT 로 분류된 표현이 실제로 무엇을 바꾸는지 예시로 보여준다. None."""
    rows = avoid_terms_by_sentence()
    soft_terms = {t for t, (label, _) in detail.items() if label == "SOFT"}
    if not soft_terms:
        print("[2] SOFT 로 분류된 표현이 없다 — 비교할 예시가 없다\n")
        return

    print(f"[2] SOFT 표현 예시 — '닿기만 해도 제거' vs 'concept 점수로 감점'\n")
    shown = 0
    for text, conditions in rows:
        avoid = [str(t) for t in (conditions.get("avoid") or [])]
        hit = [t for t in avoid if t in soft_terms]
        if not hit or shown >= 4:
            continue
        understood = nlr_engine.understand(index, text, conditions)
        hard, soft = split_avoid(index, detail, avoid)

        print(f"  '{text[:50]}'  회피={avoid}")
        for mode in ("현재", "전부하드", "soft"):
            rows_, n = search_variant(index, understood["core"], hard, soft, mode)
            names = [str(index["name"][r])[:24] for r in rows_[:3]]
            print(f"    {mode:6s} 후보 {n:>6,}  상위 3  {names}")
        print()
        shown += 1
    print()


def measure_evalset(index, detail):
    """600문장 NDCG@5 — 현재 / 전부하드 / soft. None."""
    spec = importlib.util.spec_from_file_location("ndcg41", "41_lexicon_ndcg.py")
    ndcg41 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ndcg41)
    queries = ndcg41.load_queries()
    key = pd.read_csv(ANSWER_KEY).set_index("perfume_id")

    print("[3] 합성 600문장")
    for mode in ("현재", "전부하드", "soft"):
        scores, gains_all, affected = [], [], 0
        for text, conditions, answer_pid in queries:
            C = [a for a in str(key.loc[answer_pid, "C"]).split("|") if a in index["aidx"]]
            if not C:
                continue
            understood = nlr_engine.understand(index, text, conditions)
            avoid = [str(t) for t in (conditions.get("avoid") or [])] if conditions else []
            hard, soft = split_avoid(index, detail, avoid)
            affected += bool(soft)
            if not understood["core"]:
                scores.append(0.0)
                continue
            rows_, _ = search_variant(index, understood["core"], hard, soft, mode)
            cols = [index["aidx"][a] for a in C]
            gains = [int(index["has"][r, cols].sum()) for r in rows_]
            scores.append(ndcg41.ndcg_at_k(gains, len(C)))
            gains_all += [g / len(C) for g in gains]
        print(f"    {mode:6s} NDCG@5 {np.mean(scores):.4f}  "
              f"조건충족률 {np.mean(gains_all):.4f}  SOFT 표현이 있는 문장 {affected}")
    print()


def main():
    index = nlr_engine.load_index()
    print(f"향수 {index['n_perfumes']:,} · 사전 {nlr_engine.DEFAULT_LEXICON.name}\n")
    detail = measure_classification(index)
    show_examples(index, detail)
    measure_evalset(index, detail)


if __name__ == "__main__":
    main()

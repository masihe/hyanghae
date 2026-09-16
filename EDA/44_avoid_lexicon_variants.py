"""회피 정책을 정하기 전에 사전 변형 A·B 가 무엇을 바꾸는지 잰다.

    ./venv/Scripts/python.exe 44_avoid_lexicon_variants.py

API 호출 0회. 원본 사전을 덮어쓰지 않는다 — 변형은 임시 파일로만 만든다.

무엇을 정하려는가
-----------------
회피(avoid) 처리 규칙이 `spec.md` §8 11번에 미결로 남아 있다. 254 로 ①단계가 붙어
`avoid` 에 값이 들어오기 시작했고, 43번 측정에서 이런 상태가 확인됐다.

    avoid 항목 59개 중 accord 로 해석되는 것 7개 (12%)
    회피가 실제로 도는 문장 2건 — 둘 다 `달달`

레퍼런스 조사(2026-09-15)는 "component 를 삭제하는 대신 concept 를 회피한다" 를 권하고,
`relation_type` 으로 hard/soft 를 가르자고 한다. 그런데 우리 값 4종에는 직접 지칭을
뜻하는 값이 없다. `나무 -> woody` 는 N10 이 "직역 대응" 으로 판정했는데 `EVOKES` 다.

변형 둘
-------
A   `relation_type` 에 IDENTITY 를 더하고 N10 이 직역으로 판정한 5행을 재라벨
    과육 fruity · 꿀 sweet · 나무 woody · 상큼한 citrus · 풀 냄새 green

B   A + 엔진 상수 KOREAN_ACCORD 10종을 사전 항목으로 옮긴다
    바닐라 · 스위트 · 시트러스 · 아로마틱 · 앰버 · 파우더리 · 프레시 · 프루티 · 플로럴
    (`우디` 는 이미 `나무` 의 alias 라 제외)

**A 단독은 런타임 변화가 0 이다.** 엔진이 읽는 사전 컬럼은 8개뿐이고 `relation_type`
은 그중에 없다. 그래서 A 는 회피 정책과 함께여야 의미가 생긴다.

재는 것
-------
1. 선호 경로   커버리지 · 검색 단계 분포 · NDCG@5     A·B 가 기존 추천을 깨는가
2. 회피 도달   avoid 59개가 accord 에 닿는 비율        사전을 태우면 얼마나 느는가
3. 회피 정책   현재 / IDENTITY-hard / concept-필터     동작이 어떻게 갈리는가

출력 없음. 표준출력에만 쓴다.
"""
import collections
import importlib.util
import pathlib
import re
import sys
import tempfile

import pandas as pd

sys.path.insert(0, "C:/Users/SSAFY/Desktop/S15P21E203/ai")
import llm_stage1  # noqa: E402
import nlr_engine  # noqa: E402

LEXICON = pathlib.Path(nlr_engine.DEFAULT_LEXICON)
CHECKPOINT = "analysis_outputs/34_evalset_stage1_checkpoint.csv"
ANSWER_KEY = "analysis_outputs/32_evalset_answer_key.csv"

# N10 이 "직역 대응" 으로 판정한 다섯. 새 판단이 아니라 기존 판정을 옮기는 것이다.
DIRECT = {("과육", "fruity"), ("꿀", "sweet"), ("나무", "woody"),
          ("상큼한", "citrus"), ("풀 냄새", "green")}


def load_41():
    """41_lexicon_ndcg.py 의 채점 함수를 재사용한다. module."""
    spec = importlib.util.spec_from_file_location("ndcg41", "41_lexicon_ndcg.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# 사전 변형 — 원본을 덮어쓰지 않는다
# ---------------------------------------------------------------------------
def make_variant_a(base):
    """N10 직역 5행의 relation_type 을 IDENTITY 로. DataFrame."""
    out = base.copy()
    mask = out.apply(lambda r: (r["expression"], r["candidate_name"]) in DIRECT, axis=1)
    out.loc[mask, "relation_type"] = "IDENTITY"
    return out


def make_variant_b(variant_a):
    """A + KOREAN_ACCORD 음차를 사전 항목으로 더한다. DataFrame."""
    existing = set(variant_a["expression"])
    for surface in variant_a["aliases"]:
        existing |= {a for a in surface.split("|") if a}

    template = variant_a.iloc[0].to_dict()
    rows = []
    for korean, accord in nlr_engine.KOREAN_ACCORD.items():
        if korean in existing or korean.endswith("한"):
            continue          # 우디 는 이미 나무의 alias. '~한' 형은 기본형에 붙인다
        row = dict.fromkeys(template, "")
        row.update({
            "entry_id": f"kr.accord.{accord.replace(' ', '_')}",
            "expression": korean,
            "aliases": f"{korean}|{korean}한",
            "expression_type": "DIRECT_SCENT",
            "target_field": "STAGE1_DIRECT",
            "candidate_type": "ACCORD",
            "candidate_name": accord,
            "rank": "1",
            "required": "core",
            "match_condition": "",
            "rationale": "accord 이름의 한국어 음차. 엔진 상수 KOREAN_ACCORD 에서 옮겼다",
            "evidence_tier": "VERIFIED",
            "corpus_support": "",
            "standardness": "loanword",
            "status": "candidate",
            "source_query_ids": "",
            "source_type": "TEAM_DOC",
            "verification_status": "UNMEASURED",
            "relation_type": "IDENTITY",
        })
        rows.append(row)
    return pd.concat([variant_a, pd.DataFrame(rows)], ignore_index=True), len(rows)


# ---------------------------------------------------------------------------
# 1. 선호 경로 — A·B 가 기존 추천을 깨는가
# ---------------------------------------------------------------------------
def measure_preference(paths, ndcg41):
    """사전별 커버리지 · 단계 분포 · NDCG@5. None."""
    queries = ndcg41.load_queries()
    key = pd.read_csv(ANSWER_KEY).set_index("perfume_id")

    print("[1] 선호 경로 — 기존 추천이 깨지는가")
    print(f"    {'사전':10s} {'조건을 뽑은 문장':>14s} {'NDCG@5':>9s} {'조건충족률':>10s}   단계 분포")
    for label, path in paths.items():
        index = nlr_engine.load_index(lexicon_csv=path)
        stages = collections.Counter()
        got = 0
        for text, conditions, _ in queries:
            out = nlr_engine.recommend(index, text, conditions)
            stages[out["diagnostics"]["stage"]] += 1
            got += bool(out["conditions"]["core"])
        frame = ndcg41.score(path, queries, key)
        dist = " · ".join(f"{k} {v}" for k, v in sorted(stages.items()))
        print(f"    {label:10s} {got:>10d}/600 {frame['ndcg5'].mean():>9.4f} "
              f"{frame['gain_ratio'].mean():>10.4f}   {dist}")
    print()


# ---------------------------------------------------------------------------
# 2. 회피 도달 — 사전을 태우면 얼마나 느는가
# ---------------------------------------------------------------------------
def avoid_terms():
    """저장된 구조화 결과에서 avoid 항목을 모은다. list[str]."""
    check = pd.read_csv(CHECKPOINT)
    terms = []
    for row in check.to_dict("records"):
        try:
            conditions = llm_stage1.validate(llm_stage1.parse_content(row["raw_response"]))
        except llm_stage1.Stage1Error:
            continue
        terms += [str(t) for t in (conditions.get("avoid") or [])]
    return terms


def resolve_avoid(index, term):
    """회피 문구 하나를 accord 로 옮긴다. (경로, list[accord]).

    ① accord 이름과 완전히 일치     지금 엔진이 하는 유일한 경로
    ② 사전 표현이 문구 안에 있음     선호 경로가 쓰는 방식을 회피에도 적용
    ③ 닿지 못함
    """
    exact = nlr_engine._normalize_accord(index, term)
    if exact:
        return "① accord 직접", [exact]
    hit = set()
    for form, expressions in index["lexicon_surface"].items():
        if form and form in term:
            hit |= expressions
    accords = sorted({row["candidate_name"]
                      for name in hit
                      for row in index["lexicon_by_expression"].get(name, [])
                      if row["required"] == "core"})
    if accords:
        return "② 사전 경유", accords
    return "③ 닿지 못함", []


def measure_avoid_reach(paths):
    """사전별 회피 도달률. None."""
    terms = avoid_terms()
    print(f"[2] 회피 도달 — avoid 항목 {len(terms)}개가 accord 에 닿는가")
    for label, path in paths.items():
        index = nlr_engine.load_index(lexicon_csv=path)
        buckets = collections.Counter(resolve_avoid(index, t)[0] for t in terms)
        line = " · ".join(f"{k} {v}" for k, v in sorted(buckets.items()))
        reached = len(terms) - buckets["③ 닿지 못함"]
        print(f"    {label:10s} 닿음 {reached:2d}/{len(terms)} ({reached/len(terms):4.0%})   {line}")
    print()


# ---------------------------------------------------------------------------
# 3. 회피 정책 — IDENTITY 구분이 동작을 바꾸는가
# ---------------------------------------------------------------------------
def measure_policy(path):
    """세 정책이 같은 문장에서 어떻게 갈리는지. None.

    현재         accord 이름이 일치할 때만 뺀다
    IDENTITY-hard  IDENTITY 로 닿은 accord 만 뺀다. 나머지는 안 뺀다
    concept-필터   composite 는 accord 를 빼지 않고, 구성 accord 가 모두 강한 향수를 거른다
    """
    index = nlr_engine.load_index(lexicon_csv=path)
    lex = pd.read_csv(path, keep_default_na=False, dtype=str)
    rel = {(r["expression"], r["candidate_name"]): r["relation_type"]
           for r in lex.to_dict("records")}

    check = pd.read_csv(CHECKPOINT)
    print("[3] 회피 정책 — 같은 문장에서 무엇이 갈리는가")
    shown = 0
    for row in check.to_dict("records"):
        try:
            conditions = llm_stage1.validate(llm_stage1.parse_content(row["raw_response"]))
        except llm_stage1.Stage1Error:
            continue
        if not conditions.get("avoid"):
            continue
        text = row["sentence"]
        understood = nlr_engine.understand(index, text, conditions)
        if not understood["avoid"]:
            continue

        evidence = understood["evidence"]
        current = set(understood["core"])
        # 회피된 accord 를 데려온 표현과 그 relation
        sources = {(e["from"], e["accord"]) for e in evidence
                   if e["accord"] in set(understood["avoid"])}
        relations = {rel.get(s, "?") for s in sources}
        identity_only = {a for f, a in sources if rel.get((f, a)) == "IDENTITY"}

        print(f"    '{text[:46]}'")
        print(f"       avoid={conditions['avoid']} -> accord {understood['avoid']}")
        print(f"       회피 accord 의 근거 {sorted(sources)}  relation {sorted(relations)}")
        print(f"       현재          core {sorted(current)}")
        print(f"       IDENTITY-hard core {sorted(current | (set(understood['avoid']) - identity_only))}"
              f"   <- IDENTITY 가 아니면 되돌린다")
        shown += 1
        if shown >= 6:
            break
    print()


def main():
    """변형을 만들고 세 측정을 돌린다. None."""
    base = pd.read_csv(LEXICON, keep_default_na=False, dtype=str)
    variant_a = make_variant_a(base)
    variant_b, added = make_variant_b(variant_a)

    tmp = pathlib.Path(tempfile.mkdtemp(prefix="lexvar_"))
    paths = {"v1.8": str(LEXICON)}
    for label, frame in (("A", variant_a), ("B", variant_b)):
        out = tmp / f"lexicon_{label}.csv"
        frame.to_csv(out, index=False, encoding="utf-8-sig")
        paths[label] = str(out)

    print(f"원본 {len(base)}행 · A {len(variant_a)}행(재라벨 {len(DIRECT)}) "
          f"· B {len(variant_b)}행(추가 {added})")
    print(f"변형은 임시 폴더에만 만든다 — {tmp}")
    print()

    ndcg41 = load_41()
    measure_preference(paths, ndcg41)
    measure_avoid_reach(paths)
    measure_policy(paths["A"])


if __name__ == "__main__":
    main()

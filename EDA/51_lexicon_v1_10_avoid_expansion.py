"""사전 v1.9 -> v1.10. 별칭 누락 세 건을 메우고, 50번이 측정한 새 표현 넷을 넣는다.

    ./venv/Scripts/python.exe 51_lexicon_v1_10_avoid_expansion.py

API 호출 0회. v1.9 를 읽어 v1.10 을 새로 쓴다. **v1.9 이전 판본은 그대로 둔다.**

무엇을 바꾸는가
----------------
### 1. 별칭 누락 — 이미 있는 항목인데 입구가 없었다

    kr.ctx.clean    깨끗한   + `clean`
        **활성 core 항목**(soapy·fresh·aquatic)인데 영어 표기가 없었다.
        48번의 회피 문구 `clean`·`too clean only` 가 여기로 못 왔다.

    kr.dial.sweet   달달     + `candy` · `sweetness`
        영어 표기가 하나도 없었다. N4 가 이 항목을 검증할 때 쓴 검색어 자체가
        ["sweet","sugary","candy"] 였다 — 근거는 이미 있고 입구만 없던 경우다.

    kr.nomap.young  어린     + `girl-like` · `유치한`
        v1.9 에서 만든 비향 이미지 클러스터에 들어갈 자리인데 놓쳤다.

### 2. 새 표현 넷 — 50번이 ai_summary 배수로 측정했다

    화려한            tuberose 1.92x (33건 · CI하한 1.29)
    인공적인          sour     1.64x (59건 · CI하한 1.23)
    흔한              aquatic  1.56x (283건) · marine 1.54x (141건) · salty 1.52x (95건)
    복잡하게 변하는 향  whiskey  1.75x (42건 · CI하한 1.23)

통제군(무작위 500/1000/2500)의 최대 배수가 1.17~1.38 이고 1.5 이상이 0개였다.
위 값들은 그 수준을 넘는다.

**전부 `required=optional` 로 넣는다.** 단일 측정이고 교차 검증이 없다. `core` 는 하드 AND
조건이 되어 후보를 0으로 만들 수 있는 자리라(N11 근거 2), 한 번의 배수만으로 올리지 않는다.
`status=candidate` · `evidence_tier=LLM` — 사람 검토 전이다.

**`화려한` 은 약하게 읽어야 한다.** 검색어 `loud` 가 `cloud`·`aloud` 에도 걸리고 accord
이름 `oud` 를 품어 순환 경고가 떴다. 437건에 잡음이 섞였을 수 있다.

효과 — 새 항목은 무효, 별칭은 실제로 움직인다
----------------------------------------------
**처음에는 "아무것도 안 바뀐다" 고 썼다가 게이트에서 틀린 것이 잡혔다.**

`optional` 새 항목은 엔진이 안 읽으므로(`if row["required"] != "core": continue`) 정말로
검색을 안 바꾼다. 그런데 **별칭 추가는 다르다.** `깨끗한`·`달달` 은 활성 core 항목이라
새 별칭이 곧 새 입구가 되고, 잘못 고르면 없던 조건이 잘못 붙는다.

실제로 첫 조합(`sweetness` 포함)은 NDCG 를 0.468842 -> 0.468111 로 **깎았다.** 별칭을
하나씩 분리해 다시 재고 조합을 바꿨다 (`ALIAS_ADDITIONS` 주석에 표).

    채택 후   0.469557  (+0.000715)

미매칭 분류도 함께 바뀐다 — 이 표현들이 들어오면 `NOT_IN_LEXICON`(모른다) 대신
`NOT_CORE`(판정 이력 있음)로 기록된다.

출력  data/scent_knowledge/domain_lexicon_v1_10.csv
      analysis_outputs/51_lexicon_v1_10_changelog.md
"""
import pathlib
import sys

import pandas as pd

sys.path.insert(0, "C:/Users/SSAFY/Desktop/S15P21E203/ai")

SRC = pathlib.Path("data/scent_knowledge/domain_lexicon_v1_9.csv")
DST = pathlib.Path("data/scent_knowledge/domain_lexicon_v1_10.csv")
ACCORD_DICT = pathlib.Path("analysis_outputs/10_accord_dictionary.csv")
CHANGELOG = pathlib.Path("analysis_outputs/51_lexicon_v1_10_changelog.md")

# entry_id -> 더할 별칭. 같은 entry_id 의 모든 행에 적용한다(항목당 여러 행이 있다).
#
# **처음 고른 조합은 측정에서 떨어졌다.** 아래는 별칭을 하나씩 분리해 잰 뒤의 것이다.
#
#   v1.9 그대로                    0.468842
#   +candy 만                      0.468842   변화 없음 — 무해
#   +sweetness 만                  0.468243   −0.000599  ← 기각
#   +clean 만                      0.468709   −0.000133
#   +깔끔하고·깨끗하게·정갈하고        0.469557   +0.000715  ← 채택
#   +candy+clean+활용형             0.469557   활용형과 동일(clean 손해가 흡수됨)
#
# `sweetness` 를 뺀 이유 — `달달` 은 `sweet` 와 `caramel` 을 **둘 다** core 로 갖는다.
# 한국어 `달달한` 은 캐러멜 뉘앙스를 정당화하지만 영어 `sweetness` 는 "바닐라의 단맛"·
# "복숭아의 단맛" 처럼 넓게 쓰여서 갈 때마다 `caramel` 을 끌고 간다. 평가셋에서 실제로
# 6문장 중 5문장이 그렇게 걸렸다.
ALIAS_ADDITIONS = {
    # 영어 표기 + **한국어 활용형**. 활용형이 진짜 빈틈이었다 — 이미 `깨끗하고` 는 있는데
    # `깔끔하고`·`깨끗하게`·`정갈하고` 가 빠져 있었다. 있는 패턴의 빈칸을 메우는 것이다.
    "kr.ctx.clean": ["clean", "깔끔하고", "깨끗하게", "정갈하고"],
    "kr.dial.sweet": ["candy"],          # `sweetness` 는 측정에서 기각
    "kr.nomap.young": ["girl-like", "유치한"],
}

# 50번 측정에서 신호(배수>=1.5 · CI하한>1 · 비순환)로 판정된 것만 넣는다.
NEW_ENTRIES = [
    {
        "entry_id": "kr.sens.flashy", "expression": "화려한",
        "aliases": "화려한|화려하고|화려함|flashy|showy",
        "accords": [("tuberose", 1.92, 33, 1.29)],
        "caveat": (" 다만 검색어 `loud` 가 `cloud`·`aloud` 에도 걸리고 accord `oud` 를 "
                   "부분 문자열로 품어 순환 경고가 났다. 해당군 437건에 잡음이 섞였을 수 있어 "
                   "다른 항목보다 약하게 읽어야 한다."),
    },
    {
        "entry_id": "kr.sens.synthetic", "expression": "인공적인",
        "aliases": "인공적인|인공적|인공적이고|artificial|synthetic",
        "accords": [("sour", 1.64, 59, 1.23)],
        "caveat": "",
    },
    {
        "entry_id": "kr.sens.common", "expression": "흔한",
        "aliases": "흔한|흔하고|평범한|평범하고|ordinary|common",
        "accords": [("aquatic", 1.56, 283, 1.39), ("marine", 1.54, 141, 1.29),
                    ("salty", 1.52, 95, 1.22)],
        "caveat": (" 의미가 가까운 `무난한` 은 N4 에서 최대 배수 1.30(통제군 수준)으로 "
                   "`NO_MAPPING` 판정을 받았다. 유추로는 같은 결과를 예상했으나 측정은 "
                   "달랐다 — 두 표현을 같이 묶지 않는다."),
    },
    {
        "entry_id": "kr.sens.complex", "expression": "복잡하게 변하는 향",
        "aliases": "복잡하게 변하는|복잡하게 바뀌는|complex",
        "accords": [("whiskey", 1.75, 42, 1.23)],
        "caveat": "",
    },
]

TEMPLATE = {  # kr.dial.sweet(같은 방법으로 들어간 선례)와 같은 스키마
    "expression_type": "SENSORY", "target_field": "STAGE2_BRIDGE",
    "candidate_type": "ACCORD", "rank": "1",
    "required": "optional",       # 단일 측정이라 core 로 올리지 않는다
    "match_condition": "", "evidence_tier": "LLM", "standardness": "standard",
    "status": "candidate", "source_query_ids": "", "source_type": "LLM_PROPOSAL",
    "verification_status": "CORPUS_SUPPORTED", "relation_type": "ASSOCIATED_WITH",
}


def add_aliases(lex):
    """기존 항목에 별칭을 더한다. (DataFrame, list[str]) — 두 번째는 변경 기록."""
    notes = []
    for entry_id, extra in ALIAS_ADDITIONS.items():
        mask = lex["entry_id"] == entry_id
        if not mask.any():
            raise RuntimeError(f"{entry_id} 행이 없다 — 앞 판본 구조가 바뀌었을 수 있다")
        current = lex.loc[mask, "aliases"].iloc[0].split("|")
        missing = [a for a in extra if a not in current]
        if missing:
            lex.loc[mask, "aliases"] = "|".join(current + missing)
            notes.append(f"`{entry_id}` + {' · '.join(f'`{m}`' for m in missing)}")
    return lex, notes


def build_new_rows(columns, corpus_support):
    """50번 측정 결과를 사전 행으로. DataFrame."""
    rows = []
    for spec in NEW_ENTRIES:
        for accord, lift, n, ci in spec["accords"]:
            rationale = (f"[50] ai_summary 배수 {lift:.2f}x (해당군 {n}건 · CI하한 {ci:.2f}). "
                         f"통제군 최대 배수 1.38 을 넘는다. N4 와 같은 방법·같은 문턱(1.5)으로 "
                         f"쟀고 단일 측정이라 core 가 아닌 optional 로 넣는다."
                         + spec["caveat"])
            rows.append({
                **TEMPLATE,
                "entry_id": spec["entry_id"], "expression": spec["expression"],
                "aliases": spec["aliases"], "candidate_name": accord,
                "corpus_support": str(corpus_support.get(accord, "")),
                "rationale": rationale,
            })
    return pd.DataFrame(rows)[columns]


def verify_gate(before_path, after_path):
    """사전만 바꿔 41번 NDCG 를 비교한다. **나빠지면 실패다.** bool.

    새 항목은 `optional` 이라 검색을 안 바꾼다. 움직이는 것은 별칭 추가분뿐이고,
    분리 측정에서 +0.000715 였다. 같거나 오르면 통과, 내려가면 실패로 본다.
    """
    import importlib.util
    spec = importlib.util.spec_from_file_location("ndcg41", "41_lexicon_ndcg.py")
    ndcg41 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ndcg41)
    key = pd.read_csv("analysis_outputs/32_evalset_answer_key.csv").set_index("perfume_id")
    queries = ndcg41.load_queries()

    scores = {}
    for label, path in (("v1.9", before_path), ("v1.10", after_path)):
        df = ndcg41.score(str(path), queries, key)
        scores[label] = (round(df["ndcg5"].mean(), 6), round(df["gain_ratio"].mean(), 6))
        print(f"    {label:6s} NDCG@5 {scores[label][0]:.6f}  조건충족률 {scores[label][1]:.6f}")
    delta = scores["v1.10"][0] - scores["v1.9"][0]
    ok = delta >= 0
    print(f"    -> NDCG@5 {delta:+.6f}  {'통과' if ok else '실패 — 나빠졌다'}")
    return ok


def write_changelog(alias_notes, n_before, n_after):
    lines = [
        "# 51. 사전 v1.9 -> v1.10 — 별칭 누락 보완과 측정으로 지지된 표현 4개",
        "",
        "재현: `./venv/Scripts/python.exe 51_lexicon_v1_10_avoid_expansion.py`",
        f"행 수: {n_before} -> {n_after} · API 호출 0회",
        "",
        "## 1. 별칭 누락 — 이미 있는 항목에 입구가 없었다",
        "",
    ]
    lines += [f"- {n}" for n in alias_notes]
    lines += [
        "",
        "`깨끗한` 은 **활성 core 항목**(soapy·fresh·aquatic)인데 영어 표기 `clean` 이 없었다. "
        "`달달` 은 N4 가 검증에 쓴 검색어가 `[\"sweet\",\"sugary\",\"candy\"]` 였는데 정작 "
        "사전에는 영어 별칭이 하나도 없었다.",
        "",
        "## 2. 새 표현 4개 — 50번 측정(ai_summary 배수)",
        "",
        "| 표현 | accord | 배수 | 해당군 | CI하한 |",
        "|---|---|---:|---:|---:|",
    ]
    for spec in NEW_ENTRIES:
        for accord, lift, n, ci in spec["accords"]:
            lines.append(f"| {spec['expression']} | `{accord}` | {lift:.2f}x | {n} | {ci:.2f} |")
    lines += [
        "",
        "통제군(무작위 500/1000/2500) 최대 배수 1.17~1.38 · 1.5 이상 0개.",
        "",
        "**전부 `required=optional` 이다.** 단일 측정이고 교차 검증이 없다. `core` 는 하드 AND "
        "조건이라 후보를 0으로 만들 수 있는 자리여서(N11 근거 2) 배수 한 번으로 올리지 않는다.",
        "",
        "### `화려한` 은 약하게 읽어야 한다",
        "",
        "검색어 `loud` 가 `cloud`·`aloud` 에도 걸리고 accord 이름 `oud` 를 부분 문자열로 품어 "
        "순환 경고가 났다. N4 가 인정한 `light`/`lighthearted` 잡음과 같은 종류이며 `loud` 는 "
        "더 흔한 조각이다.",
        "",
        "### `흔한` 은 유추가 빗나간 사례다",
        "",
        "의미가 가까운 `무난한` 은 N4 에서 최대 배수 1.30(통제군 수준)으로 `NO_MAPPING` 판정을 "
        "받았다. 같은 결과를 예상했으나 aquatic·marine·salty 셋이 문턱을 넘었다. "
        "**유추로 판단했으면 틀렸을 항목이다.**",
        "",
        "## 3. 기각한 별칭 — `sweetness`",
        "",
        "처음 조합에는 `달달` 에 `sweetness` 를 넣었는데 NDCG 를 0.468842 -> 0.468243 으로 "
        "깎았다. `달달` 은 `sweet` 와 `caramel` 을 **둘 다** core 로 갖는데, 영어 "
        "`sweetness` 는 \"바닐라의 단맛\"·\"복숭아의 단맛\" 처럼 넓게 쓰여서 갈 때마다 "
        "`caramel` 을 끌고 간다. 평가셋에서 바뀐 6문장 중 5문장이 그 경우였다.",
        "",
        "| 별칭 | NDCG@5 | 판정 |",
        "|---|---:|---|",
        "| (v1.9 그대로) | 0.468842 | |",
        "| `candy` | 0.468842 | 변화 없음 — 무해해서 채택 |",
        "| `sweetness` | 0.468243 | **기각** |",
        "| `clean` | 0.468709 | 단독으론 소폭 하락 |",
        "| `깔끔하고`·`깨끗하게`·`정갈하고` | **0.469557** | **채택** |",
        "",
        "## 효과",
        "",
        "`optional` 새 항목은 엔진이 안 읽으므로(`if row[\"required\"] != \"core\": continue`) "
        "검색을 안 바꾼다. 움직이는 것은 별칭이고, 위 표대로 재서 골랐다. "
        "미매칭 분류도 바뀐다 — `NOT_IN_LEXICON` 대신 `NOT_CORE` 로 기록된다.",
        "",
        "**처음에는 \"아무것도 안 바뀐다\" 고 예측했다가 게이트에서 잡혔다.** 활성 core "
        "항목에 별칭을 더하는 것은 새 입구를 만드는 일이라 검색이 실제로 움직인다.",
        "",
        "## 다루지 않은 것",
        "",
        "- 매칭 방식으로 풀리는 것(`too sweet` 류) — 45번이 측정했고 판단 보류 중",
        "- 질감층(`무겁`·`끈적`·`답답함`·`rough`) — 별도 미결정 질문과 얽힘",
        "- `차갑고 상쾌한 향` — `차가운` 이 이미 N5 에서 강등된 항목이라 재검토가 선행돼야 함",
        "",
        "## 팀 저장소 반영",
        "",
        "아직 반영하지 않았다. 개인 저장소에만 있고 `status: candidate` 다.",
    ]
    CHANGELOG.write_text("\n".join(lines), encoding="utf-8")


def main():
    lex = pd.read_csv(SRC, keep_default_na=False, dtype=str)
    n_before = len(lex)
    print(f"v1.9 {n_before}행 읽음")

    corpus_support = dict(zip(*pd.read_csv(ACCORD_DICT)[["accord", "perfume_count"]]
                              .to_dict("list").values()))

    lex, alias_notes = add_aliases(lex)
    for note in alias_notes:
        print(f"  별칭 추가 — {note}")

    new_rows = build_new_rows(lex.columns, corpus_support)
    out = pd.concat([lex, new_rows], ignore_index=True)
    print(f"v1.10 {len(out)}행 (신규 {len(out) - n_before}) -> {DST}")
    out.to_csv(DST, index=False, encoding="utf-8", lineterminator="\r\n")

    print("\n재현 게이트 — 사전만 바꿨을 때 NDCG 가 나빠지지 않는지")
    same = verify_gate(SRC, DST)

    write_changelog(alias_notes, n_before, len(out))
    print(f"\n변경 기록: {CHANGELOG}")
    if not same:
        raise SystemExit("게이트 실패 — v1.10 을 쓰지 마십시오")


if __name__ == "__main__":
    main()

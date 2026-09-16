"""사전 v1.10 -> v1.11. 활용형 제안 1군(엔진이 안 읽는 항목의 완성 활용형)만 반영한다.

    ./venv/Scripts/python.exe 53_lexicon_v1_11_inflection_group1.py

API 호출 0회. v1.10 을 읽어 v1.11 을 새로 쓴다. 앞 판본은 그대로 둔다.

어디서 온 제안인가
------------------
외부 조사 `한국어 향 표현 사전의 활용형 빈틈 분석`(2026-09-16)이 94개를 제안했고,
`52_alias_proposal_review.py` 로 검산했다.

    없는 entry_id   0개     지어낸 항목이 없다
    NO_OP           0개     이미 잡혀서 무효인 제안이 없다
    DUPLICATE       0개
    NEW            76개
    WIDENS         18개     기존 별칭보다 넓은 어간

1군의 범위 — 셋을 모두 만족하는 것만
--------------------------------------
    1. 엔진이 검색에 쓰지 않는 항목      틀려도 추천 결과가 안 바뀐다
       (candidate_type != ACCORD 이거나 target_field == NO_MAPPING 이거나 core 행이 없음)
    2. 완성 활용형 또는 띄어쓰기 변형    어간이 아니다
    3. 조사가 매긴 과잉매칭 위험이 `낮음`

뺀 것과 이유
------------
**어간 전부(WIDENS 18개 + NEW 로 분류됐지만 어간인 4개).** 검산의 NEW/WIDENS 는 "기존
별칭 대비 중복인가" 를 본 것이지 "어간인가" 를 본 것이 아니다. `보드랍`·`고급스럽`·
`여성스럽`·`귀엽` 은 NEW 로 분류됐지만 ㅂ불규칙 어간이라 어간과 같은 문제를 갖는다.

    실측 — 지금은 아무것도 안 걸리는 문장이 어간을 넣으면 정반대 뜻으로 걸린다

        "평범하지 않은 향을 원해"   지금 [] -> `평범` 추가시 걸림
        "포근하지 않았으면"         지금 [] -> `포근` 추가시 걸림
        "섹시하지 않은 향"          지금 [] -> `섹시` 추가시 걸림

검색은 안 바뀌지만 **미매칭 로그가 오염된다.** 로그는 다음 사전 확장의 입력 데이터라
(참고 조사의 사전 확장 파이프라인) 공짜가 아니다.

**`쨍하게`·`유치하게`·`유치하고`·`유치함`** — 조사가 매긴 위험이 `중간`이다(동음이의어).

**`kr.nomap.young` 전체** — 이 항목은 이미 `어린` 이 `어린이` 에 걸리는 결함이 있다
(조사가 지적했고 실측으로 확인했다). 결함을 고치기 전에 별칭을 더하지 않는다.

**활성 항목(2·3군)** — `깨끗한`·`촉촉한`·`달달`·`비 오는 숲`·`분내`·`나무`·`상큼한`·
`과육`·`풀 냄새`·`빨래`. 검색을 실제로 움직이므로 NDCG 게이트로 따로 잰다.

무엇을 검증하는가
------------------
대상이 전부 **엔진이 안 읽는 항목**이므로 NDCG 가 **정확히 그대로여야 한다.**
v1.10 작업에서 "안 바뀐다" 는 예측이 틀린 적이 있는데(활성 항목 별칭을 놓쳤다), 이번에는
대상 항목이 엔진의 적재 필터에서 걸러지는 것을 확인하고 골랐다. 바뀌면 그 이해가 틀린 것이다.

출력  data/scent_knowledge/domain_lexicon_v1_11.csv
      analysis_outputs/53_lexicon_v1_11_changelog.md
"""
import pathlib
import sys

import pandas as pd

sys.path.insert(0, "C:/Users/SSAFY/Desktop/S15P21E203/ai")

SRC = pathlib.Path("data/scent_knowledge/domain_lexicon_v1_10.csv")
DST = pathlib.Path("data/scent_knowledge/domain_lexicon_v1_11.csv")
CHANGELOG = pathlib.Path("analysis_outputs/53_lexicon_v1_11_changelog.md")

# 1군. entry_id -> (더할 별칭, 형태 종류)
GROUP1 = {
    "kr.term.top_note": (["톱 노트"], "띄어쓰기"),
    "kr.term.middle_note": (["하트 노트", "미드 노트"], "띄어쓰기"),
    "kr.term.base_note": (["라스트 노트"], "띄어쓰기"),
    "kr.term.residual": (["끝 향"], "띄어쓰기"),
    "kr.term.concentration": (["오드 퍼퓸", "오 드 퍼퓸", "오드 뚜왈렛", "오 드 뚜왈렛"],
                              "띄어쓰기"),
    "kr.sens.cozy": (["보드라워"], "활용형"),                      # `보드랍`(어간) 제외
    "kr.sens.cold": (["차가워"], "활용형"),                        # `차갑`·`서늘`(어간) 제외
    "kr.nomap.plain": (["부담 없는", "부담없이", "부담 없이",
                        "튀지않는", "튀지 않고", "튀지않고"], "띄어쓰기/활용형"),
    "kr.nomap.luxurious": (["고급스러워", "고급지고", "고급지게",
                            "우아하게", "우아하고", "우아해"], "활용형"),  # `고급스럽`·`세련` 제외
    "kr.nomap.natural": (["자연스러워"], "활용형"),                 # `자연스럽`·`내추럴` 제외
    "kr.nomap.feminine": (["여성스러워"], "활용형"),                # `여성스럽`·`여성적` 제외
    "kr.nomap.cute": (["귀여워", "귀여움"], "활용형"),              # `귀엽`(어간) 제외
    "kr.sens.flashy": (["화려하게", "화려해"], "활용형"),
    "kr.sens.common": (["흔하게", "흔해", "흔함"], "활용형"),        # `평범`(어간) 제외
    "kr.sens.complex": (["복잡하게 변해", "복잡하게 변하고",
                         "복잡하게 바뀌어", "복잡하게 바뀌고"], "활용형"),
}


def assert_inert(lex, entry_ids):
    """대상 항목이 정말로 엔진이 안 읽는 것인지 확인한다. None.

    `load_index()` 는 candidate_type=='ACCORD' 이고 target_field!='NO_MAPPING' 인 행만
    싣고, `_lexicon_lookup()` 은 required!='core' 를 건너뛴다. 셋을 다 만족하는 행이
    하나라도 있으면 그 항목은 검색에 쓰인다.
    """
    live = lex[(lex["candidate_type"] == "ACCORD")
               & (lex["target_field"] != "NO_MAPPING")
               & (lex["required"] == "core")]
    bad = sorted(set(entry_ids) & set(live["entry_id"]))
    if bad:
        raise RuntimeError(f"1군에 검색에 쓰이는 항목이 섞였다: {bad}")
    print(f"  대상 {len(entry_ids)}개 항목이 모두 엔진 적재 필터에서 걸러지는 것을 확인")


def add_aliases(lex):
    """1군 별칭을 더한다. (DataFrame, list[tuple])."""
    notes = []
    for entry_id, (extra, kind) in GROUP1.items():
        mask = lex["entry_id"] == entry_id
        if not mask.any():
            raise RuntimeError(f"{entry_id} 행이 없다")
        current = lex.loc[mask, "aliases"].iloc[0].split("|")
        missing = [a for a in extra if a not in current]
        if missing:
            lex.loc[mask, "aliases"] = "|".join(current + missing)
            notes.append((entry_id, lex.loc[mask, "expression"].iloc[0], missing, kind))
    return lex, notes


def verify_gate(before_path, after_path):
    """사전만 바꿔 41번 NDCG 를 비교한다. **정확히 같아야 통과다.** bool."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("ndcg41", "41_lexicon_ndcg.py")
    ndcg41 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ndcg41)
    key = pd.read_csv("analysis_outputs/32_evalset_answer_key.csv").set_index("perfume_id")
    queries = ndcg41.load_queries()

    scores = {}
    for label, path in (("v1.10", before_path), ("v1.11", after_path)):
        df = ndcg41.score(str(path), queries, key)
        scores[label] = (round(df["ndcg5"].mean(), 6), round(df["gain_ratio"].mean(), 6))
        print(f"    {label:6s} NDCG@5 {scores[label][0]:.6f}  조건충족률 {scores[label][1]:.6f}")
    same = scores["v1.10"] == scores["v1.11"]
    print(f"    -> {'동일함 — 예측대로' if same else '다르다 — 대상 선정이 틀렸다'}")
    return same


def write_changelog(notes, n_before, n_after, n_alias):
    lines = [
        "# 53. 사전 v1.10 -> v1.11 — 활용형 제안 1군 반영",
        "",
        "재현: `./venv/Scripts/python.exe 53_lexicon_v1_11_inflection_group1.py`",
        f"행 수: {n_before} -> {n_after} (행은 늘지 않는다. 별칭 {n_alias}개 추가) · API 호출 0회",
        "",
        "## 출처",
        "",
        "외부 조사 `한국어 향 표현 사전의 활용형 빈틈 분석`(2026-09-16)의 제안 94개 중 "
        "1군만 반영했다. 검산은 `52_alias_proposal_review.py` — 지어낸 entry_id 0개, "
        "이미 잡혀서 무효인 제안 0개였다.",
        "",
        "## 1군의 범위",
        "",
        "셋을 모두 만족하는 것만 넣었다.",
        "",
        "1. 엔진이 검색에 쓰지 않는 항목 (틀려도 추천 결과가 안 바뀐다)",
        "2. 완성 활용형 또는 띄어쓰기 변형 (어간이 아니다)",
        "3. 조사가 매긴 과잉매칭 위험이 `낮음`",
        "",
        "| entry_id | 표현 | 추가한 별칭 | 형태 |",
        "|---|---|---|---|",
    ]
    for entry_id, expr, added, kind in notes:
        lines.append(f"| `{entry_id}` | {expr} | {' · '.join(f'`{a}`' for a in added)} | {kind} |")
    lines += [
        "",
        "## 뺀 것",
        "",
        "### 어간 전부 (WIDENS 18개 + NEW 로 분류됐지만 어간인 4개)",
        "",
        "검산의 NEW/WIDENS 는 \"기존 별칭 대비 중복인가\" 를 본 것이지 \"어간인가\" 를 본 "
        "것이 아니다. `보드랍`·`고급스럽`·`여성스럽`·`귀엽` 은 NEW 로 분류됐지만 ㅂ불규칙 "
        "어간이라 같은 문제를 갖는다.",
        "",
        "```",
        "실측 — 지금은 아무것도 안 걸리는 문장이 어간을 넣으면 정반대 뜻으로 걸린다",
        "",
        '  "평범하지 않은 향을 원해"   지금 [] -> `평범` 추가시 걸림',
        '  "포근하지 않았으면"         지금 [] -> `포근` 추가시 걸림',
        '  "섹시하지 않은 향"          지금 [] -> `섹시` 추가시 걸림',
        "```",
        "",
        "조사는 `NO_MAPPING` 항목이라 accord 오염이 없다고 봤다. 검색은 안 바뀌는 것이 "
        "맞지만 **미매칭 로그가 오염된다.** 로그는 다음 사전 확장의 입력 데이터라 공짜가 "
        "아니다. 조사 본인도 `어린` 에 대해서는 같은 우려를 적었는데 나머지 어간에는 그 "
        "기준을 적용하지 않았다.",
        "",
        "### `쨍하게` · `유치하게` · `유치하고` · `유치함`",
        "",
        "조사가 매긴 위험이 `중간` 이다. 동음이의어(`유치하다`=끌어들이다)가 있다.",
        "",
        "### `kr.nomap.young` 전체",
        "",
        "이 항목은 이미 결함이 있다 — v1.9 에서 넣은 `어린` 이 `어린이` 에 걸린다.",
        "",
        "```",
        '  "어린이도 쓸 수 있는 향"  ->  `어린` 에 걸림',
        "```",
        "",
        "조사가 지적했고 실측으로 확인했다. **결함을 고치기 전에 별칭을 더하지 않는다.**",
        "",
        "### 활성 항목 (2·3군)",
        "",
        "`깨끗한`·`촉촉한`·`달달`·`비 오는 숲`·`분내`·`나무`·`상큼한`·`과육`·`풀 냄새`·"
        "`빨래`. 검색을 실제로 움직이므로 NDCG 게이트로 따로 잰다. 특히 `달콤하게`/"
        "`달콤해`(`달달` 이 sweet+caramel 을 강제한다), `숲속`, `단정하게` 는 하나씩 재야 한다.",
        "",
        "## 검증",
        "",
        "대상이 전부 엔진 적재 필터에서 걸러지는 항목이므로 NDCG 가 **정확히 같아야** "
        "통과다. 스크립트가 대상 선정 자체도 검사한다(`assert_inert`).",
        "",
        "v1.10 에서 \"안 바뀐다\" 는 예측이 한 번 틀렸다 — 활성 항목에 별칭을 더하면 "
        "새 입구가 생긴다는 것을 놓쳤다. 이번에는 대상을 엔진 코드 기준으로 골랐다.",
        "",
        "## 팀 저장소 반영",
        "",
        "아직 하지 않았다. 개인 저장소에만 있다.",
    ]
    CHANGELOG.write_text("\n".join(lines), encoding="utf-8")


def main():
    lex = pd.read_csv(SRC, keep_default_na=False, dtype=str)
    n_before = len(lex)
    print(f"v1.10 {n_before}행 읽음")

    assert_inert(lex, list(GROUP1))

    lex, notes = add_aliases(lex)
    n_alias = sum(len(added) for _, _, added, _ in notes)
    for entry_id, expr, added, _ in notes:
        print(f"  {entry_id:24s} ({expr}) + {' · '.join(added)}")
    print(f"\n별칭 {n_alias}개 추가 · 행 수는 그대로 {len(lex)} -> {DST}")
    lex.to_csv(DST, index=False, encoding="utf-8", lineterminator="\r\n")

    print("\n재현 게이트 — 엔진이 안 읽는 항목만 건드렸으니 NDCG 가 정확히 같아야 한다")
    same = verify_gate(SRC, DST)

    write_changelog(notes, n_before, len(lex), n_alias)
    print(f"\n변경 기록: {CHANGELOG}")
    if not same:
        raise SystemExit("게이트 실패 — 대상 선정을 다시 확인해야 한다")


if __name__ == "__main__":
    main()

"""형태소 분석기 경계 판정을 평가셋으로 잰다 — v1.15 의 문맥 조건과 비교.

    ./venv/Scripts/python.exe -W ignore 82_morpheme_boundary.py

**GMS 호출 0회.** 저장된 ①단계 체크포인트만 쓴다. 결정적이다.

왜 다시 여는가
---------------
`DECISIONS.md` N13 이 형태소 분석기를 기각했는데 **그것은 다른 용도였다.**

    N13 이 잰 용도   어간 매칭으로 **더 많이 잡기**
                    `달콤하지` -> (달콤,) 로 걸려 부정 표현 오탐이 3.4% -> 14.8%
    이번 용도       낱말 경계 판정으로 **덜 잡기**
                    `꿀꿀하다` 안의 `꿀` 이 독립 형태소가 아니면 조건을 만들지 않는다

N13 자신이 *"되돌리기 쉬운 결정이다. `_lexicon_lookup` 하나를 바꾸는 일이라 언제든
다시 연다"* 고 적어 뒀다.

**문장 10개로 먼저 본 것** [측정 2026-09-18] — 문맥 조건(v1.15)이 못 막는 **긴 문장
오탐**을 경계 판정이 막는다.

                                  문맥 조건   경계(mecab)
    "꿀꿀한 기분일 때 쓸 향수"          통과 ✗      차단 ✓
    "해변가에 주차했는데 향수 냄새가"     통과 ✗      차단 ✓
    "세탁기 돌리면서 향수 생각났어"      통과 ✗      차단 ✓
    "초록불 기다리며 향수 골랐다"        통과 ✗      통과 ✗   합성어
    "초록빛 풀 냄새 나는 향"           통과 ✓      차단 ✗   경계가 잘못 막는다

**분석기마다 갈린다.** `꿀꿀하다` 를 kiwi 는 `꿀+꿀` 로 쪼개고(못 막음) mecab·pecab 은
안 쪼갠다(막음). N13 이 *"셋이 갈리지 않는다"* 고 한 것은 어간 매칭 기준이다.

무엇을 재는가
--------------
    현행         부분 문자열 포함 그대로 (v1.14)
    문맥 조건     v1.15 — 짧은 표면형 9개를 분리해 query_contains 를 걸었다
    경계 판정     표면형이 문장에서 **독립 형태소**일 때만 인정
    둘 다        문맥 조건 + 경계 판정

경계 판정은 사전으로 표현할 수 없다. 코드가 하는 일이라 이 스크립트가 `_lexicon_lookup`
을 흉내 내어 잰다. **팀 저장소 코드는 건드리지 않는다.**

판정 기준 — 결과를 보기 전에 정했다 (N4 · 80번과 같은 관례)
--------------------------------------------------------------
    채택   긴 문장 오탐을 문맥 조건보다 많이 막고
           **설문 143 · 합성 600 손실이 0건**이며
           NDCG@5 델타 >= 0
    기각   손실이 생기거나 오탐 차단이 문맥 조건 이하일 때

**손실이 0건이 아니면 기각한다.** 의존성 +1 과 메모리 +10MB 를 쓰는 변경인데, v1.15 가
의존성 0 으로 이미 짧은 입력을 막고 있다. 같은 값을 더 비싸게 살 이유가 없다.

출력
-----
표는 표준출력에만 쓴다. 파일을 만들지 않는다 (41번 이후 관례).
"""
import json
import re
import sys
import unicodedata

import pandas as pd

sys.path.insert(0, "C:/Users/SSAFY/Desktop/S15P21E203/ai")
import nlr_engine as e  # noqa: E402

BASE = "data/scent_knowledge/domain_lexicon_v1_14.csv"    # 현행 · 경계 판정의 바탕
WITH_CONTEXT = "data/scent_knowledge/domain_lexicon_v1_15.csv"   # 문맥 조건

SURVEY = ("설문 143", "analysis_outputs/37_survey_stage1_checkpoint.csv", "query_text")
SYNTH = ("합성 600", "analysis_outputs/34_evalset_stage1_checkpoint.csv", "sentence")
NOT_A_QUERY = re.compile(r"^(네|넵|넴|예)\s*[.!]?$|^넵\s*알겠습니다\.?$")

# 경계 판정을 적용할 표면형. **v1.15 가 문맥 조건을 건 것과 같은 9개**다 —
# 두 방법을 같은 대상에 걸어야 비교가 성립한다.
TARGET = {"꿀", "분내", "빨래", "산림", "세탁", "이불", "잔디", "잼", "초록"}

# 막아야 하는 것. 앞 14개는 81번이 어휘 조사에서 받아 검증한 낱말(짧은 입력)이고,
# 뒤 5개는 **문맥 조건이 못 막는 긴 문장**이다. 이 다섯이 이번 측정의 핵심이다.
MISFIRE_SHORT = [
    "꿀꿀하다", "꿀밤", "꿀팁", "잼민이", "분내다", "산림청",
    "세탁기", "세탁소", "이불킥", "잔디깎기", "잔디밭", "초록불",
    "빨래판", "빨래감",
]
MISFIRE_LONG = [
    "꿀꿀한 기분일 때 쓸 향수 추천해줘",
    "세탁기 돌리면서 향수 생각났어",
    "초록불 기다리며 향수 골랐다",
    "잼민이들이 향수 뿌리고 다녀",
    "이불킥 하고 싶은 향수 있어?",
]

# 살려야 하는 것. v1.15 가 35/35 를 지킨 목록과 같다.
MUST_KEEP = [
    "달달하다", "새콤달콤", "말캉말캉", "탱글탱글", "풋풋하다", "편백나무", "흰꽃",
    "갓 세탁한", "세탁한", "침구", "침대", "코튼 이불",
    "분가루", "아기분", "베이비파우더", "로션 같은",
    "당밀", "시럽", "생풀", "수액", "잎사귀", "젖은 잎",
    "고목", "목재", "숲", "연필심", "톱밥", "편백",
    "꿀 향 나는 향수 추천해줘",
    "꿀을 뿌린 듯 달콤한 향",
    "초록빛 풀 냄새 나는 향",
    "잔디 깎은 냄새 같은 것",
    "이불 냄새 나는 향수",
    "빨래 냄새 나는 향수 찾고 있어",
    "갓 세탁한 이불 같은 향",
]


def make_boundary(name):
    """그 분석기로 "이 표면형이 문장에서 독립 형태소인가" 를 묻는 함수. callable.

    **형태소 목록에 표면형이 그대로 있으면 독립으로 본다.** 어간을 풀거나 원형으로
    바꾸지 않는다 — 그것이 N13 이 기각한 어간 매칭이다.
    """
    if name == "kiwi":
        from kiwipiepy import Kiwi
        analyzer = Kiwi()
        return lambda text: {t.form for t in analyzer.tokenize(text)}
    if name == "mecab":
        import mecab
        analyzer = mecab.MeCab()
        return lambda text: {w for w, _ in analyzer.pos(text)}
    import pecab
    analyzer = pecab.PeCab()
    return lambda text: {w for w, _ in analyzer.pos(text)}


def core_of(index, text, structured, morphs=None):
    """그 문장에서 나오는 core accord. set[str].

    `nlr_engine.understand()` 의 사전 경로를 흉내 낸다. `morphs` 를 주면 **대상 표면형에
    한해** 독립 형태소일 때만 인정한다.
    """
    parts = [unicodedata.normalize("NFC", str(text))]
    if structured:
        parts += [str(v) for v in (structured.get("additional_requirements") or [])]
    haystack = " ".join(parts)
    forms_in_text = morphs(haystack) if morphs else None

    hit = set()
    for form, expressions in index["lexicon_surface"].items():
        if not form or form not in haystack:
            continue
        if forms_in_text is not None and form in TARGET and form not in forms_in_text:
            continue          # 더 큰 낱말의 일부다
        hit |= expressions

    core = set()
    for expression in sorted(hit):
        for row in index["lexicon_by_expression"].get(expression, []):
            condition = row["match_condition"]
            if condition.startswith("query_contains:"):
                tokens = [t for t in condition.split(":", 1)[1].split(",") if t]
                if not any(t in haystack for t in tokens):
                    continue
            if row["required"] != "core":
                continue
            if row["candidate_name"] in index["aidx"]:
                core.add(row["candidate_name"])

    if structured:
        for raw in (structured.get("scent_preference") or []):
            accord = e._normalize_accord(index, raw)
            if accord:
                core.add(accord)
            else:
                core.update(e._bridge_lookup(index, raw))
        avoid = {e._normalize_accord(index, r) for r in (structured.get("avoid") or [])}
        core -= {a for a in avoid if a}
    return core


def load_rows(path, column):
    """체크포인트를 (문장, ①단계 dict) 목록으로. list."""
    table = pd.read_csv(path)
    out = []
    for row in table.to_dict("records"):
        text = str(row[column])
        if NOT_A_QUERY.match(text.strip()):
            continue
        try:
            parsed = json.loads(row["raw_response"])
        except Exception:
            parsed = None
        out.append((text, parsed if isinstance(parsed, dict) else None))
    return out


def main():
    analyzer = sys.argv[1] if len(sys.argv) > 1 else "mecab"
    morphs = make_boundary(analyzer)

    base = e.load_index(lexicon_csv=BASE)
    ctx = e.load_index(lexicon_csv=WITH_CONTEXT)

    # (이름, index, 경계 판정 함수)
    VARIANTS = [
        ("현행", base, None),
        ("문맥 조건 (v1.15)", ctx, None),
        ("경계 판정만", base, morphs),
        ("둘 다", ctx, morphs),
    ]

    print("=" * 96)
    print(f"형태소 분석기 경계 판정 — 분석기 {analyzer} · GMS 호출 0회")
    print("=" * 96)
    print(f"대상 표면형 {len(TARGET)}개 — {' · '.join(sorted(TARGET))}")
    print()

    datasets = []
    for name, path, column in (SURVEY, SYNTH):
        datasets.append((name, load_rows(path, column)))
        print(f"  {name} — {len(datasets[-1][1])}건")
    print()

    baseline = {name: {t: frozenset(core_of(base, t, o)) for t, o in rows}
                for name, rows in datasets}

    summary = []
    for label, index, boundary in VARIANTS:
        print("=" * 96)
        print(f"■ {label}")
        print("=" * 96)

        short = sum(1 for t in MISFIRE_SHORT if not core_of(index, t, None, boundary))
        print(f"  짧은 오탐  {short}/{len(MISFIRE_SHORT)} 막힘")
        long_blocked = 0
        for text in MISFIRE_LONG:
            got = sorted(core_of(index, text, None, boundary))
            if not got:
                long_blocked += 1
            mark = "막힘" if not got else "**안 막힘**"
            print(f"    {mark:10} {text:30} -> {got}")
        print(f"  긴 문장 오탐 {long_blocked}/{len(MISFIRE_LONG)} 막힘")

        dead = [t for t in MUST_KEEP if not core_of(index, t, None, boundary)]
        print(f"  살릴 것    {len(MUST_KEEP) - len(dead)}/{len(MUST_KEEP)} 생존")
        for t in dead:
            print(f"    **같이 죽음** {t}")

        lost = shrunk = 0
        examples = []
        for name, rows in datasets:
            for text, structured in rows:
                now = frozenset(core_of(index, text, structured, boundary))
                was = baseline[name][text]
                if was and not now:
                    lost += 1
                    examples.append((name, text, was, now))
                elif now and now < was:
                    shrunk += 1
                    examples.append((name, text, was, now))
        print(f"  평가셋     통째로 잃음 {lost}건 · 줄어듦 {shrunk}건")
        for name, text, was, now in examples[:6]:
            print(f"    [{name}] {text[:46]:48} {sorted(was)} -> {sorted(now)}")
        if len(examples) > 6:
            print(f"    ... 앞 6건만 찍었다 (총 {len(examples)}건)")
        print()
        summary.append((label, short, long_blocked, len(MUST_KEEP) - len(dead), lost + shrunk))

    print("=" * 96)
    print("■ 판정")
    print("=" * 96)
    print(f"{'변형':20} {'짧은 오탐':>10} {'긴 문장':>10} {'살릴 것':>10} {'평가셋 손실':>12}")
    for label, short, long_b, kept, loss in summary:
        print(f"{label:20} {short:>6}/{len(MISFIRE_SHORT):<3} {long_b:>6}/{len(MISFIRE_LONG):<3} "
              f"{kept:>6}/{len(MUST_KEEP):<3} {loss:>12}")
    print()
    print("기준 — 긴 문장 오탐을 문맥 조건보다 많이 막고 · 평가셋 손실 0건 · NDCG 델타 >= 0")
    print("손실이 0건이 아니면 기각한다. 의존성 +1 과 메모리 +10MB 를 쓸 이유가 없다.")


if __name__ == "__main__":
    main()

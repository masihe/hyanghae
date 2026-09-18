"""GPT 조사가 권한 「경계 검사」를 우리 데이터로 잰다 — 78번의 「문맥 조건」과 비교.

    ./venv/Scripts/python.exe -W ignore 79_boundary_vs_context.py

**GMS 를 호출하지 않는다.** 저장된 ①단계 체크포인트만 쓴다. 결정적이다.

왜 재는가
----------
2026-09-18 GPT 조사(`한국어 향수 추천 입력 처리...pdf`)가 오탐을 두 층으로 나누고
층마다 다른 방법을 권했다.

    lexical boundary   꿀 in 꿀꿀한 · 잼 in 잼민이 · 나무 in 나무젓가락 · 초록 in 초록불
                       -> **경계 검사로 대부분 해결** · 문맥 조건은 낮은 우선순위
    semantic/domain    해변 in 해변가에 주차 · 침대 in 침대에서 뒹굴
                       -> 경계로는 **해결 불가** · 문맥 조건이 필요

그 근거로 Algolia 의 Contains 조건이 letter substring 이 아니라 word 단위라는 점,
FlashText 가 keyword boundary 를 검사한다는 점을 들었다. 다만 **한국어에는 영어식
`\\b` 를 그대로 못 쓴다**는 것도 같이 적었고, 대신 작은 조사 allowlist 를 제안했다.

    은 는 이 가 을 를 에 에서 의 로 으로 와 과 도 만

**78번은 오탐 열한 건을 전부 문맥 조건(`match_condition`)으로 다뤘고 10/11 을 막았다.**
조사가 권한 경계 검사가 그보다 나은지, 아니면 우리 데이터에서는 다른 결과가 나오는지
재본다. 조사의 주장을 검증하는 것이 목적이다.

무엇을 재는가
--------------
    현행         부분 문자열 포함 그대로
    경계 검사     조사 조사가 권한 방식. 표면형 뒤가 조사/공백/문장끝일 때만 인정
    문맥 조건     78번의 E1. 오탐 확인된 10개에 query_contains 를 건다
    둘 다        경계 검사 + 문맥 조건

**경계 검사는 사전 CSV 로 표현할 수 없다.** 코드가 하는 일이라 이 스크립트가
`_lexicon_lookup` 을 흉내 내어 잰다. 팀 저장소 코드는 건드리지 않는다.

판정 기준은 78번과 같다 (N4 · 측정과 반영을 분리한다).

    막아야 하는 것   오탐 문장에서 조건이 0개가 된다
    잃으면 안 되는 것 설문 143 · 합성 600 에서 조건이 줄어드는 문장이 0건

출력
-----
표는 표준출력에만 쓴다. 파일을 만들지 않는다 (41번 이후 관례).
"""
import json
import re
import sys
import unicodedata
from pathlib import Path

import pandas as pd

TEAM = Path("C:/Users/SSAFY/Desktop/S15P21E203/ai")
sys.path.insert(0, str(TEAM))
import nlr_engine as e  # noqa: E402

SURVEY = ("설문 143", "analysis_outputs/37_survey_stage1_checkpoint.csv", "query_text")
SYNTH = ("합성 600", "analysis_outputs/34_evalset_stage1_checkpoint.csv", "sentence")
NOT_A_QUERY = re.compile(r"^(네|넵|넴|예)\s*[.!]?$|^넵\s*알겠습니다\.?$")

# 조사가 제안한 조사(助詞) allowlist. PDF 4쪽 그대로다.
PARTICLES = ("은", "는", "이", "가", "을", "를", "에", "에서", "의",
             "로", "으로", "와", "과", "도", "만")

# 경계 검사를 적용할 표면형. 조사가 "boundary 로 해결된다" 고 분류한 것들이다.
BOUNDED = {"꿀", "숲", "잼", "나무", "초록", "잔디"}

# 문맥 조건을 걸 표면형. 78번 E1 과 같다.
CONTEXT_FORMS = {"꿀", "숲", "잼", "이불", "침구", "침대", "잔디", "초록", "해변", "나무"}
CONTEXT_WORDS = ("향", "냄새", "느낌")

PROBES_BLOCK = [
    ("경계", "꿀꿀한 기분이야"),
    ("경계", "잼민이들 때문에 시끄러워"),
    ("경계", "나무젓가락 하나 부러뜨렸어"),
    ("경계", "초록불에 건넜어"),
    ("경계", "잔디깎기 새로 샀다"),
    ("경계", "숲속마을에 살고 싶다"),
    ("의미", "침대에서 뒹굴기만 했다"),
    ("의미", "해변가에 주차했다"),
    ("의미", "이불 빨래 개기 싫다"),
    ("의미", "나는 초록불에 건넜어"),
    ("의미", "내가 좋아하는 나무젓가락 같은 거 사줘"),
]

PROBES_KEEP = [
    "꿀 향 나는 향수 추천해줘",
    "꿀을 뿌린 듯 달콤한 향",
    "숲 냄새 나는 향수",
    "숲속에 온 것 같은 향수 추천해줘",
    "숲향 나는 향수 추천좀",
    "나무 냄새 나는 향수",
    "초록빛 풀 냄새 나는 향",
    "잔디 깎은 냄새 같은 것",
    "침대에 누운 것 같은 포근한 향",
    "이불 냄새 나는 향수",
    "해변 느낌 향수",
    "빨래",
    "상큼",
    "해변",
]


def boundary_ok(text, form, start):
    """표면형이 낱말 경계에서 끝나는가. bool.

    조사 조사가 권한 규칙이다 — 표면형 바로 뒤가 문장 끝 · 한글이 아닌 글자 ·
    조사 allowlist 중 하나면 인정하고, 그 밖의 한글이면 더 큰 낱말의 일부로 본다.

    **앞쪽은 보지 않는다.** `꿀꿀한` 은 첫 `꿀` 뒤에 `꿀` 이 오므로 이미 걸린다.
    """
    tail = text[start + len(form):]
    if not tail:
        return True
    if not ("가" <= tail[0] <= "힣"):
        return True          # 공백 · 구두점 · 영문 · 숫자
    for particle in PARTICLES:
        if tail.startswith(particle):
            rest = tail[len(particle):]
            if not rest or not ("가" <= rest[0] <= "힣"):
                return True
    return False


def found(text, form, *, bounded):
    """표면형이 문장에 있는가. bool. `bounded` 면 경계 검사를 함께 한다."""
    if not bounded:
        return form in text
    start = text.find(form)
    while start >= 0:
        if boundary_ok(text, form, start):
            return True
        start = text.find(form, start + 1)
    return False


def core_of(index, text, structured, *, use_boundary, use_context):
    """그 문장에서 나오는 core accord. set[str].

    `nlr_engine.understand()` 의 사전 경로를 흉내 낸다. ①단계가 뽑은
    `additional_requirements` 를 원문에 붙여 훑는 것까지 같다.
    """
    parts = [unicodedata.normalize("NFC", str(text))]
    if structured:
        parts += [str(v) for v in (structured.get("additional_requirements") or [])]
    haystack = " ".join(parts)

    hit = set()
    for form, expressions in index["lexicon_surface"].items():
        if not form:
            continue
        bounded = use_boundary and form in BOUNDED
        if found(haystack, form, bounded=bounded):
            if use_context and form in CONTEXT_FORMS:
                if not any(w in haystack for w in CONTEXT_WORDS):
                    continue
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

    # ①단계가 accord 이름을 직접 준 경우. understand() 와 같은 처리다
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


def load_rows(path, col):
    """체크포인트를 (문장, ①단계 dict) 목록으로. list."""
    d = pd.read_csv(path)
    out = []
    for r in d.to_dict("records"):
        text = str(r[col])
        if NOT_A_QUERY.match(text.strip()):
            continue
        try:
            o = json.loads(r["raw_response"])
        except Exception:
            o = None
        out.append((text, o if isinstance(o, dict) else None))
    return out


VARIANTS = [
    ("현행", False, False),
    ("경계 검사만", True, False),
    ("문맥 조건만", False, True),
    ("둘 다", True, True),
]


def main():
    index = e.load_index()
    datasets = []
    for name, path, col in (SURVEY, SYNTH):
        if Path(path).exists():
            datasets.append((name, load_rows(path, col)))

    print("=" * 96)
    print("GPT 조사가 권한 「경계 검사」 vs 78번의 「문맥 조건」 — GMS 호출 없음")
    print("=" * 96)
    print(f"사전 표면형 {len(index['lexicon_surface'])}개 · "
          f"경계 검사 대상 {len(BOUNDED)}개 · 문맥 조건 대상 {len(CONTEXT_FORMS)}개")
    for name, rows in datasets:
        print(f"  {name} — {len(rows)}건")
    print()

    base = {}
    for name, rows in datasets:
        base[name] = {t: frozenset(core_of(index, t, o, use_boundary=False, use_context=False))
                      for t, o in rows}

    for label, ub, uc in VARIANTS:
        print("=" * 96)
        print(f"■ {label}")
        print("=" * 96)

        blocked = {"경계": 0, "의미": 0}
        total = {"경계": 0, "의미": 0}
        for kind, text in PROBES_BLOCK:
            total[kind] += 1
            got = core_of(index, text, None, use_boundary=ub, use_context=uc)
            if not got:
                blocked[kind] += 1
            mark = "막힘" if not got else "**안 막힘**"
            print(f"    [{kind}] {mark:10} {text:30} -> {sorted(got)}")

        print()
        kept = 0
        for text in PROBES_KEEP:
            got = core_of(index, text, None, use_boundary=ub, use_context=uc)
            if got:
                kept += 1
            else:
                print(f"    **같이 죽음** {text:30} -> []")
        print(f"\n    오탐 막음 — 경계형 {blocked['경계']}/{total['경계']} · "
              f"의미형 {blocked['의미']}/{total['의미']}   ·   살릴 것 {kept}/{len(PROBES_KEEP)}")

        print()
        for name, rows in datasets:
            lost = shrunk = 0
            examples = []
            for text, o in rows:
                now = frozenset(core_of(index, text, o, use_boundary=ub, use_context=uc))
                was = base[name][text]
                if was and not now:
                    lost += 1
                    examples.append((text, was, now))
                elif now and now < was:
                    shrunk += 1
                    examples.append((text, was, now))
            print(f"    {name}  조건을 통째로 잃은 문장 {lost}건 · 줄어든 문장 {shrunk}건")
            for text, was, now in examples[:5]:
                print(f"        {text[:52]:54} {sorted(was)} -> {sorted(now)}")
            if len(examples) > 5:
                print(f"        ... 앞 5건만 찍었다 (총 {len(examples)}건)")
        print()


if __name__ == "__main__":
    main()

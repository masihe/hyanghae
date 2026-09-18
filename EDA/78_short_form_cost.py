"""짧은 표면형을 막으면 무엇을 잃는가 — 고치기 전에 대가를 잰다.

    ./venv/Scripts/python.exe -W ignore 78_short_form_cost.py

**GMS 를 호출하지 않는다.** 저장된 ①단계 체크포인트만 쓴다. 결정적이라 몇 번 돌려도 같다.

왜 재는가
----------
77번이 사전의 부분 문자열 매칭에서 오탐 셋을 확인했다 [측정 · 3회 모두 재현].

    꿀꿀한 기분이야        -> '꿀'   -> sweet           -> 향수 5개
    잼민이들 때문에 시끄러워  -> '잼'   -> sweet           -> 향수 5개
    침대에서 뒹굴기만 했다   -> '침대'  -> powdery·soapy   -> 향수 5개

**두 종류가 섞여 있다. 고치는 방법이 다르다.**

    낱말 경계   '꿀'·'잼'·'숲' 이 다른 낱말 안에 박힌다      꿀꿀한 · 잼민이 · 숲속마을
                낱말로 쓰일 때는 향 표현이 맞다
    문맥       '침대'·'이불' 은 온전한 낱말로 나오는데        침대에서 뒹굴었다
                그 문장이 향 얘기가 아니다

**막으면 잃는 것이 있다.** `꿀 향 나는 향수` 를 함께 막으면 고친 것이 아니다. 이 스크립트는
후보 변형마다 **지금 잡히던 것 중 몇 건을 잃는지** 센다. 잃는 것이 없으면 그 변형은 공짜다.

무엇을 재는가
--------------
    현행     v1_8 그대로
    C1      1글자 표면형 셋(꿀·숲·잼)을 뺀다. 같은 뜻의 긴 표면형은 남긴다
    C2      C1 + '침대'·'침구'·'이불' 에 match_condition 을 건다
    C3      C2 + 2글자 표면형 전체에 match_condition 을 건다

`match_condition` 은 **새로 만드는 장치가 아니다.** 사전 v1_8 이 이미 5행에서 쓴다
(`깨끗한` 이 `비누`·`세탁`·`빨래` 와 같이 나올 때만 soapy). 같은 문법을 쓴다.

**판정 기준을 먼저 적는다** (N4 · 측정과 반영을 분리한다).

    막아야 하는 것   77번의 오탐 문장 3건에서 조건이 0개가 된다
    잃으면 안 되는 것 설문 143 · 합성 600 에서 조건이 줄어드는 문장이 **0건**

    잃는 것이 0건이 아니면 그 변형은 **이 스크립트가 권하지 않는다.** 무엇을 잃는지
    문장을 찍어 사람이 판단한다.

출력
-----
표는 표준출력에만 쓴다. 파일을 만들지 않는다 (41번 이후 관례).
"""
import json
import sys
import tempfile
from pathlib import Path

import pandas as pd

TEAM = Path("C:/Users/SSAFY/Desktop/S15P21E203/ai")
sys.path.insert(0, str(TEAM))
import nlr_engine as e  # noqa: E402

LEXICON = TEAM / "data/domain_lexicon_v1_8.csv"
SYNTH = ("합성 600", "analysis_outputs/34_evalset_stage1_checkpoint.csv", "sentence")
SURVEY = ("설문 143", "analysis_outputs/37_survey_stage1_checkpoint.csv", "query_text")

# 19번 판정 — 동의 표현은 향수 요청이 아니다. 67·72·74번과 같은 규칙
import re  # noqa: E402
SURVEY_NOT_A_QUERY = re.compile(r"^(네|넵|넴|예)\s*[.!]?$|^넵\s*알겠습니다\.?$")

# 77번이 확인한 오탐(앞 셋)과 같은 원인으로 뚫릴 문장들. 이것이 막혀야 고친 것이다.
MISFIRE = [
    "꿀꿀한 기분이야",
    "잼민이들 때문에 시끄러워",
    "침대에서 뒹굴기만 했다",
    "숲속마을에 살고 싶다",
    "나무젓가락 하나 부러뜨렸어",
    "잔디깎기 새로 샀다",
    "초록불에 건넜어",
    "해변가에 주차했다",
    "이불 빨래 개기 싫다",
    # 조건 낱말이 문장에 우연히 있는 경우. `나는` 은 「나는 학생이다」 의 `나는` 과 같다
    "나는 초록불에 건넜어",
    "내가 좋아하는 나무젓가락 같은 거 사줘",
]

# 막으면서 살아야 하는 것. 같은 표현이 향 얘기로 쓰인 경우다.
# **여기서 하나라도 죽으면 그 변형은 못 쓴다.**
MUST_KEEP = [
    "꿀 향 나는 향수 추천해줘",
    "숲 냄새 나는 향수",
    "침대에 누운 것 같은 포근한 향",
    "이불 냄새 나는 향수",
    "숲속에 온 것 같은 향수 추천해줘",
    "꿀을 뿌린 듯 달콤한 향",
    "나무 냄새 나는 향수",
    "잔디 깎은 냄새 같은 것",
    "초록빛 풀 냄새 나는 향",
    "해변 느낌 향수",
    "갓 세탁한 이불 같은 향",
    # 한 낱말만 치는 경우. 화면이 1~500자를 받으므로 실제로 가능하다
    "빨래",
    "상큼",
    "해변",
]

# `침대`·`이불` 계열에 걸 조건. 향 얘기일 때 같이 나오는 낱말이다.
# `깨끗한` 이 쓰는 것과 같은 문법이다 — 새로 만드는 것이 아니다.
BEDDING_COND = "query_contains:냄새,향,포근,뽀송,같은,느낌"

# 1글자 표면형에 걸 조건. **문장이 향 얘기라는 신호**를 요구한다.
# `꿀꿀한 기분이야` 에는 이 중 아무것도 없고 `꿀을 뿌린 듯한 향` 에는 `향` 이 있다.
SCENT_COND = "query_contains:향,냄새,느낌,노트,향수,나는,같은"

# 위에서 `나는` · `같은` 을 뺀 것. 둘이 조건을 뚫는 것을 확인했다 [측정].
#     "나는 초록불에 건넜어"            -> `나는` 때문에 통과 -> green
#     "내가 좋아하는 나무젓가락 같은 거"   -> `같은` 때문에 통과 -> woody
# 둘 다 향과 무관한 문장에 흔히 나오는 말이라 향 얘기의 신호가 되지 못한다.
SCENT_COND2 = "query_contains:향,냄새,느낌,노트,향수"

# 오탐이 실제로 확인된 2글자 표면형만. 2글자 33개 전체에 거는 것(D3)은
# 한 낱말 요청(`빨래` · `상큼` · `해변`)을 죽이므로 범위를 좁힌다.
MISFIRING_TWO = {"이불", "침구", "침대", "잔디", "초록", "해변", "나무"}


def variants():
    """후보 변형. list[(이름, 설명, 적용함수)].

    적용함수는 사전 DataFrame 을 받아 고친 것을 돌려준다. 원본을 고치지 않는다.
    """
    def c1(d):
        """1글자 표면형 셋을 alias 에서 뺀다."""
        d = d.copy()
        d["aliases"] = d["aliases"].apply(lambda v: drop_forms(v, {"꿀", "숲", "잼"}))
        d["expression"] = d["expression"].apply(
            lambda v: v if str(v) not in ("꿀", "숲", "잼") else f"{v} 향")
        return d

    def c2(d):
        d = c1(d)
        return add_condition(d, {"이불", "침구", "침대"}, BEDDING_COND)

    def c3(d):
        d = c2(d)
        two = {f for f in all_surface(d) if len(f) == 2}
        return add_condition(d, two, BEDDING_COND)

    def d1(d):
        """1글자 셋을 빼지 않고 조건만 건다.

        C1 이 비쌌던 이유는 한국어가 교착어라서다. `숲향` · `숲속에` · `숲의` 처럼 뒤에
        무엇이든 붙는데, 부분 문자열 매칭이 그것을 잡던 **유일한 수단**이었다. 빼면
        `숲 냄새` 처럼 띄어 쓴 것만 남는다.
        """
        return add_condition(d, {"꿀", "숲", "잼"}, SCENT_COND)

    def d2(d):
        return add_condition(d1(d), {"이불", "침구", "침대"}, BEDDING_COND)

    def d3(d):
        d = d2(d)
        two = {f for f in all_surface(d) if len(f) == 2}
        return add_condition(d, two, SCENT_COND)

    def e1(d):
        """오탐이 확인된 표면형에만, 좁힌 조건을 건다. 지금까지 중 가장 작은 변경이다."""
        return add_condition(d, {"꿀", "숲", "잼"} | MISFIRING_TWO, SCENT_COND2)

    return [("C1", "1글자 셋(꿀·숲·잼)을 뺀다", c1),
            ("C2", "C1 + 침대·침구·이불에 조건", c2),
            ("C3", "C2 + 2글자 전체에 조건", c3),
            ("D1", "1글자 셋을 빼지 않고 조건만 건다", d1),
            ("D2", "D1 + 침대·침구·이불에 조건", d2),
            ("D3", "D2 + 2글자 전체에 조건", d3),
            ("E1", "오탐 확인된 10개에만 · 조건에서 나는·같은을 뺀다", e1)]


def drop_forms(aliases, drop):
    """alias 문자열에서 특정 표면형을 뺀다. str."""
    if not isinstance(aliases, str):
        return aliases
    kept = [a for a in aliases.split("|") if a.strip() not in drop]
    return "|".join(kept)


def all_surface(d):
    """사전의 모든 표면형. set[str]."""
    out = set()
    for _, r in d.iterrows():
        out.add(str(r["expression"]).strip())
        for a in _aliases(r).split("|"):
            if a.strip():
                out.add(a.strip())
    return {f for f in out if f and f != "nan"}


def add_condition(d, forms, condition):
    """그 표면형을 가진 행에 match_condition 을 건다. DataFrame.

    **이미 조건이 있는 행은 건드리지 않는다.** 덮어쓰면 `깨끗한` 처럼 이미 판정을 거친
    조건이 사라진다.
    """
    d = d.copy()
    for i, r in d.iterrows():
        row_forms = {str(r["expression"]).strip()}
        row_forms |= {a.strip() for a in _aliases(r).split("|") if a.strip()}
        if row_forms & forms and not _text(r.get("match_condition")):
            d.at[i, "match_condition"] = condition
    return d


def _text(value):
    """결측을 빈 문자열로. str.

    **`str(value or "")` 로 쓰면 안 된다.** pandas 의 결측(`NaN`)은 참이라 그대로 남고
    `str(NaN)` 이 `'nan'` 이 되어 "값이 있다" 로 읽힌다. 처음에 그렇게 썼다가 C2·C3 의
    조건이 한 행도 안 걸렸고 결과가 C1 과 같게 나왔다.
    """
    return "" if pd.isna(value) else str(value).strip()


def _aliases(row):
    """alias 칸을 문자열로. str."""
    return _text(row.get("aliases"))


def load_rows(path, col):
    """체크포인트를 (문장, ①단계 dict) 목록으로. list."""
    d = pd.read_csv(path)
    out = []
    for r in d.to_dict("records"):
        text = str(r[col])
        if SURVEY_NOT_A_QUERY.match(text.strip()):
            continue
        try:
            o = json.loads(r["raw_response"])
        except Exception:
            o = None
        out.append((text, o if isinstance(o, dict) else None))
    return out


def build(d):
    """고친 사전으로 index 를 만든다. dict. 임시 파일에 쓰고 읽는다 — 원본을 안 건드린다."""
    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False,
                                     encoding="utf-8", newline="") as f:
        d.to_csv(f, index=False)
        tmp = f.name
    try:
        return e.load_index(lexicon_csv=tmp)
    finally:
        Path(tmp).unlink(missing_ok=True)


def cores(index, rows):
    """문장별 조건 집합. dict[str, frozenset]."""
    return {t: frozenset(e.understand(index, t, o)["core"]) for t, o in rows}


def main():
    base_lex = pd.read_csv(LEXICON)
    print("=" * 92)
    print("짧은 표면형을 막으면 무엇을 잃는가 — GMS 호출 없음")
    print("=" * 92)
    print(f"사전 {LEXICON.name} · {len(base_lex)}행")

    datasets = []
    for name, path, col in (SURVEY, SYNTH):
        if not Path(path).exists():
            print(f"  ⚠ {path} 가 없다. {name} 은 건너뛴다")
            continue
        rows = load_rows(path, col)
        datasets.append((name, rows))
        print(f"  {name} — {len(rows)}건")

    probe = [(t, None) for t in MISFIRE + MUST_KEEP]

    base_index = build(base_lex)
    base = {name: cores(base_index, rows) for name, rows in datasets}
    base_probe = cores(base_index, probe)

    print()
    print("현행에서 확인 문장이 어떻게 나오는가")
    for t in MISFIRE:
        print(f"  ✗ 막아야 함  {t:28} -> {sorted(base_probe[t])}")
    for t in MUST_KEEP:
        print(f"  ✓ 살아야 함  {t:28} -> {sorted(base_probe[t])}")

    for code, why, apply in variants():
        index = build(apply(base_lex))
        got = cores(index, probe)
        print()
        print("=" * 92)
        print(f"■ {code} — {why}")
        print("=" * 92)

        blocked = sum(1 for t in MISFIRE if not got[t])
        kept = sum(1 for t in MUST_KEEP if got[t])
        print(f"  오탐 {blocked}/{len(MISFIRE)} 막힘 · 살려야 할 것 {kept}/{len(MUST_KEEP)} 살아남음")
        for t in MISFIRE:
            mark = "막힘" if not got[t] else "**안 막힘**"
            print(f"    {mark:10} {t:28} -> {sorted(got[t])}")
        for t in MUST_KEEP:
            mark = "살아남음" if got[t] else "**같이 죽음**"
            print(f"    {mark:10} {t:28} -> {sorted(got[t])}")

        print()
        for name, rows in datasets:
            now = cores(index, rows)
            lost = [t for t in now if base[name][t] and not now[t]]
            shrunk = [t for t in now if now[t] and now[t] < base[name][t]]
            grew = [t for t in now if now[t] > base[name][t]]
            print(f"  {name}  조건을 통째로 잃은 문장 {len(lost)}건 · "
                  f"줄어든 문장 {len(shrunk)}건 · 늘어난 문장 {len(grew)}건")
            for t in lost[:6]:
                print(f"      잃음  {t[:56]:58} {sorted(base[name][t])} -> []")
            for t in shrunk[:6]:
                print(f"      줄음  {t[:56]:58} {sorted(base[name][t])} -> {sorted(now[t])}")
            if len(lost) + len(shrunk) > 12:
                print(f"      ... 앞 6건씩만 찍었다")

    print()
    print("=" * 92)
    print("판정 — 잃는 것이 0건인 변형만 공짜다. 아니면 무엇을 잃는지 사람이 본다")
    print("=" * 92)


if __name__ == "__main__":
    main()

"""사전 v1.14 -> v1.15. 짧은 표면형이 다른 낱말 안에 박히는 오탐을 문맥 조건으로 막는다.

    ./venv/Scripts/python.exe -W ignore 80_lexicon_v1_15_short_form_condition.py

API 호출 0회. v1.14 를 읽는다. 판정을 통과할 때만 v1.15 를 쓴다.

무엇이 문제인가
----------------
`_lexicon_lookup` 이 `if form in haystack` 한 줄이라 **표면형이 더 큰 낱말 안에 박혀도
걸린다.** 77번에서 향과 무관한 문장 11건을 넣었더니 11건 다 향수가 나왔다
[측정 2026-09-18 · 3회 반복해도 같았다].

    "꿀꿀한 기분이야"          -> '꿀'   -> sweet           -> 향수 5개
    "잼민이들 때문에 시끄러워"   -> '잼'   -> sweet           -> 향수 5개
    "나무젓가락 하나 부러뜨렸어" -> '나무'  -> woody           -> 향수 5개
    "초록불에 건넜어"          -> '초록'  -> green           -> 향수 5개
    "해변가에 주차했다"        -> '해변'  -> coconut/tropical -> 향수 5개
    "침대에서 뒹굴기만 했다"    -> '침대'  -> powdery/soapy    -> 향수 5개

측정 기록 14번이 이 위험을 이미 적어 뒀다 — *"지금 오탐이 0인 것은 사전에 `달`·`무겁`
같은 어간이 없어서다. 설계가 막은 것이 아니라 운이다."* **그 운이 1글자 명사에서는
따르지 않았다.**

왜 문맥 조건인가 — 두 대안을 재고 골랐다
-----------------------------------------
    표면형을 뺀다        78번 [측정]  오탐 5/11 막힘 · **설문 4건 · 합성 14건 손실**
    낱말 경계를 본다      79번 [측정]  오탐 8/11 막힘 · **설문 2건 · 합성 9건 손실**
    문맥 조건 (이 변경)   78·79번     오탐 10/11 막힘 · **손실 0건**

앞의 둘이 비싼 이유가 같다. **한국어가 교착어라서다.** `숲향` · `숲속에` · `숲의` 처럼
뒤에 무엇이든 붙는데, 부분 문자열 매칭이 그것을 잡던 유일한 수단이었다. 빼거나 경계를
요구하면 `숲향 나는 향수 추천좀` 같은 정상 문장을 잃는다.

경계 검사는 2026-09-18 GPT 조사가 권한 방식인데(Algolia 의 word 단위 rule · FlashText
의 keyword boundary), **우리 데이터에서는 문맥 조건이 나았다.** 조사도 한국어에 영어식
`\\b` 를 그대로 쓸 수 없다고 적었고, 조사가 제안한 조사(助詞) allowlist 로는
`초록불`(막아야 함)과 `초록빛`(살려야 함)을 가르지 못한다.

`match_condition` 은 새로 만드는 장치가 아니다. v1.14 가 이미 `깨끗한` 에서 쓴다
(`query_contains:비누,세탁,빨래,...`). 문법도 검사 코드도 그대로 쓴다.

조건 낱말을 무엇으로 할지도 쟀다
---------------------------------
처음에 짐작으로 일곱 개를 적었다가 둘을 빼고 둘을 더 뺐다 [측정 2026-09-18].

    낱말    설문 143   합성 600   향 무관 18   판정
    향       96%       99%        0%         쓴다
    냄새     15%       23%        0%         쓴다
    느낌     24%       40%        0%         쓴다
    노트      6%        0%        6%         **뺀다** — '노트북' 에 걸린다. 조건 낱말도
                                             부분 문자열로 검사되므로 같은 함정이다
    향수     70%        1%        0%         **뺀다** — '향' 의 부분집합이라 743건 중
                                             0건을 추가로 건진다. 군더더기다
    나는     24%        2%        6%         **뺀다** — "나는 초록불에 건넜어" 가 통과
    같은     10%       26%        6%         **뺀다** — "나무젓가락 같은 거" 가 통과

    향·냄새·느낌 셋   설문 99.3% · 합성 100.0% · 향 무관 0건 통과

판정 기준 — 측정 전에 정한다 (N4 · 56번과 같은 관례)
------------------------------------------------------
    채택   오탐 문장에서 조건이 0개가 되고
           **설문 143 · 합성 600 에서 조건이 줄어든 문장이 0건**이고
           NDCG@5 델타 >= 0
    기각   위 중 하나라도 어긋나면. 무엇을 잃는지 문장을 찍어 사람이 본다

NDCG 는 이 스크립트가 재지 않는다. 41번으로 따로 잰다 (아래 「재현」).

출력
-----
    data/scent_knowledge/domain_lexicon_v1_15.csv   판정을 통과할 때만
    analysis_outputs/80_lexicon_v1_15_changelog.md
표는 표준출력에만 쓴다.
"""
import importlib.util
import json
import pathlib
import re
import sys
import tempfile

import pandas as pd

sys.path.insert(0, "C:/Users/SSAFY/Desktop/S15P21E203/ai")
import nlr_engine as e  # noqa: E402

SRC = pathlib.Path("data/scent_knowledge/domain_lexicon_v1_14.csv")
DST = pathlib.Path("data/scent_knowledge/domain_lexicon_v1_15.csv")
CHANGELOG = pathlib.Path("analysis_outputs/80_lexicon_v1_15_changelog.md")

SURVEY = ("설문 143", "analysis_outputs/37_survey_stage1_checkpoint.csv", "query_text")
SYNTH = ("합성 600", "analysis_outputs/34_evalset_stage1_checkpoint.csv", "sentence")

# 19번 판정 — 동의 표현은 향수 요청이 아니다. 67·72·74·78번과 같은 규칙
NOT_A_QUERY = re.compile(r"^(네|넵|넴|예)\s*[.!]?$|^넵\s*알겠습니다\.?$")

CONDITION = "query_contains:향,냄새,느낌"

# 조건을 걸 표면형. **81번이 어휘 조사를 엔진으로 검증해 정했다** — 작성자가 떠올린
# 문장에서 역산하지 않았다. 이것이 든 **행 전체**에 조건이 걸린다 (match_condition 은
# 행 단위다). 딸려오는 표면형은 changelog 에 적는다.
#
# 판정 기준 — 그 표면형을 포함하는 향 무관 낱말이 실재하고, 그 낱말을 엔진에 넣었을 때
# 실제로 조건이 생기는 것만 [측정 2026-09-18 · 81번].
#
#     꿀    꿀꿀하다 · 꿀밤 · 꿀팁        세탁   세탁기 · 세탁소
#     잼    잼민이                     빨래   빨래판 · 빨래감
#     초록   초록불                     잔디   잔디깎기 · 잔디밭
#     분내   분내다(화내다)              이불   이불킥
#     산림   산림청
#
# **`숲` · `침대` · `침구` · `해변` 은 뺐다.** 어휘 조사에서 향 무관 낱말이 나오지 않았다.
# 77번이 이 넷에서 본 오탐(`"침대에서 뒹굴기만 했다"`)은 낱말 경계 문제가 아니라 **문맥
# 문제**라 어휘 조사로는 판정할 수 없다. 기준을 결과에 맞춰 고치지 않으려고 뺐다.
# (다만 `침대`·`침구`는 `이불` 과 같은 행이라 결과적으로 함께 제약된다 — 아래 참고.)
#
# **근거가 있는데도 뺀 것이 셋 있다** [측정 2026-09-18 · 81번].
#
#     우디   `KOREAN_ACCORD` 로 매칭돼 **조건이 아예 닿지 않는다.** 걸어도 안 막히고
#           같은 행의 `편백`·`고목` 만 제약한다
#     나무   `나무젓가락`·`나무라다` 를 막지만 같은 행의 `편백`·`고목`·`목재`·`톱밥` 이
#           함께 제약돼 **`"편백나무"` 가 죽는다.** 대가가 크다
#     과즙   `과즙기` 하나를 막으려고 `상큼한`·`상큼`·`새콤`·`껍질` 을 제약한다.
#           `상큼한` 은 흔한 향 표현이라 명백히 손해다
#
# `match_condition` 이 **행 단위**라 생기는 한계다. 표면형 단위로 걸려면 행을 쪼개야
# 하는데(같은 accord 를 두 entry_id 로) 사전 구조 변경이라 이번에는 하지 않는다.
TARGET = {"꿀", "분내", "빨래", "산림", "세탁", "이불", "잔디", "잼", "초록"}

# 막아야 하는 것 — **81번이 어휘 조사에서 받아 엔진으로 검증한 낱말이다.**
# 작성자가 지어낸 문장이 아니라 국어사전·신조어로 실재하는 낱말이고, 부분 문자열
# 매칭이라 낱말 하나만 넣어도 오탐이 재현된다.
MISFIRE = [
    "꿀꿀하다", "꿀밤", "꿀팁",
    "잼민이",
    "분내다",
    "산림청",
    "세탁기", "세탁소",
    "이불킥",
    "잔디깎기", "잔디밭",
    "초록불",
    "빨래판", "빨래감",
]

# 근거는 있으나 **대상에서 뺀 것**. 이 변경으로 막히지 않는다는 사실을 기록으로 남긴다.
NOT_BLOCKED = [
    ("우디", "KOREAN_ACCORD 경로라 조건이 닿지 않는다"),
    ("나무젓가락", "`나무` 를 걸면 `편백나무` 가 죽어서 뺐다"),
    ("나무라다", "위와 같다"),
    ("과즙기", "`과즙` 을 걸면 `상큼한` 이 제약돼서 뺐다"),
]

# 살려야 하는 것. 앞쪽 일곱은 **어휘 조사가 「향 무관」으로 잘못 분류한 향·맛 표현**이고
# (사전이 바로 그 뜻으로 매핑해 둔 것들이다) 나머지는 향 맥락 문장이다.
MUST_KEEP = [
    # 어휘 조사가 「향 무관」으로 잘못 분류한 향·맛 표현
    "달달하다", "새콤달콤", "말캉말캉", "탱글탱글", "풋풋하다", "편백나무", "흰꽃",
    # 조건을 거는 행에 **딸려 들어가는 표면형 전체.** 전부 향 표현이라 살아야 한다.
    # 행 단위 조건의 진짜 비용이 여기서 드러난다 — 한 낱말로 입력하면 조건 낱말이 없다.
    "갓 세탁한", "세탁한",
    "침구", "침대", "코튼 이불",
    "분가루", "아기분", "베이비파우더", "로션 같은",
    "당밀", "시럽",
    "생풀", "수액", "잎사귀", "젖은 잎",
    "고목", "목재", "숲", "연필심", "톱밥", "편백",
    # 향 맥락 문장
    "꿀 향 나는 향수 추천해줘",
    "꿀을 뿌린 듯 달콤한 향",
    "초록빛 풀 냄새 나는 향",
    "잔디 깎은 냄새 같은 것",
    "이불 냄새 나는 향수",
    "빨래 냄새 나는 향수 찾고 있어",
    "갓 세탁한 이불 같은 향",
]


def text_of(value):
    """결측을 빈 문자열로. str.

    `str(value or "")` 로 쓰면 pandas 의 결측이 `'nan'` 이 되어 "값이 있다" 로 읽힌다.
    78번에서 그 실수로 조건이 한 행도 안 걸렸다.
    """
    return "" if pd.isna(value) else str(value).strip()


def surfaces(row):
    """그 행이 문장에서 찾는 표면형 전체. set[str]."""
    out = {text_of(row["expression"])}
    out |= {a.strip() for a in text_of(row["aliases"]).split("|") if a.strip()}
    return {f for f in out if f}


def apply_condition(lexicon):
    """대상 표면형을 새 행으로 분리해 거기에만 조건을 건다. (DataFrame, list[dict]).

    **행을 쪼갠다.** `match_condition` 이 행 단위라, 대상이 든 행에 그냥 조건을 걸면
    같은 행의 다른 별칭까지 제약된다. 처음에는 그렇게 만들었다가 **향 표현 22개가 함께
    죽는 것**을 보고 바꿨다 [측정 2026-09-18].

        그냥 걸면   kr.source.honey_syrup  꿀·잼·당밀·시럽  -> 넷 다 제약
        쪼개면      kr.source.honey_syrup  당밀·시럽        -> 조건 없음. 그대로 산다
                   kr.source.honey_syrup.short  꿀·잼      -> 조건 있음

    원래 행에서 대상 표면형을 빼고, 대상만 담은 새 행을 `.short` 접미사를 붙인
    `entry_id` 로 더한다. accord·등급·근거는 원래 행에서 그대로 물려받는다.

    **이미 조건이 있는 행은 건드리지 않는다.** 덮어쓰면 `깨끗한` 처럼 이미 판정을 거친
    조건이 사라진다.

    **`optional` 행도 건드리지 않는다.** 조건을 만들지 않는 행이라 오탐에 기여하지
    않고, 측정 기록 22번이 `optional` 을 "설계와 어긋난 누락" 으로 따로 다루고 있어
    이 변경과 섞지 않는다.
    """
    out = lexicon.copy()
    changed, added = [], []
    for i, row in out.iterrows():
        if text_of(row["required"]) != "core":
            continue
        forms = surfaces(row)
        hit = forms & TARGET
        if not hit or text_of(row.get("match_condition")):
            continue

        # 원래 행에서 대상 표면형을 뺀다. expression 이 대상이면 남은 것 중 하나로 바꾼다.
        rest = sorted(forms - TARGET)
        expression = text_of(row["expression"])
        out.at[i, "expression"] = expression if expression not in TARGET else rest[0]
        out.at[i, "aliases"] = "|".join(rest)

        # 대상만 담은 새 행. 나머지 칸은 원래 행을 그대로 물려받는다.
        new = row.copy()
        new["entry_id"] = f"{row['entry_id']}.short"
        new["expression"] = sorted(hit)[0]
        new["aliases"] = "|".join(sorted(hit))
        new["match_condition"] = CONDITION
        new["rationale"] = (
            f"{text_of(row['rationale'])} "
            f"[80] 짧은 표면형이 다른 낱말 안에 박히는 오탐을 막으려고 "
            f"{row['entry_id']} 에서 분리해 문맥 조건을 걸었다.")
        added.append(new)

        changed.append({
            "entry_id": row["entry_id"],
            "candidate": row["candidate_name"],
            "target": sorted(hit),
            "kept_free": rest,
        })

    if added:
        out = pd.concat([out, pd.DataFrame(added)], ignore_index=True)
    return out, changed


def build(lexicon):
    """그 사전으로 index 를 만든다. dict. 임시 파일을 쓰고 지운다 — 원본을 안 건드린다."""
    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False,
                                     encoding="utf-8", newline="") as handle:
        lexicon.to_csv(handle, index=False)
        tmp = handle.name
    try:
        return e.load_index(lexicon_csv=tmp)
    finally:
        pathlib.Path(tmp).unlink(missing_ok=True)


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


def cores(index, rows):
    """문장별 조건 집합. dict[str, frozenset]."""
    return {t: frozenset(e.understand(index, t, o)["core"]) for t, o in rows}


def ndcg(before_path, after_path):
    """두 사전의 NDCG@5 와 조건충족률. list[tuple[str, float, float]].

    41번을 그대로 불러 쓴다 — 같은 계산을 두 벌 두면 어긋난다. 56번이 쓴 방식이다.
    **changelog 의 숫자를 하드코딩하지 않으려고 여기서 잰다.** 재현할 때 값이 달라지면
    기록도 같이 달라져야 한다.
    """
    spec = importlib.util.spec_from_file_location("ndcg41", "41_lexicon_ndcg.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    key = pd.read_csv("analysis_outputs/32_evalset_answer_key.csv").set_index("perfume_id")
    queries = module.load_queries()
    out = []
    for path in (before_path, after_path):
        frame = module.score(str(path), queries, key)
        out.append((pathlib.Path(path).name,
                    float(frame["ndcg5"].mean()), float(frame["gain_ratio"].mean())))
    return out


def main():
    lexicon = pd.read_csv(SRC)
    after, changed = apply_condition(lexicon)

    print("=" * 92)
    print(f"사전 v1.14 -> v1.15 — 짧은 표면형에 문맥 조건. GMS 호출 0회")
    print("=" * 92)
    print(f"{SRC.name} {len(lexicon)}행 · 조건을 건 행 {len(changed)}개")
    print(f"조건 — {CONDITION}")
    print()
    for item in changed:
        print(f"  {item['entry_id']}.short -> {item['candidate']}")
        print(f"  {'':24} 조건 검사  {' · '.join(item['target'])}")
        print(f"  {'':24} 원래 행에 남김 {' · '.join(item['kept_free']) or '(없음)'}")
    print()

    base_index = build(lexicon)
    new_index = build(after)

    # ---- 확인 문장 ----
    print("=" * 92)
    print("■ 확인 문장")
    print("=" * 92)
    blocked = 0
    for text in MISFIRE:
        got = sorted(e.understand(new_index, text, None)["core"])
        was = sorted(e.understand(base_index, text, None)["core"])
        if not got:
            blocked += 1
        mark = "막힘" if not got else "**안 막힘**"
        print(f"  {mark:10} {text:30} {was} -> {got}")
    kept = 0
    for text in MUST_KEEP:
        got = sorted(e.understand(new_index, text, None)["core"])
        if got:
            kept += 1
        else:
            print(f"  **같이 죽음** {text:30} -> []")
    print(f"\n  오탐 {blocked}/{len(MISFIRE)} 막힘 · 살릴 것 {kept}/{len(MUST_KEEP)} 생존")

    print()
    print("  대상에서 뺀 것 — 막히지 않는 것이 정상이다")
    for word, why in NOT_BLOCKED:
        got = sorted(e.understand(new_index, word, None)["core"])
        print(f"    {word:10} -> {str(got):28} {why}")

    # ---- 평가셋 손실 ----
    print()
    print("=" * 92)
    print("■ 평가셋에서 잃는 것 — 판정의 핵심")
    print("=" * 92)
    total_lost = 0
    for name, path, column in (SURVEY, SYNTH):
        if not pathlib.Path(path).exists():
            print(f"  ⚠ {path} 가 없다. {name} 을 건너뛴다")
            continue
        rows = load_rows(path, column)
        was = cores(base_index, rows)
        now = cores(new_index, rows)
        lost = [t for t in now if was[t] and not now[t]]
        shrunk = [t for t in now if now[t] and now[t] < was[t]]
        grew = [t for t in now if now[t] > was[t]]
        total_lost += len(lost) + len(shrunk)
        print(f"  {name} {len(rows)}건 — 통째로 잃음 {len(lost)}건 · "
              f"줄어듦 {len(shrunk)}건 · 늘어남 {len(grew)}건")
        for t in (lost + shrunk)[:8]:
            print(f"      {t[:56]:58} {sorted(was[t])} -> {sorted(now[t])}")

    # ---- 판정 ----
    print()
    print("=" * 92)
    passed = total_lost == 0
    print(f"판정 — 평가셋 손실 {total_lost}건 · {'채택' if passed else '기각'}")
    print("=" * 92)
    if not passed:
        print("손실이 0건이 아니다. v1.15 를 쓰지 않는다. 위 문장을 사람이 본다.")
        return

    DST.parent.mkdir(parents=True, exist_ok=True)
    after.to_csv(DST, index=False, encoding="utf-8")
    print(f"{DST} 를 썼다 ({len(after)}행)")

    print()
    print("=" * 92)
    print("■ NDCG@5 — 41번을 그대로 불러 잰다")
    print("=" * 92)
    scored = ndcg(SRC, DST)
    for name, value, ratio in scored:
        print(f"  {name:32} NDCG@5 {value:.6f} · 조건충족률 {ratio:.6f}")
    delta = scored[1][1] - scored[0][1]
    print(f"  {'델타':32} {delta:+.6f}")
    if delta < 0:
        print("\n  ⚠ 델타가 음수다. 판정 기준(>= 0)에 어긋난다 — v1.15 를 쓰지 말아야 한다.")
        print("  파일은 이미 썼으므로 사람이 보고 지울지 정한다.")

    write_changelog(changed, blocked, kept, scored, delta)
    print(f"\n{CHANGELOG} 를 썼다")


def write_changelog(changed, blocked, kept, scored, delta):
    """변경 기록. None. 56번과 같은 형식이다."""
    lines = [
        "# 80. 사전 v1.14 -> v1.15 — 짧은 표면형이 낱말 안에 박히는 오탐을 문맥 조건으로 막는다",
        "",
        "재현: `./venv/Scripts/python.exe -W ignore 80_lexicon_v1_15_short_form_condition.py`",
        f"API 호출 0회 · 행 수 변화 없음 · 조건을 건 행 {len(changed)}개",
        "",
        "## 무엇이 문제였나",
        "",
        "`_lexicon_lookup` 이 `if form in haystack` 이라 표면형이 더 큰 낱말 안에 박혀도 "
        "걸린다. 77번에서 향과 무관한 문장 11건을 넣었더니 11건 다 향수가 나왔다 "
        "[측정 2026-09-18 · 3회 반복해도 같았다].",
        "",
        "```",
        "\"꿀꿀한 기분이야\"          -> '꿀'   -> sweet           -> 향수 5개",
        "\"잼민이들 때문에 시끄러워\"   -> '잼'   -> sweet           -> 향수 5개",
        "\"나무젓가락 하나 부러뜨렸어\" -> '나무'  -> woody           -> 향수 5개",
        "\"초록불에 건넜어\"          -> '초록'  -> green           -> 향수 5개",
        "\"해변가에 주차했다\"        -> '해변'  -> coconut/tropical -> 향수 5개",
        "```",
        "",
        "측정 기록 14번이 이 위험을 적어 뒀다 — *\"지금 오탐이 0인 것은 사전에 `달`·`무겁` "
        "같은 어간이 없어서다. 설계가 막은 것이 아니라 운이다.\"* **1글자 명사에서는 그 운이 "
        "따르지 않았다.**",
        "",
        "## 왜 문맥 조건인가 — 대안 둘을 재고 골랐다",
        "",
        "| 방법 | 오탐 막음 | 설문 143 손실 | 합성 600 손실 |",
        "|---|---:|---:|---:|",
        "| 표면형을 뺀다 (78번) | 5/11 | 4건 | 14건 |",
        "| 낱말 경계를 본다 (79번) | 8/11 | 2건 | 9건 |",
        "| **문맥 조건 (이 변경)** | **10/11** | **0건** | **0건** |",
        "",
        "앞의 둘이 비싼 이유가 같다. **한국어가 교착어라서다.** `숲향`·`숲속에`·`숲의` 처럼 "
        "뒤에 무엇이든 붙는데 부분 문자열 매칭이 그것을 잡던 유일한 수단이었다. 실제로 잃은 "
        "문장이 `숲향 나는 향수 추천좀`·`나무통에 숙성한 술을 떠올리게 하는 향` 같은 것들이다.",
        "",
        "경계 검사는 2026-09-18 GPT 조사가 권한 방식이다(Algolia 의 word 단위 rule · "
        "FlashText 의 keyword boundary). **우리 데이터에서는 문맥 조건이 나았다.** 조사가 "
        "제안한 조사(助詞) allowlist 로는 `초록불`(막아야 함)과 `초록빛`(살려야 함)을 "
        "가르지 못한다.",
        "",
        "## 조건 낱말을 어떻게 골랐나",
        "",
        "처음에 짐작으로 일곱 개를 적었다가 넷을 뺐다 [측정 2026-09-18].",
        "",
        "| 낱말 | 설문 143 | 합성 600 | 향 무관 18 | 판정 |",
        "|---|---:|---:|---:|---|",
        "| `향` | 96% | 99% | 0% | 쓴다 |",
        "| `냄새` | 15% | 23% | 0% | 쓴다 |",
        "| `느낌` | 24% | 40% | 0% | 쓴다 |",
        "| `노트` | 6% | 0% | **6%** | 뺀다 — `노트북` 에 걸린다 |",
        "| `향수` | 70% | 1% | 0% | 뺀다 — `향` 의 부분집합. 743건 중 0건 추가 |",
        "| `나는` | 24% | 2% | **6%** | 뺀다 — \"나는 초록불에 건넜어\" 통과 |",
        "| `같은` | 10% | 26% | **6%** | 뺀다 — \"나무젓가락 같은 거\" 통과 |",
        "",
        "**`노트` 가 `노트북` 에 걸린 것이 시사적이다.** 조건 낱말도 부분 문자열로 검사되므로 "
        "고치려는 문제와 똑같은 함정에 빠질 수 있다.",
        "",
        f"셋을 합치면 설문 99.3% · 합성 100.0% 를 덮고 향 무관 18건은 0건이 통과한다.",
        "",
        "## 바꾼 행",
        "",
        f"조건 — `{CONDITION}`",
        "",
        "**행을 쪼갰다.** `match_condition` 이 행 단위라 대상이 든 행에 그냥 조건을 걸면 "
        "같은 행의 다른 별칭까지 제약된다. 처음에 그렇게 만들었더니 **향 표현 22개가 함께 "
        "죽었다**(`편백`·`고목`·`목재`·`당밀`·`시럽`·`분가루`·`침대` …). 그래서 조건이 "
        "필요한 표면형만 `.short` 접미사를 붙인 새 entry_id 로 분리했다. 사전이 63행에서 "
        "72행이 된 이유다.",
        "",
        "| 새 행 | 조건을 검사할 표면형 | 원래 행에 그대로 남긴 것 | accord |",
        "|---|---|---|---|",
    ]
    for item in changed:
        lines.append(f"| `{item['entry_id']}.short` | {' · '.join(item['target'])} | "
                     f"{' · '.join(item['kept_free']) or '—'} | {item['candidate']} |")
    lines += [
        "",
        "딸려온 것 중 `풀 냄새`·`풀향`·`이불 냄새`·`백단향` 처럼 **자체에 `향`·`냄새` 가 든 "
        "표면형은 조건을 자동으로 통과한다.** 평가셋 손실이 0건인 이유 중 하나다.",
        "",
        "`optional` 행은 건드리지 않았다. 조건을 만들지 않는 행이라 오탐에 기여하지 않고, "
        "측정 기록 22번이 `optional` 을 따로 다루고 있어 이 변경과 섞지 않는다.",
        "",
        "## 측정 결과",
        "",
        "```",
        f"오탐 문장          {blocked}/{len(MISFIRE)} 막힘",
        f"살려야 할 문장      {kept}/{len(MUST_KEEP)} 생존",
        "설문 143           조건이 줄어든 문장 0건",
        "합성 600           조건이 줄어든 문장 0건",
        "```",
        "",
        "| 사전 | NDCG@5 | 조건충족률 |",
        "|---|---:|---:|",
    ] + [
        f"| `{name}` | {value:.6f} | {ratio:.6f} |" for name, value, ratio in scored
    ] + [
        f"| **델타** | **{delta:+.6f}** | |",
        "",
        "NDCG 가 움직이지 않은 것은 **평가셋에서 조건이 바뀐 문장이 0건**이기 때문이다. "
        "이 변경은 평가셋이 담지 못하는 입력(향과 무관한 일상 문장)에서만 동작을 바꾼다. "
        "**합성 600건과 설문 143건은 전부 향수 요청이라 이 변경의 이득이 보이지 않는다** — "
        "해롭지 않다는 것까지만 말할 수 있다.",
        "",
        "## 남는 것",
        "",
        "- **`\"이불 빨래 개기 싫다\"` 는 여전히 뚫린다.** `빨래` 에는 조건을 걸지 않았다. "
        "걸면 `빨래` 한 낱말 입력이 죽는다. 같은 원인이라 둘 다는 못 얻는다",
        "- **`\"꿀꿀한 향이 나\"` 처럼 조건 낱말이 우연히 든 문장은 통과한다.** 조건은 "
        "\"향 얘기냐\" 를 낱말 셋으로 근사하는 것이라 원리상 완벽해지지 않는다",
        "- **한 낱말 입력**(`해변`)은 조건을 못 만족해 죽는다. 다만 설문 143건에 띄어쓰기 "
        "없는 한 낱말 입력이 **0건**이라 지금 데이터로는 걱정할 근거가 없다 [측정]. "
        "실사용 로그가 쌓이면 다시 본다",
        "",
        "## 이 평가셋이 답하지 못하는 것",
        "",
        "확인 문장 25개는 **내가 만든 것**이다. 실제 사용자가 향과 무관한 말을 어떻게 쓰는지는 "
        "데이터가 없다. 오탐 11건으로 잰 100% 는 Wilson 95% 구간이 74.1%~100% 라 "
        "**어느 표면형까지 일반화되는지 말할 수 없다.** 표면형마다 정상·오탐 문장을 만들어 "
        "180개 규모로 넓히는 것이 다음 단계다.",
        "",
        "## ⏸ 상태 — 넣기로 정했고 대상 범위를 조사 중이다 (2026-09-18)",
        "",
        "### 넣기로 한 근거 — 비용이 0 이면 편익 불확실성이 결정을 바꾸지 않는다",
        "",
        "```",
        "넣는다      오탐 막힘 (빈도 미상)   ·  잃는 것 0건 (설문 143 + 합성 600 · NDCG 델타 0)",
        "안 넣는다    오탐 그대로 (빈도 미상)  ·  잃는 것 없음",
        "```",
        "",
        "**기댓값이 음수가 될 수 없다.** 편익이 0일 수는 있어도 마이너스는 아니다. "
        "되돌리기도 CSV 칸을 비우는 한 줄이다. 사용자가 겪기 전에 막는 예방 조치로 본다.",
        "",
        "처음에는 *\"편익을 못 쟀으니 보류\"* 로 판단했는데 **`spec.md` §7.2 를 잘못 "
        "적용한 것이었다.** 그 조항은 사전 **확장**의 출처를 제한한다. 이 변경은 **제약**이고 "
        "둘은 위험 방향이 반대다.",
        "",
        "```",
        "확장   근거 없이 넣으면 -> 틀린 매핑이 생긴다     -> 출처를 엄격히 따진다",
        "제약   근거 없이 걸면  -> 정상 매칭을 잃는다      -> 743건으로 쟀고 0건이다",
        "```",
        "",
        "### 남은 것 — 어느 표면형에 걸 것인가",
        "",
        "오탐이 실재하는 것과 **어디에 조건을 걸어야 하는지**는 다른 문제다. 지금 대상 10개는 "
        "작성자가 떠올린 문장에서 역산한 것이라 과하거나 모자랄 수 있다. 조건을 거는 행마다 "
        "별칭이 함께 제약을 받으므로(이 문서 「바꾼 행」의 「딸려옴」) 근거 없는 것까지 걸면 "
        "불필요한 제약이 생긴다.",
        "",
        "**조사 방법** — 표면형 36개 각각에 대해 그 글자열을 포함하는 **향과 무관한 한국어 "
        "낱말**을 모은 뒤, 그 낱말을 **그대로 엔진에 입력해** 오탐이 실제로 나는지 확인한다. "
        "부분 문자열 매칭이라 문장으로 감쌀 필요가 없다. 낱말은 국어사전으로 검증되므로 "
        "지어낸 문장보다 근거가 단단하다.",
        "",
        "**판정 기준 (결과를 보기 전에 정한다)**",
        "",
        "```",
        "조건을 건다      향 무관 낱말이 1개 이상 실재하고",
        "                그 낱말이 실제로 엔진에서 오탐을 내고",
        "                조건을 걸어도 평가셋 손실이 0건일 때",
        "조건을 안 건다    낱말이 0개이거나 · 사전 등재가 확인되지 않거나 · 손실이 생길 때",
        "```",
        "",
        "### 근거의 현재 수준",
        "",
        "| | 근거 |",
        "|---|---|",
        "| 오탐이 **일어날 수 있다** | 코드로 확실. `if form in haystack` 이라 반드시 일어난다 |",
        "| 조건을 걸면 **막힌다** | 측정. 다만 **이 파일이 쓰는 확인 문장 11개** 기준이다 |",
        "| **잃는 것이 없다** | 설문 143 + 합성 600 손실 0건 · NDCG 델타 0 |",
        "| **그 오탐이 실제로 일어나는가** | **근거 없음.** 실사용 표본에 0건 |",
        "",
        "확인 문장 25개는 **작성자가 지어낸 것**이다. 대상 표면형 10개도 그 문장에서 "
        "걸린 것을 고른 것이라 순환이다.",
        "",
        "### 실사용 설문에서 확인한 것 [측정 2026-09-18]",
        "",
        "대상 표면형 10개가 설문 143건 중 7건에 등장하는데 **7건 전부 정상적인 향 요청**이다. "
        "막아야 할 쪽은 0건이고 살려야 할 쪽만 있다.",
        "",
        "```",
        "[숲]   여름에 어울리는 숲 속에 온 듯한 향을 추천해줘",
        "[숲]   비 온 뒤의 숲의 냄새",
        "[숲]   숲향 나는 향수 추천좀",
        "[숲]   산뜻하고 숲속에 온 거 같은 피톤치드 가득한 느낌이 나는 향을 원해",
        "[숲]   차분한데 숲같은 느낌이 좋아",
        "[나무] 편백나무, 산내음처럼 자연스러운 향을 좋아해",
        "[침대] 주말 오후에 따뜻한 햇살을 받으며 침대 위에 누워있는 듯한 느낌의 향수 추천해줘",
        "```",
        "",
        "### 다만 한쪽으로만 읽지 않는다",
        "",
        "**설문 143건은 \"오탐이 안 일어난다\" 를 증명하지 못한다.** *\"향수 추천 문장을 써 "
        "주세요\"* 로 받은 자료라 오탐이 날 만한 입력이 표본에 애초에 없다. 지금 상태는 "
        "*\"오탐이 없다\"* 가 아니라 **\"오탐이 일어나는지 이 데이터로는 알 수 없다\"** 다.",
        "",
        "### 빈도는 조사 뒤에도 모른다",
        "",
        "낱말 조사로 알 수 있는 것은 *\"칠 수 있는 낱말이 몇 개 존재하는가\"*(노출면)까지다. "
        "*\"실사용자가 향수 검색창에 그 낱말을 치는가\"*(빈도)는 여전히 모른다. 그것은 "
        "`NLR_DB_TABLE_REQUEST.md` 의 표 4개가 실사용 로그를 모아야 알 수 있다.",
        "",
        "**근거 수준이 \"작성자가 떠올린 문장 11개\" 에서 \"국어사전에 실재하는 낱말 N개\" 로 "
        "올라가는 것이지 빈도가 밝혀지는 것이 아니다.**",
        "",
        "### 인계 묶음",
        "",
        "`delivery/lexicon_v1_15/` 는 **아직 만들지 않았다.** 대상 범위가 정해지면 사전이 "
        "바뀌므로 그때 만든다.",
        "",
        "⚠ 만들 때 주의 — **원본 v1_14 패치를 손으로 고치면 안 된다.** 패치에 결과 blob "
        "해시(`index 891184a..7e6cd36`)가 박혀 있어 내용을 바꾸면 3-way 병합이 깨진다 "
        "[측정 2026-09-18 · 치환한 패치가 6개 파일 전부 conflict]. 임시 worktree 에 "
        "`origin/develop` 을 꺼내 v1_14 패치를 적용하고, 버전 표기를 바꾼 뒤 `git diff` 로 "
        "새로 떠야 한다. 그때 **줄바꿈도 봐야 한다** — 작업 트리가 CRLF 인데 `git diff` 가 "
        "LF 로 정규화해 내면 그 패치는 `-3` 으로도 conflict 가 난다.",
        "",
        "## 팀 저장소 반영",
        "",
        "하지 않았다. 개인 저장소에만 있다.",
    ]
    CHANGELOG.parent.mkdir(parents=True, exist_ok=True)
    CHANGELOG.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

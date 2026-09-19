"""사전 v1.16 -> v1.17. `껍질`·`시럽` 에도 문맥 조건을 건다.

    ./venv/Scripts/python.exe -W ignore 85_lexicon_v1_17_peel_syrup_condition.py

API 호출 0회. v1.16 을 읽는다. 판정을 통과할 때만 v1.17 을 쓴다.

**80번을 그대로 불러 쓴다** — 행을 쪼개는 방법·조건 문자열·판정 기준이 같다.
84번(v1.16)과 같은 구조이고 대상만 다르다.

무엇을 고치나
--------------
측정 기록 31번이 국어 낱말 23만 개로 오탐 노출면을 재면서 찾은 둘이다 [측정].

    조개껍질 주웠어        -> '껍질' -> citrus -> 향수 5개
    달걀 껍질 까느라 힘들었어  -> 같음
    눈껍질이 무겁다        -> 같음
    귀찬시럽다            -> '시럽' -> sweet  -> 향수 5개
    거치장시럽다           -> 같음

`시럽` 쪽은 **방언 어미 `-시럽다`**(=`-스럽다`)다. 국어 낱말 목록에 49개가 있다.
`껍질` 은 11개다.

행이 어떻게 생겼나
-------------------
둘 다 **향 표현과 한 행에 있다.** 그래서 행에 그냥 조건을 걸면 향 표현이 함께 죽는다.
v1.15 가 배운 것 그대로 `.short` 로 쪼갠다.

    kr.sens.tangy          상큼|새콤|톡 쏘는|과즙|껍질   -> citrus
    kr.source.honey_syrup  당밀|시럽                 -> sweet

쪼개면 `상큼한`·`새콤`·`과즙`·`당밀` 은 조건 없이 그대로 산다.

**`과즙` 은 이번에도 대상이 아니다.** 80번이 `NOT_BLOCKED` 에 *"`과즙` 을 걸면
`상큼한` 이 제약돼서 뺐다"* 로 남겼다. 행을 쪼개면 그 걱정은 사라지지만, `과즙기` 하나를
막자고 대상을 늘리는 것은 이 변경의 범위가 아니다. **한 번에 하나씩 바꾼다.**

무엇을 잃나 — 먼저 쟀다
------------------------
v1.15·v1.16 과 같은 기준이다.

    막아야 하는 것   위 오탐 문장에서 조건이 0개가 된다
    잃으면 안 되는 것 설문 143 · 합성 600 에서 조건이 줄어드는 문장이 **0건**

한 낱말 `껍질`·`시럽` 입력은 죽는다. `이불`·`꿀`·`잼`·`빨래`·`침대` 가 이미 그렇고
한 낱말 입력은 설문 143건에 0건이다.

딸려 오는 것
-------------
**사전 버전이 올라가면 보호 목록도 다시 만들어야 한다**(`DECISIONS.md` N18 한계 6).
`85_protected_words_v1_17.py` 로 돌린다.

의존성: pandas. 80번과 41번을 파일에서 불러 쓴다.
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys

import pandas as pd

SRC = pathlib.Path("data/scent_knowledge/domain_lexicon_v1_16.csv")
DST = pathlib.Path("data/scent_knowledge/domain_lexicon_v1_17.csv")
CHANGELOG = pathlib.Path("analysis_outputs/85_lexicon_v1_17_changelog.md")

TARGET = {"껍질", "시럽"}

# 막아야 하는 것 — 31번이 국어 낱말 목록에서 찾아 엔진으로 확인한 것이다.
MISFIRE = [
    "조개껍질 주웠어",
    "달걀 껍질 까느라 힘들었어",
    "눈껍질이 무겁다",
    "귀찬시럽다",
    "거치장시럽다",
]

# 살려야 하는 것. 같은 행의 향 표현과 조건을 만족하는 문장이다.
MUST_KEEP = [
    "상큼한 향 추천해줘",
    "새콤달콤한 향",
    "과즙 같은 향",
    "감귤 껍질 향",
    "당밀 같은 단 향",
    "시럽 같은 달콤한 향",
]


def load80():
    """80번을 모듈로 읽는다. module. 이름이 숫자로 시작해 `import` 가 안 된다."""
    spec = importlib.util.spec_from_file_location(
        "lex80", "80_lexicon_v1_15_short_form_condition.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    if not SRC.is_file():
        sys.exit(f"사전이 없다: {SRC}")

    m = load80()
    m.TARGET = TARGET

    lexicon = pd.read_csv(SRC, keep_default_na=False, dtype=str)
    after, changed = m.apply_condition(lexicon)

    print("=" * 92)
    print("사전 v1.16 -> v1.17 — `껍질`·`시럽` 에 문맥 조건. GMS 호출 0회")
    print("=" * 92)
    print(f"{SRC.name} {len(lexicon)}행 -> {len(after)}행 · 조건을 건 행 {len(changed)}개")
    print(f"조건 — {m.CONDITION}")
    for item in changed:
        print(f"  {item['entry_id']}.short -> {item['candidate']}")
        print(f"  {'':24} 조건 검사  {' · '.join(item['target'])}")
        print(f"  {'':24} 원래 행에 남김 {' · '.join(item['kept_free']) or '(없음)'}")
    if not changed:
        sys.exit("조건을 건 행이 없다")

    base_index = m.build(lexicon)
    new_index = m.build(after)

    print()
    print("■ 막아야 하는 것")
    blocked = 0
    for text in MISFIRE:
        was = sorted(m.e.understand(base_index, text, None)["core"])
        got = sorted(m.e.understand(new_index, text, None)["core"])
        if not got:
            blocked += 1
        print(f"  {'막힘' if not got else '**안 막힘**':10} {text:26} {was} -> {got}")

    print()
    print("■ 살려야 하는 것")
    kept = 0
    for text in MUST_KEEP:
        got = sorted(m.e.understand(new_index, text, None)["core"])
        if got:
            kept += 1
        print(f"  {'살았다' if got else '**죽었다**':10} {text:26} {got}")

    print()
    print("■ 평가셋 손실 — 조건이 줄어드는 문장")
    lost = 0
    for name, path, column in (m.SURVEY, m.SYNTH):
        rows = m.load_rows(path, column)
        before = m.cores(base_index, rows)
        now = m.cores(new_index, rows)
        hurt = [t for t in before if now[t] < before[t]]
        lost += len(hurt)
        print(f"  {name:10} {len(rows)}문장 중 {len(hurt)}건")
        for t in hurt[:5]:
            print(f"      {t[:56]}  {sorted(before[t])} -> {sorted(now[t])}")

    print()
    print("=" * 92)
    ok = blocked == len(MISFIRE) and kept == len(MUST_KEEP) and lost == 0
    print(f"막음 {blocked}/{len(MISFIRE)} · 살림 {kept}/{len(MUST_KEEP)} · 평가셋 손실 {lost}건")
    if not ok:
        sys.exit("판정 기준을 통과하지 못했다. v1.17 을 쓰지 않는다")

    after.to_csv(DST, index=False, encoding="utf-8")
    print(f"통과. {DST} 를 썼다")

    scores = m.ndcg(SRC, DST)
    for name, nd, gain in scores:
        print(f"  {name:32} NDCG@5 {nd:.6f} · 조건충족률 {gain:.6f}")
    print(f"  {'차이':32} NDCG@5 {scores[1][1] - scores[0][1]:+.6f}")

    CHANGELOG.write_text("\n".join([
        "# 향 사전 v1.17 — `껍질`·`시럽` 에 문맥 조건",
        "",
        f"- 만든 스크립트: `{pathlib.Path(__file__).name}`",
        f"- 입력 `{SRC.name}` {len(lexicon)}행 -> 출력 `{DST.name}` {len(after)}행",
        f"- 조건: `{m.CONDITION}`",
        "",
        "## 왜",
        "",
        "측정 기록 31번이 국어 낱말 23만 개로 오탐 노출면을 재면서 찾았다.",
        "`껍질` 은 11개(조개껍질·눈껍질·베개껍질…), `시럽` 은 49개인데 대부분",
        "**방언 어미 `-시럽다`**(=`-스럽다`)다.",
        "",
        "## 바꾼 행",
        "",
        *[f"- `{i['entry_id']}` -> `{i['entry_id']}.short` ({i['candidate']}) "
          f"조건 검사 {' · '.join(i['target'])} · 원래 행에 남김 "
          f"{' · '.join(i['kept_free']) or '(없음)'}" for i in changed],
        "",
        "## 판정",
        "",
        f"- 막아야 하는 것 {blocked}/{len(MISFIRE)}",
        f"- 살려야 하는 것 {kept}/{len(MUST_KEEP)}",
        f"- 평가셋 손실 {lost}건 (설문 143 · 합성 600)",
        *[f"- {n} NDCG@5 {nd:.6f} · 조건충족률 {g:.6f}" for n, nd, g in scores],
        f"- NDCG@5 차이 {scores[1][1] - scores[0][1]:+.6f}",
        "",
        "## 한계",
        "",
        "- **`과즙` 은 대상이 아니다.** 80번이 `NOT_BLOCKED` 에 남긴 `과즙기` 오탐은",
        "  그대로다. 행을 쪼개면 막을 수 있지만 한 번에 하나씩 바꾼다",
        "- `나무껍질이 벗겨졌다` 는 `껍질` 이 막혀도 `나무` 가 `woody` 를 낸다.",
        "  `나무` 는 품은 낱말 624개가 거의 다 다른 나무라 대상이 아니다(31번)",
        "- 한 낱말 `껍질`·`시럽` 입력은 죽는다. `이불`·`꿀`·`잼`·`빨래`·`침대` 가 이미",
        "  그렇고 한 낱말 입력은 설문 143건에 0건이다",
        "- **보호 목록을 다시 만들어야 한다** — `DECISIONS.md` N18 한계 6",
        "- 오탐의 실사용 빈도는 여전히 모른다. `nlr_*` 표가 쌓여야 안다",
        "",
    ]) + "\n", encoding="utf-8")
    print(f"  changelog -> {CHANGELOG}")


if __name__ == "__main__":
    main()

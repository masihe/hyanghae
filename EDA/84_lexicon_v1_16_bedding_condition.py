"""사전 v1.15 -> v1.16. `침대`·`침구` 에도 문맥 조건을 건다. 78번의 C2 를 완성한다.

    ./venv/Scripts/python.exe -W ignore 84_lexicon_v1_16_bedding_condition.py

API 호출 0회. v1.15 를 읽는다. 판정을 통과할 때만 v1.16 을 쓴다.

**80번을 그대로 불러 쓴다** — 행을 쪼개는 방법·조건 문자열·판정 기준이 같다. 같은 일을
두 벌 두면 어긋난다. 다른 것은 대상뿐이다.

무엇이 남아 있었나
-------------------
77번이 사전 오탐 다섯을 확인했는데 그중 `침대` 가 v1.15 이후에도 그대로다 [측정].

    침대에서 뒹굴기만 했다   -> '침대' -> powdery·soapy -> 향수 5개
    침대보 샀다            -> 같음
    침구 정리했다           -> 같음

78번이 **C2 로 `침대`·`침구`·`이불` 을 함께 제안**했는데 80번(v1.15)이 `이불` 만
가져갔다. 80번의 `MISFIRE` 목록에 `침대` 가 없어 시험조차 하지 않았다.

**누락이라기보다 분류가 갈린 것이다.** 기록 27이 `침대`·`침구` 를 *"행 조건에 딸려
죽던 향 표현 22개"* 안에 넣어 **살릴 것** 으로 봤다. 같은 행의 `이불` 은 *"향 표현이면서
오탐원"* 으로 보고 쪼갰다. **같은 행의 같은 성질인데 한쪽만 쪼갠 것이 불일치다.**

무엇을 잃나 — 먼저 쟀다
------------------------
v1.15와 같은 기준이다.

    막아야 하는 것   77번의 오탐 문장 3건에서 조건이 0개가 된다
    잃으면 안 되는 것 설문 143 · 합성 600 에서 조건이 줄어드는 문장이 **0건**

한 낱말 `침대` 입력은 죽는다. 다만 **`이불`·`꿀`·`잼`·`빨래` 는 v1.15부터 이미 그렇고**,
한 낱말 입력은 설문 143건에 0건이다(`NLR_NEXT_SESSION.md` 2장).

딸려 오는 것
-------------
**사전 버전이 올라가면 오타 검문소의 보호 목록도 다시 만들어야 한다**
(`DECISIONS.md` N18 한계 6). `83_protected_words_v1_15.py` 의 사본을 v1.16 으로
돌린다. 안 하면 새 표면형의 오타를 못 잡거나 새로 위험해진 낱말을 못 막는다.

의존성: pandas. 80번과 41번을 파일에서 불러 쓴다.
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys

import pandas as pd

SRC = pathlib.Path("data/scent_knowledge/domain_lexicon_v1_15.csv")
DST = pathlib.Path("data/scent_knowledge/domain_lexicon_v1_16.csv")
CHANGELOG = pathlib.Path("analysis_outputs/84_lexicon_v1_16_changelog.md")

# 이번 대상. 78번의 C2 에서 v1.15 가 가져가지 않은 둘이다.
TARGET = {"침대", "침구"}

# 막아야 하는 것 — 77번이 확인한 오탐과 국어 낱말 목록에서 나온 것이다.
MISFIRE = [
    "침대에서 뒹굴기만 했다",
    "침대보 샀다",
    "침구 정리했다",
    "받침대를 샀다",
    "침대칸 기차표 끊었어",
]

# 살려야 하는 것. 조건이 걸려도 통과해야 한다.
MUST_KEEP = [
    "침대 냄새 같은 향수",
    "침대에 누운 것 같은 포근한 향",
    "침구 냄새 나는 향",
    "갓 세탁한 이불 같은 향",
    "이불 냄새 나는 향수",
]


def load80():
    """80번을 모듈로 읽는다. module.

    이름이 숫자로 시작해 `import` 가 안 된다. 파일 경로로 읽는다 — 56번·80번이 쓴 방식.
    """
    spec = importlib.util.spec_from_file_location(
        "lex80", "80_lexicon_v1_15_short_form_condition.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    if not SRC.is_file():
        sys.exit(f"사전이 없다: {SRC}")

    m = load80()
    m.TARGET = TARGET                      # 대상만 바꾼다. 방법·조건·기준은 그대로다

    lexicon = pd.read_csv(SRC, keep_default_na=False, dtype=str)
    after, changed = m.apply_condition(lexicon)

    print("=" * 92)
    print("사전 v1.15 -> v1.16 — `침대`·`침구` 에 문맥 조건. GMS 호출 0회")
    print("=" * 92)
    print(f"{SRC.name} {len(lexicon)}행 -> {len(after)}행 · 조건을 건 행 {len(changed)}개")
    print(f"조건 — {m.CONDITION}")
    for item in changed:
        print(f"  {item['entry_id']}.short -> {item['candidate']}")
        print(f"  {'':24} 조건 검사  {' · '.join(item['target'])}")
        print(f"  {'':24} 원래 행에 남김 {' · '.join(item['kept_free']) or '(없음)'}")
    if not changed:
        sys.exit("조건을 건 행이 없다. 대상이 이미 조건을 갖고 있거나 사전에 없다")

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
        sys.exit("판정 기준을 통과하지 못했다. v1.16 을 쓰지 않는다")

    after.to_csv(DST, index=False, encoding="utf-8")
    print(f"통과. {DST} 를 썼다")

    scores = m.ndcg(SRC, DST)
    for name, nd, gain in scores:
        print(f"  {name:32} NDCG@5 {nd:.6f} · 조건충족률 {gain:.6f}")
    print(f"  {'차이':32} NDCG@5 {scores[1][1] - scores[0][1]:+.6f}")

    CHANGELOG.write_text("\n".join([
        "# 향 사전 v1.16 — `침대`·`침구` 에 문맥 조건",
        "",
        f"- 만든 스크립트: `{pathlib.Path(__file__).name}`",
        f"- 입력 `{SRC.name}` {len(lexicon)}행 -> 출력 `{DST.name}` {len(after)}행",
        f"- 조건: `{m.CONDITION}`",
        "",
        "## 왜",
        "",
        "77번이 확인한 사전 오탐 다섯 중 `침대` 가 v1.15 이후에도 남아 있었다.",
        "78번이 C2 로 `침대`·`침구`·`이불` 을 함께 제안했는데 80번이 `이불` 만 가져갔다.",
        "80번의 `MISFIRE` 목록에 `침대` 가 없어 시험하지 않았다.",
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
        "- 한 낱말 `침대` 입력은 조건이 없어 죽는다. `이불`·`꿀`·`잼`·`빨래` 는 v1.15부터",
        "  이미 그렇고, 한 낱말 입력은 설문 143건에 0건이다",
        "- **`kr.scene.bedding` 의 `musky` 행에는 `침대`·`침구` 가 조건 없이 남는다.**",
        "  그 행이 `optional` 이라 80번의 쪼개기가 건드리지 않았고, 엔진이 `optional` 을",
        "  버리므로 지금은 새지 않는다. **기록 22(`optional` 살리기)를 고치면**",
        "  `침대에서 뒹굴기만 했다` 가 `optional=['musky']` 를 낸다 [측정].",
        "  `core` 가 비어 향수는 안 나가지만, 다른 조건이 함께 잡힌 문장에서는 점수에 섞인다.",
        "  **둘을 같이 볼 때 이 행도 쪼개야 한다**",
        "- **보호 목록을 다시 만들어야 한다** — `DECISIONS.md` N18 한계 6.",
        "  이번에는 표면형 집합이 안 바뀌어 v1.15 와 **같은 파일**이 나왔다(sha256 일치).",
        "  그래도 절차는 돌렸다 — 다음에 표면형이 바뀌면 달라진다",
        "- 오탐의 실사용 빈도는 여전히 모른다. `nlr_*` 표가 쌓여야 안다",
        "",
    ]) + "\n", encoding="utf-8")
    print(f"  changelog -> {CHANGELOG}")


if __name__ == "__main__":
    main()

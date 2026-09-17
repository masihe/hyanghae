"""⑤단계 추정이 부정 표현을 긍정 조건으로 바꾸는가 — 설문 143건으로 잰다.

    cd EDA
    ./venv/Scripts/python.exe -W ignore 75_estimator_negation.py

왜 재는가
--------
패치된 `nlr_engine._apply_estimates()` 는 추정 결과를 **`core` 에만** 넣는다.
`avoid` 로 가는 경로가 없다. 그래서 부정 표현이 추정기에 닿으면 긍정 조건이 된다.

로컬 서버에서 한 건 관찰했다 — `"포근하고 달지 않은 향"` 이
`['amber', 'bitter', 'sweet', 'warm spicy']` 를 받았다. `"달지 않은"` 이라고 했는데
`sweet` 가 조건에 들어갔고, `"달지 않은 향"` 자체는 `bitter` 라는 긍정 조건이 됐다.

**한 건으로는 경향인지 우연인지 모른다.** 이 스크립트가 설문 143건에서 몇 건인지 센다.

마지막 방어선
------------
`_apply_estimates()` 끝줄이 `core - avoid` 를 한다. ①단계가 부정된 accord 를
`avoid` 에 제대로 넣었으면 거기서 걸러진다. 그게 실제로 도는지도 함께 센다.

`understand()` 가 `avoid` 를 `_normalize_accord` 로만 푼다 — 사전을 안 탄다
(`DECISIONS.md` N12). 그래서 한국어 부정은 `avoid` 에 안 들어갈 것으로 본다 [제안].

정의를 새로 만들지 않는다
----------------------
부정 판정은 `64_negation_handling.py` 의 `NEG_RE` 를 그대로 쓴다. 설문 로딩과
추정기 재생은 `74_unmatched_estimator.py` 의 함수를 그대로 쓴다. 같은 것을 두 번
다르게 정의하면 기존 측정 기록과 비교할 수 없다.

GMS 를 부르지 않는다
------------------
`analysis_outputs/74_estimator_checkpoint.csv`(369행)를 재생한다. 체크포인트에 없는
표현은 **"안 물어봄"** 으로 세고 따로 보고한다 — 그 표현은 이 측정의 사각지대다.

출력만 한다. 파일을 만들지 않는다 (41번 이후 관례).
"""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import pandas as pd

TEAM = Path("C:/Users/SSAFY/Desktop/S15P21E203/ai")
sys.path.insert(0, str(TEAM))
import nlr_engine as e  # noqa: E402

SURVEY_CKPT = Path("analysis_outputs/37_survey_stage1_checkpoint.csv")
ESTIMATOR_CKPT = Path("analysis_outputs/74_estimator_checkpoint.csv")
TOP_N = 3                 # 측정 기록 20번의 E3


def load_module(name: str, path: str):
    """번호로 시작하는 파일명은 import 할 수 없어 파일 경로로 읽는다. module."""
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> None:
    """설문 143건에서 부정 표현이 긍정 조건으로 바뀌는 건수를 센다."""
    est74 = load_module("est74", "74_unmatched_estimator.py")
    neg64 = load_module("neg64", "64_negation_handling.py")
    neg_re: re.Pattern = neg64.NEG_RE

    print("=" * 78)
    print("⑤단계 추정과 부정 표현 — 설문 143건")
    print("=" * 78)
    print(f"  부정 판정      64번 NEG_RE  {neg_re.pattern}")
    print(f"  추정 재생      {ESTIMATOR_CKPT}  (top_n={TOP_N})")
    print(f"  엔진          {TEAM}  (패치 적용 상태를 그대로 읽는다)")
    print()

    index = e.load_index()
    print(f"  사전          {e.DEFAULT_LEXICON.name}")
    print(f"  향수 {index['n_perfumes']:,}개 · accord {len(index['accords'])}종")
    print()

    rows = est74.load_rows(str(SURVEY_CKPT), "query_text")
    table = pd.read_csv(ESTIMATOR_CKPT)
    estimator = est74.make_estimator(table, TOP_N)
    known = {str(r["expression"]) for r in table.to_dict("records")}
    print(f"  설문 {len(rows)}건 · 추정 체크포인트 {len(known)}개 표현")
    print()

    # ── 집계 ────────────────────────────────────────────────────────────
    fired = 0              # 추정기 발동 대상 (core 0개 + 미매칭 있음)
    fired_neg = 0          # 그중 문장에 부정이 든 것
    rescued = 0            # 추정으로 조건이 생긴 것
    rescued_neg = 0        # 그중 문장에 부정이 든 것
    frag_neg = 0           # 부정이 든 **표현 조각** 수
    frag_neg_got = 0       # 그 조각이 accord 를 받은 수   ← 직접 누출
    frag_neg_unknown = 0   # 그 조각이 체크포인트에 없는 수 (사각지대)
    avoid_nonempty = 0     # 부정 문장에서 avoid 가 채워진 수 (방어선이 도는가)
    samples = []

    for text, structured, _ in rows:
        u = e.understand(index, text, structured)
        if u["core"] or not u["unmatched"]:
            continue
        fired += 1
        sent_neg = bool(neg_re.search(text))
        if sent_neg:
            fired_neg += 1
            if u["avoid"]:
                avoid_nonempty += 1

        leaked = []
        for item in u["unmatched"]:
            expr = item["expression"]
            if not neg_re.search(expr):
                continue
            frag_neg += 1
            if expr not in known:
                frag_neg_unknown += 1
                continue
            guess = estimator(expr)
            # **엔진과 같은 기준으로 걸러낸다.** `_apply_estimates()` 가
            # `if a in index["aidx"]` 로 거르므로 여기서도 같이 걸러야 한다.
            # 74번 `make_estimator` 는 체크포인트의 빈 칸을 `["nan"]` 으로 내놓는다
            # (`float('nan')` 이 참이라 `str()` 이 붙는다). 엔진은 이걸 버린다.
            got = [a for a in ((guess or {}).get("accords") or [])
                   if a in index["aidx"]]
            if got:
                frag_neg_got += 1
                leaked.append((expr, got))

        after = e.recommend(index, text, structured, estimator=estimator)
        core_after = after["conditions"]["core"]
        if core_after:
            rescued += 1
            if sent_neg:
                rescued_neg += 1

        if leaked and len(samples) < 8:
            samples.append((text, u["avoid"], leaked, core_after))

    # ── 출력 ────────────────────────────────────────────────────────────
    print("─" * 78)
    print("1. 추정기가 발동하는 범위")
    print("─" * 78)
    print(f"  설문 전체                                  {len(rows):>4d}건")
    print(f"  추정기 발동 대상 (조건 0개 + 미매칭 있음)      {fired:>4d}건"
          f"  {fired/len(rows):>6.1%}")
    print(f"  그중 문장에 부정 표현이 든 것                 {fired_neg:>4d}건"
          f"  {fired_neg/fired:>6.1%} (발동 대상 기준)" if fired else "")
    print()
    print("  ⚠ 추정기는 `core` 가 비어 있을 때만 발동한다 (`nlr_engine.py` 617행).")
    print("    사전이 이미 조건을 잡은 문장은 건드리지 않는다.")
    print()

    print("─" * 78)
    print("2. 추정으로 조건이 생긴 문장")
    print("─" * 78)
    print(f"  조건이 생긴 것                              {rescued:>4d}건"
          f"  발동 대상의 {rescued/fired:>5.1%}" if fired else "")
    print(f"  그중 부정 표현이 든 것                       {rescued_neg:>4d}건")
    print()

    print("─" * 78)
    print("3. 부정 표현 조각이 긍정 accord 를 받은 건수  ← 직접 누출")
    print("─" * 78)
    print(f"  부정이 든 표현 조각                          {frag_neg:>4d}개")
    print(f"    accord 를 받았다 (긍정 조건이 됐다)         {frag_neg_got:>4d}개")
    print(f"    체크포인트에 없어 판정 못 함 (사각지대)      {frag_neg_unknown:>4d}개")
    judged = frag_neg - frag_neg_unknown
    if judged:
        print(f"    판정한 {judged}개 중 누출 비율            {frag_neg_got/judged:>6.1%}")
    print()

    print("─" * 78)
    print("4. 마지막 방어선 (`core - avoid`) 이 도는가")
    print("─" * 78)
    print(f"  부정 문장 {fired_neg}건 중 avoid 가 채워진 것      {avoid_nonempty:>4d}건")
    if fired_neg:
        print(f"                                  비어 있는 것  {fired_neg-avoid_nonempty:>4d}건"
              f"  {(fired_neg-avoid_nonempty)/fired_neg:>6.1%}")
    print()
    print("  avoid 가 비어 있으면 `core - avoid` 가 아무것도 걸러내지 못한다.")
    print()

    print("─" * 78)
    print("5. 사례")
    print("─" * 78)
    if not samples:
        print("  누출 사례가 없다.")
    for text, avoid, leaked, core_after in samples:
        print(f"  \"{text[:60]}\"")
        print(f"      avoid = {avoid}")
        for expr, got in leaked:
            print(f"      부정 조각 \"{expr}\"  ->  {got}")
        print(f"      최종 core = {core_after}")
        print()


if __name__ == "__main__":
    main()

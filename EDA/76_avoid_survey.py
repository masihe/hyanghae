"""회피가 설문 143건에서 몇 개나 닿는가 — 지금 경로와 사전 경유 경로를 함께 잰다.

    cd EDA
    ./venv/Scripts/python.exe -W ignore 76_avoid_survey.py

왜 재는가
--------
75번에서 부정 문장 16건 중 **14건의 `avoid` 가 비어 있었다.** `_apply_estimates()` 끝줄의
`core - avoid` 방어선이 사실상 안 돈다는 뜻이다.

회피 도달률은 **합성 600문장으로만** 재 뒀다 — 59개 중 7개(12%)가 닿는다(측정 기록 13번).
**설문으로는 잰 적이 없다.** 실사용 문장이 합성과 다르게 생겼으므로 따로 잰다.

무엇을 고르게 되는가
------------------
`DECISIONS.md` N12(회피도 사전을 경유한다)를 구현할 가치가 있는지다. 지금 닿는 개수만
알면 현황만 알고, 사전을 태웠을 때 몇 개가 더 닿는지를 알아야 판단이 된다.

정의를 새로 만들지 않는다
----------------------
- 설문 로딩과 무효 응답 제외는 `74_unmatched_estimator.py` 의 `load_rows()`
- 지금 경로 측정은 `43_avoid_rule_measurement.py` 의 `measure_normalization()`
- 세 경로 분류는 `44_avoid_lexicon_variants.py` 의 `resolve_avoid()`

세 스크립트가 합성 600에 쓴 정의를 그대로 설문에 적용한다. 그래야 12% 와 비교된다.

출력만 한다. 파일을 만들지 않는다 (41번 이후 관례).
"""
from __future__ import annotations

import collections
import importlib.util
import json
import sys
from pathlib import Path

import pandas as pd

TEAM = Path("C:/Users/SSAFY/Desktop/S15P21E203/ai")
sys.path.insert(0, str(TEAM))
import nlr_engine as e  # noqa: E402

SURVEY_CKPT = Path("analysis_outputs/37_survey_stage1_checkpoint.csv")


def load_module(name: str, path: str):
    """번호로 시작하는 파일명은 import 할 수 없어 파일 경로로 읽는다. module."""
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def survey_rows(est74) -> list[tuple[str, dict]]:
    """설문 체크포인트를 (문장, ①단계 dict) 목록으로. 43번이 받는 모양에 맞춘다."""
    rows = est74.load_rows(str(SURVEY_CKPT), "query_text")
    return [(text, o or {}) for text, o, _ in rows]


def main() -> None:
    """설문 143건의 회피 항목이 지금 경로와 사전 경유 경로에서 각각 몇 개 닿는지 센다."""
    est74 = load_module("est74", "74_unmatched_estimator.py")
    m43 = load_module("m43", "43_avoid_rule_measurement.py")
    m44 = load_module("m44", "44_avoid_lexicon_variants.py")

    print("=" * 78)
    print("회피 도달 — 설문 143건")
    print("=" * 78)

    # **사전을 두 판으로 잰다.** N12 의 근거 측정(`57_avoid_lexicon_routing.py`)이
    # v1.14 로 했고, 팀 저장소 배포본은 v1_8 이다. v1.9~v1.14 확장의 상당수가
    # 회피용 표현이라(`delivery/lexicon_v1_14/README.md`) 사전에 따라 결과가 갈린다.
    lexicons = {
        "v1_8 (팀 배포본)": e.DEFAULT_LEXICON,
        "v1_14 (최신)": Path("data/scent_knowledge/domain_lexicon_v1_14.csv"),
    }
    index = e.load_index()
    print(f"  기준 사전  {e.DEFAULT_LEXICON.name}  ·  accord {len(index['accords'])}종")
    print()

    rows = survey_rows(est74)
    terms = [str(t) for _, c in rows for t in (c.get("avoid") or [])]
    print(f"  설문 {len(rows)}건 · 회피가 있는 문장 "
          f"{sum(1 for _, c in rows if c.get('avoid'))}건 · 회피 항목 {len(terms)}개")
    print()

    # ── 1. 지금 엔진이 하는 경로 (43번 정의 그대로) ──────────────────────
    print("─" * 78)
    m43.measure_normalization(index, rows)

    # ── 2. 사전 경유까지 더한 세 경로 (44번 정의 그대로) ─────────────────
    print("─" * 78)
    print("[2] 사전 경유 경로를 더하면 몇 개가 더 닿는가")
    print()
    by_path: dict[str, list[tuple[str, list[str]]]] = collections.defaultdict(list)
    print(f"    {'사전':18s} {'① 직접':>8s} {'② 사전경유':>11s} {'③ 못닿음':>9s}"
          f"   {'지금':>7s} {'N12 뒤':>9s}")
    for label, path in lexicons.items():
        if not Path(path).is_file():
            print(f"    {label:18s} 사전 파일이 없다: {path}")
            continue
        idx = e.load_index(lexicon_csv=str(path))
        buckets = collections.Counter()
        for t in terms:
            route, accords = m44.resolve_avoid(idx, t)
            buckets[route] += 1
            if label.startswith("v1_14"):
                by_path[route].append((t, accords))
        direct = buckets["① accord 직접"]
        via = buckets["② 사전 경유"]
        missed = buckets["③ 닿지 못함"]
        print(f"    {label:18s} {direct:>8d} {via:>11d} {missed:>9d}"
              f"   {direct/len(terms):>6.1%} {(direct+via)/len(terms):>8.1%}"
              f"  (+{via})")
    print()
    print("    ⚠ N12 의 근거 측정은 합성 600 · v1.14 로 7/59 -> 12/59 였다.")
    print("      여기는 설문 143 이고 같은 정의(44번 resolve_avoid)를 쓴다.")
    print()

    # ── 3. 사례 ─────────────────────────────────────────────────────────
    print("─" * 78)
    print("[3] 사례 — v1_14 기준")
    print()
    for label in ("② 사전 경유", "③ 닿지 못함", "① accord 직접"):
        got = by_path.get(label) or []
        print(f"    {label}  ({len(got)}개)")
        seen = set()
        shown = 0
        for term, accords in got:
            if term in seen:
                continue
            seen.add(term)
            arrow = f" -> {accords}" if accords else ""
            print(f"      {term}{arrow}")
            shown += 1
            if shown >= 10:
                break
        print()


if __name__ == "__main__":
    main()

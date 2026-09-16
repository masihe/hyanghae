"""48번이 찾은 회피 후보 중 진짜 새 개념 넷에 N4 의 ai_summary 배수 방법을 그대로 적용한다.

    ./venv/Scripts/python.exe 50_avoid_corpus_evidence.py

API 호출 0회. `perfumes.jsonl` 을 한 번 읽는다. **노트북 30번은 실행하지 않는다** —
그 계산 로직(`lift_table`, 통제군, 순환 검출)만 읽어서 새 후보에 재적용한다.

왜 이 넷만 재는가
------------------
48번이 찾은 NO_MAP 41개 중 v1.9(향이 아닌 표현 4개)로 이미 처리한 것, 그리고 아래
기계적 별칭 수정으로 해결되는 것을 빼면 남는 게 이 넷이다.

    화려한        <- "Too flashy"
    인공적인      <- "artificial/인공적인 향" · "artificial candy"
    흔한          <- "흔한 디저트 향" · "평범한 과일 향" · "평범한 꽃향" (같은 "일반적인" 계열)
    복잡하게 변하는 향  <- 그대로

뺀 것 — 새 조사가 필요 없는 이유
--------------------------------
    too sweet · cake-like sweet · sweetness · sweet orange · ordinary citrus ·
    cloying floral · 디저트 같은 너무 달콤함
        이미 사전에 있는 accord 이름(sweet·citrus·floral)에 수식어가 붙은 것뿐이다.
        `NLR_NEXT_SESSION.md` 1장③이 판단 보류 중인 매칭 방식(45번) 문제이지 새 개념이 아니다.

    무겁·too heavy·무겁지 않게·무겁거나·too light·sticky·끈적·답답함·rough·rough leather
        질감층. `nlr_engineering_notes.md` 부록의 별도 미결정 질문과 얽혀 있다. 이 스크립트
        범위가 아니다.

    clean·too clean only
        `깨끗한`(kr.ctx.clean, **활성 core** 항목)에 영어 표기 `clean`이 빠져 있었을 뿐이다.
    candy·artificial candy(의 candy 부분)
        `달달`(kr.dial.sweet)에 영어 표기가 하나도 없었다. N4 가 애초에 `달달`을 검색할 때
        쓴 영어 대응어 자체가 `["sweet","sugary","candy"]`였다 — 이미 있는 증거다.
    girl-like·유치한
        v1.9 의 `어린`(비향 이미지 표현 클러스터)에 넣을 자리가 있는데 놓쳤다.

    차갑고 상쾌한 향
        `차갑고`가 이미 사전에 있다(`차가운`, N5 가 강등해 optional+NO_MAPPING으로 둔 것).
        다시 조사하는 것은 N5 결정을 재검토하는 일이라 이 스크립트 범위가 아니다.

방법 — N4(`30_ai_summary_expression_accord.ipynb`)와 동일
-----------------------------------------------------------
    match_rule    ai_summary pros+cons 텍스트, 소문자 부분 문자열 포함
    min_support   30    해당군에서 이 개수 미만인 accord 는 버린다
    min_subset    100   표현에 걸린 향수가 이 개수 미만이면 판정하지 않는다
    signal_lift   1.5   배수가 이 값 이상 + CI 하한 > 1 + 비순환이면 신호로 본다
    통제군         500/1000/2500 무작위 표본으로 방법이 신호를 지어내지 않는지 확인

영어 대응어는 **결과를 보기 전에 미리 정한다** — N4 의 6개 사전조사 표현과 같은 함정을
피하려는 것이다.

출력  analysis_outputs/50_avoid_corpus_lift.csv
      analysis_outputs/50_avoid_corpus_report.md
"""
import json
import pathlib
import random
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "C:/Users/SSAFY/Desktop/S15P21E203/ai")

PROJECT_ROOT = pathlib.Path.cwd()
JSONL = PROJECT_ROOT / "perfumes.jsonl"
ACCORD_DICT = PROJECT_ROOT / "analysis_outputs" / "10_accord_dictionary.csv"
OUT_LIFT = PROJECT_ROOT / "analysis_outputs" / "50_avoid_corpus_lift.csv"
OUT_REPORT = PROJECT_ROOT / "analysis_outputs" / "50_avoid_corpus_report.md"

# N4 와 같은 문턱값 — 같은 척도로 비교하려고 그대로 가져온다.
MIN_SUPPORT = 30
MIN_SUBSET = 100
SIGNAL_LIFT = 1.5
CONTROL_SEED = 42

# 결과를 보기 전에 정한 영어 대응어. accord 이름과 같은 말은 §순환 검출이 자동으로 뺀다.
EXPRESSION_TERMS = {
    "화려한":        ["flashy", "showy", "loud", "extravagant", "glamorous"],
    "인공적인":      ["synthetic", "artificial", "chemical"],
    "흔한":          ["common", "ordinary", "generic", "basic", "typical"],
    "복잡하게 변하는 향": ["complex", "evolves", "evolving", "multifaceted", "layered"],
}


def detect_circular(accord_names, terms_by_expr):
    """검색어가 accord 이름과 같거나 포함하면 순환으로 표시한다. dict[str, list[str]]."""
    circular = {}
    for expr, terms in terms_by_expr.items():
        same = sorted({a for a in accord_names for t in terms
                       if t.lower() == a.lower() or a.lower() in t.lower()})
        if same:
            circular[expr] = same
    return circular


def scan_jsonl(path, terms_by_expr):
    """perfumes.jsonl 을 한 번 읽어 accord 집합·ai_summary 보유·표현별 히트를 낸다.

    반환: (accords_list, has_summary, expr_hits, n_total, n_summary, n_stmt)
    """
    accords_list, has_summary = [], []
    expr_hits = {e: [] for e in terms_by_expr}
    n_total = n_summary = n_stmt = 0
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            rec = json.loads(line)
            n_total += 1
            acc = {a["name"] for a in (rec.get("accords") or []) if a.get("name")}
            accords_list.append(acc)

            summary = rec.get("ai_summary") or {}
            items = (summary.get("pros") or []) + (summary.get("cons") or [])
            blob = " ".join((i.get("text") or "") for i in items).lower()
            has_summary.append(bool(items))
            if items:
                n_summary += 1
                n_stmt += len(items)
            for expr, terms in terms_by_expr.items():
                expr_hits[expr].append(bool(blob) and any(t in blob for t in terms))
    has_summary = np.array(has_summary)
    expr_hits = {e: np.array(v) for e, v in expr_hits.items()}
    return accords_list, has_summary, expr_hits, n_total, n_summary, n_stmt


def lift_table(accords_list, mask, base_counts, base_n, label, circular):
    """mask 에 걸린 향수들의 accord 배수. (DataFrame, 해당군 수). N4 의 lift_table 과 동일."""
    m = int(mask.sum())
    if m < MIN_SUBSET:
        return pd.DataFrame(), m
    sub = {}
    for acc, ok in zip(accords_list, mask):
        if ok:
            for a in acc:
                sub[a] = sub.get(a, 0) + 1
    out = []
    for a, c in sub.items():
        if c < MIN_SUPPORT:
            continue
        p_sub, p_base = c / m, base_counts.get(a, 0) / base_n
        if p_base == 0:
            continue
        se = (p_sub * (1 - p_sub) / m) ** 0.5
        out.append({
            "표현": label, "accord": a, "해당군 수": c, "해당군 비율": p_sub,
            "전체 비율": p_base, "배수": p_sub / p_base,
            "배수 CI하한": max(p_sub - 1.96 * se, 0) / p_base,
            "순환": a in circular.get(label, []),
        })
    df = pd.DataFrame(out)
    return (df.sort_values("배수", ascending=False) if len(df) else df), m


def main():
    accord_master = pd.read_csv(ACCORD_DICT)
    accord_names = set(accord_master.accord)
    circular = detect_circular(accord_names, EXPRESSION_TERMS)
    for expr, names in circular.items():
        print(f"  순환 경고 — {expr}: 검색어가 accord 이름과 겹친다 -> {names}")

    print(f"perfumes.jsonl 읽는 중...")
    (accords_list, has_summary, expr_hits,
     n_total, n_summary, n_stmt) = scan_jsonl(JSONL, EXPRESSION_TERMS)
    has_accord = np.array([bool(a) for a in accords_list])
    both = has_summary & has_accord
    base_n = int(both.sum())

    base_counts = {}
    for acc, ok in zip(accords_list, both):
        if ok:
            for a in acc:
                base_counts[a] = base_counts.get(a, 0) + 1

    print(f"향수 {n_total:,} · ai_summary 보유 {n_summary:,} ({n_summary/n_total:.1%}) "
          f"· 서술문 {n_stmt:,} · 둘 다 보유 {base_n:,}\n")

    # 재현 게이트 — N4 와 같은 accord 92개 perfume_count 대조
    counts = {}
    for acc in accords_list:
        for a in acc:
            counts[a] = counts.get(a, 0) + 1
    ref = dict(zip(accord_master.accord, accord_master.perfume_count))
    bad = [(a, ref[a], counts.get(a, 0)) for a in ref if counts.get(a, 0) != ref[a]]
    if bad:
        raise RuntimeError(f"재현 게이트 실패 — accord {len(bad)}개 불일치: {bad[:5]}")
    print("재현 게이트 통과 — accord 92개 perfume_count 오차 0\n")

    # 통제군 — 방법이 신호를 지어내지 않는지
    rng = random.Random(CONTROL_SEED)
    idx = [i for i, ok in enumerate(both) if ok]
    print("[1] 통제군 — 무작위 표본")
    ctrl_max = 0.0
    for size in (500, 1000, 2500):
        pick = set(rng.sample(idx, size))
        mask = np.array([i in pick for i in range(n_total)])
        t, m = lift_table(accords_list, mask, base_counts, base_n, f"통제군 n={size}", {})
        if len(t):
            row_max = float(t["배수"].max())
            ctrl_max = max(ctrl_max, row_max)
            print(f"    n={size:5d}  accord {len(t):3d}종  최대 배수 {row_max:.2f}  "
                  f"1.5 이상 {int((t['배수']>=SIGNAL_LIFT).sum())}개")
    print()

    # 표현별 측정
    print("[2] 표현별 측정")
    all_tables, subset_sizes = [], {}
    for expr in EXPRESSION_TERMS:
        t, m = lift_table(accords_list, expr_hits[expr] & both, base_counts, base_n, expr, circular)
        subset_sizes[expr] = m
        if len(t):
            all_tables.append(t)
        if m < MIN_SUBSET:
            print(f"    {expr:14s} 향수 {m:>5,}개 — 표본 부족(<{MIN_SUBSET})으로 판정하지 않음")
            continue
        top = "  ".join(f"{r.accord}{'*' if r.순환 else ''} {r.배수:.2f}x"
                        for r in t.head(6).itertuples())
        print(f"    {expr:14s} 향수 {m:>5,}개  {top or '(문턱 넘는 accord 없음)'}")
    print()

    lift_df = pd.concat(all_tables, ignore_index=True) if all_tables else pd.DataFrame()
    if len(lift_df):
        lift_df["신호"] = ((lift_df["배수"] >= SIGNAL_LIFT)
                          & (lift_df["배수 CI하한"] > 1.0) & (~lift_df["순환"]))
        signals = lift_df[lift_df["신호"]]
        print(f"[3] 신호 판정 — 배수>={SIGNAL_LIFT} · CI하한>1 · 비순환")
        if len(signals):
            print(signals[["표현", "accord", "해당군 수", "배수", "배수 CI하한"]]
                  .to_string(index=False))
        else:
            print("    없음 — 통제군 수준을 넘는 accord 가 하나도 없었다")
    else:
        print("[3] 표본 부족으로 아무것도 측정하지 못했다")

    lift_df.to_csv(OUT_LIFT, index=False, encoding="utf-8")
    write_report(lift_df, subset_sizes, circular, ctrl_max, n_total, n_summary, base_n)
    print(f"\n저장: {OUT_LIFT.relative_to(PROJECT_ROOT)}")
    print(f"저장: {OUT_REPORT.relative_to(PROJECT_ROOT)}")


def write_report(lift_df, subset_sizes, circular, ctrl_max, n_total, n_summary, base_n):
    lines = [
        "# 50. 회피 후보 넷의 ai_summary 배수 — N4 방법 재적용",
        "",
        f"재현: `./venv/Scripts/python.exe 50_avoid_corpus_evidence.py`",
        f"방법: `30_ai_summary_expression_accord.ipynb`(N4)의 계산을 새 후보 4개에 재적용. "
        f"노트북은 실행하지 않았다 — 로직만 새 스크립트로 옮겼다.",
        "",
        "## 표본",
        "",
        f"- 전체 향수 {n_total:,} · `ai_summary` 보유 {n_summary:,}({n_summary/n_total:.1%}) "
        f"· accord 와 둘 다 보유 {base_n:,}",
        f"- 통제군(무작위) 최대 배수 {ctrl_max:.2f} — 표현별 배수와 이 값을 비교해서 읽는다",
        "",
        "## 표현별 결과",
        "",
        "| 표현 | 해당 향수 | 상위 accord (배수) |",
        "|---|---:|---|",
    ]
    for expr, terms in EXPRESSION_TERMS.items():
        m = subset_sizes.get(expr, 0)
        if m < MIN_SUBSET:
            lines.append(f"| {expr} | {m:,} | 표본 부족(<{MIN_SUBSET}) — 판정하지 않음 |")
            continue
        t = lift_df[lift_df["표현"] == expr].head(5) if len(lift_df) else pd.DataFrame()
        s = " · ".join(f"`{r.accord}`{'*' if r.순환 else ''} {r.배수:.2f}x"
                       for r in t.itertuples()) or "(문턱 넘는 accord 없음)"
        lines.append(f"| {expr} | {m:,} | {s} |")
    lines += [
        "",
        "`*` 는 검색어가 accord 이름과 겹쳐 순환인 항목 — 신호로 읽지 않는다.",
        "",
        "## 검색어 (결과를 보기 전에 정함)",
        "",
    ]
    for expr, terms in EXPRESSION_TERMS.items():
        lines.append(f"- `{expr}` -> {terms}" + (f"  (순환: {circular[expr]})" if expr in circular else ""))
    lines += [
        "",
        "## 한계 — N4 와 동일하게 적용된다",
        "",
        "- 대중적 향수에 쏠린 표본이다(`ai_summary` 커버리지 9.4%, 평가자 수 중앙값이 70배 차이)",
        "- 동반 출현이지 인과가 아니다",
        "- 영어 서술이라 번역 가정이 들어간다",
        "- Fragrantica 출처라 서비스 반영 여부는 별도 판단(`spec.md` §8)이 필요하다",
        "- 부분 문자열 검색이라 잡음 제거가 안 돼 있다",
        "",
        "## 관련 자료",
        "",
        "- `DECISIONS.md` N4 — 이 방법의 원 결정과 근거",
        "- `30_ai_summary_expression_accord.ipynb` — 원 계산 (실행하지 않음, 로직만 참고)",
        "- `48_avoid_concept_suppression.py` — 이 넷을 후보로 고른 근거(NO_MAP 41개 분류)",
    ]
    OUT_REPORT.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()

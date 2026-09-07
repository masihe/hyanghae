"""자동 확정의 상한을 먼저 잰다 — 규칙을 구현하기 전에 (10a).

Run with venv/Scripts/python.exe src/matching/evaluate_confirmation_dev.py

이전 Verification 설계 시도가 적대적 검토에서 기각된 이유가 이 숫자였다.
자동 확정 상한이 당시 Top-1 보다 낮았는데 구현을 끝낸 뒤에 알았다.
그래서 **증거 차원을 만들기 전에 그 차원이 정답과 오확정을 실제로 갈라내는지** 먼저 본다.

여기서 하는 일은 셋이다.

  1. 현재 파이프라인(브랜드 매핑 + LLM 채널)의 DEV 자동 확정 상태를 재현한다 (게이트)
  2. 자동 확정된 행마다 증거 차원을 계산하고 정답/오확정 분포를 대조한다
  3. 차원 조합을 느슨/중간/엄격 세 단계로 적용해 **건수와 정확도의 교환비**를 낸다

Gold Set·기존 산출물을 하나도 수정하지 않는다. 파일을 쓰지 않고 표로만 보고한다.

**D074 주의.** Gold 는 `취 오드퍼퓸 사찰` 을 NO_MATCH 로 라벨했는데, 그때 브랜드 `취` 가
카탈로그에서 해결되지 않았기 때문이다. 검토 브랜드 매핑(D13) 이후 `Chwi 취 / Sachal 사찰`
이 존재하므로 **라벨이 낡았다.** Gold 를 고치지 않고 이 1건을 분리해 함께 보고한다.
DEV NO_MATCH 16건 중 같은 사유는 이 1건뿐임을 확인했다.
"""
import re
import sys
import tempfile
from difflib import SequenceMatcher
from pathlib import Path

import pandas as pd

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "korea"))
import build_korea_popularity_map as matcher
import evaluate_fragrantica_matcher_dev as baseline
import evaluate_pipeline_dev as pipeline_dev
import identity_remap as ir

ROOT = Path(__file__).resolve().parents[2]  # MAP/
DATA = ROOT / "data/korea_popularity"

# 9c 로 기록한 값. 이 상태에서만 아래 분석이 의미가 있다.
EXPECTED = {"auto": 41, "correct": 33, "false": 8, "review": 9, "no_match": 27}
# 라벨 당시 브랜드 미해결이라 NO_MATCH 였고, 브랜드 매핑 후 정답이 생긴 건 (docstring 참조).
STALE_GOLD = {"D074"}

# 확정 취소 기준의 단계. 값은 "이 조건이면 자동 확정을 취소한다".
# 차원별 분리력을 먼저 재고 그 결과로 조합했다 — 숫자를 정해두고 맞춘 것이 아니다.
TIERS = {
    "현재 (규칙 없음)":
        lambda f: pd.Series(False, index=f.index),
    "A — 음성키 단독 확정만 취소":
        lambda f: f.phonetic_only,
    "D — 기본명 변형 5개 이상이면 취소":
        lambda f: f.variant_siblings >= 5,
    "E — A + D":
        lambda f: f.phonetic_only | (f.variant_siblings >= 5),
    "F — A + 기본명 변형 3개 이상":
        lambda f: f.phonetic_only | (f.variant_siblings >= 3),
}


def frame_kept(frame: pd.DataFrame, fn) -> pd.DataFrame:
    return frame[~fn(frame)]


def load_state() -> tuple[pd.DataFrame, pd.DataFrame]:
    """현재 파이프라인 상태로 DEV 평가를 돌려 결과와 카탈로그를 준다."""
    baseline.verify_snapshot()
    new = pd.read_csv(pipeline_dev.NEW_COMMERCIAL, keep_default_na=False)
    translated, _ = ir.as_old_ids(new)
    with tempfile.TemporaryDirectory(prefix="confirm_dev_") as tmp:
        tmp = Path(tmp)
        path = tmp / "korea_commercial_identities.csv"
        translated.to_csv(path, index=False)
        results = pipeline_dev.run(path, tmp / "llm", llm=True)
    stats = pipeline_dev.confirmation_stats(results)
    drift = {k: (EXPECTED[k], stats[k]) for k in EXPECTED if EXPECTED[k] != stats[k]}
    if drift:
        raise RuntimeError(f"9c 상태 재현 실패. 여기서 멈춘다: {drift}")
    print(f"9c 상태 재현 확인: {EXPECTED}")
    perfumes = pd.read_csv(baseline.PERFUMES_PATH,
                           usecols=["id", "name", "brand", "year", "description"],
                           keep_default_na=False).set_index("id", drop=False)
    return results, perfumes


def num(value, default: float) -> float:
    """빈 값·NaN 을 기본값으로. override 행은 margin 이 비어 있어 파싱이 실패한다."""
    parsed = pd.to_numeric(value, errors="coerce")
    return default if pd.isna(parsed) else float(parsed)


def candidate_core(name: str, brand: str) -> str:
    """후보 이름에서 브랜드 문자열을 떼고 라틴 키로 만든다 — match_one 과 같은 규칙."""
    core = re.sub(re.escape(str(brand)), " ", str(name), flags=re.IGNORECASE)
    return matcher.latin_key(re.sub(r"\s+", " ", core).strip())


def query_tokens(query: str, llm_query: str) -> list[str]:
    """질의를 라틴 토큰으로 쪼갠다. LLM 표현이 있으면 그것이 토큰 경계가 정확하다.

    없으면 규칙 음역을 쓴다 — 이때는 토큰 경계가 부정확할 수 있어 차원의 신뢰도가 낮다.
    """
    source = llm_query if llm_query.strip() else matcher.romanize(query)
    return [t for t in (matcher.latin_key(x) for x in re.split(r"[\s\-_/]+", str(source))) if len(t) >= 3]


def channel_scores(query: str, candidate_core_text: str, llm_query: str) -> dict:
    """match_score 의 채널별 값. 어느 채널이 판정을 끌었는지 보려고 따로 계산한다."""
    q, c = matcher.latin_key(matcher.romanize(query)), candidate_core_text
    qp, cp = matcher.phonetic_key(query), matcher.phonetic_key(candidate_core_text)
    ql = matcher.latin_key(llm_query)
    ratio = lambda a, b: SequenceMatcher(None, a, b).ratio() if a and b else 0.0
    contains = lambda a, b: (min(len(a), len(b)) / max(len(a), len(b))
                             if a and b and (a in b or b in a) else 0.0)
    return {
        "direct": ratio(q, c), "phonetic": ratio(qp, cp), "contains": contains(q, c),
        "llm_direct": ratio(ql, c), "llm_contains": contains(ql, c),
    }


def variant_siblings(row, chosen_core: str, brand_rows: pd.DataFrame,
                     perfumes: pd.DataFrame, chosen_id: int) -> tuple[int, int]:
    """후보 **풀 전체**에서, 고른 후보의 이름을 접두사로 갖는 더 긴 변형이 몇 개인가.

    상위 5개만 보면 안 된다 — D016(`미스` -> `Miss Dior`)의 정답은 22위다.
    `Miss Dior` 는 46개 변형의 기본명이라, 기본명에 완전일치했다는 사실 자체가
    "변형 중 어느 것인지 모른다" 는 뜻이 된다. 그게 이 차원이 재려는 것이다.
    """
    total = 0
    for p in brand_rows.itertuples(index=False):
        if int(p.id) == chosen_id:
            continue
        core = candidate_core(p.name, p.brand)
        if chosen_core and core.startswith(chosen_core) and core != chosen_core:
            total += 1
    return total, len(brand_rows)


def evidence(row, perfumes: pd.DataFrame, brand_groups: dict) -> dict:
    """자동 확정 한 건의 증거 차원. 없는 필드에 의존하지 않는다."""
    brand = str(row.canonical_brand)
    chosen_id = int(float(row.predicted_fragrantica_id))
    chosen = perfumes.loc[chosen_id]
    chosen_core = candidate_core(chosen["name"], chosen.brand)
    query = str(row.fragrance_name_normalized)
    llm_query = matcher.LLM_KO_LATIN_NAMES.get(str(row.commercial_identity_id), "")
    conc = str(row.concentration)

    # 같은 후보군 안에, 고른 후보의 이름을 그대로 포함하면서 더 구체적인 형제가 있는가.
    # D016/D022/D028/D047 이 전부 이 구조다 — 기본명이 짧아서 완전일치로 이기고,
    # 정답은 농도나 연도가 붙은 더 긴 이름이다.
    sibling, sibling_conc = None, None
    for cid in str(row.predicted_candidate_ids).split("|"):
        if not cid.strip() or int(float(cid)) == chosen_id:
            continue
        other = perfumes.loc[int(float(cid))]
        other_core = candidate_core(other["name"], other.brand)
        if not (chosen_core and other_core.startswith(chosen_core) and other_core != chosen_core):
            continue
        sibling = other["name"] if sibling is None else sibling
        explicit = matcher.candidate_concentrations(other["name"], other.description)
        if conc in {"EDP", "EDT", "EDC", "EXTRAIT"} and conc in explicit:
            sibling_conc = other["name"]

    # 토큰 단위 증거. 질의의 어느 토큰이 후보에 없는지, 2위가 더 잘 덮는지 본다.
    # D078(쿨 코튼 -> Classic **Warm** Cotton)처럼 반의어가 치환된 경우는 유사도로 안 잡힌다.
    q_tokens = query_tokens(query, llm_query)
    chosen_missing = [x for x in q_tokens if x not in chosen_core]
    runner_up, runner_up_gain = None, 0
    for cid in str(row.predicted_candidate_ids).split("|"):
        if not cid.strip() or int(float(cid)) == chosen_id:
            continue
        other = perfumes.loc[int(float(cid))]
        other_core = candidate_core(other["name"], other.brand)
        gain = len(chosen_missing) - len([x for x in q_tokens if x not in other_core])
        if gain > runner_up_gain:
            runner_up, runner_up_gain = other["name"], gain

    pool = brand_groups.get(matcher.latin_key(brand), perfumes.iloc[0:0])
    variants, pool_size = variant_siblings(row, chosen_core, pool, perfumes, chosen_id)

    ch = channel_scores(query, chosen_core, llm_query)
    top = max(ch.values())
    chosen_concs = matcher.candidate_concentrations(chosen["name"], chosen.description)
    return {
        "queue_id": row.queue_id,
        "brand": brand,
        "query": query,
        "chosen": chosen["name"],
        "gold": (perfumes.at[int(float(row.gold_fragrantica_id)), "name"]
                 if str(row.gold_fragrantica_id) not in ("", "nan") else ""),
        # 사람 확정 override(SNAPSHOT_FRAGRANTICA_MATCHES)는 margin 이 비어 있다.
        "score": num(row.predicted_match_score, 1.0),
        "margin": num(row.predicted_match_margin, 1.0),
        "snapshot_override": str(row.predicted_match_basis).startswith("snapshot manual"),
        "name_exact": "name exact" in row.predicted_match_basis,
        "llm_exact": "llm reconstructed" in row.predicted_match_basis,
        # 고른 후보가 질의 농도를 이름·설명에서 명시하는가. 없으면 배제만 가능하다(긍정 확인 불가).
        "conc_explicit": bool(conc in chosen_concs),
        "conc_silent": not chosen_concs,
        # 더 구체적인 형제 후보의 존재. _conc 는 그 형제가 질의 농도를 명시하는 경우다.
        "longer_sibling": sibling,
        "sibling_names_conc": sibling_conc,
        # 음성 키(모음 제거)만으로 이긴 경우. 우먼(woman) 과 Man 이 같은 키가 되는 붕괴를 잡는다.
        "phonetic_only": ch["phonetic"] >= top and max(
            ch["direct"], ch["contains"], ch["llm_direct"], ch["llm_contains"]) < top,
        "query_len": len(matcher.latin_key(matcher.romanize(query))),
        "llm_len": len(matcher.latin_key(llm_query)),
        # 질의 토큰 중 고른 후보에 없는 것의 개수, 그리고 그것을 더 잘 덮는 다른 후보.
        "query_token_count": len(q_tokens),
        "missing_tokens": len(chosen_missing),
        "runner_up": runner_up,
        "runner_up_gain": runner_up_gain,
        # 고른 후보가 계열의 기본명인가 — 풀 전체에서 이 이름을 접두사로 갖는 변형의 수.
        "variant_siblings": variants,
        "pool_size": pool_size,
        # 질의가 고른 후보의 이름과 정확히 같은 길이(= 질의가 기본명을 그대로 가리킨다)
        "query_is_base_name": bool(chosen_core) and matcher.latin_key(llm_query or matcher.romanize(query)) == chosen_core,
    }


def dimension_table(frame: pd.DataFrame) -> None:
    """차원별로 정답/오확정이 갈리는지 본다. 갈라내지 못하는 차원은 규칙에 쓸 수 없다."""
    dims = [
        ("name_exact", lambda f: f.name_exact),
        ("llm_exact", lambda f: f.llm_exact),
        ("conc_explicit", lambda f: f.conc_explicit),
        ("conc_silent", lambda f: f.conc_silent),
        ("longer_sibling 있음", lambda f: f.longer_sibling.notna()),
        ("  그 형제가 농도 명시", lambda f: f.sibling_names_conc.notna()),
        ("phonetic_only", lambda f: f.phonetic_only),
        ("query_len <= 6", lambda f: f.query_len <= 6),
        ("margin < 0.25", lambda f: f.margin < 0.25),
        ("score < 1.0", lambda f: f.score < 1.0),
        ("질의 토큰 누락 >= 1", lambda f: f.missing_tokens >= 1),
        ("2위가 더 잘 덮음", lambda f: f.runner_up.notna()),
        ("LLM 표현 없음", lambda f: f.llm_len == 0),
        ("기본명 변형 >= 1개", lambda f: f.variant_siblings >= 1),
        ("기본명 변형 >= 3개", lambda f: f.variant_siblings >= 3),
        ("기본명 변형 >= 5개", lambda f: f.variant_siblings >= 5),
        ("질의 = 기본명 그대로", lambda f: f.query_is_base_name),
    ]
    correct, false = frame[frame.correct], frame[~frame.correct]
    print()
    print(f"  {'차원':<22}{'정답 33':>9}{'오확정 8':>10}{'오확정 비율':>12}  판정")
    for label, fn in dims:
        c, f = int(fn(correct).sum()), int(fn(false).sum())
        rate = f / (c + f) if (c + f) else 0.0
        base = len(false) / len(frame)
        verdict = ("갈라냄" if rate >= base * 2.5 and f >= 3
                   else "약함" if rate > base else "무관/역방향")
        print(f"  {label:<22}{c:>9}{f:>10}{rate:>11.1%}  {verdict}")
    print(f"  {'(전체 기준선)':<22}{len(correct):>9}{len(false):>10}"
          f"{len(false) / len(frame):>11.1%}")


def tier_table(frame: pd.DataFrame) -> None:
    """차원 조합을 세 단계로 적용해 건수와 정확도의 교환비를 낸다.

    '확정 유지' 는 자동 확정을 그대로 두는 것, '확정 취소' 는 MATCH_REVIEW 로 내리는 것이다.
    숫자를 미리 정하고 거기 맞추지 않는다 — 먼저 재고 그다음에 고른다.
    """
    tiers = TIERS
    print()
    print(f"  {'단계':<38}{'확정':>6}{'정답':>6}{'오확정':>8}{'precision':>11}{'정답 손실':>10}")
    for label, fn in tiers.items():
        drop = fn(frame)
        kept = frame[~drop]
        c, f = int(kept.correct.sum()), int((~kept.correct).sum())
        lost = int(frame.correct.sum()) - c
        prec = c / len(kept) if len(kept) else 0.0
        print(f"  {label:<38}{len(kept):>6}{c:>6}{f:>8}{prec:>11.4f}{lost:>10}")


def main() -> None:
    baseline.use_llm_channel(matcher.LLM_KO_LATIN_NAMES or baseline.LLM_KO_LATIN_NAMES_PRODUCTION)
    results, perfumes = load_state()
    flag = lambda c: results[c].astype(str).str.lower().isin(["true", "1"])
    auto = results[results.predicted_status.eq("MATCH")].copy()
    auto["correct"] = flag("correct_auto_match")[auto.index]

    brand_groups = {matcher.latin_key(b): g for b, g in perfumes.groupby("brand", sort=False)
                    if matcher.latin_key(b)}
    rows = pd.DataFrame([evidence(r, perfumes, brand_groups) for r in auto.itertuples(index=False)])
    rows["correct"] = auto.correct.values
    assert len(rows) == EXPECTED["auto"]

    print()
    print("=== 잘못 확정한 8건의 실패 구조 ===")
    print(f"  {'q':<6}{'국내 이름':<15}{'정답':<30}{'판정':<28}실패 원인")
    for r in rows[~rows.correct].itertuples(index=False):
        has = lambda v: isinstance(v, str) and v != ""
        cause = ("Gold 라벨 낡음 (브랜드 매핑 이전)" if r.queue_id in STALE_GOLD else
                 "음성 키 붕괴 (모음 제거)" if r.phonetic_only else
                 f"농도 명시 형제: {r.sibling_names_conc}" if has(r.sibling_names_conc) else
                 f"더 긴 형제: {r.longer_sibling}" if has(r.longer_sibling) else
                 f"2위가 질의 토큰을 더 덮음: {r.runner_up}" if has(r.runner_up) else
                 "이름 유사도만으로 판정")
        print(f"  {r.queue_id:<6}{str(r.query)[:13]:<15}{str(r.gold)[:28]:<30}{str(r.chosen)[:26]:<28}{cause}")

    stale = rows[rows.queue_id.isin(STALE_GOLD)]
    real_false = int((~rows.correct).sum()) - len(stale[~stale.correct])
    print()
    print(f"  Gold 라벨이 낡은 것 {len(stale[~stale.correct])}건을 빼면 실제 오확정은 {real_false}건이다.")
    print("  Gold Set 은 수정하지 않았다. 재라벨은 사람이 결정할 일이다.")

    print()
    print("=== 증거 차원별 분리력 (규칙을 만들기 전에 확인) ===")
    dimension_table(rows)

    print()
    print("=== 기준 단계별 건수와 정확도의 교환비 ===")
    tier_table(rows)

    print()
    print("=== 단계별로 지도에 몇 개가 남는가 (현재 파이프라인 규모에 외삽) ===")
    pipeline = sorted(DATA.glob("korea_map_identities_*.csv"))
    latest = max(pipeline, key=lambda p: p.stat().st_mtime) if pipeline else None
    ready = int(pd.read_csv(latest, keep_default_na=False).map_ready
                .astype(str).str.lower().isin(["true", "1"]).sum()) if latest else 0
    print(f"  기준: {latest.name if latest else '없음'} | map_ready {ready}")
    print(f"  {'단계':<38}{'확정 비율':>10}{'예상 map_ready':>15}{'200 달성':>10}")
    for label, fn in TIERS.items():
        kept = frame_kept(rows, fn)
        share = len(kept) / len(rows)
        expected = round(ready * share)
        print(f"  {label:<38}{share:>9.1%}{expected:>15}{'가능' if expected >= 200 else '미달':>10}")
    print()
    print("  외삽이다. DEV 61건 표본에서 나온 비율이며 실측이 아니다.")
    print("  신규 300건의 이름 표현은 DEV 에 라벨이 없어 **정확도를 측정할 수 없다.**")
    print("  MATCH 가 61건 늘었다는 것은 건수이고, 그것이 맞는 매칭이라는 측정이 아니다.")


if __name__ == "__main__":
    main()

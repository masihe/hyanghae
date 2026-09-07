"""현재 Fragrantica matcher를 Gold DEV Set에 직접 실행해 baseline을 측정한다.

progressive matching queue를 거치지 않고 평가 가능한 DEV identity 77개를 모두
build_korea_popularity_map.match_one에 전달한다. matcher 구현과 입력 결과 파일은
수정하지 않는다.
"""
from __future__ import annotations

import hashlib
import math
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "korea"))
import build_korea_popularity_map as matcher

# 프로덕션의 LLM 이름 표현. use_llm_channel() 로 되돌릴 수 있게 사본을 잡아 둔다 (9c).
LLM_KO_LATIN_NAMES_PRODUCTION = dict(matcher.LLM_KO_LATIN_NAMES)


ROOT = Path(__file__).resolve().parents[2]  # MAP/
EVAL_DIR = ROOT / "data" / "korea_popularity" / "evaluation"
GOLD_PATH = EVAL_DIR / "gold_set_dev.csv"
PERFUMES_PATH = ROOT / "perfumes.csv"

# ---- 재현 게이트의 기준점 (9a-4) ----
# 이 스크립트와 method1/2/3 · brand_mapping 은 모두 "기록된 수치를 다시 만들어내는지" 를
# 확인하는 재현 게이트를 갖고 있다. 그 게이트가 파이프라인이 매번 덮어쓰는 산출물을
# 가리키면, 파이프라인을 고치는 순간 게이트가 의미를 잃는다(숫자를 고쳐 맞추게 된다).
#
# 그래서 브랜드 매핑 반영 직전 상태를 별도 디렉터리에 동결하고 게이트를 그쪽에 고정한다.
# 이 값들은 사람이 손댈 파일이 아니며, SHA-256 이 어긋나면 실행 자체를 멈춘다.
SNAPSHOT_DIR = ROOT / "data" / "korea_popularity" / "snapshot_pre_brand_mapping"
COMMERCIAL_PATH = SNAPSHOT_DIR / "korea_commercial_identities.csv"
MEMBERS_PATH = SNAPSHOT_DIR / "korea_commercial_identity_members.csv"
FAMILIES_PATH = SNAPSHOT_DIR / "korea_candidate_families.csv"
SNAPSHOT_HASHES = {
    COMMERCIAL_PATH: "069a30ca2c053ba0222f66aa529996b61ede12df8bb97f743f8c3a2718787588",
    MEMBERS_PATH: "b27d8c8accccb4afbe513c748a00ed1d1b3479595b054bf42992e7952d0bcf74",
    FAMILIES_PATH: "b853a639e9d707ac03e25e012cb16cf184703f56fa27c1c5d475e828debf749d",
}

RESULTS_PATH = EVAL_DIR / "fragrantica_matcher_baseline_dev_results.csv"
REPORT_PATH = EVAL_DIR / "fragrantica_matcher_baseline_dev_report.md"

EXPECTED_GOLD = {"rows": 80, "eligible": 77, "match": 61, "no_match": 16, "unresolved": 3}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def verify_snapshot() -> None:
    """재현 게이트의 기준 스냅샷이 그대로인지 확인한다. 어긋나면 그 자리에서 멈춘다.

    SNAPSHOT_HASHES 의 키는 import 시점의 Path 객체다. 다른 스크립트가 모듈 전역
    COMMERCIAL_PATH 를 갈아끼워도(evaluate_pipeline_dev.py) 이 검사는 항상 스냅샷을 본다.
    """
    missing = [p for p in SNAPSHOT_HASHES if not p.exists()]
    if missing:
        raise FileNotFoundError(f"재현 기준 스냅샷이 없다: {[p.name for p in missing]}")
    actual = {p: sha256(p) for p in SNAPSHOT_HASHES}
    bad = {p.name: (expected, actual[p]) for p, expected in SNAPSHOT_HASHES.items()
           if actual[p] != expected}
    if bad:
        raise RuntimeError(f"재현 기준 스냅샷이 변경됐다. 게이트를 신뢰할 수 없다: {bad}")


def use_llm_channel(names: dict[str, str] | None) -> dict[str, str]:
    """matcher 의 LLM 이름 채널을 갈아끼우고 이전 값을 돌려준다 (9c).

    `None` 이면 끈다. **기록된 수치를 재현하는 게이트는 전부 끈 상태로 돌아야 한다** —
    이 모듈과 method1~3 · brand_mapping 의 기록값은 모두 채널 도입 전에 측정된 것이다.

    import 부작용으로 끄지 않는다. 그러면 이 모듈을 라이브러리로 쓰는 다른 스크립트가
    영향을 받는지 알 수 없다. 끄는 쪽이 `__main__` 또는 자기 main() 에서 명시적으로 부른다.
    """
    previous = matcher.LLM_KO_LATIN_NAMES
    matcher.LLM_KO_LATIN_NAMES = {} if names is None else names
    return previous


def use_verification(enabled: bool) -> bool:
    """matcher 의 Verification(10b) 을 켜고 끈다. 이전 값을 돌려준다.

    기록된 수치는 모두 Verification 도입 **전** 측정본이다. 재현 게이트는 꺼야 한다.
    """
    previous = matcher.VERIFICATION_ENABLED
    matcher.VERIFICATION_ENABLED = enabled
    return previous


def retrieve_candidates(row: pd.Series, brand_rows: pd.DataFrame) -> list[tuple[float, int, str]]:
    """match_one의 candidate retrieval 경로를 변경 없이 평가용으로 재현한다.

    match_one 과 같은 LLM 이름 채널을 쓴다. 채널이 꺼져 있으면(이 모듈의 기본값)
    이전과 완전히 동일하게 동작한다. 켜져 있는데 여기서 쓰지 않으면 retrieval 과
    confirmation 이 서로 다른 점수 함수로 측정돼 R@k 수치가 실제와 어긋난다.
    """
    llm_query = matcher.LLM_KO_LATIN_NAMES.get(str(row.commercial_identity_id), "")
    candidates = []
    for perfume in brand_rows.itertuples(index=False):
        if not matcher.form_compatible(row.product_form, perfume.name):
            continue
        concentrations = matcher.candidate_concentrations(perfume.name, perfume.description)
        if (row.concentration in {"EDP", "EDT", "EDC", "EXTRAIT"}
                and concentrations and row.concentration not in concentrations):
            continue
        candidate_name = re.sub(
            re.escape(str(perfume.brand)), " ", str(perfume.name), flags=re.IGNORECASE
        )
        candidate_name = re.sub(r"\s+", " ", candidate_name).strip()
        score = matcher.match_score(row.fragrance_name_normalized, candidate_name, llm_query)
        candidates.append((score, int(perfume.id), str(perfume.name)))
    candidates.sort(reverse=True)
    return candidates


def as_bool(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.lower().eq("true")


def ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else math.nan


def measure(frame: pd.DataFrame, label: str, level: str) -> dict:
    gold_match = frame.gold_status.eq("MATCH")
    gold_no_match = frame.gold_status.eq("NO_MATCH")
    auto = frame.predicted_status.eq("MATCH")
    correct_auto = frame.correct_auto_match
    match_rows = frame[gold_match]
    ranks = pd.to_numeric(match_rows.gold_candidate_rank, errors="coerce")
    return {
        "breakdown_level": level,
        "breakdown_value": label,
        "evaluation_count": len(frame),
        "gold_match_count": int(gold_match.sum()),
        "gold_no_match_count": int(gold_no_match.sum()),
        "retrieval_recall_at_1": float(ranks.le(1).mean()) if len(ranks) else math.nan,
        "retrieval_recall_at_3": float(ranks.le(3).mean()) if len(ranks) else math.nan,
        "retrieval_recall_at_5": float(ranks.le(5).mean()) if len(ranks) else math.nan,
        "retrieval_mrr": float(match_rows.reciprocal_rank.mean()) if len(match_rows) else math.nan,
        "retrieval_top5_miss_count": int((ranks.isna() | ranks.gt(5)).sum()),
        "auto_match_count": int(auto.sum()),
        "correct_auto_match_count": int(correct_auto.sum()),
        "false_auto_match_count": int(frame.false_auto_match.sum()),
        "auto_match_precision": ratio(int(correct_auto.sum()), int(auto.sum())),
        "auto_match_recall": ratio(int(correct_auto.sum()), int(gold_match.sum())),
        "match_review_count": int(frame.predicted_status.eq("MATCH_REVIEW").sum()),
        "no_match_count": int(frame.predicted_status.eq("NO_MATCH").sum()),
        "gold_match_to_no_match_count": int((gold_match & frame.predicted_status.eq("NO_MATCH")).sum()),
        "gold_no_match_to_match_count": int((gold_no_match & auto).sum()),
    }


def metric_rows(results: pd.DataFrame) -> pd.DataFrame:
    rows = [measure(results, "ALL", "OVERALL")]
    for group, subset in results.groupby("sample_group", sort=False):
        rows.append(measure(subset, str(group), "SAMPLE_GROUP"))
    challenge = results[results.sample_group.eq("CHALLENGE")]
    for challenge_type, subset in challenge.groupby("challenge_type", sort=True):
        rows.append(measure(subset, str(challenge_type), "CHALLENGE_TYPE"))
    return pd.DataFrame(rows)


def pct(value: float) -> str:
    return "-" if pd.isna(value) else f"{value:.4f}"


def markdown_metric_table(metrics: pd.DataFrame) -> list[str]:
    lines = [
        "| 구분 | 대상 | Gold MATCH | R@1 | R@3 | R@5 | MRR | Auto MATCH | 정답 Auto | 오탐 | Precision | Recall | REVIEW | NO_MATCH |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in metrics.itertuples(index=False):
        lines.append(
            f"| {row.breakdown_value} | {row.evaluation_count} | {row.gold_match_count} | "
            f"{pct(row.retrieval_recall_at_1)} | {pct(row.retrieval_recall_at_3)} | "
            f"{pct(row.retrieval_recall_at_5)} | {pct(row.retrieval_mrr)} | "
            f"{row.auto_match_count} | {row.correct_auto_match_count} | {row.false_auto_match_count} | "
            f"{pct(row.auto_match_precision)} | {pct(row.auto_match_recall)} | "
            f"{row.match_review_count} | {row.no_match_count} |"
        )
    return lines


def example_table(frame: pd.DataFrame, limit: int = 8) -> list[str]:
    lines = [
        "| DEV ID | 상품 | Gold | Gold ID | 현재 판정 | 현재 ID | 후보 Top5 |",
        "|---|---|---|---:|---|---:|---|",
    ]
    for row in frame.head(limit).itertuples(index=False):
        gold_id = "" if pd.isna(row.gold_fragrantica_id) else str(int(row.gold_fragrantica_id))
        predicted_id = "" if pd.isna(row.predicted_fragrantica_id) else str(int(row.predicted_fragrantica_id))
        product = str(row.raw_product_names).replace("|", "/")
        candidates = str(row.retrieval_top5_names).replace("|", " / ")
        lines.append(
            f"| {row.queue_id} | {product} | {row.gold_status} | {gold_id} | "
            f"{row.predicted_status} | {predicted_id} | {candidates} |"
        )
    if len(frame) == 0:
        lines.append("| - | 해당 사례 없음 | - |  | - |  | - |")
    return lines


def write_report(results: pd.DataFrame, metrics: pd.DataFrame, input_hashes: dict[Path, str]) -> None:
    overall = metrics.iloc[0]
    representative = metrics[
        (metrics.breakdown_level == "SAMPLE_GROUP") & (metrics.breakdown_value == "REPRESENTATIVE")
    ].iloc[0]
    challenge = metrics[
        (metrics.breakdown_level == "SAMPLE_GROUP") & (metrics.breakdown_value == "CHALLENGE")
    ].iloc[0]
    false_matches = results[results.false_auto_match].sort_values("queue_id")
    retrieval_misses = results[
        results.gold_status.eq("MATCH")
        & (pd.to_numeric(results.gold_candidate_rank, errors="coerce").isna()
           | pd.to_numeric(results.gold_candidate_rank, errors="coerce").gt(5))
    ].sort_values("queue_id")
    snapshot_count = int(results.snapshot_override_used.sum())

    lines = [
        "# Fragrantica matcher Gold DEV baseline", "",
        "## 평가 범위", "",
        f"- Gold DEV: {EXPECTED_GOLD['rows']}개",
        f"- 평가 대상: {int(overall.evaluation_count)}개",
        f"- Gold MATCH: {int(overall.gold_match_count)}개",
        f"- Gold NO_MATCH: {int(overall.gold_no_match_count)}개",
        f"- UNRESOLVED 제외: {EXPECTED_GOLD['unresolved']}개",
        "- progressive stopping을 사용하지 않고 평가 대상 전체를 match_one에 직접 전달했다.",
        "- Candidate Retrieval은 현재 matcher의 브랜드 범위, 형태·농도 필터와 fuzzy 정렬을 그대로 재현했다.",
        f"- Match Confirmation에는 현재 matcher에 이미 존재하던 snapshot manual override도 포함된다: {snapshot_count}개.",
        "- gold_set_test.csv는 읽거나 사용하지 않았다.", "",
        "## 전체 baseline", "",
        f"- Recall@1: {overall.retrieval_recall_at_1:.4f}",
        f"- Recall@3: {overall.retrieval_recall_at_3:.4f}",
        f"- Recall@5: {overall.retrieval_recall_at_5:.4f}",
        f"- MRR: {overall.retrieval_mrr:.4f}",
        f"- Top5 retrieval miss: {int(overall.retrieval_top5_miss_count)}개",
        f"- Auto-MATCH: {int(overall.auto_match_count)}개",
        f"- Correct Auto-MATCH: {int(overall.correct_auto_match_count)}개",
        f"- False Auto-MATCH: {int(overall.false_auto_match_count)}개",
        f"- Auto-MATCH Precision: {overall.auto_match_precision:.4f}",
        f"- Auto-MATCH Recall: {overall.auto_match_recall:.4f}",
        f"- MATCH_REVIEW: {int(overall.match_review_count)}개",
        f"- NO_MATCH: {int(overall.no_match_count)}개",
        f"- Gold MATCH를 NO_MATCH로 판정: {int(overall.gold_match_to_no_match_count)}개",
        f"- Gold NO_MATCH를 MATCH로 잘못 확정: {int(overall.gold_no_match_to_match_count)}개", "",
        "## Representative와 Challenge", "",
        f"- Representative: {int(representative.evaluation_count)}개, R@5 {representative.retrieval_recall_at_5:.4f}, "
        f"Precision {representative.auto_match_precision:.4f}, Recall {representative.auto_match_recall:.4f}",
        f"- Challenge: {int(challenge.evaluation_count)}개, R@5 {challenge.retrieval_recall_at_5:.4f}, "
        f"Precision {challenge.auto_match_precision:.4f}, Recall {challenge.auto_match_recall:.4f}", "",
        "### 상세 breakdown", "",
    ]
    lines.extend(markdown_metric_table(metrics))
    lines += ["", "## False Auto-MATCH 사례", ""]
    lines.extend(example_table(false_matches))
    lines += ["", "## Candidate Retrieval Top5 miss 사례", ""]
    lines.extend(example_table(retrieval_misses))
    lines += [
        "", "## 재현 정보", "",
        f"- gold_set_dev.csv SHA-256: `{input_hashes[GOLD_PATH]}`",
        f"- build_korea_popularity_map.py SHA-256: `{input_hashes[ROOT / 'src' / 'korea' / 'build_korea_popularity_map.py']}`",
        f"- korea_commercial_identities.csv SHA-256: `{input_hashes[COMMERCIAL_PATH]}`",
        f"- perfumes.csv SHA-256: `{input_hashes[PERFUMES_PATH]}`",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    verify_snapshot()
    matcher_path = ROOT / "src" / "korea" / "build_korea_popularity_map.py"
    inputs = (GOLD_PATH, matcher_path, COMMERCIAL_PATH, PERFUMES_PATH)
    before_hashes = {path: sha256(path) for path in inputs}

    gold = pd.read_csv(GOLD_PATH, encoding="utf-8-sig")
    commercial = pd.read_csv(COMMERCIAL_PATH, keep_default_na=False)
    perfumes = pd.read_csv(
        PERFUMES_PATH, usecols=["id", "name", "brand", "description"], low_memory=False
    )
    assert len(gold) == EXPECTED_GOLD["rows"]
    assert gold.split.eq("DEV").all()
    eligible_mask = as_bool(gold.evaluation_eligible)
    eligible = gold[eligible_mask].copy()
    assert len(eligible) == EXPECTED_GOLD["eligible"]
    assert eligible.gold_status.value_counts().to_dict() == {
        "MATCH": EXPECTED_GOLD["match"], "NO_MATCH": EXPECTED_GOLD["no_match"]
    }
    assert int((~eligible_mask).sum()) == EXPECTED_GOLD["unresolved"]
    assert gold.loc[~eligible_mask, "gold_status"].eq("UNRESOLVED").all()
    assert eligible.commercial_identity_id.isin(commercial.commercial_identity_id).all()

    joined = eligible.merge(
        commercial[
            ["commercial_identity_id", "fragrance_name_normalized", "canonical_brand",
             "concentration", "product_form"]
        ],
        on="commercial_identity_id", how="left", suffixes=("_gold", ""), validate="one_to_one",
    )
    brand_groups = {
        matcher.latin_key(brand): rows.copy() for brand, rows in perfumes.groupby("brand", sort=False)
        if matcher.latin_key(brand)
    }

    output_rows = []
    for row in joined.itertuples(index=False):
        series = pd.Series(row._asdict())
        brand_rows = brand_groups.get(matcher.latin_key(row.canonical_brand), pd.DataFrame())
        candidates = retrieve_candidates(series, brand_rows)
        result = matcher.match_one(series, brand_rows)
        gold_id = int(row.gold_fragrantica_id) if row.gold_status == "MATCH" else None
        candidate_ids = [candidate[1] for candidate in candidates]
        candidate_rank = candidate_ids.index(gold_id) + 1 if gold_id in candidate_ids else None
        predicted_id = int(result["fragrantica_id"]) if pd.notna(result["fragrantica_id"]) else None
        correct_auto = bool(
            result["fragrantica_match_status"] == "MATCH"
            and row.gold_status == "MATCH" and predicted_id == gold_id
        )
        false_auto = bool(result["fragrantica_match_status"] == "MATCH" and not correct_auto)
        override_key = (row.canonical_brand, row.fragrance_name_normalized, row.concentration)
        output_rows.append({
            "queue_id": row.queue_id, "sample_group": row.sample_group,
            "challenge_type": row.challenge_type, "population_stratum": row.population_stratum,
            "commercial_identity_id": row.commercial_identity_id,
            "raw_product_names": row.raw_product_names, "canonical_brand": row.canonical_brand,
            "fragrance_name_normalized": row.fragrance_name_normalized,
            "concentration": row.concentration, "product_form": row.product_form,
            "gold_status": row.gold_status, "gold_fragrantica_id": gold_id,
            "gold_fragrantica_name": row.gold_fragrantica_name,
            "gold_candidate_rank": candidate_rank,
            "reciprocal_rank": 1.0 / candidate_rank if candidate_rank else 0.0,
            "retrieval_top5_ids": "|".join(str(x[1]) for x in candidates[:5]),
            "retrieval_top5_names": "|".join(x[2] for x in candidates[:5]),
            "predicted_status": result["fragrantica_match_status"],
            "predicted_fragrantica_id": predicted_id,
            "predicted_match_basis": result["fragrantica_match_basis"],
            "predicted_candidate_ids": result["fragrantica_candidate_ids"],
            "predicted_candidate_names": result["fragrantica_candidate_names"],
            "predicted_match_score": result["fragrantica_match_score"],
            "predicted_match_margin": result["fragrantica_match_margin"],
            "snapshot_override_used": override_key in matcher.SNAPSHOT_FRAGRANTICA_MATCHES,
            "correct_auto_match": correct_auto, "false_auto_match": false_auto,
            "false_auto_match_type": (
                "GOLD_NO_MATCH" if false_auto and row.gold_status == "NO_MATCH"
                else "WRONG_FRAGRANTICA_ID" if false_auto else ""
            ),
        })

    results = pd.DataFrame(output_rows)
    metrics = metric_rows(results)
    assert len(results) == EXPECTED_GOLD["eligible"]
    assert set(results.predicted_status) <= matcher.ALLOWED_MATCH_STATUS
    assert int(results.gold_status.eq("MATCH").sum()) == EXPECTED_GOLD["match"]
    assert int(results.gold_status.eq("NO_MATCH").sum()) == EXPECTED_GOLD["no_match"]
    assert int((results.predicted_status == "MATCH").sum()) == int(
        results.correct_auto_match.sum() + results.false_auto_match.sum()
    )

    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    results.to_csv(RESULTS_PATH, index=False, encoding="utf-8-sig")
    write_report(results, metrics, before_hashes)
    assert all(sha256(path) == before_hashes[path] for path in inputs)

    overall = metrics.iloc[0]
    print(
        f"eligible={int(overall.evaluation_count)} retrieval="
        f"R@1 {overall.retrieval_recall_at_1:.4f} R@3 {overall.retrieval_recall_at_3:.4f} "
        f"R@5 {overall.retrieval_recall_at_5:.4f} MRR {overall.retrieval_mrr:.4f}"
    )
    print(
        f"confirmation=auto {int(overall.auto_match_count)} correct {int(overall.correct_auto_match_count)} "
        f"false {int(overall.false_auto_match_count)} precision {overall.auto_match_precision:.4f} "
        f"recall {overall.auto_match_recall:.4f} review {int(overall.match_review_count)} "
        f"no_match {int(overall.no_match_count)}"
    )


if __name__ == "__main__":
    use_llm_channel(None)   # 이 스크립트는 LLM 채널 도입 전 baseline 을 잰다
    use_verification(False)  # Verification 도입 전 baseline 이기도 하다
    main()

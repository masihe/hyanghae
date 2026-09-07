"""Compare five independent Method 3 DEV retrieval representations.

Run: venv/Scripts/python.exe evaluate_fragrantica_method3_dev.py

The two LLM CSVs are immutable, pre-generated inputs.  Gold labels enter only
after all five rankings have been constructed over Method 2's candidate pools.
There is no fusion, gating, verification, or final match classification here.
"""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import platform
import re
import sys
import time
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "korea"))
import build_korea_popularity_map as matcher
import evaluate_fragrantica_matcher_dev as baseline
import evaluate_fragrantica_method2_dev as method2
from evaluate_fragrantica_method1_dev import table

ROOT = Path(__file__).resolve().parents[2]  # MAP/
DATA = ROOT / "data/korea_popularity"
OUT = DATA / "evaluation"
PREFIX = "fragrantica_method3_dev"
KO_LATIN_PATH = OUT / "llm_ko_to_latin_outputs.csv"
LATIN_KO_PATH = OUT / "llm_latin_to_ko_outputs.csv"
METHOD2_RESULTS_PATH = OUT / "fragrantica_method2_dev_results.csv"
METHOD2_METRICS_PATH = OUT / "fragrantica_method2_dev_metrics.csv"
METHOD2_CANDIDATES_PATH = OUT / "fragrantica_method2_dev_candidate_transliterations.csv"
METHODS = (
    "baseline_lexical",
    "uroman",
    "enko_transliteration",
    "llm_ko_to_latin",
    "llm_latin_to_ko",
)
LLM_METHODS = ("llm_ko_to_latin", "llm_latin_to_ko")
EXPECTED_LLM_HASHES = {
    KO_LATIN_PATH: "8a4345e467ff6f2867f7cb512c555da95f10cc01ffc22e8e5a315e955ded20cb",
    LATIN_KO_PATH: "3b2082956f6f9de884790d5a8252eb02c8b4768fefef3842e01dfddb6279bc40",
}
SETTINGS = {
    "methods": list(METHODS),
    "method2_reuse": "prepare_rankings/evaluate/measure, including exact brand blocking and original concentration/form filters",
    "candidate_pool": "exactly the Method 2 full per-identity candidate pool for every method",
    "llm_ko_to_latin_query": "reconstructed_fragrance_latin; literal UNKNOWN/blank comparison key is empty; reconstructed brand diagnostic only",
    "llm_ko_to_latin_candidate": "Method 2 structured-normalized candidate Latin core",
    "llm_ko_to_latin_comparison": "NFKC casefold alphanumeric-only, SequenceMatcher(autojunk=False).ratio()",
    "llm_latin_to_ko_query": "Method 2 structured-normalized Korean member cores, NFD canonical Hangul jamo",
    "llm_latin_to_ko_candidate": "fixed korean_transliteration linked by exact Method 2 Latin core; literal UNKNOWN/blank key is empty",
    "llm_latin_to_ko_comparison": "same Method 2 NFD jamo key and SequenceMatcher ratio as dedicated en-ko channel",
    "reconstruction_status_in_ranking": False,
    "reconstructed_brand_in_ranking": False,
    "ties": "score descending then Fragrantica ID descending (Method 2 rank_channel)",
    "output_k": 10,
    "mrr": "full common candidate pool; absent gold rank contributes zero",
    "fusion": False,
    "gating": False,
    "verification": False,
    "parameter_tuning": False,
}


def dump(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def core_id(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def llm_comparison_key(text: str, jamo=False) -> str:
    """Use output content only; reconstruction_status is diagnostic metadata."""
    text = text.strip()
    if not text or text.casefold() == "unknown":
        return ""
    return method2.comparison_key(text, jamo)


def as_text(series: pd.Series) -> pd.Series:
    return series.fillna("").astype(str)


def assert_frame_reproduced(actual: pd.DataFrame, saved: pd.DataFrame, key_columns: list[str]) -> None:
    """Compare saved CSV content without relying on pandas' inferred dtypes."""
    assert list(actual.columns) == list(saved.columns)
    actual = actual.sort_values(key_columns).reset_index(drop=True)
    saved = saved.sort_values(key_columns).reset_index(drop=True)
    assert len(actual) == len(saved)
    numeric = [c for c in actual.columns if c in {
        "fragrantica_id", "input_tokens", "queue_id", "gold_fragrantica_id",
        "candidate_count", "baseline_rank", "gold_candidate_rank", "reciprocal_rank",
        "gold_match", "catalog_missing", "in_candidate_pool", "mrr", "mrr_at_10",
        "recall_at_1", "recall_at_3", "recall_at_5", "recall_at_10",
        "top5_miss", "top10_miss", "rescue_at_5", "regression_at_5",
        "rescue_at_10", "regression_at_10", "baseline_top5_miss",
        "baseline_top5_hit", "baseline_top10_miss", "baseline_top10_hit",
    }]
    booleans = [c for c in actual.columns if c in {
        "catalog_retrievable", "rescue_at_5", "regression_at_5",
        "rescue_at_10", "regression_at_10", "non_ascii_core",
    }]
    for column in actual.columns:
        if column in booleans:
            left = baseline.as_bool(actual[column])
            right = baseline.as_bool(saved[column])
            assert left.tolist() == right.tolist(), column
        elif column in numeric:
            left = pd.to_numeric(actual[column], errors="coerce").to_numpy(float)
            right = pd.to_numeric(saved[column], errors="coerce").to_numpy(float)
            assert np.allclose(left, right, equal_nan=True), column
        else:
            assert as_text(actual[column]).tolist() == as_text(saved[column]).tolist(), column


def load_and_validate_llm_inputs(identity_ids, inputs, candidates):
    llm_hashes = {path: matcher.sha256(path) for path in EXPECTED_LLM_HASHES}
    assert llm_hashes == EXPECTED_LLM_HASHES, "Frozen LLM input hash differs"

    ko_latin = pd.read_csv(KO_LATIN_PATH, keep_default_na=False)
    latin_ko = pd.read_csv(LATIN_KO_PATH, keep_default_na=False)
    expected_ko_columns = {
        "commercial_identity_id", "source_brands", "existing_canonical_brand", "query_cores",
        "reconstructed_brand_latin", "reconstructed_fragrance_latin", "reconstruction_status",
    }
    expected_latin_columns = {"core_id", "latin_core", "korean_transliteration", "reconstruction_status"}
    assert set(ko_latin.columns) == expected_ko_columns
    assert set(latin_ko.columns) == expected_latin_columns
    assert len(ko_latin) == 77 and ko_latin.commercial_identity_id.is_unique
    assert len(latin_ko) == 2450 and latin_ko.core_id.is_unique and latin_ko.latin_core.is_unique
    assert set(ko_latin.commercial_identity_id) == set(identity_ids)
    assert set(ko_latin.reconstruction_status) <= {"OK", "UNCERTAIN", "UNKNOWN"}
    assert set(latin_ko.reconstruction_status) <= {"OK", "UNCERTAIN", "UNKNOWN"}
    assert latin_ko.apply(lambda row: core_id(row.latin_core) == row.core_id, axis=1).all()

    candidate_cores = set(candidates.core)
    llm_cores = set(latin_ko.latin_core)
    assert candidate_cores == llm_cores, (
        f"Latin core mismatch: missing={len(candidate_cores-llm_cores)}, extra={len(llm_cores-candidate_cores)}"
    )
    ko_by_id = ko_latin.set_index("commercial_identity_id", drop=False)
    for ci in identity_ids:
        assert json.loads(ko_by_id.at[ci, "query_cores"]) == inputs[ci]["query_cores"]

    validation = {
        "ko_to_latin_rows": len(ko_latin),
        "ko_to_latin_duplicate_ids": int(ko_latin.commercial_identity_id.duplicated().sum()),
        "ko_to_latin_missing_identity_ids": 0,
        "ko_to_latin_extra_identity_ids": 0,
        "ko_to_latin_status_counts": ko_latin.reconstruction_status.value_counts().to_dict(),
        "ko_to_latin_blank_outputs": int(ko_latin.reconstructed_fragrance_latin.str.strip().eq("").sum()),
        "latin_to_ko_rows": len(latin_ko),
        "latin_to_ko_unique_cores": int(latin_ko.latin_core.nunique()),
        "latin_to_ko_duplicate_core_ids": int(latin_ko.core_id.duplicated().sum()),
        "latin_to_ko_duplicate_latin_cores": int(latin_ko.latin_core.duplicated().sum()),
        "latin_to_ko_missing_method2_cores": 0,
        "latin_to_ko_extra_cores": 0,
        "latin_to_ko_status_counts": latin_ko.reconstruction_status.value_counts().to_dict(),
        "latin_to_ko_blank_outputs": int(latin_ko.korean_transliteration.str.strip().eq("").sum()),
        "candidate_rows": len(candidates),
        "candidate_unique_ids": int(candidates.fragrantica_id.nunique()),
        "candidate_unique_cores": int(candidates.core.nunique()),
        "core_id_sha256_prefix_valid": True,
    }
    return ko_latin, latin_ko, validation


def add_llm_rankings(identity_ids, inputs, rankings, candidates, ko_latin, latin_ko):
    started = time.perf_counter()
    ko_by_id = ko_latin.set_index("commercial_identity_id")
    latin_by_core = latin_ko.set_index("latin_core")
    candidate_latin_keys = dict(zip(candidates.fragrantica_id, candidates.core.map(method2.comparison_key)))
    llm_text_by_core = latin_by_core.korean_transliteration.to_dict()
    candidate_llm_jamo_keys = {
        int(row.fragrantica_id): llm_comparison_key(llm_text_by_core[row.core], True)
        for row in candidates.itertuples(index=False)
    }
    for ci in identity_ids:
        row = ko_by_id.loc[ci]
        reconstructed = row.reconstructed_fragrance_latin.strip()
        query_key = llm_comparison_key(reconstructed)
        inputs[ci].update({
            "reconstructed_brand_latin": row.reconstructed_brand_latin,
            "reconstructed_fragrance_latin": reconstructed,
            "ko_to_latin_status": row.reconstruction_status,
            "ko_to_latin_comparison": query_key,
        })
        rankings[ci]["llm_ko_to_latin"] = method2.rank_channel(
            [(reconstructed, query_key)], inputs[ci]["pool"], candidate_latin_keys
        )
        rankings[ci]["llm_latin_to_ko"] = method2.rank_channel(
            list(zip(inputs[ci]["query_cores"], inputs[ci]["jamo_queries"])),
            inputs[ci]["pool"], candidate_llm_jamo_keys,
        )
        expected_pool = set(inputs[ci]["pool"])
        for method in METHODS:
            ranking = rankings[ci][method]
            assert len(ranking) == len(expected_pool)
            assert {item[1] for item in ranking} == expected_pool

    candidates = candidates.copy()
    candidates["llm_core_id"] = candidates.core.map(latin_by_core.core_id)
    candidates["llm_korean_transliteration"] = candidates.core.map(latin_by_core.korean_transliteration)
    candidates["llm_latin_to_ko_status"] = candidates.core.map(latin_by_core.reconstruction_status)
    candidates["llm_jamo_comparison"] = candidates.fragrantica_id.map(candidate_llm_jamo_keys)
    return candidates, time.perf_counter() - started


def evaluate(gold, inputs, rankings, candidates, perfumes):
    """Evaluate already-created rankings; Gold fields are not retrieval inputs."""
    old_results = pd.read_csv(baseline.RESULTS_PATH, keep_default_na=False).set_index("commercial_identity_id")
    catalog = perfumes.set_index("id", drop=False)
    ctable = candidates.set_index("fragrantica_id")
    records = []
    for g in gold.itertuples(index=False):
        ci = g.commercial_identity_id
        info = inputs[ci]
        baseline_ids = [item[1] for item in rankings[ci]["baseline_lexical"]]
        gid = int(g.gold_fragrantica_id) if g.gold_status == "MATCH" else None
        base_rank = baseline_ids.index(gid) + 1 if gid in baseline_ids else None
        stored = old_results.loc[ci]
        assert stored.retrieval_top5_ids == "|".join(map(str, baseline_ids[:5]))
        expected_rank = int(float(stored.gold_candidate_rank)) if stored.gold_candidate_rank != "" else None
        assert base_rank == expected_rank
        catalog_status = "NOT_APPLICABLE"
        if gid is not None:
            if gid not in catalog.index:
                catalog_status = "CATALOG_MISSING"
            elif gid in baseline_ids:
                catalog_status = "IN_CANDIDATE_POOL"
            elif matcher.latin_key(catalog.at[gid, "brand"]) != matcher.latin_key(stored.canonical_brand):
                catalog_status = "BRAND_BLOCKED"
            else:
                catalog_status = "CONCENTRATION_OR_FORM_FILTER"

        for method in METHODS:
            ranking = rankings[ci][method]
            ranked_ids = [item[1] for item in ranking]
            rank = ranked_ids.index(gid) + 1 if gid in ranked_ids else None
            top = [dict(
                rank=position,
                id=i,
                score=score,
                name=ctable.at[i, "name"],
                core=ctable.at[i, "core"],
                enko_transliteration=ctable.at[i, "korean_transliteration"],
                llm_korean_transliteration=ctable.at[i, "llm_korean_transliteration"],
                llm_latin_to_ko_status=ctable.at[i, "llm_latin_to_ko_status"],
                uroman=ctable.at[i, "uroman"],
                matched_query=query,
            ) for position, (score, i, query) in enumerate(ranking[:10], 1)]
            record = dict(
                queue_id=g.queue_id,
                commercial_identity_id=ci,
                method=method,
                sample_group=g.sample_group,
                challenge_type=g.challenge_type,
                population_stratum=g.population_stratum,
                gold_status=g.gold_status,
                raw_product_names=json.dumps(info["raw_names"], ensure_ascii=False),
                query_cores=json.dumps(info["query_cores"], ensure_ascii=False),
                query_uroman=json.dumps(info["uroman_queries"], ensure_ascii=False),
                query_jamo=json.dumps(info["jamo_queries"], ensure_ascii=False),
                reconstructed_brand_latin=info["reconstructed_brand_latin"],
                reconstructed_fragrance_latin=info["reconstructed_fragrance_latin"],
                llm_ko_to_latin_status=info["ko_to_latin_status"],
                llm_ko_to_latin_comparison=info["ko_to_latin_comparison"],
                source_refs=json.dumps(info["source_refs"], ensure_ascii=False),
                gold_fragrantica_id=gid,
                gold_fragrantica_name=g.gold_fragrantica_name,
                catalog_status=catalog_status,
                catalog_retrievable=gid in catalog.index if gid else False,
                candidate_count=len(ranking),
                baseline_rank=base_rank,
                gold_candidate_rank=rank,
                reciprocal_rank=1 / rank if rank else 0,
                gold_core=ctable.at[gid, "core"] if gid in ctable.index else "",
                gold_uroman=ctable.at[gid, "uroman"] if gid in ctable.index else "",
                gold_enko_transliteration=ctable.at[gid, "korean_transliteration"] if gid in ctable.index else "",
                gold_llm_korean_transliteration=ctable.at[gid, "llm_korean_transliteration"] if gid in ctable.index else "",
                gold_llm_latin_to_ko_status=ctable.at[gid, "llm_latin_to_ko_status"] if gid in ctable.index else "NOT_IN_METHOD2_CANDIDATE_CORES",
                top10_ids="|".join(map(str, ranked_ids[:10])),
                top10_candidates=json.dumps(top, ensure_ascii=False),
            )
            for k in (5, 10):
                old_hit = base_rank is not None and base_rank <= k
                new_hit = rank is not None and rank <= k
                record[f"rescue_at_{k}"] = gid is not None and not old_hit and new_hit
                record[f"regression_at_{k}"] = gid is not None and old_hit and not new_hit
            records.append(record)
    return pd.DataFrame(records)


def measure(results):
    rows = []
    matches = results[results.gold_status.eq("MATCH")]
    for scope, cohort in (
        ("ALL_GOLD_MATCH", matches),
        ("CATALOG_RETRIEVABLE", matches[matches.catalog_retrievable]),
    ):
        for method, frame in cohort.groupby("method", sort=False):
            groups = [("OVERALL", "ALL", frame)]
            groups += [("SAMPLE_GROUP", key, sub) for key, sub in frame.groupby("sample_group")]
            groups += [("CHALLENGE_TYPE", key, sub) for key, sub in frame[frame.sample_group.eq("CHALLENGE")].groupby("challenge_type")]
            for level, group, sub in groups:
                ranks = sub.gold_candidate_rank
                old = sub.baseline_rank
                row = dict(
                    scope=scope,
                    method=method,
                    level=level,
                    group=group,
                    gold_match=len(sub),
                    catalog_missing=int(sub.catalog_status.eq("CATALOG_MISSING").sum()),
                    in_candidate_pool=int(sub.catalog_status.eq("IN_CANDIDATE_POOL").sum()),
                    mrr=float(sub.reciprocal_rank.mean()),
                    mrr_at_10=float(sub.reciprocal_rank.where(ranks.le(10), 0).mean()),
                )
                row.update({f"recall_at_{k}": float(ranks.le(k).mean()) for k in (1, 3, 5, 10)})
                for k in (5, 10):
                    row[f"top{k}_miss"] = int((~ranks.le(k)).sum())
                    row[f"rescue_at_{k}"] = int(sub[f"rescue_at_{k}"].sum())
                    row[f"regression_at_{k}"] = int(sub[f"regression_at_{k}"].sum())
                    row[f"baseline_top{k}_miss"] = int((~old.le(k)).sum())
                    row[f"baseline_top{k}_hit"] = int(old.le(k).sum())
                    assert int(ranks.le(k).sum()) == int(old.le(k).sum()) + row[f"rescue_at_{k}"] - row[f"regression_at_{k}"]
                rows.append(row)
    return pd.DataFrame(rows)


def status_measure(results):
    rows = []
    matches = results[results.gold_status.eq("MATCH")]
    configurations = (
        ("llm_ko_to_latin", "llm_ko_to_latin_status", ["OK", "UNCERTAIN", "UNKNOWN"]),
        ("llm_latin_to_ko", "gold_llm_latin_to_ko_status", ["OK", "UNCERTAIN", "UNKNOWN", "NOT_IN_METHOD2_CANDIDATE_CORES"]),
    )
    for scope, cohort in (
        ("ALL_GOLD_MATCH", matches),
        ("CATALOG_RETRIEVABLE", matches[matches.catalog_retrievable]),
    ):
        for method, status_column, statuses in configurations:
            frame = cohort[cohort.method.eq(method)]
            for status in statuses:
                sub = frame[frame[status_column].eq(status)]
                ranks = sub.gold_candidate_rank
                rows.append(dict(
                    scope=scope,
                    method=method,
                    status=status,
                    gold_match=len(sub),
                    recall_at_5=float(ranks.le(5).mean()) if len(sub) else np.nan,
                    recall_at_10=float(ranks.le(10).mean()) if len(sub) else np.nan,
                    mrr=float(sub.reciprocal_rank.mean()) if len(sub) else np.nan,
                ))
    return pd.DataFrame(rows)


def direction_comparison(results, scope):
    matches = results[results.gold_status.eq("MATCH")]
    if scope == "CATALOG_RETRIEVABLE":
        matches = matches[matches.catalog_retrievable]
    pivot = matches.pivot(index="commercial_identity_id", columns="method", values="gold_candidate_rank")
    rows = []
    for k in (5, 10):
        base_miss = ~pivot.baseline_lexical.le(k)
        ko_hit = pivot.llm_ko_to_latin.le(k)
        latin_hit = pivot.llm_latin_to_ko.le(k)
        rows.append(dict(
            scope=scope,
            k=k,
            baseline_miss=int(base_miss.sum()),
            ko_to_latin_only_rescue=int((base_miss & ko_hit & ~latin_hit).sum()),
            latin_to_ko_only_rescue=int((base_miss & ~ko_hit & latin_hit).sum()),
            both_rescue=int((base_miss & ko_hit & latin_hit).sum()),
            neither_rescues=int((base_miss & ~ko_hit & ~latin_hit).sum()),
        ))
    return pd.DataFrame(rows)


def case_table(results, method, kind, k, limit=10):
    frame = results[results.method.eq(method) & results.gold_status.eq("MATCH")].copy()
    flag = f"{kind}_at_{k}"
    frame = frame[frame[flag]]
    frame["rank_change"] = frame.baseline_rank - frame.gold_candidate_rank
    ascending = kind == "regression"
    return frame.sort_values(["rank_change", "queue_id"], ascending=[ascending, True]).head(limit)


def language_marker(name: str) -> str:
    """Post-hoc display aid only; never used by candidate selection or ranking."""
    lowered = unicodedata.normalize("NFKC", name).casefold()
    french = re.search(r"(^|[\s'-])(eau|le|la|les|de|du|des|pour|femme|homme|nuit|fleur|l'|d')([\s'-]|$)", lowered)
    italian = re.search(r"(^|[\s'-])(acqua|di|della|delle|uomo|donna|notte|fiore)([\s'-]|$)", lowered)
    if french:
        return "FRENCH_MARKER"
    if italian:
        return "ITALIAN_MARKER"
    if re.search(r"[^\x00-\x7f]", name):
        return "NON_ASCII_LATIN"
    return "NO_FRENCH_ITALIAN_MARKER"


def add_posthoc_case_types(frame):
    frame = frame.copy()
    frame["language_signal"] = frame.gold_fragrantica_name.map(language_marker)
    frame["number_year_version"] = frame.apply(
        lambda row: bool(re.search(r"\d", f"{row.reconstructed_fragrance_latin} {row.gold_fragrantica_name}")), axis=1
    )
    frame["variant_flanker"] = frame.challenge_type.eq("FAMILY_VARIANT_RISK")
    frame["query_information_limited"] = frame.challenge_type.eq("SHORT_GENERIC_NAME")
    return frame


def fmt_delta(value):
    return f"{value:+.4f}"


def write_report(results, metrics, status_metrics, candidates, directions, times, hashes, validation, generated):
    metric_cols = ["method", "group", "gold_match", "recall_at_1", "recall_at_3", "recall_at_5", "recall_at_10", "mrr", "mrr_at_10", "top5_miss", "top10_miss"]
    rescue_cols = ["method", "group", "gold_match", "baseline_top5_miss", "rescue_at_5", "baseline_top5_hit", "regression_at_5", "baseline_top10_miss", "rescue_at_10", "baseline_top10_hit", "regression_at_10"]
    status_cols = ["method", "status", "gold_match", "recall_at_5", "recall_at_10", "mrr"]
    direction_cols = ["scope", "k", "baseline_miss", "ko_to_latin_only_rescue", "latin_to_ko_only_rescue", "both_rescue", "neither_rescues"]
    example_cols = [
        "queue_id", "raw_product_names", "query_cores", "reconstructed_fragrance_latin",
        "gold_fragrantica_name", "gold_enko_transliteration", "gold_llm_korean_transliteration",
        "baseline_rank", "gold_candidate_rank", "catalog_status",
    ]
    diagnostic_cols = ["queue_id", "method", "gold_fragrantica_name", "language_signal", "number_year_version", "variant_flanker", "query_information_limited", "baseline_rank", "gold_candidate_rank", "catalog_status"]
    base = results[results.method.eq("baseline_lexical") & results.gold_status.eq("MATCH")]
    lines = [
        "# Method 3: fixed LLM name representations DEV retrieval",
        "",
        "## 실험 범위",
        "",
        f"- DEV 80행 중 evaluation-eligible 77 identity를 실행했고, Gold MATCH {len(base)}개를 지표 분모로 사용했다. NO_MATCH 16개는 retrieval 지표에서 제외했다.",
        "- Gold는 다섯 ranking이 모두 만들어진 뒤 평가에만 사용했다. TEST 입력은 코드 경로와 입력 목록에 없으며 열지 않았다.",
        "- 다섯 방법은 identity별로 같은 Method 2 전체 candidate ID 집합과 같은 exact-brand blocking, concentration/form filter를 쓴다. 어떤 ranking도 fusion하지 않았다.",
        "- baseline lexical, uroman, 전용 en→ko는 Method 2 구현을 직접 재실행했다. 저장된 Method 2 results 231행, metrics, candidate representations 전 항목이 일치했다.",
        "- LLM KO→Latin은 고정 reconstructed_fragrance_latin 하나와 Method 2 structured-normalized Latin core를 NFKC/casefold/alphanumeric key로 바꿔 동일 SequenceMatcher ratio로 비교했다. reconstructed_brand_latin은 결과에 보존했지만 ranking에 쓰지 않았다.",
        "- LLM Latin→KO는 고정 korean_transliteration을 exact latin_core로 연결했다. 국내 query는 Method 2 Korean core를 그대로 쓰고 양쪽 모두 같은 NFD Hangul jamo key와 같은 SequenceMatcher ratio를 썼다.",
        "- reconstruction_status는 ranking/filter에 전혀 읽히지 않고 사후 분석에만 쓰였다. 출력 문자열 자체가 `UNKNOWN` 또는 빈 값이면 comparison key를 비워 score 0으로 유지했다. 원문 대체, 보정, threshold 조정, 예외 규칙, gating, Verification은 없다.",
        "- MRR은 전체 공통 pool 순위, MRR@10은 10위 밖을 0으로 계산한다. CATALOG_RETRIEVABLE은 기존 Method 2 정의대로 Gold ID가 perfumes.csv에 존재한다는 뜻이며 pool 통과를 뜻하지 않는다.",
    ]
    for scope in ("ALL_GOLD_MATCH", "CATALOG_RETRIEVABLE"):
        subset = metrics[metrics.scope.eq(scope)]
        lines += ["", f"## {scope}: 전체 성능", ""] + table(subset[subset.level.eq("OVERALL")], metric_cols)
        lines += ["", "### Representative / Challenge", ""] + table(subset[subset.level.eq("SAMPLE_GROUP")], metric_cols)
        lines += ["", "### Challenge type별 성능", ""] + table(subset[subset.level.eq("CHALLENGE_TYPE")], metric_cols)
        lines += ["", "### Baseline 기준 Rescue / Regression", ""] + table(subset[~subset.level.eq("CHALLENGE_TYPE")], rescue_cols)
        lines += ["", "### Challenge type별 Rescue / Regression", ""] + table(subset[subset.level.eq("CHALLENGE_TYPE")], rescue_cols)

    lines += ["", "## 두 LLM 방향의 Top-K 관계", "", "아래 네 rescue 구분은 baseline miss를 분모로 한다. `neither_rescues`는 두 LLM 모두 해당 K에서 baseline miss를 구하지 못한 경우다."]
    lines += [""] + table(directions, direction_cols)
    for k in (5, 10):
        match = results[results.gold_status.eq("MATCH")]
        pivot = match.pivot(index="commercial_identity_id", columns="method", values="gold_candidate_rank")
        base_miss = ~pivot.baseline_lexical.le(k)
        categories = {
            "KO→Latin만 rescue": base_miss & pivot.llm_ko_to_latin.le(k) & ~pivot.llm_latin_to_ko.le(k),
            "Latin→KO만 rescue": base_miss & ~pivot.llm_ko_to_latin.le(k) & pivot.llm_latin_to_ko.le(k),
            "둘 다 rescue": base_miss & pivot.llm_ko_to_latin.le(k) & pivot.llm_latin_to_ko.le(k),
            "둘 다 실패": base_miss & ~pivot.llm_ko_to_latin.le(k) & ~pivot.llm_latin_to_ko.le(k),
        }
        metadata = match[match.method.eq("llm_ko_to_latin")].set_index("commercial_identity_id")
        lines += ["", f"### Top{k} 실제 사례", ""]
        for label, mask in categories.items():
            ids = pivot.index[mask]
            sample = metadata.loc[metadata.index.intersection(ids)].reset_index()
            sample["ko_to_latin_rank"] = sample.commercial_identity_id.map(pivot.llm_ko_to_latin)
            sample["latin_to_ko_rank"] = sample.commercial_identity_id.map(pivot.llm_latin_to_ko)
            cols = ["queue_id", "raw_product_names", "reconstructed_fragrance_latin", "gold_fragrantica_name", "baseline_rank", "ko_to_latin_rank", "latin_to_ko_rank", "catalog_status"]
            lines += [f"**{label} ({len(ids)})**", ""] + table(sample.head(10), cols)

    lines += ["", "## LLM reconstruction_status 사후 분석", "", "상태는 ranking/filter에 사용하지 않고 사후 slice에만 사용했다. KO→Latin은 query 행 상태, Latin→KO는 Gold candidate core에 연결된 출력 상태다. Gold가 Method 2 candidate core 집합에 없으면 별도 `NOT_IN_METHOD2_CANDIDATE_CORES`로 보존했다."]
    for scope in ("ALL_GOLD_MATCH", "CATALOG_RETRIEVABLE"):
        lines += ["", f"### {scope}", ""] + table(status_metrics[status_metrics.scope.eq(scope)], status_cols)

    lines += ["", "## 주요 개선·회귀 사례", ""]
    for method in LLM_METHODS:
        lines += [f"### {method}: 개선", ""] + table(case_table(results, method, "rescue", 10), example_cols)
        lines += ["", f"### {method}: 회귀", ""] + table(case_table(results, method, "regression", 10), example_cols)

    llm_affected = pd.concat([
        case_table(results, method, kind, k, 100)
        for method in LLM_METHODS for kind in ("rescue", "regression") for k in (5, 10)
    ]).drop_duplicates(["commercial_identity_id", "method"])
    llm_affected = add_posthoc_case_types(llm_affected)
    in_pool_misses = results[
        results.method.isin(LLM_METHODS)
        & results.gold_status.eq("MATCH")
        & results.catalog_status.eq("IN_CANDIDATE_POOL")
        & ~results.gold_candidate_rank.le(10)
    ].copy()
    in_pool_misses = add_posthoc_case_types(in_pool_misses)
    lines += [
        "",
        "## 실패 유형 구분",
        "",
        "언어 표시는 사후 설명용 일반 marker다. French/Italian marker 또는 비ASCII 철자를 식별하며 점수나 후보 선택에는 쓰지 않았다. marker가 없다는 이유만으로 실제 어원을 영어로 단정하지 않는다.",
        "",
        "### 이름 언어·숫자·variant·짧은 query 진단 (LLM rescue/regression 사례)",
        "",
    ] + table(llm_affected.sort_values(["catalog_status", "queue_id"]), diagnostic_cols)
    lines += [
        "",
        "### Candidate pool 내부 Top10 실패",
        "",
    ] + table(in_pool_misses.sort_values(["queue_id", "method"]), [
        "queue_id", "method", "raw_product_names", "reconstructed_fragrance_latin",
        "gold_fragrantica_name", "baseline_rank", "gold_candidate_rank",
    ])
    lines += [
        "",
        "- 영어 이름에서는 `Red Roses`와 `Eros Flame`이 두 LLM 모두 Top5 rescue한 반면, 일반적인 국내 표기 `Signature`만으로 `Chloé Eau de Parfum`을, `Woman`만으로 `Jimmy Choo Eau de Toilette`를 특정하지 못해 두 방향 모두 Top10 밖이었다.",
        "- French 계열 표기의 `Blanche`, `Libre`, `Le Sel d'Issey`, `Chloé ... Naturelle`은 두 LLM에서 모두 개선됐다. 이 사례들에서 고정 Latin→KO 출력은 국내 관용 표기에 전용 en→ko 출력보다 가까웠지만, 이 소표본만으로 언어 일반화를 주장하지 않는다.",
        "- Italian 이름 `Fico di Amalfi`는 baseline 46위에서 두 LLM 모두 3위로 올랐다. 긴 Fragrantica core 속 핵심 이름을 KO→Latin reconstruction 또는 더 적합한 KO 음역이 보존한 사례다.",
        "- 숫자/연도/버전에서는 `Firenze 1221 Edition Fresia`, `Miss Dior ... (2021)`, `Dior Homme Cologne 2022`가 rescue됐다. 다만 올바른 flanker 구분 능력은 별도 검증하지 않았고, 숫자가 있는 것 자체를 성공 원인으로 단정하지 않는다.",
        "- variant/flanker에서는 `Le Sel d'Issey` EDT(D012)는 baseline부터 1위였고 EDP(D022)는 두 LLM이 1위로 rescue했다. 반면 `Glow`(D002)는 concentration/form filter에서 빠져 이름 representation으로 평가할 수 없었다.",
        "- 국내 query 정보가 부족한 `Signature`(D029)와 `Woman`(D059)은 두 LLM 모두 실패했다. D030은 정규화 core에 상품 선택 문구가 남고 KO→Latin이 `Ralph`로 재구성해 Gold `Polo`와 어긋났지만, Latin→KO는 한국어 `폴로` 증거로 7위에 들어 유일한 Top10 단독 rescue가 됐다.",
    ]
    for status in ("CATALOG_MISSING", "BRAND_BLOCKED", "CONCENTRATION_OR_FORM_FILTER"):
        subset = base[base.catalog_status.eq(status)]
        lines += ["", f"### {status} ({len(subset)})", ""] + table(subset, ["queue_id", "raw_product_names", "gold_fragrantica_name", "catalog_status"])
    lines += [
        "",
        "위 세 pool 진단은 모든 방법에 공통이며 이름 ranking 실패로 해석하지 않는다. 특히 pool 밖 Gold는 어느 representation도 rescue할 수 없다. FAMILY_VARIANT_RISK는 variant/flanker 위험, SHORT_GENERIC_NAME은 국내 query 정보 부족의 사전 challenge label로만 사용했다.",
    ]

    overall = metrics[(metrics.scope.eq("ALL_GOLD_MATCH")) & metrics.level.eq("OVERALL")].set_index("method")
    base_row = overall.loc["baseline_lexical"]
    enko_row = overall.loc["enko_transliteration"]
    ko_row = overall.loc["llm_ko_to_latin"]
    latin_row = overall.loc["llm_latin_to_ko"]
    top5_direction = directions[(directions.scope.eq("ALL_GOLD_MATCH")) & directions.k.eq(5)].iloc[0]
    top10_direction = directions[(directions.scope.eq("ALL_GOLD_MATCH")) & directions.k.eq(10)].iloc[0]
    uncertain_ko = results[
        results.method.eq("llm_ko_to_latin")
        & results.gold_status.eq("MATCH")
        & results.llm_ko_to_latin_status.eq("UNCERTAIN")
    ]
    uncertain_ko_in_pool = int(uncertain_ko.catalog_status.eq("IN_CANDIDATE_POOL").sum())
    lines += [
        "",
        "## 판단",
        "",
        f"1. **LLM KO→Latin**: baseline 대비 ΔR@5={fmt_delta(ko_row.recall_at_5-base_row.recall_at_5)}, ΔR@10={fmt_delta(ko_row.recall_at_10-base_row.recall_at_10)}, ΔMRR={fmt_delta(ko_row.mrr-base_row.mrr)}. 전용 en→ko 대비 ΔR@5={fmt_delta(ko_row.recall_at_5-enko_row.recall_at_5)}, ΔR@10={fmt_delta(ko_row.recall_at_10-enko_row.recall_at_10)}, ΔMRR={fmt_delta(ko_row.mrr-enko_row.mrr)}.",
        f"2. **LLM Latin→KO**: 전용 en→ko 대비 ΔR@5={fmt_delta(latin_row.recall_at_5-enko_row.recall_at_5)}, ΔR@10={fmt_delta(latin_row.recall_at_10-enko_row.recall_at_10)}, ΔMRR={fmt_delta(latin_row.mrr-enko_row.mrr)}.",
        f"3. **실패 중첩/보완성**: baseline Top5 miss에서 KO→Latin만 {int(top5_direction.ko_to_latin_only_rescue)}, Latin→KO만 {int(top5_direction.latin_to_ko_only_rescue)}, 둘 다 {int(top5_direction.both_rescue)}; Top10에서는 각각 {int(top10_direction.ko_to_latin_only_rescue)}, {int(top10_direction.latin_to_ko_only_rescue)}, {int(top10_direction.both_rescue)}다. 방향별 단독 rescue가 있으면 오류 구조가 완전히 같지는 않다는 관찰 근거지만 fusion의 순효과는 측정하지 않았다.",
        f"4. **다음 단계**: 단일 채널 선택은 전체·challenge slice와 regression을 함께 보고 판단한다. KO→Latin UNCERTAIN Gold {len(uncertain_ko)}건 중 pool 내부는 {uncertain_ko_in_pool}건뿐이라 낮은 status slice 성능에는 pool 부재가 크게 섞여 있다. 따라서 status별 차이나 방향별 단독 rescue를 이 DEV에서 새 gating 규칙의 근거로 사용하지 않았다. selective/gated retrieval은 별도 사전 규칙과 독립 평가셋을 둔 후 연구할 수 있는 후보일 뿐, 이번 결과에는 구현하지 않았다.",
        "",
        "최고 수치만으로 결론내리지 않았으며, 61개 DEV MATCH의 표본 변동성과 candidate-pool 상한 때문에 일반화는 미확인이다.",
        "",
        "## 재현성 및 입력 검증",
        "",
        "```json",
        json.dumps(validation, ensure_ascii=False, indent=2),
        "```",
        "",
        "- 고정 LLM 파일 SHA-256은 제공값과 정확히 일치했다.",
        "- KO→Latin ID는 eligible DEV 77개와 정확히 1:1이고 query_cores도 Method 2 runtime 값과 전수 일치했다.",
        "- Latin→KO core_id는 `SHA256(latin_core)[:16]`과 전수 일치했고, 2,450 Latin core 집합은 Method 2 candidate unique core 집합과 정확히 같다. 2,570 candidate ID 모두 exact core로 연결됐다.",
        "- 기존 Method 2 results 231행, metrics 전체, candidate representations 2,570행을 재실행 결과와 전수 비교했다.",
        "- 실행 중 모든 입력 hash가 불변임을 종료 직전에 다시 확인했다.",
        "",
        "### 실행 시간 (wall-clock seconds)",
        "",
        "```json",
        json.dumps(times, ensure_ascii=False, indent=2),
        "```",
        f"- Python {platform.python_version()}, Unicode database {unicodedata.unidata_version}, pandas {importlib.metadata.version('pandas')}, uroman {importlib.metadata.version('uroman')}.",
        f"- 실행: `venv/Scripts/python.exe {Path(__file__).name}`",
        "",
        "### 입력 SHA-256",
        "",
    ]
    lines += [f"- `{path.relative_to(ROOT)}`: `{value}`" for path, value in hashes.items()]
    lines += ["", "### 생성 파일", ""]
    lines += [f"- `{path.relative_to(ROOT)}`" for path in generated]
    (OUT / f"{PREFIX}_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    baseline.verify_snapshot()  # 재현 게이트의 기준 스냅샷 고정 (9a-4)
    baseline.use_llm_channel(None)  # 기록값은 LLM 채널 도입 전 측정본이다 (9c)
    baseline.use_verification(False)  # 기록값은 Verification 도입 전 측정본이다 (10b)
    started = time.perf_counter()
    settings_path = OUT / f"{PREFIX}_settings.json"
    if settings_path.exists():
        assert json.loads(settings_path.read_text(encoding="utf-8")) == SETTINGS, "Frozen settings differ"
    else:
        dump(settings_path, SETTINGS)

    input_paths = [
        baseline.GOLD_PATH,
        baseline.COMMERCIAL_PATH,
        baseline.PERFUMES_PATH,
        baseline.MEMBERS_PATH,
        baseline.FAMILIES_PATH,
        baseline.RESULTS_PATH,
        baseline.REPORT_PATH,
        METHOD2_RESULTS_PATH,
        METHOD2_METRICS_PATH,
        METHOD2_CANDIDATES_PATH,
        OUT / "fragrantica_method2_dev_report.md",
        OUT / "fragrantica_method2_dev_settings.json",
        KO_LATIN_PATH,
        LATIN_KO_PATH,
        ROOT / "src" / "korea" / "build_korea_popularity_map.py",
        ROOT / "src" / "matching" / "evaluate_fragrantica_matcher_dev.py",
        ROOT / "src" / "matching" / "evaluate_fragrantica_method1_dev.py",
        ROOT / "src" / "matching" / "evaluate_fragrantica_method2_dev.py",
        Path(__file__).resolve(),
        settings_path,
    ]
    input_paths += sorted((ROOT / "cache/method2").glob("transliterations_*.json"))
    assert all(path.is_file() for path in input_paths)
    hashes = {path: matcher.sha256(path) for path in input_paths}

    gold = pd.read_csv(baseline.GOLD_PATH, keep_default_na=False)
    assert len(gold) == 80 and gold.split.eq("DEV").all()
    eligible = gold[baseline.as_bool(gold.evaluation_eligible)].copy()
    assert len(eligible) == 77 and eligible.gold_status.value_counts().to_dict() == {"MATCH": 61, "NO_MATCH": 16}
    commercial = pd.read_csv(baseline.COMMERCIAL_PATH, keep_default_na=False).set_index("commercial_identity_id", drop=False)
    members = pd.read_csv(baseline.MEMBERS_PATH, keep_default_na=False)
    perfumes = pd.read_csv(baseline.PERFUMES_PATH, usecols=["id", "name", "brand", "description"], keep_default_na=False)
    assert perfumes.id.is_unique and commercial.index.is_unique

    stage = time.perf_counter()
    inputs, rankings, method2_candidates, method2_times = method2.prepare_rankings(
        commercial, members, perfumes, eligible.commercial_identity_id
    )
    fresh_method2_results = method2.evaluate(eligible, inputs, rankings, method2_candidates, perfumes)
    fresh_method2_metrics = method2.measure(fresh_method2_results)
    assert_frame_reproduced(
        fresh_method2_results,
        pd.read_csv(METHOD2_RESULTS_PATH, keep_default_na=False),
        ["queue_id", "method"],
    )
    assert_frame_reproduced(
        fresh_method2_metrics,
        pd.read_csv(METHOD2_METRICS_PATH, keep_default_na=False),
        ["scope", "method", "level", "group"],
    )
    assert_frame_reproduced(
        method2_candidates,
        pd.read_csv(METHOD2_CANDIDATES_PATH, keep_default_na=False),
        ["fragrantica_id"],
    )
    method2_reproduction_seconds = time.perf_counter() - stage

    ko_latin, latin_ko, validation = load_and_validate_llm_inputs(
        eligible.commercial_identity_id.tolist(), inputs, method2_candidates
    )
    candidates, llm_ranking_seconds = add_llm_rankings(
        eligible.commercial_identity_id.tolist(), inputs, rankings, method2_candidates, ko_latin, latin_ko
    )
    evaluation_started = time.perf_counter()
    results = evaluate(eligible, inputs, rankings, candidates, perfumes)
    metrics = measure(results)
    status_metrics = status_measure(results)
    directions = pd.concat([
        direction_comparison(results, "ALL_GOLD_MATCH"),
        direction_comparison(results, "CATALOG_RETRIEVABLE"),
    ], ignore_index=True)
    evaluation_seconds = time.perf_counter() - evaluation_started

    assert len(results) == 77 * len(METHODS)
    assert results.groupby("commercial_identity_id").candidate_count.nunique().eq(1).all()
    method2_subset = results[results.method.isin(method2.METHODS)]
    assert method2_subset[["commercial_identity_id", "method", "top10_ids"]].reset_index(drop=True).equals(
        fresh_method2_results[["commercial_identity_id", "method", "top10_ids"]].reset_index(drop=True)
    )
    overall = metrics[(metrics.scope.eq("ALL_GOLD_MATCH")) & metrics.level.eq("OVERALL")].set_index("method")
    base_row = overall.loc["baseline_lexical"]
    assert [round(base_row[f"recall_at_{k}"], 4) for k in (1, 3, 5, 10)] == [0.3115, 0.5082, 0.5902, 0.6721]
    assert round(base_row.mrr, 4) == 0.4451
    assert len(overall) == 5

    results_path = OUT / f"{PREFIX}_results.csv"
    metrics_path = OUT / f"{PREFIX}_metrics.csv"
    status_path = OUT / f"{PREFIX}_llm_status_metrics.csv"
    directions_path = OUT / f"{PREFIX}_llm_direction_comparison.csv"
    candidates_path = OUT / f"{PREFIX}_candidate_representations.csv"
    report_path = OUT / f"{PREFIX}_report.md"
    generated = [settings_path, results_path, metrics_path, status_path, directions_path, candidates_path, report_path]
    results.to_csv(results_path, index=False, encoding="utf-8-sig")
    metrics.to_csv(metrics_path, index=False, encoding="utf-8-sig")
    status_metrics.to_csv(status_path, index=False, encoding="utf-8-sig")
    directions.to_csv(directions_path, index=False, encoding="utf-8-sig")
    candidates.to_csv(candidates_path, index=False, encoding="utf-8-sig")
    times = {
        "method2_reproduction_seconds": method2_reproduction_seconds,
        "method2_internal": method2_times,
        "llm_validation_and_ranking_seconds": llm_ranking_seconds,
        "evaluation_and_metrics_seconds": evaluation_seconds,
        "total_before_report_seconds": time.perf_counter() - started,
    }
    assert all(matcher.sha256(path) == value for path, value in hashes.items())
    write_report(results, metrics, status_metrics, candidates, directions, times, hashes, validation, generated)
    assert all(path.is_file() for path in generated)
    assert all(matcher.sha256(path) == value for path, value in hashes.items())
    print(metrics[metrics.level.eq("OVERALL")].to_string(index=False), flush=True)
    print("\nLLM direction comparison\n" + directions.to_string(index=False), flush=True)
    print("\nLLM status metrics\n" + status_metrics.to_string(index=False), flush=True)


if __name__ == "__main__":
    main()

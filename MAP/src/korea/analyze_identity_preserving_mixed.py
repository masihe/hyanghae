"""Re-review only the five Personal Fragrance MIXED-option rows.

Run: venv/Scripts/python.exe -B analyze_identity_preserving_mixed.py
Python 3.11, standard library only. Prior results remain read-only.
"""
import csv
import hashlib
import unicodedata
import re
from collections import Counter
from pathlib import Path


MAP_DIR = Path(__file__).resolve().parents[2]  # MAP/
DATA = MAP_DIR / "data" / "korea_popularity"

SCOPE_REVIEW = DATA / "korea_non_perfume_personal_fragrance_review.csv"
BASE_CANDIDATES = DATA / "korea_personal_fragrance_purchase_candidates.csv"
BASE_OVERLAP = DATA / "hwahae_personal_fragrance_overlap.csv"
HWAHAE_RAW = DATA / "hwahae_perfume_top100_raw.csv"
BASE_REPORT = DATA / "korea_personal_fragrance_scope_overlap.md"

MIXED_REVIEW = DATA / "korea_personal_fragrance_mixed_identity_review.csv"
PURCHASE_CANDIDATES = DATA / "korea_personal_fragrance_mixed_purchase_candidates.csv"
OVERLAP = DATA / "hwahae_personal_fragrance_mixed_overlap.csv"
REPORT = DATA / "korea_personal_fragrance_mixed_scope_overlap.md"

EXPECTED_HASHES = {
    SCOPE_REVIEW: "e81bf425b096a221b014b02db43f0064dfb5c68bce594fe087313b27f224071b",
    BASE_CANDIDATES: "97b5bf6db8fc327db126957d0cfdbfd9e9bb5abdb56b08b9873c3c695d76b292",
    BASE_OVERLAP: "ebdf037f10e320159477fe6d39a50d0a1dd156fb9528b7830d5708ba2d33f1c7",
    HWAHAE_RAW: "7fc5930d5fb54d912de0c24bbb7ac989c1e20b9efa865929905ce656eadb65cc",
    BASE_REPORT: "2849dbbee18237ba8dd9d4eef479e604496acdb3029edfdcc518a5ae32d35957",
}

# Snapshot-specific decisions for the five rows that the preceding analysis
# excluded only because their option type was MIXED.
MIXED_DECISIONS = {
    ("oliveyoung", "21"): (
        "IDENTITY_CHANGING",
        "multiple_scents_and_sizes",
        "헤어&바디 퍼퓸 미스트 6종과 100ml/236ml 선택이 함께 있어 향수 정체성이 달라질 수 있다.",
    ),
    ("oliveyoung", "28"): (
        "IDENTITY_CHANGING",
        "multiple_scents_and_package",
        "헤어 퍼퓸 3종 택1과 단품/기획 선택이 함께 있어 향수 정체성이 달라질 수 있다.",
    ),
    ("oliveyoung", "75"): (
        "IDENTITY_PRESERVING",
        "single_identity_size_and_package",
        "파파야 파라다이스 한 향수에서 88ml/236ml 및 단품/기획 구성만 달라진다.",
    ),
    ("oliveyoung", "118"): (
        "IDENTITY_CHANGING",
        "multiple_scents_and_package",
        "헤어 우유 퍼퓸 5종 택1과 단품/기획 선택이 함께 있어 향수 정체성이 달라질 수 있다.",
    ),
    ("oliveyoung", "217"): (
        "IDENTITY_PRESERVING",
        "single_identity_size_and_package",
        "로즈올데이 한 향수에서 88ml/236ml 및 단품/기획 구성만 달라진다.",
    ),
}


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        return reader.fieldnames, list(reader)


def write_csv(path, fieldnames, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    saved_fields, saved_rows = read_csv(path)
    if saved_fields != fieldnames or saved_rows != rows:
        raise ValueError(f"CSV round-trip mismatch: {path.name}")


def normalize_brand(text):
    text = unicodedata.normalize("NFKC", text).lower()
    value = re.sub(r"[^0-9a-z가-힣]+", "", text)
    return {"clean": "클린"}.get(value, value)


def build_mixed_review(scope_rows):
    mixed = [r for r in scope_rows if r["candidate_decision"] == "EXCLUDE_MIXED_OPTION"]
    keys = {(r["source"], r["source_rank"]) for r in mixed}
    if len(mixed) != 5 or keys != set(MIXED_DECISIONS):
        raise ValueError("The preceding MIXED set is not the expected five-row snapshot")

    results = []
    for row in mixed:
        status, rule, reason = MIXED_DECISIONS[(row["source"], row["source_rank"])]
        results.append(dict(
            row,
            mixed_identity_status=status,
            mixed_identity_rule=rule,
            mixed_identity_reason=reason,
            mixed_candidate_decision=(
                "RETURN_TO_CANDIDATES" if status == "IDENTITY_PRESERVING" else "KEEP_EXCLUDED"
            ),
        ))
    return results


def build_candidates(base_fields, base_rows, mixed_rows):
    results = [dict(row) for row in base_rows]
    for row in mixed_rows:
        if row["mixed_candidate_decision"] != "RETURN_TO_CANDIDATES":
            continue
        candidate = {field: row.get(field, "") for field in base_fields}
        candidate.update(
            personal_fragrance_candidate_status="KEEP",
            candidate_basis="identity_preserving_MIXED_return",
            previous_effective_basis=row["previous_effective_basis"],
            scope_review_ref=f"{row['source']}:{row['source_rank']}",
        )
        results.append(candidate)

    source_order = {source: index for index, source in enumerate(dict.fromkeys(r["source"] for r in base_rows))}
    results.sort(key=lambda r: (source_order[r["source"]], int(r["source_rank"])))
    return results


def build_overlap(base_fields, base_rows, candidates):
    candidate_by_ref = {(r["source"], r["source_rank"]): r for r in candidates}
    results = []
    for old in base_rows:
        row = dict(old)
        row["mixed_update_previous_status"] = old["overlap_status"]
        row["mixed_update_change"] = "UNCHANGED"
        ref = (old["matched_purchase_source"], old["matched_purchase_source_rank"])
        row["matched_candidate_basis_after_mixed"] = (
            candidate_by_ref[ref]["candidate_basis"] if ref in candidate_by_ref else ""
        )
        results.append(row)

    expected_fields = base_fields + [
        "mixed_update_previous_status", "mixed_update_change", "matched_candidate_basis_after_mixed"
    ]
    if list(results[0]) != expected_fields:
        raise ValueError("Unexpected overlap field order")
    return results


def validate_outputs(scope_fields, scope_rows, mixed_rows, base_candidate_rows, candidates,
                     hwahae_rows, base_overlap_fields, base_overlap_rows, overlap):
    if len(mixed_rows) != 5:
        raise ValueError("MIXED review must contain exactly five rows")
    if Counter(r["mixed_identity_status"] for r in mixed_rows) != Counter(
        {"IDENTITY_PRESERVING": 2, "IDENTITY_CHANGING": 3}
    ):
        raise ValueError("Unexpected identity-preserving/changing split")
    if any(field not in mixed_rows[0] for field in scope_fields):
        raise ValueError("MIXED review did not preserve preceding review columns")
    scope_by_key = {(r["source"], r["source_rank"]): r for r in scope_rows}
    if any(
        {field: row[field] for field in scope_fields}
        != scope_by_key[(row["source"], row["source_rank"])]
        for row in mixed_rows
    ):
        raise ValueError("MIXED review changed a value from the preceding review")

    base_keys = {(r["source"], r["source_rank"]) for r in base_candidate_rows}
    candidate_keys = {(r["source"], r["source_rank"]) for r in candidates}
    restored_keys = candidate_keys - base_keys
    expected_restored = {("oliveyoung", "75"), ("oliveyoung", "217")}
    if len(base_candidate_rows) != 826 or len(candidates) != 828:
        raise ValueError("Purchase candidates must change from 826 to 828")
    if not base_keys.issubset(candidate_keys) or restored_keys != expected_restored:
        raise ValueError("Candidate update did not preserve the baseline and add exactly two rows")
    if len(candidate_keys) != len(candidates):
        raise ValueError("Updated candidates contain duplicate source/rank keys")
    if len({(r["source"], r["source_product_id"]) for r in candidates}) != len(candidates):
        raise ValueError("Updated candidates contain duplicate source product IDs")
    for row in candidates:
        if (row["source"], row["source_rank"]) in expected_restored:
            if row["candidate_basis"] != "identity_preserving_MIXED_return":
                raise ValueError("Restored MIXED row has an unexpected candidate basis")

    if len(hwahae_rows) != 100 or [int(r["source_rank"]) for r in hwahae_rows] != list(range(1, 101)):
        raise ValueError("Hwahae input must retain 100 continuous ranks")
    if len({r["source_product_id"] for r in hwahae_rows}) != 100:
        raise ValueError("Hwahae source product IDs must be unique")
    if len(overlap) != 100 or Counter(r["overlap_status"] for r in overlap) != Counter(
        {"MATCH": 30, "NO_MATCH": 68, "MATCH_REVIEW": 2}
    ):
        raise ValueError("Unexpected updated overlap totals")
    if [{field: row[field] for field in base_overlap_fields} for row in overlap] != base_overlap_rows:
        raise ValueError("The conservative overlap result changed unexpectedly")
    if any(r["mixed_update_change"] != "UNCHANGED" for r in overlap):
        raise ValueError("Unexpected overlap status change")

    candidate_by_ref = {(r["source"], r["source_rank"]): r for r in candidates}
    for row in overlap:
        ref = (row["matched_purchase_source"], row["matched_purchase_source_rank"])
        if row["overlap_status"] == "NO_MATCH":
            if any(ref):
                raise ValueError("NO_MATCH contains a purchase reference")
            continue
        if ref not in candidate_by_ref:
            raise ValueError(f"Overlap reference is absent from updated candidates: {ref}")
        if row["matched_purchase_product_id"] != candidate_by_ref[ref]["source_product_id"]:
            raise ValueError(f"Overlap product ID differs from referenced candidate: {ref}")

    restored = [r for r in candidates if r["candidate_basis"] == "identity_preserving_MIXED_return"]
    same_brand_pairs = {
        (p["source"], int(p["source_rank"]), int(h["source_rank"]))
        for p in restored for h in hwahae_rows
        if normalize_brand(p["brand_raw"]) == normalize_brand(h["brand_raw"])
    }
    expected_pairs = {
        ("oliveyoung", 75, 62), ("oliveyoung", 75, 88),
        ("oliveyoung", 217, 62), ("oliveyoung", 217, 88),
    }
    if same_brand_pairs != expected_pairs:
        raise ValueError("Restored-row same-brand Hwahae review coverage changed")
    if any(r["matched_candidate_basis_after_mixed"] == "identity_preserving_MIXED_return" for r in overlap):
        raise ValueError("A restored MIXED row was unexpectedly matched")


def write_report(mixed_rows, base_candidates, candidates, base_overlap, overlap, hashes):
    identity_counts = Counter(r["mixed_identity_status"] for r in mixed_rows)
    old_counts = Counter(r["overlap_status"] for r in base_overlap)
    new_counts = Counter(r["overlap_status"] for r in overlap)
    new_matches = [
        r for r in overlap
        if r["overlap_status"] == "MATCH" and r["mixed_update_previous_status"] != "MATCH"
    ]
    lines = [
        "# identity-preserving MIXED 재검토와 화해 overlap", "",
        "최근 Personal Fragrance 재검토에서 `EXCLUDE_MIXED_OPTION`이었던 5행만 frozen 상품명과 기존 옵션 판정 근거로 다시 확인했다. 외부 데이터 수집, SKU 통합, Fragrantica 매칭, 최종 Top200 선정은 하지 않았다.", "",
        "## MIXED 5행 판정", "",
        "| 구매 행 | 브랜드 | 상품 | MIXED 판정 | 후보 처리 | 근거 |",
        "|---|---|---|---|---|---|",
    ]
    for row in mixed_rows:
        lines.append(
            f"| `{row['source']}:{row['source_rank']}` | {row['brand_raw']} | {row['product_name_raw']} | "
            f"{row['mixed_identity_status']} | {row['mixed_candidate_decision']} | {row['mixed_identity_reason']} |"
        )
    lines.extend([
        "",
        f"identity-preserving은 **{identity_counts['IDENTITY_PRESERVING']}건**, identity-changing은 **{identity_counts['IDENTITY_CHANGING']}건**이다. identity-preserving 2건만 구매 후보로 복귀했다.", "",
        "## 구매 후보 변화", "",
        f"구매 후보는 **{len(base_candidates)}행에서 {len(candidates)}행으로 {len(candidates) - len(base_candidates)}행 증가**했다. 새 복귀 상품은 클린 헤어&바디 퍼퓸 미스트 `파파야 파라다이스`와 `로즈올데이`다. 이 수치는 SKU 통합 전 판매상품 행 수다.", "",
        "## 화해 TOP100 overlap", "",
        "| 상태 | 변경 전 | 변경 후 | 변화 |",
        "|---|---:|---:|---:|",
        f"| MATCH | {old_counts['MATCH']} | {new_counts['MATCH']} | {new_counts['MATCH'] - old_counts['MATCH']:+d} |",
        f"| NO_MATCH | {old_counts['NO_MATCH']} | {new_counts['NO_MATCH']} | {new_counts['NO_MATCH'] - old_counts['NO_MATCH']:+d} |",
        f"| MATCH_REVIEW | {old_counts['MATCH_REVIEW']} | {new_counts['MATCH_REVIEW']} | {new_counts['MATCH_REVIEW'] - old_counts['MATCH_REVIEW']:+d} |",
        f"| MATCH 비율 | {old_counts['MATCH'] / len(base_overlap):.1%} | {new_counts['MATCH'] / len(overlap):.1%} | {(new_counts['MATCH'] / len(overlap) - old_counts['MATCH'] / len(base_overlap)) * 100:+.1f}%p |", "",
        f"이번 수정으로 새롭게 MATCH된 화해 상품은 **{len(new_matches)}건**이다. 복귀한 두 상품과 화해의 클린 상품(62위 퓨어솝, 88위 쿨코튼)은 브랜드만 같고 향수 정체성이 달라 연결하지 않았다.", "",
        "## 검증", "",
        "- 실행: `venv/Scripts/python.exe -B analyze_identity_preserving_mixed.py`.",
        "- 이전 MIXED 집합이 정확히 5행이며 2/3으로 빠짐없이 분류되는지 검사했다.",
        "- 기존 구매 후보 826행을 모두 보존하고 지정한 2행만 추가해 828행인지 검사했다.",
        "- 화해 입력 100행과 1~100위 연속성, source_product_id 고유성을 검사했다.",
        "- MATCH/NO_MATCH/MATCH_REVIEW 합계가 100이며 30/68/2인지 검사했다.",
        "- 모든 MATCH와 MATCH_REVIEW가 갱신 후보의 실제 source/rank와 product_id를 참조하는지 검사했다.",
        "- 기존 overlap 컬럼과 상태가 모두 그대로인지, 새 복귀 행이 약한 근거로 연결되지 않았는지 검사했다.",
        "- 세 CSV round-trip과 입력·이전 결과 파일의 실행 전후 바이트 불변을 검사했다.", "",
        "보호 입력 SHA-256:", "",
    ])
    for path, digest in hashes.items():
        lines.append(f"- `{path.name}`: `{digest}`")
    lines.extend([
        "", "## 남은 문제", "",
        "- identity-changing 3행은 여러 향 선택이 포함되어 계속 제외한다.",
        "- 이번 5행에는 추가 unresolved가 없다.",
        "- 이전 Personal Fragrance 검토의 UNRESOLVED 6행, UNKNOWN 옵션 4행과 기존 MANUAL_CHECK는 이번 범위에서 손대지 않았다.",
        "- 향수 SKU 통합과 외부 정체성 매칭은 다음 단계 전까지 보류한다.", "",
    ])
    REPORT.write_text("\n".join(lines), encoding="utf-8")


def main():
    protected = {path: path.read_bytes() for path in EXPECTED_HASHES}
    hashes = {path: hashlib.sha256(data).hexdigest() for path, data in protected.items()}
    for path, expected in EXPECTED_HASHES.items():
        if hashes[path] != expected:
            raise ValueError(f"Snapshot or prior result changed; re-review required: {path.name}")

    scope_fields, scope_rows = read_csv(SCOPE_REVIEW)
    candidate_fields, base_candidates = read_csv(BASE_CANDIDATES)
    overlap_fields, base_overlap = read_csv(BASE_OVERLAP)
    _, hwahae_rows = read_csv(HWAHAE_RAW)

    mixed_rows = build_mixed_review(scope_rows)
    candidates = build_candidates(candidate_fields, base_candidates, mixed_rows)
    overlap = build_overlap(overlap_fields, base_overlap, candidates)
    validate_outputs(
        scope_fields, scope_rows, mixed_rows, base_candidates, candidates,
        hwahae_rows, overlap_fields, base_overlap, overlap,
    )

    mixed_fields = scope_fields + [
        "mixed_identity_status", "mixed_identity_rule", "mixed_identity_reason",
        "mixed_candidate_decision",
    ]
    updated_overlap_fields = overlap_fields + [
        "mixed_update_previous_status", "mixed_update_change", "matched_candidate_basis_after_mixed",
    ]
    write_csv(MIXED_REVIEW, mixed_fields, mixed_rows)
    write_csv(PURCHASE_CANDIDATES, candidate_fields, candidates)
    write_csv(OVERLAP, updated_overlap_fields, overlap)
    write_report(mixed_rows, base_candidates, candidates, base_overlap, overlap, hashes)

    if any(path.read_bytes() != data for path, data in protected.items()):
        raise ValueError("An input or prior result changed during processing")

    print("mixed_identity", dict(Counter(r["mixed_identity_status"] for r in mixed_rows)))
    print(f"purchase_candidates {len(base_candidates)} -> {len(candidates)} (+{len(candidates) - len(base_candidates)})")
    print("overlap", dict(Counter(r["overlap_status"] for r in overlap)))
    print("new_matches_from_mixed_update", sum(
        r["overlap_status"] == "MATCH" and r["mixed_update_previous_status"] != "MATCH"
        for r in overlap
    ))
    print("PASS: scope, counts, provenance, references, conservative identity review, hashes, and CSV round trips")
    for path in (MIXED_REVIEW, PURCHASE_CANDIDATES, OVERLAP, REPORT):
        print(path)


if __name__ == "__main__":
    main()

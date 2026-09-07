"""Resolve only first-pass REVIEW rows in the frozen 2026-09-05 snapshot.

Run: venv/Scripts/python.exe -B review_korea_rankings.py
No network calls, row deletion, SKU merging, or source-file edits.
"""
import csv
import hashlib
from collections import Counter

from analyze_korea_rankings import AUDIT, DATA, RAW, RAW_SHA256, SOURCES

FIRST_PASS = DATA / "korea_perfume_ranking_first_pass.csv"
FIRST_PASS_REPORT = DATA / "korea_perfume_ranking_first_pass.md"
OUTPUT = DATA / "korea_perfume_ranking_second_pass_review.csv"
QUEUE = DATA / "korea_perfume_manual_check_queue.csv"
REPORT = DATA / "korea_perfume_ranking_second_pass.md"

EXPECTED_HASHES = {
    RAW: RAW_SHA256,
    AUDIT: "b6ba913938b9fb65fd68759a79308c2d3c2c6232d321b102b27231d0e8c07e15",
    FIRST_PASS: "0775e32f757b42f832a5ac858e7b0aecc020ba5e40f5a0ae8ea33b306dbe10fd",
    FIRST_PASS_REPORT: "57931ca4021ac66c7df82452661c41cdce19217365c4bfd913ad54c629450db9",
}
SECOND_STATUSES = (
    "KEEP", "EXCLUDE_NON_PERFUME", "EXCLUDE_DISCOVERY",
    "EXCLUDE_SCENT_OPTION", "MANUAL_CHECK",
)

# Snapshot-specific decisions after reading each title. Lists are keyed by the
# immutable source rank and are enabled only when every input hash matches.
DECISIONS = []


def decide(source, ranks, status, basis, reason, local_refs=""):
    DECISIONS.append((source, ranks, status, basis, reason, local_refs))


# Same named perfume across size/package choices. Every selectable item keeps
# one fragrance identity and concentration, so the sales row can remain.
decide("oliveyoung", [9,17,36,37,40,48,49,93,99,104,125,163,206,227,238,242,270,277], "KEEP",
       "same_identity_size_package",
       "상품명에 하나의 향수명이 있고 선택지는 용량과 단품/기획 구성뿐이다. 농도와 단위 원문은 고치지 않는다.")

# Mixed listings whose ranked row represents multiple fragrance identities.
decide("musinsa", [199,325], "EXCLUDE_SCENT_OPTION", "mixed_contains_scent_selection",
       "용량/농도 옵션도 있지만 한 판매순위에 여러 향수 선택이 포함되어 개별 향수 순위로 배분할 수 없다.")
decide("oliveyoung", [2,10,38,43,47,74,136,147,157,171,192,201,269,285,322],
       "EXCLUDE_SCENT_OPTION", "mixed_contains_scent_selection",
       "구성 또는 용량과 함께 서로 다른 향수/향 선택이 포함되어 개별 향수 순위로 배분할 수 없다.")

# All selectable main products are outside the agreed liquid-perfume scope.
decide("oliveyoung", [21,28,75,118,217], "EXCLUDE_NON_PERFUME", "mixed_but_all_non_perfume",
       "용량/구성/향 선택이 섞였지만 모든 주상품이 헤어·바디 향 제품이므로 서비스 범위 밖임은 명확하다.")
decide("musinsa", [46,66,250], "EXCLUDE_NON_PERFUME", "unknown_option_but_all_non_perfume",
       "옵션의 세부 유형과 무관하게 주상품이 고체향수·이너퍼퓸·바디스프레이로 명확하다.")
decide("oliveyoung", [143,291], "EXCLUDE_NON_PERFUME", "unknown_option_but_all_non_perfume",
       "옵션의 세부 유형과 무관하게 주상품이 헤어퍼퓸으로 명확하다.")

# A single stated volume and N variants without set/pack/multiplication wording
# is sufficient local evidence for a multi-scent ranked listing.
decide("musinsa", [2,4,249,327], "EXCLUDE_SCENT_OPTION", "single_size_multiple_scent_variants",
       "한 용량의 향수 N종을 한 판매상품으로 제시하며 세트/다개입 표기가 없어 서로 다른 향 선택 상품으로 판정했다.")
decide("oliveyoung", [8,19,57,214,248,253,301,324], "EXCLUDE_SCENT_OPTION",
       "single_size_multiple_scent_variants",
       "한 용량의 향수 N종을 한 판매상품으로 제시하며 세트/다개입 표기가 없어 서로 다른 향 선택 상품으로 판정했다.")
decide("oliveyoung", [160], "EXCLUDE_SCENT_OPTION", "cross_source_scent_option",
       "같은 KEYTH 50ml 상품이 무신사 270위에서 5종 택1로 확인되어 향 선택 상품으로 판정했다.",
       "musinsa:270")

# The typo changes size notation, not the named perfume or its option meaning.
decide("oliveyoung", [67], "KEEP", "single_identity_size_typo",
       "지미추 아이 원 추 EDP라는 단일 정체성과 40m/60ml 두 용량이 명확하다. 40m은 보정하지 않고 원문으로 유지한다.")
decide("lotte", [31], "KEEP", "single_identity_unit_typo",
       "그랑크뤼 아쌈 오브 인디아 EDP라는 향수 정체성은 명확하다. 100m은 보정하지 않고 원문으로 유지한다.")
decide("lotte", [34,188], "KEEP", "single_identity_unmapped_concentration",
       "인텐스 세드라 부아제라는 향수 정체성은 두 로컬 행에서 동일하다. EXDP 의미는 추정하지 않고 농도 원문을 유지한다.",
       "lotte:34;lotte:188")

# Local cross-source evidence supplies the missing product-type expression.
decide("musinsa", [189], "KEEP", "cross_source_product_type",
       "같은 브랜드·근사 동일 상품명이 올리브영에서 퍼퓸 30ml로 확인된다. 철자 차이는 원문 그대로 둔다.",
       "oliveyoung:56")
decide("musinsa", [200], "KEEP", "cross_source_product_type",
       "같은 브랜드·상품명·30ml가 올리브영에서 퍼퓸으로 확인된다.", "oliveyoung:29")
decide("musinsa", [345], "KEEP", "cross_source_product_type",
       "같은 브랜드·상품명·50ml가 올리브영에서 EDT로 확인된다.", "oliveyoung:193")
decide("oliveyoung", [177,186,286], "KEEP", "cross_source_product_type",
       "같은 베르사체 맨 오 프레쉬 상품이 로컬 롯데 행에서 EDT/오드뚜왈렛으로 확인된다.",
       "lotte:15;lotte:107;lotte:108;lotte:135;lotte:150;lotte:296")


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return reader.fieldnames, list(reader)


def manual_text(row):
    rule = row["cleaning_rule"]
    if rule in ("mixed_product_types", "option_mixed"):
        return (
            "일반 액상 향수와 다른 제품/옵션의 대응 관계가 상품명만으로 분리되지 않는다.",
            "선택 가능한 모든 옵션과 각 옵션의 제품 유형·향수명을 확인하고, 판매순위를 개별 액상 향수에 귀속할 근거가 있는가?",
        )
    if rule == "option_unknown":
        return (
            "택1/N종/묶음 표기는 있으나 향·용량·구성 중 무엇을 선택하는지 확정할 수 없다.",
            "상세 옵션명이 향, 용량, 단품/기획 중 무엇이며 모든 옵션에서 동일한 향수 정체성이 유지되는가?",
        )
    if rule == "identity_unclear":
        return (
            "상품명에 개별 향수명 또는 판매 옵션별 향수명이 부족하다.",
            "정확한 향수명과 농도는 무엇이며, 한 상품 ID에 서로 다른 향 선택이 포함되는가?",
        )
    if rule == "unclear_use":
        return (
            "퍼퓸 스프레이·멀티 프래그런스·미스트만으로 인체용 일반 향수인지 공간/섬유용인지 구별할 수 없다.",
            "사용 부위가 피부인가, 공간/섬유인가? 제품 제형이 일반 액상 향수에 해당하는가?",
        )
    if rule == "product_type_unconfirmed":
        return (
            "제품명과 용량만으로 일반 액상 향수임을 확인할 수 없고 같은 상품의 로컬 보강 근거도 없다.",
            "상품 유형과 사용 부위는 무엇이며 EDP/EDT/Parfum 등 일반 액상 향수인가?",
        )
    raise ValueError(f"No manual question for {rule}")


def build_decision_map(review_refs):
    decisions = {}
    for source, ranks, status, basis, reason, refs in DECISIONS:
        for rank in ranks:
            key = (source, rank)
            if key in decisions or key not in review_refs or status not in SECOND_STATUSES[:-1]:
                raise ValueError(f"Invalid or duplicate second-pass decision: {key}")
            decisions[key] = (status, basis, reason, refs)
    return decisions


def validate(first_fields, review_input, results, queue):
    if len(review_input) != 128 or len(results) != 128:
        raise ValueError("Expected exactly 128 first-pass REVIEW rows")
    if [{k: r[k] for k in first_fields} for r in results] != review_input:
        raise ValueError("First-pass provenance, values, or REVIEW order changed")
    if set(r["second_pass_status"] for r in results) - set(SECOND_STATUSES):
        raise ValueError("Invalid second-pass status")
    if sum(Counter(r["second_pass_status"] for r in results).values()) != 128:
        raise ValueError("Second-pass counts do not sum to 128")
    expected = Counter({"KEEP": 28, "EXCLUDE_NON_PERFUME": 10,
                        "EXCLUDE_DISCOVERY": 0, "EXCLUDE_SCENT_OPTION": 30,
                        "MANUAL_CHECK": 60})
    if Counter(r["second_pass_status"] for r in results) != expected:
        raise ValueError("Unexpected snapshot decision counts")
    manual = [r for r in results if r["second_pass_status"] == "MANUAL_CHECK"]
    if len(queue) != len(manual):
        raise ValueError("Manual queue does not match unresolved rows")
    if {(r["source"], r["source_rank"]) for r in queue} != {(r["source"], r["source_rank"]) for r in manual}:
        raise ValueError("Manual queue keys do not match unresolved rows")
    for r in results:
        if not r["second_pass_basis"] or not r["second_pass_reason"]:
            raise ValueError("Every second-pass decision needs explicit evidence")
    for r in queue:
        if not r["product_url"].startswith("http") or not r["manual_check_reason"] or not r["manual_check_question"]:
            raise ValueError("Manual queue needs URL, reason, and question")


def write_report(results, hashes):
    lines = [
        "# 국내 판매 랭킹 REVIEW 2차 검토", "",
        "1차 REVIEW 128건만 로컬 상품명·audit 근거·다른 로컬 판매행으로 재검토했다. 상품 페이지와 외부 API는 열지 않았다.",
        "2차 판정은 정제 기준 검증용이다. 원본/1차 판정 수정, 행 삭제, SKU 통합, 농도·단위 보정은 하지 않았다.", "",
        "## 결과", "",
        "| 2차 판정 | musinsa | oliveyoung | lotte | 전체 |", "|---|---:|---:|---:|---:|",
    ]
    for status in SECOND_STATUSES:
        counts = [sum(r["second_pass_status"] == status and r["source"] == s for r in results) for s in SOURCES]
        lines.append("| " + " | ".join([status, *map(str, counts), str(sum(counts))]) + " |")
    lines.extend(["| 합계 | 53 | 72 | 3 | 128 |", "",
                  f"자동 재판정 {sum(r['second_pass_status'] != 'MANUAL_CHECK' for r in results)}건, MANUAL_CHECK {sum(r['second_pass_status'] == 'MANUAL_CHECK' for r in results)}건이다.", "",
                  "1차 확정 871건과 합치면 현재 전체 999건은 KEEP 790, EXCLUDE_NON_PERFUME 69, EXCLUDE_DISCOVERY 8, EXCLUDE_SCENT_OPTION 72, MANUAL_CHECK 60이다. 이는 행 기준이며 고유 향수 수가 아니다.", "",
                  "## 기존 REVIEW 사유별 변화", "",
                  "| 기존 cleaning_rule | 입력 | KEEP | 비향수 제외 | discovery 제외 | 향 선택 제외 | MANUAL_CHECK |",
                  "|---|---:|---:|---:|---:|---:|---:|"])
    rules = sorted({r["cleaning_rule"] for r in results})
    for rule in rules:
        subset = [r for r in results if r["cleaning_rule"] == rule]
        counts = [sum(r["second_pass_status"] == s for r in subset) for s in SECOND_STATUSES]
        lines.append("| " + " | ".join([rule, str(len(subset)), *map(str, counts)]) + " |")
    lines.extend(["", "## 재판정 근거", "",
                  "- SIZE+PACKAGE 18건은 상품명에 하나의 향수와 농도가 유지되고 용량·단품/기획만 달라 KEEP했다.",
                  "- 여러 향과 용량/구성이 한 판매행에 함께 있는 17건, 단일 용량의 N종 향수 12건, KEYTH 교차 확인 1건은 EXCLUDE_SCENT_OPTION으로 이동했다.",
                  "- 헤어·바디·고체·이너 제품 10건은 옵션 세부사항과 무관하게 모든 주상품이 서비스 범위 밖이어서 EXCLUDE_NON_PERFUME으로 이동했다.",
                  "- 상품 유형이 생략된 6건은 다른 로컬 행에서 같은 상품의 퍼퓸/EDT 표현을 확인해 KEEP했다.",
                  "- 100m/40m 및 EXDP는 값을 보정하지 않았다. 해당 4개 판매행은 개별 향수명이 명확해 정제 상태만 KEEP하고 원문을 유지했다.",
                  "- 1차 REVIEW 중 EXCLUDE_DISCOVERY로 새로 이동한 상품은 0건이다. discovery 주상품 8건은 이미 1차에서 제외됐다.", "",
                  "## MANUAL_CHECK 유형", "",
                  "| 유형 | 건수 | 사람이 확인할 핵심 질문 |", "|---|---:|---|"])
    manual = [r for r in results if r["second_pass_status"] == "MANUAL_CHECK"]
    for rule, count in sorted(Counter(r["cleaning_rule"] for r in manual).items()):
        sample = next(r for r in manual if r["cleaning_rule"] == rule)
        lines.append(f"| {rule} | {count} | {sample['manual_check_question']} |")
    lines.extend(["", "대표 사례:", ""])
    refs = [("oliveyoung",9), ("oliveyoung",40), ("oliveyoung",21), ("musinsa",2),
            ("oliveyoung",160), ("musinsa",189), ("lotte",31), ("lotte",34),
            ("oliveyoung",12), ("musinsa",31), ("musinsa",57), ("musinsa",67), ("musinsa",22)]
    by_ref = {(r["source"], int(r["source_rank"])): r for r in results}
    for ref in refs:
        r = by_ref[ref]
        lines.append(f"- **{r['source']}:{r['source_rank']} / {r['second_pass_status']}** "
                     f"(ID `{r['source_product_id']}`): {r['product_name_raw']} — {r['second_pass_reason']}")
    lines.extend(["", "## 검증", "",
                  "- 실행: `venv/Scripts/python.exe -B review_korea_rankings.py`.",
                  "- 입력 REVIEW=128, 자동 재판정+MANUAL_CHECK=128, 판매처 53/72/3을 검사한다.",
                  "- 결과 128행에 1차 CSV의 모든 값과 순서를 보존하고, manual queue의 URL·이유·질문을 검사한다.",
                  "- 입력 네 파일은 고정 SHA256과 처리 전후 바이트를 확인한다.", ""])
    for path, digest in hashes.items():
        lines.append(f"- `{path.name}` SHA256: `{digest}`")
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    protected = {path: path.read_bytes() for path in EXPECTED_HASHES}
    hashes = {path: hashlib.sha256(data).hexdigest() for path, data in protected.items()}
    for path, expected in EXPECTED_HASHES.items():
        if hashes[path] != expected:
            raise ValueError(f"Snapshot changed; re-review decisions: {path.name}")

    first_fields, first_rows = read_csv(FIRST_PASS)
    _, audit_rows = read_csv(AUDIT)
    review_input = [r for r in first_rows if r["cleaning_status"] == "REVIEW"]
    if len(review_input) != 128:
        raise ValueError(f"Expected 128 REVIEW rows, got {len(review_input)}")
    audit_by_ref = {(r["source"], r["source_rank"]): r for r in audit_rows}
    review_refs = {(r["source"], int(r["source_rank"])) for r in review_input}
    decisions = build_decision_map(review_refs)

    results = []
    queue = []
    for row in review_input:
        key = (row["source"], int(row["source_rank"]))
        if key in decisions:
            status, basis, reason, refs = decisions[key]
            manual_reason = manual_question = ""
        else:
            status, basis = "MANUAL_CHECK", "product_page_required"
            manual_reason, manual_question = manual_text(row)
            reason, refs = manual_reason, ""
        audit = audit_by_ref[(row["source"], row["source_rank"])]
        result = dict(row, second_pass_status=status, second_pass_basis=basis,
                      second_pass_reason=reason, local_evidence_refs=refs,
                      audit_evidence_json=audit["flag_evidence_json"],
                      manual_check_reason=manual_reason,
                      manual_check_question=manual_question)
        results.append(result)
        if status == "MANUAL_CHECK":
            queue.append({
                "source": row["source"], "source_rank": row["source_rank"],
                "source_product_id": row["source_product_id"],
                "product_name_raw": row["product_name_raw"], "product_url": row["product_url"],
                "first_pass_cleaning_rule": row["cleaning_rule"],
                "first_pass_option_type": row["option_type"],
                "manual_check_reason": manual_reason,
                "manual_check_question": manual_question,
            })

    validate(first_fields, review_input, results, queue)
    with OUTPUT.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0]))
        writer.writeheader(); writer.writerows(results)
    with QUEUE.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(queue[0]))
        writer.writeheader(); writer.writerows(queue)
    _, saved_results = read_csv(OUTPUT)
    _, saved_queue = read_csv(QUEUE)
    validate(first_fields, review_input, saved_results, saved_queue)
    if saved_results != results or saved_queue != queue:
        raise ValueError("CSV round trip changed output values")
    if any(path.read_bytes() != data for path, data in protected.items()):
        raise ValueError("An input file changed during processing")
    write_report(results, hashes)
    print("second_pass_status", dict(Counter(r["second_pass_status"] for r in results)))
    for source in SOURCES:
        print(source, dict(Counter(r["second_pass_status"] for r in results if r["source"] == source)))
    print("PASS: REVIEW 128; decisions 128; input hashes and first-pass provenance preserved")
    print(OUTPUT); print(QUEUE); print(REPORT)


if __name__ == "__main__":
    main()

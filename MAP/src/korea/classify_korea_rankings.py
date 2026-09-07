"""First-pass decisions for the frozen local snapshot; never delete/merge rows.

Run: venv/Scripts/python.exe -B classify_korea_rankings.py
Python 3.11, standard library only. Existing raw/audit remain read-only.
"""
import csv
import hashlib
import json
import re
from collections import Counter

from analyze_korea_rankings import AUDIT, DATA, RAW, RAW_SHA256, SOURCES

OUTPUT = DATA / "korea_perfume_ranking_first_pass.csv"
REPORT = DATA / "korea_perfume_ranking_first_pass.md"
AUDIT_SHA256 = "b6ba913938b9fb65fd68759a79308c2d3c2c6232d321b102b27231d0e8c07e15"
STATUSES = ("KEEP", "EXCLUDE_NON_PERFUME", "EXCLUDE_DISCOVERY", "EXCLUDE_SCENT_OPTION", "REVIEW")
OPTIONS = ("NONE", "SIZE", "PACKAGE", "SCENT", "MIXED", "UNKNOWN")

# Snapshot-specific title review, not reusable keyword rules. Ranks are safe
# only after checking BOTH input hashes. Raw names/IDs remain in every result.
# A single stated size + explicit N fragrances to choose is scent selection;
# N types alone or an unexplained 'select one' is insufficient.
OPTION_REVIEW = [
    ("musinsa", [9,26,41,61,65,77,81,137,144,166,270,346], "SCENT",
     "한 용량의 향수 N종 택1; 개별 향이 특정되지 않은 향수 선택 상품"),
    ("musinsa", [87], "SCENT", "샌달우드/블랙티앤피그/바질앤베티버의 서로 다른 향 나열"),
    ("musinsa", [279,311], "SCENT", "향 선택 가능 또는 향9종이라는 명시적 향 선택 문맥"),
    ("musinsa", [52,72,170,185,280], "SCENT", "한 용량/제형의 복수 향 제품 중 택1; 주상품은 모두 서비스 범위 밖"),
    ("musinsa", [199], "MIXED", "30ml/10ml 용량 선택과 18종 향수 선택이 함께 있음"),
    ("musinsa", [325], "MIXED", "EDP/EDT 농도와 4종 택2 선택이 섞여 있음"),
    ("musinsa", [80], "NONE", "고정 크림퍼퓸+틴트 세트; 2종은 틴트 구성으로 향수 선택 근거가 아님"),
    ("musinsa", [63,106], "UNKNOWN", "두 개 묶음이지만 같은 향인지 서로 다른 향 선택인지 미확인"),
    ("oliveyoung", [1,6,18,22,42,69,73,84,139,155,205,254,260,315,326], "SCENT",
     "동일 용량 또는 단일 향수 제형의 복수 향수 중 택1; 개별 향을 고를 수 없음"),
    ("oliveyoung", [13,35,151,168,204,212,213,216,294,320,331], "SCENT",
     "서로 다른 향/향수 이름 또는 여러 가지 향을 나열한 상품; 한 향의 용량 목록이 아님"),
    ("oliveyoung", [169], "SCENT", "얼그레이티/앰버 우드/머스크 향 오일퍼퓸 중 택1"),
    ("oliveyoung", [5,24,64,101,119,166,218,273,283,319], "SCENT",
     "한 용량/제형의 복수 향 제품 중 선택; 주상품은 모두 서비스 범위 밖"),
    ("oliveyoung", [2,43,118,136,147,157,192,269,285], "MIXED",
     "복수 향수 선택과 단품/기획 선택이 함께 있음"),
    ("oliveyoung", [10,21,74,201,322], "MIXED",
     "복수 향수/향과 서로 다른 용량 선택이 함께 있음"),
    ("oliveyoung", [28], "MIXED", "헤어퍼퓸 3종 택1과 단품/기획 구성 선택이 함께 있음"),
    ("oliveyoung", [11], "MIXED", "본품 향 목록과 단품/헤어오일 기획 구성 선택이 함께 있음"),
    ("oliveyoung", [12,15,16,46,77,255], "MIXED",
     "일반 향수와 헤어퍼퓸/미스트/고체/샤쉐 등 서로 다른 제품 유형이 함께 있음"),
    ("oliveyoung", [38,47,171], "MIXED", "서로 다른 향수와 농도 표현이 혼합된 목록"),
    ("oliveyoung", [7,312,343], "UNKNOWN", "용량은 나열됐지만 본품 향 이름 또는 옵션 대응이 불명확"),
    ("oliveyoung", [4], "UNKNOWN", "택1이지만 선택할 향/용량/구성 미표기; NEW/기획은 구성 선택 근거가 아님"),
    ("oliveyoung", [37,48,49,99,125,163,206,242,270,277], "MIXED",
     "서로 다른 용량과 특정 용량의 기획 구성 선택이 함께 있음"),
]

IDENTITY_REVIEW = {
    "musinsa": {
        38: "오 드 퍼퓸 25ml만 표기; 같은 브랜드 올리브영 6위는 15종 택1",
        50: "타투 퍼퓸만 표기; 같은 브랜드 올리브영 22위는 여러 향 선택",
        57: "오 드 퍼퓸 30ml만 표기되어 개별 향 미식별",
        104: "향기에 집중한 향수라는 일반 문구만 있고 개별 향 미식별",
        116: "오드퍼퓸 미니 향수만 표기되어 개별 향 미식별; sample로 단정하지 않음",
        127: "오드퍼퓸 50ml만 표기되어 개별 향 미식별",
        132: "오 드 퍼퓸 50ml만 표기되어 개별 향 미식별",
        165: "시그니처 퍼퓸만 표기; 같은 브랜드 125위에는 플레르 에끌로라는 향 이름 존재",
        220: "더 블룸 컬렉션만 표기되어 단일 향 또는 컬렉션 선택 여부 미확인",
        254: "시그니처 퍼퓸만 표기되어 개별 향 미식별",
        296: "향수 본품+핸드크림은 명확하지만 스테이퍼퓸의 향이 미식별; 137위는 5종 택1",
    },
    "oliveyoung": {
        26: "오드퍼퓸 롤온만 표기; 무신사 29/55위에는 서로 다른 향 이름 존재",
        94: "필로소피 EDT만 표기되어 개별 향 미식별",
        174: "로이비 오드퍼퓸만 표기되어 개별 향 미식별",
    },
}


def flagged(row, name):
    return row["flag_" + name] == "1"


def option_decision(row, manual):
    key = (row["source"], int(row["source_rank"]))
    if key in manual:
        option, reason = manual[key]
        return option, reason, "snapshot_option_review"
    name = row["product_name_raw"]
    # A fixed gift/bundle is not a PACKAGE choice. Remove gift parentheses only
    # for option detection; the full original name is always retained.
    context = re.sub(r"\([^()]*(?:바이알|미니어[처쳐]|샘플|증정)[^()]*\)", " ", name)
    package = bool(re.search(r"단품.*기획|기획.*단품|(?:ml|m|\d)\s*/\s*기획", context, re.I))
    size = flagged(row, "volume_choice")
    if size and package:
        return "MIXED", "용량 목록과 단품/기획 선택이 함께 있음", "size_and_package"
    if size:
        return "SIZE", "동일 상품명에 단위가 명시된 용량 목록", "size_list"
    if package:
        return "PACKAGE", "단품과 기획 구성 선택; 고정 증정 세트와 구별", "package_choice"
    if flagged(row, "discovery_trial_main"):
        return "NONE", "디스커버리 키트 내 여러 향은 선택 옵션으로 세지 않음", "fixed_discovery"
    if flagged(row, "explicit_option") or flagged(row, "count_option_candidate"):
        return "UNKNOWN", "선택/N종 표기는 있으나 향·용량·구성의 대응 근거 부족", "unresolved_option"
    # Slashes in advertising, synonymous perfume descriptions, and A/O brand
    # spelling are not evidence of selectable scents.
    context = re.sub(r"\[[^\]]*\]", " ", context)
    context = re.sub(r"(?:퍼퓸|향수|엑스트레드퍼퓸)\s*/\s*(?:향수|퍼퓸|니치향수)|A/O", " ", context)
    if "/" in context:
        return "UNKNOWN", "슬래시 목록의 의미를 안전하게 확정하지 못함", "unresolved_slash"
    return "NONE", "상품명에서 선택 옵션 근거 없음; 옵션 부재를 상세페이지에서 확인한 것은 아님", "no_option_evidence"


def cleaning_decision(row, option):
    source, rank = row["source"], int(row["source_rank"])
    if flagged(row, "mixed_product_types"):
        return "REVIEW", "mixed_product_types", row["review_context_note"]
    # Apply the requested MIXED/UNKNOWN hold even to out-of-scope candidates.
    if option in ("MIXED", "UNKNOWN"):
        return "REVIEW", "option_" + option.lower(), "옵션 유형 혼합 또는 옵션 대응 근거 부족"
    if flagged(row, "discovery_trial_main"):
        return "EXCLUDE_DISCOVERY", "discovery_main", row["review_context_note"]
    for flag in ("main_nonperfume", "main_hair_body", "main_solid_cream_stick", "intimate_mention"):
        if flagged(row, flag):
            return "EXCLUDE_NON_PERFUME", flag, row["review_context_note"] or "이너/Y존/속옷 향수가 주상품"
    if option == "SCENT":
        return "EXCLUDE_SCENT_OPTION", "scent_selection", "판매상품 순위를 개별 향의 구매 순위로 배분할 근거 없음"
    if flagged(row, "unclear_use"):
        return "REVIEW", "unclear_use", row["review_context_note"]
    if rank in IDENTITY_REVIEW.get(source, {}):
        return "REVIEW", "identity_unclear", IDENTITY_REVIEW[source][rank]
    evidence = json.loads(row["flag_evidence_json"])
    if flagged(row, "multiple_concentrations") or evidence.get("unmapped_concentration_code"):
        return "REVIEW", "concentration_unclear", "복수 농도 또는 EDPI/EXDP/PFM 등 미해석 코드; 임의 치환하지 않음"
    if flagged(row, "possible_unit_typo"):
        return "REVIEW", "unit_typo", "40m/100m 등 단위 오타 의심; 원문만으로 보정하지 않음"
    if not row["concentration_labels"] and not re.search(r"퍼퓸|향수|perfume", row["product_name_raw"], re.I):
        return "REVIEW", "product_type_unconfirmed", "용량/이름만 있고 인체용 향수 표현이 없어 로컬 상품명만으로 용도 확정 불가"
    return "KEEP", "named_perfume", "본품 향수 표현과 개별 상품명 확인; 고정 증정품 허용, 용량/농도 원문 유지"


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return reader.fieldnames, list(reader)


def validate(raw_fields, raw_rows, results):
    if len(raw_rows) != 999 or len(results) != 999:
        raise ValueError("Expected 999 raw and output rows")
    if [{k: r[k] for k in raw_fields} for r in results] != raw_rows:
        raise ValueError("Raw column values or row order changed")
    if Counter(r["source"] for r in results) != Counter(SOURCES):
        raise ValueError("Source counts changed")
    for source, count in SOURCES.items():
        rows = [r for r in results if r["source"] == source]
        if [int(r["source_rank"]) for r in rows] != list(range(1, count + 1)):
            raise ValueError("Source ranks changed")
        if len({r["source_product_id"] for r in rows}) != count:
            raise ValueError("Product IDs missing or duplicated")
    for r in results:
        if r["cleaning_status"] not in STATUSES or r["option_type"] not in OPTIONS:
            raise ValueError("Invalid status/option")
        if not all(r[k] for k in ("source_product_id", "product_name_raw", "cleaning_reason", "option_reason")):
            raise ValueError("Missing required field or decision reason")
        if r["cleaning_status"] == "KEEP" and r["option_type"] not in ("NONE", "SIZE", "PACKAGE"):
            raise ValueError("Unsafe option retained")
        if r["option_type"] in ("MIXED", "UNKNOWN") and r["cleaning_status"] != "REVIEW":
            raise ValueError("Unresolved option must remain REVIEW")
    for field in ("cleaning_status", "option_type"):
        if sum(Counter(r[field] for r in results).values()) != 999:
            raise ValueError("Decision counts do not sum to 999")


def write_report(rows, audit, hashes):
    lines = ["# 국내 판매 랭킹 1차 정제 판정", "",
             "999개 판매상품의 판정표이며 삭제·SKU 통합 결과가 아니다. KEEP 수는 고유 향수 수가 아니다.",
             "근거: 기존 audit 문맥 검토 및 이번 로컬 상품명 검토. 상세페이지/외부 API/Fragrantica는 확인하지 않았다.", "",
             "## 적용 기준과 우선순위", "",
             "- 일반 향수+다른 제품 유형 선택 → REVIEW. 단일 향수+고정 증정품은 선택형 MIXED가 아니다.",
             "- MIXED/UNKNOWN → 모든 행 REVIEW. 비향수 주상품 후보라도 보류 조건을 우선 적용하며 기존 audit 문맥 근거는 결과의 prior_review_context에 보존한다.",
             "- discovery 키트 자체 → EXCLUDE_DISCOVERY. 헤어/바디 discovery도 이 사유를 우선 기록한다.",
             "- 나머지 중 주상품/모든 선택지가 서비스 범위 밖 → EXCLUDE_NON_PERFUME. 서비스 범위 밖 향 제품의 SCENT는 비향수 제외 사유가 우선이다.",
             "- 나머지 SCENT → EXCLUDE_SCENT_OPTION. SIZE/PACKAGE/NONE은 본품 향수가 명확할 때만 KEEP.",
             "- SIZE+PACKAGE도 MIXED로 보류. N종만으로 향 선택을 확정하지 않는다. 단일 용량의 향수 N종 택1 및 명시적 향 목록은 수동 문맥 검토로 SCENT를 부여했다.",
             "- 고정 본품+바이알/미니어처/다른 제품 증정은 NONE. 기획이라는 단어만으로 PACKAGE 선택을 만들지 않는다.",
             "- 오일퍼퓸/롤온을 일괄 제외하지 않는다. 이름과 용도가 명확한 액상 향수는 유지한다. 농도 미표기만으로 제외하지 않지만 불명확한 제품명·용도·농도 코드·단위 오타는 REVIEW.",
             "- KEEP도 제목에 드러나지 않는 옵션 부재, 실제 성분, 매칭 가능성을 보증하지 않는다. EDP와 EDT, 원문 상품명, 브랜드, 용량은 치환하지 않았다.", "",
             "## 판정 건수", ""]

    def counts_table(field, values):
        lines.extend(["| 판정 | musinsa | oliveyoung | lotte | 전체 |", "|---|---:|---:|---:|---:|"])
        for value in values:
            counts = [sum(r[field] == value and r["source"] == s for r in rows) for s in SOURCES]
            lines.append("| " + " | ".join([value, *map(str, counts), str(sum(counts))]) + " |")
        lines.extend(["| 합계 | 350 | 350 | 299 | 999 |", ""])
    counts_table("cleaning_status", STATUSES)
    counts_table("option_type", OPTIONS)
    lines.extend(["## 기존 audit 후보에서 달라진 이유", "",
                  "후보 플래그는 서로 중복되지만 cleaning_status는 한 행에 하나다. 아래는 같은 후보 행의 실제 판정 이동이다.", "",
                  "| audit 후보 | 후보 수 | KEEP | 비향수 제외 | discovery 제외 | 향 선택 제외 | REVIEW |",
                  "|---|---:|---:|---:|---:|---:|---:|"])
    for flag in ("nonstandard_main_candidate", "discovery_trial_main", "multi_option_candidate",
                 "unresolved_slash", "bundle_or_gift_candidate", "sample_addon_candidate"):
        subset = [r for r, a in zip(rows, audit) if flagged(a, flag)]
        counts = [sum(r["cleaning_status"] == status for r in subset) for status in STATUSES]
        lines.append("| " + " | ".join([flag, str(len(subset)), *map(str, counts)]) + " |")
    lines.extend(["", "- 비일반 주상품 후보에는 일반 향수와 다른 유형의 혼합 선택 및 MIXED/UNKNOWN 옵션이 있어 일부는 REVIEW다. 헤어/바디 discovery는 discovery 제외로 중복 없이 기록한다.",
                  "- multi-option 후보에는 용량 선택, 구성 선택, 틴트 묶음과 미확인 N종이 섞여 있었다. 향 선택 제외 수와 같지 않다.",
                  "- 미탐 후보: 올리브영 13위 CK One/Be 등, 212위 3가지향, 331위 두 향 나열은 명시적 택N 없이도 서로 다른 향을 제시한다.",
                  "- 샘플 증정은 본품이 명확하면 유지한다. EXDP 등 본품 정보가 불명확하면 샘플 때문이 아니라 해당 근거로 REVIEW한다.", "",
                  "## 주요 사례", ""])
    refs = [("musinsa",17), ("oliveyoung",5), ("musinsa",46), ("musinsa",91),
            ("oliveyoung",340), ("lotte",2), ("musinsa",239), ("oliveyoung",30),
            ("oliveyoung",34), ("oliveyoung",9), ("musinsa",87), ("oliveyoung",13),
            ("oliveyoung",12), ("oliveyoung",11), ("musinsa",4), ("oliveyoung",106),
            ("musinsa",80), ("musinsa",57), ("oliveyoung",97), ("lotte",238),
            ("musinsa",214), ("musinsa",29), ("lotte",34)]
    by_ref = {(r["source"], int(r["source_rank"])): r for r in rows}
    for ref in refs:
        r = by_ref[ref]
        lines.append(f"- **{r['source']}:{r['source_rank']} / {r['cleaning_status']} / {r['option_type']}** "
                     f"(ID `{r['source_product_id']}`, Raw {r['audit_raw_csv_line']}행): {r['product_name_raw']} "
                     f"— {r['cleaning_reason']} / 옵션 근거: {r['option_reason']}")
    lines.extend(["", "## REVIEW 사유", "", "| 주사유 | musinsa | oliveyoung | lotte | 전체 |", "|---|---:|---:|---:|---:|"])
    reasons = Counter(r["cleaning_rule"] for r in rows if r["cleaning_status"] == "REVIEW")
    for reason, total in sorted(reasons.items()):
        counts = [sum(r["cleaning_status"] == "REVIEW" and r["cleaning_rule"] == reason and r["source"] == s for r in rows) for s in SOURCES]
        lines.append("| " + " | ".join([reason, *map(str, counts), str(total)]) + " |")
    lines.extend(["", "한 행에 여러 불확실성이 있으면 우선순위에 따른 주사유 하나를 기록했다. 옵션 근거와 기존 audit에 다른 단서도 남아 있다.",
                  "SKU 통합 전 옵션별 향/농도/용량/구성 대응, 일반 이름만 있는 상품의 개별 향, 공간용인지 불명확한 스프레이, 미해석 농도/단위를 확인해야 한다. 롯데 brand_raw=향수존은 실제 브랜드로 쓰면 안 되며 이번에는 보존했다.", "",
                  "## 재현과 검증", "",
                  "- 실행: `venv/Scripts/python.exe -B classify_korea_rankings.py` (기존 Python 3.11.9). 스크립트는 유효 상태/옵션, 원본 값·순서, 행 수·순위·ID, 입력 해시를 검사하고 실패 시 예외를 발생시킨다.",
                  "- 일반 규칙은 option_decision/cleaning_decision, snapshot 수동 근거는 OPTION_REVIEW/IDENTITY_REVIEW 및 기존 audit의 문맥 검토로 구분했다. 입력 해시가 바뀌면 수동 판정을 재검토하도록 중단한다.",
                  "- 입력 Raw 999행과 결과 999행, musinsa 350 / oliveyoung 350 / lotte 299를 유지. 행 삭제·SKU 통합·브랜드 정규화 없음.",
                  "- `make check` 실행 실패: `No rule to make target 'check'`. make는 설치되어 있지만 MAP/저장소 루트에 Makefile 및 check 타깃이 없다. 프로젝트 공통 검사를 통과한 것으로 간주하지 않는다.", ""])
    for name, digest in hashes.items():
        lines.append(f"- 입력 `{name}` SHA256: `{digest}` (처리 전후 동일)")
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    inputs = {p: p.read_bytes() for p in (RAW, AUDIT)}
    hashes = {p.name: hashlib.sha256(b).hexdigest() for p, b in inputs.items()}
    if hashes[RAW.name] != RAW_SHA256 or hashes[AUDIT.name] != AUDIT_SHA256:
        raise ValueError("Snapshot changed: re-review manual decisions before classifying")
    raw_fields, raw_rows = read_csv(RAW)
    _, audit = read_csv(AUDIT)
    if len(audit) != 999 or [{k: r[k] for k in raw_fields} for r in audit] != raw_rows:
        raise ValueError("Audit does not preserve the raw snapshot")
    manual = {}
    for source, ranks, option, reason in OPTION_REVIEW:
        for rank in ranks:
            key = (source, rank)
            if key in manual or source not in SOURCES or not 1 <= rank <= SOURCES[source] or option not in OPTIONS:
                raise ValueError(f"Invalid/duplicate manual option reference: {key}")
            manual[key] = (option, reason)
    results = []
    for raw, a in zip(raw_rows, audit):
        option, option_reason, option_basis = option_decision(a, manual)
        status, rule, reason = cleaning_decision(a, option)
        results.append(dict(raw, cleaning_status=status, option_type=option,
                            cleaning_rule=rule, cleaning_reason=reason,
                            option_basis=option_basis, option_reason=option_reason,
                            prior_review_context=a["review_context_note"],
                            audit_raw_csv_line=a["audit_raw_csv_line"]))
    validate(raw_fields, raw_rows, results)
    with OUTPUT.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0]))
        writer.writeheader()
        writer.writerows(results)
    _, saved = read_csv(OUTPUT)
    validate(raw_fields, raw_rows, saved)
    if saved != results:
        raise ValueError("CSV round trip changed decision values")
    if any(p.read_bytes() != b for p, b in inputs.items()):
        raise ValueError("Raw or existing audit changed")
    write_report(results, audit, hashes)
    for field in ("cleaning_status", "option_type"):
        print(field, dict(Counter(r[field] for r in results)))
        for source in SOURCES:
            print(source, dict(Counter(r[field] for r in results if r["source"] == source)))
    print("PASS: 999 rows, original cells/order/ranks/IDs and both input hashes preserved")
    print(OUTPUT)
    print(REPORT)


if __name__ == "__main__":
    main()

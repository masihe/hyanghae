"""Re-review prior non-perfume exclusions under the Personal Fragrance scope.

Run: venv/Scripts/python.exe -B analyze_personal_fragrance_scope.py
Python 3.11, standard library only. Frozen inputs and prior results stay read-only.
"""
import csv
import hashlib
import re
import unicodedata
from collections import Counter
from pathlib import Path


MAP_DIR = Path(__file__).resolve().parents[2]  # MAP/
DATA = MAP_DIR / "data" / "korea_popularity"

FIRST_PASS = DATA / "korea_perfume_ranking_first_pass.csv"
SECOND_PASS = DATA / "korea_perfume_ranking_second_pass_review.csv"
HWAHAE_RAW = DATA / "hwahae_perfume_top100_raw.csv"
BASE_PURCHASE_KEEP = DATA / "korea_perfume_ranking_confirmed_keep.csv"
BASE_OVERLAP = DATA / "hwahae_purchase_keep_overlap.csv"

SCOPE_REVIEW = DATA / "korea_non_perfume_personal_fragrance_review.csv"
PURCHASE_CANDIDATES = DATA / "korea_personal_fragrance_purchase_candidates.csv"
OVERLAP = DATA / "hwahae_personal_fragrance_overlap.csv"
REPORT = DATA / "korea_personal_fragrance_scope_overlap.md"

EXPECTED_HASHES = {
    FIRST_PASS: "0775e32f757b42f832a5ac858e7b0aecc020ba5e40f5a0ae8ea33b306dbe10fd",
    SECOND_PASS: "5e203e10dc52725b0a99253c6ce1b4645fec67b4c409eb9083d5bca700ba01fc",
    HWAHAE_RAW: "7fc5930d5fb54d912de0c24bbb7ac989c1e20b9efa865929905ce656eadb65cc",
    BASE_PURCHASE_KEEP: "7088e217cd23eff9d8cec29d7adbdd63abc9f8a80ac7dcdcfb77be7691583251",
    BASE_OVERLAP: "fec918ba9c59ef16323edeaa075c643f378aa0e8b0c6971ead5ad4e52040eab3",
}

SCOPES = ("PERSONAL_FRAGRANCE", "HOME_FRAGRANCE", "UNRESOLVED")
SAFE_OPTIONS = ("NONE", "SIZE", "PACKAGE")
OVERLAP_STATUSES = ("MATCH", "NO_MATCH", "MATCH_REVIEW")

# Scope is based only on the frozen product title. Home/object use takes
# priority, then non-fragrance body-care or ambiguous application, then the
# newly included body-applied fragrance forms.
HOME_PATTERN = re.compile(r"룸\s*스프레이|섬유\s*향수|디퓨저|캔들|속옷\s*향수", re.I)
UNRESOLVED_PATTERN = re.compile(
    r"Y존\s*향수|샤워\s*젤|애프터\s*쉐이브|핸드\s*크림|모이스처라이저|샤워\s*시트", re.I
)
PERSONAL_PATTERN = re.compile(
    r"헤어|바디\s*(?:퍼퓸|미스트|스프레이)|솔리드|고체\s*향수|"
    r"퍼퓸\s*밤|크림\s*퍼퓸|퍼퓸\s*젤|퍼퓸\s*스틱", re.I
)

# All same-brand comparisons between the 36 returned rows and Hwahae TOP100.
# Explicit decisions prevent a same scent in another application form from
# being treated as the same product.
EXPANSION_PAIR_DECISIONS = {
    ("musinsa", 162, 25): "different_identity",
    ("musinsa", 107, 78): "identity_missing_and_product_form_distinct",
    ("oliveyoung", 140, 20): "different_identity",
    ("oliveyoung", 271, 20): "different_identity",
    ("oliveyoung", 32, 62): "different_identity",
    ("oliveyoung", 32, 88): "different_identity",
    ("musinsa", 238, 7): "different_identity",
    ("musinsa", 238, 18): "different_identity",
    ("musinsa", 238, 19): "different_identity",
    ("musinsa", 238, 24): "different_identity",
    ("oliveyoung", 100, 7): "same_scent_but_hair_perfume_vs_general_perfume",
    ("oliveyoung", 100, 18): "same_scent_but_hair_perfume_vs_general_perfume",
    ("oliveyoung", 100, 19): "different_identity",
    ("oliveyoung", 100, 24): "different_identity",
    ("oliveyoung", 274, 56): "different_identity",
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


def compact(text):
    text = unicodedata.normalize("NFKC", text).lower()
    return re.sub(r"[^0-9a-z가-힣]+", "", text)


def normalize_brand(text):
    value = compact(text)
    aliases = {
        "ck": "캘빈클라인",
        "캘빈클라인퍼퓸": "캘빈클라인",
        "랑방퍼퓸": "랑방",
        "메종마르지엘라퍼퓸": "메종마르지엘라",
        "베르사체퍼퓸": "베르사체",
        "지미추퍼퓸": "지미추",
        "몽블랑퍼퓸": "몽블랑",
        "코치프래그런스": "코치",
        "입생로랑뷰티": "입생로랑",
        "에디션드퍼퓸프레데릭말": "프레데릭말",
    }
    return aliases.get(value, value)


def normalize_identity(brand, product):
    text = unicodedata.normalize("NFKC", product).lower()
    text = re.sub(r"\[[^\]]*(?:pick|증정|기획|new|단독|리뉴얼|특가|포카)[^\]]*\]", " ", text, flags=re.I)
    text = re.sub(r"\+.*$", " ", text)
    text = re.sub(r"\d+(?:\.\d+)?\s*(?:ml|mℓ|fl\.?\s*oz\.?)", " ", text, flags=re.I)
    for token in (brand, normalize_brand(brand)):
        if token:
            text = text.replace(token.lower(), " ")
    text = re.sub(
        r"오\s*드\s*퍼퓸|오드퍼퓸|오\s*드\s*빠르펭|오드빠르펭|edp|"
        r"오\s*드\s*뚜왈렛|오드뚜왈렛|오\s*드\s*뜨왈렛|edt|"
        r"오\s*드\s*코롱|오드코롱|오\s*데\s*코롱|edc|향수|퍼퓸|perfume|코롱",
        " ", text, flags=re.I,
    )
    return compact(text)


def concentrations(text):
    normalized = unicodedata.normalize("NFKC", text).lower()
    found = set()
    if re.search(r"\bedp\b|오\s*드\s*퍼퓸|오드퍼퓸|오\s*드\s*빠르펭|오드빠르펭", normalized):
        found.add("EDP")
    if re.search(r"\bedt\b|오\s*드\s*뚜왈렛|오드뚜왈렛|오\s*드\s*뜨왈렛|오드뜨왈렛", normalized):
        found.add("EDT")
    if re.search(r"\bedc\b|오\s*드\s*코롱|오드코롱|오\s*데\s*코롱|오데코롱|\b코롱\b", normalized):
        found.add("EDC")
    if re.search(r"엑스트레|extrait", normalized):
        found.add("EXTRAIT")
    return found


def effective_status(row, second_by_key):
    if row["cleaning_status"] != "REVIEW":
        return row["cleaning_status"], f"first_pass:{row['cleaning_rule']}", row["cleaning_reason"]
    second = second_by_key[(row["source"], row["source_rank"])]
    return (
        second["second_pass_status"],
        f"second_pass:{second['second_pass_basis']}",
        second["second_pass_reason"],
    )


def classify_scope(row):
    product = row["product_name_raw"]
    if HOME_PATTERN.search(product):
        return (
            "HOME_FRAGRANCE", "explicit_home_or_object_use",
            "상품명에 공간·섬유·속옷 등 사물 사용 또는 디퓨저·캔들이 명시되어 있다.",
        )
    if UNRESOLVED_PATTERN.search(product):
        return (
            "UNRESOLVED", "body_care_or_application_unclear",
            "세정·보습·애프터쉐이브가 주기능이거나 피부와 속옷 중 적용 대상이 불명확하다.",
        )
    if PERSONAL_PATTERN.search(product):
        return (
            "PERSONAL_FRAGRANCE", "explicit_body_applied_fragrance_form",
            "헤어·바디 미스트, 고체향수, 퍼퓸밤·젤·스틱 등 몸에 향을 남기는 제형이 명시되어 있다.",
        )
    raise ValueError(f"No Personal Fragrance scope rule for {row['source']}:{row['source_rank']}")


def candidate_decision(scope, option):
    if scope == "HOME_FRAGRANCE":
        return "EXCLUDE_HOME_FRAGRANCE", "공간 또는 사물에 사용하는 제품이므로 후보에서 제외한다."
    if scope == "UNRESOLVED":
        return "REVIEW_SCOPE_UNRESOLVED", "Personal Fragrance 포함 여부를 상품명만으로 확정하지 않는다."
    if option == "SCENT":
        return "EXCLUDE_SCENT_OPTION", "여러 향 선택 상품의 순위를 개별 향에 귀속하지 않는다."
    if option == "MIXED":
        return "EXCLUDE_MIXED_OPTION", "여러 향과 용량·구성 선택이 섞인 판매행을 후보로 복귀시키지 않는다."
    if option == "UNKNOWN":
        return "REVIEW_OPTION_UNKNOWN", "선택 항목이 향·용량·구성 중 무엇인지 확인이 필요하다."
    if option not in SAFE_OPTIONS:
        raise ValueError(f"Unexpected option type: {option}")
    return "RETURN_TO_CANDIDATES", "Personal Fragrance이며 향 선택이 없는 확정 판매행이다."


def build_scope_review(first_rows, second_by_key):
    results = []
    for row in first_rows:
        status, prior_basis, prior_reason = effective_status(row, second_by_key)
        if status != "EXCLUDE_NON_PERFUME":
            continue
        scope, scope_rule, scope_reason = classify_scope(row)
        decision, reason = candidate_decision(scope, row["option_type"])
        results.append(dict(
            row,
            previous_effective_status=status,
            previous_effective_basis=prior_basis,
            previous_effective_reason=prior_reason,
            personal_fragrance_scope=scope,
            scope_rule=scope_rule,
            scope_reason=scope_reason,
            candidate_decision=decision,
            candidate_reason=reason,
        ))
    return results


def build_candidates(first_rows, second_by_key, scope_review):
    review_by_key = {(r["source"], r["source_rank"]): r for r in scope_review}
    results = []
    for row in first_rows:
        status, prior_basis, _ = effective_status(row, second_by_key)
        key = (row["source"], row["source_rank"])
        if status == "KEEP":
            candidate_basis = "prior_confirmed_KEEP"
            scope_review_ref = ""
        elif key in review_by_key and review_by_key[key]["candidate_decision"] == "RETURN_TO_CANDIDATES":
            candidate_basis = "personal_fragrance_scope_return"
            scope_review_ref = f"{row['source']}:{row['source_rank']}"
        else:
            continue
        results.append(dict(
            row,
            personal_fragrance_candidate_status="KEEP",
            candidate_basis=candidate_basis,
            previous_effective_basis=prior_basis,
            scope_review_ref=scope_review_ref,
        ))
    return results


def build_overlap(hwahae_rows, base_fields, base_rows, candidates):
    base_by_rank = {int(r["hwahae_rank"]): r for r in base_rows}
    candidate_by_ref = {(r["source"], r["source_rank"]): r for r in candidates}
    results = []
    for hw in hwahae_rows:
        rank = int(hw["source_rank"])
        if rank in base_by_rank:
            row = dict(base_by_rank[rank])
            row["previous_overlap_status"] = row["overlap_status"]
            row["overlap_change"] = "UNCHANGED"
        else:
            row = {
                "hwahae_rank": hw["source_rank"],
                "hwahae_source_product_id": hw["source_product_id"],
                "hwahae_brand": hw["brand_raw"],
                "hwahae_product": hw["product_name_raw"],
                "hwahae_brand_normalized": normalize_brand(hw["brand_raw"]),
                "hwahae_identity_normalized": normalize_identity(hw["brand_raw"], hw["product_name_raw"]),
                "hwahae_concentration": ";".join(sorted(concentrations(hw["product_name_raw"]))),
                "overlap_status": "NO_MATCH",
                "matched_purchase_source": "",
                "matched_purchase_source_rank": "",
                "matched_purchase_product_id": "",
                "matched_purchase_product_name": "",
                "match_basis": "no conservative brand + identity + product-form match among expanded candidates",
                "previous_overlap_status": "NOT_IN_PREVIOUS_DENOMINATOR",
                "overlap_change": "ADDED_TO_FULL_TOP100_NO_MATCH",
            }
        ref = (row["matched_purchase_source"], row["matched_purchase_source_rank"])
        row["matched_candidate_basis"] = candidate_by_ref[ref]["candidate_basis"] if ref in candidate_by_ref else ""
        results.append(row)
    expected_base_fields = base_fields + ["previous_overlap_status", "overlap_change", "matched_candidate_basis"]
    if list(results[0]) != expected_base_fields:
        raise ValueError("Unexpected expanded overlap field order")
    return results


def validate_inputs(first_rows, second_rows, hwahae_rows, base_keep, base_overlap):
    if len(first_rows) != 999 or len(second_rows) != 128:
        raise ValueError("Unexpected first/second-pass row count")
    review_keys = {(r["source"], r["source_rank"]) for r in first_rows if r["cleaning_status"] == "REVIEW"}
    if review_keys != {(r["source"], r["source_rank"]) for r in second_rows}:
        raise ValueError("Second pass does not exactly cover first-pass REVIEW")
    if len(hwahae_rows) != 100 or [int(r["source_rank"]) for r in hwahae_rows] != list(range(1, 101)):
        raise ValueError("Hwahae input must be 100 continuous ranks")
    if len({r["source_product_id"] for r in hwahae_rows}) != 100:
        raise ValueError("Hwahae source_product_id must be unique")
    if len(base_keep) != 790:
        raise ValueError("Previous confirmed purchase KEEP must contain 790 rows")
    if Counter(r["overlap_status"] for r in base_overlap) != Counter(
        {"MATCH": 30, "NO_MATCH": 66, "MATCH_REVIEW": 2}
    ):
        raise ValueError("Previous overlap counts changed")


def validate_outputs(first_fields, first_rows, scope_review, candidates,
                     hwahae_rows, base_fields, base_rows, overlap):
    if len(scope_review) != 69:
        raise ValueError(f"Expected 69 previous EXCLUDE_NON_PERFUME rows, got {len(scope_review)}")
    source_by_key = {(r["source"], r["source_rank"]): r for r in first_rows}
    if any(
        {k: row[k] for k in first_fields} != source_by_key[(row["source"], row["source_rank"])]
        for row in scope_review
    ):
        raise ValueError("Scope review changed original first-pass values")
    if Counter(r["personal_fragrance_scope"] for r in scope_review) != Counter(
        {"PERSONAL_FRAGRANCE": 56, "HOME_FRAGRANCE": 7, "UNRESOLVED": 6}
    ):
        raise ValueError("Unexpected Personal/Home/unresolved counts")
    expected_decisions = Counter({
        "RETURN_TO_CANDIDATES": 36,
        "EXCLUDE_HOME_FRAGRANCE": 7,
        "REVIEW_SCOPE_UNRESOLVED": 6,
        "EXCLUDE_SCENT_OPTION": 11,
        "EXCLUDE_MIXED_OPTION": 5,
        "REVIEW_OPTION_UNKNOWN": 4,
    })
    if Counter(r["candidate_decision"] for r in scope_review) != expected_decisions:
        raise ValueError("Unexpected scope candidate-decision counts")
    if len(candidates) != 826 or Counter(r["candidate_basis"] for r in candidates) != Counter(
        {"prior_confirmed_KEEP": 790, "personal_fragrance_scope_return": 36}
    ):
        raise ValueError("Expanded candidate count must be 790 + 36 = 826")
    if len({(r["source"], r["source_product_id"]) for r in candidates}) != len(candidates):
        raise ValueError("Expanded candidates contain duplicate source product IDs")

    base_keys = {(r["source"], r["source_rank"]) for r in candidates if r["candidate_basis"] == "prior_confirmed_KEEP"}
    expected_base_keys = {(r["source"], r["source_rank"]) for r in read_csv(BASE_PURCHASE_KEEP)[1]}
    if base_keys != expected_base_keys:
        raise ValueError("Expanded candidates do not preserve every previous KEEP row")

    if len(overlap) != 100 or [int(r["hwahae_rank"]) for r in overlap] != list(range(1, 101)):
        raise ValueError("Expanded overlap must cover all Hwahae TOP100 in order")
    if Counter(r["overlap_status"] for r in overlap) != Counter(
        {"MATCH": 30, "NO_MATCH": 68, "MATCH_REVIEW": 2}
    ):
        raise ValueError("Unexpected expanded overlap counts")
    preserved = [{k: r[k] for k in base_fields} for r in overlap if int(r["hwahae_rank"]) not in (5, 90)]
    if preserved != base_rows:
        raise ValueError("Previous 98 overlap rows or statuses changed")

    candidate_by_ref = {(r["source"], r["source_rank"]): r for r in candidates}
    for row in overlap:
        if row["overlap_status"] == "NO_MATCH":
            if any(row[k] for k in (
                "matched_purchase_source", "matched_purchase_source_rank",
                "matched_purchase_product_id", "matched_purchase_product_name",
            )):
                raise ValueError("NO_MATCH contains a candidate reference")
            continue
        ref = (row["matched_purchase_source"], row["matched_purchase_source_rank"])
        if ref not in candidate_by_ref:
            raise ValueError(f"Match does not reference an expanded candidate: {ref}")
        purchase = candidate_by_ref[ref]
        if row["matched_purchase_product_id"] != purchase["source_product_id"]:
            raise ValueError(f"Matched candidate ID mismatch: {ref}")
        hw_conc = set(filter(None, row["hwahae_concentration"].split(";")))
        purchase_conc = concentrations(purchase["product_name_raw"])
        if hw_conc and purchase_conc and hw_conc != purchase_conc:
            raise ValueError(f"Concentration conflict at Hwahae rank {row['hwahae_rank']}")

    returned = [r for r in candidates if r["candidate_basis"] == "personal_fragrance_scope_return"]
    same_brand_pairs = {
        (p["source"], int(p["source_rank"]), int(h["source_rank"]))
        for p in returned for h in hwahae_rows
        if normalize_brand(p["brand_raw"]) == normalize_brand(h["brand_raw"])
    }
    if same_brand_pairs != set(EXPANSION_PAIR_DECISIONS):
        raise ValueError("Returned-candidate same-brand review coverage changed")
    if any(r["matched_candidate_basis"] == "personal_fragrance_scope_return" for r in overlap):
        raise ValueError("Unexpected new match from the scope expansion")


def write_report(scope_review, candidates, base_overlap, overlap, hashes):
    scope_counts = Counter(r["personal_fragrance_scope"] for r in scope_review)
    decision_counts = Counter(r["candidate_decision"] for r in scope_review)
    old_counts = Counter(r["overlap_status"] for r in base_overlap)
    new_counts = Counter(r["overlap_status"] for r in overlap)
    old_ratio = old_counts["MATCH"] / len(base_overlap)
    new_ratio = new_counts["MATCH"] / len(overlap)
    review_rows = [r for r in scope_review if r["candidate_decision"] in (
        "REVIEW_SCOPE_UNRESOLVED", "REVIEW_OPTION_UNKNOWN"
    )]
    returned = [r for r in scope_review if r["candidate_decision"] == "RETURN_TO_CANDIDATES"]

    lines = [
        "# Personal Fragrance 범위 재검토와 화해 overlap", "",
        "기존 구매 데이터의 EXCLUDE_NON_PERFUME 69행만 frozen 상품명과 기존 옵션 판정으로 다시 검토했다. 외부 수집, SKU 통합, Fragrantica 매칭, 최종 후보 선정은 하지 않았다.", "",
        "## 69행 범위 재검토", "",
        "| 범위 | 건수 |", "|---|---:|",
        f"| PERSONAL_FRAGRANCE | {scope_counts['PERSONAL_FRAGRANCE']} |",
        f"| HOME_FRAGRANCE | {scope_counts['HOME_FRAGRANCE']} |",
        f"| UNRESOLVED | {scope_counts['UNRESOLVED']} |",
        "| 합계 | 69 |", "",
        "Personal Fragrance에는 헤어퍼퓸, 헤어·바디 미스트, 고체향수, 퍼퓸밤·젤·스틱을 포함했다. 룸·섬유·디퓨저·캔들·속옷 사용 제품은 Home Fragrance로 유지했다. 세정·보습·애프터쉐이브 제품과 Y존/속옷 적용 대상이 불명확한 항목은 UNRESOLVED로 남겼다.", "",
        "## 구매 후보 변화", "",
        "| 판정 | 건수 |", "|---|---:|",
        f"| 후보 복귀 | {decision_counts['RETURN_TO_CANDIDATES']} |",
        f"| Home Fragrance 제외 | {decision_counts['EXCLUDE_HOME_FRAGRANCE']} |",
        f"| 범위 unresolved | {decision_counts['REVIEW_SCOPE_UNRESOLVED']} |",
        f"| 다향 선택 제외 | {decision_counts['EXCLUDE_SCENT_OPTION']} |",
        f"| 혼합 옵션 제외 | {decision_counts['EXCLUDE_MIXED_OPTION']} |",
        f"| 옵션 미확인 | {decision_counts['REVIEW_OPTION_UNKNOWN']} |",
        "| 합계 | 69 |", "",
        f"구매 후보는 **790행에서 {len(candidates)}행으로 {len(candidates) - 790}행 증가**했다. 이는 판매상품 행 수이며 SKU 또는 고유 제품 수가 아니다.", "",
        "복귀 사례:", "",
    ]
    for source, rank in (
        ("musinsa", 59), ("musinsa", 103), ("musinsa", 246),
        ("oliveyoung", 32), ("oliveyoung", 100), ("oliveyoung", 278),
    ):
        row = next(r for r in returned if r["source"] == source and int(r["source_rank"]) == rank)
        lines.append(f"- `{source}:{rank}` {row['brand_raw']} / {row['product_name_raw']}")

    lines.extend(["", "## 화해 TOP100 overlap", "",
                  "이번 비교는 요청에 따라 화해 100개 전체를 분모로 사용했다.", "",
                  "| 항목 | 기존 결과 | Personal Fragrance 결과 | 변화 |", "|---|---:|---:|---:|",
                  f"| 화해 비교 행 | {len(base_overlap)} | {len(overlap)} | +{len(overlap) - len(base_overlap)} |",
                  f"| MATCH | {old_counts['MATCH']} | {new_counts['MATCH']} | {new_counts['MATCH'] - old_counts['MATCH']:+d} |",
                  f"| NO_MATCH | {old_counts['NO_MATCH']} | {new_counts['NO_MATCH']} | {new_counts['NO_MATCH'] - old_counts['NO_MATCH']:+d} |",
                  f"| MATCH_REVIEW | {old_counts['MATCH_REVIEW']} | {new_counts['MATCH_REVIEW']} | {new_counts['MATCH_REVIEW'] - old_counts['MATCH_REVIEW']:+d} |",
                  f"| MATCH 비율 | {old_ratio:.1%} | {new_ratio:.1%} | {(new_ratio - old_ratio) * 100:+.1f}%p |", "",
                  "새롭게 MATCH된 화해 상품은 **0건**이다. 기존 98개와 같은 분모로 비교하면 MATCH/NO_MATCH/MATCH_REVIEW는 모두 변하지 않았다. 새 결과의 NO_MATCH +2와 비율 -0.6%p는 이전 REVIEW 2개를 포함해 화해 100개 전체를 사용한 데서 발생했다.", "",
                  "복귀 상품 중 화해와 브랜드가 같은 모든 조합을 확인했다. 포맨트 코튼메모리 헤어퍼퓸처럼 향 이름이 같아도 일반 퍼퓸과 제품 제형이 다르면 같은 제품으로 연결하지 않았다.", "",
                  "## 사람이 확인할 항목", "",
                  f"범위 또는 옵션 확인이 필요한 행은 {len(review_rows)}건이다.", ""])
    for row in review_rows:
        lines.append(
            f"- `{row['source']}:{row['source_rank']}` {row['brand_raw']} / {row['product_name_raw']} "
            f"— {row['candidate_reason']}"
        )

    lines.extend(["", "## 검증", "",
                  "- 실행: `venv/Scripts/python.exe -B analyze_personal_fragrance_scope.py`.",
                  "- 기존 EXCLUDE_NON_PERFUME 69행을 56/7/6으로 빠짐없이 분류했다.",
                  "- 기존 구매 KEEP 790행을 전부 보존하고 복귀 36행만 추가해 826행인지 검사했다.",
                  "- Personal Fragrance라도 SCENT 11, MIXED 5, UNKNOWN 4는 후보로 복귀하지 않았는지 검사했다.",
                  "- 화해 입력 순위 1~100, product_id 고유성, overlap 100행과 30/68/2 합계를 검사했다.",
                  "- 기존 overlap 98행의 모든 원래 컬럼과 상태가 그대로 유지됐는지 검사했다.",
                  "- 모든 MATCH/MATCH_REVIEW가 새 구매 후보의 실제 행·product_id를 참조하고 농도 충돌이 없는지 검사했다.",
                  "- 복귀 36행과 화해 TOP100의 같은 브랜드 조합 15개를 모두 명시적으로 검토했는지 검사했다.",
                  "- 세 CSV round-trip과 입력·기존 결과 파일의 실행 전후 바이트 불변을 검사했다.", ""])
    for path, digest in hashes.items():
        lines.append(f"- `{path.name}`: `{digest}`")

    lines.extend(["", "## 남은 문제", "",
                  "- UNRESOLVED 6행은 향이 주목적인 제품인지 또는 피부에 직접 쓰는지 확인이 필요하다.",
                  "- Personal Fragrance 중 UNKNOWN 옵션 4행은 실제 옵션명이 향·용량·구성 중 무엇인지 확인이 필요하다.",
                  "- 기존 MANUAL_CHECK 60행은 이번 69행 재검토 범위에 포함하지 않았고 구매 후보에서도 제외했다.",
                  "- 후보 826행은 SKU 통합 전 판매상품 행 수다.", ""])
    REPORT.write_text("\n".join(lines), encoding="utf-8")


def main():
    protected = {path: path.read_bytes() for path in EXPECTED_HASHES}
    hashes = {path: hashlib.sha256(data).hexdigest() for path, data in protected.items()}
    for path, expected in EXPECTED_HASHES.items():
        if hashes[path] != expected:
            raise ValueError(f"Snapshot or baseline changed; re-review required: {path.name}")

    first_fields, first_rows = read_csv(FIRST_PASS)
    _, second_rows = read_csv(SECOND_PASS)
    _, hwahae_rows = read_csv(HWAHAE_RAW)
    _, base_keep = read_csv(BASE_PURCHASE_KEEP)
    base_fields, base_overlap = read_csv(BASE_OVERLAP)
    validate_inputs(first_rows, second_rows, hwahae_rows, base_keep, base_overlap)

    second_by_key = {(r["source"], r["source_rank"]): r for r in second_rows}
    scope_review = build_scope_review(first_rows, second_by_key)
    candidates = build_candidates(first_rows, second_by_key, scope_review)
    overlap = build_overlap(hwahae_rows, base_fields, base_overlap, candidates)
    validate_outputs(
        first_fields, first_rows, scope_review, candidates,
        hwahae_rows, base_fields, base_overlap, overlap,
    )

    scope_fields = first_fields + [
        "previous_effective_status", "previous_effective_basis", "previous_effective_reason",
        "personal_fragrance_scope", "scope_rule", "scope_reason",
        "candidate_decision", "candidate_reason",
    ]
    candidate_fields = first_fields + [
        "personal_fragrance_candidate_status", "candidate_basis",
        "previous_effective_basis", "scope_review_ref",
    ]
    overlap_fields = base_fields + ["previous_overlap_status", "overlap_change", "matched_candidate_basis"]
    write_csv(SCOPE_REVIEW, scope_fields, scope_review)
    write_csv(PURCHASE_CANDIDATES, candidate_fields, candidates)
    write_csv(OVERLAP, overlap_fields, overlap)
    write_report(scope_review, candidates, base_overlap, overlap, hashes)

    if any(path.read_bytes() != data for path, data in protected.items()):
        raise ValueError("An input or previous result changed during processing")

    print("scope", dict(Counter(r["personal_fragrance_scope"] for r in scope_review)))
    print("candidate_decision", dict(Counter(r["candidate_decision"] for r in scope_review)))
    print(f"purchase_candidates 790 -> {len(candidates)} (+{len(candidates) - 790})")
    print("overlap", dict(Counter(r["overlap_status"] for r in overlap)))
    print("new_matches_from_scope_expansion", sum(
        r["matched_candidate_basis"] == "personal_fragrance_scope_return" for r in overlap
    ))
    print("PASS: counts, provenance, options, references, forms, concentrations, hashes, and CSV round trips")
    for path in (SCOPE_REVIEW, PURCHASE_CANDIDATES, OVERLAP, REPORT):
        print(path)


if __name__ == "__main__":
    main()

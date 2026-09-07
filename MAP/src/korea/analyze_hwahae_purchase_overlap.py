"""Minimally clean Hwahae TOP100 and compare it with confirmed purchase KEEP rows.

Run: venv/Scripts/python.exe -B analyze_hwahae_purchase_overlap.py
Python 3.11, standard library only. Frozen inputs remain read-only.
"""
import csv
import hashlib
import re
import unicodedata
from collections import Counter
from pathlib import Path


MAP_DIR = Path(__file__).resolve().parents[2]  # MAP/
DATA = MAP_DIR / "data" / "korea_popularity"

HWAHAE_RAW = DATA / "hwahae_perfume_top100_raw.csv"
HWAHAE_EXTRACTION = DATA / "hwahae_perfume_top100_extraction.md"
FIRST_PASS = DATA / "korea_perfume_ranking_first_pass.csv"
SECOND_PASS = DATA / "korea_perfume_ranking_second_pass_review.csv"

HWAHAE_CLEAN = DATA / "hwahae_perfume_top100_minimal_clean.csv"
PURCHASE_KEEP = DATA / "korea_perfume_ranking_confirmed_keep.csv"
OVERLAP = DATA / "hwahae_purchase_keep_overlap.csv"
REPORT = DATA / "hwahae_purchase_keep_overlap.md"

EXPECTED_HASHES = {
    HWAHAE_RAW: "7fc5930d5fb54d912de0c24bbb7ac989c1e20b9efa865929905ce656eadb65cc",
    HWAHAE_EXTRACTION: "bf729d41920b7bf2c81f9652b38ad7af6eb5b3d03fa611743d1bdb7985ef013a",
    FIRST_PASS: "0775e32f757b42f832a5ac858e7b0aecc020ba5e40f5a0ae8ea33b306dbe10fd",
    SECOND_PASS: "5e203e10dc52725b0a99253c6ce1b4645fec67b4c409eb9083d5bca700ba01fc",
}

HWAHAE_STATUSES = ("KEEP", "EXCLUDE_NON_PERFUME", "REVIEW")
OVERLAP_STATUSES = ("MATCH", "NO_MATCH", "MATCH_REVIEW")

OUT_OF_SCOPE = re.compile(
    r"헤어\s*퍼퓸|바디\s*미스트|헤어\s*&?\s*바디|룸\s*스프레이|섬유\s*향수|"
    r"디퓨저|캔들|고체\s*향수|솔리드\s*퍼퓸|퍼퓸\s*(?:밤|크림|젤|스틱)",
    re.IGNORECASE,
)
PERFUME_EVIDENCE = re.compile(
    r"향수|퍼퓸|perfume|parfum|EDP|EDT|EDC|오\s*드|오드\s*코롱|오\s*데\s*코롱|코롱|센트\s*스프레이",
    re.IGNORECASE,
)

# Snapshot-specific scope decisions are isolated from reusable title rules.
# Rank 20 has explicit local purchase evidence for the same brand and identity.
LOCAL_SCOPE_EVIDENCE = {20: "musinsa:200;oliveyoung:29"}
REVIEW_RANKS = {
    5: ("product_type_unconfirmed", "상품명과 10ml 표기만으로 일반 액상 향수 제형을 확인할 수 없다."),
    90: ("product_type_unconfirmed", "고유 제품명만 있고 상품명에 일반 액상 향수 제형 또는 농도 표현이 없다."),
}

# One representative confirmed purchase KEEP row per Hwahae product.
# These links were reviewed by brand + fragrance identity; no fuzzy threshold is used.
# A concentration missing on one side or an abbreviated identity stays MATCH_REVIEW.
MATCHES = {
    3: ("MATCH_REVIEW", "musinsa", 109,
        "brand_exact + identity_exact; purchase specifies EDC while Hwahae omits concentration"),
    6: ("MATCH", "oliveyoung", 197, "brand_exact + identity_exact + EDP_exact"),
    7: ("MATCH", "oliveyoung", 20, "brand_exact + identity_exact + promotional_copy_removed"),
    12: ("MATCH", "musinsa", 27, "brand_alias + replica_collection_label_removed + identity_exact + EDT_exact"),
    18: ("MATCH", "oliveyoung", 20, "brand_exact + identity_exact + promotional_edition_removed"),
    19: ("MATCH", "musinsa", 5, "brand_exact + identity_exact"),
    20: ("MATCH", "oliveyoung", 29, "brand_exact + identity_exact + local_product_type_evidence"),
    24: ("MATCH", "oliveyoung", 96, "brand_exact + identity_exact + promotional_copy_removed"),
    25: ("MATCH", "musinsa", 21, "brand_exact + identity_exact + EDP_exact"),
    27: ("MATCH", "oliveyoung", 76, "brand_exact + identity_exact + EDT_exact"),
    29: ("MATCH", "musinsa", 93, "brand_exact + identity_exact; size_difference_ignored"),
    30: ("MATCH", "oliveyoung", 33, "brand_alias_CK_CalvinKlein + identity_exact + EDT_exact"),
    33: ("MATCH", "oliveyoung", 31, "brand_exact + identity_exact + EDP_exact; 2.0_variant_not_used"),
    35: ("MATCH", "musinsa", 39, "brand_alias + replica_collection_label_removed + identity_exact + EDT_exact"),
    38: ("MATCH", "musinsa", 294, "brand_alias_spacing + identity_exact + EDP_exact"),
    39: ("MATCH", "oliveyoung", 199, "brand_exact + identity_exact + EDP_exact"),
    52: ("MATCH", "oliveyoung", 188, "brand_exact + identity_exact + EDP_exact"),
    54: ("MATCH", "oliveyoung", 132, "brand_exact + identity_exact + EDP_exact"),
    59: ("MATCH", "oliveyoung", 44, "brand_exact + identity_exact + EDP_exact"),
    62: ("MATCH", "musinsa", 73, "brand_exact + identity_exact + EDP_exact"),
    63: ("MATCH", "lotte", 148, "brand_in_purchase_title + identity_exact + EDT_exact"),
    68: ("MATCH", "oliveyoung", 62, "brand_exact + collection_label_normalized + identity_exact + EDT_exact"),
    72: ("MATCH", "oliveyoung", 112, "brand_exact + identity_exact + EDP_exact"),
    78: ("MATCH", "musinsa", 45, "brand_exact + identity_exact"),
    79: ("MATCH", "oliveyoung", 41, "brand_alias_CK_CalvinKlein + identity_exact + EDT_exact"),
    80: ("MATCH_REVIEW", "musinsa", 176,
         "brand_alias + EDT_exact; Hwahae identity is abbreviated while purchase says women"),
    82: ("MATCH", "musinsa", 188, "brand_alias + collection_label_normalized + identity_exact + EDT_exact"),
    83: ("MATCH", "oliveyoung", 72, "brand_exact + identity_exact + EDT_exact"),
    84: ("MATCH", "oliveyoung", 195, "brand_exact + identity_exact + EDT_exact"),
    86: ("MATCH", "oliveyoung", 30, "brand_alias_CK_CalvinKlein + identity_exact + EDT_exact"),
    88: ("MATCH", "musinsa", 293, "brand_exact + classic_collection_label_removed + identity_exact + EDP_exact"),
    97: ("MATCH", "oliveyoung", 123, "brand_alias + identity_exact + EDP_exact"),
}

NO_MATCH_DETAILS = {
    1: "related purchase row is a multi-scent listing excluded from confirmed KEEP; no individual Bombshell KEEP row",
    44: "same-brand purchase rows are Modern Princess EDP, not Eau Sensuelle EDT",
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
        "아리아나그란데": "아리아나그란데",
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


def classify_hwahae(row):
    rank = int(row["source_rank"])
    product = row["product_name_raw"]
    if rank in REVIEW_RANKS:
        rule, reason = REVIEW_RANKS[rank]
        return "REVIEW", rule, reason, ""
    if OUT_OF_SCOPE.search(product):
        return (
            "EXCLUDE_NON_PERFUME", "explicit_non_perfume_type",
            "상품명에 서비스 범위 밖 용도 또는 제형이 명시되어 있다.", "",
        )
    if rank in LOCAL_SCOPE_EVIDENCE:
        return (
            "KEEP", "local_confirmed_perfume_identity",
            "동일 브랜드·제품명의 로컬 구매 행에서 일반 액상 퍼퓸 표현을 확인했다.",
            LOCAL_SCOPE_EVIDENCE[rank],
        )
    if PERFUME_EVIDENCE.search(product):
        return (
            "KEEP", "named_liquid_perfume",
            "상품명에 향수·농도·코롱 등 일반 액상 향수 근거가 있고 범위 밖 제형 표기가 없다.", "",
        )
    return "REVIEW", "product_type_unconfirmed", "상품명만으로 일반 액상 향수 제형을 확인할 수 없다.", ""


def build_purchase_keep(first_rows, second_rows):
    second_by_key = {(r["source"], r["source_rank"]): r for r in second_rows}
    results = []
    for row in first_rows:
        if row["cleaning_status"] == "KEEP":
            basis = "first_pass_KEEP"
        elif row["cleaning_status"] == "REVIEW":
            second = second_by_key[(row["source"], row["source_rank"])]
            if second["second_pass_status"] != "KEEP":
                continue
            basis = "second_pass_KEEP"
        else:
            continue
        results.append(dict(row, effective_cleaning_status="KEEP", effective_status_basis=basis))
    return results


def validate_inputs(hwahae_rows, first_rows, second_rows):
    if len(hwahae_rows) != 100:
        raise ValueError(f"Expected 100 Hwahae rows, got {len(hwahae_rows)}")
    if [int(r["source_rank"]) for r in hwahae_rows] != list(range(1, 101)):
        raise ValueError("Hwahae ranks are not continuous 1..100")
    if len({r["source_product_id"] for r in hwahae_rows}) != 100:
        raise ValueError("Hwahae product IDs are not unique")
    if len(first_rows) != 999 or len(second_rows) != 128:
        raise ValueError("Unexpected purchase decision row counts")
    review_keys = {(r["source"], r["source_rank"]) for r in first_rows if r["cleaning_status"] == "REVIEW"}
    if review_keys != {(r["source"], r["source_rank"]) for r in second_rows}:
        raise ValueError("Second-pass rows do not exactly cover first-pass REVIEW")


def validate_outputs(hwahae_fields, hwahae_rows, cleaned, purchase_keep, overlap):
    if [{k: row[k] for k in hwahae_fields} for row in cleaned] != hwahae_rows:
        raise ValueError("Hwahae Raw values or row order changed in cleaned output")
    if set(r["cleaning_status"] for r in cleaned) - set(HWAHAE_STATUSES):
        raise ValueError("Invalid Hwahae cleaning status")
    if sum(Counter(r["cleaning_status"] for r in cleaned).values()) != 100:
        raise ValueError("Hwahae cleaning status counts do not sum to 100")
    if len(purchase_keep) != 790:
        raise ValueError(f"Expected 790 confirmed purchase KEEP rows, got {len(purchase_keep)}")
    if any(r["effective_cleaning_status"] != "KEEP" for r in purchase_keep):
        raise ValueError("Purchase output contains a non-KEEP row")
    keep_count = sum(r["cleaning_status"] == "KEEP" for r in cleaned)
    if len(overlap) != keep_count:
        raise ValueError("Overlap rows do not exactly cover Hwahae KEEP")
    if set(r["overlap_status"] for r in overlap) - set(OVERLAP_STATUSES):
        raise ValueError("Invalid overlap status")
    if sum(Counter(r["overlap_status"] for r in overlap).values()) != keep_count:
        raise ValueError("Overlap status counts do not sum to Hwahae KEEP")

    purchase_by_ref = {(r["source"], r["source_rank"]): r for r in purchase_keep}
    for row in overlap:
        status = row["overlap_status"]
        if status == "NO_MATCH":
            if any(row[f] for f in (
                "matched_purchase_source", "matched_purchase_source_rank",
                "matched_purchase_product_id", "matched_purchase_product_name",
            )):
                raise ValueError("NO_MATCH row contains a purchase reference")
            continue
        ref = (row["matched_purchase_source"], row["matched_purchase_source_rank"])
        if ref not in purchase_by_ref:
            raise ValueError(f"Match does not reference confirmed purchase KEEP: {ref}")
        purchase = purchase_by_ref[ref]
        if row["matched_purchase_product_id"] != purchase["source_product_id"]:
            raise ValueError(f"Purchase product ID mismatch: {ref}")
        hw_conc = set(filter(None, row["hwahae_concentration"].split(";")))
        purchase_conc = concentrations(purchase["product_name_raw"])
        if hw_conc and purchase_conc and hw_conc != purchase_conc:
            raise ValueError(f"Concentration conflict in match: Hwahae rank {row['hwahae_rank']}")


def write_report(cleaned, purchase_keep, overlap, input_hashes):
    clean_counts = Counter(r["cleaning_status"] for r in cleaned)
    overlap_counts = Counter(r["overlap_status"] for r in overlap)
    keep_count = clean_counts["KEEP"]
    ratio = overlap_counts["MATCH"] / keep_count
    by_rank = {int(r["hwahae_rank"]): r for r in overlap}
    clean_by_rank = {int(r["source_rank"]): r for r in cleaned}

    lines = [
        "# 화해 TOP100과 구매 KEEP 제품 overlap", "",
        "화해 향수 TOP100을 상품명과 현재 로컬 근거만으로 최소 정제하고, 국내 판매 랭킹의 확정 KEEP 행과 브랜드·향수 정체성 기준으로 비교했다. 외부 요청, fuzzy threshold, SKU 통합, Fragrantica 매칭, 인기 점수 산출은 하지 않았다.", "",
        "## 측정 결과", "",
        "| 항목 | 건수 |", "|---|---:|",
        f"| 화해 KEEP | {clean_counts['KEEP']} |",
        f"| 화해 EXCLUDE_NON_PERFUME | {clean_counts['EXCLUDE_NON_PERFUME']} |",
        f"| 화해 REVIEW | {clean_counts['REVIEW']} |",
        f"| 구매 확정 KEEP | {len(purchase_keep)} |",
        f"| MATCH | {overlap_counts['MATCH']} |",
        f"| NO_MATCH | {overlap_counts['NO_MATCH']} |",
        f"| MATCH_REVIEW | {overlap_counts['MATCH_REVIEW']} |", "",
        f"엄격 overlap 비율은 `MATCH / 화해 KEEP` = `{overlap_counts['MATCH']} / {keep_count}` = **{ratio:.1%}**다. MATCH_REVIEW는 분자에서 제외했다.",
        f"구매 확정 KEEP {len(purchase_keep)}건은 판매상품 행 수다. SKU 또는 고유 향수 수로 통합하지 않았다.", "",
        "## 화해 최소 정제", "",
        "상품명에 피부용 일반 액상 향수로 볼 수 있는 향수·농도·코롱 표현이 있고 범위 밖 제형이 없으면 KEEP했다. 상품명만으로 제형을 확인할 수 없는 항목은 REVIEW로 유지했다.", "",
    ]
    for rank in sorted(REVIEW_RANKS):
        row = clean_by_rank[rank]
        lines.append(f"- REVIEW {rank}위 `{row['brand_raw']} / {row['product_name_raw']}`: {row['cleaning_reason']}")

    lines.extend(["", "## 대표 사례", "", "화해에만 확인된 대표 향수:", ""])
    for rank in (1, 2, 4, 8, 15, 26, 46, 53):
        row = by_rank[rank]
        lines.append(f"- {rank}위 `{row['hwahae_brand']} / {row['hwahae_product']}` — {row['overlap_status']}")
    lines.extend(["", "구매 데이터와 겹친 대표 향수:", ""])
    for rank in (6, 12, 19, 27, 52, 97):
        row = by_rank[rank]
        lines.append(
            f"- {rank}위 `{row['hwahae_brand']} / {row['hwahae_product']}` ↔ "
            f"`{row['matched_purchase_source']}:{row['matched_purchase_source_rank']} "
            f"{row['matched_purchase_product_name']}`"
        )
    lines.extend(["", "화해 추가로 보완되는 브랜드·제품 사례:", ""])
    for rank in (2, 4, 8, 15, 26, 46):
        row = by_rank[rank]
        lines.append(f"- `{row['hwahae_brand']}`: {row['hwahae_product']}")

    lines.extend(["", "## 매칭 원칙", "",
                  "- 비교용 값에서 대소문자, 공백, 용량, 명시적 판촉 문구를 정규화했지만 Raw 값은 별도 컬럼에 그대로 유지했다.",
                  "- 최종 연결은 snapshot-specific MATCHES에 명시한 확인된 행만 사용했다. 문자열 유사도나 fuzzy 임계값은 사용하지 않았다.",
                  "- 양쪽에 농도가 있으면 동일해야 한다. 한쪽 농도가 없거나 상품 정체성 표현이 축약된 2건은 MATCH_REVIEW로 남겼다.",
                  "- 구매의 MANUAL_CHECK와 그 밖의 비확정 행은 비교 대상과 매칭 참조에서 제외했다.", "",
                  "MATCH_REVIEW:", ""])
    for row in overlap:
        if row["overlap_status"] == "MATCH_REVIEW":
            lines.append(
                f"- 화해 {row['hwahae_rank']}위 `{row['hwahae_brand']} / {row['hwahae_product']}` ↔ "
                f"`{row['matched_purchase_source']}:{row['matched_purchase_source_rank']}` — {row['match_basis']}"
            )

    lines.extend(["", "## 검증", "",
                  "- 실행: `venv/Scripts/python.exe -B analyze_hwahae_purchase_overlap.py` (동일 명령 2회 실행).",
                  "- 화해 입력 100행, 순위 1~100 연속, source_product_id 100개 고유를 검사했다.",
                  "- 화해 Raw 모든 컬럼과 행 순서를 정제 CSV에 그대로 보존하고 상태 합계 100을 검사했다.",
                  "- 구매 1차 999행과 2차 128행을 다시 합성해 확정 KEEP 790행을 검사했다.",
                  f"- MATCH + NO_MATCH + MATCH_REVIEW = {overlap_counts['MATCH']} + {overlap_counts['NO_MATCH']} + {overlap_counts['MATCH_REVIEW']} = {keep_count}를 검사했다.",
                  "- 모든 MATCH/MATCH_REVIEW가 생성된 구매 KEEP CSV의 실제 source:rank와 product_id를 참조하는지 검사했다.",
                  "- 양쪽에 농도 표현이 있는 매칭에서 농도 집합이 같은지 검사해 EDP/EDT 등 충돌을 차단했다.",
                  "- 세 CSV를 다시 읽어 필드·값 round-trip 일치를 검사했다.",
                  "- 네 입력 파일의 고정 SHA256을 실행 전 확인하고, 실행 후 바이트가 동일한지 검사했다.", ""])
    for path, digest in input_hashes.items():
        lines.append(f"- `{path.name}`: `{digest}`")

    lines.extend(["", "## 남은 문제", "",
                  f"- 화해 REVIEW {clean_counts['REVIEW']}건은 상세 상품 정보 없이 일반 액상 향수 제형을 확정할 수 없다.",
                  f"- MATCH_REVIEW {overlap_counts['MATCH_REVIEW']}건은 농도 누락 1건과 축약된 제품 정체성 1건이다.",
                  "- 다음 단계 전에 REVIEW/MATCH_REVIEW의 상세 제품 근거를 확인할 수 있다. 이번 결과에서는 임의 해결하지 않았다.",
                  "- 구매 KEEP 790행은 SKU 통합 전 판매상품 행이므로 최종 고유 향수 수로 해석하면 안 된다.", ""])
    REPORT.write_text("\n".join(lines), encoding="utf-8")


def main():
    protected = {path: path.read_bytes() for path in EXPECTED_HASHES}
    input_hashes = {path: hashlib.sha256(data).hexdigest() for path, data in protected.items()}
    for path, expected in EXPECTED_HASHES.items():
        if input_hashes[path] != expected:
            raise ValueError(f"Snapshot changed; re-review decisions: {path.name}")

    hwahae_fields, hwahae_rows = read_csv(HWAHAE_RAW)
    first_fields, first_rows = read_csv(FIRST_PASS)
    _, second_rows = read_csv(SECOND_PASS)
    validate_inputs(hwahae_rows, first_rows, second_rows)

    cleaned = []
    for row in hwahae_rows:
        status, rule, reason, refs = classify_hwahae(row)
        cleaned.append(dict(row, cleaning_status=status, cleaning_rule=rule,
                            cleaning_reason=reason, local_evidence_refs=refs))

    purchase_keep = build_purchase_keep(first_rows, second_rows)
    purchase_by_ref = {(r["source"], int(r["source_rank"])): r for r in purchase_keep}

    overlap = []
    for row in cleaned:
        if row["cleaning_status"] != "KEEP":
            continue
        rank = int(row["source_rank"])
        hw_concentration = ";".join(sorted(concentrations(row["product_name_raw"])))
        result = {
            "hwahae_rank": row["source_rank"],
            "hwahae_source_product_id": row["source_product_id"],
            "hwahae_brand": row["brand_raw"],
            "hwahae_product": row["product_name_raw"],
            "hwahae_brand_normalized": normalize_brand(row["brand_raw"]),
            "hwahae_identity_normalized": normalize_identity(row["brand_raw"], row["product_name_raw"]),
            "hwahae_concentration": hw_concentration,
            "overlap_status": "NO_MATCH",
            "matched_purchase_source": "",
            "matched_purchase_source_rank": "",
            "matched_purchase_product_id": "",
            "matched_purchase_product_name": "",
            "match_basis": NO_MATCH_DETAILS.get(
                rank, "no conservative brand + identity match among confirmed purchase KEEP rows"
            ),
        }
        if rank in MATCHES:
            status, source, source_rank, basis = MATCHES[rank]
            purchase = purchase_by_ref.get((source, source_rank))
            if purchase is None:
                raise ValueError(f"Configured match is not confirmed purchase KEEP: {source}:{source_rank}")
            result.update(
                overlap_status=status,
                matched_purchase_source=source,
                matched_purchase_source_rank=str(source_rank),
                matched_purchase_product_id=purchase["source_product_id"],
                matched_purchase_product_name=purchase["product_name_raw"],
                match_basis=basis,
            )
        overlap.append(result)

    validate_outputs(hwahae_fields, hwahae_rows, cleaned, purchase_keep, overlap)

    clean_fields = hwahae_fields + ["cleaning_status", "cleaning_rule", "cleaning_reason", "local_evidence_refs"]
    purchase_fields = first_fields + ["effective_cleaning_status", "effective_status_basis"]
    overlap_fields = list(overlap[0])
    write_csv(HWAHAE_CLEAN, clean_fields, cleaned)
    write_csv(PURCHASE_KEEP, purchase_fields, purchase_keep)
    write_csv(OVERLAP, overlap_fields, overlap)
    write_report(cleaned, purchase_keep, overlap, input_hashes)

    if any(path.read_bytes() != data for path, data in protected.items()):
        raise ValueError("An input file changed during processing")

    print("hwahae_cleaning_status", dict(Counter(r["cleaning_status"] for r in cleaned)))
    print("purchase_confirmed_KEEP", len(purchase_keep))
    print("overlap_status", dict(Counter(r["overlap_status"] for r in overlap)))
    match_count = sum(r["overlap_status"] == "MATCH" for r in overlap)
    print(f"overlap_ratio MATCH/Hwahae_KEEP = {match_count}/{len(overlap)} = {match_count / len(overlap):.6f}")
    print("PASS: input hashes/bytes, row counts, ranks, IDs, references, concentrations, and CSV round trips")
    for path in (HWAHAE_CLEAN, PURCHASE_KEEP, OVERLAP, REPORT):
        print(path)


if __name__ == "__main__":
    main()

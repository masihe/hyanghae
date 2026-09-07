"""사람이 검토한 브랜드 리뷰 결과를 재사용 가능한 매핑 파일로 만든다 (Phase B1a).

Run with venv/Scripts/python.exe build_brand_mapping.py.

입력은 둘 다 읽기 전용이다.
  - 사람 검토본: fragrantica_unresolved_brand_review.xlsx ('내 검토 결과' 열)
  - 로컬 카탈로그: perfumes.csv (brand 열)

이 스크립트는 사람 판정을 바꾸지 않는다. MATCH로 승인된 항목만 옮기고,
그 브랜드가 로컬 perfumes.csv 스냅샷에 실제로 존재하는지만 별도 열로 기록한다.
NOT_IN_FRAGRANTICA 판정은 매핑으로 만들지 않는다.

카탈로그에 없는 것은 판정 오류가 아니라 '이 스냅샷에서는 쓸 수 없음'이다.
지우지 않고 NOT_IN_CATALOG로 남겨 다음 단계가 이유를 알 수 있게 한다.
"""
import hashlib
import sys
from pathlib import Path

import pandas as pd

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]  # MAP/
DATA = ROOT / "data/korea_popularity"
REVIEW = DATA / "evaluation/fragrantica_unresolved_brand_review.xlsx"
PERFUMES = ROOT / "perfumes.csv"
OUTPUT = DATA / "brand_mapping_reviewed.csv"

# 사람이 확정한 검토본. 리뷰가 갱신되면 다시 검토한 뒤 이 값을 갱신한다.
REVIEW_SHA256 = "d3f0dc6f1c77fa3284750a2ded7387c0ba804f51b445005f9c39b7090ebce999"
EXPECTED_REVIEW = {"MATCH": 32, "NOT_IN_FRAGRANTICA": 42}

SHEET = "Brand Review"
COL_BRAND = "국내 브랜드"
COL_CANDIDATE = "Fragrantica 후보"
COL_RESULT = "내 검토 결과"
COL_FIRST_PASS = "1차 비교 결과"
COL_ROWS = "상품 행 수"
COL_SOURCES = "출처"
COL_URL = "Fragrantica 근거 URL"
COL_NOTE = "메모"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def resolve_catalog(candidate: str, exact: set[str], lowered: dict[str, list[str]]) -> tuple[str, str]:
    """리뷰 값을 로컬 카탈로그 표기와 대조한다. 추측하지 않는다."""
    if candidate in exact:
        return candidate, "USABLE"
    hits = lowered.get(candidate.casefold(), [])
    if len(hits) == 1:
        # 같은 브랜드인데 표기 대소문자만 다른 경우. 카탈로그 표기를 정답으로 쓴다.
        return hits[0], "CASE_NORMALIZED"
    if len(hits) > 1:
        return "", "CATALOG_AMBIGUOUS"
    if "/" in candidate:
        # 리뷰 칸에 후보가 둘 이상 적혀 있어 하나로 확정할 수 없다.
        return "", "AMBIGUOUS_REVIEW_VALUE"
    return "", "NOT_IN_CATALOG"


def main() -> None:
    digest = sha256(REVIEW)
    if digest != REVIEW_SHA256:
        raise ValueError(
            f"검토본이 바뀌었다 ({digest}). 사람이 다시 검토한 뒤 REVIEW_SHA256을 갱신할 것")

    review = pd.read_excel(REVIEW, sheet_name=SHEET)
    counts = review[COL_RESULT].value_counts().to_dict()
    if counts != EXPECTED_REVIEW:
        raise ValueError(f"검토 결과 분포가 다르다: {counts} != {EXPECTED_REVIEW}")

    approved = review[review[COL_RESULT] == "MATCH"].copy()
    if approved[COL_BRAND].duplicated().any():
        raise ValueError("같은 국내 브랜드가 두 번 승인됐다")

    catalog = pd.read_csv(PERFUMES, usecols=["brand"])
    brand_counts = catalog.brand.dropna().value_counts()
    exact = set(brand_counts.index)
    lowered: dict[str, list[str]] = {}
    for name in exact:
        lowered.setdefault(name.casefold(), []).append(name)

    rows = []
    for _, r in approved.iterrows():
        candidate = str(r[COL_CANDIDATE]).strip()
        resolved, status = resolve_catalog(candidate, exact, lowered)
        rows.append({
            "korea_brand": str(r[COL_BRAND]).strip(),
            "fragrantica_brand": resolved,
            "catalog_status": status,
            "catalog_perfume_count": int(brand_counts[resolved]) if resolved else 0,
            "reviewed_candidate": candidate,
            "review_result": r[COL_RESULT],
            "first_pass_result": r[COL_FIRST_PASS],
            "product_row_count": int(r[COL_ROWS]),
            "sources": r[COL_SOURCES],
            "evidence_url": "" if pd.isna(r[COL_URL]) else r[COL_URL],
            "reviewer_note": "" if pd.isna(r[COL_NOTE]) else r[COL_NOTE],
            "review_file_sha256": digest,
        })

    out = pd.DataFrame(rows).sort_values(
        ["catalog_status", "product_row_count", "korea_brand"], ascending=[True, False, True])
    out.to_csv(OUTPUT, index=False, encoding="utf-8-sig")

    saved = pd.read_csv(OUTPUT, encoding="utf-8-sig", keep_default_na=False)
    if len(saved) != len(approved):
        raise ValueError("라운드트립에서 행 수가 달라졌다")

    print(f"검토본 {REVIEW.name} SHA-256 {digest}")
    print(f"검토 결과: {counts}")
    print(f"승인 매핑 {len(out)}건 (NOT_IN_FRAGRANTICA {counts['NOT_IN_FRAGRANTICA']}건은 매핑하지 않음)")
    print()
    print("카탈로그 대조:")
    for status, group in out.groupby("catalog_status"):
        print(f"  {status}: {len(group)}건 (상품 행 {int(group.product_row_count.sum())})")
        if status != "USABLE":
            for _, g in group.iterrows():
                print(f"    - {g.korea_brand} -> {g.reviewed_candidate} (상품 행 {g.product_row_count})")
    usable = out[out.catalog_status.isin(["USABLE", "CASE_NORMALIZED"])]
    print()
    print(f"실제 적용 가능: {len(usable)}건 / 후보 향수 합계 {int(usable.catalog_perfume_count.sum())}개")
    print(OUTPUT)


if __name__ == "__main__":
    main()

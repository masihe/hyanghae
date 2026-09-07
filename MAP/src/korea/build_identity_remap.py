"""브랜드 매핑 적용 시 바뀌는 Commercial Identity ID 대응표를 만든다 (9a-1).

Run with venv/Scripts/python.exe src/korea/build_identity_remap.py

`commercial_identity_id` 는 `latin_key(canonical_brand)` 를 해시 키의 첫 필드로 쓴다.
`latin_key("키엘")` 은 빈 문자열이고 `latin_key("Kiehl's")` 는 "kiehls" 라서,
사람이 검토한 브랜드 매핑을 반영하면 해당 identity 의 ID 가 바뀐다.

이 스크립트는 **산출물을 하나도 덮어쓰지 않는다.** 재매핑표만 새로 만든다.

방식: 프로덕션 함수 `make_identity_rows()` / `aggregate_commercial()` 을 그대로 두 번 호출한다.
한 번은 검토 매핑을 비운 상태(= 반영 직전), 한 번은 프로덕션 기본 상태로.
로직을 재구현하지 않는다.

먼저 기존 683개 ID 를 원본 스냅샷에서 재현하는지 확인한다(known-answer test).
재현이 안 되면 대응표를 신뢰할 수 없으므로 그 자리에서 멈춘다.
"""
import sys
from pathlib import Path

import pandas as pd

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_korea_popularity_map as m

ROOT = Path(__file__).resolve().parents[2]  # MAP/
DATA = ROOT / "data/korea_popularity"
MAPPING_PATH = DATA / "brand_mapping_reviewed.csv"
STORED_MEMBERS = DATA / "snapshot_pre_brand_mapping/korea_commercial_identity_members.csv"
STORED_COMMERCIAL = DATA / "snapshot_pre_brand_mapping/korea_commercial_identities.csv"
OUT_PATH = DATA / "identity_remap_brand_mapping.csv"

USABLE_STATUS = ("USABLE", "CASE_NORMALIZED")
# 실행 전에 못박은 기대값. 어긋나면 대응표의 성질이 달라진 것이므로 보고 대상이다.
EXPECTED = {"changed": 87, "merges": 0, "splits": 1, "incidental": 0}


def load_mapping() -> dict[str, str]:
    frame = pd.read_csv(MAPPING_PATH, encoding="utf-8-sig", keep_default_na=False)
    usable = frame[frame.catalog_status.isin(USABLE_STATUS)]
    return dict(zip(usable.korea_brand, usable.fragrantica_brand))


def raw_product_names(members: pd.DataFrame) -> pd.Series:
    """Gold Set 의 raw_product_names 와 같은 규칙 — 멤버 상품명을 순서 유지·중복 제거해 조인."""
    return members.groupby("commercial_identity_id", sort=False).product_name_raw.apply(
        lambda s: " | ".join(dict.fromkeys(s.astype(str))))


def verify_gold_rejoin(new_names: pd.Series) -> None:
    """Gold Set 을 수정하지 않고 raw_product_names 로 새 identity 에 다시 붙는지 확인한다 (9a-2).

    gold_set_test.csv 는 열지 않는다. gold_set_final.csv 는 TEST 행을 포함하지만
    정답 열(gold_*)을 usecols 로 제외해 읽어 TEST 정답을 보지 않는다.
    """
    lookup = {}
    for ci, names in new_names.items():
        lookup.setdefault(names, []).append(ci)

    cols = ["queue_id", "split", "commercial_identity_id", "raw_product_names",
            "concentration", "product_form"]
    for name in ("gold_set_dev.csv", "gold_set_final.csv"):
        gold = pd.read_csv(DATA / "evaluation" / name, encoding="utf-8-sig",
                           usecols=cols, keep_default_na=False)
        hits = gold.raw_product_names.map(lambda v: lookup.get(v, []))
        exact = hits.map(len).eq(1)
        print(f"  {name}: {len(gold)}행 | 새 identity 1개로 재조인 {int(exact.sum())}행 "
              f"| 미매칭 {int((hits.map(len) == 0).sum())} | 다중 {int((hits.map(len) > 1).sum())}")
        if not exact.all():
            bad = gold.loc[~exact, ["queue_id", "raw_product_names"]]
            print("    실패 행:", bad.to_dict("records")[:5])
            raise RuntimeError(f"{name} 재조인 실패")
        if "split" in gold:
            print(f"    split 분포: {dict(gold.split.value_counts())}")


def build(purchase, hwahae, brand_index, reviewed: dict[str, str]):
    """프로덕션 함수를 그대로 호출한다. 검토 매핑의 유무만 바꾼다.

    9a-3 으로 프로덕션이 `brand_mapping_reviewed.csv` 를 직접 읽게 됐으므로,
    "변경 전" 은 그 매핑을 비운 상태로 같은 코드를 돌려 재현한다.
    """
    saved = m.REVIEWED_BRAND_MAPPING
    m.REVIEWED_BRAND_MAPPING = reviewed
    try:
        members = m.make_identity_rows(purchase.copy(), hwahae.copy(), brand_index)
        return members, m.aggregate_commercial(members)
    finally:
        m.REVIEWED_BRAND_MAPPING = saved


def main() -> None:
    for path, expected in m.INPUT_HASHES.items():
        digest = m.sha256(path)
        if digest != expected:
            raise RuntimeError(f"입력 스냅샷이 바뀌었다: {path} ({digest})")
    print(f"입력 스냅샷 {len(m.INPUT_HASHES)}개 SHA-256 일치")

    purchase = pd.read_csv(m.PURCHASE_PATH)
    hwahae = pd.read_csv(m.HWAHAE_PATH)
    perfume_cols = ["id", "name", "brand", "year", "description", "accords"] + m.sm.NOTE_COLS
    perfumes = pd.read_csv(m.PERFUME_PATH, usecols=perfume_cols, low_memory=False)
    brand_index = {m.latin_key(x): x for x in perfumes.brand.dropna().unique() if m.latin_key(x)}

    # ---- known-answer test: 저장된 ID 를 그대로 재현하는가 ----
    # 검토 매핑을 비운 상태 = 브랜드 매핑 반영 직전 상태.
    members_old, commercial_old = build(purchase, hwahae, brand_index, {})
    stored_members = pd.read_csv(STORED_MEMBERS, keep_default_na=False)
    stored_commercial = pd.read_csv(STORED_COMMERCIAL, keep_default_na=False)
    assert len(members_old) == len(stored_members), \
        f"멤버 행 수 불일치 {len(members_old)} != {len(stored_members)}"
    key_cols = ["commercial_identity_id", "canonical_brand", "fragrance_name_normalized",
                "concentration", "product_form"]
    mismatch = int((members_old[key_cols].fillna("").astype(str).values
                    != stored_members[key_cols].fillna("").astype(str).values).any(axis=1).sum())
    if mismatch:
        raise RuntimeError(f"저장된 멤버를 재현하지 못했다: {mismatch}행 불일치")
    assert set(commercial_old.commercial_identity_id) == set(stored_commercial.commercial_identity_id)
    print(f"재현 확인: 멤버 {len(members_old)}행 / Commercial Identity {len(commercial_old)}개 "
          f"저장본과 일치 (origin {dict(members_old.origin.value_counts())})")

    mapping = load_mapping()
    overlap = sorted(set(mapping) & set(m.BRAND_ALIASES))
    print(f"검토 매핑 {len(mapping)}건 | 기존 BRAND_ALIASES 와 겹침 {len(overlap)}건 {overlap}")
    if overlap:
        raise RuntimeError("기존 alias 와 겹친다. 순수 가산이 아니므로 원인 분리가 불가능하다")
    assert mapping == m.REVIEWED_BRAND_MAPPING, (
        "프로덕션이 읽는 매핑과 다르다. 대응표가 파이프라인 상태를 대표하지 못한다")

    # ---- 매핑을 반영해 다시 계산 (프로덕션 기본 상태) ----
    members_new, commercial_new = build(purchase, hwahae, brand_index, mapping)
    print(f"매핑 적용 후: 멤버 {len(members_new)}행 / Commercial Identity {len(commercial_new)}개")

    old_names = raw_product_names(members_old)
    new_names = raw_product_names(members_new)
    old_brand = commercial_old.set_index("commercial_identity_id").canonical_brand
    new_brand = commercial_new.set_index("commercial_identity_id").canonical_brand
    old_family = commercial_old.set_index("commercial_identity_id").candidate_family_id
    new_family = commercial_new.set_index("commercial_identity_id").candidate_family_id

    # 멤버 단위로 old ci -> new ci 를 짝지어 identity 대응을 만든다 (행 순서가 보존된다)
    pairs = pd.DataFrame({
        "old_ci": members_old.commercial_identity_id.values,
        "new_ci": members_new.commercial_identity_id.values,
    }).drop_duplicates()

    rows = []
    for old_ci, group in pairs.groupby("old_ci", sort=False):
        for new_ci in group.new_ci:
            changed = old_ci != new_ci
            rows.append({
                "old_commercial_identity_id": old_ci,
                "new_commercial_identity_id": new_ci,
                "changed": changed,
                "old_canonical_brand": old_brand.get(old_ci, ""),
                "new_canonical_brand": new_brand.get(new_ci, ""),
                "old_candidate_family_id": old_family.get(old_ci, ""),
                "new_candidate_family_id": new_family.get(new_ci, ""),
                "old_raw_product_names": old_names.get(old_ci, ""),
                "new_raw_product_names": new_names.get(new_ci, ""),
                "change_reason": ("brand_mapping_reviewed" if changed else "unchanged"),
            })
    out = pd.DataFrame(rows)
    out.to_csv(OUT_PATH, index=False, encoding="utf-8-sig")

    # ---- 합격 기준 검증 ----
    changed = out[out.changed]
    changed_old = changed.old_commercial_identity_id.nunique()
    splits = int((changed.groupby("old_commercial_identity_id").size() > 1).sum())
    merges = int((out.groupby("new_commercial_identity_id").old_commercial_identity_id.nunique() > 1).sum())
    mapped_brands = set(mapping)
    incidental = int(changed[~changed.old_canonical_brand.isin(mapped_brands)]
                     .old_commercial_identity_id.nunique())
    measured = {"changed": changed_old, "merges": merges, "splits": splits, "incidental": incidental}
    print()
    print(f"대응표 {len(out)}행 -> {OUT_PATH.name}")
    print(f"  측정: {measured}")
    print(f"  기대: {EXPECTED}")
    if measured != EXPECTED:
        print("  ** 기대값과 다르다. 진행 전에 원인을 확인할 것 **")

    print(f"  신규 raw_product_names 전역 유일: "
          f"{new_names.nunique()} / {len(new_names)}")
    print(f"  브랜드가 바뀐 identity 의 브랜드 분포:")
    dist = changed.groupby("old_canonical_brand").old_commercial_identity_id.nunique().sort_values(ascending=False)
    print("   ", dict(dist))

    split_rows = changed.groupby("old_commercial_identity_id").filter(lambda g: len(g) > 1)
    if len(split_rows):
        print()
        print("  분할된 identity (기존 해시 충돌이 해소되는 건):")
        for _, r in split_rows.iterrows():
            print(f"    {r.old_commercial_identity_id} -> {r.new_commercial_identity_id}  "
                  f"{r.old_canonical_brand} -> {r.new_canonical_brand}  | {r.new_raw_product_names}")

    print()
    print("9a-2 Gold 재조인 검증 (Gold CSV 미수정, TEST 정답 열 미열람):")
    verify_gold_rejoin(new_names)

    for path, expected in m.INPUT_HASHES.items():
        assert m.sha256(path) == expected, f"입력이 변경됐다: {path}"
    print()
    print("입력 스냅샷 불변 재확인 완료. 기존 산출물은 하나도 쓰지 않았다")


if __name__ == "__main__":
    main()

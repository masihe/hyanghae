"""Verification 이 확정을 취소한 건을 사람 검토 큐로 뽑는다 (10d).

Run with venv/Scripts/python.exe src/matching/build_confirmation_review_queue.py [건수]

**왜 필요한가.** Verification(10b, 기준 E)은 DEV 에서 precision 을 0.8049 → 0.9200 으로
올렸지만, 취소된 89건 중 화해 순위 보유 향수가 15건이다. 그중 상당수는 눈으로 보면
맞는 매칭이다 — 예: 화해 30위 `CK One` 이 "기본명에 변형 40개" 로 취소됐는데
국내 이름이 정확히 "CK One" 이다. 규칙이 인기 상위 구간에서 뭉툭하다.

지도에 올라갈 향수는 인기 상위부터다. 그래서 **거절을 기본으로 두되(사용자 결정),
인기 순서대로 상한 건수만 사람에게 보여준다.**

이 스크립트는 **판정하지 않는다.** 후보와 증거, 왜 확정하지 못했는지를 정리해서 낸다.
사람이 채운 결과는 별도 파일로 받아 코드가 뒤집지 못하게 고정한다.
"""
import sys
from pathlib import Path

import pandas as pd

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "korea"))
import build_korea_popularity_map as matcher

ROOT = Path(__file__).resolve().parents[2]  # MAP/
DATA = ROOT / "data/korea_popularity"
OUT = DATA / "evaluation"
COMMERCIAL = DATA / "korea_commercial_identities_verified.csv"
MEMBERS = DATA / "korea_commercial_identity_members_verified.csv"
BEFORE = DATA / "korea_commercial_identities_llm300.csv"
QUEUE_CSV = OUT / "confirmation_review_queue.csv"
QUEUE_DOC = OUT / "confirmation_review_queue.md"

DEFAULT_LIMIT = 50  # 사용자 결정: 사람 검토는 50건 이하
DECISION_COLUMNS = ["human_decision", "human_fragrantica_id", "human_note"]


def load() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    after = pd.read_csv(COMMERCIAL, keep_default_na=False)
    before = pd.read_csv(BEFORE, keep_default_na=False).set_index("commercial_identity_id")
    members = pd.read_csv(MEMBERS, keep_default_na=False)
    perfumes = pd.read_csv(ROOT / "perfumes.csv",
                           usecols=["id", "name", "brand", "year", "description"],
                           low_memory=False, keep_default_na=False).set_index("id", drop=False)
    return after, before, members, perfumes


def catalog_name(perfumes: pd.DataFrame, value) -> str:
    try:
        row = perfumes.loc[int(float(value))]
    except (ValueError, TypeError, KeyError):
        return ""
    year = f" ({int(row.year)})" if str(row.year) not in ("", "nan") else ""
    return f"{row['name']}{year}"


def main() -> None:
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_LIMIT
    after, before, members, perfumes = load()

    refused = after[after.fragrantica_verification_refusal.astype(str) != ""].copy()
    assert len(refused), "취소된 건이 없다. Verification 이 켜진 산출물인지 확인할 것"
    # 취소된 건은 정의상 취소 전에 MATCH 였다 (verification_refusal 은 strong 일 때만 계산한다).
    was_match = before.loc[refused.commercial_identity_id, "fragrantica_match_status"]
    assert (was_match == "MATCH").all(), "취소 전 상태가 MATCH 가 아닌 건이 있다"

    refused["hwahae_rank"] = pd.to_numeric(refused.best_hwahae_rank, errors="coerce")
    refused["rrf"] = pd.to_numeric(refused.purchase_rrf_k60, errors="coerce").fillna(0.0) \
        if "purchase_rrf_k60" in refused else 0.0
    # 인기 순서 — 화해 순위 보유가 먼저, 그 안에서 순위 오름차순. 나머지는 구매 RRF 내림차순.
    refused["has_hwahae"] = refused.hwahae_rank.notna()
    ordered = refused.sort_values(["has_hwahae", "hwahae_rank", "rrf"],
                                  ascending=[False, True, False], na_position="last")

    print(f"취소된 확정 {len(refused)}건 | 화해 순위 보유 {int(refused.has_hwahae.sum())}건 "
          f"| 구매만 {int((~refused.has_hwahae).sum())}건")
    reasons = refused.fragrantica_verification_refusal.str.replace(
        r"base name with \d+ catalog variants", "base name with N variants", regex=True)
    print(f"취소 사유: {reasons.value_counts().to_dict()}")

    queue = ordered.head(limit).copy()
    raw = members.groupby("commercial_identity_id", sort=False).product_name_raw.apply(
        lambda s: " | ".join(dict.fromkeys(s.astype(str))))

    rows = []
    for i, r in enumerate(queue.itertuples(index=False), 1):
        prev_id = before.at[r.commercial_identity_id, "fragrantica_id"]
        cands = [c for c in str(r.fragrantica_candidate_ids).split("|") if c.strip()]
        rows.append({
            "review_order": i,
            "commercial_identity_id": r.commercial_identity_id,
            "hwahae_rank": "" if pd.isna(r.hwahae_rank) else int(r.hwahae_rank),
            "canonical_brand": r.canonical_brand,
            "fragrance_name_normalized": r.fragrance_name_normalized,
            "concentration": r.concentration,
            "product_form": r.product_form,
            "raw_product_names": raw.get(r.commercial_identity_id, ""),
            "refused_fragrantica_id": "" if str(prev_id) in ("", "nan") else int(float(prev_id)),
            "refused_candidate": catalog_name(perfumes, prev_id),
            "refusal_reason": r.fragrantica_verification_refusal,
            "match_score": r.fragrantica_match_score,
            "match_margin": r.fragrantica_match_margin,
            "candidate_ids": r.fragrantica_candidate_ids,
            "candidate_names": " | ".join(catalog_name(perfumes, c) for c in cands),
            **{c: "" for c in DECISION_COLUMNS},
        })
    out = pd.DataFrame(rows)
    assert out.commercial_identity_id.is_unique
    out.to_csv(QUEUE_CSV, index=False, encoding="utf-8-sig")

    lines = [
        "# 자동 확정 취소분 사람 검토 큐 (10d)",
        "",
        f"Verification(10b, 기준 E)이 확정을 취소한 **{len(refused)}건** 중 인기 상위 "
        f"**{len(out)}건**이다 (상한 {limit}건, 사용자 결정).",
        "",
        "## 왜 검토가 필요한가",
        "",
        "규칙은 DEV 에서 precision 을 0.8049 → 0.9200 으로 올렸다. 대신 정답 확정 10건을 함께 잃었고,",
        "취소된 89건에 **화해 순위 보유 향수 15건**이 들어 있다. 규칙이 인기 상위 구간에서 뭉툭하다.",
        "",
        "예: 화해 30위 `CK One` 이 \"기본명에 카탈로그 변형 40개\" 로 취소됐지만 국내 이름이 정확히 `CK One` 이다.",
        "",
        "## 판정 방법",
        "",
        f"`{QUEUE_CSV.name}` 의 빈 3열을 채운다.",
        "",
        "| 열 | 값 |",
        "|---|---|",
        "| `human_decision` | `CONFIRM` (취소를 되돌려 확정) / `REJECT` (지도에서 제외) / `OTHER` (다른 후보가 정답) |",
        "| `human_fragrantica_id` | `CONFIRM` 이면 비워도 된다(`refused_fragrantica_id` 를 쓴다). `OTHER` 면 정답 ID 를 적는다 |",
        "| `human_note` | 판단 근거. 나중에 규칙을 고칠 때 쓴다 |",
        "",
        "- **`candidate_names` 는 상위 5개뿐이다.** 정답이 그 밖에 있을 수 있다",
        "  (DEV 오확정 7건 중 5건은 정답이 8~22위였다). 확신이 없으면 `REJECT` 가 안전하다.",
        "- 사람이 확정한 결과는 코드가 뒤집지 못하게 고정한다. 되돌리지 않는다.",
        "",
        "## 취소 사유별 분포 (전체 89건)",
        "",
        "| 사유 | 건수 | 의미 |",
        "|---|---:|---|",
        f"| `phonetic key only` | {int((refused.fragrantica_verification_refusal == 'phonetic key only').sum())} "
        "| 모음을 지운 음성 키만으로 이겼다. `우먼`(woman)과 `Man` 이 같은 키가 되는 붕괴 |",
        f"| `base name with N catalog variants` | {int((refused.fragrantica_verification_refusal != 'phonetic key only').sum())} "
        "| 고른 이름을 접두사로 갖는 카탈로그 변형이 5개 이상이다 |",
        "",
        f"## 검토 대상 {len(out)}건",
        "",
        "| # | 화해 | 브랜드 | 국내 이름 | 농도 | 취소된 판정 | 취소 사유 |",
        "|---:|---:|---|---|---|---|---|",
    ]
    for r in out.itertuples(index=False):
        lines.append(f"| {r.review_order} | {r.hwahae_rank} | {r.canonical_brand} | "
                     f"{r.fragrance_name_normalized} | {r.concentration} | "
                     f"{r.refused_candidate} | {r.refusal_reason} |")
    lines += ["", "## 상품명 원문과 후보 목록", ""]
    for r in out.itertuples(index=False):
        lines += [
            f"**{r.review_order}. {r.canonical_brand} / {r.fragrance_name_normalized}** "
            f"({r.concentration}, {r.product_form}"
            + (f", 화해 {r.hwahae_rank}위" if r.hwahae_rank != "" else "") + ")",
            "",
            f"- 국내 상품명: {r.raw_product_names}",
            f"- 취소된 판정: `{r.refused_fragrantica_id}` {r.refused_candidate}",
            f"- 취소 사유: {r.refusal_reason} (score {r.match_score}, margin {r.match_margin})",
            f"- 후보 상위 5: {r.candidate_names}",
            "",
        ]
    QUEUE_DOC.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print()
    print(f"큐 {len(out)}건 (화해 보유 {int((out.hwahae_rank != '').sum())} / 구매만 "
          f"{int((out.hwahae_rank == '').sum())})")
    print(f"  -> {QUEUE_CSV.relative_to(ROOT)}")
    print(f"  -> {QUEUE_DOC.relative_to(ROOT)}")
    print()
    print(f"큐에 넣지 못한 취소분 {len(refused) - len(out)}건은 지도에서 제외된다 (사용자 결정: 거절이 기본).")


if __name__ == "__main__":
    main()

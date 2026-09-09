"""accord -> 향 계열 매핑 초안을 사람 검토용 CSV 로 낸다 (Phase 0-5).

Run with venv/Scripts/python.exe src/map/experiment_phase0_family_mapping.py

**왜 이 산출물인가.** 향 계열 영역 실험(Phase 3)과 영역 균형 실험(Phase 4) 전체가
"어떤 accord 를 어느 계열로 볼 것인가" 위에 서 있다. 그런데 Fragrantica 가 설명문에
넣어둔 계열은 Korea 200 에서 16개가 결측이고, 현재 좌표에서 2D 응집도가 0.387
(무작위 0.256, 1.5배)로 영역을 이루지 못한다. 그래서 accord 에서 계열을 만든다.

**계열 정의의 근거.** 9계열 중 7개는 Michael Edwards / Fragrances of the World 의
Fragrance Wheel 에 대응이 있다 (팀 검증본: EDA/data/scent_knowledge/source/
perfume_14families_korean_descriptors.md — 공식 휠 원문과 14개 명칭·순서 대조 확인).
**Gourmand 와 Musk 는 휠에 독립 계열이 없다.** 이 둘은 IFRA primary descriptor
(EDA/analysis_outputs/17_ifra_primary_descriptor_distribution.csv 에서 Gourmand 113건,
Musk Like 62건, Powdery 32건)에 근거해 추가한 것이며, **계열 수를 7/8/9 중 무엇으로
할지는 팀 결정 사항이다.** 이 파일은 9계열 안을 초안으로 제시한다.

**검토 범위.** accord 92종 전부에 제안을 붙이되, 판단이 실제로 갈리는 9종만
review_required=True 로 표시한다. 나머지 83종은 근거가 명확하거나(IFRA 정확 일치)
보유율이 무의미하게 낮다. 사람 검토를 92종 전수로 요구하면 Phase 3 가 막힌다.

**PROVISIONAL.** 검토 전 proposed_family 로 만든 결과는 PROVISIONAL 이다.
Phase 0 진단과 시각화는 계속 진행하되, Phase 3 의 최종 결정에는 검토본만 쓴다
(SCENT_MAP_EXPERIMENT_DESIGN_v4.md 8.2).

산출: experiments/phase0/family_mapping_draft.csv
"""
import hashlib
import json
import os
import sys

import pandas as pd

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "common")))
import scent_map as sm  # noqa: F401  (경로 상수·규약 공유용)

OUT_DIR = os.path.join("experiments", "phase0")
OUT_CSV = os.path.join(OUT_DIR, "family_mapping_draft.csv")
OUT_JSON = os.path.join(OUT_DIR, "family_mapping_draft_meta.json")
ACCORD_DICT = os.path.join("..", "EDA", "analysis_outputs", "10_accord_dictionary.csv")
IFRA_MATCH = os.path.join("..", "EDA", "analysis_outputs", "17_accord_ifra_matching.csv")
IFRA_ALIAS = os.path.join("..", "EDA", "analysis_outputs", "17_ifra_alias_candidates.csv")

MAPPING_VERSION = "draft-1"

# --------------------------------------------------------------------------
# 계열 정의 — 7개는 휠, 2개는 IFRA primary descriptor
# --------------------------------------------------------------------------
FAMILY_DEF = {
    "CITRUS": ("시트러스", "WHEEL", "Fragrance Wheel: Citrus"),
    "FRUITY": ("프루티", "WHEEL", "Fragrance Wheel: Fruity"),
    "FLORAL": ("플로럴", "WHEEL", "Fragrance Wheel: Floral / Soft Floral"),
    "GREEN": ("그린·아로마틱", "WHEEL", "Fragrance Wheel: Green / Aromatic Fougere"),
    "AQUATIC": ("아쿠아틱", "WHEEL", "Fragrance Wheel: Water"),
    "WOODY": ("우디", "WHEEL", "Fragrance Wheel: Woods / Mossy Woods / Dry Woods"),
    "AMBER": ("앰버·스파이시", "WHEEL", "Fragrance Wheel: Amber / Soft Amber / Woody Amber"),
    "GOURMAND": ("구르망", "IFRA", "휠에 없음. IFRA primary descriptor Gourmand (113건)"),
    "MUSK": ("머스크·파우더리", "IFRA", "휠에 없음. IFRA primary Musk Like(62) / Powdery(32)"),
}
FAMILY_ORDER = list(FAMILY_DEF)
UNMAPPED = "UNMAPPED"

# 판단이 갈리는 9종. Phase 0 의 사람 검토 대상은 여기까지다.
AMBIGUOUS = {
    "powdery": ("FLORAL", "보유율 47.7% 로 배경에 가깝다. 계열로 쓸지 자체가 쟁점"),
    "vanilla": ("AMBER", "휠에서는 Amber 축의 대표 원료. 국내 인식은 구르망 쪽"),
    "fresh": ("AQUATIC|GREEN", "어느 축의 신선함인지 데이터가 구분하지 않는다"),
    "leather": ("AMBER", "휠 Dry Woods 가 가죽을 포함하지만 상업 분류는 Amber 쪽이 많다"),
    "iris": ("MUSK", "식물학적으로는 꽃이지만 향 인상은 파우더리"),
    "smoky": ("AMBER", "Dry Woods 축과 인센스(Amber) 축 양쪽에 걸린다"),
    "lactonic": ("FLORAL", "우유·크림 인상이지만 흰꽃의 락톤에서도 나온다"),
    "aldehydic": ("CITRUS", "IFRA secondary->primary 분포가 Green 38 / Floral 25 / Citrus 17% 로 흩어진다"),
    "honey": ("AMBER", "단맛 축이지만 휠에서는 Amber 쪽 원료"),
}

# accord -> (제안 계열, 근거). 보유율과 IFRA 대응은 CSV 를 만들 때 붙인다.
ACCORD_FAMILY = {
    "woody": ("WOODY", "IFRA PRIMARY Woody 정확 일치. 휠 Woods 직결"),
    "powdery": ("MUSK", "IFRA PRIMARY Powdery. 휠에는 없는 축"),
    "sweet": ("GOURMAND", "IFRA SECONDARY Sweet. 단맛 인상"),
    "citrus": ("CITRUS", "IFRA PRIMARY Citrus 정확 일치. 휠 Citrus"),
    "aromatic": ("GREEN", "IFRA PRIMARY Aromatic. 휠 Aromatic Fougere"),
    "fresh spicy": ("AMBER", "향신료 축. 휠 Amber 계열의 spicy 성분"),
    "floral": ("FLORAL", "IFRA PRIMARY Floral 정확 일치. 휠 Floral"),
    "amber": ("AMBER", "IFRA PRIMARY Amber 정확 일치. 휠 Amber(구 Oriental)"),
    "warm spicy": ("AMBER", "따뜻한 향신료. 휠 Amber 축"),
    "fruity": ("FRUITY", "IFRA PRIMARY Fruity 정확 일치. 휠 Fruity"),
    "musky": ("MUSK", "IFRA alias 후보 Musk Like (17_ifra_alias_candidates)"),
    "white floral": ("FLORAL", "흰꽃 계열. 휠 Floral 하위"),
    "vanilla": ("GOURMAND", "IFRA SECONDARY Vanilla"),
    "fresh": ("CITRUS", "IFRA SECONDARY Fresh"),
    "green": ("GREEN", "IFRA PRIMARY Green 정확 일치. 휠 Green"),
    "rose": ("FLORAL", "IFRA SECONDARY Rose"),
    "earthy": ("WOODY", "IFRA PRIMARY Earthy. 휠 Mossy Woods 축"),
    "animalic": ("MUSK", "IFRA alias 후보 Animal Like"),
    "balsamic": ("AMBER", "IFRA PRIMARY Balsamic. 수지성 = Amber 축"),
    "patchouli": ("WOODY", "IFRA SECONDARY Patchouli. 휠 Mossy Woods 대표 원료"),
    "soft spicy": ("AMBER", "부드러운 향신료. 휠 Soft Amber 축"),
    "leather": ("WOODY", "휠 Dry Woods 가 가죽 노트를 포함"),
    "aquatic": ("AQUATIC", "휠 Water"),
    "herbal": ("GREEN", "IFRA PRIMARY Herbal"),
    "lavender": ("GREEN", "IFRA SECONDARY Lavender. 휠 Aromatic Fougere 대표 원료"),
    "oud": ("WOODY", "IFRA alias 후보 Agarwood. 목질"),
    "violet": ("FLORAL", "IFRA SECONDARY Violet"),
    "iris": ("FLORAL", "IFRA SECONDARY Iris"),
    "smoky": ("WOODY", "IFRA PRIMARY Smoky. 휠 Dry Woods 축"),
    "lactonic": ("GOURMAND", "IFRA SECONDARY Lactonic. 우유·크림 인상"),
    "yellow floral": ("FLORAL", "노란꽃 계열. 휠 Floral 하위"),
    "tropical": ("FRUITY", "열대 과일 인상"),
    "mossy": ("WOODY", "IFRA SECONDARY Mossy. 휠 Mossy Woods 직결"),
    "ozonic": ("AQUATIC", "IFRA PRIMARY Ozonic. 휠 Water 축"),
    "tobacco": ("AMBER", "IFRA SECONDARY Tobacco. 휠 Amber 축"),
    "marine": ("AQUATIC", "IFRA PRIMARY Marine. 휠 Water"),
    "cinnamon": ("AMBER", "IFRA SECONDARY Cinnamon"),
    "caramel": ("GOURMAND", "IFRA SECONDARY Caramel"),
    "tuberose": ("FLORAL", "IFRA SECONDARY Tuberose"),
    "nutty": ("GOURMAND", "IFRA SECONDARY Nutty"),
    "aldehydic": ("MUSK", "IFRA PRIMARY Aldehydic"),
    "honey": ("GOURMAND", "IFRA PRIMARY Honey"),
    "almond": ("GOURMAND", "IFRA SECONDARY Almond"),
    "coconut": ("GOURMAND", "IFRA SECONDARY Coconut"),
    "salty": ("AQUATIC", "해양 인상"),
    "metallic": ("MUSK", "IFRA SECONDARY Metallic. 무기질 인상"),
    "cacao": ("GOURMAND", "카카오"),
    "sour": ("CITRUS", "IFRA SECONDARY Sour. 산미"),
    "conifer": ("GREEN", "침엽수. 휠 Green / Aromatic 축"),
    "coffee": ("GOURMAND", "IFRA SECONDARY Coffee"),
    "cherry": ("FRUITY", "IFRA SECONDARY Cherry"),
    "soapy": ("MUSK", "IFRA SECONDARY Soapy. 청결·파우더리 축"),
    "chocolate": ("GOURMAND", "IFRA SECONDARY Chocolate"),
    "anis": ("GREEN", "IFRA PRIMARY Anisic. 허브 축"),
    "rum": ("AMBER", "주정·수지 인상"),
    "bitter": ("CITRUS", "IFRA SECONDARY Bitter. 감귤 껍질의 쓴맛"),
    "whiskey": ("AMBER", "주정 인상"),
    "camphor": ("GREEN", "IFRA PRIMARY Camphoraceous"),
    "mineral": ("AQUATIC", "무기질·바위 인상"),
    "savory": ("GREEN", "허브·향신 축"),
    "terpenic": ("CITRUS", "IFRA SECONDARY Terpenic. 감귤 껍질 테르펜"),
    "cannabis": ("GREEN", "허브 축"),
    "beeswax": ("AMBER", "밀랍. 수지 축"),
    "Champagne": ("FRUITY", "발포 과실 인상"),
    "wine": ("FRUITY", "IFRA SECONDARY Wine"),
    "sand": ("AQUATIC", "해변 인상"),
    "alcohol": ("GOURMAND", "주정"),
    "gourmand": ("GOURMAND", "IFRA PRIMARY Gourmand 정확 일치"),
    "oily": ("GOURMAND", "IFRA SECONDARY Oily"),
    "coca-cola": ("FRUITY", "감귤·향신 발포 인상"),
    "vodka": ("GOURMAND", "주정"),
    "paper": ("WOODY", "종이 = 목질 파생"),
    "clay": ("WOODY", "흙·점토"),
    "milky": ("GOURMAND", "IFRA SECONDARY Milky"),
    "sake": ("GOURMAND", "주정"),
    "spice": ("AMBER", "향신료 총칭"),
    "bacon": ("GOURMAND", "훈연 식품 인상. IFRA Food Like 축"),
    "Pear": ("FRUITY", "IFRA SECONDARY Pear"),
    "meat": ("GOURMAND", "식품 인상. IFRA Food Like 축"),
    "bbq": ("GOURMAND", "훈연 식품 인상"),
    "foresty": ("WOODY", "숲 인상"),
    # 향 계열로 볼 근거가 없는 것 — 보유율 0.0% 대. 계열을 만들지 않는다.
    "plastic": (UNMAPPED, "향 계열로 볼 근거 없음"),
    "vinyl": (UNMAPPED, "향 계열로 볼 근거 없음"),
    "asphault": (UNMAPPED, "향 계열로 볼 근거 없음"),
    "gasoline": (UNMAPPED, "향 계열로 볼 근거 없음"),
    "rubber": (UNMAPPED, "향 계열로 볼 근거 없음"),
    "industrial glue": (UNMAPPED, "향 계열로 볼 근거 없음"),
    "hot iron": (UNMAPPED, "향 계열로 볼 근거 없음"),
    "varnish": (UNMAPPED, "향 계열로 볼 근거 없음"),
    "tennis ball": (UNMAPPED, "향 계열로 볼 근거 없음"),
    "wet plaster": (UNMAPPED, "향 계열로 볼 근거 없음"),
    "brown scotch tape": (UNMAPPED, "향 계열로 볼 근거 없음"),
}


def mapping_digest() -> str:
    """매핑 내용만으로 해시를 만든다. 하위 실험이 이 값으로 매핑 버전을 고정한다."""
    payload = json.dumps({k: v[0] for k, v in sorted(ACCORD_FAMILY.items())},
                         ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_frame() -> pd.DataFrame:
    acc = pd.read_csv(ACCORD_DICT)
    ifra = pd.read_csv(IFRA_MATCH).set_index("accord")
    alias = pd.read_csv(IFRA_ALIAS)
    alias = alias[alias.feature_type == "accord"]
    alias_map = dict(zip(alias.fragrantica_feature, alias.ifra_candidate))

    missing = sorted(set(acc.accord) - set(ACCORD_FAMILY))
    extra = sorted(set(ACCORD_FAMILY) - set(acc.accord))
    print(f"accord 사전 {len(acc)}종 / 매핑 정의 {len(ACCORD_FAMILY)}종")
    print(f"  사전에 있는데 매핑에 없는 것: {missing if missing else '없음'}")
    print(f"  매핑에 있는데 사전에 없는 것: {extra if extra else '없음'}")
    assert not missing, "accord 사전의 모든 accord 에 제안이 있어야 한다"
    assert not extra, "사전에 없는 accord 를 매핑에 두지 않는다"

    rows = []
    for r in acc.itertuples(index=False):
        fam, rationale = ACCORD_FAMILY[r.accord]
        term = level = ""
        if r.accord in ifra.index:
            info = ifra.loc[r.accord]
            term = "" if pd.isna(info.matched_ifra_term) else str(info.matched_ifra_term)
            level = "" if pd.isna(info.matched_ifra_level) else str(info.matched_ifra_level)
        if not term and r.accord in alias_map:
            term, level = alias_map[r.accord], "ALIAS_CANDIDATE"
        review = r.accord in AMBIGUOUS
        rows.append({
            "accord": r.accord,
            "perfume_share": round(float(r.perfume_share), 4),
            "perfume_count": int(r.perfume_count),
            "ifra_term": term,
            "ifra_level": level,
            "proposed_family": fam,
            "proposed_family_ko": FAMILY_DEF[fam][0] if fam in FAMILY_DEF else "",
            "family_basis": FAMILY_DEF[fam][1] if fam in FAMILY_DEF else "NONE",
            "rationale": rationale,
            "review_required": review,
            "alt_families": AMBIGUOUS[r.accord][0] if review else "",
            "review_reason": AMBIGUOUS[r.accord][1] if review else "",
            "human_decision": "",   # CONFIRM / REJECT / OTHER
            "human_family": "",
            "human_note": "",
        })
    return pd.DataFrame(rows).sort_values("perfume_share", ascending=False)


def main() -> None:
    os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))  # MAP/
    os.makedirs(OUT_DIR, exist_ok=True)

    print("=" * 78)
    print("Phase 0-5 — accord -> 향 계열 매핑 초안 (PROVISIONAL)")
    print("=" * 78)
    frame = build_frame()
    frame.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")

    print()
    print("계열별 accord 수 (제안 기준)")
    counts = frame.proposed_family.value_counts()
    for fam in FAMILY_ORDER + [UNMAPPED]:
        n = int(counts.get(fam, 0))
        share = frame.loc[frame.proposed_family == fam, "perfume_share"].sum()
        ko = FAMILY_DEF[fam][0] if fam in FAMILY_DEF else "(매핑 없음)"
        basis = FAMILY_DEF[fam][1] if fam in FAMILY_DEF else "-"
        print(f"  {ko:<14} {basis:<6} accord {n:>2}종  보유율 합 {share:.2f}")

    print()
    print(f"사람 검토 대상 {int(frame.review_required.sum())}종")
    for r in frame[frame.review_required].itertuples(index=False):
        print(f"  {r.accord:<11} 보유율 {r.perfume_share:.3f}  제안 {r.proposed_family_ko}"
              f" <-> {r.alt_families}")
        print(f"  {'':11} {r.review_reason}")

    unmapped_share = frame.loc[frame.proposed_family == UNMAPPED, "perfume_share"].sum()
    print()
    print(f"매핑 없음 {int((frame.proposed_family == UNMAPPED).sum())}종 "
          f"(보유율 합 {unmapped_share:.4f})")

    digest = mapping_digest()
    meta = {
        "mapping_version": MAPPING_VERSION,
        "status": "PROVISIONAL",
        "mapping_sha256": digest,
        "family_count": len(FAMILY_DEF),
        "families": {k: {"ko": v[0], "basis": v[1], "source": v[2]}
                     for k, v in FAMILY_DEF.items()},
        "accord_total": int(len(frame)),
        "review_required": int(frame.review_required.sum()),
        "unmapped": int((frame.proposed_family == UNMAPPED).sum()),
        "unmapped_share_sum": round(float(unmapped_share), 4),
        "note": ("Gourmand 와 Musk 는 Fragrance Wheel 에 독립 계열이 없고 IFRA primary "
                 "descriptor 에 근거해 추가했다. 계열 수 7/8/9 는 팀 결정 사항이다."),
    }
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
        f.write("\n")

    print()
    print(f"매핑 해시 {digest[:16]}... (mapping_version={MAPPING_VERSION}, PROVISIONAL)")
    print(f"  -> {OUT_CSV}")
    print(f"  -> {OUT_JSON}")


if __name__ == "__main__":
    main()

"""사전 확장 우선순위를 accord 단위로 계산한다.

    ./venv/Scripts/python.exe 42_lexicon_expansion_priority.py [사전.csv]

왜 accord 단위인가 — 계열(family)로 재면 평가셋의 계열 이름(Fragrantica)과 팀 문서의
계열 체계(Fragrance Wheel 14개)가 달라 연결되지 않는다. accord 는 양쪽이 공유한다.

방법
  합성 평가셋 600건 중 향 조건을 하나도 못 뽑은 쿼리를 찾고,
  그 쿼리의 정답 향수가 가진 조건 accord 를 센다.
  = "사전이 이 accord 로 가는 길을 못 만들고 있다"

결핍을 두 종류로 나눈다
  REACHABLE_BUT_MISSED  사전이 그 accord 에 닿을 수 있는데도 실패 — 표현이 부족하다
  UNREACHABLE           어떤 한국어 표현으로도 그 accord 에 닿을 수 없다 — 항목이 없다

그리고 "고칠 수 있는 결핍인가" 를 함께 잰다 (v1.6 작업에서 amber 로 확인한 것)

  기대_영향권   그 accord 의 한국어 후보 표현이 평가셋 600건 중 몇 문장에 나오는가
  확장_가능성   NO_SECTION_MAPPED  팀 문서에 이 accord 를 직접 다루는 절이 없다
                KO_UNSPECIFIABLE   절은 있으나 판별력 있는 표현이 평가셋에 0건
                LOW(30 미만) / MID(100 미만) / HIGH

**장이 아니라 절 단위로 후보를 뽑는다.** 장 단위로 하면 그 계열의 모든 표현이 딸려온다 —
Amber 장의 `달콤한 꽃향`·`밤에 핀 꽃` 은 앰버를 가리키는 말이 아니다. 팀 문서에는
`앰버 쪽이 앞설 때`·`불/연기 표현`·`가죽 표현` 처럼 accord 를 직접 가리키는 절이 있다.

실측 — 효과 크기는 기대_영향권을 따라간다
  나무 195건 -> NDCG +0.0205 · 하얀 꽃 39건 -> +0.0066 · 분내 28건 -> +0.0047

출력  analysis_outputs/42_lexicon_expansion_priority.csv
"""
import sys
import json
import ast
import collections
import pathlib
import re
import unicodedata

import pandas as pd

sys.path.insert(0, "C:/Users/SSAFY/Desktop/S15P21E203/ai")
from nlr_engine import load_index, recommend, KOREAN_ACCORD

DEFAULT_LEXICON = "data/scent_knowledge/domain_lexicon_v1_6.csv"
OUT = pathlib.Path("analysis_outputs/42_lexicon_expansion_priority.csv")
SRC_DOC = "data/scent_knowledge/source/perfume_14families_korean_descriptors.md"
MIN_CORPUS = 500   # 이보다 적으면 조합 검색에서 0 이 되기 쉽다 (spec 4.3 규칙 2)
MAX_FAMILIES = 2   # 팀 문서에서 이보다 많은 계열에 나오면 판별력이 없다고 본다

# accord -> 그 accord 를 직접 가리키는 팀 문서의 (장 앞부분, 절 일부).
# **사람이 만든 표이고 사람이 검토해야 한다.** 여기 없는 accord 는 NO_SECTION_MAPPED 로
# 나오는데, 그것도 정보다 — 팀 문서가 그 accord 를 따로 다루지 않는다는 뜻이다.
ACCORD_SECTIONS = {
    "white floral": [("Floral", "화이트 플로럴")],
    "aldehydic": [("Soft Floral", "알데하이드")],
    "musky": [("Soft Floral", "머스크/아이리스")],
    "powdery": [("Soft Floral", "머스크/아이리스"), ("Soft Floral", "질감 표현")],
    "amber": [("Floral Amber", "앰버 쪽이"), ("Woody Amber", "앰버가 강할"),
              ("Amber", "드라이 앰버")],
    "vanilla": [("Soft Amber", "바닐라/통카")],
    "sweet": [("Amber", "당도 표현")],
    "smoky": [("Dry Woods", "불/연기"), ("Soft Amber", "인센스")],
    "leather": [("Dry Woods", "가죽")],
    "tobacco": [("Dry Woods", "담배")],
    # 장 이름이 곧 accord 인 경우에만 `핵심 형용사` 를 넣는다. Amber 장의 핵심 형용사는
    # `농밀한`·`진득한` 처럼 밀도 표현이라 앰버를 가리키지 않으므로 넣지 않았다.
    "woody": [("Woods", "핵심 형용사"), ("Woods", "목재 질감"), ("Woods", "샌달우드"),
              ("Woods", "베티버/시더"), ("Woody Amber", "우드가 강할")],
    "mossy": [("Mossy Woods", "오크모스")],
    "earthy": [("Mossy Woods", "습도 표현")],
    "lavender": [("Aromatic Foug", "라벤더")],
    "aromatic": [("Aromatic Foug", "모던 푸제르"), ("Aromatic Foug", "클래식 푸제르")],
    "marine": [("Water", "바다/마린")],
    "ozonic": [("Water", "오존/메탈릭")],
    "aquatic": [("Water", "깨끗한 워터"), ("Water", "칼론")],
    "citrus": [("Citrus", "핵심 형용사"), ("Citrus", "과즙"), ("Citrus", "껍질"), ("Citrus", "레몬/라임"),
               ("Citrus", "오렌지/만다린"), ("Citrus", "베르가못")],
    "fruity": [("Fruity", "핵심 형용사"), ("Fruity", "과육")],
    "green": [("Green", "핵심 형용사"), ("Green", "생풀/잎"), ("Green", "갈바넘")],
}

_STRIP = re.compile(r"[*`\u2705\u26a0\u26d4]")


def team_doc_expressions():
    """팀 문서를 (장, 절, 표현) 으로 읽는다. (list[tuple], Counter).

    두 번째 값은 표현별 등장 계열 수다. 작을수록 판별력이 높다 —
    팀 문서가 "달달한·포근한 같은 단어는 패밀리를 단독 판별하지 않는다" 고 적어뒀다.
    """
    text = pathlib.Path(SRC_DOC).read_text(encoding="utf-8")
    family = section = None
    rows = []
    for line in text.splitlines():
        line = line.strip()
        m = re.match(r"^#\s+\d+\.\s*(.+)$", line)
        if m:
            family, section = m.group(1).strip(), None
            continue
        m = re.match(r"^#{2,3}\s+(.+)$", line)
        if m:
            section = m.group(1).strip()
            continue
        if not family or not section or "출처" in section:
            continue
        if line.startswith("- "):
            items = [line[2:]]
        elif line and not line.startswith(("#", ">", "|", "*")):
            items = line.split(",")
        else:
            items = []
        for item in items:
            item = unicodedata.normalize("NFC", _STRIP.sub("", item)).strip()
            if 2 <= len(item) <= 20 and re.search(r"[가-힣]", item):
                rows.append((family, section, item))
    counts = collections.Counter()
    for expr in {e for _, _, e in rows}:
        counts[expr] = len({f for f, _, e in rows if e == expr})
    return rows, counts


# 별칭을 쓸 때 사람이 실제로 떼는 꼬리말. `살냄새 같은` -> `살냄새`
_TAILS = (" 같은", " 나는", " 있는", " 드는", " 어린", " 섞인", " 감도는", " 밴")


def alias_forms(expr):
    """표현 하나에서 별칭으로 쓸 형태들. set[str].

    팀 문서는 `분내 나는`·`살냄새 같은` 처럼 구로 적혀 있는데 실제 문장에는
    `살냄새 나는` 으로 나온다. 사람이 별칭을 쓸 때 하는 것과 같은 처리를 한다.
    """
    forms = {expr}
    for tail in _TAILS:
        if expr.endswith(tail) and len(expr) - len(tail) >= 2:
            forms.add(expr[: -len(tail)].strip())
    return {f for f in forms if len(f) >= 2}


def korean_candidates(accord, doc_rows, fam_counts):
    """그 accord 를 직접 다루는 절에서 판별력 있는 표현을 뽑는다. list[str]."""
    targets = ACCORD_SECTIONS.get(accord, [])
    if not targets:
        return []
    picked = set()
    for fam, sec, e in doc_rows:
        if fam_counts[e] > MAX_FAMILIES:
            continue
        if any(fam.startswith(c) and s in sec for c, s in targets):
            picked |= alias_forms(e)
    return sorted(picked)


def reachable_accords(lexicon_path):
    """지금 사전과 한글 표기로 닿을 수 있는 accord. set[str]."""
    lex = pd.read_csv(lexicon_path, keep_default_na=False, dtype=str)
    hit = set(lex[(lex["candidate_type"] == "ACCORD")
                  & (lex["target_field"] != "NO_MAPPING")]["candidate_name"])
    return hit | set(KOREAN_ACCORD.values())


def classify(candidates, reach_n):
    """확장 가능성 라벨. str."""
    if not candidates:
        return "NO_SECTION_MAPPED"
    if reach_n == 0:
        return "KO_UNSPECIFIABLE"
    if reach_n < 30:
        return "LOW"
    if reach_n < 100:
        return "MID"
    return "HIGH"


def parse_conditions(raw):
    """체크포인트의 parsed 칸을 dict 로. dict 또는 None."""
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        return json.loads(raw)
    except Exception:
        try:
            return ast.literal_eval(raw)
        except Exception:
            return None


def main():
    lexicon = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_LEXICON
    key = pd.read_csv("analysis_outputs/32_evalset_answer_key.csv").set_index("perfume_id")
    ck = pd.read_csv("analysis_outputs/34_evalset_stage1_checkpoint.csv")
    index = load_index(lexicon_csv=lexicon)
    reach = reachable_accords(lexicon)
    doc_rows, fam_counts = team_doc_expressions()

    blobs = []
    missed, total = collections.Counter(), collections.Counter()
    for r in ck.to_dict("records"):
        conditions = parse_conditions(r["parsed"])
        extra = " ".join(str(e) for e
                         in ((conditions or {}).get("additional_requirements") or []))
        blobs.append(unicodedata.normalize("NFC", str(r["sentence"]) + " " + extra))
        C = [a for a in str(key.loc[r["perfume_id"], "C"]).split("|") if a in index["aidx"]]
        for a in C:
            total[a] += 1
        if recommend(index, r["sentence"], conditions)["status"] == "NO_CONDITION":
            for a in C:
                missed[a] += 1

    rows = []
    for a in total:
        corpus = int(index["has"][:, index["aidx"][a]].sum())
        cands = korean_candidates(a, doc_rows, fam_counts)
        reach_n = sum(1 for b in blobs if any(c in b for c in cands)) if cands else 0
        rows.append({
            "accord": a,
            "결핍유형": "REACHABLE_BUT_MISSED" if a in reach else "UNREACHABLE",
            "조건0건에_등장": missed[a],
            "전체_등장": total[a],
            "실패율": round(missed[a] / total[a], 3),
            "코퍼스_보유": corpus,
            "검색가능": corpus >= MIN_CORPUS,
            "기대_영향권": reach_n,
            "확장_가능성": classify(cands, reach_n),
            "한국어_후보수": len(cands),
        })
    d = pd.DataFrame(rows).sort_values(["결핍유형", "기대_영향권"], ascending=[True, False])
    d.to_csv(OUT, index=False, encoding="utf-8")

    print(f"사전 {pathlib.Path(lexicon).name} · 닿는 accord {len(reach)}종 / 92종")
    print(f"저장: {OUT}  ({len(d)}행)\n")
    for kind in ("UNREACHABLE", "REACHABLE_BUT_MISSED"):
        sel = d[(d["결핍유형"] == kind) & d["검색가능"] & (d["조건0건에_등장"] > 0)]
        print(f"[{kind}] 검색 가능하고 실패 이력이 있는 accord {len(sel)}종 — 기대_영향권 순")
        print(sel.head(8).to_string(index=False), "\n")

    for label, note in (("KO_UNSPECIFIABLE", "절은 있으나 그 표현이 평가셋에 0건"),
                        ("NO_SECTION_MAPPED", "팀 문서에 이 accord 를 다루는 절이 없다")):
        blocked = d[(d["확장_가능성"] == label) & (d["조건0건에_등장"] > 0)]
        if len(blocked):
            print(f"[{label}] {note}")
            print(blocked[["accord", "조건0건에_등장", "실패율", "한국어_후보수"]]
                  .head(8).to_string(index=False), "\n")


if __name__ == "__main__":
    main()

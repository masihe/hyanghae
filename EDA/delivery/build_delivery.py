"""전달 묶음을 만들고 검증한다.

    venv/Scripts/python.exe delivery/build_delivery.py

하는 일
  1. 사전 CSV 를 for_backend/ 로 복사
  2. 장면 쿼리 7개를 참조 구현으로 돌려 example_response.json 생성
  3. 합성 평가셋 600건으로 커버리지를 재서 verification.json 생성

원본은 읽기만 한다. for_backend/ 밖으로는 아무것도 쓰지 않는다.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
EDA = HERE.parent
sys.path.insert(0, str(HERE / "for_backend"))

from nlr_reference import load_index, recommend, understand, search  # noqa: E402

SOURCES = {
    "perfumes": EDA / "perfumes.csv",
    "lexicon": EDA / "data" / "scent_knowledge" / "domain_lexicon_v1_2.csv",
    "accords": EDA / "analysis_outputs" / "10_accord_dictionary.csv",
    "evalset": EDA / "analysis_outputs" / "34_evalset_stage1_checkpoint.csv",
}
OUT_DIR = HERE / "for_backend"

SCENE_QUERIES = [
    "휴양지에서 쓸 향수 추천해줘",
    "빨래 냄새 나는 향수 찾고 있어",
    "비 오는 숲 같은 향이면 좋겠어",
    "이불 같은 포근한 향 추천해줘",
    "데이트할 때 쓸 향수 추천해줘",
    "밤에 쓰기 좋은 섹시한 향 추천해줘",
    "호텔 라운지 같은 고급스러운 향 찾아줘",
]


def sha256(path):
    """파일의 SHA-256 앞 16자리. str."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()[:16]


def main():
    missing = [str(p) for p in SOURCES.values() if not p.is_file()]
    if missing:
        raise FileNotFoundError(f"입력이 없다: {missing}")
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("입력 해시")
    hashes = {k: sha256(p) for k, p in SOURCES.items()}
    for key, value in hashes.items():
        print(f"  {key:10s} {value}  {SOURCES[key].name}")

    shutil.copy2(SOURCES["lexicon"], OUT_DIR / SOURCES["lexicon"].name)
    shutil.copy2(SOURCES["accords"], OUT_DIR / SOURCES["accords"].name)
    print(f"\n복사: {SOURCES['lexicon'].name}, {SOURCES['accords'].name}")

    print("\n인덱스 적재 (재현 게이트 포함)")
    index = load_index(SOURCES["perfumes"], SOURCES["lexicon"], SOURCES["accords"])
    print(f"  향수 {index['n_perfumes']:,} / accord {len(index['accords'])}")

    # --- 장면 쿼리 7개 -----------------------------------------------------
    examples = [recommend(index, q) for q in SCENE_QUERIES]
    ok = sum(1 for e in examples if e["status"].startswith("OK"))
    (OUT_DIR / "example_response.json").write_text(
        json.dumps({"generated_from": "nlr_reference.py",
                    "lexicon": SOURCES["lexicon"].name,
                    "note": "LLM 구조화 없이 사전 문자열 매칭만 쓴 결과다.",
                    "examples": examples}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    print(f"\n장면 쿼리 7개: 결과 있음 {ok}/7 -> example_response.json")

    # --- 합성 평가셋 600건 --------------------------------------------------
    print("\n합성 평가셋 600건 검증")
    evalset = pd.read_csv(SOURCES["evalset"])
    stats = {}
    for label, use_llm in (("llm_plus_lexicon", True), ("lexicon_only", False)):
        counts = {"OK": 0, "OK_RELAXED": 0, "NO_CONDITION": 0, "NO_RESULT": 0}
        by_arm = {"A": 0, "B": 0}
        for record in evalset.to_dict("records"):
            conditions = None
            if use_llm and isinstance(record["parsed"], str) and record["parsed"].strip():
                conditions = json.loads(record["parsed"])
            found = understand(index, str(record["sentence"]), conditions)
            picked = search(index, found["core"], found["avoid"])
            if not found["core"]:
                counts["NO_CONDITION"] += 1
            elif len(picked["rows"]) == 0:
                counts["NO_RESULT"] += 1
            elif picked["stage"] == "AND":
                counts["OK"] += 1
                by_arm[record["arm"]] += 1
            else:
                counts["OK_RELAXED"] += 1
                by_arm[record["arm"]] += 1
        total = counts["OK"] + counts["OK_RELAXED"]
        stats[label] = {**counts, "with_results": total,
                        "with_results_pct": round(total / len(evalset) * 100, 1),
                        "arm_A_pct": round(by_arm["A"] / 300 * 100, 1),
                        "arm_B_pct": round(by_arm["B"] / 300 * 100, 1)}
        print(f"  [{label}] 결과 있음 {total}/{len(evalset)} "
              f"({stats[label]['with_results_pct']}%)  "
              f"AND {counts['OK']} / 완화 {counts['OK_RELAXED']} / "
              f"조건없음 {counts['NO_CONDITION']} / 결과없음 {counts['NO_RESULT']}")

    (HERE / "verification.json").write_text(
        json.dumps({"input_sha256_head": hashes,
                    "perfume_count": index["n_perfumes"],
                    "accord_count": len(index["accords"]),
                    "scene_queries": {"total": len(SCENE_QUERIES), "with_results": ok},
                    "evalset_600": stats}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    print("\n저장: verification.json")


if __name__ == "__main__":
    main()

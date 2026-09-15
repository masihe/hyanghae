"""향 지도에 올라간 향수 200개의 note 목록을 뽑는다.

**`build_delivery.py` 와 분리한 이유.** 그쪽은 "표준 라이브러리만 쓰고 v3 JSON
하나만 읽는다" 가 설계 전제다. note 는 전달 스키마에 들어 있지 않아 121 MB 원본
(`perfumes.csv`)과 pandas 가 필요하므로, 전제를 깨지 않도록 생성기를 따로 둔다.

**note 는 지도 좌표에 쓰였지만 전달 데이터에는 없다.** 거리의 절반이
note IDF 자카드인데, 전달 파일에는 accord 만 넣었다 (D29 스키마).

**tier 를 살린다.** 지도 계산은 `parse_notes()` 가 tier 구분 없이 합집합으로
쓴다 (EDA 06 에서 tier 가중이 기각됐다). 원본에는 top/middle/base 가 남아 있어
여기서는 그대로 내보낸다. 한 향수 안에서 note 가 여러 tier 에 걸치면
`middle+base` 처럼 합쳐 적어 (향수, note) 당 한 줄을 지킨다 — ERD 의
`perfume_notes` 기본키가 `(perfume_id, note_id)` 이기 때문이다.

재현::

    venv/Scripts/python.exe src/delivery/build_note_list.py
"""

import csv
import io
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
MAP_DIR = os.path.abspath(os.path.join(HERE, "..", ".."))

MAP_JSON = os.path.join("delivery", "for_frontend", "scent_map.json")
OUT_CSV = os.path.join("delivery", "map_perfume_notes.csv")

# perfumes.csv 의 note 컬럼 -> 내보낼 tier 이름. scent_map.NOTE_COLS 와 같은 순서다.
TIERS = (("notes_top", "top"), ("notes_middle", "middle"),
         ("notes_base", "base"), ("notes_flat", "flat"))


def map_perfume_ids(map_json_path):
    """지도 JSON 에서 향수 id 목록을 읽는다. (str) -> list[int]"""
    doc = json.load(io.open(map_json_path, encoding="utf-8"))
    return [p["fragrantica_id"] for p in doc["points"]]


def note_rows(frame, known_vocab, split_notes):
    """향수 행들을 (향수, note) 한 줄씩으로 편다.

    frame        pandas.DataFrame  id · brand · name + note 컬럼 4개
    known_vocab  set[str]          공식 note 어휘. '|' 가 든 이름을 되붙이는 데 쓴다
    split_notes  callable          scent_map._split_notes

    반환 list[list] — fragrantica_id · brand · name · note · note_type · rank
    """
    rows = []
    for _, r in frame.iterrows():
        seen = {}
        for col, tier in TIERS:
            v = r[col]
            if isinstance(v, str) and v:
                for n in split_notes(v, known_vocab):
                    seen.setdefault(n, []).append(tier)
        for i, (note, tiers) in enumerate(seen.items(), 1):
            rows.append([r["id"], r["brand"], r["name"], note,
                         "+".join(dict.fromkeys(tiers)), i])
    return rows


def main() -> None:
    os.chdir(MAP_DIR)
    sys.path.insert(0, os.path.join("src", "common"))
    import pandas as pd
    import scent_map as sm

    ids = map_perfume_ids(MAP_JSON)
    known = set(pd.read_csv(sm.NOTE_DICT_CSV)["note"])
    df = pd.read_csv(sm.PERFUMES_CSV, low_memory=False,
                     usecols=["id", "brand", "name"] + sm.NOTE_COLS)
    frame = df[df["id"].isin(ids)]
    if len(frame) != len(ids):
        raise SystemExit(f"원본에서 {len(frame)}/{len(ids)}개만 찾았다 — 중단한다")

    rows = note_rows(frame, known, sm._split_notes)
    # 향수는 지도 순서(국내 인기순)를 따르고, 그 안에서는 tier 순서를 유지한다.
    order = {fid: i for i, fid in enumerate(ids)}
    rows.sort(key=lambda r: (order[r[0]], r[5]))

    with io.open(OUT_CSV, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["fragrantica_id", "brand", "name", "note", "note_type", "rank"])
        w.writerows(rows)

    notes = {r[3] for r in rows}
    spans = sum(1 for r in rows if "+" in r[4])
    tier_n = sum(1 for r in rows if r[4] != "flat")
    print("=" * 70)
    print("지도 향수의 note 목록")
    print("=" * 70)
    print(f"  향수 {len(frame)}개 · note 종류 {len(notes)}종 · 행 {len(rows)}개")
    print(f"  향수당 평균 {len(rows) / len(frame):.1f}개")
    print(f"  tier 있음 {tier_n}행 / flat {len(rows) - tier_n}행 "
          f"/ 여러 tier 에 걸친 것 {spans}행")
    print(f"  -> {OUT_CSV}")


if __name__ == "__main__":
    main()

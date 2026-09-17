"""AI 서버가 쓸 보조 파일을 팀 저장소의 원천에서 만든다.

    python build_ai_inputs.py

입력은 읽기만 한다. 출력은 `data/` 아래에만 쓴다.

무엇을 만드는가
--------------
    map_perfume_ids.csv    fragrantica_id                            200행
    perfume_names_ko.csv   fragrantica_id · name_ko              약 12만행

왜 파일로 갖는가
--------------
AI 서버는 DB 를 읽지 않는다. 검색을 이 서버가 하기로 정했으므로 데이터를 파일로 들고
있다(`ai/data/perfumes_nlr.csv.gz`). 배포 조건도 아웃바운드를 `gms.ssafy.io` 하나로
제한하고 있어 DB 에 닿을 수 없다(`NLR_DEPLOY_HANDOFF.md` · 2026-09-15 인계).

두 파일이 필요한 이유가 각각 있다.

    map_perfume_ids.csv    향 지도 200개를 추천에서 먼저 보여주려면 어느 향수가
                           그 200개인지 알아야 한다. `nlr_api_contract.md` 의
                           「결정 넷」 4번이 정한 것이고 아직 구현되지 않았다
    perfume_names_ko.csv   사용자가 향수를 한국어로 말한다("모스키노 토이2").
                           엔진이 들고 있는 CSV 에는 영문 이름만 있다

**같은 데이터가 여러 곳에 생긴다.** `spec.md` §8 19번이 이미 향수 정보가 두 곳에
있는 것을 문제로 적었고 이 파일들이 한 곳을 더 만든다. 그래서 **원천을 복사하지 않고
여기서 다시 만든다** — 원천이 바뀌면 이 스크립트를 다시 돌린다.

원천
----
    backend/db/seed/perfume_map_points.csv   향 지도 200개 (MAP 담당 산출물)
    backend/db/seed/perfume_ko.csv           향수 한국어 이름 (백엔드 seed)
    data/perfumes_nlr.csv.gz                 엔진이 쓰는 향수 129,161개

**한국어 이름 맞추기 규칙은 `load_perfume_catalog.sql` 133~140행과 같다.** 영문 이름
하나에 번역이 하나로 정해지는 것만 쓰고 겹치면 버린다. 규칙이 두 곳에 있으면 어긋나므로
바꿀 때 양쪽을 함께 본다.

**앞뒤 공백은 `build_load_files.py` 와 같은 방식으로 턴다.** 원본 향수 이름 917개에
앞뒤 공백이 있고 그중 NBSP(U+00A0)가 섞여 있어 SQL 의 `TRIM()` 으로는 걷지 못한다.
"""
from __future__ import annotations

import argparse
import collections
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
TEAM = HERE.parent

SOURCE = HERE / "data" / "perfumes_nlr.csv.gz"
MAP_POINTS = TEAM / "backend" / "db" / "seed" / "perfume_map_points.csv"
PERFUME_KO = TEAM / "backend" / "db" / "seed" / "perfume_ko.csv"
OUTPUT_DIR = HERE / "data"


def build_map_ids(map_points: Path, output_dir: Path) -> dict:
    """향 지도 200개의 fragrantica_id 만 뽑는다. 요약 dict.

    map_points : Path   backend/db/seed/perfume_map_points.csv
    output_dir : Path   여기 아래에만 쓴다
    """
    # BOM 이 붙어 있어 utf-8-sig 로 읽는다. 첫 컬럼 이름이 '﻿fragrantica_id' 가 된다.
    d = pd.read_csv(map_points, encoding="utf-8-sig")
    ids = pd.Series(d["fragrantica_id"].astype("int64").unique(), name="fragrantica_id")
    ids = ids.sort_values().reset_index(drop=True)
    ids.to_frame().to_csv(output_dir / "map_perfume_ids.csv", index=False)
    return {"rows": len(ids)}


def build_names_ko(source: Path, perfume_ko: Path, output_dir: Path) -> dict:
    """향수 id 에 한국어 이름을 붙인다. 요약 dict.

    source     : Path   data/perfumes_nlr.csv.gz — 엔진이 쓰는 향수 목록
    perfume_ko : Path   backend/db/seed/perfume_ko.csv — name -> translated_name
    output_dir : Path   여기 아래에만 쓴다

    **`load_perfume_catalog.sql` 133~140행과 같은 규칙을 쓴다.** 영문 이름 하나에
    번역이 하나로 정해지는 것만 쓰고, 여러 개면 버린다.
    """
    perfumes = pd.read_csv(source, usecols=["id", "name"], low_memory=False)
    # build_load_files.py 와 같은 방식. SQL 의 TRIM() 은 NBSP 를 걷지 못한다.
    perfumes["name"] = perfumes["name"].astype(str).str.strip()

    ko = pd.read_csv(perfume_ko)
    ko["name"] = ko["name"].astype(str).str.strip()
    ko["translated_name"] = ko["translated_name"].astype(str).str.strip()
    ko = ko[(ko["name"] != "") & (ko["translated_name"] != "")
            & (ko["translated_name"] != "nan")]

    # 영문 이름별로 서로 다른 번역이 몇 개인지 센다. 하나뿐인 것만 쓴다.
    distinct = ko.groupby("name")["translated_name"].nunique()
    unique_names = set(distinct[distinct == 1].index)
    dropped_names = len(distinct) - len(unique_names)

    table = (ko[ko["name"].isin(unique_names)]
             .drop_duplicates("name")
             .set_index("name")["translated_name"])

    out = pd.DataFrame({
        "fragrantica_id": perfumes["id"].astype("int64"),
        "name_ko": perfumes["name"].map(table),
    })
    matched = int(out["name_ko"].notna().sum())
    out = out[out["name_ko"].notna()]
    out.to_csv(output_dir / "perfume_names_ko.csv", index=False)

    return {
        "perfumes": len(perfumes),
        "ko_rows": len(ko),
        "ko_names": len(distinct),
        "dropped_names": dropped_names,
        "matched": matched,
        "rows": len(out),
    }


def build(source: Path = SOURCE, map_points: Path = MAP_POINTS,
          perfume_ko: Path = PERFUME_KO, output_dir: Path = OUTPUT_DIR) -> dict:
    """보조 파일 둘을 만든다. 요약 dict."""
    for path in (source, map_points, perfume_ko):
        if not path.is_file():
            raise FileNotFoundError(f"원천이 없습니다: {path}")
    output_dir.mkdir(parents=True, exist_ok=True)

    summary = {"map": build_map_ids(map_points, output_dir)}
    summary["ko"] = build_names_ko(source, perfume_ko, output_dir)

    def kb(name):
        return round((output_dir / name).stat().st_size / 1024, 1)

    summary["map"]["kb"] = kb("map_perfume_ids.csv")
    summary["ko"]["kb"] = kb("perfume_names_ko.csv")
    summary["output_dir"] = str(output_dir)
    return summary


def main() -> None:
    """명령줄 실행."""
    parser = argparse.ArgumentParser(description="AI 서버 보조 파일 생성")
    parser.add_argument("--source", default=str(SOURCE))
    parser.add_argument("--map-points", default=str(MAP_POINTS))
    parser.add_argument("--perfume-ko", default=str(PERFUME_KO))
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR))
    args = parser.parse_args()

    s = build(Path(args.source), Path(args.map_points),
              Path(args.perfume_ko), Path(args.output_dir))
    m, k = s["map"], s["ko"]
    print(f"출력        {s['output_dir']}\n")
    print(f"  map_perfume_ids.csv    {m['rows']:>9,}행  {m['kb']:>7}KB")
    print(f"  perfume_names_ko.csv   {k['rows']:>9,}행  {k['kb']:>7}KB")
    print()
    print(f"  향수 {k['perfumes']:,}개 중 한국어 이름이 붙은 것 {k['matched']:,}개"
          f"  ({k['matched'] / k['perfumes']:.1%})")
    print(f"  번역 원천 {k['ko_rows']:,}행 · 영문 이름 {k['ko_names']:,}개")
    print(f"  번역이 여러 개여서 버린 이름 {k['dropped_names']:,}개"
          f"  (`load_perfume_catalog.sql` 과 같은 규칙)")


if __name__ == "__main__":
    main()

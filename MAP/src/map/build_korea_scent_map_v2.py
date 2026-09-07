"""국내 200개 향 지도를 프론트 전달 스키마 v2로 다시 쓴다 (Phase A1).

Run with venv/Scripts/python.exe src/map/build_korea_scent_map_v2.py

하는 일은 셋뿐이다.
  1. output/korea_scent_map_v1.json 의 raw UMAP 좌표를 [0,1]로 정규화한다 (x·y 동일 배율).
  2. 글로벌 output/scent_map_v1.json 과 같은 스키마로 필드를 맞춘다.
  3. 프론트가 오해하지 않도록 측정값과 미확정 상태를 데이터에 싣는다.

좌표를 다시 계산하지 않는다. 유사도·선정 결과도 바꾸지 않는다.
v1 의 이웃 집합을 재현하는지 확인하는 것으로 유사도 재현을 검증한다.

terrain / regions / contours 는 Phase A2 산출물이라 여기서는 null 로 둔다.
v1 의 cluster(k=4, silhouette 0.09) 는 일부러 옮기지 않는다 — 빈도 기반 라벨이라
Phase A2 에서 두드러짐(lift) 기반 영역으로 대체할 예정이고, 그대로 실으면
프론트가 약한 군집을 1차 시각 언어로 쓰게 된다 (docs/FRONTEND_MAP_DATA_WORKFLOW.md P1/P4).
"""
import hashlib
import json
import os
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "common")))
import build_map as bm
import scent_map as sm

MAP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))  # MAP/
DATA = os.path.join(MAP_DIR, "data", "korea_popularity")
V1_PATH = os.path.join(MAP_DIR, "output", "korea_scent_map_v1.json")
V2_PATH = os.path.join(MAP_DIR, "output", "korea_scent_map_v2.json")
TOP200 = os.path.join(DATA, "korea_representative_perfumes_top200.csv")
COMMERCIAL = os.path.join(DATA, "korea_commercial_identities.csv")
LAYOUT_CSV = os.path.join(MAP_DIR, "results", "korea_layout_comparison.csv")

# build_korea_popularity_map.py 가 고정한 값. 스냅샷이 바뀌면 좌표 전제가 달라진다.
PERFUMES_SHA256 = "cec1ea0b498853032bcf44d33ad52ac83e2ed2896b67d5a2765d90a0345cc055"

# 이 집합 안에서 사람이 "닮았다"고 투표한 신뢰 간선 실측값 (찬성>=3 & 찬성>반대).
# Phase A2 의 모집단 결정 근거이자, 프론트에 검증 밀도를 알리는 값이다.
TRUSTED_EDGES_IN_SET = 40
PERFUMES_WITH_TRUSTED_EDGE = 44

NEIGHBOR_K = 10


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def normalize_uniform(coords):
    """x·y에 같은 배율을 적용해 [0,1]로 옮긴다.

    축별로 따로 정규화하면 종횡비가 깨져 UMAP이 만든 거리 구조가 왜곡된다
    (docs/DECISIONS.md D5). 넓은 축만 1.0을 채우고 좁은 축에는 여백이 남는다.
    """
    low = coords.min(axis=0)
    span = (coords.max(axis=0) - low).max()
    assert span > 0
    return (coords - low) / span, float(span)


def match_block(row, commercial):
    """Map Identity 를 이루는 Commercial Identity 들의 매칭 상태를 모은다."""
    ids = [x for x in str(row.commercial_identity_ids).split("|") if x]
    members = commercial.loc[commercial.commercial_identity_id.isin(ids)]
    statuses = sorted({s for s in members.fragrantica_match_status if s})
    return {
        "status": statuses[0] if len(statuses) == 1 else "|".join(statuses),
        "basis": " / ".join(sorted({b for b in members.fragrantica_match_basis if b})),
        "verification_status": "UNVERIFIED",
        "commercial_identity_ids": ids,
        "map_identity_conflict": bool(row.map_identity_conflict),
    }


def main():
    digest = sha256(sm.PERFUMES_CSV)
    if digest != PERFUMES_SHA256:
        raise ValueError(f"perfumes.csv 스냅샷이 바뀌었다 ({digest}). 좌표 전제를 다시 확인할 것")

    v1 = json.loads(open(V1_PATH, encoding="utf-8").read())
    top200 = pd.read_csv(TOP200, keep_default_na=False)
    commercial = pd.read_csv(COMMERCIAL, keep_default_na=False)
    layout = pd.read_csv(LAYOUT_CSV).set_index("layout")

    assert len(v1["points"]) == 200 and len(top200) == 200
    v1_by_id = {int(p["fragrantica_id"]): p for p in v1["points"]}
    assert len(v1_by_id) == 200, "v1 에 중복 fragrantica_id 가 있다"

    ordered = top200.sort_values("selection_rank")
    ids = ordered.fragrantica_id.astype(int).tolist()
    assert set(ids) == set(v1_by_id), "top200 과 v1 의 향수 집합이 다르다"

    perfumes = sm.load_perfumes().set_index("id")
    rows = perfumes.loc[ids].reset_index()

    idf = sm.load_note_idf()
    similarity, _, _ = sm.base_similarity(rows.accord_list.tolist(), rows.note_set.tolist(), idf)
    np.fill_diagonal(similarity, -np.inf)

    # v1 의 이웃 집합을 재현하는지 확인한다 (유사도 재현 검증).
    order = np.argsort(-similarity, axis=1)[:, :NEIGHBOR_K]
    mismatched = []
    for i, pid in enumerate(ids):
        mine = {ids[j] for j in order[i]}
        theirs = set(v1_by_id[pid]["neighbors"])
        if mine != theirs:
            mismatched.append((pid, sorted(theirs - mine), sorted(mine - theirs)))
    print(f"이웃 집합 재현: 일치 {200 - len(mismatched)}/200")
    for pid, only_v1, only_new in mismatched[:5]:
        print(f"   불일치 id={pid} v1에만={only_v1} 새것에만={only_new}")

    coords = np.array([[v1_by_id[pid]["x"], v1_by_id[pid]["y"]] for pid in ids], dtype=float)
    raw_span = coords.max(axis=0) - coords.min(axis=0)
    unit, span = normalize_uniform(coords)

    layout_row = layout.loc[v1["layout"]]
    sel = ordered.set_index("fragrantica_id")

    points = []
    for i, pid in enumerate(ids):
        p = rows.iloc[i]
        s = sel.loc[pid]
        points.append({
            "map_identity_id": s.map_identity_id,
            "fragrantica_id": int(pid),
            "brand": p.brand,
            "name": p["name"],
            "year": None if pd.isna(p.year) else int(p.year),
            "gender": p.gender,
            "x": round(float(unit[i, 0]), 5),
            "y": round(float(unit[i, 1]), 5),
            "display": True,
            "display_priority": int(s.selection_rank),
            "region": None,  # Phase A2
            "korea": {
                "selection_rank": int(s.selection_rank),
                "selection_basis": s.selection_basis,
                "has_purchase_signal": bool(s.has_purchase_signal),
                "has_hwahae_signal": bool(s.has_hwahae_signal),
                "best_hwahae_rank": None if s.best_hwahae_rank == "" else int(float(s.best_hwahae_rank)),
                "purchase_rrf_k60": float(s.purchase_rrf_k60),
            },
            "match": match_block(s, commercial),
            "top_accords": [{"name": name, "strength": int(value)} for name, value in p.accord_list],
            "seasons": bm.season_block(p),
            "daypart": bm.daypart_block(p),
            "neighbors": [{"id": int(ids[j]), "sim": round(float(similarity[i, j]), 4)}
                          for j in order[i]],
        })

    payload = {
        "schema_version": 2,
        # 9~11단계로 Verification 과 사람 검토가 반영됐다 (D18·D19). 좌표·이웃 관계는 확정본이다.
        # 지형(해안선·섬)은 시드에 흔들리므로 terrain 블록의 seed_stability 를 함께 볼 것.
        "dataset_status": "VERIFIED",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "source": {
            "perfumes_csv_sha256": digest,
            "coordinates_from": "output/korea_scent_map_v1.json",
            "selection_source": "data/korea_popularity/korea_representative_perfumes_top200.csv",
            "matcher": ("build_korea_popularity_map.py — 브랜드 매핑(D13) + LLM 이름 채널(D15·D17) "
                        "+ Verification(D18, 음성키 단독·기본명 애매 확정 취소) + 사람 검토 확정 49건(D19)"),
        },
        "similarity": {
            "accord_weight": 0.5, "note_weight": 0.5,
            "note_weighting": "idf", "source": "EDA 04-06",
        },
        "layout": {
            "method": "umap", "n_neighbors": 10, "min_dist": 0.1, "random_state": 42,
            "layout_id": v1["layout"],
            "population": 200, "display_count": 200,
            "normalization": "[0,1], uniform scale on x and y",
            "distance_is_metric": False,
            "metrics": {
                "trust_at_10": round(float(layout_row.trust_at_10), 4),
                "trust_at_20": round(float(layout_row.trust_at_20), 4),
                "knn_overlap_at_10": round(float(layout_row.knn_overlap_at_10), 4),
                "source": "results/korea_layout_comparison.csv",
                "trusted_reminds_edges_in_set": TRUSTED_EDGES_IN_SET,
                "perfumes_with_trusted_reminds_edge": PERFUMES_WITH_TRUSTED_EDGE,
                "reminds_distance_percentile": None,  # Phase A2
            },
        },
        "bounds": {
            "x_min": round(float(unit[:, 0].min()), 5), "x_max": round(float(unit[:, 0].max()), 5),
            "y_min": round(float(unit[:, 1].min()), 5), "y_max": round(float(unit[:, 1].max()), 5),
        },
        "terrain": None,   # Phase A2
        "contours": None,  # Phase A2
        "regions": None,   # Phase A2
        "points": points,
    }

    with open(V2_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
        f.write("\n")

    # ---- 합격 기준 검증 ----
    saved = json.loads(open(V2_PATH, encoding="utf-8").read())
    pts = saved["points"]
    assert len(pts) == 200
    assert len({p["fragrantica_id"] for p in pts}) == 200
    xs = [p["x"] for p in pts]
    ys = [p["y"] for p in pts]
    assert all(np.isfinite(v) for v in xs + ys)
    assert min(xs) >= 0 and max(xs) <= 1 and min(ys) >= 0 and max(ys) <= 1
    present = {p["fragrantica_id"] for p in pts}
    dangling = [n["id"] for p in pts for n in p["neighbors"] if n["id"] not in present]
    assert not dangling, f"파일 안에 없는 이웃 id {len(dangling)}건"

    # 종횡비 보존: 정규화 전후 x/y 폭 비율이 같아야 한다.
    unit_span = np.array([max(xs) - min(xs), max(ys) - min(ys)])
    before = raw_span[0] / raw_span[1]
    after = unit_span[0] / unit_span[1]
    assert abs(before - after) < 1e-4, f"종횡비 깨짐 {before:.6f} -> {after:.6f}"

    size = os.path.getsize(V2_PATH)
    print()
    print(f"points {len(pts)} / 중복 id 0 / NaN 0 / 이웃 미해결 0")
    print(f"공통 배율 {span:.6f} (raw 폭 x {raw_span[0]:.4f} y {raw_span[1]:.4f})")
    print(f"정규화 폭  x {unit_span[0]:.4f} y {unit_span[1]:.4f} | 종횡비 {before:.6f} -> {after:.6f}")
    print(f"seasons 있는 향수 {sum(p['seasons'] is not None for p in pts)}/200, "
          f"daypart {sum(p['daypart'] is not None for p in pts)}/200")
    print(f"accord 개수 분포 {pd.Series([len(p['top_accords']) for p in pts]).value_counts().to_dict()}")
    print(f"match status {pd.Series([p['match']['status'] for p in pts]).value_counts().to_dict()}")
    print(f"파일 크기 {size:,} bytes ({size/1024/1024:.2f} MB)")
    print(V2_PATH)


if __name__ == "__main__":
    main()

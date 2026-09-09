"""실험 스냅샷 3종을 고정하고 기준값을 실측으로 재현한다 (Phase 0-3).

Run with venv/Scripts/python.exe src/map/experiment_phase0_snapshot.py

**왜 이 산출물인가.** 실험 캠페인의 모든 비교는 "같은 향수 집합을 썼다" 가 전제다.
집합이 달라지면 지도 방법의 효과인지 데이터 차이인지 알 수 없다
(SCENT_MAP_EXPERIMENT_DESIGN_v4.md 6.4). 그래서 세 모집단의 ID·해시·검증 밀도를
한 번 고정하고, 이후 실험은 이 manifest 의 해시를 자기 manifest 에 적는다.

**모집단 3종의 역할이 다르다.**
  Dev 700      유사도 정의를 고르는 외부 시험지 (Phase 1)
  Global 1,000 방법 선택과 보호 지표 (Phase 1·2, Phase 3 가드레일)
  Korea 200    실제 서비스 지도. 영역·균형·UX 평가 (Phase 3·4·5)

Korea 200 만으로 Feature/Projection 을 고르지 않는다 — 내부 신뢰 간선이 44쌍뿐이고
간선을 가진 향수가 46개라 나머지 154개는 위치가 맞는지 외부 근거로 확인할 수 없다.

**출하 메타데이터와의 차이는 여기서 고치지 않는다.** output/korea_scent_map_v2.json 은
trusted_reminds_edges_in_set=40 / perfumes_with_trusted_reminds_edge=44 를 싣고 있는데
현재 200개 실측은 44 / 46 이다. build_korea_scent_map_v2.py 의 하드코딩 상수에서 온
차이이며 production follow-up 으로 분리해 기록한다. 실험 중에 프로덕션을 수정하지 않는다.

산출: experiments/phase0/snapshots/, experiments/phase0/manifest.json, metrics.json
"""
import json
import os
import sys
import time

import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "common")))
import scent_map as sm
import build_map as bm
import verify_similarity as vs
import experiment_note_canonical as enc
import experiment_phase0_family_mapping as fm
import experiment_phase0_family_score as fs

PHASE0 = os.path.join("experiments", "phase0")
SNAP = os.path.join(PHASE0, "snapshots")
TOP200 = os.path.join("data", "korea_popularity", "korea_representative_perfumes_top200.csv")
V2_JSON = os.path.join("output", "korea_scent_map_v2.json")   # 읽기만 한다
SEEDS = (42, 1, 2, 3, 4)   # compare_korea_map_population.py 와 같은 집합

# 이번 세션에서 실측한 기준값. 재현되지 않으면 입력이 달라진 것이다.
EXPECTED = {
    "korea200_n": 200,
    "korea200_trusted_edges": 44,
    "korea200_trusted_nodes": 46,
    "global1000_n": 1000,
    "global1000_trusted_edges": 872,
    "global1000_cross_family_edges": 435,
    "dev700_n": 700,
    "korea200_trust10_seed42": 0.9191,
    "korea200_overlap10_seed42": 0.4875,
    "korea200_trust10_seed_mean": 0.9213,
    "korea200_reminds_seed_mean": 0.1672,
    "global1000_trust10_seed42": 0.9387,
    "global1000_overlap10_seed42": 0.3888,
    "global1000_top10_hit": 0.4464,
    "global1000_top10_hit_note_cosine": 0.4501,
    "dev700_ndcg10": 0.2709,
}
TOL = 0.0015   # 지표 재현 허용 오차


def sha256(path):
    return bm.__dict__.get("_sha", None) or _sha256(path)


def _sha256(path):
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def top10_hit(sim, ids, index_of, edges):
    """신뢰 파트너가 유사도 상위 10 안에 들어오는 비율. Phase 1 의 외부 기준."""
    import collections
    sim = sim.copy()
    np.fill_diagonal(sim, -np.inf)
    order = np.argsort(-sim, axis=1)[:, :10]
    partners = collections.defaultdict(set)
    for a, b in edges:
        partners[a].add(b)
        partners[b].add(a)
    hits = []
    for q, ps in partners.items():
        got = {ids[j] for j in order[index_of[q]]}
        hits.append(len(got & ps) / len(ps))
    return float(np.mean(hits)), len(partners)


def layout_metrics(distance, index_of, edges, seeds):
    """시드별 UMAP 배치 지표. 게이트 판정은 평균과 최소값으로 한다."""
    import umap
    rows = []
    for seed in seeds:
        coords = umap.UMAP(n_neighbors=10, min_dist=0.1, metric="precomputed",
                           random_state=seed).fit_transform(distance)
        m = bm.evaluate_layout(np.asarray(coords, float), distance, index_of, edges)
        rows.append({"seed": seed, **{k: float(v) for k, v in m.items()}})
    frame = pd.DataFrame(rows)
    agg = {}
    for col in ("trust@10", "trust@20", "knn_overlap@10", "reminds_pct"):
        agg[col] = {"mean": round(float(frame[col].mean()), 4),
                    "std": round(float(frame[col].std(ddof=0)), 4),
                    "min": round(float(frame[col].min()), 4),
                    "max": round(float(frame[col].max()), 4),
                    "seed42": round(float(frame.loc[frame.seed == 42, col].iloc[0]), 4)}
    return frame, agg


def check(name, got, want, tol, results):
    hit = abs(got - want) <= tol
    results.append({"name": name, "measured": round(float(got), 4),
                    "expected": want, "tolerance": tol, "ok": bool(hit)})
    print(f"  {name:<38} 실측 {got:<9.4f} 기대 {want:<9} {'OK' if hit else '** 차이 **'}")
    return hit


def main() -> None:
    os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))  # MAP/
    os.makedirs(SNAP, exist_ok=True)
    t0 = time.time()

    print("=" * 78)
    print("Phase 0-3 — 실험 스냅샷 고정과 기준값 재현")
    print("=" * 78)

    # ---- 입력 해시 ----
    perfumes_digest = _sha256(sm.PERFUMES_CSV)
    print(f"perfumes.csv sha256 {perfumes_digest[:16]}...")
    import build_korea_scent_map_v2 as v2
    frozen = perfumes_digest == v2.PERFUMES_SHA256
    print(f"  build_korea_scent_map_v2.PERFUMES_SHA256 와 일치: {frozen}")
    assert frozen, "perfumes.csv 스냅샷이 바뀌었다. 좌표 전제를 다시 확인할 것"

    # ---- Global 1,000 + 전체 코퍼스 (perfumes.csv 로드는 한 번만) ----
    df, targets, idf_map, S_global, D_global, index_of_g, ce_g, ae_g = bm.prepare(
        with_selection_comparison=False)
    print(f"\n전체 코퍼스 {len(df)} / Global 1,000 신뢰 간선 {len(ce_g)} / also_liked {len(ae_g)}")

    # ---- Korea 200 ----
    korea_ids = pd.read_csv(TOP200).fragrantica_id.astype(int).tolist()
    korea_rows = df.set_index("id").loc[korea_ids].reset_index()
    rin = bm.edges_within(sm.load_edges("reminds_edges.csv"), set(korea_ids))
    conf_k = rin[bm.confident(rin)]
    ce_k = [(int(a), int(b)) for a, b in conf_k[["src", "dst"]].itertuples(index=False, name=None)]
    nodes_k = {int(x) for pair in conf_k[["src", "dst"]].itertuples(index=False, name=None)
               for x in pair}
    S_korea, _, _ = sm.base_similarity(korea_rows.accord_list.tolist(),
                                       korea_rows.note_set.tolist(), idf_map)
    D_korea = 1.0 - S_korea
    np.fill_diagonal(D_korea, 0.0)
    index_of_k = {int(v): i for i, v in enumerate(korea_ids)}

    # 출하 JSON 과의 대조 (읽기만)
    v2_doc = json.loads(open(V2_JSON, encoding="utf-8").read())
    v2_ids = [p["fragrantica_id"] for p in v2_doc["points"]]
    shipped = v2_doc["layout"]["metrics"]
    print(f"Korea 200 신뢰 간선 {len(ce_k)} / 보유 향수 {len(nodes_k)}")
    print(f"  출하 JSON 기록값 {shipped['trusted_reminds_edges_in_set']} / "
          f"{shipped['perfumes_with_trusted_reminds_edge']}  <- production follow-up")
    assert set(v2_ids) == set(korea_ids), "출하 JSON 과 top200 CSV 의 향수 집합이 다르다"

    # ---- Dev 700 / Holdout 300 ----
    id_to_row, perfume_ids, relevant_by_query, development, holdout = vs.build_eval_set(df)
    print(f"Dev {len(development)} / Holdout {len(holdout)} (Holdout 은 ID 도 기록하지 않는다)")

    # ---- 계열 배정과 cross-family 간선 ----
    Mg, fams = fs.score_matrix(targets.accord_list.tolist(), mode=fs.FS_DEFAULT)
    fam_g = np.array([fams[i] for i in Mg.argmax(axis=1)], dtype=object)
    cross = [(a, b) for a, b in ce_g if fam_g[index_of_g[a]] != fam_g[index_of_g[b]]]
    print(f"Global 1,000 cross-family 신뢰 간선 {len(cross)}/{len(ce_g)} "
          f"(매핑 {fm.MAPPING_VERSION}, FS {fs.FS_DEFAULT})")

    # ---- 배치 지표 ----
    print("\nKorea 200 UMAP 시드 5개...")
    k_frame, k_agg = layout_metrics(D_korea, index_of_k, ce_k, SEEDS)
    print(f"  trust@10 {k_agg['trust@10']['mean']:.4f} ± {k_agg['trust@10']['std']:.4f} "
          f"(최소 {k_agg['trust@10']['min']:.4f}) · "
          f"overlap {k_agg['knn_overlap@10']['mean']:.3f} · "
          f"trusted-edge {k_agg['reminds_pct']['mean']:.4f} ± {k_agg['reminds_pct']['std']:.4f}")
    print("Global 1,000 UMAP seed 42...")
    g_frame, g_agg = layout_metrics(D_global, index_of_g, ce_g, (42,))
    print(f"  trust@10 {g_agg['trust@10']['seed42']:.4f} · "
          f"overlap {g_agg['knn_overlap@10']['seed42']:.4f}")

    # ---- Phase 1 외부 기준과 A8 대조군 ----
    A, _ = sm.build_accord_matrix(list(targets.accord_list))
    S_acc = A @ A.T
    B, w, _, _ = sm.build_note_matrix(list(targets.note_set), idf_map)
    Bw = B * w
    inter = Bw @ B.T
    rs = Bw.sum(axis=1)
    union = rs[:, None] + rs[None, :] - inter
    S_jac = np.zeros_like(inter)
    np.divide(inter, union, out=S_jac, where=union > 0)
    nrm = np.linalg.norm(Bw, axis=1, keepdims=True)
    nrm[nrm == 0] = 1.0
    S_cos = (Bw / nrm) @ (Bw / nrm).T
    ids_g = targets.id.astype(int).tolist()
    hit_base, n_q = top10_hit(0.5 * S_acc + 0.5 * S_jac, ids_g, index_of_g, ce_g)
    hit_cos, _ = top10_hit(0.5 * S_acc + 0.5 * S_cos, ids_g, index_of_g, ce_g)
    print(f"\n신뢰 파트너 top10 포함률 (질의 {n_q}개)")
    print(f"  baseline (accord 0.5 + note IDF-Jaccard) {hit_base:.4f}")
    print(f"  A8 대조군 (accord 0.5 + note IDF-cosine)  {hit_cos:.4f}  <- PPMI 효과를 귀속할 기준선")

    # ---- Dev 700 ndcg 재현 (experiment_note_canonical 의 평가 절차 재사용) ----
    print("\nDev 700 baseline 재현 (전체 코퍼스 평가)...")
    t1 = time.time()
    dev = enc.evaluate(df, df.note_set, idf_map, id_to_row, perfume_ids,
                       relevant_by_query, development, "baseline (accord 0.5 + note IDF)")
    print(f"  소요 {time.time() - t1:.0f}초")

    # ---- 기준값 재현 확인 ----
    print("\n기준값 재현 확인")
    res = []
    ok = True
    ok &= check("korea200 신뢰 간선", len(ce_k), EXPECTED["korea200_trusted_edges"], 0, res)
    ok &= check("korea200 보유 향수", len(nodes_k), EXPECTED["korea200_trusted_nodes"], 0, res)
    ok &= check("global1000 신뢰 간선", len(ce_g), EXPECTED["global1000_trusted_edges"], 0, res)
    ok &= check("global1000 cross-family 간선", len(cross),
                EXPECTED["global1000_cross_family_edges"], 0, res)
    ok &= check("dev700 질의 수", len(development), EXPECTED["dev700_n"], 0, res)
    ok &= check("korea200 trust@10 seed42", k_agg["trust@10"]["seed42"],
                EXPECTED["korea200_trust10_seed42"], TOL, res)
    ok &= check("korea200 overlap@10 seed42", k_agg["knn_overlap@10"]["seed42"],
                EXPECTED["korea200_overlap10_seed42"], TOL, res)
    ok &= check("korea200 trust@10 5시드 평균", k_agg["trust@10"]["mean"],
                EXPECTED["korea200_trust10_seed_mean"], TOL, res)
    ok &= check("korea200 trusted-edge 5시드 평균", k_agg["reminds_pct"]["mean"],
                EXPECTED["korea200_reminds_seed_mean"], 0.003, res)
    ok &= check("global1000 trust@10 seed42", g_agg["trust@10"]["seed42"],
                EXPECTED["global1000_trust10_seed42"], TOL, res)
    ok &= check("global1000 overlap@10 seed42", g_agg["knn_overlap@10"]["seed42"],
                EXPECTED["global1000_overlap10_seed42"], TOL, res)
    ok &= check("global1000 top10 포함률", hit_base, EXPECTED["global1000_top10_hit"], TOL, res)
    ok &= check("global1000 top10 (note cosine)", hit_cos,
                EXPECTED["global1000_top10_hit_note_cosine"], TOL, res)
    ok &= check("dev700 ndcg@10", dev["ndcg"], EXPECTED["dev700_ndcg10"], TOL, res)
    if not ok:
        print("\n  ** 재현되지 않은 값이 있다. 입력이 달라졌다는 뜻이므로 원인을 확인하고")
        print("     Phase 1 로 넘어가지 않는다. **")

    # ---- 스냅샷 CSV ----
    korea_out = korea_rows[["id", "brand", "name", "year", "gender", "vote_count", "people"]].copy()
    korea_out["accords"] = korea_rows.accord_list.map(
        lambda l: "|".join(f"{n}:{int(s)}" for n, s in l))
    korea_out["accord_rank"] = korea_rows.accord_list.map(
        lambda l: "|".join(n for n, _ in l))
    korea_out["notes_flat"] = korea_rows.note_set.map(lambda s: "|".join(sorted(s)))
    for col in ("notes_top", "notes_middle", "notes_base"):
        korea_out[col] = korea_rows[col].values
    for col in ("winter", "spring", "summer", "autumn", "day", "night"):
        korea_out[col] = korea_rows[col].values
    korea_out["family"] = korea_rows["family"].values
    korea_out["group"] = korea_rows["group"].values
    korea_out.to_csv(os.path.join(SNAP, "korea200.csv"), index=False, encoding="utf-8-sig")

    targets[["id", "brand", "name", "year", "vote_count", "group", "dominant_accord"]].to_csv(
        os.path.join(SNAP, "global1000.csv"), index=False, encoding="utf-8-sig")
    pd.DataFrame({"query_id": development}).to_csv(
        os.path.join(SNAP, "dev700.csv"), index=False)
    k_frame.to_csv(os.path.join(SNAP, "korea200_layout_seeds.csv"), index=False)

    # ---- manifest / metrics ----
    manifest = {
        "experiment_id": "phase0",
        "phase": 0,
        "status": "NEW",
        "hypothesis": "해당 없음 — 실험 기반 고정 단계",
        "user_meaning": "모든 실험이 같은 데이터를 썼다는 것을 해시로 보장한다",
        "changed_variable": "없음",
        "population": ["dev700", "global1000", "korea200"],
        "snapshot_hash": {
            "perfumes_csv": perfumes_digest,
            "note_dictionary": _sha256(sm.NOTE_DICT_CSV),
            "reminds_edges": _sha256(os.path.join(sm.CACHE, "reminds_edges.csv")),
            "also_liked_edges": _sha256(os.path.join(sm.CACHE, "also_liked_edges.csv")),
            "people": _sha256(os.path.join(sm.CACHE, "people.csv")),
            "korea_top200_csv": _sha256(TOP200),
        },
        "family_mapping_version": fm.MAPPING_VERSION,
        "family_mapping_sha256": fm.mapping_digest(),
        "family_mapping_status": "PROVISIONAL",
        "family_score_version": fs.FS_DEFAULT,
        "projection": "umap n_neighbors=10 min_dist=0.1 metric=precomputed",
        "seeds": list(SEEDS),
        "baseline_reference": EXPECTED,
        "reproduction_gate_result": {
            "script": "src/matching/evaluate_brand_mapping_dev.py",
            "pre_phase0": "PASS — 5개 방법 4자리 재현 일치, 보호 산출물 8개 SHA-256 불변",
            "post_phase0": "TODO — Phase 0 종료 시 재실행",
        },
        "production_followup": {
            "issue": "output/korea_scent_map_v2.json 의 검증 밀도 메타데이터가 현재 구성과 다르다",
            "shipped": {"trusted_reminds_edges_in_set":
                        shipped["trusted_reminds_edges_in_set"],
                        "perfumes_with_trusted_reminds_edge":
                        shipped["perfumes_with_trusted_reminds_edge"]},
            "measured": {"trusted_edges": len(ce_k), "trusted_nodes": len(nodes_k)},
            "cause": "build_korea_scent_map_v2.py 의 하드코딩 상수 (잠정 200개 시점 값)",
            "action": "실험 범위 밖. 프로덕션 재생성 시 별도 처리",
        },
        "output_files": sorted(os.listdir(SNAP)),
        "reproduction_ok": bool(ok),
        "elapsed_sec": round(time.time() - t0, 1),
    }
    metrics = {
        "korea200": {
            "n": len(korea_ids), "trusted_edges": len(ce_k), "trusted_nodes": len(nodes_k),
            "layout_seeds": k_agg,
        },
        "global1000": {
            "n": len(targets), "trusted_edges": len(ce_g),
            "cross_family_trusted_edges": len(cross),
            "also_liked_edges": len(ae_g),
            "layout_seed42": g_agg,
            "top10_hit_baseline": round(hit_base, 4),
            "top10_hit_note_cosine_control": round(hit_cos, 4),
            "top10_hit_queries": n_q,
        },
        "dev700": {"n": len(development), **{k: dev[k] for k in
                                             ("recall", "hit_rate", "mrr", "ndcg")}},
        "reproduction_checks": res,
    }
    with open(os.path.join(PHASE0, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)
        f.write("\n")
    with open(os.path.join(PHASE0, "metrics.json"), "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=1)
        f.write("\n")

    print()
    print(f"재현 판정 {'PASS' if ok else 'FAIL'} · 총 소요 {time.time() - t0:.0f}초")
    print(f"  -> {SNAP}/ (korea200.csv, global1000.csv, dev700.csv, korea200_layout_seeds.csv)")
    print(f"  -> {PHASE0}/manifest.json · metrics.json")


if __name__ == "__main__":
    main()

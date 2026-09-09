"""Phase 3b — Territory 방식 C1~C8 비교.

Run with venv/Scripts/python.exe src/map/experiment_phase3b_territory.py

**기준 투영은 UMAP seed 42** (팀 결정). **Family 정의는 Set B** = reviewed-1 accord 기반
9계열 (Phase 3a 제안). 두 전제를 고정하고 "영역을 어떻게 표현할 것인가" 만 바꾼다.

**보호 지표가 이 실험의 핵심 비용이다.** 계열이 달라도 사람이 비슷하다고 평가한 향수가
있다 — Global 1,000 에 412쌍이다. 영역을 나누면서 이들을 억지로 멀리 밀어내면 실패다.
D9 가 반지도 UMAP 을 기각한 것이 정확히 이 지점이었다 (0.363 -> 0.52~0.56).

    Gate A   cross-family trusted-pair 근접도 <= baseline + 0.05
             baseline(UMAP seed42 · Set B · Global 1,000) = 0.2615  ->  합격선 0.3115

**모집단 역할이 다르다** (v4 24). 영역 가독성은 Korea 200, 유사 향수 훼손 보호는
Global 1,000 (Korea 는 계열 횡단 쌍이 25쌍뿐이라 판정에 쓰지 않는다).

**안정성은 Hard Gate 가 아니다** (팀 결정). 시드 5개에서 구조가 크게 무너지지 않는지만
확인해 기록한다.

방식:
    C1  Post-hoc Territory        좌표 유지 + 계열 밀도로 영역 폴리곤. 개입 0
    C2  Family Supervised UMAP    계열 라벨을 UMAP target 으로. 가중 4단계
    C3  Semi-Supervised UMAP      계열이 명확한 향수만 라벨 (RuleB margin>=0.10)
    C4  Fixed Territory + Local   해역 위치를 고정하고 해역 안에서만 국소 배치
    C5  Wheel Anchor              계열 앵커를 휠 순서로 원에 배치, Family Score 로 위치 결정
    C6  Anchor + Local Similarity C5 의 큰 위치 + 셀 안에서 국소 유사도로 퍼뜨림
    C7  Gradient Territory        경계를 끊지 않고 전이 지대로. 좌표 유지 (렌더링 변형)
    C8a Perception-only Blend     사용자 투표 축을 거리에 섞는다 (계열 무관)
    C8b Family + Perception       계열 + 인식 축을 함께 섞는다

산출: experiments/phase3b/
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
import build_korea_terrain as bkt
import experiment_phase0_family_mapping as fm
import experiment_family_systems as es

OUT_DIR = os.path.join("experiments", "phase3b")
TOP200 = os.path.join("data", "korea_popularity", "korea_representative_perfumes_top200.csv")
V2_JSON = os.path.join("output", "korea_scent_map_v2.json")   # 읽기만 한다
SEEDS = (42, 1, 2, 3, 4)
NEIGHBOR_K = 10
SYSTEM = "S9"                 # Set B = reviewed-1 9계열
C3_MARGIN = 0.10              # RuleB — Phase 0 에서 편중이 가장 작았다 (59.5% 커버리지)
GATE_A_MARGIN = 0.05
BOUNDARY_MARGIN = 0.10        # 이 값 미만이면 '경계 향수'

VOTE_COLS = ["id", "winter", "spring", "summer", "autumn",
             "perceived_female", "perceived_female_leaning", "perceived_unisex",
             "perceived_male_leaning", "perceived_male"]
MIN_VOTES = 20


def sha256(path):
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


# --------------------------------------------------------------------------
# 입력 준비
# --------------------------------------------------------------------------
def perception_distance(ids, path=None):
    """사용자 투표 축(따뜻함 · 남성향)에서 거리행렬. Phase 0 축 회전과 같은 정의."""
    from scipy.spatial.distance import squareform, pdist
    raw = pd.read_csv(sm.PERFUMES_CSV, low_memory=False, usecols=VOTE_COLS).set_index("id")
    raw = raw.loc[ids]
    seas = raw[["winter", "spring", "summer", "autumn"]].astype(float)
    st = seas.sum(axis=1)
    warmth = np.where(st >= MIN_VOTES,
                      ((seas.winter + seas.autumn) - (seas.summer + seas.spring))
                      / st.replace(0, np.nan), np.nan)
    g = raw[["perceived_female", "perceived_female_leaning", "perceived_unisex",
             "perceived_male_leaning", "perceived_male"]].astype(float)
    gt = g.sum(axis=1)
    masc = np.where(gt >= MIN_VOTES,
                    ((g.perceived_male + 0.5 * g.perceived_male_leaning)
                     - (g.perceived_female + 0.5 * g.perceived_female_leaning))
                    / gt.replace(0, np.nan), np.nan)

    def zf(v):
        v = np.asarray(v, float)
        v = np.where(np.isnan(v), np.nanmedian(v), v)
        return (v - v.mean()) / (v.std() or 1.0)

    P = np.c_[zf(warmth), zf(masc)]
    Dp = squareform(pdist(P))
    return Dp / Dp.max(), int((~np.isnan(warmth)).sum()), int((~np.isnan(masc)).sum())


def family_profile_distance(M):
    Mn = M / np.maximum(np.linalg.norm(M, axis=1, keepdims=True), 1e-12)
    D = 1.0 - Mn @ Mn.T
    np.fill_diagonal(D, 0.0)
    return np.clip(D, 0.0, None)


# --------------------------------------------------------------------------
# Territory 방식
# --------------------------------------------------------------------------
def umap_layout(D, seed, y=None, target_weight=None):
    import umap
    kw = dict(n_neighbors=10, min_dist=0.1, metric="precomputed", random_state=seed)
    if y is not None:
        kw.update(target_metric="categorical", target_weight=target_weight)
        return np.asarray(umap.UMAP(**kw).fit_transform(D, y=y), dtype=float)
    return np.asarray(umap.UMAP(**kw).fit_transform(D), dtype=float)


def fixed_territory(D, labels, families, seed, gap=1.0, radius=0.42):
    """C4 — 해역 중심을 계열 간 평균거리 MDS 로 놓고 해역 안에서만 국소 UMAP."""
    from sklearn.manifold import MDS
    import umap
    labels = np.asarray(labels, dtype=object)
    K = len(families)
    Dk = np.zeros((K, K))
    for i, a in enumerate(families):
        ia = np.flatnonzero(labels == a)
        for j, b in enumerate(families):
            if i < j:
                ib = np.flatnonzero(labels == b)
                Dk[i, j] = Dk[j, i] = D[np.ix_(ia, ib)].mean()
    C = MDS(n_components=2, dissimilarity="precomputed", random_state=seed,
            normalized_stress="auto").fit_transform(Dk)
    C = C - C.mean(axis=0)
    C = C / (np.abs(C).max() or 1.0)
    cnt = np.array([(labels == a).sum() for a in families], float)
    rad = np.sqrt(cnt)
    rad = rad / rad.max() * radius
    out = np.zeros((len(labels), 2))
    for i, a in enumerate(families):
        idx = np.flatnonzero(labels == a)
        if len(idx) >= 4:
            loc = umap.UMAP(n_neighbors=min(10, len(idx) - 1), min_dist=0.1,
                            metric="precomputed",
                            random_state=seed).fit_transform(D[np.ix_(idx, idx)])
            loc = np.asarray(loc, float)
            loc -= loc.mean(axis=0)
            loc /= (np.abs(loc).max() or 1.0)
        elif len(idx) == 1:
            loc = np.zeros((1, 2))
        else:
            loc = np.c_[np.linspace(-1, 1, len(idx)), np.zeros(len(idx))]
        out[idx] = C[i] * gap + loc * rad[i]
    return out


def wheel_anchor(M, families, seed, local_D=None, labels=None, radius=0.0):
    """C5/C6 — 계열 앵커를 원에 배치하고 Family Score 로 위치를 정한다 (RadViz).

    radius > 0 이면 각 향수를 자기 계열 앵커 쪽으로 모은 뒤 셀 안에서 국소 배치한다(C6).
    """
    import umap
    ang = np.linspace(0, 2 * np.pi, len(families), endpoint=False)
    anchors = np.c_[np.cos(ang), np.sin(ang)]
    pos = M @ anchors
    if radius <= 0:
        return pos
    labels = np.asarray(labels, dtype=object)
    out = np.zeros_like(pos)
    for i, a in enumerate(families):
        idx = np.flatnonzero(labels == a)
        if not len(idx):
            continue
        center = anchors[i]
        if len(idx) >= 4 and local_D is not None:
            loc = umap.UMAP(n_neighbors=min(10, len(idx) - 1), min_dist=0.1,
                            metric="precomputed",
                            random_state=seed).fit_transform(local_D[np.ix_(idx, idx)])
            loc = np.asarray(loc, float)
            loc -= loc.mean(axis=0)
            loc /= (np.abs(loc).max() or 1.0)
        else:
            loc = np.zeros((len(idx), 2))
        out[idx] = center + loc * radius
    return out


# --------------------------------------------------------------------------
# 지표
# --------------------------------------------------------------------------
def readability(coords, labels, families):
    import collections
    from scipy.spatial.distance import squareform, pdist
    coords = np.asarray(coords, float)
    labels = np.asarray(labels, dtype=object)
    obs, exp, per = bm.region_cohesion(coords, labels, k=NEIGHBOR_K)
    D = squareform(pdist(coords))
    np.fill_diagonal(D, np.inf)
    nn = np.argsort(D, axis=1)[:, :NEIGHBOR_K]
    shares = np.array([collections.Counter(labels[r]).most_common(1)[0][1] / NEIGHBOR_K
                       for r in nn])
    sizes = pd.Series(labels).value_counts()
    return {"observed_cohesion": round(float(obs), 4),
            "random_expected_cohesion": round(float(exp), 4),
            "cohesion_ratio": round(float(obs / exp), 3),
            "neighborhood_top_family_share": round(float(shares.mean()), 4),
            "purity_ge_0.7": int((shares >= 0.7).sum()),
            "size_max_share": round(float(sizes.max() / len(labels)), 4),
            "per_family_cohesion": per}


def region_field(coords, labels, families, min_members=3):
    """계열별 KDE argmax 격자 — 영역이 몇 조각으로 갈라지는지와 자기 영역 위 비율."""
    from scipy.ndimage import label as cc_label
    coords = np.asarray(coords, float)
    labels = np.asarray(labels, dtype=object)
    lo, hi, width, height, sample, xs, ys = bkt.make_grid(coords)
    usable = [f for f in families if (labels == f).sum() >= min_members]
    if len(usable) < 2:
        return None
    G = np.zeros((len(usable), height, width))
    for i, f in enumerate(usable):
        g = bkt.density(coords[labels == f], sample, width, height)
        G[i] = g / g.max()
    win = G.argmax(axis=0)
    row, col = bkt.cell_index(coords, lo, hi, width, height)
    on_own = counted = 0
    for i, f in enumerate(labels):
        if f not in usable:
            continue
        counted += 1
        if usable[win[row[i], col[i]]] == f:
            on_own += 1
    frags = []
    for i in range(len(usable)):
        m = win == i
        lab, _ = cc_label(m)
        sz = np.bincount(lab.ravel())[1:]
        frags.append(int((sz >= 30).sum()))
    return {"on_own_region": round(on_own / counted, 4),
            "families_with_region": len(usable),
            "fragments_total": int(sum(frags)), "fragments_max": int(max(frags)),
            "grid": f"{width}x{height}"}


def guardrail(coords, index_of, edges, labels, ids):
    pos = {int(v): i for i, v in enumerate(ids)}
    lab = np.asarray(labels, dtype=object)
    same = [(a, b) for a, b in edges if lab[pos[a]] == lab[pos[b]]]
    cross = [(a, b) for a, b in edges if lab[pos[a]] != lab[pos[b]]]
    out = {"cross_pairs": len(cross), "same_pairs": len(same)}
    if cross:
        out["cross_family_proximity"] = round(
            bm.edge_distance_percentile(coords, index_of, cross)[0], 4)
    if same:
        out["same_family_proximity"] = round(
            bm.edge_distance_percentile(coords, index_of, same)[0], 4)
    return out


def boundary_consistency(coords, labels, families, M, margin_thr=BOUNDARY_MARGIN):
    """margin 이 작은 향수가 실제로 두 영역 사이에 있는가.

    각 향수에서 자기 계열 중심까지의 거리와 2위 계열 중심까지의 거리 비를 본다.
    경계 향수라면 두 거리가 비슷해야 한다.
    """
    coords = np.asarray(coords, float)
    labels = np.asarray(labels, dtype=object)
    srt = np.sort(M, axis=1)
    margin = srt[:, -1] - srt[:, -2]
    order = np.argsort(-M, axis=1)
    centers = {f: coords[labels == f].mean(axis=0) for f in families
               if (labels == f).sum() > 0}
    ratios = []
    for i in range(len(coords)):
        f1 = families[order[i, 0]]
        f2 = families[order[i, 1]]
        if f1 not in centers or f2 not in centers:
            continue
        d1 = np.linalg.norm(coords[i] - centers[f1])
        d2 = np.linalg.norm(coords[i] - centers[f2])
        ratios.append(d1 / (d1 + d2) if (d1 + d2) > 0 else 0.5)
    ratios = np.array(ratios)
    is_boundary = margin[:len(ratios)] < margin_thr
    return {"boundary_perfumes": int(is_boundary.sum()),
            "boundary_share": round(float(is_boundary.mean()), 4),
            "center_ratio_boundary": round(float(ratios[is_boundary].mean()), 4)
            if is_boundary.any() else None,
            "center_ratio_clear": round(float(ratios[~is_boundary].mean()), 4)
            if (~is_boundary).any() else None,
            "reading": ("경계 향수의 중심거리비가 0.5 에 가까우면 실제로 두 영역 사이에 있다. "
                        "명확한 향수보다 0.5 에 가까워야 정상")}


def transition_zone(coords, labels, families, M):
    """C7 — 계열 점수의 1·2위 차가 작은 구역이 지도의 얼마를 차지하는가."""
    coords = np.asarray(coords, float)
    lo, hi, width, height, sample, xs, ys = bkt.make_grid(coords)
    usable = [f for f in families if (np.asarray(labels) == f).sum() >= 3]
    G = np.zeros((len(usable), height, width))
    for i, f in enumerate(usable):
        g = bkt.density(coords[np.asarray(labels) == f], sample, width, height)
        G[i] = g / g.max()
    srt = np.sort(G, axis=0)
    grid_margin = srt[-1] - srt[-2]
    out = {}
    for t in (0.05, 0.10, 0.20):
        out[f"zone_share_margin_lt_{t}"] = round(float((grid_margin < t).mean()), 4)
    srt_m = np.sort(M, axis=1)
    pm = srt_m[:, -1] - srt_m[:, -2]
    out["perfume_share_margin_lt_0.10"] = round(float((pm < 0.10).mean()), 4)
    out["reading"] = ("격자 margin 이 작은 구역이 전이 지대다. 이게 지도 대부분이면 "
                      "사용자가 '여기가 어느 지역인가' 를 읽을 수 없다")
    return out


# --------------------------------------------------------------------------
def main() -> None:
    os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))  # MAP/
    os.makedirs(OUT_DIR, exist_ok=True)
    t0 = time.time()

    print("=" * 78)
    print("Phase 3b — Territory 방식 비교 (Set B 9계열 · UMAP seed 42 기준)")
    print("=" * 78)

    df, targets, idf_map, _S, D_g, index_of_g, ce_g, _ae = bm.prepare(
        with_selection_comparison=False)
    korea_ids = pd.read_csv(TOP200).fragrantica_id.astype(int).tolist()
    korea = df.set_index("id").loc[korea_ids].reset_index()
    index_of_k = {int(v): i for i, v in enumerate(korea_ids)}
    S_k, _, _ = sm.base_similarity(korea.accord_list.tolist(), korea.note_set.tolist(), idf_map)
    D_k = 1.0 - S_k
    np.fill_diagonal(D_k, 0.0)
    rin = bm.edges_within(sm.load_edges("reminds_edges.csv"), set(korea_ids))
    ce_k = [(int(a), int(b)) for a, b in rin[bm.confident(rin)][["src", "dst"]].itertuples(
        index=False, name=None)]

    res_k = es.family_scores(korea.accord_list.tolist(), SYSTEM)
    res_g = es.family_scores(targets.accord_list.tolist(), SYSTEM)
    families = res_k["families"]
    lab_k, lab_g = res_k["argmax"], res_g["argmax"]
    M_k, M_g = res_k["M"], res_g["M"]
    fam_idx = {f: i for i, f in enumerate(families)}
    y_k = np.array([fam_idx[f] for f in lab_k])
    y_g = np.array([fam_idx[f] for f in lab_g])
    # C3 — 계열이 명확한 향수만 라벨 (RuleB)
    srt_k = np.sort(M_k, axis=1)
    marg_k = srt_k[:, -1] - srt_k[:, -2]
    y_k_semi = np.where(marg_k >= C3_MARGIN, y_k, -1)
    srt_g = np.sort(M_g, axis=1)
    marg_g = srt_g[:, -1] - srt_g[:, -2]
    y_g_semi = np.where(marg_g >= C3_MARGIN, y_g, -1)
    print(f"Set B {len(families)}계열 · Korea 라벨 200 / C3 라벨 {(y_k_semi >= 0).sum()} "
          f"({(y_k_semi >= 0).mean():.1%}) · Global C3 라벨 {(y_g_semi >= 0).sum()} "
          f"({(y_g_semi >= 0).mean():.1%})")

    Dp_k, nw, nm = perception_distance(korea_ids)
    Dp_g, _, _ = perception_distance(targets.id.astype(int).tolist())
    Df_k, Df_g = family_profile_distance(M_k), family_profile_distance(M_g)
    print(f"인식 축 투표 — 계절 {nw}/200 · 성별 {nm}/200")

    doc = json.loads(open(V2_JSON, encoding="utf-8").read())
    by_id = {p["fragrantica_id"]: (p["x"], p["y"]) for p in doc["points"]}
    base_k = np.array([by_id[i] for i in korea_ids], dtype=float)

    # ---- 방식 정의 ----
    def methods(pop):
        D = D_k if pop == "korea200" else D_g
        y = y_k if pop == "korea200" else y_g
        ysemi = y_k_semi if pop == "korea200" else y_g_semi
        M = M_k if pop == "korea200" else M_g
        lab = lab_k if pop == "korea200" else lab_g
        Dp = Dp_k if pop == "korea200" else Dp_g
        Df = Df_k if pop == "korea200" else Df_g
        base = (lambda s: base_k) if pop == "korea200" else (
            lambda s: umap_layout(D, s))
        out = [
            ("C1 post-hoc", "좌표 유지 + 계열 밀도 영역", lambda s: base(s)),
            ("C7 gradient", "좌표 유지 + 전이 지대 렌더링", lambda s: base(s)),
        ]
        for w in (0.2, 0.35, 0.5, 0.7):
            out.append((f"C2 supervised w={w}", "계열 라벨을 UMAP target 으로",
                        lambda s, w=w: umap_layout(D, s, y=y, target_weight=w)))
        for w in (0.35, 0.5):
            out.append((f"C3 semi w={w}", f"margin>={C3_MARGIN} 인 향수만 라벨",
                        lambda s, w=w: umap_layout(D, s, y=ysemi, target_weight=w)))
        out += [
            ("C4 fixed+local", "해역 고정 + 해역 내 국소 UMAP",
             lambda s: fixed_territory(D, lab, families, s)),
            ("C5 wheel anchor", "계열 앵커 원배치 + Family Score",
             lambda s: wheel_anchor(M, families, s)),
            ("C6 anchor+local", "앵커 셀 + 셀 내 국소 유사도",
             lambda s: wheel_anchor(M, families, s, local_D=D, labels=lab, radius=0.28)),
            ("C8a perception b=0.15", "인식 축만 거리에 섞음 (계열 무관)",
             lambda s: umap_layout(0.85 * D + 0.15 * Dp, s)),
            ("C8b family .35 + perc .15", "계열 + 인식 축을 함께 섞음",
             lambda s: umap_layout(0.5 * D + 0.35 * Df + 0.15 * Dp, s)),
        ]
        return out

    # ---- Korea 200: 가독성 (시드 5개) ----
    print()
    print("=" * 78)
    print("Korea 200 — 영역 가독성 (시드 5개)")
    print("=" * 78)
    print(f"  {'방식':<26}{'ratio':>8}{'이웃최다':>9}{'영역위':>8}{'조각':>6}"
          f"{'최대비중':>9}{'정답간선':>9}{'시드편차':>9}")
    res_korea = {}
    coords_keep = {}
    for name, desc, fn in methods("korea200"):
        ratios, blocks, coord_list = [], [], []
        for s in SEEDS:
            c = np.asarray(fn(s), dtype=float)
            coord_list.append(c)
            blocks.append(readability(c, lab_k, families))
            ratios.append(blocks[-1]["cohesion_ratio"])
        c42 = coord_list[0]
        rf = region_field(c42, lab_k, families)
        m = bm.evaluate_layout(c42, D_k, index_of_k, ce_k)
        gr = guardrail(c42, index_of_k, ce_k, lab_k, korea_ids)
        bc = boundary_consistency(c42, lab_k, families, M_k)
        res_korea[name] = {
            "description": desc, "readability_seed42": blocks[0],
            "region_field": rf, "layout": {k: round(float(v), 4) for k, v in m.items()},
            "guardrail_korea": gr, "boundary": bc,
            "seed_check": {"ratios": ratios,
                           "mean": round(float(np.mean(ratios)), 3),
                           "std": round(float(np.std(ratios)), 3),
                           "min": round(float(np.min(ratios)), 3),
                           "collapsed": bool(np.min(ratios) < 0.7 * np.mean(ratios))},
        }
        if name in ("C1 post-hoc", "C2 supervised w=0.35", "C4 fixed+local",
                    "C5 wheel anchor", "C6 anchor+local", "C8b family .35 + perc .15"):
            coords_keep[name] = c42
        if "C7" in name:
            res_korea[name]["transition"] = transition_zone(c42, lab_k, families, M_k)
        b = blocks[0]
        print(f"  {name:<26}{b['cohesion_ratio']:>8.3f}"
              f"{b['neighborhood_top_family_share']:>9.3f}"
              f"{(rf or {}).get('on_own_region', float('nan')):>8.3f}"
              f"{(rf or {}).get('fragments_total', -1):>6}"
              f"{b['size_max_share']:>9.1%}{m['reminds_pct']:>9.4f}"
              f"{np.std(ratios):>9.3f}")

    # ---- Global 1,000: 보호 지표 (seed 42) ----
    print()
    print("=" * 78)
    print("Global 1,000 — 보호 지표 (seed 42). Gate A 합격선 = baseline + 0.05")
    print("=" * 78)
    base_g = umap_layout(D_g, 42)
    g_ids = targets.id.astype(int).tolist()
    gr_base = guardrail(base_g, index_of_g, ce_g, lab_g, g_ids)
    gate_line = round(gr_base["cross_family_proximity"] + GATE_A_MARGIN, 4)
    print(f"baseline cross-family 근접도 {gr_base['cross_family_proximity']} "
          f"({gr_base['cross_pairs']}쌍) -> Gate A 합격선 {gate_line}")
    print()
    print(f"  {'방식':<26}{'횡단근접':>9}{'Δ':>9}{'동일근접':>9}{'trust@10':>10}"
          f"{'overlap':>9}{'ratio':>8}  판정")
    res_global = {}
    for name, desc, fn in methods("global1000"):
        c = np.asarray(fn(42), dtype=float)
        gr = guardrail(c, index_of_g, ce_g, lab_g, g_ids)
        m = bm.evaluate_layout(c, D_g, index_of_g, ce_g)
        rd = readability(c, lab_g, families)
        prox = gr.get("cross_family_proximity", float("nan"))
        delta = prox - gr_base["cross_family_proximity"]
        verdict = "PASS" if prox <= gate_line else "DROP"
        res_global[name] = {"description": desc, "guardrail": gr,
                            "layout": {k: round(float(v), 4) for k, v in m.items()},
                            "readability": rd, "gate_a_delta": round(float(delta), 4),
                            "gate_a": verdict}
        print(f"  {name:<26}{prox:>9.4f}{delta:>+9.4f}"
              f"{gr.get('same_family_proximity', float('nan')):>9.4f}"
              f"{m['trust@10']:>10.4f}{m['knn_overlap@10']:>9.4f}"
              f"{rd['cohesion_ratio']:>8.3f}  {verdict}")

    # ---- 좌표 저장 ----
    frames = []
    for name, c in coords_keep.items():
        frames.append(pd.DataFrame({"method": name, "fragrantica_id": korea_ids,
                                    "x": c[:, 0], "y": c[:, 1],
                                    "family": lab_k}))
    pd.concat(frames).to_csv(os.path.join(OUT_DIR, "coordinates_korea200.csv"),
                             index=False, encoding="utf-8-sig")

    passed = [n for n, v in res_global.items() if v["gate_a"] == "PASS"]
    print()
    print(f"Gate A 통과 {len(passed)}/{len(res_global)}: {passed}")

    metrics = {
        "projection": "umap n_neighbors=10 min_dist=0.1 seed=42 (팀 결정)",
        "family_definition": f"Set B — {es.MAPPING_VERSION} accord 기반 {len(families)}계열",
        "families": families,
        "families_ko": [fm.FAMILY_DEF[f][0] for f in families],
        "c3_rule": f"RuleB — margin >= {C3_MARGIN}",
        "gate_a": {"baseline_cross_family_proximity": gr_base["cross_family_proximity"],
                   "margin": GATE_A_MARGIN, "pass_line": gate_line,
                   "population": "global1000", "cross_pairs": gr_base["cross_pairs"]},
        "korea200": res_korea, "global1000": res_global,
        "gate_a_passed": passed,
        "stability_policy": "팀 결정 — Hard Gate 아님. 구조 붕괴 여부만 기록",
        "population_roles": ("영역 가독성은 Korea 200, 유사 향수 훼손 보호는 Global 1,000 "
                             "(Korea 는 계열 횡단 쌍이 25쌍뿐이라 판정에 쓰지 않는다)"),
    }
    with open(os.path.join(OUT_DIR, "metrics.json"), "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=1)
        f.write("\n")

    flat = []
    for name in res_korea:
        k, g = res_korea[name], res_global[name]
        flat.append({
            "method": name, "description": k["description"],
            "korea_cohesion_ratio": k["readability_seed42"]["cohesion_ratio"],
            "korea_neighborhood_purity": k["readability_seed42"]["neighborhood_top_family_share"],
            "korea_on_own_region": (k["region_field"] or {}).get("on_own_region"),
            "korea_fragments": (k["region_field"] or {}).get("fragments_total"),
            "korea_reminds_pct": k["layout"]["reminds_pct"],
            "korea_trust10": k["layout"]["trust@10"],
            "korea_seed_std": k["seed_check"]["std"],
            "korea_collapsed": k["seed_check"]["collapsed"],
            "global_cross_proximity": g["guardrail"].get("cross_family_proximity"),
            "global_gate_a_delta": g["gate_a_delta"], "global_gate_a": g["gate_a"],
            "global_trust10": g["layout"]["trust@10"],
            "global_overlap10": g["layout"]["knn_overlap@10"],
            "global_cohesion_ratio": g["readability"]["cohesion_ratio"],
        })
    pd.DataFrame(flat).to_csv(os.path.join(OUT_DIR, "territory_comparison.csv"),
                              index=False, encoding="utf-8-sig")

    manifest = {
        "experiment_id": "phase3b", "phase": 3, "status": "NEW",
        "hypothesis": ("영역 표현 방식에 따라 '여기가 어느 구역인가' 를 읽는 정도와 "
                       "사람이 닮았다고 한 향수의 배치가 달라진다"),
        "user_meaning": "영역이 읽히면서도 닮았다고 한 향수가 갈라지지 않는 표현이 있는가",
        "changed_variable": "Territory 표현 방식 (유사도·투영·계열 정의 고정)",
        "population": ["korea200", "global1000"],
        "snapshot_hash": {"perfumes_csv": sha256(sm.PERFUMES_CSV),
                          "korea_top200_csv": sha256(TOP200)},
        "projection": "umap n_neighbors=10 min_dist=0.1 seed=42",
        "family_mapping_version": es.MAPPING_VERSION,
        "family_score_version": "FS1",
        "seeds": list(SEEDS),
        "primary_metrics": ["cohesion_ratio", "neighborhood_purity", "on_own_region"],
        "guardrail_metrics": [f"cross_family_proximity <= {gate_line} (Global 1,000)"],
        "gate_a_passed": passed,
        "region_field_params": "build_korea_terrain 격자 (D12: bandwidth scott x0.5)",
        "elapsed_sec": round(time.time() - t0, 1),
    }
    with open(os.path.join(OUT_DIR, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print()
    print(f"총 소요 {time.time()-t0:.0f}초")
    print(f"  -> {OUT_DIR}/ (metrics.json, manifest.json, territory_comparison.csv, "
          f"coordinates_korea200.csv)")


if __name__ == "__main__":
    main()

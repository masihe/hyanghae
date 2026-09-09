"""Phase 2 투영 후보의 의존성 설치 가능성과 실제 데이터 구동을 확인한다 (Phase 0-10).

Run with venv/Scripts/python.exe src/map/experiment_phase0_dependency_check.py

**왜 이 확인인가.** Phase 2 는 같은 유사도 정의를 여러 투영 알고리즘으로 2D 로 옮겨
비교하는 단계다. 그런데 후보를 확정한 뒤에 "설치가 안 된다" 를 발견하면 Phase 2 설계를
다시 써야 한다. 그래서 후보를 확정하기 전에 (1) 설치가 되는가 (2) import 가 되는가
(3) **우리 실제 데이터로 돌아가는가** 를 먼저 확인한다.

**무작위 행렬로 확인하지 않는다.** 200x200 무작위 거리행렬은 통과하는데 실제 데이터에서
깨지는 경우가 있다 (희소 특징행렬, 동일 좌표 중복, 삼각부등식 위반 등). 그래서 Korea 200
스냅샷의 실제 accord/note 로 거리행렬과 특징행렬을 만들어 넣는다.

**precomputed 지원 여부가 핵심 쟁점이다.** 지금 지도는 `metric="precomputed"` 로 우리가
정의한 유사도 행렬을 UMAP 에 직접 넣는다. 투영 알고리즘이 precomputed 를 못 받으면
같은 유사도 정의를 비교할 수 없고 (알고리즘이 자기 내부 거리로 다시 계산한다),
그러면 Phase 2 의 "투영만 바꾼다" 라는 통제가 깨진다. 이 스크립트는 후보마다
precomputed 를 받는지, 못 받으면 어떤 입력으로 대체할 수 있는지를 기록한다.

**이 스크립트는 Phase 2 실험이 아니다.** 여기서 재는 trust@10 등은 "출력이 쓰레기가
아니다" 를 확인하는 smoke test 값이며 시드 1개다. Phase 2 판정에 인용하면 안 된다
(게이트 판정은 시드 5개의 평균과 최소값으로 한다 — experiments/README.md).

산출: experiments/phase0/dependency_check.json
"""
import importlib.metadata as md
import json
import os
import sys
import time
import traceback

import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "common")))
import scent_map as sm
import build_map as bm

PHASE0 = os.path.join("experiments", "phase0")
SNAPSHOT = os.path.join(PHASE0, "snapshots", "korea200.csv")
OUT_JSON = os.path.join(PHASE0, "dependency_check.json")

SEED = 42
CORE_PKGS = ["numpy", "pandas", "scikit-learn", "scipy", "numba", "umap-learn",
             "llvmlite", "torch", "pacmap", "trimap", "annoy", "faiss-cpu"]

# 설치 전에 실측해 둔 버전. 4단계 비교의 기준값이다 (사람이 옮겨 적은 값이 아니라
# 같은 방식으로 실측한 값이다 — 본문 주석은 dependency_check.json 의 versions 참조).
BEFORE_MAP = {"numpy": "2.4.6", "pandas": "3.0.5", "scikit-learn": "1.9.0",
              "scipy": "1.17.1", "numba": "0.67.0", "umap-learn": "0.5.12",
              "llvmlite": "0.49.0", "torch": "2.14.0+cpu",
              "pacmap": None, "trimap": None, "annoy": None, "faiss-cpu": None}
BEFORE_EDA = {"numpy": "2.4.6", "pandas": "3.0.5", "scikit-learn": "1.9.0",
              "scipy": "1.17.1", "numba": None, "umap-learn": None,
              "llvmlite": None, "torch": None,
              "pacmap": None, "trimap": None, "annoy": None, "faiss-cpu": None}

EDA_PYTHON = os.path.join("..", "EDA", "venv", "Scripts", "python.exe")


def versions_of(python_exe=None):
    """현재 인터프리터 또는 다른 venv 의 패키지 버전을 읽는다. 없으면 None."""
    if python_exe is None:
        out = {}
        for p in CORE_PKGS:
            try:
                out[p] = md.version(p)
            except md.PackageNotFoundError:
                out[p] = None
        return out
    import subprocess
    code = (
        "import importlib.metadata as md, json\n"
        f"pkgs={CORE_PKGS!r}\n"
        "o={}\n"
        "for p in pkgs:\n"
        "    try: o[p]=md.version(p)\n"
        "    except Exception: o[p]=None\n"
        "print(json.dumps(o))\n"
    )
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    r = subprocess.run([python_exe, "-c", code], capture_output=True, text=True, env=env)
    if r.returncode != 0:
        return {"_error": r.stderr.strip()[:400]}
    return json.loads(r.stdout)


def load_korea200():
    """스냅샷의 200개 id 로 거리행렬과 특징행렬을 만든다.

    거리행렬은 experiment_phase0_axis_rotation.py 와 같은 방식,
    특징행렬은 build_map.py main() 과 같은 방식으로 만든다 (둘 다 재정의하지 않는다).
    """
    snap = pd.read_csv(SNAPSHOT)
    ids = snap["id"].astype(int).tolist()

    perf = sm.load_perfumes().set_index("id")
    rows = perf.loc[ids].reset_index()
    idf_map = sm.load_note_idf()

    S, _, _ = sm.base_similarity(rows.accord_list.tolist(), rows.note_set.tolist(), idf_map)
    D = 1.0 - S
    np.fill_diagonal(D, 0.0)

    A, _ = sm.build_accord_matrix(list(rows["accord_list"]))
    B, w, _, _ = sm.build_note_matrix(list(rows["note_set"]), idf_map)
    Bn = B * w
    norm = np.linalg.norm(Bn, axis=1, keepdims=True)
    norm[norm == 0] = 1
    features = np.hstack([A, Bn / norm])

    index_of = {int(v): i for i, v in enumerate(ids)}
    rin = bm.edges_within(sm.load_edges("reminds_edges.csv"), set(ids))
    conf_edges = [(int(a), int(b)) for a, b in
                  rin[bm.confident(rin)][["src", "dst"]].itertuples(index=False, name=None)]
    return ids, D, features, index_of, conf_edges


def smoke(name, fn, D, index_of, conf_edges, n):
    """투영 1회를 돌리고 출력이 정상 좌표인지 확인한다. 실패는 잡아서 기록한다."""
    rec = {"name": name, "ok": False}
    t = time.time()
    try:
        coords = np.asarray(fn(), dtype=float)
        rec["elapsed_sec"] = round(time.time() - t, 2)
        rec["shape"] = list(coords.shape)
        if coords.shape != (n, 2):
            rec["error"] = f"shape 이 (200, 2) 가 아니다: {coords.shape}"
            return rec, None
        if not np.isfinite(coords).all():
            rec["error"] = "좌표에 NaN 또는 inf 가 있다"
            return rec, None
        # 모든 점이 한 곳에 뭉치면 좌표가 나왔어도 지도로 쓸 수 없다.
        rec["coord_spread"] = round(float(coords.std(axis=0).mean()), 6)
        rec["n_unique_points"] = int(len(np.unique(np.round(coords, 6), axis=0)))
        m = bm.evaluate_layout(coords, D, index_of, conf_edges)
        rec["smoke_metrics_seed42_only"] = {k: (round(float(v), 4) if k != "n_edges" else int(v))
                                            for k, v in m.items()}
        rec["ok"] = True
        return rec, coords
    except Exception as e:
        rec["elapsed_sec"] = round(time.time() - t, 2)
        rec["error"] = f"{type(e).__name__}: {e}"
        rec["traceback_tail"] = traceback.format_exc().strip().splitlines()[-1][:300]
        return rec, None


def main() -> None:
    os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))  # MAP/

    print("=" * 78)
    print("Phase 0-10 — Phase 2 투영 후보 의존성 확인 (실제 Korea 200 데이터로 구동)")
    print("=" * 78)

    after_map = versions_of()
    after_eda = versions_of(EDA_PYTHON)

    print("\n[버전] MAP venv 설치 후")
    for p in CORE_PKGS:
        was, now = BEFORE_MAP.get(p), after_map.get(p)
        tag = "신규" if was is None and now else ("변경" if was != now else "")
        print(f"  {p:<14} {str(was):<12} -> {str(now):<12} {tag}")

    # 기존 패키지가 다운그레이드/제거되지 않았는지가 확인의 핵심이다.
    regressions = [{"package": p, "before": BEFORE_MAP[p], "after": after_map.get(p)}
                   for p in CORE_PKGS
                   if BEFORE_MAP.get(p) is not None and after_map.get(p) != BEFORE_MAP[p]]
    eda_changes = [{"package": p, "before": BEFORE_EDA[p], "after": after_eda.get(p)}
                   for p in CORE_PKGS if after_eda.get(p) != BEFORE_EDA.get(p)]
    print(f"\n  MAP 기존 패키지 변경 {len(regressions)}건 · EDA venv 변경 {len(eda_changes)}건")

    # ---- import ----
    print("\n[import]")
    imports = {}
    for mod in ("pacmap", "trimap"):
        try:
            m = __import__(mod)
            imports[mod] = {"ok": True, "version": getattr(m, "__version__", None)}
            print(f"  {mod:<8} OK  ({imports[mod]['version']})")
        except Exception as e:
            imports[mod] = {"ok": False, "error": f"{type(e).__name__}: {e}"}
            print(f"  {mod:<8} 실패  {imports[mod]['error']}")

    # ---- 실제 데이터 ----
    ids, D, features, index_of, conf_edges = load_korea200()
    n = len(ids)
    print(f"\n[데이터] Korea 200 스냅샷 {n}개 · 거리행렬 {D.shape} · "
          f"특징행렬 {features.shape} · 신뢰 간선 {len(conf_edges)}쌍")
    print(f"  거리 범위 {D[~np.eye(n, dtype=bool)].min():.4f} ~ "
          f"{D[~np.eye(n, dtype=bool)].max():.4f}")

    runs = []
    precomputed_support = {}

    # ---- 기준: UMAP precomputed (지금 출하 파이프라인과 같은 입력) ----
    print("\n[UMAP] precomputed — 지금 파이프라인 기준선")
    import umap
    rec, _ = smoke("UMAP(precomputed)",
                   lambda: umap.UMAP(n_components=2, metric="precomputed", n_neighbors=10,
                                     min_dist=0.1, random_state=SEED).fit_transform(D),
                   D, index_of, conf_edges, n)
    runs.append(rec)
    print(f"  {'OK' if rec['ok'] else '실패'} · {rec.get('elapsed_sec')}s · "
          f"{rec.get('smoke_metrics_seed42_only') or rec.get('error')}")

    # ---- PaCMAP ----
    if imports["pacmap"]["ok"]:
        import pacmap
        # 먼저 precomputed 를 정말 못 받는지 실행으로 확인한다 (문서만 믿지 않는다).
        print("\n[PaCMAP] precomputed 지원 여부를 실행으로 확인")
        try:
            pacmap.PaCMAP(n_components=2, n_neighbors=10, distance="precomputed",
                          random_state=SEED).fit_transform(D)
            precomputed_support["PaCMAP"] = {"supported": True}
            print("  precomputed 통과")
        except Exception as e:
            precomputed_support["PaCMAP"] = {
                "supported": False,
                "error": f"{type(e).__name__}: {e}",
                # pacmap/pacmap.py:1162 의 VALID_METRICS 를 그대로 옮긴 것이다.
                # 'precomputed' 가 없다.
                "allowed_metrics": sorted(["angular", "euclidean", "manhattan",
                                           "hamming", "dot"]),
                "allowed_metrics_source": "pacmap/pacmap.py:1162 VALID_METRICS",
                "fallback": "accord+note 특징행렬 (build_map.py main() 과 동일)",
            }
            print(f"  미지원 — {type(e).__name__}: {e}")

        print("[PaCMAP] 특징행렬 입력으로 구동")
        rec, _ = smoke("PaCMAP(features)",
                       lambda: pacmap.PaCMAP(n_components=2, n_neighbors=10,
                                             random_state=SEED).fit_transform(features),
                       D, index_of, conf_edges, n)
        runs.append(rec)
        print(f"  {'OK' if rec['ok'] else '실패'} · {rec.get('elapsed_sec')}s · "
              f"{rec.get('smoke_metrics_seed42_only') or rec.get('error')}")

    # ---- TriMap ----
    if imports["trimap"]["ok"]:
        import trimap
        # trimap 1.2.0 은 구현이 두 개다.
        #   TRIMAP      — 기존 numba/annoy 구현. annoy 가 없으면 import 자체가 안 된다.
        #   TorchTRIMAP — torch 구현. annoy 를 쓰지 않고 use_dist_matrix 로 거리행렬을 받는다.
        print("\n[TriMap] 두 구현 중 어느 것이 쓸 수 있는지 확인")
        legacy = {}
        try:
            trimap.TRIMAP
            legacy = {"available": True}
            print("  TRIMAP(legacy, annoy) 사용 가능")
        except Exception as e:
            legacy = {"available": False, "error": f"{type(e).__name__}: {e}"}
            print(f"  TRIMAP(legacy, annoy) 사용 불가 — {type(e).__name__}: {e}")

        print("[TriMap] TorchTRIMAP + use_dist_matrix=True (거리행렬 직접 입력)")
        rec, _ = smoke("TorchTRIMAP(dist_matrix)",
                       lambda: trimap.TorchTRIMAP(n_dims=2, n_inliers=10, n_outliers=5,
                                                  n_random=5, use_dist_matrix=True,
                                                  apply_pca=False, random_state=SEED,
                                                  verbose=False).fit_transform(D).cpu().numpy(),
                       D, index_of, conf_edges, n)
        runs.append(rec)
        print(f"  {'OK' if rec['ok'] else '실패'} · {rec.get('elapsed_sec')}s · "
              f"{rec.get('smoke_metrics_seed42_only') or rec.get('error')}")
        precomputed_support["TriMap"] = {
            "supported": bool(rec["ok"]),
            "how": "TorchTRIMAP(use_dist_matrix=True) — torch 구현이라 annoy 불필요",
            "legacy_TRIMAP_annoy": legacy,
        }

        print("[TriMap] TorchTRIMAP 특징행렬 입력 (대안 경로도 되는지)")
        rec2, _ = smoke("TorchTRIMAP(features)",
                        lambda: trimap.TorchTRIMAP(n_dims=2, n_inliers=10, n_outliers=5,
                                                   n_random=5, random_state=SEED,
                                                   verbose=False).fit_transform(features).cpu().numpy(),
                        D, index_of, conf_edges, n)
        runs.append(rec2)
        print(f"  {'OK' if rec2['ok'] else '실패'} · {rec2.get('elapsed_sec')}s · "
              f"{rec2.get('smoke_metrics_seed42_only') or rec2.get('error')}")

    # ---- 후보 확정 ----
    pacmap_ok = any(r["name"] == "PaCMAP(features)" and r["ok"] for r in runs)
    trimap_ok = any(r["name"] == "TorchTRIMAP(dist_matrix)" and r["ok"] for r in runs)
    candidates = ["UMAP", "t-SNE"]
    if pacmap_ok:
        candidates.append("PaCMAP")
    if trimap_ok:
        candidates.append("TriMap")
    candidates.append("kNN graph")

    excluded = []
    if not pacmap_ok:
        excluded.append({"candidate": "PaCMAP", "reason": imports["pacmap"].get("error")
                         or "실제 데이터 구동 실패"})
    if not trimap_ok:
        excluded.append({"candidate": "TriMap", "reason": imports["trimap"].get("error")
                         or "실제 데이터 구동 실패"})

    print("\n" + "=" * 78)
    print(f"Phase 2 후보: {candidates}")
    if excluded:
        print(f"제외: {excluded}")
    print("=" * 78)

    doc = {
        "experiment_id": "phase0",
        "step": "Phase 0-10 dependency check",
        "purpose": ("Phase 2 투영 후보를 확정하기 전에 설치·import·실제 데이터 구동을 "
                    "확인한다. 여기의 지표는 smoke test 값이며 Phase 2 판정에 쓰지 않는다."),
        "population": "korea200",
        "snapshot": SNAPSHOT.replace("\\", "/"),
        "n_perfumes": n,
        "seed": SEED,
        "install_attempts": [
            {
                "package": "pacmap",
                "command": "venv/Scripts/python.exe -m pip install pacmap",
                "result": "성공",
                "installed": {"pacmap": after_map.get("pacmap"),
                              "faiss-cpu": after_map.get("faiss-cpu")},
                "note": "faiss-cpu 1.15.0 이 kNN 백엔드로 함께 설치됐다. 기존 패키지 변경 없음.",
            },
            {
                "package": "trimap",
                "command": "venv/Scripts/python.exe -m pip install trimap",
                "result": "실패 (의존성 annoy 빌드 불가)",
                "failure_log_key_lines": [
                    "Building wheel for annoy (pyproject.toml): finished with status 'error'",
                    "building 'annoy.annoylib' extension",
                    "error: Microsoft Visual C++ 14.0 or greater is required.",
                    "ERROR: Failed building wheel for annoy",
                ],
                "cause": ("annoy 는 PyPI 에 sdist 만 있고 (--only-binary=:all: 로 확인: "
                          "wheel 0개) C++ 확장을 컴파일해야 한다. 이 Windows 환경에는 "
                          "MSVC 빌드 도구가 없다."),
                "not_done": ("MSVC 빌드 도구 설치(시스템 변경)와 서드파티 annoy 포크 "
                             "git 설치는 하지 않았다."),
            },
            {
                "package": "trimap (재시도)",
                "command": "venv/Scripts/python.exe -m pip install --no-deps trimap",
                "result": "성공",
                "installed": {"trimap": after_map.get("trimap")},
                "rationale": ("trimap 1.2.0 의 __init__.py 는 TorchTRIMAP 만 즉시 import 하고 "
                              "annoy 를 쓰는 legacy TRIMAP 은 __getattr__ 로 지연 로딩한다. "
                              "즉 annoy 는 legacy 경로 전용 의존성이다. annoy 외의 의존성"
                              "(numpy/scikit-learn/numba/torch)은 --dry-run 에서 이미 "
                              "충족 확인됐으므로 --no-deps 로 빠지는 것은 annoy 뿐이다."),
                "side_effect": ("pip check 가 'trimap 1.2.0 requires annoy, which is not "
                                "installed' 를 보고한다. legacy TRIMAP 경로만 못 쓰고 "
                                "TorchTRIMAP 은 정상 동작한다."),
            },
        ],
        "imports": imports,
        "precomputed_support": precomputed_support,
        "pacmap_precomputed_partial_route": {
            "note": ("PaCMAP 은 distance='precomputed' 를 받지 않지만 pair_neighbors 를 "
                     "외부에서 만들어 넣을 수 있다 (shape (n*n_neighbors, 2)). 우리 거리행렬로 "
                     "이웃쌍을 만들어 주입하는 경로다."),
            "limitation": ("그래도 MN/FP 쌍은 PaCMAP 이 X 와 self.distance 로 다시 만든다. "
                           "따라서 완전한 precomputed 가 아니다. Phase 2 에서 이 경로를 쓰려면 "
                           "'유사도 정의가 부분만 반영된다' 를 한계로 적어야 한다."),
            "verified": False,
        },
        "runs": runs,
        "smoke_metric_caveat": ("runs[].smoke_metrics_seed42_only 는 시드 1개 값이고 "
                                "파라미터도 조정하지 않았다. 출력이 정상 좌표인지 확인하는 "
                                "용도이며 Phase 2 알고리즘 비교나 게이트 판정에 인용하면 안 된다."),
        "versions": {
            "map_venv_before": BEFORE_MAP,
            "map_venv_after": after_map,
            "eda_venv_before": BEFORE_EDA,
            "eda_venv_after": after_eda,
            "map_existing_package_changes": regressions,
            "map_existing_packages_intact": len(regressions) == 0,
            "eda_venv_changes": eda_changes,
            "eda_venv_unchanged": len(eda_changes) == 0,
            "eda_venv_isolation": ("두 venv 는 include-system-site-packages=false 이고 "
                                   "site-packages 가 분리돼 있다. EDA venv 에는 어떤 "
                                   "pip 명령도 실행하지 않았다 (버전 읽기만 했다)."),
        },
        "phase2_candidates": candidates,
        "phase2_excluded": excluded,
        "phase2_input_note": ("UMAP·t-SNE·kNN graph 는 precomputed 거리행렬을 받으므로 "
                              "지금 유사도 정의를 그대로 쓴다. TriMap 은 TorchTRIMAP "
                              "use_dist_matrix=True 로 같은 거리행렬을 쓴다. PaCMAP 만 "
                              "특징행렬 입력이라 '입력 표현이 다르다' 를 대조 조건으로 "
                              "manifest 에 적어야 한다 — PaCMAP 의 차이가 투영 방식 때문인지 "
                              "입력 표현 때문인지 구분되지 않는다."),
    }
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print(f"\n  -> {OUT_JSON}")


if __name__ == "__main__":
    main()

"""노트 브리지의 두 문턱(`p` 와 `lift`)을 흔들어 무엇이 달라지는지 잰다.

    ./venv/Scripts/python.exe -W ignore 72_bridge_lift_threshold.py

GMS 호출 0회. 저장된 ①단계 출력을 쓴다. 팀 저장소를 수정하지 않는다. 파일을 만들지 않는다.

왜 재는가
----------
18번이 `p >= 0.5 그리고 lift >= 1.4` 를 권했다. 그런데 **두 숫자 다 이 문제에서
검증되지 않았다.**

    lift >= 1.4   N4 가 `ai_summary` 배수의 통제군에서 정한 값을 빌려 왔다
                  통제군 500·1,000·2,500 에서 배수가 1.17·1.38·1.14 였다
                  **그 통제군은 서술문 검색이고 여기는 노트-accord 동시출현이다**

    p >= 0.5      67번이 규칙을 만들 때 "절반 이상" 이라는 상식으로 쓴 값이다
                  10번 노트북이 정한 값이 아니다

하나만 흔들고 다른 하나를 두면 반쪽짜리 검증이라 둘 다 흔든다.

무엇을 재는가
--------------
    ① lift 스윕     `p >= 0.5` 고정 · lift 를 0(게이트 없음) ~ 2.5 로 움직인다
    ② p 스윕        lift 를 ①의 최적값에 고정 · p 를 0.3 ~ 0.7 로 움직인다
    ③ 부트스트랩     후보들이 서로 갈리는지 짝지어 본다
    ④ 설문 155      최종 후보만 stage 분포를 본다 (정답 라벨이 없어 NDCG 는 못 잰다)

`lift = 0` 행이 18번의 D2, `top1` 행이 D1 이다. 비교 기준으로 함께 싣는다.

깨질 수 있는 곳
----------------
브리지 CSV 가 노트당 상위 5개만 남긴 표라서, 문턱을 아무리 낮춰도 6번째 accord 는
안 나온다. **`lift = 0` 이 "필터 없음" 이 아니라 "이미 상위 5 로 걸러진 것 전부" 다.**

출력 없음. 표준출력에만 쓴다.
"""
import collections
import importlib.util
import json
import re
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "C:/Users/SSAFY/Desktop/S15P21E203/ai")
import nlr_engine  # noqa: E402

SYNTH = ("합성 600", "analysis_outputs/34_evalset_stage1_checkpoint.csv", "sentence")
SURVEY = ("설문 143", "analysis_outputs/37_survey_stage1_checkpoint.csv", "query_text")

# [판정] 설문 체크포인트 155행 중 12행은 향수 요청이 아니라 동의 표현이다 (`네`·`넵`·`예`·
# `넴`). 측정에서 뺀다. 행운의 편지 1건과 향 정보 없는 요청 9건은 **남긴다.**
# 규칙과 근거는 67번에 같은 이름으로 있다. 한쪽만 고치지 말 것. 측정 기록 19번.
SURVEY_NOT_A_QUERY = re.compile(r"^(네|넵|넴|예)\s*[.!]?$|^넵\s*알겠습니다\.?$")
ANSWER_KEY = "analysis_outputs/32_evalset_answer_key.csv"
LEXICON = "data/scent_knowledge/domain_lexicon_v1_14.csv"
BRIDGE = "analysis_outputs/10_note_accord_bridge.csv"

LIFT_GRID = [0.0, 1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 2.0, 2.5]
P_GRID = [0.3, 0.4, 0.5, 0.6, 0.7]
STAGES = ["AND", "SINGLE_BROAD", "RELAXED_OR", "RELAXED_OR_NO_THRESHOLD", "NO_CONDITION"]
BOOT = 20000
SEED = 20260916


def load_rows(path, col):
    """체크포인트 CSV 한 장을 (문장, ①단계 dict, 향수 id) 목록으로 읽는다.

    향수 요청이 아닌 응답은 뺀다. 몇 건을 뺐는지 찍는다 — 조용히 줄이면 뒤의 분모가
    왜 달라졌는지 알 수 없다.
    """
    d = pd.read_csv(path)
    out, dropped = [], 0
    for r in d.to_dict("records"):
        text = str(r[col])
        if SURVEY_NOT_A_QUERY.match(text.strip()):
            dropped += 1
            continue
        try:
            o = json.loads(r["raw_response"])
        except Exception:
            o = None
        pid = int(r["perfume_id"]) if "perfume_id" in r and pd.notna(r["perfume_id"]) else None
        out.append((text, o if isinstance(o, dict) else None, pid))
    if dropped:
        print(f"  {path} — 원본 {len(d)}행 중 향수 요청이 아닌 {dropped}행 제외 "
              f"→ {len(out)}행으로 잰다 (측정 기록 19번)")
    return out


def build_bridge(b, p_min, lift_min, top1=False):
    """브리지 표를 문턱으로 걸러 dict[note_lower, set[accord]] 로 만든다.

    top1=True 면 문턱을 무시하고 노트당 확률 최상위 1개만 쓴다 (18번의 D1).
    """
    out = {}
    if top1:
        sel = b.sort_values("p_accord_given_note", ascending=False).groupby("note").head(1)
    else:
        sel = b[(b["p_accord_given_note"] >= p_min) & (b["lift"] >= lift_min)]
    for r in sel.to_dict("records"):
        out.setdefault(str(r["note"]).strip().lower(), set()).add(r["accord"])
    return out


def measure(index, rows, bridge, ndcg41=None, key=None):
    """한 브리지 설정을 합성/설문 한 벌에 돌린다. dict.

    bridge=None 이면 현행 엔진 그대로다 (브리지를 안 탄다).
    반환 — nonzero(조건을 뽑은 응답 수) · cond(평균 조건 수) · stage(Counter) ·
           ndcg(평균) · per(응답별 NDCG 배열. 부트스트랩용)
    """
    ncond, nonzero, per = [], 0, []
    stage = collections.Counter()
    for text, o, pid in rows:
        hay = " ".join([text] + [str(v) for v in ((o or {}).get("additional_requirements") or [])])
        core = nlr_engine._extract(index, hay)[0]
        for raw in ((o or {}).get("scent_preference") or []):
            a = nlr_engine._normalize_accord(index, raw)
            if a:
                core.add(a)
            elif bridge is not None:
                core |= bridge.get(str(raw).strip().lower(), set())
        avoid = {a for a in (nlr_engine._normalize_accord(index, r)
                             for r in ((o or {}).get("avoid") or [])) if a}
        core = sorted(set(core) - avoid)
        ncond.append(len(core))
        nonzero += bool(core)
        found = nlr_engine.search(index, core, avoid)
        stage[found["stage"]] += 1
        if key is not None and pid is not None:
            C = [a for a in str(key.loc[pid, "C"]).split("|") if a in index["aidx"]]
            if C:
                cols = [index["aidx"][a] for a in C]
                per.append(ndcg41.ndcg_at_k(
                    [int(index["has"][r, cols].sum()) for r in found["rows"]], len(C)))
    return {"nonzero": nonzero, "cond": float(np.mean(ncond)), "stage": stage,
            "ndcg": float(np.mean(per)) if per else None, "per": np.array(per)}


def print_table(title, n, results):
    """results: [(라벨, 브리지 dict 또는 None, measure 결과)] 를 한 표로 찍는다."""
    print("=" * 108)
    print(title)
    print("=" * 108)
    print(f"  {'설정':16s} {'노트':>5s} {'acc/노트':>8s} {'조건추출':>11s} {'평균조건':>8s} "
          f"{'NDCG@5':>10s} {'vs 현행':>10s} " + " ".join(f"{s[:9]:>9s}" for s in STAGES[:4]))
    base = results[0][2]
    for label, br, r in results:
        nn = len(br) if br else 0
        ac = (sum(len(v) for v in br.values()) / nn) if nn else 0.0
        nd = f"{r['ndcg']:.6f}" if r["ndcg"] is not None else "—"
        dl = (f"{r['ndcg'] - base['ndcg']:+.6f}"
              if (r["ndcg"] is not None and base["ndcg"] is not None) else "—")
        print(f"  {label:16s} {nn:>5d} {ac:>8.2f} {r['nonzero']:>5d}/{n} "
              f"{r['nonzero']/n:>4.0%} {r['cond']:>8.2f} {nd:>10s} {dl:>10s} "
              + " ".join(f"{r['stage'][s]:>9d}" for s in STAGES[:4]))
    print()


def bootstrap(pairs, n):
    """짝지은 부트스트랩. pairs: [(라벨A, 배열A, 라벨B, 배열B)]"""
    rng = np.random.default_rng(SEED)
    idx = rng.integers(0, n, size=(BOOT, n))
    print(f"  {'비교':34s} {'차이':>10s} {'95% 구간':>24s} {'차이>0':>8s}")
    for la, a, lb, b in pairs:
        d = b - a
        boot = d[idx].mean(axis=1)
        lo, hi = np.percentile(boot, [2.5, 97.5])
        mark = "" if lo > 0 or hi < 0 else "   <- 0 을 포함. 갈리지 않는다"
        print(f"  {la + ' -> ' + lb:34s} {d.mean():>+10.6f} "
              f"[{lo:>+9.6f}, {hi:>+9.6f}] {(boot > 0).mean():>7.1%}{mark}")
    print()


def main():
    spec = importlib.util.spec_from_file_location("ndcg41", "41_lexicon_ndcg.py")
    ndcg41 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ndcg41)

    index = nlr_engine.load_index(lexicon_csv=LEXICON)
    key = pd.read_csv(ANSWER_KEY).set_index("perfume_id")
    b = pd.read_csv(BRIDGE)
    b = b[b["accord"].isin(index["aidx"])]
    print(f"브리지 {len(b)}행 · 노트 {b['note'].nunique()}개 · accord {b['accord'].nunique()}개")
    print("노트당 상위 5개만 담긴 표다. 문턱을 0 으로 내려도 6번째는 안 나온다.\n")

    rows = load_rows(SYNTH[1], SYNTH[2])
    n = len(rows)
    cur = measure(index, rows, None, ndcg41, key)

    # ① lift 스윕 — p 는 0.5 고정
    res = [("A 현행(브리지 없음)", None, cur),
           ("D1 top1", build_bridge(b, 0, 0, top1=True), None)]
    res[1] = (res[1][0], res[1][1], measure(index, rows, res[1][1], ndcg41, key))
    for lv in LIFT_GRID:
        br = build_bridge(b, 0.5, lv)
        label = "D2 lift 없음" if lv == 0.0 else f"lift >= {lv}"
        res.append((label, br, measure(index, rows, br, ndcg41, key)))
    print_table(f"① lift 스윕 — `p >= 0.5` 고정 · [{SYNTH[0]}] {n}건", n, res)

    # ①의 최적 lift 를 고른다 — NDCG 최대
    swept = [(lbl, br, r) for lbl, br, r in res if lbl.startswith("lift") or lbl.startswith("D2")]
    best = max(swept, key=lambda x: x[2]["ndcg"])
    best_lift = 0.0 if best[0].startswith("D2") else float(best[0].split(">=")[1])
    print(f"  ① 에서 NDCG 가 가장 높은 설정 — {best[0]} (lift {best_lift})\n")

    # ② p 스윕 — lift 는 ①의 최적값 고정
    res2 = [("A 현행(브리지 없음)", None, cur)]
    for pv in P_GRID:
        br = build_bridge(b, pv, best_lift)
        res2.append((f"p >= {pv}", br, measure(index, rows, br, ndcg41, key)))
    print_table(f"② p 스윕 — `lift >= {best_lift}` 고정 · [{SYNTH[0]}] {n}건", n, res2)

    # ③ 부트스트랩 — 현행 · D2(게이트 없음) · 1.4 · 최적 을 짝지어 본다
    print("=" * 108)
    print(f"③ 짝지은 부트스트랩 — 응답별 NDCG 를 짝지어 빼고 {BOOT:,}회 복원추출 (seed {SEED})")
    print("=" * 108)
    pick = {lbl: r["per"] for lbl, _, r in res + res2}
    cur_per = pick["A 현행(브리지 없음)"]

    # (가) 브리지를 넣는 것 자체가 갈리는가
    print("  (가) 현행 대비 — 브리지를 넣는 것 자체")
    bootstrap([("현행", cur_per, lbl, pick[lbl])
               for lbl in ("D1 top1", "D2 lift 없음", best[0])], len(cur_per))

    # (나) 문턱끼리 갈리는가 — 최적값을 기준으로 스윕 전체를 짝짓는다.
    #      여기가 핵심이다. NDCG 가 평평하면 어느 문턱도 최적값과 갈리지 않는다
    print(f"  (나) 최적값({best[0]}) 대비 — 문턱끼리 갈리는가")
    bootstrap([(best[0], pick[best[0]], lbl, pick[lbl])
               for lbl, _, _ in swept if lbl != best[0]], len(cur_per))

    # ④ 설문 155 — 최종 후보만. 정답 라벨이 없어 stage 만 본다
    srows = load_rows(SURVEY[1], SURVEY[2])
    sn = len(srows)
    cand = [("A 현행(브리지 없음)", None), ("D1 top1", build_bridge(b, 0, 0, top1=True)),
            ("D2 lift 없음", build_bridge(b, 0.5, 0.0)),
            ("lift >= 1.4", build_bridge(b, 0.5, 1.4))]
    if best[0] not in [c[0] for c in cand]:
        cand.append((best[0], best[1]))
    res3 = [(lbl, br, measure(index, srows, br)) for lbl, br in cand]
    print_table(f"④ [{SURVEY[0]}] {sn}건 — 정답 라벨이 없어 NDCG 는 못 잰다", sn, res3)


if __name__ == "__main__":
    main()

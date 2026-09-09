"""Phase 3c 팀 검토용 summary.html — 혼합 가중 스윕 + 시드 재확인 + TriMap 판정.

Run with venv/Scripts/python.exe src/map/experiment_phase3c_summary.py

산출: experiments/phase3c/summary.html
"""
import csv
import json
import os
import sys

import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
MAP_DIR = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(MAP_DIR, "experiments", "_report_template"))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "common")))
import render_report as rr   # noqa: E402

P3C = os.path.join("experiments", "phase3c")
P3B = os.path.join("experiments", "phase3b")

# 5시드 재확인에 쓴 후보의 사람이 읽는 이름
NICE = {
    "wf=0 wp=0": "C1 — 개입 없음 (현재 출하)",
    "wf=0.1 wp=0": "계열 0.10",
    "wf=0.2 wp=0": "계열 0.20",
    "wf=0.35 wp=0": "계열 0.35",
    "wf=0 wp=0.15": "C8a — 인식 0.15",
    "wf=0.1 wp=0.15": "계열 0.10 + 인식 0.15",
    "wf=0.2 wp=0.15": "계열 0.20 + 인식 0.15",
    "wf=0.35 wp=0.15": "C8b — 계열 0.35 + 인식 0.15",
    "C3 semi w=0.35": "C3 semi w=0.35 (기존 안전 대안)",
}


def rj(*p):
    with open(os.path.join(*p), encoding="utf-8") as f:
        return json.load(f)


def rc(*p):
    with open(os.path.join(*p), encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def tbl(headers, rows, note=None, align=None):
    h = "".join(f"<th>{rr.esc(x)}</th>" for x in headers)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    cap = f'<p class="note">{note}</p>' if note else ""
    return (f'<div class="tw"><table class="tight"><thead><tr>{h}</tr></thead>'
            f'<tbody>{body}</tbody></table></div>{cap}')


def b(x):
    return f"<b>{x}</b>"


def paired(sc):
    """seed_check 의 후보별 baseline 대비 짝지은 차이."""
    cs = {c["candidate"]: c for c in sc["candidates"]}
    base = cs["wf=0 wp=0"]

    def per(c, k):
        return np.array([r[k] for r in c["per_seed"]], dtype=float)

    out = {}
    for name, c in cs.items():
        if name == "wf=0 wp=0":
            continue
        dd = per(c, "cross_family_proximity") - per(base, "cross_family_proximity")
        out[name] = {
            "d_cross_mean": round(float(dd.mean()), 4),
            "d_cross_std": round(float(dd.std()), 4),
            "significant": bool(abs(dd.mean()) > 2 * dd.std()),
            "neg_seeds": int((dd < 0).sum()),
            "d_overlap": round(float((per(c, "knn_overlap@10")
                                      - per(base, "knn_overlap@10")).mean()), 4),
            "d_trust": round(float((per(c, "trust@10") - per(base, "trust@10")).mean()), 4),
            "d_ratio": round(float((per(c, "cohesion_ratio")
                                    - per(base, "cohesion_ratio")).mean()), 3),
            "d_reminds": round(float((per(c, "reminds_pct")
                                      - per(base, "reminds_pct")).mean()), 4),
        }
    return out, cs, base


# --------------------------------------------------------------------------
def section_question(m, ref):
    ga = m["gates"]["gate_a"]
    body = f"""
<p>Phase 3 는 <b>C8b</b>(계열 프로파일 0.35 + 인식 축 0.15 를 거리에 섞는 방식)를 메인
Territory 후보로 선택했다. 그런데 두 가지가 확인되지 않은 상태였다.</p>
{tbl(["미확인 항목", "왜 문제인가"],
     [["C8b 를 한 점에서만 쟀다",
       "(계열 0.35 · 인식 0.15) 조합 하나뿐이었다. 그 점이 최적인지 모르고, "
       "두 성분이 각각 무슨 일을 하는지도 모른다"],
      ["Global 지표가 seed 42 단일 측정이었다",
       f"Gate A Δ 차이가 0.01~0.03 수준인데 시드를 바꾸면 그만큼 흔들릴 수 있다. "
       f"순위 근거로 쓸 수 없다"]])}
<p>그리고 팀 결정 두 개가 이 실험을 조건으로 걸고 있었다.</p>
{tbl(["팀 결정", "조건", "이 실험이 답하는 것"],
     [["② 투영 변경",
       "TriMap-dist 로 같은 후보를 다시 만들어 <b>사용자 가치가 실제로 개선되는 경우에만</b> "
       "전체 파이프라인을 재생성한다",
       "같은 혼합 거리를 TriMap-dist 로 만들어 게이트와 지표를 비교"],
      ["④ 안전 대안",
       "<b>C8b 의 local overlap 손실이 후속 실험에서도 해결되지 않을 경우</b> "
       "C3 semi w=0.35 를 쓴다",
       "가중을 바꿔 손실을 줄일 수 있는지, 그리고 C3 semi 가 여전히 최선의 대안인지"]])}
"""
    lead = ("C8b 의 혼합 가중을 격자로 재고, 최종 후보를 시드 5개에서 다시 확인한 뒤, "
            "같은 거리를 TriMap-dist 로도 만들어 비교했다.")
    after = f"""
{rr.h_callout("게이트는 Phase 3 에서 확정한 값을 그대로 쓴다", [
    f"Gate A — 계열 횡단 신뢰 쌍의 2D 근접도 <= {ga['pass_line']} "
    f"(baseline {ga['baseline']} + 마진 {ga['margin']}) · Global 1,000 · {ga['cross_pairs']}쌍",
    f"Gate B — trustworthiness@10 >= {m['gates']['gate_b']['threshold']} · Global 1,000",
    "이번 실험에서 기준선을 다시 고르지 않았다. 후보만 새로 만들었다.",
])}
"""
    return rr.make_section("q", "질문", "이 실험이 답하는 질문", body, lead=lead, after=after)


def section_blend(m):
    rows = []
    for c in m["reproduction_checks"]:
        rows.append([rr.esc(c["point"]), f"<code>{rr.esc(c['metric'])}</code>",
                     f"{c['got']:.4f}", f"{c['expected']:.4f}",
                     ('<span class="ok">PASS</span>' if c["ok"]
                      else '<span class="bad">FAIL</span>')])
    body = f"""
<p>혼합 거리를 두 성분으로 분리했다. 각 성분이 무슨 일을 하는지를 따로 보기 위해서다.</p>
<pre class="eq">D_blend = (1 - wf - wp)·D + wf·Df + wp·Dp</pre>
{tbl(["성분", "무엇인가", "어디서 왔나"],
     [["<code>D</code>", "Base Similarity 거리 — 0.5·accord cosine(L2) + 0.5·note IDF Jaccard",
       "D1 (EDA 04~06 재사용)"],
      ["<code>Df</code>", "계열 프로파일 코사인 거리 — Set B 9계열 Family Score 벡터 사이 거리",
       "팀 결정 ③ (accord 매핑 <code>reviewed-1</code>)"],
      ["<code>Dp</code>", "인식 축 거리 — 사용자 투표에서 만든 계절 따뜻함·성별 남성향 2축",
       "Phase 0 축 회전 실험과 같은 정의"]])}
{tbl(["격자", "값"],
     [["계열 가중 <code>wf</code>", "0 · 0.10 · 0.20 · 0.35 · 0.50 · 0.65"],
      ["인식 가중 <code>wp</code>", "0 · 0.075 · 0.15 · 0.30"],
      ["지점 수", f"{m['grid']['points']}점 (제약 <code>wf + wp &lt; 1</code>)"],
      ["Korea 200", f"시드 {len(m['seeds']['umap'])}개 — 영역 가독성"],
      ["Global 1,000", "seed 42 — 보호 지표 (최종 후보만 뒤에서 시드 5개로 다시 잰다)"]])}
<p>격자 안에 기준점 세 개가 들어 있다 — <code>(0, 0)</code> baseline ·
<code>(0, 0.15)</code> C8a · <code>(0.35, 0.15)</code> C8b.
<b>그 세 점이 Phase 3b 기록과 소수 4자리까지 일치한 뒤에만</b> 결과를 냈다.</p>
{tbl(["기준점", "지표", "이번 측정", "Phase 3b 기록", "판정"], rows,
     note="Korea (0,0) 는 재계산한 UMAP 이고 Phase 3b 의 C1 은 출하 좌표다. "
          "출하 좌표는 x·y 동일 배율 정규화라 상대 거리가 보존되므로 지표가 같아야 한다.")}
"""
    return rr.make_section("blend", "혼합 정의", "혼합 거리 정의와 격자, 기준점 재현", body)


def section_two_levers(m, pr, cs):
    order = ["wf=0.1 wp=0", "wf=0.2 wp=0", "wf=0.35 wp=0",
             "wf=0 wp=0.15", "wf=0.1 wp=0.15", "wf=0.2 wp=0.15", "wf=0.35 wp=0.15",
             "C3 semi w=0.35"]
    rows = []
    for n in order:
        p = pr[n]
        sig = ("<b>예</b>" if p["significant"] else "아니오")
        arrow = "개선" if p["d_cross_mean"] < 0 else "악화"
        rows.append([
            rr.esc(NICE[n]),
            f"{p['d_cross_mean']:+.4f} ± {p['d_cross_std']:.4f}",
            f"{sig} ({arrow})",
            f"{p['neg_seeds']}−/{5 - p['neg_seeds']}+",
            f"{p['d_overlap']:+.4f}",
            b(f"{p['d_ratio']:+.3f}") if abs(p["d_ratio"]) > 0.4 else f"{p['d_ratio']:+.3f}",
            f"{p['d_reminds']:+.4f}"])

    cats = ["계열 0.10", "계열 0.20", "계열 0.35"]
    fig = rr.fig_grouped_bar(
        cats,
        [("영역 가독성 ratio 증가", [pr["wf=0.1 wp=0"]["d_ratio"], pr["wf=0.2 wp=0"]["d_ratio"],
                              pr["wf=0.35 wp=0"]["d_ratio"]], rr.FIG_SHOAL),
         ("overlap@10 손실 (×10)", [-pr["wf=0.1 wp=0"]["d_overlap"] * 10,
                                 -pr["wf=0.2 wp=0"]["d_overlap"] * 10,
                                 -pr["wf=0.35 wp=0"]["d_overlap"] * 10], rr.FIG_WARN)],
        title="계열 축은 영역을 얻고 이웃 보존은 거의 잃지 않는다",
        xlabel="baseline 대비 변화 (시드 5개 짝 평균) · 손실은 눈에 보이게 10배",
        fmt=lambda v: f"{v:+.2f}")
    fig2 = rr.fig_grouped_bar(
        ["인식 0 → 0.15 (계열 0)", "인식 0 → 0.15 (계열 0.20)", "인식 0 → 0.15 (계열 0.35)"],
        [("계열 횡단 근접도 개선 (×10)",
          [-pr["wf=0 wp=0.15"]["d_cross_mean"] * 10,
           (pr["wf=0.2 wp=0"]["d_cross_mean"] - pr["wf=0.2 wp=0.15"]["d_cross_mean"]) * 10,
           (pr["wf=0.35 wp=0"]["d_cross_mean"] - pr["wf=0.35 wp=0.15"]["d_cross_mean"]) * 10],
          rr.FIG_DEEP),
         ("영역 가독성 ratio 변화",
          [pr["wf=0 wp=0.15"]["d_ratio"],
           pr["wf=0.2 wp=0.15"]["d_ratio"] - pr["wf=0.2 wp=0"]["d_ratio"],
           pr["wf=0.35 wp=0.15"]["d_ratio"] - pr["wf=0.35 wp=0"]["d_ratio"]],
          rr.FIG_LAND)],
        title="인식 축은 사람 유사성을 얻고 영역은 오히려 잃는다",
        xlabel="인식 가중 0.15 를 더했을 때의 변화 · 근접도 개선은 눈에 보이게 10배",
        fmt=lambda v: f"{v:+.2f}")

    body = f"""
<p>이것이 이 실험의 주된 발견이다. 아래는 <b>Global 1,000 · 시드 5개</b>에서
baseline 과 <b>시드를 짝지어</b> 뺀 차이다. 짝을 지으면 시드 자체가 만드는 흔들림이
상쇄된다. 계열 횡단 근접도는 <b>낮을수록 좋다</b>(사람이 닮았다고 한 쌍이 가깝다).</p>
{tbl(["지점", "Δ 계열 횡단 근접도", "시드 편차 대비 유의", "부호",
      "Δ overlap@10", "Δ 영역 ratio", "Δ 정답간선"], rows,
     note="유의 판정은 |평균| > 2 × 시드 표준편차. 부호는 5개 시드 중 개선 방향 개수. "
          "정답간선 근접도도 낮을수록 좋다.")}
{rr.figure_block(fig,
                 "계열 가중을 올리면 영역 가독성이 거의 선형으로 오르고 이웃 보존 손실은 "
                 "그보다 훨씬 작게 늘어난다.", source="experiments/phase3c/seed_check.json")}
{rr.figure_block(fig2,
                 "인식 가중은 반대다 — 계열 횡단 근접도를 유의하게 개선하지만 영역 가독성은 "
                 "떨어뜨린다. 계열 0 에서는 ratio 가 baseline 보다 낮아진다.",
                 source="experiments/phase3c/seed_check.json")}
{rr.h_callout("두 축은 서로 다른 일을 한다", [
    "계열 프로파일 축(Df)은 영역 레버 — 가중 0.10 / 0.20 / 0.35 에서 ratio +0.289 / +0.499 / "
    "+0.814, overlap 비용은 −0.0038 / −0.0129 / −0.0294 뿐이다.",
    "인식 축(Dp)은 사람 유사성 레버 — 계열 횡단 근접도를 유의하게 개선(−0.032~−0.060)하고 "
    "정답간선도 개선하지만, 영역 가독성은 오히려 낮춘다.",
    "두 축이 다른 일을 하므로 가중치를 따로 고를 수 있다. C8b 는 두 레버를 동시에 당긴 조합이다.",
])}
"""
    return rr.make_section("levers", "두 축의 역할",
                           "핵심 발견 — 계열 축과 인식 축은 서로 다른 일을 한다", body)


def section_seed(m, sc, cs):
    gl = sc["gates"]["gate_a_pass_line"]
    rows = []
    for c in sc["candidates"]:
        n = c["candidate"]
        cr, tr, ov = c["cross_family_proximity"], c["trust@10"], c["knn_overlap@10"]
        av = c["gate_a_verdict"]
        cls = "ok" if av == "PASS" else ("bad" if av == "DROP" else "warn")
        rows.append([
            b(rr.esc(NICE[n])) if n == "wf=0.35 wp=0.15" else rr.esc(NICE[n]),
            f"{cr['mean']:.4f} ± {cr['std']:.4f}",
            f"{cr['min']:.4f} ~ {cr['max']:.4f}",
            f'<span class="{cls}">{c["gate_a_pass_seeds"]}/5 {av}</span>',
            f"{tr['mean']:.4f} ± {tr['std']:.4f}",
            f"{c['gate_b_pass_seeds']}/5",
            f"{ov['mean']:.4f}",
            f"{c['cohesion_ratio']['mean']:.3f} ± {c['cohesion_ratio']['std']:.3f}",
            f"{c['reminds_pct']['mean']:.4f}"])
    mx = sc["max_seed_std_cross_family"]
    order = sorted(sc["candidates"], key=lambda r: r["cross_family_proximity"]["mean"])
    gaps = []
    for a, bb in zip(order, order[1:]):
        gap = (bb["cross_family_proximity"]["mean"]
               - a["cross_family_proximity"]["mean"])
        v = "구별 가능" if gap > 2 * mx else ("경계" if gap > mx else b("구별 불가"))
        gaps.append([rr.esc(NICE[a["candidate"]]), rr.esc(NICE[bb["candidate"]]),
                     f"{gap:+.4f}", v])
    body = f"""
<p>격자의 Global 지표는 seed 42 한 번이었다. 최종 후보 {len(sc['candidates'])}개를
<b>시드 5개</b>에서 다시 재고, <b>게이트를 시드마다 따로 적용</b>해 통과 개수를 셌다.
<code>experiments/README.md</code> 의 게이트 시드 규칙(전부 통과 PASS · 일부만 REVIEW ·
전부 실패 DROP)을 따랐다.</p>
{tbl(["후보", "계열 횡단 근접도 (5시드)", "범위", "Gate A", "trust@10", "Gate B",
      "overlap@10", "영역 ratio (G)", "정답간선 (G)"], rows,
     note=f"Gate A 합격선 {gl} · Gate B 0.90. 모든 값은 Global 1,000.")}
{rr.h_callout("계열 가중만 0.35 로 올리면 게이트가 흔들린다", [
    "계열 0.35 단독은 5시드 평균 0.3056, 최대 0.3147 로 합격선 0.3115 를 2개 시드에서 넘는다 "
    "→ 3/5 REVIEW.",
    "인식 항을 더한 C8b 는 5/5 통과(0.2315). 즉 C8b 의 인식 항은 장식이 아니라 "
    "게이트를 지탱하는 하중을 받는다.",
    "게이트 안에서 가장 높은 영역 가독성(Global ratio 5.021)을 얻는 것이 C8b 다. "
    "더 높은 5.048 은 시드 규칙에서 탈락한다.",
], kind="warn")}
<h3 style="margin-top:1.6rem">후보를 Gate A 로 서열화할 수 있는가</h3>
<p>시드 표준편차 최대 <b>{mx:.4f}</b> 와 후보 간 간격을 비교했다.</p>
{tbl(["더 좋은 쪽", "다음", "간격", "판정"], gaps,
     note="간격이 시드 표준편차보다 작으면 순위를 근거로 쓸 수 없다.")}
<p class="note">C8b · 계열 0.10 · 계열 0.20 · C1 네 후보의 Gate A 는 서로 구별되지 않는다.
<b>이 네 후보를 Gate A 숫자로 줄 세우면 안 된다.</b> 반면 C3 semi 와 계열 0.35 는
baseline 과 구별 가능하게 나쁘다.</p>
"""
    return rr.make_section("seed", "시드 재확인",
                           "최종 후보를 시드 5개에서 다시 확인", body)


def section_decision4(m, sc, pr, cs, refb):
    cond = m["best_by_condition"]
    rows = []
    for name, v in cond.items():
        if v is None:
            rows.append([rr.esc(name), "—", "—", "—", "—"])
            continue
        rows.append([rr.esc(name), rr.esc(NICE.get(v["label"], v["label"])),
                     f"{v['korea_cohesion_ratio']:.3f}",
                     f"{v['global_knn_overlap10']:.4f}",
                     f"{v['gate_a_delta']:+.4f}"])
    c1k = refb["korea200"]["C1 post-hoc"]["readability_seed42"]["cohesion_ratio"]
    k20 = next(r for r in m["sweep"] if r["label"] == "wf=0.2 wp=0")
    k8b = next(r for r in m["sweep"] if r["label"] == "wf=0.35 wp=0.15")
    gain20 = k20["korea_cohesion_ratio"] - c1k
    gain8b = k8b["korea_cohesion_ratio"] - c1k
    l20 = -pr["wf=0.2 wp=0"]["d_overlap"]
    l8b = -pr["wf=0.35 wp=0.15"]["d_overlap"]

    cmp_rows = [
        ["C3 semi w=0.35 (기존 안전 대안)",
         f'<span class="bad">{pr["C3 semi w=0.35"]["d_cross_mean"]:+.4f}</span> (유의하게 악화)',
         f'{pr["C3 semi w=0.35"]["d_overlap"]:+.4f}',
         f'{cs["C3 semi w=0.35"]["cohesion_ratio"]["mean"]:.3f}',
         "3.563",
         b(f'{cs["C3 semi w=0.35"]["trust@10"]["mean"]:.4f}')],
        [b("계열 0.20 단독 (새 제안)"),
         f'{pr["wf=0.2 wp=0"]["d_cross_mean"]:+.4f} (중립 — 유의하지 않음)',
         f'{pr["wf=0.2 wp=0"]["d_overlap"]:+.4f}',
         f'{cs["wf=0.2 wp=0"]["cohesion_ratio"]["mean"]:.3f}',
         b("3.793"),
         f'{cs["wf=0.2 wp=0"]["trust@10"]["mean"]:.4f}'],
    ]
    body = f"""
<p>팀 결정 ④ 는 <b>C8b 의 local overlap 손실이 후속 실험에서도 해결되지 않을 경우</b>
C3 semi w=0.35 를 쓰기로 했다. 그 조건을 판정한다.</p>
<h3 style="margin-top:1.4rem">답 — 손실을 없앨 수는 없지만 1/5 로 줄일 수 있다</h3>
{tbl(["조건 (seed 42 기준)", "그 안에서 최고 가독성 지점", "Korea ratio",
      "Global overlap@10", "Gate A Δ"], rows,
     note="조건 판정은 격자 측정(seed 42)에서 했다. 5시드로 다시 재면 "
          "'손실 ≤ 0.04' 의 답인 계열 0.35 단독은 Gate A 3/5 로 탈락한다.")}
{rr.h_callout("계열 0.20 단독의 위치", [
    f"Korea 영역 개선 +{gain20:.3f} — C8b 의 +{gain8b:.3f} 의 {gain20/gain8b:.0%}",
    f"overlap 손실 {l20:.4f} — C8b 의 {l8b:.4f} 의 {l20/l8b:.0%}",
    f"Gate A 중립 ({pr['wf=0.2 wp=0']['d_cross_mean']:+.4f}, 유의하지 않음) · "
    f"trust@10 은 baseline 과 같다 ({cs['wf=0.2 wp=0']['trust@10']['mean']:.4f} vs "
    f"{cs['wf=0 wp=0']['trust@10']['mean']:.4f})",
    "대신 포기하는 것 — 사람 유사성 개선과 축 의미. 정답간선 "
    f"{cs['wf=0.2 wp=0']['reminds_pct']['mean']:.4f} vs C8b "
    f"{cs['wf=0.35 wp=0.15']['reminds_pct']['mean']:.4f}, Global ratio "
    f"{cs['wf=0.2 wp=0']['cohesion_ratio']['mean']:.3f} vs "
    f"{cs['wf=0.35 wp=0.15']['cohesion_ratio']['mean']:.3f}",
])}
<h3 style="margin-top:1.6rem">C3 semi w=0.35 는 더 이상 최선의 보수적 대안이 아니다</h3>
{tbl(["대안", "Δ 계열 횡단 근접도", "Δ overlap@10", "영역 ratio (G)",
      "Korea ratio", "trust@10"], cmp_rows)}
<p>C3 semi 의 강점은 실재한다 — overlap 손실이 사실상 0
({pr['C3 semi w=0.35']['d_overlap']:+.4f})이고 trust@10 이 후보 중 최고
({cs['C3 semi w=0.35']['trust@10']['mean']:.4f})이며 시드 편차가 가장 작다
(± {cs['C3 semi w=0.35']['cross_family_proximity']['std']:.4f}).</p>
<p><b>그런데 계열 횡단 신뢰 쌍 근접도를 유의하게 악화시킨다</b>
({pr['C3 semi w=0.35']['d_cross_mean']:+.4f}, 5개 시드 모두 악화 방향).
그 지표가 "닮았다고 한 향수가 옆에 있다" 를 계열을 넘어 재는 지표다.
계열 0.20 단독은 그것을 건드리지 않으면서 Korea 영역 가독성이 더 높다.</p>
{rr.h_callout("제안 — 안전 대안을 계열 0.20 단독으로 교체", [
    "C3 semi 는 '이웃 목록을 지킨다' 는 기준에서만 낫고 '닮은 향수가 근처에 있다' 는 "
    "기준에서는 나쁘다.",
    "C3 semi 를 그대로 두려면 근거는 trust@10 과 시드 안정성이고, 그 두 값은 실제로 최고다.",
    "최종 선택은 팀이 한다. 이 실험은 순위를 자동으로 정하지 않는다.",
])}
"""
    return rr.make_section("d4", "팀 결정 ④ 판정",
                           "overlap 손실을 줄일 수 있는가 — 팀 결정 ④ 판정", body)


def section_trimap(m):
    rows = []
    for r in m["trimap"]:
        gb = r["global_trust10"]
        miss = 0.90 - gb
        v = "PASS" if r["passes_both"] else ("Gate B 미달" if r["gate_a"] else "Gate A 미달")
        cls = "ok" if r["passes_both"] else "bad"
        rows.append([
            rr.esc(r["label"]) + ("" if r["point_predeclared"] else " <i>(사후 추가)</i>"),
            rr.esc(r["projection"]),
            f"{r['gate_a_delta']:+.4f}",
            f"{gb:.4f}" + (f" <span class='note'>(−{miss:.4f})</span>" if miss > 0 else ""),
            f"{r['global_knn_overlap10']:.4f}",
            f"{r['korea_cohesion_ratio']:.3f}",
            f'<span class="{cls}">{v}</span>'])
    dl = [[rr.esc(d["label"]), f"{d['d_gate_a']:+.4f}",
           f"{d['d_korea_cohesion_ratio']:+.3f}", f"{d['d_korea_knn_overlap10']:+.4f}",
           f"{d['d_global_trust10']:+.4f}", f"{d['d_korea_reminds_pct']:+.4f}"]
          for d in m["projection_delta"]]
    body = f"""
<p>팀 결정 ② 는 TriMap-dist 로 같은 후보를 다시 만들어 <b>사용자 가치가 실제로 개선되는
경우에만</b> 전체 파이프라인을 재생성하라고 했다. 재검증 지점 4개는
<b>실행 전에 고정</b>했다 — 스윕 결과를 보고 고르지 않았다.</p>
{tbl(["지점", "투영", "Gate A Δ", "trust@10 (Gate B)", "overlap@10",
      "Korea ratio", "판정"], rows,
     note="괄호 안은 Gate B 0.90 미달 폭. Global 은 seed 42, Korea ratio 는 seed 42.")}
<h3 style="margin-top:1.6rem">투영만 바꾼 차이 (TriMap-dist − UMAP)</h3>
{tbl(["지점", "Δ Gate A", "Δ Korea ratio", "Δ Korea overlap", "Δ Global trust",
      "Δ Korea 정답간선"], dl)}
{rr.h_callout("판정 — 전체 파이프라인을 TriMap-dist 로 재생성하지 않는다", [
    "혼합을 넣은 네 지점 모두 seed 42 에서 Gate B 아래다 (trust@10 0.8683~0.8988).",
    "원본 거리 (0,0) 에서만 통과하고(0.9101), 그 값은 Phase 2 의 5시드 측정 "
    "0.9135 ± 0.0044(범위 0.9091~0.921)와 일치한다.",
    "C8b 지점에서 미달 폭 0.0177 은 Phase 2 가 관측한 시드 폭 0.0119 보다 크고, "
    "그러면서 Global overlap@10 이 0.3146 → 0.2378 로 떨어진다.",
    "TriMap 이 얻는 것도 있다 — Korea 영역 가독성 +0.145~+0.211, Gate A 소폭 개선. "
    "그런데 그 대가가 Gate B 다.",
], kind="warn")}
<p class="note">한계 — TriMap Global 측정은 <b>seed 42 단독</b>이다.
<code>(0.20, 0.15)</code> 지점은 미달 폭이 0.0012 로 시드 폭 안쪽이라
단일 시드로는 결론을 낼 수 없다. 그 지점은 C8b 가 아니므로 판정을 미룬다.</p>
"""
    return rr.make_section("trimap", "TriMap 판정",
                           "TriMap-dist 재검증 — 팀 결정 ② 판정", body)


def section_maps(coord_rows):
    by = {}
    fam = {}
    for r in coord_rows:
        by.setdefault(r["method"], []).append(
            (int(r["fragrantica_id"]), float(r["x"]), float(r["y"])))
        fam[int(r["fragrantica_id"])] = r["family"]
    want = [("wf=0 wp=0", "C1 — 개입 없음"), ("wf=0.2 wp=0", "계열 0.20"),
            ("wf=0.35 wp=0.15", "C8b — 계열 0.35 + 인식 0.15"),
            ("wf=0 wp=0.15", "C8a — 인식 0.15")]
    panels = []
    for key, title in want:
        if key not in by:
            continue
        rowsk = by[key]
        panels.append((title, [i for i, _, _ in rowsk],
                       np.array([[x, y] for _, x, y in rowsk], dtype=float)))
    figblock = rr.map_compare_figure(
        panels, families=fam, align_to_first=True,
        source="experiments/phase3c/coordinates_korea200.csv", point_size=13,
        extra_note="Korea 200 · UMAP seed 42 · 색은 Set B 9계열 argmax")
    body = f"""
<p>Korea 200 을 같은 계열 색으로 칠하고 혼합 가중만 바꿔 나란히 놓았다.</p>
{figblock}
{rr.h_callout("눈으로 보는 차이", [
    "C1 은 계열이 섞여 있고 같은 색이 지도 여러 곳에 흩어진다 (영역 조각 24개).",
    "계열 0.20 은 같은 색 덩어리가 커지지만 점 배치의 큰 구조는 C1 과 닮아 있다.",
    "C8b 는 색 덩어리가 가장 뚜렷하다 (조각 15개). 강제 분리처럼 섬으로 갈라지지는 않는다.",
    "C8a 는 계열 색이 오히려 더 섞인다 — 인식 축은 계열과 다른 축이기 때문이다.",
])}
"""
    return rr.make_section("maps", "지도 비교", "같은 계열 색으로 본 지도 4장", body)


def section_next(m, sc, pr, cs):
    body = f"""
<h3>팀이 결정할 것</h3>
{tbl(["결정", "선택지", "판단 근거"],
     [["안전 대안을 무엇으로 둘 것인가",
       "계열 0.20 단독 <b>(제안)</b> / C3 semi w=0.35 유지",
       "계열 0.20 은 Gate A 중립 + Korea ratio 3.793 · C3 semi 는 overlap 손실 0 + "
       "trust@10 0.9431 · 시드 편차 최소"],
      ["C8b 를 그대로 갈 것인가",
       "유지 <b>(권장)</b> / 계열 0.20 으로 교체",
       "C8b 는 게이트 안에서 가장 높은 영역 가독성을 얻는 유일한 조합이다. "
       "다만 overlap 손실이 계열 0.20 의 6배다"],
      ["인식 가중을 0.15 로 둘 것인가",
       "0.15 유지 / 0.075 로 낮춤",
       "0.30 은 전 구간에서 Gate B 를 위협한다(trust@10 0.8545~0.9015). 상한은 0.15 근처다"]])}
<h3 style="margin-top:1.6rem">이어서 할 것</h3>
{tbl(["순서", "작업", "왜"],
     [["1", "Phase 4 — 균형",
       "계열별 향수 수를 어떻게 맞출지. Fruity 가 Korea 200 에서 8개뿐인 문제가 여기서 다뤄진다"],
      ["2", "Phase 5 — UX 프로토타입",
       "9개 라벨이 첫 화면에서 읽히는지. 데이터가 답할 수 없는 문제다"],
      ["3", "Phase 6 — 사용자 테스트", "과제 2개 × 후보 2개"],
      ["4", "인식 축 결측 처리 민감도",
       "인식 축이 사람 유사성 레버라는 것이 밝혀졌으므로 투표 20표 미달 향수의 "
       "중앙값 대체가 결과에 영향을 준다 — 아직 재지 않았다"],
      ["—", "Holdout 300 · <code>gold_set_test.csv</code>",
       "모든 튜닝이 끝난 뒤 1회. 이번에도 열지 않았다"]])}
{rr.h_callout("이 실험이 D22 의 기록을 고친 부분", [
    "D22 가 보고한 C8b 의 Gate A 개선 −0.0342 는 seed 42 값이었다. 5시드 짝 평균은 "
    "−0.0177 ± 0.0099 로 절반이고, 크기는 시드 잡음 대비 유의하지 않다 "
    "(5개 시드 모두 개선 방향이라 부호는 신뢰할 수 있다).",
    "baseline 의 seed 42 값 0.2615 는 5개 시드 중 가장 나쁜 값이었다 "
    "(평균 0.2492, 범위 0.2347~0.2615). Gate A 합격선을 그 값에서 잡은 것은 결과적으로 "
    "가장 보수적인 선택이었고, 합격선은 그대로 둔다.",
    "최종 후보 9개는 스윕 결과를 보고 골랐다 (사후 선택). 게이트 기준선만 실행 전 확정값이다.",
], kind="warn")}
"""
    return rr.make_section("next", "다음", "팀 결정 사항과 다음 단계", body)


def main() -> None:
    os.chdir(MAP_DIR)
    m = rj(P3C, "metrics.json")
    sc = rj(P3C, "seed_check.json")
    refb = rj(P3B, "metrics.json")
    coord_rows = rc(P3C, "coordinates_korea200.csv")
    pr, cs, _base = paired(sc)

    sections = [section_question(m, refb), section_blend(m),
                section_two_levers(m, pr, cs), section_seed(m, sc, cs),
                section_decision4(m, sc, pr, cs, refb), section_trimap(m),
                section_maps(coord_rows), section_next(m, sc, pr, cs)]
    print(f"고유 절 {len(sections)}개를 렌더러에 넘깁니다")
    path, nsec, nkpi, nchk, nfig = rr.render(
        P3C, os.path.abspath(os.path.join(P3C, "summary.html")),
        title="Phase 3c — 혼합 가중 스윕과 투영 재검증",
        extra_sections=sections, auto_data_figures=False)
    print(f"  -> {os.path.relpath(path)}  ({os.path.getsize(path)/1024:.0f} KB) · "
          f"절 {nsec}개 · KPI {nkpi} · 재현검증 {nchk} · 그림 {nfig}")


if __name__ == "__main__":
    main()

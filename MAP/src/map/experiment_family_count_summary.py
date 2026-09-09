"""Family 체계 비교의 팀 검토용 summary.html 을 만든다.

Run with venv/Scripts/python.exe src/map/experiment_family_count_summary.py

experiment_family_count_comparison.py 가 만든 JSON/CSV 를 읽어 공통 렌더러
(experiments/_report_template/render_report.py) 로 HTML 하나를 만든다.
개별 실험 코드가 HTML 을 직접 문자열로 쓰지 않는다는 규약을 따른다.

산출: experiments/phase0_family_count_comparison/summary.html
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
import render_report as rr
import experiment_family_systems as es
import experiment_phase0_family_mapping as fm

EXP = os.path.join("experiments", "phase0_family_count_comparison")
OUT_HTML = os.path.join(EXP, "summary.html")
V2_JSON = os.path.join("output", "korea_scent_map_v2.json")   # 읽기만 한다
TOP200 = os.path.join("data", "korea_popularity", "korea_representative_perfumes_top200.csv")

BASE = ["9", "8A", "8B", "7"]
SENS = ["8A-A", "8B-A", "7-A"]
ALL = BASE + SENS
POP_KO = {"korea200": "Korea 200", "global1000": "Global 1,000"}
POP_COLOR = {"korea200": rr.FIG_SHOAL, "global1000": rr.FIG_DEEP}
GROUP_COLOR = {"base": rr.FIG_DEEP, "sensitivity": rr.FIG_LAND}


def rj(*p):
    with open(os.path.join(EXP, *p), encoding="utf-8") as f:
        return json.load(f)


def rc(*p):
    with open(os.path.join(EXP, *p), encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def by_short(metrics, pop):
    return {v["short"]: v for v in metrics[pop].values()}


def tbl(headers, rows, note=None, cls="tight"):
    h = "".join(f"<th>{rr.esc(x)}</th>" for x in headers)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    cap = f'<p class="note">{note}</p>' if note else ""
    return f'<div class="tw"><table class="{cls}"><thead><tr>{h}</tr></thead><tbody>{body}</tbody></table></div>{cap}'


# --------------------------------------------------------------------------
def section_intro(systems):
    rows = []
    for s in ALL:
        key = next(k for k, v in systems["systems"].items() if v["short"] == s)
        v = systems["systems"][key]
        rows.append([
            f"<b>{rr.esc(s)}</b>", rr.esc(v["label"]),
            "기본 비교" if v["group"] == "base" else "민감도",
            v["family_count"],
            rr.esc(", ".join(v["families_ko"])),
            v["modifier_count"],
        ])
    ov = systems["reviewed_overrides"]
    diff = tbl(["accord", "draft-1", "reviewed-1", "근거"],
               [[f"<code>{rr.esc(a)}</code>",
                 "MUSK" if a == "aldehydic" else "CITRUS",
                 rr.esc(b["family"]), rr.esc(b["reason"])] for a, b in ov.items()])
    body = f"""
<p>Phase 0 의 9계열은 <b>PROVISIONAL</b> 이다. Fragrance Wheel 7계열을 뼈대로 하고
휠에 없는 Gourmand·Musk/Powdery 를 IFRA primary descriptor 근거로 추가한 후보안이며,
<b>9라는 숫자가 실험으로 검증된 적은 없다.</b> 그래서 계열 개수를 실험 변수로 두고
같은 좌표·같은 스냅샷에서 7개 체계를 비교했다.</p>
<p class="note">이 실험은 숫자를 자동으로 고르지 않는다. 각 체계가 무엇을 얻고 무엇을
잃는지 수치와 사례로 보여주고, 선택은 팀이 한다.</p>
{tbl(["체계", "이름", "구분", "계열 수", "계열", "modifier accord"], rows)}
<h3>매핑 버전 — draft-1 은 동결, reviewed-1 을 새로 만들었다</h3>
<p>팀이 결정한 2건만 draft-1 에 오버라이드했다. Phase 0 산출물은 draft-1 기준으로 그대로
재현되고(cross-family 435쌍 assert 포함), 이 실험만 reviewed-1 을 쓴다.</p>
{diff}
<p class="note"><code>fresh</code> 는 <b>모든 체계에서 modifier</b> 다 — 어느 축의 신선함인지
데이터가 구분하지 않으므로 특정 계열에 강제 배정하지 않는다. 계열 점수 계산에서만 빼고
accord 데이터는 그대로 남는다.</p>
"""
    return rr.make_section("fc1", "체계 정의", "무엇을 비교했는가", body, after="s1")


def section_maps(k_rows, ids, coords):
    import matplotlib.pyplot as plt
    rr._rc()
    fig, axes = plt.subplots(1, 4, figsize=(13.2, 3.6))
    fam_of = {s: {int(r["fragrantica_id"]): r[f"{s}_family"] for r in k_rows} for s in BASE}
    for ax, s in zip(axes, BASE):
        colors = [rr.FAMILY_COLORS.get(fam_of[s][i], rr.UNMAPPED_COLOR) for i in ids]
        ax.scatter(coords[:, 0], coords[:, 1], c=colors, s=11, linewidths=0)
        n = len({fam_of[s][i] for i in ids})
        ax.set_title(f"{s}  ({n}계열)", fontsize=10, color=rr.FIG_INK)
        ax.set_xticks([]); ax.set_yticks([])
        for sp in ax.spines.values():
            sp.set_color(rr.FIG_HAIR)
    fig.tight_layout()
    img = rr.fig_to_img(fig, "체계 4개의 Korea 200 지도")
    legend = " ".join(
        f'<span class="chip" style="--c:{rr.FAMILY_COLORS[f]}">{rr.esc(fm.FAMILY_DEF[f][0])}</span>'
        for f in fm.FAMILY_ORDER)
    body = f"""
<p><b>네 지도는 같은 좌표다.</b> 계열 체계는 재라벨링이므로 점이 1픽셀도 움직이지 않는다.
색칠 기준만 다르다.</p>
{rr.figure_block(img, "Korea 200 · 좌표는 output/korea_scent_map_v2.json (읽기 전용, seed 42)",
                 source="assignments_korea200.csv",
                 must="정렬을 적용하지 않았습니다 — 네 지도가 같은 좌표이므로 회전/반사 정렬이 불필요합니다")}
<p class="note">계열 색: {legend}</p>
"""
    return rr.make_section("fc2", "지도 비교", "같은 좌표, 색칠 기준만 다름", body, after="fc1")


def section_sizes(metrics):
    body_parts = []
    for pop in ("korea200", "global1000"):
        d = by_short(metrics, pop)
        cats = [fm.FAMILY_DEF[f][0] for f in fm.FAMILY_ORDER]
        series = []
        for s in BASE:
            sizes = d[s]["family_sizes"]
            series.append((s, [sizes.get(f, 0) for f in fm.FAMILY_ORDER],
                           GROUP_COLOR["base"] if s == "9" else None))
        fig = rr.fig_grouped_bar(cats, [(a, b, None) for a, b, _ in series],
                                 title=f"{POP_KO[pop]} — 계열별 향수 수", fmt=lambda v: f"{v:.0f}")
        if fig:
            body_parts.append(rr.figure_block(fig, f"{POP_KO[pop]} 계열별 향수 수",
                                              source="metrics.json"))
        rows = [[f"<b>{s}</b>", d[s]["family_count"], d[s]["size_max"], d[s]["size_min"],
                 f'{d[s]["size_max_share"]:.1%}', f'{d[s]["size_cv"]:.2f}',
                 " · ".join(f"{k}={v}" for k, v in d[s]["small_families"].items())]
                for s in ALL]
        body_parts.append(f"<h3>{POP_KO[pop]}</h3>" + tbl(
            ["체계", "계열 수", "최대", "최소", "최대 비중", "CV", "작은 계열"], rows))
    warn = """
<p class="warn"><b>민감도 변형의 편중이 심하다.</b> Global 1,000 에서 8B-A 는 Amber 최대 비중
44.3%(CV 1.04), 7-A 는 <b>53.0%(CV 1.16)</b> 다. Gourmand accord 20종을 Amber 로 병합하면
Amber 가 accord 31~33종이 되어 지도의 절반을 차지한다.</p>
"""
    return rr.make_section("fc3", "분포", "계열별 향수 수가 치우치지 않는가",
                           "".join(body_parts) + warn, after="fc2")


def section_cohesion(metrics):
    stab = metrics["seed_stability_korea200"]
    stab_short = {es.SYSTEMS[k]["short"]: v for k, v in stab.items()}
    figs = []
    for pop in ("korea200", "global1000"):
        d = by_short(metrics, pop)
        items = [(s, d[s]["cohesion_ratio"], GROUP_COLOR[
            "base" if s in BASE else "sensitivity"]) for s in ALL]
        f = rr.fig_bar_colored(items, title=f"{POP_KO[pop]} — normalized cohesion ratio",
                               xlabel="observed / random expected (높을수록 좋음)", fmt=lambda v: f"{v:.3f}")
        if f:
            figs.append(rr.figure_block(f, f"{POP_KO[pop]} 정규화 응집도 비율",
                                        source="metrics.json"))
    rows = []
    for pop in ("korea200", "global1000"):
        d = by_short(metrics, pop)
        for s in ALL:
            v = d[s]
            st = stab_short[s] if pop == "korea200" else None
            rows.append([f"<b>{s}</b>", POP_KO[pop], v["family_count"],
                         f'{v["observed_cohesion"]:.3f}',
                         f'{v["random_expected_cohesion"]:.3f}',
                         f'<b>{v["cohesion_ratio"]:.3f}</b>',
                         f'{st["mean"]:.3f} ± {st["std"]:.3f}' if st else "—",
                         f'{v["neighborhood_purity"]["mean_top_family_share"]:.3f}',
                         f'{v["region_purity"]["on_own_region"]:.3f}'
                         if v.get("region_purity") else "—"])
    body = f"""
<p><b>계열 수가 다르면 응집도 절대값을 비교할 수 없다.</b> 계열이 적으면 무작위로 칠해도
같은 색이 자주 걸린다. 그래서 기본 비교 지표는
<code>observed / random expected</code> 비율이다.</p>
{"".join(figs)}
{tbl(["체계", "모집단", "계열", "observed", "무작위 기대", "ratio", "시드 5개(ratio)",
      "이웃 최다 점유", "영역 위"], rows,
     note="이웃 최다 점유율과 영역 위 비율은 무작위 보정이 없어 계열이 적을수록 높게 나온다. 판정에 쓰지 않고 참고로만 본다.")}
<p><b>정규화 지표로는 9계열이 두 모집단 모두 1위다</b> (Korea 200 3.264 · Global 1,000 4.187)
그리고 시드 안정성도 가장 좋다 (3.205 ± 0.043).</p>
<p class="warn">다만 정직하게 적어둘 것 — <code>cohesion_ratio</code> 도 계열 수에 완전히
중립적이지는 않다. 무작위 기대값으로 나누어 보정하지만, 계열이 많으면 기대값이 작아져
비율이 커지는 경향이 남는다. 그래서 이 지표만으로 9계열을 결정하지 말고 아래의
정보 손실·오배정 지표를 함께 봐야 한다.</p>
"""
    return rr.make_section("fc4", "응집도", "같은 계열끼리 실제로 모이는가", body, after="fc3")


def section_loss(metrics):
    figs = []
    for pop in ("korea200", "global1000"):
        d = by_short(metrics, pop)
        f = rr.fig_grouped_bar(
            ALL,
            [("ratio<0.20", [d[s]["low_family_mass"]["ratio_lt_0.2"] for s in ALL], rr.FIG_WARN),
             ("ratio<0.30", [d[s]["low_family_mass"]["ratio_lt_0.3"] for s in ALL], rr.FIG_LAND),
             ("ratio<0.50", [d[s]["low_family_mass"]["ratio_lt_0.5"] for s in ALL], rr.FIG_SHOAL)],
            title=f"{POP_KO[pop]} — 계열 신호가 약한 향수 수", fmt=lambda v: f"{v:.0f}")
        if f:
            figs.append(rr.figure_block(f, f"{POP_KO[pop]} low family-mass", source="metrics.json"))
    rows = []
    for pop in ("korea200", "global1000"):
        d = by_short(metrics, pop)
        for s in ALL:
            v = d[s]
            rows.append([f"<b>{s}</b>", POP_KO[pop], v["modifier_count"],
                         v["no_family_signal"], f'{v["coverage"]:.1%}',
                         v["low_family_mass"]["ratio_lt_0.5"],
                         f'{v["family_mass_ratio"]["median"]:.3f}',
                         f'{v["modifier_mass_ratio"]["median"]:.3f}',
                         v["top_accord_is_modifier"],
                         f'<b>{1 - v["top_accord_in_assigned_family"]:.1%}</b>'])
    body = f"""
<p>계열을 해체하면 그 accord 의 신호가 계열 점수에서 빠진다. 얼마나 빠지는지를 세 층으로 쟀다.</p>
<ul>
<li><b>no-family-signal</b> — 계열 점수 총량이 0. argmax 계열이 없다</li>
<li><b>low family-mass</b> — <code>family_mass_ratio = 계열 배정 strength / 전체 accord strength</code>
가 낮다. 임계값을 하나로 고정하지 않고 0.20 / 0.30 / 0.50 세 지점을 낸다</li>
<li><b>1순위 accord 미포함</b> — 가장 강한 accord 가 배정된 계열에 없다 = 배정 근거가 약하다</li>
</ul>
<p class="warn"><b>사전 예상과 결과가 달랐다.</b> no-family-signal 은 거의 생기지 않는다
(7계열 Global 1,000 에서 1개, Korea 200 은 0개). 손실은 신호 소멸이 아니라
<b>오배정</b> 으로 나타난다 — 남은 소수의 신호로 계열이 결정된다.</p>
{"".join(figs)}
{tbl(["체계", "모집단", "modifier", "no-signal", "coverage", "mass<0.5",
      "mass ratio 중앙", "modifier 중앙", "1순위=modifier", "1순위≠계열"], rows)}
<p><b>계열을 줄일수록 배정 근거가 약해진다.</b> 1순위 accord 가 배정된 계열에 없는 향수가
9계열 31.9% → 7계열 <b>44.5%</b> (Global 1,000) 로 늘어난다. 7계열에서는 향수 절반 가까이가
가장 강한 accord 와 다른 계열에 놓인다.</p>
<p class="note">Amber 병합 변형(8A-A · 8B-A · 7-A)은 정보 손실을 없앤다 (mass&lt;0.5 가 0개).
대가는 위 절의 편중과 아래 절의 응집도 하락이다.</p>
"""
    return rr.make_section("fc5", "정보 손실", "계열을 빼면 무엇이 사라지는가", body, after="fc4")


def section_cross(metrics):
    figs = []
    d = by_short(metrics, "global1000")
    f = rr.fig_grouped_bar(
        ALL,
        [("cross-family 쌍 수", [d[s]["cross_family"]["cross_family"] for s in ALL], rr.FIG_DEEP)],
        title="Global 1,000 — 계열을 넘는 신뢰 쌍 수 (전체 872쌍)", fmt=lambda v: f"{v:.0f}")
    if f:
        figs.append(rr.figure_block(f, "계열 횡단 신뢰 쌍 수", source="metrics.json"))
    f2 = rr.fig_grouped_bar(
        ALL,
        [("cross-family", [d[s]["cross_family"]["cross_family_proximity"] for s in ALL], rr.FIG_WARN),
         ("same-family", [d[s]["cross_family"].get("same_family_proximity") for s in ALL], rr.FIG_SHOAL)],
        title="Global 1,000 — 신뢰 쌍의 2D 근접도 (낮을수록 가까움)", fmt=lambda v: f"{v:.4f}")
    if f2:
        figs.append(rr.figure_block(f2, "근접도 — 0 이 가장 가깝고 0.5 가 무작위",
                                    source="metrics.json"))
    rows = []
    for pop in ("global1000", "korea200"):
        dd = by_short(metrics, pop)
        for s in ALL:
            c = dd[s]["cross_family"]
            rows.append([f"<b>{s}</b>", POP_KO[pop], c["trusted_edges"], c["cross_family"],
                         f'{c["cross_family_share"]:.1%}',
                         f'{c.get("cross_family_proximity", float("nan")):.4f}',
                         f'{c.get("same_family_proximity", float("nan")):.4f}'])
    body = f"""
<p>사람이 "닮았다" 고 투표한 쌍 중 계열을 넘는 것들이 지도에서 멀어지면 실패다. 보호 지표다.</p>
{"".join(figs)}
{tbl(["체계", "모집단", "신뢰 쌍", "계열 횡단", "비율", "횡단 근접도", "동일 계열 근접도"], rows,
     note="Korea 200 은 계열 횡단 쌍이 21~25쌍뿐이라 판정에 쓰지 않는다. 판정은 Global 1,000(388~414쌍)에서 한다.")}
<p><b>어느 체계도 사람 판단을 특별히 더 훼손하지 않는다.</b> Global 1,000 횡단 근접도가
0.2199~0.2615 범위이고 체계 간 차이가 0.04 이내다. 계열 수는 이 지표의 결정 요인이 아니다.</p>
"""
    return rr.make_section("fc6", "보호 지표", "닮았다고 한 향수를 갈라놓지 않는가", body, after="fc5")


def section_margin(metrics, k_rows, g_rows):
    panels = []
    for pop, rows in (("korea200", k_rows), ("global1000", g_rows)):
        for s in ("9", "7"):
            vals = [float(r[f"{s}_margin"]) for r in rows
                    if r[f"{s}_margin"] not in ("", "nan")]
            panels.append((f"{POP_KO[pop]} · {s}계열", vals, f"중앙 {np.median(vals):.3f}"))
    f = rr.fig_hist(panels, bins=22, xlabel="margin (1위 계열 점수 - 2위)",
                    vlines=[(0.10, "0.10")])
    rows = []
    for pop in ("korea200", "global1000"):
        d = by_short(metrics, pop)
        for s in ALL:
            m = d[s]["margin"]
            rows.append([f"<b>{s}</b>", POP_KO[pop],
                         f'{m["top1"]["median"]:.3f}', f'{m["margin"]["median"]:.3f}',
                         m["margin_lt_0.02"], m["margin_lt_0.05"], m["margin_lt_0.1"]])
    body = f"""
<p>margin 은 1위 계열 점수와 2위의 차다. 작으면 두 계열 사이에 있는 향수이고, 경계가
새로운 취향으로 넘어가는 다리가 될 수 있다.</p>
{rr.figure_block(f, "margin 분포 — 9계열과 7계열 대비", source="assignments_*.csv") if f else ""}
{tbl(["체계", "모집단", "top1 중앙", "margin 중앙", "&lt;0.02", "&lt;0.05", "&lt;0.10"], rows)}
<p><b>계열을 줄이면 margin 이 커진다</b> (Global 1,000 중앙 0.134 → 0.183). 계열이 적으니
1·2위 차가 벌어지는 것이며, 경계 향수가 줄어드는 대신 위 절의 오배정이 늘어난다.</p>
"""
    return rr.make_section("fc7", "경계", "두 계열 사이에 있는 향수", body, after="fc6")


def section_change(metrics, cases):
    change = metrics["assignment_change"]["korea200"]
    mat = [[change[a][b] for b in ALL] for a in ALL]
    f = rr.fig_heatmap(ALL, ALL, mat, title="Korea 200 — 체계 간 배정이 달라지는 향수 수")
    moved = [c for c in cases if c["case_type"] == "assignment_change" and c["system"] == "7"]
    low = [c for c in cases if c["case_type"] == "low_family_mass_7"][:10]
    rows_m = [[rr.esc(c["brand"]), rr.esc(c["name"][:34]),
               rr.esc(fm.FAMILY_DEF.get(c["family_9"], (c["family_9"],))[0]),
               rr.esc(fm.FAMILY_DEF.get(c["family_this"], (c["family_this"],))[0]),
               c["mass_ratio"], f'<code>{rr.esc(c["top_accords"])}</code>']
              for c in moved[:12]]
    rows_l = [[rr.esc(c["brand"]), rr.esc(c["name"][:34]), c["mass_ratio"],
               rr.esc(fm.FAMILY_DEF.get(c["family_9"], (c["family_9"],))[0]),
               rr.esc(fm.FAMILY_DEF.get(c["family_this"], (c["family_this"],))[0]),
               f'<code>{rr.esc(c["top_accords"])}</code>'] for c in low]
    body = f"""
{rr.figure_block(f, "숫자가 클수록 두 체계가 다르게 배정한다", source="metrics.json") if f else ""}
<h3>7계열에서 배정이 바뀌는 향수 (9계열 대비 38건 중 12건)</h3>
{tbl(["브랜드", "이름", "9계열", "7계열", "mass ratio", "상위 accord"], rows_m)}
<h3>7계열에서 계열 신호가 가장 약한 향수</h3>
{tbl(["브랜드", "이름", "mass ratio", "9계열", "7계열", "상위 accord"], rows_l,
     note="mass ratio 가 0.06 이면 그 향수 accord 신호의 94% 를 무시한 채 계열을 정한 것이다.")}
<p class="warn"><b>이게 정보 손실의 실제 모습이다.</b> Ariana Grande Cloud 는
<code>sweet 100 · lactonic 49 · vanilla 43 · coconut 34</code> 인데 7계열에서는 그 신호가
전부 modifier 로 빠져 남은 6% 로 <b>GREEN</b> 에 배정된다. 사용자에게는 명백히 틀린 지도다.</p>
"""
    return rr.make_section("fc8", "변경 사례", "체계를 바꾸면 어떤 향수가 움직이는가",
                           body, after="fc7")


def section_recommend(metrics):
    kd, gd = by_short(metrics, "korea200"), by_short(metrics, "global1000")
    stab = {es.SYSTEMS[k]["short"]: v for k, v in metrics["seed_stability_korea200"].items()}
    rows = []
    for s in ALL:
        rows.append([
            f"<b>{s}</b>",
            f'{kd[s]["cohesion_ratio"]:.3f} / {gd[s]["cohesion_ratio"]:.3f}',
            f'{stab[s]["mean"]:.3f} ± {stab[s]["std"]:.3f}',
            f'{kd[s]["low_family_mass"]["ratio_lt_0.5"]} / {gd[s]["low_family_mass"]["ratio_lt_0.5"]}',
            f'{1 - gd[s]["top_accord_in_assigned_family"]:.1%}',
            f'{gd[s]["cross_family"]["cross_family_proximity"]:.4f}',
            f'{gd[s]["size_max_share"]:.1%}',
        ])
    body = f"""
{tbl(["체계", "cohesion ratio (K/G)", "시드 5개 (Korea)", "mass&lt;0.5 (K/G)",
      "1순위≠계열 (G)", "횡단 근접도 (G)", "최대 비중 (G)"], rows)}
<h3>체계별로 무엇을 얻고 무엇을 잃는가</h3>
<table class="tight"><thead><tr><th>체계</th><th>얻는 것</th><th>잃는 것</th></tr></thead><tbody>
<tr><td><b>9</b></td><td>정규화 응집도 1위(3.264 / 4.187) · 시드 안정성 1위 · 정보 손실 0 ·
오배정 최저(31.9%) · 분포 가장 고름(최대 비중 19.9%)</td>
<td>계열이 많아 첫 화면에 라벨 9개를 얹어야 한다 · Korea 200 에서 프루티가 8개로 작다 ·
Gourmand·Musk 는 Fragrance Wheel 근거가 아니라 IFRA 근거다</td></tr>
<tr><td><b>8A</b></td><td>Musk/Powdery 를 빼도 응집도 손실이 작다(3.053 / 3.846) ·
이웃 점유율은 오히려 9계열보다 높다</td>
<td>powdery(47.7%)·musky(31.2%) 신호를 버린다 · mass&lt;0.5 향수 5 / 12개 발생 ·
오배정 34.5%</td></tr>
<tr><td><b>8B</b></td><td>Musk/Powdery 를 남겨 파우더리 구역이 생긴다</td>
<td>Gourmand 20종을 버려 mass&lt;0.5 가 10 / 80개 · 오배정 41.7% ·
구르망 향수가 엉뚱한 계열로 간다</td></tr>
<tr><td><b>7</b></td><td>Fragrance Wheel 만으로 설명된다 · 라벨 7개로 가장 단순 ·
margin 이 커서 경계가 선명(중앙 0.183)</td>
<td>응집도 최저(2.881 / 3.302) · mass&lt;0.5 22 / 162개 ·
<b>오배정 44.5%</b> · 시드 안정성도 가장 낮다</td></tr>
<tr><td><b>8A-A · 8B-A · 7-A</b></td><td>정보 손실이 0 이다 (Amber 로 병합하므로)</td>
<td>Amber 비대화 — Global 1,000 최대 비중 8B-A 44.3% · 7-A <b>53.0%</b>(CV 1.16) ·
응집도가 기본안보다 낮다 (7-A 2.011)</td></tr>
</tbody></table>
<h3>내 추천 — 9계열 유지. 다만 결정은 팀이 한다</h3>
<p>정규화 응집도·시드 안정성·정보 손실·오배정·분포 균형의 <b>다섯 축에서 모두 9계열이 우세</b>하고,
보호 지표(계열 횡단 근접도)는 체계 간 차이가 0.04 이내로 결정 요인이 아니다.
계열을 줄이는 대가가 응집도 하락에 그치지 않고 <b>오배정 증가</b>로 나타나는 것이 핵심이다 —
7계열에서는 향수 절반 가까이(44.5%)가 자신의 가장 강한 accord 와 다른 계열에 놓인다.</p>
<p><b>Amber 병합은 대안이 아니다.</b> 정보 손실은 없어지지만 Amber 가 지도의 44~53% 를 차지해
"여기가 어느 구역인가" 자체가 무의미해진다. 플랜에서 위험으로 적어둔 편중이 실제로 발생했다.</p>
<h3>다만 9계열을 그대로 확정하기 전에 팀이 볼 것</h3>
<ol>
<li><b>라벨 9개가 첫 화면에서 읽히는가</b> — 이건 데이터가 답할 수 없다. Phase 5 의 semantic zoom
프로토타입에서 확인할 문제다</li>
<li><b>프루티가 Korea 200 에서 8개</b> 다. 지도에서 영역으로 보이기에 충분한지, 아니면
Floral 이나 Citrus 와 합칠지</li>
<li><b>powdery(47.7%)를 계열로 쓸 것인가</b> — 보유율이 배경에 가깝다. 8A 가 이걸 빼는 안이고
응집도 손실은 작았다(3.264 → 3.053)</li>
<li><b>Gourmand·Musk 의 근거가 IFRA</b> 라는 점 — Fragrance Wheel 만 쓰겠다는 방침이면 7계열이
정답이고, 그때 잃는 것이 위 표에 있다</li>
<li>확정 후 <code>experiments/README.md</code> 기준값 표와
<code>family_mapping_draft.csv</code> 의 <code>human_decision</code> 갱신</li>
</ol>
<p class="note">아직 실행하지 않은 것 — <code>sweet</code> 만 modifier 로 두고 나머지 Gourmand 를
Amber 로 보내는 절충안(팀 결정으로 보류). 기본 modifier 안의 정보 손실이 크고 Amber 병합안의
편중이 과도하다는 것이 이 실험에서 확인됐으므로, 후속으로 검토할 근거는 생겼다.</p>
"""
    return rr.make_section("fc9", "판단", "장점 · 단점 · 추천", body, after="fc8")


def main() -> None:
    os.chdir(MAP_DIR)
    print("=" * 78)
    print("Family 체계 비교 — 팀 검토용 summary.html")
    print("=" * 78)

    systems = rj("systems.json")
    metrics = rj("metrics.json")
    k_rows = rc("assignments_korea200.csv")
    g_rows = rc("assignments_global1000.csv")
    cases = rc("cases.csv")
    print(f"읽은 산출물 — 체계 {len(systems['systems'])}개 · Korea 배정 {len(k_rows)}행 · "
          f"Global 배정 {len(g_rows)}행 · 사례 {len(cases)}건")

    doc = json.loads(open(V2_JSON, encoding="utf-8").read())
    by_id = {p["fragrantica_id"]: (p["x"], p["y"]) for p in doc["points"]}
    ids = [int(r["fragrantica_id"]) for r in k_rows]
    coords = np.array([by_id[i] for i in ids], dtype=float)

    sections = [
        section_intro(systems),
        section_maps(k_rows, ids, coords),
        section_sizes(metrics),
        section_cohesion(metrics),
        section_loss(metrics),
        section_cross(metrics),
        section_margin(metrics, k_rows, g_rows),
        section_change(metrics, cases),
        section_recommend(metrics),
    ]
    print(f"고유 절 {len(sections)}개를 렌더러에 넘깁니다")

    path, nsec, nkpi, nchk, nfig = rr.render(
        EXP, os.path.abspath(OUT_HTML),
        title="Family 체계 7 / 8A / 8B / 9 비교",
        extra_sections=sections, auto_data_figures=False)
    size = os.path.getsize(path) / 1024
    print(f"\n  -> {os.path.relpath(path)}  ({size:.0f} KB)")
    print(f"     섹션 {nsec}개 · KPI {nkpi}개 · 재현 검증 {nchk}개 · 자동 그림 {nfig}개")


if __name__ == "__main__":
    main()

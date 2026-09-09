"""Phase 5 팀 검토용 summary.html — soft / multi-family Territory 스윕.

Run with venv/Scripts/python.exe src/map/experiment_phase5_summary.py

산출: experiments/phase5/summary.html
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

P5 = os.path.join("experiments", "phase5")
ORDER = ["T0", "T0w", "T1", "T2", "T3", "T4", "T5", "T6"]
FIELD_PANELS = ["T0", "T0w", "T1", "T6"]
KO = {"CITRUS": "시트러스", "FRUITY": "프루티", "FLORAL": "플로럴",
      "GREEN": "그린·아로마틱", "AQUATIC": "아쿠아틱", "WOODY": "우디",
      "AMBER": "앰버·스파이시", "GOURMAND": "구르망", "MUSK": "머스크·파우더리"}
FAMS = list(KO)


def rj(*p):
    with open(os.path.join(*p), encoding="utf-8") as f:
        return json.load(f)


def rc(*p):
    with open(os.path.join(*p), encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def tbl(headers, rows, note=None):
    h = "".join(f"<th>{rr.esc(x)}</th>" for x in headers)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    cap = f'<p class="note">{note}</p>' if note else ""
    return (f'<div class="tw"><table class="tight"><thead><tr>{h}</tr></thead>'
            f'<tbody>{body}</tbody></table></div>{cap}')


def b(x):
    return f"<b>{x}</b>"


def mk(ok):
    return '<span class="ok">○</span>' if ok else '<span class="bad">✕</span>'


def field_figure(m):
    """조건별 Territory field. 점은 그대로이고 색면만 바뀐다."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap
    z = np.load(os.path.join(P5, "field_seed42.npz"), allow_pickle=True)
    rr._rc()
    n = len(FIELD_PANELS)
    fig, axes = plt.subplots(1, n, figsize=(3.5 * n, 3.7), squeeze=False)
    for ax, name in zip(axes[0], FIELD_PANELS):
        win = z[name]
        land = z[name + "_land"]
        usable = [str(x) for x in z[name + "_usable"]]
        rgb = np.zeros(win.shape + (4,), dtype=float)
        for i, f in enumerate(usable):
            c = matplotlib.colors.to_rgba(rr.FAMILY_COLORS.get(f, rr.UNMAPPED_COLOR))
            sel = (win == i) & land
            rgb[sel] = c
        rgb[~land] = matplotlib.colors.to_rgba(rr.FIG_BG)
        ax.imshow(rgb, origin="lower", interpolation="nearest")
        cnt = int(m["seed_aggregates"][name]["families_with_territory"]["mean"] + 0.5)
        ax.set_title(f"{name} · Territory {cnt}계열", loc="left",
                     color=rr.FIG_INK, fontsize=10, pad=6)
        ax.set_xticks([])
        ax.set_yticks([])
        for sp in ax.spines.values():
            sp.set_color(rr.FIG_HAIR)
    fig.tight_layout()
    img = rr.fig_to_img(fig, "조건별 Territory field")
    leg = " ".join(
        f'<span style="display:inline-flex;align-items:center;gap:4px;margin-right:10px">'
        f'<span style="width:10px;height:10px;border-radius:2px;background:'
        f'{rr.FAMILY_COLORS[f]};display:inline-block"></span>{KO[f]}</span>'
        for f in FAMS)
    return rr.figure_block(
        img,
        "같은 200개 향수 · 같은 좌표(C8b seed 42). 색면은 각 칸을 어느 계열이 차지했는지다. "
        "T6 은 계열이 서로 먹어 들어가 색면이 3~4개로 줄어든다.",
        source="experiments/phase5/field_seed42.npz") + f'<p class="note">{leg}</p>'


def section_setup(m):
    fx = m["fixed"]
    d = m["design"]
    body = f"""
<p>D26 결정 ⑤ 를 검증한다 — <b>Fruity 문제를 향수 수가 아니라 Family 표현 방식으로 푼다.</b>
argmax 로는 8개지만 fractional 로는 14.9개분의 Fruity 신호가 이미 지도에 있다.</p>
{rr.h_callout("향수도 좌표도 바꾸지 않는다", [
    f"구성 {rr.esc(fx['composition'])} · {fx['n']}개 — Phase 4 에서 D0 유지로 확정됐다.",
    f"좌표 {rr.esc(fx['projection'])} — D24 에서 확정됐다.",
    "바뀌는 것은 Territory 를 그릴 때 각 향수가 어느 계열에 얼마나 기여하는가 뿐이다.",
], kind="ok")}
{tbl(["설계 결정", "내용"],
     [["재정규화 금지 (팀)", rr.esc(d["no_renormalization"])],
      ["argmax 항상 유지", rr.esc(d["argmax_always_kept"])],
      ["T0w 통제 조건", rr.esc(d["t0w_rationale"])],
      ["weighted coverage (팀)", rr.esc(d["weighted_coverage"])]])}
{rr.h_callout("실행 전 예측", [
    "Family Score 를 전부 그대로 쓰면 프루티 신호의 퍼짐이 0.147 → 0.653 으로 4.4배 "
    "나빠진다 (D26 Trade-off ②).",
    "그래서 'soft 를 쓸까' 가 아니라 '얼마나 soft 하게 할까' 를 스윕했다.",
    "결과 — T6(문자 그대로 soft)는 Territory 가 9 → 1.6계열로 무너졌다. 예측이 맞았다.",
], kind="warn")}
"""
    lead = ("향수 구성과 좌표를 고정하고, Territory 를 그릴 때 쓰는 계열 기여 방식만 "
            "hard(T0) 에서 soft(T6) 까지 8단계로 바꿔 비교했다.")
    return rr.make_section("setup", "전제", "무엇을 고정하고 무엇을 바꿨는가", body, lead=lead)


def section_conditions(m):
    rows = []
    for r in m["conditions"]:
        rows.append([b(r["condition"]) if r["condition"] in ("T0w", "T1") else r["condition"],
                     rr.esc(r["description"]),
                     f'{r["mean_active_families"]:.2f}',
                     str(r["median_active_families"]), str(r["max_active_families"]),
                     f'{r["share_le3_families"]:.1%}',
                     f'{r["total_signal"]:.1f}',
                     mk(r["gate_c_ok"])])
    body = f"""
<p>조건 8개다. <b>argmax 계열은 어떤 조건에서도 유지</b>되므로
T0w ⊆ T1 ⊆ T2 ⊆ T3 ⊆ T6 로 hard → soft 가 단조 구간이 된다.</p>
{tbl(["조건", "설명", "평균 active Family", "중앙", "최대", "≤3계열 비율",
      "총 신호량", "P5-C"], rows,
     note="총 신호량 = 모든 향수·모든 계열의 기여 가중치 합. T0 는 향수당 1.0 씩 200. "
          "T0w 는 원래 강도를 쓰므로 80.2 로 줄어든다 — Family Score 는 향수마다 합이 1.0 "
          "이므로 이는 계열 소속이 흐릿한 향수(1위 비중 0.22)의 영향력이 뚜렷한 향수"
          "(0.82)보다 작아진다는 뜻이다.")}
{rr.h_callout("팀 결정 ③ 기록 항목", [
    "T1 에서 두 번째 계열을 얻는 향수는 28개(14%)뿐이다. 나머지 172개는 여전히 1계열이다.",
    "T1·T4 는 100% 가 3계열 이하다. T2 는 99%, T3 는 84%, T6 는 7% 다.",
    "P5-C(평균 2.0 이하)는 UX 제약이지 통계적으로 유도한 값이 아니다 — "
    "한 향수가 지나치게 많은 Territory 에 영향을 주는 것을 막는다.",
])}
"""
    return rr.make_section("cond", "조건 정의", "hard → soft 8단계와 기여 구조", body)


def section_result(m, ps):
    agg = m["seed_aggregates"]
    rows = []
    for n in ORDER:
        a = agg[n]
        fr = int(sum(1 for r in ps if r["condition"] == n and r["fruity_territory"] == "True"))
        hl = n in ("T0w", "T1")
        rows.append([b(n) if hl else n,
                     b(f'{a["families_with_territory"]["mean"]:.1f} ± '
                       f'{a["families_with_territory"]["std"]:.1f}') if hl
                     else f'{a["families_with_territory"]["mean"]:.1f} ± '
                          f'{a["families_with_territory"]["std"]:.1f}',
                     f'{a["fragments_total"]["mean"]:.1f}',
                     f'{a["mean_coverage"]["mean"]:.3f}',
                     f'{fr}/5', f'{a["fruity_area"]["mean"]:.1%}',
                     f'{a["fruity_blob"]["mean"]:.0%}'])
    per = m["territory_per_family"]
    frows = []
    for f in FAMS:
        row = [KO[f]]
        for n in ORDER:
            v = per[n][f]
            hs = v["has_territory_seeds"]
            row.append('<span class="ok">✓</span>' if hs >= 3
                       else ('<span class="warn">~</span>' if hs
                             else '<span class="bad">✕</span>'))
        frows.append(row)
    body = f"""
{field_figure(m)}
{tbl(["조건", "Territory 보유 계열", "영역 조각 수", "평균 coverage",
      "프루티 보유", "프루티 면적", "프루티 덩어리"], rows)}
{tbl(["계열"] + ORDER, frows,
     note="✓ 보유(시드 5개 중 3+) · ~ 부분(1~2) · ✕ 없음(0)")}
{rr.h_callout("T1 은 9계열 전부 Territory 를 만든다", [
    "T1 의 Territory 보유 계열 수는 9.0 ± 0.0 — 5개 시드 전부에서 9계열이다.",
    "D0(T0)는 7.4계열이었고 프루티와 머스크가 없었다. T1 에서 둘 다 생긴다.",
    "영역 조각 수도 22.0 → 19.4 로 줄어든다. 더 뭉친다는 뜻이다.",
    "T2 부터는 무너진다 — 6.4 → 3.8 → 1.6. 계열이 서로 먹어 들어간다.",
], kind="ok")}
"""
    return rr.make_section("result", "결과", "조건별 Territory — T1 이 9계열을 만든다", body)


def section_lever(m):
    agg = m["seed_aggregates"]
    per = m["territory_per_family"]
    rows = [
        ["T0 → T0w", "강도 가중만 추가 (다계열 없음)",
         b(f'+{agg["T0w"]["families_with_territory"]["mean"] - agg["T0"]["families_with_territory"]["mean"]:.1f}계열'),
         "1.00 → 1.00", "프루티 1/5 → 4/5 · 머스크 없음 → 보유"],
        ["T0w → T1", "비중 0.30 이상 계열 추가",
         f'+{agg["T1"]["families_with_territory"]["mean"] - agg["T0w"]["families_with_territory"]["mean"]:.1f}계열',
         "1.00 → 1.14", "프루티 4/5 → 5/5"],
    ]
    musk = [[KO["MUSK"], n, str(per[n]["MUSK"]["contributors"]),
             f'{per[n]["MUSK"]["signal"]:.1f}',
             b(f'{per[n]["MUSK"]["largest_blob_share"]:.0%}'),
             f'{per[n]["MUSK"]["spread"]:.3f}',
             ('<span class="ok">보유</span>' if per[n]["MUSK"]["has_territory"]
              else '<span class="bad">없음</span>')] for n in ("T0", "T0w", "T1")]
    body = f"""
<p>T0w 는 <b>제가 추가한 통제 조건</b>이다. argmax 만 쓰되 Family Score 의 원래 강도로
가중한다 — 즉 <b>다계열을 전혀 쓰지 않는다.</b> T0 → T1 의 개선에서 '가중' 효과와
'다계열' 효과를 분리하기 위한 것이다.</p>
{tbl(["구간", "무엇이 추가됐나", "Territory 변화", "평균 active", "주목 계열"], rows)}
{rr.h_callout("개선의 75% 는 다계열이 아니라 '강도 가중' 에서 나온다", [
    "T0 → T0w 가 +1.2계열, T0w → T1 이 +0.4계열이다.",
    "T0w 는 향수당 계열이 여전히 1개다. 바뀐 것은 계열 신호가 약한 향수의 영향력을 "
    "줄인 것뿐이다 (총 신호량 200 → 80.2).",
    "즉 D0 의 Territory 문제는 '한 향수가 한 계열만 갖는 것' 보다 "
    "'계열 소속이 약한 향수가 강한 향수와 똑같은 무게로 영역을 그린 것' 이 더 컸다.",
])}
<h3 style="margin-top:1.6rem">머스크·파우더리가 이것으로 해결된다</h3>
{tbl(["계열", "조건", "기여 향수", "신호량", "최대 덩어리", "퍼짐", "판정"], musk,
     note="향수 수는 18 → 18 → 23 인데 신호량은 18.0 → 6.8 → 8.6 이다. "
          "머스크 argmax 인 18개의 평균 머스크 신호가 0.38 밖에 안 된다는 뜻이다.")}
{rr.h_callout("D25 의 '개수와 무관' 진단이 확인되고, 원인이 좁혀진다", [
    "D25 에서 머스크는 18 → 22 → 25개로 늘려도 덩어리가 55% → 83% → 53% 로 비단조였다.",
    "여기서는 개수를 그대로 두고 강도 가중만 넣었는데 55% → 61% 로 Territory 가 생긴다.",
    "머스크 argmax 18개 중 다수가 머스크 신호가 약한 향수였고, 그것들이 영역을 흩고 있었다.",
    "D26 결정 ④(powdery 를 modifier 로 다루기)와 같은 방향이다 — "
    "다만 이 실험은 taxonomy 를 바꾸지 않고 가중만 바꿨다.",
], kind="ok")}
"""
    return rr.make_section("lever", "무엇이 효과를 냈나",
                           "T0w 가 분리해낸 것 — 다계열이 아니라 강도 가중", body)


def section_focus(m):
    per = m["territory_per_family"]
    rows = []
    for f in m["focus_families"]:
        for n in ORDER:
            v = per[n][f]
            rows.append([KO[f] if n == ORDER[0] else "", n, str(v["contributors"]),
                         f'{v["signal"]:.1f}', f'{v["area_share"]:.1%}',
                         f'{v["largest_blob_share"]:.0%}',
                         f'{v["weighted_coverage"]:.3f}', f'{v["spread"]:.3f}',
                         ('<span class="ok">보유</span>' if v["has_territory"]
                          else '<span class="bad">없음</span>')])
    body = f"""
{tbl(["계열", "조건", "기여 향수", "신호량", "면적", "최대 덩어리",
      "weighted coverage", "퍼짐", "판정"], rows)}
<h3 style="margin-top:1.4rem">프루티 — 목적을 달성한다</h3>
<p>T0 에서 면적 2.7% 로 판정 1/5 이던 것이 T1 에서 4.0% · 덩어리 81% · <b>5/5</b> 가 된다.
<b>향수를 하나도 늘리지 않고</b> D26 결정 ⑤ 의 가설이 성립했다.</p>
<p>다만 <b>면적만 보면 T2 가 더 낫다</b>(7.1% · 덩어리 100%). 그런데 T2 는 프루티의
weighted coverage 가 0.571 로 떨어지고 다른 계열(구르망 · 머스크)이 무너져 전체
Territory 가 6.4계열이 된다. <b>Phase 4 의 앰버와 같은 상쇄</b>다.</p>
<h3 style="margin-top:1.6rem">아쿠아틱 — 어느 조건에서도 유지된다</h3>
<p>T0 부터 T6 까지 전 구간에서 Territory 를 유지한다. D26 결정 ③("작은 독립 Territory 를
유지한다")이 표현 방식을 바꿔도 성립한다. 다만 면적은 6.3% → 5.5%(T1)로 <b>줄어든다</b> —
다른 계열이 커지면서 밀린 것이다.</p>
"""
    return rr.make_section("focus", "주목 계열", "프루티 · 아쿠아틱 · 머스크", body)


def section_gate(m):
    v = m["verdicts"]
    rows = []
    for n in ORDER:
        d = v[n]
        rows.append([b(n) if d["passes_all"] else n,
                     f'{mk(d["gate_a_territory"])} {d["territory_families"]:.1f}',
                     f'{mk(d["gate_b_fruity"])} {d["fruity_seeds"]}/5',
                     f'{mk(d["gate_c_active"])} {d["mean_active_families"]:.2f}',
                     ('<span class="ok">통과</span>' if d["passes_all"]
                      else '<span class="bad">탈락</span>')])
    g = m["gates"]
    body = f"""
{tbl(["게이트", "기준", "근거"],
     [["P5-A", f'Territory 보유 계열 수 ≥ T0 ({g["P5-A"]["t0_value"]:.1f})',
       "Phase 4 P4-C 와 같은 전체 손실을 막는다"],
      ["P5-B", "프루티 Territory 보유 (시드 3/5 이상)",
       "이 실험의 목적 자체다 (팀 결정 ②)"],
      ["P5-C", f'향수당 평균 active Family ≤ {g["P5-C"]["threshold"]}',
       rr.esc(g["P5-C"]["note"])]])}
{tbl(["조건", "P5-A Territory", "P5-B 프루티", "P5-C 평균 active", "판정"], rows,
     note="T0(현재 방식)는 프루티가 1/5 이라 P5-B 에서 탈락한다 — 이 실험이 풀려는 문제 자체다.")}
{rr.h_callout("통과 2/8 — T0w · T1", [
    "T1 이 모든 축에서 앞선다 — Territory 9.0(최대) · 프루티 5/5 · 조각 19.4(T0w 22.4 보다 적음).",
    "T0w 는 다계열을 전혀 쓰지 않고도 통과한다. 구현이 더 단순하다는 장점이 있다.",
    "T2~T6 은 전부 P5-A 에서 탈락한다 — soft 를 더 넣을수록 계열이 서로 먹어 들어간다.",
], kind="ok")}
"""
    return rr.make_section("gate", "게이트 판정", "Hard Gate 판정", body)


def section_next(m):
    body = f"""
<h3>팀이 결정할 것</h3>
{tbl(["결정", "선택지", "판단 근거"],
     [["최종 Territory 계산 방식",
       "<b>T1 (권장)</b> / T0w / T0 유지",
       "T1 은 9계열 전부 · 프루티 5/5 · 조각 최소. T0w 는 다계열 없이 8.6계열로 "
       "구현이 더 단순하다"],
      ["D26 결정 ② (Amber 제한 balance)",
       "<b>불필요 (권장)</b> / 그래도 진행",
       "결정 ⑤ 가 성공했으므로 조건부였던 targeted balance 실험은 발동하지 않는다"],
      ["D26 결정 ④ (powdery modifier)",
       "계속 진행 / 우선순위 하향",
       "강도 가중으로 머스크 Territory 가 생겼지만 taxonomy 문제 자체가 사라진 것은 아니다. "
       "다만 시급성은 낮아졌다"],
      ["프론트 전달 형식",
       "계열별 기여 가중치를 함께 내보낼지",
       "T1 을 쓰면 향수마다 1~3개 계열과 그 가중치가 필요하다. 현재 스키마는 계열 1개다"]])}
<h3 style="margin-top:1.6rem">이어서 할 것</h3>
{tbl(["순서", "작업", "왜"],
     [["1", "T1 을 적용한 지도 재생성과 프론트 스키마 확인",
       "채택하면 <code>output/</code> 의 영역 데이터가 바뀐다. 좌표는 그대로다"],
      ["2", "UX 프로토타입 — 9개 라벨이 첫 화면에서 읽히는지",
       "Territory 가 9개 다 생겼으므로 이제 화면에서 구분되는지가 다음 문제다"],
      ["3", "사용자 테스트", "과제 2개 × 후보 2개"],
      ["—", "인식 축 결측 처리 민감도", "아직 재지 않았다"],
      ["—", "Holdout 300 · <code>gold_set_test.csv</code>", "이번에도 열지 않았다"]])}
{rr.h_callout("한계", [
    "T1 의 임계 0.30 은 스윕 격자의 한 점이다. 0.25 나 0.35 는 재지 않았다 — "
    "다만 T1(0.30) 과 T2(0.20) 사이에서 결과가 크게 갈리므로 그 사이는 볼 값이 있다.",
    "이 실험은 Territory 계산만 바꿨다. 좌표·향수 구성·계열 정의는 전부 그대로다.",
    "weighted coverage 임계 0.50 은 Phase 4 에서 그대로 가져온 값이다. "
    "T0 에서 두 정의가 정확히 일치함을 확인했으므로 재보정하지 않았다.",
], kind="warn")}
"""
    return rr.make_section("next", "다음", "팀 결정 사항과 다음 단계", body)


def main() -> None:
    os.chdir(MAP_DIR)
    m = rj(P5, "metrics.json")
    ps = rc(P5, "per_seed.csv")
    sections = [section_setup(m), section_conditions(m), section_result(m, ps),
                section_lever(m), section_focus(m), section_gate(m), section_next(m)]
    print(f"고유 절 {len(sections)}개를 렌더러에 넘깁니다")
    path, nsec, nkpi, nchk, nfig = rr.render(
        P5, os.path.abspath(os.path.join(P5, "summary.html")),
        title="Phase 5 — soft / multi-family Territory",
        extra_sections=sections, auto_data_figures=False)
    print(f"  -> {os.path.relpath(path)}  ({os.path.getsize(path)/1024:.0f} KB) · "
          f"절 {nsec}개 · 재현검증 {nchk} · 그림 {nfig}")


if __name__ == "__main__":
    main()

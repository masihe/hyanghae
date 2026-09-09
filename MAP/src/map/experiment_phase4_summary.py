"""Phase 4 팀 검토용 summary.html — 대표 향수 구성 균형 D0 / D1 / D2.

Run with venv/Scripts/python.exe src/map/experiment_phase4_summary.py

산출: experiments/phase4/summary.html
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

P4 = os.path.join("experiments", "phase4")
COMPS = ["D0 현재", "D1 cap30", "D2 최대균형"]
ROLE = {"D0 현재": "Control · 현재 출하 구성",
        "D1 cap30": "Conservative · 계열 상한 30",
        "D2 최대균형": "Territory candidate · 후보 풀 안 최대 균형"}
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


def mark(ok):
    return ('<span class="ok">○</span>' if ok else '<span class="bad">✕</span>')


# --------------------------------------------------------------------------
def section_setup(m):
    fx = m["fixed"]
    body = f"""
<p>Phase 4 는 <b>대표 향수 200개의 구성만</b> 바꾼다. 좌표 생성 방식과 구성을 동시에
바꾸면 개선의 원인을 판단할 수 없으므로, Phase 3 가 확정한 C8b 를 고정했다.</p>
{tbl(["고정한 것", "값", "근거"],
     [["좌표 방식", f"<b>C8b</b> — {rr.esc(fx['projection'])}", "D24 팀 결정 · 메인 후보"],
      ["대표 향수 수", f"{fx['n_display']}개 유지", "기획 유지 · 프론트·파이프라인이 200 기준"],
      ["후보 풀", f"{fx['pool']}개 고정", "매칭 파이프라인(D13~D20) 재실행 없음"],
      ["계열 체계", f"Set B {rr.esc(fx['family_system'])}", "D24 팀 결정 · Phase 4 중 수정 금지"],
      ["계열 내 선정 순서", rr.esc(fx["within_family_order"]),
       "계열이 뭉치도록 구성원을 고르면 결과 지표로 선정을 최적화하는 순환이 된다"],
      ["시드", f"{fx['seeds']}", "Phase 3 과 동일"]])}
<p>후보 풀의 계열 상한이 균형의 천장이다. <b>완전 균등은 데이터가 허용하지 않는다.</b></p>
{tbl(["계열"] + [KO[f] for f in FAMS],
     [["후보 풀 상한"] + [b(m["pool_supply"][f]) if m["pool_supply"][f] < 20
                       else str(m["pool_supply"][f]) for f in FAMS],
      ["D2 배분"] + [str(m["d2_quota"][f]) for f in FAMS]],
     note="프루티 14개 · 아쿠아틱 15개가 후보 풀 전체의 상한이다. "
          "9계열을 정확히 균등하게 하려면 지도가 126개가 된다.")}
"""
    lead = ("좌표 방식을 C8b 로 고정하고 구성 3안(D0 / D1 cap30 / D2 최대균형)을 "
            "같은 조건에서 비교했다.")
    return rr.make_section("setup", "전제", "고정한 전제와 데이터 상한", body, lead=lead)


def section_ratio_trap(m):
    c3 = m["cohesion_three_way"]
    rows = []
    e0 = c3["D0 현재"]["random_expected"]["mean"]
    for t in COMPS:
        o, e, r = c3[t]["observed"], c3[t]["random_expected"], c3[t]["ratio"]
        rows.append([rr.esc(t), f"{o['mean']:.4f} ± {o['std']:.4f}",
                     f"{e['mean']:.4f}", f"{e['mean']/e0:.3f}",
                     b(f"{r['mean']:.3f} ± {r['std']:.3f}")])
    d1 = m["paired_vs_d0"]["D1 cap30"]
    d2 = m["paired_vs_d0"]["D2 최대균형"]
    body = f"""
<p>Phase 4 의 Hard Gate 를 <code>normalized cohesion ratio</code> 로 걸지 않았다.
그 값의 분모가 <b>무작위 기대 Σp<sub>f</sub>²</b> 이고, Phase 4 는 <b>계열 분포를 조작
변수로 삼는 실험</b>이라 분모가 오염된다.</p>
<pre class="eq">ratio = 관측 응집도 / 무작위 기대(Σp²)        분모가 균형에 따라 작아진다</pre>
{tbl(["구성", "관측 응집도 (raw)", "무작위 기대 Σp²", "분모 D0 대비", "ratio"], rows,
     note="관측 응집도는 시드 5개 평균±표준편차. 무작위 기대는 계열 분포만으로 결정되므로 "
          "시드에 무관하다.")}
{rr.h_callout("실행 전 예측이 그대로 맞았다", [
    "실행 전 계산 — 관측 응집도가 D0 와 똑같더라도 D2 의 ratio 는 3.921 → 5.411 로 오른다.",
    f"실측 — D2 의 ratio 는 {d2['cohesion_ratio']['diff_mean']:+.3f} 올랐는데 "
    f"관측 응집도는 {d2['observed_cohesion']['diff_mean']:+.4f} 로 오히려 내려갔다.",
    f"D1 도 같다 — ratio {d1['cohesion_ratio']['diff_mean']:+.3f} · "
    f"관측 {d1['observed_cohesion']['diff_mean']:+.4f}.",
    "ratio 상승분은 전부 분모에서 나왔다. ratio 로 게이트를 걸었다면 두 안 모두 "
    "'큰 개선' 으로 통과했을 것이다.",
], kind="warn")}
<p class="note">같은 정규화가 계열 개수 비교(7 / 8 / 9)에서는 <b>필수</b>였다.
거기서는 계열 <b>개수</b>가 변수여서 교정이었고, 여기서는 계열 <b>분포</b>가 변수여서
버그가 된다. 같은 공식이 무엇을 조작하느냐에 따라 역할이 반대가 된다.</p>
"""
    return rr.make_section("trap", "지표 함정",
                           "왜 cohesion ratio 로 게이트를 걸지 않았는가", body)


def section_composition(m):
    rows = []
    for t in COMPS:
        c = m["compositions"][t]
        rows.append([b(rr.esc(t)) if t == "D2 최대균형" else rr.esc(t),
                     rr.esc(ROLE[t]), str(c["swapped"]),
                     f'{mark(c["gate_a_top50"])} {c["top50_kept"]}/50',
                     f'{c["top100_kept"]}/100',
                     f'{mark(c["gate_b_accord"])} {c["accord_coverage"]}',
                     str(c["brands"]),
                     f'{c["trusted_edges"]}쌍', f'{c["cross_family_edges"]}쌍'])
    dr = []
    for t in COMPS:
        c = m["compositions"][t]
        d, a = c["dropped_ranks"], c["added_ranks"]
        dr.append([rr.esc(t),
                   "—" if not d else f"{min(d)}위 / 중앙 {int(np.median(d))}위 / {max(d)}위",
                   "—" if not a else f"{min(a)}위 / 중앙 {int(np.median(a))}위 / {max(a)}위"])
    dist = []
    for f in FAMS:
        row = [KO[f], str(m["pool_supply"][f])]
        for t in COMPS:
            c = m["compositions"][t]
            row.append(f'{c["argmax_counts"][f]} / {c["fractional_counts"][f]:.1f}')
        dist.append(row)
    cv = [["argmax 기준"] + [f'{m["compositions"][t]["argmax_cv"]:.3f}' for t in COMPS],
          ["fractional 기준"] + [b(f'{m["compositions"][t]["fractional_cv"]:.3f}')
                             for t in COMPS],
          ["argmax 최대 비중"] + [f'{m["compositions"][t]["argmax_max_share"]:.1%}'
                            for t in COMPS],
          ["fractional 최대 비중"] + [f'{m["compositions"][t]["fractional_max_share"]:.1%}'
                                for t in COMPS]]
    body = f"""
<p>Gate P4-A(TOP50)와 P4-B(accord)는 좌표를 만들지 않고 선정 단계에서 판정된다.</p>
{tbl(["구성", "역할", "교체", "P4-A TOP50", "TOP100", "P4-B accord", "브랜드",
      "신뢰 간선", "계열 횡단"], rows,
     note="Review Guardrail — 신뢰 간선 >= 38 · 계열 횡단 >= 20. 자동 탈락 기준이 아니다. "
          "D2 는 38쌍 / 21쌍으로 두 값 모두 경계선이다.")}
{rr.h_callout("Gate P4-A · P4-B 는 세 안 모두 통과한다", [
    "국내 TOP50 은 어느 안에서도 빠지지 않는다 (50/50).",
    "균형이 오히려 다양성을 늘린다 — accord 60 → 62 → 63종, 브랜드 71 → 74 → 76개.",
    "대신 신뢰 간선이 줄어든다 — 44 → 42 → 38쌍, 계열 횡단 25 → 25 → 21쌍.",
], kind="ok")}
<h3 style="margin-top:1.6rem">교체되는 향수의 국내 순위</h3>
{tbl(["구성", "빠지는 향수 (최상위 / 중앙 / 최하위)", "들어오는 향수"], dr,
     note="D2 에서 빠지는 37개는 전부 플로럴이다. 들어오는 37개는 앰버 11 · 머스크 7 · "
          "프루티 6 · 구르망 5 · 그린 3 · 아쿠아틱 3 · 시트러스 1 · 우디 1.")}
<h3 style="margin-top:1.6rem">계열 분포 — argmax / fractional 병기</h3>
{tbl(["계열", "후보 풀 상한"] + COMPS, dist,
     note="형식: argmax 개수 / fractional 합. fractional 은 계열 점수를 비중으로 나눠 더한 값. "
          "선정은 argmax 로 했고 검증만 두 기준으로 본다 (균형을 맞추려고 경계 향수를 "
          "재분류하지 않았다).")}
{tbl(["편중 지표"] + COMPS, cv)}
{rr.h_callout("argmax 와 fractional 의 결론이 갈린다", [
    "플로럴 편중은 argmax 의 산물이다 — D0 에서 argmax 61개(30.5%)인데 fractional 39.3(19.6%).",
    "프루티는 개수가 부족한 게 아니다 — D0 argmax 8개인데 fractional 14.9. "
    "프루티 성분을 가진 향수는 이미 있는데 1위를 못 잡는다.",
    "아쿠아틱은 반대로 과대표집돼 있다 — argmax 12개인데 fractional 6.9 로 9계열 중 "
    "성분 총량이 가장 작다.",
    "그래서 D1 과 D2 의 균형 차이가 줄어든다 — argmax CV 0.301 vs 0.187 인데 "
    "fractional CV 는 0.305 vs 0.279 로 거의 같다.",
], kind="warn")}
"""
    return rr.make_section("comp", "구성 3안", "구성 3안과 선정 단계 판정", body)


def section_territory(m, terr):
    per = m["territory_per_family"]
    rows = []
    for f in FAMS:
        row = [KO[f]]
        for t in COMPS:
            v = per[t][f]
            hs = v["has_territory_seeds"]
            sym = ('<span class="ok">✓</span>' if hs >= 3
                   else ('<span class="warn">~</span>' if hs > 0
                         else '<span class="bad">✕</span>'))
            row.append(f'{sym} {v["n"]}개 · 면적 {v["area_share"]:.1%} · '
                       f'덩어리 {v["largest_blob_share"]:.0%} · 위 {v["on_own"]:.2f}')
        rows.append(row)
    agg = m["seed_aggregates"]
    summ = [["Territory 보유 계열 수"] + [b(f'{agg[t]["families_with_territory"]["mean"]:.1f}'
                                     f' ± {agg[t]["families_with_territory"]["std"]:.1f}')
                                   for t in COMPS],
            ["자기 계열 영역 위"] + [f'{agg[t]["on_own_region"]["mean"]:.3f}' for t in COMPS],
            ["영역 조각 수"] + [f'{agg[t]["fragments_total"]["mean"]:.1f}' for t in COMPS],
            ["관측 응집도"] + [f'{agg[t]["observed_cohesion"]["mean"]:.4f}' for t in COMPS]]
    seeds = sorted({int(r["seed"]) for r in terr})
    sd = [["시드 " + str(s)] + [str(int(sum(1 for r in terr
                                            if r["composition"] == t and int(r["seed"]) == s
                                            and r["has_territory"] == "True")))
                              for t in COMPS] for s in seeds]
    body = f"""
<p>팀 §12 우선순위 ①②를 직접 재기 위해 <b>계열별 Territory 존재</b>를 판정했다.
판정 규칙은 실행 전에 확정했다.</p>
{tbl(["조건", "임계", "근거"],
     [["면적 점유", "≥ 3%", "9계열 균등이 11.1% 이므로 그 1/4 미만이면 화면에서 못 찾는다"],
      ["최대 연속 덩어리", "≥ 60%", "자기 면적 중 가장 큰 조각. 조각나면 '그 구역' 이 없다"],
      ["자기 영역 위", "≥ 0.50", "구성원 절반 이상이 자기 영역 안에"],
      ["시드", "5개 중 3개 이상 통과", "experiments/README.md 게이트 시드 규칙"]])}
{tbl(["지표"] + COMPS, summ)}
{tbl(["계열"] + COMPS, rows,
     note="면적은 육지 셀 점유율(KDE argmax · D12 고정 파라미터). "
          "✓ 보유(5시드 중 3+) · ~ 부분(1~2) · ✕ 없음(0).")}
{tbl(["시드별 Territory 보유 계열 수"] + COMPS, sd)}
{rr.h_callout("균형을 맞추면 Territory 보유 계열 수가 줄어든다", [
    "D0 7.4계열 → D1 6.2 → D2 6.8. 두 안 모두 5개 시드 전부에서 D0 보다 낮다.",
    "프루티는 D2 에서 얻는다 — 면적 2.7% → 3.7%, 덩어리 71% → 84%, 판정 1/5 → 5/5.",
    "앰버·스파이시는 두 안 모두에서 잃는다 — 덩어리 99% → 53%(D1) / 48%(D2). "
    "개수는 14 → 22 → 25 로 늘고 면적도 7.7% → 11.7% 로 늘지만 영역이 갈라진다.",
    "앰버 향수의 95.2%가 자기 영역 위에 있다. 향수가 흩어진 것이 아니라 "
    "**영역이 두 조각 이상으로 갈라진** 것이다.",
    "영역 조각 수도 늘어난다 — 16.4 → 19.0 → 25.0 (D2 는 +8.6, 유의).",
], kind="warn")}
"""
    return rr.make_section("terr", "Territory 판정",
                           "계열별 Territory 존재 — Phase 4 의 최우선 지표", body)


def section_focus(m):
    per = m["territory_per_family"]
    rows = []
    for f in ("FRUITY", "AQUATIC", "MUSK"):
        for t in COMPS:
            v = per[t][f]
            rows.append([KO[f] if t == COMPS[0] else "", rr.esc(t), str(v["n"]),
                         f'{v["area_share"]:.1%}',
                         b(f'{v["largest_blob_share"]:.0%}'),
                         f'{v["spread"]:.3f}', f'{v["on_own"]:.3f}',
                         ('<span class="ok">보유</span>' if v["has_territory"]
                          else '<span class="bad">없음</span>')])
    body = f"""
{tbl(["계열", "구성", "개수", "면적", "최대 덩어리", "퍼짐", "자기 영역 위", "판정"], rows,
     note="퍼짐 = 자기 계열 중심까지 평균거리 / 지도 평균 반경. 1.0 이면 지도 전체에 "
          "흩어진 것과 같다.")}
<h3 style="margin-top:1.6rem">프루티 — D2 가 문제를 해결한다</h3>
<p>개수 8 → 14, 면적 2.7% → 3.7%, 덩어리 71% → 84%. 판정이 1/5 에서 5/5 로 바뀐다.
팀 §2 가 정의한 문제("Fruity 가 지도에서 사실상 존재하지 않는 것처럼 보이는 경우")를
D2 가 해결한다.</p>
{rr.h_callout("다만 임계값에 민감한 판정이다", [
    "면적 임계 3% 에서 D0 는 2.7% 로 간신히 미달, D2 는 3.7% 로 간신히 통과다.",
    "임계가 2.5% 면 D0 도 통과해서 D2 의 이득이 사라지고, 4% 면 D2 도 탈락한다.",
    "임계값에 무관한 사실 — 면적 +37% · 덩어리 +13%p. 방향은 실재한다.",
], kind="warn")}
<h3 style="margin-top:1.6rem">아쿠아틱 — 개수를 늘려도 나아지지 않는다</h3>
<p>12 → 15개로 늘려도 면적은 6.3% → 6.8% 로 거의 그대로고 <b>덩어리는 85% → 73% 로
나빠진다.</b> 판정도 5/5 → 3/5 로 약해진다. 선정 단계에서 이미 예측된 결과다 —
아쿠아틱의 fractional 합은 6.9(D0) / 7.4(D2)로 <b>9계열 중 성분 총량이 가장 작다.</b>
argmax 로는 12개지만 실제 아쿠아틱 성분을 가진 향수는 7개분에 불과하다.</p>
<h3 style="margin-top:1.6rem">머스크·파우더리 — 개수와 무관하다 (팀 §9 진단)</h3>
{tbl(["개수", "면적", "최대 덩어리", "퍼짐", "판정"],
     [["18개 (D0)", "10.3%", b("55%"), "1.010", "없음"],
      ["22개 (D1)", "15.0%", b("83%"), "0.836", '<span class="ok">보유</span>'],
      ["25개 (D2)", "17.4%", b("53%"), "1.093", "없음"]])}
{rr.h_callout("팀 §9 의 두 갈래 중 후자다 — 별도 후속 작업으로 분리한다", [
    "18개 → 22개에서 좋아지고 22개 → 25개에서 다시 나빠진다. **단조롭지 않다.**",
    "개수가 원인이라면 늘릴수록 좋아져야 한다. 그렇지 않으므로 개수는 원인이 아니다.",
    "퍼짐도 1.010 → 0.836 → 1.093 으로 되돌아온다. 25개에서는 지도 전체에 흩어진 것과 같다.",
    "팀 §9 에 따라 Phase 4 에서 Set B taxonomy 를 수정하지 않았다. "
    "powdery 보유율 47.7% 와 'powdery 가 Family 보다 cross-family modifier 에 가까운지' 는 "
    "별도 후속 작업에서 다룬다.",
], kind="warn")}
"""
    return rr.make_section("focus", "주목 계열",
                           "프루티 · 아쿠아틱 · 머스크 — 팀 §10 별도 확인", body)


def section_gate(m):
    v = m["verdicts"]
    g = m["gates"]["P4-C"]
    rows = []
    for t in COMPS:
        d = v[t]
        rows.append([b(rr.esc(t)), mark(d["gate_a"]), mark(d["gate_b"]),
                     f'{mark(d["gate_c_territory"])} {d["territory_families"]:.1f}',
                     f'{mark(d["gate_c_observed"])} {d["observed_cohesion"]:.4f}',
                     ('<span class="ok">통과</span>' if d["passes_all"]
                      else '<span class="bad">탈락</span>'),
                     " · ".join(d["review_flags"]) or "—"])
    pk = [("families_with_territory", "Territory 보유 계열", 2, +1),
          ("observed_cohesion", "관측 응집도", 4, +1),
          ("cohesion_ratio", "ratio (분모 오염)", 3, 0),
          ("on_own_region", "자기 계열 영역 위", 4, +1),
          ("fragments_total", "영역 조각 수", 1, -1),
          ("boundary_gap", "경계 향수 분리도", 4, +1),
          ("knn_overlap10", "Korea overlap@10", 4, +1),
          ("reminds_pct", "정답 간선 근접도", 4, -1),
          ("cross_family_proximity", "계열 횡단 근접도", 4, -1)]
    prow = []
    for k, ko, nd, good in pk:
        row = [ko]
        for t in COMPS[1:]:
            d = m["paired_vs_d0"][t][k]
            sig = "*" if d["significant"] else ""
            row.append(f'{d["diff_mean"]:+.{nd}f}{sig} · {d["positive_seeds"]}/5')
        prow.append(row)
    ra = m["record_axes"]
    rrow = [["trust@10"] + [f'{ra[t]["trust10"]["mean"]:.4f}' for t in COMPS],
            ["rare accord 공유"] + [f'{ra[t]["shared_rare_accord_ge1"]["mean"]:.1%}'
                                 for t in COMPS],
            ["최근접 이웃 설명 불가"] + [f'{ra[t]["nearest_unexplained"]["mean"]:.1f}'
                                for t in COMPS],
            ["y = 계절"] + [f'{ra[t]["y_warmth_rho"]["mean"]:.3f}' for t in COMPS],
            ["x = 성별"] + [f'{ra[t]["x_masculine_rho"]["mean"]:.3f}' for t in COMPS]]
    body = f"""
<p>Hard Gate 는 실행 전에 확정했고 결과를 보고 바꾸지 않았다.
P4-C baseline 은 D0 다 — Territory {g['d0_territory_families']:.1f}계열 ·
관측 응집도 {g['d0_observed_cohesion']:.4f}.</p>
{tbl(["구성", "P4-A TOP50", "P4-B accord", "P4-C Territory ≥ D0",
      "P4-C 관측 응집도 ≥ D0", "판정", "Review"], rows)}
{rr.h_callout("Hard Gate 판정 — D1 · D2 모두 탈락, D0 유지", [
    "P4-A · P4-B 는 세 안 모두 통과한다.",
    "P4-C 두 조건 모두 실패한다 — Territory 계열 수(D1 6.2 / D2 6.8 < D0 7.4)와 "
    "관측 응집도(D1 0.6121 / D2 0.6135 < D0 0.6222).",
    "D2 는 Review Guardrail 도 경계선이다 (신뢰 간선 38 = 기준 38, 계열 횡단 21 vs 기준 20).",
], kind="warn")}
<h3 style="margin-top:1.6rem">D0 대비 시드를 짝지은 차이</h3>
{tbl(["지표"] + COMPS[1:], prow,
     note="* = |평균| > 2 × 시드 표준편차. n/5 = D0 보다 값이 큰 시드 수. "
          "정답 간선 근접도와 계열 횡단 근접도는 낮을수록 좋다.")}
{rr.h_callout("예상하지 못한 이득과 손실", [
    "Korea overlap@10 이 개선된다 — D1 +0.0157 · D2 +0.0173(유의, 5/5). "
    "플로럴 61개를 24개로 줄이면 이웃 경쟁이 줄어 이웃 목록이 원본과 더 잘 맞는다.",
    "자기 계열 영역 위도 개선된다 — D2 +0.0280 (4/5).",
    "경계 향수 분리도는 나빠진다 — D2 −0.0426(유의, 0/5). 팀 §12 우선순위 ④ 와 충돌한다.",
    "정답 간선 근접도와 계열 횡단 근접도도 나빠진다 (D2 +0.0207 · +0.0343).",
])}
<h3 style="margin-top:1.6rem">기록 축 (판정에 쓰지 않는다)</h3>
{tbl(["지표"] + COMPS, rrow,
     note="accord 종류는 늘었는데(60 → 63종) 이웃끼리 희귀 accord 를 공유하는 비율은 "
          "떨어진다(73.3% → 66.6%). 다양성이 늘어도 이웃의 설명력은 약해진다.")}
"""
    return rr.make_section("gate", "게이트 판정", "Hard Gate 판정과 D0 대비 차이", body)


def section_maps(coord_rows):
    by, fam = {}, {}
    for r in coord_rows:
        by.setdefault(r["composition"], []).append(
            (int(r["fragrantica_id"]), float(r["x"]), float(r["y"])))
        fam[int(r["fragrantica_id"])] = r["family"]
    panels = []
    for t in COMPS:
        if t not in by:
            continue
        rows = by[t]
        panels.append((t, [i for i, _, _ in rows],
                       np.array([[x, y] for _, x, y in rows], dtype=float)))
    fig = rr.map_compare_figure(
        panels, families=fam, align_to_first=True,
        source="experiments/phase4/coordinates_korea200.csv", point_size=13,
        extra_note="Korea 200 · C8b · seed 42 · 색은 Set B 9계열 argmax")
    body = f"""
<p>세 구성을 같은 계열 색으로 칠했다. <b>구성원이 다르므로 점의 개체가 다르다</b> —
D0 와 D2 는 163개를 공유하고 37개가 다르다.</p>
{fig}
{rr.h_callout("눈으로 보는 차이", [
    "D0 는 플로럴(자홍)이 지도의 29.4% 를 덮는다. D2 는 7.2% 로 줄어든다.",
    "D2 에서 프루티(주홍)가 하나의 덩어리로 보이기 시작한다.",
    "D2 에서 앰버(주황)가 두 군데 이상으로 갈라진다 — 최대 덩어리 48%.",
    "머스크(회청)는 세 구성 모두 지도 여러 곳에 흩어져 있다.",
])}
"""
    return rr.make_section("maps", "지도 비교", "같은 계열 색으로 본 구성 3안", body)


def section_next(m):
    body = f"""
<h3>팀이 결정할 것</h3>
{tbl(["결정", "선택지", "판단 근거"],
     [["D0 / D1 / D2 최종 선택",
       "<b>D0 유지 (게이트 판정)</b> / D2 채택 (우선순위 ② 근거)",
       "Hard Gate 로는 D1·D2 모두 탈락한다. 그런데 팀 §12 우선순위 ②('Fruity 처럼 작은 "
       "계열이 분명한 영역을 형성하는가')는 D2 가 유일하게 달성한다. "
       "게이트와 우선순위가 충돌하는 지점이다"],
      ["Gate P4-C 를 그대로 둘 것인가",
       "유지 / 계열별 판정으로 완화",
       "현재 P4-C 는 '보유 계열 수 총합'이라 프루티 획득(+1)과 앰버 상실(−1)이 상쇄된다. "
       "'작은 계열의 획득'에 가중을 두면 판정이 달라질 수 있다"],
      ["앰버·스파이시를 어떻게 다룰지",
       "D0 유지로 회피 / 앰버만 상한을 걸어 D2 변형",
       "앰버는 국내 상위 14개가 우연히 응집적이었고(덩어리 99%) 후보 풀의 나머지 앰버는 "
       "흩어져 있다. 앰버를 14~18개로 제한한 D2 변형이 가능하다"],
      ["아쿠아틱을 독립 Territory 로 만들 것인가",
       "포기 / 후보 확보 재검토",
       "fractional 6.9~7.4 로 성분 총량이 9계열 중 최소다. 개수를 늘려도 덩어리가 "
       "85% → 73% 로 나빠진다. 후보 풀 안에서는 해결되지 않는다"],
      ["프루티의 원인 진단",
       "개수 조정(D2) / 라벨 규칙 재검토",
       "argmax 8개인데 fractional 14.9 다. 개수를 늘리는 것보다 라벨 규칙을 보는 쪽이 "
       "근본적일 수 있다. 다만 팀 §9 와 같은 이유로 Phase 4 중에는 Set B 를 수정하지 않았다"]])}
<h3 style="margin-top:1.6rem">이어서 할 것</h3>
{tbl(["순서", "작업", "왜"],
     [["1", "머스크·파우더리 계열 정의 재검토 (별도 작업)",
       "개수와 무관함이 확인됐다. powdery 보유율 47.7% · Family vs cross-family modifier"],
      ["2", "앰버 상한을 건 D2 변형 (팀이 요청하면)",
       "D2 의 유일한 Territory 손실이 앰버다. 이것만 막으면 게이트를 통과할 수 있다"],
      ["3", "Phase 5 — UX 프로토타입",
       "9개 라벨이 첫 화면에서 읽히는지. 데이터가 답할 수 없는 문제다"],
      ["4", "Phase 6 — 사용자 테스트", "과제 2개 × 후보 2개"],
      ["—", "인식 축 결측 처리 민감도", "아직 재지 않았다"],
      ["—", "Holdout 300 · <code>gold_set_test.csv</code>",
       "모든 튜닝이 끝난 뒤 1회. 이번에도 열지 않았다"]])}
{rr.h_callout("이 실험이 남긴 방법론", [
    "정규화 지표는 무엇을 조작하느냐에 따라 교정이 되거나 버그가 된다. "
    "계열 개수 비교에서는 Σp² 정규화가 필수였고, 계열 분포 비교에서는 같은 정규화가 "
    "분모 오염이었다.",
    "실행 전에 이 함정을 계산해 두고 게이트를 관측값으로 바꾼 것이 결론을 뒤집었다 — "
    "ratio 로 걸었다면 D2 가 +1.414 로 '큰 개선' 통과였다.",
])}
"""
    return rr.make_section("next", "다음", "팀 결정 사항과 다음 단계", body)


def main() -> None:
    os.chdir(MAP_DIR)
    m = rj(P4, "metrics.json")
    terr = rc(P4, "territory.csv")
    coord = rc(P4, "coordinates_korea200.csv")
    sections = [section_setup(m), section_ratio_trap(m), section_composition(m),
                section_territory(m, terr), section_focus(m), section_gate(m),
                section_maps(coord), section_next(m)]
    print(f"고유 절 {len(sections)}개를 렌더러에 넘깁니다")
    path, nsec, nkpi, nchk, nfig = rr.render(
        P4, os.path.abspath(os.path.join(P4, "summary.html")),
        title="Phase 4 — 대표 향수 구성 균형",
        extra_sections=sections, auto_data_figures=False)
    print(f"  -> {os.path.relpath(path)}  ({os.path.getsize(path)/1024:.0f} KB) · "
          f"절 {nsec}개 · KPI {nkpi} · 재현검증 {nchk} · 그림 {nfig}")


if __name__ == "__main__":
    main()

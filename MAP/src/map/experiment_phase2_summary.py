"""Phase 2 팀 검토용 summary.html — 투영 7종을 한 화면에서 비교한다.

Run with venv/Scripts/python.exe src/map/experiment_phase2_summary.py

산출: experiments/phase2/summary.html
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

PHASE2 = os.path.join("experiments", "phase2")
FAM_CSV = os.path.join("experiments", "phase0_family_count_comparison",
                       "assignments_korea200.csv")
ORDER = ["UMAP", "t-SNE", "PaCMAP", "TriMap-dist", "TriMap-feat", "kNN graph + force", "PCA"]
K_LEVELS = (5, 10, 20)
POP_KO = {"global1000": "Global 1,000", "korea200": "Korea 200"}


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


def agg(m, pop, layout, metric, field="mean"):
    return m[pop][layout]["agg"][metric][field]


def section_intro(m):
    rows = []
    for L in ORDER:
        b = m["global1000"][L]
        rows.append([f"<b>{rr.esc(L)}</b>", rr.esc(b["input"]),
                     "확률적" if b["kind"] == "stochastic" else "결정적",
                     len(b["seeds"]), f'{b["elapsed_sec"]}s'])
    body = f"""
<p>Phase 2 의 질문은 하나다 — <b>고정된 유사도를 어떤 2D 투영이 가장 잘 옮기는가.</b>
모든 투영이 같은 원본 공간을 공유하므로 kNN overlap 계열 지표를 공정하게 쓸 수 있다
(Phase 1 은 원본 공간 자체를 바꾸는 실험이라 이 지표를 쓸 수 없었다).</p>
<p><b>입력이 하나다.</b> Phase 1 의 A8 / A7 / A2 가 전부 baseline 을 넘지 못해 신규 후보가
0개이므로 유사도는 현재 방식으로 고정했다 —
<code>0.5 x accord 코사인(raw strength, L2) + 0.5 x note IDF 가중 Jaccard</code>.</p>
{tbl(["투영", "입력", "종류", "시드", "소요"], rows,
     note="PaCMAP 만 특징행렬 입력이다 — Phase 0 의 의존성 확인에서 distance='precomputed' 가 NotImplementedError 로 거부되는 것을 실행으로 확인했다. 그 교란을 통제하려고 TriMap 을 거리·특징 두 경로로 돌렸다.")}
<p class="note">UMAP seed 42 가 Phase 0 이 고정한 기준값을 재현한 뒤에만 결과를 냈다 —
Global 1,000 trust@10 0.9387 / overlap@10 0.3888, Korea 200 0.9191 / 0.4875.</p>
"""
    return rr.make_section("p2a", "설정", "무엇을 비교했는가", body, after="s1")


def section_maps(coord_rows, fam_rows):
    fam_of = {int(r["fragrantica_id"]): r["9_family"] for r in fam_rows}
    panels = []
    for L in ORDER:
        rows = [r for r in coord_rows if r["layout"] == L]
        if not rows:
            continue
        ids = [int(r["fragrantica_id"]) for r in rows]
        xy = np.array([[float(r["x"]), float(r["y"])] for r in rows])
        panels.append((L, ids, xy))
    blocks = []
    for chunk in (panels[:4], panels[4:]):
        if chunk:
            blocks.append(rr.map_compare_figure(
                chunk, families=fam_of, align_to_first=True,
                source="coordinates_korea200.csv", point_size=13))
    body = f"""
<p>Korea 200 을 7가지 투영으로 그린 것이다. 색은 accord 기반 9계열
(reviewed-1 · Family 체계 비교 실험의 배정)이다.</p>
{"".join(blocks)}
<p class="note"><b>이번에는 정렬이 실제로 필요하다.</b> 투영마다 좌표계가 다르므로 회전·반사
정렬 없이는 모양을 비교할 수 없다. Family 체계 비교 실험에서는 모든 체계가 같은 좌표를
공유해 정렬이 no-op 이었던 것과 다르다. <b>지표는 정렬 전 좌표로 계산했다.</b></p>
"""
    return rr.make_section("p2b", "지도", "같은 유사도, 다른 투영", body, after="p2a")


def section_local(m):
    figs = []
    for pop in ("global1000", "korea200"):
        series = [(f"overlap@{k}", [agg(m, pop, L, f"knn_overlap@{k}") for L in ORDER], None)
                  for k in K_LEVELS]
        f = rr.fig_grouped_bar(ORDER, series,
                               title=f"{POP_KO[pop]} — kNN overlap@5/10/20 (높을수록 좋음)",
                               fmt=lambda v: f"{v:.3f}")
        if f:
            figs.append(rr.figure_block(f, f"{POP_KO[pop]} 국소 이웃 보존",
                                        source="layout_comparison.csv"))
    rows = []
    for pop in ("global1000", "korea200"):
        for L in ORDER:
            rows.append([f"<b>{rr.esc(L)}</b>", POP_KO[pop],
                         f'{agg(m, pop, L, "trust@10"):.4f} ± {agg(m, pop, L, "trust@10", "std"):.4f}',
                         f'{agg(m, pop, L, "knn_overlap@5"):.4f}',
                         f'{agg(m, pop, L, "knn_overlap@10"):.4f}',
                         f'{agg(m, pop, L, "knn_overlap@20"):.4f}',
                         f'{agg(m, pop, L, "continuity@10"):.4f}'])
    body = f"""
<p>세 지표가 국소 보존을 다른 각도에서 잰다.</p>
<ul>
<li><b>trustworthiness@K</b> — 지도에서는 옆에 있는데 원본에서는 멀었던 향수에 벌점.
1 에 가까우면 거짓 이웃이 적다</li>
<li><b>kNN overlap@K</b> — 원본에서 가까운 K개가 지도에서도 이웃 K개 안에 몇 개 남는가</li>
<li><b>continuity@K</b> — 원본에서는 이웃인데 지도에서 밀려난 향수에 벌점 (직접 구현.
scikit-learn 에 없다)</li>
</ul>
{"".join(figs)}
{tbl(["투영", "모집단", "trust@10 (시드 5개)", "overlap@5", "overlap@10", "overlap@20",
      "continuity@10"], rows)}
<p class="warn"><b>t-SNE 가 UMAP 보다 국소 보존이 낫다.</b> Global 1,000 에서 trust@10
0.9484 vs 0.9366, overlap@10 0.4261 vs 0.3878 이다. Korea 200 에서도 overlap@10 이
0.4935 vs 0.4846 로 앞선다. <b>"UMAP 이 최선" 이라는 전제가 이 측정으로 부정됐다.</b></p>
"""
    return rr.make_section("p2c", "국소", "옆에 있는 게 실제로 비슷한가", body, after="p2b")


def section_global(m):
    figs = []
    for pop in ("global1000", "korea200"):
        items = [(L, agg(m, pop, L, "distance_rank_corr"),
                  rr.FIG_DEEP if L == "UMAP" else None) for L in ORDER]
        f = rr.fig_bar_colored([(a, b, c or rr.FIG_SHOAL) for a, b, c in items],
                               title=f"{POP_KO[pop]} — 거리 순위 상관 (높을수록 좋음)",
                               xlabel="원본 거리 순서와 2D 거리 순서의 spearman",
                               fmt=lambda v: f"{v:.3f}")
        if f:
            figs.append(rr.figure_block(f, f"{POP_KO[pop]} 전역 구조 보존",
                                        source="layout_comparison.csv"))
    rows = [[f"<b>{rr.esc(L)}</b>",
             f'{agg(m, "global1000", L, "distance_rank_corr"):+.3f}',
             f'{agg(m, "korea200", L, "distance_rank_corr"):+.3f}',
             f'{agg(m, "global1000", L, "continuity@20"):.4f}',
             f'{agg(m, "korea200", L, "continuity@20"):.4f}'] for L in ORDER]
    body = f"""
<p>전역 구조는 "지도에서 멀리 있는 지역이 실제로도 더 다른가" 다. 원본 거리 순서와 2D 거리
순서의 spearman 상관으로 잰다.</p>
{"".join(figs)}
{tbl(["투영", "거리순위 (Global)", "거리순위 (Korea)", "continuity@20 (Global)",
      "continuity@20 (Korea)"], rows)}
<p><b>국소와 전역이 반대로 움직인다.</b> Global 1,000 에서 kNN 그래프+force 는 거리 순위
상관이 0.520 으로 가장 높지만(UMAP 0.440) overlap@10 은 0.1067 로 무너진다(UMAP 0.3878).
PCA 도 같은 방향이다 — 전역 0.476, 국소 0.0810.</p>
<p class="note">이건 차원 축소 문헌이 말하는 local/global trade-off 가 우리 데이터에서
그대로 나타난 것이다. 하나의 지표로 최선을 정할 수 없다는 v4 의 전제가 확인됐다.</p>
"""
    return rr.make_section("p2d", "전역", "멀리 있는 지역이 실제로 더 다른가", body, after="p2c")


def section_guardrail(m):
    figs = []
    for pop in ("global1000", "korea200"):
        items = [(L, agg(m, pop, L, "reminds_pct"),
                  rr.FIG_DEEP if L == "UMAP" else rr.FIG_WARN) for L in ORDER]
        f = rr.fig_bar_colored(items,
                               title=f"{POP_KO[pop]} — 사람 투표 신뢰 쌍의 2D 근접도 (낮을수록 좋음)",
                               xlabel="0 이 가장 가깝고 0.5 가 무작위", fmt=lambda v: f"{v:.4f}")
        if f:
            figs.append(rr.figure_block(f, f"{POP_KO[pop]} 보호 지표",
                                        source="layout_comparison.csv"))
    rows = [[f"<b>{rr.esc(L)}</b>",
             f'{agg(m, "global1000", L, "reminds_pct"):.4f}',
             f'{agg(m, "global1000", L, "reminds_pct") - agg(m, "global1000", "UMAP", "reminds_pct"):+.4f}',
             f'{agg(m, "korea200", L, "reminds_pct"):.4f}',
             f'{agg(m, "korea200", L, "reminds_pct") - agg(m, "korea200", "UMAP", "reminds_pct"):+.4f}',
             f'{agg(m, "global1000", L, "also_liked_pct"):.4f}'] for L in ORDER]
    body = f"""
<p>이 지표가 향 지도의 원래 주장이다 — <b>사람이 "닮았다" 고 투표한 향수가 지도에서 실제로
가까운가.</b> Global 1,000 에 872쌍, Korea 200 에 44쌍이 있다.</p>
{"".join(figs)}
{tbl(["투영", "정답간선 근접도 (Global)", "UMAP 대비", "정답간선 (Korea)", "UMAP 대비",
      "also_liked (진단용)"], rows,
     note="also_liked 는 투표가 없는 알고리즘 출력이라 D6 대로 진단 지표로만 본다.")}
<p class="warn"><b>TriMap 이 사람 판단에 가장 가깝다.</b> Global 1,000 에서 TriMap-feat
0.1571 · TriMap-dist 0.1578 로 UMAP(0.1689)보다 좋고, Korea 200 에서도 TriMap-dist 가
0.1569 로 UMAP(0.1672)을 앞선다. PCA 만 뚜렷하게 나쁘다(0.2019 / 0.2269).</p>
"""
    return rr.make_section("p2e", "보호 지표", "닮았다고 한 향수가 가까운가", body, after="p2d")


def section_stability(m):
    rows = []
    for L in ORDER:
        g, k = m["global1000"][L], m["korea200"][L]
        gs = g.get("neighbor_stability@10")
        ks = k.get("neighbor_stability@10")
        gc = g.get("coordinate_stability")
        rows.append([f"<b>{rr.esc(L)}</b>",
                     "결정적 (시드 없음)" if gs is None else f'{gs["mean"]:.3f}',
                     "—" if gs is None else f'{gs["min"]:.3f}',
                     "—" if ks is None else f'{ks["mean"]:.3f}',
                     "—" if gc is None else f'{gc["mean_residual"]:.4f}',
                     f'{agg(m, "global1000", L, "trust@10", "std"):.4f}'])
    items = [(L, m["global1000"][L].get("neighbor_stability@10", {}).get("mean", 1.0),
              rr.FIG_DEEP if L == "UMAP" else rr.FIG_SHOAL) for L in ORDER]
    f = rr.fig_bar_colored(items, title="Global 1,000 — 시드 간 이웃 집합 겹침 (높을수록 안정)",
                           xlabel="시드 쌍 10개의 top10 이웃 집합 평균 겹침",
                           fmt=lambda v: f"{v:.3f}")
    body = f"""
<p>같은 데이터·같은 파라미터로 시드만 5개(42, 1, 2, 3, 4) 바꿔 돌렸다. 지도를 다시
생성해도 세계가 크게 바뀌지 않아야 사용자가 공간을 기억할 수 있다.</p>
<p class="note">이웃 집합 겹침은 <b>정합이 필요 없는 지표</b> 다 — 좌표가 회전·반사돼도
이웃 목록은 그대로다. 좌표 잔차는 Procrustes 정합 후에 잰 값이다.</p>
{rr.figure_block(f, "시드 쌍 10개의 top10 이웃 집합 평균 겹침", source="metrics.json") if f else ""}
{tbl(["투영", "이웃 겹침 (Global 평균)", "최소", "이웃 겹침 (Korea)", "좌표 잔차 (Global)",
      "trust@10 표준편차"], rows)}
<p><b>UMAP 이 가장 안정적이다</b> (Global 0.639 · Korea 0.703). PaCMAP 이 가장 불안정하다
(0.425). t-SNE 는 국소 보존이 가장 좋은 대신 안정성이 UMAP 보다 낮다(0.598).</p>
<p class="note">이웃 겹침 0.639 는 "같은 향수의 이웃 10개 중 6.4개가 시드를 바꿔도 그대로"
라는 뜻이다. 남은 3.6개는 시드가 정한다 — 어느 투영을 쓰든 지도의 세부는 재생성마다 바뀐다.</p>
"""
    return rr.make_section("p2f", "안정성", "다시 만들어도 같은 세계인가", body, after="p2e")


def section_confound(m):
    rows = []
    for L in ("TriMap-dist", "TriMap-feat"):
        rows.append([f"<b>{rr.esc(L)}</b>", rr.esc(m["global1000"][L]["input"]),
                     f'{agg(m, "global1000", L, "trust@10"):.4f}',
                     f'{agg(m, "global1000", L, "knn_overlap@10"):.4f}',
                     f'{agg(m, "global1000", L, "distance_rank_corr"):+.3f}',
                     f'{agg(m, "global1000", L, "reminds_pct"):.4f}'])
    rows.append([f"<b>PaCMAP</b>", "features",
                 f'{agg(m, "global1000", "PaCMAP", "trust@10"):.4f}',
                 f'{agg(m, "global1000", "PaCMAP", "knn_overlap@10"):.4f}',
                 f'{agg(m, "global1000", "PaCMAP", "distance_rank_corr"):+.3f}',
                 f'{agg(m, "global1000", "PaCMAP", "reminds_pct"):.4f}'])
    d_trust = abs(agg(m, "global1000", "TriMap-dist", "trust@10")
                  - agg(m, "global1000", "TriMap-feat", "trust@10"))
    d_ov = abs(agg(m, "global1000", "TriMap-dist", "knn_overlap@10")
               - agg(m, "global1000", "TriMap-feat", "knn_overlap@10"))
    body = f"""
<p><b>PaCMAP 은 다른 투영과 입력이 다르다.</b> precomputed 거리행렬을 받지 못해
accord+note 특징행렬을 쓴다. 그러면 PaCMAP 의 성적이 투영 방식 때문인지 입력 표현 때문인지
구분되지 않는다 — manifest 의 <code>changed_variable</code> 이 "한 줄에 한 가지" 여야
한다는 규약에 어긋난다.</p>
<p>그래서 <b>TriMap 을 거리행렬·특징행렬 두 경로로 돌려 입력 효과만 분리했다.</b></p>
{tbl(["조건", "입력", "trust@10", "overlap@10", "거리순위", "정답간선"], rows)}
<p class="warn"><b>입력 표현의 효과는 작다.</b> TriMap 의 두 경로 차이가 trust@10
{d_trust:.4f} · overlap@10 {d_ov:.4f} 다. PaCMAP 이 TriMap 보다 overlap@10 에서 0.02 이상
낮은 것은 <b>입력 때문이 아니라 투영 방식 때문</b> 이라고 귀속할 수 있다.</p>
<p class="note">이 대조가 없으면 "PaCMAP 이 나쁜 건 입력이 달라서" 라는 반론을 배제할 수
없었다. 교란을 제거하지 못할 때는 <b>그 교란의 크기를 따로 재는 것</b> 이 다음 최선이다.</p>
"""
    return rr.make_section("p2g", "교란 통제", "PaCMAP 의 입력 차이는 얼마나 영향을 주는가",
                           body, after="p2f")


def section_decide(m):
    rel = {r["layout"]: r for r in m["relative_to_umap_global1000"]}
    front = m["pareto_front_global1000"]
    rows = []
    for L in ORDER:
        r = rel[L]
        rows.append([f"<b>{rr.esc(L)}</b>",
                     f'{r["local"]:.4f}', f'{r["local_delta"]:+.4f}',
                     f'{r["global"]:+.3f}', f'{r["global_delta"]:+.4f}',
                     f'{r["reminds"]:.4f}', f'{r["reminds_delta"]:+.4f}',
                     f'{r["stability"]:.3f}',
                     "○" if L in front else "—"])
    body = f"""
<p>절대 탈락선을 쓰지 않았다. 기존 <code>overlap >= 0.30</code> 은 D2 의 UMAP 스윕
최저값에서 나온 값이므로 t-SNE·TriMap 에 자동 탈락선으로 적용하면 "UMAP 계열이 아니면
탈락" 이 된다 (v4 20).</p>
{tbl(["투영", "local (overlap 평균)", "UMAP 대비", "global (거리순위)", "UMAP 대비",
      "정답간선", "UMAP 대비", "시드 안정성", "Pareto"], rows,
     note="local 은 overlap@5/10/20 의 평균이다. Pareto 는 local·global·안정성 세 축에서 비지배인 후보를 표시한다 — 축이 셋이라 front 가 넓다(5/7). 이게 v4 34 가 최종 후보 축소를 Gate → 비교축 → 기록축의 계층으로 바꾼 이유다.")}
<h3>투영마다 무엇을 잘하는가</h3>
<table class="tight"><thead><tr><th>투영</th><th>강점</th><th>약점</th></tr></thead><tbody>
<tr><td><b>UMAP</b></td><td>시드 안정성 1위 (Global 0.639 · Korea 0.703) · 현재 프로덕션이라
하위 파이프라인(지형·영역)이 이미 이 좌표에 맞춰져 있다</td>
<td>국소 보존이 t-SNE 보다 낮다 · 사람 투표 근접도가 TriMap 보다 나쁘다</td></tr>
<tr><td><b>t-SNE</b></td><td>국소 보존 1위 (Global overlap@10 0.4261 · trust@10 0.9484)</td>
<td>전역 구조가 가장 약하다(거리순위 0.414) · 시드 안정성 0.598 ·
문헌상 cluster 간 거리·방향을 의미로 읽으면 안 된다</td></tr>
<tr><td><b>TriMap-dist</b></td><td><b>사람 투표 근접도 1위</b> (Global 0.1578 · Korea 0.1569) ·
전역 구조가 UMAP 보다 낫다(+0.0083)</td>
<td>국소 보존이 UMAP 보다 낮다(overlap@10 0.3244) · 시드 안정성 0.506</td></tr>
<tr><td><b>kNN graph + force</b></td><td>전역 구조 1위 (거리순위 0.520) ·
continuity@10 1위 (0.9162)</td>
<td>국소 보존이 무너진다 (overlap@10 0.1067) — 향 지도의 핵심 약속을 지키지 못한다</td></tr>
<tr><td><b>PaCMAP · TriMap-feat</b></td><td>—</td>
<td>Pareto 지배됨. PaCMAP 은 시드 안정성도 최하(0.425)</td></tr>
<tr><td><b>PCA</b></td><td>결정적 (시드 없음) · 비교 기준선</td>
<td>국소·정답간선 모두 최하. 단순한 방법의 바닥을 보여주는 역할</td></tr>
</tbody></table>
<h3>팀이 결정할 것</h3>
<ol>
<li><b>Phase 3 를 어느 좌표로 진행할 것인가.</b> 세 후보가 서로 다른 것을 준다 —
UMAP(안정성) · t-SNE(국소) · TriMap-dist(사람 판단 + 전역). 데이터로는 하나가 우월하지 않다</li>
<li><b>투영을 바꾸면 하위 산출물을 모두 다시 만들어야 한다.</b> 현재 출하 중인
<code>korea_scent_map_v2.json</code> 의 지형(밀도 격자·해안선)·영역·이웃 목록이 전부 UMAP
seed 42 좌표에서 나온 것이다. D12 의 지형 파라미터 스윕도 그 좌표에서 고른 값이다</li>
<li><b>t-SNE 를 쓸 경우 UI 규칙이 하나 늘어난다</b> — cluster 간 거리와 방향을 의미로
설명해서는 안 된다. Phase 0 의 축 회전(Compass) 후보와 충돌할 수 있다</li>
<li><b>안정성을 어디까지 요구하는가.</b> 이웃 겹침 0.639 는 이웃 10개 중 3.6개가 시드마다
바뀐다는 뜻이다. 어느 투영을 쓰든 지도의 세부는 재생성마다 달라진다</li>
</ol>
<h3>내 추천</h3>
<p><b>UMAP 유지를 권한다.</b> 다만 근거는 "UMAP 이 가장 좋다" 가 아니다 — 세 후보가 서로 다른
축에서 이기므로 데이터가 하나를 고르지 못하고, 그 상태에서는 <b>이미 검증된 하위 파이프라인을
버리지 않는 쪽</b>이 합리적이다. D12 의 지형 파라미터, D11 의 모집단 결정, Phase 0 의 축 회전
분석이 모두 UMAP seed 42 좌표 위에서 측정됐다.</p>
<p class="warn">단 <b>TriMap-dist 는 후속 검토 대상으로 남길 값이 있다.</b> 사람 투표 근접도가
두 모집단 모두에서 UMAP 보다 좋다(Global −0.0111 · Korea −0.0103). 향 지도의 핵심 주장이
"닮았다고 한 향수가 가깝다" 라면 이 지표가 가장 직접적이다. Phase 3 의 영역 실험이 끝난 뒤
TriMap-dist 로 같은 실험을 반복하는 비용은 좌표 재생성 한 번이다.</p>
"""
    return rr.make_section("p2h", "판단", "Pareto · 장단점 · 추천", body, after="p2g")


def main() -> None:
    os.chdir(MAP_DIR)
    print("=" * 78)
    print("Phase 2 — 팀 검토용 summary.html")
    print("=" * 78)
    m = rj(PHASE2, "metrics.json")
    coord_rows = rc(PHASE2, "coordinates_korea200.csv")
    fam_rows = rc(FAM_CSV)
    print(f"읽은 산출물 — 투영 {len(ORDER)}종 · Korea 좌표 {len(coord_rows)}행 · "
          f"계열 배정 {len(fam_rows)}행")

    sections = [section_intro(m), section_maps(coord_rows, fam_rows),
                section_local(m), section_global(m), section_guardrail(m),
                section_stability(m), section_confound(m), section_decide(m)]
    print(f"고유 절 {len(sections)}개를 렌더러에 넘깁니다")
    path, nsec, nkpi, nchk, nfig = rr.render(
        PHASE2, os.path.abspath(os.path.join(PHASE2, "summary.html")),
        title="Phase 2 — 2D 투영 비교 결과",
        extra_sections=sections, auto_data_figures=False)
    size = os.path.getsize(path) / 1024
    print(f"\n  -> {os.path.relpath(path)}  ({size:.0f} KB) · 섹션 {nsec}개")


if __name__ == "__main__":
    main()

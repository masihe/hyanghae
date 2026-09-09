"""Phase 1 팀 검토용 summary.html — A8 / A7 / A2 를 한 화면에서 비교한다.

Run with venv/Scripts/python.exe src/map/experiment_phase1_summary.py

v4 30.2 대로 팀 검토의 기본 단위는 Phase summary 다. 개별 실험은 표준 데이터만 남기고
(DROP 된 실험은 metrics.json + 한 줄 결론) 이 파일 하나에서 "다음 단계로 무엇을 올릴지" 를
결정한다.

산출: experiments/phase1/summary.html, manifest.json, metrics.json
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

PHASE1 = os.path.join("experiments", "phase1")
A8 = os.path.join("experiments", "P1_A8_NOTE_COOCCURRENCE")
A7 = os.path.join("experiments", "P1_A7_NOTE_GRANULARITY")
A2 = os.path.join("experiments", "P1_A2_ACCORD_RANK")

BASE_NDCG = 0.2709
BASE_TOP10 = 0.4464
CONTROL_TOP10 = 0.4501


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


def line_figure(series, xlabel, ylabel, title, hlines=None, logx=True):
    """(라벨, x리스트, y리스트, 색) 시리즈를 선으로 그린다."""
    import matplotlib.pyplot as plt
    rr._rc()
    fig, ax = plt.subplots(figsize=(7.2, 3.8))
    for label, xs, ys, color in series:
        ax.plot(xs, ys, marker="o", ms=5, lw=1.6, color=color, label=label)
    for y, lab, c in (hlines or []):
        ax.axhline(y, ls="--", lw=1.1, color=c)
        ax.text(ax.get_xlim()[1], y, f" {lab}", va="center", fontsize=8, color=c)
    if logx:
        ax.set_xscale("log")
    ax.set_xlabel(xlabel, fontsize=9, color=rr.FIG_MUTED)
    ax.set_ylabel(ylabel, fontsize=9, color=rr.FIG_MUTED)
    ax.set_title(title, fontsize=10, color=rr.FIG_INK)
    ax.legend(fontsize=8, frameon=False)
    ax.grid(axis="y", color=rr.FIG_HAIR, lw=0.6)
    for sp in ax.spines.values():
        sp.set_color(rr.FIG_HAIR)
    fig.tight_layout()
    return rr.fig_to_img(fig, title)


def section_overview(m8, m7, m2):
    rows = [
        ["<b>A8</b>", "note 공동출현 (PPMI + SVD)", "PRIORITY 1",
         f"{max(v['ndcg'] for v in m8['a8_variants']):.4f}",
         f"{max(v['top10_hit'] for v in m8['a8_variants']):.4f}", "<b>DROP</b>"],
        ["<b>A7</b>", "note 집계 세밀도 곡선", "PRIORITY 2",
         f"{max(r['ndcg'] for r in m7['curve'][1:]):.4f}",
         f"{max(r['top10_hit'] for r in m7['curve'][1:]):.4f}",
         f"<b>{m7['verdict']}</b>"],
        ["<b>A2</b>", "accord 순위/강도 표현", "저비용",
         f"{max(v['ndcg'] for v in m2['variants'] if v['variant'] != 'baseline_strength'):.4f}",
         f"{max(v['top10_hit'] for v in m2['variants'] if v['variant'] != 'baseline_strength'):.4f}",
         "<b>DROP</b>"],
        ["기준", "accord raw strength 0.5 + note IDF-Jaccard 0.5", "현재 프로덕션",
         f"<b>{BASE_NDCG:.4f}</b>", f"<b>{BASE_TOP10:.4f}</b>", "—"],
    ]
    body = f"""
<p>Phase 1 의 질문은 하나였다 — <b>어떤 feature 가 사람들이 "비슷하다" 고 평가한 향수를
가장 잘 찾는가.</b> 신규 실험 3개를 돌렸고 <b>전부 현재 방식을 넘지 못했다.</b></p>
{tbl(["실험", "무엇을 바꿨나", "우선순위", "최고 ndcg@10", "최고 top10 포함률", "판정"], rows,
     note="KEEP 기준은 ndcg@10 > 0.2709 AND 신뢰 파트너 top10 포함률 >= 0.4464 다 (v4 14). 세 실험의 최고 지점도 기준에 닿지 못했다.")}
<p class="warn"><b>Phase 2 로 가져갈 유사도는 현재 방식이다.</b> 이건 "바꿀 수 있는데 안 했다"
가 아니라 <b>"재보니 바꿀 게 없었다"</b> 다 — D21 이 남긴 구분이며, 세 실험의 곡선과 진단을
기록해 같은 질문의 재발을 막는다.</p>
<p class="note">모든 실험은 Dev 700 만 썼다. <b>Holdout 300 은 건드리지 않았다.</b>
세 실험 모두 baseline 재현(ndcg 0.2709 / top10 0.4464)을 4자리까지 확인한 뒤에만 결과를 냈다.</p>
"""
    return rr.make_section("p1a", "종합", "Phase 1 이 답한 것", body, after="s1")


def section_a8(m8, rel):
    v = sorted(m8["a8_variants"], key=lambda r: -r["ndcg"])
    rows = [[rr.esc(r["variant"]), r["svd_dim"], rr.esc(r["note_weighting"]),
             rr.esc(r["negative"]), f'{r["ndcg"]:.4f}',
             f'{r["ndcg"] - BASE_NDCG:+.4f}', f'{r["top10_hit"]:.4f}',
             f'{r["top10_hit"] - BASE_TOP10:+.4f}',
             f'{r["explain_shared_note_ge1"]:.1%}'] for r in v]
    probe = [r for r in rel if r.get("cooccur")]
    prow = [[f'<code>{rr.esc(r["note_a"])}</code>', f'<code>{rr.esc(r["note_b"])}</code>',
             f'{int(r["cooccur"]):,}', r["ppmi"], f'{int(r["df_a"]):,}', f'{int(r["df_b"]):,}']
            for r in probe[-5:]]
    noise = [[f'<code>{rr.esc(r["note_a"])}</code>', f'<code>{rr.esc(r["note_b"])}</code>',
              f'{int(r["cooccur"]):,}', r["ppmi"], f'{int(r["df_a"]):,}', f'{int(r["df_b"]):,}']
             for r in rel[:6]]
    fig = rr.fig_grouped_bar(
        [r["variant"] for r in v],
        [("ndcg@10", [r["ndcg"] for r in v], rr.FIG_DEEP),
         ("top10 포함률", [r["top10_hit"] for r in v], rr.FIG_SHOAL)],
        title="A8 변형 8종 — 기준선(0.2709 / 0.4464)에 닿지 못한다",
        fmt=lambda x: f"{x:.3f}")
    d = m8["diagnosis"]
    body = f"""
<p><b>가설.</b> note 문자열을 합치지 않고 note 사이 관계를 더하면, 이름이 달라도 향 구조상
가까운 향수를 더 잘 찾는다. 현재 note 채널은 IDF 가중 Jaccard 라서 <b>문자열이 같아야만</b>
유사도가 생기고, Global 1,000 쌍의 36.1% 가 note 유사도 0 이다.</p>
{rr.figure_block(fig, "차원(64/128) x 가중(idf/plain) x 음수처리(clip0/raw)", source="variants.csv") if fig else ""}
{tbl(["변형", "차원", "가중", "음수", "ndcg@10", "Δ", "top10", "Δ", "공통note≥1"], rows)}
<h3>왜 실패했는가 — 원인 두 가지</h3>
<p class="warn"><b>① 공동출현은 "대체 가능성" 이 아니라 "함께 쓰임" 을 잰다.</b>
실험의 동기가 된 쌍을 직접 보면 드러난다.</p>
{tbl(["note A", "note B", "동시출현", "PPMI", "A 보유 향수", "B 보유 향수"], prow,
     note="Oud 와 Agarwood (Oud) 는 같은 재료의 다른 이름이다. 한 향수가 둘 중 하나만 쓰므로 동시출현이 6회뿐이고 PPMI 가 0 이다. 동의어일수록 공동출현이 낮다 — 방법이 동기와 정반대 방향이다.")}
<p class="warn"><b>② PPMI 가 희귀 잡음을 최대로 증폭한다.</b> PPMI 상위 쌍이 전부
보유 향수 1개끼리의 단일 동시출현이다.</p>
{tbl(["note A", "note B", "동시출현", "PPMI", "A 보유", "B 보유"], noise)}
<p>2,523종 중 대부분이 희귀 note 라 임베딩 공간이 이 잡음에 지배된다. SVD 설명 분산도
k=64 에서 0.247, k=128 에서 0.343 뿐이다.</p>
<h3>덤으로 나온 방법론적 발견 — 외부 기준 두 개가 반대 방향을 가리켰다</h3>
<p>Phase 0 에서 미리 잰 대조군(PPMI 없이 Jaccard → 코사인만 교체)이 이렇게 갈렸다.</p>
{tbl(["조건", "Dev 700 ndcg@10", "Global top10 포함률"],
     [["baseline (IDF-Jaccard)", f"<b>{BASE_NDCG:.4f}</b>", f"{BASE_TOP10:.4f}"],
      ["대조군 (IDF-cosine, PPMI 없음)", f'{m8["control_note_cosine_no_ppmi"]["dev700"]["ndcg"]:.4f}',
       f"<b>{CONTROL_TOP10:.4f}</b>"]],
     note="같은 변경이 한 지표는 올리고(+0.0037) 다른 지표는 내린다(-0.0135). v4 가 Phase 1 에 두 지표를 모두 요구한 이유가 이 사례로 확인됐다.")}
<p class="note">진단 조건 — PPMI 없이 <code>log1p(count)</code> 로 SVD 하면 ndcg
{m8["diagnostic_count_only"]["dev700"]["ndcg"]:.4f} 로 더 나쁘다. v4 16.3 대로 최종 평가
경로로 쓰지 않았다. rescue {m8["rescue_count"]}건 vs regression
{m8["regression_count"]}건 — 신뢰 쌍이 top10 에서 빠진 경우가 두 배 많다.</p>
"""
    return rr.make_section("p1b", "A8", "note 공동출현 — DROP", body, after="p1a")


def section_a7(m7, samples):
    curve = m7["curve"]
    acc = [r for r in curve if r["input"] == "accord"]
    coo = [r for r in curve if r["input"] == "cooc"]
    base = curve[0]
    fig1 = line_figure(
        [("note→accord 프로파일 (대체 가능성)", [r["vocab"] for r in acc],
          [r["ndcg"] for r in acc], rr.FIG_DEEP),
         ("A8 PPMI+SVD (함께 쓰임)", [r["vocab"] for r in coo],
          [r["ndcg"] for r in coo], rr.FIG_LAND)],
        "어휘 크기 (log)", "ndcg@10", "세밀도 곡선 — ndcg@10",
        hlines=[(BASE_NDCG, f"기준 {BASE_NDCG}", rr.FIG_WARN)])
    fig2 = line_figure(
        [("note→accord 프로파일", [r["vocab"] for r in acc],
          [r["top10_hit"] for r in acc], rr.FIG_DEEP),
         ("A8 PPMI+SVD", [r["vocab"] for r in coo],
          [r["top10_hit"] for r in coo], rr.FIG_LAND)],
        "어휘 크기 (log)", "top10 포함률", "세밀도 곡선 — 신뢰 파트너 top10 포함률",
        hlines=[(BASE_TOP10, f"기준 {BASE_TOP10}", rr.FIG_WARN)])
    rows = [[rr.esc(r["label"]), f'{r["vocab"]:,}',
             f'{r["unique_representations"]:,}', f'{r["ndcg"]:.4f}',
             f'{r["top10_hit"]:.4f}', f'{r["zero_pair_share"]:.1%}',
             f'{r["explain_shared_note_ge1"]:.1%}'] for r in curve]
    rows.append(["<i>9계열 (Phase 0 사전점검)</i>", "9", "315", "—", "0.3114", "1.9%", "—"])
    srow = [[rr.esc(s["input_label"]), s["group_size"], f'{int(s["total_perfumes"]):,}',
             f'<code>{rr.esc(s["members_top8"])}</code>'] for s in samples]
    body = f"""
<p><b>가설.</b> note 를 중간 세밀도(100~300 그룹)로 묶으면 표층 문자열의 한계를 넘으면서
향수 구분력은 유지할 수 있다. 양 끝은 이미 알고 있었다 — 2,523종(현재)과 9계열(무너짐,
top10 0.3114), 그리고 D21 의 동의어 통일 48건(변화 없음). <b>가운데가 비어 있었다.</b></p>
<p><b>입력을 두 개 썼다.</b> 플랜은 A8 의 임베딩을 쓰기로 했는데, A8 진단에서 공동출현이
대체 가능성과 어긋난다는 것이 드러났다. 그래서 대체 가능성 신호(note→accord 프로파일)를
함께 돌려 비교했다.</p>
{rr.figure_block(fig1, "가로축은 합친 뒤의 어휘 크기 (오른쪽이 덜 합친 것)", source="granularity_curve.csv")}
{rr.figure_block(fig2, "두 지표 모두 기준선을 넘는 지점이 없다", source="granularity_curve.csv")}
{tbl(["조건", "어휘", "구별되는 note 집합", "ndcg@10", "top10", "note 유사도 0 인 쌍", "공통note≥1"], rows,
     note="구별되는 note 집합 = 131,930개 향수 중 서로 다른 note 조합의 수. 합칠수록 줄어든다 = 향수를 구별하지 못한다.")}
<h3>곡선에 스윗스팟이 없다</h3>
<p><b>덜 합칠수록 기준선에 가까워지기만 한다.</b> note→accord 입력의 최고점은
어휘 2,351종(k=600)에서 ndcg 0.2724 로 기준선을 <b>0.0015</b> 넘지만 top10 은 0.4397 로
0.0067 낮다. 한 지표만 넘었으므로 REVIEW 이고, 개선폭이 D21 이 "개선이 아니다" 로 판정한
-0.0007 과 같은 자리수다. <b>중간 세밀도에 얻을 것이 있다는 근거가 나오지 않았다.</b></p>
<p class="warn"><b>플랜이 지정한 입력(A8 임베딩)이 더 나빴다.</b> 같은 어휘 크기에서
note→accord 프로파일보다 ndcg 가 0.06~0.07 낮다. A8 진단이 예측한 대로다 —
"함께 쓰임" 으로 묶으면 대체 가능한 재료가 묶이지 않는다.</p>
<h3>사람 표본 검토 — 묶음이 말이 되는가</h3>
{tbl(["입력", "그룹 크기", "보유 향수 합", "구성원 (보유 상위 8)"], srow,
     note="일부는 진짜 대체 가능한 묶음이다 (Musk 계열, Vanilla 계열, Jasmine 계열). 그런데 Bergamot 과 Cedar 가 한 그룹에 들어가고 Peach 와 Orchid 가 같이 묶인다 — accord 차원이 74종뿐이라 같은 accord 역할을 하는 note 가 냄새가 달라도 합쳐진다.")}
<p class="note">판정 <b>{m7["verdict"]}</b> — 채택할 지점은 없지만 곡선을 기록한다.
"어느 세밀도부터 구분력이 무너지는가" 에 대한 답을 남겨 같은 질문의 재발을 막는다.</p>
"""
    return rr.make_section("p1c", "A7", f"note 집계 세밀도 — {m7['verdict']}", body, after="p1b")


def section_a2(m2):
    v = sorted(m2["variants"], key=lambda r: -r["ndcg"])
    rows = [[rr.esc(r["variant"]), rr.esc(r["description"]), f'{r["ndcg"]:.4f}',
             f'{r["ndcg"] - BASE_NDCG:+.4f}', f'{r["top10_hit"]:.4f}',
             f'{r["top10_hit"] - BASE_TOP10:+.4f}',
             "baseline" if r["variant"] == "baseline_strength" else m2["verdicts"][r["variant"]]]
            for r in v]
    fig = rr.fig_grouped_bar(
        [r["variant"] for r in v],
        [("ndcg@10", [r["ndcg"] for r in v], rr.FIG_DEEP),
         ("top10 포함률", [r["top10_hit"] for r in v], rr.FIG_SHOAL)],
        title="A2 — raw strength 를 이기는 표현이 없다", fmt=lambda x: f"{x:.3f}")
    body = f"""
<p><b>가설.</b> 현재 accord 채널은 raw strength 를 그대로 쓴다(1순위는 항상 100, 8순위는
중앙 26). 상위 accord 를 더 강조하거나 순위만 쓰면 개선될 수 있다.</p>
<p class="note">EDA 05 가 기각한 <b>accord IDF</b> 와 다른 실험이다 — 여기서 바꾼 것은
강도 표현이고 note 채널은 baseline 으로 고정했다 (한 번에 한 가지만 바꾼다).</p>
{rr.figure_block(fig, "8종 전부 두 지표에서 baseline 미달", source="variants.csv") if fig else ""}
{tbl(["변형", "설명", "ndcg@10", "Δ", "top10", "Δ", "판정"], rows)}
<p><b>가장 가까운 것이 <code>rank_linear</code>(순위만 8..1)로 ndcg -0.0049 · top10 -0.0121</b>
이고, 상위 3개만 쓰는 것이 가장 나쁘다(-0.0462 / -0.1048). <b>strength 값 자체가 정보를
담고 있다</b>는 뜻이다 — 순위로 바꾸거나 잘라내면 그만큼 잃는다.</p>
"""
    return rr.make_section("p1d", "A2", "accord 강도 표현 — DROP", body, after="p1c")


def section_next(m7):
    body = f"""
<h3>Phase 2 로 무엇을 가져가는가</h3>
<p><b>유사도는 현재 방식을 그대로 쓴다</b> —
<code>0.5 x accord 코사인(raw strength, L2) + 0.5 x note IDF 가중 Jaccard</code>.
v4 14 는 "Phase 2 에 가져갈 feature 는 현재 baseline + 신규 개선 후보 최대 1~2개" 로
제한했는데, <b>신규 후보가 0개다.</b></p>
<p>따라서 Phase 2(투영 비교)는 baseline 유사도 하나로 진행한다. Phase 0 의 의존성 확인 결과
후보는 UMAP · t-SNE · PaCMAP · TriMap · kNN graph 5개이며, <b>PaCMAP 만 precomputed 거리행렬을
받지 못해</b> accord+note 특징행렬 입력을 써야 한다 — 투영 차이와 입력 표현 차이가 섞이므로
대조 조건으로 명시해야 한다.</p>
<h3>Phase 1 이 남긴 것 — 음의 결과 세 개의 값</h3>
<ul>
<li><b>A8</b> — 공동출현으로는 "이름이 다른 같은 재료" 를 잡을 수 없다. 동의어는 오히려
동시출현이 0 에 가깝다. 이 방향을 다시 꺼낼 때 필요한 것은 <b>대체 가능성 신호</b> 이고,
공동출현은 그것이 아니다</li>
<li><b>A7</b> — 중간 세밀도 구간에 스윗스팟이 없다. 어휘를 합칠수록 단조롭게 나빠지고
기준선에 닿는 지점은 "거의 합치지 않은" 지점이다. 2,523 -> 9 구간의 곡선을 기록했다</li>
<li><b>A2</b> — accord strength 값 자체가 정보다. 순위로 바꾸거나 상위만 남기면 잃는다</li>
</ul>
<p class="warn"><b>D21 의 결론이 독립적으로 재확인됐다.</b> D21 은 가중치 스윕(42조합)과
동의어 통일만 봤고, 이번에는 완전히 다른 세 방향(공동출현 임베딩 · 세밀도 집계 · 강도 표현)을
봤다. 셋 다 음의 결과다. <b>"accord 8개 + note 표층 문자열" 의 천장 ndcg 0.2709 는
현재 데이터에서 실제로 천장이다.</b></p>
<h3>팀이 결정할 것</h3>
<ol>
<li><b>Phase 2 를 baseline 유사도 하나로 진행하는 데 동의하는가</b> — Phase 1 에 신규 후보가
없으므로 투영 비교의 입력이 하나다</li>
<li><b>천장을 넘으려면 데이터를 늘려야 한다.</b> v4 가 DEFER 한 것 중 리뷰 텍스트 기반
perception 이 그 방향이다. PLAN.md 6 이 배제한 description 임베딩·벡터 DB 도 같은 성격이며
이건 팀 범위 결정이다</li>
<li><b>Holdout 300 은 아직 쓰지 않았다.</b> 모든 튜닝이 끝난 뒤 1회만 확인해야 하며
Phase 1 에 채택된 변경이 없으므로 지금 쓸 이유가 없다</li>
</ol>
"""
    return rr.make_section("p1e", "다음", "Phase 2 진입 조건", body, after="p1d")


def main() -> None:
    os.chdir(MAP_DIR)
    os.makedirs(PHASE1, exist_ok=True)
    print("=" * 78)
    print("Phase 1 — 팀 검토용 summary.html")
    print("=" * 78)

    m8, m7, m2 = rj(A8, "metrics.json"), rj(A7, "metrics.json"), rj(A2, "metrics.json")
    rel = rc(A8, "note_relations.csv")
    samples = rc(A7, "group_samples.csv")
    print(f"읽은 산출물 — A8 변형 {len(m8['a8_variants'])}종 · A7 곡선 {len(m7['curve'])}점 · "
          f"A2 변형 {len(m2['variants'])}종 · note 관계 {len(rel)}건 · 그룹 예시 {len(samples)}건")

    metrics = {
        "phase": 1,
        "question": "어떤 feature 가 사람들이 비슷하다고 평가한 향수를 가장 잘 찾는가",
        "keep_criteria": {"dev700_ndcg_gt": BASE_NDCG, "global_top10_hit_ge": BASE_TOP10},
        "results": {
            "A8": {"verdict": "DROP", "best_ndcg": max(v["ndcg"] for v in m8["a8_variants"]),
                   "best_top10": max(v["top10_hit"] for v in m8["a8_variants"]),
                   "variants": len(m8["a8_variants"])},
            "A7": {"verdict": m7["verdict"],
                   "best_ndcg": max(r["ndcg"] for r in m7["curve"][1:]),
                   "best_top10": max(r["top10_hit"] for r in m7["curve"][1:]),
                   "points": len(m7["curve"]) - 1},
            "A2": {"verdict": "DROP",
                   "best_ndcg": max(v["ndcg"] for v in m2["variants"]
                                    if v["variant"] != "baseline_strength"),
                   "best_top10": max(v["top10_hit"] for v in m2["variants"]
                                     if v["variant"] != "baseline_strength"),
                   "variants": len(m2["variants"]) - 1},
        },
        "phase2_input": ("baseline 유사도 하나. 0.5 x accord 코사인(raw strength, L2) + "
                         "0.5 x note IDF 가중 Jaccard. 신규 후보 0개"),
        "d21_reconfirmed": ("D21 은 가중치 스윕과 동의어 통일만 봤고 이번에는 공동출현 임베딩 · "
                            "세밀도 집계 · 강도 표현 세 방향을 봤다. 셋 다 음의 결과다"),
        "holdout": "Holdout 300 미사용. 채택된 변경이 없으므로 지금 쓸 이유가 없다",
    }
    with open(os.path.join(PHASE1, "metrics.json"), "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=1)
        f.write("\n")
    manifest = {
        "experiment_id": "phase1", "phase": 1, "status": "NEW",
        "hypothesis": "해당 없음 — Phase 요약",
        "user_meaning": "마음에 드는 향수 주변에 실제로 비슷한 향수가 있는가",
        "changed_variable": "없음 (A8/A7/A2 결과 종합)",
        "population": ["dev700", "global1000"],
        "primary_metrics": ["dev700 ndcg@10", "global1000 top10_hit"],
        "baseline_reference": {"dev700_ndcg": BASE_NDCG, "global_top10_hit": BASE_TOP10,
                               "control_note_cosine_top10": CONTROL_TOP10},
        "sub_experiments": ["P1_A8_NOTE_COOCCURRENCE", "P1_A7_NOTE_GRANULARITY",
                            "P1_A2_ACCORD_RANK"],
        "recommendation": "Phase 2 를 baseline 유사도 하나로 진행한다",
    }
    with open(os.path.join(PHASE1, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)
        f.write("\n")

    sections = [section_overview(m8, m7, m2), section_a8(m8, rel),
                section_a7(m7, samples), section_a2(m2), section_next(m7)]
    print(f"고유 절 {len(sections)}개를 렌더러에 넘깁니다")
    path, nsec, nkpi, nchk, nfig = rr.render(
        PHASE1, os.path.abspath(os.path.join(PHASE1, "summary.html")),
        title="Phase 1 — 향 유사성 정의 실험 결과",
        extra_sections=sections, auto_data_figures=False)
    size = os.path.getsize(path) / 1024
    print(f"\n  -> {os.path.relpath(path)}  ({size:.0f} KB)")
    print(f"     섹션 {nsec}개 · KPI {nkpi}개 · 재현 검증 {nchk}개")


if __name__ == "__main__":
    main()

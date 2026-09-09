# -*- coding: utf-8 -*-
"""실험 보고서 공통 렌더러 (Phase 0-9).

    PYTHONIOENCODING=utf-8 PYTHONUTF8=1 \
    venv/Scripts/python.exe experiments/_report_template/render_report.py experiments/phase0

**왜 이 파일이 있는가.** 실험이 30개 넘게 생긴다. 실험마다 HTML 을 직접 쓰면 HTML 작업이
실험보다 커진다. 그래서 실험 코드는 `manifest.json` / `metrics.json` / `cases.csv` 같은
데이터만 남기고, 보고서는 이 렌더러 하나가 만든다 (experiments/README.md 의 규약).

**렌더러가 계산하는 것과 계산하지 않는 것.**
- 계산하지 않는다: 지표 값. 전부 실험 코드가 남긴 JSON/CSV 를 그대로 읽어 표시한다.
- 계산한다: 기준값 대비 delta, 게이트 판정(PASS/REVIEW/FAIL), 재현 검증 합계, 그림.
  즉 이 파일이 만들어내는 새 숫자는 "차이"와 "판정"뿐이다.

읽는 파일 (없으면 건너뛴다)
    <experiment_dir>/manifest.json      ① 실험 요약
    <experiment_dir>/metrics.json       ② KPI 카드 · ③ 시각화
    <experiment_dir>/**/*.json          ⑥ 하위 산출물 섹션 (재귀) · 재현 검증 · 그림
    <experiment_dir>/**/*cases*.csv     ④ rescue / regression 사례표
    <experiment_dir>/**/*exception*.csv  같이 사례표로 본다 (반례 목록)
    <experiment_dir>/**/coordinates*.csv ③ 지도 그림 (2개 이상이면 나란히 비교)

섹션 순서 (요청 규약)
    ① 실험 요약  ② KPI 카드  ③ 지표 시각화  ④ 사례표  ⑤ 팀 검토
    그 뒤에 ⑥ 하위 산출물 JSON, ⑦ 지표 용어, ⑧ 파일 목록.

KPI 를 실험이 직접 고르려면 manifest 에 적는다 (없으면 지표 이름으로 자동 선택).

    "primary_metrics": [
      {"path": "korea200.layout_seeds.trust@10",
       "label": "trustworthiness@10 (Korea 200)",
       "baseline": 0.9213,                      # 숫자 또는 baseline_reference 의 키
       "gate": {"min": 0.90, "label": "Gate B"},
       "direction": "up"}                       # up | down (down = 작을수록 좋다)
    ],
    "guardrail_metrics": [ ... 같은 형태 ... ]

Gate A 처럼 "기준값 + 0.05 이하" 형태는 gate 를 이렇게 적는다.

    "gate": {"max_baseline_delta": 0.05, "label": "Gate A"}

**그림.** 외부 CDN·웹폰트·스크립트를 쓰지 않는다. matplotlib 그림은 base64 PNG 로
HTML 안에 넣고, KPI 카드의 범위 막대는 인라인 SVG 로 직접 그린다. 파일 하나만 열면 전부 보인다.
matplotlib 그림은 밝은 팔레트 하나로만 만들고, HTML 쪽에서 밝은 그림판(.plate) 위에 얹는다.

**다른 실험 코드에서 쓰는 방법.** 지도 비교 그림은 이 모듈의 헬퍼를 import 해서 쓴다.

    from render_report import map_compare_figure, FAMILY_COLORS

정렬은 회전·반사만 한다. 스케일 계수는 추정하지 않는다
(src/map/compare_korea_map_population.py 의 align() 과 같은 방식).
지표는 정렬 전 좌표로 계산한다 — 정렬은 눈으로 비교하기 위한 것이다.

**실험에 고유한 시각화가 필요할 때.** 실험 코드가 HTML 문자열을 쓰지 않고도 절을 더할 수
있도록 조립 훅과 조각 만들기 함수를 둔다. 절 번호(①②③…)는 조립 단계에서 붙으므로
절을 끼워 넣어도 번호가 어긋나지 않는다.

    from render_report import (render, make_section, figure_block, h_table, h_heading,
                               h_note, h_callout, h_details, h_legend,
                               fig_bar_colored, fig_grouped_bar, fig_hist, fig_heatmap,
                               fig_series_by_seed, map_axis_figure)

    sec = make_section("fam", "계열 매핑", "accord 92종을 9계열로",
                       h_heading("검토 대상") + h_table(...) + figure_block(img, "..."),
                       lead="...", after="s2")          # s2(② KPI) 뒤에 끼운다
    render("experiments/phase0", "experiments/phase0/summary.html",
           extra_sections=[sec], auto_data_figures=False)

`after` 가 없는 절은 맨 끝에 붙는다. `auto_data_figures=False` 면 ③ 시각화에서 자동
범주 막대·좌표 산점도를 만들지 않는다 (실험이 직접 고른 그림만 쓸 때).
"""
import argparse
import base64
import csv
import datetime as _dt
import html
import io
import json
import os
import re
import sys

import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.linalg import orthogonal_procrustes

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

RENDERER_VERSION = "1.1"      # 1.1 — 절 조립 훅(extra_sections)·실험용 그림 만들기 함수 추가
TEMPLATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "template.html")

# ── 계열 색 ────────────────────────────────────────────────────────────────
# 키 순서는 src/map/experiment_phase0_family_mapping.py 의 FAMILY_DEF 를 따른다.
# 모든 실험 HTML 이 같은 색을 쓰도록 이 상수가 단일 출처다 (PNG 그림과 HTML 범례 모두).
FAMILY_COLORS = {
    "CITRUS":   "#d4b021",
    "FRUITY":   "#c1462f",
    "FLORAL":   "#b4506b",
    "GREEN":    "#4c7a4a",
    "AQUATIC":  "#2c7f8c",
    "WOODY":    "#6b5138",
    "AMBER":    "#c07d1a",
    "GOURMAND": "#8265ab",
    "MUSK":     "#6f7f96",
}
FAMILY_KO = {
    "CITRUS": "시트러스", "FRUITY": "프루티", "FLORAL": "플로럴",
    "GREEN": "그린·아로마틱", "AQUATIC": "아쿠아틱", "WOODY": "우디",
    "AMBER": "앰버·스파이시", "GOURMAND": "구르망", "MUSK": "머스크·파우더리",
}
FAMILY_ORDER = list(FAMILY_COLORS)
UNMAPPED_COLOR = "#a8b3b2"
# 계열이 아닌 범주(클러스터 c0.., setA 4대 그룹 등)에 돌려 쓰는 중립색
NEUTRAL_CYCLE = ["#0e3644", "#2c7f8c", "#a8761f", "#9d4238", "#2f6b4f",
                 "#8265ab", "#6f7f96", "#c1462f", "#4c7a4a", "#d4b021"]

# ── 그림 팔레트 (docs/scent_map_explainer.html 의 밝은 테마 값) ─────────────
FIG_BG = "#fbfcfc"
FIG_INK = "#14262b"
FIG_INK2 = "#33484e"
FIG_MUTED = "#5d757c"
FIG_HAIR = "#c6d2d1"
FIG_DEEP = "#0e3644"
FIG_SHOAL = "#2c7f8c"
FIG_LAND = "#a8761f"
FIG_WARN = "#9d4238"

# ── 지표 용어 ──────────────────────────────────────────────────────────────
# desc 는 팀원이 처음 봐도 읽히는 한 줄이어야 한다. kind="metric" 만 KPI 카드가 된다.
# aliases 는 JSON 키 표기 흔들림을 흡수한다 (trust@10 / trust10 / trustworthiness@10).
GLOSSARY = {
    "trustworthiness@10": {
        "kind": "metric", "aliases": ["trust@10", "trust10", "trustworthiness10"],
        "desc": "지도에서 옆에 있는데 원래는 멀었던 향수에 벌점을 주는 값. 1에 가까울수록 거짓 이웃이 적다"},
    "trustworthiness@20": {
        "kind": "metric", "aliases": ["trust@20", "trust20", "trustworthiness20"],
        "desc": "같은 벌점을 이웃 20개까지 넓혀 본 값. 넓게 봐도 거짓 이웃이 적은지 확인한다"},
    "trustworthiness": {
        "kind": "metric", "aliases": ["trust"],
        "desc": "지도에서 옆에 있는데 원래는 멀었던 향수에 벌점을 주는 값. 1에 가까울수록 거짓 이웃이 적다"},
    "continuity@10": {
        "kind": "metric", "aliases": ["cont@10", "continuity10"],
        "desc": "원래 가까웠는데 지도에서 멀어진 향수에 벌점을 주는 값. 놓친 이웃을 본다"},
    "continuity": {
        "kind": "metric", "aliases": ["continuity"],
        "desc": "원래 가까웠는데 지도에서 멀어진 향수에 벌점을 주는 값. 놓친 이웃을 본다"},
    "kNN overlap@10": {
        "kind": "metric", "aliases": ["knn_overlap@10", "knnoverlap10", "overlap10"],
        "desc": "원공간 이웃 10개와 지도 이웃 10개가 몇 개 겹치는가. 1이면 전부 같다"},
    "kNN overlap": {
        "kind": "metric", "aliases": ["knn_overlap", "knnoverlap"],
        "desc": "원공간 이웃과 지도 이웃이 얼마나 겹치는가. 유사도 정의를 바꾼 실험의 자기 채점에는 쓰지 않는다"},
    "ndcg@10": {
        "kind": "metric", "aliases": ["ndcg10", "ndcg"],
        "desc": "추천 상위 10개가 정답을 얼마나 앞쪽에 놓았는가. 순위를 반영한 점수로 1이 최대"},
    "recall": {
        "kind": "metric", "aliases": ["recall", "recall@10"],
        "desc": "정답 중 상위 10개 안에 들어온 비율"},
    "hit_rate": {
        "kind": "metric", "aliases": ["hit_rate", "hitrate"],
        "desc": "상위 10개 안에 정답이 하나라도 있는 질의의 비율"},
    "mrr": {
        "kind": "metric", "aliases": ["mrr"],
        "desc": "첫 정답이 몇 등에 나오는지의 역수 평균. 1등이면 1"},
    "trusted-edge 근접도": {
        "kind": "metric", "aliases": ["reminds_pct", "remindspct", "reminds", "trusted_edge_proximity"],
        "desc": "사람이 '닮았다'고 투표한 쌍이 지도에서 얼마나 가까운가. 전체 거리 대비 비율이라 작을수록 가깝다"},
    "신뢰 파트너 top10 포함률": {
        "kind": "metric", "aliases": ["top10_hit", "top10hit"],
        "desc": "사람이 닮았다고 한 상대가 유사도 상위 10위 안에 들어온 비율"},
    "cohesion_ratio": {
        "kind": "metric", "aliases": ["cohesion_ratio", "cohesionratio"],
        "desc": "같은 계열이 실제로 뭉친 정도를 무작위 배치 기대값으로 나눈 값. 1이면 우연과 같다"},
    "observed_cohesion": {
        "kind": "count", "aliases": ["observed_cohesion"],
        "desc": "같은 계열끼리 이웃인 비율의 실측값. 절대값끼리 비교하지 않고 무작위 기대값으로 나눠 쓴다"},
    "random_expected_cohesion": {
        "kind": "count", "aliases": ["random_expected_cohesion"],
        "desc": "계열 라벨을 무작위로 섞었을 때 나오는 같은 값. 비교의 분모"},
    "silhouette": {
        "kind": "metric", "aliases": ["silhouette"],
        "desc": "군집이 서로 떨어져 있는 정도. 0.1 미만이면 자연 군집으로 주장하기 어렵다"},
    "coverage": {
        "kind": "metric", "aliases": ["coverage"],
        "desc": "라벨을 붙일 수 있었던 향수의 비율"},
    "top1": {
        "kind": "metric", "aliases": ["top1"],
        "desc": "Family Score 1위 계열의 점수. 향수 하나의 점수 합을 1로 맞춘 뒤의 값"},
    "margin": {
        "kind": "metric", "aliases": ["margin"],
        "desc": "1위 계열과 2위 계열의 점수 차. 작으면 어느 계열이라 부르기 어렵다"},
    "pearson": {
        "kind": "metric", "aliases": ["pearson", "accord_note_pearson"],
        "desc": "두 값이 직선 관계인 정도. 0이면 무관, 1이면 완전히 같은 방향"},
    "spearman": {
        "kind": "metric", "aliases": ["spearman", "accord_note_spearman", "rho",
                                      "x_rho", "y_rho"],
        "desc": "순위끼리의 상관. 값의 크기보다 순서가 같은지를 본다"},
    "zero_pair_share": {
        "kind": "count", "aliases": ["zero_pair_share"],
        "desc": "유사도가 0 으로 나온 쌍의 비율. 크면 그 채널이 많은 쌍을 구분하지 못한다"},
    "rotation_deg": {
        "kind": "count", "aliases": ["rotation_deg"],
        "desc": "좌표계를 돌린 각도. 회전은 점 사이 거리를 바꾸지 않는다"},
    "n": {"kind": "count", "aliases": ["n"], "desc": "모집단 크기"},
    "trusted_edges": {
        "kind": "count", "aliases": ["trusted_edges", "trusted_edge", "n_edges"],
        "desc": "사람이 '닮았다'고 투표해 채점 근거로 쓰는 향수 쌍의 수"},
    "trusted_nodes": {
        "kind": "count", "aliases": ["trusted_nodes"],
        "desc": "신뢰 간선을 하나라도 가진 향수의 수"},
    "cross_family_trusted_edges": {
        "kind": "count", "aliases": ["cross_family_trusted_edges", "cross_family"],
        "desc": "서로 다른 계열을 잇는 신뢰 간선. 계열을 넘는 유사성이라 지도에서 가장 어려운 쌍이다"},
}
# 짧은 별칭(3자 이하)은 경로의 마지막 토큰이 정확히 같을 때만 인정한다.
_ALIAS_MIN_SUBSTR = 4
# 이름이 이 토큰으로 끝나면 개수·표본 수로 본다. 지표 이름이 걸려도 KPI 카드로 만들지 않는다
# (예: global1000.top10_hit_queries 는 비율이 아니라 질의 467개).
COUNT_LEAF_TOKENS = {"queries", "query", "count", "counts", "n", "edges", "nodes",
                     "pairs", "size", "sizes", "labeled", "unlabeled", "num", "total"}

# ── 캠페인 고정 기준값 · 게이트 ─────────────────────────────────────────────
# 출처: experiments/README.md "기준값 (Phase 0 에서 실측 고정)" 표. 실측값이며 렌더러가 만든 수가 아니다.
# 실험 manifest 의 baseline_reference 가 있으면 그것을 먼저 쓰고, 없을 때만 이 표로 떨어진다.
CAMPAIGN_BASELINE = {
    ("korea200", "trustworthiness@10", "mean"): 0.9213,
    ("korea200", "trustworthiness@10", "seed42"): 0.9191,
    ("korea200", "kNN overlap@10", "seed42"): 0.4875,
    ("korea200", "trusted-edge 근접도", "mean"): 0.1672,
    ("global1000", "trustworthiness@10", "seed42"): 0.9387,
    ("global1000", "kNN overlap@10", "seed42"): 0.3888,
    ("global1000", "신뢰 파트너 top10 포함률", None): 0.4464,
    ("dev700", "ndcg@10", None): 0.2709,
}
# Gate B — README "게이트 판정 규칙". 모집단은 manifest 에 명시해야 한다.
CAMPAIGN_GATES = {
    "trustworthiness@10": {"label": "Gate B", "min": 0.90,
                           "rule": "trustworthiness@10 >= 0.90"},
}
# 최소값이 게이트에서 이 폭 안이면 자동 판정 금지 → REVIEW (README)
GATE_MARGIN = 0.01
POPULATIONS = ("korea200", "global1000", "dev700")
BLOCK_MARKERS = {"mean", "min", "max"}      # 이 셋을 가진 dict 를 '지표 블록' 으로 본다
STATISH = {"mean", "std", "min", "max", "median", "seed42", "p10", "p50", "p90",
           "q1", "q3", "count", "sum", "var"}

ALIGN_CAPTION = "시각 비교를 위해 회전/반사 정렬했습니다. 스케일은 변경하지 않았습니다."
MAX_FIGURES = 12            # 그림 총량 상한 (파일 크기·읽는 사람 모두를 위해)
MAX_KPI = 16
MAX_TABLE_ROWS = 25         # 사례표·행 목록 표시 상한
MAX_CSV_TABLE_COLS = 12
PREFERRED_CATEGORY_LEAVES = ("family_count", "per_family_cohesion", "sizes",
                             "corpus_accord_prevalence_top10", "family_count_ko")


# ══════════════════════════════════════════════════════════════════════════
# 작은 도구
# ══════════════════════════════════════════════════════════════════════════
def esc(x):
    return html.escape("" if x is None else str(x), quote=True)


def norm(s):
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def tok(s):
    """이름을 토큰 집합으로. 'korea200_trust10_seed_mean' -> {korea,200,trust,10,seed,mean}

    끝의 복수형 s 를 떼어 'seeds' 와 'seed' 가 같은 토큰이 되게 한다 (양쪽 모두에 적용).
    """
    out = set()
    for p in re.findall(r"[a-z]+|\d+", str(s).lower()):
        out.add(p[:-1] if len(p) > 3 and p.endswith("s") else p)
    return out


# 매칭에 쓰는 이름표. 표시용 이름에 한글이 섞이면 알파벳만 남아 너무 짧아지므로
# (예: "신뢰 파트너 top10 포함률" -> "top10") 표시용 이름은 매칭에 쓰지 않고 aliases 만 쓴다.
_ALIASES = {
    key: sorted({norm(a) for a in
                 (list(spec.get("aliases", []))
                  + ([key] if re.fullmatch(r"[A-Za-z0-9@_. \-]+", key) else []))} - {""},
                key=len, reverse=True)
    for key, spec in GLOSSARY.items()
}


def is_scalar(v):
    return v is None or isinstance(v, (str, int, float, bool))


def is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and v == v


def fmt_num(v, digits=4):
    """표 안의 숫자. 정수는 자릿점, 실수는 소수 4자리까지, 극단값은 지수 표기."""
    if v is None:
        return "—"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return f"{v:,}"
    if isinstance(v, float):
        if v != v:
            return "NaN"
        a = abs(v)
        if a != 0 and (a < 1e-4 or a >= 1e7):
            return f"{v:.3e}"
        if float(v).is_integer():
            return f"{int(v):,}"
        return f"{v:.{digits}f}".rstrip("0").rstrip(".")
    return str(v)


def fmt_kpi(v, digits=4):
    """KPI 대표값. 자리수를 흔들지 않는다."""
    if not is_num(v):
        return esc(v)
    if abs(v) >= 1000 or float(v).is_integer():
        return f"{v:,.0f}"
    return f"{v:.{digits}f}"


def fmt_delta(d, digits=4):
    if d is None or not is_num(d):
        return "—"
    return f"{d:+.{digits}f}"


def cell(v):
    if isinstance(v, (list, tuple)):
        return esc(", ".join(fmt_num(x) if is_num(x) else str(x) for x in v))
    if v is None:
        return "—"
    if isinstance(v, bool):
        return "true" if v else "false"
    return esc(fmt_num(v)) if is_num(v) else esc(v)


def family_color(label):
    """계열 이름이면 고정색, 아니면 None."""
    k = str(label).strip().upper()
    if k in FAMILY_COLORS:
        return FAMILY_COLORS[k]
    if k == "UNMAPPED":
        return UNMAPPED_COLOR
    for eng, ko in FAMILY_KO.items():          # 한글 라벨도 같은 색으로
        if str(label).strip() == ko:
            return FAMILY_COLORS[eng]
    return None


def family_label(label):
    k = str(label).strip().upper()
    if k in FAMILY_KO:
        return f"{FAMILY_KO[k]} ({k})"
    return str(label)


def read_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def read_csv_rows(path, limit=None):
    """(헤더, 행들, 전체 행 수). BOM 이 붙은 CSV 가 있으므로 utf-8-sig 로 읽는다."""
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        try:
            header = next(reader)
        except StopIteration:
            return [], [], 0
        rows, total = [], 0
        for r in reader:
            total += 1
            if limit is None or len(rows) < limit:
                rows.append(r)
        return header, rows, total


def walk_json(node, path=""):
    """(경로, 값) 을 전부 훑는다. 리스트는 [i] 로 붙인다."""
    yield path, node
    if isinstance(node, dict):
        for k, v in node.items():
            yield from walk_json(v, f"{path}.{k}" if path else str(k))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from walk_json(v, f"{path}[{i}]")


# ══════════════════════════════════════════════════════════════════════════
# 그림 (matplotlib → base64 PNG)
# ══════════════════════════════════════════════════════════════════════════
_RC_DONE = False


def _rc():
    """한글 라벨이 깨지지 않게 Malgun Gothic 을 쓰고 마이너스 기호를 ASCII 로 둔다."""
    global _RC_DONE
    if _RC_DONE:
        return
    plt.rcParams.update({
        "font.family": "Malgun Gothic",
        "font.sans-serif": ["Malgun Gothic", "Gulim", "DejaVu Sans"],
        "axes.unicode_minus": False,
        "figure.facecolor": FIG_BG, "axes.facecolor": FIG_BG,
        "savefig.facecolor": FIG_BG,
        "text.color": FIG_INK, "axes.labelcolor": FIG_INK2,
        "xtick.color": FIG_MUTED, "ytick.color": FIG_MUTED,
        "axes.edgecolor": FIG_HAIR, "grid.color": FIG_HAIR,
        "axes.titlesize": 11, "axes.labelsize": 9.5,
        "xtick.labelsize": 8.5, "ytick.labelsize": 8.5,
        "figure.dpi": 120, "savefig.dpi": 120,
    })
    _RC_DONE = True


def fig_to_img(fig, alt):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", pad_inches=0.08)
    plt.close(fig)
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f'<img src="data:image/png;base64,{b64}" alt="{esc(alt)}">'


def figure_block(img_html, caption, source=None, must=None):
    src = f'<span class="src">{esc(source)}</span>' if source else ""
    m = f'<span class="must">{esc(must)}</span> ' if must else ""
    return ('<figure>'
            f'<div class="plate">{img_html}</div>'
            f'<figcaption>{m}{esc(caption) if caption else ""}{src}</figcaption>'
            '</figure>')


def _kpi_ylabel(c):
    return f'{c["metric"] or c["label"]}\n{c["population"] or ""}'.strip()


def fig_kpi_vs_baseline(cards):
    """현재값과 기준값을 KPI 별로 나란히 놓은 막대. 기준값이 있는 KPI 만 들어간다.

    비율 지표와 개수 지표가 섞이면 축 하나로는 읽을 수 없으므로 1 이하와 1 초과를
    다른 칸으로 나눠 그린다.
    """
    use = [c for c in cards if c["baseline"] is not None and is_num(c["value"])]
    if not use:
        return None
    _rc()
    groups = [g for g in ([c for c in use if max(abs(c["value"]), abs(c["baseline"])) <= 1.5],
                          [c for c in use if max(abs(c["value"]), abs(c["baseline"])) > 1.5]) if g]
    fig, axes = plt.subplots(len(groups), 1, squeeze=False,
                             gridspec_kw={"height_ratios": [len(g) for g in groups]},
                             figsize=(7.4, max(2.0, 0.52 * len(use) + 0.9 * len(groups))))
    axes = [a[0] for a in axes]
    for ax, grp in zip(axes, groups):
        y = np.arange(len(grp))[::-1]
        h = 0.34
        cur = [c["value"] for c in grp]
        base = [c["baseline"] for c in grp]
        ax.barh(y + h / 2, cur, height=h, color=FIG_SHOAL, label="이번 실험", zorder=3)
        ax.barh(y - h / 2, base, height=h, color=FIG_HAIR, label="기준값", zorder=3)
        for yy, v in zip(y + h / 2, cur):
            ax.text(v, yy, " " + fmt_num(v), va="center", fontsize=8, color=FIG_INK)
        for yy, v in zip(y - h / 2, base):
            ax.text(v, yy, " " + fmt_num(v), va="center", fontsize=8, color=FIG_MUTED)
        ax.set_yticks(y)
        ax.set_yticklabels([_kpi_ylabel(c) for c in grp], fontsize=8.5)
        ax.set_ylim(-.8, len(grp) - .2)
        ax.set_xlim(0, max(max(cur), max(base)) * 1.24)
        ax.xaxis.grid(True, linewidth=.6, zorder=0)
        ax.set_axisbelow(True)
        for s in ("top", "right", "left"):
            ax.spines[s].set_visible(False)
    axes[0].legend(loc="lower right", frameon=False, fontsize=8.5)
    axes[-1].set_xlabel("지표 값")
    fig.subplots_adjust(hspace=.35)
    return fig_to_img(fig, "KPI 현재값과 기준값 비교 막대그래프")


def fig_seed_spread(cards):
    """시드 여러 개를 돌린 KPI 의 최소~최대 폭. 게이트선을 같이 그려 판정 근거를 보인다."""
    use = [c for c in cards if c["lo"] is not None and c["hi"] is not None]
    if not use:
        return None
    _rc()
    n = len(use)
    fig, axes = plt.subplots(n, 1, figsize=(7.4, 0.78 * n + 0.7))
    if n == 1:
        axes = [axes]
    for ax, c in zip(axes, use):
        lo, hi, mean = c["lo"], c["hi"], c["value"]
        gate = c["gate"].get("min") if c["gate"] else None
        if gate is None and c["gate"]:
            gate = c["gate"].get("max")
        pts = [lo, hi, mean] + ([gate] if is_num(gate) else [])
        span = max(pts) - min(pts)
        pad = span * 0.35 if span > 0 else max(abs(mean) * 0.02, 0.01)
        single = (hi - lo) < 1e-12          # 시드 하나만 돌린 지표
        if not single:
            ax.hlines(0, lo, hi, color=FIG_SHOAL, linewidth=6, alpha=.35, zorder=2)
            ax.plot([lo, hi], [0, 0], "|", color=FIG_SHOAL, markersize=10, zorder=3)
            ax.text(lo, -.55, fmt_kpi(lo), fontsize=7.5, color=FIG_MUTED, ha="center", va="top")
            ax.text(hi, -.55, fmt_kpi(hi), fontsize=7.5, color=FIG_MUTED, ha="center", va="top")
        else:
            ax.text(mean, -.55, "시드 1개", fontsize=7.5, color=FIG_MUTED, ha="center", va="top")
        ax.plot([mean], [0], "o", color=FIG_DEEP, markersize=7, zorder=4, label="평균")
        if is_num(c["seed42"]):
            ax.plot([c["seed42"]], [0], "d", color=FIG_LAND, markersize=6, zorder=5, label="seed 42")
        if is_num(gate):
            ax.axvline(gate, color=FIG_WARN, linewidth=1.1, linestyle="--", zorder=1)
            ax.text(gate, .62, f" 게이트 {gate:g}", color=FIG_WARN, fontsize=7.5, va="center")
        ax.text(mean, .62, fmt_kpi(mean), fontsize=8, color=FIG_INK, ha="center", va="center")
        ax.set_xlim(min(pts) - pad, max(pts) + pad)
        ax.set_ylim(-1.1, 1.1)
        ax.set_yticks([])
        ax.set_ylabel(_kpi_ylabel(c), rotation=0, ha="right", va="center",
                      fontsize=8.5, labelpad=8)
        for s in ("top", "right", "left"):
            ax.spines[s].set_visible(False)
        ax.tick_params(axis="x", labelsize=7.5)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", bbox_to_anchor=(0.5, 1.0),
               ncol=2, frameon=False, fontsize=8.5)
    axes[-1].set_xlabel("지표 값 (시드 최소~최대)")
    fig.subplots_adjust(hspace=.9, top=.97)
    return fig_to_img(fig, "시드별 지표 범위와 게이트선")


def fig_category_bar(mapping, title, xlabel=None):
    """라벨 → 숫자 막대. 계열 이름이면 계열 색을, 아니면 중립색을 돌려 쓴다."""
    items = [(k, v) for k, v in mapping.items() if is_num(v)]
    if len(items) < 3:
        return None
    _rc()
    fam = all(family_color(k) for k, _ in items)
    if fam:   # 계열은 FAMILY_DEF 순서로 고정한다
        order = {f: i for i, f in enumerate(FAMILY_ORDER)}

        def key(it):
            c = str(it[0]).strip().upper()
            if c in order:
                return order[c]
            for eng, ko in FAMILY_KO.items():
                if str(it[0]).strip() == ko:
                    return order[eng]
            return len(order)
        items.sort(key=key)
        colors = [family_color(k) for k, _ in items]
        labels = [family_label(k).split(" (")[0] for k, _ in items]
    else:
        items.sort(key=lambda it: -it[1])
        colors = [NEUTRAL_CYCLE[i % len(NEUTRAL_CYCLE)] for i in range(len(items))]
        labels = [str(k) for k, _ in items]
    vals = [v for _, v in items]
    fig, ax = plt.subplots(figsize=(7.4, max(2.2, 0.34 * len(items) + 1.1)))
    y = np.arange(len(items))[::-1]
    ax.barh(y, vals, color=colors, height=.62, zorder=3)
    span = max(vals) if max(vals) > 0 else 1
    for yy, v in zip(y, vals):
        ax.text(v + span * .012, yy, fmt_num(v), va="center", fontsize=8, color=FIG_INK2)
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=8.5)
    ax.set_xlim(0, span * 1.16)
    ax.xaxis.grid(True, linewidth=.6, zorder=0)
    ax.set_axisbelow(True)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    if xlabel:
        ax.set_xlabel(xlabel)
    ax.set_title(title, loc="left", color=FIG_INK, pad=8)
    return fig_to_img(fig, f"{title} 막대그래프")


def _bare_axes(ax, sides=("top", "right", "left")):
    for s in sides:
        ax.spines[s].set_visible(False)


def fig_bar_colored(items, title=None, xlabel=None, fmt=None, width=7.4):
    """(라벨, 값, 색) 리스트 → 가로 막대. 색을 실험이 직접 정할 때 쓴다.

    `fig_category_bar` 와 달리 순서와 색을 실험이 통제한다 (근거별 색 구분 등).
    """
    items = [(str(k), v, c) for k, v, c in items if is_num(v)]
    if not items:
        return None
    _rc()
    vals = [v for _, v, _ in items]
    fig, ax = plt.subplots(figsize=(width, max(2.1, 0.34 * len(items) + 1.0)))
    y = np.arange(len(items))[::-1]
    ax.barh(y, vals, color=[c for _, _, c in items], height=.62, zorder=3)
    span = max(vals) if max(vals) > 0 else 1
    for yy, v in zip(y, vals):
        ax.text(v + span * .012, yy, (fmt(v) if fmt else fmt_num(v)),
                va="center", fontsize=8, color=FIG_INK2)
    ax.set_yticks(y)
    ax.set_yticklabels([k for k, _, _ in items], fontsize=8.5)
    ax.set_xlim(0, span * 1.18)
    ax.xaxis.grid(True, linewidth=.6, zorder=0)
    ax.set_axisbelow(True)
    _bare_axes(ax)
    if xlabel:
        ax.set_xlabel(xlabel)
    if title:
        ax.set_title(title, loc="left", color=FIG_INK, pad=8)
    return fig_to_img(fig, f"{title or '값'} 막대그래프")


def fig_grouped_bar(categories, series, title=None, xlabel=None, fmt=None,
                    vlines=None, width=7.4, row_h=0.24):
    """묶음 막대. categories 는 y축 라벨, series 는 (계열명, 값들, 색) 리스트.

    같은 항목을 조건 2~4개로 비교할 때 쓴다 (규칙 후보별 라벨률, FS1 vs FS2 등).
    vlines 는 [(값, 라벨)] — 전체 평균선 같은 기준선을 그린다.
    """
    series = [(n, list(v), c) for n, v, c in series]
    if not categories or not series:
        return None
    _rc()
    k, n = len(series), len(categories)
    fig, ax = plt.subplots(figsize=(width, max(2.4, row_h * k * n + 1.2)))
    base = np.arange(n)[::-1] * 1.0
    h = 0.82 / k
    allv = [v for _, vs, _ in series for v in vs if is_num(v)]
    span = max(allv) if allv and max(allv) > 0 else 1
    for j, (name, vs, c) in enumerate(series):
        off = (k - 1) / 2.0 * h - j * h
        ax.barh(base + off, [v if is_num(v) else 0 for v in vs], height=h * .9,
                color=c, label=name, zorder=3)
        for yy, v in zip(base + off, vs):
            if is_num(v):
                ax.text(v + span * .012, yy, (fmt(v) if fmt else fmt_num(v)),
                        va="center", fontsize=7.2, color=FIG_INK2)
    for xv, lab in (vlines or []):
        ax.axvline(xv, color=FIG_WARN, linewidth=1.1, linestyle="--", zorder=2)
        ax.text(xv, base.max() + .55, f" {lab}", color=FIG_WARN, fontsize=7.5, va="center")
    ax.set_yticks(base)
    ax.set_yticklabels([str(c) for c in categories], fontsize=8.5)
    ax.set_ylim(-.7, base.max() + .7)
    ax.set_xlim(0, span * 1.2)
    ax.xaxis.grid(True, linewidth=.6, zorder=0)
    ax.set_axisbelow(True)
    _bare_axes(ax)
    if xlabel:
        ax.set_xlabel(xlabel)
    if title:
        ax.set_title(title, loc="left", color=FIG_INK, pad=8)
    # 범례는 그림판 밖 아래에 둔다 — 막대 위에 얹으면 값을 가린다
    hs, ls = ax.get_legend_handles_labels()
    fig.legend(hs, ls, loc="upper center", bbox_to_anchor=(0.5, 0.0),
               ncol=min(k, 3), frameon=False, fontsize=8)
    return fig_to_img(fig, f"{title or '값'} 묶음 막대그래프")


def fig_hist(panels, bins=20, xlabel=None, vlines=None, shade=None, title=None,
             color=None, width=4.4, height=3.5):
    """히스토그램을 나란히. panels 는 (제목, 값 리스트, 덧말) 리스트.

    x 범위와 y 범위를 패널끼리 맞춘다 — 모집단을 나란히 놓고 모양을 비교하려면
    축이 같아야 한다. vlines 는 [(값, 라벨)], shade 는 (하한, 상한, 라벨).
    """
    panels = [(t, np.asarray([v for v in vals if is_num(v)], dtype=float), note)
              for t, vals, note in panels]
    panels = [p for p in panels if p[1].size]
    if not panels:
        return None
    _rc()
    lo = min(p[1].min() for p in panels)
    hi = max(p[1].max() for p in panels)
    edges = np.linspace(lo, hi, bins + 1)
    counts = [np.histogram(p[1], bins=edges)[0] / p[1].size for p in panels]
    ymax = max(c.max() for c in counts) * 1.28
    n = len(panels)
    fig, axes = plt.subplots(1, n, figsize=(width * n, height), squeeze=False)
    axes = axes[0]
    for ax, (t, vals, note), cnt in zip(axes, panels, counts):
        if shade:
            ax.axvspan(shade[0], shade[1], color=FIG_WARN, alpha=.10, zorder=1)
            # 띠 안에 세로로 이름을 적는다. 띠가 좁으면 글자가 막대와 겹치므로 생략한다
            # (그 경우 설명은 vlines 라벨과 그림 설명이 맡는다).
            if shade[2] and (shade[1] - shade[0]) >= (hi - lo) * .25:
                ax.text((shade[0] + shade[1]) / 2, ymax * .55, shade[2],
                        rotation=90, ha="center", va="center", fontsize=7.5,
                        color=FIG_WARN, zorder=5)
        ax.bar(edges[:-1], cnt, width=np.diff(edges), align="edge",
               color=color or FIG_SHOAL, zorder=3)
        med = float(np.median(vals))
        ax.axvline(med, color=FIG_DEEP, linewidth=1.2, zorder=4)
        ax.text(med, ymax * .97, f" 중앙 {med:.4f}", fontsize=7.5, color=FIG_DEEP,
                va="top", ha="left")
        for xv, lab in (vlines or []):
            ax.axvline(xv, color=FIG_WARN, linewidth=1.1, linestyle="--", zorder=4)
            ax.text(xv, ymax * .82, f" {lab}", fontsize=7.5, color=FIG_WARN,
                    va="top", ha="left")
        sub = f"{t}  (n={vals.size:,})" + (f"\n{note}" if note else "")
        ax.set_title(sub, fontsize=9.5, loc="left", color=FIG_INK)
        ax.set_xlim(lo, hi)
        ax.set_ylim(0, ymax)
        ax.yaxis.grid(True, linewidth=.6, zorder=0)
        ax.set_axisbelow(True)
        _bare_axes(ax, ("top", "right"))
        if xlabel:
            ax.set_xlabel(xlabel)
    axes[0].set_ylabel("향수 비율")
    if title:
        fig.suptitle(title, x=0.01, ha="left", fontsize=11, color=FIG_INK)
    fig.subplots_adjust(wspace=.22, top=.84 if title else .9)
    return fig_to_img(fig, f"{title or xlabel or '분포'} 히스토그램")


def fig_heatmap(row_labels, col_labels, matrix, title=None, xlabel=None, ylabel=None,
                cell=1.0):
    """행렬 히트맵. 라벨이 어디로 옮겨갔는지(전이) 같은 표를 그림으로 본다.

    0 인 칸은 비워 둔다 — 실제로 일어난 전이만 눈에 남게 한다.
    """
    m = np.asarray(matrix, dtype=float)
    if m.size == 0 or m.max() <= 0:
        return None
    _rc()
    fig, ax = plt.subplots(figsize=(max(4.0, cell * len(col_labels) + 2.2),
                                    max(3.0, cell * len(row_labels) + 1.6)))
    masked = np.ma.masked_where(m <= 0, m)
    cmap = matplotlib.colors.LinearSegmentedColormap.from_list(
        "shoal", ["#e4eae9", FIG_SHOAL, FIG_DEEP])
    cmap.set_bad(FIG_BG)
    im = ax.imshow(masked, cmap=cmap, aspect="auto", vmin=0, vmax=m.max())
    for i in range(m.shape[0]):
        for j in range(m.shape[1]):
            if m[i, j] > 0:
                ax.text(j, i, f"{m[i, j]:g}", ha="center", va="center", fontsize=7.5,
                        color=(FIG_BG if m[i, j] > m.max() * .55 else FIG_INK))
    ax.set_xticks(range(len(col_labels)))
    ax.set_xticklabels(col_labels, fontsize=8, rotation=40, ha="right")
    ax.set_yticks(range(len(row_labels)))
    ax.set_yticklabels(row_labels, fontsize=8)
    ax.set_xticks(np.arange(-.5, len(col_labels), 1), minor=True)
    ax.set_yticks(np.arange(-.5, len(row_labels), 1), minor=True)
    ax.grid(which="minor", color=FIG_BG, linewidth=1.5)
    ax.tick_params(which="minor", length=0)
    for s in ax.spines.values():
        s.set_color(FIG_HAIR)
    if xlabel:
        ax.set_xlabel(xlabel)
    if ylabel:
        ax.set_ylabel(ylabel)
    if title:
        ax.set_title(title, loc="left", color=FIG_INK, pad=8)
    fig.colorbar(im, ax=ax, fraction=.035, pad=.02).ax.tick_params(labelsize=7.5)
    return fig_to_img(fig, f"{title or '전이'} 히트맵")


def fig_series_by_seed(seeds, series, title=None, xlabel="시드", ylabel=None,
                       width=7.0, height=3.4):
    """시드별 값을 선으로 잇고 평균±표준편차 띠를 얹는다.

    "시드를 바꾸면 이 값이 흔들린다" 를 한 그림으로 보인다. 평균·표준편차는 이 함수가
    입력 값에서 계산하는 요약이며 새 측정이 아니다.
    """
    series = [(n, np.asarray([v for v in vs], dtype=float), c) for n, vs, c in series]
    series = [s for s in series if s[1].size == len(seeds)]
    if not series:
        return None
    _rc()
    fig, ax = plt.subplots(figsize=(width, height))
    x = np.arange(len(seeds))
    for name, vs, c in series:
        mu, sd = float(vs.mean()), float(vs.std())
        ax.fill_between([-.35, len(seeds) - .65], mu - sd, mu + sd, color=c,
                        alpha=.14, zorder=1)
        ax.axhline(mu, color=c, linewidth=1, linestyle="--", zorder=2)
        ax.plot(x, vs, "-o", color=c, markersize=5.5, linewidth=1.4, zorder=4,
                label=f"{name}  평균 {mu:.3f} ± {sd:.3f}")
        for xi, v in zip(x, vs):
            ax.text(xi, v + (mu * .035 + .012), f"{v:.3f}", ha="center", fontsize=7.2,
                    color=c)
    ax.set_xticks(x)
    ax.set_xticklabels([str(s) for s in seeds], fontsize=8.5)
    ax.set_xlim(-.35, len(seeds) - .65)
    ax.set_xlabel(xlabel)
    if ylabel:
        ax.set_ylabel(ylabel)
    # 값 라벨과 평균±표준편차 띠가 잘리지 않게 위아래 여백을 둔다
    allv = np.concatenate([vs for _, vs, _ in series])
    lo, hi = float(allv.min()), float(allv.max())
    pad = (hi - lo) * .16 if hi > lo else max(abs(hi) * .05, .01)
    ax.set_ylim(lo - pad, hi + pad * 1.5)
    ax.yaxis.grid(True, linewidth=.6, zorder=0)
    ax.set_axisbelow(True)
    _bare_axes(ax, ("top", "right"))
    hs, ls = ax.get_legend_handles_labels()
    fig.legend(hs, ls, loc="upper center", bbox_to_anchor=(0.5, 0.0),
               ncol=1, frameon=False, fontsize=8)
    if title:
        ax.set_title(title, loc="left", color=FIG_INK, pad=8)
    return fig_to_img(fig, f"{title or '시드별 값'} 꺾은선그래프")


def svg_range_strip(lo, hi, mean, seed42=None, gate=None):
    """KPI 카드 안의 범위 막대. 인라인 SVG 라 테마 색(CSS 변수)을 그대로 쓴다."""
    pts = [p for p in (lo, hi, mean, seed42, gate) if is_num(p)]
    if len(pts) < 2 or hi is None or lo is None:
        return ""
    dmin, dmax = min(pts), max(pts)
    span = dmax - dmin
    pad = span * 0.18 if span > 0 else max(abs(dmin) * 0.02, 0.01)
    a, b = dmin - pad, dmax + pad
    W, H = 240.0, 18.0

    def x(v):
        return 4 + (W - 8) * (v - a) / (b - a)
    parts = [f'<svg viewBox="0 0 {W:g} {H:g}" role="img" '
             f'aria-label="최소 {fmt_kpi(lo)} 최대 {fmt_kpi(hi)} 평균 {fmt_kpi(mean)}">',
             f'<line x1="4" y1="{H/2:g}" x2="{W-4:g}" y2="{H/2:g}" '
             f'stroke="var(--hair-2)" stroke-width="1"/>',
             f'<line x1="{x(lo):g}" y1="{H/2:g}" x2="{x(hi):g}" y2="{H/2:g}" '
             f'stroke="var(--shoal)" stroke-width="5" stroke-linecap="round" opacity=".45"/>']
    if is_num(gate):
        parts.append(f'<line x1="{x(gate):g}" y1="2" x2="{x(gate):g}" y2="{H-2:g}" '
                     f'stroke="var(--warn)" stroke-width="1.2" stroke-dasharray="2 2"/>')
    if is_num(seed42):
        parts.append(f'<rect x="{x(seed42)-1:g}" y="{H/2-4:g}" width="2" height="8" '
                     f'fill="var(--land)"/>')
    parts.append(f'<circle cx="{x(mean):g}" cy="{H/2:g}" r="3.4" fill="var(--deep)"/>')
    parts.append("</svg>")
    return f'<div class="kpi-strip">{"".join(parts)}</div>'


# ══════════════════════════════════════════════════════════════════════════
# 지도 비교 (회전·반사 정렬만)
# ══════════════════════════════════════════════════════════════════════════
def align(coords, reference):
    """Procrustes 정합. src/map/compare_korea_map_population.py 의 align() 과 같은 방식.

    UMAP 좌표는 시드마다 회전·반사가 달라 그냥 겹쳐 볼 수 없다. 두 좌표를 같은 프레임
    (중심 0, Frobenius 노름 1)에 놓고 **직교행렬 하나**만 곱한다.
    orthogonal_procrustes 는 회전·반사만 돌려주며 스케일 계수를 추정하지 않는다.
    """
    a = coords - coords.mean(axis=0)
    b = reference - reference.mean(axis=0)
    a = a / np.linalg.norm(a)
    b = b / np.linalg.norm(b)
    r, _ = orthogonal_procrustes(a, b)
    return a @ r


def _frame(coords):
    """align() 의 기준 쪽 처리와 같게 만든다 (중심 0, 노름 1)."""
    b = coords - coords.mean(axis=0)
    return b / np.linalg.norm(b)


def _align_subset(coords, reference, idx_c, idx_r):
    """공통 id 로 변환을 구하고 그 변환을 전체 점에 적용한다.

    id 집합이 같으면 align() 과 정확히 같은 결과가 된다.
    """
    cs, rs = coords[idx_c], reference[idx_r]
    cm, rm = cs.mean(axis=0), rs.mean(axis=0)
    cn, rn = np.linalg.norm(cs - cm), np.linalg.norm(rs - rm)
    r, _ = orthogonal_procrustes((cs - cm) / cn, (rs - rm) / rn)
    return ((coords - cm) / cn) @ r


def map_compare_figure(panels, families=None, align_to_first=True,
                       source=None, point_size=14, extra_note=None):
    """지도를 나란히 놓고 비교하는 그림 블록(HTML)을 만든다.

    panels    : [(제목, ids, coords(n,2)), ...]  ids 는 향수 식별자 리스트
    families  : {id: 계열키} 를 주면 FAMILY_COLORS 로 칠한다 (없으면 단색)
    align_to_first : 두 번째 이후 패널을 첫 패널에 회전·반사 정렬한다

    정렬은 눈으로 비교하기 위한 것이다. **지표는 정렬 전 좌표로 계산한다** (README 규약).
    정렬을 적용하면 캡션에 규약 문구를 반드시 넣는다.
    """
    _rc()
    prepared = []
    ref_ids, ref_xy = None, None
    for i, (title, ids, xy) in enumerate(panels):
        ids = list(ids)
        xy = np.asarray(xy, dtype=float)
        if i == 0:
            ref_ids, ref_xy = ids, xy
            prepared.append((title, ids, _frame(xy) if align_to_first else xy, False))
            continue
        if not align_to_first:
            prepared.append((title, ids, xy, False))
            continue
        pos_r = {v: j for j, v in enumerate(ref_ids)}
        shared = [v for v in ids if v in pos_r]
        if len(shared) < 3:
            prepared.append((title, ids, xy, False))   # 정렬 불가 — 원좌표 그대로
            continue
        idx_c = [ids.index(v) for v in shared]
        idx_r = [pos_r[v] for v in shared]
        prepared.append((title, ids, _align_subset(xy, ref_xy, idx_c, idx_r), True))

    n = len(prepared)
    fig, axes = plt.subplots(1, n, figsize=(4.1 * n, 4.3), squeeze=False)
    axes = axes[0]
    allpts = np.vstack([p[2] for p in prepared])
    m = max(np.abs(allpts).max() * 1.08, 1e-9)
    for ax, (title, ids, xy, aligned) in zip(axes, prepared):
        if families:
            cols = [family_color(families.get(i)) or UNMAPPED_COLOR for i in ids]
        else:
            cols = FIG_SHOAL
        ax.scatter(xy[:, 0], xy[:, 1], s=point_size, c=cols,
                   linewidths=.4, edgecolors=FIG_BG, zorder=3)
        ax.set_title(title + ("  · 정렬" if aligned else ""), fontsize=10, loc="left",
                     color=FIG_INK)
        ax.set_xlim(-m, m)
        ax.set_ylim(-m, m)
        ax.set_aspect("equal")
        ax.set_xticks([])
        ax.set_yticks([])
        for s in ("top", "right", "bottom", "left"):
            ax.spines[s].set_color(FIG_HAIR)
    img = fig_to_img(fig, "지도 좌표 산점도 비교")
    any_aligned = any(p[3] for p in prepared)
    cap = []
    if any_aligned:
        cap.append("두 지도를 같은 프레임(중심 0, 노름 1)에 두고 직교행렬만 곱했습니다 — "
                   "점 사이 거리의 비는 그대로입니다. 지표는 정렬 전 좌표로 계산합니다. "
                   "축에 눈금을 두지 않았습니다 — 위치의 절대값은 의미가 없습니다.")
    else:
        cap.append("정렬하지 않은 원좌표입니다.")
    if extra_note:
        cap.append(extra_note)
    return figure_block(img, " ".join(cap), source=source,
                        must=ALIGN_CAPTION if any_aligned else None)


def map_axis_figure(panels, families=None, axis_labels=None, annotate=None,
                    source=None, point_size=16, caption=None, note=None,
                    panel_size=4.5):
    """축에 이름을 붙인 지도. 회전 전/후처럼 **같은 점을 다른 좌표계로** 볼 때 쓴다.

    panels      : [(제목, ids, coords(n,2), 부제)] — 좌표를 그대로 그린다 (정렬하지 않는다)
    axis_labels : {panel_index: {"top":…, "bottom":…, "left":…, "right":…}}
                  축 방향 이름. 회전 전 패널은 이름이 없으므로 비워 둘 수 있다.
    annotate    : {panel_index: [(id, 라벨, kind)]}  kind: "end"(축 끝) | "exception"(반례)

    **정렬하지 않는 이유.** Procrustes 정렬은 회전을 되돌리므로 회전 전/후 비교에서는
    쓸 수 없다. 대신 패널마다 같은 축 범위를 쓰고 눈금을 지운다.
    """
    _rc()
    prepared = [(t, list(ids), np.asarray(xy, dtype=float), sub)
                for t, ids, xy, sub in panels]
    n = len(prepared)
    fig, axes = plt.subplots(1, n, figsize=(panel_size * n, panel_size + .5),
                             squeeze=False)
    axes = axes[0]
    allpts = np.vstack([p[2] for p in prepared])
    m = max(np.abs(allpts).max() * 1.10, 1e-9)
    plate = dict(facecolor=FIG_BG, edgecolor="none", alpha=.8,
                 boxstyle="square,pad=0.15")
    for pi, (ax, (title, ids, xy, sub)) in enumerate(zip(axes, prepared)):
        cols = ([family_color(families.get(i)) or UNMAPPED_COLOR for i in ids]
                if families else FIG_SHOAL)
        ax.scatter(xy[:, 0], xy[:, 1], s=point_size, c=cols,
                   linewidths=.4, edgecolors=FIG_BG, zorder=3)
        pos = {i: k for k, i in enumerate(ids)}
        for pid, lab, kind in (annotate or {}).get(pi, []):
            k = pos.get(pid)
            if k is None:
                continue
            exc = kind == "exception"
            ax.scatter([xy[k, 0]], [xy[k, 1]], s=point_size * 3.2, zorder=5,
                       facecolors="none", linewidths=1.3,
                       edgecolors=(FIG_WARN if exc else FIG_DEEP))
            # 라벨은 점이 놓인 사분면의 반대쪽으로 뺀다 (가장자리 점의 글자가 잘리지 않게)
            right = xy[k, 0] <= 0
            up = xy[k, 1] <= 0
            ax.annotate(lab, (xy[k, 0], xy[k, 1]), fontsize=7,
                        color=(FIG_WARN if exc else FIG_INK),
                        ha=("left" if right else "right"),
                        va=("bottom" if up else "top"),
                        xytext=((6 if right else -6), (6 if up else -6)),
                        textcoords="offset points", zorder=6, bbox=plate)
        # 축 화살표는 프레임 안, 축 이름은 점과 겹치지 않는 자리에 둔다
        # (세로 이름은 위·아래 여백에, 가로 이름은 프레임 밖 아래 두 귀퉁이에).
        lb = (axis_labels or {}).get(pi) or {}
        if lb:
            ax.annotate("", xy=(0, m * .93), xytext=(0, -m * .93),
                        arrowprops=dict(arrowstyle="<->", color=FIG_LAND,
                                        linewidth=1.0, alpha=.75), zorder=2)
            ax.annotate("", xy=(m * .93, 0), xytext=(-m * .93, 0),
                        arrowprops=dict(arrowstyle="<->", color=FIG_LAND,
                                        linewidth=1.0, alpha=.75), zorder=2)
            style = dict(fontsize=8.5, color=FIG_LAND, fontweight="bold", zorder=7)
            if lb.get("top"):
                ax.text(0, m * .955, lb["top"], ha="center", va="top",
                        bbox=plate, **style)
            if lb.get("bottom"):
                ax.text(0, -m * .955, lb["bottom"], ha="center", va="bottom",
                        bbox=plate, **style)
            if lb.get("left"):
                ax.text(0.0, -0.02, "← " + lb["left"], transform=ax.transAxes,
                        ha="left", va="top", **style)
            if lb.get("right"):
                ax.text(1.0, -0.02, lb["right"] + " →", transform=ax.transAxes,
                        ha="right", va="top", **style)
        nsub = sub.count("\n") + 1 if sub else 0
        ax.set_title(title, fontsize=10, loc="left", color=FIG_INK,
                     pad=(8 + 11.5 * nsub if sub else 8))
        if sub:
            ax.text(0, 1.012, sub, transform=ax.transAxes, fontsize=7.4,
                    color=FIG_MUTED, ha="left", va="bottom", linespacing=1.4)
        ax.set_xlim(-m, m)
        ax.set_ylim(-m, m)
        ax.set_aspect("equal")
        ax.set_xticks([])
        ax.set_yticks([])
        for s in ("top", "right", "bottom", "left"):
            ax.spines[s].set_color(FIG_HAIR)
    img = fig_to_img(fig, "축 이름을 붙인 지도 좌표 산점도")
    cap = [caption or "정렬하지 않은 원좌표입니다. 회전은 등거리 변환이므로 점 사이 거리가 "
                      "바뀌지 않습니다. 축에 눈금을 두지 않았습니다 — 위치의 절대값은 "
                      "의미가 없습니다."]
    if note:
        cap.append(note)
    return figure_block(img, " ".join(cap), source=source)


def _read_coord_csv(path):
    """coordinates*.csv → (ids, coords, families|None). id 열 + 숫자 2열을 찾는다."""
    header, rows, _ = read_csv_rows(path)
    if not header or not rows:
        return None
    low = [h.strip().lower() for h in header]
    id_i = next((i for i, h in enumerate(low) if h == "id" or h.endswith("_id")), 0)
    fam_i = next((i for i, h in enumerate(low) if h in ("family", "family_key", "fs1_argmax")), None)
    num_cols = []
    for i, h in enumerate(low):
        if i == id_i or i == fam_i:
            continue
        try:
            float(rows[0][i])
        except (ValueError, IndexError):
            continue
        num_cols.append(i)
    pref = [i for i in num_cols if low[i].startswith("x")] + [i for i in num_cols if low[i].startswith("y")]
    use = pref[:2] if len(pref) >= 2 else num_cols[:2]
    if len(use) < 2:
        return None
    ids, xy, fams = [], [], {}
    for r in rows:
        try:
            p = (float(r[use[0]]), float(r[use[1]]))
        except (ValueError, IndexError):
            continue
        key = r[id_i]
        ids.append(key)
        xy.append(p)
        if fam_i is not None and fam_i < len(r):
            fams[key] = r[fam_i]
    if len(ids) < 3:
        return None
    return ids, np.array(xy, dtype=float), (fams or None), [header[use[0]], header[use[1]]]


# ══════════════════════════════════════════════════════════════════════════
# 지표 / KPI
# ══════════════════════════════════════════════════════════════════════════
def detect_metric(path):
    """경로 문자열에서 지표 이름을 찾는다. 가장 긴 별칭이 이긴다 (trust10 > trust)."""
    n = norm(path)
    last = norm(re.split(r"[.\[]", str(path))[-1])
    best = None
    for key, als in _ALIASES.items():
        for a in als:
            hit = (len(a) >= _ALIAS_MIN_SUBSTR and a in n) or (a == last)
            if hit and (best is None or len(a) > best[1]):
                best = (key, len(a))
                break
    return best[0] if best else None


def detect_metric_exact(name):
    """이름이 별칭과 정확히 같을 때만 지표로 본다.

    표 안에 설명을 붙일 때 쓴다. 부분 일치를 허용하면
    'accord_sim_of_top10pct_note_pairs' 에 top10 포함률 설명이 붙는 사고가 난다.
    """
    n = norm(name)
    for key, als in _ALIASES.items():
        if n in als:
            return key
    return None


def detect_population(path, manifest):
    n = norm(path)
    for p in POPULATIONS:
        if norm(p) in n:
            return p
    pops = manifest.get("population")
    if isinstance(pops, str):
        return pops
    if isinstance(pops, list) and len(pops) == 1:
        return pops[0]
    return None


def find_metric_blocks(node, path=""):
    """mean/min/max 를 가진 dict = 시드 여러 개를 요약한 지표 블록. 그 안으로는 안 들어간다."""
    out = []
    if isinstance(node, dict):
        if BLOCK_MARKERS.issubset(set(node)) and all(is_num(node[k]) for k in BLOCK_MARKERS):
            out.append((path, node))
            return out
        for k, v in node.items():
            out += find_metric_blocks(v, f"{path}.{k}" if path else str(k))
    return out


def resolve_baseline(path, metric, stat, manifest):
    """기준값을 찾는다. 우선순위: manifest.baseline_reference → 캠페인 고정 기준값.

    이름이 실험마다 흔들리므로 토큰 부분집합으로 맞춘다. 지표 경로의 토큰을 모두 포함하는
    후보 중 **토큰이 가장 많은(가장 구체적인)** 키를 고른다.
    """
    base = manifest.get("baseline_reference")
    if isinstance(base, dict):
        want = tok(path)
        if stat:
            want |= tok(stat)
        if metric:
            spec = GLOSSARY.get(metric, {})
            want |= tok(metric)
            for al in spec.get("aliases", []):
                want |= tok(al)
        best = None
        for k, v in base.items():
            if not is_num(v):
                continue
            # 같은 지표의 기준값만 쓴다. 이 확인이 없으면 토큰이 겹치는 다른 지표
            # (예: reminds_pct 가 trusted_edges 872) 를 기준값으로 끌어온다.
            if metric and detect_metric(k) != metric:
                continue
            kt = tok(k)
            if kt and kt <= want and (best is None or len(kt) > len(best[1])):
                best = (k, kt, v)
        if best:
            return best[2], f"manifest.baseline_reference.{best[0]}"
    pop = detect_population(path, manifest)
    for key in ((pop, metric, stat), (pop, metric, None)):
        if key in CAMPAIGN_BASELINE:
            return CAMPAIGN_BASELINE[key], "캠페인 고정 기준값 (experiments/README.md)"
    return None, None


def gate_verdict(card):
    """게이트 판정. README: 판정은 평균과 최소값으로 하고, 최소값이 게이트에서
    0.01 이내면 자동 판정을 금지하고 REVIEW 로 넘긴다."""
    g = card["gate"]
    if not g:
        return None, ""
    lo, hi, mean = card["lo"], card["hi"], card["value"]
    if not is_num(mean):
        return None, ""
    gmin, gmax = g.get("min"), g.get("max")
    if g.get("max_baseline_delta") is not None and is_num(card["baseline"]):
        gmax = card["baseline"] + g["max_baseline_delta"]
    if g.get("min_baseline_delta") is not None and is_num(card["baseline"]):
        gmin = card["baseline"] + g["min_baseline_delta"]

    if is_num(gmin):
        worst = lo if is_num(lo) else mean
        if abs(worst - gmin) <= GATE_MARGIN:
            return "REVIEW", f"최소값 {worst:.4f} 이 게이트 {gmin:g} 에서 {GATE_MARGIN} 이내 — 자동 판정 금지"
        if worst > gmin:
            return "PASS", f"최소값 {worst:.4f} > 게이트 {gmin:g}"
        if mean >= gmin:
            return "REVIEW", f"평균 {mean:.4f} 은 통과하지만 최소값 {worst:.4f} 이 게이트 {gmin:g} 미달"
        return "FAIL", f"평균 {mean:.4f} · 최소값 {worst:.4f} 모두 게이트 {gmin:g} 미달"
    if is_num(gmax):
        worst = hi if is_num(hi) else mean
        if abs(worst - gmax) <= GATE_MARGIN:
            return "REVIEW", f"최대값 {worst:.4f} 이 게이트 {gmax:g} 에서 {GATE_MARGIN} 이내 — 자동 판정 금지"
        if worst < gmax:
            return "PASS", f"최대값 {worst:.4f} < 게이트 {gmax:g}"
        if mean <= gmax:
            return "REVIEW", f"평균 {mean:.4f} 은 통과하지만 최대값 {worst:.4f} 이 게이트 {gmax:g} 초과"
        return "FAIL", f"평균 {mean:.4f} · 최대값 {worst:.4f} 모두 게이트 {gmax:g} 초과"
    return None, ""


def _get_path(node, path):
    """'a.b.c' 또는 'a.b[0].c' 로 값을 꺼낸다. 없으면 None."""
    cur = node
    for part in re.findall(r"[^.\[\]]+", str(path)):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        elif isinstance(cur, list) and part.isdigit() and int(part) < len(cur):
            cur = cur[int(part)]
        else:
            return None
    return cur


def build_card(path, value, manifest, spec=None, used_terms=None):
    """KPI 카드 하나의 자료를 만든다. value 는 지표 블록(dict) 또는 스칼라."""
    spec = spec or {}
    metric = spec.get("metric") or detect_metric(path)
    if used_terms is not None and metric:
        used_terms.add(metric)
    block = value if isinstance(value, dict) else None
    if block:
        rep, stat = block.get("mean"), "mean"
        lo, hi, sd = block.get("min"), block.get("max"), block.get("std")
        seed42 = block.get("seed42")
    else:
        rep, stat = value, None
        lo = hi = sd = seed42 = None
    if not is_num(rep):
        return None

    # 기준값 — mean 기준으로 못 찾으면 seed42 기준으로 다시 찾아 같은 통계끼리 비교한다
    cmp_stat, cmp_val = stat, rep
    if "baseline" in spec:
        b = spec["baseline"]
        if isinstance(b, str):
            base_ref = manifest.get("baseline_reference") or {}
            bval, bsrc = base_ref.get(b), f"manifest.baseline_reference.{b}"
            bval = bval if is_num(bval) else None
        else:
            bval, bsrc = (b, "manifest.primary_metrics.baseline") if is_num(b) else (None, None)
    else:
        bval, bsrc = resolve_baseline(path, metric, stat, manifest)
        if bval is None and is_num(seed42):
            bval, bsrc = resolve_baseline(path, metric, "seed42", manifest)
            if bval is not None:
                cmp_stat, cmp_val = "seed42", seed42
    gate = spec.get("gate")
    if gate is None and metric in CAMPAIGN_GATES:
        gate = CAMPAIGN_GATES[metric]
    return {
        "path": path, "label": spec.get("label") or metric or path,
        "metric": metric, "population": spec.get("population") or detect_population(path, manifest),
        "value": rep, "stat": stat, "lo": lo, "hi": hi, "std": sd, "seed42": seed42,
        "baseline": bval, "baseline_source": bsrc,
        "cmp_stat": cmp_stat, "cmp_value": cmp_val,
        "delta": (cmp_val - bval) if (is_num(bval) and is_num(cmp_val)) else None,
        "direction": spec.get("direction") or ("down" if metric == "trusted-edge 근접도" else "up"),
        "gate": gate, "role": spec.get("role", "primary"),
        "desc": GLOSSARY.get(metric, {}).get("desc", ""),
    }


def collect_cards(metrics, manifest, used_terms):
    """manifest 가 KPI 를 지정하면 그대로, 없으면 지표 이름으로 자동 선택한다."""
    cards, seen = [], set()
    declared = False
    for role in ("primary_metrics", "guardrail_metrics"):
        for item in manifest.get(role) or []:
            spec = dict(item) if isinstance(item, dict) else {"path": item}
            p = spec.pop("path", None)
            if not p:
                continue
            declared = True
            spec["role"] = "primary" if role == "primary_metrics" else "guardrail"
            val = _get_path(metrics, p)
            if val is None:
                continue
            c = build_card(p, val, manifest, spec, used_terms)
            if c and p not in seen:
                seen.add(p)
                cards.append(c)
    if declared:
        return cards, True

    # 자동 선택 — 지표 블록 먼저, 그다음 지표 이름을 가진 스칼라
    def kpi_like(path):
        m = detect_metric(path)
        if not m or GLOSSARY.get(m, {}).get("kind") != "metric":
            return None
        leaf = re.split(r"[.\[]", str(path))[-1]
        parts = re.findall(r"[a-z]+|\d+", leaf.lower())
        if parts and parts[-1] in COUNT_LEAF_TOKENS:
            return None
        return m

    auto = []
    for path, block in find_metric_blocks(metrics):
        m = kpi_like(path)
        if m:
            auto.append((path, block, m))
    block_paths = [p for p, _, _ in auto]
    for path, val in walk_json(metrics):
        if not is_num(val) or any(path.startswith(bp + ".") or path == bp for bp in block_paths):
            continue
        if re.search(r"\[\d+\]", path):          # 리스트 원소(재현 검증 등)는 제외
            continue
        m = kpi_like(path)
        if m:
            auto.append((path, val, m))
    pop_rank = {p: i for i, p in enumerate(POPULATIONS)}
    gl_rank = {k: i for i, k in enumerate(GLOSSARY)}
    auto.sort(key=lambda t: (pop_rank.get(detect_population(t[0], manifest), 9),
                             gl_rank.get(t[2], 99), t[0]))
    for path, val, _ in auto[:MAX_KPI]:
        c = build_card(path, val, manifest, None, used_terms)
        if c and path not in seen:
            seen.add(path)
            cards.append(c)
    return cards, False


# ══════════════════════════════════════════════════════════════════════════
# HTML 조각
# ══════════════════════════════════════════════════════════════════════════
def h_facts(pairs):
    if not pairs:
        return ""
    items = "".join(f"<div><dt>{esc(k)}</dt><dd>{v}</dd></div>" for k, v in pairs)
    return f'<dl class="facts">{items}</dl>'


def h_table(header, rows, caption=None, num_cols=None, css_first_key=False,
            row_classes=None):
    """표 하나. row_classes 에 행별 CSS 클래스를 주면 그 행을 강조할 수 있다
    ("flag" = 검토 대상, "dim" = 배경으로 물러난 행)."""
    if not rows:
        return ""
    num_cols = num_cols or set()
    th = "".join('<th class="num">' + esc(h) + "</th>" if i in num_cols
                 else "<th>" + esc(h) + "</th>"
                 for i, h in enumerate(header))
    body = []
    for ri, r in enumerate(rows):
        tds = []
        for i, v in enumerate(r):
            cls = ""
            if i in num_cols:
                cls = ' class="num"'
            elif i == 0 and css_first_key:
                cls = ' class="key"'
            tds.append(f"<td{cls}>{v if isinstance(v, _Raw) else cell(v)}</td>")
        rc = (row_classes[ri] if row_classes and ri < len(row_classes) else "") or ""
        open_tag = '<tr class="' + esc(rc) + '">' if rc else "<tr>"
        body.append(open_tag + "".join(tds) + "</tr>")
    cap = f"<caption>{esc(caption)}</caption>" if caption else ""
    return (f'<div class="scroll"><table>{cap}<thead><tr>{th}</tr></thead>'
            f'<tbody>{"".join(body)}</tbody></table></div>')


class _Raw(str):
    """이미 HTML 인 셀 값."""


def h_kv_table(d, caption=None, used_terms=None):
    """스칼라만 있는 dict → 키·값 표. 용어 설명이 있으면 붙인다."""
    rows, nums = [], {1}
    for k, v in d.items():
        note = ""
        m = detect_metric_exact(k)
        if m and GLOSSARY.get(m, {}).get("desc"):
            if used_terms is not None:
                used_terms.add(m)
            note = f'<span class="note"> — {esc(GLOSSARY[m]["desc"])}</span>'
        rows.append([_Raw(esc(k) + note), v])
    return h_table(["항목", "값"], rows, caption=caption, num_cols=nums)


def h_rows_table(items, caption=None, limit=MAX_TABLE_ROWS):
    """같은 키를 가진 dict 리스트 → 표."""
    keys = []
    for it in items:
        for k in it:
            if k not in keys:
                keys.append(k)
    rows = [[it.get(k) for k in keys] for it in items[:limit]]
    nums = {i for i, k in enumerate(keys)
            if all(is_num(it.get(k)) or it.get(k) is None for it in items)}
    out = h_table(keys, rows, caption=caption, num_cols=nums)
    if len(items) > limit:
        out += f'<p class="note">전체 {len(items)}행 중 {limit}행만 보였습니다.</p>'
    return out


def h_checks_table(checks):
    """재현 검증 표. measured / expected / tolerance / ok 를 그대로 보인다."""
    rows = []
    for src, c in checks:
        ok = bool(c.get("ok"))
        tag = ('<span class="tag tag-ok">OK</span>' if ok
               else '<span class="tag tag-bad">불일치</span>')
        rows.append([_Raw(tag), c.get("name"), c.get("measured"), c.get("expected"),
                     c.get("tolerance"), _Raw(f'<span class="mono">{esc(src)}</span>')])
    return h_table(["판정", "항목", "측정", "기대", "허용", "출처"], rows,
                   num_cols={2, 3, 4})


def h_kpi_card(c):
    verdict, why = gate_verdict(c)
    klass = {"PASS": "pass", "REVIEW": "review", "FAIL": "fail"}.get(verdict, "")
    tag = {"PASS": '<span class="tag tag-ok">PASS</span>',
           "REVIEW": '<span class="tag tag-open">REVIEW</span>',
           "FAIL": '<span class="tag tag-bad">FAIL</span>'}.get(
        verdict, '<span class="tag tag-flat">게이트 없음</span>')
    # 시드 개수를 블록에서 알 수 없으므로 "5시드" 같은 수를 붙이지 않는다.
    if c["stat"] == "mean":
        if is_num(c["lo"]) and is_num(c["hi"]) and (c["hi"] - c["lo"]) < 1e-12:
            stat_ko = "시드 1개"
        else:
            stat_ko = "시드 평균"
    else:
        stat_ko = c["stat"] or ""
    kv = []
    if is_num(c["baseline"]):
        d = c["delta"]
        good = None
        if is_num(d):
            good = (d > 0) if c["direction"] == "up" else (d < 0)
        dcls = "flat" if (not is_num(d) or abs(d) < 5e-5) else ("up" if good else "down")
        cmp_ko = {"mean": "평균과 비교", "seed42": "seed 42 와 비교"}.get(c["cmp_stat"], "")
        kv.append(("기준", esc(fmt_kpi(c["baseline"]))
                   + (f' <span class="note">({cmp_ko})</span>' if cmp_ko else "")))
        kv.append(("Δ 기준대비", f'<span class="{dcls}">{fmt_delta(d)}</span>'))
    else:
        kv.append(("기준", '<span class="note">없음 — 비교하지 않음</span>'))
    if is_num(c["lo"]) and is_num(c["hi"]):
        s = f'{fmt_kpi(c["lo"])} ~ {fmt_kpi(c["hi"])}'
        if is_num(c["std"]):
            s += f' <span class="note">std {fmt_kpi(c["std"])}</span>'
        kv.append(("최소~최대", s))
    if is_num(c["seed42"]):
        kv.append(("seed 42", esc(fmt_kpi(c["seed42"]))))
    kvhtml = "".join(f"<dt>{esc(k)}</dt><dd>{v}</dd>" for k, v in kv)
    gate_note = ""
    if c["gate"]:
        gl = c["gate"].get("label") or "게이트"
        gate_note = f'{esc(gl)} · {esc(why)}'
    elif c["baseline_source"]:
        gate_note = esc(c["baseline_source"])
    role = "" if c["role"] == "primary" else '<span class="tag tag-flat">guardrail</span>'
    strip = svg_range_strip(c["lo"], c["hi"], c["value"], c["seed42"],
                            (c["gate"] or {}).get("min") or (c["gate"] or {}).get("max"))
    pop = ('<span class="kpi-pop">' + esc(c["population"]) + "</span>") if c["population"] else ""
    desc = ('<p class="kpi-desc">' + esc(c["desc"]) + "</p>") if c["desc"] else ""
    unit = ("<small>" + esc(stat_ko) + "</small>") if stat_ko else ""
    return (f'<article class="kpi {klass}">'
            f'<div class="kpi-top"><span class="kpi-name">{esc(c["label"])}</span>{pop}</div>'
            f'<p class="kpi-val">{esc(fmt_kpi(c["value"]))}{unit}</p>'
            + desc + strip
            + f'<dl class="kpi-kv">{kvhtml}</dl>'
            f'<p class="kpi-foot">{tag}{role}<span>{gate_note}</span></p>'
            f'<p class="kpi-foot"><span class="mono">{esc(c["path"])}</span></p>'
            "</article>")


def h_family_legend():
    return h_legend([(FAMILY_COLORS[f], FAMILY_KO[f], f) for f in FAMILY_ORDER])


def h_section(sid, eyebrow, title, body, lead=None):
    return (f'<section id="{esc(sid)}">'
            f'<div class="sec-head col"><p class="eyebrow">{esc(eyebrow)}</p>'
            f'<h2>{esc(title)}</h2>'
            + (f'<p class="lead">{lead}</p>' if lead else "")
            + f'</div>{body}</section>')


# ── 절 조립 ────────────────────────────────────────────────────────────────
# 번호는 조립 단계에서 붙인다. 절을 끼워 넣어도 ①②③… 이 어긋나지 않는다.
CIRCLED = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳"


def make_section(sid, short, title, body, lead=None, after=None):
    """절 하나의 자료. `short` 는 목차에 번호와 함께 나오는 짧은 이름이다.

    after : 이 sid 를 가진 자동 절 뒤에 끼운다 (없으면 맨 끝). 자동 절의 sid 는
            s1 실험 요약 · s2 KPI · s3 시각화 · s4 사례 · s5 팀 검토 ·
            s6 하위 산출물 · s7 용어 · s8 파일.
    """
    return {"sid": sid, "short": short, "title": title, "body": body,
            "lead": lead, "after": after}


def h_heading(text, level=3, top="1.6rem"):
    return f'<h{level} style="margin-top:{top}">{esc(text)}</h{level}>'


def h_para(text):
    return f"<p>{esc(text)}</p>"


def h_note(text):
    return f'<p class="note">{esc(text)}</p>'


def h_bullets(items):
    """가운뎃점 목록. 표 셀 안에 여러 줄을 넣을 때 쓴다 (문자열은 이스케이프한다)."""
    return "".join(f"<p>· {esc(x)}</p>" for x in items)


def h_callout(title, items, kind=None):
    """강조 블록. items 는 문자열 하나 또는 문자열 리스트.
    kind: None(기본 강조) | "warn"(주의) | "ok"(통과)"""
    if isinstance(items, str):
        items = [items]
    cls = "callout" + (f" {kind}" if kind else "")
    inner = "".join(f"<p>{esc(x)}</p>" for x in items)
    head = f'<p class="h">{esc(title)}</p>' if title else ""
    return f'<div class="{cls}">{head}{inner}</div>'


def h_details(summary, body):
    return (f'<details><summary>{esc(summary)}</summary>'
            f'<div class="d-body">{body}</div></details>')


def h_mono(text):
    """고정폭 조각. 표 셀에 넣을 때는 _Raw 로 감싸 쓴다."""
    return f'<span class="mono">{esc(text)}</span>'


def h_swatch(color, label, note=None):
    """색 견본이 붙은 이름표 하나. 표 셀·문장 안에 넣는다."""
    return (f'<span class="chip"><span class="sw" style="background:{esc(color)}"></span>'
            f'{esc(label)}' + (f' <span class="note">{esc(note)}</span>' if note else "")
            + "</span>")


def h_legend(items):
    """색 범례. items 는 (색, 이름, 덧말) 튜플 리스트."""
    return f'<div class="chips">{"".join(h_swatch(*it) for it in items)}</div>'


# ══════════════════════════════════════════════════════════════════════════
# 일반 JSON → HTML (하위 산출물 섹션)
# ══════════════════════════════════════════════════════════════════════════
MEMO_KEYS = ("conclusion", "note", "notes", "limitation", "limitations", "caveat",
             "basis", "action", "issue", "cause", "rule", "reason", "status",
             "not_the_same_as", "recommendation")


def looks_memo(key):
    k = str(key).lower()
    return any(k == m or k.endswith("_" + m) or k.startswith(m + "_") or m in k
               for m in MEMO_KEYS)


def render_json_node(node, path, depth, used_terms, out):
    """dict/list 를 표·소제목·접은 블록으로 옮긴다. 재현 검증은 ② 로 모으므로 건너뛴다."""
    if isinstance(node, dict):
        scalars = {k: v for k, v in node.items()
                   if is_scalar(v) and not (isinstance(v, str) and len(v) > 110)}
        longtexts = {k: v for k, v in node.items()
                     if isinstance(v, str) and len(v) > 110}
        if scalars:
            out.append(h_kv_table(scalars, used_terms=used_terms))
        for k, v in longtexts.items():
            out.append(f'<div class="memo"><span class="k">{esc(k)}</span><p>{esc(v)}</p></div>')
        for k, v in node.items():
            if is_scalar(v):
                continue
            if k == "reproduction_checks":
                out.append('<p class="note">재현 검증 항목은 ② KPI · 재현 검증 절로 모았습니다.</p>')
                continue
            sub = f"{path}.{k}" if path else str(k)
            inner = []
            render_json_node(v, sub, depth + 1, used_terms, inner)
            body = "".join(inner)
            if not body:
                continue
            if depth >= 2:
                out.append(f'<details><summary>{esc(sub)}</summary>'
                           f'<div class="d-body">{body}</div></details>')
            else:
                tag = "h3" if depth == 0 else "h4"
                out.append(f'<{tag} style="margin-top:1.4rem">{esc(k)}</{tag}>{body}')
    elif isinstance(node, list):
        if node and all(isinstance(x, dict) for x in node):
            out.append(h_rows_table(node))
        elif node and all(is_scalar(x) for x in node):
            vals = ", ".join(fmt_num(x) if is_num(x) else str(x) for x in node[:60])
            more = f' <span class="note">… 총 {len(node)}개</span>' if len(node) > 60 else ""
            out.append(f'<p class="note mono">{esc(vals)}{more}</p>')
        else:
            for i, x in enumerate(node[:10]):
                render_json_node(x, f"{path}[{i}]", depth + 1, used_terms, out)


# ══════════════════════════════════════════════════════════════════════════
# 그림 자동 선택
# ══════════════════════════════════════════════════════════════════════════
def category_candidates(json_files):
    """라벨→숫자 dict 를 모아 그림 후보로 만든다. 통계 요약(mean/std/...)은 제외한다."""
    cands = []
    for rel, data in json_files:
        for path, node in walk_json(data):
            if not isinstance(node, dict) or not (3 <= len(node) <= 20):
                continue
            if not all(is_num(v) for v in node.values()):
                continue
            keys = {str(k).lower() for k in node}
            if len(keys & STATISH) * 2 >= len(keys):     # 통계 요약 블록
                continue
            leaf = re.split(r"[.\[]", path)[-1]
            fam = all(family_color(k) for k in node)
            rank = (0 if leaf in PREFERRED_CATEGORY_LEAVES else 1, 0 if fam else 1)
            cands.append((rank, rel, path, leaf, node))
    # 같은 숫자를 가진 후보(영문/한글 라벨 쌍, 파일이 달라도 같은 분포)는 하나만 남긴다
    seen, out = set(), []
    for rank, rel, path, leaf, node in sorted(cands, key=lambda c: (c[0], c[1], c[2])):
        sig = tuple(sorted(node.values()))
        if sig in seen:
            continue
        seen.add(sig)
        out.append((rel, path, leaf, node))
    return out


def build_figures(exp_dir, cards, json_files, auto_data=True):
    """③ 지표 시각화에 넣을 그림들. 총량은 MAX_FIGURES 로 제한한다.

    auto_data=False 면 KPI 관련 그림만 만들고 좌표 산점도·범주 막대는 만들지 않는다
    (실험이 자기 절에서 같은 자료를 더 정확한 그림으로 보일 때).
    """
    figs = []
    img = fig_kpi_vs_baseline(cards)
    if img:
        figs.append(figure_block(
            img, "KPI 의 이번 실험 값과 기준값. 기준값이 있는 지표만 그렸습니다.",
            source="출처: metrics.json + manifest.baseline_reference"))
    img = fig_seed_spread(cards)
    if img:
        figs.append(figure_block(
            img, "시드를 여러 개 돌린 지표의 최소~최대 폭. 점선은 게이트, 동그라미는 평균, "
                 "마름모는 seed 42 입니다. 판정은 평균과 최소값으로 합니다.",
            source="출처: metrics.json"))
    if not auto_data:
        return figs[:MAX_FIGURES]
    # 지도 좌표
    coord_files = sorted(_walk_files(exp_dir, lambda n: n.lower().startswith("coordinates")
                                     and n.lower().endswith(".csv")))
    loaded = []
    for rel, full in coord_files[:2]:
        got = _read_coord_csv(full)
        if got:
            loaded.append((rel, got))
    if len(loaded) >= 2:
        (r0, (i0, c0, f0, n0)), (r1, (i1, c1, f1, n1)) = loaded[0], loaded[1]
        figs.append(map_compare_figure(
            [(r0, i0, c0), (r1, i1, c1)], families=(f0 or f1),
            source=f"출처: {r0} · {r1}"))
    elif len(loaded) == 1:
        rel, (ids, xy, fams, cols) = loaded[0]
        figs.append(map_compare_figure([(f"{rel} ({cols[0]}, {cols[1]})", ids, xy)],
                                       families=fams, align_to_first=False,
                                       source=f"출처: {rel}"))
    # 범주 막대
    for rel, path, leaf, node in category_candidates(json_files):
        if len(figs) >= MAX_FIGURES:
            break
        title = f"{path}"
        img = fig_category_bar(node, title)
        if img:
            figs.append(figure_block(img, "", source=f"출처: {rel} · {path}"))
    return figs[:MAX_FIGURES]


def _walk_files(root, pred):
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in sorted(dirnames) if d not in ("intermediates", "__pycache__")]
        for fn in sorted(filenames):
            if pred(fn):
                full = os.path.join(dirpath, fn)
                out.append((os.path.relpath(full, root).replace("\\", "/"), full))
    return out


# ══════════════════════════════════════════════════════════════════════════
# 섹션
# ══════════════════════════════════════════════════════════════════════════
MANIFEST_ORDER = [
    ("experiment_id", "실험 ID"), ("phase", "Phase"), ("status", "상태"),
    ("population", "모집단"), ("projection", "투영"),
    ("feature_version", "feature 버전"), ("family_mapping_version", "계열 매핑 버전"),
    ("family_mapping_status", "계열 매핑 상태"), ("family_score_version", "Family Score 버전"),
    ("seeds", "시드"), ("elapsed_sec", "소요(초)"),
]
MANIFEST_SHOWN = {k for k, _ in MANIFEST_ORDER} | {
    "hypothesis", "user_meaning", "changed_variable", "snapshot_hash",
    "baseline_reference", "primary_metrics", "guardrail_metrics",
    "reproduction_gate_result", "output_files", "limitations", "limitation",
    "recommendation", "strengths", "risks", "open_questions", "parameters",
    "family_mapping_sha256",
}


def section_summary(manifest, exp_rel, sid="s1"):
    if not manifest:
        return None
    facts = []
    for k, ko in MANIFEST_ORDER:
        if k not in manifest:
            continue
        v = manifest[k]
        if isinstance(v, list):
            v = ", ".join(str(x) for x in v)
        facts.append((ko, esc(v)))
    body = [h_facts(facts)]

    qa = []
    for key, ko in (("hypothesis", "가설"), ("user_meaning", "사용자에게 무슨 뜻인가"),
                    ("changed_variable", "바꾼 변수 (한 줄에 하나)")):
        v = manifest.get(key)
        cls = "qa-item" if v else "qa-item todo"
        val = esc(v) if v else f"manifest.{key} 미기재 — 사람이 채워야 합니다."
        qa.append(f'<div class="{cls}"><span class="k">{esc(key)}</span>'
                  f'<span class="v">{esc(ko)}: {val}</span></div>')
    body.append(f'<div class="qa" style="margin-top:1.5rem">{"".join(qa)}</div>')

    params = manifest.get("parameters")
    if isinstance(params, dict) and params:
        body.append("<h3 style='margin-top:1.6rem'>파라미터</h3>")
        body.append(h_kv_table({k: v for k, v in params.items() if is_scalar(v)}))

    sh = manifest.get("snapshot_hash")
    if isinstance(sh, dict) and sh:
        rows = [[k, _Raw(f'<span class="mono" title="{esc(v)}">{esc(str(v)[:16])}…</span>')]
                for k, v in sh.items()]
        body.append("<h3 style='margin-top:1.6rem'>입력 스냅숏 해시 (SHA-256)</h3>")
        body.append('<p class="note">모든 실험이 같은 데이터를 썼는지 확인하는 값입니다. '
                    '마우스를 올리면 전체 해시가 보입니다.</p>')
        body.append(h_table(["입력", "해시 앞 16자"], rows, css_first_key=True))

    gate = manifest.get("reproduction_gate_result")
    if isinstance(gate, dict) and gate:
        body.append("<h3 style='margin-top:1.6rem'>재현 게이트</h3>")
        body.append(h_kv_table(gate))
    elif gate:
        body.append(f'<div class="memo"><span class="k">reproduction_gate_result</span>'
                    f'<p>{esc(gate)}</p></div>')

    rest = {k: v for k, v in manifest.items()
            if k not in MANIFEST_SHOWN and is_scalar(v)}
    rest_c = {k: v for k, v in manifest.items()
              if k not in MANIFEST_SHOWN and not is_scalar(v)}
    if rest:
        body.append("<h3 style='margin-top:1.6rem'>그 밖의 manifest 항목</h3>")
        body.append(h_kv_table(rest))
    for k, v in rest_c.items():
        inner = []
        render_json_node(v, k, 1, None, inner)
        if inner:
            body.append(f'<details><summary>manifest.{esc(k)}</summary>'
                        f'<div class="d-body">{"".join(inner)}</div></details>')
    lead = ("아래 값은 실험 코드가 <code>manifest.json</code> 에 남긴 것을 그대로 옮긴 것입니다. "
            f"출처 폴더는 <code>{esc(exp_rel)}</code> 입니다.")
    return make_section(sid, "실험 요약", "무엇을 어떤 입력으로 돌렸는가",
                        "".join(body), lead)


def section_kpi(cards, declared, checks, sid="s2"):
    if not cards and not checks:
        return None
    body = []
    if cards:
        body.append(f'<div class="kpis">{"".join(h_kpi_card(c) for c in cards)}</div>')
        counts = {}
        for c in cards:
            v, _ = gate_verdict(c)
            counts[v or "게이트 없음"] = counts.get(v or "게이트 없음", 0) + 1
        body.append('<p class="note" style="margin-top:1rem">판정 규칙: 시드 평균과 최소값으로 '
                    f'판정하고, 최소값이 게이트에서 {GATE_MARGIN} 이내면 자동 판정을 금지하고 REVIEW 로 '
                    '넘깁니다 (experiments/README.md). 게이트가 지정되지 않은 지표는 판정하지 않습니다.</p>')
        body.append('<p class="note">' + " · ".join(f"{k} {v}개" for k, v in counts.items()) + "</p>")
        if not declared:
            body.append('<p class="note">manifest 에 <code>primary_metrics</code> 가 없어 지표 이름으로 '
                        '자동 선택했습니다. 카드를 고르고 순서를 정하려면 manifest 에 적으십시오.</p>')
    if checks:
        ok = sum(1 for _, c in checks if c.get("ok"))
        body.append("<h3 style='margin-top:1.8rem'>재현 검증</h3>")
        body.append(f'<p class="note">{len(checks)}개 항목 중 {ok}개 일치. '
                    '측정값과 기대값의 차이가 허용 폭 안인지 실험 코드가 판정한 결과입니다.</p>')
        body.append(h_checks_table(checks))
    return make_section(sid, "KPI", "측정값과 기준값", "".join(body),
                        "숫자는 실험 코드가 남긴 값입니다. 렌더러가 계산한 것은 "
                        "<strong>기준값과의 차이(Δ)와 게이트 판정</strong>뿐입니다.")


def section_figures(figs, sid="s3"):
    if not figs:
        return None
    body = "".join(figs) + h_family_legend()
    return make_section(sid, "시각화", "지표를 그림으로", body,
                        "그림은 이 파일 안에 PNG(base64)·SVG 로 들어 있습니다. "
                        "외부 CDN·웹폰트를 쓰지 않으므로 파일 하나만 열어도 전부 보입니다.")


# 사례 묶음을 나눌 열. 앞에 적은 이름이 먼저다 (axis 보다 case 가 사례 성격에 가깝다).
CASE_TYPE_COLS = ("case_type", "case", "kind", "direction", "label", "type", "axis")


def section_cases(exp_dir, sid="s4"):
    files = _walk_files(exp_dir, lambda n: n.lower().endswith(".csv") and
                        ("case" in n.lower() or "exception" in n.lower()))
    if not files:
        return None
    body = []
    for rel, full in files:
        header, rows, total = read_csv_rows(full)
        if not header:
            continue
        low = [h.strip().lower() for h in header]
        gi = next((low.index(c) for c in CASE_TYPE_COLS if c in low), None)
        # 파일 이름이 반례 목록이면 묶음 이름에 낱말이 없어도 그 성격으로 표시한다
        exc_file = "exception" in rel.lower()
        body.append(f'<h3 style="margin-top:1.6rem">{esc(rel)}'
                    f' <span class="note">{total}행</span></h3>')
        keep = list(range(min(len(header), MAX_CSV_TABLE_COLS)))
        if len(header) > MAX_CSV_TABLE_COLS:
            body.append(f'<p class="note">열 {len(header)}개 중 앞 {MAX_CSV_TABLE_COLS}개만 '
                        '보였습니다. 전체는 CSV 파일에 있습니다.</p>')
        if gi is None:
            body.append(h_table([header[i] for i in keep],
                                [[r[i] if i < len(r) else "" for i in keep]
                                 for r in rows[:MAX_TABLE_ROWS]]))
            if total > MAX_TABLE_ROWS:
                body.append(f'<p class="note">전체 {total}행 중 {MAX_TABLE_ROWS}행만 보였습니다.</p>')
            continue
        groups = {}
        for r in rows:
            groups.setdefault(r[gi] if gi < len(r) else "", []).append(r)
        for gname, grows in groups.items():
            g = str(gname).lower()
            if any(w in g for w in ("rescue", "구제", "개선", "회복")):
                tag = '<span class="tag tag-ok">rescue</span>'
            elif any(w in g for w in ("regress", "퇴행", "악화", "미달")):
                tag = '<span class="tag tag-bad">regression</span>'
            elif any(w in g for w in ("반례", "예외")) or exc_file:
                tag = '<span class="tag tag-bad">반례</span>'
            else:
                tag = '<span class="tag tag-flat">사례</span>'
            cols = [i for i in keep if i != gi]
            body.append(f'<p style="margin-top:1rem">{tag} <strong>{esc(gname)}</strong> '
                        f'<span class="note">{len(grows)}건</span></p>')
            body.append(h_table([header[i] for i in cols],
                                [[r[i] if i < len(r) else "" for i in cols]
                                 for r in grows[:MAX_TABLE_ROWS]]))
            if len(grows) > MAX_TABLE_ROWS:
                body.append(f'<p class="note">이 묶음 {len(grows)}건 중 {MAX_TABLE_ROWS}건만 '
                            '보였습니다.</p>')
    if not body:
        return None
    return make_section(sid, "사례", "rescue / regression 사례", "".join(body),
                        "지표 하나가 아니라 실제로 어떤 향수가 구제되고 어떤 향수가 나빠졌는지를 봅니다. "
                        "파일 이름에 <code>case</code> 또는 <code>exception</code> 이 들어간 CSV 를 "
                        "읽었습니다.")


def section_review(manifest, cards, json_files, sid="s5"):
    body = []
    verdicts = [(c, *gate_verdict(c)) for c in cards]
    fails = [(c, w) for c, v, w in verdicts if v == "FAIL"]
    reviews = [(c, w) for c, v, w in verdicts if v == "REVIEW"]
    passes = [c for c, v, _ in verdicts if v == "PASS"]
    if verdicts:
        body.append('<div class="callout"><p class="h">자동 게이트 판정 요약</p>'
                    f'<p>PASS {len(passes)}개 · REVIEW {len(reviews)}개 · FAIL {len(fails)}개. '
                    'REVIEW 는 사람이 판정해야 하는 항목입니다.</p>'
                    + ("".join(f'<p class="note">REVIEW — <span class="mono">{esc(c["path"])}</span>: '
                               f'{esc(w)}</p>' for c, w in reviews))
                    + ("".join(f'<p class="note">FAIL — <span class="mono">{esc(c["path"])}</span>: '
                               f'{esc(w)}</p>' for c, w in fails))
                    + "</div>")
    # 코드가 남긴 결론·한계·주의 (JSON 에서 뽑아온 그대로)
    memos = []
    for rel, data in json_files:
        for path, node in walk_json(data):
            if isinstance(node, str) and len(node) >= 15:
                leaf = re.split(r"[.\[]", path)[-1]
                if looks_memo(leaf):
                    memos.append((rel, path, node))
    if memos:
        body.append("<h3 style='margin-top:1.8rem'>실험 코드가 남긴 결론·한계</h3>")
        body.append('<p class="note">아래 문장은 JSON 에 적혀 있던 것을 그대로 옮긴 것입니다 '
                    '(렌더러가 요약하거나 고치지 않았습니다).</p>')
        for rel, path, text in memos[:24]:
            body.append(f'<div class="memo"><span class="k">{esc(rel)} · {esc(path)}</span>'
                        f'<p>{esc(text)}</p></div>')
        if len(memos) > 24:
            body.append(f'<p class="note">총 {len(memos)}개 중 24개만 보였습니다.</p>')

    # 사람이 채우는 칸 — 없으면 없다고 표시한다
    slots = [("strengths", "장점 — 이 방법이 실제로 나아진 점"),
             ("risks", "위험 — 나빠질 수 있는 것, 못 재는 것"),
             ("open_questions", "팀이 결정할 질문"),
             ("limitations", "한계")]
    body.append("<h3 style='margin-top:1.8rem'>팀 검토 칸</h3>")
    for key, ko in slots:
        v = manifest.get(key) or (manifest.get("limitation") if key == "limitations" else None)
        if isinstance(v, (list, tuple)) and v:
            items = "".join(f"<p>· {esc(x)}</p>" for x in v)
            body.append(f'<div class="callout"><p class="h">{esc(ko)}</p>{items}</div>')
        elif isinstance(v, str) and v:
            body.append(f'<div class="callout"><p class="h">{esc(ko)}</p><p>{esc(v)}</p></div>')
        else:
            body.append(f'<div class="callout warn"><p class="h">{esc(ko)}</p>'
                        f'<p class="note">manifest.{esc(key)} 가 없습니다. '
                        '렌더러가 대신 쓰지 않습니다 — 사람이 채워야 하는 칸입니다.</p></div>')

    rec = manifest.get("recommendation")
    chips = []
    for opt, note in (("KEEP", "다음 Phase 로 가져간다"),
                      ("REVIEW", "판정 보류 — 사람이 본다"),
                      ("DROP", "쓰지 않는다. 근거는 남긴다")):
        hit = isinstance(rec, str) and opt.lower() in rec.lower()
        tag = {"KEEP": "tag-ok", "REVIEW": "tag-open", "DROP": "tag-bad"}[opt]
        chips.append(f'<p style="margin-top:.4rem">'
                     f'<span class="tag {tag if hit else "tag-flat"}">{opt}</span> '
                     f'<span class="note">{esc(note)}</span>'
                     + (' <strong>← manifest.recommendation</strong>' if hit else "") + "</p>")
    body.append('<div class="callout" style="margin-top:1rem"><p class="h">KEEP / REVIEW / DROP</p>'
                + "".join(chips)
                + (f'<p>{esc(rec)}</p>' if isinstance(rec, str) and rec else
                   '<p class="note">manifest.recommendation 이 없습니다. 위 판정과 사례를 보고 팀이 고릅니다.</p>')
                + "</div>")
    return make_section(sid, "팀 검토", "장점 · 위험 · 결정할 것", "".join(body),
                        "이 절은 결론을 만들어 넣지 않습니다. 자동 판정과 실험 코드가 남긴 문장만 "
                        "모으고, 사람이 채울 칸은 비워 둡니다.")


def section_extra_json(json_files, used_terms, sid="s6"):
    if not json_files:
        return None
    body = []
    for rel, data in json_files:
        inner = []
        render_json_node(data, "", 0, used_terms, inner)
        if not inner:
            continue
        body.append(f'<h3 style="margin-top:2rem">{esc(rel)}</h3>')
        body.append("".join(inner))
    if not body:
        return None
    return make_section(sid, "하위 산출물", "폴더 안의 다른 JSON", "".join(body),
                        "하위 폴더의 JSON 을 재귀로 모아 그대로 표로 옮겼습니다.")


def section_terms(used_terms, sid="s7"):
    terms = [t for t in GLOSSARY if t in used_terms and GLOSSARY[t].get("desc")]
    if not terms:
        return None
    items = "".join(f"<div><dt>{esc(t)}</dt><dd>{esc(GLOSSARY[t]['desc'])}</dd></div>"
                    for t in terms)
    body = f'<dl class="terms">{items}</dl>'
    return make_section(sid, "용어", "이 문서에 나온 지표", body,
                        "이 문서에 실제로 등장한 용어만 모았습니다.")


def section_files(exp_dir, skip=None, sid="s8"):
    """폴더 안 산출물 목록. 보고서 자신(skip)은 빼고 센다."""
    rows = []
    for rel, full in _walk_files(exp_dir, lambda n: not n.startswith(".") and n != skip):
        size = os.path.getsize(full)
        info = ""
        if rel.lower().endswith(".csv"):
            header, _, total = read_csv_rows(full, limit=0)
            info = f"{total}행 · {len(header)}열"
        rows.append([_Raw(f'<span class="mono">{esc(rel)}</span>'), f"{size/1024:.1f} KB", info])
    if not rows:
        return None
    body = h_table(["파일", "크기", "내용"], rows, num_cols={1})
    return make_section(sid, "파일", "이 실험 폴더의 산출물", body,
                        "표에 보이지 않는 값도 이 파일들 안에 있습니다.")


# ══════════════════════════════════════════════════════════════════════════
# 조립
# ══════════════════════════════════════════════════════════════════════════
def _insert_extra(built, extra_sections):
    """실험이 만든 절을 자동 절 사이에 끼운다.

    make_section(..., after="s2") 면 그 sid 뒤에, 같은 anchor 가 여러 개면 준 순서대로
    이어 붙인다. after 가 없으면 맨 끝이다.
    """
    prev = {}
    for s in extra_sections or []:
        anchor = s.get("after")
        if not anchor:
            built.append(s)
            continue
        ref = prev.get(anchor)
        if ref not in built:
            ref = next((b for b in built if b.get("sid") == anchor), None)
        idx = built.index(ref) if ref in built else len(built) - 1
        built.insert(idx + 1, s)
        prev[anchor] = s
    return built


def render(exp_dir, out_path, title=None, extra_sections=None, auto_data_figures=True):
    exp_dir = os.path.abspath(exp_dir)
    if not os.path.isdir(exp_dir):
        raise SystemExit(f"실험 폴더가 없습니다: {exp_dir}")
    exp_rel = os.path.relpath(exp_dir).replace("\\", "/")

    manifest = {}
    mpath = os.path.join(exp_dir, "manifest.json")
    if os.path.exists(mpath):
        manifest = read_json(mpath)
    metrics = {}
    xpath = os.path.join(exp_dir, "metrics.json")
    if os.path.exists(xpath):
        metrics = read_json(xpath)

    # 하위 JSON (manifest/metrics 제외) 재귀 수집
    json_files = []
    for rel, full in _walk_files(exp_dir, lambda n: n.lower().endswith(".json")):
        if rel in ("manifest.json", "metrics.json"):
            continue
        try:
            json_files.append((rel, read_json(full)))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            print(f"  ! JSON 을 읽지 못했습니다: {rel} ({e})")

    used_terms = set()
    cards, declared = collect_cards(metrics, manifest, used_terms) if metrics else ([], False)

    # 재현 검증은 모든 JSON 에서 모은다
    checks = []
    for rel, data in [("metrics.json", metrics)] + json_files:
        if not data:
            continue
        for path, node in walk_json(data):
            if re.split(r"[.\[]", path)[-1] == "reproduction_checks" and isinstance(node, list):
                for c in node:
                    if isinstance(c, dict) and "ok" in c:
                        checks.append((rel, c))

    all_json = ([("metrics.json", metrics)] if metrics else []) + json_files
    figs = build_figures(exp_dir, cards, all_json, auto_data=auto_data_figures)

    built = [
        section_summary(manifest, exp_rel),
        section_kpi(cards, declared, checks),
        section_figures(figs),
        section_cases(exp_dir),
        section_review(manifest, cards, all_json),
        section_extra_json(json_files, used_terms),
        section_terms(used_terms),
        section_files(exp_dir, skip=os.path.basename(out_path)),
    ]
    built = _insert_extra([b for b in built if b], extra_sections)
    for i, s in enumerate(built):
        s["eyebrow"] = f"{CIRCLED[i]} {s['short']}" if i < len(CIRCLED) else s["short"]
    toc = "".join(f'<a href="#{esc(s["sid"])}">{esc(s["eyebrow"])} {esc(s["title"])}</a>'
                  for s in built)
    sections = "".join(h_section(s["sid"], s["eyebrow"], s["title"], s["body"], s["lead"])
                       for s in built)

    exp_id = manifest.get("experiment_id") or os.path.basename(exp_dir)
    headline = title or f"{exp_id} 실험 보고서"
    phase = manifest.get("phase")
    meta = [f"실험 <b>{esc(exp_id)}</b>"]
    if phase is not None:
        meta.append(f"Phase <b>{esc(phase)}</b>")
    if manifest.get("status"):
        meta.append(f"상태 <b>{esc(manifest['status'])}</b>")
    pops = manifest.get("population")
    if pops:
        meta.append("모집단 <b>" + esc(", ".join(pops) if isinstance(pops, list) else pops) + "</b>")
    meta.append(f"폴더 <b>{esc(exp_rel)}</b>")
    meta.append("생성 <b>" + _dt.datetime.now().strftime("%Y-%m-%d %H:%M") + "</b>")

    read_names = ["manifest.json" if manifest else None, "metrics.json" if metrics else None]
    read_names = [r for r in read_names if r] + [r for r, _ in json_files]
    lead = ("이 보고서는 <code>" + esc(exp_rel) + "</code> 의 산출물 파일을 그대로 읽어 만든 것입니다. "
            "지표 값은 실험 코드가 남긴 것이고, 렌더러가 계산한 것은 "
            "<strong>기준값과의 차이(Δ)·게이트 판정·그림</strong>뿐입니다.")

    footer = ("<p>읽은 파일: " + esc(", ".join(read_names) if read_names else "없음") + "</p>"
              f'<p>생성: experiments/_report_template/render_report.py v{RENDERER_VERSION} · '
              + _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S") + "</p>"
              "<p>외부 CDN·웹폰트·스크립트를 쓰지 않습니다. 그림은 base64 PNG 와 인라인 SVG 로 "
              "이 파일 안에 들어 있습니다.</p>")

    with open(TEMPLATE, encoding="utf-8") as f:
        tpl = f.read()
    fam_css = "\n".join(f"  --fam-{f.lower()}:{c};" for f, c in FAMILY_COLORS.items())
    html_out = (tpl
                .replace("{{TITLE}}", esc(headline))
                .replace("{{EYEBROW}}", "향해 · 향 지도 실험 / MAP")
                .replace("{{HEADLINE}}", esc(headline))
                .replace("{{LEAD}}", lead)
                .replace("{{META}}", "".join(f"<span>{m}</span>" for m in meta))
                .replace("{{TOC}}", toc)
                .replace("{{SECTIONS}}", sections)
                .replace("{{FOOTER}}", footer)
                .replace("{{FAMILY_CSS}}", fam_css))
    left = re.findall(r"\{\{[A-Z_]+\}\}", html_out)
    if left:
        print(f"  ! 채우지 못한 자리표시자: {sorted(set(left))}")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html_out)
    return out_path, len(built), len(cards), len(checks), len(figs)


# output/ 과 results/ 는 실험 캠페인의 보호 대상이다. 실수로 쓰지 않게 막는다.
PROTECTED_DIRS = ("output", "results")


def resolve_out(exp_dir, out):
    out = out or "summary.html"
    path = out if os.path.dirname(out) else os.path.join(exp_dir, out)
    path = os.path.abspath(path)
    parts = {p.lower() for p in os.path.normpath(path).split(os.sep)}
    if parts & set(PROTECTED_DIRS):
        raise SystemExit(f"보호 폴더에는 쓰지 않습니다 ({', '.join(PROTECTED_DIRS)}): {path}")
    return path


def main():
    ap = argparse.ArgumentParser(
        description="실험 폴더의 manifest.json / metrics.json / cases.csv 를 읽어 보고서 HTML 을 만든다.")
    ap.add_argument("experiment_dir", help="예: experiments/phase0")
    ap.add_argument("--out", default="summary.html",
                    help="출력 파일. 폴더 없이 적으면 실험 폴더 안에 만든다 (기본 summary.html)")
    ap.add_argument("--title", default=None, help="문서 제목 (기본: <experiment_id> 실험 보고서)")
    a = ap.parse_args()

    out = resolve_out(os.path.abspath(a.experiment_dir), a.out)
    path, nsec, nkpi, nchk, nfig = render(a.experiment_dir, out, a.title)
    size = os.path.getsize(path) / 1024
    print(f"  -> {os.path.relpath(path)}  ({size:.0f} KB)")
    print(f"     섹션 {nsec}개 · KPI 카드 {nkpi}개 · 재현 검증 {nchk}개 · 그림 {nfig}개")


if __name__ == "__main__":
    main()

"""Phase 0 팀 검토 산출물 summary.html 을 만든다 (Phase 0-9).

Run with venv/Scripts/python.exe src/map/experiment_phase0_summary.py

**이 스크립트가 하는 일.** Phase 0-1 ~ 0-8 이 남긴 JSON / CSV 를 읽어 Phase 0 고유의
시각화를 만들고, 공통 렌더러(`experiments/_report_template/render_report.py`)의
절 조립 훅에 끼워 넣는다. HTML 문자열은 여기서 쓰지 않는다 — 표·그림·강조 블록은
전부 렌더러의 조각 만들기 함수(`h_table`, `figure_block`, `h_callout` …)가 만든다
(experiments/README.md 의 "HTML 은 실험 코드가 직접 쓰지 않는다" 규약).

**새 숫자를 만들지 않는다.** 지표는 전부 Phase 0 산출물에서 읽은 실측값이다.
이 스크립트가 계산하는 것은 읽은 값들의 **비율뿐**이고 (예: 라벨률 최대/최소 비,
argmax 변경 건수 / 모집단 크기) 표에 원래의 두 값을 함께 적어 추적할 수 있게 한다.

**읽기 전용.** `output/korea_scent_map_v2.json` 은 회전 전 좌표를 얻기 위해 읽기만 한다.
`results/` 와 `output/` 에는 아무것도 쓰지 않는다.

산출: experiments/phase0/summary.html
"""
import csv
import json
import os
import sys

import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
MAP_DIR = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(MAP_DIR, "experiments", "_report_template"))
import render_report as rr

PHASE0 = os.path.join("experiments", "phase0")
OUT_HTML = os.path.join(PHASE0, "summary.html")
V2_JSON = os.path.join("output", "korea_scent_map_v2.json")   # 읽기만 한다

# 근거별 색 — 계열 색(FAMILY_COLORS)과 겹치지 않는 구조색을 쓴다
BASIS_COLOR = {"WHEEL": rr.FIG_DEEP, "IFRA": rr.FIG_LAND, "NONE": rr.UNMAPPED_COLOR}
BASIS_KO = {"WHEEL": "Fragrance Wheel", "IFRA": "IFRA primary/secondary", "NONE": "미매핑"}
POP_COLOR = {"korea200": rr.FIG_SHOAL, "global1000": rr.FIG_DEEP}
POP_KO = {"korea200": "Korea 200", "global1000": "Global 1,000"}
RULE_KO = {"RuleA_top1_050": "RuleA  top1 >= 0.50",
           "RuleB_margin_010": "RuleB  margin >= 0.10",
           "RuleC_top1_045_margin_008": "RuleC  top1 >= 0.45 & margin >= 0.08"}
RULE_COLOR = {"RuleA_top1_050": rr.FIG_WARN,
              "RuleB_margin_010": rr.FIG_DEEP,
              "RuleC_top1_045_margin_008": rr.FIG_LAND}


# ══════════════════════════════════════════════════════════════════════════
# 읽기
# ══════════════════════════════════════════════════════════════════════════
def rj(*parts):
    with open(os.path.join(PHASE0, *parts), encoding="utf-8") as f:
        return json.load(f)


def rc(*parts):
    with open(os.path.join(PHASE0, *parts), encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def pct(v, digits=1):
    return "—" if v is None else f"{v * 100:.{digits}f}%"


def ratio(hi, lo):
    """최대/최소 비. 최소가 0 이면 나눌 수 없으므로 만들지 않는다."""
    return None if (lo is None or lo <= 0) else hi / lo


def fam_ko(key):
    return rr.FAMILY_KO.get(key, key)


def short(name, n=20):
    s = str(name)
    return s if len(s) <= n else s[:n - 1] + "…"


# ══════════════════════════════════════════════════════════════════════════
# ④ accord -> 계열 매핑 초안
# ══════════════════════════════════════════════════════════════════════════
def section_mapping(meta, rows):
    fams = meta["families"]
    per_family = {}
    per_basis = {}
    for r in rows:
        f = r["proposed_family"]
        per_family[f] = per_family.get(f, 0) + 1
        b = r["family_basis"]
        per_basis[b] = per_basis.get(b, 0) + 1

    body = []

    # ── 계열 정의 표 ──
    order = [f for f in rr.FAMILY_ORDER if f in fams]
    def_rows = []
    for f in order:
        d = fams[f]
        def_rows.append([rr._Raw(rr.h_swatch(rr.FAMILY_COLORS[f], d["ko"])),
                         f, d["basis"], per_family.get(f, 0), d["source"]])
    body.append(rr.h_table(
        ["계열", "키", "근거", "accord 수", "출처"], def_rows,
        caption=f"계열 {meta['family_count']}종 — Fragrance Wheel 7종 + IFRA 2종 "
                f"(family_mapping_draft_meta.json)", num_cols={3}))
    body.append(rr.h_note(
        f"accord {meta['accord_total']}종 중 "
        f"{per_basis.get('WHEEL', 0)}종은 Fragrance Wheel, "
        f"{per_basis.get('IFRA', 0)}종은 IFRA descriptor 로 계열을 정했고 "
        f"{meta['unmapped']}종은 미매핑입니다. 미매핑 accord 의 보유율 합은 "
        f"{meta['unmapped_share_sum']} 입니다."))

    # ── 그림 ② 계열별 accord 수 (근거별 색) ──
    bar = [(f"{fam_ko(f)}  ({f})", per_family.get(f, 0),
            BASIS_COLOR[fams[f]["basis"]]) for f in order]
    bar.append(("미매핑  (UNMAPPED)", per_family.get("UNMAPPED", 0), BASIS_COLOR["NONE"]))
    img = rr.fig_bar_colored(bar, title="계열별 accord 수 — 근거를 색으로 구분",
                             xlabel="accord 수", fmt=lambda v: f"{v:.0f}")
    ifra_fams = [f for f in order if fams[f]["basis"] == "IFRA"]
    body.append(rr.figure_block(
        img,
        " ".join(f"{fam_ko(f)} {per_family.get(f, 0)}종" for f in ifra_fams)
        + "은 Fragrance Wheel 에 대응 계열이 없어 IFRA primary descriptor 로 넣은 "
          "것입니다. 계열 수 7/8/9 결정은 이 두 계열을 유지할지의 문제입니다.",
        source="출처: family_mapping_draft.csv · family_mapping_draft_meta.json"))
    body.append(rr.h_legend([(BASIS_COLOR[k], BASIS_KO[k], k)
                             for k in ("WHEEL", "IFRA", "NONE")]))

    # ── 그림 ① 검토 대상 9종 ──
    rev = [r for r in rows if r["review_required"].strip().lower() == "true"]
    body.append(rr.h_heading(f"검토 대상 accord {meta['review_required']}종 — 팀이 확정해야 한다"))
    body.append(rr.h_note(
        "아래 9종은 계열이 하나로 정해지지 않는 accord 입니다. `alt_families` 가 대안 계열이고 "
        "`review_reason` 이 왜 갈리는지입니다. `human_decision` / `human_family` 열은 "
        "CSV 에 비어 있습니다 — 사람이 채우는 칸입니다."))
    rrows = []
    for r in rev:
        prop = rr.h_swatch(
            rr.FAMILY_COLORS.get(r["proposed_family"], rr.UNMAPPED_COLOR),
            r["proposed_family_ko"])
        alts = " / ".join(fam_ko(a) for a in r["alt_families"].split("|") if a)
        rrows.append([rr._Raw(rr.h_mono(r["accord"])),
                      float(r["perfume_share"]),
                      f'{r["ifra_term"]} · {r["ifra_level"]}' if r["ifra_term"] else "—",
                      rr._Raw(prop), r["family_basis"], alts, r["review_reason"]])
    body.append(rr.h_table(
        ["accord", "보유율", "IFRA", "제안 계열", "근거", "대안 계열 alt_families",
         "쟁점 review_reason"], rrows,
        caption="review_required = True 인 9종", num_cols={1},
        row_classes=["flag"] * len(rrows)))

    # ── 전체 92종 (접어 둠) ──
    all_rows, cls = [], []
    for r in sorted(rows, key=lambda x: -float(x["perfume_share"])):
        flag = r["review_required"].strip().lower() == "true"
        all_rows.append([rr._Raw(rr.h_mono(r["accord"])),
                         float(r["perfume_share"]), int(r["perfume_count"]),
                         r["proposed_family_ko"] or "미매핑", r["family_basis"],
                         "검토 대상" if flag else "", r["rationale"]])
        cls.append("flag" if flag else "")
    body.append(rr.h_details(
        f"accord {len(rows)}종 전체 매핑 초안 (보유율 내림차순)",
        rr.h_table(["accord", "보유율", "보유 향수 수", "제안 계열", "근거", "검토", "근거 문장"],
                   all_rows, num_cols={1, 2}, row_classes=cls)))

    return rr.make_section(
        "fam_map", "계열 매핑", f"accord {meta['accord_total']}종을 {meta['family_count']}계열로",
        "".join(body), after="s3",
        lead=f"매핑 버전 <code>{rr.esc(meta['mapping_version'])}</code> · 상태 "
             f"<strong>{rr.esc(meta['status'])}</strong> · SHA-256 "
             f"<span class=\"mono\">{rr.esc(meta['mapping_sha256'][:16])}…</span>. "
             f"이 매핑은 Family Score·Set B·지도 색칠의 입력이므로 여기가 바뀌면 아래 모든 "
             f"수치가 다시 계산됩니다.")


# ══════════════════════════════════════════════════════════════════════════
# ⑤ Family Score 분포 (top1 · margin)
# ══════════════════════════════════════════════════════════════════════════
def section_score_dist(dist, k_rows, g_rows):
    body = []
    scores = {"korea200": k_rows, "global1000": g_rows}
    top1 = {p: [float(r["fs1_top1"]) for r in rows] for p, rows in scores.items()}
    marg = {p: [float(r["fs1_margin"]) for r in rows] for p, rows in scores.items()}

    # ── 그림 ③ top1 히스토그램 ──
    img = rr.fig_hist(
        [(POP_KO[p], top1[p], f"중앙 {dist[p]['FS1']['top1']['median']} · "
                              f"최대 {dist[p]['FS1']['top1']['max']}")
         for p in ("korea200", "global1000")],
        bins=22, xlabel="top1 Family Score (향수별 합 1 정규화)",
        vlines=[(0.5, "RuleA 기준 0.50")])
    body.append(rr.figure_block(
        img,
        "1위 계열이 향수 하나의 계열 점수 합에서 차지하는 몫입니다. 두 모집단 모두 중앙값이 "
        "0.4 아래입니다 — 대표 향수의 다수는 한 계열이 절반을 넘지 못합니다.",
        source="출처: family_score/scores_korea200.csv · scores_global1000.csv"))
    trows = []
    for th in (">=0.40", ">=0.50", ">=0.60", ">=0.70"):
        r = [th]
        for p, n in (("korea200", 200), ("global1000", 1000)):
            c = dist[p]["FS1"]["coverage"]["top1_thresholds"][th]
            r += [c, pct(c / n)]
        trows.append(r)
    body.append(rr.h_table(
        ["top1 기준", "Korea 200 향수", "비율", "Global 1,000 향수", "비율"], trows,
        caption="top1 기준을 넘는 향수 수 (FS1) — 건수는 실측값, 비율은 건수/모집단",
        num_cols={1, 2, 3, 4}))

    # ── 그림 ④ margin 히스토그램 ──
    body.append(rr.h_heading("margin — 1위 계열과 2위 계열의 점수 차"))
    lo10 = {p: dist[p]["FS1"]["coverage"]["margin_thresholds"]["<0.10"]
            for p in scores}
    img = rr.fig_hist(
        [(POP_KO[p], marg[p],
          f"margin < 0.10 이 {lo10[p]}개 ({pct(lo10[p] / len(scores[p]))})")
         for p in ("korea200", "global1000")],
        bins=22, xlabel="margin = top1 - top2",
        vlines=[(0.10, "RuleB 기준 0.10")], shade=(0.0, 0.10, "margin < 0.10 구간"),
        color=rr.FIG_LAND)
    body.append(rr.figure_block(
        img,
        "붉게 칠한 구간이 margin < 0.10 입니다. 이 구간의 향수는 1위와 2위 계열의 점수가 "
        "거의 같아 어느 계열이라고 부르기 어렵습니다.",
        source="출처: family_score/scores_*.csv · family_score/distribution.json"))
    mrows = []
    for th in ("<0.02", "<0.05", "<0.10"):
        r = [f"margin {th}"]
        for p, n in (("korea200", 200), ("global1000", 1000)):
            c = dist[p]["FS1"]["coverage"]["margin_thresholds"][th]
            r += [c, pct(c / n)]
        mrows.append(r)
    body.append(rr.h_table(
        ["구간", "Korea 200 향수", "비율", "Global 1,000 향수", "비율"], mrows,
        caption="margin 이 작은 향수 수 (FS1) — 건수는 실측값, 비율은 건수/모집단",
        num_cols={1, 2, 3, 4}))
    body.append(rr.h_callout(
        "여기서 읽어야 하는 것",
        [f"Korea 200 은 {lo10['korea200']}개({pct(lo10['korea200'] / 200)}), "
         f"Global 1,000 은 {lo10['global1000']}개({pct(lo10['global1000'] / 1000)})가 "
         "margin < 0.10 입니다.",
         "즉 대표 향수의 40% 이상은 단일 계열 라벨을 붙일 근거가 약합니다. 이것이 아래 "
         "C3 label 규칙에서 커버리지를 포기할지 편중을 감수할지의 문제로 이어집니다."]))

    return rr.make_section(
        "fs_dist", "Family Score 분포", "한 향수가 한 계열에 속하는가",
        "".join(body), after="fam_map",
        lead="FS1 은 accord strength 를 계열별로 합하고 향수별 합을 1 로 정규화한 값입니다 "
             "(<code>fs1_basis</code>). 향수 하나가 여러 계열을 동시에 갖는다는 전제를 "
             "숫자로 확인하는 절입니다.")


# ══════════════════════════════════════════════════════════════════════════
# ⑥ C3 label 규칙 후보 3종
# ══════════════════════════════════════════════════════════════════════════
def section_c3(dist):
    rules = list(RULE_KO)
    body = []

    # ── coverage ──
    img = rr.fig_grouped_bar(
        [RULE_KO[k] for k in rules],
        [(POP_KO[p], [dist[p]["FS1"]["coverage"]["c3_rules"][k]["labeled_share"]
                      for k in rules], POP_COLOR[p])
         for p in ("korea200", "global1000")],
        title="규칙별 coverage — 라벨을 붙일 수 있는 향수 비율 (FS1)",
        xlabel="coverage", fmt=lambda v: f"{v:.3f}", row_h=0.30)
    body.append(rr.figure_block(
        img, "coverage 가 낮으면 지도 위에 이름이 없는 향수가 많아집니다.",
        source="출처: family_score/distribution.json · coverage.c3_rules"))

    crows = []
    for k in rules:
        r = [RULE_KO[k]]
        for p in ("korea200", "global1000"):
            c = dist[p]["FS1"]["coverage"]["c3_rules"][k]
            r += [c["labeled"], pct(c["labeled_share"]), c["unlabeled"]]
        crows.append(r)
    body.append(rr.h_table(
        ["규칙", "Korea 라벨", "coverage", "Korea 미라벨",
         "Global 라벨", "coverage", "Global 미라벨"], crows,
        caption="규칙별 라벨 향수 수 (FS1)", num_cols={1, 2, 3, 4, 5, 6}))

    # ── 계열별 편중 ──
    body.append(rr.h_heading("계열별 label 편중 — 같은 규칙이 계열마다 다르게 작동한다"))
    for p in ("korea200", "global1000"):
        per = {k: dist[p]["FS1"]["coverage"]["c3_rules"][k]["per_family_label_rate"]
               for k in rules}
        fams = [f for f in rr.FAMILY_ORDER if f in per[rules[0]]]
        img = rr.fig_grouped_bar(
            [f"{fam_ko(f)}  ({f})" for f in fams],
            [(RULE_KO[k], [per[k][f] for f in fams], RULE_COLOR[k]) for k in rules],
            title=f"{POP_KO[p]} — 계열별 label rate (규칙 3종)",
            xlabel="그 계열 향수 중 라벨을 받은 비율", fmt=lambda v: f"{v:.3f}",
            row_h=0.235)
        body.append(rr.figure_block(
            img,
            "막대가 계열마다 들쭉날쭉하면 그 규칙은 특정 계열에만 이름을 붙여 줍니다. "
            "RuleA(붉은 막대)와 RuleB(짙은 막대)의 들쭉날쭉함을 비교해 보십시오.",
            source=f"출처: family_score/distribution.json · {p}.FS1.coverage.c3_rules"))

    srows = []
    for p in ("korea200", "global1000"):
        for k in rules:
            c = dist[p]["FS1"]["coverage"]["c3_rules"][k]
            per = c["per_family_label_rate"]
            hi_f = max(per, key=lambda f: per[f])
            lo_f = min(per, key=lambda f: per[f])
            rt = ratio(per[hi_f], per[lo_f])
            zeros = sum(1 for v in per.values() if v == 0)
            srows.append([POP_KO[p], RULE_KO[k], pct(c["labeled_share"]),
                          f"{fam_ko(hi_f)} {pct(per[hi_f])}",
                          f"{fam_ko(lo_f)} {pct(per[lo_f])}",
                          "—" if rt is None else f"{rt:.1f}배", zeros])
    body.append(rr.h_table(
        ["모집단", "규칙", "coverage", "라벨률 최고 계열", "라벨률 최저 계열",
         "최고/최저", "라벨률 0 계열"], srows,
        caption="편중의 크기. coverage 와 계열별 라벨률은 distribution.json 의 실측값이고 "
                "'최고/최저' 는 그 두 값의 비입니다 (최저가 0 이면 나눌 수 없어 — 로 둡니다)",
        num_cols={2, 5, 6}))

    ga = dist["global1000"]["FS1"]["coverage"]["c3_rules"]["RuleA_top1_050"]
    gb = dist["global1000"]["FS1"]["coverage"]["c3_rules"]["RuleB_margin_010"]
    pa, pb = ga["per_family_label_rate"], gb["per_family_label_rate"]
    body.append(rr.h_callout(
        "RuleA 와 RuleB 의 대비 (Global 1,000 · FS1)",
        [f"RuleA(top1 >= 0.50) — coverage {pct(ga['labeled_share'])}. "
         f"구르망 {pct(pa['GOURMAND'])} 대 아쿠아틱 {pct(pa['AQUATIC'])}, "
         f"{ratio(pa['GOURMAND'], pa['AQUATIC']):.1f}배 차이입니다.",
         f"RuleB(margin >= 0.10) — coverage {pct(gb['labeled_share'])}. "
         f"최고 {fam_ko(max(pb, key=lambda f: pb[f]))} {pct(max(pb.values()))} 대 "
         f"최저 {fam_ko(min(pb, key=lambda f: pb[f]))} {pct(min(pb.values()))}, "
         f"{ratio(max(pb.values()), min(pb.values())):.1f}배 차이입니다.",
         "RuleA 는 accord 개수가 적고 강한 구르망에 유리하고, 아쿠아틱처럼 accord 가 "
         "여러 계열에 걸치는 향수에는 거의 이름을 붙이지 않습니다. RuleB 는 coverage 가 "
         "3배 가까이 높으면서 계열 사이 격차가 훨씬 작습니다.",
         "다만 RuleB 는 top1 값 자체를 보지 않으므로 '1위가 낮아도 2위와 벌어져 있으면 "
         "라벨을 준다' 가 됩니다. 그 성질을 받아들일지는 팀 결정입니다."],
        kind="warn"))
    return rr.make_section(
        "c3_rules", "C3 label 규칙", "어느 향수에 계열 이름을 붙일 것인가",
        "".join(body), after="fs_dist",
        lead="후보 3종은 <code>distribution.json</code> 의 <code>_meta.c3_rules</code> 에 "
             "정의돼 있습니다. 판단 기준은 coverage 하나가 아니라 "
             "<strong>coverage 와 계열 편중의 맞바꿈</strong>입니다.")


# ══════════════════════════════════════════════════════════════════════════
# ⑦ FS1 / FS2 민감도
# ══════════════════════════════════════════════════════════════════════════
def section_fs_sensitivity(dist, diff_rows):
    body = []
    n_of = {"korea200": 200, "global1000": 1000}
    diff_n = {p: dist[p]["fs1_fs2_argmax_diff_count"] for p in n_of}

    img = rr.fig_bar_colored(
        [(f"{POP_KO[p]}  ({diff_n[p]}/{n_of[p]})", diff_n[p] / n_of[p], POP_COLOR[p])
         for p in ("korea200", "global1000")],
        title="FS1 -> FS2 에서 1위 계열이 바뀌는 향수 비율",
        xlabel="argmax 가 바뀐 향수 비율", fmt=lambda v: f"{v:.3f}")
    body.append(rr.figure_block(
        img,
        f"Korea 200 은 {diff_n['korea200']}개({pct(diff_n['korea200'] / 200)}), "
        f"Global 1,000 은 {diff_n['global1000']}개({pct(diff_n['global1000'] / 1000)})입니다. "
        "가중치 정의만 바꿨는데 향수 5개 중 1개의 계열 이름이 달라집니다.",
        source="출처: family_score/distribution.json · fs1_fs2_argmax_diff.csv"))

    for p in ("korea200", "global1000"):
        fams = [f for f in rr.FAMILY_ORDER if f in dist[p]["FS1"]["family_count"]]
        img = rr.fig_grouped_bar(
            [f"{fam_ko(f)}  ({f})" for f in fams],
            [("FS1  strength 합", [dist[p]["FS1"]["family_count"][f] for f in fams],
              rr.FIG_DEEP),
             ("FS2  strength x log(1/보유율)",
              [dist[p]["FS2"]["family_count"][f] for f in fams], rr.FIG_LAND)],
            title=f"{POP_KO[p]} — 계열별 argmax 향수 수 (FS1 vs FS2)",
            xlabel="향수 수", fmt=lambda v: f"{v:.0f}", row_h=0.26)
        body.append(rr.figure_block(
            img, "", source=f"출처: family_score/distribution.json · {p}"))

    # 전이 히트맵
    body.append(rr.h_heading("계열이 어디로 옮겨가는가"))
    for p in ("korea200", "global1000"):
        sub = [r for r in diff_rows if r["population"] == p]
        fams = rr.FAMILY_ORDER
        idx = {f: i for i, f in enumerate(fams)}
        m = np.zeros((len(fams), len(fams)))
        for r in sub:
            if r["fs1_argmax"] in idx and r["fs2_argmax"] in idx:
                m[idx[r["fs1_argmax"]], idx[r["fs2_argmax"]]] += 1
        keep_r = [i for i in range(len(fams)) if m[i].sum() > 0]
        keep_c = [j for j in range(len(fams)) if m[:, j].sum() > 0]
        img = rr.fig_heatmap([fam_ko(fams[i]) for i in keep_r],
                             [fam_ko(fams[j]) for j in keep_c],
                             m[np.ix_(keep_r, keep_c)],
                             title=f"{POP_KO[p]} — FS1 계열(행) -> FS2 계열(열) 향수 수",
                             xlabel="FS2 argmax", ylabel="FS1 argmax", cell=0.62)
        if img:
            body.append(rr.figure_block(
                img, f"바뀐 {len(sub)}개 향수만 넣었습니다. 빈 칸은 그 전이가 없었다는 뜻입니다.",
                source="출처: family_score/fs1_fs2_argmax_diff.csv"))

    # 대표 사례
    counts = {}
    for r in diff_rows:
        counts[(r["fs1_argmax"], r["fs2_argmax"])] = \
            counts.get((r["fs1_argmax"], r["fs2_argmax"]), 0) + 1
    top_pairs = sorted(counts, key=lambda k: -counts[k])[:6]
    crows = []
    for a, b in top_pairs:
        ex = [r for r in diff_rows if r["fs1_argmax"] == a and r["fs2_argmax"] == b]
        crows.append([f"{fam_ko(a)} -> {fam_ko(b)}", counts[(a, b)],
                      ", ".join(f'{r["brand"]} {r["name"]}' for r in ex[:2]),
                      ", ".join(sorted({POP_KO[r["population"]] for r in ex}))])
    body.append(rr.h_table(
        ["전이", "건수", "대표 사례 (앞 2개)", "모집단"], crows,
        caption=f"가장 많이 일어난 전이 6종 — 전체 {len(diff_rows)}건 "
                f"(Korea 200 {diff_n['korea200']}건 + Global 1,000 {diff_n['global1000']}건)",
        num_cols={1}))
    body.append(rr.h_callout(
        "FS2 를 채택하자는 뜻이 아니다",
        [f"accord IDF 방향은 이미 기각된 결과가 있습니다 — {dist['_meta']['fs2_rejected_reference']}.",
         f"기본값은 {dist['_meta']['family_score_default']} 이고 FS2 는 민감도 분석 전용입니다 "
         f"({dist['_meta']['fs2_basis']}).",
         "이 절이 보여주는 것은 '계열 라벨이 가중치 정의에 얼마나 민감한가' 이며, "
         "라벨을 UI 에 단정적으로 쓰기 어렵다는 근거입니다."]))
    return rr.make_section(
        "fs_sens", "FS1 / FS2 민감도", "가중치를 바꾸면 계열 이름이 얼마나 흔들리는가",
        "".join(body), after="c3_rules",
        lead="FS1 은 accord strength 를 그대로 합하고, FS2 는 흔한 accord 의 비중을 "
             "<code>log(1/보유율)</code> 로 낮춥니다. 두 정의의 1위 계열이 얼마나 달라지는지 "
             "봅니다.")


# ══════════════════════════════════════════════════════════════════════════
# ⑧ Axis Rotation
# ══════════════════════════════════════════════════════════════════════════
AXIS_KO = {"warmth": "따뜻함 (가을·겨울 투표 - 여름·봄 투표)",
           "nightness": "밤 (밤 투표 - 낮 투표)",
           "masculine": "남성 인식 (남성 투표 - 여성 투표)"}


def section_axis(ax, ids, before_xy, after_xy, fam_of, extremes, exceptions):
    body = []

    # ── 그림 ⑦ 회전 전/후 지도 ──
    ann = []
    for axis, end in (("y", "high"), ("y", "low"), ("x", "high"), ("x", "low")):
        rows = [r for r in extremes if r["axis"] == axis and r["end"] == end]
        for r in rows[:1]:
            ann.append((int(r["fragrantica_id"]), short(r["name"], 22), "end"))
    for r in [r for r in exceptions if r["axis"] == "y"][:3]:
        ann.append((int(r["fragrantica_id"]),
                    f'{short(r["name"], 18)} (반례)', "exception"))

    a = ax["axis_correlation_after"]
    b0 = ax["axis_correlation_before"]
    fig = rr.map_axis_figure(
        [("회전 전 — 축에 이름이 없다", ids, before_xy,
          f'output/korea_scent_map_v2.json 의 x, y\n'
          f'y-warmth rho {b0["warmth"]["y_rho"]:+.4f} · '
          f'x-masculine rho {b0["masculine"]["x_rho"]:+.4f}'),
         (f'회전 후 — {ax["rotation_deg"]}도 회전', ids, after_xy,
          f'axis_rotation/coordinates_rotated.csv\n'
          f'y-warmth rho {a["warmth"]["y_rho"]:+.4f} · '
          f'x-masculine rho {a["masculine"]["x_rho"]:+.4f}')],
        families=fam_of,
        axis_labels={1: {"top": "따뜻함", "bottom": "시원함",
                         "right": "여성 인식", "left": "남성 인식"}},
        annotate={1: ann},
        note="회전 전 좌표는 두 패널을 같은 틀에 놓기 위해 중심만 옮겼습니다 (평행이동도 "
             "거리를 바꾸지 않습니다). 축 이름은 회전 후 상관의 부호를 그대로 읽은 것입니다 — "
             "x-masculine 상관이 음수이므로 오른쪽이 여성 인식입니다. 동그라미는 축 양 끝 "
             "향수, 붉은 동그라미는 반례입니다.",
         source="출처: output/korea_scent_map_v2.json (읽기 전용) · "
                "axis_rotation/coordinates_rotated.csv · extremes.csv · exceptions.csv")
    body.append(fig)
    body.append(rr.h_family_legend())

    # ── 축 상관 표 ──
    b = ax["axis_correlation_before"]
    arows = []
    for name in ("warmth", "nightness", "masculine"):
        arows.append([AXIS_KO[name], ax["vote_availability"][name],
                      b[name]["x_rho"], b[name]["y_rho"],
                      a[name]["x_rho"], a[name]["y_rho"], a[name]["n"]])
    body.append(rr.h_table(
        ["투표 축", "투표 가용 향수", "회전 전 x", "회전 전 y", "회전 후 x", "회전 후 y", "n"],
        arows, caption=f"Spearman 상관 (min_votes = {ax['axis_definition']['min_votes']}). "
                       f"회전은 좌표계 방향만 바꾸므로 상관의 절대 크기가 아니라 "
                       f"'어느 축에 몰리는가' 가 달라집니다",
        num_cols={1, 2, 3, 4, 5, 6}))

    # ── 지표 불변 ──
    body.append(rr.h_heading("회전이 지표를 바꾸지 않는다는 확인"))
    irows = [[r["metric"], f'{r["before"]:.6f}', f'{r["after"]:.6f}',
              f'{r["abs_diff"]:.6f}'] for r in ax["metric_invariance"]]
    body.append(rr.h_table(
        ["지표", "회전 전", "회전 후", "차이"], irows,
        caption=f"소수점 6자리까지 같습니다 (metric_invariant = "
                f"{str(ax['metric_invariant']).lower()}). 2D 회전은 등거리 변환이므로 "
                f"점 사이 거리가 바뀌지 않습니다",
        num_cols={1, 2, 3}))

    # ── 그림 ⑦-b 시드 재현성 ──
    body.append(rr.h_heading("시드를 바꾸면 축이 재현되는가 — Compass UX 채택 조건"))
    sr = ax["seed_reproducibility"]
    seeds = [r["seed"] for r in sr]
    yv = np.array([r["y_warmth_rho"] for r in sr], dtype=float)
    xv = np.array([r["x_masculine_rho"] for r in sr], dtype=float)
    img = rr.fig_series_by_seed(
        seeds,
        [("y축 · 계절(따뜻함) 상관", yv, rr.FIG_WARN),
         ("x축 · 성별 인식 상관 (절대값)", xv, rr.FIG_DEEP)],
        title="같은 유사도 · UMAP 시드만 변경",
        ylabel="Spearman |rho|")
    body.append(rr.figure_block(
        img,
        f"x축(성별 인식)은 평균 {xv.mean():.3f} ± {xv.std():.3f} 로 5개 시드에서 안정적입니다. "
        f"y축(계절)은 평균 {yv.mean():.3f} ± {yv.std():.3f} 로 흔들리며 시드 4 에서 "
        f"{yv.min():.3f} 까지 내려갑니다 — seed 42 값 {yv[0]:.3f} 만 인용하면 과대평가입니다. "
        f"회전각도 {min(r['rotation_deg'] for r in sr)}~"
        f"{max(r['rotation_deg'] for r in sr)}도 사이에서 움직입니다. "
        "평균과 표준편차는 표의 5개 실측값에서 계산한 요약입니다.",
        source="출처: axis_rotation/metrics.json · seed_reproducibility"))
    body.append(rr.h_table(
        ["시드", "회전각(도)", "y · 계절 상관", "x · 성별 인식 상관"],
        [[r["seed"], r["rotation_deg"], r["y_warmth_rho"], r["x_masculine_rho"]]
         for r in sr],
        caption="시드 5개 실측값", num_cols={0, 1, 2, 3}))
    body.append(rr.h_callout(
        "Compass UX 채택 조건과 직결된다",
        [f"x축(성별 인식) {xv.mean():.3f} ± {xv.std():.3f} — 방향을 이름 붙일 근거가 있습니다.",
         f"y축(계절) {yv.mean():.3f} ± {yv.std():.3f} — 시드에 따라 "
         f"{yv.min():.3f} ~ {yv.max():.3f} 로 움직입니다. 지도를 다시 만들 때마다 "
         "위쪽이 '따뜻함' 이라고 말할 수 있는지가 달라집니다.",
         "따라서 두 축에 같은 강도의 UI 문구를 쓸 수 없습니다. y축을 쓰려면 투영을 "
         "고정하거나(시드 고정) 축 표기를 약하게 하는 조건이 필요합니다."],
        kind="warn"))

    # ── 양 끝 향수 ──
    body.append(rr.h_heading("축 양 끝의 향수"))
    for axis, tag, ko in (("y", "high", "y축 위쪽 — 따뜻함 쪽"),
                          ("y", "low", "y축 아래쪽 — 시원함 쪽"),
                          ("x", "high", "x축 오른쪽 — 여성 인식 쪽"),
                          ("x", "low", "x축 왼쪽 — 남성 인식 쪽")):
        rows = [r for r in extremes if r["axis"] == axis and r["end"] == tag]
        tgt = "warmth" if axis == "y" else "masculine"
        body.append(rr.h_table(
            ["브랜드", "향수", "축 좌표", f"{tgt} 투표값"],
            [[r["brand"], r["name"], float(r["axis_value"]),
              float(r[tgt]) if r[tgt] else None] for r in rows],
            caption=ko, num_cols={2, 3}))

    # ── 반례 ──
    body.append(rr.h_heading("반례 — 상관은 경향이고 개별 보장이 아니다"))
    n_y = sum(1 for r in exceptions if r["axis"] == "y")
    n_x = sum(1 for r in exceptions if r["axis"] == "x")
    body.append(rr.h_callout(
        f"exceptions.csv {len(exceptions)}건을 읽는 법",
        [f"뽑은 규칙은 '축 상위 25% 인데 투표는 하위 25%' 입니다 (y축 {n_y}건 · x축 {n_x}건).",
         f"y축 {n_y}건은 y-warmth 상관이 {a['warmth']['y_rho']:+.4f}(양수)이므로 방향과 "
         f"어긋나는 실제 반례입니다 — 위쪽에 있는데 여름·봄 투표가 많은 향수입니다.",
         f"x축 {n_x}건은 x-masculine 상관이 {a['masculine']['x_rho']:+.4f}(음수)입니다. "
         f"오른쪽 = 여성 인식이므로 '오른쪽인데 masculine 값이 낮다' 는 측정된 방향과 "
         f"같은 쪽입니다. 이 {n_x}건을 반례로 읽으려면 축 부호를 반대로 가정해야 합니다 — "
         f"CSV 의 case 문구가 부호를 반영하지 않은 것으로 보이므로 팀이 확인해야 합니다.",
         f"코드가 남긴 한계: {ax['limitation']}"],
        kind="warn"))
    body.append(rr.h_note(f"37건 전체 목록은 아래 사례 절에 있습니다. "
                          f"{ax['not_the_same_as']}"))
    return rr.make_section(
        "axis_rot", "Axis Rotation", "지도의 위·아래·좌·우에 이름을 붙일 수 있는가",
        "".join(body), after="fs_sens",
        lead=f"2D 회전은 점 사이 거리를 바꾸지 않으므로 지표를 손상하지 않고 좌표계를 돌릴 수 "
             f"있습니다. 사용자 투표에 가장 잘 맞는 회전각은 "
             f"<strong>{ax['rotation_deg']}도</strong>였습니다. "
             f"좌표 출처는 <code>{rr.esc(ax['coordinate_source'])}</code> 입니다.")


# ══════════════════════════════════════════════════════════════════════════
# ⑨ Family Set A/B/C
# ══════════════════════════════════════════════════════════════════════════
SET_KO = {"setA": "Set A — Fragrantica 계열 4대 그룹",
          "setB": "Set B — accord 매핑 9계열 (FS1 argmax)",
          "setC": "Set C — 유사도 군집 (계층 군집)"}
SET_COLOR = {"setA": rr.FIG_LAND, "setB": rr.FIG_DEEP, "setC": rr.FIG_SHOAL}


def section_family_sets(fsets):
    body = []
    blocks = [("setA", "korea200", fsets["setA"]["korea200"]),
              ("setA", "global1000", fsets["setA"]["global1000"]),
              ("setB", "korea200", fsets["setB"]["korea200"]),
              ("setB", "global1000", fsets["setB"]["global1000"]),
              ("setC", "korea200", fsets["setC"]["korea200_average"])]

    body.append(rr.h_callout(
        "왜 절대값으로 비교하면 안 되는가",
        [fsets["_meta"]["cohesion_rule"],
         "응집도(2D 최근접 10개 중 같은 계열 비율)는 계열 개수에 민감합니다. 계열이 적으면 "
         "아무렇게나 칠해도 같은 색이 자주 걸립니다.",
         f"Korea 200 실측 — Set A 는 응집도 {fsets['setA']['korea200']['observed_cohesion']} "
         f"이고 Set B 는 {fsets['setB']['korea200']['observed_cohesion']} 입니다. "
         f"절대값만 보면 차이가 작아 보이지만, 무작위 기대값이 각각 "
         f"{fsets['setA']['korea200']['random_expected_cohesion']} 과 "
         f"{fsets['setB']['korea200']['random_expected_cohesion']} 이므로 "
         f"배수로는 {fsets['setA']['korea200']['cohesion_ratio']}배 대 "
         f"{fsets['setB']['korea200']['cohesion_ratio']}배입니다."]))

    # ── 그림 ⑧ 응집도 배수와 절대값 ──
    cats = [f"{SET_KO[s].split(' — ')[0]} · {POP_KO[p]}" for s, p, _ in blocks]
    img = rr.fig_grouped_bar(
        cats,
        [("실측 응집도 (절대값)", [b["observed_cohesion"] for _, _, b in blocks],
          rr.FIG_HAIR),
         ("무작위 기대값", [b["random_expected_cohesion"] for _, _, b in blocks],
          rr.UNMAPPED_COLOR),
         ("무작위 대비 배수", [b["cohesion_ratio"] for _, _, b in blocks], rr.FIG_DEEP)],
        title="응집도는 배수로 비교한다", xlabel="응집도 / 배수",
        fmt=lambda v: f"{v:.3f}", row_h=0.28)
    body.append(rr.figure_block(
        img,
        "회색 두 막대(실측·무작위)는 같은 축의 비율이고 짙은 막대는 그 둘의 비입니다. "
        "실측 응집도만 보면 Set A 와 Set B 의 차이가 작아 보이지만 배수로 보면 2배 이상 "
        "벌어집니다.",
        source="출처: family_sets.json"))

    img = rr.fig_grouped_bar(
        [SET_KO[s].split(" — ")[0] for s in ("setA", "setB")],
        [(POP_KO[p], [fsets[s][p]["coverage"] for s in ("setA", "setB")], POP_COLOR[p])
         for p in ("korea200", "global1000")],
        title="coverage — 계열을 붙일 수 있었던 향수 비율", xlabel="coverage",
        fmt=lambda v: f"{v:.3f}", row_h=0.32)
    body.append(rr.figure_block(
        img,
        f"Set A 는 Korea 200 에서 Fragrantica 계열 표기가 "
        f"{fsets['setA']['korea200']['unclassified']}개 결측이라 coverage "
        f"{fsets['setA']['korea200']['coverage']} 입니다. 결측은 accord 로 추측해 채우지 "
        f"않고 UNCLASSIFIED 로 두었고, 응집도는 분류된 "
        f"{fsets['setA']['korea200']['n_classified']}개에서만 계산했습니다.",
        source="출처: family_sets.json"))

    srows = []
    for s, p, b in blocks:
        srows.append([SET_KO[s], POP_KO[p], b["family_count"], b["coverage"],
                      b["n_classified"], b["observed_cohesion"],
                      b["random_expected_cohesion"], b["cohesion_ratio"]])
    body.append(rr.h_table(
        ["Set", "모집단", "계열 수", "coverage", "분류 향수", "실측 응집도",
         "무작위 기대값", "배수"], srows,
        caption="전부 family_sets.json 의 실측값입니다 (배수도 실험 코드가 낸 "
                "cohesion_ratio 를 그대로 옮겼습니다)",
        num_cols={2, 3, 4, 5, 6, 7}))

    c = fsets["setC"]
    body.append(rr.h_heading("Set C — 자연 군집으로 주장할 수 있는가"))
    body.append(rr.h_table(
        ["연결 방식", "군집 수 k", "silhouette", "군집 크기"],
        [[k, v["k"], v["silhouette"], ", ".join(str(x) for x in v["sizes"])]
         for k, v in c["recomputed"].items()],
        caption=f"상태 {c['status']} — 기존 결과를 다시 계산해 일치를 확인했습니다",
        num_cols={1, 2}))
    body.append(rr.h_callout("실험 코드가 남긴 결론", c["note"], kind="warn"))
    body.append(rr.h_details(
        "계열별 응집도 (Set B)",
        "".join(
            rr.h_table(["계열", "향수 수", "응집도"],
                       [[fam_ko(f), fsets["setB"][p]["sizes"][f],
                         fsets["setB"][p]["per_family_cohesion"][f]]
                        for f in rr.FAMILY_ORDER
                        if f in fsets["setB"][p]["per_family_cohesion"]],
                       caption=POP_KO[p], num_cols={1, 2})
            for p in ("korea200", "global1000"))))
    return rr.make_section(
        "fam_sets", "Family Set A/B/C", "어떤 계열 정의가 지도에서 실제로 뭉치는가",
        "".join(body), after="axis_rot",
        lead="세 가지 계열 정의를 같은 좌표 위에서 비교합니다. 좌표는 "
             f"<code>{rr.esc(fsets['_meta']['coordinate_source'])}</code> 이고 "
             f"{rr.esc(fsets['_meta']['phase3a_note'])}.")


# ══════════════════════════════════════════════════════════════════════════
# ⑮ 팀 결정 대기 항목 5개
# ══════════════════════════════════════════════════════════════════════════
def section_decisions(meta, dist, fsets, ax, metrics, manifest, map_rows, exceptions):
    n_accord = {}
    for r in map_rows:
        n_accord[r["proposed_family"]] = n_accord.get(r["proposed_family"], 0) + 1
    n_exc = len(exceptions)
    n_exc_y = sum(1 for r in exceptions if r["axis"] == "y")
    d_ga = dist["global1000"]["FS1"]["coverage"]["c3_rules"]
    pa = d_ga["RuleA_top1_050"]["per_family_label_rate"]
    k10 = dist["korea200"]["FS1"]["coverage"]["margin_thresholds"]["<0.10"]
    g10 = dist["global1000"]["FS1"]["coverage"]["margin_thresholds"]["<0.10"]
    sr = ax["seed_reproducibility"]
    yv = np.array([r["y_warmth_rho"] for r in sr], dtype=float)
    xv = np.array([r["x_masculine_rho"] for r in sr], dtype=float)
    kt = metrics["korea200"]["layout_seeds"]["trust@10"]

    items = [
        ("①", "accord -> 계열 매핑 9종 확정",
         f"검토 대상 {meta['review_required']}종 (powdery, vanilla, fresh, leather, iris, "
         f"smoky, lactonic, aldehydic, honey)",
         [f"각 accord 마다 제안 계열과 대안 계열이 갈립니다. 예: vanilla 는 제안 구르망 / "
          f"대안 앰버, powdery 는 제안 머스크·파우더리 / 대안 플로럴입니다.",
          f"powdery 는 보유율 47.7% 로 계열이라기보다 배경에 가깝습니다 — 계열로 쓸지 자체가 "
          f"쟁점입니다.",
          f"현재 상태는 {meta['status']} 이고 매핑 SHA-256 은 "
          f"{meta['mapping_sha256'][:16]}… 입니다."],
         "이 매핑이 Family Score · Set B · 지도 색칠의 입력입니다. 바뀌면 아래 ②③ 의 모든 "
         "수치를 다시 계산해야 합니다.",
         "family_mapping_draft.csv 의 human_decision / human_family / human_note 열이 "
         "비어 있습니다"),

        ("②", "계열 개수 7 / 8 / 9",
         "9 (현재 초안) · 8 (Gourmand 또는 Musk 제거) · 7 (Fragrance Wheel 만)",
         [f"구르망(accord {n_accord.get('GOURMAND', 0)}종)과 "
          f"머스크·파우더리(accord {n_accord.get('MUSK', 0)}종)는 Fragrance Wheel 에 대응 "
          f"계열이 없고 IFRA primary descriptor 로 넣은 것입니다.",
          f"9계열(Set B)의 무작위 대비 응집도는 Korea 200 "
          f"{fsets['setB']['korea200']['cohesion_ratio']}배 · Global 1,000 "
          f"{fsets['setB']['global1000']['cohesion_ratio']}배이고, "
          f"4그룹(Set A)은 {fsets['setA']['korea200']['cohesion_ratio']}배 · "
          f"{fsets['setA']['global1000']['cohesion_ratio']}배입니다.",
          f"Korea 200 에서 프루티는 향수 "
          f"{fsets['setB']['korea200']['sizes']['FRUITY']}개뿐이고 아쿠아틱은 "
          f"{fsets['setB']['korea200']['sizes']['AQUATIC']}개입니다 — 계열이 늘면 작은 계열이 "
          f"생깁니다."],
         "계열 수가 응집도의 무작위 기대값을 바꿉니다. 개수를 바꾸면 Set 비교를 다시 "
         "정규화해야 합니다.",
         "9계열 초안으로 모든 Phase 0 수치를 냈습니다. 7 또는 8 로 바꾸면 재계산 대상입니다"),

        ("③", "C3 label 규칙 1종",
         "RuleA top1 >= 0.50 · RuleB margin >= 0.10 · RuleC top1 >= 0.45 & margin >= 0.08",
         [f"Global 1,000 · FS1 기준 coverage 는 RuleA "
          f"{pct(d_ga['RuleA_top1_050']['labeled_share'])} · RuleB "
          f"{pct(d_ga['RuleB_margin_010']['labeled_share'])} · RuleC "
          f"{pct(d_ga['RuleC_top1_045_margin_008']['labeled_share'])} 입니다.",
          f"RuleA 는 계열 편중이 큽니다 — 구르망 {pct(pa['GOURMAND'])} 대 아쿠아틱 "
          f"{pct(pa['AQUATIC'])} 로 {ratio(pa['GOURMAND'], pa['AQUATIC']):.1f}배입니다.",
          f"애초에 margin < 0.10 인 향수가 Korea 200 {k10}개({pct(k10 / 200)}) · "
          f"Global 1,000 {g10}개({pct(g10 / 1000)}) 이므로 어떤 규칙을 골라도 상당수는 "
          f"이름이 없습니다."],
         "지도에 계열 이름을 몇 개 띄울지, 이름 없는 향수를 어떻게 보여줄지가 여기서 "
         "결정됩니다.",
         "규칙 3종의 coverage 와 계열별 라벨률은 측정했고 어느 것을 쓸지는 미정입니다"),

        ("④", "Gate B 를 어느 모집단에서 잴 것인가",
         f"Korea 200 {manifest['baseline_reference']['korea200_trust10_seed_mean']} "
         f"(5시드 평균) vs Global 1,000 "
         f"{manifest['baseline_reference']['global1000_trust10_seed42']} (seed 42)",
         ["Gate B 는 trustworthiness@10 >= 0.90 이고 기준값이 모집단마다 다릅니다.",
          f"Korea 200 은 5시드 평균 {kt['mean']} ± {kt['std']} (최소 {kt['min']} · "
          f"최대 {kt['max']}) 이고, 게이트 0.90 과의 여유가 "
          f"{kt['min'] - 0.90:.4f} 입니다.",
          f"Global 1,000 은 seed 42 단독 "
          f"{metrics['global1000']['layout_seed42']['trust@10']['seed42']} 이고 시드를 여러 개 "
          f"돌린 값이 없습니다.",
          f"Korea 200 의 신뢰 간선은 {metrics['korea200']['trusted_edges']}쌍 / 보유 향수 "
          f"{metrics['korea200']['trusted_nodes']}개뿐이고, Global 1,000 은 "
          f"{metrics['global1000']['trusted_edges']}쌍(cross-family "
          f"{metrics['global1000']['cross_family_trusted_edges']}쌍)입니다 — 채점 근거의 "
          f"양이 다릅니다."],
         "게이트 판정 자체가 달라집니다. 모집단을 적지 않은 trust 값은 캠페인 규약상 "
         "쓸 수 없습니다 (experiments/README.md).",
         "manifest 의 population 에 세 모집단이 모두 들어 있고 Gate B 의 판정 모집단은 "
         "지정되지 않았습니다"),

        ("⑤", "방향성(Axis / Compass)이 최종 UX 에 필수인가",
         "필수 (축 이름을 UI 에 노출) · 보조 (탐색 힌트로만) · 사용하지 않음",
         [f"x축 성별 인식은 5시드 평균 {xv.mean():.3f} ± {xv.std():.3f} 로 안정적입니다.",
          f"y축 계절(따뜻함)은 {yv.mean():.3f} ± {yv.std():.3f} 이고 시드에 따라 "
          f"{yv.min():.3f} ~ {yv.max():.3f} 로 움직입니다.",
          f"회전각도 시드에 따라 {min(r['rotation_deg'] for r in sr)}~"
          f"{max(r['rotation_deg'] for r in sr)}도 사이입니다.",
          f"축을 만들 투표가 있는 향수는 계절 {ax['vote_availability']['warmth']}개 · "
          f"성별 인식 {ax['vote_availability']['masculine']}개입니다 (200개 중, "
          f"최소 {ax['axis_definition']['min_votes']}표 기준).",
          f"exceptions.csv 에 반례 {n_exc}건(y축 {n_exc_y}건 · x축 {n_exc - n_exc_y}건)이 "
          f"기록돼 있습니다 — 상관 0.4~0.75 는 경향이고 개별 향수 보장이 아닙니다.",
          f"지표는 회전으로 바뀌지 않으므로(소수점 6자리 불변) '쓰지 않기로 해도 손해가 "
          f"없다' 는 성질이 있습니다."],
         "필수로 정하면 Phase 2 투영 선택에 '축 재현성' 이라는 조건이 하나 더 붙습니다. "
         "보조로 정하면 투영은 지표만으로 고를 수 있습니다.",
         "축이 존재한다는 것은 측정했고, UX 에 쓸지는 미정입니다"),
    ]

    body = [rr.h_table(
        ["#", "결정할 것", "후보", "지금 상태"],
        [[n, t, cand, status] for n, t, cand, _, _, status in items],
        caption="Phase 0 이 측정을 끝냈지만 사람이 골라야 하는 항목")]
    for n, t, cand, basis, impact, status in items:
        body.append(rr.h_heading(f"{n} {t}"))
        body.append(rr.h_table(
            ["항목", "내용"],
            [["후보", cand], ["실측 근거", rr._Raw(rr.h_bullets(basis))],
             ["무엇에 영향을 주는가", impact], ["지금 상태", status]],
            css_first_key=True))
    body.append(rr.h_callout(
        "이 다섯 개를 정하지 않으면 막히는 일",
        ["①②③ 은 Family Score 와 Set B 의 정의를 바꾸므로 Phase 1(유사도)·Phase 3a(계열 "
         "영역)의 입력이 흔들립니다.",
         "④ 는 Phase 1·2 의 게이트 판정 모집단이므로 실험을 시작하기 전에 정해야 합니다.",
         "⑤ 는 Phase 2 투영 후보를 고르는 조건 개수를 바꿉니다.",
         f"재현 게이트는 사전 확인이 "
         f"'{manifest['reproduction_gate_result']['pre_phase0']}' 이고 사후 확인이 "
         f"'{manifest['reproduction_gate_result']['post_phase0']}' 입니다."],
        kind="warn"))
    return rr.make_section(
        "decisions", "팀 결정 대기", "무엇이 정해졌고 무엇을 정해야 하는가",
        "".join(body),
        lead="위 절의 수치는 전부 측정된 값입니다. 이 절의 5개는 <strong>측정으로 "
             "정해지지 않는 선택</strong>이며 팀이 골라야 합니다. 각 항목에 후보와 실측 "
             "근거, 그리고 정하지 않으면 무엇이 막히는지를 함께 적었습니다.")


# ══════════════════════════════════════════════════════════════════════════
def main() -> None:
    os.chdir(MAP_DIR)

    print("=" * 78)
    print("Phase 0-9 — 팀 검토 산출물 summary.html")
    print("=" * 78)

    manifest = rj("manifest.json")
    metrics = rj("metrics.json")
    meta = rj("family_mapping_draft_meta.json")
    dist = rj("family_score", "distribution.json")
    fsets = rj("family_sets.json")
    ax = rj("axis_rotation", "metrics.json")

    map_rows = rc("family_mapping_draft.csv")
    k_rows = rc("family_score", "scores_korea200.csv")
    g_rows = rc("family_score", "scores_global1000.csv")
    diff_rows = rc("family_score", "fs1_fs2_argmax_diff.csv")
    extremes = rc("axis_rotation", "extremes.csv")
    exceptions = rc("axis_rotation", "exceptions.csv")
    rot_rows = rc("axis_rotation", "coordinates_rotated.csv")

    print(f"읽은 산출물 — accord 매핑 {len(map_rows)}행 · Korea 점수 {len(k_rows)}행 · "
          f"Global 점수 {len(g_rows)}행 · FS 차이 {len(diff_rows)}행")
    print(f"             축 양끝 {len(extremes)}행 · 반례 {len(exceptions)}행 · "
          f"회전 좌표 {len(rot_rows)}행")

    # 회전 전 좌표 — output/ 은 읽기만 한다
    with open(V2_JSON, encoding="utf-8") as f:
        v2 = json.load(f)
    by_id = {p["fragrantica_id"]: (p["x"], p["y"]) for p in v2["points"]}
    ids = [int(r["fragrantica_id"]) for r in rot_rows]
    missing = [i for i in ids if i not in by_id]
    if missing:
        raise SystemExit(f"회전 전 좌표를 찾을 수 없는 향수 {len(missing)}개: {missing[:5]}")
    before = np.array([by_id[i] for i in ids], dtype=float)
    before = before - before.mean(axis=0)          # 평행이동만 (거리 불변)
    after = np.array([[float(r["x_rot"]), float(r["y_rot"])] for r in rot_rows])
    d_before = np.linalg.norm(before[:, None] - before[None], axis=2)
    d_after = np.linalg.norm(after[:, None] - after[None], axis=2)
    print(f"회전 전/후 쌍거리 최대 차이 {np.abs(d_before - d_after).max():.2e} "
          f"(회전이 등거리 변환임을 이 스크립트에서도 확인)")

    fam_of = {int(r["fragrantica_id"]): r["fs1_argmax"] for r in k_rows}

    sections = [
        section_mapping(meta, map_rows),
        section_score_dist(dist, k_rows, g_rows),
        section_c3(dist),
        section_fs_sensitivity(dist, diff_rows),
        section_axis(ax, ids, before, after, fam_of, extremes, exceptions),
        section_family_sets(fsets),
        section_decisions(meta, dist, fsets, ax, metrics, manifest, map_rows,
                          exceptions),
    ]
    print(f"Phase 0 고유 절 {len(sections)}개를 렌더러에 넘깁니다")

    path, nsec, nkpi, nchk, nfig = rr.render(
        PHASE0, os.path.abspath(OUT_HTML),
        title="Phase 0 — 실험 기반 고정 결과와 팀 결정 대기 항목",
        extra_sections=sections, auto_data_figures=False)
    size = os.path.getsize(path) / 1024
    print(f"\n  -> {os.path.relpath(path)}  ({size:.0f} KB)")
    print(f"     섹션 {nsec}개 · KPI 카드 {nkpi}개 · 재현 검증 {nchk}개 · "
          f"자동 그림 {nfig}개 + Phase 0 절 안의 그림")


if __name__ == "__main__":
    main()

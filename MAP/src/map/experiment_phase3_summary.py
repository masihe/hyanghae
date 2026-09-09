"""Phase 3 팀 검토용 summary.html — 3a(계열 정의) + 3b(Territory) + 최종 후보.

Run with venv/Scripts/python.exe src/map/experiment_phase3_summary.py

산출: experiments/phase3/summary.html
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
import experiment_phase0_family_mapping as fm

PHASE3 = os.path.join("experiments", "phase3")
P3A = os.path.join("experiments", "phase3a")
P3B = os.path.join("experiments", "phase3b")
SET_KO = {"SetA": "Set A — Fragrantica 4대 그룹", "SetB": "Set B — accord 기반 9계열",
          "SetC": "Set C — Data-driven 군집"}


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


def section_setup(a):
    body = f"""
<p>Phase 3 는 두 전제를 팀 결정으로 고정한 뒤 시작했다.</p>
{tbl(["결정", "내용", "근거"],
     [["기준 투영", "<b>UMAP seed 42</b>",
       "모든 지표에서 최고이기 때문이 아니라 국소/전역 균형과 안정성, 기존 파이프라인 연결"],
      ["하위 산출물", "재생성하지 않는다",
       "Territory 후보를 먼저 줄인 뒤 TriMap-dist 로 재검증하고, 사용자 가치가 실제로 개선될 때만 전체 재생성"],
      ["t-SNE", "메인 투영 제외",
       "국소 보존은 1위지만 거리·방향·영역 해석과 충돌. 향수 상세의 주변 유사 향수 연구 후보로만"],
      ["안정성", "Hard Gate 아님 — 기록/검토 지표",
       "최종 서비스는 스냅샷·파라미터·시드·좌표를 고정한다. 후보는 시드 5개에서 구조 붕괴만 확인"]])}
<p><b>유사도는 Phase 1 결과대로 baseline 이다</b> — A8 / A7 / A2 가 전부 baseline 을 넘지
못해 신규 후보가 0개였다.</p>
"""
    return rr.make_section("p3a0", "설정", "Phase 3 의 전제", body, after="s1")


def section_definition(a):
    rows = []
    for pop in ("korea200", "global1000"):
        for s in ("SetA", "SetB", "SetC"):
            b = a[pop][s]
            if not b.get("ok"):
                continue
            cf = b["cross_family"]
            rows.append([f"<b>{rr.esc(s)}</b>", "Korea 200" if pop == "korea200" else "Global 1,000",
                         b["family_count"], f'{b["coverage"]:.1%}',
                         f'{b["observed_cohesion"]:.3f}',
                         f'{b["random_expected_cohesion"]:.3f}',
                         f'<b>{b["cohesion_ratio"]:.3f}</b>',
                         f'{b["neighborhood_purity"]["mean_top_family_share"]:.3f}',
                         f'{b["size_max_share"]:.1%}',
                         f'{cf.get("cross_family_proximity", float("nan")):.4f}'])
    seed_rows = [[f"<b>{s}</b>",
                  f'{a["korea200"][s]["seed_check"]["mean"]:.3f} ± '
                  f'{a["korea200"][s]["seed_check"]["std"]:.3f}',
                  f'{a["korea200"][s]["seed_check"]["min"]:.3f}',
                  "없음" if not a["korea200"][s]["seed_check"]["collapsed"] else "있음"]
                 for s in ("SetA", "SetB", "SetC") if a["korea200"][s].get("seed_check")]
    fc = a["_meta"]["set_b_family_count_reference"]
    cnt_rows = [[f"<b>{k}</b>", f'{v["cohesion_ratio_korea"]:.3f}',
                 f'{v["cohesion_ratio_global"]:.3f}'] for k in ("9", "8A", "8B", "7")
                for v in [fc[k]]]
    body = f"""
<p>같은 좌표(UMAP seed 42)에서 계열 정의 3종을 비교했다. <b>계열 수가 다르면 응집도 절대값을
비교할 수 없으므로</b> <code>observed / random expected</code> 비율로 본다.</p>
{tbl(["정의", "모집단", "계열", "coverage", "observed", "무작위 기대", "ratio",
      "이웃 최다 점유", "최대 비중", "계열 횡단 근접도"], rows)}
{tbl(["정의", "시드 5개 ratio", "최소", "구조 붕괴"], seed_rows,
     note="안정성은 Hard Gate 가 아니다(팀 결정). 셋 다 구조 붕괴는 없었다.")}
<h3>Set A 는 탈락 — 영역이 읽히지 않는다</h3>
<p>정규화 응집도가 Korea 1.619 · Global 1.486 으로 <b>무작위보다 1.5배 수준</b>이다.
게다가 Korea 200 에서 16개(8%)가 결측이라 색을 칠할 수 없다.</p>
<h3>Set B 와 Set C 는 응집도가 사실상 동률이다 — 그런데 Set C 의 수치는 순환적이다</h3>
<p>Global 1,000 에서 Set B 4.187 · Set C 4.162 로 차이가 0.025 다. 이웃 최다 점유율은
Set C 가 오히려 높다(0.856 vs 0.748).</p>
<p class="warn"><b>Set C 의 높은 점수는 부분적으로 순환이다.</b> Set C 의 군집은 좌표를 만든
것과 <b>같은 거리행렬</b>에서 나온다. "내 이웃이 같은 군집인가" 를 재면 당연히 높게 나온다.
반면 Set B 는 accord 매핑이라는 <b>외부 근거</b>에서 나온 라벨이고, 그 라벨이 좌표와 4.19배
일치하는 것은 순환이 아니다.</p>
<p>그리고 Set C 는 세 가지가 더 걸린다.</p>
<ul>
<li><b>이름을 붙일 수 없다.</b> 군집이 <code>c0..c6</code> 이고 silhouette 이 0.056~0.076 이라
자연 계열로 주장할 수 없다 (v4 12). 사용자에게 "우디 구역" 이라고 말할 근거가 없다</li>
<li><b>모집단마다 계열 수가 바뀐다.</b> Korea 200 에서 k=7, Global 1,000 에서 k=9 로 규칙이
다르게 고른다. <code>build_korea_terrain.py</code> 에 같은 실패가 기록돼 있다 —
잠정 200개에서 고른 k=4 가 새 200개에서 [176,15,5,4] 로 무너졌다</li>
<li><b>계열 횡단 근접도가 가장 나쁘다</b> (Korea 0.3749 · Global 0.3668 vs Set B 0.2402/0.2615).
사람이 닮았다고 한 쌍이 Set C 경계를 넘을 때 지도에서도 멀다</li>
</ul>
<h3>Set B 내부의 계열 수는 별도 실험에서 이미 비교했다</h3>
{tbl(["계열 수", "ratio (Korea)", "ratio (Global)"], cnt_rows,
     note="출처: experiments/phase0_family_count_comparison/. 9계열이 두 모집단 모두 1위이고, 계열을 줄이면 1순위 accord 와 다른 계열에 배정되는 향수가 31.9% → 44.5% 로 늘었다.")}
<p><b>Phase 3b 는 Set B(9계열)로 진행했다.</b> 최종 확정은 팀 결정이다.</p>
"""
    return rr.make_section("p3a1", "3a 계열 정의", "어떤 정의로 영역을 만들 것인가",
                           body, after="p3a0")


def section_maps(coord_rows):
    fam_of = {}
    panels = []
    methods = []
    for r in coord_rows:
        methods.append(r["method"])
    seen = []
    for mth in methods:
        if mth not in seen:
            seen.append(mth)
    for mth in seen:
        rows = [r for r in coord_rows if r["method"] == mth]
        ids = [int(r["fragrantica_id"]) for r in rows]
        xy = np.array([[float(r["x"]), float(r["y"])] for r in rows])
        for r in rows:
            fam_of[int(r["fragrantica_id"])] = r["family"]
        panels.append((mth, ids, xy))
    blocks = []
    for chunk in (panels[:3], panels[3:]):
        if chunk:
            blocks.append(rr.map_compare_figure(
                chunk, families=fam_of, align_to_first=True,
                source="coordinates_korea200.csv", point_size=13))
    body = f"""
<p>Korea 200 · Set B 9계열 색칠. 좌표가 방식마다 다르므로 회전·반사 정렬해 모양을 비교한다.</p>
{"".join(blocks)}
<p class="note"><b>C1 post-hoc</b> 은 좌표를 바꾸지 않는다(현재 출하 좌표). 나머지는 좌표를
움직인 결과다. <b>지표는 정렬 전 좌표로 계산했다.</b></p>
"""
    return rr.make_section("p3b0", "3b 지도", "영역 표현 방식별 지도", body, after="p3a1")


def section_gate_a(b):
    ga = b["gate_a"]
    rows = []
    for name, g in b["global1000"].items():
        gr = g["guardrail"]
        rows.append([f"<b>{rr.esc(name)}</b>",
                     f'{gr.get("cross_family_proximity", float("nan")):.4f}',
                     f'{g["gate_a_delta"]:+.4f}',
                     f'{gr.get("same_family_proximity", float("nan")):.4f}',
                     f'{g["layout"]["trust@10"]:.4f}',
                     f'{g["readability"]["cohesion_ratio"]:.3f}',
                     f'<b>{g["gate_a"]}</b>'])
    body = f"""
<p>이 지표가 향 지도의 원래 주장이다 — <b>계열이 달라도 사람이 비슷하다고 평가한 향수를
억지로 멀리 밀어내지 않는다.</b> Global 1,000 에 {ga["cross_pairs"]}쌍이 있다.</p>
<p><code>Gate A</code> = 계열 횡단 신뢰 쌍 근접도 ≤ baseline + 0.05 =
<b>{ga["baseline_cross_family_proximity"]} + 0.05 = {ga["pass_line"]}</b></p>
{tbl(["방식", "횡단 근접도", "Δ", "동일계열 근접도", "trust@10", "영역 ratio", "Gate A"], rows,
     note="Korea 200 은 계열 횡단 쌍이 25쌍뿐이라 판정에 쓰지 않았다 (v4 24).")}
<h3>D9 의 실패가 계열 라벨에서도 똑같이 재현됐다</h3>
<p class="warn"><b>C2 supervised UMAP 이 전 가중에서 탈락했다</b> — 0.4495 ~ 0.5748 로
무작위(0.5) 수준이거나 그보다 나쁘다. D9 는 k=12 군집 라벨로 같은 실험을 해서
0.363 → 0.52~0.56 을 얻었다. <b>라벨을 계열로 바꿔도 실패 구조가 같다.</b></p>
<p>얻는 것은 크다 — 영역 ratio 가 4.187 → 6.6~6.7 로 오르고 Korea 이웃 최다 점유율이
0.97~0.98 이 된다. 그런데 그 대가가 정확히 "사람이 닮았다고 한 향수를 갈라놓는 것" 이다.
<b>C4 fixed+local(+0.2777)과 C6 anchor+local(+0.3140)도 같은 이유로 탈락했다.</b></p>
<p class="note">반대로 <b>C8a(−0.0751)와 C8b(−0.0342)는 이 지표를 개선한다.</b> 영역을
나누면서 사람 판단과 더 가까워지는 방식이 존재한다는 뜻이다.</p>
"""
    return rr.make_section("p3b1", "Gate A", "닮았다고 한 향수를 갈라놓지 않는가",
                           body, after="p3b0")


def section_finalists(f):
    rows = []
    for c in f["candidates"]:
        rows.append([f"<b>{rr.esc(c['candidate'])}</b>",
                     f'{c["gate_a_delta"]:+.4f}',
                     f'{c["gate_b_trust10_global"]:.4f}',
                     "○" if c["passes_both"] else "✕",
                     f'{c["axis1_cohesion_ratio_korea"]:.3f}',
                     f'{c["axis2_shared_rare_accord_ge1"]:.1%}',
                     c["axis2_nearest_unexplained"],
                     f'{c["axis3_y_warmth_rho"]:.3f}',
                     f'{c["axis3_x_masculine_rho"]:.3f}',
                     "○" if c["candidate"] in f["pareto_front"] else "—"])
    body = f"""
<p><b>Gate A 만으로는 부족했다.</b> C5 wheel anchor 는 Gate A 를 통과하지만(+0.0403)
trust@10 이 0.7068 이다 — "옆에 있는 게 비슷하다" 는 기본 약속을 못 지킨다. 그래서 v4 34 의
계층을 그대로 적용했다.</p>
<pre>통과 게이트   Gate A  계열 횡단 신뢰 쌍 근접도 ≤ {f["gate_a"]["pass_line"]}
             Gate B  trustworthiness@10 ≥ {f["gate_b"]["threshold"]}
비교 축       ① 영역 이해   ② 설명 가능성(고정 시험지)   ③ 방향성
기록 축       안정성 · 조각 수 · 정답간선 · 구현 복잡도</pre>
{tbl(["후보", "Gate A Δ", "Gate B trust@10", "통과", "① 영역 이해",
      "② 공통 rare accord", "설명 불가 향수", "③ y=계절", "③ x=성별", "Pareto"], rows,
     note="설명 가능성은 고정 시험지다 — 원본 note 문자열과 원본 accord(보유율<0.30)의 공통 개수로만 잰다. 방식이 무엇이든 기준을 바꾸지 않는다. 방향성은 회전 정렬 후 상관이며 회전은 등거리 변환이라 다른 지표를 바꾸지 않는다.")}
<p><b>두 게이트를 모두 통과한 것은 5개</b>이고, 비교축 3개 Pareto 로 <b>{" · ".join(f["pareto_front"])}</b>
두 개가 남았다.</p>
<p class="note">정직하게 적어둘 것 — C8a 가 Pareto 에 남은 이유는 방향성 축에서 C8b 를
0.535 vs 0.532 로 <b>0.003</b> 앞서기 때문이다. 이 차이는 노이즈 범위이므로 실질적으로는
<b>C8b 가 세 축 모두에서 앞선다</b>고 읽어야 한다.</p>
"""
    return rr.make_section("p3b2", "후보 좁히기", "Gate → 비교축 → 2개", body, after="p3b1")


def section_c8b(b, f):
    c1 = next(c for c in f["candidates"] if c["candidate"] == "C1 post-hoc")
    c8b = next(c for c in f["candidates"] if c["candidate"] == "C8b family .35 + perc .15")
    c8a = next(c for c in f["candidates"] if c["candidate"] == "C8a perception b=0.15")
    kb = b["korea200"]["C1 post-hoc"]
    k8 = b["korea200"]["C8b family .35 + perc .15"]
    gb = b["global1000"]["C1 post-hoc"]
    g8 = b["global1000"]["C8b family .35 + perc .15"]
    rows = [
        ["영역 이해 — Korea ratio", f'{c1["axis1_cohesion_ratio_korea"]:.3f}',
         f'<b>{c8b["axis1_cohesion_ratio_korea"]:.3f}</b>', "+20%"],
        ["영역 이해 — Global ratio", f'{gb["readability"]["cohesion_ratio"]:.3f}',
         f'<b>{g8["readability"]["cohesion_ratio"]:.3f}</b>', "+21%"],
        ["자기 계열 영역 위 (Korea)", f'{(kb["region_field"] or {}).get("on_own_region"):.3f}',
         f'<b>{(k8["region_field"] or {}).get("on_own_region"):.3f}</b>', "+6.8%"],
        ["영역 조각 수 (Korea)", f'{(kb["region_field"] or {}).get("fragments_total")}',
         f'<b>{(k8["region_field"] or {}).get("fragments_total")}</b>', "24 → 15"],
        ["설명 가능성 — 공통 rare accord", f'{c1["axis2_shared_rare_accord_ge1"]:.1%}',
         f'<b>{c8b["axis2_shared_rare_accord_ge1"]:.1%}</b>', "+4.9%p"],
        ["설명 불가 향수", f'{c1["axis2_nearest_unexplained"]}',
         f'<b>{c8b["axis2_nearest_unexplained"]}</b>', "15 → 11"],
        ["방향성 — y=계절", f'{c1["axis3_y_warmth_rho"]:.3f}',
         f'<b>{c8b["axis3_y_warmth_rho"]:.3f}</b>', "+0.116"],
        ["방향성 — x=성별", f'{c1["axis3_x_masculine_rho"]:.3f}',
         f'{c8b["axis3_x_masculine_rho"]:.3f}', "동률"],
        ["<b>Gate A — 횡단 근접도</b>", f'{gb["guardrail"]["cross_family_proximity"]:.4f}',
         f'<b>{g8["guardrail"]["cross_family_proximity"]:.4f}</b>', "<b>개선</b>"],
        ["정답간선 근접도 (Korea)", f'{kb["layout"]["reminds_pct"]:.4f}',
         f'<b>{k8["layout"]["reminds_pct"]:.4f}</b>', "개선"],
        ["trust@10 (Global)", f'{gb["layout"]["trust@10"]:.4f}',
         f'{g8["layout"]["trust@10"]:.4f}', "−0.0196 (Gate B 통과)"],
        ["kNN overlap@10 (Global)", f'{gb["layout"]["knn_overlap@10"]:.4f}',
         f'{g8["layout"]["knn_overlap@10"]:.4f}', "−0.0742"],
    ]
    body = f"""
<p>C8b 는 거리에 두 가지를 섞는다 — <b>계열 프로파일 거리 0.35 + 사용자 투표 인식 축 0.15</b>
(원본 유사도 0.5). 좌표를 계열로 강제 분리하지 않고 <b>계열이 비슷한 향수를 조금 더 끌어당기는</b>
방식이다.</p>
{tbl(["지표", "C1 (좌표 유지)", "C8b", "변화"], rows,
     note="C1 post-hoc 은 현재 출하 좌표 그대로다 — 즉 왼쪽 열이 지금의 지도다.")}
<h3>대가가 한 곳에만 있다</h3>
<p><b>국소 보존만 내려간다</b> — Global trust@10 0.9387 → 0.9191(Gate B 0.90 통과),
overlap@10 0.3888 → 0.3146. 그 외 영역 이해 · 설명 가능성 · 방향성 · <b>사람 판단 근접도까지
모두 개선된다.</b></p>
<p class="warn">이건 드문 결과다. C2·C4·C6 는 영역 가독성을 크게 얻고 사람 판단을 크게 잃었다.
C8b 는 영역 가독성을 20% 얻으면서 사람 판단도 함께 개선한다 — 섞는 축이 <b>같은 accord
데이터에서 나온 매끄러운 값</b>이라 원래 거리와 충돌하지 않고 잡음만 줄이기 때문으로 보인다.</p>
<h3>C8a 는 다른 것을 준다</h3>
<p>C8a(인식 축만 0.15)는 <b>Gate A 를 가장 크게 개선한다</b>(−0.0751, 즉 사람 판단에 가장
가깝다). 대신 영역 이해가 3.069 로 현재 지도(3.264)보다 낮다. <b>영역을 포기하고 사람 판단만
극대화하는 선택</b>이다.</p>
"""
    return rr.make_section("p3b3", "C8b 상세", "무엇을 얻고 무엇을 잃는가", body, after="p3b2")


def section_next(b, f):
    body = f"""
<h3>내 추천 — C8b. 최종 결정은 팀</h3>
<p>비교축 세 개 모두에서 앞서고, 보호 지표(Gate A)까지 개선한다. 현재 출하 좌표(C1)와 비교해
<b>영역 이해 +20% · 설명 가능성 +4.9%p · 방향성 +0.116 · 사람 판단 근접도 개선</b>이고,
잃는 것은 국소 보존 한 곳뿐이다(trust@10 −0.0196, Gate B 통과).</p>
<p><b>다만 C8b 를 채택하면 좌표가 바뀐다.</b> 팀 결정 ②에 따라 지금 하위 산출물을 재생성하지
않고, 아래 순서로 검증한 뒤에만 전체 파이프라인을 다시 만든다.</p>
<ol>
<li><b>C8b 의 혼합 가중을 스윕한다.</b> 지금은 계열 0.35 · 인식 0.15 한 점만 쟀다.
Phase 1 의 인식축 예비 실험에서 b=0.3 이면 계열 응집도가 내려갔으므로 최적점이 이 근처에
있을 가능성이 있다</li>
<li><b>TriMap-dist 로 같은 두 후보를 다시 만든다</b> (팀 결정 ②). Phase 2 에서 TriMap-dist 가
사람 판단 근접도에서 UMAP 을 앞섰으므로(Global −0.0111 · Korea −0.0103), C8b 와 결합하면
Gate A 가 더 개선될 수 있다</li>
<li><b>Phase 4 균형 실험</b>을 확정된 좌표 위에서 돌린다</li>
<li><b>Phase 5 UX 프로토타입</b>에서 라벨 9개가 첫 화면에서 읽히는지 확인한다 —
이건 데이터가 답할 수 없는 문제다</li>
</ol>
<h3>팀이 결정할 것</h3>
<ol>
<li><b>C8b 와 C8a 중 무엇을 최종 후보로 올릴지</b> — C8b 는 영역 이해, C8a 는 사람 판단
극대화다. 향해의 핵심 경험이 "여기가 어느 구역인가" 라면 C8b, "닮은 향수 찾기" 라면 C8a 다</li>
<li><b>C1(좌표 유지)을 남길지</b> — 개입이 0 이라 되돌릴 비용도 0 이다. 지금 출하본을 그대로
두고 영역만 색으로 얹는 선택이며, Gate A 가 정의상 baseline 과 같다</li>
<li><b>Set B 9계열 확정</b> — Phase 3a 의 제안이고 계열 수 비교도 9를 지지한다.
남은 쟁점은 <code>powdery</code>(보유율 47.7%)를 계열로 쓸지와 프루티(Korea 200 에서 8개)다</li>
<li><b>C3 semi 를 후속 후보로 남길지</b> — Pareto 에서 C8b 에 지배됐지만 Gate A 비용이
+0.0157 로 작고 영역 이해가 3.633 이다. 좌표 개입이 계열 라벨만이라 설명하기 쉽다는 장점이 있다</li>
</ol>
<h3>Phase 3 가 남긴 것</h3>
<ul>
<li><b>D9 의 결론이 계열 라벨에서도 재확인됐다.</b> 계열을 좌표로 강제 분리하는 방식
(C2 supervised · C4 fixed · C6 anchor)은 영역 가독성을 크게 얻지만 사람 판단을 크게 잃는다.
가중을 낮춰도(w=0.2) Gate A 를 +0.188 초과한다</li>
<li><b>Gate A 하나로는 부족하다.</b> C5 wheel anchor 가 Gate A 를 통과하면서 trust@10
0.7068 을 기록했다 — RadViz 계열의 중앙 뭉침 문제다. Gate B 가 필요한 이유가 실측으로 확인됐다</li>
<li><b>영역 가독성과 사람 판단을 동시에 개선하는 방식이 존재한다</b> — 거리에 부드럽게 섞는
C8 계열이다. 강제 분리와 다른 접근이다</li>
</ul>
"""
    return rr.make_section("p3b4", "다음", "추천과 팀 결정", body, after="p3b3")


def main() -> None:
    os.chdir(MAP_DIR)
    os.makedirs(PHASE3, exist_ok=True)
    print("=" * 78)
    print("Phase 3 — 팀 검토용 summary.html")
    print("=" * 78)
    a = rj(P3A, "metrics.json")
    b = rj(P3B, "metrics.json")
    f = rj(P3B, "finalists.json")
    coord_rows = rc(P3B, "coordinates_korea200.csv")
    print(f"읽은 산출물 — 3a 정의 3종 · 3b 방식 {len(b['korea200'])}종 · "
          f"후보 {len(f['candidates'])}개 · 좌표 {len(coord_rows)}행")

    metrics = {
        "phase": 3,
        "projection": b["projection"], "family_definition": b["family_definition"],
        "phase3a_recommendation": a["_meta"]["recommended_definition"],
        "gate_a": f["gate_a"], "gate_b": f["gate_b"],
        "survivors": f["survivors"], "pareto_front": f["pareto_front"],
        "recommendation": "C8b family .35 + perc .15",
        "recommendation_basis": ("비교축 3개 모두에서 앞서고 Gate A(보호 지표)까지 개선한다. "
                                 "잃는 것은 국소 보존 한 곳(trust@10 -0.0196, Gate B 통과)"),
        "d9_reconfirmed": ("계열을 좌표로 강제 분리하는 방식은 영역 가독성을 얻고 사람 판단을 "
                           "잃는다. C2 supervised 는 가중 0.2 에서도 Gate A 를 +0.188 초과"),
        "next": ["C8b 혼합 가중 스윕", "TriMap-dist 로 후보 재검증(팀 결정 ②)",
                 "Phase 4 균형", "Phase 5 UX 프로토타입"],
    }
    with open(os.path.join(PHASE3, "metrics.json"), "w", encoding="utf-8") as fp:
        json.dump(metrics, fp, ensure_ascii=False, indent=1)
        fp.write("\n")
    manifest = {
        "experiment_id": "phase3", "phase": 3, "status": "NEW",
        "hypothesis": "해당 없음 — Phase 요약",
        "user_meaning": "영역이 읽히면서도 닮았다고 한 향수가 갈라지지 않는 표현이 있는가",
        "changed_variable": "없음 (3a·3b 결과 종합)",
        "population": ["korea200", "global1000"],
        "projection": b["projection"],
        "family_mapping_version": "reviewed-1",
        "sub_experiments": ["phase3a", "phase3b"],
        "primary_metrics": ["cohesion_ratio", "explainability(fixed)", "axis correlation"],
        "guardrail_metrics": [f"Gate A <= {f['gate_a']['pass_line']}",
                              f"Gate B trust@10 >= {f['gate_b']['threshold']}"],
        "recommendation": "C8b family .35 + perc .15",
    }
    with open(os.path.join(PHASE3, "manifest.json"), "w", encoding="utf-8") as fp:
        json.dump(manifest, fp, ensure_ascii=False, indent=1)
        fp.write("\n")

    sections = [section_setup(a), section_definition(a), section_maps(coord_rows),
                section_gate_a(b), section_finalists(f), section_c8b(b, f),
                section_next(b, f)]
    print(f"고유 절 {len(sections)}개를 렌더러에 넘깁니다")
    path, nsec, nkpi, nchk, nfig = rr.render(
        PHASE3, os.path.abspath(os.path.join(PHASE3, "summary.html")),
        title="Phase 3 — 향 계열 영역 실험 결과",
        extra_sections=sections, auto_data_figures=False)
    print(f"\n  -> {os.path.relpath(path)}  ({os.path.getsize(path)/1024:.0f} KB) · 섹션 {nsec}개")


if __name__ == "__main__":
    main()

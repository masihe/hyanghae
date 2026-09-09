"""팀 공유용 향 지도 브리핑 — 원래 지도와 최종 지도 비교 · 과정 · 데이터 형태.

발표용 자료다. 내부 실험 코드명(후보 이름 · 시드 번호 · 게이트 기호)은 쓰지 않고
무엇이 왜 어떻게 바뀌었는지만 남긴다.

두 지도를 같은 기준으로 재서 나란히 보여준다::

    원래 지도  output/korea_scent_map_v2.json          자동 군집 7개
    최종 지도  experiments/phase6/korea_scent_map_v3.json  향 계열 9개

새로 계산하는 것은 없다 — 두 산출물을 읽어 그리고 세기만 한다.

재현::

    python src/map/build_team_briefing.py

산출  docs/team_briefing_scent_map_v2.html
"""

import io
import json
import os
import sys

import numpy as np
import pandas as pd
from scipy.ndimage import label as cc_label

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (HERE, os.path.join(HERE, "..", "common")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

COUNT_CMP = os.path.join("experiments", "phase0_family_count_comparison", "metrics.json")
MAP_DIFF = os.path.join("experiments", "phase0_family_count_comparison", "mapping_diff.csv")
FAM_META = os.path.join("experiments", "phase0", "family_mapping_draft_meta.json")
FAM_DRAFT = os.path.join("experiments", "phase0", "family_mapping_draft.csv")
IFRA_DIST = os.path.join("..", "EDA", "analysis_outputs",
                         "17_ifra_primary_descriptor_distribution.csv")
SETS = os.path.join("experiments", "phase3a", "metrics.json")
OLD = os.path.join("output", "korea_scent_map_v2.json")
NEW = os.path.join("experiments", "phase6", "korea_scent_map_v3.json")
OUT = os.path.join("docs", "team_briefing_scent_map_v2.html")

FAM_COLOR = {"CITRUS": "#d9b23a", "FRUITY": "#d1553f", "FLORAL": "#c56480",
             "GREEN": "#5f9a5c", "AQUATIC": "#3a9cab", "WOODY": "#9c7a52",
             "AMBER": "#d99a2e", "GOURMAND": "#9a7ec4", "MUSK": "#8595ac"}
# 군집은 향 계열이 아니다. 계열 색과 헷갈리지 않게 채도를 낮춘 청회색 계열로 쓰되,
# "구역이 7개 있었다" 는 사실은 보여야 하므로 명도로 구분한다.
CLUSTER_COLOR = ["#4a6472", "#6e8794", "#93a7b0", "#b5c4c9", "#5b7a70",
                 "#84999a", "#a9b6b4"]
AREA_MIN, BLOB_MIN = 0.03, 0.60
EXAMPLE_NAME = "Blanche"


def rle(a):
    out, prev, n = [], int(a[0]), 1

    def tok(v, k):
        return f"{'z' if v == 255 else chr(97 + v)}{k}"

    for v in a[1:]:
        v = int(v)
        if v == prev:
            n += 1
        else:
            out.append(tok(prev, n))
            prev, n = v, 1
    out.append(tok(prev, n))
    return "".join(out)


def read(path, block):
    d = json.load(io.open(path, encoding="utf-8"))
    t = d["terrain"]
    W, H = t["grid_width"], t["grid_height"]
    g = np.array(d[block]["grid"], dtype=np.uint8).reshape(H, W)
    n_land = int((g != 255).sum())
    stats = []
    for it in d[block]["items"]:
        m = g == it["id"]
        c = int(m.sum())
        if c:
            lab, _ = cc_label(m)
            s = np.bincount(lab.ravel())[1:]
            blob = float(s.max() / c)
        else:
            blob = 0.0
        stats.append({
            "id": it["id"],
            "name": it.get("name_ko") or f"군집 {it['id']}",
            "tags": " / ".join(a["name"] for a in it.get("label_accords", [])[:3]),
            "n": it.get("size", it.get("perfume_count_argmax")),
            "area": round(c / n_land, 4) if n_land else 0.0,
            "blob": round(blob, 4),
            "ok": bool((c / n_land if n_land else 0) >= AREA_MIN and blob >= BLOB_MIN),
        })
    return d, {"W": W, "H": H, "bounds": t["bounds"], "grid": rle(g.ravel()),
               "items": stats, "land": n_land}


def dist_block(doc, path):
    """지도 거리가 무엇을 뜻하는지 설명할 실측값과 사례. 새로 계산하지 않고 잰다."""
    import scent_map as sm
    import build_map as bm
    from scipy.spatial.distance import squareform, pdist
    from scipy.stats import spearmanr

    ids = [p["fragrantica_id"] for p in doc["points"]]
    XY = np.array([[p["x"], p["y"]] for p in doc["points"]], float)
    P = {p["fragrantica_id"]: p for p in doc["points"]}
    df, _t, idf, *_ = bm.prepare(with_selection_comparison=False)
    rows = df.set_index("id").loc[ids].reset_index()
    S, _, _ = sm.base_similarity(rows.accord_list.tolist(), rows.note_set.tolist(), idf)
    D = 1.0 - S
    np.fill_diagonal(D, 0.0)
    D2 = squareform(pdist(XY))
    iu = np.triu_indices(len(ids), 1)

    def pair(a_name, b_name):
        i = next(k for k, x in enumerate(ids) if P[x]["name"] == a_name)
        j = next(k for k, x in enumerate(ids) if P[x]["name"] == b_name)
        return {"a": f"{P[ids[i]]['brand']} {P[ids[i]]['name']}",
                "b": f"{P[ids[j]]['brand']} {P[ids[j]]['name']}",
                "map": round(float(D2[i, j]), 3), "scent": round(float(D[i, j]), 3),
                "fa": " + ".join(f"{f['name_ko']} {f['weight']:.2f}"
                                 for f in P[ids[i]]["families"]),
                "fb": " + ".join(f"{f['name_ko']} {f['weight']:.2f}"
                                 for f in P[ids[j]]["families"])}

    base = next(k for k, x in enumerate(ids) if P[x]["name"] == "Eclat d'Arpege")
    # 자기 자신은 목록에서 제외한다 (inf 로 밀어낸 뒤 마지막 한 칸을 잘라낸다).
    o2 = np.argsort(np.where(np.arange(len(ids)) == base, np.inf, D2[base]))[:len(ids) - 1]
    ladder = [{"label": lab, "who": f"{P[ids[k]]['brand']} {P[ids[k]]['name']}",
               "map": round(float(D2[base, k]), 3), "scent": round(float(D[base, k]), 3)}
              for lab, k in (("바로 옆", o2[0]), ("중간쯤", o2[100]), ("반대편", o2[-1]))]
    lay = doc["layout"]
    return {
        "weights": lay["distance"],
        "trust": lay["metrics"]["trust_at_10"],
        "reminds": lay["metrics"]["reminds_distance_percentile"],
        "edges": lay["metrics"]["trusted_reminds_edges_in_set"],
        "rank_corr": round(float(spearmanr(D[iu], D2[iu]).statistic), 3),
        "pairs": [pair("Eau Rose", "Rose Magnetic"),
                  pair("Blanche", "Lazy Sunday Morning")],
        "ladder": {"base": f"{P[ids[base]]['brand']} {P[ids[base]]['name']}",
                   "steps": ladder},
    }


def origin_block():
    """계열 9개가 어디서 왔는지 — 휠 대응 7개와 IFRA 근거 2개를 기록된 산출물에서 읽는다.

    새로 판단하지 않는다. Phase 0 이 남긴 매핑 메타/CSV 와 EDA 의 IFRA 분포를 세기만 한다.
    """
    meta = json.load(io.open(FAM_META, encoding="utf-8"))
    d = pd.read_csv(FAM_DRAFT, encoding="utf-8-sig")
    ifra = pd.read_csv(IFRA_DIST, encoding="utf-8-sig")
    diff = pd.read_csv(MAP_DIFF, encoding="utf-8-sig")

    wheel = [{"ko": v["ko"],
              "src": v["source"].split(": ", 1)[1]
                     .replace("Fougere", "Fougère").replace(" / ", " · ")}
             for v in meta["families"].values() if v["basis"] == "WHEEL"]
    wheel_covered = sum(x["src"].count("·") + 1 for x in wheel)

    def cnt(row):
        return {"n": int(len(row)), "share": round(float(row.perfume_share.sum()), 2)}

    basis = {k: cnt(d[d.family_basis == k]) for k in ("WHEEL", "IFRA", "NONE")}
    mapped = d[d.proposed_family != "UNMAPPED"]
    fam = sorted(({"ko": ko, "basis": g.family_basis.iloc[0], **cnt(g)}
                  for ko, g in mapped.groupby("proposed_family_ko")),
                 key=lambda x: -x["share"])

    ifra = ifra.sort_values("count", ascending=False).reset_index(drop=True)
    def term(name):
        i = int(ifra.index[ifra.primary_descriptor == name][0])
        return {"n": int(ifra["count"][i]), "rank": i + 1}
    g, m, pw, am = term("Gourmand"), term("Musk Like"), term("Powdery"), term("Amber")

    lv = d.ifra_level.fillna("NONE").value_counts().to_dict()
    return {
        "wheel": wheel,
        "wheel_total": 14,
        "wheel_covered": wheel_covered,
        "basis": basis,
        "share_total": round(float(d.perfume_share.sum()), 2),
        "fam": fam,
        "ifra": {"terms": int(len(ifra)),
                 "gourmand": g, "musk": m, "powdery": pw, "amber": am,
                 "musk_sum": m["n"] + pw["n"]},
        "levels": {"exact": int(lv.get("PRIMARY", 0)),
                   "related": int(lv.get("SECONDARY", 0)) + int(lv.get("ALIAS_CANDIDATE", 0)),
                   "none": int(lv.get("NONE", 0))},
        "accord_total": meta["accord_total"],
        "review_required": meta["review_required"],
        "unmapped": meta["unmapped"],
        "unmapped_share": meta["unmapped_share_sum"],
        "changed": [{"accord": r.accord, "to": r.reviewed_1} for r in diff.itertuples()],
    }


def main() -> None:
    os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))  # MAP/
    old, o = read(OLD, "regions")
    new, n = read(NEW, "families")

    for i, it in enumerate(o["items"]):
        it["color"] = CLUSTER_COLOR[i % len(CLUSTER_COLOR)]
    keys = [x["key"] for x in new["families"]["items"]]
    for it, k in zip(n["items"], keys):
        it["color"] = FAM_COLOR[k]

    o["points"] = [[round(p["x"], 4), round(p["y"], 4), p["region"]]
                   for p in old["points"]]
    fam_idx = {k: i for i, k in enumerate(keys)}
    n["points"] = [[round(p["x"], 4), round(p["y"], 4),
                    fam_idx[p["families"][0]["key"]], len(p["families"])]
                   for p in new["points"]]

    multi = [len(p["families"]) for p in new["points"]]
    ex = next(p for p in new["points"] if p["name"] == EXAMPLE_NAME)
    example = {
        "brand": ex["brand"], "name": ex["name"],
        "x": ex["x"], "y": ex["y"],
        "families": [{"ko": f["name_ko"], "w": f["weight"]} for f in ex["families"]],
        "accords": [a["name"] for a in ex["top_accords"][:4]],
        "rank": ex["korea"]["selection_rank"],
        "neighbors": len(ex["neighbors"]),
    }

    # ---- 9계열 근거 (기록된 실험값을 읽어온다) ----
    cc = json.load(io.open(COUNT_CMP, encoding="utf-8"))
    st = json.load(io.open(SETS, encoding="utf-8"))
    LAB = {"S9": "9개 (채택)", "S8B": "8개 — 구르망 제외",
           "S8A": "8개 — 머스크 제외", "S7": "7개 — 둘 다 제외"}
    counts = []
    for key in ("S9", "S8B", "S8A", "S7"):
        v = cc["korea200"][key]
        counts.append({
            "label": LAB[key], "k": v["family_count"],
            "kept": v["family_mass_ratio"]["median"],
            "dropped_tags": v["modifier_count"],
            "top_lost": v["top_accord_is_modifier"],
            "half_lost": v["low_family_mass"]["ratio_lt_0.5"],
            "ratio_g": cc["global1000"][key]["cohesion_ratio"],
            "seed": cc["seed_stability_korea200"][key],
        })
    merge = [{"label": "7개로 줄이고 앰버에 합침",
              "max_share": cc["korea200"]["S7_A"]["size_max_share"],
              "sizes": cc["korea200"]["S7_A"]["family_sizes"]},
             {"label": "8개로 줄이고 앰버에 합침",
              "max_share": cc["korea200"]["S8B_A"]["size_max_share"],
              "sizes": cc["korea200"]["S8B_A"]["family_sizes"]}]
    sets = [{"label": "데이터에 이미 있던 분류", "k": 4,
             "rk": st["korea200"]["SetA"]["cohesion_ratio"],
             "rg": st["global1000"]["SetA"]["cohesion_ratio"],
             "cov": st["korea200"]["SetA"]["coverage"], "named": True,
             "note": "무작위와 거의 구분되지 않고 16개는 분류조차 없다"},
            {"label": "자동으로 묶기", "k": 7,
             "rk": st["korea200"]["SetC"]["cohesion_ratio"],
             "rg": st["global1000"]["SetC"]["cohesion_ratio"],
             "cov": st["korea200"]["SetC"]["coverage"], "named": False,
             "note": "이름을 붙일 수 없고 대상이 바뀌면 개수도 바뀐다 (7개 ↔ 9개)"},
            {"label": "향 계열 9개 (채택)", "k": 9,
             "rk": st["korea200"]["SetB"]["cohesion_ratio"],
             "rg": st["global1000"]["SetB"]["cohesion_ratio"],
             "cov": st["korea200"]["SetB"]["coverage"], "named": True,
             "note": "외부 근거에서 나온 이름을 쓰면서 가장 잘 뭉친다"}]

    payload = {
        "old": o, "new": n, "example": example,
        "why9": {"counts": counts, "merge": merge, "sets": sets,
                 "origin": origin_block()},
        "dist": dist_block(new, NEW),
        "summary": {
            "old_ok": sum(1 for x in o["items"] if x["ok"]), "old_total": len(o["items"]),
            "new_ok": sum(1 for x in n["items"] if x["ok"]), "new_total": len(n["items"]),
            "old_area_max": max(x["area"] for x in o["items"]),
            "old_area_min": min(x["area"] for x in o["items"]),
            "new_area_max": max(x["area"] for x in n["items"]),
            "new_area_min": min(x["area"] for x in n["items"]),
            "old_named": sum(1 for x in o["items"] if not x["name"].startswith("군집")),
            "new_named": sum(1 for x in n["items"] if not x["name"].startswith("군집")),
            "multi_1": multi.count(1), "multi_2": multi.count(2), "multi_3": multi.count(3),
            "old_kb": round(os.path.getsize(OLD) / 1024),
            "new_kb": round(os.path.getsize(NEW) / 1024),
        },
        "area_min": AREA_MIN, "blob_min": BLOB_MIN,
    }
    html = TEMPLATE.replace("__PAYLOAD__", json.dumps(payload, ensure_ascii=False,
                                                      separators=(",", ":")))
    io.open(OUT, "w", encoding="utf-8", newline="\n").write(html)
    s = payload["summary"]
    print(f"원래 지도 — 구역 {s['old_ok']}/{s['old_total']} · 이름 있는 구역 "
          f"{s['old_named']}/{s['old_total']} · 면적 {s['old_area_min']:.1%}~{s['old_area_max']:.1%}")
    print(f"최종 지도 — 구역 {s['new_ok']}/{s['new_total']} · 이름 있는 구역 "
          f"{s['new_named']}/{s['new_total']} · 면적 {s['new_area_min']:.1%}~{s['new_area_max']:.1%}")
    print(f"향수당 계열 — 1개 {s['multi_1']} · 2개 {s['multi_2']} · 3개 {s['multi_3']}")
    print(f"  -> {OUT}  ({os.path.getsize(OUT)/1024:.0f} KB)")


TEMPLATE = """<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>향 지도 — 무엇을 어떻게 바꿨나</title>
<style>
:root{--bg:#fbfcfc;--card:#fff;--ink:#14262b;--ink2:#33484e;--muted:#5d757c;
      --hair:#c6d2d1;--sea:#e9eef0;--ok:#2f6b4f;--warn:#9d4238;--accent:#0e3644}
@media (prefers-color-scheme:dark){:root{--bg:#0f1719;--card:#151f22;--ink:#e8eef0;
      --ink2:#b6c6ca;--muted:#8ba0a5;--hair:#2b3a3e;--sea:#101a1c;--ok:#7fbf9e;
      --warn:#e08b80;--accent:#8fd3e0}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
     font:15.5px/1.75 -apple-system,BlinkMacSystemFont,"Segoe UI","Malgun Gothic",sans-serif}
.wrap{max-width:900px;margin:0 auto;padding:32px 22px 64px}
h1{font-size:25px;font-weight:600;margin:0 0 6px;letter-spacing:-.2px}
.lede{color:var(--muted);font-size:14px;margin:0 0 28px}
h2{font-size:19px;font-weight:600;margin:44px 0 4px;padding-top:20px;
   border-top:1px solid var(--hair)}
h2 .num{color:var(--muted);font-weight:400;margin-right:8px}
h3{font-size:15.5px;font-weight:600;margin:26px 0 8px}
p{margin:10px 0}
.big{background:var(--card);border:1px solid var(--hair);border-radius:14px;
     padding:18px 20px;margin:18px 0}
.big p{margin:6px 0}
.kpi{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:18px 0}
.kpi div{background:var(--card);border-radius:12px;padding:14px 16px;border:1px solid var(--hair)}
.kpi .l{font-size:12px;color:var(--muted);display:block}
.kpi .v{font-size:22px;font-weight:600;display:block;margin-top:2px}
.kpi .d{font-size:12px;color:var(--muted)}
table{border-collapse:collapse;width:100%;font-size:13.5px;margin:12px 0}
th,td{text-align:left;padding:7px 9px;border-bottom:1px solid var(--hair)}
th{color:var(--muted);font-weight:500;font-size:12.5px}
td.n{text-align:right;font-variant-numeric:tabular-nums}
.ok{color:var(--ok);font-weight:600}
.bad{color:var(--warn);font-weight:600}
.maps{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin:16px 0}
@media (max-width:700px){.maps{grid-template-columns:1fr}}
.mapbox{background:var(--card);border:1px solid var(--hair);border-radius:12px;padding:10px}
.mapbox h4{margin:0 0 2px;font-size:14px;font-weight:600}
.mapbox .s{margin:0 0 8px;font-size:12px;color:var(--muted)}
.mapbox canvas{width:100%;height:auto;display:block;border-radius:7px}
.leg{display:flex;flex-wrap:wrap;gap:5px;margin-top:8px}
.leg span{display:inline-flex;align-items:center;gap:4px;font-size:11.5px;color:var(--muted)}
.leg i{width:9px;height:9px;border-radius:2px;display:inline-block}
.flow{counter-reset:s}
.step{background:var(--card);border:1px solid var(--hair);border-radius:12px;
      padding:14px 18px;margin:12px 0;position:relative}
.step h4{margin:0 0 4px;font-size:15px;font-weight:600}
.step h4::before{counter-increment:s;content:counter(s);display:inline-flex;
  align-items:center;justify-content:center;width:22px;height:22px;border-radius:50%;
  background:var(--accent);color:var(--bg);font-size:12px;margin-right:9px}
.step p{margin:5px 0;font-size:14px}
.step .res{font-size:13px;color:var(--muted);margin-top:7px;padding-top:7px;
  border-top:1px dashed var(--hair)}
.fail{border-left:3px solid var(--warn);border-radius:0 12px 12px 0}
code{font:12.5px/1.5 ui-monospace,Menlo,Consolas,monospace;background:var(--sea);
     padding:1px 5px;border-radius:4px}
pre{background:var(--card);border:1px solid var(--hair);border-radius:10px;padding:14px 16px;
    overflow:auto;font:12.5px/1.65 ui-monospace,Menlo,Consolas,monospace}
.note{font-size:13px;color:var(--muted)}
ul{margin:8px 0;padding-left:22px}
li{margin:4px 0}
</style></head><body><div class="wrap">

<h1>향 지도 — 무엇을 어떻게 바꿨나</h1>
<p class="lede">국내 대표 향수 200개 지도. 팀 공유용 정리.</p>

<div class="big">
<p><b>한 줄 요약</b> — 지도의 영역이 <b>사용자가 아는 향 계열 9개</b>로 바뀌었고,
9개 전부 이름과 구역을 갖게 됐습니다.</p>
<p class="note">향수 200개는 그대로입니다. 한 개도 바꾸지 않았습니다.</p>
</div>

<div class="kpi" id="kpi"></div>

<h2><span class="num">1</span>원래 지도와 최종 지도</h2>
<p>같은 향수 200개입니다. <b>영역을 무엇으로 나눌지</b>가 달라졌습니다.</p>
<div class="maps">
 <div class="mapbox"><h4>원래 지도</h4><p class="s">자동으로 묶은 덩어리 7개</p>
  <canvas id="cOld"></canvas><div class="leg" id="lOld"></div></div>
 <div class="mapbox"><h4>최종 지도</h4><p class="s">향 계열 9개</p>
  <canvas id="cNew"></canvas><div class="leg" id="lNew"></div></div>
</div>
<p class="note">색면 = 영역 · 회색 = 바다(향수가 드문 곳) · 점 = 향수 200개</p>

<h2><span class="num">2</span>원래 지도의 문제는 무엇이었나</h2>
<p>덩어리 자체는 있었습니다. 문제는 <b>사용자가 그것을 읽을 수 없다</b>는 것이었습니다.</p>
<h3>문제 ① 영역에 이름이 없었다</h3>
<p>영역 7개가 데이터로 자동 묶인 덩어리라서 <b>한글 이름이 하나도 없었습니다.</b>
붙일 수 있는 건 향 태그뿐이었습니다.</p>
<table id="tOld"><thead><tr><th>영역</th><th>대표 향 태그</th><th class="n">향수</th>
<th class="n">면적</th><th class="n">한 덩어리</th><th>구역으로 읽히나</th></tr></thead><tbody></tbody></table>
<p class="note">"이 구역은 <code>fresh spicy / aromatic / citrus</code>" 라고 사용자에게 말할 수는 없습니다.</p>
<h3>문제 ② 크기가 극단적으로 치우쳐 있었다</h3>
<p id="pSkew"></p>
<h3>문제 ③ 향 계열과 무관한 기준이었다</h3>
<p>사용자는 "우디", "프루티" 로 향을 찾습니다. 그런데 지도의 영역은 그 개념이 아니었습니다.
지도를 봐도 <b>"어디로 가면 우디 향이 있는지" 알 수 없었습니다.</b></p>

<h2><span class="num">3</span>왜 향 계열 9개인가</h2>
<p>향 계열을 무엇으로 볼지가 지도 전체를 결정합니다. <b>네 가지 방법을 실제로 재보고</b> 골랐습니다.</p>

<h3>출발점 — 7개는 업계 표준 분류에서, 2개는 원료 데이터에서 왔다</h3>
<p>계열 이름을 우리가 지어내면 지도의 구역 이름도 근거가 없어집니다. 그래서 <b>바깥에 근거가
있는 분류</b>에서 출발했습니다. 7개와 2개의 출처가 다르므로 나눠서 적습니다.</p>

<h3>근거 ① 7개 — Fragrance Wheel</h3>
<p><b>Fragrance Wheel</b> 은 <b>Michael Edwards / Fragrances of the World</b> 가 만든 향 계열
분류입니다. 향수 업계·리테일·향수 교육에서 사실상 표준으로 쓰이고, 브랜드가 자기 향수를 소개할 때
쓰는 "우디 오리엔탈" 같은 말도 여기서 나옵니다.</p>
<p>휠의 계열은 원래 <b id="wN"></b>개입니다. 팀이 <b>공식 휠 원문과 명칭·순서를 직접 대조해
확인</b>했습니다 — 검증본 <code>EDA/data/scent_knowledge/source/perfume_14families_korean_descriptors.md</code>
(웹 검증 9회, 원본 출처 27건 전수 확인). 다만 지도의 구역으로 쓰기에는 14개가 너무 잘아서
<b>인접한 것끼리 묶어 7개 축</b>으로 정리했습니다.</p>
<table id="tWheel"><thead><tr><th>우리가 쓰는 계열</th><th>Fragrance Wheel 의 어느 패밀리인가</th>
<th class="n">묶은 개수</th></tr></thead><tbody></tbody></table>
<p class="note" id="nWheel"></p>
<p class="note">2021년에 <code>Oriental</code> 이 <code>Amber</code> 로 공식
개명됐습니다 — 국내 데이터·블로그에는 아직 "오리엔탈" 이 남아 있어 매칭할 때 옛 이름도 함께 봅니다.</p>

<h3>근거 ② 나머지 2개 — 휠에 없지만 원료 데이터에는 있다</h3>
<p><b>구르망(달콤한 디저트 계열)과 머스크·파우더리는 휠에 독립 계열이 없습니다.</b>
그래서 다른 근거를 찾았습니다. <b>IFRA(국제향료협회)</b> 가 향 원료 하나하나에 붙여 놓은
<b>대표 성격 <span id="ifN"></span>종</b>의 분포입니다. 원료 쪽에서 본 실제 사용량이라
휠과는 독립된 근거입니다.</p>
<table id="tIfra"><thead><tr><th>IFRA 가 붙인 성격</th><th class="n">해당 원료</th>
<th class="n">27종 중 순위</th><th>휠에 계열이 있나</th></tr></thead><tbody></tbody></table>
<p class="note" id="nIfra"></p>

<h3>근거 ③ 우리 데이터에서 두 계열이 실제로 차지하는 몫</h3>
<p>향수마다 붙어 있는 향 특성 태그(우디 · 로즈 · 바닐라 …) <b id="acN"></b>종을 계열에
배정했습니다. 향수 하나에 태그가 평균 8개 붙는데, 그 신호가 어느 근거로 계열에 들어갔는지
세면 이렇습니다.</p>
<div class="big" id="pBasis"></div>
<p>계열별로 나눠 보면 <b>휠에 없는 두 계열이 휠에 있는 큰 계열만큼 신호를 갖고 있습니다.</b>
9개 중 4위와 5위입니다.</p>
<table id="tMass"><thead><tr><th>계열</th><th>근거</th><th class="n">태그 수</th>
<th class="n">신호량</th></tr></thead><tbody></tbody></table>
<p class="note">"신호량" = 그 계열의 태그가 향수에 붙어 있는 비율의 합. 예를 들어 태그 하나가
향수 절반에 붙어 있으면 0.5 입니다. 계열이 지도에서 얼마나 자주 등장하는지를 뜻합니다.</p>

<h3>92종을 계열에 배정한 방법</h3>
<p id="pAssign"></p>

<h3>대안 ① 데이터에 이미 있던 분류를 쓰면 안 되나</h3>
<p>원본 데이터에 향수별 대분류가 이미 들어 있습니다. 그걸 쓰면 표를 만들 필요가 없습니다.
그런데 <b>지도에서 영역으로 보이지 않았습니다.</b></p>
<table id="tSets"><thead><tr><th>방법</th><th class="n">개수</th><th class="n">얼마나 뭉치나</th>
<th class="n">분류된 향수</th><th>이름</th><th>판정</th></tr></thead><tbody></tbody></table>
<p class="note">"얼마나 뭉치나" = 아무렇게나 칠했을 때보다 몇 배나 잘 뭉쳤는지.
1배면 무작위와 같다는 뜻입니다. 같은 지도·같은 향수에 색칠 기준만 바꿔서 잰 값입니다.</p>

<h3>대안 ② 자동으로 묶으면 안 되나</h3>
<p>데이터만 보고 비슷한 향수끼리 자동으로 묶는 방법도 있습니다. 뭉치는 정도는 9개 계열과
거의 같았습니다. <b>그런데 두 가지가 걸렸습니다.</b></p>
<ul>
<li><b>이름을 붙일 수 없습니다.</b> 자동으로 묶인 덩어리라 "우디 구역" 이라고 부를 근거가 없습니다 —
 <b>원래 지도가 겪던 문제와 똑같습니다.</b></li>
<li><b>대상이 바뀌면 개수도 바뀝니다.</b> 국내 200개에서는 7개, 더 넓은 집합에서는 9개가 나왔습니다.
 대표 향수를 갱신할 때마다 지도 구조가 달라진다는 뜻입니다.</li>
</ul>

<h3>대안 ③ 9개는 너무 많지 않나 — 7개나 8개로 줄이면</h3>
<p><b>이게 가장 중요한 확인이었습니다.</b> 계열을 지우면 그 계열에 속했던 향 특성이
"계열 없음" 이 되어 <b>지도 계산에서 통째로 빠집니다.</b> 얼마나 빠지는지 셌습니다.</p>
<table id="tCounts"><thead><tr><th>방법</th><th class="n">남는 향 신호</th>
<th class="n">버려지는 태그</th><th class="n">대표 향이 버려진 향수</th>
<th class="n">신호 절반 이상 잃은 향수</th><th class="n">얼마나 뭉치나</th></tr></thead><tbody></tbody></table>
<div class="big"><p id="pLoss"></p></div>

<h3>대안 ④ 지우는 대신 다른 계열에 합치면</h3>
<p>구르망과 머스크를 지우는 대신 <b>앰버에 합쳐</b>봤습니다. 신호는 안 버려집니다.
대신 <b>앰버가 거대해집니다.</b></p>
<table id="tMerge"><thead><tr><th>방법</th><th class="n">가장 큰 계열 비중</th><th>결과</th></tr></thead><tbody></tbody></table>

<div class="big"><p><b>결론</b> — 9개는 "많이 나눠서" 가 아니라 <b>줄이면 향 정보가 실제로 버려지기 때문에</b>
남은 숫자입니다. 9개일 때만 향수 200개 중 <b>신호를 절반 이상 잃는 향수가 0개</b>입니다.</p></div>

<h2><span class="num">4</span>어떻게 만들었나</h2>
<p>계열을 정한 뒤 <b>네 번</b> 시도했습니다. 그중 <b>두 번은 실패</b>했고, 그 실패가 최종 답을 결정했습니다.</p>
<div class="flow">
 <div class="step fail"><h4>계열별로 강제로 갈라 배치해봤다 — 실패</h4>
  <p>가장 단순한 방법입니다. 배치를 만들 때 <b>"같은 계열이면 무조건 붙여라"</b> 라고 지시했습니다.
  영역은 아주 깔끔해졌습니다 — 뭉치는 정도가 <b>4.2배 → 6.7배</b>가 됐습니다.</p>
  <p><b>그런데 지도의 본래 약속이 깨졌습니다.</b> 사용자가 "닮았다" 고 투표한 향수 쌍 872개 중
  <b>412개(47%)가 계열을 넘습니다.</b> 계열이 다르다는 이유로 그 쌍들이 밀려났습니다.</p>
  <table><thead><tr><th></th><th class="n">같은 계열 쌍</th><th class="n">계열이 다른 쌍</th></tr></thead>
  <tbody><tr><td>원래 배치</td><td class="n">0.10</td><td class="n">0.26</td></tr>
  <tr><td>강제로 가른 배치</td><td class="n">0.02</td><td class="n bad">0.45 ~ 0.57</td></tr></tbody></table>
  <p class="note">낮을수록 가깝다는 뜻입니다. 같은 계열은 거의 한 점으로 뭉치고,
  계열이 다른 쌍은 <b>0.5(무작위)</b> 에 가까워졌습니다.</p>
  <p>게다가 두 계열 사이에 걸친 향수까지 자기 계열 중심으로 끌려갔습니다.
  <b>"여기서 옆 계열로 넘어간다" 는 경계가 사라졌습니다</b> — 경계 향수와 계열이 뚜렷한 향수의
  구분이 0.11 에서 <b>0.02</b> 로 줄었습니다.</p>
  <div class="res">기각 — 영역을 얻고 "옆에 있는 향수는 닮았다" 를 잃었습니다.
   가장 약하게(20%만) 적용해도 합격선을 4배 초과했습니다.</div></div>

 <div class="step"><h4>거리를 부드럽게 조정했다</h4>
  <p>강제로 가르는 대신 <b>"계열 구성이 비슷하면 조금 더 가깝게"</b> 정도로만 조정했습니다.
  여기에 사용자가 느끼는 <b>계절·성별 인상</b>도 조금 섞었습니다.</p>
  <p>이 방식이 <b>영역과 닮음을 동시에 개선했습니다.</b> 강제 분리와 달리 원래 향 데이터와
  같은 재료에서 나온 신호라 충돌하지 않기 때문입니다.</p>
  <table><thead><tr><th>항목</th><th class="n">전</th><th class="n">후</th></tr></thead><tbody>
  <tr><td>영역이 읽히는 정도</td><td class="n">3.26</td><td class="n ok">3.91 (+20%)</td></tr>
  <tr><td>영역 조각 수</td><td class="n">24</td><td class="n ok">15</td></tr>
  <tr><td>닮은 향수 쌍이 가까운 정도</td><td class="n">0.176</td><td class="n ok">0.147</td></tr>
  <tr><td>이웃 목록이 원본과 맞는 정도</td><td class="n">0.49</td><td class="n bad">0.44</td></tr>
  </tbody></table>
  <div class="res">채택 — 마지막 한 줄이 대가입니다. 지도에서 "가장 가까운 10개" 목록이
   조금 달라지지만, 정해둔 합격선 안입니다.</div></div>

 <div class="step fail"><h4>향수 구성을 바꿔봤다 — 실패</h4>
  <p>이 단계에서 <b>프루티가 8개뿐이라 지도에서 안 보이는</b> 문제가 남아 있었습니다.
  그래서 후보 향수 풀에서 <b>37개를 교체해</b> 계열별 개수를 맞춰봤습니다
  (프루티 8 → 14, 앰버 14 → 25).</p>
  <p>프루티 구역은 생겼습니다. <b>그런데 앰버 구역이 대신 사라졌습니다.</b>
  앰버 향수를 늘렸더니 새로 들어온 향수들이 기존 덩어리에 붙지 않고
  <b>앰버 영역이 두 조각으로 갈라졌습니다.</b></p>
  <table><thead><tr><th>항목</th><th class="n">현재 구성</th><th class="n">균형 맞춘 구성</th></tr></thead><tbody>
  <tr><td>구역으로 읽히는 계열</td><td class="n">7.4</td><td class="n bad">6.8</td></tr>
  <tr><td>영역 조각 수</td><td class="n">16.4</td><td class="n bad">25.0</td></tr>
  <tr><td>앰버 영역의 한 덩어리 비율</td><td class="n">99%</td><td class="n bad">48%</td></tr>
  <tr><td>교체한 향수</td><td class="n">0</td><td class="n">37</td></tr>
  </tbody></table>
  <div class="res">기각 — 향수를 37개나 바꾸고도 구역 있는 계열이 오히려 줄었습니다.</div></div>

 <div class="step"><h4>향수를 여러 계열에 걸치게 했다</h4>
  <p>여기서 관점을 바꿨습니다. 향수 하나는 원래 <b>여러 계열을 동시에 갖습니다.</b>
  그런데 지금까지는 <b>1위 계열 하나만 인정하고 나머지를 버렸습니다.</b></p>
  <p>두 가지를 바꿨습니다.</p>
  <ul>
  <li><b>계열 소속이 뚜렷한 향수가 영역을 더 강하게 그리도록</b> 했습니다.
   지금까지는 소속이 흐릿한 향수(1위 계열이 22%뿐)도 뚜렷한 향수(82%)와 똑같은 힘으로 영역을 그렸습니다.</li>
  <li><b>2위 계열도 충분히 강하면 인정</b>하도록 했습니다.</li>
  </ul>
  <p><b>효과의 대부분은 첫 번째에서 나왔습니다.</b></p>
  <table><thead><tr><th>단계</th><th class="n">구역으로 읽히는 계열</th><th>비고</th></tr></thead><tbody>
  <tr><td>1위 계열만 · 모두 같은 힘 (기존)</td><td class="n">7.4</td><td class="note">프루티 · 머스크 구역 없음</td></tr>
  <tr><td>+ 소속이 뚜렷할수록 강하게</td><td class="n ok">8.6</td><td class="note">2위 계열은 아직 안 씀</td></tr>
  <tr><td>+ 2위 계열도 인정</td><td class="n ok">9.0</td><td class="note">9개 전부 구역 확보</td></tr>
  </tbody></table>
  <p><b>머스크가 이것으로 풀렸습니다.</b> 머스크로 분류된 18개의 <b>평균 머스크 비중이 38%뿐</b>이었습니다.
  나머지 62%는 다른 계열이라 위치가 제각각이었고, 그 향수들이 머스크 영역을 흩고 있었습니다.
  비중대로 힘을 주자 진짜 머스크 향수들이 만드는 덩어리가 드러났습니다
  — <b>향수 수는 그대로인데</b> 한 덩어리 비율이 55% → 61%가 됐습니다.</p>
  <p>마지막으로 <b>"2위 계열을 얼마나 강해야 인정할지"</b> 를 여섯 단계로 재서 골랐습니다.
  너무 느슨하면 계열끼리 서로 먹어 들어가 구역이 오히려 줄었습니다.</p>
  <div class="res">채택 — <b>향수를 한 개도 바꾸지 않고</b> 9개 계열 전부에 구역이 생겼습니다.
   프루티 영역이 넓어지고(2.7% → 6.3%) 한 덩어리가 됐습니다(71% → 100%).</div></div>
</div>

<h2><span class="num">5</span>최종 지도의 향 계열 9개</h2>
<table id="tNew"><thead><tr><th>향 계열</th><th class="n">대표 향수</th><th class="n">지도 면적</th>
<th class="n">한 덩어리</th><th>구역</th></tr></thead><tbody></tbody></table>
<p class="note" id="nNew"></p>

<h2><span class="num">6</span>지도에서 가까이 있다는 건 무슨 뜻인가</h2>
<p>지도의 핵심 약속입니다. <b>두 점이 가까우면 그 두 향수는 닮았다</b> — 이걸 지키려고
앞의 실패 두 번을 겪었습니다.</p>

<h3>거리는 세 가지를 섞은 값이다</h3>
<div class="big" id="wBox"></div>
<p class="note">셋 다 향수 데이터에서 나옵니다. 브랜드나 가격, 인기도는 거리에 들어가지 않습니다.</p>

<h3>실제로 얼마나 믿을 만한가</h3>
<table id="tTrust"><thead><tr><th>확인한 것</th><th class="n">값</th><th>읽는 법</th></tr></thead><tbody></tbody></table>

<h3>예를 들면</h3>
<div id="pairs"></div>
<p>반대로 <b>멀어지면 실제로 향도 멀어집니다.</b> 한 향수를 기준으로 재보면 이렇습니다.</p>
<table id="tLadder"><thead><tr><th id="thBase"></th><th>향수</th>
<th class="n">지도 거리</th><th class="n">향 데이터 거리</th></tr></thead><tbody></tbody></table>

<h3>주의 — 이렇게 읽으면 안 됩니다</h3>
<ul>
<li><b>거리에 단위가 없습니다.</b> "2배 멀다" 가 "2배 다르다" 를 뜻하지 않습니다.
 순서만 의미가 있습니다.</li>
<li><b>가까운 거리가 먼 거리보다 정확합니다.</b> 지도는 200개를 평면에 눌러 담은 것이라
 이웃 관계를 우선 지킵니다. <b>지도 반대편끼리의 거리는 대략적인 값</b>으로 보셔야 합니다.</li>
<li><b>축에는 방향 의미가 있습니다.</b> 지도를 돌려 맞추면 한 축은 계절감(시원함 ↔ 따뜻함),
 다른 축은 성별 인상과 이어집니다. <b>다만 이건 결과로 나타난 경향</b>이고
 축을 그렇게 설계한 것은 아닙니다.</li>
<li><b>검증에 쓸 수 있는 "정답" 이 적습니다.</b> 200개 안에서 사용자가 직접 "닮았다" 고
 투표한 쌍이 <b id="nEdge"></b>쌍뿐입니다. 그 안에서는 잘 맞지만 표본이 작다는 점은 남습니다.</li>
</ul>

<h2><span class="num">7</span>향 지도 데이터는 어떻게 생겼나</h2>
<p>지도 데이터는 파일 하나입니다. 크게 <b>지도 전체 정보</b>와 <b>향수 200개</b>로 나뉩니다.</p>

<h3>지도 전체 정보</h3>
<table><thead><tr><th>이름</th><th>무엇인가</th><th>프론트에서 쓰는 곳</th></tr></thead><tbody>
<tr><td><code>bounds</code></td><td>지도의 좌표 범위 (0~1)</td><td>화면 크기에 맞게 늘리기</td></tr>
<tr><td><code>terrain</code></td><td>향수가 얼마나 몰려 있는지 격자로 만든 값</td><td>땅과 바다, 밀도 음영</td></tr>
<tr><td><code>contours</code></td><td>해안선</td><td>육지 테두리 그리기</td></tr>
<tr><td><code>families</code> <b>(신규)</b></td><td><b>향 계열 9개</b>의 영역 · 이름 · 라벨 위치</td><td>계열 색면과 이름 표시</td></tr>
<tr><td><code>regions</code></td><td>원래 지도의 덩어리 7개 <b>(호환용, 나중에 제거)</b></td><td>전환 기간에만</td></tr>
<tr><td><code>points</code></td><td>향수 200개</td><td>지도 위의 점</td></tr>
</tbody></table>

<h3>향수 하나는 이렇게 생겼습니다</h3>
<pre id="ex"></pre>
<table><thead><tr><th>항목</th><th>무엇인가</th></tr></thead><tbody>
<tr><td><code>x</code>, <code>y</code></td><td>지도 위 위치. 0~1 이라 화면 크기에 맞춰 곱하면 됩니다</td></tr>
<tr><td><code>families</code> <b>(신규)</b></td><td><b>이 향수가 속한 향 계열과 그 비중.</b> 1~3개입니다.
 비중은 "이 향수에서 그 계열이 차지하는 몫" 이고 합이 1 이하입니다</td></tr>
<tr><td><code>top_accords</code></td><td>향 특성 태그와 세기. 계열 비중을 계산한 원본입니다</td></tr>
<tr><td><code>neighbors</code></td><td><b>닮은 향수 10개.</b> 위치와 무관하게 향 데이터로 계산합니다 —
 배치를 바꿔도 이 목록은 변하지 않습니다</td></tr>
<tr><td><code>korea</code></td><td>국내 인기 순위와 근거</td></tr>
<tr><td><code>region</code></td><td>원래 지도의 덩어리 번호 (호환용)</td></tr>
</tbody></table>

<div class="big"><p><b>가장 중요한 변화</b> — 향수 하나가 <b>여러 계열에 속할 수 있게</b> 됐습니다.</p>
<p id="pMulti" class="note"></p></div>

<h2><span class="num">8</span>남은 일</h2>
<ul>
<li><b>프론트 확인</b> — 모든 점의 위치가 바뀌고 파일이 커집니다. 확인 후 정식 반영합니다.
 <span class="note">지금은 기존 데이터를 그대로 두고 새 파일을 따로 만들어 둔 상태입니다.</span></li>
<li><b>모바일 라벨</b> — 좁은 화면(375px)에서 계열 이름 3개가 화면 가장자리에 걸립니다.
 태블릿 이상은 9개 전부 문제없습니다.</li>
<li><b>사용자 테스트</b> — "계열 이름을 보고 탐색 방향을 정하는가" 는 사람이 써봐야 압니다.</li>
<li><b>머스크·파우더리 계열 정의</b> — 이 계열의 대표 태그가 향수 절반에 붙어 있어
 계열을 가르는 기준으로 쓰기 애매합니다. 따로 검토합니다.</li>
</ul>

<p class="note" style="margin-top:32px">
모든 판단 근거와 수치는 <code>MAP/docs/DECISIONS.md</code> 에 남겨 뒀습니다.
실패한 시도도 함께 기록했습니다.</p>

</div>
<script>
const D=__PAYLOAD__;
function dec(s,N){const a=new Int16Array(N);let i=0,p=0;
 while(p<s.length){const c=s[p++];const v=(c==='z')?-1:(c.charCodeAt(0)-97);
  let n='';while(p<s.length&&s[p]>='0'&&s[p]<='9'){n+=s[p++];}
  const k=+n;a.fill(v,i,i+k);i+=k;}return a;}
function hex(h){return [parseInt(h.slice(1,3),16),parseInt(h.slice(3,5),16),parseInt(h.slice(5,7),16)];}
function css(v){return getComputedStyle(document.documentElement).getPropertyValue(v).trim();}
function drawMap(cid,S){
 const F=dec(S.grid,S.W*S.H),cv=document.getElementById(cid),ctx=cv.getContext('2d');
 const off=document.createElement('canvas');off.width=S.W;off.height=S.H;
 const oc=off.getContext('2d'),img=oc.createImageData(S.W,S.H),d=img.data,sea=hex(css('--sea')||'#e9eef0');
 for(let r=0;r<S.H;r++)for(let c=0;c<S.W;c++){
  const i=r*S.W+c,v=F[i],o=((S.H-1-r)*S.W+c)*4;
  const col=v<0?sea:hex(S.items[v].color);
  d[o]=col[0];d[o+1]=col[1];d[o+2]=col[2];d[o+3]=v<0?255:205;}
 oc.putImageData(img,0,0);
 const w=cv.clientWidth||400,h=Math.round(w*S.H/S.W),dpr=Math.min(devicePixelRatio||1,2);
 cv.width=w*dpr;cv.height=h*dpr;cv.style.height=h+'px';
 ctx.setTransform(dpr,0,0,dpr,0,0);ctx.imageSmoothingEnabled=true;ctx.drawImage(off,0,0,w,h);
 const bx=S.bounds;
 S.points.forEach(p=>{
  const x=(p[0]-bx.x_min)/(bx.x_max-bx.x_min)*w, y=h-(p[1]-bx.y_min)/(bx.y_max-bx.y_min)*h;
  ctx.beginPath();ctx.arc(x,y,2.4,0,6.2832);ctx.fillStyle=S.items[p[2]].color;ctx.fill();
  ctx.lineWidth=.8;ctx.strokeStyle=css('--card')||'#fff';ctx.stroke();});}
function legend(lid,S){document.getElementById(lid).innerHTML=
 S.items.slice().sort((a,b)=>b.area-a.area).map(it=>
  `<span><i style="background:${it.color}"></i>${it.name}</span>`).join('');}
function pct(v){return (v<0.01?(v*100).toFixed(2):(v*100).toFixed(1))+'%';}
function tbl(tid,S,tags){
 document.getElementById(tid).querySelector('tbody').innerHTML=
  S.items.slice().sort((a,b)=>b.area-a.area).map(it=>
   `<tr><td>${it.name}</td>${tags?`<td class="note">${it.tags||'—'}</td>`:''}
    <td class="n">${it.n}</td><td class="n">${pct(it.area)}</td>
    <td class="n">${(it.blob*100).toFixed(0)}%</td>
    <td class="${it.ok?'ok':'bad'}">${it.ok?'읽힌다':'너무 작다'}</td></tr>`).join('');}
const s=D.summary;
document.getElementById('kpi').innerHTML=[
 ['이름 있는 영역',`${s.new_named} / ${s.new_total}`,`전에는 ${s.old_named} / ${s.old_total}`],
 ['구역으로 읽히는 계열',`${s.new_ok} / ${s.new_total}`,`전에는 ${s.old_ok} / ${s.old_total}`],
 ['가장 큰 / 작은 영역',`${(s.new_area_max/s.new_area_min).toFixed(1)}배`,
  `전에는 ${(s.old_area_max/s.old_area_min).toFixed(0)}배 차이`],
 ['교체한 향수',`0개`,`200개 그대로`]].map(k=>
 `<div><span class="l">${k[0]}</span><span class="v">${k[1]}</span><span class="d">${k[2]}</span></div>`).join('');
document.getElementById('pSkew').innerHTML=
 `가장 큰 영역이 지도의 <b>${pct(s.old_area_max)}</b>, 가장 작은 영역이 `+
 `<b>${pct(s.old_area_min)}</b> 였습니다. <b>${(s.old_area_max/s.old_area_min).toFixed(0)}배</b> 차이입니다. `+
 `작은 두 영역은 화면에서 사실상 보이지 않았습니다. `+
 `최종 지도는 ${pct(s.new_area_min)} ~ ${pct(s.new_area_max)} `+
 `(<b>${(s.new_area_max/s.new_area_min).toFixed(1)}배</b>) 로 좁혀졌습니다.`;
document.getElementById('nNew').innerHTML=
 `"한 덩어리" = 그 계열 영역 중 가장 큰 조각의 비율. 낮으면 영역이 여러 군데로 흩어져 `+
 `"그 구역" 이라고 부를 수 없습니다. 9개 전부 기준(면적 ${D.area_min*100}% 이상 · `+
 `한 덩어리 ${D.blob_min*100}% 이상)을 넘습니다.`;
const e=D.example;
document.getElementById('ex').textContent=
`{
  "brand": "${e.brand}",
  "name": "${e.name}",
  "x": ${e.x},  "y": ${e.y},          // 지도 위 위치 (0~1)

  "families": [                       // 이 향수가 속한 향 계열
${e.families.map(f=>`    { "name_ko": "${f.ko}", "weight": ${f.w} }`).join(',\\n')}
  ],

  "top_accords": [${e.accords.map(a=>`"${a}"`).join(', ')}, ...],
  "neighbors":   [ 닮은 향수 ${e.neighbors}개 ],
  "korea":       { "selection_rank": ${e.rank} }
}`;
document.getElementById('pMulti').innerHTML=
 `200개 중 계열 1개 <b>${s.multi_1}개</b> · 2개 <b>${s.multi_2}개</b> · 3개 <b>${s.multi_3}개</b>. `+
 `예를 들어 위 향수는 두 계열에 걸쳐 있어서 <b>두 구역 사이</b>에 놓입니다. `+
 `이런 향수가 사용자를 다른 계열로 데려가는 다리가 됩니다.`;
// ---- 9계열 근거 표 3개 ----
const w9=D.why9;
const og=w9.origin;
document.getElementById('wN').textContent=og.wheel_total;
document.getElementById('ifN').textContent=og.ifra.terms;
document.getElementById('acN').textContent=og.accord_total;
document.getElementById('nWheel').innerHTML=
 `위 7개가 휠 <b>${og.wheel_total}개 중 ${og.wheel_covered}개</b>를 덮습니다. 나머지 하나인 `+
 `<code>Floral Amber</code>(꽃 + 앰버)만 두 축 사이에 걸쳐 있어 독립 계열로 두지 않았습니다.`;
document.getElementById('tWheel').querySelector('tbody').innerHTML=og.wheel.map(x=>
 `<tr><td><b>${x.ko}</b></td><td>${x.src}</td>
  <td class="n">${x.src.split(' · ').length}</td></tr>`).join('');
const IF=og.ifra;
document.getElementById('tIfra').querySelector('tbody').innerHTML=[
 ['Gourmand',IF.gourmand.n,`${IF.gourmand.rank}위`,'<span class="bad">없다</span>'],
 ['Musk Like + Powdery',IF.musk_sum,`${IF.musk.rank}위 · ${IF.powdery.rank}위`,
  '<span class="bad">없다</span>'],
 ['Amber <span class="note">(비교용)</span>',IF.amber.n,`${IF.amber.rank}위`,'있다']
].map(r=>`<tr><td>${r[0]}</td><td class="n">${r[1]}건</td>
 <td class="n">${r[2]}</td><td>${r[3]}</td></tr>`).join('');
document.getElementById('nIfra').innerHTML=
 `구르망은 ${IF.terms}종 중 <b>${IF.gourmand.rank}위</b>로, 휠에 독립 계열이 있는 `+
 `<code>Amber</code> 라는 이름(${IF.amber.n}건)보다도 자주 나옵니다. `+
 `이건 <b>원료에 붙은 이름 단위 비교라 계열 크기와 같지는 않습니다</b> — `+
 `휠의 Amber 계열은 이 이름 하나보다 넓습니다. 다만 "휠에 없으니 계열로 두지 말자" 는 `+
 `근거가 되지 못한다는 것은 보여 줍니다.`;
const B=og.basis, tot=og.share_total, sp=x=>`${(x/tot*100).toFixed(x/tot<0.01?2:0)}%`;
document.getElementById('pBasis').innerHTML=
 `<p><b>${sp(B.WHEEL.share)}</b> — 휠에서 온 7계열 (태그 ${B.WHEEL.n}종)</p>`+
 `<p><b>${sp(B.IFRA.share)}</b> — 휠에 없어 IFRA 근거로 넣은 2계열 (태그 ${B.IFRA.n}종)</p>`+
 `<p><b>${sp(og.unmapped_share)}</b> — 어느 계열에도 못 넣은 태그 ${B.NONE.n}종 `+
 `<span class="note">(plastic · rubber 처럼 향 계열로 볼 수 없는 것들)</span></p>`;
document.getElementById('tMass').querySelector('tbody').innerHTML=og.fam.map((x,i)=>
 `<tr><td>${x.basis==='IFRA'?'<b>'+x.ko+'</b>':x.ko}</td>
  <td class="note">${x.basis==='WHEEL'?'Fragrance Wheel':'IFRA (휠에 없음)'}</td>
  <td class="n">${x.n}종</td>
  <td class="n ${x.basis==='IFRA'?'ok':''}">${x.share.toFixed(2)}</td></tr>`).join('');
const CH=og.changed.map(c=>`<code>${c.accord}</code>`).join(' · ');
document.getElementById('pAssign').innerHTML=
 `태그 ${og.accord_total}종에 하나씩 계열과 근거 문구를 붙였습니다. `+
 `IFRA 이름과 <b>정확히 일치하는 것이 ${og.levels.exact}종</b>, `+
 `관련어로 연결되는 것이 ${og.levels.related}종, 대응이 없어 향 인상으로 판단한 것이 `+
 `${og.levels.none}종입니다. 이 중 <b>판단이 갈리는 ${og.review_required}종만 사람 검토 대상</b>으로 `+
 `표시했고, 팀이 그중 ${og.changed.length}건을 바꿨습니다 — ${CH}. `+
 `특히 <code>fresh</code> 는 보유율이 25%나 되지만 <b>어느 축의 신선함인지 데이터가 구분하지 않아 `+
 `어느 계열에도 넣지 않았습니다.</b>`;
document.getElementById('tSets').querySelector('tbody').innerHTML=w9.sets.map(x=>
 `<tr><td>${x.label}</td><td class="n">${x.k}</td>
  <td class="n ${x.rk>=3?'ok':'bad'}">${x.rk.toFixed(2)}배</td>
  <td class="n">${(x.cov*100).toFixed(0)}%</td>
  <td>${x.named?'있다':'<span class="bad">없다</span>'}</td>
  <td class="note">${x.note}</td></tr>`).join('');
document.getElementById('tCounts').querySelector('tbody').innerHTML=w9.counts.map(x=>{
 const best=x.k===9;
 return `<tr><td>${x.label}</td>
  <td class="n ${best?'ok':''}">${(x.kept*100).toFixed(1)}%</td>
  <td class="n ${best?'ok':'bad'}">${x.dropped_tags}종</td>
  <td class="n ${best?'ok':'bad'}">${x.top_lost}개</td>
  <td class="n ${x.half_lost===0?'ok':'bad'}">${x.half_lost}개</td>
  <td class="n ${best?'ok':''}">${x.ratio_g.toFixed(2)}배</td></tr>`;}).join('');
const c7=w9.counts.find(x=>x.k===7), c9=w9.counts.find(x=>x.k===9);
document.getElementById('pLoss').innerHTML=
 `<b>7개로 줄이면 향수 ${c7.top_lost}개는 "가장 강한 향 특성" 이 통째로 버려집니다.</b> `+
 `${c7.half_lost}개는 향 신호의 절반 이상을 잃습니다. `+
 `9개일 때는 각각 <b>${c9.top_lost}개 · ${c9.half_lost}개</b> 입니다. `+
 `그리고 줄일수록 지도에서 뭉치는 정도도 떨어집니다 `+
 `(${c9.ratio_g.toFixed(2)}배 → ${c7.ratio_g.toFixed(2)}배).`;
document.getElementById('tMerge').querySelector('tbody').innerHTML=w9.merge.map(x=>{
 const top=Object.entries(x.sizes).sort((a,b)=>b[1]-a[1]).slice(0,2);
 return `<tr><td>${x.label}</td><td class="n bad">${(x.max_share*100).toFixed(0)}%</td>
  <td class="note">앰버가 ${x.sizes.AMBER}개로 불어나 가장 큰 계열(${top[0][1]}개)과 맞먹습니다</td></tr>`;}).join('');
// ---- 거리의 의미 ----
const di=D.dist, wt=di.weights;
document.getElementById('wBox').innerHTML=
 `<p><b>향 성분이 겹치는 정도</b> <span class="note">— 가장 큰 몫 (${(wt.base_similarity_weight*100)}%)</span><br>
  <span class="note">두 향수가 같은 향 원료와 특성을 얼마나 공유하는가. 원래 지도가 쓰던 유일한 기준입니다.</span></p>
  <p><b>향 계열 구성이 비슷한 정도</b> <span class="note">— ${(wt.family_profile_weight*100)}%</span><br>
  <span class="note">"우디 60% · 앰버 30%" 같은 계열 비율이 닮았는가. 계열이 뭉치게 만드는 힘입니다.</span></p>
  <p><b>사용자가 느끼는 인상</b> <span class="note">— ${(wt.perception_weight*100)}%</span><br>
  <span class="note">계절감과 성별 인상 투표. 성분이 달라도 "느낌이 비슷한" 향수를 이어 줍니다.</span></p>`;
document.getElementById('tTrust').querySelector('tbody').innerHTML=[
 ['지도에서 이웃인 10개 중 향 데이터로도 가까운 것',
  (di.trust*10).toFixed(1)+' 개', '옆에 있으면 닮았다는 약속이 지켜지는 정도'],
 ['사용자가 "닮았다" 고 투표한 쌍이 지도에서 놓인 위치',
  '상위 '+(di.reminds*100).toFixed(0)+'%', '가까울수록 좋습니다. 무작위면 50% 입니다'],
 ['향 데이터 거리 순서와 지도 거리 순서가 맞는 정도',
  di.rank_corr.toFixed(2), '1 이면 완벽. 평면에 눌러 담으니 완벽할 수 없습니다']
].map(r=>`<tr><td>${r[0]}</td><td class="n ok">${r[1]}</td><td class="note">${r[2]}</td></tr>`).join('');
document.getElementById('pairs').innerHTML=di.pairs.map(p=>
 `<div class="big"><p><b>${p.a}</b> ↔ <b>${p.b}</b></p>
  <p class="note">지도 거리 ${p.map} (거의 붙어 있음) · 향 데이터 거리 ${p.scent}<br>
  계열 구성 — ${p.fa} / ${p.fb}</p></div>`).join('');
document.getElementById('thBase').textContent=di.ladder.base+' 기준';
document.getElementById('tLadder').querySelector('tbody').innerHTML=di.ladder.steps.map(x=>
 `<tr><td>${x.label}</td><td>${x.who}</td><td class="n">${x.map}</td><td class="n">${x.scent}</td></tr>`).join('');
document.getElementById('nEdge').textContent=di.edges;
function draw(){drawMap('cOld',D.old);drawMap('cNew',D.new);}
legend('lOld',D.old);legend('lNew',D.new);
tbl('tOld',D.old,true);tbl('tNew',D.new,false);
addEventListener('resize',draw);
matchMedia('(prefers-color-scheme:dark)').addEventListener('change',draw);
setTimeout(draw,0);
</script></body></html>
"""


if __name__ == "__main__":
    main()

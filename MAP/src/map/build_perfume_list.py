"""지도에 올라간 향수 200개(+예비 20개)를 사람이 읽을 수 있는 목록으로 낸다.

Run with venv/Scripts/python.exe src/map/build_perfume_list.py

`korea_representative_perfumes_top200.csv` 는 파이프라인 출력이라 RRF 점수 같은
내부 열이 27개인데, 정작 사람이 확인하고 싶은 것 — **국내 상품명, 향 특징, 지도 영역** —
이 없다. 그래서 여러 산출물을 조인해 검토용 목록을 만든다.

산출물 셋을 항상 같이 만든다. 따로 관리하면 어긋난다.

  - output/korea_map_perfume_list.csv    엑셀에서 열어 정렬·필터·주석
  - docs/korea_map_perfume_list.html     검색·필터되는 표 (데이터 인라인, 단독 파일)
  - output/korea_map_vocabulary.csv      지도에 등장하는 accord 60종 · note 411종 전수

세 번째는 화면에 어떤 향 이름이 뜰 수 있는지를 정리한 것이다. 프론트가 아이콘·번역·필터를
붙이려면 어휘 전체가 필요하고, 대표 향수 200개가 바뀌면 어휘도 바뀐다.

이 스크립트는 판정하지 않는다. 이미 확정된 결과를 옮겨 적기만 한다.
"""
import html
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]  # MAP/
DATA = ROOT / "data/korea_popularity"
MAP_JSON = ROOT / "output/korea_scent_map_v2.json"
CSV_OUT = ROOT / "output/korea_map_perfume_list.csv"
VOCAB_OUT = ROOT / "output/korea_map_vocabulary.csv"
HTML_OUT = ROOT / "docs/korea_map_perfume_list.html"

SEASON_KO = {"winter": "겨울", "spring": "봄", "summer": "여름", "autumn": "가을"}
GENDER_KO = {"unisex": "공용", "female": "여성", "male": "남성"}
# 매칭 근거 문자열 -> 사람이 읽는 신뢰 표시. 근거를 요약할 뿐 판정을 바꾸지 않는다.
BASIS_KO = {
    "snapshot manual confirmation": "사람 확정",
    "human confirmation review": "사람 검토",
    "brand exact/explicit alias": "자동 판정",
}


def basis_label(bases: list[str]) -> str:
    """여러 상품 묶음이 한 향수에 붙으면 근거가 섞인다. 사람 근거가 하나라도 있으면 그것을 쓴다."""
    labels = []
    for b in bases:
        for key, ko in BASIS_KO.items():
            if str(b).startswith(key):
                labels.append(ko)
                break
        else:
            labels.append("기타")
    for ko in ("사람 검토", "사람 확정", "자동 판정", "기타"):
        if ko in labels:
            return ko
    return ""


def build() -> pd.DataFrame:
    points = {p["fragrantica_id"]: p for p in json.loads(MAP_JSON.read_text(encoding="utf-8"))["points"]}
    regions = {r["id"]: " · ".join(a["name"] for a in r["label_accords"])
               for r in json.loads(MAP_JSON.read_text(encoding="utf-8"))["regions"]["items"]}
    commercial = pd.read_csv(DATA / "korea_commercial_identities.csv",
                             keep_default_na=False).set_index("commercial_identity_id")
    members = pd.read_csv(DATA / "korea_commercial_identity_members.csv", keep_default_na=False)
    raw_names = members.groupby("commercial_identity_id", sort=False).product_name_raw.apply(
        lambda s: " | ".join(dict.fromkeys(s.astype(str))))

    frames = []
    for path, role in ((DATA / "korea_representative_perfumes_top200.csv", "지도 200"),
                       (DATA / "korea_representative_perfumes_reserve20.csv", "예비 20")):
        f = pd.read_csv(path, keep_default_na=False)
        f["역할"] = role
        frames.append(f)
    sel = pd.concat(frames, ignore_index=True)

    def num(v):
        return "" if str(v).strip() in ("", "nan") else int(float(v))

    rows = []
    for r in sel.itertuples(index=False):
        fid = int(r.fragrantica_id)
        cis = [c for c in str(r.commercial_identity_ids).split("|") if c]
        p = points.get(fid)                      # 예비 20개는 지도 JSON 에 없다
        seasons = (p or {}).get("seasons") or {}
        daypart = (p or {}).get("daypart") or {}
        accords = (p or {}).get("top_accords") or []
        rows.append({
            "역할": r.역할,
            "순위": num(r.selection_rank),
            "화해 순위": num(r.best_hwahae_rank),
            "브랜드": r.fragrantica_brand,
            "향수명": r.fragrantica_name,
            "출시": num(r.fragrantica_year),
            "국내 상품명": " ‖ ".join(raw_names.get(c, "") for c in cis),
            "국내 브랜드 표기": " / ".join(dict.fromkeys(
                str(commercial.at[c, "canonical_brand"]) for c in cis if c in commercial.index)),
            "지도 영역": "" if p is None else p["region"],
            "영역 성격": "" if p is None else regions.get(p["region"], ""),
            "대표 향": " · ".join(f'{a["name"]}({a["strength"]})' for a in accords[:3]),
            "잘 맞는 계절": SEASON_KO.get(max(seasons, key=seasons.get)) if seasons else "",
            "밤/낮": ("밤 우세" if daypart.get("night", 0) > 0.55 else
                     "낮 우세" if daypart.get("day", 0) > 0.55 else
                     "비슷" if daypart else ""),
            "성별 표기": GENDER_KO.get((p or {}).get("gender"), ""),
            "매칭 근거": basis_label([commercial.at[c, "fragrantica_match_basis"]
                                  for c in cis if c in commercial.index]),
            "상품 묶음 수": int(r.commercial_identity_count),
            "무신사": num(r.best_musinsa_rank),
            "올리브영": num(r.best_oliveyoung_rank),
            "롯데": num(r.best_lotte_rank),
            "지도 x": "" if p is None else round(p["x"], 4),
            "지도 y": "" if p is None else round(p["y"], 4),
            "fragrantica_id": fid,
        })
    out = pd.DataFrame(rows)
    assert out.fragrantica_id.is_unique, "같은 Fragrantica ID 가 두 번 있다"
    return out


def build_vocabulary() -> pd.DataFrame:
    """지도 200개에 등장하는 accord·note 를 전수 집계한다.

    유사도는 두 향수가 **공유하는** 것으로만 계산되므로, 한 향수에만 있는 note 는
    어떤 쌍도 잇지 못한다. 그걸 `유사도 기여` 열로 표시한다.
    """
    import sys as _sys
    _sys.path.insert(0, str(ROOT / "src/common"))
    import scent_map as sm

    top = pd.read_csv(DATA / "korea_representative_perfumes_top200.csv", keep_default_na=False)
    rows = sm.load_perfumes().set_index("id").loc[top.fragrantica_id.astype(int).tolist()].reset_index()
    idf = sm.load_note_idf()
    n = len(rows)

    acc_count, acc_strength, acc_first = {}, {}, {}
    for lst in rows.accord_list:
        for rank, (name, strength) in enumerate(sorted(lst, key=lambda x: -x[1])):
            acc_count[name] = acc_count.get(name, 0) + 1
            acc_strength.setdefault(name, []).append(strength)
            if rank == 0:
                acc_first[name] = acc_first.get(name, 0) + 1
    note_count = {}
    for s in rows.note_set:
        for name in s:
            note_count[name] = note_count.get(name, 0) + 1

    out = []
    for name, c in sorted(acc_count.items(), key=lambda kv: (-kv[1], kv[0])):
        out.append({"종류": "accord", "이름": name, "보유 향수": c, "비율": round(c / n, 4),
                    "평균 강도": round(float(np.mean(acc_strength[name])), 1),
                    "최고 강도": int(max(acc_strength[name])),
                    "1순위 횟수": acc_first.get(name, 0), "IDF": "",
                    "유사도 기여": "가능" if c >= 2 else "없음 (한 향수에만)"})
    for name, c in sorted(note_count.items(), key=lambda kv: (-kv[1], kv[0])):
        out.append({"종류": "note", "이름": name, "보유 향수": c, "비율": round(c / n, 4),
                    "평균 강도": "", "최고 강도": "", "1순위 횟수": "",
                    "IDF": round(float(idf[name]), 3) if name in idf else "",
                    "유사도 기여": "가능" if c >= 2 else "없음 (한 향수에만)"})
    return pd.DataFrame(out)


HTML_TEMPLATE = """<title>지도에 올라간 향수 220개</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Gothic+A1:wght@700;800&family=Noto+Sans+KR:wght@300;400;500&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
:root{
  --paper:#f2f1ef; --surface:#fbfaf8; --surface-2:#e9e6e0;
  --ink:#1c1b19; --ink-2:#3d3b37; --muted:#78746d;
  --hair:#d6d3cd; --hair-2:#e6e3dd; --accent:#0d6e6e;
  --on-fill:#f8f7f5; --hi:#fdf3d4;
  --r0:#4c7a4a; --r1:#b4506b; --r2:#2c7f8c; --r3:#7a5b3a;
  --r4:#3f6bb8; --r5:#c08a24; --r6:#8265ab; --r7:#c4553c;
}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
  --paper:#161514; --surface:#201f1d; --surface-2:#2b2926;
  --ink:#efedea; --ink-2:#c8c4be; --muted:#918c84;
  --hair:#3a3733; --hair-2:#2e2c29; --accent:#5fbdbd;
  --on-fill:#161514; --hi:#3a3218;
  --r0:#7aa877; --r1:#d97e97; --r2:#5fb3bf; --r3:#b08d62;
  --r4:#7d9fe0; --r5:#dcae4f; --r6:#a992cf; --r7:#e0836c;
}}
:root[data-theme="dark"]{
  --paper:#161514; --surface:#201f1d; --surface-2:#2b2926;
  --ink:#efedea; --ink-2:#c8c4be; --muted:#918c84;
  --hair:#3a3733; --hair-2:#2e2c29; --accent:#5fbdbd;
  --on-fill:#161514; --hi:#3a3218;
  --r0:#7aa877; --r1:#d97e97; --r2:#5fb3bf; --r3:#b08d62;
  --r4:#7d9fe0; --r5:#dcae4f; --r6:#a992cf; --r7:#e0836c;
}
*{box-sizing:border-box}
body{background:var(--paper);color:var(--ink);
  font-family:"Noto Sans KR",-apple-system,"Malgun Gothic",sans-serif;
  font-size:.875rem;font-weight:300;line-height:1.6;-webkit-font-smoothing:antialiased;margin:0}
.wrap{max-width:96rem;margin:0 auto;padding:clamp(1.5rem,4vw,2.5rem) clamp(.75rem,3vw,2rem) 4rem}
h1{font-family:"Gothic A1",sans-serif;font-weight:800;font-size:clamp(1.6rem,4vw,2.25rem);
  letter-spacing:-.015em;margin:0 0 .5rem;line-height:1.25}
.eyebrow{font-family:"IBM Plex Mono",monospace;font-size:.75rem;letter-spacing:.05em;color:var(--muted);margin:0 0 .75rem}
.lead{color:var(--ink-2);max-width:44rem;margin:0}
code{font-family:"IBM Plex Mono",monospace;font-size:.85em;background:var(--surface-2);padding:.1em .35em;border-radius:2px}

.bar{display:flex;flex-wrap:wrap;gap:.6rem;align-items:flex-end;margin:1.75rem 0 1rem;
  padding-bottom:1rem;border-bottom:1px solid var(--hair)}
.fld{display:flex;flex-direction:column;gap:.25rem}
.fld label{font-family:"IBM Plex Mono",monospace;font-size:.68rem;letter-spacing:.04em;color:var(--muted)}
.fld input,.fld select{font-family:"Noto Sans KR",sans-serif;font-size:.85rem;font-weight:400;
  padding:.4rem .55rem;border:1px solid var(--hair);border-radius:2px;background:var(--surface);color:var(--ink)}
.fld input{min-width:16rem}
.count{margin-left:auto;font-family:"IBM Plex Mono",monospace;font-size:.8rem;color:var(--muted);
  font-variant-numeric:tabular-nums;padding-bottom:.45rem}
.count b{color:var(--ink);font-weight:500}
:focus-visible{outline:2px solid var(--accent);outline-offset:2px}

.scroll{overflow-x:auto;border:1px solid var(--hair);border-radius:3px;background:var(--surface)}
table{border-collapse:separate;border-spacing:0;width:100%;min-width:64rem}
th,td{padding:.5rem .7rem;border-bottom:1px solid var(--hair-2);text-align:left;vertical-align:top}
thead th{position:sticky;top:0;z-index:1;background:var(--surface-2);color:var(--muted);
  font-family:"IBM Plex Mono",monospace;font-weight:500;font-size:.7rem;letter-spacing:.04em;
  white-space:nowrap;cursor:pointer;user-select:none;border-bottom:1px solid var(--hair)}
thead th:hover{color:var(--ink)}
thead th[aria-sort]{color:var(--accent)}
thead th .ar{opacity:.55;font-size:.9em}
tbody tr:hover{background:var(--hi)}
tbody tr:last-child td{border-bottom:0}
td.n{text-align:right;font-family:"IBM Plex Mono",monospace;font-variant-numeric:tabular-nums;white-space:nowrap;color:var(--ink-2)}
td.nm{min-width:14rem}
td.nm b{font-weight:500}
td.nm span{display:block;color:var(--muted);font-size:.78rem;line-height:1.45}
td.ko{min-width:18rem;max-width:26rem;color:var(--ink-2);font-size:.8rem;line-height:1.5}
td.ac{font-family:"IBM Plex Mono",monospace;font-size:.72rem;color:var(--ink-2);min-width:11rem;white-space:nowrap}
.rg{display:inline-flex;align-items:center;gap:.35rem;white-space:nowrap}
.rg i{width:.7rem;height:.7rem;border-radius:2px;flex:none}
.rg small{color:var(--muted);font-family:"IBM Plex Mono",monospace;font-size:.72rem}
.bd{display:inline-block;font-family:"IBM Plex Mono",monospace;font-size:.68rem;
  padding:.1rem .4rem;border-radius:2px;white-space:nowrap;background:var(--surface-2);color:var(--muted)}
.bd.h{background:var(--accent);color:var(--on-fill)}
.bd.r{background:var(--surface-2);color:var(--ink-2);border:1px solid var(--hair)}
.empty{padding:2.5rem;text-align:center;color:var(--muted)}
.foot{margin-top:1.5rem;color:var(--muted);font-size:.8rem;max-width:44rem;display:flex;flex-direction:column;gap:.5rem}
</style>
<div class="wrap">
  <p class="eyebrow">향해 · 향 지도 / 대표 향수 목록</p>
  <h1>지도에 올라간 향수 220개</h1>
  <p class="lead">
    향 지도에 표시되는 <strong>200개</strong>와 <strong>예비 20개</strong>입니다.
    브랜드·향수명·국내 상품명으로 검색되고, 열 제목을 누르면 정렬됩니다.
    같은 내용의 CSV는 <code>output/korea_map_perfume_list.csv</code>에 있습니다.
  </p>

  <div class="bar">
    <div class="fld">
      <label for="q">검색 — 브랜드 · 향수명 · 국내 상품명 · 향</label>
      <input id="q" type="search" placeholder="예: 조 말론, Bloom, 코튼, citrus" autocomplete="off">
    </div>
    <div class="fld">
      <label for="f-role">역할</label>
      <select id="f-role"><option value="">전체</option><option>지도 200</option><option>예비 20</option></select>
    </div>
    <div class="fld">
      <label for="f-region">지도 영역</label>
      <select id="f-region"></select>
    </div>
    <div class="fld">
      <label for="f-basis">매칭 근거</label>
      <select id="f-basis"><option value="">전체</option><option>사람 확정</option><option>사람 검토</option><option>자동 판정</option></select>
    </div>
    <div class="fld">
      <label for="f-hw">화해 순위</label>
      <select id="f-hw"><option value="">전체</option><option value="y">보유</option><option value="n">없음</option></select>
    </div>
    <p class="count" id="count"></p>
  </div>

  <div class="scroll">
    <table>
      <thead><tr id="head"></tr></thead>
      <tbody id="body"></tbody>
    </table>
  </div>
  <div id="empty" class="empty" hidden>조건에 맞는 향수가 없습니다.</div>

  <div class="foot">
    <p><b>매칭 근거</b>는 이 향수가 국내 상품과 연결된 방식입니다 —
      <span class="bd h">사람 검토</span> 최근 사람이 직접 판정,
      <span class="bd r">사람 확정</span> 이전에 사람이 확정,
      <span class="bd">자동 판정</span> 규칙으로 자동 확정.</p>
    <p><b>국내 상품명</b>은 쇼핑몰에 올라온 원문입니다. 한 향수에 여러 상품이 붙으면 <code>‖</code>로 구분했습니다.</p>
    <p><b>예비 20개</b>는 지도에 표시되지 않습니다. 200개 중 문제가 발견되면 교체용으로 씁니다.</p>
  </div>
</div>
<script id="rows" type="application/json">__ROWS__</script>
<script>
(function(){
const ROWS = JSON.parse(document.getElementById('rows').textContent);
const REGIONS = __REGIONS__;
const $ = id => document.getElementById(id);
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));

const COLS = [
  {k:'순위',      t:'순위',        c:'n'},
  {k:'화해 순위', t:'화해',        c:'n'},
  {k:null,        t:'브랜드 · 향수명', c:'nm', get:r=>`<b>${esc(r['브랜드'])}</b><span>${esc(r['향수명'])}${r['출시']?' · '+r['출시']:''}</span>`,
                  sort:r=>r['브랜드']+' '+r['향수명']},
  {k:'국내 상품명', t:'국내 상품명', c:'ko'},
  {k:'지도 영역', t:'영역',        c:'', get:r=>r['지도 영역']===''?'<span style="color:var(--muted)">—</span>'
                  :`<span class="rg"><i style="background:var(--r${r['지도 영역']})"></i>${r['지도 영역']}<small>${esc(r['영역 성격'].split(' · ')[0])}</small></span>`},
  {k:'대표 향',   t:'대표 향 (강도)', c:'ac'},
  {k:'잘 맞는 계절', t:'계절',     c:''},
  {k:'밤/낮',     t:'밤/낮',       c:''},
  {k:'성별 표기', t:'성별',        c:''},
  {k:'매칭 근거', t:'매칭 근거',   c:'', get:r=>{
      const cls = r['매칭 근거']==='사람 검토'?'bd h':r['매칭 근거']==='사람 확정'?'bd r':'bd';
      return r['매칭 근거']?`<span class="${cls}">${esc(r['매칭 근거'])}</span>`:''}},
  {k:'무신사',    t:'무신사',      c:'n'},
  {k:'올리브영',  t:'올리브영',    c:'n'},
  {k:'롯데',      t:'롯데',        c:'n'},
  {k:'fragrantica_id', t:'F.ID',   c:'n'},
];

$('head').innerHTML = COLS.map((c,i)=>`<th data-i="${i}" title="정렬">${esc(c.t)} <span class="ar">↕</span></th>`).join('');
$('f-region').innerHTML = '<option value="">전체</option>' +
  REGIONS.map(r=>`<option value="${r.id}">${r.id} — ${esc(r.label)}</option>`).join('');

let sortI = 0, sortDir = 1;
const valOf = (r,c) => c.sort ? c.sort(r) : r[c.k];

function apply(){
  const q = $('q').value.trim().toLowerCase();
  const role = $('f-role').value, rg = $('f-region').value,
        bs = $('f-basis').value, hw = $('f-hw').value;
  let list = ROWS.filter(r=>{
    if (role && r['역할'] !== role) return false;
    if (rg !== '' && String(r['지도 영역']) !== rg) return false;
    if (bs && r['매칭 근거'] !== bs) return false;
    if (hw === 'y' && r['화해 순위'] === '') return false;
    if (hw === 'n' && r['화해 순위'] !== '') return false;
    if (!q) return true;
    return [r['브랜드'],r['향수명'],r['국내 상품명'],r['국내 브랜드 표기'],r['대표 향'],r['영역 성격']]
      .join(' ').toLowerCase().includes(q);
  });
  const c = COLS[sortI];
  list.sort((a,b)=>{
    const x = valOf(a,c), y = valOf(b,c);
    const xe = x === '' || x == null, ye = y === '' || y == null;
    if (xe && ye) return 0;
    if (xe) return 1;                        // 빈 값은 항상 뒤로
    if (ye) return -1;
    if (typeof x === 'number' && typeof y === 'number') return (x-y)*sortDir;
    return String(x).localeCompare(String(y),'ko')*sortDir;
  });

  $('body').innerHTML = list.map(r=>'<tr>'+COLS.map(c=>{
    const v = c.get ? c.get(r) : esc(r[c.k]);
    return `<td class="${c.c}">${v===''||v==null?'<span style="color:var(--muted)">—</span>':v}</td>`;
  }).join('')+'</tr>').join('');
  $('empty').hidden = list.length > 0;
  const hwN = list.filter(r=>r['화해 순위']!=='').length;
  $('count').innerHTML = `<b>${list.length}</b>개 표시 · 전체 ${ROWS.length}개 · 화해 순위 보유 <b>${hwN}</b>개`;
  document.querySelectorAll('#head th').forEach((th,i)=>{
    if (i===sortI){ th.setAttribute('aria-sort', sortDir>0?'ascending':'descending');
      th.querySelector('.ar').textContent = sortDir>0?'↑':'↓'; }
    else { th.removeAttribute('aria-sort'); th.querySelector('.ar').textContent='↕'; }
  });
}
$('head').addEventListener('click', e=>{
  const th = e.target.closest('th'); if (!th) return;
  const i = +th.dataset.i;
  if (i===sortI) sortDir = -sortDir; else { sortI = i; sortDir = 1; }
  apply();
});
['q','f-role','f-region','f-basis','f-hw'].forEach(id=>{
  $(id).addEventListener(id==='q'?'input':'change', apply);
});
apply();
})();
</script>
"""


def main() -> None:
    frame = build()
    CSV_OUT.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(CSV_OUT, index=False, encoding="utf-8-sig")   # utf-8-sig: 엑셀에서 한글이 깨지지 않는다

    doc = json.loads(MAP_JSON.read_text(encoding="utf-8"))
    regions = [{"id": r["id"],
                "label": " · ".join(a["name"] for a in r["label_accords"])}
               for r in doc["regions"]["items"]]
    rows = json.dumps(frame.to_dict("records"), ensure_ascii=False, separators=(",", ":"))
    assert "</script" not in rows, "행 데이터에 script 종료 태그가 들어 있다"
    HTML_OUT.write_text(
        HTML_TEMPLATE.replace("__ROWS__", rows)
                     .replace("__REGIONS__", json.dumps(regions, ensure_ascii=False)),
        encoding="utf-8")

    print(f"목록 {len(frame)}행 · 열 {len(frame.columns)}개")
    print(f"  역할: {frame.역할.value_counts().to_dict()}")
    print(f"  매칭 근거: {frame['매칭 근거'].value_counts().to_dict()}")
    print(f"  화해 순위 보유: {int((frame['화해 순위'] != '').sum())}개")
    print(f"  국내 상품명 비어 있음: {int((frame['국내 상품명'].str.strip() == '').sum())}개")
    vocab = build_vocabulary()
    vocab.to_csv(VOCAB_OUT, index=False, encoding="utf-8-sig")
    acc = vocab[vocab.종류 == "accord"]; note = vocab[vocab.종류 == "note"]
    solo = int((note["유사도 기여"] != "가능").sum())
    print(f"어휘: accord {len(acc)}종 · note {len(note)}종 "
          f"(한 향수에만 있는 note {solo}종 = {solo / len(note):.1%})")

    print(f"  -> {CSV_OUT.relative_to(ROOT)} ({CSV_OUT.stat().st_size:,} bytes)")
    print(f"  -> {VOCAB_OUT.relative_to(ROOT)} ({VOCAB_OUT.stat().st_size:,} bytes)")
    print(f"  -> {HTML_OUT.relative_to(ROOT)} ({HTML_OUT.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()

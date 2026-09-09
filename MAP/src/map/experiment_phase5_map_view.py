"""Phase 5 지도 뷰어 — 채택안(임계 0.24)의 향 계열 Territory 를 눈으로 확인한다.

`experiments/phase5b/field_seed42.npz` 의 Territory field 와
`experiments/phase4/coordinates_korea200.csv` 의 좌표를 합쳐 정적 HTML 하나로 만든다.
새로 계산하는 것은 없다 — 기록된 산출물을 그리기만 한다.

D28 에서 채택 임계가 0.30 → 0.24 로 바뀌었다. 탭 문구의 수치는
`experiments/phase5b/metrics.json` 에서 읽으므로 실험을 다시 돌리면 함께 갱신된다.

격자는 128x107 = 13,696칸이라 그대로 실으면 무겁다. 같은 계열이 이어지는 구간이
길어서 **런렝스 부호화(RLE)** 로 1.6KB 까지 줄어든다.

재현::

    python src/map/experiment_phase5_map_view.py

산출  experiments/phase5b/map_view.html
"""

import io
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in (HERE, os.path.join(HERE, "..", "common")):
    if p not in sys.path:
        sys.path.insert(0, p)
import build_korea_terrain as bkt   # noqa: E402

P5 = os.path.join("experiments", "phase5")
P5B = os.path.join("experiments", "phase5b")
P4 = os.path.join("experiments", "phase4")
# field_seed42.npz 의 키 (phase5b 조건 이름의 첫 토큰)
PANELS = ("0.24", "0.30", "T0", "0.20")
COND = {"0.24": "0.24", "0.30": "0.30 (T1)", "T0": "T0 (1위만)", "0.20": "0.20 (T2)"}
TITLE = {"0.24": "0.24 · 채택안", "0.30": "0.30 · 이전 제안",
         "T0": "T0 · 현재 방식 (1위만)", "0.20": "0.20 · 너무 낮춘 경우"}
FAMS = ["CITRUS", "FRUITY", "FLORAL", "GREEN", "AQUATIC", "WOODY", "AMBER",
        "GOURMAND", "MUSK"]
KO = ["시트러스", "프루티", "플로럴", "그린·아로마틱", "아쿠아틱", "우디",
      "앰버·스파이시", "구르망", "머스크·파우더리"]
COLOR = ["#d9b23a", "#d1553f", "#c56480", "#5f9a5c", "#3a9cab", "#9c7a52",
         "#d99a2e", "#9a7ec4", "#8595ac"]
EXTRA = {"0.24": "프루티가 면적 5.6% · 한 덩어리 100% 로 확실히 자리 잡는다.",
         "0.30": "프루티가 판정선(면적 3%)에 0.01%p 차이로 걸쳐 있다.",
         "T0": "프루티와 머스크에 구역이 없다.",
         "0.20": "구르망과 머스크가 무너진다. 계열끼리 먹어 들어간다."}


def rle(mask_ids):
    """런렝스 부호화. 값은 글자(a~i = 계열 0~8 · z = 바다), 길이는 숫자다.

    값을 숫자로 쓰면 계열 번호와 반복 횟수의 경계를 구분할 수 없다
    (".481" + "0513" -> ".4810513" 은 되돌릴 수 없다). 글자가 구분자 역할을 한다.
    """
    flat = mask_ids.ravel()
    out, prev, n = [], flat[0], 1

    def tok(v, k):
        return f"{'z' if v < 0 else chr(97 + int(v))}{k}"

    for v in flat[1:]:
        if v == prev:
            n += 1
        else:
            out.append(tok(prev, n))
            prev, n = v, 1
    out.append(tok(prev, n))
    return "".join(out)


def main() -> None:
    os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))  # MAP/
    z = np.load(os.path.join(P5B, "field_seed42.npz"), allow_pickle=True)
    m5b = json.load(io.open(os.path.join(P5B, "metrics.json"), encoding="utf-8"))
    agg = m5b["seed_aggregates"]
    ps = pd.read_csv(os.path.join(P5B, "per_seed.csv"))
    label, note = {}, {}
    for k in PANELS:
        a = agg[COND[k]]
        r = ps[(ps.condition == COND[k]) & (ps.seed == 42)].iloc[0]
        label[k] = TITLE[k]
        # 그림은 seed 42 한 장이고 판정은 시드 5개 평균이다. 둘이 다르므로 함께 적는다
        # (예: T0 는 seed 42 에서 8계열로 보이지만 5시드 평균은 7.4 다).
        note[k] = (f"<b>이 그림(seed 42)</b> 구역 {int(r.families_with_territory)}계열 · "
                   f"프루티 {r.fruity_area:.1%} · 조각 {int(r.fragments_total)}개"
                   f" &nbsp;|&nbsp; <b>판정 근거(시드 5개 평균)</b> 구역 "
                   f"{a['families_with_territory']['mean']:.1f}"
                   f" ± {a['families_with_territory']['std']:.1f}계열 · "
                   f"프루티 {a['fruity_area']['mean']:.1%} · "
                   f"덩어리 {a['fruity_blob']['mean']:.0%} · "
                   f"조각 {a['fragments_total']['mean']:.1f}개<br>{EXTRA[k]}")
    co = pd.read_csv(os.path.join(P4, "coordinates_korea200.csv"))
    co.columns = [c.lstrip("﻿") for c in co.columns]
    d0 = co[co.composition == "D0 현재"]
    ids = d0.fragrantica_id.astype(int).tolist()
    XY = d0[["x", "y"]].to_numpy(float)
    fs = pd.read_csv(os.path.join(P5, "family_scores.csv")).set_index(
        "fragrantica_id").loc[ids]
    share = fs[[f"share_{f}" for f in FAMS]].to_numpy()
    lo, hi, W, H, _s, _x, _y = bkt.make_grid(XY)

    grids = {}
    for name in PANELS:
        win, land = z[name], z[name + "_land"]
        usable = [str(v) for v in z[name + "_usable"]]
        m = np.full(win.shape, -1, dtype=int)
        for i, f in enumerate(usable):
            m[(win == i) & land] = FAMS.index(f)
        grids[name] = rle(m)

    gx = (XY[:, 0] - lo[0]) / (hi[0] - lo[0]) * (W - 1)
    gy = (XY[:, 1] - lo[1]) / (hi[1] - lo[1]) * (H - 1)
    pts = []
    for i in range(len(ids)):
        o = np.argsort(-share[i])[:2]
        pts.append([str(fs["name"].iloc[i]), str(fs.brand.iloc[i]), int(o[0]),
                    round(float(gx[i]), 1), round(float(gy[i]), 1),
                    round(float(share[i, o[0]]), 2), int(o[1]),
                    round(float(share[i, o[1]]), 2)])
    counts = [int((share.argmax(axis=1) == k).sum()) for k in range(len(FAMS))]

    payload = {"W": int(W), "H": int(H), "F": FAMS, "K": KO, "C": COLOR,
               "N": counts, "G": grids, "P": pts,
               "LABEL": label, "NOTE": note, "ORDER": list(PANELS)}
    html = TEMPLATE.replace("__PAYLOAD__", json.dumps(payload, ensure_ascii=False,
                                                      separators=(",", ":")))
    out = os.path.join(P5B, "map_view.html")
    io.open(out, "w", encoding="utf-8", newline="\n").write(html)
    print(f"격자 {W}x{H} · RLE " +
          " · ".join(f"{n} {len(g)}B" for n, g in grids.items()))
    print(f"향수 {len(pts)}개 · 계열 분포 {dict(zip(KO, counts))}")
    print(f"  -> {out}  ({os.path.getsize(out)/1024:.0f} KB)")


TEMPLATE = """<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>향 지도 — 계열 Territory (Phase 5)</title>
<style>
:root{--bg:#fbfcfc;--card:#fff;--ink:#14262b;--ink2:#33484e;--muted:#5d757c;
      --hair:#c6d2d1;--sea:#eef2f3}
@media (prefers-color-scheme:dark){:root{--bg:#0f1719;--card:#151f22;--ink:#e8eef0;
      --ink2:#b6c6ca;--muted:#8ba0a5;--hair:#2b3a3e;--sea:#111a1c}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
     font:15px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI","Malgun Gothic",sans-serif}
.wrap{max-width:900px;margin:0 auto;padding:24px 20px 40px}
h1{font-size:20px;font-weight:600;margin:0 0 4px}
.sub{color:var(--muted);font-size:13px;margin:0 0 18px}
.tabs{display:flex;gap:6px;margin-bottom:10px;flex-wrap:wrap}
.tab{padding:7px 13px;border:1px solid var(--hair);background:transparent;color:var(--ink2);
     border-radius:8px;cursor:pointer;font-size:13px;font-family:inherit}
.tab.on{background:var(--card);border-color:var(--ink2);color:var(--ink);font-weight:600}
.note{color:var(--muted);font-size:12.5px;margin:0 0 12px;min-height:38px;line-height:1.6}
.note b{color:var(--ink2);font-weight:600}
.stage{position:relative;background:var(--card);border:1px solid var(--hair);
       border-radius:12px;padding:10px}
canvas{width:100%;height:auto;display:block;border-radius:8px;cursor:crosshair}
.tip{margin-top:10px;min-height:52px;font-size:13px;color:var(--ink2);line-height:1.5}
.tip b{color:var(--ink)}
.legend{display:flex;flex-wrap:wrap;gap:6px;margin:14px 0 0}
.chip{display:inline-flex;align-items:center;gap:6px;padding:5px 10px;border-radius:999px;
      border:1px solid var(--hair);background:transparent;color:var(--ink2);cursor:pointer;
      font-size:12.5px;font-family:inherit}
.chip.on{border-color:var(--ink2);color:var(--ink)}
.chip i{width:10px;height:10px;border-radius:3px;display:inline-block}
.foot{color:var(--muted);font-size:12px;margin-top:18px;line-height:1.7}
</style></head><body><div class="wrap">
<h1>향 지도 — 향 계열 Territory</h1>
<p class="sub">국내 대표 향수 200개 · 좌표 C8b(seed 42) · 네 방식 모두 <b>같은 향수 · 같은 위치</b>다.
바뀌는 것은 색면(구역)을 그릴 때 각 향수가 어느 계열에 얼마나 기여하는지 정하는 <b>임계값</b>뿐이다.</p>
<div class="tabs" id="tabs"></div>
<p class="note" id="note"></p>
<div class="stage"><canvas id="cv"></canvas><p class="tip" id="tip">점에 커서를 올리면 향수 이름과 계열 비중이 나옵니다.</p></div>
<div class="legend" id="legend"></div>
<p class="foot">색면 = 그 칸을 어느 계열이 차지했는지(KDE argmax · 육지만). 회색 = 바다(향수 밀도 하위 40%).<br>
점 = 향수 200개, 색은 1위 계열. 계열 이름을 누르면 그 계열만 남습니다.<br>
출처: experiments/phase5b/field_seed42.npz · experiments/phase4/coordinates_korea200.csv (D28)</p>
</div>
<script>
const D=__PAYLOAD__;
function decode(s){const a=new Int8Array(D.W*D.H);let i=0,p=0;
 while(p<s.length){const c=s[p++];const v=(c==='z')?-1:(c.charCodeAt(0)-97);
  let n='';while(p<s.length&&s[p]>='0'&&s[p]<='9'){n+=s[p++];}
  const k=+n;a.fill(v,i,i+k);i+=k;}
 if(i!==D.W*D.H)console.error('RLE 길이 불일치',i,D.W*D.H);
 return a;}
const FIELD={};D.ORDER.forEach(n=>FIELD[n]=decode(D.G[n]));
let cur=D.ORDER[0],sel=null,hover=-1;
const cv=document.getElementById('cv'),ctx=cv.getContext('2d');
const off=document.createElement('canvas');off.width=D.W;off.height=D.H;
const octx=off.getContext('2d');
function css(v){return getComputedStyle(document.documentElement).getPropertyValue(v).trim();}
function hex(h){return [parseInt(h.slice(1,3),16),parseInt(h.slice(3,5),16),parseInt(h.slice(5,7),16)];}
function paint(){
 const f=FIELD[cur],img=octx.createImageData(D.W,D.H),d=img.data;
 const seaC=hex(css('--sea')||'#eef2f3');
 for(let r=0;r<D.H;r++)for(let c=0;c<D.W;c++){
  const i=r*D.W+c,v=f[i],o=((D.H-1-r)*D.W+c)*4;
  if(v<0){d[o]=seaC[0];d[o+1]=seaC[1];d[o+2]=seaC[2];d[o+3]=255;}
  else{const rgb=hex(D.C[v]);const dim=(sel!==null&&sel!==v);
   d[o]=rgb[0];d[o+1]=rgb[1];d[o+2]=rgb[2];d[o+3]=dim?40:210;}}
 octx.putImageData(img,0,0);
 const dpr=Math.min(window.devicePixelRatio||1,2);
 const w=cv.clientWidth||860,h=Math.round(w*D.H/D.W);
 cv.width=w*dpr;cv.height=h*dpr;cv.style.height=h+'px';
 ctx.setTransform(dpr,0,0,dpr,0,0);ctx.clearRect(0,0,w,h);
 ctx.imageSmoothingEnabled=true;ctx.drawImage(off,0,0,w,h);
 const sx=w/(D.W-1),sy=h/(D.H-1);
 D.P.forEach((p,i)=>{
  const x=p[3]*sx,y=h-p[4]*sy,dim=(sel!==null&&sel!==p[2]);
  ctx.beginPath();ctx.arc(x,y,i===hover?6.5:3.6,0,6.2832);
  ctx.fillStyle=D.C[p[2]];ctx.globalAlpha=dim?0.12:1;ctx.fill();
  ctx.lineWidth=i===hover?2.5:1;ctx.strokeStyle=css('--card')||'#fff';ctx.stroke();
  ctx.globalAlpha=1;});
 cv._sx=sx;cv._sy=sy;cv._h=h;}
function tabs(){const t=document.getElementById('tabs');t.innerHTML='';
 D.ORDER.forEach(n=>{const b=document.createElement('button');
  b.className='tab'+(n===cur?' on':'');b.textContent=D.LABEL[n];
  b.onclick=()=>{cur=n;tabs();document.getElementById('note').innerHTML=D.NOTE[n];paint();};
  t.appendChild(b);});}
function legend(){const l=document.getElementById('legend');l.innerHTML='';
 D.K.forEach((k,i)=>{const b=document.createElement('button');
  b.className='chip'+(sel===i?' on':'');
  b.innerHTML='<i style="background:'+D.C[i]+'"></i>'+k+' '+D.N[i];
  b.onclick=()=>{sel=(sel===i?null:i);legend();paint();};l.appendChild(b);});}
cv.addEventListener('mousemove',e=>{
 const r=cv.getBoundingClientRect(),mx=e.clientX-r.left,my=e.clientY-r.top;
 let best=-1,bd=1e9;
 D.P.forEach((p,i)=>{const x=p[3]*cv._sx,y=cv._h-p[4]*cv._sy;
  const d2=(x-mx)*(x-mx)+(y-my)*(y-my);if(d2<bd){bd=d2;best=i;}});
 const nh=(bd<=100)?best:-1;
 if(nh!==hover){hover=nh;paint();
  const t=document.getElementById('tip');
  if(hover<0){t.textContent='점에 커서를 올리면 향수 이름과 계열 비중이 나옵니다.';}
  else{const p=D.P[hover];
   t.innerHTML='<b>'+p[0]+'</b> · '+p[1]+'<br>'+D.K[p[2]]+' '+p[5].toFixed(2)+
    ' · '+D.K[p[6]]+' '+p[7].toFixed(2)+
    (p[7]>=0.30?'  <span style="color:var(--muted)">— T1 에서 두 계열 모두에 기여</span>':'');}}});
cv.addEventListener('mouseleave',()=>{if(hover>=0){hover=-1;paint();
 document.getElementById('tip').textContent='점에 커서를 올리면 향수 이름과 계열 비중이 나옵니다.';}});
window.addEventListener('resize',paint);
matchMedia('(prefers-color-scheme:dark)').addEventListener('change',paint);
tabs();legend();document.getElementById('note').innerHTML=D.NOTE[cur];
setTimeout(paint,0);
</script></body></html>
"""


if __name__ == "__main__":
    main()

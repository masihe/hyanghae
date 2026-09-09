"""Phase 6 UX 프로토타입 — 9개 계열 라벨이 첫 화면에서 읽히는가.

데이터가 답할 수 없는 질문이라 **실제 화면**을 만든다. v3 초안
(`experiments/phase6/korea_scent_map_v3.json`)을 그대로 읽어 렌더하고,
읽히지 않는 지점을 화면에서 드러낸다.

측정으로 미리 확인한 것::

    라벨 앵커 9개 전부 자기 계열 땅 위에 있다 (9/9)
    앵커 사이 최소 간격 0.122 (우디 ↔ 앰버·스파이시)
      -> 지도 폭 375px 에서 46px · 768px 에서 93px · 1280px 에서 156px
    앵커가 가장자리에 붙은 계열 — 아쿠아틱 x=0.011 · 플로럴 x=0.972 ·
      우디/앰버 y≈0.05 · 머스크 y=0.794

즉 **모바일에서 우디·앰버 라벨이 겹치고, 가장자리 라벨은 화면 밖으로 나간다.**
프로토타입은 그것을 감추지 않고 진단 패널에 센다.

프로토타입이 다루는 것::

    뷰포트   375 (모바일) · 768 (태블릿) · 1280 (데스크톱)
    줌 3단계 멀리(색면+라벨) · 중간(+점) · 가까이(+향수 이름)
    라벨     앵커 배치 -> 가장자리 클램프 -> 겹침 밀어내기. 각 단계를 센다
    탐색     계열 누르기 -> 영역 강조 + 향수 목록(가중치 순)
    경계     2계열 이상 향수 95개 토글 — 다른 계열로 넘어가는 다리

재현::

    python src/map/build_phase6_ux_prototype.py

산출  experiments/phase6/ux_prototype.html · label_report.json

프로덕션 파일은 읽지도 쓰지도 않는다 (v3 초안만 읽는다).
"""

import io
import json
import os
import sys

import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join("experiments", "phase6")
V3 = os.path.join(OUT_DIR, "korea_scent_map_v3.json")
OUT = os.path.join(OUT_DIR, "ux_prototype.html")

COLOR = {"CITRUS": "#d9b23a", "FRUITY": "#d1553f", "FLORAL": "#c56480",
         "GREEN": "#5f9a5c", "AQUATIC": "#3a9cab", "WOODY": "#9c7a52",
         "AMBER": "#d99a2e", "GOURMAND": "#9a7ec4", "MUSK": "#8595ac"}
VIEWPORTS = [375, 768, 1280]


def rle(a):
    """값은 글자(a~i = 계열 id · z = 바다), 길이는 숫자. 숫자끼리 붙으면 못 되돌린다."""
    out, prev, n = [], int(a[0]), 1
    tok = lambda v, k: f"{'z' if v == 255 else chr(97 + v)}{k}"   # noqa: E731
    for v in a[1:]:
        v = int(v)
        if v == prev:
            n += 1
        else:
            out.append(tok(prev, n))
            prev, n = v, 1
    out.append(tok(prev, n))
    return "".join(out)


def main() -> None:
    os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))  # MAP/
    d = json.load(io.open(V3, encoding="utf-8"))
    fa, tr = d["families"], d["terrain"]
    W, H = tr["grid_width"], tr["grid_height"]
    b = tr["bounds"]
    grid = np.array(fa["grid"], dtype=np.uint8)

    items = [{"id": it["id"], "key": it["key"], "ko": it["name_ko"],
              "color": COLOR[it["key"]],
              "ax": it["label_anchor"]["x"], "ay": it["label_anchor"]["y"],
              "area": it["area_share"], "blob": it["largest_blob_share"],
              "n": it["perfume_count_argmax"], "contrib": it["contributing_perfumes"]}
             for it in fa["items"]]
    keys = [it["key"] for it in items]

    pts = []
    for p in d["points"]:
        fams = [[keys.index(f["key"]), round(f["weight"], 3)] for f in p["families"]]
        pts.append([p["name"], p["brand"], round(p["x"], 4), round(p["y"], 4),
                    fams, p["korea"]["selection_rank"]])

    payload = {
        "W": W, "H": H, "bounds": b, "grid": rle(grid),
        "items": items, "points": pts, "viewports": VIEWPORTS,
        "threshold": fa["assignment"]["threshold"],
        "multi": int(sum(1 for p in d["points"] if len(p["families"]) >= 2)),
    }

    # 라벨 배치 문제를 미리 계산해 리포트로 남긴다 (화면에서도 같은 규칙을 쓴다)
    report = {"anchors": [{"ko": it["ko"], "x": it["ax"], "y": it["ay"],
                           "area_share": it["area"]} for it in items]}
    pair_min, pair = 9.0, None
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            dd = float(np.hypot(items[i]["ax"] - items[j]["ax"],
                                items[i]["ay"] - items[j]["ay"]))
            if dd < pair_min:
                pair_min, pair = dd, (items[i]["ko"], items[j]["ko"])
    report["closest_pair"] = {"a": pair[0], "b": pair[1], "distance": round(pair_min, 4),
                              "px_at": {str(v): round(pair_min * v) for v in VIEWPORTS}}
    report["edge_anchors"] = [
        {"ko": it["ko"], "x": it["ax"], "y": it["ay"],
         "near": [s for s, cond in (("left", it["ax"] < 0.08), ("right", it["ax"] > 0.92),
                                    ("bottom", it["ay"] < 0.08), ("top", it["ay"] > 0.80))
                  if cond]}
        for it in items
        if it["ax"] < 0.08 or it["ax"] > 0.92 or it["ay"] < 0.08 or it["ay"] > 0.80]
    json.dump(report, io.open(os.path.join(OUT_DIR, "label_report.json"), "w",
                              encoding="utf-8"), ensure_ascii=False, indent=1)

    html = TEMPLATE.replace("__PAYLOAD__", json.dumps(payload, ensure_ascii=False,
                                                      separators=(",", ":")))
    io.open(OUT, "w", encoding="utf-8", newline="\n").write(html)
    print(f"격자 {W}x{H} · RLE {len(payload['grid'])}B · 향수 {len(pts)}개 · "
          f"2계열 이상 {payload['multi']}개")
    print(f"가장 가까운 라벨 쌍 — {pair[0]} ↔ {pair[1]} {pair_min:.3f} "
          f"({', '.join(f'{v}px 에서 {round(pair_min*v)}px' for v in VIEWPORTS)})")
    print(f"가장자리에 붙은 앵커 {len(report['edge_anchors'])}개: "
          f"{[e['ko'] + '(' + ','.join(e['near']) + ')' for e in report['edge_anchors']]}")
    print(f"  -> {OUT}  ({os.path.getsize(OUT)/1024:.0f} KB)")
    print(f"  -> {OUT_DIR}/label_report.json")


TEMPLATE = """<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Phase 6 — 향 지도 UX 프로토타입</title>
<style>
:root{--bg:#fbfcfc;--card:#fff;--ink:#14262b;--ink2:#33484e;--muted:#5d757c;
      --hair:#c6d2d1;--sea:#e9eef0;--warn:#9d4238}
@media (prefers-color-scheme:dark){:root{--bg:#0f1719;--card:#151f22;--ink:#e8eef0;
      --ink2:#b6c6ca;--muted:#8ba0a5;--hair:#2b3a3e;--sea:#101a1c;--warn:#e08b80}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
     font:15px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI","Malgun Gothic",sans-serif}
.wrap{max-width:1380px;margin:0 auto;padding:22px 20px 48px}
h1{font-size:20px;font-weight:600;margin:0 0 4px}
.sub{color:var(--muted);font-size:13px;margin:0 0 16px}
.bar{display:flex;gap:16px;flex-wrap:wrap;align-items:center;margin-bottom:14px}
.grp{display:flex;gap:5px;align-items:center}
.grp>span{font-size:12px;color:var(--muted);margin-right:2px}
button{font-family:inherit;font-size:13px;padding:6px 11px;border:1px solid var(--hair);
       background:transparent;color:var(--ink2);border-radius:8px;cursor:pointer}
button.on{background:var(--card);border-color:var(--ink2);color:var(--ink);font-weight:600}
.stagewrap{display:flex;gap:18px;align-items:flex-start;flex-wrap:wrap}
.frame{position:relative;background:var(--card);border:1px solid var(--hair);
       border-radius:12px;padding:8px;flex:0 0 auto}
.frame .cap{font-size:11px;color:var(--muted);margin:0 0 6px 2px}
.map{position:relative;overflow:hidden;border-radius:8px}
canvas{display:block;width:100%;height:auto}
.lab{position:absolute;transform:translate(-50%,-50%);font-size:12px;font-weight:600;
     white-space:nowrap;padding:2px 7px;border-radius:999px;pointer-events:auto;
     cursor:pointer;border:1px solid rgba(0,0,0,.12)}
.lab.dim{opacity:.28}
.lab.clip{outline:2px dashed var(--warn);outline-offset:1px}
.side{flex:1 1 300px;min-width:280px}
.card{background:var(--card);border:1px solid var(--hair);border-radius:12px;
      padding:12px 14px;margin-bottom:12px}
.card h2{font-size:14px;font-weight:600;margin:0 0 8px}
.row{display:flex;justify-content:space-between;gap:10px;font-size:13px;padding:3px 0;
     border-bottom:1px solid var(--hair)}
.row:last-child{border-bottom:0}
.row .r{color:var(--muted);font-variant-numeric:tabular-nums}
.warn{color:var(--warn)}
ul.pl{list-style:none;margin:0;padding:0;max-height:300px;overflow:auto}
ul.pl li{font-size:12.5px;padding:4px 0;border-bottom:1px solid var(--hair);
         display:flex;justify-content:space-between;gap:8px}
ul.pl li span.w{color:var(--muted);font-variant-numeric:tabular-nums}
.legend{display:flex;flex-wrap:wrap;gap:5px;margin-top:10px}
.chip{display:inline-flex;align-items:center;gap:5px;padding:4px 9px;border-radius:999px;
      border:1px solid var(--hair);background:transparent;color:var(--ink2);cursor:pointer;
      font-size:12px}
.chip.on{border-color:var(--ink2);color:var(--ink)}
.chip i{width:9px;height:9px;border-radius:2px;display:inline-block}
.foot{color:var(--muted);font-size:12px;margin-top:16px;line-height:1.7}
</style></head><body><div class="wrap">
<h1>향 지도 UX 프로토타입 — 9개 계열 라벨이 읽히는가</h1>
<p class="sub">v3 초안 데이터를 그대로 렌더한다. 뷰포트와 줌을 바꿔가며 라벨이 겹치는지·잘리는지 확인한다.
읽히지 않는 라벨은 <b style="color:var(--warn)">주황 점선</b>으로 표시하고 오른쪽에 센다.</p>
<div class="bar">
 <div class="grp"><span>뷰포트</span><span id="vp"></span></div>
 <div class="grp"><span>줌</span><span id="zm"></span></div>
 <div class="grp"><button id="bd">경계 향수 보기</button><button id="rs">초기화</button></div>
</div>
<div class="stagewrap">
 <div class="frame"><p class="cap" id="cap"></p>
  <div class="map" id="map"><canvas id="cv"></canvas></div></div>
 <div class="side">
  <div class="card"><h2>라벨 진단</h2><div id="diag"></div></div>
  <div class="card"><h2 id="selh">계열을 누르면 향수가 나옵니다</h2>
   <ul class="pl" id="plist"></ul></div>
 </div>
</div>
<div class="legend" id="legend"></div>
<p class="foot">색면 = 계열 Territory · 회색 = 바다 · 점 = 향수 200개.
라벨은 앵커에 놓은 뒤 가장자리로 나가면 안으로 당기고, 겹치면 밀어낸다. 각 단계를 오른쪽에 센다.<br>
출처: experiments/phase6/korea_scent_map_v3.json (schema_version 3 · DRAFT)</p>
</div>
<script>
const D=__PAYLOAD__;
function decode(s){const a=new Int16Array(D.W*D.H);let i=0,p=0;
 while(p<s.length){const c=s[p++];const v=(c==='z')?-1:(c.charCodeAt(0)-97);
  let n='';while(p<s.length&&s[p]>='0'&&s[p]<='9'){n+=s[p++];}
  const k=+n;a.fill(v,i,i+k);i+=k;}
 if(i!==D.W*D.H)console.error('RLE 길이 불일치',i,D.W*D.H);return a;}
const F=decode(D.grid);
let vw=375, zoom=1, sel=null, showB=false;
const ZOOM=[{n:'멀리',pt:false,name:false},{n:'중간',pt:true,name:false},{n:'가까이',pt:true,name:true}];
const cv=document.getElementById('cv'),ctx=cv.getContext('2d');
const off=document.createElement('canvas');off.width=D.W;off.height=D.H;
const octx=off.getContext('2d');
function css(v){return getComputedStyle(document.documentElement).getPropertyValue(v).trim();}
function hex(h){return [parseInt(h.slice(1,3),16),parseInt(h.slice(3,5),16),parseInt(h.slice(5,7),16)];}
// 지도 좌표 [0,1] -> 화면 px. 격자 bounds 가 [-0.05,1.05] 라 여백이 포함돼 있다
function sx(x,w){return (x-D.bounds.x_min)/(D.bounds.x_max-D.bounds.x_min)*w;}
function sy(y,h){return h-(y-D.bounds.y_min)/(D.bounds.y_max-D.bounds.y_min)*h;}
function paint(){
 const w=vw, h=Math.round(w*D.H/D.W);
 document.getElementById('map').style.width=w+'px';
 const img=octx.createImageData(D.W,D.H),dd=img.data,sea=hex(css('--sea')||'#e9eef0');
 for(let r=0;r<D.H;r++)for(let c=0;c<D.W;c++){
  const i=r*D.W+c,v=F[i],o=((D.H-1-r)*D.W+c)*4;
  if(v<0){dd[o]=sea[0];dd[o+1]=sea[1];dd[o+2]=sea[2];dd[o+3]=255;}
  else{const g=hex(D.items[v].color),dim=(sel!==null&&sel!==v);
   dd[o]=g[0];dd[o+1]=g[1];dd[o+2]=g[2];dd[o+3]=dim?36:205;}}
 octx.putImageData(img,0,0);
 const dpr=Math.min(window.devicePixelRatio||1,2);
 cv.width=w*dpr;cv.height=h*dpr;cv.style.height=h+'px';
 ctx.setTransform(dpr,0,0,dpr,0,0);ctx.clearRect(0,0,w,h);
 ctx.imageSmoothingEnabled=true;ctx.drawImage(off,0,0,w,h);
 const Z=ZOOM[zoom];
 if(Z.pt){D.points.forEach(p=>{
   const fam=p[4],main=fam[0][0],multi=fam.length>=2;
   const dim=(sel!==null&&!fam.some(f=>f[0]===sel));
   if(showB&&!multi&&sel===null)return;
   const x=sx(p[2],w),y=sy(p[3],h);
   ctx.beginPath();ctx.arc(x,y,multi&&showB?4:3,0,6.2832);
   ctx.fillStyle=D.items[main].color;ctx.globalAlpha=dim?.12:1;ctx.fill();
   ctx.lineWidth=1;ctx.strokeStyle=css('--card')||'#fff';ctx.stroke();ctx.globalAlpha=1;});}
 if(Z.name){ctx.font='9px sans-serif';ctx.fillStyle=css('--ink2');ctx.globalAlpha=.85;
  D.points.filter(p=>p[5]<=24).forEach(p=>{
   const fam=p[4];if(sel!==null&&!fam.some(f=>f[0]===sel))return;
   ctx.fillText(p[0].slice(0,12),sx(p[2],w)+5,sy(p[3],h)+3);});ctx.globalAlpha=1;}
 placeLabels(w,h);
 document.getElementById('cap').textContent=`지도 ${w} x ${h}px · 줌 ${Z.n}`;}
function placeLabels(w,h){
 document.querySelectorAll('.lab').forEach(e=>e.remove());
 const map=document.getElementById('map'),PAD=3,made=[];
 D.items.forEach(it=>{
  const e=document.createElement('div');e.className='lab';e.textContent=it.ko;
  e.style.background=it.color+'e6';e.style.color='#1a1a1a';
  e.onclick=()=>{sel=(sel===it.id?null:it.id);render();};
  map.appendChild(e);
  const bw=e.offsetWidth,bh=e.offsetHeight;
  let x=sx(it.ax,w),y=sy(it.ay,h),clipped=false;
  if(x-bw/2<PAD){x=PAD+bw/2;clipped=true;} if(x+bw/2>w-PAD){x=w-PAD-bw/2;clipped=true;}
  if(y-bh/2<PAD){y=PAD+bh/2;clipped=true;} if(y+bh/2>h-PAD){y=h-PAD-bh/2;clipped=true;}
  made.push({e,it,x,y,bw,bh,clipped,pushed:false});});
 // 겹치면 밀어낸다 (작은 계열이 밀린다 — 큰 계열의 라벨 위치가 더 안정적이다)
 made.sort((a,b)=>b.it.area-a.it.area);
 for(let i=0;i<made.length;i++)for(let j=i+1;j<made.length;j++){
  const A=made[i],B=made[j];
  const ox=(A.bw+B.bw)/2+4-Math.abs(A.x-B.x), oy=(A.bh+B.bh)/2+3-Math.abs(A.y-B.y);
  if(ox>0&&oy>0){const dir=(B.y>=A.y)?1:-1;B.y+=dir*oy;B.pushed=true;
   if(B.y-B.bh/2<PAD){B.y=PAD+B.bh/2;B.clipped=true;}
   if(B.y+B.bh/2>h-PAD){B.y=h-PAD-B.bh/2;B.clipped=true;}}}
 made.forEach(m=>{m.e.style.left=m.x+'px';m.e.style.top=m.y+'px';
  if(m.clipped)m.e.classList.add('clip');
  if(sel!==null&&sel!==m.it.id)m.e.classList.add('dim');});
 diag(made,w,h);}
function diag(made,w,h){
 const cl=made.filter(m=>m.clipped),pu=made.filter(m=>m.pushed);
 const small=D.items.filter(it=>it.area*w*h<1600);
 const rows=[
  ['지도 크기',`${w} x ${h}px`],
  ['가장자리로 잘려 당겨진 라벨',cl.length?`<span class="warn">${cl.length}개 — ${cl.map(m=>m.it.ko).join(', ')}</span>`:'0개'],
  ['겹쳐서 밀어낸 라벨',pu.length?`<span class="warn">${pu.length}개 — ${pu.map(m=>m.it.ko).join(', ')}</span>`:'0개'],
  ['영역이 40x40px 미만인 계열',small.length?`<span class="warn">${small.length}개 — ${small.map(i=>i.ko).join(', ')}</span>`:'0개'],
  ['2계열 이상 향수',`${D.multi}개 / 200 (임계 ${D.threshold})`]];
 document.getElementById('diag').innerHTML=rows.map(r=>
  `<div class="row"><span>${r[0]}</span><span class="r">${r[1]}</span></div>`).join('');}
function panel(){
 const h=document.getElementById('selh'),l=document.getElementById('plist');
 if(sel===null){h.textContent='계열을 누르면 향수가 나옵니다';l.innerHTML='';return;}
 const it=D.items[sel];
 const list=D.points.map(p=>({p,f:p[4].find(f=>f[0]===sel)}))
   .filter(o=>o.f).sort((a,b)=>b.f[1]-a.f[1]);
 h.innerHTML=`${it.ko} — 기여 향수 ${list.length}개 · 면적 ${(it.area*100).toFixed(1)}% · 한 덩어리 ${(it.blob*100).toFixed(0)}%`;
 l.innerHTML=list.map(o=>{
  const other=o.p[4].filter(f=>f[0]!==sel).map(f=>D.items[f[0]].ko).join(', ');
  return `<li><span>${o.p[0]} <span class="w">· ${o.p[1]}</span>${other?` <span class="w">→ ${other}</span>`:''}</span><span class="w">${o.f[1].toFixed(2)}</span></li>`;}).join('');}
function btns(id,arr,cur,fn){const c=document.getElementById(id);c.innerHTML='';
 arr.forEach((t,i)=>{const b=document.createElement('button');b.textContent=t;
  if(i===cur)b.className='on';b.onclick=()=>fn(i);c.appendChild(b);});}
function legend(){const c=document.getElementById('legend');c.innerHTML='';
 D.items.forEach(it=>{const b=document.createElement('button');
  b.className='chip'+(sel===it.id?' on':'');
  b.innerHTML=`<i style="background:${it.color}"></i>${it.ko} ${it.n}`;
  b.onclick=()=>{sel=(sel===it.id?null:it.id);render();};c.appendChild(b);});}
function render(){
 btns('vp',D.viewports.map(v=>v+'px'),D.viewports.indexOf(vw),i=>{vw=D.viewports[i];render();});
 btns('zm',ZOOM.map(z=>z.n),zoom,i=>{zoom=i;render();});
 document.getElementById('bd').className=showB?'on':'';
 legend();paint();panel();}
document.getElementById('bd').onclick=()=>{showB=!showB;render();};
document.getElementById('rs').onclick=()=>{sel=null;showB=false;zoom=1;vw=375;render();};
matchMedia('(prefers-color-scheme:dark)').addEventListener('change',render);
render();
</script></body></html>
"""


if __name__ == "__main__":
    main()

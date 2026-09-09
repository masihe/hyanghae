"""담당자별 인계 문서 3종 — DB · BE · FE.

읽는 사람은 이 저장소도 실험 과정도 모른다. 그래서 "정확한 명세" 가 아니라
"읽고 바로 일할 수 있는 안내" 로 쓴다. 저장소 없이 단독으로 열리는 HTML 이다.

**사실과 제안을 눈에 보이게 구분한다.** 기존 저장소가 쓰는 표기를 그대로 쓴다
(docs/FRONTEND_MAP_DATA_WORKFLOW.md).

    [측정]  실제 파일에서 확인한 값. 여기에 맞지 않으면 데이터가 안 들어간다
    [제안]  우리 판단. 참고용이고 그대로 구현하지 않아도 된다

수치는 전부 delivery/ 산출물과 v3 에서 읽어온다. 새로 계산하지 않는다.

프론트 문서에는 지형 파일만으로 지도를 실제로 그려 넣는다 — 문서가 예시이면서
동시에 "정적 파일만으로 같은 지도가 나오는가" 검증이 된다.

재현::

    venv/Scripts/python.exe src/delivery/build_handoff_docs.py
"""

import base64
import io
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
MAP_DIR = os.path.abspath(os.path.join(HERE, "..", ".."))
DB_DIR = os.path.join("delivery", "for_db")
BE_DIR = os.path.join("delivery", "for_backend")
FE_DIR = os.path.join("delivery", "for_frontend")

FAM_COLOR = {"CITRUS": "#d9b23a", "FRUITY": "#d1553f", "FLORAL": "#c56480",
             "GREEN": "#5f9a5c", "AQUATIC": "#3a9cab", "WOODY": "#9c7a52",
             "AMBER": "#d99a2e", "GOURMAND": "#9a7ec4", "MUSK": "#8595ac"}

CSS = """
:root{--bg:#fbfcfc;--card:#f2f5f6;--ink:#1d2528;--muted:#6b797f;--hair:#dde4e6;
      --ok:#2f7d4f;--warn:#b4442e;--sea:#e7edef;--acc:#2b6b7a}
*{box-sizing:border-box}
body{background:var(--bg);color:var(--ink);
     font:15px/1.72 -apple-system,'Segoe UI',Roboto,'Malgun Gothic',sans-serif;
     -webkit-font-smoothing:antialiased}
.wrap{max-width:880px;margin:0 auto;padding:34px 22px 72px}
h1{font-size:26px;font-weight:600;margin:0 0 6px;letter-spacing:-.3px}
.lede{color:var(--muted);font-size:14px;margin:0 0 26px}
h2{font-size:19.5px;font-weight:600;margin:46px 0 10px;padding-top:22px;
   border-top:1px solid var(--hair)}
h2 .num{color:var(--muted);font-weight:400;margin-right:9px}
h3{font-size:16px;font-weight:600;margin:28px 0 8px}
p{margin:11px 0}
.notice{background:#fff;border:1px solid var(--hair);border-left:3px solid var(--acc);
        border-radius:0 10px 10px 0;padding:13px 17px;margin:0 0 26px;font-size:14px}
.notice p{margin:5px 0}
.todo{background:var(--card);border:1px solid var(--hair);border-radius:13px;
      padding:18px 22px;margin:18px 0}
.todo h3{margin:0 0 8px;font-size:15px}
.todo ol{margin:0;padding-left:22px}
.todo li{margin:7px 0}
.big{background:var(--card);border:1px solid var(--hair);border-radius:13px;
     padding:15px 19px;margin:16px 0}
.big p:first-child{margin-top:0}.big p:last-child{margin-bottom:0}
.alert{background:#fdf4f1;border:1px solid #f0d9d1;border-left:3px solid var(--warn);
       border-radius:0 12px 12px 0;padding:15px 19px;margin:18px 0}
.alert p:first-child{margin-top:0}.alert p:last-child{margin-bottom:0}
.tag{display:inline-block;font-size:11.5px;font-weight:600;padding:1px 7px;
     border-radius:4px;vertical-align:2px;margin-right:5px;letter-spacing:.2px}
.m{background:#e3eef1;color:#1d5764}
.s{background:#efe9f5;color:#5b4780}
table{border-collapse:collapse;width:100%;font-size:13.5px;margin:14px 0}
th,td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--hair);
      vertical-align:top}
th{color:var(--muted);font-weight:500;font-size:12.5px}
td.n{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
code{font:13px/1.5 ui-monospace,Menlo,Consolas,monospace;background:var(--sea);
     padding:1px 5px;border-radius:4px}
pre{background:#20282b;color:#dfe7e9;border-radius:11px;padding:15px 18px;
    overflow:auto;font:12.5px/1.7 ui-monospace,Menlo,Consolas,monospace;margin:14px 0}
pre .c{color:#8fa3a8}
pre .k{color:#8fc7d6}
pre .s{color:#c8d9a0;background:none;padding:0}
.note{font-size:13px;color:var(--muted)}
ul{margin:10px 0;padding-left:22px}li{margin:5px 0}
.step{background:var(--card);border:1px solid var(--hair);border-radius:13px;
      padding:16px 20px;margin:16px 0;counter-increment:st}
.steps{counter-reset:st}
.step h3{margin:0 0 6px;display:flex;align-items:center;gap:9px}
.step h3::before{content:counter(st);background:var(--acc);color:#fff;
   width:22px;height:22px;border-radius:50%;display:inline-flex;
   align-items:center;justify-content:center;font-size:12.5px;flex:none}
.leg{display:flex;flex-wrap:wrap;gap:7px;margin:12px 0}
.leg span{display:inline-flex;align-items:center;gap:5px;font-size:12.5px;
          color:var(--muted)}
.leg i{width:11px;height:11px;border-radius:3px;display:inline-block}
canvas{width:100%;height:auto;display:block;border-radius:10px;
       border:1px solid var(--hair);background:var(--sea)}
.ask{background:#fff;border:1px dashed var(--hair);border-radius:12px;
     padding:15px 19px;margin:18px 0}
.ask h3{margin:0 0 7px;font-size:15px}
.ask ul{margin:0}
.files{background:#20282b;color:#dfe7e9;border-radius:11px;padding:15px 18px;
       font:12.5px/1.75 ui-monospace,Menlo,Consolas,monospace;margin:14px 0}
.files b{color:#8fc7d6;font-weight:400}
"""

SHELL = """<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__</title>
<style>__CSS__</style>
<div class="wrap">
<h1>__H1__</h1>
<p class="lede">__LEDE__</p>
<div class="notice">
<p><span class="tag m">측정</span> 은 실제 데이터에서 확인한 값입니다. 여기에 맞지 않게
만들면 데이터가 들어가지 않으니 그대로 지켜 주세요.</p>
<p><span class="tag s">제안</span> 은 저희 판단일 뿐입니다. <b>참고만 하시고 실제 설계는
담당자분이 정하시면 됩니다.</b> 그대로 구현하지 않으셔도 괜찮습니다.</p>
</div>
__BODY__
</div>
"""


def page(path, title, h1, lede, body):
    html = (SHELL.replace("__CSS__", CSS).replace("__TITLE__", title)
            .replace("__H1__", h1).replace("__LEDE__", lede).replace("__BODY__", body))
    with io.open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(html)
    return os.path.getsize(path)


M = '<span class="tag m">측정</span>'
S = '<span class="tag s">제안</span>'


# ==========================================================================
# DB
# ==========================================================================
def doc_db(sm, counts):
    fam = sm["families"]["items"]
    ap = sm["families"]["assignment"]["families_per_perfume"]
    fam_rows = "".join(
        f'<tr><td><code>{it["key"]}</code></td><td>{it["name_ko"]}</td>'
        f'<td class="n">{it["perfume_count_argmax"]}</td>'
        f'<td class="n">{it["contributing_perfumes"]}</td></tr>' for it in fam)

    return f"""
<div class="todo"><h3>이 문서를 다 읽지 않아도 되는 요약</h3><ol>
<li><b>먼저 하나 정해 주세요</b> — <code>perfumes</code> 테이블에서 향수를 식별할 방법이
필요합니다. 이게 정해지지 않으면 나머지가 전부 막힙니다 (아래 1번).</li>
<li><b>표 5개를 만듭니다.</b> 4개는 지금 ERD 에 있는 것과 거의 같고, 1개는 새로
필요합니다 (아래 2번).</li>
<li><b>CSV 6개를 순서대로 넣습니다.</b> <code>seed/</code> 폴더에 있습니다.</li>
</ol></div>

<p>넘겨드리는 것은 <b>국내 대표 향수 200개를 향 지도 위에 배치한 결과</b>입니다.
향수마다 지도 위 위치가 있고, 어떤 향 계열에 속하는지, 어떤 향수와 닮았는지가 붙어
있습니다. 향 계열은 시트러스 · 플로럴 · 우디 같은 <b>9개</b>입니다.</p>

<h2><span class="num">1</span>먼저 정해야 하는 것 — 향수를 무엇으로 식별할까요</h2>

<p>저희 데이터는 향수를 <b>Fragrantica 의 id</b> 로 식별합니다. 향수 데이터의 원천이
Fragrantica 라서 그렇습니다. 그런데 지금 ERD 의 <code>perfumes</code> 테이블에는
외부 id 를 담는 컬럼이 없습니다.</p>

<p>그래서 <b>넘겨드리는 CSV 를 <code>perfumes</code> 행과 이어붙일 방법이 없습니다.</b>
브랜드명과 향수명으로 맞추는 방법도 있지만, 같은 향수가 농도나 표기만 달라도 여러 줄로
존재해서 정확하지 않습니다.</p>

<div class="alert">
<p>{S} <code>perfumes</code> 에 <code>fragrantica_id BIGINT UNIQUE</code> 컬럼을
추가하는 것이 가장 단순합니다.</p>
<p>컬럼 추가가 부담스러우면 <b>매핑 테이블을 따로 두는 방법</b>도 있습니다. 어느 쪽이든
정해 주시면 <b>저희가 CSV 를 그 키로 다시 내보내 드립니다.</b> 지금 CSV 는 전부
<code>fragrantica_id</code> 로 되어 있습니다.</p>
</div>

<h2><span class="num">2</span>지금 설계로는 담기지 않는 것 — 향수 하나가 계열 여러 개</h2>

<p>향수는 보통 한 가지 향만 나지 않습니다. 예를 들어 Byredo 의 Blanche 는
<b>플로럴 0.60 + 머스크·파우더리 0.32</b> 로, 두 계열에 걸쳐 있습니다. 이런 향수가
지도에서 두 영역 사이에 놓여서, 사용자가 한 계열에서 다른 계열로 넘어가는 다리가
됩니다.</p>

<p>{M} 향수 200개 중 <b>계열이 1개인 향수가 {counts['f1']}개, 2개가 {counts['f2']}개,
3개가 {counts['f3']}개</b>입니다. 향수당 평균 {ap['mean']}개이고 3개를 넘는 향수는
없습니다. 전부 합치면 <b>{counts['fam_rows']}행</b>이 됩니다.</p>

<p>그런데 지금 <code>perfume_map_points</code> 의
<code>scent_region_id BIGINT NOT NULL</code> 은 <b>영역을 하나만 담을 수 있습니다.</b>
이대로면 두 번째·세 번째 계열이 버려지고, 지도에서 경계에 놓이는 향수를 표현할 수
없습니다.</p>

<div class="alert">
<p>{S} <b>향수 ↔ 계열 표를 따로 두는 것</b>을 제안합니다
(<code>perfume_id</code> · <code>family_key</code> · <code>weight</code> ·
<code>rank</code>).</p>
<p><code>perfume_map_points.scent_region_id</code> 는 <b>가중치가 가장 큰 계열</b>을
넣어 그대로 두셔도 되고, 빼셔도 됩니다. CSV 에
<code>primary_family_key</code> 로 함께 넣어 두었습니다.</p>
</div>

<h2><span class="num">3</span>그 밖에 안 맞는 곳 4가지</h2>

<p>충돌이라기보다 <b>"저희 데이터가 이 모양이라 이 컬럼으로는 안 들어갑니다"</b> 정도의
이야기입니다.</p>

<h3>① 향 계열 영역이 사각형이 아닙니다</h3>
<p>{M} <code>scent_regions</code> 는 <code>min_x</code> · <code>min_y</code> ·
<code>max_x</code> · <code>max_y</code> 로 사각형만 담습니다. 그런데 향 계열 영역은
지도 위에 <b>불규칙한 모양</b>으로 퍼져 있고, 계열마다 조각이 1~5개입니다.
사각형으로는 모양을 그릴 수 없습니다.</p>
<p>{S} <code>polygon JSONB</code> 와 라벨 위치(<code>anchor_x</code> ·
<code>anchor_y</code>) 컬럼을 더하는 것을 제안합니다.</p>

<h3>② <code>scent_regions</code> 가 지금 무엇을 담고 있는지 저희가 모릅니다</h3>
<p><code>user_preference_regions</code> 가 이 테이블을 참조하고 있어서,
<b>기존 행이 있다면 의미가 바뀌는 문제</b>가 생깁니다. 확인 부탁드립니다.</p>
<p>참고로 이전 버전 지도에는 데이터로 자동 묶은 영역 7개가 있었는데, 그 7개는
<b>한글 이름을 붙일 수 없어서</b> 이번에 버렸습니다. 향 계열 9개만 넘겨드립니다.</p>

<h3>③ 닮은 향수 목록에 순서 컬럼이 필요합니다</h3>
<p>{M} <code>perfume_neighbors</code> 는 <code>(perfume_id, neighbor_perfume_id)</code>
만 담습니다. 그런데 저희가 주는 목록은 <b>닮은 순서대로 정렬된 상위 10개</b>이고
유사도 값도 있습니다. 순서를 잃으면 "가장 닮은 향수" 를 알 수 없게 됩니다.</p>
<p>{S} <code>rank INTEGER</code> 와 <code>similarity NUMERIC</code> 을 더해 주세요.</p>

<h3>④ 지도 배경은 DB 에 안 넣는 편이 낫습니다</h3>
<p>지도에는 땅과 바다, 색면, 해안선이 있습니다. 이건 향수별 데이터가 아니라
<b>지도를 128×108 칸으로 나눈 격자</b>라서, 조회할 조건이 없고 지도를 다시 만들 때만
바뀝니다.</p>
<p>{S} 이 부분은 <code>scent_map_terrain.json</code> 파일로 따로 드리니
<b>정적 파일로 프론트에 바로 내려주는 것</b>을 제안합니다. 팀에서 이미 그렇게 정했습니다.</p>

<h2><span class="num">4</span>적재할 때 걸리기 쉬운 것 3가지</h2>

<p>실제로 넣어 보면 막힐 수 있는 곳입니다. 미리 봐 두시면 좋습니다.</p>

<div class="big">
<p><b>① 계열 가중치에 <code>>= 0.24</code> 제약을 걸면 적재가 실패합니다.</b></p>
<p>계열을 뽑는 기준은 0.24 지만, <b>가장 큰 계열은 기준에 못 미쳐도 반드시 넣습니다</b>
(그러지 않으면 어느 계열에도 속하지 않는 향수가 생깁니다). 그래서 {M} 실제 최솟값은
<b>{counts['w_min']}</b> 입니다.</p>
<p>쓰셔야 하는 제약은 <code>weight > 0 AND weight &lt;= 1</code> 입니다.</p>
</div>

<div class="big">
<p><b>② 향수별 가중치 합이 1.0 이 아닙니다.</b></p>
<p>{M} 향수별 합이 <b>{counts['w_sum_min']} ~ {counts['w_sum_max']}</b> 사이입니다.
기준 미달인 작은 계열은 목록에서 빠지는데 <b>남은 것을 다시 정규화하지 않았기</b>
때문입니다.</p>
<p>그래서 <code>SUM(weight) = 1</code> 같은 제약을 걸면 안 되고,
<code>1 - SUM(weight)</code> 를 "기타 계열" 로 읽어서도 안 됩니다.</p>
</div>

<div class="big">
<p><b>③ 좌표 <code>CHECK (0~1)</code> 은 향수 좌표에만 걸어야 합니다.</b></p>
<p>{M} 향수 좌표는 <code>x</code> 0~1, <code>y</code> 0~{counts['y_max']} 입니다.
그런데 <b>계열 영역의 폴리곤과 라벨 위치는 좌표계가 다릅니다</b> — 지도 바깥으로
여백이 붙어 있어서 <code>{counts['ring_y_min']}</code> 같은 음수가 나옵니다.</p>
<p>폴리곤 컬럼에 0~1 제약을 걸면 계열 9개가 전부 적재에 실패합니다.</p>
</div>

<h2><span class="num">5</span>넘겨드리는 CSV 6개</h2>

<div class="files">
<b>seed/</b>
  accords.csv                  {counts['accords']:>5}행   향 특성 이름 목록
  scent_families.csv           {counts['families']:>5}행   향 계열 9개 (이름 · 영역 · 라벨 위치)
  perfume_map_points.csv       {counts['points']:>5}행   향수 좌표
  perfume_map_families.csv     {counts['fam_rows']:>5}행   향수 ↔ 계열  <b>← 새로 필요한 표</b>
  perfume_map_neighbors.csv    {counts['nb_rows']:>5}행   닮은 향수 (향수당 10개)
  perfume_map_accords.csv      {counts['ac_rows']:>5}행   향수의 향 특성 (향수당 7~8개)
</div>

<p>모두 UTF-8(BOM) CSV 이라 Excel 로 바로 열립니다. 향수는 전부
<code>fragrantica_id</code> 로 되어 있으니, <code>perfumes</code> 와 조인해
<code>perfume_id</code> 로 바꿔 넣으시면 됩니다.</p>

<h3>향 계열 9개</h3>
<table><thead><tr><th>키</th><th>이름</th><th class="n">대표 향수</th>
<th class="n">걸쳐 있는 향수</th></tr></thead><tbody>{fam_rows}</tbody></table>
<p class="note">"대표 향수" 는 이 계열이 1순위인 향수 수로 합이 200입니다.
"걸쳐 있는 향수" 는 2·3순위까지 포함한 수로 합이 {counts['fam_rows']}입니다.</p>

<div class="alert">
<p>{M} <b>계열의 키는 <code>CITRUS</code> 같은 문자열을 쓰시는 걸 권합니다.</b></p>
<p>저희 파일에는 0~8 정수 번호도 있는데 그건 <b>배열 위치값</b>입니다. 나중에 계열이
하나 빠지면 그 뒤 번호가 전부 밀려서, 저장해 둔 지도 격자가 어긋납니다. 문자열 키는
그런 일이 없습니다.</p>
</div>

<h2><span class="num">6</span>적재 순서와 갱신</h2>

<p>참조 관계 때문에 순서가 있습니다.</p>
<ol>
<li><code>accords.csv</code> — 기존 <code>accords</code> 테이블이 이미 있으면 확인만</li>
<li><code>scent_families.csv</code> — 9행</li>
<li><code>perfumes</code> 에 향수 식별 컬럼 채우기 (1번 항목)</li>
<li><code>perfume_map_points.csv</code> — 200행</li>
<li><code>perfume_map_families.csv</code> — {counts['fam_rows']}행</li>
<li><code>perfume_map_neighbors.csv</code> — {counts['nb_rows']}행</li>
<li><code>perfume_map_accords.csv</code> — {counts['ac_rows']}행</li>
</ol>

<p>{S} <b>갱신은 행 단위로 고치기보다 4~7번을 비우고 다시 넣는 쪽이 안전합니다.</b>
지도를 다시 만들면 향수 200개의 좌표와 계열 영역이 <b>전부</b> 바뀌기 때문입니다
(일부만 바뀌는 일이 없습니다).</p>

<p>CREATE / ALTER 문 초안은 <code>scent_map_proposal.sql</code> 에
있습니다. <b>실행해 본 적이 없는 제안이니</b> 팀 규약(네이밍 · <code>is_active</code> ·
삭제 정책)에 맞게 검토해 주세요. 타입과 길이가 실제 값을 받는지는 저희가 확인했습니다.</p>

<div class="ask"><h3>확인이 필요한 것</h3><ul>
<li><b>향수를 무엇으로 식별할까요.</b> 정해 주시면 CSV 를 그 키로 다시 냅니다.</li>
<li><b><code>scent_regions</code> 에 지금 행이 들어 있나요.</b> 있으면 향 계열 9개를
같은 테이블에 넣을지, 새 테이블로 나눌지 정해야 합니다.</li>
<li><b>향수별 계절·시간대 투표를 쓸까요.</b> 데이터는 있는데(향수 200개 중 185개 ·
181개) ERD 에 담을 곳이 없습니다. 지금 지도에는 필요하지 않아 이번 CSV 에서 뺐습니다.
쓰실 거면 표를 하나 더 만들어야 합니다.</li>
</ul></div>
"""


# ==========================================================================
# Backend
# ==========================================================================
def doc_be(sm, counts):
    fam = sm["families"]["items"]
    ex = json.load(io.open(os.path.join(BE_DIR, "example_map_response.json"), encoding="utf-8"))
    ex_pts = json.dumps(ex["points"], ensure_ascii=False, indent=2)
    return f"""
<div class="todo"><h3>이 문서를 다 읽지 않아도 되는 요약</h3><ol>
<li><b>지도를 처음 열 때</b> 향수 200개와 향 계열 9개를 한 번에 내려주면 됩니다.
약 {counts['sm_compact']} KB 이고 gzip 이면 {counts['sm_gzip']} KB 입니다.</li>
<li><b>지도 배경(땅 · 바다 · 색면 · 해안선)은 DB 를 거치지 않습니다.</b> 정적 파일
하나로 프론트에 바로 내려주는 것을 제안합니다.</li>
<li><b>"닮은 향수" 는 미리 계산돼 있습니다.</b> 좌표로 거리를 계산하지 말고 저장된
목록을 그대로 내려주세요.</li>
</ol></div>

<p>향 지도는 국내 대표 향수 200개를 <b>향이 비슷한 것끼리 가까이</b> 놓은 평면
지도입니다. 향수마다 좌표가 있고, 지도는 시트러스 · 플로럴 · 우디 같은
<b>향 계열 9개 구역</b>으로 나뉩니다. 사용자는 돛단배를 움직여 지도를 돌아다니면서
새 향수를 발견합니다.</p>

<h2><span class="num">1</span>기능별로 무엇을 조회해 무엇을 돌려주나</h2>

<p>{S} 아래는 기능 명세의 향 지도 항목을 데이터에 대응시켜 본 것입니다.
엔드포인트를 어떻게 나눌지는 담당자분이 정하시면 됩니다.</p>

<div class="steps">
<div class="step"><h3>지도를 처음 열 때 <span class="note">MAP-01 향 지도 조회</span></h3>
<p>향수 200개의 좌표·이름·소속 계열과, 향 계열 9개의 이름·영역·라벨 위치를 한 번에
내려줍니다. <b>200개가 전부이므로 페이지 나눌 필요가 없습니다.</b></p>
<p>지도 배경은 이 응답에 넣지 않고, 정적 파일 주소만 알려주면 됩니다 (아래 3번).</p>
</div>

<div class="step"><h3>향수를 눌렀을 때 <span class="note">MAP-05 지도 내 향수 선택 ·
MAP-07 향수 상세 이동</span></h3>
<p>그 향수의 향 특성(향수당 7~8개, 세기 0~100)과 소속 계열, 그리고 닮은 향수 10개를
내려줍니다. 상세 페이지로 넘어가면 기존 향수 상세 API 를 쓰시면 됩니다.</p>
</div>

<div class="step"><h3>닮은 향수를 보여줄 때 <span class="note">MAP-06 유사 향수 탐색
</span></h3>
<p>저장된 목록을 <code>rank</code> 순서로 그대로 내려주면 됩니다. 향수당 10개 고정이고
<b>이미 닮은 순서로 정렬</b>돼 있습니다.</p>
<p>이 유사도는 향 성분으로 계산한 값입니다. <b>지도 위 거리와 다릅니다</b> — 자세한
이유는 아래 4번에 있습니다.</p>
</div>

<div class="step"><h3>추천 주변을 탐색할 때 <span class="note">MAP-11 추천 주변 향 탐색
</span></h3>
<p>추천된 향수를 중심으로 주변 향수를 보여주는 기능입니다. 여기서는 <b>지도 좌표를
쓰는 게 맞습니다</b> — "화면에서 이 근처에 뭐가 있나" 를 묻는 것이기 때문입니다.</p>
<p>좌표는 0~1 범위라 사각형 범위 조회로 충분합니다.
<code>WHERE map_x BETWEEN ? AND ? AND map_y BETWEEN ? AND ?</code></p>
</div>

<div class="step"><h3>다음에 갈 곳을 추천할 때 <span class="note">MAP-12~15 탐색 방향
추천</span></h3>
<p>사용자를 어디로 보낼지는 취향 데이터로 정하는 별개의 문제입니다. 다만
<b>목표 지점을 좌표로 표현할 수 있다</b>는 점만 알려드립니다 — 특정 향수의 좌표를 쓰거나,
향 계열의 라벨 위치(<code>anchor</code>)를 그 계열의 대표 지점으로 쓸 수 있습니다.</p>
<p>돛단배 위치는 이미 <code>map_exploration_states</code> 에 좌표로 저장되게 되어
있으니 그대로 맞습니다.</p>
</div>
</div>

<h2><span class="num">2</span>응답 예시</h2>

<p>{S} 지도를 처음 열 때의 응답 예시입니다. 필드 이름과 구조는 프로젝트 규약에 맞게
바꿔 쓰셔도 됩니다. 전체 파일은
<code>example_map_response.json</code> 에 있고, TypeScript 타입 정의는
<code>scent-map.d.ts</code> 에 있습니다.</p>

<p><b>향 계열</b> — 9개. <code>polygon</code> 은 영역 외곽선이고 조각이 1~5개입니다.</p>
<pre>{{
  <span class="s">"key"</span>: <span class="s">"FRUITY"</span>,          <span class="c">// 안정적인 키. 이걸로 조인하세요</span>
  <span class="s">"nameKo"</span>: <span class="s">"프루티"</span>,
  <span class="s">"displayOrder"</span>: 1,
  <span class="s">"perfumeCount"</span>: 8,           <span class="c">// 이 계열이 1순위인 향수 수</span>
  <span class="s">"anchor"</span>: {{ <span class="s">"x"</span>: 0.70354, <span class="s">"y"</span>: 0.43702 }},  <span class="c">// 라벨 놓을 위치</span>
  <span class="s">"polygon"</span>: [ [ [0.70, 0.43], ... ] ]      <span class="c">// 조각 배열</span>
}}</pre>

<p><b>향수</b> — 200개. 아래는 2개만 보여드립니다 (계열 1개인 향수와 3개인 향수).</p>
<pre>{ex_pts}</pre>

<table><thead><tr><th>필드</th><th>무엇인가</th></tr></thead><tbody>
<tr><td><code>x</code>, <code>y</code></td><td>지도 위 위치. {M} <code>x</code> 는
0~1, <code>y</code> 는 0~{counts['y_max']}. 화면 크기에 맞춰 곱하면 됩니다</td></tr>
<tr><td><code>families</code></td><td>속한 향 계열과 비중. 1~3개이고 비중 내림차순.
{M} 비중은 {counts['w_min']}~{counts['w_max']}</td></tr>
<tr><td><code>koreaRank</code></td><td>국내 인기 순위 1~200. 점 크기나 이름 표시 우선순위에
쓸 수 있습니다</td></tr>
</tbody></table>

<h2><span class="num">3</span>지도 배경은 왜 DB 를 거치지 않나</h2>

<p>지도의 땅·바다와 계열 색면은 <b>지도를 {counts['gw']}×{counts['gh']} 칸으로 나눈
격자</b>입니다. 칸마다 숫자 하나가 들어 있어서 총 {counts['cells']:,}칸 × 2장입니다.
해안선은 좌표 점 목록입니다.</p>

<p>이건 향수별 데이터가 아니라 <b>지도 한 장에 딱 하나 있는 그림</b>입니다. 조회할 조건이
없고, 지도를 다시 만들 때만 바뀌고, 사용자마다 다르지도 않습니다. DB 에 넣으면
{S} <b>BE 가 매 요청마다 쓸 데없이 {counts['tr_compact']} KB 를 지나 보내게 됩니다.</b></p>

<p>{S} 그래서 <code>scent_map_terrain.json</code> 을 정적 파일로 두고 프론트가 한 번
받아 캐시하게 하는 것을 제안합니다. 버전은 파일명이나 쿼리스트링으로 관리하면 됩니다.
팀에서 이미 이 방향으로 정했습니다.</p>

<h3>크기</h3>
<table><thead><tr><th>파일</th><th class="n">그대로</th><th class="n">공백 제거</th>
<th class="n">gzip</th></tr></thead><tbody>
<tr><td>향수 200 + 계열 9 <span class="note">(API 응답)</span></td>
<td class="n">{counts['sm_kb']} KB</td><td class="n">{counts['sm_compact']} KB</td>
<td class="n"><b>{counts['sm_gzip']} KB</b></td></tr>
<tr><td>지도 배경 <span class="note">(정적 파일)</span></td>
<td class="n">{counts['tr_kb']} KB</td><td class="n">{counts['tr_compact']} KB</td>
<td class="n"><b>{counts['tr_gzip']} KB</b></td></tr>
</tbody></table>
<p class="note">{M} gzip 을 켜면 둘 다 충분히 작습니다. 저희가 드리는 파일은 사람이 읽기
쉽게 들여쓰기가 되어 있어서, 그것만 지워도 절반이 됩니다.</p>

<h2><span class="num">4</span>주의할 것 3가지</h2>

<div class="alert">
<p><b>① "닮은 향수" 를 좌표로 계산하지 마세요.</b></p>
<p>지도 좌표는 향수 200개를 <b>평면에 눌러 담은 결과</b>입니다. 원래 향의 차이는 훨씬
많은 축으로 되어 있는데 그걸 2차원으로 줄인 것이라, 가까운 관계는 잘 보존되지만
<b>거리 자체는 향의 차이와 정확히 대응하지 않습니다.</b></p>
<p>그래서 닮은 향수는 미리 계산해 저장해 두었습니다. 그 목록을 쓰시면 됩니다.
데이터에도 <code>layout.distance_is_metric: false</code> 로 표시해 두었습니다.</p>
<p class="note">참고로 지도를 새로 만들면서 좌표는 200개 전부 바뀌었지만,
닮은 향수 목록은 <b>이전 버전과 완전히 같습니다.</b> 좌표와 무관하게 계산되기 때문입니다.</p>
</div>

<div class="alert">
<p><b>② 계열 비중의 합을 1.0 으로 가정하지 마세요.</b></p>
<p>{M} 향수별 합이 {counts['w_sum_min']}~{counts['w_sum_max']} 사이입니다. 비중이 작은
계열은 목록에서 빠지는데 남은 것을 다시 정규화하지 않았습니다.
<code>1 - 합</code> 은 "기타 계열" 이라는 뜻이 아닙니다.</p>
</div>

<div class="alert">
<p><b>③ 좌표계가 두 개입니다.</b></p>
<p>{M} 향수 좌표는 0~1 인데, <b>계열 영역의 폴리곤과 라벨 위치는 다른 좌표계</b>입니다
(지도 바깥으로 여백이 붙어서 {counts['ring_y_min']} 같은 음수가 나옵니다).
그대로 내려주시고 변환은 하지 마세요 — 프론트가 각각 맞게 처리합니다.</p>
</div>

<div class="ask"><h3>확인이 필요한 것</h3><ul>
<li><b>지도 배경을 정적 파일로 낼 수 있나요.</b> 어려우면 DB 에 넣는 방법도 있어서,
그쪽이면 알려주세요.</li>
<li><b>매칭 근거를 API 로 내보낼 일이 있나요.</b> 향수마다 "왜 이 향수와 매칭했는지"
설명 문자열이 있는데 {M} 73종의 자유 형식 문장이라 필터링에는 못 씁니다. 필요하면
정리해서 다시 드립니다.</li>
<li><b>지도 데이터 버전을 어떻게 알릴까요.</b> 지금은 만든 시각을 넣어 두었습니다.</li>
</ul></div>
"""


# ==========================================================================
# Frontend
# ==========================================================================
def doc_fe(sm, tr, counts, blob):
    fam = sm["families"]["items"]
    leg = "".join(f'<span><i style="background:{FAM_COLOR[it["key"]]}"></i>'
                  f'{it["name_ko"]}</span>' for it in fam)
    return f"""
<div class="alert">
<p><b>먼저 이것 하나만 기억해 주세요.</b></p>
<p>지도에서 <b>"닮은 향수" 를 좌표 거리로 계산하면 안 됩니다.</b> 향수마다
<code>families</code> 옆에 <b>미리 계산된 목록</b>이 붙어 있으니 그걸 쓰세요.</p>
<p class="note">좌표는 향수 200개를 평면에 눌러 담은 결과입니다. 가까운 것끼리 가깝게
놓는 것은 지켜지지만 <b>거리 값 자체가 향의 차이를 뜻하지는 않습니다.</b> 그래서
"2배 멀다" 가 "2배 다르다" 가 아니고, 지도 반대편끼리의 거리는 대략적인 값입니다.</p>
</div>

<div class="todo"><h3>이 문서를 다 읽지 않아도 되는 요약</h3><ol>
<li><b>파일 2개를 받습니다</b> — 향수·계열 데이터 하나, 지도 배경 하나.</li>
<li><b>5단계로 그립니다</b> — 바다/땅 → 계열 색면 → 해안선 → 점 → 라벨.</li>
<li><b>좌표계가 두 개입니다.</b> 향수 점과 나머지(색면·해안선·라벨)가 다릅니다.
3번에서 설명합니다.</li>
</ol></div>

<h2><span class="num">1</span>받는 파일 2개</h2>

<div class="files">
<b>scent_map.json</b>            {counts['sm_kb']:>4} KB   향수 200개 + 향 계열 9개
  bounds                  좌표 범위
  families[9]             계열 이름 · 영역 폴리곤 · 라벨 위치
  points[200]             향수 좌표 · 소속 계열 · 닮은 향수

<b>scent_map_terrain.json</b>    {counts['tr_kb']:>4} KB   지도 배경 (한 번 받아 캐시)
  grid_width / grid_height  {counts['gw']} / {counts['gh']}
  bounds                  이 파일 좌표 범위 (향수 좌표보다 넓다)
  density.values          {counts['cells']:,}칸 — 향수가 몰린 정도
  family_grid.values      {counts['cells']:,}칸 — 칸마다 어느 계열인지
  contours                해안선
</div>

<p>배경 파일은 지도를 다시 만들 때만 바뀌므로 <b>한 번 받아 캐시</b>하면 됩니다.</p>

<h2><span class="num">2</span>이렇게 그리면 됩니다</h2>

<p>{S} 아래 5단계가 저희가 실제로 그려 본 순서입니다. 캔버스든 SVG 든 WebGL 이든
방식은 담당자분이 정하시면 됩니다.</p>

<div class="steps">

<div class="step"><h3>좌표를 화면 크기에 맞추기</h3>
<p>향수 좌표는 <code>0~1</code> 범위입니다. 화면 크기를 곱하면 됩니다. 다만
<b><code>bounds</code> 를 읽어서 쓰고 숫자를 코드에 적어 두지 마세요</b> — 지도를 다시
만들면 <code>y</code> 의 최대값이 바뀝니다.</p>
<pre><span class="c">// 향수 점을 화면에 놓기</span>
<span class="k">const</span> b = map.bounds;
<span class="k">const</span> px = (p.x - b.x_min) / (b.x_max - b.x_min) * W;
<span class="k">const</span> py = (p.y - b.y_min) / (b.y_max - b.y_min) * H;</pre>
<p class="note">{M} 현재 <code>y_max</code> 는 {counts['y_max']} 입니다. 이전 버전은
0.57069 였습니다.</p>
</div>

<div class="step"><h3>바다와 땅 칠하기</h3>
<p><code>density.values</code> 는 칸마다 0~255 숫자가 든 배열입니다. 향수가 몰린 곳이
높습니다. <code>sea_level</code>({tr['density']['sea_level']})<b>보다 큰 칸이 땅</b>이고
나머지가 바다입니다.</p>
<pre><span class="c">// 칸 하나 찾기 — 배경 파일의 bounds 를 쓴다 (향수 좌표의 bounds 가 아니다)</span>
<span class="k">const</span> i = row * grid_width + col;
<span class="k">const</span> isLand = density.values[i] &gt; density.sea_level;</pre>
<div class="alert">
<p><b>두 가지 함정이 있습니다.</b></p>
<p><b>위아래가 뒤집혀 있습니다.</b> {M} <code>row 0</code> 이 <b>아래쪽</b>
(<code>y_min</code>)입니다. 화면 좌표는 보통 위가 0 이므로, 그대로 그리면 지도가
거꾸로 나옵니다. 행을 뒤집어 주세요.</p>
<p><b>여기서 255 는 바다가 아닙니다.</b> 이 격자에서 255 는 "가장 붐비는 칸" 이라는
정상값입니다. 뒤에 나오는 계열 격자에서만 255 가 바다를 뜻합니다.</p>
</div>
</div>

<div class="step"><h3>향 계열 색면 얹기</h3>
<p><code>family_grid.values</code> 도 같은 크기의 배열입니다. 칸마다 <b>어느 계열의
땅인지</b>가 들어 있습니다.</p>
<pre><span class="k">const</span> v = family_grid.values[i];
<span class="k">if</span> (v === 255) {{ <span class="c">/* 바다 */</span> }}
<span class="k">else</span> {{
  <span class="k">const</span> key = family_grid.id_to_key[v];   <span class="c">// "CITRUS" 같은 문자열</span>
  fill(COLOR[key]);
}}</pre>
<p>{M} <b>여기서는 255 가 바다입니다.</b> 격자값은 그냥 배열 위치라
<code>id_to_key</code> 를 거쳐 문자열 키로 바꿔서 쓰세요. 그러면 나중에 계열이 하나
빠져도 코드가 안 깨집니다.</p>
<p>색은 정해진 것이 없습니다. 아래는 저희가 검토용으로 쓴 값이니 디자인에 맞게 바꾸세요.</p>
<div class="leg">{leg}</div>
</div>

<div class="step"><h3>해안선 그리기</h3>
<p><code>contours</code> 에 해안선이 들어 있습니다. 안 그려도 되지만 있으면 지도처럼
보입니다.</p>
<div class="alert">
<p><b>고리가 닫혀 있지 않습니다.</b> {M} 해안선 조각
{len(tr['contours'][0]['polygons'])}개 중 <b>3개가 열려 있습니다</b> (지도 가장자리에서
잘린 것들입니다). 감기 방향이나 구멍 표시도 없습니다.</p>
<p><code>closePath()</code> 를 직접 불러 주세요. 안 그러면 칠할 때 이상하게 나옵니다.</p>
</div>
<p class="note">계열 영역의 <code>polygon</code> 도 같습니다 — 조각이 1~5개이고,
작은 조각(정점 5개)은 <b>다른 계열 안에 섬처럼 박힌 영역</b>이라 일부러 남긴
것입니다. 노이즈가 아닙니다.</p>
</div>

<div class="step"><h3>점과 라벨 붙이기</h3>
<p>향수 200개를 <code>points</code> 로 찍습니다. <code>koreaRank</code>(1~200)를 점
크기나 이름 표시 우선순위에 쓸 수 있습니다.</p>
<p>계열 이름은 <code>families[].anchor</code> 위치에 붙입니다. {M} <b>9개 전부 자기
계열 땅 위에 있습니다</b> — 별도 배치 계산이 필요 없습니다.</p>
<div class="alert">
<p><b>앵커와 폴리곤은 향수 좌표와 좌표계가 다릅니다.</b> 배경 파일의
<code>bounds</code> 를 써야 하고, {M} <code>{counts['ring_y_min']}</code> 같은
음수가 나옵니다. 향수 점의 <code>bounds</code> 로 변환하면 위치가 어긋납니다.</p>
</div>
</div>
</div>

<h2><span class="num">3</span>좌표계가 두 개인 이유</h2>

<p>헷갈리기 쉬운 부분이라 따로 적습니다.</p>

<p><b>향수 점</b>은 딱 <code>0~1</code> 에 맞춰 정규화되어 있습니다. 화면에 곱해서
쓰기 좋게 만든 값입니다.</p>

<p><b>지도 배경</b>은 그보다 조금 넓습니다. 땅의 밀도를 계산할 때 <b>가장자리 향수도
주변에 여유가 있어야</b> 자연스러운 해안선이 나오기 때문에, 사방으로 0.05 만큼 여백을
두고 격자를 만들었습니다. 그래서 색면·해안선·라벨 위치는 이 넓은 좌표계에 있고
음수가 나옵니다.</p>

<pre><span class="c">// 향수 점 </span>       map.bounds          x 0 ~ 1        y 0 ~ {counts['y_max']}
<span class="c">// 배경 · 색면 · 해안선 · 라벨</span>
                    terrain.bounds      x {tr['bounds']['x_min']} ~ {tr['bounds']['x_max']}   y {tr['bounds']['y_min']} ~ {tr['bounds']['y_max']}</pre>

<p>둘 중 하나로 통일해 쓰고 싶으면, <b>배경 쪽 좌표계로 향수 점을 옮기는 편이 쉽습니다</b>
(같은 변환식에 <code>terrain.bounds</code> 를 넣으면 됩니다).</p>

<h2><span class="num">4</span>실제로 그려 본 것</h2>

<p>아래 지도는 <b>드리는 파일 2개만으로 이 문서 안에서 직접 그린 것</b>입니다. 위의
5단계를 그대로 따랐습니다.</p>

<canvas id="cv" width="900" height="760"></canvas>
<div class="leg">{leg}<span><i style="background:#dfe8ea"></i>바다</span></div>
<p class="note">칠한 땅 <b id="nl"></b>칸 · 향수 <b id="np"></b>개 · 계열 라벨
<b id="nf"></b>개. 격자 {counts['gw']}×{counts['gh']}.</p>

<h2><span class="num">5</span>좁은 화면에서 라벨이 걸립니다</h2>

<p>{M} 저희가 뷰포트 3개(375 · 768 · 1280)에서 라벨 배치를 돌려 봤습니다.
<b>768px 이상에서는 계열 이름 9개가 전부 겹치지도 잘리지도 않습니다.</b></p>

<p>모바일(375px)에서만 <b>3개가 화면 밖으로 나가 안으로 당겨집니다</b> — 플로럴 ·
앰버·스파이시 · 아쿠아틱입니다. 영역이 작아서가 아니고 <b>그 계열의 라벨 위치가 지도
가장자리에 붙어 있어서</b>입니다 (아쿠아틱은 왼쪽 끝 <code>x = 0.011</code>, 플로럴은
오른쪽 끝 <code>x = 0.972</code>). 걱정했던 작은 계열은 375px 에서도 전부 라벨이 들어갈
만큼 넓었습니다.</p>

<p>또 <b>우디와 앰버·스파이시의 라벨이 가장 가깝습니다</b> — 간격이 375px 지도에서
46px 인데 "앰버·스파이시" 7자가 약 70px 이라 겹칩니다.</p>

<div class="ask"><h3>확인이 필요한 것 — 모바일 라벨</h3>
<p>아직 정하지 않았습니다. 세 가지 중에 어느 쪽이 나을지 의견 주세요.</p><ul>
<li><b>범례로 빼기</b> — 지도 밖에 계열 목록을 두고 지도에는 색면만</li>
<li><b>줌 인했을 때만 표시</b> — 멀리서는 색면, 가까이 가면 이름</li>
<li><b>짧은 이름 쓰기</b> — "앰버·스파이시" 대신 "앰버"</li>
</ul>
<p class="note">저희 생각은 두 번째와 세 번째를 같이 쓰는 쪽이지만, 화면을 만져 보시는
분 판단이 맞다고 봅니다.</p>
</div>

<div class="ask"><h3>그 밖에 확인이 필요한 것</h3><ul>
<li><b>지도 배경을 정적 파일로 받을 수 있나요.</b> API 응답에 섞는 것보다 캐시가
잘 되어 그렇게 제안했습니다.</li>
<li><b>줌 단계를 몇 개로 할까요.</b> 저희 프로토타입은 3단계였습니다 —
멀리(색면+라벨) · 중간(+점) · 가까이(+향수 이름).</li>
<li><b>격자를 그대로 쓸지, 이미지로 미리 구워 둘지.</b> 칸이
{counts['cells']:,}개 × 2장이라 매 프레임 다시 칠하면 느릴 수 있습니다. 저희는 한 번
칠해 두고 재사용했습니다.</li>
</ul></div>

<script>
const B = {blob};

function unb64(s) {{
  const bin = atob(s);
  const a = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) a[i] = bin.charCodeAt(i);
  return a;
}}

const dens = unb64(B.dens), famg = unb64(B.fam);
const GW = B.gw, GH = B.gh, SEA = B.sea;
const cv = document.getElementById('cv'), ctx = cv.getContext('2d');
const W = cv.width, H = cv.height;

// 배경 좌표계 -> 화면
const tb = B.tbounds;
const tx = x => (x - tb[0]) / (tb[2] - tb[0]) * W;
const ty = y => H - (y - tb[1]) / (tb[3] - tb[1]) * H;   // row 0 이 아래라 뒤집는다

// 2단계 + 3단계 — 격자를 한 번만 칠해 재사용한다
const img = ctx.createImageData(GW, GH);
let land = 0;
for (let row = 0; row < GH; row++) {{
  for (let col = 0; col < GW; col++) {{
    const i = row * GW + col;
    // 화면은 위가 0 이므로 행을 뒤집어 넣는다
    const o = ((GH - 1 - row) * GW + col) * 4;
    let c;
    if (dens[i] > SEA) {{ land++; c = B.colors[famg[i]] || [200, 200, 200]; }}
    else c = [223, 232, 234];
    img.data[o] = c[0]; img.data[o + 1] = c[1];
    img.data[o + 2] = c[2]; img.data[o + 3] = 255;
  }}
}}
const off = document.createElement('canvas');
off.width = GW; off.height = GH;
off.getContext('2d').putImageData(img, 0, 0);
ctx.imageSmoothingEnabled = true;
ctx.drawImage(off, 0, 0, W, H);

// 4단계 — 해안선. 고리가 열려 있을 수 있어 직접 닫는다
ctx.strokeStyle = 'rgba(40,60,66,.5)';
ctx.lineWidth = 1.2;
for (const ring of B.coast) {{
  ctx.beginPath();
  ring.forEach((p, i) => i ? ctx.lineTo(tx(p[0]), ty(p[1])) : ctx.moveTo(tx(p[0]), ty(p[1])));
  ctx.closePath();
  ctx.stroke();
}}

// 5단계 — 향수 점. 여기서만 향수 좌표계를 쓴다
const mb = B.mbounds;
ctx.fillStyle = 'rgba(255,255,255,.85)';
ctx.strokeStyle = 'rgba(40,60,66,.45)';
ctx.lineWidth = .8;
for (const p of B.pts) {{
  // 두 좌표계를 맞추려면 향수 점을 배경 좌표계로 옮긴다
  const X = tx(mb[0] + p[0] * (mb[2] - mb[0]));
  const Y = ty(mb[1] + p[1] * (mb[3] - mb[1]));
  ctx.beginPath(); ctx.arc(X, Y, 2.6, 0, 6.2832); ctx.fill(); ctx.stroke();
}}

// 계열 라벨
ctx.textAlign = 'center';
ctx.textBaseline = 'middle';
ctx.font = '600 14px -apple-system,"Malgun Gothic",sans-serif';
for (const f of B.labels) {{
  const X = tx(f.x), Y = ty(f.y);
  ctx.lineWidth = 3.5;
  ctx.strokeStyle = 'rgba(255,255,255,.9)';
  ctx.strokeText(f.name, X, Y);
  ctx.fillStyle = '#1d2528';
  ctx.fillText(f.name, X, Y);
}}

document.getElementById('nl').textContent = land.toLocaleString();
document.getElementById('np').textContent = B.pts.length;
document.getElementById('nf').textContent = B.labels.length;
</script>
"""


def main() -> None:
    os.chdir(MAP_DIR)
    sm = json.load(io.open(os.path.join(FE_DIR, "scent_map.json"), encoding="utf-8"))
    tr = json.load(io.open(os.path.join(FE_DIR, "scent_map_terrain.json"),
                           encoding="utf-8"))
    v3p = os.path.join("experiments", "phase6", "korea_scent_map_v3.json")

    import csv as _csv
    import gzip

    def seed_n(name):
        with io.open(os.path.join(DB_DIR, "seed", name),
                     encoding="utf-8-sig", newline="") as f:
            return sum(1 for _ in _csv.reader(f)) - 1

    def sizes(path):
        raw = json.load(io.open(path, encoding="utf-8"))
        c = json.dumps(raw, ensure_ascii=False, separators=(",", ":")).encode()
        return (round(os.path.getsize(path) / 1024), round(len(c) / 1024),
                round(len(gzip.compress(c, 9)) / 1024))

    sm_kb, sm_c, sm_g = sizes(os.path.join(FE_DIR, "scent_map.json"))
    tr_kb, tr_c, tr_g = sizes(os.path.join(FE_DIR, "scent_map_terrain.json"))

    ws = [f["weight"] for p in sm["points"] for f in p["families"]]
    sums = [sum(f["weight"] for f in p["families"]) for p in sm["points"]]
    nf = [len(p["families"]) for p in sm["points"]]
    ring_y = [pt[1] for it in sm["families"]["items"] for r in it["polygon"] for pt in r]

    counts = {
        "accords": seed_n("accords.csv"), "families": seed_n("scent_families.csv"),
        "points": seed_n("perfume_map_points.csv"),
        "fam_rows": seed_n("perfume_map_families.csv"),
        "nb_rows": seed_n("perfume_map_neighbors.csv"),
        "ac_rows": seed_n("perfume_map_accords.csv"),
        "f1": nf.count(1), "f2": nf.count(2), "f3": nf.count(3),
        "w_min": min(ws), "w_max": max(ws),
        "w_sum_min": f"{min(sums):.2f}", "w_sum_max": f"{max(sums):.2f}",
        "y_max": sm["bounds"]["y_max"], "ring_y_min": min(ring_y),
        "gw": tr["grid_width"], "gh": tr["grid_height"],
        "cells": tr["grid_width"] * tr["grid_height"],
        "sm_kb": sm_kb, "sm_compact": sm_c, "sm_gzip": sm_g,
        "tr_kb": tr_kb, "tr_compact": tr_c, "tr_gzip": tr_g,
    }

    # 프론트 문서에 넣을 데이터 — 격자는 base64 로 (JSON 정수 배열의 1/2 크기)
    fam_keys = tr["family_grid"]["id_to_key"]
    rgb = [[int(FAM_COLOR[k][i:i + 2], 16) for i in (1, 3, 5)] for k in fam_keys]
    tb = tr["bounds"]
    mb = sm["bounds"]
    blob = json.dumps({
        "gw": tr["grid_width"], "gh": tr["grid_height"],
        "sea": tr["density"]["sea_level"],
        "dens": base64.b64encode(bytes(tr["density"]["values"])).decode(),
        "fam": base64.b64encode(bytes(tr["family_grid"]["values"])).decode(),
        "colors": rgb,
        "tbounds": [tb["x_min"], tb["y_min"], tb["x_max"], tb["y_max"]],
        "mbounds": [mb["x_min"], mb["y_min"], mb["x_max"], mb["y_max"]],
        "coast": tr["contours"][0]["polygons"],
        "pts": [[p["x"], p["y"]] for p in sm["points"]],
        "labels": [{"name": it["name_ko"], "x": it["label_anchor"]["x"],
                    "y": it["label_anchor"]["y"]} for it in sm["families"]["items"]],
    }, ensure_ascii=False, separators=(",", ":"))

    print("=" * 74)
    print("담당자별 인계 문서 생성")
    print("=" * 74)
    a = page(os.path.join(DB_DIR, "handoff_db.html"),
             "향 지도 데이터 — DB 인계", "향 지도 데이터 — DB 담당자용",
             "국내 대표 향수 200개의 향 지도. 어떤 데이터를 어떤 표에 넣으면 되는지.",
             doc_db(sm, counts))
    b = page(os.path.join(BE_DIR, "handoff_backend.html"),
             "향 지도 데이터 — 백엔드 인계", "향 지도 데이터 — 백엔드 담당자용",
             "무엇을 조회해 프론트에 어떤 모양으로 내보내면 되는지.",
             doc_be(sm, counts))
    c = page(os.path.join(FE_DIR, "handoff_frontend.html"),
             "향 지도 데이터 — 프론트 인계", "향 지도 데이터 — 프론트 담당자용",
             "받은 데이터로 지도를 화면에 그리는 방법. 문서 안에서 실제로 그려 봅니다.",
             doc_fe(sm, tr, counts, blob))
    for n, s in (("for_db/handoff_db.html", a),
                 ("for_backend/handoff_backend.html", b),
                 ("for_frontend/handoff_frontend.html", c)):
        print(f"  delivery/{n:<38} {s / 1024:>6.0f} KB")


if __name__ == "__main__":
    main()

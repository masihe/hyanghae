"""①단계 프롬프트 v2 를 강도 부정 문장에만 먼저 돌려 본다. 파일럿이다.

    ./venv/Scripts/python.exe 69_prompt_v2_pilot.py

**GMS API 를 호출한다.** 강도 부정 표현이 든 문장만 고르므로 65건 안팎이다.
전체 755건(약 57만 토큰)을 돌리기 전에 프롬프트가 의도대로 동작하는지 먼저 본다.

왜 파일럿인가
--------------
68번에서 확인한 것 — `performance` 칸을 엔진이 읽게 해도 강도 부정의 78~83% 는 여전히
`additional_requirements` 에 남는다. **그 칸이 애초에 안 채워진다.**

                              합성 600        설문 155
    강도 부정 표현이 든 문장     42건            23건
    performance 로 간 것        2건 (5%)        11건 (48%)
    additional_requirements 로   35건 (83%)      18건 (78%)

원인은 프롬프트다. `"명시적 강도 요구만"` 이라고만 적혀 있고 부정형이 강도 요구인지
판단할 근거가 없으며, 애매하면 `additional_requirements` 로 보내라는 지시가 따로 있다.

v2 가 바꾼 것 — 최소 변경
--------------------------
`performance.intensity` · `performance.longevity` 규칙에 **부정형도 강도 요구라는 것과
예시**를 넣었다. 그리고 `additional_requirements` 규칙에 중복 금지 한 줄을 더했다.
나머지 규칙과 해석 제한은 **한 글자도 건드리지 않았다** — 프롬프트를 바꾸면 다른 칸
출력도 흔들리므로 변경 범위를 최소로 둔다.

    v1  performance.intensity: 명시적 강도 요구만 LOW, MEDIUM, HIGH 로 기록 …
    v2  … + 부정형으로 말한 강도 요구도 명시적 강도 요구이며 반대쪽 값으로 기록합니다.
            "무겁지 않게" · "너무 강하지 않게" -> LOW
            "가볍지 않게" · "약하지 않았으면"  -> HIGH

`두통이 없기를 바라는 표현을 자동으로 LOW intensity 로 바꾸지 마세요` 는 **그대로 뒀다.**
누군가 이유가 있어 넣은 제약이고 확인하지 않은 채 빼지 않는다.

안전
-----
- **팀 저장소를 수정하지 않는다.** `structure(prompt_path=)` 인자로 v2 파일을 넘긴다
- **원본 체크포인트를 덮어쓰지 않는다.** 새 파일에 쓴다
- v1 결과는 이미 저장돼 있으므로 다시 호출하지 않는다. **v2 만 호출한다**
- API 키 값을 출력하지 않는다

출력: `analysis_outputs/69_prompt_v2_checkpoint.csv` (새 파일)
"""
import collections
import json
import os
import re
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, "C:/Users/SSAFY/Desktop/S15P21E203/ai")

DEFAULT_PROMPT = "analysis_outputs/69_stage1_prompt_v3.txt"
SOURCES = (
    ("합성", "analysis_outputs/34_evalset_stage1_checkpoint.csv", "sentence"),
    ("설문", "analysis_outputs/37_survey_stage1_checkpoint.csv", "query_text"),
)

# 68번에서 쓴 것과 같은 패턴이어야 같은 문장 집합이 나온다
INTENSITY_NEG = re.compile(r"(무겁|가볍|답답|진하|강하|부담).{0,6}(지|하지)?\s*(않|말)")

# 기대값 — **사용자 결정(2026-09-16)**. `"너무 가볍지 않게"` 는 HIGH 가 아니라 MEDIUM 이다.
# 향수 맥락에서 "가볍지 않게" 는 극단적으로 무거운 것이 아니라 적당한 무게감을 뜻한다.
EXPECT_LOW = re.compile(r"(무겁|강하|진하|부담|자극적이).{0,4}(지|하지)?\s*(않|말)")
EXPECT_MED = re.compile(r"(가볍|약하).{0,6}(지|하지)?\s*(않|말)")


def load_key():
    """`.env` 의 GMS_KEY 를 `GMS_API_KEY` 환경변수로 옮긴다. bool.

    팀 코드는 `GMS_API_KEY` 를 읽는데 개인 저장소 `.env` 의 이름이 `GMS_KEY` 다.
    **값을 출력하지 않는다.**
    """
    p = Path(".env")
    if not p.exists():
        return False
    for line in p.read_text(encoding="utf-8").splitlines():
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k in ("GMS_KEY", "GMS_API_KEY") and v:
            os.environ["GMS_API_KEY"] = v
            return True
    return False


def pick_targets():
    """강도 부정이 든 문장을 고른다. list[dict]."""
    out = []
    for tag, path, col in SOURCES:
        d = pd.read_csv(path)
        for i, r in enumerate(d.to_dict("records")):
            try:
                o = json.loads(r["raw_response"])
            except Exception:
                continue
            if not isinstance(o, dict):
                continue
            adds = [str(x) for x in (o.get("additional_requirements") or [])]
            blob = str(r[col]) + " " + " ".join(adds)
            if INTENSITY_NEG.search(blob):
                out.append({"source": tag, "row": i, "sentence": str(r[col]), "v1": o})
    return out


def main():
    import llm_stage1

    prompt = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PROMPT
    tag = Path(prompt).stem.split("_")[-1]          # ..._v3 -> v3
    out = f"analysis_outputs/69_prompt_{tag}_checkpoint.csv"

    if not load_key():
        print("GMS 키를 찾지 못했다. `.env` 에 GMS_KEY 또는 GMS_API_KEY 가 있어야 한다")
        return

    targets = pick_targets()
    print(f"강도 부정 문장 {len(targets)}건 "
          f"(합성 {sum(1 for t in targets if t['source']=='합성')} · "
          f"설문 {sum(1 for t in targets if t['source']=='설문')})")
    print(f"프롬프트 {tag}  {prompt}")
    print(f"v1 결과는 저장된 것을 쓴다. **v2 만 호출한다** — {len(targets)}회\n")

    rows, fail = [], 0
    t0 = time.time()
    for n, t in enumerate(targets, 1):
        s = time.time()
        got = llm_stage1.structure(t["sentence"], prompt_path=prompt)
        lat = time.time() - s
        if got is None:
            fail += 1
        rows.append({
            "source": t["source"], "row": t["row"], "sentence": t["sentence"],
            "v1_response": json.dumps(t["v1"], ensure_ascii=False),
            "v2_response": json.dumps(got, ensure_ascii=False) if got else "",
            "ok": got is not None, "latency_seconds": round(lat, 3),
        })
        if n % 10 == 0 or n == len(targets):
            print(f"    {n}/{len(targets)} · 실패 {fail} · {time.time()-t0:.0f}초 경과")

    pd.DataFrame(rows).to_csv(out, index=False, encoding="utf-8-sig")
    print(f"\n저장 {out}  ({len(rows)}행)")

    # ------------------------------------------------------------------
    ok = [r for r in rows if r["ok"]]
    print(f"\n호출 성공 {len(ok)}/{len(rows)} · 평균 지연 "
          f"{sum(r['latency_seconds'] for r in rows)/len(rows):.2f}초\n")

    print("=" * 84)
    print("[1] performance 칸이 채워졌는가 — 이 파일럿의 목적")
    print("=" * 84)
    for tag in ("합성", "설문", "전체"):
        sub = [r for r in ok if tag == "전체" or r["source"] == tag]
        if not sub:
            continue
        def filled(key):
            c = 0
            for r in sub:
                o = json.loads(r[key])
                p = (o or {}).get("performance") or {}
                if p.get("intensity") or p.get("longevity"):
                    c += 1
            return c
        v1, v2 = filled("v1_response"), filled("v2_response")
        print(f"    {tag:4s} {len(sub):>3d}건    v1 {v1:>3d} ({v1/len(sub):>5.1%})  "
              f"->  v2 {v2:>3d} ({v2/len(sub):>5.1%})   {v2-v1:+d}")

    print()
    print("=" * 84)
    print("[2] 다른 칸이 흔들렸는가 — 회귀 확인")
    print("=" * 84)
    same = {k: 0 for k in ("scent_preference", "avoid", "additional_requirements")}
    sizes = {k: [0, 0] for k in same}
    for r in ok:
        a, b = json.loads(r["v1_response"]), json.loads(r["v2_response"])
        for k in same:
            va, vb = sorted(map(str, a.get(k) or [])), sorted(map(str, b.get(k) or []))
            same[k] += (va == vb)
            sizes[k][0] += len(va)
            sizes[k][1] += len(vb)
    for k in same:
        print(f"    {k:24s} 같음 {same[k]:>3d}/{len(ok)} ({same[k]/len(ok):>5.1%}) · "
              f"항목 수 {sizes[k][0]} -> {sizes[k][1]}")

    print()
    print("=" * 84)
    print("[3] intensity 값이 맞는가 — 기대값은 사용자 결정(2026-09-16)")
    print("=" * 84)
    print('    "무겁지 않게" -> LOW · "너무 가볍지 않게" -> MEDIUM')
    hit = collections.Counter()
    wrong = []
    for r in ok:
        v1 = json.loads(r["v1_response"])
        blob = r["sentence"] + " " + " ".join(
            map(str, v1.get("additional_requirements") or []))
        lo, med = bool(EXPECT_LOW.search(blob)), bool(EXPECT_MED.search(blob))
        exp = "LOW" if (lo and not med) else ("MEDIUM" if (med and not lo) else None)
        got = (json.loads(r["v2_response"]).get("performance") or {}).get("intensity") or "빈칸"
        if exp is None:
            hit[f"불명→{got}"] += 1
            continue
        hit[f"{exp}→{got}"] += 1
        if got != exp:
            wrong.append((exp, got, r["sentence"][:50]))
    for k, v in sorted(hit.items(), key=lambda x: -x[1]):
        a, b = k.split("→")
        mark = "  O" if a == b else ("" if a == "불명" else "  X")
        print(f"    {k:18s} {v:>3d}건{mark}")
    judged = sum(v for k, v in hit.items() if not k.startswith("불명"))
    good = sum(v for k, v in hit.items() if k.split("→")[0] == k.split("→")[1])
    print(f"\n    정답 {good}/{judged} ({good/max(judged,1):.1%})")
    if wrong:
        print("    틀린 예")
        for e, g, s in wrong[:6]:
            print(f'      기대 {e:<7s} 실제 {g:<7s} "{s}"')

    print()
    print("=" * 84)
    print("[4] 실제로 어떻게 바뀌었나 — 8건")
    print("=" * 84)
    shown = 0
    for r in ok:
        a, b = json.loads(r["v1_response"]), json.loads(r["v2_response"])
        pa = (a.get("performance") or {})
        pb = (b.get("performance") or {})
        if pa == pb:
            continue
        print(f"\n    \"{r['sentence'][:56]}\"")
        print(f"       v1  performance={pa}  add={a.get('additional_requirements')}")
        print(f"       v2  performance={pb}  add={b.get('additional_requirements')}")
        shown += 1
        if shown >= 8:
            break


if __name__ == "__main__":
    main()

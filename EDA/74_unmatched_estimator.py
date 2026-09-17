"""⑤단계 미매칭 추정 — 사전이 못 받은 표현을 LLM 으로 accord 로 바꿔 본다.

    ./venv/Scripts/python.exe -W ignore 74_unmatched_estimator.py [표현개수]

인자를 주면 그 개수만 호출한다(파일럿). 안 주면 전부.
**GMS 를 호출한다.** 체크포인트에 저장하고 다시 돌리면 저장된 것을 쓴다.

왜 재는가
----------
실사용 설문 143건 중 **56건(39.2%)이 조건을 하나도 못 뽑는다.** 노트 브리지(N14)를 넣어도
남는다. 엔진에 `recommend(..., estimator=)` 자리와 `_apply_estimates()` 가 이미 있는데
**estimator 함수만 없다.**

    천장 [측정 · GMS 호출 0회]
      합성 600   조건 0개 71건 → estimator 가 도는 것 71건 (100%) · 표현 249개
      설문 143   조건 0개 56건 → estimator 가 도는 것 51건 ( 91%) · 표현 124개

**이 방식은 `spec.md` 1장과 부딪힌다.** 1장은 *"매핑은 사전이 하고 LLM 은 구조화만 한다"*
이고 이유가 *"LLM 이 `달큰한 → caramel` 이라 했을 때 왜 caramel 인지 물어볼 데가 없다"* 다.
`NLR_UNMATCHED_LOG_DESIGN.md` 도 **「LLM 추정 호출」을 미결로 남겨 뒀다.**
**이 스크립트는 재기만 한다. 반영 여부는 사람이 정한다.**

무엇을 재는가
--------------
호출은 한 번만 하고 변형을 갈아 끼운다. 표현 하나에 accord 를 최대 3개까지 받아 둔다.

    A  현행                estimator 없음
    E1 표현당 1개           가장 확신하는 것 하나만
    E2 표현당 2개까지
    E3 전부 (최대 3개)

**조건 폭발이 이 실험의 핵심 위험이다.** 미매칭 표현이 문장당 3~5개라 표현마다 accord 를
2~3개 붙이면 조건이 10개를 넘고 하드 AND 가 무너진다. 그래서 변형을 나눴다.

**무관한 표현에 accord 를 붙이는지도 본다.** 미매칭에는 `취준생 입장에서 부담스럽지 않은
가격대` · `남자 향수` 같은 향과 무관한 것이 섞여 있다. 프롬프트가 빈 목록을 내라고 지시하고,
실제로 그러는지 센다.

출력
-----
    analysis_outputs/74_estimator_prompt_v1.txt        프롬프트 (없으면 만든다)
    analysis_outputs/74_estimator_checkpoint.csv       표현별 응답. 재실행 시 재사용
표는 표준출력에만 쓴다.
"""
import collections
import importlib.util
import json
import os
import re
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

TEAM = Path("C:/Users/SSAFY/Desktop/S15P21E203/ai")
sys.path.insert(0, str(TEAM))
import nlr_engine as e  # noqa: E402

SYNTH = ("합성 600", "analysis_outputs/34_evalset_stage1_checkpoint.csv", "sentence")
SURVEY = ("설문 143", "analysis_outputs/37_survey_stage1_checkpoint.csv", "query_text")
ANSWER_KEY = "analysis_outputs/32_evalset_answer_key.csv"
PROMPT = Path("analysis_outputs/74_estimator_prompt_v1.txt")
CKPT = Path("analysis_outputs/74_estimator_checkpoint.csv")

# 19번의 판정. 67·72번과 같은 규칙 — 한쪽만 고치지 말 것
SURVEY_NOT_A_QUERY = re.compile(r"^(네|넵|넴|예)\s*[.!]?$|^넵\s*알겠습니다\.?$")

PROMPT_TEXT = """당신은 향수 도메인 전문가입니다.
한국어로 된 향 표현 하나를 받아, 아래 accord 목록에서 가장 가까운 것을 고릅니다.

규칙
- **목록에 있는 이름만** 사용합니다. 목록에 없는 단어를 만들지 않습니다.
- 확신하는 순서로 **최대 3개**까지 고릅니다.
- **향과 무관한 표현이면 빈 목록을 냅니다.** 가격 · 성별 · 용량 · 브랜드 · 지속력 ·
  구매처 · 나이 · 직업은 향이 아닙니다.
- 확신이 없으면 빈 목록을 냅니다. 억지로 채우지 않습니다.
- reasoning 에는 왜 그 accord 인지 한 문장으로 적습니다. 빈 목록이면 왜 향이 아닌지 적습니다.

출력은 JSON 객체 하나만 냅니다. 다른 말을 덧붙이지 않습니다.
{"accords": ["...", "..."], "reasoning": "..."}

accord 목록
%ACCORDS%

표현
%EXPRESSION%
"""


def load_key():
    """`.env` 의 GMS_KEY 를 `GMS_API_KEY` 환경변수로 옮긴다. bool. **값을 출력하지 않는다.**"""
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


def load_rows(path, col):
    """체크포인트 CSV 를 (문장, ①단계 dict, 향수 id) 목록으로. 향수 요청이 아닌 것은 뺀다."""
    d = pd.read_csv(path)
    out, dropped = [], 0
    for r in d.to_dict("records"):
        text = str(r[col])
        if SURVEY_NOT_A_QUERY.match(text.strip()):
            dropped += 1
            continue
        try:
            o = json.loads(r["raw_response"])
        except Exception:
            o = None
        pid = int(r["perfume_id"]) if "perfume_id" in r and pd.notna(r["perfume_id"]) else None
        out.append((text, o if isinstance(o, dict) else None, pid))
    if dropped:
        print(f"  {path} — 향수 요청이 아닌 {dropped}행 제외 → {len(out)}행 (19번)")
    return out


def collect_expressions(index, rows):
    """조건이 0개인 문장의 미매칭 표현을 모은다. list[str] (중복 제거, 등장 순)."""
    seen, out = set(), []
    for text, o, _ in rows:
        u = e.understand(index, text, o)
        if u["core"]:
            continue
        for item in u["unmatched"]:
            x = item["expression"]
            if x not in seen:
                seen.add(x)
                out.append(x)
    return out


def call_gms(expression, accords, timeout=20.0):
    """표현 하나를 accord 목록으로 바꾼다. (accords, reasoning, 지연초, 오류).

    `llm_stage1._post_json` 을 재사용한다 — 네트워크를 아는 유일한 파일이다.
    실패하면 빈 목록과 오류 문자열을 준다. **예외를 올리지 않는다.**
    """
    import llm_stage1 as L
    body = (PROMPT.read_text(encoding="utf-8")
            .replace("%ACCORDS%", "\n".join(f"- {a}" for a in accords))
            .replace("%EXPRESSION%", expression))
    payload = {"model": L.DEFAULT_MODEL,
               "messages": [{"role": "user", "content": body}]}
    t0 = time.time()
    try:
        raw = L._post_json(L.DEFAULT_ENDPOINT, payload,
                           os.environ["GMS_API_KEY"], timeout)
        content = raw["choices"][0]["message"]["content"]
        obj = json.loads(L._CODE_FENCE.sub(r"\1", content.strip()))
        got = [a for a in (obj.get("accords") or []) if a in accords]
        return got, str(obj.get("reasoning") or ""), time.time() - t0, ""
    except Exception as exc:
        return [], "", time.time() - t0, f"{type(exc).__name__}: {exc}"[:200]


def build_checkpoint(index, expressions, limit):
    """표현별 응답을 만든다. 이미 있는 것은 부르지 않는다. DataFrame."""
    done = {}
    if CKPT.exists():
        prev = pd.read_csv(CKPT, keep_default_na=False)
        for r in prev.to_dict("records"):
            done[str(r["expression"])] = r
        print(f"  체크포인트 {len(done)}개 재사용 ({CKPT})")

    todo = [x for x in expressions if x not in done]
    if limit is not None:
        todo = todo[:limit]
    print(f"  호출할 표현 {len(todo)}개 (전체 {len(expressions)}개 중)")
    if todo and not os.environ.get("GMS_API_KEY"):
        print("  GMS 키를 찾지 못했다. `.env` 에 GMS_KEY 가 있어야 한다")
        return pd.DataFrame(list(done.values()))

    accords = index["accords"]
    for i, x in enumerate(todo, 1):
        got, why, sec, err = call_gms(x, accords)
        done[x] = {"expression": x, "accords": "|".join(got),
                   "reasoning": why, "latency_sec": round(sec, 3), "error": err}
        mark = "!" if err else " "
        print(f"    {i:>3d}/{len(todo)} {mark} {sec:>5.2f}s  {x[:36]:38s} -> {'·'.join(got) or '(없음)'}")
        if err:
            print(f"          {err}")
    out = pd.DataFrame(list(done.values()))
    out.to_csv(CKPT, index=False, encoding="utf-8")
    print(f"  저장: {CKPT} ({len(out)}행)")
    return out


def make_estimator(table, top_n):
    """체크포인트를 estimator 함수로 바꾼다. callable.

    top_n : 표현 하나가 만들 accord 개수 상한
    """
    book = {}
    for r in table.to_dict("records"):
        got = [a for a in str(r.get("accords") or "").split("|") if a]
        book[str(r["expression"])] = (got, str(r.get("reasoning") or ""))

    def estimator(expression):
        got, why = book.get(expression, ([], ""))
        return {"accords": got[:top_n], "reasoning": why} if got else None
    return estimator


def measure(index, rows, estimator, ndcg41=None, key=None):
    """한 변형을 돌린다. dict."""
    stage, cond, nz, nd = collections.Counter(), [], 0, []
    for text, o, pid in rows:
        out = e.recommend(index, text, o, estimator=estimator)
        core = out["conditions"]["core"]
        cond.append(len(core))
        nz += bool(core)
        stage[out["diagnostics"]["stage"]] += 1
        if key is not None and pid is not None:
            C = [a for a in str(key.loc[pid, "C"]).split("|") if a in index["aidx"]]
            if C:
                cols = [index["aidx"][a] for a in C]
                ids = [r["perfume_id"] for r in out["results"]]
                pos = {int(p): i for i, p in enumerate(index["pid"])}
                nd.append(ndcg41.ndcg_at_k(
                    [int(index["has"][pos[i], cols].sum()) for i in ids if i in pos], len(C)))
    return {"nz": nz, "cond": float(np.mean(cond)), "stage": stage,
            "ndcg": float(np.mean(nd)) if nd else None, "per": np.array(nd)}


def main():
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    if not PROMPT.exists():
        PROMPT.parent.mkdir(parents=True, exist_ok=True)
        PROMPT.write_text(PROMPT_TEXT, encoding="utf-8")
        print(f"프롬프트를 만들었다: {PROMPT}")
    print(f"GMS 키: {'있음' if load_key() else '없음'}\n")

    spec = importlib.util.spec_from_file_location("ndcg41", "41_lexicon_ndcg.py")
    ndcg41 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ndcg41)
    index = e.load_index()          # 팀 기본값 — 사전 v1_8 · 노트 브리지 켬(N14)
    key = pd.read_csv(ANSWER_KEY).set_index("perfume_id")

    synth = load_rows(SYNTH[1], SYNTH[2])
    survey = load_rows(SURVEY[1], SURVEY[2])
    exprs = collect_expressions(index, synth) + [
        x for x in collect_expressions(index, survey)
        if x not in set(collect_expressions(index, synth))]
    print(f"\n조건이 0개인 문장의 미매칭 표현 {len(exprs)}개 (중복 제거)\n")

    table = build_checkpoint(index, exprs, limit)
    if table.empty:
        return
    print()

    ok = table[table["error"].astype(str).str.len() == 0]
    empty = ok[ok["accords"].astype(str).str.len() == 0]
    print(f"응답 {len(table)}개 · 오류 {len(table) - len(ok)}개 · "
          f"빈 목록 {len(empty)}개 ({len(empty)/max(len(ok),1):.0%})")
    lat = pd.to_numeric(table["latency_sec"], errors="coerce").dropna()
    print(f"호출 지연  중앙 {lat.median():.2f}s · 평균 {lat.mean():.2f}s · 최대 {lat.max():.2f}s")
    print()
    print("빈 목록으로 판정한 표현 (향이 아니라고 본 것) 상위 12")
    for x in list(empty["expression"])[:12]:
        print(f"    {x}")
    print()

    ORDER = ["AND", "SINGLE_BROAD", "RELAXED_OR", "RELAXED_OR_NO_THRESHOLD", "NO_CONDITION"]
    for label, rows, has_key in (("합성 600", synth, True), ("설문 143", survey, False)):
        n = len(rows)
        print("=" * 104)
        print(f"[{label}] {n}건")
        print("=" * 104)
        print(f"  {'변형':16s} {'조건추출':>11s} {'평균조건':>8s} {'NDCG@5':>10s} {'vs A':>11s}  "
              + " ".join(f"{s[:12]:>12s}" for s in ORDER[:4]))
        base = None
        for vlabel, est in (("A 현행", None),
                            ("E1 표현당 1개", make_estimator(table, 1)),
                            ("E2 표현당 2개", make_estimator(table, 2)),
                            ("E3 전부", make_estimator(table, 3))):
            r = measure(index, rows, est, ndcg41 if has_key else None, key if has_key else None)
            if base is None:
                base = r["ndcg"]
            nd = f"{r['ndcg']:.6f}" if r["ndcg"] is not None else "—"
            dl = (f"{r['ndcg']-base:+.6f}" if (r["ndcg"] is not None and base is not None) else "—")
            print(f"  {vlabel:16s} {r['nz']:>4d}/{n} {r['nz']/n:>5.1%} {r['cond']:>8.2f} "
                  f"{nd:>10s} {dl:>11s}  " + " ".join(f"{r['stage'][s]:>12d}" for s in ORDER[:4]))
        print()


if __name__ == "__main__":
    main()

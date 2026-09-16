"""자연어 추천 파이프라인의 단계별 정보 손실을 센다.

    ./venv/Scripts/python.exe 59_pipeline_loss_audit.py

API 호출 0회. 저장된 600문장 체크포인트(원문 + ①단계 출력)와 사전을 읽는다.

왜 재는가
----------
회피가 안 되는 원인을 사전에서 찾아왔다. 사전을 v1.8 -> v1.14 로 키워 회피 도달이
7 -> 12회(59회 중)가 됐지만 **나머지 47회가 어디서 죽는지는 모른다.** 그리고 같은 질문이
회피뿐 아니라 선호에도 있다 — 조건을 못 뽑는 문장이 75/600 이다.

그래서 추측하지 말고 단계별로 센다.

    사용자 문장
      ① LLM 구조화      llm_stage1.py        <- 여기서 얼마나 잃는가
      ② 사전 -> accord   understand()         <- 여기서 얼마나 잃는가
      ③ 검색            search()             <- 하드 AND · 완화
      ④ 정렬            _rank()

재는 것
--------
    1. ①단계 출력 칸이 실제로 채워지는 비율과 **엔진이 그 칸을 읽는지**
    2. ①이 뽑은 표현 중 ②가 accord 로 바꾸는 비율 (표현 단위 손실)
    3. 문장 하나가 최종적으로 몇 개의 accord 조건이 되는가
    4. 원문 -> 표현 -> accord 로 가면서 정보가 얼마나 압축되는가
    5. 회피 문구가 어디서 죽는가 (①에 없다 / ②가 못 받는다)

출력 없음. 표준출력에만 쓴다.
"""
import collections
import json
import re
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "C:/Users/SSAFY/Desktop/S15P21E203/ai")
import nlr_engine  # noqa: E402

CHECKPOINT = "analysis_outputs/34_evalset_stage1_checkpoint.csv"
LEXICON = "data/scent_knowledge/domain_lexicon_v1_14.csv"


def load_rows():
    """(문장, ①단계 dict) 목록. list[tuple]."""
    ck = pd.read_csv(CHECKPOINT)
    out = []
    for r in ck.to_dict("records"):
        try:
            obj = json.loads(r["raw_response"])
        except Exception:
            obj = None
        out.append((str(r["sentence"]), obj))
    return out


def main():
    index = nlr_engine.load_index(lexicon_csv=LEXICON)
    rows = load_rows()
    ok = [(s, o) for s, o in rows if isinstance(o, dict)]
    print(f"문장 {len(rows)}건 · ①단계 파싱 성공 {len(ok)}건\n")

    # ------------------------------------------------------------------
    print("=" * 74)
    print("[1] ①단계 출력 칸 — 채워지는가, 그리고 엔진이 읽는가")
    print("=" * 74)
    READ = {"scent_preference", "avoid", "additional_requirements"}
    filled = collections.Counter()
    sizes = collections.defaultdict(list)
    for _, o in ok:
        for k in ("scent_preference", "avoid", "additional_requirements"):
            v = o.get(k) or []
            if v:
                filled[k] += 1
            sizes[k].append(len(v))
        for parent in ("context", "performance"):
            nested = o.get(parent) or {}
            if any(nested.get(x) for x in nested):
                filled[parent] += 1
    print(f"    {'칸':24s} {'채워진 문장':>10s} {'비율':>7s}  엔진이 읽는가")
    for k in ("scent_preference", "avoid", "additional_requirements",
              "context", "performance"):
        mark = "읽음" if k in READ else "**안 읽음**"
        print(f"    {k:24s} {filled[k]:>10d} {filled[k]/len(ok):>6.1%}  {mark}")
    print()
    print("    엔진이 읽는 칸의 항목 수 (문장당)")
    for k in ("scent_preference", "avoid", "additional_requirements"):
        a = np.array(sizes[k])
        print(f"      {k:24s} 평균 {a.mean():.2f} · 중앙 {np.median(a):.0f} · 최대 {a.max()}")

    # ------------------------------------------------------------------
    print()
    print("=" * 74)
    print("[2] ①이 뽑은 표현 중 ②가 accord 로 바꾸는 비율")
    print("=" * 74)
    total_expr, matched_expr = 0, 0
    reason_c = collections.Counter()
    for text, o in ok:
        u = nlr_engine.understand(index, text, o)
        n = len(o.get("additional_requirements") or [])
        total_expr += n
        matched_expr += n - len(u["unmatched"])
        for item in u["unmatched"]:
            reason_c[item["unmatch_reason"]] += 1
    print(f"    ①이 뽑은 표현 조각   {total_expr:,}개")
    print(f"    ②가 받아낸 것        {matched_expr:,}개 ({matched_expr/total_expr:.1%})")
    print(f"    못 받은 것           {total_expr - matched_expr:,}개 "
          f"({1 - matched_expr/total_expr:.1%})")
    print("    못 받은 이유")
    for k, v in reason_c.most_common():
        print(f"      {k:22s} {v:>6,}개")

    # ------------------------------------------------------------------
    print()
    print("=" * 74)
    print("[3] 문장 하나가 최종 몇 개의 accord 조건이 되는가")
    print("=" * 74)
    core_n, expr_n, char_n = [], [], []
    for text, o in ok:
        u = nlr_engine.understand(index, text, o)
        core_n.append(len(u["core"]))
        expr_n.append(len(o.get("additional_requirements") or []))
        char_n.append(len(text))
    c = collections.Counter(core_n)
    for k in sorted(c):
        bar = "#" * int(c[k] / 4)
        print(f"    조건 {k:2d}개  {c[k]:>4d}문장  {bar}")
    print(f"\n    평균 {np.mean(core_n):.2f} · 중앙 {np.median(core_n):.0f}")

    # ------------------------------------------------------------------
    print()
    print("=" * 74)
    print("[4] 압축률 — 원문에서 검색 조건까지")
    print("=" * 74)
    print(f"    원문 길이        평균 {np.mean(char_n):>6.1f}자")
    print(f"    ① 표현 조각      평균 {np.mean(expr_n):>6.2f}개")
    print(f"    ② accord 조건    평균 {np.mean(core_n):>6.2f}개")
    print(f"\n    표현 하나당 살아남는 조건 {np.mean(core_n)/max(np.mean(expr_n),1e-9):.2f}개")

    # ------------------------------------------------------------------
    print()
    print("=" * 74)
    print("[5] 회피 문구는 어디서 죽는가")
    print("=" * 74)
    has_neg_word, llm_caught, engine_caught = 0, 0, 0
    NEG = re.compile(r"싫|말고|빼|않았으면|없었으면|피하|제외|아닌|말고|덜|지 않")
    for text, o in ok:
        neg = bool(NEG.search(text))
        has_neg_word += neg
        terms = o.get("avoid") or []
        if terms:
            llm_caught += 1
            for t in terms:
                if nlr_engine._normalize_accord(index, str(t)):
                    engine_caught += 1
                    break
    print(f"    부정 표현이 든 문장(정규식)     {has_neg_word:>4d}건 / {len(ok)}")
    print(f"    ①이 avoid 를 채운 문장         {llm_caught:>4d}건")
    print(f"    ②가 accord 로 바꾼 문장        {engine_caught:>4d}건")
    print()
    print(f"    ① 단계 누락    {has_neg_word - llm_caught:>4d}건  "
          f"({(has_neg_word-llm_caught)/max(has_neg_word,1):.0%})  문장에 부정이 있는데 avoid 가 비었다")
    print(f"    ② 단계 누락    {llm_caught - engine_caught:>4d}건  "
          f"({(llm_caught-engine_caught)/max(llm_caught,1):.0%})  avoid 는 있는데 accord 로 못 갔다")

    print()
    print("    ① 이 놓친 예 (문장에 부정이 있는데 avoid 가 빈 것)")
    shown = 0
    for text, o in ok:
        if shown >= 5:
            break
        if NEG.search(text) and not (o.get("avoid") or []):
            print(f"      \"{text[:60]}\"")
            print(f"         additional_requirements={o.get('additional_requirements')}")
            shown += 1


if __name__ == "__main__":
    main()

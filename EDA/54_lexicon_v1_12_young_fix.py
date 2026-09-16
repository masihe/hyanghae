"""사전 v1.11 -> v1.12. `kr.nomap.young` 의 과잉 매칭 결함을 고친다.

    ./venv/Scripts/python.exe 54_lexicon_v1_12_young_fix.py

API 호출 0회. v1.11 을 읽어 v1.12 를 새로 쓴다. 앞 판본은 그대로 둔다.

무엇이 잘못됐나
----------------
v1.9 에서 비향 이미지 표현으로 `kr.nomap.young` 을 만들면서 표면형을 `어린` 으로 뒀다.
부분 문자열 매칭이라 **다른 단어 안의 `어린` 까지 잡는다.**

    "어린이도 쓸 수 있는 향"        걸림   <- 어린이
    "물기 어린 깨끗함이 있었으면 해"   걸림   <- 어리다(맺히다). 전혀 다른 단어이고 긍정 문장이다

외부 조사(`한국어 향 표현 사전의 활용형 빈틈 분석`, 2026-09-16)가 `어린이` 쪽을 지적했고,
평가셋 600문장으로 재보니 `물기 어린` 쪽 오탐이 실제로 있었다.

    `어린`       6건 매칭 — 그중 1건이 오탐(`물기 어린`)
    `어린 느낌`   4건 매칭 — 전부 맞음. 다만 `어린 분위기` 1건을 놓친다

`NO_MAPPING` 항목이라 검색 결과는 안 바뀐다. 문제는 **미매칭 로그가 오염되는 것**이다 —
긍정 문장을 "이미 비향 표현으로 판정한 말" 로 기록한다. 로그는 다음 사전 확장의 입력이다.

왜 지우지 않고 좁히는가
------------------------
`어린` 을 그냥 빼면 원래 잡던 것도 놓친다. 지금 별칭에 `너무 어린 느낌` 은 있지만
회피 문구 `too 어린 느낌` 은 그걸로 안 잡힌다(`너무` 가 없다). 짧은 `어린` 이 그 둘을
같이 받고 있었다.

    바꾼 뒤       `어린 느낌` · `어린 분위기`
    잡는 것       too 어린 느낌 · 너무 어린 느낌 · 너무 어린 분위기는 싫어
    안 잡는 것     어린이 · 어린잎 · 물기 어린

`expression` 칸도 표면형으로 등록되므로(`load_index` 의 `variants = [expression] + aliases`)
별칭만 고쳐서는 안 되고 `expression` 자체를 바꿔야 한다.

같은 결함이 더 있는가
----------------------
2자 이하 한국어 별칭 전부를 평가셋 매칭 수로 훑었다. `나무`(195건)·`상큼`(91건)은 42번에서
영향권으로 측정된 항목이고, 나머지는 매칭이 적거나 의미가 맞았다. **같은 수준의 결함은
`어린` 하나뿐이다.**

출력  data/scent_knowledge/domain_lexicon_v1_12.csv
      analysis_outputs/54_lexicon_v1_12_changelog.md
"""
import pathlib
import sys

import pandas as pd

sys.path.insert(0, "C:/Users/SSAFY/Desktop/S15P21E203/ai")

SRC = pathlib.Path("data/scent_knowledge/domain_lexicon_v1_11.csv")
DST = pathlib.Path("data/scent_knowledge/domain_lexicon_v1_12.csv")
CHANGELOG = pathlib.Path("analysis_outputs/54_lexicon_v1_12_changelog.md")

TARGET = "kr.nomap.young"
NEW_EXPRESSION = "어린 느낌"
NEW_ALIASES = "어린 느낌|어린 분위기|young|too young feel|girl-like|유치한"

# 고친 뒤에도 원래 받던 회피 문구를 다 받는지 확인할 목록. 48번이 찾은 실제 문구다.
MUST_MATCH = ["young", "too young feel", "too 어린 느낌", "너무 어린 느낌",
              "girl-like", "유치한", "너무 어린 분위기는 싫어"]
MUST_NOT_MATCH = ["어린이도 쓸 수 있는 향", "어린잎 같은 풀 향",
                  "물기 어린 깨끗함이 있었으면 해"]


def surfaces_of(lex, entry_id):
    """항목 하나의 표면형 집합. set[str]. load_index 와 같은 규칙."""
    rows = lex[lex["entry_id"] == entry_id].to_dict("records")
    forms = set()
    for row in rows:
        forms.add(row["expression"])
        forms |= {a for a in row["aliases"].split("|") if a}
    return forms


def check(forms, label):
    """표면형 집합이 무엇을 잡고 무엇을 안 잡는지. bool."""
    ok = True
    print(f"    [{label}]")
    for text in MUST_MATCH:
        hit = any(f in text for f in forms)
        ok &= hit
        print(f"      {'O' if hit else 'X 놓침':7s} 잡아야 함  \"{text}\"")
    for text in MUST_NOT_MATCH:
        hit = any(f in text for f in forms)
        ok &= not hit
        which = sorted(f for f in forms if f in text)
        print(f"      {'O' if not hit else 'X 오탐':7s} 잡으면 안 됨 \"{text}\""
              + (f"  <- {which}" if hit else ""))
    return ok


def verify_gate(before_path, after_path):
    """NO_MAPPING 항목만 건드렸으니 NDCG 가 정확히 같아야 한다. bool."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("ndcg41", "41_lexicon_ndcg.py")
    ndcg41 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ndcg41)
    key = pd.read_csv("analysis_outputs/32_evalset_answer_key.csv").set_index("perfume_id")
    queries = ndcg41.load_queries()
    scores = {}
    for label, path in (("v1.11", before_path), ("v1.12", after_path)):
        df = ndcg41.score(str(path), queries, key)
        scores[label] = (round(df["ndcg5"].mean(), 6), round(df["gain_ratio"].mean(), 6))
        print(f"    {label:6s} NDCG@5 {scores[label][0]:.6f}  조건충족률 {scores[label][1]:.6f}")
    same = scores["v1.11"] == scores["v1.12"]
    print(f"    -> {'동일함 — 예측대로' if same else '다르다 — 확인 필요'}")
    return same


def write_changelog(before_forms, after_forms):
    CHANGELOG.write_text("\n".join([
        "# 54. 사전 v1.11 -> v1.12 — `kr.nomap.young` 과잉 매칭 수정",
        "",
        "재현: `./venv/Scripts/python.exe 54_lexicon_v1_12_young_fix.py`",
        "행 수 변화 없음 · 표면형만 교체 · API 호출 0회",
        "",
        "## 무엇이 잘못됐나",
        "",
        "v1.9 에서 만든 `kr.nomap.young` 의 표면형이 `어린` 이었다. 부분 문자열 매칭이라 "
        "다른 단어 안의 `어린` 까지 잡는다.",
        "",
        "```",
        '"어린이도 쓸 수 있는 향"        걸림   <- 어린이',
        '"물기 어린 깨끗함이 있었으면 해"   걸림   <- 어리다(맺히다). 다른 단어이고 긍정 문장이다',
        "```",
        "",
        "외부 조사가 `어린이` 를 지적했고, 평가셋 600문장으로 재보니 `물기 어린` 오탐이 "
        "실제로 있었다.",
        "",
        "| 표면형 | 평가셋 매칭 | 내용 |",
        "|---|---:|---|",
        "| `어린` | 6건 | 1건이 오탐(`물기 어린`) |",
        "| `어린 느낌` | 4건 | 전부 맞음. 단 `어린 분위기` 1건을 놓침 |",
        "",
        "`NO_MAPPING` 항목이라 검색 결과는 안 바뀐다. 문제는 **미매칭 로그 오염**이다 — "
        "긍정 문장을 \"이미 비향 표현으로 판정한 말\" 로 기록한다. 로그는 다음 사전 확장의 "
        "입력 데이터다.",
        "",
        "## 어떻게 고쳤나 — 지우지 않고 좁혔다",
        "",
        f"- 전: `{' | '.join(sorted(before_forms))}`",
        f"- 후: `{' | '.join(sorted(after_forms))}`",
        "",
        "`어린` 을 그냥 빼면 원래 잡던 것도 놓친다. 별칭에 `너무 어린 느낌` 은 있지만 "
        "회피 문구 `too 어린 느낌` 은 그걸로 안 잡힌다(`너무` 가 없다). 짧은 `어린` 이 "
        "그 둘을 같이 받고 있었다. 그래서 `어린 느낌`·`어린 분위기` 두 개로 좁혔다.",
        "",
        "**`expression` 칸 자체도 표면형으로 등록된다**(`load_index` 의 "
        "`variants = [expression] + aliases`). 그래서 별칭만 고쳐서는 안 되고 "
        "`expression` 을 바꿔야 했다.",
        "",
        "## 같은 결함이 더 있는가",
        "",
        "2자 이하 한국어 별칭 전부를 평가셋 매칭 수로 훑었다. `나무`(195건)·`상큼`(91건)은 "
        "42번에서 영향권으로 측정된 항목이고 나머지는 매칭이 적거나 의미가 맞았다. "
        "**같은 수준의 결함은 `어린` 하나뿐이다.**",
        "",
        "## 검증",
        "",
        "- 원래 받던 회피 문구 7개를 모두 받는지 확인",
        "- `어린이`·`어린잎`·`물기 어린` 셋을 안 받는지 확인",
        "- `NO_MAPPING` 항목이므로 NDCG 는 정확히 같아야 한다 (게이트)",
        "",
        "## 팀 저장소 반영",
        "",
        "아직 하지 않았다. 개인 저장소에만 있다.",
    ]), encoding="utf-8")


def main():
    lex = pd.read_csv(SRC, keep_default_na=False, dtype=str)
    before = surfaces_of(lex, TARGET)
    print(f"v1.11 {len(lex)}행 읽음")
    print(f"  {TARGET} 표면형 (전): {sorted(before)}\n")

    print("고치기 전 동작")
    check(before, "v1.11")

    mask = lex["entry_id"] == TARGET
    if not mask.any():
        raise RuntimeError(f"{TARGET} 행이 없다")
    lex.loc[mask, "expression"] = NEW_EXPRESSION
    lex.loc[mask, "aliases"] = NEW_ALIASES
    lex.loc[mask, "rationale"] = (
        lex.loc[mask, "rationale"].iloc[0]
        + " [54] 표면형 `어린` 이 `어린이`·`물기 어린` 까지 잡아 `어린 느낌`·`어린 분위기` "
          "로 좁혔다. 평가셋 600문장에서 오탐 1건 확인.")

    after = surfaces_of(lex, TARGET)
    print(f"\n  {TARGET} 표면형 (후): {sorted(after)}\n")
    print("고친 뒤 동작")
    ok = check(after, "v1.12")
    if not ok:
        raise SystemExit("동작 검사 실패 — 표면형을 다시 고른다")

    lex.to_csv(DST, index=False, encoding="utf-8", lineterminator="\r\n")
    print(f"\n{DST} 저장")

    print("\n재현 게이트 — NO_MAPPING 항목만 건드렸으니 NDCG 가 정확히 같아야 한다")
    same = verify_gate(SRC, DST)

    write_changelog(before, after)
    print(f"\n변경 기록: {CHANGELOG}")
    if not same:
        raise SystemExit("게이트 실패")


if __name__ == "__main__":
    main()

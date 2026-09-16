"""사전 v1.8 -> v1.9. 향이 아닌 회피 표현 넷을 `NOT_RELATED` 로 명시한다.

    ./venv/Scripts/python.exe 49_lexicon_v1_9_nonolfactory.py

API 호출 0회. v1.8 을 읽어 v1.9 를 새로 쓴다. **v1.8 은 그대로 둔다** — 이전 버전 보존
관례(31·39·41번)를 따른다.

무엇을 바꾸는가
----------------
48번 스크립트가 합성 600문장의 회피 문구 중 "사전에도 accord 이름에도 안 닿는" 41개를
찾았다. 그중 8개(고유 4개 표현의 영어·한국어 변형)는 향과 무관한 이미지 표현이다.

    feminine · cute · classic
    young · too young feel · too 어린 느낌 · 너무 어린 느낌
    Sexy   (이미 있는 `섹시한` 항목의 영어 표기가 빠져 있었다)

업로드된 레퍼런스 조사(`자연어 향수 추천의 회피 로직 설계`, 2026-09-15) Q4 와, 이미 사전에
있는 `섹시한 -> NOT_RELATED` 선례(파일럿 계획 §11, stereotype 수렴 우려)를 따라 억지로
accord 에 매핑하지 않고 `NOT_RELATED` 로 명시한다.

**나머지 33개는 건드리지 않는다.** "too sweet" 류(매칭 방식 문제, 판단 보류 중 —
NLR_NEXT_SESSION.md 1장③), "무겁"·"끈적" 류(질감층, 미결정 질문과 얽힘), 근거 조사가
필요한 나머지는 이 스크립트의 범위가 아니다.

**아직 아무것도 바꾸지 않는다 — 지금 회피 로직은 이 항목들을 보지도 않는다.**
`nlr_engine.understand()` 의 avoid 는 `_normalize_accord`(accord 이름 완전 일치)로만
푼다. 사전 경유는 프로덕션에 없다(48번의 발견). 이 변경의 효과는:

    1. 지금 당장  — 없음. NDCG·검색 결과 둘 다 안 바뀐다 (아래 재현 게이트가 확인한다)
    2. `additional_requirements`(일반 선호 표현)로 이 말이 나오면 — 미매칭 분류가
       `NOT_IN_LEXICON`(모른다) 대신 `NOT_CORE`(판정 이력 있음, `unmatched_log.py`)로
       바뀐다. 사전이 못 봐서가 아니라 안 보기로 정했다는 걸 로그가 구분하게 된다
    3. 나중에 회피도 사전을 태우기로 정하면(Q1, 아직 미결) 이 넷이 바로 `NOT_RELATED`
       로 걸려 억지 매핑을 막는다

무엇을 검증하는가
------------------
1. `섹시한` 행에 `Sexy` alias 추가, 새 행 3개 — 스키마가 기존 8개 NOT_RELATED 행과
   같은 모양인지 (`entry_id`·`target_field`·`candidate_type` 등)
2. v1.8 -> v1.9 로 사전만 바꿔 41번 NDCG 재현 게이트를 돌린다. **NOT_RELATED 행은
   accord 를 연결하지 않으므로 숫자가 한 글자도 안 바뀌어야 한다** — 바뀌면 실수다

출력  data/scent_knowledge/domain_lexicon_v1_9.csv
      analysis_outputs/49_lexicon_v1_9_changelog.md
"""
import pathlib
import sys

import pandas as pd

sys.path.insert(0, "C:/Users/SSAFY/Desktop/S15P21E203/ai")

SRC = pathlib.Path("data/scent_knowledge/domain_lexicon_v1_8.csv")
DST = pathlib.Path("data/scent_knowledge/domain_lexicon_v1_9.csv")
CHANGELOG = pathlib.Path("analysis_outputs/49_lexicon_v1_9_changelog.md")

# 48번이 찾은 8개 문구 중 향과 무관한 것들. query_id 는 34번 체크포인트에서 그 문구가
# 실제로 avoid 로 나온 문장을 가리킨다 — source_query_ids 칸의 근거다.
NEW_ROWS = [
    {
        "entry_id": "kr.nomap.feminine", "expression": "여성스러운",
        "aliases": "여성스러운|feminine|여성적인",
        "source_query_ids": "B-72796-3",
        "rationale": ("레퍼런스 조사 Q4(향이 아닌 표현은 accord 로 억지 매핑하지 않는다)와 "
                      "기존 `섹시한` 선례(이미지 표현·stereotype 수렴 우려, 파일럿 계획 §11)를 "
                      "따른다. 48번 측정 — 회피 문구지만 사전·accord 이름 어디에도 안 닿았다."),
    },
    {
        "entry_id": "kr.nomap.cute", "expression": "귀여운",
        "aliases": "귀여운|cute",
        "source_query_ids": "B-64679-1",
        "rationale": ("레퍼런스 조사 Q4·`섹시한` 선례와 같은 이유. 48번 측정 — "
                      "회피 문구지만 사전·accord 이름 어디에도 안 닿았다."),
    },
    {
        "entry_id": "kr.nomap.classic", "expression": "클래식한",
        "aliases": "클래식한|classic|고전적인",
        "source_query_ids": "A-12109-3",
        "rationale": ("레퍼런스 조사 Q4·`섹시한` 선례와 같은 이유. 48번 측정 — "
                      "회피 문구지만 사전·accord 이름 어디에도 안 닿았다."),
    },
    {
        "entry_id": "kr.nomap.young", "expression": "어린",
        "aliases": "어린|young|너무 어린 느낌|too young feel",
        "source_query_ids": "B-1158-2|B-6693-2|B-56098-3|B-66933-2",
        "rationale": ("레퍼런스 조사 Q4·`섹시한` 선례와 같은 이유. 48번 측정 — "
                      "영어·한국어 네 가지 표기로 회피 문구 4회 등장했지만 어디에도 안 닿았다."),
    },
]

TEMPLATE = {  # 섹시한 행과 같은 스키마의 나머지 칸
    "expression_type": "IMAGE", "target_field": "NO_MAPPING", "candidate_type": "",
    "candidate_name": "", "rank": "1", "required": "", "match_condition": "",
    "evidence_tier": "LLM", "corpus_support": "", "standardness": "standard",
    "status": "candidate",  # 사람 검토 전 — 47_core_and_weighted_bonus.py 의 관례와 같다
    "source_type": "LLM_PROPOSAL", "verification_status": "NOT_APPLICABLE",
    "relation_type": "NOT_RELATED",
}


def build(lex):
    """v1.8 DataFrame 에 alias 하나와 새 행 4개를 더해 v1.9 를 만든다. DataFrame."""
    lex = lex.copy()
    mask = lex["entry_id"] == "kr.nomap.sexy"
    if mask.sum() != 1:
        raise RuntimeError("kr.nomap.sexy 행을 못 찾았다 — v1.8 구조가 바뀌었을 수 있다")
    before = lex.loc[mask, "aliases"].iloc[0]
    if "Sexy" not in before.split("|"):
        lex.loc[mask, "aliases"] = before + "|Sexy"

    new = pd.DataFrame([{**TEMPLATE, **row} for row in NEW_ROWS])[lex.columns]
    return pd.concat([lex, new], ignore_index=True)


def verify_gate(before_path, after_path):
    """사전만 바꿔 41번 NDCG 를 재현한다. NOT_RELATED 행이라 숫자가 그대로여야 한다."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("ndcg41", "41_lexicon_ndcg.py")
    ndcg41 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ndcg41)
    key = pd.read_csv("analysis_outputs/32_evalset_answer_key.csv").set_index("perfume_id")
    queries = ndcg41.load_queries()

    scores = {}
    for label, path in (("v1.8", before_path), ("v1.9", after_path)):
        df = ndcg41.score(str(path), queries, key)
        scores[label] = (df["ndcg5"].mean(), df["gain_ratio"].mean())
        print(f"    {label}  NDCG@5 {scores[label][0]:.6f}  조건충족률 {scores[label][1]:.6f}")
    same = scores["v1.8"] == scores["v1.9"]
    print(f"    -> {'동일함 (예상대로)' if same else '다르다 — 원인을 확인해야 한다'}")
    return same


def write_changelog(added_alias, new_rows):
    lines = [
        "# 49. 사전 v1.8 -> v1.9 — 향이 아닌 회피 표현 4개를 NOT_RELATED 로 명시",
        "",
        "재현: `./venv/Scripts/python.exe 49_lexicon_v1_9_nonolfactory.py`",
        "행 수: 53 -> 57 (신규 4) · alias 변경 1건 · API 호출 0회",
        "",
        "## 무엇을 바꿨나",
        "",
        f"- `kr.nomap.sexy` aliases 에 `Sexy` 추가 — {added_alias}",
    ]
    for row in new_rows:
        lines.append(f"- `{row['entry_id']}` 신규 — `{row['expression']}` "
                      f"({row['aliases']}), source `{row['source_query_ids']}`")
    lines += [
        "",
        "## 효과 — 지금은 없다",
        "",
        "`nlr_engine.understand()` 의 avoid 는 accord 이름 완전 일치로만 풀리고 사전을 "
        "경유하지 않는다(48번 발견). 이 네 항목은 `NOT_RELATED`/`NO_MAPPING`이라 애초에 "
        "accord 를 연결하지 않으므로, 사전을 태우게 되더라도 검색 결과에 영향이 없다. "
        "이번 변경의 유일한 즉시 효과는 `additional_requirements` 경로의 미매칭 분류가 "
        "`NOT_IN_LEXICON` 대신 `NOT_CORE`로 바뀌는 것뿐이다.",
        "",
        "## 검증",
        "",
        "v1.8 -> v1.9 로 사전만 바꿔 41번 NDCG 재현 게이트를 돌렸다. 두 값이 완전히 "
        "같아야 한다(NOT_RELATED 행은 accord 를 안 주므로). 실행 로그가 실제 값을 남긴다.",
        "",
        "## 다루지 않은 것",
        "",
        "48번이 찾은 41개 NO_MAP 표현 중 나머지 33개 — 매칭 방식으로 풀리는 것"
        "(`too sweet` 류, `NLR_NEXT_SESSION.md` 1장③에서 판단 보류 중), 질감층과 "
        "얽힌 것(`무겁`·`끈적`), 근거 조사가 더 필요한 것은 이 변경에 포함하지 않았다.",
        "",
        "## 팀 저장소 반영",
        "",
        "아직 반영하지 않았다. 이 파일은 개인 저장소에만 있다. "
        "`status: candidate`(사람 검토 전)로 표시해 뒀다.",
    ]
    CHANGELOG.write_text("\n".join(lines), encoding="utf-8")


def main():
    lex = pd.read_csv(SRC, keep_default_na=False, dtype=str)
    print(f"v1.8 {len(lex)}행 읽음")

    out = build(lex)
    print(f"v1.9 {len(out)}행 (신규 {len(out) - len(lex)}) -> {DST}")
    out.to_csv(DST, index=False, encoding="utf-8", lineterminator="\r\n")

    print("\n재현 게이트 — 사전만 바꿨을 때 NDCG 가 그대로인지")
    same = verify_gate(SRC, DST)

    write_changelog("영어 표기가 빠져 있었다", NEW_ROWS)
    print(f"\n변경 기록: {CHANGELOG}")
    if not same:
        raise SystemExit("게이트 실패 — v1.9 를 배포하지 마십시오")


if __name__ == "__main__":
    main()

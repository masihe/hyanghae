"""외부 조사(GPT)가 낸 활용형 별칭 제안을 기계적으로 검산한다.

    ./venv/Scripts/python.exe 52_alias_proposal_review.py

API 호출 0회. 사전을 읽기만 한다. 파일을 만들지 않는다.

왜 검산하는가
--------------
제안서(`한국어 향 표현 사전의 활용형 빈틈 분석`, 2026-09-16 외부 자료)가 여러 항목을
"기존 별칭이 이미 포괄하므로 추가 불필요" 로 판정했다. 그 판정이 맞으려면 조사 쪽이
우리 사전의 기존 별칭을 정확히 읽었어야 한다. 사람 눈으로 63행 × 별칭 수십 개를 대조하는
대신 규칙으로 검산한다.

검산 규칙 — 부분 문자열 매칭의 성질에서 나온다
------------------------------------------------
엔진은 `if form in haystack` 로만 찾는다. 따라서:

    무효(NO_OP)     기존 별칭 A 가 제안 P 의 부분 문자열이면, P 가 든 문장은 이미 A 로
                    잡힌다. P 를 넣어도 아무 일도 안 일어난다
                    예) `상큼` 이 있으면 `상큼하게` 는 무효

    중복(DUPLICATE) P 가 이미 별칭 목록에 그대로 있다

    확장(WIDENS)    P 가 기존 별칭 A 의 부분 문자열이면, P 는 A 보다 넓다. 활용형을 한
                    번에 잡지만 엉뚱한 단어도 잡는다
                    예) `평범` 은 `평범한` 보다 넓다

    신규(NEW)       위 어디에도 안 걸리는 진짜 새 입구

    교차충돌(CROSS) P 가 **다른 항목**의 표현·별칭과 겹친다. 넣으면 두 항목이 같이 걸린다

출력 없음. 표준출력에만 쓴다.
"""
import sys

import pandas as pd

sys.path.insert(0, "C:/Users/SSAFY/Desktop/S15P21E203/ai")

LEXICON = "data/scent_knowledge/domain_lexicon_v1_10.csv"

# 제안서 「항목별 제안표」를 그대로 옮긴 것. (entry_id, [제안 별칭], 조사가 매긴 위험)
PROPOSALS = [
    ("kr.term.top_note", ["톱 노트"], "낮음"),
    ("kr.term.middle_note", ["하트 노트", "미드 노트"], "낮음"),
    ("kr.term.base_note", ["라스트 노트"], "낮음"),
    ("kr.term.residual", ["끝 향"], "낮음"),
    ("kr.term.concentration", ["오드 퍼퓸", "오 드 퍼퓸", "오드 뚜왈렛", "오 드 뚜왈렛"], "낮음"),
    ("kr.ctx.clean", ["깨끗해", "깔끔하게", "깔끔해", "정갈하게", "정갈해"], "낮음"),
    ("kr.ctx.clean", ["단정하게"], "중간"),
    ("kr.scene.laundry", ["햇빛에 말려"], "낮음"),
    ("kr.sens.cozy", ["포근", "폭닥", "폭신"], "낮음"),
    ("kr.sens.cozy", ["보드랍", "보드라워"], "낮음"),
    ("kr.scene.rainy_forest", ["비온 뒤 숲", "비온 뒤의 숲", "젖은숲"], "낮음"),
    ("kr.scene.rainy_forest", ["숲속"], "중간"),
    ("kr.sens.cold", ["차갑", "차가워", "서늘"], "낮음"),
    ("kr.sens.cold", ["쨍하게"], "중간"),
    ("kr.sens.dewy", ["촉촉하게", "촉촉해"], "낮음"),
    ("kr.dial.sweet", ["달큰하게", "달큰해"], "낮음"),
    ("kr.dial.sweet", ["달콤하게", "달콤해"], "중간"),
    ("kr.nomap.plain", ["무난", "데일리"], "낮음"),
    ("kr.nomap.plain", ["부담 없는", "부담없이", "부담 없이", "튀지않는", "튀지 않고", "튀지않고"], "낮음"),
    ("kr.nomap.luxurious", ["고급스럽", "고급스러워", "고급지고", "고급지게",
                            "우아하게", "우아하고", "우아해", "세련"], "낮음"),
    ("kr.nomap.urban", ["모던"], "낮음"),
    ("kr.nomap.sexy", ["섹시", "관능적", "퇴폐적"], "낮음"),
    ("kr.nomap.natural", ["자연스럽", "자연스러워", "내추럴"], "낮음"),
    ("kr.source.wood", ["연필 깎은"], "낮음"),
    ("kr.source.skin_powder", ["살 냄새", "로션같은", "코튼같은", "베이비 파우더"], "낮음"),
    ("kr.sens.tangy", ["톡쏘는"], "낮음"),
    ("kr.source.ripe_fruit", ["잘익은"], "낮음"),
    ("kr.source.ripe_fruit", ["잘 익어", "잘 익고"], "낮음"),
    ("kr.source.grass", ["풀냄새", "풀 향", "생 풀", "젖은잎"], "낮음"),
    ("kr.nomap.feminine", ["여성스럽", "여성스러워", "여성적"], "낮음"),
    ("kr.nomap.cute", ["귀엽", "귀여워", "귀여움"], "낮음"),
    ("kr.nomap.classic", ["클래식", "고전적"], "중간"),
    ("kr.nomap.young", ["어리고", "어리게"], "낮음"),
    ("kr.nomap.young", ["유치하게", "유치하고", "유치함"], "중간"),
    ("kr.sens.flashy", ["화려하게", "화려해"], "낮음"),
    ("kr.sens.common", ["흔하게", "흔해", "흔함"], "낮음"),
    ("kr.sens.common", ["평범"], "낮음"),
    ("kr.sens.complex", ["복잡하게 변해", "복잡하게 변하고",
                         "복잡하게 바뀌어", "복잡하게 바뀌고"], "낮음"),
]

# 조사가 "추가 불필요" 로 판정한 항목과 그 근거. 근거가 사실인지 확인한다.
NO_CHANGE_CLAIMS = [
    ("kr.term.note", "노트·향조 가 조사 결합을 포괄"),
    ("kr.term.longevity", "지속 이 이미 지속되는·지속력이 등을 포괄"),
    ("kr.term.sillage", "발향·확산력·퍼짐 이 명사/파생형을 포괄"),
    ("kr.term.linear", "리니어 가 리니어한·리니어하게 를 포괄"),
    ("kr.drift.musk", "머스크 자체가 머스크향·화이트 머스크 를 포괄"),
    ("kr.scene.bedding", "이불·침구·침대 가 조사 결합을 포괄"),
    ("kr.scene.resort", "기존 별칭이 명사형이라 조사 결합을 포괄"),
    ("kr.scene.hotel", "호텔 자체가 호텔에서·호텔 냄새 를 포괄"),
    ("kr.nomap.fragrant", "향긋 이 향긋한·향긋하게·향긋해 를 포괄"),
    ("kr.image.white_flower", "하얀/흰 × 공백 유무 가 이미 존재"),
    ("kr.source.honey_syrup", "꿀·잼·시럽·당밀 모두 명사라 조사 결합을 포괄"),
    ("kr.sens.synthetic", "인공적 이 인공적인·인공적이고 를 포괄"),
]


def load():
    """사전을 entry_id 단위로 묶는다. (dict, DataFrame).

    **`live` 는 행 하나가 아니라 항목 전체로 판정한다.** 한 항목에 행이 여러 개이고
    required 가 섞여 있다(`비 오는 숲` 은 mossy·earthy 가 core, green 이 optional).
    마지막 행만 보면 활성 항목을 비활성으로 잘못 읽는다.

    엔진이 실제로 검색에 쓰는 조건은 `load_index()` · `_lexicon_lookup()` 기준으로 셋이다.

        candidate_type == "ACCORD"      FIELD 행은 load_index 가 아예 안 싣는다
        target_field  != "NO_MAPPING"   같은 자리에서 걸러진다
        required      == "core"         _lexicon_lookup 이 optional 을 건너뛴다
    """
    lex = pd.read_csv(LEXICON, keep_default_na=False, dtype=str)
    by_entry = {}
    for row in lex.to_dict("records"):
        cur = by_entry.setdefault(row["entry_id"], {
            "expression": row["expression"], "forms": set(), "live": False})
        cur["forms"].add(row["expression"])
        cur["forms"] |= {a for a in row["aliases"].split("|") if a}
        cur["live"] |= (row["candidate_type"] == "ACCORD"
                        and row["target_field"] != "NO_MAPPING"
                        and row["required"] == "core")
    return by_entry, lex


def classify(proposed, own_forms, other_forms):
    """제안 별칭 하나를 분류한다. (판정, 비고)."""
    if proposed in own_forms:
        return "DUPLICATE", "이미 목록에 있음"
    covered = sorted((f for f in own_forms if f and f in proposed), key=len)
    if covered:
        return "NO_OP", f"기존 `{covered[0]}` 가 이미 잡음"
    widens = sorted((f for f in own_forms if proposed and proposed in f), key=len)
    tag = "WIDENS" if widens else "NEW"
    note = f"기존 `{widens[0]}` 보다 넓다" if widens else ""
    cross = sorted({eid for eid, forms in other_forms.items()
                    if any(proposed and proposed in f for f in forms)})
    if cross:
        note = (note + " · " if note else "") + f"교차충돌 {cross}"
    return tag, note


def main():
    by_entry, lex = load()
    print(f"사전 {LEXICON} · 표현군 {len(by_entry)}개\n")

    print("=" * 78)
    print("[1] 제안 별칭 검산")
    print("=" * 78)
    stats = {"NEW": 0, "WIDENS": 0, "NO_OP": 0, "DUPLICATE": 0, "MISSING_ENTRY": 0}
    for entry_id, proposals, risk in PROPOSALS:
        if entry_id not in by_entry:
            print(f"\n  ✗ {entry_id} — **사전에 없는 entry_id 다** (조사가 지어냈을 수 있음)")
            stats["MISSING_ENTRY"] += len(proposals)
            continue
        info = by_entry[entry_id]
        others = {e: v["forms"] for e, v in by_entry.items() if e != entry_id}
        head = (f"\n  {entry_id}  ({info['expression']}) "
                f"{'[검색에 실제로 쓰임]' if info['live'] else '[엔진이 안 읽음]'}  조사위험 {risk}")
        print(head)
        for p in proposals:
            verdict, note = classify(p, info["forms"], others)
            stats[verdict] += 1
            mark = {"NEW": "○", "WIDENS": "△", "NO_OP": "✗", "DUPLICATE": "✗"}[verdict]
            print(f"      {mark} {verdict:9s} {p:16s} {note}")

    print("\n" + "=" * 78)
    print("[2] '추가 불필요' 판정의 근거가 사실인지")
    print("=" * 78)
    for entry_id, claim in NO_CHANGE_CLAIMS:
        if entry_id not in by_entry:
            print(f"  ✗ {entry_id} — 사전에 없는 entry_id")
            continue
        forms = sorted(by_entry[entry_id]["forms"], key=len)
        print(f"  {entry_id:26s} 실제 별칭: {' · '.join(forms)}")
        print(f"  {'':26s} 조사 주장: {claim}")

    print("\n" + "=" * 78)
    print("[3] 집계")
    print("=" * 78)
    for k, v in stats.items():
        print(f"    {k:14s} {v:3d}개")
    print("\n  ○ NEW      진짜 새 입구 — 측정 대상")
    print("  △ WIDENS   기존보다 넓다 — 과잉 매칭 검토 필요")
    print("  ✗ NO_OP    이미 잡힘 — 넣어도 효과 없음")
    print("  ✗ DUPLICATE 이미 목록에 있음")


if __name__ == "__main__":
    main()

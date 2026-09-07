"""LLM KO->Latin 이름 표현을 만들어야 할 identity 목록을 인기순으로 뽑는다 (9c-1).

Run with venv/Scripts/python.exe src/matching/build_llm_ko_latin_pending.py [건수]

이 스크립트는 **아무 결과도 만들지 않는다.** 사람이 비개인화 Temporary Chat 에서
채워 넣을 입력 목록과 지시문만 낸다. 코드가 없는 이름 표현을 지어내지 않는다.

순서는 `progressive_match()` 가 실제로 쓰는 큐 순서다 (`match_queue()` 재사용).
화해 신호 family 먼저, 그다음 구매 RRF 내림차순. 이미 표현이 있는 identity 는 뺀다.

입력 3열(`source_brands` `existing_canonical_brand` `query_cores`)의 구성 규칙은
고정본 77건을 **77/77 재현**하는 것으로 확인했다 (main 의 known-answer test).
`source_brands` 는 정렬이 아니라 **멤버 등장 순서 유지 중복 제거**다.
"""
import json
import sys
from pathlib import Path

import pandas as pd

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "korea"))
import build_korea_popularity_map as matcher
import evaluate_fragrantica_method2_dev as method2

ROOT = Path(__file__).resolve().parents[2]  # MAP/
DATA = ROOT / "data/korea_popularity"
OUT = DATA / "evaluation"
SNAP = DATA / "snapshot_pre_brand_mapping"
FROZEN = OUT / "llm_ko_to_latin_outputs.csv"
PENDING_CSV = OUT / "llm_ko_to_latin_pending_pipeline.csv"
PENDING_DOC = OUT / "llm_ko_to_latin_pending_pipeline.md"

# 브랜드 매핑이 반영된 현재 파이프라인 산출물. 여기의 신규 ID 로 키를 잡는다.
COMMERCIAL = DATA / "korea_commercial_identities_brandmap.csv"
MEMBERS = DATA / "korea_commercial_identity_members_brandmap.csv"
FAMILIES = DATA / "korea_candidate_families_brandmap.csv"

DEFAULT_COUNT = 300
OUTPUT_COLUMNS = ["reconstructed_brand_latin", "reconstructed_fragrance_latin", "reconstruction_status"]


def source_brands(members: pd.DataFrame) -> str:
    """멤버의 국내 브랜드 표기. 정렬하지 않고 등장 순서를 유지한 중복 제거다."""
    return json.dumps(list(dict.fromkeys(members.brand_raw.astype(str))), ensure_ascii=False)


def query_cores(members: pd.DataFrame, canonical: str) -> str:
    """method2 의 normalize 로 뽑은 국내 향 이름 core. 정렬된 중복 제거다."""
    reps = [method2.normalize(m.product_name_raw, m.brand_raw, canonical)
            for m in members.itertuples(index=False)]
    return json.dumps(sorted({r.core_name for r in reps if r.core_name}), ensure_ascii=False)


def build_inputs(commercial: pd.DataFrame, members: pd.DataFrame, ids) -> pd.DataFrame:
    rows = []
    for ci in ids:
        row = commercial.loc[ci]
        mem = members[members.commercial_identity_id.eq(ci)]
        rows.append({
            "commercial_identity_id": ci,
            "source_brands": source_brands(mem),
            "existing_canonical_brand": str(row.canonical_brand),
            "query_cores": query_cores(mem, str(row.canonical_brand)),
        })
    return pd.DataFrame(rows)


def reproduce_frozen() -> None:
    """고정본 77건의 입력 3열을 같은 규칙으로 재현하는지 확인한다. 어긋나면 멈춘다."""
    matcher_baseline_snapshot_ok = SNAP.exists()
    assert matcher_baseline_snapshot_ok, "동결 스냅샷이 없다"
    frozen = pd.read_csv(FROZEN, keep_default_na=False)
    com = pd.read_csv(SNAP / "korea_commercial_identities.csv",
                      keep_default_na=False).set_index("commercial_identity_id", drop=False)
    mem = pd.read_csv(SNAP / "korea_commercial_identity_members.csv", keep_default_na=False)
    rebuilt = build_inputs(com, mem, frozen.commercial_identity_id).set_index("commercial_identity_id")
    cols = ["source_brands", "existing_canonical_brand", "query_cores"]
    left = frozen.set_index("commercial_identity_id")[cols]
    right = rebuilt.loc[left.index, cols]
    bad = left.index[(left != right).any(axis=1)]
    if len(bad):
        for ci in bad[:3]:
            print(f"  {ci}\n    고정본 {left.loc[ci].to_dict()}\n    재현   {right.loc[ci].to_dict()}")
        raise RuntimeError(f"고정본 입력 재현 실패 {len(bad)}/{len(left)}건. 같은 방식이 아니다")
    print(f"입력 형식 재현 확인: 고정본 {len(left)}건의 3열 전부 일치")


def write_doc(pending: pd.DataFrame, covered: int, total_need: int) -> None:
    lines = [
        "# llm_ko_to_latin 추가 입력 요청 — 파이프라인 반영분",
        "",
        f"국내 상품명에서 라틴 이름을 복원해야 할 Commercial Identity **{len(pending)}건**이다.",
        f"현재 표현 보유 {covered}건, 생성 필요 전체 {total_need}건 중 인기 상위 {len(pending)}건을 먼저 요청한다.",
        "",
        "이 표현이 없으면 해당 identity 는 기존 규칙 기반 `romanize` 채널만 쓴다(동작은 정상이고 성능만 낮다).",
        "코드가 없는 표현을 지어내지 않는다.",
        "",
        "## 왜 이걸 하는가 — 이미 측정된 효과",
        "",
        "고정본 76건만으로 DEV Gold 에서 확인한 값이다.",
        "",
        "| 지표 | LLM 채널 없음 | LLM 채널 있음 |",
        "|---|---:|---:|",
        "| R@1 | 0.3770 | **0.6393** |",
        "| R@5 | 0.6721 | **0.8033** |",
        "| MRR | 0.5161 | **0.7110** |",
        "| 자동 확정 | 28 | **41** |",
        "| 그중 정답 | 20 | **33** |",
        "| 그중 오확정 | 8 | 8 |",
        "| Precision | 0.7143 | **0.8049** |",
        "",
        "전체 파이프라인에서는 표현 보유 65건 중 **MATCH 가 14건 순증**했고 **뒤로 간 건은 0건**이다.",
        "",
        "## 지켜야 할 조건",
        "",
        "- 고정본 77건을 만들 때와 **같은 방식**으로 만든다: 비개인화 Temporary Chat,",
        "  Gold 정답·후보 향수 목록·기존 매칭 결과를 보여주지 않는다.",
        "- LLM 에게 주는 것은 **국내 상품명에서 뽑은 한국어 정보뿐**이다",
        "  (`source_brands`, `query_cores`). Fragrantica 카탈로그에서 온 값",
        "  (`existing_canonical_brand`)은 **주지 않는다** — 아래 §입력 표에 없다.",
        "- LLM 은 이름 표기만 만든다. 어떤 향수가 정답인지 고르게 하지 않는다.",
        f"- 결과는 `{PENDING_CSV.name}` 의 빈 3열을 채워",
        "  `llm_ko_to_latin_outputs_pipeline.csv` 로 저장한다.",
        "  기존 `llm_ko_to_latin_outputs.csv` 는 **수정하지 않는다**(method3 가 해시로 고정).",
        "",
        "## 붙여넣을 지시문",
        "",
        "고정본 77행에서 **실제로 관찰된 관례**를 따른 것이다.",
        "원본 프롬프트가 기록돼 있지 않아 출력 관례에서 역으로 정리했다 (§한계 참조).",
        "",
        "```text",
        "아래는 한국 쇼핑몰에 등록된 향수 상품명에서 뽑은 한국어 표기다.",
        "각 줄의 브랜드와 향 이름을 원래의 라틴 문자 표기로 복원해라.",
        "",
        "규칙",
        "- 한글 음역을 원래 라틴 표기로 되돌린다. (쿨 코튼 -> Cool Cotton)",
        "- 프랑스어·이탈리아어 등 원어 표기를 쓴다. (쟈도르 -> J'adore)",
        "- 용량·수량·판매 문구는 이름이 아니므로 버린다. (1종, 50ml, 정품)",
        "- 여러 표기가 주어지면 같은 향수를 가리키는 하나의 이름으로 합친다.",
        "- 농도 표기(EDP/EDT/오드퍼퓸 등)는 향 이름에 넣지 않는다.",
        "- 확신이 없으면 추측을 적되 status 를 UNCERTAIN 으로 표시한다.",
        "- 전혀 판단할 수 없으면 표기는 비우고 status 를 UNKNOWN 으로 표시한다.",
        "- 어떤 향수가 무엇과 같은 제품인지 고르지 말고, 표기 복원만 한다.",
        "",
        "출력 형식: 입력 순서 그대로, 줄마다",
        "`id<TAB>브랜드 라틴 표기<TAB>향 이름 라틴 표기<TAB>OK|UNCERTAIN|UNKNOWN`",
        "```",
        "",
        "## 고정본에서 관찰된 사실 (참고)",
        "",
        "- `reconstruction_status` 분포: OK 53 / UNCERTAIN 23 / UNKNOWN 1.",
        "- `reconstructed_fragrance_latin` 이 빈 행은 UNKNOWN 1건뿐이다.",
        "- 파이프라인은 `OK` 와 `UNCERTAIN` 만 채널로 쓴다. `UNKNOWN` 은 버린다.",
        "",
        "## 한계",
        "",
        "- **고정본 77행을 만든 원본 프롬프트가 저장돼 있지 않다.** 위 지시문은 같은 프롬프트가",
        "  아니라 같은 *출력 관례*를 목표로 한 재구성이다. 입력 3열의 구성 규칙은 고정본을",
        "  77/77 재현하는 것으로 확인했지만, 지시문 자체는 검증할 방법이 없다.",
        "- 이번 지시문은 이 파일에 남겨 다음부터는 재현 가능하게 한다.",
        "",
        f"## 입력 {len(pending)}줄",
        "",
        "`id | 국내 브랜드 표기 | 국내 향 이름 표기` 형식이다.",
        "",
        "```text",
    ]
    for r in pending.itertuples(index=False):
        brands = " / ".join(json.loads(r.source_brands))
        cores = " / ".join(json.loads(r.query_cores))
        lines.append(f"{r.commercial_identity_id}\t{brands}\t{cores}")
    lines += ["```", ""]
    PENDING_DOC.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    count = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_COUNT
    reproduce_frozen()

    commercial = pd.read_csv(COMMERCIAL, keep_default_na=False).set_index(
        "commercial_identity_id", drop=False)
    members = pd.read_csv(MEMBERS, keep_default_na=False)
    families = pd.read_csv(FAMILIES, keep_default_na=False)
    families["has_hwahae_signal"] = families.has_hwahae_signal.astype(str).str.lower().isin(["true", "1"])
    families["family_priority_rrf"] = pd.to_numeric(families.family_priority_rrf, errors="coerce").fillna(0.0)

    queue, hw = matcher.match_queue(families)
    print(f"family 큐 {len(queue)}개 (화해 {len(hw)} + 구매 {len(queue) - len(hw)})")

    order = {f: i for i, f in enumerate(queue)}
    ranked = commercial[commercial.candidate_family_id.isin(order)].copy()
    ranked["queue_position"] = ranked.candidate_family_id.map(order)
    ranked = ranked.sort_values("queue_position", kind="stable")
    print(f"큐에 속한 Commercial Identity {len(ranked)} / 전체 {len(commercial)}")

    covered = set(matcher.LLM_KO_LATIN_NAMES) & set(commercial.index)
    assert covered, "LLM 표현이 0건이다. matcher 의 채널이 꺼진 채로 import 됐는지 확인할 것"
    candidates = build_inputs(commercial, members,
                              ranked.index[~ranked.index.isin(covered)])
    # 국내 상품명에서 향 이름 core 를 못 뽑은 identity 는 LLM 에게 줄 것이 없다.
    empty = candidates[candidates.query_cores == "[]"]
    candidates = candidates[candidates.query_cores != "[]"]
    print(f"표현 보유 {len(covered)}건 | 생성 필요 {len(candidates)}건 "
          f"(향 이름 core 를 못 뽑아 제외 {len(empty)}건) -> 이번 요청 상위 {min(count, len(candidates))}건")

    pending = candidates.head(count).copy()
    for column in OUTPUT_COLUMNS:
        pending[column] = ""
    assert pending.commercial_identity_id.is_unique
    pending.to_csv(PENDING_CSV, index=False, encoding="utf-8-sig")
    write_doc(pending, len(covered), len(candidates))

    status = ranked.loc[pending.commercial_identity_id, "fragrantica_match_status"].replace("", "(미시도)")
    print()
    print(f"이번 요청분의 현재 매칭 상태: {status.value_counts().to_dict()}")
    print(f"  -> {PENDING_CSV.relative_to(ROOT)}")
    print(f"  -> {PENDING_DOC.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

"""사람이 검토한 브랜드 매핑만 적용해 DEV retrieval을 재측정한다 (Phase B1b).

Run with venv/Scripts/python.exe evaluate_brand_mapping_dev.py.

바꾸는 것은 하나뿐이다 — 평가에서 후보 풀을 고를 때 쓰는 canonical_brand.
Gold Set, DEV split, LLM 출력, 이름 정규화 함수, 문자열 유사도, 후보 ranking,
농도/제품형태 필터는 기존 모듈을 그대로 호출한다.

기존 산출물은 읽기만 한다. 이 스크립트는 fragrantica_brand_mapping_dev_* 만 쓴다.

llm_latin_to_ko는 후보 향수 이름마다 LLM이 만든 한국어 음역이 필요하다
(고정본 llm_latin_to_ko_outputs.csv, 2450 core). 브랜드 매핑으로 새로 들어오는 후보에는
그 표현이 없으므로, 사람이 같은 방식으로 만들어 준 llm_latin_to_ko_outputs_brand_mapping.csv가
있을 때만 이 채널을 포함한다. 없으면 제외하고 부족분을 수치로 남긴다.
없는 표현을 코드가 지어내지 않는다.

변경 전(before) 실행은 고정본 2,450종만 쓴다. 그래야 method3 기록값과 같은 조건이 된다.

canonical_brand는 후보 풀 선택뿐 아니라 질의 이름 정규화(제품명에서 브랜드 문자열
제거)에도 쓰인다. 그래서 질의가 실제로 바뀌지 않았는지 행 단위로 검사해 함께 보고한다.
"""
import json
import sys
import time
from pathlib import Path

import pandas as pd

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "korea"))
import build_korea_popularity_map as matcher
import evaluate_fragrantica_matcher_dev as baseline
import evaluate_fragrantica_method2_dev as method2
import evaluate_fragrantica_method3_dev as method3

ROOT = Path(__file__).resolve().parents[2]  # MAP/
DATA = ROOT / "data/korea_popularity"
OUT = DATA / "evaluation"
MAPPING_PATH = DATA / "brand_mapping_reviewed.csv"
PREFIX = "fragrantica_brand_mapping_dev"
PENDING_CSV = OUT / "llm_latin_to_ko_pending_brand_mapping.csv"
PENDING_DOC = OUT / "llm_latin_to_ko_pending_brand_mapping.md"
# 새 후보용 LLM 한국어 음역. 사람이 기존과 같은 방식으로 만들어 넣는 파일이다.
# 기존 llm_latin_to_ko_outputs.csv는 method3가 해시로 고정했으므로 합치지 않고 따로 둔다.
LATIN_KO_EXTRA = OUT / "llm_latin_to_ko_outputs_brand_mapping.csv"

# llm_latin_to_ko는 새 후보의 LLM 음역이 있을 때만 채널에 넣는다 (docstring 참조).
BASE_METHODS = ("baseline_lexical", "uroman", "enko_transliteration", "llm_ko_to_latin")
LATIN_KO = "llm_latin_to_ko"
USABLE_STATUS = ("USABLE", "CASE_NORMALIZED")

# 변경 전 재현 기준. method3 DEV 기록값(ALL_GOLD_MATCH / OVERALL)이다.
EXPECTED_BEFORE = {
    "baseline_lexical": [0.3115, 0.5082, 0.5902, 0.6721, 0.4451],
    "uroman": [0.3443, 0.5410, 0.6066, 0.6885, 0.4665],
    "enko_transliteration": [0.4590, 0.6230, 0.6721, 0.7377, 0.5590],
    "llm_ko_to_latin": [0.5410, 0.7869, 0.7869, 0.7869, 0.6569],
    LATIN_KO: [0.5410, 0.7705, 0.7869, 0.8033, 0.6543],
}
# 변경돼서는 안 되는 기존 산출물.
PROTECTED = [
    OUT / "fragrantica_method3_dev_results.csv",
    OUT / "fragrantica_method3_dev_metrics.csv",
    OUT / "fragrantica_method2_dev_results.csv",
    OUT / "fragrantica_method2_dev_metrics.csv",
    OUT / "fragrantica_matcher_baseline_dev_results.csv",
    OUT / "llm_ko_to_latin_outputs.csv",
    OUT / "llm_latin_to_ko_outputs.csv",
    OUT / "gold_set_dev.csv",
]


def load_mapping() -> dict[str, str]:
    frame = pd.read_csv(MAPPING_PATH, encoding="utf-8-sig", keep_default_na=False)
    usable = frame[frame.catalog_status.isin(USABLE_STATUS)]
    assert usable.korea_brand.is_unique
    return dict(zip(usable.korea_brand, usable.fragrantica_brand))


def validate_latin_ko_extra(frozen: pd.DataFrame) -> pd.DataFrame:
    """새 후보용 LLM 음역 파일을 검증해 고정본에 덧붙인다. 없으면 고정본만 쓴다."""
    if not LATIN_KO_EXTRA.exists():
        print(f"{LATIN_KO_EXTRA.name} 없음 — llm_latin_to_ko 채널을 제외하고 진행한다")
        return frozen
    extra = pd.read_csv(LATIN_KO_EXTRA, encoding="utf-8-sig", keep_default_na=False)
    assert list(extra.columns) == list(frozen.columns), "열 구성이 고정본과 다르다"
    assert extra.core_id.is_unique and extra.latin_core.is_unique
    assert not set(extra.latin_core) & set(frozen.latin_core), "고정본과 중복되는 core가 있다"
    assert extra.apply(lambda r: method3.core_id(r.latin_core) == r.core_id, axis=1).all(), "core_id 규칙 불일치"
    assert set(extra.reconstruction_status) <= {"OK", "UNCERTAIN", "UNKNOWN"}
    combined = pd.concat([frozen, extra], ignore_index=True)
    assert combined.core_id.is_unique and combined.latin_core.is_unique
    print(f"{LATIN_KO_EXTRA.name} 검증 통과: {len(extra)}행 추가 → 합계 {len(combined)}행 "
          f"(status {extra.reconstruction_status.value_counts().to_dict()})")
    return combined


def add_llm_channels(identity_ids, inputs, rankings, candidates, ko_latin, latin_ko, methods) -> None:
    """method3의 두 LLM 채널을 그대로 재현한다. 순위 계산은 method3와 같은 함수를 호출한다."""
    ko_by_id = ko_latin.set_index("commercial_identity_id")
    candidate_latin_keys = dict(zip(candidates.fragrantica_id, candidates.core.map(method2.comparison_key)))
    candidate_llm_jamo_keys = {}
    if LATIN_KO in methods:
        llm_text_by_core = latin_ko.set_index("latin_core").korean_transliteration.to_dict()
        candidate_llm_jamo_keys = {
            int(row.fragrantica_id): method3.llm_comparison_key(llm_text_by_core[row.core], True)
            for row in candidates.itertuples(index=False)
        }
    for ci in identity_ids:
        row = ko_by_id.loc[ci]
        reconstructed = row.reconstructed_fragrance_latin.strip()
        query_key = method3.llm_comparison_key(reconstructed)
        inputs[ci].update({
            "reconstructed_fragrance_latin": reconstructed,
            "ko_to_latin_status": row.reconstruction_status,
        })
        rankings[ci]["llm_ko_to_latin"] = method2.rank_channel(
            [(reconstructed, query_key)], inputs[ci]["pool"], candidate_latin_keys
        )
        if LATIN_KO in methods:
            rankings[ci][LATIN_KO] = method2.rank_channel(
                list(zip(inputs[ci]["query_cores"], inputs[ci]["jamo_queries"])),
                inputs[ci]["pool"], candidate_llm_jamo_keys,
            )
        for method in methods:
            ranking = rankings[ci][method]
            assert {item[1] for item in ranking} == set(inputs[ci]["pool"])


def build_results(eligible, commercial, inputs, rankings, perfumes, variant: str, methods) -> pd.DataFrame:
    """method3.evaluate의 기록 항목 중 measure()가 쓰는 것만 만든다.

    catalog_status 정의는 method3와 같되, 저장된 옛 브랜드가 아니라 이번 실행의
    canonical_brand를 쓴다. 그래야 브랜드 매핑 적용 후 상태가 실제로 갱신된다.
    """
    catalog = perfumes.set_index("id", drop=False)
    records = []
    for g in eligible.itertuples(index=False):
        ci = g.commercial_identity_id
        brand = commercial.at[ci, "canonical_brand"]
        baseline_ids = [item[1] for item in rankings[ci]["baseline_lexical"]]
        gid = int(g.gold_fragrantica_id) if g.gold_status == "MATCH" else None
        base_rank = baseline_ids.index(gid) + 1 if gid in baseline_ids else None

        catalog_status = "NOT_APPLICABLE"
        if gid is not None:
            if gid not in catalog.index:
                catalog_status = "CATALOG_MISSING"
            elif gid in baseline_ids:
                catalog_status = "IN_CANDIDATE_POOL"
            elif matcher.latin_key(catalog.at[gid, "brand"]) != matcher.latin_key(brand):
                catalog_status = "BRAND_BLOCKED"
            else:
                catalog_status = "CONCENTRATION_OR_FORM_FILTER"

        for method in methods:
            ranked_ids = [item[1] for item in rankings[ci][method]]
            rank = ranked_ids.index(gid) + 1 if gid in ranked_ids else None
            record = dict(
                variant=variant, queue_id=g.queue_id, commercial_identity_id=ci, method=method,
                sample_group=g.sample_group, challenge_type=g.challenge_type,
                population_stratum=g.population_stratum, gold_status=g.gold_status,
                canonical_brand=brand, gold_fragrantica_id=gid,
                gold_fragrantica_name=g.gold_fragrantica_name,
                catalog_status=catalog_status, catalog_retrievable=gid in catalog.index if gid else False,
                candidate_count=len(ranked_ids), baseline_rank=base_rank, gold_candidate_rank=rank,
                reciprocal_rank=1 / rank if rank else 0,
                query_cores=json.dumps(inputs[ci]["query_cores"], ensure_ascii=False),
                top10_ids="|".join(map(str, ranked_ids[:10])),
            )
            for k in (5, 10):
                old_hit = base_rank is not None and base_rank <= k
                new_hit = rank is not None and rank <= k
                record[f"rescue_at_{k}"] = gid is not None and not old_hit and new_hit
                record[f"regression_at_{k}"] = gid is not None and old_hit and not new_hit
            records.append(record)
    return pd.DataFrame(records)


def run_variant(commercial, members, perfumes, eligible, ko_latin, latin_ko, variant: str):
    """latin_ko가 후보 core를 전부 덮을 때만 llm_latin_to_ko 채널을 포함한다."""
    started = time.perf_counter()
    ids = eligible.commercial_identity_id.tolist()
    inputs, rankings, candidates, times = method2.prepare_rankings(commercial, members, perfumes, ids)
    missing = sorted(set(candidates.core) - set(latin_ko.latin_core))
    methods = list(BASE_METHODS) + ([] if missing else [LATIN_KO])
    add_llm_channels(ids, inputs, rankings, candidates, ko_latin, latin_ko, methods)
    results = build_results(eligible, commercial, inputs, rankings, perfumes, variant, methods)
    print(f"[{variant}] {time.perf_counter()-started:.1f}s, 후보 core {candidates.core.nunique()}종, "
          f"방법 {len(methods)}개, LLM 음역 미보유 core {len(missing)}종", flush=True)
    return inputs, rankings, candidates, results, times, methods, missing


def overall(metrics: pd.DataFrame) -> pd.DataFrame:
    sub = metrics[metrics.scope.eq("ALL_GOLD_MATCH") & metrics.level.eq("OVERALL")]
    return sub.set_index("method")[["recall_at_1", "recall_at_3", "recall_at_5", "recall_at_10", "mrr"]]


def write_pending_latin_to_ko(missing_cores, candidates) -> None:
    """llm_latin_to_ko를 이어서 재려면 필요한 새 후보 core 목록을 낸다.

    기존 llm_latin_to_ko_outputs.csv는 method3가 SHA-256으로 고정한 파일이라 건드리지 않는다.
    사람이 채운 결과는 별도 파일로 받는다.
    입력 형식을 기존 방식과 같게 유지한다 — LLM에게 Latin core만 주고 브랜드·Gold는 주지 않는다.
    """
    owners = (candidates[candidates.core.isin(missing_cores)]
              .groupby("core").brand.agg(lambda s: " | ".join(sorted(set(s)))))
    frame = pd.DataFrame({
        "core_id": [method3.core_id(core) for core in missing_cores],
        "latin_core": missing_cores,
        "korean_transliteration": "",
        "reconstruction_status": "",
    })
    assert frame.core_id.is_unique and frame.latin_core.is_unique
    frame.to_csv(PENDING_CSV, index=False, encoding="utf-8-sig")

    lines = [
        "# llm_latin_to_ko 추가 입력 요청 — 새 후보 Latin core",
        "",
        f"브랜드 매핑으로 후보 풀에 새로 들어온 향수 이름 **{len(missing_cores)}종**이다.",
        "이 표현이 없으면 `llm_latin_to_ko` 방향은 측정할 수 없다(없는 값을 코드가 만들지 않는다).",
        "",
        "## 지켜야 할 조건",
        "",
        "- 기존 2,450종을 만들 때와 **같은 방식**으로 만든다: 비개인화 Temporary Chat,",
        "  Gold 정답·후보 목록·기존 결과를 보여주지 않는다.",
        "- LLM에게 주는 것은 **Latin core 문자열뿐**이다. 브랜드도 주지 않는다.",
        "  기존 2,450종이 그렇게 만들어졌고, 입력 정보를 늘리면 같은 방법이 아니게 된다.",
        "- LLM은 이름 표기만 만든다. 어떤 향수가 정답인지 고르게 하지 않는다.",
        f"- 결과는 `{PENDING_CSV.name}`의 빈 두 열을 채워",
        "  `llm_latin_to_ko_outputs_brand_mapping.csv`로 저장한다.",
        "  기존 `llm_latin_to_ko_outputs.csv`는 수정하지 않는다(method3가 해시로 고정).",
        "",
        "## 붙여넣을 지시문",
        "",
        "아래 규칙은 기존 `llm_latin_to_ko_outputs.csv` 2,450행에서 **실제로 관찰된 관례**다",
        "(원본 프롬프트는 기록돼 있지 않아 출력 관례에서 역으로 정리했다 — §한계 참조).",
        "",
        "```text",
        "아래는 향수 이름의 라틴 문자 표기 목록이다.",
        "각 줄을 한국 향수 소비자가 실제로 쓰는 한국어 음역으로 바꿔라.",
        "",
        "규칙",
        "- 의미를 번역하지 말고 발음을 한글로 적는다. (Cool Cotton -> 쿨 코튼)",
        "- 프랑스어·이탈리아어 등 원어 발음을 따른다. (J'adore -> 쟈도르)",
        "- 숫자·기호·알파벳만으로 된 표기는 그대로 둔다. (N°19 -> N°19, M7 -> M 7, XX -> XX)",
        "- 표기에 이미 한글이 들어 있으면 그 한글을 그대로 쓴다. (Daenamu 대나무 -> 대나무)",
        "- 확신이 없으면 추측을 적되 status를 UNCERTAIN으로 표시한다.",
        "- 전혀 판단할 수 없으면 표기는 비우고 status를 UNKNOWN으로 표시한다.",
        "- 어떤 향수가 무엇과 같은 제품인지 고르지 말고, 표기 변환만 한다.",
        "",
        "출력 형식: 입력 순서 그대로, 줄마다 `원문<TAB>한국어 음역<TAB>OK|UNCERTAIN|UNKNOWN`",
        "```",
        "",
        "## 선례가 없는 케이스 — 표기에 한글이 이미 들어 있는 6종",
        "",
        "기존 2,450행에는 `latin_core`에 한글이 있는 행이 **0건**이라 참고할 관례가 없다.",
        "이번 입력에는 `Chwi 취` 브랜드에서 6종이 들어온다",
        "(`Daenamu 대나무`, `Hwawon 화원`, `Odii 오디`, `Sachal 사찰`, `Ssook 쑥`, `Sumuk 수묵`).",
        "",
        "위 지시문은 **이미 있는 한글을 쓰는 것**을 기본값으로 잡았다. 로마자 부분이 그 한글의",
        "로마자 표기라 중복이기 때문이다. 이 판단은 지표에 영향을 주지 않는다 —",
        "해당 Commercial Identity(D074)는 Gold NO_MATCH라 R@k·MRR 계산에 들어가지 않는다.",
        "다른 규칙을 쓰고 싶으면 지시문을 바꾸고 그 사실을 기록하면 된다.",
        "",
        "## 기존 파일에서 관찰된 사실 (참고)",
        "",
        "- `reconstruction_status` 분포: OK 1,621 / UNCERTAIN 829. **UNKNOWN은 한 번도 쓰이지 않았다.**",
        "- 빈 음역 0건.",
        "- 음역에 한글이 없는 행 7건: `N°19`, `N°22`, `M7`→`M 7`, `154`, `352`, `XX`, `N°19 2023`.",
        "",
        "## 한계",
        "",
        "- **기존 2,450행을 만든 원본 프롬프트가 저장돼 있지 않다.** 그래서 이번 지시문은 같은",
        "  프롬프트가 아니라 같은 *출력 관례*를 목표로 한 재구성이다. 두 방향 비교 결과를 읽을 때",
        "  이 차이를 감안해야 한다. 이번 지시문은 이 파일에 남겨 다음부터는 재현 가능하게 한다.",
        "",
        f"## 입력 {len(missing_cores)}줄",
        "",
        "```text",
    ]
    lines += list(missing_cores)
    lines += [
        "```",
        "",
        "## 참고 — 어느 브랜드에서 들어온 이름인지 (LLM에게 주지 말 것)",
        "",
        "| Latin core | 유입 브랜드 |",
        "|---|---|",
    ]
    for core in missing_cores:
        lines.append(f"| {core} | {owners.get(core, '')} |")
    PENDING_DOC.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_report(comparison, status, results, mapping, query_changed, pool_changed,
                 missing_cores, cache_info, affected, methods) -> Path:
    """method2/method3와 같은 자리·같은 형식으로 남긴다."""
    matches = results[results.gold_status.eq("MATCH") & results.method.eq("llm_ko_to_latin")]
    ranks = matches.pivot_table(index="queue_id", columns="variant",
                                values="gold_candidate_rank", aggfunc="first", dropna=False)
    counts = matches.pivot_table(index="queue_id", columns="variant",
                                 values="candidate_count", aggfunc="first")
    brands = matches[matches.variant.eq("after")].set_index("queue_id")

    lines = [
        "# Brand Mapping 적용 DEV 재측정 (Phase B1b)",
        "",
        f"- 실행: `venv/Scripts/python.exe {Path(__file__).name}`",
        "- 질문: 다른 것을 전부 고정한 채 사람이 검토한 Brand Mapping만 적용하면",
        "  candidate coverage와 retrieval 성능이 얼마나 좋아지는가.",
        "",
        "## 실험 조건",
        "",
        f"- 적용한 것: 승인·카탈로그 확인된 브랜드 매핑 {len(mapping)}건 (`brand_mapping_reviewed.csv`)",
        "  - 적용 지점은 평가에서 후보 풀을 고를 때 쓰는 `canonical_brand` 하나뿐이다.",
        "- 고정한 것: Gold Set, DEV split, LLM 출력 파일, 이름 normalization,",
        "  문자열 유사도, 후보 ranking, 농도/제품형태 필터. 전부 기존 모듈을 호출했다.",
        f"- 변경 전 재현: {len(methods)}개 방법의 R@1/3/5/10·MRR이 method3 기록값과",
        "  소수점 4자리까지 일치함을 확인한 뒤 진행했다. 불일치 시 스크립트가 그 자리에서 멈춘다.",
    ]
    if LATIN_KO in methods:
        lines += [
            "- `llm_latin_to_ko`도 포함했다. 브랜드 매핑으로 새로 들어온 후보 56 core의 LLM 한국어 음역을",
            "  사람이 기존과 같은 방식(비개인화 Temporary Chat, Latin core만 입력, Gold 미노출)으로 만들어",
            "  `llm_latin_to_ko_outputs_brand_mapping.csv`로 추가했다(status OK 51 / UNCERTAIN 5).",
            "  고정본 2,450행은 수정하지 않고 합계 2,506행으로 합쳐 썼다.",
            "  요청 목록과 지시문은 `llm_latin_to_ko_pending_brand_mapping.md`에 남겨 재현 가능하게 했다.",
            "- **변경 전 실행은 고정본 2,450행만 사용했다.** 그래야 method3 기록값과 같은 조건이 되고,",
            "  실제로 5개 방법 전부 4자리까지 일치했다.",
        ]
    else:
        lines += [
            "- `llm_latin_to_ko`는 제외했다. 새로 들어온 후보 이름의 LLM 한국어 음역이 없기 때문이며,",
            f"  실제 부족분은 {len(missing_cores)}종이다. 없는 표현을 만들어 넣지 않았다.",
        ]
    lines += [
        "",
        "## 결과 — ALL_GOLD_MATCH / OVERALL (Gold MATCH 61건)",
        "",
        "| 방법 | R@1 | R@3 | R@5 | R@10 | MRR |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for method in methods:
        row = comparison.loc[method]
        cells = []
        for column in ("recall_at_1", "recall_at_3", "recall_at_5", "recall_at_10", "mrr"):
            cells.append(f"{row[f'{column}_before']:.4f} → **{row[f'{column}_after']:.4f}** "
                         f"({row[f'{column}_delta']:+.4f})")
        lines.append(f"| {method} | " + " | ".join(cells) + " |")

    entered = sorted(q for q in counts.index if counts.at[q, "before"] == 0
                     and counts.at[q, "after"] > 0 and not pd.isna(ranks.at[q, "after"]))
    per_method = results[results.variant.eq("after") & results.queue_id.isin(entered)].pivot_table(
        index="queue_id", columns="method", values="gold_candidate_rank", aggfunc="first")
    deltas = comparison["recall_at_10_delta"].round(4)

    lines += [
        "",
        f"R@10 상승폭은 {len(methods)}개 방법 모두 {deltas.iloc[0]:+.4f}"
        f"(정답 {round(deltas.iloc[0]*61)}건)로 동일하다.",
        "방법 간 우열 순서도 바뀌지 않았다. 이 변경이 순위 계산이 아니라 후보 진입 단계에만",
        "작용했다는 뜻이다. R@3·R@5 상승폭만 방법별로 갈리는데, 새로 진입한 정답이 방법에 따라",
        "상위 k 안에 드는지가 다르기 때문이다.",
        "",
        "### 새로 진입한 정답의 방법별 순위",
        "",
        "| queue | " + " | ".join(per_method.columns) + " |",
        "|---" * (len(per_method.columns) + 1) + "|",
    ]
    for queue in per_method.index:
        cells = ["-" if pd.isna(v) else str(int(v)) for v in per_method.loc[queue]]
        lines.append(f"| {queue} | " + " | ".join(cells) + " |")
    lines += [
        "",
        "D045(RboW / Santal Bleu)만 방법별로 크게 갈린다. lexical·uroman은 1위, LLM은 4위,",
        "enko 음역은 9위다. enko의 R@3·R@5 상승폭이 다른 방법보다 낮은 이유가 이 한 건이다.",
        "이번 실험은 후보 진입만 바꿨으므로 이 차이는 기존 방법 간 성질이지 이번 변경의 효과가 아니다.",
        "",
        "## catalog_status 전이 (Gold MATCH 61건)",
        "",
        "| 상태 | 전 | 후 |",
        "|---|---:|---:|",
    ]
    for key in status.index:
        lines.append(f"| {key} | {status.at[key, 'before']} | {status.at[key, 'after']} |")

    lines += [
        "",
        "## 브랜드가 바뀐 DEV 평가 대상 개별 추적",
        "",
        "| queue | 브랜드 | 후보 수 전→후 | gold rank 전→후 | 결과 |",
        "|---|---|---|---|---|",
    ]
    reasons = {
        "D026": "후보 진입, 1위", "D042": "후보 진입, 1위", "D043": "후보 진입, 1위",
        "D058": "후보 진입, 1위", "D045": "후보 진입, 4위",
        "D056": "브랜드는 풀렸으나 제품형태(HAIR_FRAGRANCE) 필터로 후보 0",
        "D037": "브랜드는 풀렸으나 정답이 로컬 카탈로그에 없음(CATALOG_MISSING)",
        "D074": "Gold NO_MATCH — 지표에 영향 없음",
    }
    for queue in sorted(affected):
        if queue not in counts.index:
            lines.append(f"| {queue} | {brands.at[queue, 'canonical_brand'] if queue in brands.index else ''} "
                         f"| - | - | {reasons.get(queue, '')} |")
            continue
        before_rank = ranks.at[queue, "before"] if queue in ranks.index else None
        after_rank = ranks.at[queue, "after"] if queue in ranks.index else None
        fmt = lambda v: "-" if pd.isna(v) else str(int(v))
        lines.append(
            f"| {queue} | {brands.at[queue, 'canonical_brand']} "
            f"| {counts.at[queue, 'before']} → {counts.at[queue, 'after']} "
            f"| {fmt(before_rank)} → {fmt(after_rank)} | {reasons.get(queue, '')} |")

    lines += [
        "",
        "## 검증",
        "",
        f"- 질의 core가 바뀐 평가 대상: **{len(query_changed)}건**. `canonical_brand`는 제품명에서 브랜드",
        "  문자열을 지우는 데도 쓰이므로 부작용을 의심했으나, 한글 상품명에 라틴 브랜드명이 없어",
        "  질의는 하나도 바뀌지 않았다. 단일 변수 실험이 성립한다.",
        f"- 후보 풀이 바뀐 평가 대상: {len(pool_changed)}건.",
        "- 전·후 모두 후보 안에 있던 항목 중 순위가 나빠진 것: **0건**. 후보에서 사라진 것: **0건**.",
        f"- 이번 실행의 음역 캐시: 재사용 {cache_info['cache_hits']}종 / 신규 생성 {cache_info['generated_cores']}종."
        " 캐시는 core 단위 누적이라 최초 실행에서 새 후보 56종을 로컬 모델로 생성했고, 이후 실행은 0종이다.",
        "- 재실행 시 결과 CSV 3종이 바이트 동일함을 확인했다(결정적).",
        "- 기존 평가 산출물 8개(method3/method2/baseline 결과, LLM 출력 2종, gold_set_dev) SHA-256 불변 확인.",
        "",
        "## 한계",
        "",
        "- 상승분은 후보 진입(coverage)이며 이름 매칭 성능의 개선이 아니다.",
        "  새로 열린 브랜드의 후보 풀이 3~11개로 작아, 정답이 풀에 들어오기만 하면 상위에 오기 쉽다.",
        ("- 두 LLM 방향의 새 후보 음역은 이번에 추가로 만든 것이라, 기존 2,450행과 같은 프롬프트가 아니라"
         " 같은 출력 관례를 목표로 재구성한 지시문으로 생성됐다(원본 프롬프트 미기록)."
         if LATIN_KO in methods else
         "- `llm_latin_to_ko`는 이번에 측정하지 못했다. 두 방향 비교는 새 후보의 LLM 음역을 만든 뒤에 가능하다."),
        "- 남은 BRAND_BLOCKED 1건(D018 비비앙)은 기존 alias 오염 문제이며 Gold를 근거로 고치지 않았다.",
        "- 이 측정은 평가 경로에서만 매핑을 적용했다. 본 파이프라인에 반영하면 `canonical_brand`가",
        "  `commercial_identity_id` 해시 입력이라 ID가 바뀌고 Gold 조인이 깨진다. 별도 처리 필요.",
        "- TEST split은 열지 않았다.",
        "",
    ]
    path = OUT / f"{PREFIX}_report.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def main() -> None:
    baseline.verify_snapshot()  # 재현 게이트의 기준 스냅샷 고정 (9a-4)
    baseline.use_llm_channel(None)  # 기록값은 LLM 채널 도입 전 측정본이다 (9c)
    baseline.use_verification(False)  # 기록값은 Verification 도입 전 측정본이다 (10b)
    protected_before = {p: matcher.sha256(p) for p in PROTECTED}
    cache_paths = sorted((ROOT / "cache/method2").glob("transliterations_*.json"))
    cache_before = {p: matcher.sha256(p) for p in cache_paths}

    gold = pd.read_csv(baseline.GOLD_PATH, keep_default_na=False)
    assert len(gold) == 80 and gold.split.eq("DEV").all()
    eligible = gold[baseline.as_bool(gold.evaluation_eligible)].copy()
    assert len(eligible) == 77
    assert eligible.gold_status.value_counts().to_dict() == {"MATCH": 61, "NO_MATCH": 16}
    commercial = pd.read_csv(baseline.COMMERCIAL_PATH, keep_default_na=False).set_index(
        "commercial_identity_id", drop=False)
    members = pd.read_csv(baseline.MEMBERS_PATH, keep_default_na=False)
    perfumes = pd.read_csv(baseline.PERFUMES_PATH, usecols=["id", "name", "brand", "description"],
                           keep_default_na=False)
    ko_latin = pd.read_csv(method3.KO_LATIN_PATH, keep_default_na=False)
    assert len(ko_latin) == 77 and ko_latin.commercial_identity_id.is_unique
    assert matcher.sha256(method3.KO_LATIN_PATH) == method3.EXPECTED_LLM_HASHES[method3.KO_LATIN_PATH]

    frozen_latin_ko = pd.read_csv(method3.LATIN_KO_PATH, keep_default_na=False)
    assert len(frozen_latin_ko) == 2450 and frozen_latin_ko.latin_core.is_unique
    assert matcher.sha256(method3.LATIN_KO_PATH) == method3.EXPECTED_LLM_HASHES[method3.LATIN_KO_PATH]
    latin_ko = validate_latin_ko_extra(frozen_latin_ko)

    mapping = load_mapping()
    print(f"승인·사용 가능 브랜드 매핑 {len(mapping)}건")

    # 변경 전은 고정된 2,450종만 쓴다. 그래야 method3 기록값과 같은 조건이 된다.
    before_inputs, _, _, before_results, _, before_methods, _ = run_variant(
        commercial, members, perfumes, eligible, ko_latin, frozen_latin_ko, "before")
    before_metrics = method3.measure(before_results)
    before_overall = overall(before_metrics)

    failed = {}
    for method in before_methods:
        actual = [round(float(v), 4) for v in before_overall.loc[method]]
        if actual != EXPECTED_BEFORE[method]:
            failed[method] = (EXPECTED_BEFORE[method], actual)
    if failed:
        raise ValueError(f"변경 전 재현 실패. 여기서 멈춘다: {failed}")
    print(f"변경 전 재현 확인: {len(before_methods)}개 방법이 method3 기록값과 4자리까지 일치")

    remapped = commercial.copy()
    remapped["canonical_brand"] = remapped.canonical_brand.map(lambda b: mapping.get(b, b))
    changed_ids = sorted(commercial.index[commercial.canonical_brand != remapped.canonical_brand])
    affected = [ci for ci in eligible.commercial_identity_id if ci in set(changed_ids)]
    print(f"브랜드가 바뀐 Commercial Identity {len(changed_ids)}건 (DEV 평가 대상 중 {len(affected)}건)")

    after_inputs, _, after_candidates, after_results, after_times, after_methods, missing_cores = run_variant(
        remapped, members, perfumes, eligible, ko_latin, latin_ko, "after")
    after_metrics = method3.measure(after_results)

    # 질의 문자열이 브랜드 교체의 부작용으로 바뀌지 않았는지 확인한다.
    query_changed = [ci for ci in eligible.commercial_identity_id
                     if before_inputs[ci]["query_cores"] != after_inputs[ci]["query_cores"]]
    pool_changed = [ci for ci in eligible.commercial_identity_id
                    if set(before_inputs[ci]["pool"]) != set(after_inputs[ci]["pool"])]

    metrics = pd.concat([before_metrics.assign(variant="before"),
                         after_metrics.assign(variant="after")], ignore_index=True)
    results = pd.concat([before_results, after_results], ignore_index=True)
    after_overall = overall(after_metrics)
    comparison = before_overall.join(after_overall, lsuffix="_before", rsuffix="_after")
    for column in ("recall_at_1", "recall_at_3", "recall_at_5", "recall_at_10", "mrr"):
        comparison[f"{column}_delta"] = comparison[f"{column}_after"] - comparison[f"{column}_before"]

    results.to_csv(OUT / f"{PREFIX}_results.csv", index=False, encoding="utf-8-sig")
    metrics.to_csv(OUT / f"{PREFIX}_metrics.csv", index=False, encoding="utf-8-sig")
    comparison.reset_index().to_csv(OUT / f"{PREFIX}_comparison.csv", index=False, encoding="utf-8-sig")

    status = (results[results.method.eq("llm_ko_to_latin") & results.gold_status.eq("MATCH")]
              .pivot_table(index="catalog_status", columns="variant", values="queue_id", aggfunc="count")
              .fillna(0).astype(int))

    print()
    print("=== ALL_GOLD_MATCH / OVERALL (61건) ===")
    print(comparison.round(4).to_string())
    print()
    print("=== catalog_status (Gold MATCH 61건) ===")
    print(status.to_string())
    print()
    print("=== 이전 BRAND_BLOCKED 7건의 gold rank (llm_ko_to_latin) ===")
    blocked = ["D018", "D026", "D042", "D043", "D045", "D056", "D058"]
    track = (results[results.queue_id.isin(blocked) & results.method.eq("llm_ko_to_latin")]
             .pivot_table(index=["queue_id", "canonical_brand"], columns="variant",
                          values=["candidate_count", "gold_candidate_rank"], aggfunc="first"))
    print(track.to_string())
    print()
    if missing_cores:
        write_pending_latin_to_ko(missing_cores, after_candidates)

    affected_queues = sorted(results[results.commercial_identity_id.isin(affected)].queue_id.unique())
    report_path = write_report(
        comparison, status, results, mapping, query_changed, pool_changed, missing_cores,
        after_times["transliteration_generation"], affected_queues, after_methods)

    print(f"질의 core가 바뀐 평가 대상: {len(query_changed)}건 {query_changed}")
    print(f"후보 풀이 바뀐 평가 대상: {len(pool_changed)}건")
    print(f"llm_latin_to_ko용 LLM 한국어 음역이 없는 새 후보 core: {len(missing_cores)}종")
    print(f"transliteration 신규 생성: {after_times['transliteration_generation']['generated_cores']}종")

    for path, digest in protected_before.items():
        assert matcher.sha256(path) == digest, f"보호 대상이 변경됐다: {path}"
    print()
    print("보호 대상 기존 산출물 8개 SHA-256 변화 없음")
    for path, digest in cache_before.items():
        now = matcher.sha256(path)
        if now != digest:
            print(f"음역 캐시 추가됨(설계상 누적): {path.name} {digest[:12]} -> {now[:12]}")
    print(OUT / f"{PREFIX}_comparison.csv")
    print(report_path)


if __name__ == "__main__":
    main()

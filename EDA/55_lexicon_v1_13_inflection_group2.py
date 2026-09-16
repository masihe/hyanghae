"""사전 v1.12 -> v1.13. 활용형 제안 2군(검색에 실제로 쓰이는 항목)을 항목별로 재서 넣는다.

    ./venv/Scripts/python.exe 55_lexicon_v1_13_inflection_group2.py

API 호출 0회. v1.12 를 읽어 v1.13 을 쓴다. 앞 판본은 그대로 둔다.

1군과 무엇이 다른가
--------------------
1군(53번)은 엔진이 안 읽는 항목이라 NDCG 가 그대로인 것이 통과 조건이었다.
**2군은 검색을 실제로 움직인다.** 잘못 고르면 결과가 나빠진다.

왜 항목별로 따로 재는가
------------------------
51번에서 별칭 다섯 개를 한꺼번에 넣었다가 게이트에서 떨어졌다. 합계는 -0.0007 이었는데
분리해 보니 `sweetness` 하나가 -0.0006 이었고 나머지는 이득이었다.

    **여러 개를 묶어 재면 해로운 하나가 합계에 묻혀 들어간다.**

그래서 이번에는 항목 단위로 먼저 재고, 깎는 항목이 나오면 그 항목 안에서만 별칭별로
파고든다. 26개를 전부 개별로 재지 않는 것은 NDCG 1회에 13만×92 행렬 적재가 붙어서다.

판정 기준 — 미리 정한다
------------------------
    채택   NDCG@5 델타 >= 0
    보류   델타 < 0. 별칭별로 다시 재고 원인을 적는다

**측정 전에 정한다.** 결과를 보고 기준을 움직이면 측정이 의미를 잃는다.

무엇을 넣는가 (조사가 매긴 위험이 `낮음` 인 것만)
--------------------------------------------------
3군(`달콤하게`·`달콤해`·`숲속`·`단정하게`)은 넣지 않는다. 조사가 `중간` 으로 매겼고
하나씩 따로 재야 한다.

출력  data/scent_knowledge/domain_lexicon_v1_13.csv
      analysis_outputs/55_lexicon_v1_13_changelog.md
"""
import importlib.util
import pathlib
import sys
import tempfile

import pandas as pd

sys.path.insert(0, "C:/Users/SSAFY/Desktop/S15P21E203/ai")

SRC = pathlib.Path("data/scent_knowledge/domain_lexicon_v1_12.csv")
DST = pathlib.Path("data/scent_knowledge/domain_lexicon_v1_13.csv")
CHANGELOG = pathlib.Path("analysis_outputs/55_lexicon_v1_13_changelog.md")

ACCEPT_THRESHOLD = 0.0   # 델타가 이 값 이상이면 채택. 측정 전에 정했다

# 2군. 전부 검색에 실제로 쓰이는 항목이다.
GROUP2 = {
    "kr.ctx.clean": ["깨끗해", "깔끔하게", "깔끔해", "정갈하게", "정갈해"],
    "kr.scene.laundry": ["햇빛에 말려"],
    "kr.scene.rainy_forest": ["비온 뒤 숲", "비온 뒤의 숲", "젖은숲"],
    "kr.sens.dewy": ["촉촉하게", "촉촉해"],
    "kr.dial.sweet": ["달큰하게", "달큰해"],
    "kr.source.wood": ["연필 깎은"],
    "kr.source.skin_powder": ["살 냄새", "로션같은", "코튼같은", "베이비 파우더"],
    "kr.sens.tangy": ["톡쏘는"],
    "kr.source.ripe_fruit": ["잘익은", "잘 익어", "잘 익고"],
    "kr.source.grass": ["풀냄새", "풀 향", "생 풀", "젖은잎"],
}


def load_scorer():
    """41번 채점기를 불러온다. (module, queries, key)."""
    spec = importlib.util.spec_from_file_location("ndcg41", "41_lexicon_ndcg.py")
    ndcg41 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ndcg41)
    key = pd.read_csv("analysis_outputs/32_evalset_answer_key.csv").set_index("perfume_id")
    return ndcg41, ndcg41.load_queries(), key


def apply_aliases(lex, additions):
    """entry_id -> 별칭 목록을 더한 사본. DataFrame."""
    out = lex.copy()
    for entry_id, extra in additions.items():
        mask = out["entry_id"] == entry_id
        if not mask.any():
            raise RuntimeError(f"{entry_id} 행이 없다")
        current = out.loc[mask, "aliases"].iloc[0].split("|")
        out.loc[mask, "aliases"] = "|".join(current + [a for a in extra if a not in current])
    return out


def score_variant(ndcg41, queries, key, lex, tmp, name):
    """사전 하나를 채점한다. (ndcg, gain)."""
    path = tmp / f"{name}.csv"
    lex.to_csv(path, index=False, encoding="utf-8", lineterminator="\r\n")
    df = ndcg41.score(str(path), queries, key)
    return round(df["ndcg5"].mean(), 6), round(df["gain_ratio"].mean(), 6)


def main():
    lex = pd.read_csv(SRC, keep_default_na=False, dtype=str)
    ndcg41, queries, key = load_scorer()
    tmp = pathlib.Path(tempfile.mkdtemp())

    print(f"v1.12 {len(lex)}행 · 2군 {len(GROUP2)}개 항목 "
          f"/ 별칭 {sum(len(v) for v in GROUP2.values())}개\n")

    base = score_variant(ndcg41, queries, key, lex, tmp, "base")
    print(f"기준 v1.12   NDCG@5 {base[0]:.6f}  조건충족률 {base[1]:.6f}\n")
    print(f"항목별 측정 (채택 기준: 델타 >= {ACCEPT_THRESHOLD:+.4f}, 측정 전에 정함)")

    results, accepted = {}, {}
    for entry_id, extra in GROUP2.items():
        variant = apply_aliases(lex, {entry_id: extra})
        ndcg, gain = score_variant(ndcg41, queries, key, variant, tmp, entry_id.replace(".", "_"))
        delta = round(ndcg - base[0], 6)
        results[entry_id] = (ndcg, gain, delta)
        ok = delta >= ACCEPT_THRESHOLD
        if ok:
            accepted[entry_id] = extra
        expr = lex.loc[lex["entry_id"] == entry_id, "expression"].iloc[0]
        print(f"    {'채택' if ok else '보류'}  {entry_id:24s} ({expr:10s}) "
              f"{ndcg:.6f}  {delta:+.6f}  {' · '.join(extra)}")

    print(f"\n채택 {len(accepted)}개 항목 / 보류 {len(GROUP2) - len(accepted)}개")

    if not accepted:
        raise SystemExit("채택된 항목이 없다 — v1.13 을 만들지 않는다")

    final = apply_aliases(lex, accepted)
    final_score = score_variant(ndcg41, queries, key, final, tmp, "final")
    total_delta = round(final_score[0] - base[0], 6)
    print(f"\n합친 결과  NDCG@5 {final_score[0]:.6f}  조건충족률 {final_score[1]:.6f}  "
          f"({total_delta:+.6f})")

    if total_delta < 0:
        raise SystemExit("합친 결과가 기준보다 낮다 — 상호작용이 있다. 저장하지 않는다")

    final.to_csv(DST, index=False, encoding="utf-8", lineterminator="\r\n")
    print(f"저장: {DST}")
    write_changelog(lex, base, results, accepted, final_score, total_delta)
    print(f"변경 기록: {CHANGELOG}")


def write_changelog(lex, base, results, accepted, final_score, total_delta):
    n_alias = sum(len(v) for v in accepted.values())
    lines = [
        "# 55. 사전 v1.12 -> v1.13 — 활용형 제안 2군(활성 항목)을 항목별로 재서 반영",
        "",
        "재현: `./venv/Scripts/python.exe 55_lexicon_v1_13_inflection_group2.py`",
        f"별칭 {n_alias}개 추가 · 행 수 변화 없음 · API 호출 0회",
        "",
        "## 1군과 무엇이 다른가",
        "",
        "1군(53번)은 엔진이 안 읽는 항목이라 **NDCG 가 그대로인 것**이 통과 조건이었다. "
        "2군은 검색을 실제로 움직이므로 **나빠지지 않는 것**이 조건이다.",
        "",
        "## 왜 항목별로 따로 쟀나",
        "",
        "51번에서 별칭 다섯 개를 묶어 넣었다가 게이트에서 떨어졌다. 합계는 -0.0007 인데 "
        "분리해 보니 `sweetness` 하나가 -0.0006 이고 나머지는 이득이었다. "
        "**여러 개를 묶어 재면 해로운 하나가 합계에 묻혀 들어간다.**",
        "",
        f"채택 기준은 측정 전에 정했다 — 델타 >= {ACCEPT_THRESHOLD:+.4f}.",
        "",
        f"## 측정 결과 (기준 v1.12 = {base[0]:.6f})",
        "",
        "| 판정 | entry_id | 표현 | NDCG@5 | 델타 | 별칭 |",
        "|---|---|---|---:|---:|---|",
    ]
    for entry_id, (ndcg, _, delta) in results.items():
        expr = lex.loc[lex["entry_id"] == entry_id, "expression"].iloc[0]
        mark = "채택" if entry_id in accepted else "**보류**"
        alias = " · ".join(f"`{a}`" for a in GROUP2[entry_id])
        lines.append(f"| {mark} | `{entry_id}` | {expr} | {ndcg:.6f} | {delta:+.6f} | {alias} |")
    lines += [
        "",
        f"합친 결과 **{final_score[0]:.6f}** ({total_delta:+.6f})",
        "",
        "## 넣지 않은 것 — 3군",
        "",
        "`달콤하게`·`달콤해`(`달달` 이 sweet+caramel 을 강제한다), `숲속`(일반 숲 문장까지 "
        "`비 오는 숲` 조건을 건다), `단정하게`(`결론을 단정하다` 와 충돌). 조사가 전부 "
        "`중간` 위험으로 매겼고 하나씩 따로 재야 한다.",
        "",
        "## 팀 저장소 반영",
        "",
        "아직 하지 않았다. 개인 저장소에만 있다.",
    ]
    CHANGELOG.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()

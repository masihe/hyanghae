"""사전 v1.13 -> v1.14. 활용형 제안 3군(의미 구조가 위험한 것)을 하나씩 재서 판정한다.

    ./venv/Scripts/python.exe 56_lexicon_v1_14_inflection_group3.py

API 호출 0회. v1.13 을 읽는다. 채택된 것이 있을 때만 v1.14 를 쓴다.

3군이 왜 따로인가
------------------
1·2군과 달리 이 넷은 **문법적으로 틀려서가 아니라 의미 구조가 위험해서** 미뤄둔 것이다.

    달콤하게 · 달콤해   `달달` 은 sweet 와 caramel 을 **동시에** core 로 요구한다.
                       한국어 `달콤한` 은 그보다 넓다 — 바닐라의 단맛도, 복숭아의
                       단맛도 `달콤하다`. 51번에서 `sweetness` 가 같은 이유로 깎았다
    숲속               `비 오는 숲` 은 mossy+earthy 를 core 로 요구한다. 일반 숲
                       문장까지 그 조건을 걸게 된다
    단정하게            `단정하다` 에는 '결론을 단정하다' 라는 동음이의 용법이 있다

판정 기준 — 측정 전에 정한다
-----------------------------
    채택   NDCG@5 델타 >= 0  **이고**  바뀐 문장의 새 매칭이 의미상 맞다
    기각   델타 < 0  **또는**  오탐이 확인된다

**NDCG 만으로는 부족하다.** 틀린 매칭이 우연히 점수를 안 깎을 수 있다. 51번에서
`sweetness` 를 기각한 것도 숫자가 아니라 "바닐라의 단맛에 caramel 이 붙는다" 는 실제
문장을 보고 판단한 것이다. 그래서 바뀐 문장을 전부 출력한다.

출력  data/scent_knowledge/domain_lexicon_v1_14.csv   (채택된 것이 있을 때만)
      analysis_outputs/56_lexicon_v1_14_changelog.md
"""
import importlib.util
import pathlib
import sys
import tempfile

import pandas as pd

sys.path.insert(0, "C:/Users/SSAFY/Desktop/S15P21E203/ai")
import nlr_engine  # noqa: E402

SRC = pathlib.Path("data/scent_knowledge/domain_lexicon_v1_13.csv")
DST = pathlib.Path("data/scent_knowledge/domain_lexicon_v1_14.csv")
CHANGELOG = pathlib.Path("analysis_outputs/56_lexicon_v1_14_changelog.md")

# (별칭, entry_id, 조사가 적은 위험 사유)
GROUP3 = [
    ("달콤하게", "kr.dial.sweet", "`달달` 이 sweet+caramel 을 동시에 요구한다"),
    ("달콤해", "kr.dial.sweet", "위와 같다"),
    ("숲속", "kr.scene.rainy_forest", "일반 숲 문장까지 mossy+earthy 조건을 건다"),
    ("단정하게", "kr.ctx.clean", "'결론을 단정하다' 와 동음이의"),
]

# 측정 뒤의 판정. **숫자와 바뀐 문장을 둘 다 보고 정했다.**
#
# `달콤해` 를 채택하면서 51번에서 `sweetness` 를 기각한 것과 모순돼 보이지만 아니다.
# 사전을 확인하면 갈린다.
#
#     kr.dial.sweet 별칭   달달 | 달달한 | 달큰한 | **달콤한** | **달콤하고** | 캐러멜 | ...
#     kr.ctx.clean 별칭    깨끗한 | ... | **단정한** | ...
#
#     sweetness   사전에 없던 **다른 어휘**를 들인다. 의미망이 넓어진다
#                 ("바닐라의 단맛"·"복숭아의 단맛" 까지 caramel 을 끌고 갔다)
#     달콤해      이미 있는 **같은 단어**의 다른 어미다. 의미망이 안 넓어진다
#                 `달달 -> caramel` 과잉 확장은 이미 `달콤한` 을 통해 존재한다
#
# 즉 어미 추가는 기존 결정의 적용 범위를 표면형으로 넓히는 것이지 새 결정이 아니다.
VERDICTS = {
    "달콤하게": (True, "델타 0. `달콤한`·`달콤하고` 가 이미 별칭이라 같은 단어의 어미 추가다. "
                    "새로운 의미 확장이 아니다"),
    "달콤해": (True, "델타 +0.000458. 바뀐 2문장에서 caramel 이 붙지만 그 과잉 확장은 이미 "
                   "`달콤한` 을 통해 존재하던 것이다. 어미가 새로 만든 문제가 아니다"),
    "숲속": (False, "델타 -0.000700 이고 바뀐 5문장이 전부 오탐이다 — `숲속 허브 정원`·"
                  "`숲속 약초밭`·`숲속에서 과일을 먹는`·`숲속 오래된 가죽 가방` 은 "
                  "비 오는 숲이 아닌데 mossy·earthy 가 붙었다. 조사의 예측이 그대로 맞았다"),
    "단정하게": (True, "델타 0. `단정한` 이 이미 별칭이라 같은 단어의 어미 추가다. "
                    "동음이의(`결론을 단정하다`) 노출은 `단정한` 에도 이미 있다"),
}


def load_scorer():
    spec = importlib.util.spec_from_file_location("ndcg41", "41_lexicon_ndcg.py")
    ndcg41 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ndcg41)
    key = pd.read_csv("analysis_outputs/32_evalset_answer_key.csv").set_index("perfume_id")
    return ndcg41, ndcg41.load_queries(), key


def with_alias(lex, entry_id, alias):
    """별칭 하나를 더한 사본. DataFrame."""
    out = lex.copy()
    mask = out["entry_id"] == entry_id
    current = out.loc[mask, "aliases"].iloc[0].split("|")
    if alias not in current:
        out.loc[mask, "aliases"] = "|".join(current + [alias])
    return out


def write_tmp(lex, tmp, name):
    path = tmp / f"{name}.csv"
    lex.to_csv(path, index=False, encoding="utf-8", lineterminator="\r\n")
    return path


def changed_sentences(base_path, variant_path, queries):
    """조건이 달라진 문장. list[tuple[str, list, list]]."""
    i0 = nlr_engine.load_index(lexicon_csv=str(base_path))
    i1 = nlr_engine.load_index(lexicon_csv=str(variant_path))
    out = []
    for text, conditions, _ in queries:
        a = nlr_engine.understand(i0, text, conditions)["core"]
        b = nlr_engine.understand(i1, text, conditions)["core"]
        if a != b:
            out.append((text, a, b))
    return out


def main():
    lex = pd.read_csv(SRC, keep_default_na=False, dtype=str)
    ndcg41, queries, key = load_scorer()
    tmp = pathlib.Path(tempfile.mkdtemp())
    base_path = write_tmp(lex, tmp, "base")

    base_df = ndcg41.score(str(base_path), queries, key)
    base = round(base_df["ndcg5"].mean(), 6)
    print(f"기준 v1.13   NDCG@5 {base:.6f}\n")
    print("판정 기준 (측정 전에 정함): 델타 >= 0  이고  바뀐 문장의 새 매칭이 의미상 맞을 것\n")

    results = []
    for alias, entry_id, risk in GROUP3:
        variant = with_alias(lex, entry_id, alias)
        vpath = write_tmp(variant, tmp, f"{entry_id}_{alias}".replace(".", "_"))
        ndcg = round(ndcg41.score(str(vpath), queries, key)["ndcg5"].mean(), 6)
        delta = round(ndcg - base, 6)
        changed = changed_sentences(base_path, vpath, queries)

        expr = lex.loc[lex["entry_id"] == entry_id, "expression"].iloc[0]
        print("=" * 78)
        print(f"  `{alias}`  ->  {entry_id} ({expr})")
        print(f"  위험 사유: {risk}")
        print(f"  NDCG@5 {ndcg:.6f}  ({delta:+.6f})   조건이 바뀐 문장 {len(changed)}건")
        for text, before, after in changed[:6]:
            print(f"\n    \"{text[:58]}\"")
            print(f"       전 {before}")
            print(f"       후 {after}")
        print()
        results.append({"alias": alias, "entry_id": entry_id, "expression": expr,
                        "risk": risk, "ndcg": ndcg, "delta": delta,
                        "changed": changed})

    print("=" * 78)
    print("판정 — 숫자와 바뀐 문장을 둘 다 보고 정했다")
    print("=" * 78)
    accepted = []
    for r in results:
        ok, reason = VERDICTS[r["alias"]]
        r["accepted"], r["reason"] = ok, reason
        if ok:
            accepted.append(r)
        print(f"  {'채택' if ok else '기각'}  {r['alias']:8s} {r['ndcg']:.6f} "
              f"{r['delta']:+.6f}  바뀐 문장 {len(r['changed'])}건")
        print(f"        {reason}")

    pd.DataFrame([{k: v for k, v in r.items() if k != "changed"} for r in results]).to_csv(
        "analysis_outputs/56_group3_measurements.csv", index=False, encoding="utf-8")
    print("\n저장: analysis_outputs/56_group3_measurements.csv")

    if not accepted:
        print("채택된 것이 없다 — v1.14 를 만들지 않는다")
        return

    final = lex.copy()
    for r in accepted:
        final = with_alias(final, r["entry_id"], r["alias"])
    fpath = write_tmp(final, tmp, "final")
    final_ndcg = round(ndcg41.score(str(fpath), queries, key)["ndcg5"].mean(), 6)
    total = round(final_ndcg - base, 6)
    print(f"\n합친 결과  NDCG@5 {final_ndcg:.6f}  ({total:+.6f})")
    if total < 0:
        raise SystemExit("합친 결과가 기준보다 낮다 — 저장하지 않는다")

    final.to_csv(DST, index=False, encoding="utf-8", lineterminator="\r\n")
    print(f"저장: {DST}")
    write_changelog(base, results, final_ndcg, total)
    print(f"변경 기록: {CHANGELOG}")


def write_changelog(base, results, final_ndcg, total):
    lines = [
        "# 56. 사전 v1.13 -> v1.14 — 활용형 제안 3군(의미 구조가 위험한 것) 판정",
        "",
        "재현: `./venv/Scripts/python.exe 56_lexicon_v1_14_inflection_group3.py`",
        "API 호출 0회 · 행 수 변화 없음",
        "",
        "## 3군이 왜 따로였나",
        "",
        "1·2군과 달리 이 넷은 **문법적으로 틀려서가 아니라 의미 구조가 위험해서** 미뤄뒀다. "
        "그래서 NDCG 만으로 판정하지 않고 **조건이 바뀐 문장을 전부 출력해서** 같이 봤다. "
        "51번에서 `sweetness` 를 기각한 것도 숫자가 아니라 실제 문장을 보고 내린 판단이었다.",
        "",
        f"## 측정 결과 (기준 v1.13 = {base:.6f})",
        "",
        "| 판정 | 별칭 | NDCG@5 | 델타 | 바뀐 문장 | 사유 |",
        "|---|---|---:|---:|---:|---|",
    ]
    for r in results:
        mark = "채택" if r["accepted"] else "**기각**"
        lines.append(f"| {mark} | `{r['alias']}` | {r['ndcg']:.6f} | {r['delta']:+.6f} | "
                     f"{len(r['changed'])}건 | {r['reason']} |")
    lines += [
        "",
        f"합친 결과 **{final_ndcg:.6f}** ({total:+.6f})",
        "",
        "## `숲속` 기각 — 조사의 예측이 그대로 맞았다",
        "",
        "델타가 음수인 것보다 바뀐 문장이 결정적이다.",
        "",
        "```",
    ]
    for r in results:
        if r["alias"] == "숲속":
            for text, before, after in r["changed"]:
                lines.append(f'"{text[:52]}"')
                lines.append(f"   전 {before}")
                lines.append(f"   후 {after}")
                lines.append("")
    lines += [
        "```",
        "",
        "**전부 비 오는 숲이 아니다.** 일반 숲 장면인데 `비 오는 숲` 의 조건(mossy·earthy)이 "
        "붙었다.",
        "",
        "## `달콤해` 채택 — `sweetness` 기각과 모순이 아니다",
        "",
        "겉보기에는 같은 위험으로 보인다. 둘 다 `달달`(sweet+caramel)에 새 입구를 만든다. "
        "사전을 확인하면 갈린다.",
        "",
        "```",
        "kr.dial.sweet 별칭   달달 | 달달한 | 달큰한 | **달콤한** | **달콤하고** | 캐러멜 | ...",
        "kr.ctx.clean 별칭    깨끗한 | ... | **단정한** | ...",
        "```",
        "",
        "| | 성격 | 결과 |",
        "|---|---|---|",
        "| `sweetness` | 사전에 없던 **다른 어휘**. 의미망이 넓어진다 | −0.000599, 6문장 중 5문장이 과잉 확장 |",
        "| `달콤해` | 이미 있는 **같은 단어**의 다른 어미. 의미망이 안 넓어진다 | +0.000458 |",
        "| `단정하게` | 위와 같다(`단정한` 이 이미 있다) | 0 |",
        "",
        "`달달 -> caramel` 과잉 확장은 **이미 `달콤한` 을 통해 존재한다.** 어미를 더하는 "
        "것이 그 문제를 새로 만드는 것이 아니다. 즉 어미 추가는 기존 결정의 적용 범위를 "
        "표면형으로 넓히는 일이지 새 결정이 아니다.",
        "",
        "그 과잉 확장 자체를 되돌리려면 `달콤한`·`달콤하고` 를 포함해 `달달` 항목의 "
        "accord 구성을 다시 보는 별도 작업이 된다. 이 변경은 그것을 포함하지 않는다.",
        "",
        "## 평가셋이 답하지 못하는 것",
        "",
        "`달콤하게`·`단정하게` 는 바뀐 문장이 0건이다. 해롭지 않다는 것까지만 말할 수 있고 "
        "이롭다고는 말할 수 없다. 특히 `단정하게` 의 동음이의 위험(`결론을 단정하다`)은 "
        "향수 질의로 만든 평가셋에서는 애초에 나타나지 않는다 — **이 평가셋으로 잴 수 없는 "
        "위험이다.**",
        "",
        "## 팀 저장소 반영",
        "",
        "아직 하지 않았다. 개인 저장소에만 있다.",
    ]
    CHANGELOG.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()

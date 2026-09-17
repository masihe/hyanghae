"""칸 배정 결함을 고쳤을 때 무엇이 달라지는지 잰다. 합성 600 과 설문 155 양쪽에서.

    ./venv/Scripts/python.exe 67_field_assignment_defects.py

GMS 호출 0회. 저장된 ①단계 출력을 쓴다. 팀 저장소를 수정하지 않는다.

왜 재는가
----------
14번이 결함 둘을 찾았고 우선순위 1번으로 지정했다.

    결함1  sweet 이 additional_requirements 로 오면 버려진다          실측 8회
    결함2  ①단계가 부정을 잡는데 avoid 가 아닌 칸에 넣는다              부정의 53%

다시 세어 보니 **14번이 못 본 역방향 결함이 훨씬 크다.**

                                              합성 600          설문 155
    결함1  additional_requirements 의 accord   10회 ·  1.7%     2회 ·  1.3%
    역방향 scent_preference 의 비-accord      256회 · 31.8%    29회 · 14.2%   <- 19배
    결함2  additional_requirements 의 부정     88회 · 14.3%    64회 · 28.4%

`scent_preference` 는 `_normalize_accord` 만 타는데 그 함수가 정확 일치·소문자화·복수형
제거·`e->y` 추측만 한다. 들어온 것의 상당수가 accord 이름이 아니라 **노트 이름이거나
근접 형용사** 라서 통째로 버려진다.

    herb 14 · spicy 14      accord 에 `herbal` · `spice` 가 있다   문자열 규칙으로 풀린다
    Mint 11 · lemon 8       **노트 이름이다**                      노트 브리지로 풀린다
    flower 18 · clean 11    어간이 다르거나 accord 에 없다          의미 판정이 필요하다

무엇을 재는가
--------------
    A  현행
    B  결함1 — additional_requirements 도 `_normalize_accord` 를 태운다
    C  역방향 — `_normalize_accord` 의 문자열 규칙을 넓힌다 (`y->e`, `+al`, `+ic`)
    D1 역방향 — 노트 브리지 경유. 노트당 **확률 최상위 1개** accord
    D2 역방향 — 노트 브리지 경유. **p >= 0.5** 인 accord 전부
    D3 역방향 — 노트 브리지 경유. **p >= 0.5 그리고 lift >= 1.4** 인 accord 전부
    D4 역방향 — 노트 브리지 경유. D3 에 노트당 최상위 1개를 lift 와 무관하게 더한다
    E  결함2 — additional_requirements 의 부정 문구를 건초더미에서 뺀다
    F  B + C + D1 + E

**노트 브리지 규칙을 하나로 정하지 않는다.** 노트 하나가 여러 accord 에 붙어 있고
(`Absinthe -> aromatic 0.91 · woody 0.69 · fresh spicy 0.49`), 어느 것을 쓸지는
결정 사항이지 구현 편의로 정할 것이 아니다. 넷 다 싣는다.

**D2 는 `p` 만 보기 때문에 기저율이 섞인다.** `woody` 는 전체 향수의 61.7% 가 갖고
있어 어떤 노트든 `p >= 0.5` 를 넘긴다. D2 가 top1 위에 더 얹는 조건을 합성 600 의
발화 횟수로 가중하면 **56.9% 가 lift < 1.4** 이고, `peony -> woody` 는 lift 0.87 로
**그 노트가 있을 때 오히려 덜 나온다.** D3·D4 는 그 문턱을 넘긴 것만 쓴다.

**D 는 N2 와 얽힌다.** N2 가 단독 매핑을 금지했고 N10 이 직역에만 예외를 뒀다.
노트 경유가 그 경계에 어떻게 서는지는 이 측정이 답하지 않는다.

출력 없음. 표준출력에만 쓴다.
"""
import collections
import importlib.util
import json
import re
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "C:/Users/SSAFY/Desktop/S15P21E203/ai")
import nlr_engine  # noqa: E402

SYNTH = ("합성 600", "analysis_outputs/34_evalset_stage1_checkpoint.csv", "sentence")
SURVEY = ("설문 143", "analysis_outputs/37_survey_stage1_checkpoint.csv", "query_text")

# [판정] 설문 체크포인트 155행 중 12행은 향수 요청이 아니라 동의 표현이다 — `네` · `넵` ·
# `예` · `넴` · `넵 알겠습니다`. 설문의 다른 문항에 대한 답으로 보인다. 채점 대상이 아니므로
# 측정에서 뺀다. **원본 CSV 는 건드리지 않고 읽는 쪽에서 거른다.** 판정이 뒤집힐 수 있다.
#
# 행운의 편지 1건은 **남긴다.** `spec.md` §5.3 이 *"향과 무관한 입력은 조건이 하나도 안
# 잡히므로 감지된다"* 는 정책의 시험 사례로 쓰고 있다. 빼면 그 기능을 검사할 데이터가 없다.
# 향 정보가 없는 요청 9건(`나한테 어울리는 향수 찾아줘` 등)도 남긴다. 실사용자의 진짜
# 요청이고, 못 푸는 것은 시스템의 한계지 데이터의 결함이 아니다.
#
# 같은 규칙이 72번에도 있다. 한쪽만 고치지 말 것. 근거는 측정 기록 19번.
SURVEY_NOT_A_QUERY = re.compile(r"^(네|넵|넴|예)\s*[.!]?$|^넵\s*알겠습니다\.?$")
ANSWER_KEY = "analysis_outputs/32_evalset_answer_key.csv"
LEXICON = "data/scent_knowledge/domain_lexicon_v1_14.csv"
BRIDGE = "analysis_outputs/10_note_accord_bridge.csv"
LIFT_MIN = 1.4  # N4 통제군이 정한 문턱. 무작위 집단은 배수 1.4 를 넘지 못했다

NEG = re.compile(r"싫|말고|빼|않았으면|없었으면|피하|제외|아닌|덜|지 않|안 ")


def wide_normalize(index, raw):
    """`_normalize_accord` 에 문자열 규칙을 더한다. str 또는 None.

    원본이 시도하는 것 — 정확 일치 · 소문자화 · 복수형 제거 · `e` 떼고 `y` 붙이기.
    여기서 더하는 것 — `y` 를 `e` 로 · `al` 붙이기 · `ic` 붙이기.

        spicy -> spice   (원본은 y 를 떼지 않는다)
        herb  -> herbal  (원본은 herby 만 시도한다)

    깨질 수 있는 곳 — 규칙이 우연히 다른 accord 를 만들 수 있다. 예를 들어 `sour` 에
    `al` 을 붙이면 없는 단어지만, 짧은 입력에서는 충돌이 날 수 있다.
    """
    got = nlr_engine._normalize_accord(index, raw)
    if got:
        return got
    x = re.sub(r"\s+", " ", str(raw).strip().lower())
    cands = [x.rstrip("s"), x + "al", x + "ic"]
    if x.endswith("y"):
        cands += [x[:-1], x[:-1] + "e"]
    for c in cands:
        if c in index["aidx"]:
            return c
    return None


def load_bridge(index, rule):
    """노트 -> accord 표. dict[str, set[str]].

    rule : "top1"      노트당 확률 최상위 1개
           "p50"       p_accord_given_note >= 0.5 인 것 전부
           "gate"      p >= 0.5 **그리고** lift >= LIFT_MIN 인 것 전부
           "top1gate"  gate 에 노트당 최상위 1개를 lift 와 무관하게 더한다

    `gate` 는 `top1` 을 포함하지 않는다. 최상위 accord 의 lift 가 문턱 아래인 노트가
    771개 중 85개 있다 (`fig` 의 top1 `woody` 는 lift 1.4 미만이라 떨어진다).
    `top1gate` 는 그 85개에서 top1 을 되살린다. 둘의 차이를 재려고 나눠 뒀다.
    """
    b = pd.read_csv(BRIDGE)
    b = b[b["accord"].isin(index["aidx"])]
    out = {}

    def add(records):
        for r in records:
            out.setdefault(str(r["note"]).strip().lower(), set()).add(r["accord"])

    best = b.sort_values("p_accord_given_note", ascending=False).groupby("note").head(1)
    if rule == "top1":
        add(best.to_dict("records"))
    elif rule == "p50":
        add(b[b["p_accord_given_note"] >= 0.5].to_dict("records"))
    else:
        add(b[(b["p_accord_given_note"] >= 0.5) & (b["lift"] >= LIFT_MIN)].to_dict("records"))
        if rule == "top1gate":
            add(best.to_dict("records"))
    return out


def status_of(found):
    if found["stage"] == "NO_CONDITION":
        return "NO_CONDITION"
    if not len(found["rows"]):
        return "NO_RESULT"
    if found["stage"] == "AND":
        return "OK"
    return "OK_RELAXED"


def load(path, col):
    """체크포인트 CSV 를 (문장, ①단계 dict, 향수 id) 목록으로 읽는다.

    향수 요청이 아닌 응답은 뺀다 (`SURVEY_NOT_A_QUERY`). 몇 건을 뺐는지 찍는다 —
    조용히 줄이면 뒤에 나오는 분모가 왜 달라졌는지 알 수 없다.
    """
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
        print(f"  {path} — 원본 {len(d)}행 중 향수 요청이 아닌 {dropped}행 제외 "
              f"→ {len(out)}행으로 잰다 (측정 기록 19번)")
    return out


def run(index, rows, variant, bridges, ndcg41=None, key=None):
    """한 변형을 돌린다. dict."""
    wide = variant in ("C", "F")
    fix1 = variant in ("B", "F")
    fix2 = variant in ("E", "F")
    bridge = bridges.get({"D1": "top1", "F": "top1", "D2": "p50",
                          "D3": "gate", "D4": "top1gate"}.get(variant))

    ndcgs, ncond, nonzero, avoid_hit = [], [], 0, 0
    statuses = collections.Counter()
    for text, o, pid in rows:
        adds = [str(v) for v in ((o or {}).get("additional_requirements") or [])]
        if fix2:
            adds = [a for a in adds if not NEG.search(a)]
        hay = " ".join([text] + adds)
        core = nlr_engine._extract(index, hay)[0]

        norm = (lambda s: wide_normalize(index, s)) if wide else (
            lambda s: nlr_engine._normalize_accord(index, s))

        for raw in ((o or {}).get("scent_preference") or []):
            a = norm(raw)
            if a:
                core.add(a)
            elif bridge is not None:
                core |= bridge.get(str(raw).strip().lower(), set())
        if fix1:
            for raw in adds:
                a = norm(raw)
                if a:
                    core.add(a)

        avoid = set()
        for raw in ((o or {}).get("avoid") or []):
            a = norm(raw)
            if a:
                avoid.add(a)
        avoid_hit += bool(avoid)

        core = sorted(set(core) - avoid)
        ncond.append(len(core))
        nonzero += bool(core)
        found = nlr_engine.search(index, core, avoid)
        statuses[status_of(found)] += 1
        if key is not None and pid is not None:
            C = [a for a in str(key.loc[pid, "C"]).split("|") if a in index["aidx"]]
            if C:
                cols = [index["aidx"][a] for a in C]
                ndcgs.append(ndcg41.ndcg_at_k(
                    [int(index["has"][r, cols].sum()) for r in found["rows"]], len(C)))
    return {"nonzero": nonzero, "cond": float(np.mean(ncond)), "avoid": avoid_hit,
            "ndcg": float(np.mean(ndcgs)) if ndcgs else None, "status": statuses}


def main():
    spec = importlib.util.spec_from_file_location("ndcg41", "41_lexicon_ndcg.py")
    ndcg41 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ndcg41)
    key = pd.read_csv(ANSWER_KEY).set_index("perfume_id")
    index = nlr_engine.load_index(lexicon_csv=LEXICON)
    bridges = {r: load_bridge(index, r) for r in ("top1", "p50", "gate", "top1gate")}
    print("노트 브리지  " + " · ".join(
        f"{r} {len(v)}개 노트 · accord/노트 {sum(len(s) for s in v.values())/len(v):.2f}"
        for r, v in bridges.items()) + "\n")

    VARIANTS = [
        ("A 현행", "—"),
        ("B 결함1", "additional_requirements 도 accord 로 해석"),
        ("C 규칙확장", "_normalize_accord 에 y->e · +al · +ic"),
        ("D1 노트top1", "노트 브리지 · 확률 최상위 1개"),
        ("D2 노트p50", "노트 브리지 · p >= 0.5 전부"),
        ("D3 p50+lift", f"노트 브리지 · p >= 0.5 그리고 lift >= {LIFT_MIN}"),
        ("D4 top1+lift", "노트 브리지 · D3 에 노트당 top1 을 무조건 더함"),
        ("E 결함2", "부정 문구를 건초더미에서 뺀다"),
        ("F 전부", "B + C + D1 + E"),
    ]
    order = ["OK", "OK_RELAXED", "NO_CONDITION", "NO_RESULT"]

    for name, path, col in (SYNTH, SURVEY):
        rows = load(path, col)
        n = len(rows)
        has_key = rows[0][2] is not None
        print("=" * 96)
        print(f"[{name}] {n}건" + ("" if has_key else "  — 정답 라벨이 없어 NDCG 는 못 잰다"))
        print("=" * 96)
        base = None
        print(f"    {'변형':14s} {'조건추출':>12s} {'평균조건':>8s} {'회피':>5s} "
              f"{'NDCG@5':>10s} {'vs A':>11s}   설명")
        for label, desc in VARIANTS:
            v = label.split()[0]
            r = run(index, rows, v, bridges,
                    ndcg41 if has_key else None, key if has_key else None)
            if base is None:
                base = r
            nd = f"{r['ndcg']:.6f}" if r["ndcg"] is not None else "—"
            dl = (f"{r['ndcg']-base['ndcg']:+.6f}" if r["ndcg"] is not None else "—")
            print(f"    {label:14s} {r['nonzero']:>4d}/{n} {r['nonzero']/n:>6.1%} "
                  f"{r['cond']:>8.2f} {r['avoid']:>5d} {nd:>10s} {dl:>11s}   {desc}")
            if v == "A":
                base_status = r["status"]
            r["_label"] = label
            VARIANTS[[x[0] for x in VARIANTS].index(label)] = (label, desc, r)
        print()
        print(f"    status 분포")
        print(f"    {'변형':14s} " + " ".join(f"{s:>13s}" for s in order))
        for item in VARIANTS:
            label, _, r = item
            if label.startswith("A"):
                print(f"    {label:14s} " + " ".join(f"{r['status'][s]:>13d}" for s in order))
            else:
                print(f"    {label:14s} " + " ".join(
                    f"{r['status'][s]:>6d}({r['status'][s]-base_status[s]:+5d})" for s in order))
        print()
        VARIANTS = [(a, b) for a, b, *_ in VARIANTS]


if __name__ == "__main__":
    main()

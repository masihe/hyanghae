"""임베딩 모델이 사전 밖 표현을 받아낼 수 있는지 잰다.

    ./venv/Scripts/python.exe 63_embedding_estimator.py

API 호출 0회(GMS). 모델 가중치는 허깅페이스에서 받는다. 팀 저장소를 수정하지 않는다.

왜 형태소 분석기와 같은 표에 못 놓는가
----------------------------------------
60~62번이 잰 분석기는 **사전 41개 표현 안에서** 표면형을 맞추는 방식을 바꾼다.
임베딩이 노리는 것은 그 바깥이다 — 14번 감사가 찾은 **미매칭 고유 표현 1,049개**다.

    은은한 꽃향 · 부드러운 꽃향     floral 이 있는데 `꽃향` 항목이 없다
    따뜻한 향신료 느낌              warm spicy 가 있는데 `향신료` 항목이 없다
    보송한 분냄새 (4회)             `분내` 항목이 있는데 `분냄새` 를 못 잡는다

그래서 "분석기 대신 임베딩" 이 아니라 **"사전이 못 받은 것을 임베딩이 받아내는가"** 를 잰다.
`spec.md` 의 ⑤단계, `recommend(..., estimator=)` 자리에 들어갈 물건이다.

두 설계를 나눠 재는 이유 — accord 에 한국어 설명이 없다
---------------------------------------------------------
`accord_dictionary.csv` 는 영어 이름과 통계뿐이고 엔진의 `KOREAN_ACCORD` 는 음차 16개다.
한국어 표현을 accord 에 직접 붙이려면 두 언어가 같은 공간에 있어야 한다.

    설계 1  미매칭 표현 -> 92개 accord(영어) 직접     **교차언어 모델만 가능**
    설계 2  미매칭 표현 -> 사전 41개 표현 중 최근접   양쪽이 한국어라 전 모델 가능
            -> 그 표현의 core accord 를 쓴다

설계 2 가 전 모델 공통 비교이고, 설계 1 은 교차언어 모델에만 추가로 잰다.

문턱을 고르지 않는다
---------------------
유사도 문턱은 튜닝 손잡이다. 모델마다 코사인 분포가 달라 하나로 못 맞추고, 이 평가셋에서
제일 좋은 값을 고르면 평가셋에 맞춘 것이 된다(N11·N12 가 계수를 튜닝하지 않은 것과 같은
이유). **여러 문턱의 곡선을 그대로 싣는다.**

기준선
-------
`understand()` 를 그대로 부른 것이 지금 프로덕션이다. 60~62번의 A(부분문자열)와 같은
값(525/600 · NDCG 0.471540)이 나와야 한다. 안 나오면 비교가 성립하지 않으므로 먼저 찍는다.

출력 없음. 표준출력에만 쓴다.
"""
import collections
import gc
import importlib.util
import json
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, "C:/Users/SSAFY/Desktop/S15P21E203/ai")
import nlr_engine  # noqa: E402

CHECKPOINT = "analysis_outputs/34_evalset_stage1_checkpoint.csv"
ANSWER_KEY = "analysis_outputs/32_evalset_answer_key.csv"
LEXICON = "data/scent_knowledge/domain_lexicon_v1_14.csv"

THRESHOLDS = [0.40, 0.50, 0.60, 0.70, 0.80]

# (짧은 이름, 허깅페이스 저장소, 종류, e5 계열인가)
MODELS = [
    ("ko-sroberta",   "jhgan/ko-sroberta-multitask",                                "한국어", False),
    ("kr-sbert",      "snunlp/KR-SBERT-V40K-klueNLI-augSTS",                        "한국어", False),
    ("mling-MiniLM",  "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2", "교차언어", False),
    ("mling-e5-base", "intfloat/multilingual-e5-base",                              "교차언어", True),
]


def load_queries():
    """(문장, ①단계 dict, 정답 향수 id) 목록. list[tuple]."""
    ck = pd.read_csv(CHECKPOINT)
    out = []
    for r in ck.to_dict("records"):
        try:
            o = json.loads(r["raw_response"])
        except Exception:
            o = None
        out.append((str(r["sentence"]), o, int(r["perfume_id"])))
    return out


def core_of_expression(index, expression, haystack):
    """사전 표현 하나가 주는 core accord. set[str].

    `required == core` 만 쓴다 — `optional` 로 강등된 행은 판정 이력이 있다(N5).
    `match_condition` 도 엔진과 같게 적용한다. 임베딩이 표현을 바꿔치기해도 문맥 조건은
    그대로 지켜야 엔진의 의미와 어긋나지 않는다.
    """
    out = set()
    for row in index["lexicon_by_expression"].get(expression, []):
        cond = row["match_condition"]
        if cond.startswith("query_contains:"):
            toks = [t for t in cond.split(":", 1)[1].split(",") if t]
            if not any(t in haystack for t in toks):
                continue
        if row["required"] == "core" and row["candidate_name"] in index["aidx"]:
            out.add(row["candidate_name"])
    return out


def prepare(index, queries):
    """문장마다 기준선 조건과 미매칭 표현을 미리 뽑는다. list[dict].

    모델마다 다시 계산할 필요가 없는 부분이다. `understand()` 를 그대로 쓰므로
    이 결과가 지금 프로덕션의 동작이다.
    """
    out = []
    for text, structured, pid in queries:
        u = nlr_engine.understand(index, text, structured)
        parts = [text]
        if structured:
            parts += [str(v) for v in (structured.get("additional_requirements") or [])]
        out.append({
            "core": set(u["core"]),
            "avoid": set(u["avoid"]),
            "unmatched": [x["expression"] for x in u["unmatched"]],
            "haystack": " ".join(parts),
            "pid": pid,
        })
    return out


def status_of(found):
    """`search()` 결과를 `recommend()` 와 같은 status 로 접는다. str."""
    if found["stage"] == "NO_CONDITION":
        return "NO_CONDITION"
    if not len(found["rows"]):
        return "NO_RESULT"
    if found["stage"] == "AND":
        return "OK"
    return "OK_RELAXED"


def evaluate(index, prepared, key, ndcg41, extra_core):
    """조건 집합을 받아 지표를 낸다. dict.

    extra_core : dict[int, set]   문장 번호 -> 임베딩이 더한 accord. 비면 기준선이다.
    """
    ndcgs, ncond, nonzero = [], [], 0
    statuses = collections.Counter()
    for i, p in enumerate(prepared):
        core = sorted((p["core"] | extra_core.get(i, set())) - p["avoid"])
        ncond.append(len(core))
        nonzero += bool(core)
        found = nlr_engine.search(index, core, p["avoid"])
        statuses[status_of(found)] += 1
        C = [a for a in str(key.loc[p["pid"], "C"]).split("|") if a in index["aidx"]]
        if not C:
            continue
        cols = [index["aidx"][a] for a in C]
        ndcgs.append(ndcg41.ndcg_at_k(
            [int(index["has"][r, cols].sum()) for r in found["rows"]], len(C)))
    return {"nonzero": nonzero, "cond": float(np.mean(ncond)),
            "ndcg": float(np.mean(ndcgs)), "status": statuses}


def encode(model, texts, e5):
    """문장 목록을 정규화된 벡터로. np.ndarray (n, d).

    e5 계열은 접두사를 요구한다. 안 붙이면 성능이 떨어진다 — 대칭 유사도에는
    양쪽 모두 `query: ` 를 쓴다.
    """
    if e5:
        texts = [f"query: {t}" for t in texts]
    return model.encode(texts, normalize_embeddings=True, batch_size=64,
                        show_progress_bar=False, convert_to_numpy=True)


def probe(short):
    """모델 하나의 자원과 유사도 분포. 표준출력에 JSON 한 줄. 별도 프로세스로 돈다.

    한 프로세스에서 모델을 차례로 올리면 앞 모델이 반납한 힙을 뒤 모델이 재사용해
    증가분이 실제보다 작게 나온다. 62번에서 같은 이유로 프로세스를 나눴다.
    가중치가 이미 캐시에 있어야 적재 시간에서 다운로드가 빠진다.
    """
    import psutil
    from sentence_transformers import SentenceTransformer
    _, repo, kind, e5 = {m[0]: m for m in MODELS}[short]
    proc = psutil.Process()
    index = nlr_engine.load_index(lexicon_csv=LEXICON)
    prepared = prepare(index, load_queries())
    uniq = sorted({e for p in prepared for e in p["unmatched"]})
    lex_expressions = sorted(index["lexicon_by_expression"].keys())

    base = proc.memory_info().rss
    t = time.time()
    model = SentenceTransformer(repo, device="cpu")
    load_sec = time.time() - t
    t = time.time()
    v = encode(model, uniq, e5)
    enc_ms = (time.time() - t) / len(uniq) * 1000
    v_lex = encode(model, lex_expressions, e5)
    after = proc.memory_info().rss

    qs = (5, 25, 50, 75, 95)
    out = {"model": short, "base": base, "after": after, "load_sec": load_sec,
           "enc_ms": enc_ms,
           "lex_p": [float(np.percentile((v @ v_lex.T).max(axis=1), q)) for q in qs]}
    if kind == "교차언어":
        v_acc = encode(model, index["accords"], e5)
        out["acc_p"] = [float(np.percentile((v @ v_acc.T).max(axis=1), q)) for q in qs]
    print(json.dumps(out))


def main():
    import psutil
    from sentence_transformers import SentenceTransformer

    spec = importlib.util.spec_from_file_location("ndcg41", "41_lexicon_ndcg.py")
    ndcg41 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ndcg41)
    key = pd.read_csv(ANSWER_KEY).set_index("perfume_id")

    index = nlr_engine.load_index(lexicon_csv=LEXICON)
    queries = load_queries()
    prepared = prepare(index, queries)

    # 사전의 고유 표현과 accord 목록
    lex_expressions = sorted(index["lexicon_by_expression"].keys())
    accords = index["accords"]

    # 미매칭 표현을 모아 중복을 없앤다. 모델마다 이것만 임베딩하면 된다
    uniq = sorted({e for p in prepared for e in p["unmatched"]})
    total_unmatched = sum(len(p["unmatched"]) for p in prepared)

    print(f"문장 {len(queries)}건 · 사전 표현 {len(lex_expressions)}개 · accord {len(accords)}개")
    print(f"미매칭 표현 {total_unmatched:,}회 · 고유 {len(uniq):,}개\n")

    base = evaluate(index, prepared, key, ndcg41, {})
    print("[0] 기준선 — `understand()` 그대로. 지금 프로덕션이다")
    print(f"    조건추출 {base['nonzero']}/{len(queries)} "
          f"({base['nonzero']/len(queries):.1%}) · 평균조건 {base['cond']:.2f} · "
          f"NDCG@5 {base['ndcg']:.6f}")
    print(f"    60~62번의 A(부분문자열)와 같아야 한다 — 525/600 · 0.471540")
    print(f"    status {dict(base['status'])}\n")

    proc = psutil.Process()
    rows = []
    for short, repo, kind, e5 in MODELS:
        rss0 = proc.memory_info().rss
        t = time.time()
        try:
            model = SentenceTransformer(repo, device="cpu")
        except Exception as exc:
            print(f"  {short}: 적재 실패 {type(exc).__name__} {exc}")
            continue
        load_sec = time.time() - t
        rss1 = proc.memory_info().rss

        t = time.time()
        v_uniq = encode(model, uniq, e5)
        enc_sec = time.time() - t
        v_lex = encode(model, lex_expressions, e5)
        v_acc = encode(model, accords, e5) if kind == "교차언어" else None

        eidx = {e: i for i, e in enumerate(uniq)}
        sim_lex = v_uniq @ v_lex.T                      # (미매칭, 사전표현)
        best_lex = sim_lex.argmax(axis=1)
        top_lex = sim_lex.max(axis=1)
        if v_acc is not None:
            sim_acc = v_uniq @ v_acc.T
            best_acc = sim_acc.argmax(axis=1)
            top_acc = sim_acc.max(axis=1)

        for design, ok in (("설계2 사전표현", True),
                           ("설계1 accord직접", v_acc is not None)):
            if not ok:
                continue
            for th in THRESHOLDS:
                extra, fired = {}, 0
                for i, p in enumerate(prepared):
                    add = set()
                    for e in p["unmatched"]:
                        j = eidx[e]
                        if design.startswith("설계2"):
                            if top_lex[j] >= th:
                                add |= core_of_expression(
                                    index, lex_expressions[best_lex[j]], p["haystack"])
                                fired += 1
                        else:
                            if top_acc[j] >= th:
                                add.add(accords[best_acc[j]])
                                fired += 1
                    if add:
                        extra[i] = add
                r = evaluate(index, prepared, key, ndcg41, extra)
                r.update({"model": short, "kind": kind, "design": design,
                          "th": th, "fired": fired, "load_sec": load_sec,
                          "enc_ms": enc_sec / len(uniq) * 1000,
                          "rss_mb": (rss1 - rss0) / 1024 / 1024})
                rows.append(r)

        del model
        gc.collect()

    # ------------------------------------------------------------------
    print("=" * 96)
    print("[1] 설계 2 — 미매칭 표현을 사전 41개 표현 중 최근접으로 보낸다 (전 모델)")
    print("=" * 96)
    hdr = (f"    {'모델':14s} {'종류':>6s} {'문턱':>5s} {'발동':>7s} "
           f"{'조건추출':>11s} {'평균조건':>8s} {'NDCG@5':>10s} {'vs 기준선':>11s}")
    print(hdr)
    for r in [x for x in rows if x["design"].startswith("설계2")]:
        print(f"    {r['model']:14s} {r['kind']:>6s} {r['th']:>5.2f} {r['fired']:>7,d} "
              f"{r['nonzero']:>4d}/{len(queries)} {r['nonzero']/len(queries):>5.1%} "
              f"{r['cond']:>8.2f} {r['ndcg']:>10.6f} {r['ndcg']-base['ndcg']:>+11.6f}")

    xling = [x for x in rows if x["design"].startswith("설계1")]
    if xling:
        print()
        print("=" * 96)
        print("[2] 설계 1 — 미매칭 표현을 92개 accord(영어)에 직접 붙인다 (교차언어만)")
        print("=" * 96)
        print(hdr)
        for r in xling:
            print(f"    {r['model']:14s} {r['kind']:>6s} {r['th']:>5.2f} {r['fired']:>7,d} "
                  f"{r['nonzero']:>4d}/{len(queries)} {r['nonzero']/len(queries):>5.1%} "
                  f"{r['cond']:>8.2f} {r['ndcg']:>10.6f} {r['ndcg']-base['ndcg']:>+11.6f}")

    print()
    print("=" * 96)
    print("[3] status 분포 — 각 모델의 최고 NDCG 지점만")
    print("=" * 96)
    b = base["status"]
    order = ["OK", "OK_RELAXED", "NO_CONDITION", "NO_RESULT"]
    print(f"    {'모델 · 설계 · 문턱':34s} " + " ".join(f"{s:>13s}" for s in order))
    print(f"    {'기준선':34s} " + " ".join(f"{b[s]:>13d}" for s in order))
    seen = set()
    for r in sorted(rows, key=lambda x: -x["ndcg"]):
        tag = (r["model"], r["design"])
        if tag in seen:
            continue
        seen.add(tag)
        label = f"{r['model']} · {r['design']} · {r['th']:.2f}"
        cells = " ".join(f"{r['status'][s]:>6d}({r['status'][s]-b[s]:+5d})" for s in order)
        print(f"    {label:34s} " + cells)

    print()
    print("=" * 96)
    print("[4] 자원 — 배포 비용")
    print("=" * 96)
    print(f"    {'모델':14s} {'적재':>9s} {'표현 1개 인코딩':>16s} {'메모리':>10s}")
    for short, _, _, _ in MODELS:
        r = next((x for x in rows if x["model"] == short), None)
        if r:
            print(f"    {short:14s} {r['load_sec']:>8.2f}초 {r['enc_ms']:>15.2f}ms "
                  f"{r['rss_mb']:>+9.0f}MB")


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--probe":
        probe(sys.argv[2])
    else:
        main()

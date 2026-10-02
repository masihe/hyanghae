"""①단계(구조화)의 성별·계절·낮밤만 LLM 대신 규칙·임베딩으로 채워 391 엔진에 넣고 비교한다.

41번(문장 통째로 임베딩)의 다음 질문이다 (2026-09-29, 사용자 결정으로 범위를 좁혔다).
391 엔진(추정 끔)·합성 600 에서 ①단계 칸을 하나씩 비워 보니 LLM 의 이득 0.042 가 전부 context
(성별·계절·낮밤)에서 왔다 — avoid·additional·scent 는 0 포함. 그래서 context 만 바꿔 넣는다.

방식 (모두 context 만 채우고 나머지 칸은 비운다)
    llm    저장된 ①단계 출력의 context (기준)
    rule   팀 기존 규칙 그대로 — 노트북 14 의 GENDER_RULES · parse_gender · parse_existing_rules
           (11_rule_lexicon.csv 전체로 긴 표현부터 겹침 없이 찾는다). 여기서 새로 만들지 않았다
    proto  문장 벡터와 라벨 예시(= 위 규칙의 낱말)의 최대 코사인이 문턱 이상이면 그 라벨. 성별은 최고 1개.
           문턱은 Golden 200 **정답**으로 성별·계절 각각 F1 최대(0.05 격자). 낮밤은 정답이 0개라 계절 문턱
    clf    문장 벡터 -> 라벨별 로지스틱 회귀(class_weight=balanced · 기본 C · 0.5). 학습 = Golden 200 +
           설문 155 의 **LLM 출력**(LLM 흉내). 합성 600 은 전체로 학습한 모델로, 설문 143 은 설문을
           5조각 교차 적합해 판정한다(학습에 쓴 문장을 평가하지 않게)
    none   context 비움

판정 기준 — 측정 전에 고정했다
    관문 1  llm 경로의 확장 NDCG 가 절제 실험의 0.701844 와 같다
    관문 2  none 경로가 0.659341(context 만 뺌)과 같다
    관문 3  rule 의 Golden 200 성별 F1(정답이 있는 문장 한정)이 노트북 14 기록 0.9189 와 같다
    주 지표 확장 NDCG@5 · 합성 600 · llm 대비 짝지은 부트스트랩(87 과 같은 20,000 · seed)
    채점 기준 둘 — llm: "문장이 말했다" = LLM context / union: 모든 방식 중 하나라도 말했다고 본 값.
            노트 조건은 둘 다 LLM structured 그대로다(context 만 바꾼다)
    합성 600 은 평가에만 쓴다. 승패 문턱은 두지 않는다.

사용법 (결과와 해석은 docs/nlr_engineering_notes.md 42번)
    predict   --method ... [--model ...] --out ctx.json     방식별 context 예측 (합성+설문+Golden)
    run       --contexts ctx.json --out res.json            context 만 넣은 structured 로 391 엔진(추정 끔)
    evaluate  --reference res_llm.json --results ... --contexts ...   두 채점 기준 · 설문 일치 · LLM 닮음
    gate-rule                                               관문 3
    latency   --model ...                                   CPU 기준 문장 1개 판정 지연 · 메모리
"""
import argparse
import collections
import importlib.util
import json
import re
import unicodedata
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
DEFAULT_OUTPUTS = HERE / "analysis_outputs"
DEFAULT_GOLDEN = HERE / "evaluation_data" / "stage1" / "13_stage1_golden_set_v1_200.xlsx"
GOLDEN_LLM = "15_llm_stage1_predictions.csv"
RULE_LEXICON = "11_rule_lexicon.csv"
FIELDS = ("gender", "season", "daypart")
LABELS = {"gender": ("male", "female", "neuter"),
          "season": ("spring", "summer", "autumn", "winter"),
          "daypart": ("day", "night")}
EMB_MODELS = {"ko-sroberta": "jhgan/ko-sroberta-multitask", "bge-m3": "BAAI/bge-m3"}
GRID = [round(0.05 * i, 2) for i in range(1, 20)]
CV_FOLDS = 5
CV_SEED = 42

# ── 노트북 14 (14_stage1_extended_rule_evaluation.ipynb) 코드 셀 3·4·5 에서 옮겼다. 고치지 않았다 ──
GENDER_RULES = [
    ("neuter", r"중성적인|유니섹스|남녀\s*공용"),
    ("male", r"남성용|남성|남자용|남자가\s*쓰(?:기|는)\s*좋은|남자"),
    ("female", r"여성용|여성|여자용|여자가\s*쓰(?:기|는)\s*좋은|여자"),
]
# 예시 비교(proto)의 성별 예시 — 위 정규식의 선택지를 풀어 쓴 것이다. 따로 설계하지 않았다
GENDER_EXAMPLES = {
    "neuter": ["중성적인", "유니섹스", "남녀 공용"],
    "male": ["남성용", "남성", "남자용", "남자가 쓰기 좋은", "남자가 쓰는 좋은", "남자"],
    "female": ["여성용", "여성", "여자용", "여자가 쓰기 좋은", "여자가 쓰는 좋은", "여자"],
}


def normalize_text(text):
    """노트북 14 셀 4 그대로."""
    text = unicodedata.normalize("NFKC", str(text)).casefold()
    return re.sub(r"\s+", " ", text).strip()


def spans_overlap(span, occupied):
    """노트북 14 셀 4 그대로."""
    start, end = span
    return any(start < used_end and used_start < end for used_start, used_end in occupied)


def surface_matches(normalized_query, surface):
    """노트북 14 셀 4 그대로."""
    escaped = re.escape(surface)
    if re.search(r"[a-z0-9]", surface):
        pattern = rf"(?<![a-z0-9]){escaped}(?![a-z0-9])"
    else:
        pattern = escaped
    return list(re.finditer(pattern, normalized_query))


def choose_rule(candidates, original_fragment, after_text):
    """노트북 14 셀 4 그대로."""
    by_type = collections.defaultdict(list)
    for candidate in candidates:
        by_type[candidate["feature_type"]].append(candidate)
    if "NOTE" in by_type and re.search(r"^\s*(노트|note)", after_text):
        return by_type["NOTE"][0]
    if "ACCORD" in by_type and re.search(r"^\s*(향|accord)", after_text):
        return by_type["ACCORD"][0]
    if "SEASON" in by_type:
        return by_type["SEASON"][0]
    if "DAYPART" in by_type:
        return by_type["DAYPART"][0]
    if len(by_type) == 1:
        return candidates[0]
    if "NOTE" in by_type and any(character.isupper() for character in original_fragment):
        return by_type["NOTE"][0]
    if "ACCORD" in by_type:
        return by_type["ACCORD"][0]
    return candidates[0]


class RuleParser:
    """노트북 14 의 parse_existing_rules · parse_gender. 사전을 인자로 받게만 바꿨다."""

    def __init__(self, lexicon_csv):
        import pandas as pd
        df = pd.read_csv(lexicon_csv, dtype=str, keep_default_na=False)
        self.rows = df.to_dict("records")
        self.by_surface = collections.defaultdict(list)
        for row in self.rows:
            self.by_surface[row["normalized_form"]].append(row)
        self.sorted_surfaces = sorted(self.by_surface, key=lambda value: (-len(value), value))

    def parse_existing_rules(self, query):
        """노트북 14 셀 4 그대로 (seasons · dayparts 만 쓴다)."""
        normalized_query = normalize_text(query)
        occupied, resolved = [], []
        for surface in self.sorted_surfaces:
            for match in surface_matches(normalized_query, surface):
                if spans_overlap(match.span(), occupied):
                    continue
                original_fragment = str(query)[match.start():match.end()]
                after_text = normalized_query[match.end():match.end() + 12]
                chosen = choose_rule(self.by_surface[surface], original_fragment, after_text)
                resolved.append({"start": match.start(), "chosen": chosen})
                occupied.append(match.span())
        result = {"seasons": [], "dayparts": []}
        key = {"SEASON": "seasons", "DAYPART": "dayparts"}
        for item in sorted(resolved, key=lambda value: value["start"]):
            k = key.get(item["chosen"]["feature_type"])
            if k and item["chosen"]["feature_name"] not in result[k]:
                result[k].append(item["chosen"]["feature_name"])
        return result

    @staticmethod
    def parse_gender(query):
        """노트북 14 셀 5 그대로 (deduplicate_preserving_order 를 풀어 썼다)."""
        normalized_query = normalize_text(query)
        matches = []
        for value, pattern in GENDER_RULES:
            for match in re.finditer(pattern, normalized_query):
                matches.append((match.start(), value))
        seen, out = set(), []
        for _, value in sorted(matches):
            if value not in seen:
                seen.add(value)
                out.append(value)
        return out

    def context(self, query):
        """문장 하나의 context. dict[field, list[str]]."""
        existing = self.parse_existing_rules(query)
        return {"gender": self.parse_gender(query), "season": existing["seasons"],
                "daypart": existing["dayparts"]}

    def examples(self):
        """예시 비교용 라벨 예시. 성별은 정규식 선택지, 계절·낮밤은 사전의 SEASON·DAYPART 표면형."""
        ex = {("gender", k): list(v) for k, v in GENDER_EXAMPLES.items()}
        for row in self.rows:
            field = {"SEASON": "season", "DAYPART": "daypart"}.get(row["feature_type"])
            if field:
                ex.setdefault((field, row["feature_name"]), []).append(row["surface_form"])
        return ex


def load_87():
    """87_embedding_vs_engine.py 를 모듈로 불러온다. module."""
    path = HERE / "87_embedding_vs_engine.py"
    spec = importlib.util.spec_from_file_location("exp87", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def norm_ctx(ctx):
    """context 를 비교 가능한 모양으로. dict[field, sorted list[str]] — 문자열 하나도 한 값으로 본다."""
    out = {}
    ctx = ctx if isinstance(ctx, dict) else {}
    for field in FIELDS:
        raw = ctx.get(field) or []
        raw = [raw] if isinstance(raw, str) else raw
        out[field] = sorted({str(v).strip().lower() for v in raw if str(v).strip()})
    return out


def load_golden(golden_xlsx, outputs_dir):
    """Golden 200 의 문장 · 정답 context · LLM context. list[dict]."""
    import pandas as pd
    gold = pd.read_excel(golden_xlsx, sheet_name="Golden Set", header=4)
    llm = pd.read_csv(Path(outputs_dir) / GOLDEN_LLM)
    llm_ctx = {r.query_id: r.pred_context for r in llm.itertuples()}
    rows = []
    for r in gold.itertuples():
        pred = llm_ctx.get(r.query_id)
        rows.append({"query_id": r.query_id, "sentence": r.query_text,
                     "gold": norm_ctx(json.loads(r.gold_context)),
                     "llm": norm_ctx(json.loads(pred) if isinstance(pred, str) and pred.strip() else {})})
    if len(rows) != 200:
        raise ValueError(f"Golden 이 200 문장이 아니다: {len(rows)}")
    return rows


def eval_sets(x87, outputs_dir, golden_xlsx):
    """(합성+설문 문장, 설문 155 전체 LLM, Golden 200). 설문 155 는 학습용이라 동의 응답까지 포함한다."""
    import csv
    evalq = x87.load_synth(outputs_dir) + x87.load_survey(outputs_dir)
    survey155 = []
    with open(Path(outputs_dir) / x87.SURVEY, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            parsed = json.loads(r["parsed"]) if r["parsed"] else {}
            survey155.append({"query_id": r["query_id"], "sentence": r["query_text"],
                              "llm": norm_ctx((parsed or {}).get("context"))})
    return evalq, survey155, load_golden(golden_xlsx, outputs_dir)


def f1(pairs):
    """[(정답 set, 예측 set)] 의 micro F1 · P · R. (float, float, float)."""
    tp = sum(len(g & p) for g, p in pairs)
    fp = sum(len(p - g) for g, p in pairs)
    fn = sum(len(g - p) for g, p in pairs)
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    return (2 * prec * rec / (prec + rec) if prec + rec else 0.0), prec, rec


def encode(model, texts):
    """정규화된 문장 벡터. np.ndarray."""
    return model.encode(list(texts), batch_size=64, normalize_embeddings=True,
                        convert_to_numpy=True, show_progress_bar=False).astype(np.float32)


def proto_scores(model, texts, examples):
    """문장마다 라벨별 최대 코사인. dict[(field,label), np.ndarray]."""
    v = encode(model, texts)
    out = {}
    for key, ex in examples.items():
        out[key] = (v @ encode(model, ex).T).max(axis=1)
    return out


def proto_decide(scores, i, thresholds):
    """문장 i 의 예시 비교 판정. dict[field, list[str]]."""
    ctx = {f: [] for f in FIELDS}
    g = {lab: scores[("gender", lab)][i] for lab in LABELS["gender"] if ("gender", lab) in scores}
    if g:
        best = max(g, key=g.get)
        if g[best] >= thresholds["gender"]:
            ctx["gender"] = [best]
    for field in ("season", "daypart"):
        t = thresholds[field]
        ctx[field] = sorted(lab for lab in LABELS[field]
                            if (field, lab) in scores and scores[(field, lab)][i] >= t)
    return ctx


def predict(method, model_key, device, outputs_dir, golden_xlsx, out_path):
    """방식 하나의 context 를 합성·설문·Golden 문장마다 예측해 저장한다. None."""
    x87 = load_87()
    evalq, survey155, golden = eval_sets(x87, outputs_dir, golden_xlsx)
    meta = {"method": method, "model": model_key}
    ctx = {}
    if method == "llm":
        for q in evalq:
            ctx[q["query_id"]] = norm_ctx((q["structured"] or {}).get("context"))
        for g in golden:
            ctx[g["query_id"]] = g["llm"]
    elif method == "none":
        for q in evalq + golden:
            ctx[q["query_id"]] = norm_ctx({})
    elif method == "rule":
        parser = RuleParser(Path(outputs_dir) / RULE_LEXICON)
        for q in evalq + golden:
            ctx[q["query_id"]] = norm_ctx(parser.context(q["sentence"]))
    else:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer(EMB_MODELS[model_key], device=device)
        model.max_seq_length = 512
        if method == "proto":
            examples = RuleParser(Path(outputs_dir) / RULE_LEXICON).examples()
            gs = proto_scores(model, [g["sentence"] for g in golden], examples)
            thresholds = {}
            for field in ("gender", "season"):
                best = None
                for t in GRID:
                    th = {"gender": t, "season": t, "daypart": t}
                    pairs = [(set(g["gold"][field]), set(proto_decide(gs, i, th)[field]))
                             for i, g in enumerate(golden)]
                    score = f1(pairs)[0]
                    if best is None or score > best[0]:   # 같으면 낮은 문턱을 먼저 본 것이 남는다
                        best = (score, t)
                thresholds[field] = best[1]
                meta[f"golden_f1_{field}"] = round(best[0], 4)
            thresholds["daypart"] = thresholds["season"]   # Golden 정답에 낮밤이 0개다
            meta["thresholds"] = thresholds
            es = proto_scores(model, [q["sentence"] for q in evalq + golden], examples)
            for i, q in enumerate(evalq + golden):
                ctx[q["query_id"]] = proto_decide(es, i, thresholds)
        else:
            from sklearn.linear_model import LogisticRegression
            from sklearn.model_selection import KFold
            train = golden + survey155
            xt = encode(model, [t["sentence"] for t in train])
            y = {(f, lab): np.array([lab in t["llm"][f] for t in train])
                 for f in FIELDS for lab in LABELS[f]}
            meta["train_positives"] = {f"{f}:{lab}": int(v.sum()) for (f, lab), v in y.items()}

            def fit_predict(rows_train, x_pred):
                pred = {f: [[] for _ in range(len(x_pred))] for f in FIELDS}
                for (f, lab), yy in y.items():
                    yt = yy[rows_train]
                    if yt.sum() == 0 or yt.all():
                        continue                     # 한 가지 값뿐이면 배울 수 없다 (night 0개)
                    clf = LogisticRegression(class_weight="balanced", max_iter=1000)
                    clf.fit(xt[rows_train], yt)
                    for i, p in enumerate(clf.predict_proba(x_pred)[:, 1]):
                        if p >= 0.5:
                            pred[f][i].append(lab)
                return [{f: sorted(pred[f][i]) for f in FIELDS} for i in range(len(x_pred))]

            all_rows = np.arange(len(train))
            synth = [q for q in evalq if q["arm"] != "S"]
            for q, c in zip(synth, fit_predict(all_rows, encode(model, [q["sentence"] for q in synth]))):
                ctx[q["query_id"]] = c
            # 설문 143 은 교차 적합 — 설문 조각 하나를 빼고 학습한 모델로 그 조각을 판정한다
            n_g = len(golden)
            survey_idx = {s["query_id"]: n_g + i for i, s in enumerate(survey155)}
            want = {q["query_id"] for q in evalq if q["arm"] == "S"}
            folds = KFold(CV_FOLDS, shuffle=True, random_state=CV_SEED).split(survey155)
            for _, test in folds:
                test_rows = n_g + test
                keep = np.setdiff1d(all_rows, test_rows)
                preds = fit_predict(keep, xt[test_rows])
                for j, c in zip(test, preds):
                    qid = survey155[j]["query_id"]
                    if qid in want:
                        ctx[qid] = c
            for g in golden:
                ctx[g["query_id"]] = None             # Golden 은 학습에 썼다 — 평가하지 않는다
            missing = [q["query_id"] for q in evalq if q["query_id"] not in ctx]
            if missing:
                raise ValueError(f"예측이 빠진 문장 {len(missing)}: {missing[:5]}")
    meta["contexts"] = ctx
    Path(out_path).write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    counts = collections.Counter(f"{f}:{v}" for q in evalq for f in FIELDS for v in (ctx[q["query_id"]] or {}).get(f, []))
    print(f"{method} {model_key or ''} -> {out_path}")
    print("  합성+설문 예측 분포", dict(sorted(counts.items())))
    for k in ("thresholds", "golden_f1_gender", "golden_f1_season", "train_positives"):
        if k in meta:
            print(f"  {k} {meta[k]}")


def empty_structured(ctx):
    """context 만 채운 ①단계 출력. dict."""
    return {"scent_preference": [], "context": ctx,
            "performance": {"intensity": "", "longevity": ""},
            "avoid": [], "additional_requirements": []}


def run(engine_dir, contexts_path, outputs_dir, golden_xlsx, out_path):
    """context 만 넣은 structured 로 391 엔진(추정 끔)을 돌려 결과를 저장한다. None."""
    x87 = load_87()
    engine = x87.load_engine(engine_dir)
    index = engine.load_index()
    ctx = json.loads(Path(contexts_path).read_text(encoding="utf-8"))["contexts"]
    evalq, _, _ = eval_sets(x87, outputs_dir, golden_xlsx)
    result, status = {}, collections.Counter()
    for q in evalq:
        rec = engine.recommend(index, q["sentence"], structured=empty_structured(ctx[q["query_id"]]),
                               top_k=x87.TOP_K, estimator=None)
        result[q["query_id"]] = {"status": rec["status"], "stage": rec["diagnostics"]["stage"],
                                 "ids": [r["perfume_id"] for r in rec["results"]]}
        status[("합성" if q["arm"] != "S" else "설문", rec["status"])] += 1
    Path(out_path).write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    print(f"{contexts_path} -> {out_path}  {dict(sorted(status.items()))}")


def evaluate(engine_dir, outputs_dir, golden_xlsx, reference, results, contexts):
    """두 채점 기준으로 확장 NDCG · 설문 일치 · LLM 닮음을 출력한다. None.

    results[i] 와 contexts[i] 가 같은 방식이다. union 기준은 contexts 전부의 합집합이다.
    """
    import copy
    x87 = load_87()
    engine = x87.load_engine(engine_dir)
    index = engine.load_index()
    scorer = x87.Scorer(engine, index, x87.load_answer_key(outputs_dir))
    evalq, _, _ = eval_sets(x87, outputs_dir, golden_xlsx)
    synth = [q for q in evalq if q["arm"] != "S"]
    survey = [q for q in evalq if q["arm"] == "S"]
    ctxs = [json.loads(Path(c).read_text(encoding="utf-8")) for c in contexts]
    names = [f"{c['method']}{('-' + c['model']) if c['model'] else ''}" for c in ctxs]
    llm_ctx = {q["query_id"]: norm_ctx((q["structured"] or {}).get("context")) for q in evalq}
    union = {}
    for q in evalq:
        u = {f: set(llm_ctx[q["query_id"]][f]) for f in FIELDS}
        for c in ctxs:
            for f in FIELDS:
                u[f] |= set(c["contexts"][q["query_id"]][f])
        union[q["query_id"]] = {f: sorted(v) for f, v in u.items()}
    bases = {"llm": llm_ctx, "union": union}
    ref = json.loads(Path(reference).read_text(encoding="utf-8"))
    res = [json.loads(Path(r).read_text(encoding="utf-8")) for r in results]

    for basis, bctx in bases.items():
        conds = []
        for q in synth:
            qq = dict(q)
            s = copy.deepcopy(q["structured"]) or {}
            s["context"] = bctx[q["query_id"]]
            qq["structured"] = s
            conds.append(scorer.conditions(qq))
        n_ctx = sum(1 for c in conds for k, _ in c if k in FIELDS)
        print(f"\n## 채점 기준 {basis} — 합성 600 · context 조건 {n_ctx}개 · 조건 수 평균 "
              f"{np.mean([len(c) for c in conds]):.2f}")
        base = [scorer.ndcg(ref[q["query_id"]]["ids"], c) for q, c in zip(synth, conds)]
        print(f"  reference {Path(reference).name}  {np.mean(base):.6f}")
        for name, r in zip(names, res):
            new = [scorer.ndcg(r[q["query_id"]]["ids"], c) for q, c in zip(synth, conds)]
            m, lo, hi = x87.paired_bootstrap(base, new)
            st = collections.Counter(r[q["query_id"]]["status"] for q in synth)
            print(f"  {name:18s} {np.mean(new):.6f}  차이 {m:+.6f} [{lo:+.6f}, {hi:+.6f}]  {dict(st)}")
        print(f"  설문 143 — 추천 5개 중 맞는 개수 (결과 0건은 0개)")
        for f in FIELDS:
            asked = [q for q in survey if bctx[q["query_id"]][f]]
            line = []
            for name, r in [("reference", ref)] + list(zip(names, res)):
                counts = []
                for q in asked:
                    want = bctx[q["query_id"]][f]
                    rows = [scorer.row_of[int(p)] for p in r[q["query_id"]]["ids"]]
                    table = index["context"][f]
                    want_d = [{"neuter": "unisex"}.get(v, v) for v in want]
                    counts.append(sum(any(bool(table[v][row]) for v in want_d if v in table) for row in rows))
                line.append(f"{name} {np.mean(counts):.2f}" if counts else f"{name} -")
            print(f"    {f} ({len(asked)}문장)  " + " · ".join(line))

    print("\n## LLM 을 얼마나 닮았나 — 합성 600 · 라벨 단위 micro F1 (P / R) · 문장 단위 context 완전 일치")
    for name, c in zip(names, ctxs):
        parts = []
        for f in FIELDS:
            pairs = [(set(llm_ctx[q["query_id"]][f]), set(c["contexts"][q["query_id"]][f])) for q in synth]
            ff, p, rr = f1(pairs)
            parts.append(f"{f} {ff:.3f} ({p:.2f}/{rr:.2f})")
        exact = np.mean([c["contexts"][q["query_id"]] == llm_ctx[q["query_id"]] for q in synth])
        print(f"  {name:18s} " + " · ".join(parts) + f" · 완전 일치 {exact:.1%}")


def gate_rule(outputs_dir, golden_xlsx):
    """관문 3 — 규칙의 Golden 200 성별 F1(정답이 있는 문장 한정). 노트북 14 기록 0.9189. None."""
    parser = RuleParser(Path(outputs_dir) / RULE_LEXICON)
    golden = load_golden(golden_xlsx, outputs_dir)
    for f in FIELDS:
        pairs = [(set(g["gold"][f]), set(norm_ctx(parser.context(g["sentence"]))[f]))
                 for g in golden if g["gold"][f]]
        ff, p, r = f1(pairs) if pairs else (float("nan"), 0, 0)
        print(f"rule · Golden 정답이 있는 문장 {len(pairs)} · {f} F1 {ff:.4f} (P {p:.3f} / R {r:.3f})")


def latency(model_key, outputs_dir, n=50):
    """CPU 기준 문장 1개 context 판정(인코딩) 지연과 메모리. 모델마다 프로세스를 따로 띄운다. None."""
    import time
    import psutil
    import torch  # noqa: F401
    from sentence_transformers import SentenceTransformer
    proc = psutil.Process()
    rss_t = proc.memory_info().rss / 2**20
    model = SentenceTransformer(EMB_MODELS[model_key], device="cpu")
    model.max_seq_length = 512
    x87 = load_87()
    queries = x87.load_survey(outputs_dir)[:n]
    encode(model, ["워밍업"])
    times = []
    for q in queries:
        t = time.perf_counter()
        encode(model, [q["sentence"]])
        times.append((time.perf_counter() - t) * 1000)
    rss = proc.memory_info().rss / 2**20
    print(f"{model_key} · torch 적재 후 {rss_t:.0f}MB -> 최종 {rss:.0f}MB (+{rss - rss_t:.0f}) · "
          f"문장 {n}개 중앙 {np.median(times):.1f}ms · p95 {np.percentile(times, 95):.1f}ms")


def main(argv=None):
    """명령행 진입점."""
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--outputs-dir", default=str(DEFAULT_OUTPUTS))
    p.add_argument("--golden-xlsx", default=str(DEFAULT_GOLDEN))
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("predict")
    a.add_argument("--method", required=True, choices=["llm", "rule", "proto", "clf", "none"])
    a.add_argument("--model", choices=sorted(EMB_MODELS))
    a.add_argument("--device", default="cpu")
    a.add_argument("--out", required=True)
    b = sub.add_parser("run")
    b.add_argument("--engine-dir", required=True)
    b.add_argument("--contexts", required=True)
    b.add_argument("--out", required=True)
    c = sub.add_parser("evaluate")
    c.add_argument("--engine-dir", required=True)
    c.add_argument("--reference", required=True)
    c.add_argument("--results", nargs="+", required=True)
    c.add_argument("--contexts", nargs="+", required=True)
    sub.add_parser("gate-rule")
    d = sub.add_parser("latency")
    d.add_argument("--model", required=True, choices=sorted(EMB_MODELS))
    args = p.parse_args(argv)
    if args.cmd == "predict":
        if args.method in ("proto", "clf") and not args.model:
            p.error("proto · clf 에는 --model 이 필요하다")
        predict(args.method, args.model, args.device, args.outputs_dir, args.golden_xlsx, args.out)
    elif args.cmd == "run":
        run(args.engine_dir, args.contexts, args.outputs_dir, args.golden_xlsx, args.out)
    elif args.cmd == "evaluate":
        if len(args.results) != len(args.contexts):
            p.error("--results 와 --contexts 는 같은 방식끼리 같은 순서로 준다")
        evaluate(args.engine_dir, args.outputs_dir, args.golden_xlsx, args.reference,
                 args.results, args.contexts)
    elif args.cmd == "gate-rule":
        gate_rule(args.outputs_dir, args.golden_xlsx)
    else:
        latency(args.model, args.outputs_dir)


if __name__ == "__main__":
    main()

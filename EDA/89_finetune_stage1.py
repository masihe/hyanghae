"""①단계 LLM 의 구조화(성별·계절·낮밤 + 회피 조각 + 분위기 조각)를 파인튜닝한 한국어 인코더로 대체할 수 있나.

41번(통째 임베딩 검색)·42번(고정 임베딩으로 성별·계절)의 다음 질문이다 (2026-09-29, 사용자 결정).
42번에서 "조각 추출은 임베딩으로 안 된다" 고 적은 것은 고정 임베딩에만 맞다 — 파인튜닝하면 토큰 분류로 자를 수 있다.

과제와 정답 (측정 전에 고정)
    조각   AutoModelForTokenClassification · BIO 5태그(O · B/I-AVOID · B/I-ADD) · 정답 = Golden 200 사람 정답만
          (LLM 출력 조각은 원문과 달라 — avoid 가 원문에 그대로 있는 비율 17% — 학습에 쓰지 않는다)
    문맥   AutoModelForSequenceClassification · 다중 라벨 9개(BCE · 0.5) · 정답 = Golden 사람 정답 + 설문 155 LLM 출력
    백본   klue/roberta-base · jhgan/ko-sroberta-multitask (후자는 전자 위에 문장 임베딩 학습을 더한 것)
    설정   lr 3e-5 · 10 epoch · 배치 16 · 최대 128토큰 · AdamW(weight_decay 0.01) · 선형 감쇠(warmup 0) · fp32
          seed 0·1·2. 평가셋을 보고 바꾸지 않는다

평가
    A  Golden 200 · 5조각 교차검증 · 노트북 25 채점기(전체 층 L0~L4) — LLM · 확장 규칙과 같은 채점
    B  391 엔진 · 추정 끔 — Golden 전체로 학습한 모델로 합성 600(안 본 문장) · 설문 143 은 5조각 교차 적합.
       88 의 evaluate · 87 의 extras 를 그대로 쓴다(출력 형식을 맞췄다)
    C  CPU 지연 · 메모리

관문
    1  옮긴 채점기가 25_stage1_rescoring_metrics.csv 의 LLM · 확장 규칙 값을 재현한다
    2  Golden 정답 조각 -> BIO -> 조각 복원이 원래 조각과 같은 비율 >= 99%
    3  run 경로에 LLM 전체 structured 를 넣으면 0.699865

사용법 (결과와 해석은 docs/nlr_engineering_notes.md 43번)
    gate-scorer · gate-bio --backbone B · cv --backbone B --seed S --out F · e2e --backbone B --seed S --out F
    score-cv --preds F... · run --preds F --out R [--llm-mode full|three] · latency --model-dir D
"""
import argparse
import collections
import csv
import importlib.util
import json
import math
import random
import re
import unicodedata
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
DEFAULT_OUTPUTS = HERE / "analysis_outputs"
DEFAULT_GOLDEN = HERE / "evaluation_data" / "stage1" / "13_stage1_golden_set_v1_200.xlsx"
ALIAS_CSV = "25_stage1_scoring_alias_v1.csv"
RESCORED = "25_stage1_rescoring_metrics.csv"
PRED_FILES = {"llm": "15_llm_stage1_predictions.csv", "extended_rule": "14_extended_rule_stage1_predictions.csv"}
BACKBONES = {"klue-roberta": "klue/roberta-base", "ko-sroberta": "jhgan/ko-sroberta-multitask"}
TAGS = ["O", "B-AVOID", "I-AVOID", "B-ADD", "I-ADD"]
CTX_LABELS = [("gender", "male"), ("gender", "female"), ("gender", "neuter"),
              ("season", "spring"), ("season", "summer"), ("season", "autumn"), ("season", "winter"),
              ("daypart", "day"), ("daypart", "night")]
HP = {"lr": 3e-5, "epochs": 10, "batch": 16, "max_len": 128, "weight_decay": 0.01}
CV_FOLDS = 5
CV_SEED = 42

# ── 노트북 25 (25_stage1_rescoring_rule_v2.ipynb) 코드 셀 2 에서 옮겼다. 고치지 않았다 ──
MAX_EXCESS_TOKENS = 1
MIN_MATCH_CHARS = 2
LAYERS_FULL = {"L1_punct": True, "L2_alias": True, "L3_suffix": True, "L4_contain": True}
PUNCT_PATTERN = re.compile(r"[^0-9a-z가-힣\s]+")
COMPACT_PATTERN = re.compile(r"[^0-9a-z가-힣]+")
SUFFIX_PATTERN = re.compile(r"\s*(?:향기|향수|향|냄새|노트|계열|느낌|것|거|건)$")


def normalize_l0(value):
    """노트북 25 셀 2 그대로."""
    text = unicodedata.normalize("NFKC", "" if value is None else str(value)).casefold()
    return re.sub(r"\s+", " ", text).strip()


def strip_punct(key):
    """노트북 25 셀 2 그대로."""
    return re.sub(r"\s+", " ", PUNCT_PATTERN.sub(" ", key)).strip()


def strip_scent_suffix(key):
    """노트북 25 셀 2 그대로."""
    current = key
    for _ in range(3):
        stripped = SUFFIX_PATTERN.sub("", current).strip()
        if stripped == current or len(stripped.replace(" ", "")) < MIN_MATCH_CHARS:
            break
        current = stripped
    return current


def canonical_key(value, layers, alias):
    """노트북 25 셀 2 그대로."""
    key = normalize_l0(value)
    if layers.get("L1_punct"):
        key = strip_punct(key)
    if layers.get("L2_alias"):
        key = alias.get(key, key)
    if layers.get("L3_suffix"):
        stripped = strip_scent_suffix(key)
        if stripped != key:
            key = alias.get(stripped, stripped) if layers.get("L2_alias") else stripped
    return key


def dedupe_keys(keys):
    """노트북 25 셀 2 그대로."""
    seen, ordered = set(), []
    for key in keys:
        if key and key not in seen:
            seen.add(key)
            ordered.append(key)
    return ordered


def pair_quality(gold_key, pred_key, layers, max_excess=None):
    """노트북 25 셀 2 그대로."""
    if gold_key == pred_key:
        return (2, 1.0)
    if not layers.get("L4_contain"):
        return None
    budget = MAX_EXCESS_TOKENS if max_excess is None else max_excess
    gold_compact = COMPACT_PATTERN.sub("", gold_key)
    pred_compact = COMPACT_PATTERN.sub("", pred_key)
    if not gold_compact or not pred_compact:
        return None
    if len(gold_compact) <= len(pred_compact):
        short_key, long_key, short_c, long_c = gold_key, pred_key, gold_compact, pred_compact
    else:
        short_key, long_key, short_c, long_c = pred_key, gold_key, pred_compact, gold_compact
    if len(short_c) < MIN_MATCH_CHARS or short_c not in long_c:
        return None
    excess = len(long_key.split()) - len(short_key.split())
    if excess > budget:
        return None
    return (1, 1.0 / (1 + max(excess, 0)))


def match_items(gold_items, pred_items, layers, alias, max_excess=None):
    """노트북 25 셀 2 그대로."""
    gold_keys = dedupe_keys([canonical_key(v, layers, alias) for v in gold_items])
    pred_keys = dedupe_keys([canonical_key(v, layers, alias) for v in pred_items])
    candidates = []
    for gold_index, gold_key in enumerate(gold_keys):
        for pred_index, pred_key in enumerate(pred_keys):
            quality = pair_quality(gold_key, pred_key, layers, max_excess)
            if quality is not None:
                tier, score = quality
                candidates.append((-tier, -score, gold_key, pred_key, gold_index, pred_index))
    candidates.sort()
    used_gold, used_pred, pairs = set(), set(), []
    for neg_tier, neg_score, _, _, gold_index, pred_index in candidates:
        if gold_index in used_gold or pred_index in used_pred:
            continue
        used_gold.add(gold_index)
        used_pred.add(pred_index)
        pairs.append((gold_index, pred_index, -neg_tier, -neg_score))
    tp = len(pairs)
    return tp, len(pred_keys) - tp, len(gold_keys) - tp, pairs, gold_keys, pred_keys


def evaluate_multilabel(gold_values, pred_values, layers, alias, mask=None):
    """노트북 25 셀 2 그대로 (max_excess 인자만 뺐다)."""
    if mask is None:
        mask = np.ones(len(gold_values), dtype=bool)
    tp = fp = fn = eligible = 0
    for gold, pred, include in zip(gold_values, pred_values, mask):
        if not include:
            continue
        eligible += 1
        item_tp, item_fp, item_fn, _, _, _ = match_items(gold, pred, layers, alias)
        tp += item_tp
        fp += item_fp
        fn += item_fn
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": precision, "recall": recall, "f1": f1, "eligible": eligible}


def list_exact(gold_items, pred_items, layers, alias):
    """노트북 25 셀 2 그대로."""
    _, fp, fn, _, _, _ = match_items(gold_items, pred_items, layers, alias)
    return fp == 0 and fn == 0


def load_alias(outputs_dir):
    """노트북 25 셀 3 의 ALIAS 를 저장된 별칭표에서 다시 만든다. dict[str, str]."""
    surface_map, canonicals = {}, []
    with open(Path(outputs_dir) / ALIAS_CSV, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            for surface in row["aliases"].split("|"):
                surface_map[normalize_l0(surface)] = row["canonical_key"]
            canonicals.append(row["canonical_key"])
    alias = dict(surface_map)
    for c in canonicals:
        alias.setdefault(c, c)
    return alias


# ── 데이터 ──

def load_mod(name, filename):
    """같은 폴더의 번호 붙은 스크립트를 모듈로 불러온다. module."""
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_golden_full(golden_xlsx):
    """Golden 200 의 문장과 다섯 칸 정답. list[dict]. 조각은 원문 속 부분 문자열이다(nb25 불변식)."""
    import pandas as pd
    df = pd.read_excel(golden_xlsx, sheet_name="Golden Set", header=4, dtype=str, keep_default_na=False)
    rows = []
    for r in df.itertuples(index=False):
        g = {"query_id": r.query_id, "sentence": r.query_text,
             "context": json.loads(r.gold_context), "avoid": json.loads(r.gold_avoid),
             "additional": json.loads(r.gold_additional_requirements)}
        for span in g["avoid"] + g["additional"]:
            if span.strip() and span.strip() not in r.query_text:
                raise ValueError(f"원문에 없는 정답 조각: {r.query_id} {span}")
        rows.append(g)
    if len(rows) != 200:
        raise ValueError(f"Golden 이 200 문장이 아니다: {len(rows)}")
    return rows


def load_system_preds(outputs_dir, system):
    """저장된 시스템 예측(LLM · 확장 규칙). dict[query_id, dict(context, avoid, additional)]."""
    out = {}
    with open(Path(outputs_dir) / PRED_FILES[system], encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            out[r["query_id"]] = {"context": json.loads(r["pred_context"]),
                                  "avoid": json.loads(r["pred_avoid"]),
                                  "additional": json.loads(r["pred_additional_requirements"])}
    return out


def score_golden(golden, preds, alias):
    """Golden 200 채점 — 노트북 25 score_system 의 해당 부분과 같은 정의. dict."""
    L = LAYERS_FULL
    out = {}
    fields = {
        "avoid": ([g["avoid"] for g in golden], [preds[g["query_id"]]["avoid"] for g in golden]),
        "additional": ([g["additional"] for g in golden], [preds[g["query_id"]]["additional"] for g in golden]),
    }
    for f in ("season", "daypart", "gender"):
        fields[f] = ([g["context"][f] for g in golden], [preds[g["query_id"]]["context"].get(f, []) for g in golden])
    for f, (gold, pred) in fields.items():
        mask = np.asarray([bool(dedupe_keys([canonical_key(v, L, alias) for v in x])) for x in gold])
        out[f] = evaluate_multilabel(gold, pred, L, alias, mask)
    ctx_exact, av_exact, ad_exact, three = [], [], [], []
    for g in golden:
        p = preds[g["query_id"]]
        c = all(list_exact(g["context"][k], p["context"].get(k, []), L, alias) for k in ("season", "daypart", "gender"))
        a = list_exact(g["avoid"], p["avoid"], L, alias)
        d = list_exact(g["additional"], p["additional"], L, alias)
        ctx_exact.append(c)
        av_exact.append(a)
        ad_exact.append(d)
        three.append(c and a and d)
    out["context_exact"] = float(np.mean(ctx_exact))
    out["avoid_exact"] = float(np.mean(av_exact))
    out["additional_exact"] = float(np.mean(ad_exact))
    out["three_exact"] = float(np.mean(three))
    return out


def gate_scorer(outputs_dir, golden_xlsx):
    """관문 1 — 옮긴 채점기가 25_stage1_rescoring_metrics.csv 를 재현하는지. None."""
    published = {}
    with open(Path(outputs_dir) / RESCORED, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            published[r["metric"]] = float(r["value"])
    golden = load_golden_full(golden_xlsx)
    alias = load_alias(outputs_dir)
    bad = 0
    for system in PRED_FILES:
        s = score_golden(golden, load_system_preds(outputs_dir, system), alias)
        checks = {f"positive_{f}_micro_f1": s[f]["f1"] for f in ("avoid", "additional", "season", "gender")}
        checks.update({f"positive_{f}_micro_precision": s[f]["precision"] for f in ("avoid", "additional")})
        checks.update({"context_exact_match": s["context_exact"], "avoid_exact_match": s["avoid_exact"],
                       "additional_exact_match": s["additional_exact"]})
        for k, v in checks.items():
            want = published.get(f"{system}_{k}")
            ok = want is not None and abs(want - v) < 1e-9
            bad += int(not ok)
            print(f"{'OK ' if ok else 'XX '} {system:14s} {k:34s} 기록 {want} · 재계산 {v:.10f}")
        print(f"   {system:14s} 3칸 완전 일치 {s['three_exact']:.3f} (기존 5칸 EM 과 다른 지표)")
    print("관문 1 " + ("통과" if bad == 0 else f"실패 {bad}건"))


# ── BIO ──

def char_labels(text, avoid, additional):
    """원문 글자마다 (칸, 조각 번호). 겹치면 먼저 놓인 조각이 이긴다(회피 우선). (list, list[dropped])."""
    lab = [None] * len(text)
    dropped = []
    n = 0
    for kind, spans in (("AVOID", avoid), ("ADD", additional)):
        for span in spans:
            s = span.strip()
            if not s:
                continue
            start = -1
            pos = text.find(s)
            while pos >= 0:
                if all(x is None for x in lab[pos:pos + len(s)]):
                    start = pos
                    break
                pos = text.find(s, pos + 1)
            if start < 0:
                dropped.append((kind, s))
                continue
            for i in range(start, start + len(s)):
                lab[i] = (kind, n)
            n += 1
    return lab, dropped


def encode_bio(tokenizer, text, avoid, additional, max_len):
    """원문 -> 토큰과 BIO 라벨. (input_ids, attention, labels, offsets, dropped)."""
    lab, dropped = char_labels(text, avoid, additional)
    enc = tokenizer(text, truncation=True, max_length=max_len, return_offsets_mapping=True)
    labels, prev = [], None
    for (s, e) in enc["offset_mapping"]:
        if s == e:
            labels.append(-100)
            prev = None
            continue
        first = next((lab[i] for i in range(s, e) if lab[i] is not None), None)
        if first is None:
            labels.append(TAGS.index("O"))
            prev = None
        else:
            kind, idx = first
            tag = f"I-{kind}" if prev == first else f"B-{kind}"
            labels.append(TAGS.index(tag))
            prev = first
    return enc["input_ids"], enc["attention_mask"], labels, enc["offset_mapping"], dropped


def decode_bio(text, offsets, tags):
    """토큰 태그 -> 원문 조각. dict(avoid=[...], additional=[...])."""
    out = {"AVOID": [], "ADD": []}
    cur = None                      # [kind, start, end]
    for (s, e), t in zip(offsets, tags):
        if s == e:
            continue
        name = TAGS[t]
        if name == "O":
            if cur:
                out[cur[0]].append(text[cur[1]:cur[2]].strip())
            cur = None
            continue
        bio, kind = name.split("-")
        if bio == "B" or cur is None or cur[0] != kind:
            if cur:
                out[cur[0]].append(text[cur[1]:cur[2]].strip())
            cur = [kind, s, e]
        else:
            cur[2] = e
    if cur:
        out[cur[0]].append(text[cur[1]:cur[2]].strip())
    dedup = lambda xs: list(dict.fromkeys(x for x in xs if x))  # noqa: E731
    return {"avoid": dedup(out["AVOID"]), "additional": dedup(out["ADD"])}


def gate_bio(backbone, golden_xlsx):
    """관문 2 — 정답 조각 -> BIO -> 조각 복원이 원래와 같은 비율. None."""
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(BACKBONES[backbone])
    if not tok.is_fast:
        raise RuntimeError(f"{backbone} 토크나이저가 fast 가 아니라 offset 을 못 준다")
    golden = load_golden_full(golden_xlsx)
    total = same = 0
    lost = []
    for g in golden:
        ids, _, labels, offsets, dropped = encode_bio(tok, g["sentence"], g["avoid"], g["additional"], HP["max_len"])
        back = decode_bio(g["sentence"], offsets, [max(x, 0) for x in labels])
        for kind in ("avoid", "additional"):
            want = [s.strip() for s in g[kind] if s.strip()]
            total += len(want)
            for s in want:
                if s in back[kind]:
                    same += 1
                else:
                    lost.append((g["query_id"], kind, s, back[kind]))
        if len(ids) >= HP["max_len"]:
            lost.append((g["query_id"], "잘림", len(ids), None))
    print(f"{backbone} · 정답 조각 {total} · 복원 일치 {same} ({same / total:.1%})")
    for x in lost[:15]:
        print("  ", x)
    print("관문 2 " + ("통과" if same / total >= 0.99 else "실패"))


# ── 학습 ──

def set_seed(seed):
    """재현을 위한 seed 고정. None."""
    import torch
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def train_loop(model, batches_fn, n_items, device, seed, loss_fn=None):
    """고정 설정으로 학습한다. batches_fn(order) 는 배치 dict 를 낸다. loss_fn 이 없으면 모델 내장 손실. model."""
    import torch
    from transformers import get_linear_schedule_with_warmup
    model.to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=HP["lr"], weight_decay=HP["weight_decay"])
    steps = math.ceil(n_items / HP["batch"]) * HP["epochs"]
    sched = get_linear_schedule_with_warmup(opt, 0, steps)
    rng = np.random.default_rng(seed)
    model.train()
    for _ in range(HP["epochs"]):
        order = rng.permutation(n_items)
        for batch in batches_fn(order):
            batch = {k: v.to(device) for k, v in batch.items()}
            loss = loss_fn(model, batch) if loss_fn else model(**batch).loss
            loss.backward()
            opt.step()
            sched.step()
            opt.zero_grad()
    model.eval()
    return model


def pad(seqs, value):
    """길이를 맞춘다. list[list]."""
    n = max(len(s) for s in seqs)
    return [s + [value] * (n - len(s)) for s in seqs]


def train_span(backbone, seed, train_rows, device):
    """조각 모델 학습. (model, tokenizer)."""
    import torch
    from transformers import AutoModelForTokenClassification, AutoTokenizer
    set_seed(seed)
    tok = AutoTokenizer.from_pretrained(BACKBONES[backbone])
    model = AutoModelForTokenClassification.from_pretrained(BACKBONES[backbone], num_labels=len(TAGS))
    enc = [encode_bio(tok, r["sentence"], r["avoid"], r["additional"], HP["max_len"]) for r in train_rows]

    def batches(order):
        for i in range(0, len(order), HP["batch"]):
            idx = order[i:i + HP["batch"]]
            yield {"input_ids": torch.tensor(pad([enc[j][0] for j in idx], tok.pad_token_id)),
                   "attention_mask": torch.tensor(pad([enc[j][1] for j in idx], 0)),
                   "labels": torch.tensor(pad([enc[j][2] for j in idx], -100))}
    return train_loop(model, batches, len(enc), device, seed), tok


def predict_span(model, tok, texts, device):
    """원문 -> 조각. list[dict(avoid, additional)]."""
    import torch
    out = []
    with torch.no_grad():
        for t in texts:
            enc = tok(t, truncation=True, max_length=HP["max_len"], return_offsets_mapping=True, return_tensors="pt")
            offsets = enc.pop("offset_mapping")[0].tolist()
            logits = model(**{k: v.to(device) for k, v in enc.items()}).logits[0]
            out.append(decode_bio(t, offsets, logits.argmax(-1).tolist()))
    return out


def ctx_vector(ctx):
    """context -> 9개 라벨 0/1. list[float]."""
    ctx = ctx if isinstance(ctx, dict) else {}
    have = set()
    for f in ("gender", "season", "daypart"):
        v = ctx.get(f) or []
        v = [v] if isinstance(v, str) else v
        have |= {(f, str(x).strip().lower()) for x in v}
    return [float(lab in have) for lab in CTX_LABELS]


def train_ctx(backbone, seed, train_rows, device, pos_weight=False):
    """문맥 모델 학습. train_rows = [dict(sentence, context)]. (model, tokenizer).

    pos_weight  True 면 라벨별 BCE 양성 가중치 = 음성 수 / 양성 수 (학습 데이터에서 자동 계산 · 양성 0 이면 1).
                실험 2(45번)에서 바꾸는 단 하나다. 그 밖의 설정은 43번과 같다
    """
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer
    set_seed(seed)
    tok = AutoTokenizer.from_pretrained(BACKBONES[backbone])
    model = AutoModelForSequenceClassification.from_pretrained(
        BACKBONES[backbone], num_labels=len(CTX_LABELS), problem_type="multi_label_classification")
    enc = [tok(r["sentence"], truncation=True, max_length=HP["max_len"]) for r in train_rows]
    ys = [ctx_vector(r["context"]) for r in train_rows]
    loss_fn = None
    if pos_weight:
        y = np.asarray(ys)
        pos = y.sum(axis=0)
        weight = np.where(pos > 0, (len(y) - pos) / np.maximum(pos, 1), 1.0)
        pw = torch.tensor(weight, dtype=torch.float32, device=device)
        bce = torch.nn.BCEWithLogitsLoss(pos_weight=pw)

        def loss_fn(m, batch):
            labels = batch.pop("labels")
            return bce(m(**batch).logits, labels)

    def batches(order):
        for i in range(0, len(order), HP["batch"]):
            idx = order[i:i + HP["batch"]]
            yield {"input_ids": torch.tensor(pad([enc[j]["input_ids"] for j in idx], tok.pad_token_id)),
                   "attention_mask": torch.tensor(pad([enc[j]["attention_mask"] for j in idx], 0)),
                   "labels": torch.tensor([ys[j] for j in idx])}
    return train_loop(model, batches, len(enc), device, seed, loss_fn), tok


def predict_ctx(model, tok, texts, device):
    """원문 -> context. list[dict(gender, season, daypart)]."""
    import torch
    out = []
    with torch.no_grad():
        for t in texts:
            enc = tok(t, truncation=True, max_length=HP["max_len"], return_tensors="pt")
            p = torch.sigmoid(model(**{k: v.to(device) for k, v in enc.items()}).logits[0]).tolist()
            ctx = {"gender": [], "season": [], "daypart": []}
            for (f, lab), pr in zip(CTX_LABELS, p):
                if pr >= 0.5:
                    ctx[f].append(lab)
            out.append(ctx)
    return out


def survey155(outputs_dir):
    """설문 155 원문과 LLM context (문맥 학습 보탬). list[dict]."""
    x87 = load_mod("exp87", "87_embedding_vs_engine.py")
    rows = []
    with open(Path(outputs_dir) / x87.SURVEY, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            parsed = json.loads(r["parsed"]) if r["parsed"] else {}
            rows.append({"query_id": r["query_id"], "sentence": r["query_text"],
                         "context": (parsed or {}).get("context") or {}})
    return rows


def folds(n, k=CV_FOLDS, seed=CV_SEED):
    """0..n-1 을 k 조각으로. list[np.ndarray]."""
    order = np.random.default_rng(seed).permutation(n)
    return [order[i::k] for i in range(k)]


def load_span_from(path, backbone, seed):
    """이전 실행의 조각 예측을 재사용한다 — 같은 백본 · seed 인지 확인한다. dict[qid, dict]."""
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    if "preds" in d:                     # cv 파일
        tag = (d["backbone"], d["seed"])
        if tag != (backbone, seed):
            raise ValueError(f"조각 파일이 {tag} 다 — {(backbone, seed)} 가 아니다: {path}")
        return {k: {"avoid": v["avoid"], "additional": v["additional"]} for k, v in d["preds"].items()}
    if d["model"] != f"{backbone}-s{seed}":
        raise ValueError(f"조각 파일이 {d['model']} 다 — {backbone}-s{seed} 가 아니다: {path}")
    return d["spans"]


def cv(backbone, seed, device, outputs_dir, golden_xlsx, out_path, span_from=None, pos_weight=False):
    """A — Golden 200 5조각 교차검증 예측. 각 조각은 나머지로 학습한 모델이 판정한다. None.

    span_from   주면 조각은 그 파일(같은 백본 · seed 의 이전 cv)에서 가져오고 문맥 모델만 학습한다
    """
    golden = load_golden_full(golden_xlsx)
    extra = survey155(outputs_dir)
    old_spans = load_span_from(span_from, backbone, seed) if span_from else None
    preds = {}
    for k, test in enumerate(folds(len(golden))):
        test_set = set(test.tolist())
        train = [g for i, g in enumerate(golden) if i not in test_set]
        texts = [golden[i]["sentence"] for i in test]
        if old_spans is None:
            sm, st = train_span(backbone, seed, train, device)
            spans = predict_span(sm, st, texts, device)
            del sm
        else:
            spans = [old_spans[golden[i]["query_id"]] for i in test]
        cm, ct = train_ctx(backbone, seed, [{"sentence": g["sentence"], "context": g["context"]} for g in train] + extra,
                           device, pos_weight)
        ctxs = predict_ctx(cm, ct, texts, device)
        del cm
        for i, s, c in zip(test, spans, ctxs):
            preds[golden[i]["query_id"]] = {"context": c, "avoid": s["avoid"], "additional": s["additional"]}
        print(f"  {backbone} seed {seed} 조각 {k + 1}/{CV_FOLDS} 끝")
    Path(out_path).write_text(json.dumps({"backbone": backbone, "seed": seed, "pos_weight": pos_weight, "preds": preds},
                                         ensure_ascii=False), encoding="utf-8")
    print(f"-> {out_path}")


def score_cv(outputs_dir, golden_xlsx, pred_paths):
    """A 채점 — 교차검증 예측을 LLM · 확장 규칙과 같은 채점기로. None."""
    golden = load_golden_full(golden_xlsx)
    alias = load_alias(outputs_dir)
    rows = {s: score_golden(golden, load_system_preds(outputs_dir, s), alias) for s in PRED_FILES}
    groups = collections.defaultdict(list)
    for p in pred_paths:
        d = json.loads(Path(p).read_text(encoding="utf-8"))
        groups[d["backbone"]].append((d["seed"], score_golden(golden, d["preds"], alias)))
    keys = [("avoid", "f1"), ("additional", "f1"), ("gender", "f1"), ("season", "f1"),
            ("avoid", "precision"), ("avoid", "recall"), ("additional", "precision"), ("additional", "recall")]
    head = " · ".join(f"{f} {m[0].upper()}" for f, m in keys)
    print(f"Golden 200 · 정답이 있는 문장 한정 micro · 노트북 25 전체 층\n  {'':22s} {head} · 3칸 완전 일치")
    for s, r in rows.items():
        print(f"  {s:22s} " + " · ".join(f"{r[f][m]:.3f}" for f, m in keys) + f" · {r['three_exact']:.3f}")
    for b, lst in groups.items():
        for seed, r in sorted(lst):
            print(f"  {b + ' s' + str(seed):22s} " + " · ".join(f"{r[f][m]:.3f}" for f, m in keys)
                  + f" · {r['three_exact']:.3f}")
        mean = lambda f, m: np.mean([r[f][m] for _, r in lst])  # noqa: E731
        sd = lambda f, m: np.std([r[f][m] for _, r in lst])  # noqa: E731
        print(f"  {b + ' 평균±sd':22s} " + " · ".join(f"{mean(f, m):.3f}±{sd(f, m):.3f}" for f, m in keys)
              + f" · {np.mean([r['three_exact'] for _, r in lst]):.3f}")


def e2e(backbone, seed, device, outputs_dir, golden_xlsx, out_path, save_dir=None, span_from=None, pos_weight=False):
    """B 용 예측 — Golden 전체로 학습해 합성 600(안 본 문장)을, 설문 143 은 5조각 교차 적합으로. None.

    출력은 88 의 contexts 형식(method · model · contexts)에 조각을 더한 것이다 — 88 evaluate 가 그대로 읽는다.
    span_from   주면 조각은 그 파일(같은 백본 · seed 의 이전 e2e)에서 가져오고 문맥 모델만 학습한다
    """
    x87 = load_mod("exp87", "87_embedding_vs_engine.py")
    golden = load_golden_full(golden_xlsx)
    extra = survey155(outputs_dir)
    synth = x87.load_synth(outputs_dir)
    survey = x87.load_survey(outputs_dir)
    if span_from:
        spans = load_span_from(span_from, backbone, seed)
    else:
        sm, st = train_span(backbone, seed, golden, device)
        spans = dict(zip([q["query_id"] for q in synth + survey],
                         predict_span(sm, st, [q["sentence"] for q in synth + survey], device)))
        if save_dir:
            sm.save_pretrained(Path(save_dir) / "span")
            st.save_pretrained(Path(save_dir) / "span")
        del sm
    gold_ctx = [{"sentence": g["sentence"], "context": g["context"]} for g in golden]
    cm, ct = train_ctx(backbone, seed, gold_ctx + extra, device, pos_weight)
    ctxs = dict(zip([q["query_id"] for q in synth], predict_ctx(cm, ct, [q["sentence"] for q in synth], device)))
    if save_dir:
        cm.save_pretrained(Path(save_dir) / "ctx")
        ct.save_pretrained(Path(save_dir) / "ctx")
    del cm
    want = {q["query_id"] for q in survey}
    for test in folds(len(extra)):
        test_set = set(test.tolist())
        train = gold_ctx + [e for i, e in enumerate(extra) if i not in test_set]
        cm, ct = train_ctx(backbone, seed, train, device, pos_weight)
        rows = [extra[i] for i in test if extra[i]["query_id"] in want]
        for r, c in zip(rows, predict_ctx(cm, ct, [r["sentence"] for r in rows], device)):
            ctxs[r["query_id"]] = c
        del cm
    missing = [q["query_id"] for q in synth + survey if q["query_id"] not in ctxs]
    if missing:
        raise ValueError(f"예측이 빠진 문장 {len(missing)}: {missing[:5]}")
    out = {"method": "ft-pw" if pos_weight else "ft", "model": f"{backbone}-s{seed}",
           "contexts": {k: {f: sorted(v.get(f, [])) for f in ("gender", "season", "daypart")} for k, v in ctxs.items()},
           "spans": spans}
    Path(out_path).write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    n_av = sum(1 for s in spans.values() if s["avoid"])
    n_ad = sum(1 for s in spans.values() if s["additional"])
    print(f"-> {out_path} · 회피가 있는 문장 {n_av} · 분위기 조각이 있는 문장 {n_ad}")


def train_ctx_save(backbone, seed, device, outputs_dir, golden_xlsx, save_dir, pos_weight=False):
    """성별·계절 모델 하나를 Golden 전체 + 설문 155 로 학습해 저장한다 — e2e 의 합성 600 판정 모델과 같다. None.

    46번(오타 강건성)에서 오타 문장을 판정하려고 만들었다. 설문 교차 적합은 하지 않는다.
    """
    golden = load_golden_full(golden_xlsx)
    extra = survey155(outputs_dir)
    gold_ctx = [{"sentence": g["sentence"], "context": g["context"]} for g in golden]
    cm, ct = train_ctx(backbone, seed, gold_ctx + extra, device, pos_weight)
    cm.save_pretrained(Path(save_dir))
    ct.save_pretrained(Path(save_dir))
    print(f"-> {save_dir} ({backbone} · seed {seed} · pos_weight {pos_weight})")


def run(engine_dir, outputs_dir, out_path, preds_path=None, llm_mode=None):
    """391 엔진(추정 끔)에 structured 를 넣어 결과를 저장한다. None.

    preds_path   파인튜닝 예측 — context · avoid · additional 을 채우고 scent · performance 는 비운다
    llm_mode     full = LLM 출력 그대로(관문 3) · three = LLM 의 같은 세 칸만(scent · performance 비움)
    """
    x87 = load_mod("exp87", "87_embedding_vs_engine.py")
    engine = x87.load_engine(engine_dir)
    index = engine.load_index()
    queries = x87.load_synth(outputs_dir) + x87.load_survey(outputs_dir)
    p = json.loads(Path(preds_path).read_text(encoding="utf-8")) if preds_path else None
    result, status = {}, collections.Counter()
    for q in queries:
        llm = q["structured"] or {}
        if p:
            s = {"scent_preference": [], "context": p["contexts"][q["query_id"]],
                 "performance": {"intensity": "", "longevity": ""},
                 "avoid": p["spans"][q["query_id"]]["avoid"],
                 "additional_requirements": p["spans"][q["query_id"]]["additional"]}
        elif llm_mode == "full":
            s = q["structured"]
        else:
            s = {"scent_preference": [], "context": llm.get("context") or {},
                 "performance": {"intensity": "", "longevity": ""},
                 "avoid": llm.get("avoid") or [], "additional_requirements": llm.get("additional_requirements") or []}
        rec = engine.recommend(index, q["sentence"], structured=s, top_k=x87.TOP_K, estimator=None)
        result[q["query_id"]] = {"status": rec["status"], "stage": rec["diagnostics"]["stage"],
                                 "ids": [r["perfume_id"] for r in rec["results"]]}
        status[("합성" if q["arm"] != "S" else "설문", rec["status"])] += 1
    Path(out_path).write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    print(f"-> {out_path}  {dict(sorted(status.items()))}")


def latency(model_dir, outputs_dir, n=50):
    """C — CPU 기준 문장 1개 처리(조각 + 문맥 두 번) 지연과 메모리. 프로세스를 따로 띄운다. None."""
    import time
    import psutil
    import torch
    from transformers import AutoModelForSequenceClassification, AutoModelForTokenClassification, AutoTokenizer
    proc = psutil.Process()
    rss_t = proc.memory_info().rss / 2**20
    sm = AutoModelForTokenClassification.from_pretrained(Path(model_dir) / "span").eval()
    st = AutoTokenizer.from_pretrained(Path(model_dir) / "span")
    cm = AutoModelForSequenceClassification.from_pretrained(Path(model_dir) / "ctx").eval()
    ct = AutoTokenizer.from_pretrained(Path(model_dir) / "ctx")
    x87 = load_mod("exp87", "87_embedding_vs_engine.py")
    texts = [q["sentence"] for q in x87.load_survey(outputs_dir)[:n]]
    predict_span(sm, st, ["워밍업"], "cpu")
    predict_ctx(cm, ct, ["워밍업"], "cpu")
    times = []
    with torch.no_grad():
        for t in texts:
            t0 = time.perf_counter()
            predict_span(sm, st, [t], "cpu")
            predict_ctx(cm, ct, [t], "cpu")
            times.append((time.perf_counter() - t0) * 1000)
    rss = proc.memory_info().rss / 2**20
    size = sum(f.stat().st_size for f in Path(model_dir).rglob("*.safetensors")) / 2**20
    print(f"{model_dir} · torch 적재 후 {rss_t:.0f}MB -> 최종 {rss:.0f}MB (+{rss - rss_t:.0f}) · 가중치 {size:.0f}MB · "
          f"문장 {n}개 중앙 {np.median(times):.1f}ms · p95 {np.percentile(times, 95):.1f}ms")


def main(argv=None):
    """명령행 진입점."""
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--outputs-dir", default=str(DEFAULT_OUTPUTS))
    p.add_argument("--golden-xlsx", default=str(DEFAULT_GOLDEN))
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("gate-scorer")
    g = sub.add_parser("gate-bio")
    g.add_argument("--backbone", required=True, choices=sorted(BACKBONES))
    for name in ("cv", "e2e"):
        a = sub.add_parser(name)
        a.add_argument("--backbone", required=True, choices=sorted(BACKBONES))
        a.add_argument("--seed", type=int, required=True)
        a.add_argument("--device", default="cuda")
        a.add_argument("--out", required=True)
        a.add_argument("--span-from", help="조각은 이 파일(같은 백본 · seed)에서 가져오고 문맥 모델만 학습")
        a.add_argument("--pos-weight", action="store_true", help="문맥 BCE 에 라벨별 양성 가중치 (45번)")
        if name == "e2e":
            a.add_argument("--save-dir", help="가중치를 남길 곳 (latency 측정용 · 저장소 밖)")
    tc = sub.add_parser("train-ctx")
    tc.add_argument("--backbone", required=True, choices=sorted(BACKBONES))
    tc.add_argument("--seed", type=int, required=True)
    tc.add_argument("--device", default="cuda")
    tc.add_argument("--pos-weight", action="store_true")
    tc.add_argument("--save-dir", required=True)
    s = sub.add_parser("score-cv")
    s.add_argument("--preds", nargs="+", required=True)
    r = sub.add_parser("run")
    r.add_argument("--engine-dir", required=True)
    r.add_argument("--out", required=True)
    grp = r.add_mutually_exclusive_group(required=True)
    grp.add_argument("--preds")
    grp.add_argument("--llm-mode", choices=["full", "three"])
    lt = sub.add_parser("latency")
    lt.add_argument("--model-dir", required=True)
    args = p.parse_args(argv)
    if args.cmd == "gate-scorer":
        gate_scorer(args.outputs_dir, args.golden_xlsx)
    elif args.cmd == "gate-bio":
        gate_bio(args.backbone, args.golden_xlsx)
    elif args.cmd == "cv":
        cv(args.backbone, args.seed, args.device, args.outputs_dir, args.golden_xlsx, args.out,
           args.span_from, args.pos_weight)
    elif args.cmd == "e2e":
        e2e(args.backbone, args.seed, args.device, args.outputs_dir, args.golden_xlsx, args.out, args.save_dir,
            args.span_from, args.pos_weight)
    elif args.cmd == "train-ctx":
        train_ctx_save(args.backbone, args.seed, args.device, args.outputs_dir, args.golden_xlsx, args.save_dir,
                       args.pos_weight)
    elif args.cmd == "score-cv":
        score_cv(args.outputs_dir, args.golden_xlsx, args.preds)
    elif args.cmd == "run":
        run(args.engine_dir, args.outputs_dir, args.out, args.preds, args.llm_mode)
    else:
        latency(args.model_dir, args.outputs_dir)


if __name__ == "__main__":
    main()

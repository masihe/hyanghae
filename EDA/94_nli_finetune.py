"""48번의 한국어 NLI 두 모델을 context(성별·계절·낮밤) 판정용으로 미세조정한다 — 49번.

바꾸는 것 (두 칸 · 사용자 결정 — 한 번에 한 가지만 바뀌게)
    human      Golden 200(사람 정답) + 설문 155(GMS 라벨) 로만 학습
    human+tmpl 위에 템플릿 문장을 더한다 — 조건 없음 40% · 조건 있음 40% · 부정 20% (사용자 결정)

라벨 (가설은 93 HYPOTHESES 그대로)
    사람 · 설문 문장   정답에 있는 값 = entailment · 없는 값 = neutral (부정 정보는 없다)
    템플릿 문장        말한 값 = entailment · 부정한 값 = contradiction · 말하지 않은 값 = neutral
판정은 48번과 같다 — 세 라벨 중 entailment 가 가장 높으면 붙인다

평가 누수 방지
    Golden · 설문은 5-fold 교차 적합(자기가 든 조각을 뺀 모델로 예측). 합성 600 은 학습에 없어 전체로 학습한 모델로 예측
    템플릿 표현은 규칙 사전 · 엔진 한국어 사전 · 일반 한국어에서 만들었다. 평가 문장과 겹치는 표현은 overlap 으로 세어 기록한다

판정 기준 (측정 전 고정 · seed 3개 모두 충족해야 통과)
    규칙을 넘음              엔진(391 · 추정 끔 · context 만) 확장 NDCG 규칙 context 만 대비 95% 구간 > 0
    공짜 점수 빼고도 넘음     위에서 규칙이 0건을 낸 '조건 없음' 문장(48번 분류)을 뺀 구간 > 0
    정밀도 문제를 풂          합성 600 GMS 판정 대비 정밀도 >= 규칙 (성별 0.88 · 계절 0.98 · 낮밤 0.95)
    실사용                   설문 143 은 따로 보고한다 (템플릿과 무관한 문장)

사용법 (결과와 해석은 docs/nlr_engineering_notes.md 49번)
    templates --engine-dir <391 ai> --out T.json
    overlap --templates T.json
    cv --model M --arm human|human+tmpl --seed S --templates T.json --out C.json     (88 contexts 형식)
    judge --engine-dir <391 ai> --rule-results R.json --results X.json...
"""
import argparse
import csv
import importlib.util
import json
import math
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
DEFAULT_OUTPUTS = HERE / "analysis_outputs"
HP = {"lr": 2e-5, "epochs": 3, "batch": 32, "weight_decay": 0.01, "max_len": 128}
FOLDS = 5
FOLD_SEED = 42
# mDeBERTa 2.8억 중 1.9억이 다국어 단어 임베딩(25만 × 768) — float32 로 다 학습하면 6GB GPU 를 넘어 fold 하나에 40분이 걸렸다.
# 단어 임베딩만 고정한다(사용자 결정). kornli 는 전부 학습하므로 두 모델의 학습 방식이 다르다
FREEZE_WORD_EMBEDDINGS = {"mdeberta-2mil7"}
# 고정만으로는 모자랐다 — 메모리를 먹는 것은 문장 계산(활성값)이었다. 가장 긴 배치 32 = 8.3GB · 16 = 5.1GB (실측).
# mDeBERTa 는 16 씩 두 번 계산해 기울기를 합친다(실질 배치 32 그대로 · 사용자 결정)
MICRO_BATCH = {"mdeberta-2mil7": 16}
TEMPLATE_SEED = 20260930
N_TEMPLATES = 1500
MIX = {"none": 0.4, "pos": 0.4, "neg": 0.2}

# 조건 표현 — 규칙 사전(봄 · 여름 · 가을 · 겨울 · 낮 · 밤)과 88 GENDER_RULES 의 낱말 + 일반 한국어의 돌려 말하기.
# ⚠ '더운 날' · '추운 날' 은 48번에서 평가 문장에서 본 표현이다(일반적인 표현이라 뺄 수 없다고 판단 · overlap 으로 센다)
TIME_PHRASES = {
    ("season", "spring"): ["봄에", "봄날에", "꽃 피는 봄에"],
    ("season", "summer"): ["여름에", "더운 날에", "한여름에"],
    ("season", "autumn"): ["가을에", "선선한 가을에", "낙엽 지는 계절에"],
    ("season", "winter"): ["겨울에", "추운 날에", "눈 오는 날에"],
    ("daypart", "day"): ["낮에", "햇빛 좋은 낮에", "낮 시간에"],
    ("daypart", "night"): ["밤에", "저녁에", "잠들기 전에"],
}
GENDER_PHRASES = {
    ("gender", "male"): ["남자가 쓸", "남성용으로 쓸", "남자 향수로 쓸"],
    ("gender", "female"): ["여자가 쓸", "여성용으로 쓸", "여자 향수로 쓸"],
    ("gender", "neuter"): ["남녀 공용으로 쓸", "남녀 구분 없이 쓸", "성별 상관없이 쓸"],
}
# 부정 — 이 낱말의 값은 contradiction
NEG_WORDS = {("season", "spring"): "봄", ("season", "summer"): "여름", ("season", "autumn"): "가을",
             ("season", "winter"): "겨울", ("daypart", "day"): "낮", ("daypart", "night"): "밤",
             ("gender", "male"): "남성용", ("gender", "female"): "여성용"}
FRAMES_TIME = ["{t} 쓸 {s} 향을 찾고 있어.", "{s} 향이 좋아. {t} 뿌리기 좋았으면 해.", "{t} 어울리는 {s} 향수를 추천해줘.",
               "{s} 느낌이 나는 향으로 {t} 쓰고 싶어."]
FRAMES_GENDER = ["{g} {s} 향수를 찾고 있어.", "{s} 향이 나는 걸로 {g} 향수를 추천해줘."]
FRAMES_BOTH = ["{t} {g} {s} 향수를 찾고 있어."]
FRAMES_NEG = ["{n} 말고 다른 때 쓸 {s} 향을 원해.", "{n}에는 안 쓸 거고 {s} 향이면 좋겠어.", "{n} 말고 {t} 쓸 {s} 향을 찾고 있어."]
FRAMES_NEG_GENDER = ["{n} 향수는 싫고 {s} 향이면 좋겠어.", "{n}은 말고 {s} 향수를 추천해줘."]
FRAMES_NONE = ["{s} 향을 찾고 있어.", "{s} 향과 {s2} 느낌이 섞였으면 좋겠어.", "{s} 향이 은은하게 나는 향수를 추천해줘.",
               "처음엔 {s} 향이고 나중엔 {s2} 느낌이 남았으면 해.", "{s} 같은 향이 좋아."]
# 엔진 사전 표현 중 향 묘사로 쓰지 않는 것 — 조건을 암시하거나(여성스러운 · 휴양지 · 차가운) 향 묘사가 아니다(성능 용어)
SCENT_EXCLUDE = {"여성스러운", "휴양지", "차가운", "달달", "섹시한", "귀여운", "어린 느낌"}


def load_mod(name, path):
    """파일 경로의 모듈을 불러온다. module."""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(Path(path).parent))
    spec.loader.exec_module(module)
    return module


def scent_words(engine_dir):
    """향 묘사 낱말 — 엔진의 한국어 노트 별칭 + 도메인 사전 표현(성능 용어 · 조건 암시 제외). list[str]."""
    data = Path(engine_dir) / "data"
    with open(data / "note_alias_ko.csv", encoding="utf-8-sig", newline="") as f:
        words = [r["alias"].strip() for r in csv.DictReader(f)]
    with open(data / "domain_lexicon_v1_18.csv", encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            e = r["expression"].strip()
            if r["expression_type"] == "PERFORMANCE" or e in SCENT_EXCLUDE or e.endswith("향"):
                continue
            words.append(e)
    return sorted({w for w in words if w})


def empty_labels():
    """모든 값 neutral. dict[(field, value), str]."""
    x93 = load_mod("exp93", HERE / "93_nli_context.py")
    return {(f, v): "neutral" for f, v, _ in x93.PAIRS}


def make_templates(engine_dir, n=N_TEMPLATES, seed=TEMPLATE_SEED):
    """템플릿 문장과 값별 라벨. list[dict(sentence, kind, labels{field:value -> entailment|neutral|contradiction})]."""
    rng = np.random.default_rng(seed)
    scents = scent_words(engine_dir)
    pick = lambda xs: xs[int(rng.integers(len(xs)))]
    out = []
    counts = {k: int(round(n * v)) for k, v in MIX.items()}
    for _ in range(counts["none"]):
        s, s2 = pick(scents), pick(scents)
        out.append({"sentence": pick(FRAMES_NONE).format(s=s, s2=s2), "kind": "none", "labels": empty_labels()})
    for i in range(counts["pos"]):
        lab = empty_labels()
        s = pick(scents)
        kind = ("time", "gender", "both")[i % 3]
        tkey = pick(sorted(TIME_PHRASES))
        gkey = pick(sorted(GENDER_PHRASES))
        t, g = pick(TIME_PHRASES[tkey]), pick(GENDER_PHRASES[gkey])
        if kind == "time":
            sent = pick(FRAMES_TIME).format(t=t, s=s)
            lab[tkey] = "entailment"
        elif kind == "gender":
            sent = pick(FRAMES_GENDER).format(g=g, s=s)
            lab[gkey] = "entailment"
        else:
            sent = pick(FRAMES_BOTH).format(t=t, g=g, s=s)
            lab[tkey] = lab[gkey] = "entailment"
        out.append({"sentence": sent, "kind": f"pos-{kind}", "labels": lab})
    time_neg = [k for k in NEG_WORDS if k[0] != "gender"]
    gender_neg = [k for k in NEG_WORDS if k[0] == "gender"]
    for i in range(counts["neg"]):
        lab = empty_labels()
        s = pick(scents)
        if i % 3 == 2:
            nkey = pick(gender_neg)
            sent = pick(FRAMES_NEG_GENDER).format(n=NEG_WORDS[nkey], s=s)
        else:
            nkey = pick(time_neg)
            frame = pick(FRAMES_NEG)
            if "{t}" in frame:
                others = [k for k in sorted(TIME_PHRASES) if k[0] == nkey[0] and k != nkey]
                tkey = pick(others)
                sent = frame.format(n=NEG_WORDS[nkey], t=pick(TIME_PHRASES[tkey]), s=s)
                lab[tkey] = "entailment"
            else:
                sent = frame.format(n=NEG_WORDS[nkey], s=s)
        lab[nkey] = "contradiction"
        out.append({"sentence": sent, "kind": "neg", "labels": lab})
    return [{"sentence": r["sentence"], "kind": r["kind"],
             "labels": {f"{f}:{v}": l for (f, v), l in r["labels"].items()}} for r in out]


def human_rows(outputs_dir, golden_xlsx):
    """사람 · 설문 학습 문장. list[dict(query_id, sentence, source, labels)] — 정답에 있는 값 entailment, 나머지 neutral."""
    x88 = load_mod("exp88", HERE / "88_embedding_stage1_context.py")
    x87 = x88.load_87()
    _, survey155, golden = x88.eval_sets(x87, outputs_dir, golden_xlsx)
    rows = []
    for src, items, key in (("golden", golden, "gold"), ("survey", survey155, "llm")):
        for it in items:
            lab = {f"{f}:{v}": "neutral" for (f, v) in empty_labels()}
            for f, vs in it[key].items():
                for v in vs:
                    if f"{f}:{v}" in lab:
                        lab[f"{f}:{v}"] = "entailment"
            rows.append({"query_id": it["query_id"], "sentence": it["sentence"], "source": src, "labels": lab})
    return rows


class Trainer:
    """NLI 모델 하나를 (문장, 가설) 짝으로 미세조정하고 context 를 판정한다."""

    def __init__(self, model_key, device):
        self.x93 = load_mod("exp93", HERE / "93_nli_context.py")
        self.key = model_key
        self.device = device

    def fresh(self, seed):
        """새 모델 · 토크나이저. (model, tok, label2id)."""
        from transformers import AutoModelForSequenceClassification, AutoTokenizer, set_seed
        set_seed(seed)
        name = self.x93.MODELS[self.key]
        tok = AutoTokenizer.from_pretrained(name)
        # transformers 5.x 는 체크포인트 자료형을 그대로 쓴다 — mDeBERTa 는 float16 으로 저장돼 있어 AdamW 첫 단계에 가중치가 NaN 이 된다
        import torch
        model = AutoModelForSequenceClassification.from_pretrained(name, dtype=torch.float32).to(self.device)
        if self.key in FREEZE_WORD_EMBEDDINGS:
            model.get_input_embeddings().weight.requires_grad_(False)
        return model, tok, {k.lower(): v for k, v in model.config.label2id.items()}

    def encode(self, tok, model, prem, hyp):
        """짝 입력. dict[str, tensor] — type_vocab_size 1 이면 token_type_ids 를 뺀다(93 과 같다)."""
        enc = tok(prem, hyp, truncation="only_first", max_length=HP["max_len"], padding=True, return_tensors="pt")
        use_types = getattr(model.config, "type_vocab_size", 0) > 1
        return {k: v.to(self.device) for k, v in enc.items() if k != "token_type_ids" or use_types}

    def pretokenize(self, tok, model, prem, hyp):
        """짝을 패딩 없이 한 번 토큰화한다. list[dict] — 배치마다 tok.pad 로 맞춘다(encode 와 같은 토큰)."""
        enc = tok(prem, hyp, truncation="only_first", max_length=HP["max_len"])
        keys = [k for k in enc.keys() if k != "token_type_ids" or getattr(model.config, "type_vocab_size", 0) > 1]
        return [{k: enc[k][i] for k in keys} for i in range(len(prem))]

    def pad(self, tok, feats):
        """미리 토큰화한 짝 묶음을 텐서로. dict[str, tensor]."""
        return {k: v.to(self.device) for k, v in tok.pad(feats, return_tensors="pt").items()}

    def train(self, rows, seed):
        """rows 의 (문장, 가설 9개) 짝으로 학습. (model, tok, label2id)."""
        import torch
        from transformers import get_linear_schedule_with_warmup
        model, tok, l2i = self.fresh(seed)
        hyp = {f"{f}:{v}": h for f, v, h in self.x93.PAIRS}
        pairs = [(r["sentence"], hyp[k], l2i[lab]) for r in rows for k, lab in r["labels"].items()]
        feats = self.pretokenize(tok, model, [p for p, _, _ in pairs], [h for _, h, _ in pairs])
        opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=HP["lr"],
                                weight_decay=HP["weight_decay"])
        steps = math.ceil(len(pairs) / HP["batch"]) * HP["epochs"]
        sched = get_linear_schedule_with_warmup(opt, 0, steps)
        rng = np.random.default_rng(seed)
        model.train()
        for _ in range(HP["epochs"]):
            order = rng.permutation(len(pairs))
            for i in range(0, len(order), HP["batch"]):
                idx = order[i:i + HP["batch"]]
                micro = MICRO_BATCH.get(self.key, HP["batch"])
                for c in range(0, len(idx), micro):        # 기울기 누적 — 조각 평균 × 조각 비율의 합 = 배치 평균
                    part = idx[c:c + micro]
                    enc = self.pad(tok, [feats[j] for j in part])
                    y = torch.tensor([pairs[j][2] for j in part], device=self.device)
                    loss = torch.nn.functional.cross_entropy(model(**enc).logits, y) * (len(part) / len(idx))
                    loss.backward()
                opt.step()
                sched.step()
                opt.zero_grad()
        model.eval()
        return model, tok, l2i

    def context(self, model, tok, l2i, sentences, batch=64):
        """문장마다 context — entailment 가 세 라벨 중 가장 높은 값만. list[dict]."""
        import torch
        prem = [s for s in sentences for _ in self.x93.PAIRS]
        hyp = [h for _ in sentences for _, _, h in self.x93.PAIRS]
        ent = []
        with torch.no_grad():
            for i in range(0, len(prem), batch):
                logits = model(**self.encode(tok, model, prem[i:i + batch], hyp[i:i + batch])).logits
                ent.append((logits.argmax(-1) == l2i["entailment"]).cpu().numpy())
        ent = np.concatenate(ent).reshape(len(sentences), len(self.x93.PAIRS))
        res = []
        for row in ent:
            ctx = {f: [] for f in self.x93.HYPOTHESES}
            for (f, v, _), e in zip(self.x93.PAIRS, row):
                if e:
                    ctx[f].append(v)
            res.append({f: sorted(vs) for f, vs in ctx.items()})
        return res


def cv(model_key, arm, seed, templates_path, device, outputs_dir, golden_xlsx, out_path, full_only=False):
    """5-fold 교차 적합(Golden · 설문) + 전체 학습(합성 600). 88 contexts 형식으로 저장. None.

    full_only 면 교차 적합을 건너뛰고 전체 학습 모델로 설문 · Golden 도 채운다 — 학습에 든 문장이라 meta 에 leaked 로 적고 보고하지 않는다.
    """
    from sklearn.model_selection import KFold
    import torch
    x88 = load_mod("exp88", HERE / "88_embedding_stage1_context.py")
    x87 = x88.load_87()
    evalq, _, _ = x88.eval_sets(x87, outputs_dir, golden_xlsx)
    human = human_rows(outputs_dir, golden_xlsx)
    tmpl = json.loads(Path(templates_path).read_text(encoding="utf-8"))["items"] if arm == "human+tmpl" else []
    tr = Trainer(model_key, device)
    ctx, t0 = {}, time.perf_counter()
    folds = [] if full_only else KFold(FOLDS, shuffle=True, random_state=FOLD_SEED).split(human)
    for k, (train_idx, test_idx) in enumerate(folds):
        model, tok, l2i = tr.train(tmpl + [human[i] for i in train_idx], seed)
        held = [human[i] for i in test_idx]
        for r, c in zip(held, tr.context(model, tok, l2i, [r["sentence"] for r in held])):
            ctx[r["query_id"]] = c
        del model
        torch.cuda.empty_cache()
        print(f"  fold {k} · {time.perf_counter() - t0:.0f}초", flush=True)
    synth = [q for q in evalq if q["arm"] != "S"]
    model, tok, l2i = tr.train(tmpl + human, seed)
    full_items = synth + ([{"query_id": r["query_id"], "sentence": r["sentence"]} for r in human] if full_only else [])
    for q, c in zip(full_items, tr.context(model, tok, l2i, [q["sentence"] for q in full_items])):
        ctx[q["query_id"]] = c
    missing = [q["query_id"] for q in evalq if q["query_id"] not in ctx]
    if missing:
        raise ValueError(f"예측이 빠진 평가 문장 {len(missing)}: {missing[:5]}")
    meta = {"method": f"ft-{arm}", "model": f"{model_key}-s{seed}", "arm": arm, "seed": seed, "hp": HP, "encoding": "pair",
            "frozen": ["word_embeddings"] if model_key in FREEZE_WORD_EMBEDDINGS else [],
            "micro_batch": MICRO_BATCH.get(model_key, HP["batch"]),
            "leaked": ["survey", "golden"] if full_only else [],
            "n_templates": len(tmpl), "n_human": len(human), "contexts": ctx}
    Path(out_path).write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    print(f"{model_key} · {arm} · seed {seed} -> {out_path} · 학습 문장 템플릿 {len(tmpl)} + 사람 {len(human)} · "
          f"{time.perf_counter() - t0:.0f}초")


# 48번 분류 — 규칙이 0건을 낸 문장 중 '조건 없음' 이 아닌 것
CLASSIFIED = {"B-1067-1", "B-2802-2", "B-58907-1", "B-6-1", "B-3247-3", "B-11238-3", "B-49144-3", "B-85038-3",
              "B-103715-2", "B-6759-2", "B-6759-3", "B-25967-1", "B-25967-3", "B-64204-2", "B-113627-2"}


def judge(engine_dir, rule_results, results, outputs_dir):
    """규칙 대비 전체 · '조건 없음' 0건 문장을 뺀 확장 NDCG 차이와 구간. None."""
    x87 = load_mod("exp87", HERE / "87_embedding_vs_engine.py")
    engine = x87.load_engine(engine_dir)
    scorer = x87.Scorer(engine, engine.load_index(), x87.load_answer_key(outputs_dir))
    rule = json.loads(Path(rule_results).read_text(encoding="utf-8"))
    qs = [q for q in x87.load_synth(outputs_dir) if scorer.conditions(q) is not None]
    none = {q["query_id"] for q in qs if rule[q["query_id"]]["status"] == "NO_CONDITION"} - CLASSIFIED
    base = {q["query_id"]: scorer.ndcg(rule[q["query_id"]]["ids"], scorer.conditions(q)) for q in qs}
    print(f"합성 {len(qs)} · 규칙 0건 중 조건 없음 {len(none)}문장 제외 칸")
    for p in results:
        new = json.loads(Path(p).read_text(encoding="utf-8"))
        n = {q["query_id"]: scorer.ndcg(new[q["query_id"]]["ids"], scorer.conditions(q)) for q in qs}
        full = x87.paired_bootstrap([base[k] for k in base], [n[k] for k in base])
        keep = [k for k in base if k not in none]
        sub = x87.paired_bootstrap([base[k] for k in keep], [n[k] for k in keep])
        print(f"  {Path(p).name:38s} 전체 {full[0]:+.6f} [{full[1]:+.6f}, {full[2]:+.6f}] · "
              f"조건 없음 제외({len(keep)}) {sub[0]:+.6f} [{sub[1]:+.6f}, {sub[2]:+.6f}]")


def overlap(templates_path, outputs_dir, golden_xlsx):
    """템플릿 조건 표현이 평가 문장(합성 600 · 설문 143 · Golden 200)에 나오는 횟수. None."""
    x88 = load_mod("exp88", HERE / "88_embedding_stage1_context.py")
    x87 = x88.load_87()
    evalq, _, golden = x88.eval_sets(x87, outputs_dir, golden_xlsx)
    sets = {"합성": [q["sentence"] for q in evalq if q["arm"] != "S"],
            "설문": [q["sentence"] for q in evalq if q["arm"] == "S"], "Golden": [g["sentence"] for g in golden]}
    phrases = sorted({p.rstrip("에").replace(" 쓸", "").replace("으로", "") for ps in list(TIME_PHRASES.values()) +
                      list(GENDER_PHRASES.values()) for p in ps})
    items = json.loads(Path(templates_path).read_text(encoding="utf-8"))["items"]
    print(f"템플릿 {len(items)}문장 · 종류 {dict(sorted({k: sum(1 for r in items if r['kind'] == k) for k in {r['kind'] for r in items}}.items()))}")
    print("조건 표현 · 평가 문장에 나온 문장 수 (합성 · 설문 · Golden)")
    for p in phrases:
        c = [sum(p in s for s in v) for v in sets.values()]
        if any(c):
            print(f"  {p:12s} {c[0]:3d} · {c[1]:3d} · {c[2]:3d}")


def main(argv=None):
    """명령행 진입점."""
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--outputs-dir", default=str(DEFAULT_OUTPUTS))
    p.add_argument("--golden-xlsx", default=str(HERE / "evaluation_data" / "stage1" / "13_stage1_golden_set_v1_200.xlsx"))
    sub = p.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("templates")
    t.add_argument("--engine-dir", required=True)
    t.add_argument("--out", required=True)
    o = sub.add_parser("overlap")
    o.add_argument("--templates", required=True)
    c = sub.add_parser("cv")
    c.add_argument("--model", required=True, choices=["kornli-roberta", "mdeberta-2mil7"])
    c.add_argument("--arm", required=True, choices=["human", "human+tmpl"])
    c.add_argument("--seed", type=int, required=True)
    c.add_argument("--templates", required=True)
    c.add_argument("--device", default="cuda")
    c.add_argument("--out", required=True)
    c.add_argument("--full-only", action="store_true", help="교차 적합 없이 전체 학습만 (설문 · Golden 은 누수 · 보고 안 함)")
    j = sub.add_parser("judge")
    j.add_argument("--engine-dir", required=True)
    j.add_argument("--rule-results", required=True)
    j.add_argument("--results", nargs="+", required=True)
    args = p.parse_args(argv)
    if args.cmd == "templates":
        items = make_templates(args.engine_dir)
        Path(args.out).write_text(json.dumps({"seed": TEMPLATE_SEED, "mix": MIX, "items": items}, ensure_ascii=False),
                                  encoding="utf-8")
        print(f"-> {args.out} · {len(items)}문장")
        for r in items[::150]:
            print("  ", r["kind"], "|", r["sentence"], "|", {k: v for k, v in r["labels"].items() if v != "neutral"})
    elif args.cmd == "overlap":
        overlap(args.templates, args.outputs_dir, args.golden_xlsx)
    elif args.cmd == "cv":
        cv(args.model, args.arm, args.seed, args.templates, args.device, args.outputs_dir, args.golden_xlsx, args.out,
           args.full_only)
    else:
        judge(args.engine_dir, args.rule_results, args.results, args.outputs_dir)


if __name__ == "__main__":
    main()

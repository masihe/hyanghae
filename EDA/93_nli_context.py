"""①단계 context(성별·계절·낮밤)를 한국어 NLI 모델로 학습 없이 판정한다 — 48번.

41~47번에서 작은 방식(인코더 · 작은 LLM)이 공통으로 진 곳은 "말하지 않은 문장에 조건을 붙이지 않기"(정밀도)였다.
NLI 는 학습 때부터 '알 수 없음(neutral)' 을 따로 배운다 — 말하지 않았으면 조건을 붙이지 않을 것으로 기대하고 잰다.

방법 (측정 전 고정 · 사용자 결정)
    가설    칸마다 한 문장 (HYPOTHESES). 결과를 보고 고치지 않는다
    판정    (사용자 문장, 가설) 의 세 라벨 중 entailment 가 가장 높으면 그 값을 붙인다. 문턱 없음. 값마다 따로(여러 값 가능)
    모델    kornli-roberta = pongjin/roberta_with_kornli (klue/roberta-base + KorNLI) ·
            mdeberta-2mil7 = MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7 (ko 기계번역 NLI 포함)
    입력    pongjin 카드의 변환 코드는 문장 목록을 글자로 끼워 넣는 버그가 있어 쓰지 않는다. 두 문장 짝 입력(pair)과
            sep 토큰으로 이어 붙이기(sep) 중 관문에서 맞는 쪽을 쓴다

판정 기준 (측정 전 고정)
    규칙을 넘음        엔진(391 · 추정 끔 · context 만) 확장 NDCG 가 규칙 context 만(0.690193) 대비 95% 구간이 0 보다 위
    정밀도 문제를 풂   합성 600 에서 GMS 판정 대비 정밀도가 규칙 이상 (성별 0.88 · 계절 0.98 · 낮밤 0.95 · 42번)
    관문               KLUE-NLI dev 3,000쌍 정확도 >= 0.70 (입력 형식이 맞는지. 우연 0.33)

사용법 (결과와 해석은 docs/nlr_engineering_notes.md 48번)
    gate --model M --klue-parquet P
    predict --model M --encoding pair|sep --out C.json          (88 contexts 형식 · 합성 · 설문 · Golden)
    score-golden --contexts C.json...
    latency --model M --encoding pair|sep
    엔진 · 설문 · 닮음은 88 run · evaluate 를 그대로 쓴다
"""
import argparse
import importlib.util
import json
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
DEFAULT_OUTPUTS = HERE / "analysis_outputs"
MODELS = {"kornli-roberta": "pongjin/roberta_with_kornli",
          "mdeberta-2mil7": "MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7"}
HYPOTHESES = {
    "season": {"spring": "이 사람은 봄에 쓸 향수를 원한다.", "summer": "이 사람은 여름에 쓸 향수를 원한다.",
               "autumn": "이 사람은 가을에 쓸 향수를 원한다.", "winter": "이 사람은 겨울에 쓸 향수를 원한다."},
    "daypart": {"day": "이 사람은 낮에 쓸 향수를 원한다.", "night": "이 사람은 밤에 쓸 향수를 원한다."},
    "gender": {"male": "이 사람은 남성용 향수를 원한다.", "female": "이 사람은 여성용 향수를 원한다.",
               "neuter": "이 사람은 남녀 공용 향수를 원한다."},
}
PAIRS = [(f, v, h) for f, vals in HYPOTHESES.items() for v, h in vals.items()]
MAX_LEN = 256
GATE_MIN = 0.70


def load_mod(name, path):
    """파일 경로의 모듈을 불러온다. module."""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(Path(path).parent))
    spec.loader.exec_module(module)
    return module


class Nli:
    """NLI 모델 하나. (전제, 가설) 짝마다 세 라벨 확률을 낸다."""

    def __init__(self, model_key, device, encoding):
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer
        if encoding not in ("pair", "sep"):
            raise ValueError(f"encoding 은 pair 또는 sep: {encoding}")
        self.tok = AutoTokenizer.from_pretrained(MODELS[model_key])
        # transformers 5.x 는 체크포인트 자료형을 그대로 쓴다 — mDeBERTa 는 float16 으로 저장돼 있어 48번 첫 측정은 float16 이었다
        self.model = AutoModelForSequenceClassification.from_pretrained(MODELS[model_key], dtype=torch.float32).to(device).eval()
        label2id = {k.lower(): v for k, v in self.model.config.label2id.items()}
        if set(label2id) != {"entailment", "neutral", "contradiction"}:
            raise ValueError(f"라벨이 NLI 세 개가 아니다: {self.model.config.label2id}")
        self.idx = label2id
        self.device = device
        self.encoding = encoding
        self.torch = torch

    def probs(self, premises, hypotheses, batch=64):
        """짝마다 [entailment, neutral, contradiction] 확률. np.ndarray (n, 3)."""
        out = []
        order = [self.idx["entailment"], self.idx["neutral"], self.idx["contradiction"]]
        for i in range(0, len(premises), batch):
            p, h = premises[i:i + batch], hypotheses[i:i + batch]
            if self.encoding == "pair":
                enc = self.tok(p, h, truncation="only_first", max_length=MAX_LEN, padding=True, return_tensors="pt")
            else:
                enc = self.tok([f"{a} {self.tok.sep_token} {b}" for a, b in zip(p, h)], truncation=True,
                               max_length=MAX_LEN, padding=True, return_tensors="pt")
            # klue/roberta 는 type_vocab_size 1 이라 짝 입력의 token_type_ids(두 번째 문장 = 1)가 범위를 넘는다
            use_types = self.encoding == "pair" and getattr(self.model.config, "type_vocab_size", 0) > 1
            enc = {k: v.to(self.device) for k, v in enc.items() if k != "token_type_ids" or use_types}
            with self.torch.no_grad():
                logits = self.model(**enc).logits.float()
            out.append(self.torch.softmax(logits, -1)[:, order].cpu().numpy())
        return np.concatenate(out)

    def context(self, sentences):
        """문장마다 context. list[dict[field, sorted list[str]]] — entailment 가 세 라벨 중 가장 높은 값만."""
        prem = [s for s in sentences for _ in PAIRS]
        hyp = [h for _ in sentences for _, _, h in PAIRS]
        pr = self.probs(prem, hyp).reshape(len(sentences), len(PAIRS), 3)
        res = []
        for row in pr:
            ctx = {f: [] for f in HYPOTHESES}
            for (f, v, _), p in zip(PAIRS, row):
                if p.argmax() == 0:
                    ctx[f].append(v)
            res.append({f: sorted(vs) for f, vs in ctx.items()})
        return res


def gate(model_key, klue_parquet, device):
    """관문 — KLUE-NLI dev 정확도를 두 입력 방식으로 잰다. None."""
    import pyarrow.parquet as pq
    rows = pq.read_table(klue_parquet).to_pylist()
    names = ["entailment", "neutral", "contradiction"]      # parquet 메타데이터의 ClassLabel 순서 (확인함)
    gold = np.array([r["label"] for r in rows])
    for enc in ("pair", "sep"):
        nli = Nli(model_key, device, enc)
        pred = nli.probs([r["premise"] for r in rows], [r["hypothesis"] for r in rows]).argmax(1)
        acc = float((pred == gold).mean())
        per = {names[k]: round(float((pred[gold == k] == k).mean()), 3) for k in range(3)}
        verdict = "통과" if acc >= GATE_MIN else "미달"
        print(f"[{model_key} · {enc}] KLUE-NLI dev {len(rows)}쌍 정확도 {acc:.4f} ({verdict} · 기준 {GATE_MIN}) · 라벨별 재현율 {per}")


def predict(model_key, encoding, device, outputs_dir, golden_xlsx, out_path):
    """합성 · 설문 · Golden 문장의 context 를 88 contexts 형식으로 저장한다. None."""
    x88 = load_mod("exp88", HERE / "88_embedding_stage1_context.py")
    x87 = x88.load_87()
    evalq, _, golden = x88.eval_sets(x87, outputs_dir, golden_xlsx)
    items = evalq + golden
    nli = Nli(model_key, device, encoding)
    t0 = time.perf_counter()
    ctxs = nli.context([q["sentence"] for q in items])
    ctx = {q["query_id"]: c for q, c in zip(items, ctxs)}
    meta = {"method": "nli", "model": model_key, "encoding": encoding, "hypotheses": HYPOTHESES, "contexts": ctx}
    Path(out_path).write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    counts = {}
    for q in evalq:
        for f, vs in ctx[q["query_id"]].items():
            for v in vs:
                counts[f"{f}:{v}"] = counts.get(f"{f}:{v}", 0) + 1
    print(f"nli {model_key} ({encoding}) -> {out_path} · {len(items)}문장 · {time.perf_counter() - t0:.0f}초")
    print("  합성+설문 예측 분포", dict(sorted(counts.items())))


def score_golden(contexts_paths, outputs_dir, golden_xlsx):
    """Golden 200 성별 · 계절 F1 — 89 score_golden(노트북 25 채점기) 으로 context 만. None."""
    x88 = load_mod("exp88", HERE / "88_embedding_stage1_context.py")
    x89 = load_mod("exp89", HERE / "89_finetune_stage1.py")
    golden = x89.load_golden_full(x89.DEFAULT_GOLDEN)
    alias = x89.load_alias(outputs_dir)
    rule = x88.RuleParser(Path(outputs_dir) / x88.RULE_LEXICON)
    rows = [("rule(88)", {g["query_id"]: x88.norm_ctx(rule.context(g["sentence"])) for g in golden})]
    llm = x89.load_system_preds(outputs_dir, "llm")
    rows.insert(0, ("GMS LLM", {g["query_id"]: x88.norm_ctx(llm[g["query_id"]]["context"]) for g in golden}))
    for p in contexts_paths:
        d = json.loads(Path(p).read_text(encoding="utf-8"))
        rows.append((f"nli-{d['model']} ({d['encoding']})", d["contexts"]))
    print("Golden 200 · 정답이 있는 문장 한정 micro F1 (P / R) · 노트북 25 전체 층")
    for name, ctx in rows:
        preds = {g["query_id"]: {"context": ctx[g["query_id"]], "avoid": [], "additional": []} for g in golden}
        r = x89.score_golden(golden, preds, alias)
        cells = " · ".join(f"{f} {r[f]['f1']:.3f} ({r[f]['precision']:.2f}/{r[f]['recall']:.2f})" for f in ("gender", "season"))
        print(f"  {name:28s} {cells}")


def latency(model_key, encoding, outputs_dir, n=20):
    """CPU fp32 로 설문 앞 n 문장을 하나씩(가설 9개를 한 묶음). 지연 · RSS. None."""
    import psutil
    x87 = load_mod("exp87", HERE / "87_embedding_vs_engine.py")
    proc = psutil.Process()
    rss0 = proc.memory_info().rss / 2**20
    nli = Nli(model_key, "cpu", encoding)
    rss1 = proc.memory_info().rss / 2**20
    texts = [q["sentence"] for q in x87.load_survey(outputs_dir)][:n]
    nli.context(["워밍업"])
    times = []
    for t in texts:
        t0 = time.perf_counter()
        nli.context([t])
        times.append(time.perf_counter() - t0)
    print(f"[{model_key} · {encoding} · CPU fp32] RSS 시작 {rss0:.0f} -> 모델 {rss1:.0f}MB · "
          f"문장당 중앙 {np.median(times) * 1000:.0f}ms · p95 {np.percentile(times, 95) * 1000:.0f}ms · 최대 {max(times) * 1000:.0f}ms")


def main(argv=None):
    """명령행 진입점."""
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--outputs-dir", default=str(DEFAULT_OUTPUTS))
    p.add_argument("--golden-xlsx", default=str(HERE / "evaluation_data" / "stage1" / "13_stage1_golden_set_v1_200.xlsx"))
    sub = p.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("gate")
    g.add_argument("--model", required=True, choices=sorted(MODELS))
    g.add_argument("--klue-parquet", required=True)
    g.add_argument("--device", default="cuda")
    a = sub.add_parser("predict")
    a.add_argument("--model", required=True, choices=sorted(MODELS))
    a.add_argument("--encoding", required=True, choices=["pair", "sep"])
    a.add_argument("--device", default="cuda")
    a.add_argument("--out", required=True)
    s = sub.add_parser("score-golden")
    s.add_argument("--contexts", nargs="+", required=True)
    lt = sub.add_parser("latency")
    lt.add_argument("--model", required=True, choices=sorted(MODELS))
    lt.add_argument("--encoding", required=True, choices=["pair", "sep"])
    args = p.parse_args(argv)
    if args.cmd == "gate":
        gate(args.model, args.klue_parquet, args.device)
    elif args.cmd == "predict":
        predict(args.model, args.encoding, args.device, args.outputs_dir, args.golden_xlsx, args.out)
    elif args.cmd == "score-golden":
        score_golden(args.contexts, args.outputs_dir, args.golden_xlsx)
    else:
        latency(args.model, args.encoding, args.outputs_dir)


if __name__ == "__main__":
    main()

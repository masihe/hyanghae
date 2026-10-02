"""파인튜닝한 ①단계 인코더(43번)를 torch 없이 ONNX Runtime 으로 돌리고 int8 로 줄였을 때 정확도·메모리·지연.

실험 1 (2026-09-29, 사용자 결정). 대상은 43번이 저장한 ko-sroberta seed 0 의 조각·분류 모델 두 개다.

세 벌을 같은 저장 모델에서 만든다
    torch   transformers + torch fp32 (기준)
    fp32    ONNX fp32  (torch.onnx.export)
    int8    ONNX 동적 양자화 (onnxruntime.quantization.quantize_dynamic · 가중치 QInt8)

판정 기준 — 측정 전에 고정했다
    fp32 는 torch 와 예측이 같아야 한다 — 조각 · context 문장 단위 일치 >= 99.5%. 아니면 변환 오류로 보고 멈춘다
    int8 정확도 유지 = 엔진(391 · 추정 끔) 확장 NDCG@5 의 torch 대비 차이 95% 구간이 0 을 포함하고 일치 >= 95%
    "서버에 들어간다" = 서빙 흉내 프로세스의 최종 RSS <= 실제 서버 값(사용자가 팀에 확인 중). 512MB 는 추정이다

서빙 흉내는 torch 를 import 하지 않는다 — onnxruntime + tokenizers + numpy 만 쓰고, 끝에 sys.modules 로 확인한다.
391 엔진 색인도 같은 프로세스에 올린다(실제 AI 서버가 한 프로세스다).

사용법 (결과와 해석은 docs/nlr_engineering_notes.md 44번)
    export  --model-dir <ft89_..._s0> --out-dir <onnx 폴더>
    predict --variant {torch,fp32,int8} --model-dir <torch 폴더> --onnx-dir <onnx 폴더> --out <예측.json>
    agree   --base <torch 예측> --new <예측>...
    probe   --variant {torch,fp32,int8} --model-dir ... --onnx-dir ... --engine-dir <391 ai>
"""
import argparse
import importlib.util
import json
import shutil
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
DEFAULT_OUTPUTS = HERE / "analysis_outputs"
MAX_LEN = 128        # 43번 학습 설정과 같다
PARTS = ("span", "ctx")


def load_mod(name, filename):
    """같은 폴더의 번호 붙은 스크립트를 모듈로 불러온다 (87 · 89 는 맨 위에서 torch 를 안 부른다). module."""
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def export(model_dir, out_dir):
    """torch 모델 두 개를 ONNX fp32 로 내보내고 int8 로 양자화한다. None."""
    import torch
    from onnxruntime.quantization import QuantType, quantize_dynamic
    from transformers import AutoModelForSequenceClassification, AutoModelForTokenClassification, AutoTokenizer
    out_dir = Path(out_dir)
    for part, cls in (("span", AutoModelForTokenClassification), ("ctx", AutoModelForSequenceClassification)):
        src = Path(model_dir) / part
        dst = out_dir / part
        dst.mkdir(parents=True, exist_ok=True)
        model = cls.from_pretrained(src).eval()
        tok = AutoTokenizer.from_pretrained(src)
        dummy = tok("가을에 쓸 남성적인 우드향", return_tensors="pt")
        fp32 = dst / "model_fp32.onnx"
        with torch.no_grad():
            torch.onnx.export(
                model, (dummy["input_ids"], dummy["attention_mask"]), str(fp32),
                input_names=["input_ids", "attention_mask"], output_names=["logits"],
                dynamic_axes={"input_ids": {0: "batch", 1: "seq"}, "attention_mask": {0: "batch", 1: "seq"},
                              "logits": {0: "batch"}},
                dynamo=False)
        int8 = dst / "model_int8.onnx"
        quantize_dynamic(str(fp32), str(int8), weight_type=QuantType.QInt8)
        shutil.copy(src / "tokenizer.json", dst / "tokenizer.json")
        (dst / "labels.json").write_text(json.dumps({"num_labels": model.config.num_labels}), encoding="utf-8")
        print(f"{part}: fp32 {fp32.stat().st_size / 2**20:.0f}MB · int8 {int8.stat().st_size / 2**20:.0f}MB "
              f"(torch 가중치 {(src / 'model.safetensors').stat().st_size / 2**20:.0f}MB)")


class OnnxPart:
    """ONNX 모델 하나 + tokenizers 토크나이저. torch 없이 돈다."""

    def __init__(self, part_dir, variant):
        import onnxruntime as ort
        from tokenizers import Tokenizer
        self.tok = Tokenizer.from_file(str(Path(part_dir) / "tokenizer.json"))
        self.tok.enable_truncation(MAX_LEN)
        self.tok.no_padding()
        opts = ort.SessionOptions()
        self.sess = ort.InferenceSession(str(Path(part_dir) / f"model_{variant}.onnx"), opts,
                                         providers=["CPUExecutionProvider"])

    def logits(self, text):
        """문장 하나의 logits 와 문자 offset. (np.ndarray, list[tuple])."""
        enc = self.tok.encode(text)
        ids = np.array([enc.ids], dtype=np.int64)
        mask = np.array([enc.attention_mask], dtype=np.int64)
        out = self.sess.run(["logits"], {"input_ids": ids, "attention_mask": mask})[0][0]
        offsets = [(s, e) if not special else (0, 0)
                   for (s, e), special in zip(enc.offsets, enc.special_tokens_mask)]
        return out, offsets


class Predictor:
    """세 벌 공통 예측기. span(text) -> dict · ctx(text) -> dict."""

    def __init__(self, variant, model_dir, onnx_dir):
        self.x89 = load_mod("exp89", "89_finetune_stage1.py")
        self.variant = variant
        if variant == "torch":
            from transformers import (AutoModelForSequenceClassification, AutoModelForTokenClassification,
                                      AutoTokenizer)
            self.sm = AutoModelForTokenClassification.from_pretrained(Path(model_dir) / "span").eval()
            self.st = AutoTokenizer.from_pretrained(Path(model_dir) / "span")
            self.cm = AutoModelForSequenceClassification.from_pretrained(Path(model_dir) / "ctx").eval()
            self.ct = AutoTokenizer.from_pretrained(Path(model_dir) / "ctx")
        else:
            self.span_part = OnnxPart(Path(onnx_dir) / "span", variant)
            self.ctx_part = OnnxPart(Path(onnx_dir) / "ctx", variant)

    def span(self, text):
        """원문 -> 조각. dict(avoid, additional)."""
        if self.variant == "torch":
            return self.x89.predict_span(self.sm, self.st, [text], "cpu")[0]
        logits, offsets = self.span_part.logits(text)
        return self.x89.decode_bio(text, offsets, logits.argmax(-1).tolist())

    def ctx(self, text):
        """원문 -> context. dict(gender, season, daypart)."""
        if self.variant == "torch":
            return self.x89.predict_ctx(self.cm, self.ct, [text], "cpu")[0]
        logits, _ = self.ctx_part.logits(text)
        prob = 1.0 / (1.0 + np.exp(-logits))
        out = {"gender": [], "season": [], "daypart": []}
        for (f, lab), p in zip(self.x89.CTX_LABELS, prob):
            if p >= 0.5:
                out[f].append(lab)
        return out


def predict(variant, model_dir, onnx_dir, outputs_dir, out_path):
    """합성 600 + 설문 143 을 한 벌로 예측해 89 e2e 와 같은 형식으로 저장한다. None."""
    x87 = load_mod("exp87", "87_embedding_vs_engine.py")
    queries = x87.load_synth(outputs_dir) + x87.load_survey(outputs_dir)
    pr = Predictor(variant, model_dir, onnx_dir)
    ctxs, spans = {}, {}
    for q in queries:
        c = pr.ctx(q["sentence"])
        ctxs[q["query_id"]] = {f: sorted(c.get(f, [])) for f in ("gender", "season", "daypart")}
        spans[q["query_id"]] = pr.span(q["sentence"])
    out = {"method": "onnx", "model": f"ko-sroberta-s0-{variant}", "contexts": ctxs, "spans": spans}
    Path(out_path).write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    print(f"{variant} -> {out_path} · 문장 {len(queries)} · torch 적재됨 {'torch' in sys.modules}")


def agree(base_path, new_paths):
    """예측끼리 문장 단위 일치율. None."""
    base = json.loads(Path(base_path).read_text(encoding="utf-8"))
    for p in new_paths:
        new = json.loads(Path(p).read_text(encoding="utf-8"))
        keys = list(base["contexts"])
        c = np.mean([base["contexts"][k] == new["contexts"][k] for k in keys])
        a = np.mean([base["spans"][k]["avoid"] == new["spans"][k]["avoid"] for k in keys])
        d = np.mean([base["spans"][k]["additional"] == new["spans"][k]["additional"] for k in keys])
        s = np.mean([base["spans"][k] == new["spans"][k] for k in keys])
        print(f"{Path(p).name:28s} vs {Path(base_path).name} · 문장 {len(keys)} · context {c:.2%} · "
              f"조각 전체 {s:.2%} (회피 {a:.2%} · 분위기 {d:.2%})")


def probe(variant, model_dir, onnx_dir, engine_dir, outputs_dir, n=50):
    """서빙 흉내 — 엔진 색인 + 인코더 두 개를 한 프로세스에 올려 단계별 RSS 와 지연을 잰다. None."""
    import psutil
    proc = psutil.Process()
    mb = lambda: proc.memory_info().rss / 2**20  # noqa: E731
    steps = [("시작", mb())]
    x87 = load_mod("exp87", "87_embedding_vs_engine.py")
    engine = x87.load_engine(engine_dir)
    engine.load_index()
    steps.append(("엔진 색인", mb()))
    t0 = time.perf_counter()
    pr = Predictor(variant, model_dir, onnx_dir)
    load_sec = time.perf_counter() - t0
    steps.append(("인코더 두 개", mb()))
    texts = [q["sentence"] for q in x87.load_survey(outputs_dir)[:n]]
    pr.span("워밍업")
    pr.ctx("워밍업")
    times = []
    for t in texts:
        t1 = time.perf_counter()
        pr.span(t)
        pr.ctx(t)
        times.append((time.perf_counter() - t1) * 1000)
    steps.append(("문장 50개 후", mb()))
    line = " -> ".join(f"{name} {v:.0f}MB" for name, v in steps)
    print(f"[{variant}] {line} · 인코더 적재 {load_sec:.1f}초 · torch 적재됨 {'torch' in sys.modules}")
    print(f"  문장 {n}개 (조각 + 분류) 중앙 {np.median(times):.1f}ms · p95 {np.percentile(times, 95):.1f}ms · "
          f"최대 {max(times):.1f}ms")


def main(argv=None):
    """명령행 진입점."""
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--outputs-dir", default=str(DEFAULT_OUTPUTS))
    sub = p.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("export")
    e.add_argument("--model-dir", required=True)
    e.add_argument("--out-dir", required=True)
    for name in ("predict", "probe"):
        a = sub.add_parser(name)
        a.add_argument("--variant", required=True, choices=["torch", "fp32", "int8"])
        a.add_argument("--model-dir", required=True)
        a.add_argument("--onnx-dir", required=True)
        if name == "predict":
            a.add_argument("--out", required=True)
        else:
            a.add_argument("--engine-dir", required=True)
    g = sub.add_parser("agree")
    g.add_argument("--base", required=True)
    g.add_argument("--new", nargs="+", required=True)
    args = p.parse_args(argv)
    if args.cmd == "export":
        export(args.model_dir, args.out_dir)
    elif args.cmd == "predict":
        predict(args.variant, args.model_dir, args.onnx_dir, args.outputs_dir, args.out)
    elif args.cmd == "agree":
        agree(args.base, args.new)
    else:
        probe(args.variant, args.model_dir, args.onnx_dir, args.engine_dir, args.outputs_dir)


if __name__ == "__main__":
    main()

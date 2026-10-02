"""작은 공개 LLM 을 학습 없이(zero-shot) ①단계 구조화에 써 본다 — GMS 와 같은 지시문 · 같은 해석기.

사용자 제안(2026-09-30): 임베딩 인코더 대신 Hugging Face 공개 LLM 을 우리 서버에서 돌리면 토큰 비용 · 외부 API 없이
LLM 의 지시 이해 능력을 쓸 수 있다. 역할은 둘 — 서비스에서 직접 ①단계 대체 / 오프라인 선생(인코더 학습 라벨).
먼저 학습 없이 얼마나 하는지 잰다.

모델 (사용자 결정 · 둘 다 Apache 2.0)
    qwen3-0.6b     Qwen/Qwen3-0.6B                          enable_thinking=False
    kanana-2.1b    kakaocorp/kanana-1.5-2.1b-instruct-2505

GMS 와 같게 한 것
    지시문 engine/ai/data/stage1_prompt_v1.txt 를 system 역할로(GMS 는 developer) · 사용자 문장은 llm_stage1.build_user_prompt
    응답 해석 · 형식 검사 = llm_stage1.parse_content · validate. 실패는 EMPTY_STAGE1 로 두고 센다
    greedy(do_sample=False — GMS 의 temperature 0) · max_new_tokens 256
GMS 와 다른 것 (하나)
    Qwen3 는 생각 모드를 꺼도 빈 <think></think> 가 나올 수 있어 해석 전에 그 태그만 걷는다

판정 기준 (측정 전 고정)
    GMS 수준     엔진 확장 NDCG(합성 600 · 391 · 추정 끔) 의 GMS LLM 전체 대비 95% 구간이 0 을 포함하거나 위
    규칙을 넘음   규칙 context 만(42번) 대비 95% 구간이 0 보다 위
    서비스 후보   규칙을 넘고 CPU 지연 중앙 <= 1.53초 (메모리는 실제 서버 값을 받은 뒤)
    선생 후보     Golden 성별 · 계절 F1 >= 규칙(0.919 · 1.000) 그리고 회피 F1 >= GMS LLM(0.493)
    관문          지시문 sha256 = 저장본 · greedy 결정성 · 형식 준수율 >= 90% (미달이면 그 모델은 멈추고 보고)

사용법 (결과와 해석은 docs/nlr_engineering_notes.md 47번)
    determinism --model M --engine-dir <391 ai>
    generate --model M --engine-dir <391 ai> --out G.json
    score-golden --gens G.json... · run --engine-dir <391 ai> --gen G.json --out R.json --contexts-out C.json
    cpu-probe --model M --engine-dir <391 ai>
"""
import argparse
import copy
import importlib.util
import json
import re
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
DEFAULT_OUTPUTS = HERE / "analysis_outputs"
MODELS = {"qwen3-0.6b": "Qwen/Qwen3-0.6B", "kanana-2.1b": "kakaocorp/kanana-1.5-2.1b-instruct-2505"}
MAX_NEW = 256
THINK = re.compile(r"<think>.*?</think>", re.DOTALL)


def load_mod(name, path):
    """파일 경로의 모듈을 불러온다. module."""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(Path(path).parent))
    spec.loader.exec_module(module)
    return module


def stage1_mod(engine_dir):
    """엔진 사본의 llm_stage1 (지시문 · 해석 · 검사). module."""
    return load_mod("llm_stage1_copy", Path(engine_dir) / "llm_stage1.py")


def all_items(outputs_dir):
    """Golden 200 · 합성 600 · 설문 143 문장. list[(qid, set, text)]."""
    x87 = load_mod("exp87", HERE / "87_embedding_vs_engine.py")
    x89 = load_mod("exp89", HERE / "89_finetune_stage1.py")
    items = [(g["query_id"], "golden", g["sentence"]) for g in x89.load_golden_full(x89.DEFAULT_GOLDEN)]
    items += [(q["query_id"], "synth", q["sentence"]) for q in x87.load_synth(outputs_dir)]
    items += [(q["query_id"], "survey", q["sentence"]) for q in x87.load_survey(outputs_dir)]
    return items


def allow_explicit_head_dim():
    """LlamaConfig 의 구조 검사를 head_dim 을 반영한 검사로 바꾼다. None.

    Kanana 설정은 hidden 1792 · head 24 · head_dim 128 로 head 폭을 따로 적는다(4.48 에서 만든 설정).
    5.17 의 검사는 head_dim 을 보지 않고 1792 % 24 만 봐서 막지만, 모델 본체(modeling_llama)는 head_dim 을 읽는다.
    검사 목록은 클래스를 만들 때 __class_validators__ 에 담기므로 그 항목을 바꿔 끼운다. 이 프로세스에서만 유효하다.
    """
    from transformers import LlamaConfig

    def validate_architecture(self):
        if self.head_dim is None and self.hidden_size % self.num_attention_heads != 0:
            raise ValueError(f"hidden {self.hidden_size} 이 head 수 {self.num_attention_heads} 로 나눠지지 않고 head_dim 도 없다")
        if self.num_attention_heads % self.num_key_value_heads != 0:
            raise ValueError(f"head {self.num_attention_heads} 가 kv head {self.num_key_value_heads} 로 나눠지지 않는다")

    names = [v.__name__ for v in LlamaConfig.__class_validators__]
    assert names.count("validate_architecture") == 1, names
    LlamaConfig.__class_validators__ = [validate_architecture if v.__name__ == "validate_architecture" else v
                                        for v in LlamaConfig.__class_validators__]


class Generator:
    """작은 LLM 하나로 ①단계 JSON 을 만든다."""

    def __init__(self, model_key, engine_dir, device):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        self.key = model_key
        self.st1 = stage1_mod(engine_dir)
        self.system = self.st1.load_prompt(Path(engine_dir) / "data" / "stage1_prompt_v1.txt")
        if model_key.startswith("kanana"):
            allow_explicit_head_dim()
        self.tok = AutoTokenizer.from_pretrained(MODELS[model_key], padding_side="left")
        if self.tok.pad_token is None:
            self.tok.pad_token = self.tok.eos_token
        dtype = torch.float32 if device == "cpu" else (torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16)
        self.model = AutoModelForCausalLM.from_pretrained(MODELS[model_key], dtype=dtype).to(device).eval()
        self.device = device

    def prompt(self, text):
        """채팅 템플릿을 적용한 입력 문자열. str."""
        messages = [{"role": "system", "content": self.system},
                    {"role": "user", "content": self.st1.build_user_prompt(text)}]
        kwargs = {"enable_thinking": False} if self.key.startswith("qwen3") else {}
        return self.tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=True, **kwargs)

    def generate(self, texts):
        """문장 묶음 -> 생성된 원문. list[str]."""
        import torch
        enc = self.tok([self.prompt(t) for t in texts], return_tensors="pt", padding=True).to(self.device)
        with torch.no_grad():
            out = self.model.generate(**enc, do_sample=False, max_new_tokens=MAX_NEW,
                                      pad_token_id=self.tok.pad_token_id)
        new = out[:, enc["input_ids"].shape[1]:]
        return [self.tok.decode(x, skip_special_tokens=True) for x in new]

    def parse(self, raw):
        """원문 -> (structured, 오류 코드 또는 None)."""
        cleaned = THINK.sub("", raw).strip()
        try:
            return self.st1.validate(self.st1.parse_content(cleaned)), None
        except self.st1.Stage1Error as exc:
            return copy.deepcopy(self.st1.EMPTY_STAGE1), exc.code


def determinism(model_key, engine_dir, outputs_dir, device, n=20, batch=8):
    """관문 2 — 같은 입력 두 번 · 묶음과 한 문장씩이 같은 출력인지. None."""
    gen = Generator(model_key, engine_dir, device)
    texts = [t for _, s, t in all_items(outputs_dir) if s == "synth"][:n]
    run1 = sum((gen.generate(texts[i:i + batch]) for i in range(0, n, batch)), [])
    run2 = sum((gen.generate(texts[i:i + batch]) for i in range(0, n, batch)), [])
    single = [gen.generate([t])[0] for t in texts]
    print(f"{model_key} · {n}문장 · 묶음 두 번 같음 {sum(a == b for a, b in zip(run1, run2))} · "
          f"묶음 = 한 문장씩 {sum(a == b for a, b in zip(run1, single))}")
    for a, b, t in zip(run1, single, texts):
        if a != b:
            print(f"  다름: {t[:40]}\n    묶음   {a[:120]!r}\n    한문장 {b[:120]!r}")
            break
    print(f"  예시 출력: {run1[0][:300]!r}")


def generate(model_key, engine_dir, outputs_dir, device, out_path, batch):
    """943문장을 생성해 저장한다. None."""
    gen = Generator(model_key, engine_dir, device)
    items = all_items(outputs_dir)
    result, t0 = {}, time.time()
    for i in range(0, len(items), batch):
        chunk = items[i:i + batch]
        raws = gen.generate([t for _, _, t in chunk]) if batch > 1 else [gen.generate([chunk[0][2]])[0]]
        for (qid, s, _), raw in zip(chunk, raws):
            structured, err = gen.parse(raw)
            result[qid] = {"set": s, "raw": raw, "error": err, "structured": structured}
        if (i // batch) % 10 == 0:
            print(f"  {i + len(chunk)}/{len(items)} · {time.time() - t0:.0f}초")
    sec = time.time() - t0
    Path(out_path).write_text(json.dumps({"model": model_key, "seconds": sec, "items": result},
                                         ensure_ascii=False), encoding="utf-8")
    errs = {}
    for v in result.values():
        errs[v["error"]] = errs.get(v["error"], 0) + 1
    ok = errs.get(None, 0)
    print(f"-> {out_path} · {len(result)}문장 · {sec:.0f}초({sec / len(result):.2f}초/문장) · "
          f"형식 준수 {ok}/{len(result)} ({ok / len(result):.1%}) · 오류 {errs}")


def score_golden(gen_paths, outputs_dir):
    """A — Golden 200 칸별 F1 (노트북 25 채점기 · 전체 층). None."""
    x88 = load_mod("exp88", HERE / "88_embedding_stage1_context.py")
    x89 = load_mod("exp89", HERE / "89_finetune_stage1.py")
    golden = x89.load_golden_full(x89.DEFAULT_GOLDEN)
    alias = x89.load_alias(outputs_dir)
    L = x89.LAYERS_FULL
    gold_scent = {}
    import pandas as pd
    df = pd.read_excel(x89.DEFAULT_GOLDEN, sheet_name="Golden Set", header=4, dtype=str, keep_default_na=False)
    for r in df.itertuples(index=False):
        gold_scent[r.query_id] = json.loads(r.gold_scent_preference)
    llm_scent = {}
    import csv
    with open(Path(outputs_dir) / x89.PRED_FILES["llm"], encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            llm_scent[r["query_id"]] = json.loads(r["pred_scent_preference"])

    def scent_f1(pred):
        gold = [gold_scent[g["query_id"]] for g in golden]
        p = [pred.get(g["query_id"], []) for g in golden]
        mask = np.asarray([bool(x89.dedupe_keys([x89.canonical_key(v, L, alias) for v in x])) for x in gold])
        return x89.evaluate_multilabel(gold, p, L, alias, mask)["f1"]

    rows = []
    for s in x89.PRED_FILES:
        preds = x89.load_system_preds(outputs_dir, s)
        rows.append((s, x89.score_golden(golden, preds, alias), scent_f1(llm_scent) if s == "llm" else None))
    rule = x88.RuleParser(Path(outputs_dir) / x88.RULE_LEXICON)
    rp = {g["query_id"]: {"context": rule.context(g["sentence"]), "avoid": [], "additional": []} for g in golden}
    rows.append(("rule(88) context 만", x89.score_golden(golden, rp, alias), None))
    for p in gen_paths:
        d = json.loads(Path(p).read_text(encoding="utf-8"))
        items = d["items"]
        # 엔진(_context_values)처럼 문자열 하나를 값 하나로 읽는다. 그대로 넘기면 채점기가 "winter" 를 글자로 쪼갠다
        preds = {g["query_id"]: {"context": x88.norm_ctx(items[g["query_id"]]["structured"].get("context")),
                                 "avoid": items[g["query_id"]]["structured"].get("avoid") or [],
                                 "additional": items[g["query_id"]]["structured"].get("additional_requirements") or []}
                 for g in golden}
        sp = {g["query_id"]: items[g["query_id"]]["structured"].get("scent_preference") or [] for g in golden}
        ok = sum(items[g["query_id"]]["error"] is None for g in golden)
        rows.append((f"{d['model']} (형식 {ok}/200)", x89.score_golden(golden, preds, alias), scent_f1(sp)))
    print("Golden 200 · 정답이 있는 문장 한정 micro F1 · 노트북 25 전체 층")
    print(f"  {'':28s} 회피 · 분위기 · 성별 · 계절 · 좋아하는 향 · 3칸 완전 일치")
    for name, r, sc in rows:
        scs = f"{sc:.3f}" if sc is not None else "  -  "
        print(f"  {name:28s} {r['avoid']['f1']:.3f} · {r['additional']['f1']:.3f} · {r['gender']['f1']:.3f} · "
              f"{r['season']['f1']:.3f} · {scs} · {r['three_exact']:.3f}")


def run(engine_dir, gen_path, outputs_dir, out_path, contexts_out):
    """B — 작은 LLM 의 전체 structured 를 391(추정 끔)에 넣는다. 88 evaluate 용 contexts 도 저장. None."""
    x87 = load_mod("exp87", HERE / "87_embedding_vs_engine.py")
    x88 = load_mod("exp88", HERE / "88_embedding_stage1_context.py")
    d = json.loads(Path(gen_path).read_text(encoding="utf-8"))
    engine = x87.load_engine(engine_dir)
    index = engine.load_index()
    queries = x87.load_synth(outputs_dir) + x87.load_survey(outputs_dir)
    result, ctx, status = {}, {}, {}
    for q in queries:
        s = d["items"][q["query_id"]]["structured"]
        rec = engine.recommend(index, q["sentence"], structured=s, top_k=x87.TOP_K, estimator=None)
        result[q["query_id"]] = {"status": rec["status"], "stage": rec["diagnostics"]["stage"],
                                 "ids": [r["perfume_id"] for r in rec["results"]]}
        ctx[q["query_id"]] = x88.norm_ctx(s.get("context"))
        k = ("합성" if q["arm"] != "S" else "설문", rec["status"])
        status[k] = status.get(k, 0) + 1
    Path(out_path).write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    Path(contexts_out).write_text(json.dumps({"method": "small-llm", "model": d["model"], "contexts": ctx},
                                             ensure_ascii=False), encoding="utf-8")
    print(f"-> {out_path} · {dict(sorted(status.items()))}")


def cpu_probe(model_key, engine_dir, outputs_dir, n=20):
    """C — CPU fp32 로 설문 앞 n 문장을 하나씩. 지연 · 생성 토큰 수 · RSS. None."""
    import psutil
    proc = psutil.Process()
    rss0 = proc.memory_info().rss / 2**20
    gen = Generator(model_key, engine_dir, "cpu")
    rss1 = proc.memory_info().rss / 2**20
    texts = [t for _, s, t in all_items(outputs_dir) if s == "survey"][:n]
    gen.generate(["워밍업"])
    times, ntok, oks = [], [], 0
    for t in texts:
        t0 = time.perf_counter()
        raw = gen.generate([t])[0]
        times.append(time.perf_counter() - t0)
        ntok.append(len(gen.tok(raw)["input_ids"]))
        oks += int(gen.parse(raw)[1] is None)
    rss2 = proc.memory_info().rss / 2**20
    print(f"[{model_key} · CPU fp32] RSS 시작 {rss0:.0f} -> 모델 {rss1:.0f} -> {n}문장 후 {rss2:.0f}MB · "
          f"문장당 중앙 {np.median(times):.2f}초 · p95 {np.percentile(times, 95):.2f}초 · 최대 {max(times):.2f}초 · "
          f"생성 토큰 중앙 {np.median(ntok):.0f} · 형식 준수 {oks}/{n}")


def main(argv=None):
    """명령행 진입점."""
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--outputs-dir", default=str(DEFAULT_OUTPUTS))
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("determinism", "generate", "cpu-probe"):
        a = sub.add_parser(name)
        a.add_argument("--model", required=True, choices=sorted(MODELS))
        a.add_argument("--engine-dir", required=True)
        if name != "cpu-probe":
            a.add_argument("--device", default="cuda")
        if name == "generate":
            a.add_argument("--out", required=True)
            a.add_argument("--batch", type=int, default=8)
    s = sub.add_parser("score-golden")
    s.add_argument("--gens", nargs="+", required=True)
    r = sub.add_parser("run")
    r.add_argument("--engine-dir", required=True)
    r.add_argument("--gen", required=True)
    r.add_argument("--out", required=True)
    r.add_argument("--contexts-out", required=True)
    args = p.parse_args(argv)
    if args.cmd == "determinism":
        determinism(args.model, args.engine_dir, args.outputs_dir, args.device)
    elif args.cmd == "generate":
        generate(args.model, args.engine_dir, args.outputs_dir, args.device, args.out, args.batch)
    elif args.cmd == "score-golden":
        score_golden(args.gens, args.outputs_dir)
    elif args.cmd == "run":
        run(args.engine_dir, args.gen, args.outputs_dir, args.out, args.contexts_out)
    else:
        cpu_probe(args.model, args.engine_dir, args.outputs_dir)


if __name__ == "__main__":
    main()

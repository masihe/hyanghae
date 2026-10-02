"""오타·띄어쓰기에 강한가 — 규칙 vs 파인튜닝 인코더(43번 · 45번)의 성별·계절·낮밤 판정.

사용자 지적(2026-09-29): 규칙은 우리가 만든 문장의 단어를 알고 만들어 평가가 유리하고, 오타에 약할 것이다.
합성 600 은 오타가 없고 생성 지시문 예시가 "여름에 쓸 건데 …" 라 계절을 단어로 말하는 문장이 많다.

오타 (30번 기록의 세 유형을 다시 구현 + 띄어쓰기 · 원 스크립트는 남아 있지 않다)
    keyboard  두벌식 같은 줄 좌우 자모로 한 자리 치환 (그 자리에 올 수 있는 자모만)
    vowel     ㅐ↔ㅔ · ㅚ/ㅙ/ㅞ · ㅓ↔ㅗ
    batchim   받침 탈락, 또는 {ㄴ·ㅇ·ㅁ} · {ㄱ·ㅋ·ㄲ} · {ㅅ·ㅆ·ㄷ·ㅌ} 안에서 바꿈
    spacing   두 어절 붙이기, 또는 어절 안에 공백 넣기

조건 (측정 전 고정)
    clean    원문
    rand10 · rand30   한글 어절마다 10% · 30% 확률로 네 유형 중 하나 · 난수 seed 20260929 · +1 · +2 세 벌
    target   규칙 사전이 원문에서 찾은 성별·계절·낮밤 단어마다 오타 한 번(띄어쓰기 제외) — 규칙은 구조상 진다

판정 기준 (측정 전 고정)
    "인코더가 오타에 더 강하다" = rand30 과 target 에서 인코더의 F1 하락폭(clean 대비)이 규칙보다 작고
    절대 F1 도 규칙보다 높다 — 인코더는 seed 3개 평균 · 성별 · 계절 따로
    정답 = 오타 없는 문장의 LLM 판정(합성 600). LLM 은 오타 문장을 못 잰다(저장본 없음 · GMS 없이)

사용법 (결과와 해석은 docs/nlr_engineering_notes.md 46번)
    perturb --out P.json · predict --perturbed P.json --model-dirs D... --out C.json · score --contexts C.json
    engine --engine-dir <391 ai> --perturbed P.json --contexts C.json
"""
import argparse
import collections
import importlib.util
import json
import random
import re
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
DEFAULT_OUTPUTS = HERE / "analysis_outputs"
SEED = 20260929
RATES = {"rand10": 0.10, "rand30": 0.30}
N_REPEAT = 3

CHO = list("ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ")
JUNG = list("ㅏㅐㅑㅒㅓㅔㅕㅖㅗㅘㅙㅚㅛㅜㅝㅞㅟㅠㅡㅢㅣ")
JONG = [""] + list("ㄱㄲㄳㄴㄵㄶㄷㄹㄺㄻㄼㄽㄾㄿㅀㅁㅂㅄㅅㅆㅇㅈㅊㅋㅌㅍㅎ")
KEY_ROWS = ["ㅂㅈㄷㄱㅅㅛㅕㅑㅐㅔ", "ㅁㄴㅇㄹㅎㅗㅓㅏㅣ", "ㅋㅌㅊㅍㅠㅜㅡ"]
VOWEL_CONFUSE = {"ㅐ": "ㅔ", "ㅔ": "ㅐ", "ㅓ": "ㅗ", "ㅗ": "ㅓ",
                 "ㅚ": "ㅙㅞ", "ㅙ": "ㅚㅞ", "ㅞ": "ㅚㅙ"}
BATCHIM_GROUPS = ["ㄴㅇㅁ", "ㄱㅋㄲ", "ㅅㅆㄷㅌ"]
HANGUL = re.compile(r"[가-힣]")


def split_syl(ch):
    """음절 -> (초, 중, 종) 자모. 한글 음절이 아니면 None."""
    code = ord(ch) - 0xAC00
    if not 0 <= code < 11172:
        return None
    return CHO[code // 588], JUNG[(code % 588) // 28], JONG[code % 28]


def join_syl(cho, jung, jong):
    """(초, 중, 종) -> 음절. str."""
    return chr(0xAC00 + CHO.index(cho) * 588 + JUNG.index(jung) * 28 + JONG.index(jong))


def key_neighbors(j):
    """두벌식 같은 줄 좌우 자모. list[str]."""
    for row in KEY_ROWS:
        i = row.find(j)
        if i >= 0:
            return [row[k] for k in (i - 1, i + 1) if 0 <= k < len(row)]
    return []


def typo_syllable(ch, kind, rng):
    """음절 하나에 오타 유형 하나. 적용할 수 없으면 None."""
    parts = split_syl(ch)
    if parts is None:
        return None
    cho, jung, jong = parts
    if kind == "keyboard":
        options = []
        for c in key_neighbors(cho):
            if c in CHO:
                options.append((c, jung, jong))
        for v in key_neighbors(jung):
            if v in JUNG:
                options.append((cho, v, jong))
        if jong:
            for t in key_neighbors(jong):
                if t in JONG:
                    options.append((cho, jung, t))
    elif kind == "vowel":
        options = [(cho, v, jong) for v in VOWEL_CONFUSE.get(jung, "")]
    elif kind == "batchim":
        if not jong:
            return None
        options = [(cho, jung, "")]
        for g in BATCHIM_GROUPS:
            if jong in g:
                options += [(cho, jung, t) for t in g if t != jong]
    else:
        raise ValueError(kind)
    if not options:
        return None
    return join_syl(*rng.choice(options))


def typo_in(text, start, end, kinds, rng):
    """text[start:end] 안의 한글 음절 하나에 kinds 중 적용되는 오타 하나. (새 text, 적용 여부)."""
    positions = [i for i in range(start, end) if HANGUL.match(text[i])]
    rng.shuffle(positions)
    kinds = list(kinds)
    rng.shuffle(kinds)
    for kind in kinds:
        for i in positions:
            new = typo_syllable(text[i], kind, rng)
            if new and new != text[i]:
                return text[:i] + new + text[i + 1:], True
    return text, False


def perturb_random(text, rate, rng):
    """한글 어절마다 rate 확률로 네 유형 중 하나. (새 text, 바뀐 어절 수, 한글 어절 수)."""
    words = text.split(" ")
    hangul_idx = [i for i, w in enumerate(words) if HANGUL.search(w)]
    changed = 0
    merge_after = set()
    for i in hangul_idx:
        if rng.random() >= rate:
            continue
        kind = rng.choice(["keyboard", "vowel", "batchim", "spacing"])
        if kind == "spacing":
            if i + 1 < len(words) and rng.random() < 0.5:
                merge_after.add(i)
                changed += 1
            elif len(words[i]) >= 2:
                cut = rng.randrange(1, len(words[i]))
                words[i] = words[i][:cut] + " " + words[i][cut:]
                changed += 1
            continue
        new, ok = typo_in(words[i], 0, len(words[i]), [kind], rng)
        if not ok:
            new, ok = typo_in(words[i], 0, len(words[i]), ["keyboard", "vowel", "batchim"], rng)
        words[i] = new
        changed += int(ok)
    out = []
    for i, w in enumerate(words):
        out.append(w)
        if i < len(words) - 1:
            out.append("" if i in merge_after else " ")
    return "".join(out), changed, len(hangul_idx)


def target_spans(text, rule):
    """규칙 사전이 찾는 성별·계절·낮밤 단어의 위치(한글만). list[(start, end)]."""
    spans = []
    for _, pattern in rule_gender_rules():
        spans += [m.span() for m in re.finditer(pattern, text)]
    for row in rule.rows:
        if row["feature_type"] in ("SEASON", "DAYPART") and HANGUL.search(row["surface_form"]):
            spans += [m.span() for m in re.finditer(re.escape(row["surface_form"]), text)]
    spans.sort()
    merged = []
    for s, e in spans:
        if merged and s < merged[-1][1]:
            merged[-1] = (merged[-1][0], max(e, merged[-1][1]))
        else:
            merged.append((s, e))
    return merged


def load_mod(name, filename):
    """같은 폴더의 번호 붙은 스크립트를 모듈로 불러온다. module."""
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def rule_gender_rules():
    """88 의 GENDER_RULES (노트북 14 원본). list."""
    return load_mod("exp88", "88_embedding_stage1_context.py").GENDER_RULES


def perturb(outputs_dir, out_path):
    """조건별 오타 문장을 만든다. {cond: {qid: text}} 를 저장. None."""
    x87 = load_mod("exp87", "87_embedding_vs_engine.py")
    x88 = load_mod("exp88", "88_embedding_stage1_context.py")
    rule = x88.RuleParser(Path(outputs_dir) / x88.RULE_LEXICON)
    synth = x87.load_synth(outputs_dir)
    out = {"clean": {q["query_id"]: q["sentence"] for q in synth}}
    for name, rate in RATES.items():
        for r in range(N_REPEAT):
            rng = random.Random(SEED + r)
            cond, changed, total = {}, 0, 0
            for q in synth:
                t, c, n = perturb_random(q["sentence"], rate, rng)
                cond[q["query_id"]] = t
                changed += c
                total += n
            out[f"{name}_s{r}"] = cond
            print(f"{name}_s{r}: 바뀐 한글 어절 {changed}/{total} ({changed / total:.1%}) · "
                  f"문장이 바뀐 비율 {np.mean([cond[k] != out['clean'][k] for k in cond]):.1%}")
    rng = random.Random(SEED)
    cond, hit, gone = {}, 0, 0
    for q in synth:
        t = q["sentence"]
        spans = target_spans(t, rule)
        for s, e in reversed(spans):
            t, _ = typo_in(t, s, e, ["keyboard", "vowel", "batchim"], rng)
        cond[q["query_id"]] = t
        if spans:
            hit += 1
            before, after = rule.context(q["sentence"]), rule.context(t)
            gone += int(any(before[f] and not after[f] for f in ("gender", "season", "daypart")))
    out["target"] = cond
    print(f"target: 규칙 단어가 있는 문장 {hit} · 그중 규칙이 원래 찾던 칸 하나 이상을 못 찾게 된 문장 {gone} ({gone / max(hit, 1):.1%})")
    Path(out_path).write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    ex = [k for k in out["target"] if out["target"][k] != out["clean"][k]][:4]
    for k in ex:
        print(f"  {out['clean'][k][:50]}\n  -> {out['target'][k][:50]}")
    print(f"-> {out_path}")


def predict(perturbed_path, model_dirs, outputs_dir, out_path, device):
    """규칙과 인코더로 조건별 context 를 판정한다. {method: {cond: {qid: ctx}}} 저장. None."""
    x88 = load_mod("exp88", "88_embedding_stage1_context.py")
    x89 = load_mod("exp89", "89_finetune_stage1.py")
    pert = json.loads(Path(perturbed_path).read_text(encoding="utf-8"))
    rule = x88.RuleParser(Path(outputs_dir) / x88.RULE_LEXICON)
    out = {"rule": {c: {k: x88.norm_ctx(rule.context(t)) for k, t in texts.items()} for c, texts in pert.items()}}
    from transformers import AutoModelForSequenceClassification, AutoTokenizer
    for d in model_dirs:
        model = AutoModelForSequenceClassification.from_pretrained(d).to(device).eval()
        tok = AutoTokenizer.from_pretrained(d)
        name = Path(d).name
        out[name] = {}
        for c, texts in pert.items():
            keys = list(texts)
            preds = x89.predict_ctx(model, tok, [texts[k] for k in keys], device)
            out[name][c] = {k: x88.norm_ctx(p) for k, p in zip(keys, preds)}
        print(f"  {name} 끝")
        del model
    Path(out_path).write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    print(f"-> {out_path}")


def cond_groups(conds):
    """조건 이름을 묶는다 — rand10_s0..s2 -> rand10. dict[group, list[cond]]."""
    groups = collections.OrderedDict()
    for c in conds:
        groups.setdefault(c.split("_s")[0] if c.startswith("rand") else c, []).append(c)
    return groups


def method_groups(methods):
    """방식 이름을 묶는다 — ctx91_ft45_s0..s2 -> ft45. dict[group, list[method]]."""
    groups = collections.OrderedDict()
    for m in methods:
        groups.setdefault(re.sub(r"^ctx91_|_s\d+$", "", m), []).append(m)
    return groups


def score(contexts_path, outputs_dir):
    """조건 × 방식의 F1(정답 = 원문 LLM 판정)과 흔들림. None."""
    x87 = load_mod("exp87", "87_embedding_vs_engine.py")
    x88 = load_mod("exp88", "88_embedding_stage1_context.py")
    ctx = json.loads(Path(contexts_path).read_text(encoding="utf-8"))
    llm = {q["query_id"]: x88.norm_ctx((q["structured"] or {}).get("context")) for q in x87.load_synth(outputs_dir)}
    keys = list(llm)
    conds = cond_groups(next(iter(ctx.values())).keys())
    print("정답 = 원문 문장의 LLM 판정 · 합성 600 · 라벨 micro F1 (규칙은 오타 seed 평균 · 인코더는 모델 seed × 오타 seed 평균)")
    print(f"  {'':8s} {'':10s} " + " · ".join(f"{g:>8s}" for g in conds) + " · 흔들림(clean 과 다른 문장)")
    for field in ("gender", "season", "daypart"):
        for mg, members in method_groups(ctx).items():
            vals, shake = [], []
            for g, cs in conds.items():
                f1s = []
                for m in members:
                    for c in cs:
                        f1s.append(x88.f1([(set(llm[k][field]), set(ctx[m][c][k][field])) for k in keys])[0])
                vals.append((np.mean(f1s), np.std(f1s)))
                if g != "clean":
                    shake.append(np.mean([np.mean([ctx[m][c][k][field] != ctx[m]["clean"][k][field] for k in keys])
                                          for m in members for c in cs]))
            cells = " · ".join(f"{v:.3f}" + (f"±{s:.3f}" if len(members) > 1 else "      ") for v, s in vals)
            print(f"  {field:8s} {mg:10s} {cells} · " + " · ".join(f"{x:.1%}" for x in shake))


def engine(engine_dir, perturbed_path, contexts_path, outputs_dir, conds_keep=("clean", "rand30", "target")):
    """엔진 확장 NDCG@5 — context 만 넣고 입력 문장은 오타 문장, 채점 조건은 원문 기준. None.

    참고선 llm-ref = LLM 의 원문 context 를 오타 문장과 함께 넣은 것(LLM 이 오타를 완벽히 알아들었다고 친 상한).
    """
    x87 = load_mod("exp87", "87_embedding_vs_engine.py")
    x88 = load_mod("exp88", "88_embedding_stage1_context.py")
    eng = x87.load_engine(engine_dir)
    index = eng.load_index()
    scorer = x87.Scorer(eng, index, x87.load_answer_key(outputs_dir))
    synth = x87.load_synth(outputs_dir)
    conds_of = {q["query_id"]: scorer.conditions(q) for q in synth}
    pert = json.loads(Path(perturbed_path).read_text(encoding="utf-8"))
    ctx = json.loads(Path(contexts_path).read_text(encoding="utf-8"))
    ctx["llm-ref"] = {c: {q["query_id"]: x88.norm_ctx((q["structured"] or {}).get("context")) for q in synth}
                      for c in pert}
    groups = {g: cs for g, cs in cond_groups(pert).items() if g in conds_keep}
    results = collections.defaultdict(dict)
    for m in ["llm-ref"] + [m for m in ctx if m != "llm-ref"]:
        for g, cs in groups.items():
            scores = []
            for c in cs:
                s = []
                for q in synth:
                    rec = eng.recommend(index, pert[c][q["query_id"]],
                                        structured=x88.empty_structured(ctx[m][c][q["query_id"]]),
                                        top_k=x87.TOP_K, estimator=None)
                    s.append(scorer.ndcg([r["perfume_id"] for r in rec["results"]], conds_of[q["query_id"]]))
                scores.append(s)
            results[m][g] = np.mean(scores, axis=0)
        print(f"  {m} 끝")
    print("\n엔진 확장 NDCG@5 (context 만 · 입력 = 오타 문장 · rand30 은 오타 seed 3벌 평균) — llm-ref 대비 [95%]")
    for g in groups:
        base = results["llm-ref"][g]
        print(f"  [{g}] llm-ref {base.mean():.6f}")
        for mg, members in method_groups([m for m in results if m != "llm-ref"]).items():
            parts = []
            for m in members:
                d, lo, hi = x87.paired_bootstrap(base, results[m][g])
                parts.append(f"{results[m][g].mean():.4f} ({d:+.4f} [{lo:+.4f}, {hi:+.4f}])")
            print(f"    {mg:8s} " + " · ".join(parts))


def main(argv=None):
    """명령행 진입점."""
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--outputs-dir", default=str(DEFAULT_OUTPUTS))
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("perturb")
    a.add_argument("--out", required=True)
    b = sub.add_parser("predict")
    b.add_argument("--perturbed", required=True)
    b.add_argument("--model-dirs", nargs="+", required=True)
    b.add_argument("--device", default="cuda")
    b.add_argument("--out", required=True)
    c = sub.add_parser("score")
    c.add_argument("--contexts", required=True)
    d = sub.add_parser("engine")
    d.add_argument("--engine-dir", required=True)
    d.add_argument("--perturbed", required=True)
    d.add_argument("--contexts", required=True)
    args = p.parse_args(argv)
    if args.cmd == "perturb":
        perturb(args.outputs_dir, args.out)
    elif args.cmd == "predict":
        predict(args.perturbed, args.model_dirs, args.outputs_dir, args.out, args.device)
    elif args.cmd == "score":
        score(args.contexts, args.outputs_dir)
    else:
        engine(args.engine_dir, args.perturbed, args.contexts, args.outputs_dir)


if __name__ == "__main__":
    main()

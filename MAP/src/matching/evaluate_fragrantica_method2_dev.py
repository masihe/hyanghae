"""Independent baseline/uroman/en-ko DEV retrieval; no verification or fusion.

Run: venv/Scripts/python.exe evaluate_fragrantica_method2_dev.py
Uses a predownloaded pinned public model; all inference is offline. Gold is used
only for evaluation after unlabeled query/candidate rankings are constructed.
"""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import platform
import re
import sys
import time
import unicodedata
from dataclasses import asdict
from difflib import SequenceMatcher
from pathlib import Path

os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

import pandas as pd
import uroman

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "korea"))
import build_korea_popularity_map as matcher
import evaluate_fragrantica_matcher_dev as baseline
from evaluate_fragrantica_method1_dev import normalize, table, validate_normalization

ROOT = Path(__file__).resolve().parents[2]  # MAP/
DATA = ROOT / "data/korea_popularity"
OUT = DATA / "evaluation"
CACHE = ROOT / "cache/method2"
PREFIX = "fragrantica_method2_dev"
MODEL = "feVeRin/enko-transliterator"
REVISION = "24b55c9bb8ab1f8682f8d8300c57340e2e0bcd66"
MODEL_DIR = CACHE / "model/models--feVeRin--enko-transliterator/snapshots" / REVISION
METHODS = ("baseline_lexical", "uroman", "enko_transliteration")
SETTINGS = {
    "model": MODEL, "revision": REVISION, "num_beams": 3, "max_length": 64,
    "do_sample": False, "batch_size": 16, "device": "cpu", "dtype": "float32",
    "seed": 42, "torch_threads": 4,
    "pool": "identical to baseline exact-brand and original form/concentration filters; no ranking preselection",
    "normalization": "Method1 normalize() reused symmetrically on raw members and candidate name, complete leading raw brand only",
    "uroman_language_hint": None,
    "uroman_comparison": "casefold, alphanumeric only, SequenceMatcher(query,candidate,autojunk=False).ratio()",
    "enko_comparison": "NFD canonical Hangul jamo, casefold, alphanumeric only, same SequenceMatcher ratio",
    "generation_input": "complete normalized candidate core in original spelling/case, no word-by-word splitting or translation",
    "non_latin_input": "preserved as-is; model limitations flagged, no uroman preprocessing in enko channel",
    "multi_member_aggregation": "max similarity across unique member cores within each channel",
    "ties": "score descending then Fragrantica ID descending",
    "empty_comparison": "score 0, keep candidate with diagnostic; do not drop or repair generation",
    "output_k": 10, "mrr": "full common candidate pool, absent gold rank contributes zero",
    "fusion": False, "fine_tuning": False,
}


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def comparison_key(text, jamo=False):
    text = unicodedata.normalize("NFD" if jamo else "NFKC", text).casefold()
    return "".join(c for c in text if c.isalnum())


def similarity(query, candidate):
    if not query or not candidate:
        return 0.0
    return SequenceMatcher(None, query, candidate, autojunk=False).ratio()


def load_transliterator():
    import torch
    from peft import PeftModel
    from safetensors.torch import load_file
    from transformers import GenerationConfig, MarianConfig, MarianMTModel, MarianTokenizer

    torch.manual_seed(SETTINGS["seed"])
    torch.set_num_threads(SETTINGS["torch_threads"])
    torch.use_deterministic_algorithms(True)
    config = MarianConfig.from_pretrained(MODEL_DIR, local_files_only=True)
    # Explicit weights avoid automatic adapter redirect to another, unpinned repo.
    base = MarianMTModel.from_pretrained(None, config=config,
        state_dict=load_file(str(MODEL_DIR / "model.safetensors")), dtype=torch.float32)
    model = PeftModel.from_pretrained(base, MODEL_DIR, is_trainable=False, local_files_only=True).eval()
    model.generation_config = GenerationConfig.from_pretrained(MODEL_DIR, local_files_only=True)
    tokenizer = MarianTokenizer.from_pretrained(MODEL_DIR, local_files_only=True)
    return model, tokenizer


def transliterate(cores):
    """Persistent cache by exact core and model/decoding settings, never by Gold ID."""
    import torch

    started = time.perf_counter()
    generation_settings = {k: SETTINGS[k] for k in (
        "model", "revision", "num_beams", "max_length", "do_sample", "batch_size", "device", "dtype", "seed")}
    generation_settings["versions"] = {p: importlib.metadata.version(p) for p in ("torch", "transformers", "peft", "sentencepiece")}
    signature = hashlib.sha256(json.dumps(generation_settings, sort_keys=True).encode()).hexdigest()
    path = CACHE / f"transliterations_{signature}.json"
    content = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {
        "settings": generation_settings, "entries": {}, "generation_seconds": 0.0}
    assert content["settings"] == generation_settings
    entries = content["entries"]
    missing = sorted(set(cores) - entries.keys())
    new_count = len(missing)
    cache_hits = len(set(cores)) - new_count
    if missing:
        model, tokenizer = load_transliterator()
        for start in range(0, len(missing), SETTINGS["batch_size"]):
            batch_started = time.perf_counter()
            batch = missing[start:start + SETTINGS["batch_size"]]
            active = []
            for core in batch:
                length = len(tokenizer(core)["input_ids"])
                if not core.strip():
                    entries[core] = {"text": "", "status": "EMPTY_CORE", "input_tokens": length}
                elif length > model.config.max_position_embeddings:
                    entries[core] = {"text": "", "status": "INPUT_TOO_LONG", "input_tokens": length}
                else:
                    active.append(core)
            if active:
                inputs = tokenizer(active, return_tensors="pt", padding=True, truncation=False)
                with torch.inference_mode():
                    outputs = model.generate(**inputs, max_length=SETTINGS["max_length"],
                        num_beams=SETTINGS["num_beams"], do_sample=False)
                decoded = tokenizer.batch_decode(outputs, skip_special_tokens=True)
                for core, text, tokens in zip(active, decoded, outputs.tolist()):
                    # forced_eos_token_id may force termination at the length limit.
                    eos = tokens.index(tokenizer.eos_token_id) if tokenizer.eos_token_id in tokens else len(tokens)
                    status = "MAX_LENGTH_REACHED" if eos >= SETTINGS["max_length"]-1 else "OK"
                    if not text.strip():
                        status = "EMPTY_OUTPUT"
                    entries[core] = {"text": text, "status": status,
                        "input_tokens": len(tokenizer(core)["input_ids"]), "output_tokens_before_eos": eos}
            content["generation_seconds"] += time.perf_counter() - batch_started
            dump(path, content)  # Preserve completed generations if a later batch fails.
            if start % (SETTINGS["batch_size"] * 10) == 0:
                print(f"Transliterated {min(start+len(batch),len(missing))}/{len(missing)} new cores", flush=True)
    return entries, {"cache_hits": cache_hits, "generated_cores": new_count,
        "stage_seconds": time.perf_counter()-started,
        "cached_generation_seconds": content["generation_seconds"], "cache_path": str(path.relative_to(ROOT)),
        "cache_sha256": matcher.sha256(path) if path.exists() else ""}


def rank_channel(queries, pool, candidate_keys):
    scored = []
    for perfume_id in pool:
        options = [(similarity(qkey, candidate_keys[perfume_id]), q) for q, qkey in queries]
        score, query = max(options, default=(0.0, ""))
        scored.append((score, perfume_id, query))
    scored.sort(key=lambda item: (-item[0], -item[1]))
    return scored


def prepare_rankings(commercial, members, perfumes, identity_ids):
    times = {}
    started = time.perf_counter()
    brand_groups = {matcher.latin_key(b): g for b, g in perfumes.groupby("brand", sort=False) if matcher.latin_key(b)}
    catalog = perfumes.set_index("id", drop=False)
    inputs, rankings, candidate_ids = {}, {}, set()
    validate_normalization()
    assert comparison_key("가든", True) == "가든"
    assert similarity("", "") == 0.0
    for ci in identity_ids:
        row = commercial.loc[ci]
        mem = members[members.commercial_identity_id.eq(ci)]
        assert len(mem) == int(row.member_count)
        representations = [normalize(m.product_name_raw, m.brand_raw, row.canonical_brand)
                           for m in mem.itertuples(index=False)]
        cores = sorted({item.core_name for item in representations if item.core_name})
        result = baseline.retrieve_candidates(row, brand_groups.get(matcher.latin_key(row.canonical_brand), pd.DataFrame()))
        pool = [item[1] for item in result]
        candidate_ids.update(pool)
        rankings[ci] = {"baseline_lexical": [(score, i, row.fragrance_name_normalized) for score, i, _ in result]}
        inputs[ci] = {"raw_names": mem.product_name_raw.tolist(), "query_cores": cores, "pool": pool,
            "representations": [asdict(item) for item in representations],
            "source_refs": [f"{m.source}:{m.source_rank}:{m.source_product_id}" for m in mem.itertuples(index=False)]}
    times["baseline_and_query_normalization_seconds"] = time.perf_counter()-started
    started = time.perf_counter()
    romanizer = uroman.Uroman()
    all_cores = {i: normalize(catalog.at[i, "name"], catalog.at[i, "brand"], catalog.at[i, "brand"]).core_name
                 for i in sorted(candidate_ids)}
    roman_text = {text: romanizer.romanize_string(text) for text in sorted(
        set(all_cores.values()) | {q for info in inputs.values() for q in info["query_cores"]})}
    roman_keys = {i: comparison_key(roman_text[core]) for i, core in all_cores.items()}
    for ci, info in inputs.items():
        info["uroman_queries"] = [roman_text[q] for q in info["query_cores"]]
        info["jamo_queries"] = [comparison_key(q, True) for q in info["query_cores"]]
        rankings[ci]["uroman"] = rank_channel(
            [(q, comparison_key(roman_text[q])) for q in info["query_cores"]], info["pool"], roman_keys)
    times["uroman_normalization_and_ranking_seconds"] = time.perf_counter()-started
    print(f"Prepared {len(inputs)} identities; {len(candidate_ids)} unique candidate IDs / {len(set(all_cores.values()))} unique cores", flush=True)
    translations, cache_info = transliterate(all_cores.values())
    times["transliteration_generation"] = cache_info
    started = time.perf_counter()
    korean_keys = {i: comparison_key(translations[core]["text"], True) for i, core in all_cores.items()}
    for ci, info in inputs.items():
        rankings[ci]["enko_transliteration"] = rank_channel(
            list(zip(info["query_cores"], info["jamo_queries"])), info["pool"], korean_keys)
        for ranking in rankings[ci].values():
            assert set(item[1] for item in ranking) == set(info["pool"])
            assert len(ranking) == len(info["pool"])
    candidates = pd.DataFrame([dict(fragrantica_id=i, name=catalog.at[i, "name"], brand=catalog.at[i, "brand"],
        core=core, uroman=roman_text[core], uroman_comparison=roman_keys[i],
        korean_transliteration=translations[core]["text"], jamo_comparison=korean_keys[i],
        generation_status=translations[core]["status"], input_tokens=translations[core]["input_tokens"],
        non_ascii_core=bool(re.search(r"[^\x00-\x7F]", core))) for i, core in all_cores.items()])
    times["enko_jamo_ranking_seconds"] = time.perf_counter()-started
    return inputs, rankings, candidates, times


def evaluate(gold, inputs, rankings, candidates, perfumes):
    """Labels enter here; no Gold field is passed to any retrieval/generation function."""
    old_results = pd.read_csv(baseline.RESULTS_PATH, keep_default_na=False).set_index("commercial_identity_id")
    catalog = perfumes.set_index("id", drop=False)
    ctable = candidates.set_index("fragrantica_id")
    records = []
    for g in gold.itertuples(index=False):
        ci = g.commercial_identity_id
        info = inputs[ci]
        original = rankings[ci]["baseline_lexical"]
        ids = [item[1] for item in original]
        gid = int(g.gold_fragrantica_id) if g.gold_status == "MATCH" else None
        base_rank = ids.index(gid)+1 if gid in ids else None
        stored = old_results.loc[ci]
        assert stored.retrieval_top5_ids == "|".join(map(str, ids[:5]))
        expected_rank = int(float(stored.gold_candidate_rank)) if stored.gold_candidate_rank != "" else None
        assert base_rank == expected_rank
        status = "NOT_APPLICABLE"
        if gid is not None:
            if gid not in catalog.index:
                status = "CATALOG_MISSING"
            elif gid in ids:
                status = "IN_CANDIDATE_POOL"
            elif matcher.latin_key(catalog.at[gid, "brand"]) != matcher.latin_key(stored.canonical_brand):
                status = "BRAND_BLOCKED"
            else:
                status = "CONCENTRATION_OR_FORM_FILTER"
        for method in METHODS:
            ranking = rankings[ci][method]
            ranked_ids = [item[1] for item in ranking]
            rank = ranked_ids.index(gid)+1 if gid in ranked_ids else None
            top = [dict(rank=position, id=i, score=score, name=ctable.at[i, "name"],
                core=ctable.at[i, "core"], korean_transliteration=ctable.at[i, "korean_transliteration"],
                uroman=ctable.at[i, "uroman"], matched_query=q)
                for position, (score, i, q) in enumerate(ranking[:10], 1)]
            record = dict(queue_id=g.queue_id, commercial_identity_id=ci, method=method,
                sample_group=g.sample_group, challenge_type=g.challenge_type,
                population_stratum=g.population_stratum, gold_status=g.gold_status,
                raw_product_names=json.dumps(info["raw_names"], ensure_ascii=False),
                query_cores=json.dumps(info["query_cores"], ensure_ascii=False),
                query_uroman=json.dumps(info["uroman_queries"], ensure_ascii=False),
                query_jamo=json.dumps(info["jamo_queries"], ensure_ascii=False),
                source_refs=json.dumps(info["source_refs"], ensure_ascii=False),
                gold_fragrantica_id=gid, gold_fragrantica_name=g.gold_fragrantica_name,
                catalog_status=status, catalog_retrievable=gid in catalog.index if gid else False,
                candidate_count=len(ranking), baseline_rank=base_rank, gold_candidate_rank=rank,
                reciprocal_rank=1/rank if rank else 0,
                gold_core=ctable.at[gid, "core"] if gid in ctable.index else "",
                gold_uroman=ctable.at[gid, "uroman"] if gid in ctable.index else "",
                gold_transliteration=ctable.at[gid, "korean_transliteration"] if gid in ctable.index else "",
                top10_ids="|".join(map(str, ranked_ids[:10])),
                top10_candidates=json.dumps(top, ensure_ascii=False))
            for k in (5, 10):
                old_hit, new_hit = base_rank is not None and base_rank <= k, rank is not None and rank <= k
                record[f"rescue_at_{k}"] = gid is not None and not old_hit and new_hit
                record[f"regression_at_{k}"] = gid is not None and old_hit and not new_hit
            records.append(record)
    return pd.DataFrame(records)


def measure(results):
    metrics = []
    matches = results[results.gold_status.eq("MATCH")]
    for scope, cohort in (("ALL_GOLD_MATCH", matches), ("CATALOG_RETRIEVABLE", matches[matches.catalog_retrievable])):
        for method, frame in cohort.groupby("method", sort=False):
            groups = [("OVERALL", "ALL", frame)]
            groups += [("SAMPLE_GROUP", k, sub) for k, sub in frame.groupby("sample_group")]
            groups += [("CHALLENGE_TYPE", k, sub) for k, sub in frame[frame.sample_group.eq("CHALLENGE")].groupby("challenge_type")]
            for level, group, sub in groups:
                ranks, old = sub.gold_candidate_rank, sub.baseline_rank
                row = dict(scope=scope, method=method, level=level, group=group, gold_match=len(sub),
                    catalog_missing=int(sub.catalog_status.eq("CATALOG_MISSING").sum()),
                    in_candidate_pool=int(sub.catalog_status.eq("IN_CANDIDATE_POOL").sum()),
                    mrr=float(sub.reciprocal_rank.mean()),
                    mrr_at_10=float(sub.reciprocal_rank.where(ranks.le(10), 0).mean()))
                row.update({f"recall_at_{k}": float(ranks.le(k).mean()) for k in (1, 3, 5, 10)})
                for k in (5, 10):
                    row[f"top{k}_miss"] = int((~ranks.le(k)).sum())
                    row[f"rescue_at_{k}"] = int(sub[f"rescue_at_{k}"].sum())
                    row[f"regression_at_{k}"] = int(sub[f"regression_at_{k}"].sum())
                    row[f"baseline_top{k}_miss"] = int((~old.le(k)).sum())
                    row[f"baseline_top{k}_hit"] = int(old.le(k).sum())
                    assert int(ranks.le(k).sum()) == int(old.le(k).sum()) + row[f"rescue_at_{k}"] - row[f"regression_at_{k}"]
                metrics.append(row)
    return pd.DataFrame(metrics)


def write_report(results, metrics, candidates, times, hashes):
    metric_cols = ["method", "group", "gold_match", "recall_at_1", "recall_at_3", "recall_at_5", "recall_at_10", "mrr", "mrr_at_10", "top5_miss", "top10_miss"]
    rescue_cols = ["method", "group", "gold_match", "baseline_top5_miss", "rescue_at_5", "baseline_top5_hit", "regression_at_5", "baseline_top10_miss", "rescue_at_10", "baseline_top10_hit", "regression_at_10"]
    base = results[results.method.eq("baseline_lexical") & results.gold_status.eq("MATCH")]
    missing = base[base.catalog_status.eq("CATALOG_MISSING")]
    lines = ["# Method 2: independent pronunciation/transliteration DEV retrieval", "",
        "## 설계와 범위", "",
        f"- DEV 80행 중 eligible 77 identity를 실행했다. 지표는 Gold MATCH {len(base)}개만 평가하며 NO_MATCH 16개/UNRESOLVED 3개는 Recall·MRR 분모에서 제외했다. TEST는 열지 않았다.",
        f"- 전체 MATCH {len(base)}개와 catalog-retrievable {int(base.catalog_retrievable.sum())}개 두 분모를 보고한다. catalog-retrievable은 Gold ID가 perfumes.csv에 존재한다는 뜻이며 브랜드/필터를 통과한다는 뜻은 아니다.",
        "- 세 방법의 후보 ID 집합은 각 identity마다 정확히 같다. 기존 exact brand blocking과 Commercial Identity의 기존 형태/농도 필터를 그대로 재사용한다. Method 1의 soft brand fallback은 사용하지 않는다. 후보 Top5로 미리 자르지 않는다.",
        "- baseline은 기존 retrieve_candidates를 재실행해 저장된 77개 Top5와 Gold rank 전수 일치를 검증했다. baseline 문자열/점수식을 그대로 유지했다.",
        "- B/C는 Method 1 structured normalize를 raw member query와 candidate name 양쪽에 적용한다. 같은 완전 접두 브랜드 제거·농도/형태/패키지 분리 규칙을 적용하고 원래 이름을 함께 보존한다. 검증된 원본 identity나 family는 수정/병합하지 않는다.",
        "- B: uroman 기본 언어 자동 처리로 양쪽 core를 Latin 문자열로 변환한 후 casefold·공백/구두점 제외, SequenceMatcher ratio(autojunk=False) 하나로 정렬한다. 기존 phonetic 최대값이나 baseline ranking을 합치지 않는다.",
        "- C: 후보 core 전체를 영어→한국어 모델에 입력한다. query는 한국어 core를 그대로 쓴다. 양쪽을 Unicode NFD 자모로 분해하고 알파벳/숫자/자모만 남긴 뒤 B와 동일한 문자열 비교식을 적용한다.",
        "- 자모 단위를 선택한 이유: 한 음절의 모음/받침이 달라도 같은 초성 등 부분 일치를 반영할 수 있다. 표준 Unicode 분해만 쓰며 발음 동화·초종성 통합·추가 자모 라이브러리·음절 점수와의 혼합은 없다.",
        "- 여러 member core는 채널 내부에서 최대 유사도를 사용한다. 동점은 Fragrantica ID 내림차순. ML 학습·threshold·제품명 예외·Gold alias·RRF·weighted fusion·DEV parameter sweep 없음.",
        "- A 대비 B/C 차이에는 구조화 정규화와 점수식 차이도 포함된다. 순수 모델 효과만 분리한 ablation은 아니다. B와 C는 같은 core·pool·문자열 비교식에 기반하지만 representation이 다르다.",
        "- MRR은 공통 전체 후보군 내 정답 순위 역수(미검색=0). MRR@10도 제공한다. rescue는 baseline 밖→새 방법 안, regression은 baseline 안→새 방법 밖이며 각 K에서 독립적으로 집계한다.",
        "", "## 모델 및 실행 설정", "",
        f"- 모델 `{MODEL}`, revision `{REVISION}`. 해당 snapshot의 Marian base 가중치와 LoRA adapter를 한 번씩 로드한다. adapter가 참조하는 다른 repo로 자동 이동하지 않는다. adapter 병합/학습 없음.",
        "- 공개 wrapper의 beam 3, max_length 64를 사용하고 샘플링만 끈다(do_sample=False). CPU float32, seed 42, batch 16, threads 4, deterministic algorithms. sentence 전체 생성 1개만 사용하고 후보별 최적 출력 선택을 하지 않는다.",
        "- 모델 API smoke test에서 공개 예제 `LORA IS ALL YOU NEED` → `로라 이즈 올 유 니드`가 실행됐다. 후보/Gold를 보고 decoding을 조정하지 않았다.",
        "- 캐시는 exact core + 모델 revision + decoding 설정 + 라이브러리 버전으로 분리한다. 동일 core는 한 번만 생성한다. generation 실패/길이 한도/빈 출력은 보존·표시하며 원문으로 조용히 복구하지 않는다.",
        "- 비ASCII/비영어 이름도 철자를 그대로 넣는다. uroman을 앞단에 붙이지 않는다. French/Italian/Turkish/조어의 원어 발음, 관용 한국어 표기, 혼합언어 query는 영어 전용 모델의 보장 범위가 아니다.",
        "- [uroman 공식 문서](https://github.com/isi-nlp/uroman) · [enko 모델](https://huggingface.co/feVeRin/enko-transliterator) · [공개 추론 구현](https://github.com/feVeRin/enko_transliterator/blob/main/transliteration.py)"]
    for scope in ("ALL_GOLD_MATCH", "CATALOG_RETRIEVABLE"):
        subset = metrics[metrics.scope.eq(scope)]
        lines += ["", f"## {scope}: 전체 성능", ""] + table(subset[subset.level.eq("OVERALL")], metric_cols)
        lines += ["", "### Representative / Challenge", ""] + table(subset[subset.level.eq("SAMPLE_GROUP")], metric_cols)
        lines += ["", "### Rescue / Regression", ""] + table(subset[~subset.level.eq("CHALLENGE_TYPE")], rescue_cols)
        lines += ["", "### Challenge type별 성능", ""] + table(subset[subset.level.eq("CHALLENGE_TYPE")], metric_cols)
        lines += ["", "### Challenge type별 Rescue / Regression", ""] + table(subset[subset.level.eq("CHALLENGE_TYPE")], rescue_cols)
    lines += ["", "## Catalog 및 공통 후보 범위 한계", ""]
    lines += table(missing, ["queue_id", "gold_fragrantica_id", "gold_fragrantica_name", "catalog_status"])
    lines += ["", "공통 pool 상태: " + ", ".join(f"{k}={v}" for k,v in base.catalog_status.value_counts().items()),
        "이 상태는 방법 간 동일하다. CATALOG_MISSING을 NO_MATCH로 재라벨링하지 않았으며, 브랜드/필터에서 빠진 정답은 이번 이름 ranking 실험으로 복구할 수 없다."]
    example_cols = ["queue_id", "query_cores", "gold_fragrantica_name", "gold_uroman", "gold_transliteration", "baseline_rank", "gold_candidate_rank"]
    for method in METHODS[1:]:
        frame = results[results.method.eq(method) & results.gold_status.eq("MATCH")].copy()
        frame["rank_gain"] = frame.baseline_rank - frame.gold_candidate_rank
        lines += ["", f"## {method}: 개선 사례", ""]
        lines += table(frame[frame.rescue_at_5 | frame.rescue_at_10].sort_values("rank_gain", ascending=False).head(10), example_cols)
        lines += ["", f"### {method}: 회귀 사례", ""]
        lines += table(frame[frame.regression_at_5 | frame.regression_at_10].sort_values("rank_gain").head(10), example_cols)
    lines += ["", "## Transliteration 생성 예시와 품질", "",
        "아래 출력은 모델이 실제 생성한 문자열이다. retrieval 적중은 언어학적 음역 정확성과 같지 않으므로, 성공/오류 해석은 원문과 국내 표기를 함께 봐야 한다."]
    enko = results[results.method.eq("enko_transliteration") & results.gold_status.eq("MATCH") & results.catalog_status.eq("IN_CANDIDATE_POOL")]
    lines += ["", "### 상위 적중 출력", ""] + table(enko[enko.gold_candidate_rank.le(3)].head(10), example_cols)
    lines += ["", "### 순위 실패 출력", ""] + table(enko[~enko.gold_candidate_rank.le(10)].head(10), example_cols)
    lines += ["", "### 실제 비ASCII 후보 생성 예시", ""]
    lines += table(candidates[candidates.non_ascii_core].head(12), ["fragrantica_id", "name", "core", "korean_transliteration", "generation_status"])
    overall = metrics[(metrics.scope == "ALL_GOLD_MATCH") & (metrics.level == "OVERALL")].set_index("method")
    lines += ["", "## 보완 가치와 판단", ""]
    for method in METHODS[1:]:
        row = overall.loc[method]
        lines += [f"- {method}: baseline 대비 ΔR@5={row.recall_at_5-overall.loc['baseline_lexical'].recall_at_5:+.4f}, ΔMRR={row.mrr-overall.loc['baseline_lexical'].mrr:+.4f}; Top5 rescue {int(row.rescue_at_5)}, regression {int(row.regression_at_5)}; Top10 rescue {int(row.rescue_at_10)}, regression {int(row.regression_at_10)}."]
    lines += ["rescue가 있으면 baseline과 다른 오류 구조를 가진다는 증거이나, 자동 교체나 fusion 성능 향상을 입증하지 않는다. 두 새 채널을 합친 ranking이나 최종 MATCH Precision은 측정하지 않았다.",
        "Gold DEV에서만 측정했으므로 미관측 데이터에 대한 일반화는 미확인이다. Verification과 다음 단계 구현은 진행하지 않았다.",
        "", "## 실행시간 및 재현 검증", "",
        "시간은 실제 실행의 wall-clock seconds이며 모델 다운로드·의존성 설치 시간은 제외한다. 캐시가 있는 재실행은 별도의 생성 시간을 만들지 않는다.",
        "```json", json.dumps(times, ensure_ascii=False, indent=2), "```",
        f"- catalog 후보 {len(candidates)}개 ID, core {candidates.core.nunique()}개. 생성 상태: {candidates.generation_status.value_counts().to_dict()} (ID 기준).",
        "- baseline 77개 Gold rank/Top5 일치, 모든 방법의 후보 ID 집합/길이 일치, rescue-regression 적중 수 항등식, structured normalization 검사, 입력 hash 불변 검사를 실행했다.",
        f"- Python {platform.python_version()}, Unicode database {unicodedata.unidata_version}."]
    for package in ("uroman", "torch", "transformers", "peft", "sentencepiece", "sacremoses", "pandas"):
        lines.append(f"- {package}: {importlib.metadata.version(package)}")
    lines += [f"- 실행: `venv/Scripts/python.exe {Path(__file__).name}`", f"- 고정 설정: `{PREFIX}_settings.json`", "- 입력 SHA-256:"]
    lines += [f"  - `{p.relative_to(ROOT)}`: `{h}`" for p,h in hashes.items()]
    (OUT / f"{PREFIX}_report.md").write_text("\n".join(lines)+"\n", encoding="utf-8")


def main():
    baseline.verify_snapshot()  # 재현 게이트의 기준 스냅샷 고정 (9a-4)
    baseline.use_llm_channel(None)  # 기록값은 LLM 채널 도입 전 측정본이다 (9c)
    baseline.use_verification(False)  # 기록값은 Verification 도입 전 측정본이다 (10b)
    started = time.perf_counter()
    CACHE.mkdir(parents=True, exist_ok=True)
    settings_path = OUT / f"{PREFIX}_settings.json"
    if settings_path.exists():
        assert json.loads(settings_path.read_text(encoding="utf-8")) == SETTINGS, "Frozen settings differ"
    else:
        dump(settings_path, SETTINGS)  # Written before loading Gold or generating rankings.
    input_paths = [baseline.GOLD_PATH, baseline.COMMERCIAL_PATH, baseline.PERFUMES_PATH,
        baseline.RESULTS_PATH, baseline.REPORT_PATH, baseline.MEMBERS_PATH,
        baseline.FAMILIES_PATH, ROOT / "src" / "korea" / "build_korea_popularity_map.py",
        ROOT / "src" / "matching" / "evaluate_fragrantica_matcher_dev.py", ROOT / "src" / "matching" / "evaluate_fragrantica_method1_dev.py",
        Path(__file__).resolve(), settings_path]
    input_paths += sorted(OUT.glob("fragrantica_method1_dev_*"))
    input_paths += sorted(MODEL_DIR.glob("*"))
    hashes = {p: matcher.sha256(p) for p in input_paths if p.is_file()}
    gold = pd.read_csv(baseline.GOLD_PATH, keep_default_na=False)
    assert len(gold) == 80 and gold.split.eq("DEV").all()
    eligible = gold[baseline.as_bool(gold.evaluation_eligible)].copy()
    assert len(eligible) == 77 and eligible.gold_status.value_counts().to_dict() == {"MATCH":61,"NO_MATCH":16}
    commercial = pd.read_csv(baseline.COMMERCIAL_PATH, keep_default_na=False).set_index("commercial_identity_id", drop=False)
    members = pd.read_csv(baseline.MEMBERS_PATH, keep_default_na=False)
    perfumes = pd.read_csv(baseline.PERFUMES_PATH, usecols=["id","name","brand","description"], keep_default_na=False)
    assert perfumes.id.is_unique and commercial.index.is_unique
    inputs, rankings, candidates, times = prepare_rankings(commercial, members, perfumes, eligible.commercial_identity_id)
    results = evaluate(eligible, inputs, rankings, candidates, perfumes)
    metrics = measure(results)
    base = metrics[(metrics.scope == "ALL_GOLD_MATCH") & (metrics.method == "baseline_lexical") & (metrics.level == "OVERALL")].iloc[0]
    assert [round(base[f"recall_at_{k}"],4) for k in (1,3,5,10)] == [0.3115,0.5082,0.5902,0.6721]
    assert round(base.mrr,4) == 0.4451
    assert len(results) == 77 * 3
    assert all(matcher.sha256(p) == h for p,h in hashes.items())
    results.to_csv(OUT / f"{PREFIX}_results.csv", index=False, encoding="utf-8-sig")
    candidates.to_csv(OUT / f"{PREFIX}_candidate_transliterations.csv", index=False, encoding="utf-8-sig")
    metrics.to_csv(OUT / f"{PREFIX}_metrics.csv", index=False, encoding="utf-8-sig")
    times["total_before_report_seconds"] = time.perf_counter()-started
    write_report(results, metrics, candidates, times, hashes)
    assert all(matcher.sha256(p) == h for p,h in hashes.items())
    print(metrics[metrics.level.eq("OVERALL")].to_string(index=False), flush=True)


if __name__ == "__main__":
    main()

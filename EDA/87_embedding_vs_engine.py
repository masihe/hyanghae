"""현재 엔진(LLM 구조화 + 사전)과 임베딩 검색을 같은 문장·같은 채점으로 비교한다.

발표 질문 "왜 임베딩 대신 LLM 을 썼나" 에 기록으로 답하기 위한 실험이다 (2026-09-29).

판정 기준 — 측정 전에 고정했다 (2026-09-29, 사용자 결정)
    재현 관문   이 파일의 채점기로 390(4b9d93d) -> 391(0efc20e) 차이를 재서
                기록값 -0.010963 과 같은 방향이고 기록 구간 [-0.019653, -0.001987] 안이면 통과.
                통과 못 하면 그 뒤 비교를 하지 않는다.
                절대값은 과거 기록과 견주지 않는다 (기록 스스로 절대값이 재현 안 됐다고 적었다).
    주 지표     확장 NDCG@5 · 합성 600 · 짝지은 부트스트랩 20,000회 · seed 20260916
                95% 구간이 0 을 빼면 "차이 있음". 승패 문턱은 두지 않는다
    보조        갈래 A·B 별 · 회피 누출 · 설문 143 성별·계절 일치 · 일관성 · 메모리·지연
    임베딩 쪽은 코사인 상위 5개만 쓴다. 문턱·가중치를 평가셋에 맞춰 조정하지 않는다.

확장 NDCG@5 의 조건 (측정 기록 35번 5절의 정의를 따르고, 조건 해석을 한 엔진에 고정했다)
    조건 = 정답 향수의 accord 3개(C)
         + 쿼리가 말했고 정답 향수도 실제로 가진 노트 · 성별 · 계절 · 낮밤
    "쿼리가 말했다" 는 **391 엔진의 해석 함수**(note_spoken · _context_values)로 한 번만 계산한다.
    그래서 390 · 391 · 임베딩이 모두 같은 조건으로 채점된다.
    gain = 추천 향수가 충족한 조건 수 (선형 · 같은 무게) · 이상값 = 조건 수를 5칸 모두 채운 경우

사용법 (결과와 해석은 docs/nlr_engineering_notes.md 41번)
    run-engine     엔진을 합성 600 + 설문 143 에 돌린다. --estimator-cache 로 ⑤단계 저장본을 켠다
    run-embedding  향수 description 과 문장을 임베딩해 코사인 상위 5개 (브랜드 제한 유·무)
    score          두 결과를 확장 NDCG@5 로 짝지어 비교 (갈래 A·B 포함)
    extras         경로 분포 · 결과 회피 누출 · 설문 성별·계절·낮밤 일치
    resources      CPU 기준 메모리 · 지연 (방식마다 따로 실행)
"""
import argparse
import csv
import importlib.util
import json
import math
import sys
from pathlib import Path

import numpy as np

DEFAULT_OUTPUTS = Path(__file__).resolve().parent / "analysis_outputs"
STAGE1_SYNTH = "34_evalset_stage1_checkpoint.csv"
ANSWER_KEY = "32_evalset_answer_key.csv"
TOP_K = 5
BOOT_N = 20_000
BOOT_SEED = 20260916


def load_engine(engine_dir):
    """engine_dir 의 nlr_engine.py 를 모듈로 불러온다. module."""
    path = Path(engine_dir) / "nlr_engine.py"
    if not path.is_file():
        raise FileNotFoundError(path)
    spec = importlib.util.spec_from_file_location(f"nlr_engine_{abs(hash(str(path)))}", path)
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(path.parent))
    spec.loader.exec_module(module)
    return module


def load_synth(outputs_dir):
    """합성 600 의 ①단계 저장 출력. list[dict(query_id, arm, perfume_id, sentence, structured)]."""
    rows = []
    with open(Path(outputs_dir) / STAGE1_SYNTH, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            parsed = json.loads(r["parsed"]) if r["parsed"] else None
            rows.append({
                "query_id": r["query_id"],
                "arm": r["arm"],
                "perfume_id": int(r["perfume_id"]),
                "sentence": r["sentence"],
                "status": r["status"],
                "structured": parsed,
            })
    if len(rows) != 600:
        raise ValueError(f"합성 평가셋이 600문장이 아니다: {len(rows)}")
    return rows


SURVEY = "37_survey_stage1_checkpoint.csv"
# 설문 155건 중 향 요청이 아닌 동의 응답 12건 — 측정 기록 19번 판정 (nlr_engineering_notes.md:7346)
CONSENT_REPLIES = {"네": 4, "넵": 2, "넵!": 1, "예": 2, "넴": 1, "네.": 1, "넵 알겠습니다.": 1}


def load_survey(outputs_dir):
    """설문 143 의 원문과 ①단계 저장 출력. list[dict(query_id, arm, sentence, structured)]."""
    rows, dropped = [], {}
    with open(Path(outputs_dir) / SURVEY, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            text = r["query_text"].strip()
            if text in CONSENT_REPLIES:
                dropped[text] = dropped.get(text, 0) + 1
                continue
            rows.append({
                "query_id": r["query_id"],
                "arm": "S",
                "perfume_id": None,
                "sentence": r["query_text"],
                "status": r["status"],
                "structured": json.loads(r["parsed"]) if r["parsed"] else None,
            })
    if dropped != CONSENT_REPLIES or len(rows) != 143:
        raise ValueError(f"설문 제외가 기록과 다르다: 뺀 것 {dropped} · 남은 것 {len(rows)}")
    return rows


def load_answer_key(outputs_dir):
    """정답표. dict[perfume_id, list[accord]] — C 는 파이프 구분 문자열이다."""
    key = {}
    with open(Path(outputs_dir) / ANSWER_KEY, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            key[int(r["perfume_id"])] = [a for a in r["C"].split("|") if a]
    return key


def cached_estimator(cache_csv):
    """저장된 ⑤단계 추정(표현별 v1)을 돌려주는 estimator 와 호출 통계. (callable, dict).

    저장본에 없는 표현은 None(호출 실패)으로 둔다 — 엔진은 그 표현을 조건으로 쓰지 않는다.
    ⚠ 서비스(391)는 표현을 묶어 원문과 함께 묻는다. 이 저장본은 표현별 v1 이라 서비스와 다르다.
    """
    table = {}
    with open(cache_csv, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            if r["error"]:
                continue
            table[r["expression"]] = {"accords": [a for a in r["accords"].split("|") if a],
                                      "reasoning": r["reasoning"]}
    stats = {"asked": set(), "missing": set()}

    def estimator(raw_text, expressions):
        out = []
        for e in expressions:
            stats["asked"].add(e)
            if e not in table:
                stats["missing"].add(e)
            out.append(table.get(e))
        return out

    return estimator, stats


def run_engine(engine_dir, outputs_dir, out_path, estimator_cache=None):
    """엔진을 합성 600 과 설문 143 에 돌려 문장별 상위 5개 향수 id 를 저장한다. None."""
    engine = load_engine(engine_dir)
    index = engine.load_index()
    estimator, stats = cached_estimator(estimator_cache) if estimator_cache else (None, None)
    result = {}
    for row in load_synth(outputs_dir) + load_survey(outputs_dir):
        rec = engine.recommend(index, row["sentence"], structured=row["structured"],
                               top_k=TOP_K, estimator=estimator)
        result[row["query_id"]] = {
            "status": rec["status"],
            "stage": rec["diagnostics"]["stage"],
            "ids": [r["perfume_id"] for r in rec["results"]],
        }
    Path(out_path).write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    counts = {}
    for v in result.values():
        counts[v["status"]] = counts.get(v["status"], 0) + 1
    print(f"{engine_dir} -> {out_path}  문장 {len(result)}  status {counts}")
    if stats:
        asked = len(stats["asked"])
        print(f"추정 표현 고유 {asked} · 저장본에 없음 {len(stats['missing'])}")


MODELS = {
    # 짧은 이름: (허깅페이스 저장소, 쿼리 접두사, 문서 접두사, 최대 토큰)
    "e5-base": ("intfloat/multilingual-e5-base", "query: ", "passage: ", 512),
    "minilm": ("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2", "", "", 128),
    "bge-m3": ("BAAI/bge-m3", "", "", 512),
}


def pool_ids(engine, index):
    """엔진과 같은 후보 풀(people >= PEOPLE_MIN)의 id·브랜드. (list[int], list[str])."""
    keep = np.asarray(index["people"]) >= engine.PEOPLE_MIN
    ids = [int(p) for p, k in zip(index["pid"], keep) if k]
    brands = [b for b, k in zip(index["brand"], keep) if k]
    return ids, brands


def load_pool(engine, index, perfumes_jsonl):
    """후보 풀의 id·브랜드·설명문. (ids, brands, texts)."""
    ids, brand_list = pool_ids(engine, index)
    brands = dict(zip(ids, brand_list))
    wanted = set(ids)
    desc = {}
    with open(perfumes_jsonl, encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            if d["id"] in wanted:
                desc[d["id"]] = d.get("description") or ""
    empty = [i for i in ids if not desc.get(i)]
    if empty:
        raise ValueError(f"설명문이 없는 향수 {len(empty)}개: {empty[:5]}")
    return ids, [brands[i] for i in ids], [desc[i] for i in ids]


def top_ids(scores, ids, brands, brand_cap):
    """점수 내림차순으로 상위 TOP_K 개 id. brand_cap 이면 브랜드당 1개. list[int]."""
    order = np.argsort(-scores)
    picked, seen = [], set()
    for j in order:
        if brand_cap and brands[j] in seen:
            continue
        picked.append(ids[j])
        seen.add(brands[j])
        if len(picked) == TOP_K:
            break
    return picked


def run_embedding(model_key, engine_dir, perfumes_jsonl, cache_dir, outputs_dir, out_prefix,
                  device="cpu"):
    """향수 설명문과 사용자 원문을 임베딩해 코사인 상위 5개를 저장한다. 브랜드 제한 유·무 두 벌. None.

    device 가 cpu 가 아니면 캐시·결과 파일 이름에 장치를 붙인다 — 장치끼리 결과를 견줄 수 있게.
    정밀도는 장치와 상관없이 fp32 다.
    """
    import time
    from sentence_transformers import SentenceTransformer

    repo, q_prefix, p_prefix, max_len = MODELS[model_key]
    tag = model_key if device == "cpu" else f"{model_key}_{device}"
    engine = load_engine(engine_dir)
    index = engine.load_index()
    ids, brands, texts = load_pool(engine, index, perfumes_jsonl)
    model = SentenceTransformer(repo, device=device)
    model.max_seq_length = max_len
    cache = Path(cache_dir) / f"87_{tag}_perfumes.npy"
    if cache.is_file():
        emb = np.load(cache)
        if emb.shape[0] != len(ids):
            raise ValueError(f"캐시 행 수 {emb.shape[0]} != 풀 {len(ids)}: {cache}")
        print(f"향수 벡터 캐시 사용 {cache}")
    else:
        t0 = time.time()
        emb = model.encode([p_prefix + t for t in texts], batch_size=64, normalize_embeddings=True,
                           show_progress_bar=True, convert_to_numpy=True).astype(np.float32)
        np.save(cache, emb)
        print(f"향수 {len(ids)}개 인코딩 {time.time() - t0:.0f}초 -> {cache}")
    queries = load_synth(outputs_dir) + load_survey(outputs_dir)
    t0 = time.time()
    q_emb = model.encode([q_prefix + q["sentence"] for q in queries], batch_size=32,
                         normalize_embeddings=True, convert_to_numpy=True).astype(np.float32)
    print(f"문장 {len(queries)}개 인코딩 {time.time() - t0:.1f}초")
    scores = q_emb @ emb.T
    for cap in (True, False):
        result = {}
        for q, s in zip(queries, scores):
            result[q["query_id"]] = {"status": "OK", "stage": "EMBEDDING",
                                     "ids": top_ids(s, ids, brands, cap)}
        out = f"{out_prefix}_{tag}_{'cap' if cap else 'nocap'}.json"
        Path(out).write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
        print(f"-> {out}")


class Scorer:
    """확장 NDCG@5 채점기. 조건은 한 엔진(scorer engine)의 해석으로 고정한다."""

    def __init__(self, engine, index, answer_key):
        self.engine = engine
        self.index = index
        self.answer_key = answer_key
        self.row_of = {int(p): i for i, p in enumerate(index["pid"])}
        self._notes_of = None

    def notes_of(self, row):
        """향수 한 개의 노트 이름 목록. list[str]."""
        if self._notes_of is None:
            table = {}
            for note, rows in self.index["notes"].items():
                for r in np.atleast_1d(rows):
                    table.setdefault(int(r), []).append(note)
            self._notes_of = table
        return self._notes_of.get(row, [])

    def conditions(self, query):
        """문장 하나의 조건 목록. list[tuple(kind, value)]. 정답 향수가 엔진 색인에 없으면 None."""
        answer_row = self.row_of.get(query["perfume_id"])
        if answer_row is None:
            return None
        conds = [("accord", a) for a in self.answer_key[query["perfume_id"]]]
        structured = query["structured"]
        spoken = self.engine.note_spoken(self.index, structured, query["sentence"]) or {}
        answer_notes = self.notes_of(answer_row)
        for target in sorted(set(spoken.values())):
            if any(target in n for n in answer_notes):
                conds.append(("note", target))
        ctx = (structured or {}).get("context")
        if isinstance(ctx, dict):
            for field, (_, mapping) in self.engine.CONTEXT_FIELDS.items():
                values, _ = self.engine._context_values(ctx.get(field), mapping, field)
                table = self.index["context"].get(field) or {}
                for value in sorted(values):
                    if value in table and bool(table[value][answer_row]):
                        conds.append((field, value))
        return conds

    def gain(self, row, conds):
        """추천 향수 한 개가 충족한 조건 수. int."""
        total = 0
        notes = None
        for kind, value in conds:
            if kind == "accord":
                col = self.index["aidx"].get(value)
                total += int(col is not None and self.index["strength"][row, col] > 0)
            elif kind == "note":
                notes = self.notes_of(row) if notes is None else notes
                total += int(any(value in n for n in notes))
            else:
                total += int(bool(self.index["context"][kind][value][row]))
        return total

    def ndcg(self, ids, conds):
        """확장 NDCG@5. float. 결과가 비면 0."""
        if not conds:
            return 0.0
        ideal = sum(len(conds) / math.log2(i + 2) for i in range(TOP_K))
        dcg = 0.0
        for i, pid in enumerate(ids[:TOP_K]):
            row = self.row_of.get(int(pid))
            if row is not None:
                dcg += self.gain(row, conds) / math.log2(i + 2)
        return dcg / ideal


def paired_bootstrap(base, new, n=BOOT_N, seed=BOOT_SEED):
    """짝지은 차이의 평균과 95% 백분위 구간. (float, float, float)."""
    diff = np.asarray(new, dtype=float) - np.asarray(base, dtype=float)
    rng = np.random.default_rng(seed)
    means = diff[rng.integers(0, len(diff), size=(n, len(diff)))].mean(axis=1)
    return float(diff.mean()), float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def score(scorer_engine_dir, outputs_dir, base_path, new_path):
    """두 결과 파일을 같은 조건으로 채점해 평균과 짝지은 차이를 출력한다. None."""
    engine = load_engine(scorer_engine_dir)
    index = engine.load_index()
    scorer = Scorer(engine, index, load_answer_key(outputs_dir))
    base = json.loads(Path(base_path).read_text(encoding="utf-8"))
    new = json.loads(Path(new_path).read_text(encoding="utf-8"))
    queries = load_synth(outputs_dir)
    missing = [q["query_id"] for q in queries if q["query_id"] not in base or q["query_id"] not in new]
    if missing:
        raise ValueError(f"결과 파일에 없는 문장 {len(missing)}개: {missing[:5]}")
    b, n, arms, skipped, n_conds = [], [], [], [], []
    for q in queries:
        conds = scorer.conditions(q)
        if conds is None:
            skipped.append(q["query_id"])
            continue
        n_conds.append(len(conds))
        arms.append(q["arm"])
        b.append(scorer.ndcg(base[q["query_id"]]["ids"], conds))
        n.append(scorer.ndcg(new[q["query_id"]]["ids"], conds))
    mean, lo, hi = paired_bootstrap(b, n)
    print(f"채점 문장 {len(b)} · 정답 향수가 색인에 없어 뺀 문장 {len(skipped)} {skipped[:5]}")
    print(f"조건 수 평균 {np.mean(n_conds):.2f} · 최소 {min(n_conds)} · 최대 {max(n_conds)}")
    print(f"base {np.mean(b):.6f}  new {np.mean(n):.6f}")
    print(f"차이 {mean:+.6f}  95% [{lo:+.6f}, {hi:+.6f}]")
    up = sum(1 for x, y in zip(b, n) if y > x)
    down = sum(1 for x, y in zip(b, n) if y < x)
    print(f"오른 문장 {up} · 내린 문장 {down} · 같은 문장 {len(b) - up - down}")
    # 갈래 A 는 accord 에서, 갈래 B 는 ai_summary 에서 문장을 만들었다 — 순환이 갈래마다 다르다
    for arm in sorted(set(arms)):
        bb = [x for x, a in zip(b, arms) if a == arm]
        nn = [y for y, a in zip(n, arms) if a == arm]
        m, lo, hi = paired_bootstrap(bb, nn)
        print(f"  갈래 {arm} ({len(bb)})  base {np.mean(bb):.6f}  new {np.mean(nn):.6f}  "
              f"차이 {m:+.6f}  95% [{lo:+.6f}, {hi:+.6f}]")


def extras(scorer_engine_dir, outputs_dir, result_paths):
    """보조 지표: 경로 분포 · 결과 회피 누출 · 설문 성별·계절·낮밤 일치. 결과 파일마다 출력한다. None.

    회피 대상은 391 `_avoid_targets()` 로 한 번만 계산해 고정한다.
    누출 판정 = 추천 향수가 회피 accord 를 강도 > 0 으로 갖거나 회피 노트를 가짐 (채점기의 충족 판정과 같다).
    ⚠ 9/21 기록의 "회피 누출"(싫다고 한 것이 **조건**에 들어간 문장 수)과 다른 지표다.
    """
    engine = load_engine(scorer_engine_dir)
    index = engine.load_index()
    scorer = Scorer(engine, index, load_answer_key(outputs_dir))
    sets = {"합성": load_synth(outputs_dir), "설문": load_survey(outputs_dir)}
    avoid = {}
    context = {}
    for name, queries in sets.items():
        for q in queries:
            accords, notes = engine._avoid_targets(index, q["structured"])
            if accords or notes:
                avoid[q["query_id"]] = (accords, notes)
            ctx = (q["structured"] or {}).get("context")
            if name == "설문" and isinstance(ctx, dict):
                for field, (_, mapping) in engine.CONTEXT_FIELDS.items():
                    values, _ = engine._context_values(ctx.get(field), mapping, field)
                    if values:
                        context.setdefault(q["query_id"], {})[field] = values

    def leaks(row, targets):
        accords, notes = targets
        for a in accords:
            col = index["aidx"].get(a)
            if col is not None and index["strength"][row, col] > 0:
                return True
        have = scorer.notes_of(row)
        return any(t in n for t in notes for n in have)

    for name, queries in sets.items():
        n_av = sum(1 for q in queries if q["query_id"] in avoid)
        print(f"{name}: 회피 대상이 있는 문장 {n_av}")
    fields = sorted({f for v in context.values() for f in v})
    print("설문: 조건을 말한 문장 " + " · ".join(
        f"{f} {sum(1 for v in context.values() if f in v)}" for f in fields))

    for path in result_paths:
        res = json.loads(Path(path).read_text(encoding="utf-8"))
        print(f"\n### {Path(path).name}")
        for name, queries in sets.items():
            got = [res[q["query_id"]] for q in queries if q["query_id"] in res]
            if len(got) != len(queries):
                print(f"  {name}: 결과 파일에 {len(queries) - len(got)}문장이 없다 — 건너뛴다")
                continue
            status, empty = {}, 0
            for g in got:
                status[g["status"]] = status.get(g["status"], 0) + 1
                empty += int(not g["ids"])
            shown, leaked, q_leaked = 0, 0, 0
            for q in queries:
                if q["query_id"] not in avoid:
                    continue
                rows = [scorer.row_of[int(p)] for p in res[q["query_id"]]["ids"]]
                hit = sum(leaks(r, avoid[q["query_id"]]) for r in rows)
                shown += len(rows)
                leaked += hit
                q_leaked += int(hit > 0)
            rate = f"{leaked / shown:.1%}" if shown else "-"
            print(f"  {name}: status {status} · 결과 0건 {empty} · "
                  f"회피 누출 향수 {leaked}/{shown} ({rate}) · 누출이 1개라도 있는 문장 {q_leaked}")
            if name != "설문":
                continue
            for field in fields:
                asked = [q for q in queries if field in context.get(q["query_id"], {})]
                counts = []
                for q in asked:
                    want = context[q["query_id"]][field]
                    rows = [scorer.row_of[int(p)] for p in res[q["query_id"]]["ids"]]
                    counts.append(sum(any(bool(index["context"][field][v][r]) for v in want)
                                      for r in rows))
                zero = sum(1 for q in asked if not res[q["query_id"]]["ids"])
                print(f"    {field}: {len(asked)}문장 · 추천 5개 중 맞는 개수 평균 "
                      f"{np.mean(counts):.2f} (결과 0건은 0개로 셈 · 0건 {zero})")


def resources(engine_dir, outputs_dir, model_key=None, cache_dir=None, n_queries=50):
    """CPU 기준 자원 측정. 프로세스 하나에 한 방식만 올린다(힙 재사용으로 작게 나오는 것을 막는다). None.

    model_key 가 없으면 엔진만 적재해 잰다. 있으면 torch 적재 · 모델 · 향수 행렬을 단계별로 잰다.
    ⚠ 향수 설명문(perfumes.jsonl)은 읽지 않는다 — 큰 JSON 을 읽고 풀린 힙을 모델이 재사용해
      모델 증가분이 작게 나온 적이 있다(2026-09-29 첫 측정). 풀은 엔진 색인에서만 만든다.
    ⚠ 이 환경의 torch 는 CUDA 판이다. 서버는 CPU 판이므로 torch 적재분은 따로 보고한다.
    지연은 설문 문장 앞 n_queries 개를 하나씩 처리한 시간이다. 엔진은 ①단계 LLM 호출을 빼고
    저장 출력을 넣은 값이다 — LLM 1회 지연(중앙 1.53초, 9/15 기록)은 따로 더해야 한다.
    """
    import time
    import psutil

    proc = psutil.Process()
    mb = lambda: proc.memory_info().rss / 1024 / 1024  # noqa: E731
    rss0 = mb()
    queries = load_survey(outputs_dir)[:n_queries]
    times = []
    if model_key is None:
        engine = load_engine(engine_dir)
        index = engine.load_index()
        rss1 = mb()
        for q in queries:
            t = time.perf_counter()
            engine.recommend(index, q["sentence"], structured=q["structured"], top_k=TOP_K)
            times.append((time.perf_counter() - t) * 1000)
        print(f"엔진 · 시작 {rss0:.0f}MB -> 색인 적재 후 {rss1:.0f}MB (+{rss1 - rss0:.0f})")
    else:
        import torch  # noqa: F401  적재분을 따로 재려고 먼저 올린다
        from sentence_transformers import SentenceTransformer
        rss_t = rss1 = mb()
        repo, q_prefix, _, max_len = MODELS[model_key]
        t = time.perf_counter()
        model = SentenceTransformer(repo, device="cpu")
        model.max_seq_length = max_len
        load_sec = time.perf_counter() - t
        rss2 = mb()
        emb = np.load(Path(cache_dir) / f"87_{model_key}_cuda_perfumes.npy")
        rss3 = mb()
        # 풀 목록은 **잰 뒤에** 만든다 — 엔진 색인을 먼저 올렸다 지우면 그 힙을 모델이 재사용한다
        engine = load_engine(engine_dir)
        ids, brands = pool_ids(engine, engine.load_index())
        model.encode([q_prefix + "워밍업"], normalize_embeddings=True)
        for q in queries:
            t = time.perf_counter()
            v = model.encode([q_prefix + q["sentence"]], normalize_embeddings=True,
                             convert_to_numpy=True)[0].astype(np.float32)
            top_ids(emb @ v, ids, brands, True)
            times.append((time.perf_counter() - t) * 1000)
        print(f"{model_key} · 시작 {rss0:.0f}MB -> torch 적재 {rss_t:.0f} (+{rss_t - rss0:.0f}) "
              f"-> 모델 {rss2:.0f} (+{rss2 - rss1:.0f}, 적재 {load_sec:.1f}초) "
              f"-> 향수 행렬 {rss3:.0f} (+{rss3 - rss2:.0f}, 파일 {emb.nbytes / 1024 / 1024:.0f}MB)")
    print(f"  문장 {len(times)}개 지연 중앙 {np.median(times):.1f}ms · p95 {np.percentile(times, 95):.1f}ms "
          f"· 최대 {max(times):.1f}ms · 최종 RSS {mb():.0f}MB")


def main(argv=None):
    """명령행 진입점."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--outputs-dir", default=str(DEFAULT_OUTPUTS))
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_run = sub.add_parser("run-engine")
    p_run.add_argument("--engine-dir", required=True)
    p_run.add_argument("--out", required=True)
    p_run.add_argument("--estimator-cache", help="⑤단계 저장본 CSV. 주면 추정을 켠 상태로 돈다")
    p_emb = sub.add_parser("run-embedding")
    p_emb.add_argument("--model", required=True, choices=sorted(MODELS))
    p_emb.add_argument("--engine-dir", required=True, help="후보 풀을 정할 엔진 (ai 폴더)")
    p_emb.add_argument("--perfumes-jsonl", required=True)
    p_emb.add_argument("--cache-dir", required=True)
    p_emb.add_argument("--out-prefix", required=True)
    p_emb.add_argument("--device", default="cpu", help="cpu 또는 cuda")
    p_score = sub.add_parser("score")
    p_score.add_argument("--scorer-engine-dir", required=True)
    p_score.add_argument("--base", required=True)
    p_score.add_argument("--new", required=True)
    p_ext = sub.add_parser("extras")
    p_ext.add_argument("--scorer-engine-dir", required=True)
    p_ext.add_argument("--results", nargs="+", required=True)
    p_res = sub.add_parser("resources")
    p_res.add_argument("--engine-dir", required=True)
    p_res.add_argument("--model", choices=sorted(MODELS))
    p_res.add_argument("--cache-dir")
    args = parser.parse_args(argv)
    if args.cmd == "resources" and args.model and not args.cache_dir:
        parser.error("resources --model 에는 --cache-dir 가 필요하다")
    if args.cmd == "run-engine":
        run_engine(args.engine_dir, args.outputs_dir, args.out, args.estimator_cache)
    elif args.cmd == "run-embedding":
        run_embedding(args.model, args.engine_dir, args.perfumes_jsonl, args.cache_dir,
                      args.outputs_dir, args.out_prefix, args.device)
    elif args.cmd == "resources":
        resources(args.engine_dir, args.outputs_dir, args.model, args.cache_dir)
    elif args.cmd == "extras":
        extras(args.scorer_engine_dir, args.outputs_dir, args.results)
    else:
        score(args.scorer_engine_dir, args.outputs_dir, args.base, args.new)


if __name__ == "__main__":
    main()

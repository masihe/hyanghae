"""Retrieval-only Method 1 experiment. Never calls match_one or reads TEST.

Run: venv/Scripts/python.exe evaluate_fragrantica_method1_dev.py
The frozen public model must already be in cache/method1/model (offline inference).
Gold labels enter only evaluate(), after all four rankings have been generated.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import unicodedata
from collections import defaultdict
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "korea"))
import build_korea_popularity_map as old
import evaluate_fragrantica_matcher_dev as baseline

ROOT = Path(__file__).resolve().parents[2]  # MAP/
DATA = ROOT / "data/korea_popularity"
OUT = DATA / "evaluation"
CACHE = ROOT / "cache/method1"
MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
REVISION = "e8f8c211226b894fcb81acc59f3b34ba3efd5f42"
RRF_K = 60
MAX_BRANDS = 3
MAX_PER_BRAND = 300
SOFT_BRAND_MIN = 0.75  # Conservative spelling cutoff, fixed before DEV evaluation.
METHODS = ("baseline_lexical", "improved_lexical", "baseline_multilingual", "method1_full")


def key(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).casefold()
    return "".join(c for c in value if c.isalnum() and not unicodedata.combining(c))


CONCENTRATIONS = {
    "EXTRAIT": r"(?<!\w)(?:extrait(?:\s+de\s+parfum)?|exdp|엑스트레(?:\s*드\s*퍼퓸)?)(?!\w)",
    "EDP": r"(?<!\w)(?:edp|eau\s+de\s+parfum|오\s*드\s*(?:퍼퓸|빠르펭|파르펭))(?!\w)",
    "EDT": r"(?<!\w)(?:edt|eau\s+de\s+toilette|오\s*드\s*뚜왈렛)(?!\w)",
    "EDC": r"(?<!\w)(?:edc|eau\s+de\s+cologne|오\s*드\s*코롱|코롱|cologne)(?!\w)",
}
FORMS = {
    "HAIR_FRAGRANCE": r"(?<!\w)(?:헤어\s*(?:퍼퓸|미스트|향수)|hair\s+(?:perfume|mist|fragrance))(?!\w)",
    "BODY_FRAGRANCE": r"(?<!\w)(?:바디\s*(?:퍼퓸|미스트|향수)|body\s+(?:mist|perfume|fragrance))(?!\w)",
    "SOLID_FRAGRANCE": r"(?<!\w)(?:(?:고체|솔리드)\s*(?:퍼퓸|향수)?|solid\s+perfume)(?!\w)",
    "BALM_OR_STICK": r"(?<!\w)(?:퍼퓸\s*(?:밤|스틱)|perfume\s+(?:balm|stick))(?!\w)",
    "ROLL_ON": r"(?<!\w)(?:롤온|roll[- ]on)(?!\w)",
}
PROMO = r"(?<!\w)(?:" + "|".join(re.escape(x) for x in old.PROMO_WORDS if x != "NEW") + r"|패키지|package|gift\s+set)(?!\w)"
PROMO_GROUP = r"PICK|증정|기획|미니어처|무료|포카|택\s*1|gift|리뷰이벤트"
SIZE = r"(?<!\w)\d+(?:\.\d+)?\s*(?:ml|g|oz)(?![A-Za-z가-힣])"


@dataclass(frozen=True)
class Identity:
    raw_name: str
    raw_brand: str
    canonical_brand: str
    identity_text: str
    core_name: str
    concentrations: tuple[str, ...]
    product_form: str
    noise: tuple[str, ...]
    attributes_removed: tuple[str, ...]
    brand_prefix_removed: str


def normalize(raw: str, raw_brand: str, canonical: str) -> Identity:
    """Remove complete attribute/noise spans, never arbitrary identity substrings."""
    text = unicodedata.normalize("NFKC", raw)
    noise, attributes = [], []

    def remove_noise(match):
        noise.append(match.group(0))
        return " "

    def group(match):
        if re.search(PROMO_GROUP, match.group(0), re.I) or match.group(0)[1:].lstrip().startswith("+"):
            return remove_noise(match)
        return match.group(0)

    text = re.sub(r"\[[^\]]*\]|\([^)]*\)|\{[^}]*\}", group, text)
    text = re.sub(r"\+.*$", remove_noise, text)
    text = re.sub(SIZE, remove_noise, text, flags=re.I)
    text = re.sub(r"(?<!\w)\d+\s*(?:종|개|pack)(?!\w)", remove_noise, text, flags=re.I)
    text = re.sub(PROMO, remove_noise, text, flags=re.I)

    forms = [form for form, pattern in FORMS.items() if re.search(pattern, text, re.I)]
    product_form = forms[0] if forms else "LIQUID_PERFUME"

    def remove_attribute(match):
        attributes.append(match.group(0))
        return " "

    concentrations = []
    for concentration, pattern in CONCENTRATIONS.items():
        if re.search(pattern, text, re.I):
            concentrations.append(concentration)
        text = re.sub(pattern, remove_attribute, text, flags=re.I)
    for pattern in FORMS.values():
        text = re.sub(pattern, remove_attribute, text, flags=re.I)
    # Standalone generic form words only: e.g. 밤 inside 밤쉘 is retained.
    text = re.sub(r"(?<!\w)(?:향수|퍼퓸|perfume)(?!\w)", remove_attribute, text, flags=re.I)
    text = re.sub(r"[\[\](){}<>]", " ", text)
    text = re.sub(r"\s+", " ", text).strip(" ,;/+")
    identity_text = text
    prefix = ""
    # Only an explicit, complete leading raw brand may be omitted in the core view.
    # The unabridged identity view remains available; internal Dior in Miss Dior stays.
    if raw_brand and raw_brand != "향수존":
        match = re.match(re.escape(raw_brand) + r"(?!\w)[\s,:/-]*", text, re.I)
        if match and text[match.end():].strip():
            prefix = match.group(0)
            text = text[match.end():].strip()
    return Identity(raw, raw_brand, canonical, identity_text, text,
                    tuple(concentrations), product_form, tuple(noise), tuple(attributes), prefix)


def validate_normalization():
    for token in ("Cool Cotton", "Warm Cotton", "Energy", "Flame", "Blooming Bouquet",
                  "쿨 코튼", "웜 코튼", "에너지", "플레임", "블루밍 부케", "밤쉘", "보디가드"):
        item = normalize(f"{token} EDP 50ml (+ 바디로션 증정)", "", "")
        assert item.core_name == token and item.concentrations == ("EDP",)
        assert item.product_form == "LIQUID_PERFUME"
        assert token in item.raw_name
    assert normalize("미스 디올 EDT", "디올", "Dior").core_name == "미스 디올"
    assert normalize("[블랑쉬] EDP", "", "").core_name == "블랑쉬"
    assert normalize("NEW YORK EDP", "", "").core_name == "NEW YORK"


@lru_cache(maxsize=100000)
def lexical_score(query: str, candidate: str) -> float:
    if not key(query) or not key(candidate):
        return 0.0
    return old.match_score(query, candidate)


class Retriever:
    """Unlabeled retrieval input only: catalog, commercial records, member records."""
    def __init__(self, perfumes: pd.DataFrame):
        self.perfumes = perfumes.set_index("id", drop=False)
        self.brands = sorted(perfumes.brand.unique())
        self.brand_rows = {b: g for b, g in perfumes.groupby("brand", sort=False)}
        self.brand_keys = defaultdict(list)
        for brand in self.brands:
            self.brand_keys[key(brand)].append(brand)
        self.aliases = {key(a): b for a, b in old.BRAND_ALIASES.items()}
        self.brand_cache = {}
        self.embedder = None
        self.embeddings = {}

    def resolve_brands(self, canonical: str, members: pd.DataFrame):
        raw = sorted(set(members.brand_raw) - {"", "향수존"})
        # Existing provenance can identify a retailer-supplied brand; no new alias table.
        for basis in members.brand_basis:
            if "->" in basis:
                raw.append(basis.split(":", 1)[-1].split("->", 1)[0])
        raw = sorted(set(raw))
        cache_key = (canonical, tuple(raw))
        if cache_key in self.brand_cache:
            return self.brand_cache[cache_key]
        selected = []
        for term in [canonical] + raw:
            for label, value in (("EXACT_SPELLING", term), ("EXISTING_ALIAS", self.aliases.get(key(term), ""))):
                for brand in self.brand_keys.get(key(value), []):
                    if brand not in [x[0] for x in selected]:
                        selected.append((brand, label, 1.0))
        exact_count = len(selected)
        soft_terms = raw or [canonical]
        scores = [(max(lexical_score(term, brand) for term in soft_terms), brand) for brand in self.brands]
        for score, brand in sorted(scores, key=lambda x: (-x[0], x[1])):
            if len(selected) >= MAX_BRANDS:
                break
            if brand in [x[0] for x in selected]:
                continue
            if exact_count and score < SOFT_BRAND_MIN:
                break
            selected.append((brand, "SOFT_SPELLING" if exact_count else "BOUNDED_FALLBACK", score))
        result = selected[:MAX_BRANDS]
        self.brand_cache[cache_key] = result
        return result

    def prepare(self, commercial, members):
        representations = [normalize(r.product_name_raw, r.brand_raw, commercial.canonical_brand)
                           for r in members.itertuples(index=False)]
        cores = sorted({r.core_name for r in representations if key(r.core_name)})
        forms = sorted({r.product_form for r in representations})
        concs = sorted({c for r in representations for c in r.concentrations})
        brands = self.resolve_brands(commercial.canonical_brand, members)
        pool = []
        cap_excluded = []
        filter_excluded = {}
        for brand, _, _ in brands:
            compatible = []
            for p in self.brand_rows[brand].itertuples(index=False):
                pconcs = old.candidate_concentrations(p.name, p.description)
                if not any(old.form_compatible(form, p.name) for form in forms):
                    filter_excluded[int(p.id)] = "FORM"
                elif concs and pconcs and not set(concs).intersection(pconcs):
                    filter_excluded[int(p.id)] = "CONCENTRATION"
                else:
                    compatible.append(int(p.id))
            # Bound expensive multilingual inference even for very large brands.
            if len(compatible) > MAX_PER_BRAND:
                compatible.sort(key=lambda i: (-max((lexical_score(q, self.perfumes.at[i, "name"])
                                                     for q in cores), default=0), -i))
                cap_excluded.extend(compatible[MAX_PER_BRAND:])
            pool.extend(compatible[:MAX_PER_BRAND])
        return {"representations": representations, "queries": cores, "forms": forms,
                "concentrations": concs, "brands": brands, "pool": pool,
                "filter_excluded": filter_excluded, "cap_excluded": cap_excluded}

    def encode(self, texts):
        import torch
        from sentence_transformers import SentenceTransformer

        texts = sorted(set(texts) - self.embeddings.keys())
        if not texts:
            return
        CACHE.mkdir(parents=True, exist_ok=True)
        digest = old.hashlib.sha256(json.dumps([MODEL, REVISION, texts], ensure_ascii=False).encode()).hexdigest()
        path = CACHE / f"embeddings_{digest}.npz"
        if path.exists():
            vectors = np.load(path, allow_pickle=False)["vectors"]
        else:
            if self.embedder is None:
                torch.set_num_threads(min(4, os.cpu_count() or 1))
                self.embedder = SentenceTransformer(MODEL, revision=REVISION,
                    cache_folder=str(CACHE / "model"), local_files_only=True, device="cpu")
                self.embedder.eval()
            vectors = self.embedder.encode(texts, batch_size=64, normalize_embeddings=True,
                                          show_progress_bar=True, convert_to_numpy=True)
            np.savez_compressed(path, vectors=vectors)
        assert vectors.shape == (len(texts), 384) and np.isfinite(vectors).all()
        self.embeddings.update(zip(texts, vectors))

    def semantic(self, queries, ids):
        if not queries or not ids:
            return []
        query = np.stack([self.embeddings[q] for q in queries])
        names = np.stack([self.embeddings[self.perfumes.at[i, "name"]] for i in ids])
        scores = (names @ query.T).max(axis=1)
        return [ids[j] for j in sorted(range(len(ids)), key=lambda j: (-float(scores[j]), -ids[j]))]

    def lexical(self, queries, ids):
        return sorted(ids, key=lambda i: (-max((lexical_score(q, self.perfumes.at[i, "name"])
                                               for q in queries), default=0), -i))


def fuse(lexical, semantic):
    scores = defaultdict(float)
    # Full bounded rankings keep MRR defined beyond the displayed Top10.
    for ranking in (lexical, semantic):
        for rank, perfume_id in enumerate(ranking, 1):
            scores[perfume_id] += 1 / (RRF_K + rank)
    return sorted(scores, key=lambda i: (-scores[i], -i))


def metrics(results):
    records = []
    for method, frame in results.groupby("method", sort=False):
        groups = [("OVERALL", "ALL", frame)]
        groups += [("SAMPLE_GROUP", group, sub) for group, sub in frame.groupby("sample_group")]
        groups += [("CHALLENGE_TYPE", group, sub) for group, sub in
                   frame[frame.sample_group.eq("CHALLENGE")].groupby("challenge_type")]
        for level, value, sub in groups:
            match = sub[sub.gold_status.eq("MATCH")]
            ranks = pd.to_numeric(match.gold_candidate_rank, errors="coerce")
            record = dict(method=method, level=level, group=value, eligible=len(sub),
                          gold_match=len(match), gold_no_match=int(sub.gold_status.eq("NO_MATCH").sum()))
            record.update({f"recall_at_{k}": float(ranks.le(k).mean()) if len(match) else np.nan for k in (1, 3, 5, 10)})
            record.update(mrr=float(match.reciprocal_rank.mean()),
                          mrr_at_10=float(match.reciprocal_rank.where(ranks.le(10), 0).mean()),
                          top5_miss=int((~ranks.le(5)).sum()), top10_miss=int((~ranks.le(10)).sum()))
            records.append(record)
    return pd.DataFrame(records)


def evaluate(gold, commercial, members, retriever, prepared, rankings, hashes, elapsed):
    """Gold-dependent joins, scoring and diagnostics; no influence on retrieval."""
    saved = pd.read_csv(baseline.RESULTS_PATH, keep_default_na=False).set_index("commercial_identity_id")
    records, failures = [], []
    catalog = retriever.perfumes
    for g in gold.itertuples(index=False):
        ci = g.commercial_identity_id
        info = prepared[ci]
        gold_id = int(g.gold_fragrantica_id) if g.gold_status == "MATCH" else None
        baseline_rank = None
        for method in METHODS:
            ranking = rankings[ci][method]
            assert len(ranking) == len(set(ranking))
            rank = ranking.index(gold_id) + 1 if gold_id in ranking else None
            if method == "baseline_lexical":
                baseline_rank = rank
                previous = saved.loc[ci]
                assert previous.retrieval_top5_ids == "|".join(map(str, ranking[:5]))
                expected_rank = int(float(previous.gold_candidate_rank)) if previous.gold_candidate_rank != "" else None
                assert expected_rank == rank
            top = ranking[:10]
            records.append(dict(queue_id=g.queue_id, method=method, commercial_identity_id=ci,
                sample_group=g.sample_group, challenge_type=g.challenge_type,
                population_stratum=g.population_stratum, raw_product_names=g.raw_product_names,
                gold_status=g.gold_status, gold_fragrantica_id=gold_id,
                gold_fragrantica_name=g.gold_fragrantica_name, gold_candidate_rank=rank,
                reciprocal_rank=1/rank if rank else 0, candidate_count=len(ranking),
                retrieval_top10_ids="|".join(map(str, top)),
                retrieval_top10_names="|".join(catalog.at[i, "name"] for i in top),
                improved_lexical_gold_rank=(rankings[ci]["improved_lexical"].index(gold_id)+1
                                   if gold_id in rankings[ci]["improved_lexical"] else None),
                improved_semantic_gold_rank=(rankings[ci]["improved_semantic"].index(gold_id)+1
                                   if gold_id in rankings[ci]["improved_semantic"] else None)))
        full = rankings[ci]["method1_full"]
        rank = full.index(gold_id)+1 if gold_id in full else None
        if gold_id and (rank is None or rank > 10):
            if gold_id not in catalog.index:
                cause, evidence = "OTHER", "Gold ID absent from local catalog"
            elif catalog.at[gold_id, "brand"] not in [b[0] for b in info["brands"]]:
                cause, evidence = "BRAND_RESOLUTION", "Gold brand outside bounded brand pool"
            elif gold_id in info["filter_excluded"]:
                cause, evidence = "CONCENTRATION_OR_FORM_FILTER", info["filter_excluded"][gold_id]
            elif not info["queries"]:
                cause, evidence = "NORMALIZATION", "No nonempty core query"
            elif gold_id in info["cap_excluded"]:
                cause, evidence = "OTHER", "Per-brand lexical preselection cap excluded gold"
            else:
                # A hypothesis, not proof of causal language error.
                cause = "CROSS_LINGUAL_RETRIEVAL" if any(re.search(r"[가-힣]", q) for q in info["queries"]) else "OTHER"
                evidence = "Gold survives pool/filters; lexical and semantic fusion rank remains >10 (ranking cause provisional)"
            secondary = []
            if any(re.search(r"오\s+드\s+|[,/]\s*(?:중|$)", q) for q in info["queries"]):
                secondary.append("NORMALIZATION: possible unparsed concentration/package residue in core")
            years = re.findall(r"\b(?:19|20)\d{2}\b", g.gold_fragrantica_name)
            if years and not any(year in g.raw_product_names for year in years):
                secondary.append("OTHER: gold distinguishes a year absent from raw product names")
            failures.append(dict(queue_id=g.queue_id, commercial_identity_id=ci,
                raw_product_names=g.raw_product_names, core_queries=json.dumps(info["queries"], ensure_ascii=False),
                gold_id=gold_id, gold_name=g.gold_fragrantica_name,
                gold_brand=catalog.at[gold_id, "brand"] if gold_id in catalog.index else "",
                selected_brands=json.dumps(info["brands"], ensure_ascii=False),
                concentrations="|".join(info["concentrations"]), product_forms="|".join(info["forms"]),
                baseline_rank=baseline_rank, method1_rank=rank,
                lexical_rank=(rankings[ci]["improved_lexical"].index(gold_id)+1
                              if gold_id in rankings[ci]["improved_lexical"] else None),
                semantic_rank=(rankings[ci]["improved_semantic"].index(gold_id)+1
                               if gold_id in rankings[ci]["improved_semantic"] else None), cause=cause,
                evidence=evidence, secondary_review="; ".join(secondary), review_status="MANUAL_CHECK"))
    results = pd.DataFrame(records)
    measured = metrics(results)
    failure_frame = pd.DataFrame(failures)
    prefix = OUT / "fragrantica_method1_dev"
    results.to_csv(f"{prefix}_results.csv", index=False, encoding="utf-8-sig")
    measured.to_csv(f"{prefix}_metrics.csv", index=False, encoding="utf-8-sig")
    failure_frame.to_csv(f"{prefix}_top10_misses.csv", index=False, encoding="utf-8-sig")
    normalization = []
    for ci, info in prepared.items():
        sources = members[members.commercial_identity_id.eq(ci)]
        for representation, source in zip(info["representations"], sources.itertuples(index=False)):
            normalization.append(dict(commercial_identity_id=ci, **asdict(representation),
                source=source.source, source_rank=int(source.source_rank),
                source_product_id=source.source_product_id, brand_basis=source.brand_basis,
                selected_brands=info["brands"], pool_count=len(info["pool"]),
                cap_excluded_count=len(info["cap_excluded"]),
                attribute_conflict=len(info["forms"]) > 1 or len(info["concentrations"]) > 1))
    Path(f"{prefix}_normalization.json").write_text(json.dumps(normalization, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    write_report(results, measured, failure_frame, hashes, elapsed, normalization)
    return measured


def table(frame, columns):
    lines = ["| " + " | ".join(columns) + " |", "|" + "---|" * len(columns)]
    for _, row in frame.iterrows():
        values = []
        for c in columns:
            v = row[c]
            if isinstance(v, (float, np.floating)):
                value = "—" if pd.isna(v) else f"{v:.4f}"
            else:
                value = str(v)
            values.append(value.replace("|", " / ").replace("\n", " "))
        lines.append("| " + " | ".join(values) + " |")
    return lines


def write_report(results, measured, failures, hashes, elapsed, normalization):
    import importlib.metadata
    cols = ["method", "group", "gold_match", "gold_no_match", "recall_at_1", "recall_at_3",
            "recall_at_5", "recall_at_10", "mrr", "mrr_at_10", "top5_miss", "top10_miss"]
    overall = measured[measured.level.eq("OVERALL")].set_index("method")
    b, f = overall.loc["baseline_lexical"], overall.loc["method1_full"]
    lines = ["# Method 1: DEV retrieval comparison", "",
        "## 범위와 방법", "",
        "- 평가 가능 DEV 77개: MATCH 61, NO_MATCH 16. UNRESOLVED 3개 제외. TEST는 읽지 않았다.",
        "- Recall/MRR 분모는 Gold MATCH 61개. NO_MATCH에는 정답 후보가 없어 해당 지표에서 제외하며, 후보를 생성해도 MATCH 판정으로 간주하지 않는다.",
        "- matcher/Verification/threshold/manual override, Raw, Commercial Identity, Candidate Family, Gold, baseline 파일을 수정하지 않았다. match_one도 호출하지 않는다.",
        "- baseline은 기존 evaluate_fragrantica_matcher_dev.retrieve_candidates를 재사용해 전체 순위를 재실행했다. 77개 모두 저장된 Top5와 Gold rank가 정확히 일치해야 결과를 저장한다.",
        "- 입력은 Commercial Identity와 연결된 원본 member 상품명·브랜드·브랜드 근거뿐이다. Candidate Family는 기존 관계 검증에만 사용하며 다른 identity의 상품이나 정답을 합치지 않는다.",
        "- 정규화는 원문, 브랜드, core, 농도, 형태, 제외 문구를 별도로 보존한다. 증정/프로모션 괄호를 먼저 제거한다. 단어 경계로 속성을 분리하고 내부 브랜드/variant token은 유지한다.",
        "- 명시적 raw brand가 완전한 접두어일 때만 core view에서 생략하고 identity_text에 남긴다. 브랜드로 시작하는 동명 제품의 모호성은 이 규칙의 한계다.",
        "- 기존 canonical/alias와 철자 정규화 일치를 우선 후보군에 넣고, 기존 romanize/phonetic 기반 브랜드 후보를 보완한다. 기존 alias를 새로 검증했다고 가정하지 않으며 잘못된 alias를 수정하지 않는다.",
        f"- 브랜드 최대 {MAX_BRANDS}개. exact가 있으면 raw 브랜드 유사도 {SOFT_BRAND_MIN} 이상만 추가, 없으면 상위 {MAX_BRANDS}개로 제한 fallback. 향수 전체를 대상으로 query embedding 검색하지 않는다.",
        f"- 브랜드당 최대 {MAX_PER_BRAND}개. 초과 시 기존 lexical 점수로 선별하므로 한 query 후보군은 최대 {MAX_BRANDS*MAX_PER_BRAND}개. 이 cap은 semantic 채널의 잠재 recall을 제한할 수 있다.",
        "- 농도·형태 비교 함수는 기존 것을 그대로 사용한다. 개선 경로에서만 프로모션을 먼저 분리한 원문으로 query 속성을 다시 추출하며, 명시된 속성 충돌은 복수 값을 유지한다. 후보 description에서 농도를 추정하는 기존 한계도 유지된다.",
        f"- 모델: `{MODEL}`, revision `{REVISION}`. 한국어·영어를 포함하는 다국어 모델이며 짧은 이름의 의미 비교를 낮은 복잡도로 추가하기 위해 384차원 MiniLM을 선택했다.",
        "  [공식 model card](https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2) / [공식 multilingual 모델 설명](https://sbert.net/docs/sentence_transformer/pretrained_models.html)",
        "- CPU float32, 모델 기본 mean pooling/최대 길이 128, L2 정규화 후 cosine. query는 core name, candidate는 원래 Fragrantica name. 여러 member core는 채널별 최대 유사도로 집계한다. 설명문·Gold name·Gold ID는 embedding 입력에 쓰지 않는다.",
        f"- 두 채널 동등 RRF: sum(1/({RRF_K}+rank)), 동점은 ID 내림차순. 유사도 raw score 가중합 없음. MRR 비교를 위해 Top100 절단 대신 제한된 pool의 전체 ranking을 융합했다. 출력은 Top10.",
        "- 별도 fine-tuning, DEV threshold sweep, 제품별 예외, Gold ID alias는 없다. 설정은 첫 DEV 평가 전 고정했다. baseline_multilingual은 기존 query/brand/filter/lexical 순위를 유지한 채 semantic 채널만 추가한다.",
        "- MRR은 각 실험의 전체 허용 pool 순위(미검색=0), MRR@10은 10위 밖=0. pool 범위 자체가 방법의 일부이므로 MRR@10도 함께 비교한다.",
        "", "## 전체 및 ablation", ""]
    lines += table(measured[measured.level.eq("OVERALL")], cols)
    lines += ["", "## Representative / Challenge", ""]
    lines += table(measured[measured.level.eq("SAMPLE_GROUP")], cols)
    lines += ["", "## Challenge 유형별", ""]
    lines += table(measured[measured.level.eq("CHALLENGE_TYPE")], cols)
    wide = results.pivot(index="queue_id", columns="method", values="gold_candidate_rank")
    examples = results[results.method.eq("method1_full") & results.gold_status.eq("MATCH")].copy()
    examples["baseline_rank"] = examples.queue_id.map(wide.baseline_lexical)
    examples["method1_rank"] = examples.gold_candidate_rank
    gains = examples[~examples.baseline_rank.le(5) & examples.method1_rank.le(5)]
    losses = examples[examples.baseline_rank.le(5) & ~examples.method1_rank.le(5)]
    lines += ["", "## 변화와 관찰", "",
        f"- R@1 {b.recall_at_1:.4f} → {f.recall_at_1:.4f}, R@5 {b.recall_at_5:.4f} → {f.recall_at_5:.4f}, R@10 {b.recall_at_10:.4f} → {f.recall_at_10:.4f}, MRR {b.mrr:.4f} → {f.mrr:.4f}.",
        f"- Top5 miss {int(b.top5_miss)} → {int(f.top5_miss)}; Top10 miss {int(b.top10_miss)} → {int(f.top10_miss)}. 새 Top5 적중 {len(gains)}개, 기존 Top5 적중 상실 {len(losses)}개."]
    for method in ("improved_lexical", "baseline_multilingual"):
        row = overall.loc[method]
        lines.append(f"- {method}: baseline 대비 ΔR@5={row.recall_at_5-b.recall_at_5:+.4f}, ΔMRR={row.mrr-b.mrr:+.4f}.")
    row = overall.loc["improved_lexical"]
    lines.append(f"- 개선 lexical에 semantic 추가 효과: ΔR@5={f.recall_at_5-row.recall_at_5:+.4f}, ΔMRR={f.mrr-row.mrr:+.4f}. 정규화와 브랜드 효과는 이 실험에서 묶여 있으므로 각각의 인과 기여로 분리할 수 없다.")
    semantic_hits = examples.improved_semantic_gold_rank.le(5)
    fusion_losses = examples.improved_lexical_gold_rank.le(5) & ~examples.method1_rank.le(5)
    lines += [
        f"- 개선 pool의 semantic 단독 R@5는 {semantic_hits.mean():.4f}. 개선 lexical의 Top5 적중 중 {int(fusion_losses.sum())}개가 RRF 후 Top5에서 탈락했다. rank fusion은 점수 스케일을 맞추지만 부정확한 채널의 영향을 자동으로 억제하지 않는다.",
        "- 브랜드 soft score는 기존 match_score의 자음 중심 phonetic 최대값도 사용한다. Clean에 Aquolina/Caron이 1.0으로 추가되는 등 짧은 이름의 충돌이 관찰됐다. 따라서 0.75 cutoff는 검증된 브랜드 확신도로 해석할 수 없다. 기존 alias 우선 포함만으로는 distractor 순위 상승을 막지 못했다.",
        "- D018 에끌로에: 기존 Vivienne Westwood pool에서 정답이 없었으나 raw 브랜드 음역으로 BiBiANG이 추가되어 lexical/full 모두 2위. D002 Glow: 증정 바디로션을 제거한 뒤 본품 형태가 BODY_FRAGRANCE에서 LIQUID_PERFUME으로 복구되어 lexical 5위/full 6위.",
        "- D007 Red Roses: 농도를 분리한 core로 lexical 34→1위, full 1위. D001 Fresia는 lexical 24위지만 semantic 4위 덕분에 full 5위로 개선됐다.",
        "- D078 Cool Cotton: 쿨 token은 보존되어 개선 lexical 1위지만 semantic 188위, full 14위로 회귀했다. token 보존 자체와 multilingual 순위 개선은 별개다."]
    lines += ["", "### Top5 개선 사례", ""]
    example_cols = ["queue_id", "raw_product_names", "gold_fragrantica_name", "baseline_rank", "method1_rank"]
    lines += table(gains.head(10), example_cols)
    lines += ["", "### Top5 회귀 사례 (전체)", ""] + table(losses, example_cols)
    lines += ["", "## Method 1 Top10 miss (전체)", "",
        "브랜드/필터 배제는 실행 경로로 확인했다. CROSS_LINGUAL_RETRIEVAL은 한국어 query가 있는 순위 실패의 잠정 분류이며, 음역·variant·연도 구분·정규화 잔여 noise 중 무엇이 주원인인지는 MANUAL_CHECK가 필요하다.", ""]
    if len(failures):
        lines += table(failures, ["queue_id", "raw_product_names", "core_queries", "gold_name", "method1_rank", "lexical_rank", "semantic_rank", "cause", "evidence", "secondary_review"])
        lines += ["", "원인별: " + ", ".join(f"{k}={v}" for k, v in failures.cause.value_counts().items())]
        lines += ["", "추가 수동 검토 관찰:",
            "- NORMALIZATION: D030에 `, / 중` 패키지 잔여 문구, D038에 `오 드 뜨왈렛` 미인식 농도 표현이 남는다. 초기 실험의 정규화 한계로 보존했으며 DEV를 보고 제품별 수정 규칙을 추가하지 않았다.",
            "- NORMALIZATION: D008은 query에서 앞의 브랜드를 분리해 `포 허`가 되지만 candidate `Narciso Rodriguez For Her`에는 브랜드가 남아 lexical 1→15위로 악화했다. query/candidate 표기의 비대칭과 과도하게 짧은 core도 검토 대상이다.",
            "- OTHER: D016/D028/D047의 Gold는 연도별 identity를 지정하지만 원문에는 해당 연도가 없다. 순위 실패를 cross-lingual 문제만으로 단정할 수 없다.",
            "- BRAND_RESOLUTION: Tenui/Sennok/Kiehl's/RboW/Dashu는 로컬 catalog에 있지만 제한한 브랜드 pool에서 빠졌다. raw 음역 후보의 동점과 다른 철자 때문에 fallback이 정답 브랜드를 보장하지 못했다.",
            "- CONCENTRATION_OR_FORM_FILTER: D056은 query가 HAIR_FRAGRANCE이고 catalog name 기반 판별은 LIQUID_PERFUME이라 기존 형태 필터에서 제외됐다. 형태 필터는 변경하지 않았다.",
            "- OTHER: D037 Etlee Twilight Bloom과 D054 Day Off의 Gold ID는 perfumes.csv에 없다. 현 catalog만으로 이 2개는 retrieval 불가능하다. Gold 61개 분모는 baseline과 동일하게 유지했다."]
    else:
        lines += ["Top10 miss 없음."]
    conflicts = sum(r["attribute_conflict"] for r in normalization)
    lines += ["", "## 결론 및 한계", "",
        ("DEV 기준 full Method 1은 baseline보다 R@5와 MRR이 모두 개선됐다." if f.recall_at_5 > b.recall_at_5 and f.mrr > b.mrr
         else "DEV 기준 full Method 1은 baseline보다 주요 Recall과 MRR이 하락했다. 이번 전체 조합의 retrieval 개선은 확인되지 않았으며 baseline 교체를 권하지 않는다."),
        f"Top10 miss {len(failures)}개는 MANUAL_CHECK로 남겼고 Gold UNRESOLVED 3개는 계속 제외했다. 구조화 member 중 attribute conflict 표시 {conflicts}행.",
        "DEV는 개발용 표본이며 일반화 성능이나 최종 MATCH Precision 개선을 입증하지 않는다. NO_MATCH 16개에 대한 거절 성능은 평가하지 않았다. Listwise / Identity-aware Verification은 구현하지 않았다.",
        "일반 다국어 의미 모델은 고유명사 음역, 유사 flankers, 출시 연도와 리포뮬레이션 identity를 보장하지 않는다. 기존 별칭 오류, standalone 프로모션 단어와 실제 이름의 중복, description 농도 추출이 남아 있다.",
        "다음 Verification 구현에 앞서 이번 결과를 검토해야 한다. 구조화 입력과 브랜드 fallback의 일부 복구 효과는 있으나, 현재 모델과 동등 RRF의 결합을 그대로 채택할 근거는 없다.",
        "", "## 재현 및 검증", "",
        "- 실행: `venv/Scripts/python.exe evaluate_fragrantica_method1_dev.py` (사전 다운로드 모델 필요, 실행은 offline).",
        f"- retrieval 준비/추론 실행시간: {elapsed:.2f}초 (캐시 여부에 따라 달라짐).",
        "- synthetic normalization 보존 검사, DEV 구성/identity/family 관계 검사, baseline Top5/rank 전수 일치, candidate 중복 검사, 입력 파일 SHA-256 불변 검사를 실행했다.",
        f"- 실제 최대 query pool {max(r['pool_count'] for r in normalization)}개; per-brand cap으로 제외된 member별 기록 합계 {sum(r['cap_excluded_count'] for r in normalization)}개 (중복 member 포함).",
        "- 모델 별도 sanity 실행: `장미 향기`↔`rose fragrance` cosine 0.897, `자동차 엔진`↔`car engine` 0.918. L2 norm 약 1, batch/단일 입력 embedding 일치(atol=1e-5). `쿨 코튼`↔`Cool Cotton`은 0.321로, `Or et Noir`와의 0.537보다 낮았다. 이는 이 샘플의 모델 표현 한계이며 설정 조정에 사용하지 않았다.",
        "- 프로젝트 환경의 pip check: No broken requirements found.",
        "- 새 의존성 sentence-transformers와 CPU torch를 프로젝트 venv에 설치했다. 모델·임베딩 캐시는 gitignore 대상 cache/method1에 둔다."]
    for package in ("sentence-transformers", "transformers", "torch", "numpy", "pandas"):
        lines.append(f"- {package}: {importlib.metadata.version(package)}")
    for path, digest in hashes.items():
        lines.append(f"- `{path.relative_to(ROOT)}` SHA-256: `{digest}`")
    (OUT / "fragrantica_method1_dev_report.md").write_text("\n".join(lines)+"\n", encoding="utf-8")


def main():
    baseline.verify_snapshot()  # 재현 게이트의 기준 스냅샷 고정 (9a-4)
    baseline.use_llm_channel(None)  # 기록값은 LLM 채널 도입 전 측정본이다 (9c)
    baseline.use_verification(False)  # 기록값은 Verification 도입 전 측정본이다 (10b)
    start = time.perf_counter()
    inputs = [baseline.GOLD_PATH, baseline.COMMERCIAL_PATH, baseline.PERFUMES_PATH,
              baseline.RESULTS_PATH, baseline.REPORT_PATH, ROOT / "src" / "korea" / "build_korea_popularity_map.py",
              Path(__file__).resolve(),
              ROOT / "src" / "matching" / "evaluate_fragrantica_matcher_dev.py", baseline.MEMBERS_PATH,
              baseline.FAMILIES_PATH]
    hashes = {path: old.sha256(path) for path in inputs}
    validate_normalization()
    gold = pd.read_csv(baseline.GOLD_PATH, keep_default_na=False)
    assert len(gold) == 80 and gold.split.eq("DEV").all()
    eligible = gold[baseline.as_bool(gold.evaluation_eligible)].copy()
    assert len(eligible) == 77 and eligible.gold_status.value_counts().to_dict() == {"MATCH": 61, "NO_MATCH": 16}
    assert gold[~baseline.as_bool(gold.evaluation_eligible)].gold_status.eq("UNRESOLVED").all()
    commercial = pd.read_csv(baseline.COMMERCIAL_PATH, keep_default_na=False).set_index("commercial_identity_id", drop=False)
    members = pd.read_csv(baseline.MEMBERS_PATH, keep_default_na=False)
    families = pd.read_csv(baseline.FAMILIES_PATH, keep_default_na=False)
    assert commercial.candidate_family_id.isin(families.candidate_family_id).all()
    perfumes = pd.read_csv(baseline.PERFUMES_PATH, usecols=["id", "name", "brand", "description"], keep_default_na=False)
    assert perfumes.id.is_unique
    retriever = Retriever(perfumes)
    baseline_brands = {old.latin_key(b): g for b, g in perfumes.groupby("brand", sort=False) if old.latin_key(b)}
    prepared, rankings, texts = {}, {}, set()
    # Only the unlabeled identity IDs select DEV input; no label/name/ID enters retrieval.
    for ci in eligible.commercial_identity_id:
        row = commercial.loc[ci]
        mem = members[members.commercial_identity_id.eq(ci)]
        assert len(mem) and len(mem) == int(row.member_count)
        info = retriever.prepare(row, mem)
        prepared[ci] = info
        candidates = baseline.retrieve_candidates(row, baseline_brands.get(old.latin_key(row.canonical_brand), pd.DataFrame()))
        original = [x[1] for x in candidates]
        improved = retriever.lexical(info["queries"], info["pool"])
        rankings[ci] = {"baseline_lexical": original, "improved_lexical": improved}
        texts.update(info["queries"])
        texts.add(row.fragrance_name_normalized)
        texts.update(retriever.perfumes.loc[list(set(original + improved)), "name"])
    print(f"Prepared {len(prepared)} identities; embedding {len(texts)} unique strings", flush=True)
    retriever.encode(texts)
    for ci, ranking in rankings.items():
        info = prepared[ci]
        ranking["baseline_multilingual"] = fuse(ranking["baseline_lexical"], retriever.semantic(
            [commercial.loc[ci].fragrance_name_normalized], ranking["baseline_lexical"]))
        ranking["improved_semantic"] = retriever.semantic(info["queries"], info["pool"])
        ranking["method1_full"] = fuse(ranking["improved_lexical"], ranking["improved_semantic"])
    assert all(old.sha256(p) == digest for p, digest in hashes.items())
    measured = evaluate(eligible, commercial, members, retriever, prepared, rankings, hashes, time.perf_counter()-start)
    assert all(old.sha256(p) == digest for p, digest in hashes.items())
    print(measured[measured.level.eq("OVERALL")].to_string(index=False), flush=True)


if __name__ == "__main__":
    main()

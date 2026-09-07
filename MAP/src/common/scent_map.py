"""향 지도 공통 로직 — 데이터 로드, 대상 선정, Base Similarity.

Base Similarity는 EDA 04~06에서 이미 측정으로 확정된 함수를 그대로 재현한다.

    sim(a, b) = 0.5 * cosine(accord strength, L2 정규화)
              + 0.5 * IDF 가중 Jaccard(note 합집합)

EDA에서 측정으로 기각된 것들이라 여기서 다시 시도하지 않는다:
  - note tier(top/middle/base) 가중  → 06, beta 스윕 단조 감소
  - accord에 IDF 적용                → 05, NDCG@10 0.2688 -> 0.2603
  - popularity를 유사도로 사용        → 04, NDCG@10 0.0113
"""
import os
import re

import numpy as np
import pandas as pd

MAP_DIR = os.path.dirname(os.path.abspath(__file__))
EDA_DIR = os.path.join(os.path.dirname(MAP_DIR), "EDA")
CACHE = os.path.join(MAP_DIR, "cache")

PERFUMES_CSV = os.path.join(MAP_DIR, "perfumes.csv")
NOTE_DICT_CSV = os.path.join(EDA_DIR, "analysis_outputs", "10_note_dictionary.csv")

N_TOTAL_CORPUS = 131930  # IDF 계산 기준. EDA 05와 동일하게 전체 코퍼스 크기를 쓴다.

NOTE_COLS = ["notes_top", "notes_middle", "notes_base", "notes_flat"]

# --------------------------------------------------------------------------
# 향 계열
# --------------------------------------------------------------------------
# Fragrantica는 각 향수 설명문에 자기네 계열 분류를 넣어둔다.
#   "Amarige by Givenchy is a Floral fragrance for women."
# 전체의 83.6%에서 추출되고, 첫 단어 기준으로 사실상 7종이다.
FAMILY_RE = re.compile(r" is an? ([A-Za-z ]+?) fragrance for ")

# 7종을 Michael Edwards / Fragrances of the World Fragrance Wheel의
# 4대 그룹으로 묶는다. 팀 문서(EDA/data/scent_knowledge/source/
# perfume_14families_korean_descriptors.md)가 기준으로 삼는 그 휠이다.
#
#   Floral  <- Floral (휠의 Floral / Soft Floral / Floral Amber)
#   Amber   <- Oriental (휠이 2021년에 Oriental -> Amber로 개칭)
#   Woody   <- Woody / Chypre(휠의 Mossy Woods) / Leather(휠의 Dry Woods)
#   Fresh   <- Citrus / Aromatic(휠의 Aromatic Fougere)
#
# 휠에 근거가 있는 대응만 넣었다. 근거 없는 계열은 만들지 않는다.
FAMILY_GROUP = {
    "Floral": "Floral",
    "Oriental": "Amber",
    "Woody": "Woody",
    "Chypre": "Woody",
    "Leather": "Woody",
    "Citrus": "Fresh",
    "Aromatic": "Fresh",
}
GROUP_ORDER = ["Floral", "Amber", "Woody", "Fresh"]


def extract_family(description):
    """설명문에서 Fragrantica 계열 표기를 뽑는다. 예: 'Floral Fruity'"""
    if not isinstance(description, str):
        return None
    m = FAMILY_RE.search(description)
    return m.group(1) if m else None


def family_group(label):
    """계열 표기의 첫 단어로 4대 그룹을 정한다. 대응이 없으면 None."""
    if not isinstance(label, str) or not label.strip():
        return None  # 결측은 NaN(float)으로 들어온다
    return FAMILY_GROUP.get(label.split()[0])


# --------------------------------------------------------------------------
# 로드
# --------------------------------------------------------------------------
def parse_accords(s):
    """'citrus:100|fresh spicy:47' -> [('citrus', 100.0), ('fresh spicy', 47.0)]"""
    if not isinstance(s, str) or not s:
        return []
    out = []
    for item in s.split("|"):
        if not item:
            continue
        name, _, strength = item.rpartition(":")
        try:
            out.append((name, float(strength)))
        except ValueError:
            pass
    return out


def _split_notes(value, known_vocab):
    """perfumes.csv의 note 컬럼은 '|'로 구분되는데, note 이름 자체에 '|'가
    들어간 경우가 있어(`Eustoma | Lisianthus`) 이스케이프 없이 쪼개진다.
    EDA가 JSONL로 만든 정식 vocabulary(2,523종)를 기준으로 되붙인다.
    """
    parts = value.split("|")
    out, i = [], 0
    while i < len(parts):
        tok = parts[i]
        if tok not in known_vocab and i + 1 < len(parts):
            merged = tok + "|" + parts[i + 1]
            if merged in known_vocab:
                out.append(merged)
                i += 2
                continue
        if tok:
            out.append(tok)
        i += 1
    return out


def parse_notes(row, known_vocab):
    """tier 구분 없이 합집합. EDA 06에서 tier 가중이 기각됐다."""
    out = set()
    for col in NOTE_COLS:
        v = row[col]
        if isinstance(v, str) and v:
            out.update(_split_notes(v, known_vocab))
    return out


def load_perfumes():
    """CSV에서 특징을 읽고, people은 JSONL 캐시의 값으로 덮어쓴다.

    CSV의 people은 결측이 0으로 저장돼 있어(10,405건) 그대로 쓰면 안 된다.
    """
    df = pd.read_csv(
        PERFUMES_CSV,
        low_memory=False,
        usecols=["id", "slug", "name", "brand", "year", "gender", "vote_count",
                 "accords", "description",
                 "winter", "spring", "summer", "autumn", "day", "night"]
        + NOTE_COLS,
    )
    df["vote_count"] = pd.to_numeric(df["vote_count"], errors="coerce").fillna(0).astype(int)

    people = pd.read_csv(os.path.join(CACHE, "people.csv"))
    df = df.merge(people, on="id", how="left")  # people: 결측은 NaN 유지

    known_notes = set(load_note_idf())
    df["accord_list"] = df["accords"].map(parse_accords)
    df["note_set"] = df.apply(parse_notes, axis=1, known_vocab=known_notes)
    df["dominant_accord"] = df["accord_list"].map(lambda l: l[0][0] if l else None)
    df["family"] = df["description"].map(extract_family)
    df["group"] = df["family"].map(family_group)
    df.drop(columns=["description"], inplace=True)
    return df


def load_edges(name):
    return pd.read_csv(os.path.join(CACHE, name))


# --------------------------------------------------------------------------
# 대상 선정 (PLAN.md §3.5)
# --------------------------------------------------------------------------
def _allocate(sizes, n_total, floor=1, cap=None):
    """제곱근 비례 배분. 큰 항목의 지배를 누르되 꼬리를 과대표집하지 않는다.

    보유량을 넘지 않게 자르고, 반올림 때문에 어긋난 합은 가장 큰 쪽에서 빼고
    여유 있는 쪽에 더해 맞춘다.
    """
    sizes = sizes[sizes > 0]
    weight = np.sqrt(sizes.astype(float))
    quota = (weight / weight.sum() * n_total).round().astype(int)
    quota = quota.clip(lower=min(floor, int(sizes.min())))
    if cap is not None:
        quota = quota.clip(upper=cap)
    quota = quota.clip(upper=sizes)

    guard = 0
    while quota.sum() > n_total and guard < 100000:
        room = quota[quota > 1]
        if room.empty:
            break
        quota[room.idxmax()] -= 1
        guard += 1
    while quota.sum() < n_total and guard < 200000:
        room = sizes - quota
        room = room[room > 0]
        if room.empty:
            break
        quota[room.idxmax()] += 1
        guard += 1
    return quota


def usable_pool(df, pool_min_people=500, popularity_col="vote_count"):
    """지도에 올릴 수 있는 후보. group이 없는 향수는 제외한다.

    group은 Fragrantica가 설명문에 넣어둔 계열 분류에서 나온다.
    없는 향수에 계열을 추측해서 붙이지 않는다 (근거 없는 분류 금지).
    """
    usable = df[
        df["accord_list"].str.len().gt(0)
        & df["note_set"].str.len().gt(0)
        & df["group"].notna()
    ]
    return usable[usable[popularity_col] >= pool_min_people]


def select_targets(df, n_total=1000, pool_min_people=500, popularity_col="vote_count",
                   inner_col="dominant_accord"):
    """4대 그룹에 제곱근 비례로 정원을 나누고, 그룹 안에서 다시 배분한다.

    그룹이 4개뿐이라 2단계 배분이 없으면 각 그룹이 그냥 "가장 유명한 플로럴
    300개"가 되어 지도에 구멍이 생긴다. 실제로 측정했다 (1000개 기준):

        그룹 정원만               accord 42종 / 브랜드 196 / 상위10 브랜드 27.8%
        그룹 정원 + 세부계열       accord 42종 / 브랜드 196
        그룹 정원 + accord (채택)  accord 58종 / 브랜드 223 / 상위10 브랜드 25.3%

    accord로 2단계를 나누는 쪽이 커버리지와 브랜드 다양성 모두 낫다.
    대가는 정답 간선 905 -> 872 (-3.6%)로 작다.
    """
    pool = usable_pool(df, pool_min_people, popularity_col)
    outer = _allocate(pool.groupby("group").size(), n_total)

    picked = []
    for grp, q in outer.items():
        g = pool[pool["group"] == grp]
        inner = _allocate(g.groupby(inner_col).size(), int(q))
        for key, fq in inner.items():
            sub = g[g[inner_col] == key]
            picked.append(sub.sort_values(popularity_col, ascending=False).head(int(fq)))
    out = pd.concat(picked).reset_index(drop=True)
    return out, outer


def mark_display(targets, n_display=200, popularity_col="vote_count"):
    """화면에 처음 보여줄 N개. 1000개와 같은 그룹 배분 규칙을 쓴다.

    여기서만 인기순으로 뽑으면 첫 화면에 다시 빈 구역이 생겨
    그룹 배분의 취지가 사라진다.
    """
    quota = _allocate(targets.groupby("group").size(), n_display)
    display_ids = set()
    for grp, q in quota.items():
        g = targets[targets["group"] == grp]
        display_ids.update(g.sort_values(popularity_col, ascending=False).head(int(q))["id"])
    return targets["id"].isin(display_ids)


# --------------------------------------------------------------------------
# Base Similarity (EDA 04~06)
# --------------------------------------------------------------------------
def build_accord_matrix(rows):
    """raw strength를 그대로 쓰고 행 L2 정규화. accord IDF는 05에서 기각됐다."""
    vocab = sorted({name for lst in rows for name, _ in lst})
    index = {a: i for i, a in enumerate(vocab)}
    X = np.zeros((len(rows), len(vocab)), dtype=np.float64)
    for r, lst in enumerate(rows):
        for name, strength in lst:
            X[r, index[name]] = strength
    norm = np.linalg.norm(X, axis=1, keepdims=True)
    norm[norm == 0] = 1.0
    return X / norm, vocab


def load_note_idf():
    """EDA 10_note_dictionary.csv의 idf를 재사용한다. 다시 계산하지 않는다."""
    nd = pd.read_csv(NOTE_DICT_CSV)
    return dict(zip(nd["note"], nd["idf"]))


def build_note_matrix(rows, idf_map):
    vocab = sorted({n for s in rows for n in s})
    index = {n: i for i, n in enumerate(vocab)}
    fallback = np.log((N_TOTAL_CORPUS + 1) / 1) + 1  # 사전에 없는 note (df=0 취급)
    weights = np.array([idf_map.get(n, fallback) for n in vocab], dtype=np.float64)
    B = np.zeros((len(rows), len(vocab)), dtype=np.float64)
    for r, s in enumerate(rows):
        for n in s:
            B[r, index[n]] = 1.0
    n_missing = sum(1 for n in vocab if n not in idf_map)
    return B, weights, vocab, n_missing


def base_similarity(accord_lists, note_sets, idf_map, accord_weight=0.5):
    """PLAN.md §2.1. 반환값은 (1000, 1000) 유사도 행렬."""
    A, _ = build_accord_matrix(accord_lists)
    s_accord = A @ A.T

    B, w, _, _ = build_note_matrix(note_sets, idf_map)
    Bw = B * w
    inter = Bw @ B.T                       # 교집합의 idf 합
    row_sum = Bw.sum(axis=1)
    union = row_sum[:, None] + row_sum[None, :] - inter
    s_note = np.divide(inter, union, out=np.zeros_like(inter), where=union > 0)

    S = accord_weight * s_accord + (1 - accord_weight) * s_note
    np.clip(S, 0.0, 1.0, out=S)
    return S, s_accord, s_note

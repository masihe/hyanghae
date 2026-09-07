"""Audit the local 999-row snapshot; preserve all raw columns and rows.

Run with venv/Scripts/python.exe analyze_korea_rankings.py.
Standard library only. No network, matching, cleaning, or SKU merging.
All flags and comparison keys are review candidates, not final classifications.
"""
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # MAP/
DATA = ROOT / "data/korea_popularity"
RAW = DATA / "korea_perfume_ranking_raw.csv"
AUDIT = DATA / "korea_perfume_ranking_audit.csv"
REPORT = DATA / "korea_perfume_ranking_analysis.md"
SOURCES = {"musinsa": 350, "oliveyoung": 350, "lotte": 299}
RAW_SHA256 = "820e2a3ab0bea1076a21a8b9e98e037a6c5d0b5fc87eb1dfa709ab00aac51576"

# Lexical matches concern the whole title, including gifts and advertisements.
PATTERNS = {
    "hair_body_mention": r"헤어|바디|hair|body",
    "mist_mention": r"미스트|(?<![a-z])mist(?![a-z])",
    "home_mention": r"룸\s*(?:스프레이|&패브릭)|섬유\s*향수|디퓨저|캔들|샤쉐|사쉐|인센스",
    "care_accessory_mention": r"샤워젤|샤워시트|샴푸|핸드크림|바디밀크|로션|모이스처라이저|애프터쉐이브|공병",
    "solid_cream_stick_mention": r"고체|솔리드|퍼퓸\s*밤|크림\s*퍼퓸|퍼퓸\s*젤|퍼퓸\s*스틱",
    "oil_rollon_mention": r"오일\s*퍼퓸|롤\s*온|롤러볼",
    "intimate_mention": r"이너\s*퍼퓸|속옷\s*향수|Y존",
    "explicit_option": r"택\s*\d+|선택|골라",
    "planning_set": r"기획|세트|키트|(?<![a-z])(?:set|kit|pack)(?![a-z])|(?<![가-힣])듀오|트리오|\d+\s*\+\s*\d+|\d+\s*개입|ml\s*[x×*]\s*\d+",
    "gift_mention": r"증정|기프트|선물박스|선물포장|사은품|포함",
    "discovery_trial_mention": r"디스커버리|트라이얼|discovery|trial|expedition\s+set",
    "sample_mini_mention": r"디스커버리|트라이얼|discovery|trial|expedition\s+set|샘플|sample|시향|바이알|미니어[처쳐]",
    "refill_mention": r"(?<![가-힣])리필|(?<![a-z])refill(?![a-z])",
    "possible_unit_typo": r"\d+(?:\.\d+)?m(?![a-z])",
}
RX = {k: re.compile(v, re.I) for k, v in PATTERNS.items()}
NUMBER = r"\d+(?:\.\d+)?"
VOLUME = re.compile(rf"(?<![\d.])({NUMBER}(?:\s*[/,]\s*{NUMBER})*)\s*(ml|㎖|g|그램|oz)(?=$|[^a-z]|x\s*\d)", re.I)
VOLUME_CHOICE = re.compile(rf"{NUMBER}\s*(?:ml|㎖)?\s*[/,]\s*{NUMBER}\s*(?:ml|㎖)", re.I)
CONCENTRATION = {
    "EDP": re.compile(r"(?<![a-z])edp(?![a-z])|오\s*드\s*퍼퓸|eau\s+de\s+parfum", re.I),
    "EDT": re.compile(r"(?<![a-z])edt(?![a-z])|오\s*드\s*뚜[왈알]렛|eau\s+de\s+toilette", re.I),
    "Extrait": re.compile(r"엑스트레(?:\s*드\s*퍼퓸)?|(?<![a-z])extrait(?:\s+de\s+parfum)?(?![a-z])", re.I),
    "Cologne_EDC": re.compile(r"(?<![a-z])edc(?![a-z])|오\s*드\s*코[롱론]|(?<![a-z])(?:eau\s+de\s+)?cologne(?![a-z])", re.I),
    "Parfum_word": re.compile(r"(?<![a-z])parfum(?![a-z])|파르[퓜품]|파팡", re.I),
}

# Analyst-reviewed TITLE contexts, tied to this immutable snapshot's ranks.
# These are still candidates: no product-detail/ingredient verification occurred.
REVIEWED = {
    "main_nonperfume": {"musinsa": [17, 36, 90, 170, 185, 204, 234, 280], "oliveyoung": [55, 280, 283]},
    "main_hair_body": {"musinsa": [59, 72, 86, 162, 250, 252, 253, 266],
                       "oliveyoung": [5,21,24,28,32,64,65,75,100,101,116,117,118,119,122,140,143,166,167,217,218,252,271,272,273,274,275,281,282,291,340]},
    "main_solid_cream_stick": {"musinsa": [46,52,69,80,97,103,107,140,238,246,262,329], "oliveyoung": [58,66,121,278,319,335]},
    "mixed_product_types": {"oliveyoung": [12,15,16,46,77,255]},
    "discovery_trial_main": {"musinsa": [91,105,117,123,154,264], "oliveyoung": [142,340]},
    "unclear_use": {"musinsa": [67,74,85,122,126,224,237,272,273,298,299,340,350]},
}
REVIEW_REASON = {
    "main_nonperfume": "상품명에서 주상품을 실내/섬유 방향 또는 세정/보습/시트로 확인한 후보",
    "main_hair_body": "상품명에서 주상품을 헤어/바디 향 제품으로 확인한 후보",
    "main_solid_cream_stick": "고체/크림/밤/젤/스틱 제형 표기 후보; 실제 제형은 미확인",
    "mixed_product_types": "일반 향수와 다른 용도/제형이 같은 판매상품명에 함께 나타남",
    "discovery_trial_main": "디스커버리/트라이얼/소용량 다종 키트가 주상품으로 보이는 후보",
    "unclear_use": "스프레이/멀티 프래그런스/미스트만으로 인체용 또는 공간용 판별 불가",
}


def matches(rx, text):
    return list(dict.fromkeys(m.group(0) for m in rx.finditer(text)))


def comparison_text(name):
    """Temporary candidate key text, NEVER an output product name."""
    # Preserve bracketed brand/scent names; strip only marked advertising.
    name = re.sub(r"\[([^\]]*)\]", lambda m: " " if re.search(
        r"PICK|기획|증정|기프트|SET|단독|NEW|LIMITED|리뷰|이벤트|\d+위|특가|선물포장", m[1], re.I)
        else m[1], name)
    name = re.sub(r"\([^()]*(?:바이알|미니어[처쳐]|샘플|증정|단품|기획)[^()]*\)", " ", name)
    # A '+' after an explicit size is an addition candidate. Keep the title in raw.
    plus = name.find("+")
    if plus >= 0 and VOLUME.search(name[:plus]):
        name = name[:plus]
    name = VOLUME.sub(" ", name)
    name = re.sub(r"단품|단독기획|기획세트|기획|세트", " ", name)
    # Do NOT equate EDP/EDT, brand aliases, translations, or spelling errors.
    return re.sub(r"[\W_]+", "", name.casefold())


def analyze(rows):
    audited = []
    for line, row in enumerate(rows, 2):
        n = row["product_name_raw"]
        a = dict(row, audit_raw_csv_line=line)
        evidence = {}
        for flag, rx in RX.items():
            evidence[flag] = matches(rx, n)
            a["flag_" + flag] = int(bool(evidence[flag]))
        review_types = [key for key, sources in REVIEWED.items()
                        if int(row["source_rank"]) in sources.get(row["source"], [])]
        a["review_candidate_types"] = ";".join(review_types)
        a["review_context_note"] = " / ".join(REVIEW_REASON[k] for k in review_types)
        for key in REVIEWED:
            a["flag_" + key] = int(key in review_types)

        volumes = []
        for m in VOLUME.finditer(n):
            unit = {"㎖": "ml", "그램": "g"}.get(m[2].lower(), m[2].lower())
            for value in re.findall(NUMBER, m[1]):
                volumes.append({"text": m[0], "value": value, "unit": unit})
        a["volume_mentions_json"] = json.dumps(volumes, ensure_ascii=False)
        a["volume_value_count"] = len(volumes)
        a["volume_distinct_count"] = len({(v["value"], v["unit"]) for v in volumes})
        a["flag_volume_choice"] = int(bool(VOLUME_CHOICE.search(n)))
        a["flag_multiple_volume_values"] = int(len(volumes) > 1)

        # Remove detailed concentration phrases before checking generic Parfum.
        remaining = n
        labels = []
        for label, rx in CONCENTRATION.items():
            found = matches(rx, remaining)
            evidence["concentration_" + label] = found
            a["flag_concentration_" + label] = int(bool(found))
            if found:
                labels.append(label)
                remaining = rx.sub(" ", remaining)
        a["concentration_labels"] = ";".join(labels)
        a["flag_concentration_unidentified"] = int(not labels)
        a["flag_multiple_concentrations"] = int(len(labels) > 1)
        a["flag_generic_perfume_only"] = int(not labels and bool(re.search(r"퍼퓸|perfume", n, re.I)))
        evidence["unmapped_concentration_code"] = matches(re.compile(r"(?<![a-z])(?:EDPI|EXDP|EXT|PFM)(?![a-z])", re.I), n)

        # Count expressions in gift parentheses are not main-product choices.
        main_context = re.sub(r"\([^()]*(?:바이알|미니어[처쳐]|샘플|증정)[^()]*\)", " ", n)
        main_context = re.sub(r"\[[^\]]*증정[^\]]*\]", " ", main_context)
        plus = main_context.find("+")
        if plus >= 0 and VOLUME.search(main_context[:plus]):
            main_context = main_context[:plus]
        evidence["main_count_options"] = [m[0] for m in re.finditer(r"(\d+)\s*종", main_context) if int(m[1]) >= 2]
        a["flag_count_option_candidate"] = int(bool(evidence["main_count_options"]) and not a["flag_discovery_trial_main"])
        a["flag_multi_option_candidate"] = int(bool(a["flag_explicit_option"] or
            a["flag_count_option_candidate"] or a["flag_volume_choice"] or a["flag_mixed_product_types"]))
        # Bare slash-separated scent lists are reviewed separately, not assumed.
        a["flag_unresolved_slash"] = int("/" in main_context and not a["flag_multi_option_candidate"])
        a["flag_sample_addon_candidate"] = int(a["flag_sample_mini_mention"] and not a["flag_discovery_trial_main"])
        a["flag_bundle_or_gift_candidate"] = int(bool(a["flag_planning_set"] or a["flag_gift_mention"] or
            a["flag_sample_addon_candidate"] or ("+" in n and VOLUME.search(n))))
        a["flag_nonstandard_main_candidate"] = int(any(a["flag_"+k] for k in (
            "main_nonperfume", "main_hair_body", "main_solid_cream_stick", "mixed_product_types"))
            or a["flag_intimate_mention"])
        a["comparison_key_candidate"] = comparison_text(n)
        a["flag_duplicate_comparison_eligible"] = int(not (a["flag_multi_option_candidate"] or
            a["flag_discovery_trial_main"] or a["flag_multiple_concentrations"]))
        a["flag_evidence_json"] = json.dumps({k:v for k,v in evidence.items() if v}, ensure_ascii=False)
        audited.append(a)

    for field, title_key, eligible in (
        ("exact_title_group", "product_name_raw", False),
        ("sku_candidate_group", "comparison_key_candidate", True),
    ):
        groups = defaultdict(list)
        for a in audited:
            a[field] = ""
            if not eligible or a["flag_duplicate_comparison_eligible"]:
                groups[(a["source"], a["brand_raw"], a[title_key])].append(a)
        counters = Counter()
        for (source, brand, key), members in sorted(groups.items()):
            if len(members) < 2 or not key:
                continue
            counters[source] += 1
            for a in members:
                a[field] = f"{source}_{field}_{counters[source]:03d}"
    return audited


def write_report(rows, raw_sha):
    lines = ["# 국내 판매 랭킹 Raw 구성 분석", "",
        "분석 대상: 수집일 2026-09-05의 999개 판매상품. 상품명 기반 후보 탐색이며 정제·삭제·통합·매칭 결과가 아니다.",
        "원본: `korea_perfume_ranking_raw.csv`; 추출: `../../extract_korea_rankings.py`.",
        f"Raw SHA256: `{raw_sha}`. 원본 행 순서와 모든 컬럼 값을 audit CSV에 그대로 보존했다.", "",
        "재실행: MAP에서 `venv/Scripts/python.exe analyze_korea_rankings.py`. 외부 호출·추가 의존성 없음.",
        "행 근거는 아래 `source:rank`와 audit의 `audit_raw_csv_line`, 상품 ID, 원본 HAR 위치로 추적한다.", "",
        "audit의 `flag_*`는 0/1 후보 표시, `flag_evidence_json`은 원문 매칭 근거, `review_context_note`는 상품명 문맥 검토 근거다. `comparison_key_candidate`는 중복 탐색용이며 최종 상품명이 아니다.", "",
        "## 유형별 규모", "",
        "아래 건수는 상품 행 수다. 플래그는 중복될 수 있으므로 합산하지 않는다. 비율의 분모는 각 판매처 전체 행 수다.", ""]

    def table(metrics):
        lines.extend(["| 항목 | musinsa (350) | oliveyoung (350) | lotte (299) | 전체 (999) |",
                      "|---|---:|---:|---:|---:|"])
        for label, predicate in metrics:
            values=[]
            for source in (*SOURCES, None):
                subset=[r for r in rows if source is None or r["source"]==source]
                count=sum(bool(predicate(r)) for r in subset)
                values.append(f"{count} ({count/len(subset):.1%})")
            lines.append("| "+" | ".join([label,*values])+" |")
        lines.append("")

    def flag_metrics(items):
        return [(label,lambda r,f=f:r["flag_"+f]) for f,label in items]

    table(flag_metrics([
        ("main_nonperfume","명백한 비향수 주상품 후보: 방향/세정/보습/시트"),
        ("main_hair_body","헤어/바디 향 제품이 주상품인 후보"),
        ("main_solid_cream_stick","고체·크림·밤·젤·스틱이 주상품인 후보"),
        ("mixed_product_types","향수와 다른 용도/제형 혼합 상품 후보"),
        ("intimate_mention","이너/Y존/속옷 향수 표기"),
        ("nonstandard_main_candidate","위 다섯 범주의 합집합"),
        ("unclear_use","인체용/공간용 불명확 검토 후보"),
        ("oil_rollon_mention","오일퍼퓸·롤온·롤러볼 언급 (증정 포함)"),
        ("refill_mention","리필 언급"),
        ("hair_body_mention","헤어/바디 단어 출현 (증정/브랜드 포함)"),
        ("mist_mention","미스트 단어 출현"),
        ("home_mention","실내/섬유 방향 관련 단어 출현 (이름 포함)"),
        ("care_accessory_mention","세정/보습/공병 관련 단어 출현 (증정 포함)"),
    ]))
    lines.extend(["주상품/혼합/불명확 후보는 코드 `REVIEWED`에 기록한 상품명을 직접 검토한 결과다. 원문 이름으로만 판단했고 실제 성분·용법은 확인하지 않았다.",
        "나머지 행을 모두 일반 향수로 확정할 수는 없다. 특히 이름에 제형·농도가 없는 상품은 미판정이다.", "",
        "## 옵션·기획·샘플", ""])
    table(flag_metrics([
        ("explicit_option","택N/선택/골라 명시"),
        ("count_option_candidate","주상품 문맥 N종 후보 (샘플 증정·discovery 주상품 제외)"),
        ("volume_choice","용량 / 또는 , 선택형 표기"),
        ("multi_option_candidate","multi-option 후보 합집합 (향/용량/구성 구분 전)"),
        ("unresolved_slash","위 합집합 밖 / 표기: 추가 검토 필요"),
        ("planning_set","기획/세트/키트/팩/다개입 표기"),
        ("gift_mention","증정/기프트/선물/포함 표기"),
        ("bundle_or_gift_candidate","기획·묶음·추가구성 후보 합집합"),
        ("sample_mini_mention","discovery/trial/sample/바이알/미니어처 언급"),
        ("discovery_trial_main","discovery/trial 소용량 키트 주상품 후보"),
        ("sample_addon_candidate","그 밖의 sample/미니어처 언급: 추가구성 후보"),
    ]))
    lines.extend(["multi-option 후보는 여러 향을 선택하는 상품 수가 아니다. 같은 향의 용량 선택·단품/기획 선택도 포함한다. `N종`만으로 선택인지 묶음인지 확정하지 않는다.",
        "롯데의 `(바이알 3종)`은 본품 향수에 붙은 추가구성 문맥이다. N종 또는 sample 키워드로 행 전체를 제외하면 본품을 잃는다.", "",
        "## 농도·용량 표기", "",
        "EDP/EDT/Extrait/EDC 및 명시적 Parfum/파팡 표현을 센다. 한국어 `퍼퓸` 단독은 일반 제품 명칭과 구별되지 않아 Parfum 농도로 확정하지 않았다. 여러 농도가 적힌 상품은 각 항목에 중복 계수한다.", ""])
    table(flag_metrics([(f"concentration_{k}",k) for k in CONCENTRATION]+[
        ("concentration_unidentified","명시적 농도 표현 미식별"),
        ("generic_perfume_only","미식별 중 퍼퓸/perfume 표현 있음"),
        ("multiple_concentrations","둘 이상의 명시적 농도 표현"),
    ]))
    identified = sum(not r['flag_concentration_unidentified'] for r in rows)
    lines.extend([f"하나 이상의 명시적 농도 표현을 식별한 상품: {identified}행 ({identified/len(rows):.1%}). 실제 농도 확인 또는 본품에 대한 확정 판정은 아니다.", ""])
    table([
        ("단위가 붙은 용량 하나 이상",lambda r:r["volume_value_count"]>0),
        ("용량 미식별",lambda r:r["volume_value_count"]==0),
        ("용량 수치 둘 이상 (증정·반복 포함)",lambda r:r["flag_multiple_volume_values"]),
        ("서로 다른 용량/단위 둘 이상",lambda r:r["volume_distinct_count"]>1),
        ("g/그램 표기",lambda r:any(v["unit"]=="g" for v in json.loads(r["volume_mentions_json"]))),
        ("oz 표기",lambda r:any(v["unit"]=="oz" for v in json.loads(r["volume_mentions_json"]))),
        ("40m 등 단위 오타 의심",lambda r:r["flag_possible_unit_typo"]),
    ])
    sizes=Counter()
    for r in rows:
        sizes.update({(v["value"],v["unit"]) for v in json.loads(r["volume_mentions_json"])})
    lines.extend(["용량 표기 상위 값 (한 행에서 동일 값은 한 번만 계수; 본품/증정 구분 전):",
                  ", ".join(f"{value}{unit}: {count}행" for (value,unit),count in sorted(sizes.items(), key=lambda item: (-item[1], item[0][1], float(item[0][0]), item[0][0]))[:12]), "",
                  "`30/60ml`은 공통 단위가 명시된 두 수치로 읽고, `40m`은 ml로 고치지 않는다. 용량 합계나 본품 용량은 산출하지 않는다. 10ml라는 이유만으로 sample로 보지 않는다.", "",
                  "## 잠재적 중복 SKU", "",
                  "같은 판매처·동일 brand_raw 안에서만 비교했다. 모든 원본 행을 유지하며 어떤 그룹도 통합하지 않았다.",
                  "1. exact_title_group: 원문 상품명까지 완전히 같은 서로 다른 상품 ID의 그룹.",
                  "2. sku_candidate_group: 용량·명시적 증정/기획 문구·일부 홍보 대괄호를 임시 비교 문자열에서만 제외하고 공백/기호/대소문자 차이를 무시한 그룹. 농도 표현·브랜드명은 치환하지 않는다.",
                  "multi-option/discovery/다중 농도 후보는 2번 비교에서 유보한다. alias·오타·번역 차이는 해결하지 않으므로 포착 범위가 제한되며, 이 수치를 실제 중복 수나 최종 향수 수로 해석할 수 없다.", "",
                  "| 기준/판매처 | 그룹 수 | 참여 행 수 | 그룹 내 첫 행 외 행 수(삭제량 아님) | 서로 다른 용량 표기 그룹 |", "|---|---:|---:|---:|---:|"])
    for field in ("exact_title_group","sku_candidate_group"):
        for source in (*SOURCES,None):
            groups=defaultdict(list)
            for r in rows:
                if r[field] and (source is None or r["source"]==source):groups[r[field]].append(r)
            count=sum(map(len,groups.values()))
            differing=sum(len({tuple(sorted({(v['value'],v['unit']) for v in json.loads(r['volume_mentions_json'])})) for r in members})>1 for members in groups.values())
            lines.append(f"| {field}/{source or '전체'} | {len(groups)} | {count} | {count-len(groups)} | {differing} |")
    lines.extend(["", "비교 키가 같아도 증정 구성·판매 조건은 다를 수 있다. EDP와 EDT 및 `오드퍼퓸`과 `EDP`도 자동으로 같게 만들지 않았고, 판매처 간 동일 향수 수는 미측정이다.", "",
                  "## 실제 사례와 자동 판정 위험", ""])
    by_ref={(r['source'],int(r['source_rank'])):r for r in rows}
    def example(source,rank,note):
        r=by_ref[(source,rank)]
        lines.append(f"- **{source}:{rank}** (`{r['source_product_id']}`, Raw {r['audit_raw_csv_line']}행): {r['product_name_raw']} — {note}")
    for source,rank,note in [
        ('musinsa',17,'룸스프레이·섬유향수라는 용도 표기. 비향수 주상품 후보.'),
        ('musinsa',185,'샤워젤이 주상품. 향수 카테고리 소속만으로 향수라 할 수 없음.'),
        ('oliveyoung',55,'모이스처라이저가 주상품. perfume/향수 문자열 유무만으로 탐지 불가.'),
        ('oliveyoung',283,'향이 있는 샤워시트. 퍼퓸 단어가 있어도 일반 향수는 아님.'),
        ('musinsa',59,'헤어퍼퓸과 남자향수가 함께 표기됨. 서비스 범위 판단 필요.'),
        ('oliveyoung',15,'일반 향수와 헤어퍼퓸 선택이 한 판매상품에 공존.'),
        ('oliveyoung',12,'솔리드와 오 드 퍼퓸 혼합 선택형. 상품 단위 제외/포함 모두 손실 가능.'),
        ('musinsa',46,'솔리드지만 ml 표기. 단위로 제형을 단정하지 않기.'),
        ('musinsa',246,'퍼퓸 젤은 일반 스프레이와 별도 검토.'),
        ('musinsa',329,'퍼퓸 스틱 제형 후보. 용량 표기 없음.'),
        ('musinsa',66,'이너퍼퓸 용도 포함 여부 별도 결정.'),
        ('musinsa',340,'미스트만으로 사용 부위를 확정하지 않기.'),
        ('musinsa',350,'900ml는 세트 표기일 수 있음. 본품 900ml 또는 공간용이라고 단정 불가.'),
        ('oliveyoung',11,'헤어오일은 추가구성. 헤어 단어로 본품 향수를 제외하면 오탐.'),
        ('oliveyoung',121,'헤어퍼퓸은 증정 문구, 주상품은 퍼퓸밤.'),
        ('oliveyoung',97,'로션은 향 묘사. 로션 주상품 판정의 오탐.'),
        ('oliveyoung',215,'더바디샵은 브랜드. 바디 키워드의 오탐.'),
        ('lotte',238,'인센스는 향수 이름 일부. 인센스 단어만으로 공간용 판정하면 오탐.'),
        ('lotte',29,'비엠더블유의 더블은 묶음 구성이 아님.'),
        ('oliveyoung',30,'택1은 같은 향의 용량 선택일 수 있음.'),
        ('musinsa',4,'48종은 선택/묶음 여부와 개별 향 확인 필요.'),
        ('oliveyoung',13,'택1 없이 슬래시로 향 이름 나열: 명시적 선택 키워드만으로는 누락.'),
        ('musinsa',104,'슬래시는 향수/퍼퓸 동의 표현일 수도 있음.'),
        ('musinsa',91,'discovery가 주상품인 예.'),
        ('musinsa',239,'discovery는 증정품. discovery 키워드로 행 전체 제외 금지.'),
        ('lotte',2,'바이알 3종은 추가구성 문맥. 본품과 샘플 키트를 구분해야 함.'),
        ('lotte',31,'100m은 용량 오타 후보이며 ml로 추정하지 않음.'),
        ('musinsa',69,'30mlX2는 용량과 개수의 표기. 용량 합계는 계산하지 않음.'),
        ('musinsa',80,'N종이 본품 향 선택이 아니라 함께 구성된 틴트를 가리킴. 옵션 후보 규칙의 오탐 가능성.'),
        ('oliveyoung',134,'스트로베리필즈의 리필은 이름 일부. 리필 상품으로 집계하지 않음.'),
        ('musinsa',57,'같은 브랜드의 132위 오 드 퍼퓸 50mL와 비교 키가 같지만 향 이름이 없어 같은 향인지 확정 불가.'),
        ('musinsa',14,'10ml이지만 상품명에 trial/sample 표기 없음.'),
        ('musinsa',325,'EDP/EDT 두 표현. 어느 한쪽으로 고정 불가.'),
        ('oliveyoung',40,'EDPI를 EDP로 임의 치환하지 않고 미해석 코드 근거에 보존.'),
        ('lotte',34,'EXDP를 Extrait로 추정하지 않고 미해석 코드 근거에 보존.'),
        ('musinsa',347,'퍼퓸 인텐스는 Parfum 가능성 검토 대상이나 농도 확정 근거로 사용하지 않음.'),
        ('oliveyoung',216,'40m은 오타 후보. 40ml로 자동 보정하지 않음.'),
        ('lotte',193,'대괄호가 브랜드 중간을 가름. 대괄호를 전부 삭제하면 이름 손실.'),
    ]:example(source,rank,note)
    lines.extend(["", "### 중복 후보 그룹의 원문", ""])
    for source in SOURCES:
        groups=defaultdict(list)
        for r in rows:
            if r['source']==source and r['sku_candidate_group']:groups[r['sku_candidate_group']].append(r)
        for gid,members in sorted(groups.items(),key=lambda kv:(-len(kv[1]),kv[0]))[:3]:
            lines.append(f"- `{gid}`: "+" / ".join(f"{r['source']}:{r['source_rank']} `{r['product_name_raw']}`" for r in members))
    lines.extend(["", "### 비향수 주상품 후보 전체 목록", ""])
    for r in rows:
        if r['flag_main_nonperfume']:example(r['source'],int(r['source_rank']),'이름의 주상품 문맥 검토; 삭제하지 않음.')
    lines.extend(["", "## 다음 단계에서 결정할 규칙", "",
        "- 서비스 대상: 일반 인체용 향수에 한정할지, 헤어/바디·고체/젤·오일/롤온·이너퍼퓸을 포함할지. 불명확한 사용 부위는 별도 확인할지.",
        "- 옵션 단위: 향 선택·용량 선택·본품/기획 선택을 구분할 기준과 혼합 상품의 보류 방식. 상품 순위를 모든 옵션 향의 개별 구매 실적으로 복제하지 않기.",
        "- 기획/샘플: 주상품과 증정품을 구분할 방법. 단독 discovery와 본품+discovery를 같은 규칙으로 제거하지 않기.",
        "- 용량/농도: 다중 용량의 본품/증정 구분, 단위 오타·EDPI/EXDP/PFM·퍼퓸 단독의 검토 방식. EDP/EDT 차이 유지.",
        "- 동일 향수 검토: 같은 판매처의 용량·기획 SKU 연결 기준과 농도·별칭·오타 처리. 후보 그룹 수를 확정 중복 수로 쓰지 않기.",
        "- 브랜드: 롯데 brand_raw는 299행 모두 향수존. 이 단계에서 실제 브랜드를 추정하지 않았으며 후속 단계의 브랜드 근거 확보가 필요.",
        "- 비교 범위: 각 플랫폼의 순위 기간과 카테고리 모집단이 다르므로 구성 차이를 한국 전체 수요 차이로 확대하지 않기.", "",
        "## 확인 범위와 한계", "",
        "키워드 후보와 주요 오탐 사례를 상품명으로 검토했다. 모든 상품에 대한 정답 라벨을 만들거나 precision/recall을 측정한 것은 아니다. 따라서 비향수 후보 수는 전체 비향수의 확정 총수가 아니다.",
        "명시적 선택 문구가 없는 향 목록·용도 미표기 상품은 누락 가능하다. 원문에 없는 농도·용량·브랜드는 채우지 않았다. Fragrantica 매칭 가능 수, 정제 후 고유 향수 수와 최종 200종 확보 여부는 미측정이다.",
        "Raw 999행의 순위·상품 ID·모든 provenance 값을 유지했다. 행 삭제, SKU 통합, 옵션 분해, 브랜드 번역, 매칭, 점수 산출은 수행하지 않았다.", ""])
    REPORT.write_text("\n".join(lines),encoding="utf-8")


def main():
    before=RAW.read_bytes()
    digest=hashlib.sha256(before).hexdigest()
    if digest!=RAW_SHA256:raise ValueError("Raw snapshot changed; reviewed examples must be rechecked")
    with RAW.open(encoding="utf-8-sig",newline="") as f:
        reader=csv.DictReader(f); fields=reader.fieldnames; rows=list(reader)
    if Counter(r['source'] for r in rows)!=Counter(SOURCES):raise ValueError("Unexpected source counts")
    for source,limit in SOURCES.items():
        subset=[r for r in rows if r['source']==source]
        if [int(r['source_rank']) for r in subset]!=list(range(1,limit+1)):raise ValueError("Rank mismatch")
        if len({r['source_product_id'] for r in subset})!=limit:raise ValueError("Duplicate product IDs")
    audited=analyze(rows)
    with AUDIT.open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(audited[0]));writer.writeheader();writer.writerows(audited)
    with AUDIT.open(encoding='utf-8-sig',newline='') as f: saved=list(csv.DictReader(f))
    if [{k:r[k] for k in fields} for r in saved]!=rows:raise ValueError("Raw column preservation failed")
    write_report(audited,digest)
    if RAW.read_bytes()!=before:raise ValueError("Raw changed")
    print('Raw and audit rows:',len(rows),len(saved),'all original cells preserved; SHA256 unchanged')
    for source in SOURCES:
        subset=[r for r in audited if r['source']==source]
        print(source,json.dumps({k:sum(r[k] for r in subset) for k in audited[0] if k.startswith('flag_') and k!='flag_evidence_json'},ensure_ascii=False))
    print(AUDIT);print(REPORT)


if __name__=='__main__':main()

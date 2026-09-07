"""Extract Hwahae perfume TOP100 from the frozen local HAR only.

Run: venv/Scripts/python.exe -B extract_hwahae_ranking.py
No network calls, cleaning, matching, normalization, or SKU merging.
"""
import base64
import csv
import hashlib
import json
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qs, urlsplit


MAP_DIR = Path(__file__).resolve().parents[2]  # MAP/
HAR = MAP_DIR / "data/korea_popularity/raw/hwahae_perfume_top100_20260906.har"
OUTPUT = MAP_DIR / "data/korea_popularity/hwahae_perfume_top100_raw.csv"
REPORT = MAP_DIR / "data/korea_popularity/hwahae_perfume_top100_extraction.md"
GITIGNORE = MAP_DIR.parent / ".gitignore"
HAR_SHA256 = "a085a63aa2c928799423b6dc7e78824cd25852bc426ade0ee5c74f8f7d74812d"
RANKING_HOST = "gateway.hwahae.co.kr"
RANKING_PATH = "/v14/rankings/95/details"
PAGE_SIZE = 20
TOTAL = 100
FIELDS = [
    "source", "source_rank", "ranking_basis", "ranking_updated_at",
    "source_product_id", "brand_raw", "product_name_raw", "package_info_raw",
    "price_raw", "commerce_price_raw", "review_count", "review_rating",
    "is_rank_new", "rank_delta", "collected_at", "source_file",
    "har_entry_index",
]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def csv_value(value):
    """Represent JSON scalars in CSV without filling missing values."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def response_text(entry, context):
    require(entry["response"]["status"] == 200, f"Non-200 response: {context}")
    content = entry["response"]["content"]
    text = content.get("text", "")
    require(bool(text), f"Missing response body: {context}")
    encoding = content.get("encoding")
    if encoding == "base64":
        return base64.b64decode(text, validate=True).decode("utf-8-sig")
    require(not encoding, f"Unsupported response encoding: {context}")
    return text


class NextDataParser(HTMLParser):
    """Capture only the server-rendered __NEXT_DATA__ JSON script."""

    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.capturing = False
        self.parts = []
        self.blocks = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "script" and attrs.get("id") == "__NEXT_DATA__":
            require(not self.capturing, "Nested __NEXT_DATA__ script")
            self.capturing = True
            self.parts = []

    def handle_data(self, data):
        if self.capturing:
            self.parts.append(data)

    def handle_endtag(self, tag):
        if tag == "script" and self.capturing:
            self.blocks.append("".join(self.parts))
            self.capturing = False


def find_category_path(node, target_id, path=()):
    current = path + (node,)
    if node.get("id") == target_id:
        return current
    for child in node.get("children", []):
        found = find_category_path(child, target_id, current)
        if found:
            return found
    return None


def validate_page(payload, page, context):
    meta = payload.get("meta", {})
    require(meta.get("code") == 1000, f"API result is not success: {context}")
    pagination = meta.get("pagination", {})
    expected = {"total_count": TOTAL, "page": page, "page_size": PAGE_SIZE, "count": PAGE_SIZE}
    require({key: pagination.get(key) for key in expected} == expected,
            f"Unexpected pagination: {context}: {pagination}")
    data = payload.get("data", {})
    details = data.get("details")
    require(isinstance(details, list) and len(details) == PAGE_SIZE,
            f"Expected {PAGE_SIZE} details: {context}")
    update = data.get("meta", {})
    require(update.get("last_updated_at"), f"Missing ranking update: {context}")
    require(update.get("last_updated_at_description"), f"Missing update description: {context}")
    return details, update


def extract(har):
    log = har.get("log", {})
    entries = log.get("entries", [])
    require(entries, "HAR contains no entries")

    html_matches = []
    api_pages = {}
    for index, entry in enumerate(entries):
        request = entry.get("request", {})
        url = urlsplit(request.get("url", ""))
        query = parse_qs(url.query)
        if (request.get("method") == "GET" and url.hostname == "www.hwahae.co.kr"
                and url.path == "/rankings" and query.get("english_name") == ["category"]
                and query.get("theme_id") == ["95"]):
            html_matches.append((index, entry))
        if (request.get("method") == "GET" and url.hostname == RANKING_HOST
                and url.path == RANKING_PATH):
            require(set(query) >= {"page", "page_size"}, f"Missing API pagination: entry {index}")
            page = int(query["page"][0])
            size = int(query["page_size"][0])
            require(size == PAGE_SIZE and 2 <= page <= 5,
                    f"Unexpected ranking API page: entry {index}, page={page}, size={size}")
            require(page not in api_pages, f"Duplicate captured API page {page}")
            text = response_text(entry, f"entry {index} page {page}")
            require(entry["response"]["content"].get("mimeType", "").startswith("application/json"),
                    f"Unexpected API mime type: entry {index}")
            api_pages[page] = (index, json.loads(text))

    require(len(html_matches) == 1, f"Expected one matching initial HTML, got {len(html_matches)}")
    html_index, html_entry = html_matches[0]
    require(html_entry["response"]["content"].get("mimeType", "").startswith("text/html"),
            "Initial ranking response is not HTML")
    parser = NextDataParser()
    parser.feed(response_text(html_entry, f"entry {html_index} initial HTML"))
    parser.close()
    require(not parser.capturing and len(parser.blocks) == 1,
            f"Expected one complete __NEXT_DATA__, got {len(parser.blocks)}")
    next_data = json.loads(parser.blocks[0])
    page_props = next_data["props"]["pageProps"]

    ranking_meta = page_props["rankingsCategories"]
    require(ranking_meta.get("ranking_type") == "CATEGORY", "Ranking is not category-based")
    require(ranking_meta.get("max_rank") == TOTAL, "Ranking max_rank is not 100")
    category_path = find_category_path(ranking_meta, 95)
    require(category_path and [node.get("name") for node in category_path[-2:]] == ["향수", "전체"],
            "theme_id=95 is not 향수 > 전체")
    ranking_basis = ranking_meta.get("name")
    require(ranking_basis, "Missing ranking basis")

    initial_payload = page_props["rankingProducts"]
    pages = {1: (html_index, initial_payload)}
    require(set(api_pages) == {2, 3, 4, 5}, f"Missing API pages: {set(range(2, 6)) - set(api_pages)}")
    pages.update(api_pages)

    rows = []
    update_values = set()
    update_descriptions = set()
    page_entries = []
    for page in range(1, 6):
        entry_index, payload = pages[page]
        details, update = validate_page(payload, page, f"entry {entry_index} page {page}")
        update_values.add(update["last_updated_at"])
        update_descriptions.add(update["last_updated_at_description"])
        page_entries.append((page, entry_index))
        for position, detail in enumerate(details, 1):
            product = detail.get("product")
            brand = detail.get("brand")
            require(isinstance(product, dict) and isinstance(brand, dict),
                    f"Missing product/brand object: page {page} position {position}")
            goods = detail.get("goods")
            require(goods is None or isinstance(goods, dict),
                    f"Unexpected goods object: page {page} position {position}")
            raw = {
                "source": "hwahae",
                "source_rank": (page - 1) * PAGE_SIZE + position,
                "ranking_basis": ranking_basis,
                "ranking_updated_at": update["last_updated_at"],
                "source_product_id": product.get("id"),
                "brand_raw": brand.get("name"),
                "product_name_raw": product.get("name"),
                "package_info_raw": product.get("package_info"),
                # Preserve both HAR price fields instead of selecting one.
                "price_raw": product.get("price"),
                "commerce_price_raw": goods.get("price") if goods else None,
                "review_count": product.get("review_count"),
                "review_rating": product.get("review_rating"),
                "is_rank_new": detail.get("is_rank_new"),
                "rank_delta": detail.get("rank_delta"),
                "collected_at": "",  # Assigned from the HAR page timestamp below.
                "source_file": HAR.relative_to(MAP_DIR).as_posix(),
                "har_entry_index": entry_index,
            }
            rows.append({field: csv_value(raw.get(field)) for field in FIELDS})

    require(len(update_values) == 1 and len(update_descriptions) == 1,
            "Ranking update metadata differs across captured pages")
    har_pages = log.get("pages", [])
    require(len(har_pages) == 1 and har_pages[0].get("startedDateTime"),
            "Missing HAR page capture timestamp")
    capture_timestamp = har_pages[0]["startedDateTime"]
    require(len(capture_timestamp) >= 10, "Invalid HAR page capture timestamp")
    for row in rows:
        row["collected_at"] = capture_timestamp[:10]
    return rows, {
        "page_entries": page_entries,
        "category_path": " > ".join(node["name"] for node in category_path),
        "update_description": next(iter(update_descriptions)),
        "capture_timestamp": capture_timestamp,
    }


def validate(rows):
    require(len(rows) == TOTAL, f"Expected {TOTAL} rows, got {len(rows)}")
    require([int(row["source_rank"]) for row in rows] == list(range(1, TOTAL + 1)),
            "Ranks are not exactly 1..100 in order")
    require(all(row["source"] == "hwahae" for row in rows), "Unexpected source")
    ids = [row["source_product_id"] for row in rows]
    require(all(ids), "Missing source_product_id")
    require(len(set(ids)) == TOTAL, "source_product_id is not unique")
    require(len({row["ranking_basis"] for row in rows}) == 1, "Ranking basis differs by row")
    require(len({row["ranking_updated_at"] for row in rows}) == 1,
            "Ranking update differs by row")
    require(len({row["collected_at"] for row in rows}) == 1, "Collection date differs by row")


def missing_counts(rows):
    return {field: sum(row[field] == "" for row in rows) for field in FIELDS}


def write_report(rows, structure, digest):
    missing = missing_counts(rows)
    duplicate_ids = Counter(row["source_product_id"] for row in rows)
    duplicate_values = sum(count > 1 for count in duplicate_ids.values())
    duplicate_extra_rows = sum(count - 1 for count in duplicate_ids.values() if count > 1)
    entry_text = ", ".join(f"page {page}=entry {index}" for page, index in structure["page_entries"])
    lines = [
        "# 화해 향수 TOP100 Raw 추출", "",
        "입력 HAR 응답만 사용했다. 외부 요청, 상품 정제, 기존 판매 데이터 매칭, SKU 통합은 수행하지 않았다.", "",
        "## 확인한 구조", "",
        f"- 최초 HTML entry {structure['page_entries'][0][1]}의 `__NEXT_DATA__`에 page 1 상품 20개가 있다.",
        "- `/v14/rankings/95/details` JSON 응답 page 2~5에 각각 20개가 있다.",
        f"- 페이지 provenance: {entry_text}.",
        f"- 랭킹 경로: `{structure['category_path']}`. CSV `ranking_basis`는 HAR 원문 `{rows[0]['ranking_basis']}`이다.",
        f"- 랭킹 업데이트: `{rows[0]['ranking_updated_at']}` (`{structure['update_description']}`). 모든 페이지에서 동일하다.",
        f"- HAR 페이지 수집 시각: `{structure['capture_timestamp']}`. `collected_at`에는 HAR에 있는 날짜 `{rows[0]['collected_at']}`를 기록했다.",
        "- 상품별 rank 필드는 없으므로 검증된 page/page_size와 응답 배열 순서로 1~100위를 복원했다.", "",
        "## 검증 결과", "",
        f"- 행 수: {len(rows)}",
        f"- 순위: 1~100 연속, 누락 0, 중복 0",
        f"- 고유 source_product_id: {len(duplicate_ids)}",
        f"- 중복 product_id 값: {duplicate_values}; 첫 행 이후 중복 행: {duplicate_extra_rows}",
        f"- is_rank_new: true {sum(row['is_rank_new'] == 'true' for row in rows)}, false {sum(row['is_rank_new'] == 'false' for row in rows)}",
        "",
        "| 필드 | 결측 수 |", "|---|---:|",
    ]
    for field in FIELDS:
        lines.append(f"| {field} | {missing[field]} |")
    lines.extend([
        "", "## Raw 필드 주의사항", "",
        "- `price_raw`는 `product.price`, `commerce_price_raw`는 `goods.price`를 그대로 저장했다. 두 값 중 하나를 임의로 선택하지 않았다.",
        f"- `price_raw` 결측 {missing['price_raw']}건, `commerce_price_raw` 결측 {missing['commerce_price_raw']}건이다. 값 0은 결측으로 바꾸지 않았다.",
        f"- `package_info_raw` 결측 {missing['package_info_raw']}건이다. 브랜드·상품명·review_count·review_rating은 결측이 없다.",
        "- boolean은 CSV에서 `true`/`false`로 직렬화했다. 상품명·브랜드·용량·가격 값은 정규화하거나 보정하지 않았다.",
        "- 요청 헤더, 쿠키, 사용자 식별값, 상품 이미지와 리뷰 주제는 내보내지 않았다.", "",
        "## 재현", "",
        "- 실행: `venv/Scripts/python.exe -B extract_hwahae_ranking.py`.",
        "- 스크립트는 HTML/API 페이지 구조, 총 100개, page 1~5, 순위 연속성, ID 고유성, 메타데이터 일치와 CSV round-trip을 검사한다.",
        f"- 입력 HAR SHA256: `{digest}`. 처리 전후 바이트가 동일함을 검사한다.",
        "- 저장소 `.gitignore`에는 이미 `*.har`와 `*.har.gz`가 있어 수정하지 않았다. `git check-ignore`로 이 HAR가 제외됨을 확인했다.", "",
        "## 다음 단계 전 확인", "",
        "- 가격 필드 둘의 의미와 후속 단계에서 사용할 가격을 결정해야 한다.",
        "- package_info/price 결측은 상세 상품 데이터가 필요할 때만 별도로 확인한다.",
        "- 이 CSV는 화해 향수 카테고리의 Raw 랭킹이다. 향수 범위 정제와 기존 구매 랭킹 매칭은 미수행이다.",
    ])
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    before = HAR.read_bytes()
    digest = hashlib.sha256(before).hexdigest()
    require(digest == HAR_SHA256, "HAR snapshot changed; inspect structure before extracting")
    require("*.har" in {line.strip() for line in GITIGNORE.read_text(encoding="utf-8").splitlines()},
            "Repository .gitignore does not exclude HAR files")
    rows, structure = extract(json.loads(before.decode("utf-8-sig")))
    validate(rows)
    with OUTPUT.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    with OUTPUT.open(encoding="utf-8-sig", newline="") as stream:
        saved = list(csv.DictReader(stream))
    require(saved == rows, "CSV round-trip changed Raw values")
    require(HAR.read_bytes() == before, "Input HAR changed during extraction")
    write_report(rows, structure, digest)
    missing = missing_counts(rows)
    print(f"VALID hwahae: rows={len(rows)}, ranks=1..100, unique_ids={len(set(r['source_product_id'] for r in rows))}")
    print("missing=" + json.dumps(missing, ensure_ascii=False))
    print(f"ranking_updated_at={rows[0]['ranking_updated_at']}")
    print(f"WROTE {OUTPUT}")
    print(f"WROTE {REPORT}")


if __name__ == "__main__":
    main()

"""Extract the agreed 2026-09-05 ranking snapshot from local HAR responses only.

Run: venv/Scripts/python.exe extract_korea_rankings.py
No network calls, product filtering, name normalization, or SKU deduplication.
Files are identified by request host/path/parameters, never by their names.
Only the explicitly requested rank ranges are exported; extra captured ranks
are counted in the console output. Invalid/missing pages fail before writing.

Field provenance:
  musinsa: data.list; goodsNo, brandName, goodsName, goodsLinkUrl, price.
           Rank = (request page - 1) * size + response list position.
  oliveyoung: HTML li[criteo-goods]; data-number is the global rank.
              Product ID/href from a.prd_thumb; text from .tx_brand,
              .tx_name, .tx_cur (including currency and range markers).
  lotte: itemList; pdId, brandName, pdName, pdLink, priceInfo.finalPrice.
         Rank = request u2 offset + page-local pdRank. Relative pdLink is
         resolved against the captured request URL. brandName='향수존' is
         retained as supplied, without inferring the perfume manufacturer.
  source_file: path relative to MAP; har_entry_index: zero-based log.entries
               index, allowing each CSV row to be traced to its response.

Ranking labels/periods and collection date are the user-confirmed metadata;
the script verifies sort/category parameters, not undisclosed retailer logic.
Reads one HAR at a time with the standard library; does not decode images or
save intermediate datasets. CSV uses UTF-8 with BOM for Korean Excel users.
"""

import base64
import csv
import json
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlsplit


MAP_DIR = Path(__file__).resolve().parents[2]  # MAP/
RAW_DIR = MAP_DIR / "data/korea_popularity/raw"
OUTPUT = MAP_DIR / "data/korea_popularity/korea_perfume_ranking_raw.csv"
COLLECTED_AT = "2026-09-05"
LIMITS = {"musinsa": 350, "oliveyoung": 350, "lotte": 299}
METADATA = {
    "musinsa": ("판매수량순", "3개월"),
    "oliveyoung": ("판매순", "기간 미확인"),
    "lotte": ("판매 많은순", "최근 30일"),
}
FIELDS = [
    "source", "source_rank", "ranking_basis", "ranking_period",
    "source_product_id", "brand_raw", "product_name_raw", "product_url",
    "price_raw", "collected_at", "source_file", "har_entry_index",
]


def require(condition, message):
    if not condition:
        raise ValueError(message)


class OliveYoungCards(HTMLParser):
    """Read only the captured category product cards, not navigation links."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.cards = []
        self.card = None
        self.capture = None
        self.capture_depth = 0
        self.parts = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = attrs.get("class", "").split()
        if tag == "li" and "criteo-goods" in attrs:
            require(self.card is None, "Nested Olive Young product cards")
            self.card = {"source_rank": int(attrs["data-number"])}
        if self.card is None:
            return
        if tag == "a" and "prd_thumb" in classes:
            self.card["source_product_id"] = attrs.get("data-ref-goodsno", "")
            self.card["product_url"] = attrs.get("href", "")
        if self.capture:
            if tag == self.capture[0]:
                self.capture_depth += 1
            return
        for css, field in (("tx_brand", "brand_raw"),
                           ("tx_name", "product_name_raw"),
                           ("tx_cur", "price_raw")):
            if css in classes:
                require(field not in self.card, f"Repeated card field: {field}")
                self.capture = (tag, field)
                self.capture_depth = 1
                self.parts = []
                break

    def handle_data(self, data):
        if self.capture:
            self.parts.append(data)

    def handle_endtag(self, tag):
        if self.capture and tag == self.capture[0]:
            self.capture_depth -= 1
            if self.capture_depth == 0:
                self.card[self.capture[1]] = "".join(self.parts).strip()
                self.capture = None
        if tag == "li" and self.card is not None:
            require(self.capture is None, "Unclosed product text element")
            self.cards.append(self.card)
            self.card = None


def extract_file(path):
    # The large image bodies stay encoded and are released with this HAR.
    with path.open(encoding="utf-8-sig") as stream:
        entries = json.load(stream)["log"]["entries"]
    rows = []
    for index, entry in enumerate(entries):
        request = entry["request"]
        url = urlsplit(request["url"])
        query = parse_qs(url.query)
        endpoint = (url.hostname, url.path)
        if endpoint == ("api.musinsa.com", "/api2/dp/v2/plp/goods"):
            source = "musinsa"
            expected = {"gf": "A", "sortCode": "SALE_THREE_MONTH_COUNT",
                        "category": "104005001", "caller": "CATEGORY"}
        elif endpoint == ("www.oliveyoung.co.kr", "/store/display/getMCategoryList.do"):
            source = "oliveyoung"
            expected = {"dispCatNo": "100000100050013", "prdSort": "03"}
        elif endpoint == ("www.lotteon.com", "/csearch/render/render.ecn"):
            source = "lotte"
            expected = {"u5": "p31105", "u16": "sale.desc", "u28": "brandStore"}
        else:
            continue
        context = f"{path.name} entry {index} ({source})"
        if any(query.get(key) != [value] for key, value in expected.items()):
            print(f"SKIP other category/sort: {context}")
            continue
        require(request["method"] == "GET", f"Unexpected method: {context}")
        require(entry["response"]["status"] == 200, f"Failed response: {context}")
        content = entry["response"]["content"]
        text = content.get("text", "")
        require(bool(text), f"Missing response body: {context}")
        if content.get("encoding") == "base64":
            text = base64.b64decode(text, validate=True).decode("utf-8-sig")
        else:
            require(not content.get("encoding"), f"Unsupported encoding: {context}")

        if source == "musinsa":
            payload = json.loads(text)
            data = payload["data"]
            page, size = int(query["page"][0]), int(query["size"][0])
            offset = (page - 1) * size
            require(page >= 1 and size == 60, f"Unexpected pagination: {context}")
            require(int(query["seen"][0]) == offset, f"Inconsistent seen: {context}")
            require(payload["meta"]["result"] == "SUCCESS", f"API error: {context}")
            require(data["pagination"]["page"] == page and
                    data["pagination"]["size"] == size, f"Page mismatch: {context}")
            require(len(data["list"]) == size, f"Incomplete page: {context}")
            cards = []
            for position, item in enumerate(data["list"], 1):
                # Captured pages contain no ads; do not silently remove any.
                require(item["isAd"] is False, f"Ad in sales ranking: {context}")
                cards.append({
                    "source_rank": offset + position,
                    "source_product_id": item.get("goodsNo"),
                    "brand_raw": item.get("brandName"),
                    "product_name_raw": item.get("goodsName"),
                    "product_url": item.get("goodsLinkUrl"),
                    "price_raw": item.get("price"),
                })
        elif source == "oliveyoung":
            page, size = int(query["pageIdx"][0]), int(query["rowsPerPage"][0])
            require(page >= 1 and size == 48, f"Unexpected pagination: {context}")
            offset = (page - 1) * size
            parser = OliveYoungCards()
            parser.feed(text)
            parser.close()
            require(parser.card is None, f"Truncated HTML card: {context}")
            cards = parser.cards
            require(len(cards) == size, f"Incomplete page: {context}")
            require([c["source_rank"] for c in cards] ==
                    list(range(offset + 1, offset + size + 1)),
                    f"HTML ranks disagree with pagination: {context}")
        else:
            payload = json.loads(text)
            offset, size = int(query["u2"][0]), int(query["u3"][0])
            require(size == 60 and offset >= 0 and offset % size == 0,
                    f"Unexpected pagination: {context}")
            require(payload["total"] == LIMITS[source], f"LOTTE total changed: {context}")
            items = payload["itemList"]
            require(len(items) == max(0, min(size, payload["total"] - offset)),
                    f"Incomplete page: {context}")
            cards = []
            for position, item in enumerate(items, 1):
                require(int(item["pdRank"]) == position, f"Local rank mismatch: {context}")
                link = item.get("pdLink")
                cards.append({
                    "source_rank": offset + int(item["pdRank"]),
                    "source_product_id": item.get("pdId"),
                    "brand_raw": item.get("brandName"),
                    "product_name_raw": item.get("pdName"),
                    "product_url": urljoin(request["url"], link) if link else "",
                    "price_raw": item.get("priceInfo", {}).get("finalPrice"),
                })
        print(f"PAGE {source}: offset={offset}, count={len(cards)}, entry={index}")
        basis, period = METADATA[source]
        for card in cards:
            card.update(source=source, ranking_basis=basis, ranking_period=period,
                        collected_at=COLLECTED_AT,
                        source_file=path.relative_to(MAP_DIR).as_posix(),
                        har_entry_index=index)
            rows.append({field: "" if card.get(field) is None else str(card[field])
                         for field in FIELDS})
    require(bool(rows), f"No agreed ranking responses found in {path.name}")
    return rows


def validate(rows):
    require(len(rows) == sum(LIMITS.values()), f"Expected 999 rows, got {len(rows)}")
    for source, limit in LIMITS.items():
        subset = [row for row in rows if row["source"] == source]
        ranks = [int(row["source_rank"]) for row in subset]
        require(ranks == list(range(1, limit + 1)), f"Missing/duplicate ranks: {source}")
        missing = {field: sum(not row[field].strip() for row in subset) for field in FIELDS}
        for field in ("source", "source_rank", "source_product_id", "product_name_raw"):
            require(missing[field] == 0, f"Missing {source}.{field}: {missing[field]}")
        ids = Counter(row["source_product_id"] for row in subset)
        duplicates = {key: count for key, count in ids.items() if count > 1}
        print(f"VALID {source}: rows={len(subset)}, ranks=1..{limit}, "
              f"duplicate_product_ids={duplicates}, missing={json.dumps(missing)}")


def main():
    paths = sorted(RAW_DIR.glob("*.har"))
    require(bool(paths), f"No HAR files in {RAW_DIR}")
    captured = []
    for path in paths:
        captured.extend(extract_file(path))

    rows = []
    for source, limit in LIMITS.items():
        subset = sorted((r for r in captured if r["source"] == source),
                        key=lambda r: int(r["source_rank"]))
        ranks = [int(r["source_rank"]) for r in subset]
        require(ranks == list(range(1, len(ranks) + 1)),
                f"Captured ranks contain gaps/repeated pages: {source}")
        selected = [r for r in subset if 1 <= int(r["source_rank"]) <= limit]
        print(f"RANGE {source}: captured={len(subset)}, selected={len(selected)}, "
              f"outside_requested_range={len(subset) - len(selected)}")
        rows.extend(selected)
    validate(rows)
    with OUTPUT.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    # Verify serialization, including Korean text and quoted commas/newlines.
    with OUTPUT.open(encoding="utf-8-sig", newline="") as stream:
        require(list(csv.DictReader(stream)) == rows, "CSV round-trip mismatch")
    print(f"WROTE {OUTPUT} ({len(rows)} rows; CSV round-trip verified)")


if __name__ == "__main__":
    main()

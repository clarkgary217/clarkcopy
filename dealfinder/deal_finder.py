"""Flag listings priced below what the exact card (by PSA cert) has recently sold for.

Each watchlist entry is a reference cert for the card+grade to track. One bulk
cert lookup on Card Ladder (1 Parse credit for the whole watchlist) gives the
exact card, its CL value and its 10 most recent sales. Listings come from Card
Ladder's current_listings when it has a card page for that grade, otherwise from
an eBay search built from the card details (1 credit per card). Sold prices
always come from Card Ladder; eBay is only used for active listings.

Responses are cached in .cache/ for CACHE_HOURS so re-runs don't spend credits.

Usage: uv run python deal_finder.py [--refresh]
"""

import hashlib
import json
import re
import statistics
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ebay_search import search_listings
from search_cards import CardLadder

# Reference certs for the cards to watch. title_exclude: extra words that mark a
# different version of the card on eBay (parallels etc.), since titles are free text.
WATCHLIST = [
    {"cert": "87873855", "grader": "PSA", "title_exclude": ["row 0", "row 1", "row 2"]},  # 2003 Flair LeBron #94 PSA 9
]

DEAL_THRESHOLD = 0.20      # flag listings at least 20% below the baseline
RECENT_DAYS = 180          # baseline = median sale price within this many days, else CL value
TITLE_EXCLUDE = ["reprint", " rp ", " lot ", "custom", "proxy", "facsimile", "digital", "you pick", "choose"]

CACHE_DIR = Path(__file__).parent / ".cache"
CACHE_HOURS = 12
REFRESH = "--refresh" in sys.argv


def cached(kind: str, args, fetch, keep=lambda data: True):
    """Return a cached response for (kind, args) if fresh, else fetch and cache it (when keep(data))."""
    key = hashlib.sha1(json.dumps([kind, args], sort_keys=True).encode()).hexdigest()[:16]
    path = CACHE_DIR / f"{kind}-{key}.json"
    if not REFRESH and path.exists() and time.time() - path.stat().st_mtime < CACHE_HOURS * 3600:
        return json.loads(path.read_text())
    data = fetch()
    if keep(data):
        CACHE_DIR.mkdir(exist_ok=True)
        path.write_text(json.dumps(data))
    return data


def parse_price(value):
    """1234.5 or '$1,234.56' -> float. Ranges ('$10.00 to $20.00') and junk -> None."""
    if isinstance(value, (int, float)):
        return float(value)
    if not value or "to" in value:
        return None
    m = re.fullmatch(r"\$?([\d,]+(?:\.\d+)?)", value.strip())
    return float(m.group(1).replace(",", "")) if m else None


def grade_of(card: dict) -> str:
    """Card Ladder writes the grade as 'PSA 9' on card pages and 'g9' in its sales archive."""
    m = re.search(r"(\d+(?:\.\d+)?)", card["condition"] or "")
    return m.group(1) if m else ""


def title_matches(title: str, card: dict, grader: str, extra_exclude: list) -> bool:
    t = f" {title.lower()} "
    if any(x in t for x in TITLE_EXCLUDE + extra_exclude):
        return False
    # Same player, year and set: "#94 LeBron PSA 9" alone also matches other sets' #94.
    for word in (card["player"].split()[-1], card["year"], card["set"]):
        if word and word.lower() not in t:
            return False
    if card["number"] and not re.search(rf"(?<![\d.]){re.escape(card['number'])}(?![\d.])", t):
        return False
    # Exact grade: "PSA 9" must not match "PSA 9.5" or "PSA 10".
    return re.search(rf"\b{grader.lower()}\s*{re.escape(grade_of(card))}(?![\d.])", t) is not None


def baseline(card: dict):
    cutoff = datetime.now(timezone.utc) - timedelta(days=RECENT_DAYS)
    recent = [s["price"] for s in card["recent_sales"]
              if s["price"] and datetime.fromisoformat(s["date"].replace("Z", "+00:00")) >= cutoff]
    if recent:
        return statistics.median(recent), f"median of {len(recent)} sales in the last {RECENT_DAYS} days"
    return card["cl_value"], "Card Ladder value (no recent sales)"


def listings_for(card: dict, entry: dict):
    """Card Ladder's own listings for the exact card+grade, else eBay matched by title."""
    if card["current_listings"]:
        return [{"title": l["title"], "price": l["price"], "url": l["url"],
                 "type": f"{l['platform']} {l['listing_type']}".strip(), "bids": l.get("bids")}
                for l in card["current_listings"]], "Card Ladder"
    grader = entry["grader"]
    query = f"{card['year']} {card['set']} {card['player']} {card['number']} {grader} {grade_of(card)}"
    found = cached("ebay", {"q": query}, lambda: search_listings(query, graded=True))["data"]["listings"]
    matched = [{"title": l["title"], "price": l["price"], "url": l["url"], "type": "eBay"}
               for l in found if title_matches(l["title"], card, grader, entry.get("title_exclude", []))]
    return matched, f"eBay ('{query}': {len(found)} results, {len(matched)} exact matches)"


def check_card(card: dict, entry: dict):
    grade = f"{entry['grader']} {grade_of(card)}"
    print(f"\n=== {card['year']} {card['set']} {card['player']} #{card['number']} {grade} (cert {entry['cert']}) ===")
    base, how = baseline(card)
    print(f"  Baseline: ${base:,.2f} ({how}); CL value ${card['cl_value']:,.0f}")
    for s in card["recent_sales"][:5]:
        print(f"    sold {s['date'][:10]}  ${s['price']:,.2f}  {s['type']}")

    listings, source = listings_for(card, entry)
    print(f"  Listings from {source}")
    deals = []
    for item in listings:
        price = parse_price(item["price"])
        if price is None:
            continue
        discount = 1 - price / base
        flag = "DEAL" if discount >= DEAL_THRESHOLD else "    "
        vs = f"{discount:.0%} under" if discount >= 0 else f"{-discount:.0%} above"
        print(f"    {flag} {vs:>10}  ${price:,.2f}  {item['type']}  {item['title'][:60]}")
        if discount >= DEAL_THRESHOLD:
            deals.append({**item, "price_num": price, "discount": discount})
    for d in deals:
        print(f"  -> {d['discount']:.0%} under: {d['url']}")
    return deals


def main():
    certs = [{"cert_number": e["cert"], "grading_company": e["grader"]} for e in WATCHLIST]
    with CardLadder(timeout=120) as cl:
        result = cached("certs", certs, lambda: cl.search_by_certs_bulk(certs),
                        keep=lambda data: not data.get("unprocessed"))  # don't cache a partial batch
    for err in result.get("errors", []):
        print(f"cert {err['cert_number']}: {err['message']}")

    by_cert = {c["cert_number"]: c for c in result["results"]}
    all_deals = []
    for entry in WATCHLIST:
        card = by_cert.get(entry["cert"])
        if not card:
            continue
        try:
            all_deals += check_card(card, entry)
        except Exception as e:  # one card failing shouldn't stop the rest
            print(f"  Skipped: {type(e).__name__}: {str(e)[:200]}")
    print(f"\n{len(all_deals)} deal(s) found across {len(WATCHLIST)} cards "
          f"(threshold: {DEAL_THRESHOLD:.0%} under baseline).")


if __name__ == "__main__":
    main()

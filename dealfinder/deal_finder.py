"""Flag eBay listings priced below what the card has recently sold for.

DRAFT: title-matching version, to be replaced by a PSA cert-based lookup
(Card Ladder search_by_cert / search_by_certs_bulk) for exact card+grade matches.

For each watchlist card: find it on Card Ladder (search_cards), pull its sold
history (get_card_sales), search eBay for active listings, and compare.
That's 3 Parse calls per card. Responses are cached in .cache/ for
CACHE_HOURS so re-runs while testing don't spend Parse credits.

Usage: uv run python deal_finder.py [--refresh]
"""

import hashlib
import json
import re
import statistics
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

from ebay_search import search_listings
from search_cards import CardLadder

# Keep this short while on the free Parse plan: each card costs 3 calls per uncached run.
WATCHLIST = [
    {
        "name": "1986 Fleer Michael Jordan #57 PSA 8",
        "cardladder_query": "1986 Fleer Michael Jordan 57",
        "condition": "PSA 8",
        "variation": "Base",
        "ebay_query": "1986 Fleer Michael Jordan 57 PSA 8",
        "title_must": ["jordan", "57"],
        "title_exclude": ["sticker"],
    },
    {
        "name": "2018 Prizm Luka Doncic #280 PSA 10",
        "cardladder_query": "2018 Prizm Luka Doncic 280",
        "condition": "PSA 10",
        "variation": "Base",
        "ebay_query": "2018 Prizm Luka Doncic 280 PSA 10",
        "title_must": ["doncic", "280"],
        # Base only: the parallels sell for 3-15x base and would skew matches.
        "title_exclude": ["silver", "purple", "red", "blue", "pink", "ice", "wave", "choice", "fast break",
                          "mojo", "hyper", "green", "orange", "gold", "/"],
    },
]

DEAL_THRESHOLD = 0.20      # flag listings at least 20% below the baseline
RECENT_SALES = 5           # baseline = median of this many most recent sales...
RECENT_DAYS = 180          # ...within this many days; else fall back to Card Ladder's current value
TITLE_EXCLUDE = ["reprint", " rp ", "lot", "custom", "proxy", "facsimile", "digital"]

CACHE_DIR = Path(__file__).parent / ".cache"
CACHE_HOURS = 12
REFRESH = "--refresh" in sys.argv


def cached(kind: str, args: dict, fetch, keep=lambda data: True):
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


def parse_price(text):
    """'$1,234.56' -> 1234.56. Ranges ('$10.00 to $20.00') and junk -> None."""
    if not text or "to" in text:
        return None
    m = re.fullmatch(r"\$([\d,]+(?:\.\d+)?)", text.strip())
    return float(m.group(1).replace(",", "")) if m else None


def title_matches(title: str, card: dict) -> bool:
    t = f" {title.lower()} "
    if any(x in t for x in TITLE_EXCLUDE + card.get("title_exclude", [])):
        return False
    if not all(w in t for w in card["title_must"]):
        return False
    # Exact grade: "PSA 8" must not match "PSA 8.5" or "PSA 10".
    company, grade = card["condition"].split()
    return re.search(rf"\b{company.lower()}\s*{re.escape(grade)}(?![\d.])", t) is not None


def baseline(sales: list, fallback: float):
    cutoff = datetime.now() - timedelta(days=RECENT_DAYS)
    recent = [s for s in sales if datetime.strptime(s["date"], "%m/%d/%Y") >= cutoff][:RECENT_SALES]
    if recent:
        return statistics.median(s["price"] for s in recent), f"median of {len(recent)} sales since {cutoff:%m/%d/%Y}"
    return fallback, "Card Ladder current value (no recent sales)"


def check_card(cl: CardLadder, card: dict):
    print(f"\n=== {card['name']} ===")
    search = cached("cl_search", {"q": card["cardladder_query"], "c": card["condition"], "v": card["variation"]},
                    lambda: cl.search_cards(card["cardladder_query"], limit=1,
                                            condition=card["condition"], variation=card["variation"]),
                    keep=lambda data: bool(data["cards"]))  # don't cache a miss; the query may get fixed
    if not search["cards"]:
        print("  Not found on Card Ladder; check the query/condition.")
        return []
    cl_card = search["cards"][0]
    print(f"  Card Ladder: {cl_card['label']} (current value ${cl_card['current_value']:,.0f})")

    sales = cached("cl_sales", {"id": cl_card["id"]}, lambda: cl.get_card_sales(cl_card["id"]))["sales"]
    base, how = baseline(sales, cl_card["current_value"])
    print(f"  Baseline: ${base:,.2f} ({how})")

    listings = cached("ebay", {"q": card["ebay_query"]},
                      lambda: search_listings(card["ebay_query"], graded=True))["data"]["listings"]
    deals, checked = [], 0
    for item in listings:
        price = parse_price(item["price"])
        if price is None or not title_matches(item["title"], card):
            continue
        checked += 1
        discount = 1 - price / base
        if discount >= DEAL_THRESHOLD:
            deals.append({**item, "price_num": price, "discount": discount, "card": card["name"]})
    print(f"  eBay: {len(listings)} listings, {checked} match this exact card/grade, {len(deals)} deals")
    for d in sorted(deals, key=lambda d: -d["discount"]):
        print(f"    {d['discount']:.0%} under  ${d['price_num']:,.2f}  {d['title'][:70]}\n      {d['url']}")
    return deals


def main():
    all_deals = []
    with CardLadder(timeout=150) as cl:
        for card in WATCHLIST:
            try:
                all_deals += check_card(cl, card)
            except Exception as e:  # one card failing shouldn't stop the rest
                print(f"  Skipped: {type(e).__name__}: {str(e)[:200]}")
    print(f"\n{len(all_deals)} deal(s) found across {len(WATCHLIST)} cards.")


if __name__ == "__main__":
    main()

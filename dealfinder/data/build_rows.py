"""One-off: assemble the 2026-10-13 LeBron poll (eBay search + item details + Card Ladder) into dashboard rows."""
import json, re, os, sys
from datetime import datetime, timedelta, timezone

D = os.path.dirname(os.path.abspath(__file__))
search = {l["item_id"]: l for l in json.load(open(f"{D}/ebay_search_raw.json"))["data"]["listings"]}

# item_id -> (Card Ladder result index to use or None, grade, card year, set, notes)
PICKS = {
    "407271045222": (None, "PSA 10", "2025", "Topps Chrome Purple Refractor /75", "Not found on Card Ladder"),
    "178561803986": (0, "PSA 10", "2003", "Ultra Roundball Discs", ""),
    "257780158171": (2, "PSA 9", "2003", "Topps (Base)", ""),
    "287631918422": (None, "PSA 9", "2002", "Topps Finest", "Not found on Card Ladder; item details unavailable"),
    "307221798294": (0, "PSA 10", "2003", "Topps (Base)", "Assumed Base: title doesn't name a variant"),
    "366706075832": (None, "PSA 9", "2004", "Upper Deck Black Diamond Red /100", "Not found on Card Ladder"),
}

def parse_detail_price(text):
    """'US $1,475.0027 bidsEnds in3h 21m' -> (1475.0, 27, 'or Best Offer' in text, minutes left)."""
    m = re.match(r"US \$([\d,]+\.\d{2})(or Best Offer)?(\d+) bidsEnds in(?:(\d+)d ?)?(?:(\d+)h ?)?(?:(\d+)m)?", text or "")
    if not m:
        return None
    price, bo, bids, d, h, mins = m.groups()
    return float(price.replace(",", "")), int(bids), bool(bo), int(d or 0) * 1440 + int(h or 0) * 60 + int(mins or 0)

rows = []
for item_id, (pick, grade, year, set_name, note) in PICKS.items():
    s = search[item_id]
    det_path = f"{D}/item_{item_id}.json"
    det = json.load(open(det_path)) if os.path.exists(det_path) else {}
    det = det.get("data", det)
    parsed = parse_detail_price(det.get("price")) if "title" in det else None
    if parsed:
        price, bids, best_offer, mins = parsed
        fetched = datetime.fromtimestamp(os.path.getmtime(det_path), timezone.utc)
        ends_at = (fetched + timedelta(minutes=mins)).isoformat()
        fmt = "Buy It Now" if best_offer else "Auction"  # auctions cannot take Best Offers
    else:
        price, bids, best_offer, ends_at = float(s["price"].strip("$").replace(",", "")), None, False, None
        fmt = "Unknown"
    cl = json.load(open(f"{D}/cl_{item_id}.json"))
    cl = cl.get("data", cl)
    card = cl["cards"][pick] if pick is not None and cl.get("cards") else None
    value = round(card["current_value"], 2) if card else None
    rows.append({
        "id": item_id,
        "title": s["title"],
        "url": s["url"],
        "image": s["image"],
        "format": fmt,
        "price": price,
        "bids": bids,
        "best_offer": best_offer,
        "ends_at": ends_at,
        "est_value": value,
        "vs_value": round(price / value, 4) if value else None,
        "cl_label": card["label"] if card else None,
        "cl_card_id": card["id"] if card else None,
        "cl_num_sales": card["num_sales"] if card else None,
        "cl_last_sold": card["last_sold_date"] if card else None,
        "year": year,
        "set": set_name,
        "grade": grade,
        "seller": (det.get("seller") or {}).get("name"),
        "seller_feedback": ((det.get("seller") or {}).get("feedback") or "").strip("()") or None,
        "note": note,
        "polled_at": "2026-10-13",
    })
json.dump(rows, open(f"{D}/lebron_poll_2026-10-13.json", "w"), indent=1)
for r in rows:
    print(r["id"], r["format"], r["price"], r["bids"], (r["ends_at"] or "")[:16], r["est_value"], r["vs_value"], r["seller"], r["seller_feedback"])

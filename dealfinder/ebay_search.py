"""Search eBay listings via Parse's eBay API.

Stopgap until the official eBay API account is approved. The key comes from
PARSE_API_KEY.
"""

import json
import os
import sys

import httpx

EBAY_SCRAPER_ID = "caa8e1ad-f5a8-41c1-9bd2-54a8e19b6c35"
SNAPSHOT_VERSION = "19"  # pinned so upstream changes don't alter the response shape


def search_listings(query: str, *, sold: bool = False, graded: bool = False, complete: bool = False):
    response = httpx.get(
        f"https://api.parse.bot/scraper/{EBAY_SCRAPER_ID}/search_listings",
        headers={"X-API-Key": os.environ["PARSE_API_KEY"], "API-Snapshot-Version": SNAPSHOT_VERSION},
        params={"query": query, "sold": str(sold), "graded": str(graded), "complete": str(complete)},
        timeout=120,
    )
    response.raise_for_status()
    return response.json()


def main():
    query = sys.argv[1] if len(sys.argv) > 1 else "iphone 15"
    print(json.dumps(search_listings(query), indent=2))


if __name__ == "__main__":
    main()

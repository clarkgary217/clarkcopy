"""Call Card Ladder's search_cards endpoint via Parse.

The marketplace spec for cardladder.com API has no `resources` section yet, so
`parse sync` doesn't generate a typed client for it. Until it does, this calls
the endpoint through the SDK's BaseAPI. The key comes from PARSE_API_KEY.
"""

import json
import sys

from parse_sdk import BaseAPI, ParseError

CARDLADDER_API_ID = "97d5f4bc-6c65-4546-8f71-76149a5533cb"  # canonical cardladder_com_api


class CardLadder(BaseAPI):
    SCRAPER_ID = CARDLADDER_API_ID

    def search_cards(self, query: str, *, limit: int = 5, page: int = 0, **filters):
        return self._request("GET", "search_cards", {"query": query, "limit": limit, "page": page, **filters})


def main():
    query = sys.argv[1] if len(sys.argv) > 1 else "Michael Jordan 1986 Fleer"
    try:
        with CardLadder() as cl:
            result = cl.search_cards(query, limit=5)
    except ParseError as e:
        sys.exit(f"Parse error: {e}")
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()

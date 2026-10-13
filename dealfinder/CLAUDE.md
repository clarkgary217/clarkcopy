# dealfinder

Python (uv) project for the card deal finder. Separate from the Next.js app in the repo root.

## Calling Parse

- Card data comes from the Parse "cardladder.com API" (marketplace slug `cardladder-com-api`), via the `parse-sdk` package.
- Auth: the key is read from the `PARSE_API_KEY` environment variable. Never hard-code or commit it.
- Typed clients are generated into `parse_apis/` by the CLI. Always run the CLI as `uv run parse …`:
  - `uv run parse init` (once), then `uv run parse add --marketplace cardladder-com-api`
  - `uv run parse sync` refreshes clients; `uv run parse doctor --fix` if imports don't resolve
- Import line and method names are in `parse_apis/<module>/README.md`. Catch the typed errors re-exported from `parse_apis`.
- **Current state:** the cardladder spec has no `resources`, so `parse sync` skips it ("un-modeled") and no typed client exists yet. `search_cards.py` calls it through `parse_sdk.BaseAPI` with `SCRAPER_ID` = the canonical API id, catching `parse_sdk.ParseError`. Switch to the generated client once Parse models the API.
- The account also has a `cardladder_com_api_fork` clone synced; use the canonical one unless told otherwise.
- Endpoints: `search_cards` (find cards, get IDs) → `get_card_value` / `get_card_sales` (by card ID).
- Run scripts with `uv run python <file>.py`.
- In the cloud container, set `SSL_CERT_FILE=/root/.ccr/ca-bundle.crt` or CLI calls can time out.
- Network: needs `api.parse.bot` (and `docs.parse.bot` for docs) reachable.

## Parse MCP server

- `.mcp.json` at the repo root registers Parse's hosted MCP server (`https://api.parse.bot/mcp`), authenticated with `X-API-Key: ${PARSE_API_KEY}`. The key is expanded from the environment, never written to the file.
- Tools: `marketplace_search`, `marketplace_subscribe`, `create_api`, `list_apis`, `get_api`, `revise_api`, `call_endpoint`, `fork_updates`, and others. Use `revise_api` to get the cardladder spec modeled so `parse sync` can generate a typed client.
- For cloud sessions, set `PARSE_API_KEY` in the environment's variables. On desktop, export it in your shell before starting Claude Code.

## eBay listings (stopgap)

- `ebay_search.py` calls Parse's eBay API (`search_listings`, scraper `caa8e1ad-…`, pinned with `API-Snapshot-Version: 19`) over plain HTTP via httpx. Use it until the official eBay API account is approved, then replace it.
- Params: `query`, plus `sold` / `graded` / `complete` as "True"/"False" strings. The response is `{"status", "data": {"listings": [...]}}`; each listing has title, price, url, image, condition, shipping, item_id, date_sold.
- Data quirks seen: results include loose matches (an "iphone 15" search returned iPhone 13/14), `shipping` sometimes repeats the price range, and `condition` sometimes holds shipping/returns text. Filter and parse defensively.

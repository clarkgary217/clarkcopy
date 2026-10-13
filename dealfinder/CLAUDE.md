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

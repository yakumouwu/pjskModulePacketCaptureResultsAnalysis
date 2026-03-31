# MysekaiQueryPlaceholder

This plugin provides a usable Mysekai command workflow for LangBot and is intended to work with the receiver API in this repository.

- `mysk bind <mysekai_user_id>`
- `mysk unbind`
- `mysk whoami`
- `mysk map`
- `mysk map site <id>`
- `mysk ping`

Features:

- one-to-one binding (`QQ -> mysekai_user_id`)
- query rate limit per user (default 60s)
- backend API call with optional `X-API-Key`
- supports command prefix forms: `mysk`, `!mysk`, `/mysk`
- invalid `mysk map` args are rejected with a usage hint

Backend-related config keys:

- `backend_base_url`
- `backend_map_api_path`
- `backend_api_key`

Current behavior:

- `mysk bind <mysekai_user_id>` stores a per-QQ binding (`QQ user_id -> mysekai_user_id`)
- `mysk map` queries the latest available full mysekai packet of the bound user
- `mysk map site <id>` returns a single-site map (`id` in `5,6,7,8`)
- full query without `site_id` uses empty text in the successful response
- single-site query with `site_id` uses only the localized Chinese site name as text
- successful backend responses include `source_json` so the render source file can be traced
- unbound query returns: `not bound, use: mysk bind <mysekai_user_id>`
- no data query returns: `map query failed: no full mysekai packet found for user`

Structure follows `LangBotPluginBox` style (`components/event_listener/default.py`).

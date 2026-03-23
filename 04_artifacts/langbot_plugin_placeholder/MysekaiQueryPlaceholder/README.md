# MysekaiQueryPlaceholder

This plugin now contains a usable Mysekai command workflow for LangBot:

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

Structure follows `LangBotPluginBox` style (`components/event_listener/default.py`).

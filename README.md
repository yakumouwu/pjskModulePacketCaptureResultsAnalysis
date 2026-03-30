# project-sekai
[中文](./README.zh-CN.md) | [Docker English](./04_artifacts/docker_receiver_3939_dev/README_DOCKER.md) | [Docker 中文](./04_artifacts/docker_receiver_3939_dev/README_DOCKER.zh-CN.md)

## Overview

This repository provides local and Docker receivers for:
- capturing API responses
- decoding payloads
- generating user profile card images
- sending Mysekai diamond notifications via NapCat

## Local Script (Windows)

- Script path: `01_scripts/import http.py`
- Default port: `8000`
- Shadowrocket `script-path` example:
  - `http://<your-local-ip>:8000/upload.js`

## Docker Receiver (Dev)

- Directory: `04_artifacts/docker_receiver_3939_dev`
- Runtime scripts: `04_artifacts/docker_receiver_3939_dev/dockerScripts`
- Default port: `3939`
- Health check: `GET /healthz`

Build:

```bash
docker build -t pjsk-receiver:latest .
```

Run (example):

```bash
docker run -d \
  --name pjsk-receiver-dev \
  --network <YOUR_DOCKER_NETWORK> \
  --restart=always \
  --log-driver=json-file \
  --log-opt max-size=20m \
  --log-opt max-file=5 \
  -p 3939:3939 \
  -e PUBLIC_HOST=<YOUR_SERVER_PUBLIC_IP_OR_DOMAIN> \
  -e RECEIVER_PORT=3939 \
  -e API_REGION=cn \
  -e OUTPUT_ROOT=/data \
  -e MYSEKAI_RESOURCE_MAP_JSON=/data/config/mysekai_resource_map.json \
  -e RETENTION_COUNT=25 \
  -e BOT_PUSH_ENABLED=1 \
  -e BOT_PUSH_URL=http://napcat:3000 \
  -e BOT_TOKEN=<YOUR_NAPCAT_HTTP_TOKEN> \
  -e BOT_PUSH_MODE=<private_or_group> \
  -e BOT_TARGET_ID=<YOUR_QQ_OR_GROUP_ID> \
  -e NOTIFICATION_USER_LABEL=<YOUR_USER_LABEL> \
  -e BOT_PUSH_RETRY=3 \
  -e BOT_MESSAGE_MODE=text+image \
  -e PLUGIN_API_KEY=<OPTIONAL_PLUGIN_API_KEY> \
  -e PLUGIN_QUERY_IMAGE_RETENTION=25 \
  -e MYSEKAI_MAP_IMAGE_SIZE=1024 \
  -e MYSEKAI_ICON_SIZE=36 \
  -e MYSEKAI_COUNT_FONT_SIZE=18 \
  -e MYSEKAI_ICON_SPREAD=22 \
  -e NOTIFICATION_WINDOW_CACHE_HOURS=72 \
  -e NOTIFICATION_HIT_RETENTION=100 \
  -e NOTIFICATION_EVENT_RETENTION_LINES=5000 \
  -e TZ=Asia/Shanghai \
  -v /opt/pjsk-captures:/data \
  -v /opt/pjsk-config:/data/config \
  -v /opt/docker_receiver_3939_dev/dockerScripts:/app/dockerScripts \
  pjsk-receiver:latest
```

Optional:
- recommended: bind-mount host `dockerScripts/` to container `/app/dockerScripts` so script-only updates do not require rebuilding the image
- when `dockerScripts/` is bind-mounted, script-only updates usually need only removing/recreating the container, not rebuilding the image
- the code fallback and project deployment default both use `BOT_PUSH_MODE=group`

Data output:
- raw payloads: `/data/raw_api/...`
- decoded JSON: `/data/decoded_api/...`
- Mysekai maps: `/data/decoded_api/mysekai/maps/...`
- logs: `/data/logs/receiver.log`
- notification hits: `/data/notifications/hits/`
- notification events: `/data/notifications/diamond_notifications.jsonl`
- automatic notification dedup/render rule: per user, only the first diamond hit in each window triggers render/push (`05:00-17:00` and `17:00-next 05:00`)
- plugin query render rule: with an available full mysekai packet, map rendering is allowed even without diamond hits
- renderer projection rule: fixed-origin mode is used (map center = world `(0,0)`); lock `SITE<id>_WORLD_HALF_X/Z` for stable cross-packet alignment
- single-site render output now preserves the source map aspect ratio (`16:9`), and `MYSEKAI_MAP_IMAGE_SIZE` is treated as target output width
- same-coordinate base material ignore (enabled by default): `MYSEKAI_IGNORE_BASE_MATERIALS=1`

## Key Runtime Settings

Push and notification:
- `BOT_PUSH_MODE`: current code fallback is `group`, and project deployment also defaults to group push; set `private` explicitly if needed
- `BOT_MESSAGE_MODE`: `text`, `image`, or `text+image`; current default strategy is `text+image`, and image push failure falls back to text
- `BOT_PUSH_RETRY`: retry count for NapCat push
- `NOTIFICATION_WINDOW_CACHE_HOURS`: retention for the in-memory/on-disk dedup gate cache
- `NOTIFICATION_HIT_RETENTION`: how many raw notification hit json files to keep
- `NOTIFICATION_EVENT_RETENTION_LINES`: max retained lines in `diamond_notifications.jsonl`
- automatic notification trigger: only diamond hits (`mysekai_material`, `id=12`) can trigger render/push; for each user, only the first hit inside `05:00-17:00` or `17:00-next 05:00` is allowed through

Plugin query:
- `PLUGIN_API_KEY`: optional auth key checked via `X-API-Key`
- `PLUGIN_QUERY_IMAGE_RETENTION`: retained query render image count
- query text policy:
  - full query without `site_id`: empty text
  - single-site query with `site_id`: localized Chinese map name only
- successful responses also include `source_json`, which shows which decoded mysekai file was actually used for the render

Render sizing:
- `MYSEKAI_MAP_IMAGE_SIZE`: target output width for single-site render
- `MYSEKAI_ICON_SIZE`: icon size
- `MYSEKAI_COUNT_FONT_SIZE`: count text size
- `MYSEKAI_ICON_SPREAD`: spread radius for multiple resources on the same coordinate
- `MYSEKAI_IGNORE_BASE_MATERIALS=1`: hide base materials when upgraded variants exist on the same coordinate
- icon coverage:
  - `material` uses its own icon set and is no longer treated as `mysekai_material`
  - `mysekai_music_record` uses the shared `Extra_Record.png` icon
  - unmapped `material` and unmapped `mysekai_fixture` are skipped instead of rendering placeholder dots
  - extra icons can be dropped into `04_artifacts/docker_receiver_3939_dev/dockerScripts/mysekai_assets/icon/`
  - file naming for direct pickup: `material_<id>.png`, `mysekai_fixture_<id>.png`, or `fixture_<id>.png`

Per-site calibration:
- `SITE<id>_WORLD_HALF_X` / `SITE<id>_WORLD_HALF_Z`: fixed world half-span used to project world coordinates into the map; this stabilizes cross-packet alignment
- `SITE<id>_SCALE_X_DELTA` / `SITE<id>_SCALE_Z_DELTA`: fine-tune horizontal/vertical projection scale for one site
- `SITE<id>_OFFSET_X_DELTA` / `SITE<id>_OFFSET_Z_DELTA`: fine-tune projected icon offset for one site
- supported site ids: `5,6,7,8`

## Virtual Diamond Notification Test

```bash
docker exec -i pjsk-receiver-dev python - <<'PY'
import json, importlib.util, os
test_path = "/opt/mysekai_test_id12.json"
data = {
  "updatedResources": {
    "userMysekaiHarvestMaps": [
      {
        "mysekaiSiteId": 8,
        "userMysekaiSiteHarvestResourceDrops": [
          {"resourceType": "mysekai_material", "resourceId": 12, "quantity": 1}
        ]
      }
    ]
  }
}
with open(test_path, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False)
spec = importlib.util.spec_from_file_location("receiver", "/app/dockerScripts/import http.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
mod.setup_logging()
mod.load_dedup_cache()
mod.process_mysekai_notification(
    test_path,
    "https://mkcn-prod-public-60001-1.dailygn.com/api/user/<YOUR_USER_ID>/mysekai?isForceAllReloadOnlyMysekai=True"
)
print("triggered:", os.path.exists(test_path), test_path)
PY
```

## Unit Tests

Run from repository root:

```bash
python -m unittest discover -s tests -p "test_*.py" -v
```

## LangBot Placeholder Plugin (Upload Smoke Test)

- Source directory: `04_artifacts/langbot_plugin_placeholder/MysekaiQueryPlaceholder`
- Upload-ready package:
- `04_artifacts/langbot_plugin_placeholder/dist/MysekaiQueryPlaceholder-0.3.0.lbpkg`
- Supported commands:
- `mysk ping`
- `mysk bind <mysekai_user_id>`
- `mysk unbind`
- `mysk whoami`
- `mysk map`
- `mysk map site <id>`
- invalid `mysk map` args are rejected with usage hint (no silent fallback to full-map query)
- Backend-related config keys:
- `backend_base_url`
- `backend_map_api_path`
- `backend_api_key`

Validated behavior (current):
- `mysk bind <mysekai_user_id>` stores a per-QQ binding (`QQ user_id -> mysekai_user_id`)
- `mysk map` queries the latest available full mysekai packet of the bound user
- `mysk map site <id>` returns a single-site map (`id` in `5,6,7,8`)
- unbound query returns: `not bound, use: mysk bind <mysekai_user_id>`
- no data query returns: `map query failed: no full mysekai packet found for user`

## End-to-End Checklist (Capture -> Decode -> NapCat Push)

### 1) Server / Network

- Open security group / firewall TCP `3939`
- Prepare persistent directory (example: `/opt/pjsk-captures`)
- Ensure receiver and NapCat are in the same Docker network

### 2) Deploy Receiver

- Build image from `04_artifacts/docker_receiver_3939_dev`
- Runtime code is copied from `dockerScripts/` to `/app/dockerScripts`
- If host `dockerScripts/` is bind-mounted to `/app/dockerScripts`, script-only updates usually require only recreating the container, not rebuilding the image
- Run with at least:
  - `-p 3939:3939`
  - `-v /opt/pjsk-captures:/data`
  - `-e PUBLIC_HOST=<YOUR_SERVER_PUBLIC_IP_OR_DOMAIN>`
  - if notifications are enabled, configure `BOT_PUSH_*` and `BOT_TOKEN`

### 3) Configure NapCat HTTP API

- Enable one HTTP server endpoint in NapCat WebUI (typically `0.0.0.0:3000`)
- Pass the HTTP token to receiver via `BOT_TOKEN`
- Verify from receiver container:
  - `http://napcat:3000` is reachable
  - `401/403` usually means connectivity is fine but token is missing/wrong

### 4) Configure Shadowrocket Module

- `script-path`:
  - `http://<PUBLIC_HOST>:3939/upload.js`
- `pattern` should match required endpoints:
  - `suite`
  - `mysekai`:
    - `/api/user/<uid>/mysekai?isForceAllReloadOnlyMysekai=True|False`

## Icon Overrides
- mysekai_material and mysekai_item now prefer local override files named after iconAssetbundleName, for example item_plant_4.png, before falling back to the shared built-in icon mapping.
- mysekai_fixture now uses canonical local filenames such as mysekai_fixture_<id>.png or fixture_<id>.png.
- visual hierarchy: common materials render as large icons; rare drops (world fragments, blueprint scraps, fixture/seed/sapling, and other special drops) render as smaller semi-transparent icons. Diamonds only fall back to the small tier when they share the same coordinate with stone/mineral drops.

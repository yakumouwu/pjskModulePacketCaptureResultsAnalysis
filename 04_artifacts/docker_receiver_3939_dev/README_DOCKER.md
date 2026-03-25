# Mysekai/Suite Receiver Docker (Port 3939)
[中文](./README_DOCKER.zh-CN.md) | [Project README](../../README.md) | [项目中文总览](../../README.zh-CN.md)

Runtime scripts are stored in `dockerScripts/` and copied into the image as `/app/dockerScripts`.
The image now installs `Noto Sans CJK`, so `MYSEKAI_COUNT_FONT_SIZE` and Chinese text rendering work consistently.
Recommended deployment mode: also bind-mount the host script directory to `/app/dockerScripts`. That way, later script-only updates only require replacing host files and recreating the container, without rebuilding the image every time.

## Build

Note:
- The Dockerfile now rewrites Debian `apt` sources to the Aliyun mirror to reduce slow package downloads in mainland China environments.

```bash
docker build -t pjsk-receiver:latest .
```

## Run

IMPORTANT:
- Receiver and NapCat must be in the same user-defined Docker network when `BOT_PUSH_URL` points to `http://napcat:3000`.
- Create one if needed: `docker network create <YOUR_DOCKER_NETWORK>`.
- Keep IDs/tokens as placeholders in documentation; fill them only in your deployment environment.

```bash
docker run -d \
  --name pjsk-receiver \
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

Note: query rendering now uses a fixed-origin projection (map center is world `(0,0)`). Single-site outputs preserve the original map aspect ratio (`16:9`), and `MYSEKAI_MAP_IMAGE_SIZE` is treated as output width. All four sites now ship with calibrated built-in defaults, and you can still override them with `SITE<id>_*_DELTA` if needed.

## Recommended update flow (no image rebuild)

Prerequisites:
- Python dependencies and base runtime in the image have not changed
- You only changed scripts under `dockerScripts/`
- The container was started with `-v /opt/docker_receiver_3939_dev/dockerScripts:/app/dockerScripts`

Example server flow:

```bash
cd /opt/docker_receiver_3939_dev
docker rm -f pjsk-receiver-dev
docker run -d \
  --name pjsk-receiver-dev \
  --network langbot-network \
  --restart=always \
  --log-driver=json-file \
  --log-opt max-size=20m \
  --log-opt max-file=5 \
  -p 3939:3939 \
  -e PUBLIC_HOST=39.97.43.115 \
  -e RECEIVER_PORT=3939 \
  -e API_REGION=cn \
  -e OUTPUT_ROOT=/data \
  -e MYSEKAI_RESOURCE_MAP_JSON=/data/config/mysekai_resource_map.json \
  -e RETENTION_COUNT=25 \
  -e BOT_PUSH_ENABLED=1 \
  -e BOT_PUSH_URL=http://napcat:3000 \
  -e BOT_TOKEN=<YOUR_NAPCAT_HTTP_TOKEN> \
  -e BOT_PUSH_MODE=group \
  -e BOT_TARGET_ID=<YOUR_QQ_OR_GROUP_ID> \
  -e BOT_PUSH_RETRY=3 \
  -e BOT_MESSAGE_MODE=text+image \
  -e PLUGIN_QUERY_IMAGE_RETENTION=25 \
  -e MYSEKAI_MAP_IMAGE_SIZE=1024 \
  -e MYSEKAI_ICON_SIZE=36 \
  -e MYSEKAI_COUNT_FONT_SIZE=18 \
  -e MYSEKAI_ICON_SPREAD=22 \
  -e MYSEKAI_IGNORE_BASE_MATERIALS=1 \
  -e NOTIFICATION_WINDOW_CACHE_HOURS=72 \
  -e NOTIFICATION_HIT_RETENTION=100 \
  -e NOTIFICATION_EVENT_RETENTION_LINES=5000 \
  -e TZ=Asia/Shanghai \
  -v /opt/pjsk-captures:/data \
  -v /opt/pjsk-config:/data/config \
  -v /opt/docker_receiver_3939_dev/dockerScripts:/app/dockerScripts \
  pjsk-receiver:dev3939
```

Notes:
- If you changed the `Dockerfile`, Python dependencies, or system packages, you still need to rebuild the image.
- If you only changed runtime scripts such as `render_mysekai_map.py` or `import http.py`, the mounted-script flow above is enough.

Quick checks after start:

```bash
docker logs -n 80 pjsk-receiver
docker exec -it pjsk-receiver python -m pip show sssekai
docker exec -it pjsk-receiver python -m sssekai -h
curl -sS http://127.0.0.1:3939/healthz
```

Container-to-container connectivity check (from `langbot` container):

```bash
docker exec -it langbot python -c "import urllib.request;print(urllib.request.urlopen('http://pjsk-receiver-dev:3939/healthz',timeout=5).read().decode())"
docker exec -it langbot python -c "import urllib.request;print(urllib.request.urlopen('http://pjsk-receiver-dev:3939/api/plugin/mysekai/map?mysekai_user_id=<YOUR_MYSEKAI_USER_ID>&requester_qq=123456',timeout=20).read().decode())"
```

Post-rebuild rendering test (generic single-site):

```bash
docker exec -it pjsk-receiver-dev /bin/sh -lc 'python /app/dockerScripts/render_mysekai_map.py \
  /data/decoded_api/mysekai/<YOUR_SOURCE_JSON>.json \
  /data/decoded_api/mysekai/maps/plugin_api/site_check.png \
  /app/dockerScripts/mysekai_assets \
  --site-id <5|6|7|8> --target-size 1024'
```

## Data paths in container

- raw bin: /data/raw_api/suite or /data/raw_api/mysekai
- decoded json: /data/decoded_api/suite or /data/decoded_api/mysekai
- mysekai rendered maps: /data/decoded_api/mysekai/maps
- service logs (rolling): /data/logs/receiver.log
- diamond notification trigger: decoded mysekai full packet contains `mysekai_material:12`
- automatic notification render trigger: only the first id=12 hit in current window can render/push (`05:00-17:00`, `17:00-next 05:00`)
- plugin query render trigger: any available full mysekai packet can be rendered (not limited by diamond hit)
- render output: one image per hit site; only hit sites are generated/sent
- render tuning:
  - `MYSEKAI_MAP_IMAGE_SIZE`: target output width (single-site output keeps original `16:9` aspect ratio)
  - `MYSEKAI_ICON_SIZE`: icon size on map
  - `MYSEKAI_COUNT_FONT_SIZE`: quantity text size
  - `MYSEKAI_ICON_SPREAD`: spread radius for multi-resource points
  - `MYSEKAI_IGNORE_BASE_MATERIALS`: whether to hide base materials on the same coordinate (default `1`)
    - rule: hide `id=1` if any `id=2..5` exists at that coordinate; hide `id=6` if any `id=7..12` exists
  - fallback icons: only diamond (`mysekai_material:12`) and blueprint scrap (`mysekai_item:7`) are hardcoded
  - unmapped music records are skipped entirely and no longer render placeholder dots
  - fixed world scale (recommended to lock first):
    - `SITE<id>_WORLD_HALF_X`, `SITE<id>_WORLD_HALF_Z`
    - meaning: world half-range projected onto the map (current built-ins: site5 `30/75`, site6 `30/68`, site7 `30/75`, site8 `30/70`)
  - optional per-site tuning:
    - `SITE<id>_OFFSET_X_DELTA`, `SITE<id>_OFFSET_Z_DELTA`
    - `SITE<id>_SCALE_X_DELTA`, `SITE<id>_SCALE_Z_DELTA`
  - multi-resource icons on the same coordinate now use deterministic ordering (resource type + id)
  - current built-in defaults:
    - site5: `scale_add=(25.5,25.5)`, `offset_add=(0,-90)`
    - site6: `scale_add=(16.6,16.2)`, `offset_add=(20,120)`
    - site7: `scale_add=(19,19)`, `offset_add=(-60,20)`
    - site8: `scale_add=(16.6,16.2)`, `offset_add=(20,-120)`
- diamond hit archives: /data/notifications/hits/
- diamond notification events: /data/notifications/diamond_notifications.jsonl
- health check endpoint: GET /healthz
- plugin map query endpoint: GET /api/plugin/mysekai/map
- plugin image file endpoint: GET /api/plugin/mysekai/file?name=<file_name>
- `BOT_TOKEN` is the NapCat HTTP server token (Authorization Bearer token)

## Plugin Query API

- Optional auth header: `X-API-Key` (enabled only when `PLUGIN_API_KEY` is set)
- Query parameters:
  - `mysekai_user_id` (required)
  - `requester_qq` (optional)
  - `site_id` (optional, one of `5,6,7,8`; labels: `初始空地/心愿沙滩/烂漫花田/忘却之所`)
- Successful response format:
  - `{ "ok": true, "message": "ok", "data": { "text": "...", "images": ["http://..."] } }`
  - Text rule:
    - full query (without `site_id`) returns empty text
    - single-site query (with `site_id`) returns localized map name only (e.g. `地图：心愿沙滩`)

## NapCat API baseline (v4.17.48)

For push implementation, use these action endpoints:
- `POST {BOT_PUSH_URL}/send_private_msg`
- `POST {BOT_PUSH_URL}/send_group_msg`

Message body:
- `message` can be plain string, or segment array
- image segment:
  - `{"type":"image","data":{"file":"<path|url|base64>"}}`

## Host mapped path example

If you use `-v /opt/pjsk-captures:/data`, then on server:

- /opt/pjsk-captures/raw_api/...
- /opt/pjsk-captures/decoded_api/...
- /opt/pjsk-captures/decoded_api/mysekai/maps/...
- /opt/pjsk-captures/logs/receiver.log

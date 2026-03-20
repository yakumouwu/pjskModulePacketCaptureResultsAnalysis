# Mysekai/Suite Receiver Docker (Port 3939)
[中文](./README_DOCKER.zh-CN.md) | [Project README](../../README.md) | [项目中文总览](../../README.zh-CN.md)

Runtime scripts are stored in `dockerScripts/` and copied into the image as `/app/dockerScripts`.

## Build

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
  pjsk-receiver:latest
```

Quick checks after start:

```bash
docker logs -n 80 pjsk-receiver
docker exec -it pjsk-receiver python -m pip show sssekai
docker exec -it pjsk-receiver python -m sssekai -h
curl -sS http://127.0.0.1:3939/healthz
```

## Data paths in container

- raw bin: /data/raw_api/suite or /data/raw_api/mysekai
- decoded json: /data/decoded_api/suite or /data/decoded_api/mysekai
- mysekai rendered maps: /data/decoded_api/mysekai/maps
- service logs (rolling): /data/logs/receiver.log
- diamond notification trigger: decoded mysekai full packet contains `mysekai_material:12`
- render trigger: only when id=12 hit passes dedup in current time window
- render output: one image per hit site; only hit sites are generated/sent
- render tuning:
  - `MYSEKAI_MAP_IMAGE_SIZE`: final output size
  - `MYSEKAI_ICON_SIZE`: icon size on map
  - `MYSEKAI_COUNT_FONT_SIZE`: quantity text size
  - `MYSEKAI_ICON_SPREAD`: spread radius for multi-resource points
  - optional per-site tuning:
    - `SITE<id>_OFFSET_X_DELTA`, `SITE<id>_OFFSET_Z_DELTA`
    - `SITE<id>_SCALE_X_DELTA`, `SITE<id>_SCALE_Z_DELTA`
  - current default calibration lifts site 6 (beach) overlays by about 12.5% vertically
- diamond hit archives: /data/notifications/hits/
- diamond notification events: /data/notifications/diamond_notifications.jsonl
- health check endpoint: GET /healthz
- `BOT_TOKEN` is the NapCat HTTP server token (Authorization Bearer token)

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

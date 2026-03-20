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

Optional:
- place `mysekai_resource_map.json` in the proper config path to improve icon mapping accuracy

Data output:
- raw payloads: `/data/raw_api/...`
- decoded JSON: `/data/decoded_api/...`
- Mysekai maps: `/data/decoded_api/mysekai/maps/...`
- logs: `/data/logs/receiver.log`
- notification hits: `/data/notifications/hits/`
- notification events: `/data/notifications/diamond_notifications.jsonl`

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

## End-to-End Checklist (Capture -> Decode -> NapCat Push)

### 1) Server / Network

- Open security group / firewall TCP `3939`
- Prepare persistent directory (example: `/opt/pjsk-captures`)
- Ensure receiver and NapCat are in the same Docker network

### 2) Deploy Receiver

- Build image from `04_artifacts/docker_receiver_3939_dev`
- Runtime code is copied from `dockerScripts/` to `/app/dockerScripts`
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

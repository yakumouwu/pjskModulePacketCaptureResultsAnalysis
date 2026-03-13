# project-sekai

## Overview

This repository contains local and dockerized receivers for:
- capturing `suite` / `mysekai` API payloads
- decoding payloads
- generating suite card images
- optional Mysekai diamond (`id=12`) alert push via NapCat

## Local Script (Windows)

- Script path: `01_scripts/import http.py`
- Default port: `8000`
- Use with Shadowrocket `script-path`:
  - `http://<your-local-ip>:8000/upload.js`

## Docker Receiver (Dev)

- Directory: `04_artifacts/docker_receiver_3939_dev`
- Runtime scripts: `04_artifacts/docker_receiver_3939_dev/dockerScripts`
- Default port: `3939`
- Health check: `GET /healthz`

Build:

```bash
docker build -t pjsk-receiver:dev3939 .
```

Run (example):

```bash
# Prerequisites:
# 1) Receiver and NapCat must be in the same user-defined Docker network.
# 2) Keep placeholders in docs; fill real IDs/tokens only in your own environment.
# Create network if needed:
# docker network create <YOUR_DOCKER_NETWORK>

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
  -e ALERT_WINDOW_CACHE_HOURS=72 \
  -e ALERT_HIT_RETENTION=100 \
  -e ALERT_EVENT_RETENTION_LINES=5000 \
  -v /opt/pjsk-captures:/data \
  -v /opt/pjsk-config:/data/config \
  pjsk-receiver:dev3939
```

Optional:
- place `mysekai_resource_map.json` at `/opt/pjsk-config/mysekai_resource_map.json`
- this is used to improve id/name/icon mapping for Mysekai render output

Data output:
- raw payloads: `/data/raw_api/...`
- decoded json: `/data/decoded_api/...`
- mysekai rendered maps: `/data/decoded_api/mysekai/maps/...`
- logs: `/data/logs/receiver.log`
- alert hits: `/data/alerts/hits/`
- alert events: `/data/alerts/diamond_events.jsonl`

Quick checks after start:

```bash
docker logs -n 80 pjsk-receiver-dev
docker exec -it pjsk-receiver-dev python -m pip show sssekai
docker exec -it pjsk-receiver-dev python -m sssekai -h
curl -sS http://127.0.0.1:3939/healthz
```

## Virtual Diamond Alert Test

Run inside server to trigger test alert without entering game:

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
mod.process_mysekai_alert(
    test_path,
    "https://mkcn-prod-public-60001-1.dailygn.com/api/user/<YOUR_USER_ID>/mysekai?isForceAllReloadOnlyMysekai=True"
)
print("triggered:", os.path.exists(test_path), test_path)
PY
```

Notes:
- `BOT_TOKEN` is the NapCat HTTP server token (used as `Authorization: Bearer <token>`).
- If `BOT_PUSH_URL` uses a container name (for example `http://napcat:3000`), ensure both containers are attached to the same Docker network.

## End-to-End Checklist (Capture -> Decode -> NapCat Push)

Use this checklist when you want the complete pipeline to work on a server.

### 1) Server / Network

- Open server security-group/firewall TCP port `3939`.
- Prepare persistent host directory (example): `/opt/pjsk-captures`.
- Ensure receiver and NapCat containers are in the same Docker network.

### 2) Deploy receiver container

- Build image from `04_artifacts/docker_receiver_3939_dev`.
- The image copies runtime code from `dockerScripts/` into `/app/dockerScripts`.
- Run with:
  - `-p 3939:3939`
  - `-v /opt/pjsk-captures:/data`
  - `-e PUBLIC_HOST=<YOUR_SERVER_PUBLIC_IP_OR_DOMAIN>`
  - NapCat push envs (`BOT_PUSH_*`, `BOT_TOKEN`) if alert is enabled.

### 3) Configure NapCat HTTP API

- In NapCat WebUI, enable one HTTP server endpoint (normally `0.0.0.0:3000`).
- Keep/record the HTTP token and pass it to receiver via `BOT_TOKEN`.
- Verify from receiver container:
  - `curl`/request to `http://napcat:3000` is reachable in the same Docker network.
  - Unauthorized (`401/403`) means connectivity is OK but token is missing/wrong.

### 4) Configure Shadowrocket module

- `script-path` must point to:
  - `http://<PUBLIC_HOST>:3939/upload.js`
- `pattern` must match real game endpoints you need:
  - `suite` endpoint(s)
  - `mysekai` endpoint(s), especially full packet URL:
    - `/api/user/<uid>/mysekai?isForceAllReloadOnlyMysekai=True|False`
- `hostname` in `[Mitm]` must include all related game domains.
- Install and trust mitm certificate on iOS, and enable MITM for the module.

### 5) Trigger and verify data capture

- Enter game and trigger target APIs:
  - login flow for user/suite data
  - enter Mysekai for Mysekai data
- Check receiver logs:
  - `Saved [SUITE]` / `Saved [MYSEKAI]`
  - `Decoded JSON: ...`
- Check files:
  - `/opt/pjsk-captures/raw_api/...`
  - `/opt/pjsk-captures/decoded_api/...`

### 6) Verify push path

- Use virtual test (section `Virtual Diamond Alert Test`) to send a synthetic `id=12` packet.
- Expected:
  - `/data/alerts/hits/*.json` created
  - `/data/alerts/diamond_events.jsonl` appended
  - NapCat sends message to configured private QQ or group target.

### 7) Runtime behavior (current implementation)

- Diamond alert source: decoded **full** Mysekai packet containing `mysekai_material:12`.
- Dedup logic is window-based:
  - refresh windows at local `05:00` and `17:00`
  - same point in same window is not pushed repeatedly
  - dedup cache persisted at `/data/alerts/dedup_cache.json`
- Retention:
  - raw/decoded/cards keep latest `RETENTION_COUNT`
  - alert hit files keep `ALERT_HIT_RETENTION`
  - alert events jsonl keep latest `ALERT_EVENT_RETENTION_LINES` lines

### 8) Common failure points

- Only `GET /upload.js` appears, but no `POST /upload`:
  - module `pattern` not matched or script not attached to response.
- Game hangs on Mysekai:
  - over-aggressive rewrite/redirect rules; reduce to script capture only.
- Push fails `Connection refused`:
  - receiver cannot reach NapCat host/port in Docker network.
- Push fails `401/403`:
  - token mismatch; recheck `BOT_TOKEN` and NapCat HTTP server token.

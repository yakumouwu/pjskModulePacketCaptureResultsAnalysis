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
- Default port: `3939`
- Health check: `GET /healthz`

Build:

```bash
docker build -t pjsk-receiver:dev3939 .
```

Run (example):

```bash
docker run -d \
  --name pjsk-receiver-dev \
  --network langbot-network \
  --restart=always \
  --log-driver=json-file \
  --log-opt max-size=20m \
  --log-opt max-file=5 \
  -p 3939:3939 \
  -e PUBLIC_HOST=<YOUR_SERVER_PUBLIC_IP_OR_DOMAIN> \
  -e RECEIVER_PORT=3939 \
  -e API_REGION=cn \
  -e OUTPUT_ROOT=/data \
  -e RETENTION_COUNT=25 \
  -e BOT_PUSH_ENABLED=1 \
  -e BOT_PUSH_URL=http://napcat:3000 \
  -e BOT_TOKEN=<YOUR_NAPCAT_HTTP_TOKEN> \
  -e BOT_PUSH_MODE=private \
  -e BOT_TARGET_ID=<YOUR_QQ_OR_GROUP_ID> \
  -e BOT_PUSH_RETRY=3 \
  -e ALERT_DEDUP_SECONDS=120 \
  -e ALERT_HIT_RETENTION=100 \
  -e ALERT_EVENT_RETENTION_LINES=5000 \
  -v /opt/pjsk-captures:/data \
  pjsk-receiver:dev3939
```

Data output:
- raw payloads: `/data/raw_api/...`
- decoded json: `/data/decoded_api/...`
- logs: `/data/logs/receiver.log`
- alert hits: `/data/alerts/hits/`
- alert events: `/data/alerts/diamond_events.jsonl`

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
spec = importlib.util.spec_from_file_location("receiver", "/app/01_scripts/import http.py")
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

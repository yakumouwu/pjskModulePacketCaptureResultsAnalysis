# Mysekai/Suite Receiver Docker (Port 3939)

## Build

```bash
docker build -t pjsk-receiver:3939 .
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
  pjsk-receiver:3939
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
- service logs (rolling): /data/logs/receiver.log
- diamond alert trigger: decoded mysekai full packet contains `mysekai_material:12`
- diamond hit archives: /data/alerts/hits/
- diamond alert events: /data/alerts/diamond_events.jsonl
- health check endpoint: GET /healthz
- `BOT_TOKEN` is the NapCat HTTP server token (Authorization Bearer token)

## Host mapped path example

If you use `-v /opt/pjsk-captures:/data`, then on server:

- /opt/pjsk-captures/raw_api/...
- /opt/pjsk-captures/decoded_api/...
- /opt/pjsk-captures/logs/receiver.log

# Mysekai/Suite Receiver Docker (Port 3939)

## Build

docker build -t pjsk-receiver:3939 .

## Run

docker run -d \
  --name pjsk-receiver \
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
  pjsk-receiver:3939

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

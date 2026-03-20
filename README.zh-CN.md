# project-sekai
[English](./README.md) | [Docker English](./04_artifacts/docker_receiver_3939_dev/README_DOCKER.md) | [Docker 中文](./04_artifacts/docker_receiver_3939_dev/README_DOCKER.zh-CN.md)

## 项目概览

本仓库提供本地版与 Docker 版接收器，用于：
- 捕获 API 响应
- 解密 payload
- 生成用户信息卡片图
- 通过 NapCat 推送 Mysekai 钻石通知

## 本地脚本（Windows）

- 脚本路径：`01_scripts/import http.py`
- 默认端口：`8000`
- Shadowrocket `script-path` 示例：
  - `http://<your-local-ip>:8000/upload.js`

## Docker 接收器（Dev）

- 目录：`04_artifacts/docker_receiver_3939_dev`
- 运行脚本：`04_artifacts/docker_receiver_3939_dev/dockerScripts`
- 默认端口：`3939`
- 健康检查：`GET /healthz`

构建：

```bash
docker build -t pjsk-receiver:latest .
```

启动（示例）：

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

可选配置：
- 将 `mysekai_resource_map.json` 放到对应目录以提升图标映射准确性

数据输出路径：
- 原始包：`/data/raw_api/...`
- 解密 JSON：`/data/decoded_api/...`
- Mysekai 渲染图：`/data/decoded_api/mysekai/maps/...`
- 日志：`/data/logs/receiver.log`
- 通知命中归档：`/data/notifications/hits/`
- 通知事件：`/data/notifications/diamond_notifications.jsonl`

## 虚拟钻石通知测试

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

## 端到端检查清单（Capture -> Decode -> NapCat Push）

### 1) 服务器 / 网络

- 放行安全组/防火墙 TCP `3939`
- 准备持久化目录（如：`/opt/pjsk-captures`）
- 确保 Receiver 与 NapCat 在同一 Docker 网络

### 2) 部署 Receiver

- 从 `04_artifacts/docker_receiver_3939_dev` 构建镜像
- 镜像会把 `dockerScripts/` 拷贝到 `/app/dockerScripts`
- 启动时至少包含：
  - `-p 3939:3939`
  - `-v /opt/pjsk-captures:/data`
  - `-e PUBLIC_HOST=<YOUR_SERVER_PUBLIC_IP_OR_DOMAIN>`
  - 如需通知推送，再配置 `BOT_PUSH_*` 与 `BOT_TOKEN`

### 3) 配置 NapCat HTTP API

- 在 NapCat WebUI 开启一个 HTTP Server（通常 `0.0.0.0:3000`）
- 记录 Token 并通过 `BOT_TOKEN` 注入 Receiver
- 在 Receiver 容器内验证：
  - 能访问 `http://napcat:3000`
  - `401/403` 通常说明联通正常但 Token 错误或缺失

### 4) 配置 Shadowrocket 模块

- `script-path` 指向：
  - `http://<PUBLIC_HOST>:3939/upload.js`
- `pattern` 要匹配你需要捕获的接口：
  - `suite` 接口
  - `mysekai` 接口：
    - `/api/user/<uid>/mysekai?isForceAllReloadOnlyMysekai=True|False`
# Mysekai/Suite Receiver Docker 指南（端口 3939）
[English](./README_DOCKER.md) | [Project README](../../README.md) | [项目中文总览](../../README.zh-CN.md)

运行脚本位于 `dockerScripts/`，构建镜像时会复制到容器内 `/app/dockerScripts`。

## 构建镜像

```bash
docker build -t pjsk-receiver:latest .
```

## 启动容器

注意：
- 当 `BOT_PUSH_URL` 为 `http://napcat:3000` 时，Receiver 与 NapCat 必须在同一个自定义 Docker 网络中。
- 如果没有该网络，可先创建：`docker network create <YOUR_DOCKER_NETWORK>`。
- 文档中的 ID/Token 均为占位，请在实际部署时替换为你自己的参数。

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
  -e SITE6_OFFSET_Z_DELTA=55 \ 
  -e SITE6_OFFSET_X_DELTA=25 \ 
  -e NOTIFICATION_WINDOW_CACHE_HOURS=72 \
  -e NOTIFICATION_HIT_RETENTION=100 \
  -e NOTIFICATION_EVENT_RETENTION_LINES=5000 \
  -e TZ=Asia/Shanghai \
  -v /opt/pjsk-captures:/data \
  -v /opt/pjsk-config:/data/config \
  pjsk-receiver:latest
```

说明：`SITE6_OFFSET_Z_DELTA=35` 为可选微调参数，用于当前部署中的 site6 查询渲染校准。

启动后快速检查：

```bash
docker logs -n 80 pjsk-receiver
docker exec -it pjsk-receiver python -m pip show sssekai
docker exec -it pjsk-receiver python -m sssekai -h
curl -sS http://127.0.0.1:3939/healthz
```

从 `langbot` 容器检查联通性（容器到容器）：

```bash
docker exec -it langbot python -c "import urllib.request;print(urllib.request.urlopen('http://pjsk-receiver-dev:3939/healthz',timeout=5).read().decode())"
docker exec -it langbot python -c "import urllib.request;print(urllib.request.urlopen('http://pjsk-receiver-dev:3939/api/plugin/mysekai/map?mysekai_user_id=<YOUR_MYSEKAI_USER_ID>&requester_qq=123456',timeout=20).read().decode())"
```

重建后渲染测试（site6）：

```bash
docker exec -it pjsk-receiver-dev /bin/sh -lc 'SITE6_OFFSET_Z_DELTA=35 python /app/dockerScripts/render_mysekai_map.py \
  /data/decoded_api/mysekai/<YOUR_SOURCE_JSON>.json \
  /data/decoded_api/mysekai/maps/plugin_api/site6_final_check.png \
  /app/dockerScripts/mysekai_assets \
  --site-id 6 --target-size 1024'
```

## 容器内数据路径

- 原始 bin：`/data/raw_api/suite` 或 `/data/raw_api/mysekai`
- 解密 json：`/data/decoded_api/suite` 或 `/data/decoded_api/mysekai`
- Mysekai 渲染图：`/data/decoded_api/mysekai/maps`
- 服务日志（滚动）：`/data/logs/receiver.log`
- 钻石通知触发条件：解密后的完整 mysekai 包中出现 `mysekai_material:12`
- 自动通知渲染触发条件：仅当前窗口首次命中 id=12 时触发（05:00-17:00、17:00-次日05:00）
- 插件查询渲染触发条件：有可用全量 mysekai 包即可渲染
- 渲染输出：按命中地图分别输出多张图，仅生成/发送命中地图
- 渲染参数：
  - `MYSEKAI_MAP_IMAGE_SIZE`：最终图片尺寸
  - `MYSEKAI_ICON_SIZE`：图标尺寸
  - `MYSEKAI_COUNT_FONT_SIZE`：数量文字尺寸
  - `MYSEKAI_ICON_SPREAD`：同点多资源图标扩散半径
  - 可选站点微调：
    - `SITE<id>_OFFSET_X_DELTA`、`SITE<id>_OFFSET_Z_DELTA`
    - `SITE<id>_SCALE_X_DELTA`、`SITE<id>_SCALE_Z_DELTA`
- 钻石命中归档：`/data/notifications/hits/`
- 通知事件日志：`/data/notifications/diamond_notifications.jsonl`
- 健康检查接口：`GET /healthz`
- 插件地图查询接口：`GET /api/plugin/mysekai/map`
- 插件图片文件接口：`GET /api/plugin/mysekai/file?name=<file_name>`
- `BOT_TOKEN` 为 NapCat HTTP Server Token（Bearer Token）

## 插件查询 API

- 可选鉴权头：`X-API-Key`（仅当 `PLUGIN_API_KEY` 非空时启用）
- 查询参数：
  - `mysekai_user_id`（必填）
  - `requester_qq`（可选）
  - `site_id`（可选，取值 `5,6,7,8`，分别对应 `初始空地/心愿沙滩/烂漫花田/忘却之所`）
- 成功响应格式：
  - `{ "ok": true, "message": "ok", "data": { "text": "...", "images": ["http://..."] } }`
  - 文本规则：
    - 全量查询（不带 `site_id`）返回空文本
    - 单图查询（带 `site_id`）仅显示中文地图名（例如：`地图：心愿沙滩`）

## NapCat API 基线（v4.17.48）

推送使用以下 action 接口：
- `POST {BOT_PUSH_URL}/send_private_msg`
- `POST {BOT_PUSH_URL}/send_group_msg`

消息体说明：
- `message` 可为字符串，或消息段数组
- 图片消息段格式：
  - `{"type":"image","data":{"file":"<path|url|base64>"}}`

## 宿主机路径映射示例

若使用 `-v /opt/pjsk-captures:/data`，则服务端可在以下路径查看输出：

- `/opt/pjsk-captures/raw_api/...`
- `/opt/pjsk-captures/decoded_api/...`
- `/opt/pjsk-captures/decoded_api/mysekai/maps/...`
- `/opt/pjsk-captures/logs/receiver.log`

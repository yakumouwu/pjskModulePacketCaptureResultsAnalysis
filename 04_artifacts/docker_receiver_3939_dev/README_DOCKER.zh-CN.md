# Mysekai/Suite Receiver Docker 指南（端口 3939）
[English](./README_DOCKER.md) | [Project README](../../README.md) | [项目中文总览](../../README.zh-CN.md)

## 构建镜像

```bash
docker build -t pjsk-receiver:latest .
```

## 启动容器

注意：
- Receiver 与 NapCat 必须在同一个 Docker 网络中：`docker network create <YOUR_DOCKER_NETWORK>`。
- 文档中的 ID/Token 均为占位，请在实际部署时替换为你自己的参数。
- 推荐把宿主机 `dockerScripts/` 挂载到容器 `/app/dockerScripts`；如果只是脚本更新，通常只需要重建容器，无需重建镜像。

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

渲染测试（通用单图）：

```bash
docker exec -it pjsk-receiver-dev /bin/sh -lc 'python /app/dockerScripts/render_mysekai_map.py \
  /data/decoded_api/mysekai/<YOUR_SOURCE_JSON>.json \
  /data/decoded_api/mysekai/maps/plugin_api/site_check.png \
  /app/dockerScripts/mysekai_assets \
  --site-id <5|6|7|8> --target-size 1024'
```

## 容器内数据路径

- 原始 bin：`/data/raw_api/suite` 或 `/data/raw_api/mysekai`
- 解密 json：`/data/decoded_api/suite` 或 `/data/decoded_api/mysekai`
- Mysekai 渲染图：`/data/decoded_api/mysekai/maps`
- 服务日志（滚动）：`/data/logs/receiver.log`
- 渲染参数：
  - `MYSEKAI_MAP_IMAGE_SIZE`：输出目标宽度
  - `MYSEKAI_ICON_SIZE`：图标尺寸
  - `MYSEKAI_COUNT_FONT_SIZE`：数量文字尺寸
  - `MYSEKAI_ICON_SPREAD`：同点多资源图标扩散半径
  - `MYSEKAI_IGNORE_BASE_MATERIALS`：是否忽略同点位普通材料
  - `material` 使用独立图标组，不再按 `mysekai_material` 解释
  - `mysekai_music_record` 统一使用共享图标 `Extra_Record.png`
  - 未映射的 `material`、未映射的 `mysekai_fixture` 会直接跳过，不再画占位点
  - 额外图标可放到 `/app/dockerScripts/mysekai_assets/icon/`
  - 直接识别的文件名：`material_<id>.png`、`mysekai_fixture_<id>.png`、`fixture_<id>.png`
  - `SITE<id>_WORLD_HALF_X` / `SITE<id>_WORLD_HALF_Z`：站点固定世界尺度，控制世界坐标到地图坐标的稳定投影
  - `SITE<id>_SCALE_X_DELTA` / `SITE<id>_SCALE_Z_DELTA`：站点级缩放微调
  - `SITE<id>_OFFSET_X_DELTA` / `SITE<id>_OFFSET_Z_DELTA`：站点级偏移微调
- 自动通知归档：`/data/notifications/hits/`
- 通知事件日志：`/data/notifications/diamond_notifications.jsonl`
- 健康检查接口：`GET /healthz`
- 插件地图查询接口：`GET /api/plugin/mysekai/map`
- 插件图片文件接口：`GET /api/plugin/mysekai/file?name=<file_name>`
- `BOT_TOKEN` 为 NapCat HTTP Server Token（Bearer Token）

## 通知与渲染规则

- 自动通知只在检测到钻石命中时触发：`resourceType=mysekai_material` 且 `resourceId=12`
- 去重窗口固定为本地时间 `05:00-17:00` 与 `17:00-次日05:00`
- 同一用户在同一窗口内仅首次钻石命中会触发渲染与推送；同窗口内后续命中不会再次出图或推送
- 默认推送模式为 `group`
- 默认消息模式为 `text+image`
- 若图片推送失败，会自动回退为纯文本推送
- 插件主动查询与自动通知分离：插件查询只要存在可用全量 mysekai 包即可渲染，不要求钻石命中

## 插件查询 API

- 可选鉴权头：`X-API-Key`（仅当 `PLUGIN_API_KEY` 非空时启用）
- 查询参数：
  - `mysekai_user_id`（必填）
  - `requester_qq`（可选）
  - `site_id`（可选，取值 `5,6,7,8`，分别对应 `初始空地/心愿沙滩/烂漫花田/忘却之所`）
- 成功响应格式：
  - `{ "ok": true, "message": "ok", "data": { "text": "...", "images": ["http://..."], "source_json": "..." } }`
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

## 图标命名规则
- `mysekai_material` 与 `mysekai_item` 支持按 `iconAssetbundleName` 直接覆盖图标，例如 `item_plant_4.png`。
- `mysekai_fixture` 支持简化命名，直接读取 `mysekai_fixture_<id>.png` 或 `fixture_<id>.png`。

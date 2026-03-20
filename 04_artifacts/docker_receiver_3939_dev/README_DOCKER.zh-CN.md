# Mysekai/Suite Receiver Docker 指南（端口 3939）
[English](./README_DOCKER.md) | [Project README](../../README.md) | [项目中文总览](../../README.zh-CN.md)

运行脚本位于 `dockerScripts/`，构建镜像时会复制到容器内 `/app/dockerScripts`。

## 构建镜像

```bash
docker build -t pjsk-receiver:3939 .
```

## 启动容器

注意：
- 当 `BOT_PUSH_URL` 为 `http://napcat:3000` 时，Receiver 与 NapCat 必须在同一个自定义 Docker 网络中。
- 如果没有该网络，可先创建：`docker network create <YOUR_DOCKER_NETWORK>`。
- 文档里的 ID/Token 均为占位，实际部署请填写你自己的参数。

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
  -e BOT_PUSH_RETRY=3 \
  -e BOT_MESSAGE_MODE=text+image \
  -e MYSEKAI_MAP_IMAGE_SIZE=1024 \
  -e MYSEKAI_ICON_SIZE=36 \
  -e MYSEKAI_COUNT_FONT_SIZE=18 \
  -e MYSEKAI_ICON_SPREAD=22 \
  -e ALERT_WINDOW_CACHE_HOURS=72 \
  -e ALERT_HIT_RETENTION=100 \
  -e ALERT_EVENT_RETENTION_LINES=5000 \
  -e TZ=Asia/Shanghai \
  -v /opt/pjsk-captures:/data \
  -v /opt/pjsk-config:/data/config \
  pjsk-receiver:3939
```

可选配置文件：
- 将 `mysekai_resource_map.json` 放在 `/opt/pjsk-config/mysekai_resource_map.json`
- 该文件可提升资源 ID 与图标映射的一致性
- 建议设置 `TZ=Asia/Shanghai`；去重窗口（`05:00` / `17:00`）使用容器本地时间

启动后快速检查：

```bash
docker logs -n 80 pjsk-receiver
docker exec -it pjsk-receiver python -m pip show sssekai
docker exec -it pjsk-receiver python -m sssekai -h
curl -sS http://127.0.0.1:3939/healthz
```

## 容器内数据路径

- 原始 bin：`/data/raw_api/suite` 或 `/data/raw_api/mysekai`
- 解密 json：`/data/decoded_api/suite` 或 `/data/decoded_api/mysekai`
- Mysekai 渲染图：`/data/decoded_api/mysekai/maps`
- 服务日志（滚动）：`/data/logs/receiver.log`
- 钻石告警触发条件：解密后的全量 mysekai 包中出现 `mysekai_material:12`
- 渲染触发条件：仅当 id=12 命中且通过当前窗口去重
- 渲染输出：按命中地图输出多张；只生成/发送命中地图
- 渲染参数：
  - `MYSEKAI_MAP_IMAGE_SIZE`：最终图片尺寸
  - `MYSEKAI_ICON_SIZE`：图标尺寸
  - `MYSEKAI_COUNT_FONT_SIZE`：数量字体大小
  - `MYSEKAI_ICON_SPREAD`：同点多资源扩散半径
  - 站点级微调：
    - `SITE<id>_OFFSET_X_DELTA`, `SITE<id>_OFFSET_Z_DELTA`
    - `SITE<id>_SCALE_X_DELTA`, `SITE<id>_SCALE_Z_DELTA`
  - 当前默认校准：site6（beach）图层整体上移约 12.5%
- 钻石命中归档：`/data/alerts/hits/`
- 告警事件日志：`/data/alerts/diamond_events.jsonl`
- 健康检查接口：`GET /healthz`
- `BOT_TOKEN` 是 NapCat HTTP Server Token（Bearer Token）

## NapCat API 基线（v4.17.48）

推送使用以下 action 接口：
- `POST {BOT_PUSH_URL}/send_private_msg`
- `POST {BOT_PUSH_URL}/send_group_msg`

消息体说明：
- `message` 可为字符串，也可为消息段数组
- 图片消息段：
  - `{"type":"image","data":{"file":"<path|url|base64>"}}`

## 宿主机路径映射示例

如果使用 `-v /opt/pjsk-captures:/data`，则服务器上可在以下路径查看文件：

- `/opt/pjsk-captures/raw_api/...`
- `/opt/pjsk-captures/decoded_api/...`
- `/opt/pjsk-captures/decoded_api/mysekai/maps/...`
- `/opt/pjsk-captures/logs/receiver.log`

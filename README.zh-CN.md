# project-sekai
[English](./README.md) | [Docker English](./04_artifacts/docker_receiver_3939_dev/README_DOCKER.md) | [Docker 中文](./04_artifacts/docker_receiver_3939_dev/README_DOCKER.zh-CN.md)

## 项目概览

本仓库提供本地版与 Docker 版接收器，用于：
- 捕获 `suite` / `mysekai` API 响应
- 解密 payload
- 生成 suite 卡片图
- 可选通过 NapCat 推送 Mysekai 钻石（`id=12`）通知

## 本地脚本（Windows）

- 脚本路径：`01_scripts/import http.py`
- 默认端口：`8000`
- Shadowrocket `script-path` 示例：
  - `http://<your-local-ip>:8000/upload.js`

## 本地自动化

- 定时自动提交脚本：`auto_commit.ps1`（由 `auto_commit.bat` 调用）
- 自动提交路径已包含 `tests/`，新建单元测试可被任务提交

## Docker 接收器（Dev）

- 目录：`04_artifacts/docker_receiver_3939_dev`
- 运行脚本：`04_artifacts/docker_receiver_3939_dev/dockerScripts`
- 默认端口：`3939`
- 健康检查：`GET /healthz`

构建：

```bash
docker build -t pjsk-receiver:dev3939 .
```

启动（示例）：

```bash
# 前置条件：
# 1) Receiver 与 NapCat 需在同一个自定义 Docker 网络
# 2) 文档中的 ID/Token 仅作占位，请在你自己的环境填写真实值
# 如需创建网络：
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
  pjsk-receiver:dev3939
```

可选配置：
- 将 `mysekai_resource_map.json` 放到 `/opt/pjsk-config/mysekai_resource_map.json`
- 用于提升 Mysekai 资源 ID / 名称 / 图标映射准确性

数据输出路径：
- 原始包：`/data/raw_api/...`
- 解密 JSON：`/data/decoded_api/...`
- Mysekai 渲染图：`/data/decoded_api/mysekai/maps/...`
- 日志：`/data/logs/receiver.log`
- 通知命中归档：`/data/notifications/hits/`
- 通知事件：`/data/notifications/diamond_notifications.jsonl`

启动后快速检查：

```bash
docker logs -n 80 pjsk-receiver-dev
docker exec -it pjsk-receiver-dev python -m pip show sssekai
docker exec -it pjsk-receiver-dev python -m sssekai -h
curl -sS http://127.0.0.1:3939/healthz
```

## 虚拟钻石通知测试

无需进游戏即可触发测试通知（在服务器内执行）：

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

说明：
- `BOT_TOKEN` 是 NapCat HTTP Server Token（`Authorization: Bearer <token>`）
- 如果 `BOT_PUSH_URL` 使用容器名（如 `http://napcat:3000`），需确保容器在同一网络
- 建议设置 `TZ=Asia/Shanghai`，去重窗口（`05:00` / `17:00`）基于容器本地时区

## 单元测试

在仓库根目录执行：

```bash
python -m unittest discover -s tests -p "test_*.py" -v
```

当前测试覆盖：
- API 类型识别（`extract_api_type`）
- 钻石命中提取（`find_diamond_hits`）
- 窗口边界判断（`get_refresh_window_id`）
- 当前窗口去重点位逻辑（`filter_hits_for_current_window`）

## NapCat API 基线（v4.17.48）

文本/图片推送使用：

- 接口：
  - `POST {BOT_PUSH_URL}/send_private_msg`
  - `POST {BOT_PUSH_URL}/send_group_msg`
- `message` 支持字符串或消息段数组
- 图片消息段格式：
  - `{"type":"image","data":{"file":"<path|url|base64>"}}`

文本+图片示例：

```json
[
  {"type":"text","data":{"text":"diamond hit"}},
  {"type":"image","data":{"file":"https://example.com/map.png"}}
]
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
  - `mysekai` 接口，尤其全量包：
    - `/api/user/<uid>/mysekai?isForceAllReloadOnlyMysekai=True|False`
- `[Mitm]` 的 `hostname` 需包含相关域名
- iOS 需安装并信任 MITM 证书，并在模块启用 MITM

### 5) 触发并验证抓包

- 进入游戏触发目标接口：
  - 登录流程（suite 数据）
  - 进入 Mysekai（mysekai 数据）
- 查看 Receiver 日志：
  - `Saved [SUITE]` / `Saved [MYSEKAI]`
  - `Decoded JSON: ...`
- 查看落盘文件：
  - `/opt/pjsk-captures/raw_api/...`
  - `/opt/pjsk-captures/decoded_api/...`

### 6) 验证推送链路

- 使用“虚拟钻石通知测试”发送 `id=12` 模拟包
- 预期：
  - 生成 `/data/notifications/hits/*.json`
  - `/data/notifications/diamond_notifications.jsonl` 追加一条
  - NapCat 向配置的私聊/群目标发送消息

### 7) 当前运行行为

- 通知来源：解密后的 **全量** Mysekai 包中包含 `mysekai_material:12`
- 地图渲染触发：满足通知条件（id=12 + 当前窗口去重通过）才渲染
- 渲染输出：按命中地图逐张输出；只渲染/发送命中地图；不做多地图拼图
- 去重逻辑（当前实现）：窗口去重
  - 刷新窗口：本地 `05:00` 与 `17:00`
  - 同窗口同点位不会重复推送
  - 缓存落盘：`/data/notifications/notification_dedup_cache.json`
- 推送行为：
  - 默认 `BOT_MESSAGE_MODE=text+image`
  - 图片推送失败自动回退文本推送
- 渲染可见性调参：
  - `MYSEKAI_MAP_IMAGE_SIZE`：输出尺寸
  - `MYSEKAI_ICON_SIZE`：图标尺寸
  - `MYSEKAI_COUNT_FONT_SIZE`：数量字号
  - `MYSEKAI_ICON_SPREAD`：同点多资源扩散半径
  - 站点级调参变量：
    - `SITE<id>_OFFSET_X_DELTA`, `SITE<id>_OFFSET_Z_DELTA`
    - `SITE<id>_SCALE_X_DELTA`, `SITE<id>_SCALE_Z_DELTA`
  - 当前默认校准：site6（beach）图层整体上移约 12.5%
- 保留策略：
  - raw/decoded/cards 保留最新 `RETENTION_COUNT`
  - 通知命中 JSON 保留 `NOTIFICATION_HIT_RETENTION`
  - 事件 jsonl 保留最新 `NOTIFICATION_EVENT_RETENTION_LINES` 行

### 8) 常见问题

- 只有 `GET /upload.js`，没有 `POST /upload`：
  - `pattern` 未命中，或脚本未挂到响应
- 进入 Mysekai 卡死：
  - 重写/重定向规则过激，建议仅保留脚本捕获
- 推送报 `Connection refused`：
  - Receiver 无法连到 NapCat 所在地址/端口
- 推送报 `401/403`：
  - Token 不匹配，请核对 `BOT_TOKEN` 与 NapCat Token

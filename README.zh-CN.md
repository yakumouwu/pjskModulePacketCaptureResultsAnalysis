# project-sekai
[English](./README.md) | [Docker English](./04_artifacts/docker_receiver_3939_dev/README_DOCKER.md) | [Docker 中文](./04_artifacts/docker_receiver_3939_dev/README_DOCKER.zh-CN.md)

## 项目概览

本仓库提供本地版与 Docker 版接收器，用于：
- 抓取 API 响应
- 解密 payload
- 生成用户信息卡图片
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

启动示例：

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
  pjsk-receiver:latest
```

可选：
- 将 `mysekai_resource_map.json` 放到配置目录，以提升图标映射准确性。

数据输出：
- 原始包：`/data/raw_api/...`
- 解密 JSON：`/data/decoded_api/...`
- Mysekai 地图：`/data/decoded_api/mysekai/maps/...`
- 日志：`/data/logs/receiver.log`
- 命中归档：`/data/notifications/hits/`
- 事件日志：`/data/notifications/diamond_notifications.jsonl`
- 自动通知去重与渲染规则：每用户每时间窗口仅首次钻石命中触发（`05:00-17:00`、`17:00-次日05:00`）
- 插件查询渲染规则：只要存在可用全量 mysekai 包，即可渲染（不要求钻石命中）

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

## 单元测试

在仓库根目录运行：

```bash
python -m unittest discover -s tests -p "test_*.py" -v
```

## 本地自动提交任务

- 脚本：
  - `auto_commit.bat`
  - `auto_commit.ps1`
- 日志：
  - `logs/auto_commit.log`
  - `logs/auto_commit_runner.log`
- 网络抖动时脚本会自动重试 `git pull --rebase` 和 `git push`。

当前覆盖范围：
- API 路由识别（`extract_api_type`）
- 钻石命中提取（`find_diamond_hits`，含混合数据场景）
- 窗口与去重缓存逻辑（`get_refresh_window_id`、`filter_hits_for_current_window`、`cleanup_window_dedup_cache`）
- 通知推送逻辑（`send_bot_message`、`push_text_with_optional_image`，含重试/回退/模式分支）
- 通知流程轻集成（`process_mysekai_notification` 的跳过与命中分支）
- HTTP 接口（`GET /healthz`、`GET /upload.js`、`GET /api/plugin/mysekai/map`、`GET /api/plugin/mysekai/file`、`GET /`）

## LangBot 占位插件（上传自测）

- 源码目录：`04_artifacts/langbot_plugin_placeholder/MysekaiQueryPlaceholder`
- 上传包：`04_artifacts/langbot_plugin_placeholder/dist/MysekaiQueryPlaceholder-0.3.0.lbpkg`
- 支持命令：
  - `mysk ping`
  - `mysk bind <mysekai_user_id>`
  - `mysk unbind`
  - `mysk whoami`
  - `mysk map`
  - `mysk map site <id>`
- 非法 `mysk map` 参数会直接提示用法（不会静默回退到全图查询）
- 后端相关配置：
  - `backend_base_url`
  - `backend_map_api_path`
  - `backend_api_key`

当前已验证行为：
- `mysk bind <mysekai_user_id>`：按 QQ 号保存绑定（`QQ user_id -> mysekai_user_id`）
- `mysk map`：查询已绑定用户的最新可用全量 mysekai 包并渲染
- `mysk map site <id>`：按站点单图返回（`id` 取值 `5,6,7,8`）
- 未绑定查询返回：`not bound, use: mysk bind <mysekai_user_id>`
- 无数据查询返回：`map query failed: no full mysekai packet found for user`

## 端到端检查清单（Capture -> Decode -> NapCat Push）

### 1) 服务器 / 网络

- 放行安全组/防火墙 TCP `3939`
- 准备持久化目录（例如 `/opt/pjsk-captures`）
- 确保 Receiver 与 NapCat 在同一 Docker 网络

### 2) 部署 Receiver

- 从 `04_artifacts/docker_receiver_3939_dev` 构建镜像
- 运行时代码从 `dockerScripts/` 复制到 `/app/dockerScripts`
- 启动时至少包含：
  - `-p 3939:3939`
  - `-v /opt/pjsk-captures:/data`
  - `-e PUBLIC_HOST=<YOUR_SERVER_PUBLIC_IP_OR_DOMAIN>`
  - 如启用通知，配置 `BOT_PUSH_*` 与 `BOT_TOKEN`

### 3) 配置 NapCat HTTP API

- 在 NapCat WebUI 启用 HTTP Server（常见为 `0.0.0.0:3000`）
- 将 HTTP Token 通过 `BOT_TOKEN` 注入 Receiver
- 在 Receiver 容器内验证：
  - `http://napcat:3000` 可访问
  - `401/403` 通常表示联通正常但 Token 缺失或错误

### 4) 配置 Shadowrocket 模块

- `script-path`：
  - `http://<PUBLIC_HOST>:3939/upload.js`
- `pattern` 需覆盖目标接口：
  - `suite`
  - `mysekai`：
    - `/api/user/<uid>/mysekai?isForceAllReloadOnlyMysekai=True|False`

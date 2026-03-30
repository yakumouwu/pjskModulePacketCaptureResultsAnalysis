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
  -v /opt/docker_receiver_3939_dev/dockerScripts:/app/dockerScripts \
  pjsk-receiver:latest
```

补充说明：
- 推荐把宿主机 `dockerScripts/` 挂载到容器 `/app/dockerScripts`，这样纯脚本更新通常只需要删旧容器并重建容器，无需重建镜像

数据输出：
- 原始包：`/data/raw_api/...`
- 解密 JSON：`/data/decoded_api/...`
- Mysekai 地图：`/data/decoded_api/mysekai/maps/...`
- 日志：`/data/logs/receiver.log`
- 命中归档：`/data/notifications/hits/`
- 事件日志：`/data/notifications/diamond_notifications.jsonl`
- 自动通知去重与渲染规则：每用户每时间窗口仅首次钻石命中触发（`05:00-17:00`、`17:00-次日05:00`）
- 插件查询渲染规则：只要存在可用全量 mysekai 包，即可渲染（不要求钻石命中）
- 渲染投影规则：固定零点模式（地图中心 = 世界坐标 `(0,0)`），跨包一致性依赖固定世界尺度参数
- 单图渲染默认保持底图原始比例（`16:9`），`MYSEKAI_MAP_IMAGE_SIZE` 表示输出目标宽度
- 同点位普通材料忽略（默认开启）：`MYSEKAI_IGNORE_BASE_MATERIALS=1`

## 关键运行参数

推送与通知：
- `BOT_PUSH_MODE`：当前代码回退值为 `group`，项目部署默认按群推送使用；如需私聊推送可显式设为 `private`
- `BOT_MESSAGE_MODE`：支持 `text`、`image`、`text+image`；当前默认策略是 `text+image`，图片发送失败时会回退到纯文本
- `BOT_PUSH_RETRY`：NapCat 推送重试次数
- `NOTIFICATION_WINDOW_CACHE_HOURS`：窗口去重缓存保留时长
- `NOTIFICATION_HIT_RETENTION`：命中归档 json 保留数量
- `NOTIFICATION_EVENT_RETENTION_LINES`：`diamond_notifications.jsonl` 最大保留行数
- 自动通知触发规则：只在检测到钻石命中（`mysekai_material`, `id=12`）时触发；同一用户在 `05:00-17:00` 或 `17:00-次日05:00` 窗口内仅首次命中会生成并推送图片，后续命中直接跳过

插件查询：
- `PLUGIN_API_KEY`：可选鉴权密钥，通过请求头 `X-API-Key` 校验
- `PLUGIN_QUERY_IMAGE_RETENTION`：插件查询渲染图保留数量
- 查询文本规则：
  - 不带 `site_id` 的全量查询：返回空文本
  - 带 `site_id` 的单图查询：仅返回中文地图名
- 成功响应除 `text` 与 `images` 外，还会带 `source_json`，用于定位本次渲染实际使用的源数据文件

渲染尺寸：
- `MYSEKAI_MAP_IMAGE_SIZE`：单图渲染输出目标宽度
- `MYSEKAI_ICON_SIZE`：图标尺寸
- `MYSEKAI_COUNT_FONT_SIZE`：数量文字尺寸
- `MYSEKAI_ICON_SPREAD`：同点多资源图标扩散半径
- `MYSEKAI_IGNORE_BASE_MATERIALS=1`：同点位存在高阶材料时隐藏普通材料
- 图标覆盖补充：
  - `material` 使用独立图标组，不再按 `mysekai_material` 解释
  - 未映射的 `mysekai_music_record`、未映射的 `material`、未映射的 `mysekai_fixture` 会直接跳过，不再画占位点
  - 额外图标可放到 `04_artifacts/docker_receiver_3939_dev/dockerScripts/mysekai_assets/icon/`
  - 直接识别的文件名：`material_<id>.png`、`mysekai_fixture_<id>.png`、`fixture_<id>.png`

站点级校准参数：
- `SITE<id>_WORLD_HALF_X` / `SITE<id>_WORLD_HALF_Z`：站点固定世界半宽/半高，用于把世界坐标稳定投影到底图，减少跨包漂移
- `SITE<id>_SCALE_X_DELTA` / `SITE<id>_SCALE_Z_DELTA`：站点级横向/纵向缩放微调
- `SITE<id>_OFFSET_X_DELTA` / `SITE<id>_OFFSET_Z_DELTA`：站点级横向/纵向偏移微调
- 当前站点范围：`5,6,7,8`

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

## LangBot 插件

- 源码目录：`04_artifacts/langbot_plugin_placeholder/MysekaiQueryPlaceholder`
- 上传包：`04_artifacts/langbot_plugin_placeholder/dist/MysekaiQueryPlaceholder-0.3.0.lbpkg`
- 支持命令：
  - `mysk ping`
  - `mysk bind <mysekai_user_id>`
  - `mysk unbind`
  - `mysk whoami`
  - `mysk map`
  - `mysk map site <id>`
- 非法 `mysk map` 参数会直接提示用法
- 后端相关配置：
  - `backend_base_url`
  - `backend_map_api_path`
  - `backend_api_key`

## 端到端检查清单（Capture -> Decode -> NapCat Push）

### 1) 服务器 / 网络

- 放行安全组/防火墙 TCP `3939`
- 准备持久化目录（例如 `/opt/pjsk-captures`）
- 确保 Receiver 与 NapCat 在同一 Docker 网络

### 2) 部署 Receiver

- 从 `04_artifacts/docker_receiver_3939_dev` 构建镜像
- 运行时代码从 `dockerScripts/` 复制到 `/app/dockerScripts`
- 如果宿主机 `dockerScripts/` 已挂载到 `/app/dockerScripts`，纯脚本更新通常只需要重建容器，无需重建镜像
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

import http.server
import base64
import json
import logging
import os
import re
import shutil
import socketserver
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from itertools import count
from logging.handlers import RotatingFileHandler
from pathlib import Path

logger = logging.getLogger(__name__)

PORT = int(os.environ.get("RECEIVER_PORT", "3939"))
PUBLIC_HOST = os.environ.get("PUBLIC_HOST", "127.0.0.1")
REGION = os.environ.get("API_REGION", "cn")
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUTPUT_ROOT = os.environ.get("OUTPUT_ROOT", os.path.join(ROOT_DIR, "02_captures"))
RAW_BASE_DIR = os.path.join(OUTPUT_ROOT, "raw_api")
DECODED_BASE_DIR = os.path.join(OUTPUT_ROOT, "decoded_api")
LOG_DIR = os.path.join(OUTPUT_ROOT, "logs")
RETENTION_COUNT = int(os.environ.get("RETENTION_COUNT", "25"))

BOT_PUSH_ENABLED = os.environ.get("BOT_PUSH_ENABLED", "1") == "1"
BOT_PUSH_URL = os.environ.get(
    "BOT_PUSH_URL",
    os.environ.get("BOT_PUSH_BASE_URL", "http://napcat:3000"),
).rstrip("/")
BOT_PUSH_MODE = os.environ.get("BOT_PUSH_MODE", "group").strip().lower()
BOT_TARGET_ID = os.environ.get("BOT_TARGET_ID", "0").strip()
NOTIFICATION_USER_LABEL = os.environ.get("NOTIFICATION_USER_LABEL", "player").strip()
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
BOT_PUSH_RETRY = int(os.environ.get("BOT_PUSH_RETRY", "3"))
BOT_MESSAGE_MODE = os.environ.get("BOT_MESSAGE_MODE", "text+image").strip().lower()
MYSEKAI_MAP_IMAGE_SIZE = int(os.environ.get("MYSEKAI_MAP_IMAGE_SIZE", "1024"))
PLUGIN_API_KEY = os.environ.get("PLUGIN_API_KEY", "").strip()
PLUGIN_QUERY_IMAGE_RETENTION = int(
    os.environ.get("PLUGIN_QUERY_IMAGE_RETENTION", str(RETENTION_COUNT))
)

NOTIFICATION_HIT_RETENTION = int(os.environ.get("NOTIFICATION_HIT_RETENTION", "100"))
NOTIFICATION_EVENT_RETENTION_LINES = int(
    os.environ.get("NOTIFICATION_EVENT_RETENTION_LINES", "5000")
)
NOTIFICATION_WINDOW_CACHE_HOURS = int(
    os.environ.get("NOTIFICATION_WINDOW_CACHE_HOURS", "72")
)

REQUEST_COUNTER = count(1)
NOTIFICATION_DEDUP_CACHE = {}

SITE_LABELS = {
    5: "Map 1 (grassland)",
    6: "Map 2 (beach)",
    7: "Map 3 (flowergarden)",
    8: "Map 4 (memorialplace)",
}
SITE_LABELS_CN = {
    5: "初始空地",
    6: "心愿沙滩",
    7: "烂漫花田",
    8: "忘却之所",
}
ALL_SITE_IDS = tuple(sorted(SITE_LABELS.keys()))


def extract_api_type(url):
    if re.search(r"/mysekai(?:/|\?|$)", url):
        return "mysekai"
    if re.search(r"/suite/", url):
        return "suite"
    return "unknown"


def generate_filename(api_type, original_url):
    now = datetime.now()
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    millis = int(now.microsecond / 1000)
    seq = next(REQUEST_COUNTER)
    user_id = re.search(r"/user/(\d+)", original_url)
    user_str = f"_user{user_id.group(1)}" if user_id else ""
    return f"{api_type}{user_str}_{timestamp}_{millis:03d}_{os.getpid()}_{seq:05d}.bin"


def ensure_output_dirs(api_type):
    raw_dir = os.path.join(RAW_BASE_DIR, api_type)
    decoded_dir = os.path.join(DECODED_BASE_DIR, api_type)
    os.makedirs(raw_dir, exist_ok=True)
    os.makedirs(decoded_dir, exist_ok=True)
    return raw_dir, decoded_dir


def prune_old_files(directory, pattern, keep_count):
    paths = sorted(
        Path(directory).glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True
    )
    for old in paths[keep_count:]:
        try:
            old.unlink()
            logger.info("Pruned old file: %s", old)
        except Exception as e:
            logger.warning("Failed to prune %s: %s", old, e)


def setup_logging():
    os.makedirs(LOG_DIR, exist_ok=True)
    log_file = os.path.join(LOG_DIR, "receiver.log")
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers.clear()
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    fh = RotatingFileHandler(
        log_file, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    fh.setFormatter(fmt)

    root.addHandler(sh)
    root.addHandler(fh)


def ensure_notification_dirs():
    notification_dir = os.path.join(OUTPUT_ROOT, "notifications")
    hit_dir = os.path.join(notification_dir, "hits")
    os.makedirs(hit_dir, exist_ok=True)
    return notification_dir, hit_dir


def load_dedup_cache():
    notification_dir, _ = ensure_notification_dirs()
    cache_file = os.path.join(notification_dir, "notification_dedup_cache.json")
    if not os.path.exists(cache_file):
        return
    try:
        with open(cache_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            for k, v in data.items():
                NOTIFICATION_DEDUP_CACHE[str(k)] = float(v)
    except Exception as e:
        logger.warning("Load dedup cache failed: %s", e)


def save_dedup_cache():
    notification_dir, _ = ensure_notification_dirs()
    cache_file = os.path.join(notification_dir, "notification_dedup_cache.json")
    try:
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(NOTIFICATION_DEDUP_CACHE, f, ensure_ascii=False)
    except Exception as e:
        logger.warning("Save dedup cache failed: %s", e)


def cleanup_window_dedup_cache():
    now_ts = time.time()
    max_age_seconds = max(1, NOTIFICATION_WINDOW_CACHE_HOURS) * 3600
    expired = [
        k
        for k, ts in NOTIFICATION_DEDUP_CACHE.items()
        if now_ts - float(ts) > max_age_seconds
    ]
    for k in expired:
        NOTIFICATION_DEDUP_CACHE.pop(k, None)
    if expired:
        save_dedup_cache()


def append_notification_event(event):
    notification_dir, _ = ensure_notification_dirs()
    event_file = os.path.join(notification_dir, "diamond_notifications.jsonl")
    try:
        with open(event_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
        prune_event_file(event_file, NOTIFICATION_EVENT_RETENTION_LINES)
    except Exception as e:
        logger.warning("Notification event persist failed: %s", e)


def prune_event_file(event_file, keep_lines):
    if keep_lines <= 0 or not os.path.exists(event_file):
        return
    try:
        with open(event_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
        if len(lines) <= keep_lines:
            return
        with open(event_file, "w", encoding="utf-8") as f:
            f.writelines(lines[-keep_lines:])
    except Exception as e:
        logger.warning("Event file prune failed: %s", e)


def decrypt_bin(api_type, raw_path, decoded_dir):
    if api_type not in ("suite", "mysekai"):
        return None, "skipped"
    out_json = os.path.join(
        decoded_dir, os.path.splitext(os.path.basename(raw_path))[0] + ".json"
    )
    cmd = [
        sys.executable,
        "-m",
        "sssekai",
        "apidecrypt",
        raw_path,
        out_json,
        "--region",
        REGION,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode == 0 and os.path.exists(out_json):
        return out_json, "ok"
    return None, (proc.stderr or proc.stdout or "decrypt_failed").strip()


def render_suite_card(json_path, decoded_dir):
    renderer = os.path.join(os.path.dirname(__file__), "render_suite_card.py")
    if not os.path.exists(renderer):
        return None, "renderer_not_found"
    card_dir = os.path.join(decoded_dir, "cards")
    os.makedirs(card_dir, exist_ok=True)
    card_path = os.path.join(
        card_dir, os.path.splitext(os.path.basename(json_path))[0] + ".png"
    )
    cmd = [sys.executable, renderer, json_path, card_path]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode == 0 and os.path.exists(card_path):
        return card_path, "ok"
    return None, (proc.stderr or proc.stdout or "render_failed").strip()


def render_mysekai_site_maps(json_path, decoded_dir, site_ids):
    renderer = os.path.join(os.path.dirname(__file__), "render_mysekai_map.py")
    assets_dir = os.path.join(os.path.dirname(__file__), "mysekai_assets")
    if not os.path.exists(renderer):
        return {}, "renderer_not_found"
    if not os.path.isdir(assets_dir):
        return {}, "assets_not_found"

    map_dir = os.path.join(decoded_dir, "maps")
    os.makedirs(map_dir, exist_ok=True)
    base_name = os.path.splitext(os.path.basename(json_path))[0]
    rendered_paths = {}
    failed = []
    for sid in sorted(site_ids):
        map_path = os.path.join(map_dir, f"{base_name}_site{sid}.png")
        cmd = [
            sys.executable,
            renderer,
            json_path,
            map_path,
            assets_dir,
            "--site-id",
            str(sid),
            "--target-size",
            str(MYSEKAI_MAP_IMAGE_SIZE),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if proc.returncode == 0 and os.path.exists(map_path):
            rendered_paths[sid] = map_path
            continue
        failed.append(
            f"site={sid}:{(proc.stderr or proc.stdout or 'render_failed').strip()}"
        )

    if not rendered_paths:
        return {}, "; ".join(failed) if failed else "render_failed"
    return rendered_paths, "ok"


def is_mysekai_full_packet(json_data):
    return bool(json_data.get("updatedResources", {}).get("userMysekaiHarvestMaps"))


def find_diamond_hits(json_data):
    # return {site_id: {"qty": int, "points": [{"qty":int, "seq":?, "x":?, "z":?}, ...]}}
    hits = {}
    for hm in json_data.get("updatedResources", {}).get("userMysekaiHarvestMaps", []):
        site_id = hm.get("mysekaiSiteId")
        for drop in hm.get("userMysekaiSiteHarvestResourceDrops", []):
            if (
                drop.get("resourceType") == "mysekai_material"
                and int(drop.get("resourceId", -1)) == 12
            ):
                qty = int(drop.get("quantity", 0))
                entry = hits.setdefault(site_id, {"qty": 0, "points": []})
                entry["qty"] += qty
                point = {"qty": qty}
                if "seq" in drop:
                    point["seq"] = drop.get("seq")
                if "positionX" in drop and "positionZ" in drop:
                    point["x"] = drop.get("positionX")
                    point["z"] = drop.get("positionZ")
                entry["points"].append(point)
    return hits


def get_refresh_window_id(now_dt):
    # Refresh windows: 05:00 and 17:00 local time.
    if now_dt.hour < 5:
        prev = now_dt - timedelta(days=1)
        return f"{prev.strftime('%Y%m%d')}_1700"
    if now_dt.hour < 17:
        return f"{now_dt.strftime('%Y%m%d')}_0500"
    return f"{now_dt.strftime('%Y%m%d')}_1700"


def point_signature(point):
    seq = point.get("seq")
    x = point.get("x")
    z = point.get("z")
    if seq is not None and x is not None and z is not None:
        return f"seq:{seq}|x:{x}|z:{z}"
    if seq is not None:
        return f"seq:{seq}"
    if x is not None and z is not None:
        return f"x:{x}|z:{z}"
    return "site_only"


def filter_hits_for_current_window(user_id, hits):
    # Strict window gating: only the first diamond hit in each refresh window can pass.
    now_dt = datetime.now()
    window_id = get_refresh_window_id(now_dt)
    gate_key = f"{user_id}|{window_id}|first_hit_gate"
    if gate_key in NOTIFICATION_DEDUP_CACHE:
        return window_id, {}

    NOTIFICATION_DEDUP_CACHE[gate_key] = time.time()
    save_dedup_cache()
    return window_id, hits


def send_bot_message(message):
    if not BOT_PUSH_ENABLED:
        return False, "push_disabled"
    if not BOT_PUSH_URL:
        return False, "missing_bot_push_url"
    if not BOT_TARGET_ID or BOT_TARGET_ID == "0":
        return False, "missing_bot_target_id"

    if BOT_PUSH_MODE not in ("private", "group"):
        return False, f"invalid_push_mode:{BOT_PUSH_MODE}"

    if BOT_PUSH_MODE == "group":
        endpoint = f"{BOT_PUSH_URL}/send_group_msg"
        payload = {"group_id": int(BOT_TARGET_ID), "message": message}
    else:
        endpoint = f"{BOT_PUSH_URL}/send_private_msg"
        payload = {"user_id": int(BOT_TARGET_ID), "message": message}

    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(endpoint, data=data, method="POST")
    req.add_header("Content-Type", "application/json; charset=utf-8")
    if BOT_TOKEN:
        req.add_header("Authorization", f"Bearer {BOT_TOKEN}")

    last_err = ""
    for attempt in range(1, BOT_PUSH_RETRY + 1):
        try:
            with urllib.request.urlopen(req, timeout=8) as resp:
                body = resp.read().decode("utf-8", errors="replace")
            if attempt > 1:
                logger.info("Notification push succeeded at retry #%s", attempt)
            return True, body[:300]
        except Exception as e:
            last_err = str(e)
            logger.warning(
                "Notification push failed (attempt %s/%s): %s",
                attempt,
                BOT_PUSH_RETRY,
                e,
            )
            if attempt < BOT_PUSH_RETRY:
                time.sleep(1.0 * attempt)
    return False, last_err


def image_to_segment(image_path):
    try:
        with open(image_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("ascii")
        return {"type": "image", "data": {"file": "base64://" + b64}}
    except Exception as e:
        logger.warning("Image encode failed: %s", e)
        return None


def push_text_with_optional_image(text, image_path=None):
    mode = BOT_MESSAGE_MODE
    if mode not in ("text", "image", "text+image"):
        mode = "text+image"

    if mode == "text" or not image_path:
        return send_bot_message(text)

    image_segment = image_to_segment(image_path)
    if image_segment is None:
        return send_bot_message(text)

    if mode == "image":
        ok, detail = send_bot_message([image_segment])
        if ok:
            return ok, detail
        return send_bot_message(text)

    # text+image default
    payload = [{"type": "text", "data": {"text": text}}, image_segment]
    ok, detail = send_bot_message(payload)
    if ok:
        return ok, detail
    return send_bot_message(text)


def format_hit_text(hits):
    parts = []
    for sid, detail in sorted(hits.items()):
        label = SITE_LABELS.get(sid, f"Unknown map(siteId={sid})")
        qty = detail.get("qty", 0)
        points = detail.get("points", [])
        if points:
            point_text = []
            for p in points[:6]:
                if "x" in p and "z" in p:
                    point_text.append(f"(x={p['x']},z={p['z']})")
                elif "seq" in p:
                    point_text.append(f"(seq={p['seq']})")
            more = f"...(+{len(points)-6})" if len(points) > 6 else ""
            parts.append(f"{label} diamond x{qty} points {' '.join(point_text)}{more}")
        else:
            parts.append(f"{label} diamond x{qty} siteId={sid}")
    return " | ".join(parts)


def process_mysekai_notification(out_json, original_url):
    try:
        with open(out_json, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        logger.warning("Notification parse failed: %s", e)
        return

    if not is_mysekai_full_packet(data):
        logger.info("Notification skip: not full mysekai packet")
        return

    hits = find_diamond_hits(data)
    if not hits:
        logger.info("Notification skip: no diamond(id=12) found")
        return

    cleanup_window_dedup_cache()

    user_match = re.search(r"/user/(\d+)", original_url)
    user_id = user_match.group(1) if user_match else "unknown"
    window_id, hits = filter_hits_for_current_window(user_id, hits)
    if not hits:
        logger.info(
            "Notification dedup skip: same diamond points in window %s", window_id
        )
        return

    hit_text = format_hit_text(hits)
    dedup_key = f"{user_id}|{window_id}|{hit_text}"
    event = {
        "ts": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "window_id": window_id,
        "user_id": user_id,
        "hits": hits,
        "hit_text": hit_text,
        "source_file": os.path.basename(out_json),
        "source_url": original_url,
        "dedup_key": dedup_key,
    }
    append_notification_event(event)

    _, hit_dir = ensure_notification_dirs()
    hit_archive = os.path.join(hit_dir, os.path.basename(out_json))
    try:
        shutil.copy2(out_json, hit_archive)
        prune_old_files(hit_dir, "*.json", NOTIFICATION_HIT_RETENTION)
        logger.info("Notification hit archived: %s", hit_archive)
    except Exception as e:
        logger.warning("Notification hit archive failed: %s", e)

    map_paths, map_status = render_mysekai_site_maps(
        out_json, os.path.dirname(out_json), hits.keys()
    )
    if map_status == "ok":
        map_dir = os.path.join(os.path.dirname(out_json), "maps")
        prune_old_files(map_dir, "mysekai_*.png", RETENTION_COUNT)
    else:
        logger.warning("Mysekai site map render failed: %s", map_status)

    for sid, detail in sorted(hits.items()):
        label = SITE_LABELS.get(sid, f"Unknown map(siteId={sid})")
        qty = detail.get("qty", 0)
        message = f"[Mysekai diamond notification] user: {NOTIFICATION_USER_LABEL} {label} diamond x{qty}"
        image_path = map_paths.get(sid)
        ok, detail_msg = push_text_with_optional_image(message, image_path)
        if ok:
            logger.info(
                "Notification pushed: site=%s image=%s detail=%s",
                sid,
                bool(image_path),
                detail_msg,
            )
        else:
            logger.warning(
                "Notification push failed: site=%s image=%s detail=%s",
                sid,
                bool(image_path),
                detail_msg,
            )


def _json_response(handler, status_code, payload):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status_code)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _verify_plugin_api_key(handler):
    if not PLUGIN_API_KEY:
        return True
    req_key = (handler.headers.get("X-API-Key", "") or "").strip()
    return req_key == PLUGIN_API_KEY


def _find_latest_full_mysekai_json(mysekai_user_id):
    mysekai_dir = os.path.join(DECODED_BASE_DIR, "mysekai")
    pattern = f"mysekai_user{mysekai_user_id}_*.json"
    candidates = sorted(
        Path(mysekai_dir).glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True
    )
    for path in candidates:
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if is_mysekai_full_packet(data):
                return str(path)
        except Exception:
            continue
    return None


def _render_map_for_plugin_query(json_path, mysekai_user_id, site_ids):
    renderer = os.path.join(os.path.dirname(__file__), "render_mysekai_map.py")
    assets_dir = os.path.join(os.path.dirname(__file__), "mysekai_assets")
    if not os.path.exists(renderer):
        return [], "renderer_not_found"
    if not os.path.isdir(assets_dir):
        return [], "assets_not_found"

    map_dir = os.path.join(DECODED_BASE_DIR, "mysekai", "maps", "plugin_api")
    os.makedirs(map_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    image_paths = []

    for site_id in site_ids:
        out_name = f"mysekai_user{mysekai_user_id}_query_{ts}_site{site_id}.png"
        out_path = os.path.join(map_dir, out_name)
        cmd = [
            sys.executable,
            renderer,
            json_path,
            out_path,
            assets_dir,
            "--site-id",
            str(site_id),
            "--target-size",
            str(MYSEKAI_MAP_IMAGE_SIZE),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if proc.returncode == 0 and os.path.exists(out_path):
            image_paths.append(out_path)
        else:
            logger.warning(
                "Plugin map render failed site=%s err=%s",
                site_id,
                (proc.stderr or proc.stdout or "render_failed").strip(),
            )

    prune_old_files(
        map_dir, "mysekai_user*_query_*_site*.png", PLUGIN_QUERY_IMAGE_RETENTION
    )
    return image_paths, "ok" if image_paths else "render_failed"


def _build_public_image_url(file_name):
    host = (PUBLIC_HOST or "").strip() or "127.0.0.1"
    quoted = urllib.parse.quote(file_name)
    return f"http://{host}:{PORT}/api/plugin/mysekai/file?name={quoted}"


class RequestHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        if path == "/healthz":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"ok")
            return

        if path == "/upload.js":
            js_content = """
            const upload = () => {
                $httpClient.post({
                    url: "http://%s:%d/upload",
                    headers: {
                        "X-Original-Url": $request.url,
                        "X-Request-Path": $request.path
                    },
                    body: $response.body
                }, (error) => $done({}));
            };
            upload();
            """ % (
                PUBLIC_HOST,
                PORT,
            )

            js_content = js_content.strip()
            self.send_response(200)
            self.send_header("Content-Type", "application/javascript; charset=utf-8")
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
            self.send_header("Content-Length", str(len(js_content.encode("utf-8"))))
            self.end_headers()
            self.wfile.write(js_content.encode("utf-8"))
            return

        if path == "/api/plugin/mysekai/map":
            if not _verify_plugin_api_key(self):
                _json_response(self, 401, {"ok": False, "message": "invalid api key"})
                return

            mysekai_user_id = (query.get("mysekai_user_id", [""])[0] or "").strip()
            requester_qq = (query.get("requester_qq", [""])[0] or "").strip()
            site_id_raw = (query.get("site_id", [""])[0] or "").strip()

            if not re.fullmatch(r"\d{6,25}", mysekai_user_id):
                _json_response(
                    self,
                    400,
                    {"ok": False, "message": "invalid mysekai_user_id"},
                )
                return

            site_ids = list(ALL_SITE_IDS)
            if site_id_raw:
                if not site_id_raw.isdigit() or int(site_id_raw) not in SITE_LABELS:
                    _json_response(
                        self,
                        400,
                        {"ok": False, "message": "invalid site_id"},
                    )
                    return
                site_ids = [int(site_id_raw)]

            latest_json = _find_latest_full_mysekai_json(mysekai_user_id)
            if not latest_json:
                _json_response(
                    self,
                    404,
                    {
                        "ok": False,
                        "message": "no full mysekai packet found for user",
                    },
                )
                return

            image_paths, status = _render_map_for_plugin_query(
                latest_json, mysekai_user_id, site_ids
            )
            if status != "ok":
                _json_response(
                    self,
                    500,
                    {"ok": False, "message": f"render_failed: {status}"},
                )
                return

            image_urls = [
                _build_public_image_url(os.path.basename(p)) for p in image_paths
            ]
            # Query text policy:
            # - full-site query: no text
            # - single-site query: show localized site name only
            if len(site_ids) == 1:
                label = SITE_LABELS_CN.get(site_ids[0], f"站点{site_ids[0]}")
                text = f"地图：{label}"
            else:
                text = ""
            _json_response(
                self,
                200,
                {
                    "ok": True,
                    "message": "ok",
                    "data": {
                        "text": text,
                        "images": image_urls,
                        "source_json": os.path.basename(latest_json),
                    },
                },
            )
            return

        if path == "/api/plugin/mysekai/file":
            file_name = (query.get("name", [""])[0] or "").strip()
            if not file_name:
                self.send_response(400)
                self.end_headers()
                return
            safe_name = os.path.basename(file_name)
            map_dir = os.path.join(DECODED_BASE_DIR, "mysekai", "maps", "plugin_api")
            file_path = os.path.join(map_dir, safe_name)
            if not os.path.exists(file_path):
                self.send_response(404)
                self.end_headers()
                return
            with open(file_path, "rb") as f:
                body = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        original_url = self.headers.get("X-Original-Url", "")
        api_type = extract_api_type(original_url)
        filename = generate_filename(api_type, original_url)
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self.send_response(400)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"invalid content-length")
            return

        if content_length <= 0:
            self.send_response(400)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"empty request body")
            return

        received_data = self.rfile.read(content_length)
        raw_dir, decoded_dir = ensure_output_dirs(api_type)
        raw_path = os.path.join(raw_dir, filename)

        with open(raw_path, "wb") as f:
            f.write(received_data)

        prune_old_files(raw_dir, f"{api_type}_*.bin", RETENTION_COUNT)
        logger.info("Saved [%s]: %s", api_type.upper(), raw_path)
        logger.info(
            "Source URL: %s%s",
            original_url[:100],
            "..." if len(original_url) > 100 else "",
        )
        logger.info("File Size: %.2f KB", len(received_data) / 1024)

        out_json, dstatus = decrypt_bin(api_type, raw_path, decoded_dir)
        if dstatus == "ok":
            prune_old_files(decoded_dir, f"{api_type}_*.json", RETENTION_COUNT)
            logger.info("Decoded JSON: %s", out_json)
            if api_type == "suite":
                card_path, cstatus = render_suite_card(out_json, decoded_dir)
                if cstatus == "ok":
                    card_dir = os.path.join(decoded_dir, "cards")
                    prune_old_files(card_dir, "suite_*.png", RETENTION_COUNT)
                    logger.info("Card Image: %s", card_path)
                else:
                    logger.warning("Card render failed: %s", cstatus)
            elif api_type == "mysekai":
                process_mysekai_notification(out_json, original_url)
        elif dstatus == "skipped":
            logger.info("Decode skipped (api_type unsupported)")
        else:
            logger.warning("Decode failed: %s", dstatus)

        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()


if __name__ == "__main__":
    setup_logging()
    load_dedup_cache()
    logger.info("Universal Data Receiver running at http://0.0.0.0:%s", PORT)
    logger.info("Raw output root: %s", RAW_BASE_DIR)
    logger.info("Decoded output root: %s", DECODED_BASE_DIR)
    logger.info("Log output root: %s", LOG_DIR)
    logger.info("apidecrypt region: %s", REGION)
    logger.info("Retention count per type: %s", RETENTION_COUNT)
    logger.info("Notification hit retention: %s", NOTIFICATION_HIT_RETENTION)
    logger.info(
        "Notification event retention lines: %s", NOTIFICATION_EVENT_RETENTION_LINES
    )
    logger.info("Notification window cache hours: %s", NOTIFICATION_WINDOW_CACHE_HOURS)
    logger.info(
        "Bot push: enabled=%s mode=%s target=%s url=%s retry=%s",
        BOT_PUSH_ENABLED,
        BOT_PUSH_MODE,
        BOT_TARGET_ID,
        BOT_PUSH_URL or "(empty)",
        BOT_PUSH_RETRY,
    )
    logger.info("Bot message mode: %s", BOT_MESSAGE_MODE)
    logger.info("Mysekai map image size: %s", MYSEKAI_MAP_IMAGE_SIZE)
    logger.info(
        "Plugin map API: path=/api/plugin/mysekai/map api_key=%s image_retention=%s",
        "(set)" if PLUGIN_API_KEY else "(empty)",
        PLUGIN_QUERY_IMAGE_RETENTION,
    )
    logger.info(
        "File naming format: [api_type]_[user]_[timestamp]_[ms]_[pid]_[seq].bin"
    )
    try:
        with socketserver.TCPServer(("", PORT), RequestHandler) as httpd:
            httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("Server stopped by user")

import http.server
import json
import logging
import os
import re
import shutil
import socketserver
import subprocess
import sys
import time
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
BOT_PUSH_MODE = os.environ.get("BOT_PUSH_MODE", "private").strip().lower()
BOT_TARGET_ID = os.environ.get("BOT_TARGET_ID", "0").strip()
ALERT_USER_LABEL = os.environ.get("ALERT_USER_LABEL", "player").strip()
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
BOT_PUSH_RETRY = int(os.environ.get("BOT_PUSH_RETRY", "3"))

ALERT_HIT_RETENTION = int(os.environ.get("ALERT_HIT_RETENTION", "100"))
ALERT_EVENT_RETENTION_LINES = int(os.environ.get("ALERT_EVENT_RETENTION_LINES", "5000"))
ALERT_WINDOW_CACHE_HOURS = int(os.environ.get("ALERT_WINDOW_CACHE_HOURS", "72"))

REQUEST_COUNTER = count(1)
ALERT_DEDUP_CACHE = {}

SITE_LABELS = {
    5: "Map 1 (grassland)",
    6: "Map 2 (beach)",
    7: "Map 3 (flowergarden)",
    8: "Map 4 (memorialplace)",
}


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
    paths = sorted(Path(directory).glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
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
    fh = RotatingFileHandler(log_file, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8")
    fh.setFormatter(fmt)

    root.addHandler(sh)
    root.addHandler(fh)


def ensure_alert_dirs():
    alert_dir = os.path.join(OUTPUT_ROOT, "alerts")
    hit_dir = os.path.join(alert_dir, "hits")
    os.makedirs(hit_dir, exist_ok=True)
    return alert_dir, hit_dir


def load_dedup_cache():
    alert_dir, _ = ensure_alert_dirs()
    cache_file = os.path.join(alert_dir, "dedup_cache.json")
    if not os.path.exists(cache_file):
        return
    try:
        with open(cache_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            for k, v in data.items():
                ALERT_DEDUP_CACHE[str(k)] = float(v)
    except Exception as e:
        logger.warning("Load dedup cache failed: %s", e)


def save_dedup_cache():
    alert_dir, _ = ensure_alert_dirs()
    cache_file = os.path.join(alert_dir, "dedup_cache.json")
    try:
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(ALERT_DEDUP_CACHE, f, ensure_ascii=False)
    except Exception as e:
        logger.warning("Save dedup cache failed: %s", e)


def cleanup_window_dedup_cache():
    now_ts = time.time()
    max_age_seconds = max(1, ALERT_WINDOW_CACHE_HOURS) * 3600
    expired = [k for k, ts in ALERT_DEDUP_CACHE.items() if now_ts - float(ts) > max_age_seconds]
    for k in expired:
        ALERT_DEDUP_CACHE.pop(k, None)
    if expired:
        save_dedup_cache()


def append_alert_event(event):
    alert_dir, _ = ensure_alert_dirs()
    event_file = os.path.join(alert_dir, "diamond_events.jsonl")
    try:
        with open(event_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
        prune_event_file(event_file, ALERT_EVENT_RETENTION_LINES)
    except Exception as e:
        logger.warning("Alert event persist failed: %s", e)


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
    out_json = os.path.join(decoded_dir, os.path.splitext(os.path.basename(raw_path))[0] + ".json")
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
    card_path = os.path.join(card_dir, os.path.splitext(os.path.basename(json_path))[0] + ".png")
    cmd = [sys.executable, renderer, json_path, card_path]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode == 0 and os.path.exists(card_path):
        return card_path, "ok"
    return None, (proc.stderr or proc.stdout or "render_failed").strip()


def render_mysekai_map(json_path, decoded_dir):
    renderer = os.path.join(os.path.dirname(__file__), "render_mysekai_map.py")
    assets_dir = os.path.join(os.path.dirname(__file__), "mysekai_assets")
    if not os.path.exists(renderer):
        return None, "renderer_not_found"
    if not os.path.isdir(assets_dir):
        return None, "assets_not_found"

    map_dir = os.path.join(decoded_dir, "maps")
    os.makedirs(map_dir, exist_ok=True)
    map_path = os.path.join(map_dir, os.path.splitext(os.path.basename(json_path))[0] + ".png")
    cmd = [sys.executable, renderer, json_path, map_path, assets_dir]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode == 0 and os.path.exists(map_path):
        return map_path, "ok"
    return None, (proc.stderr or proc.stdout or "render_failed").strip()


def is_mysekai_full_packet(json_data):
    return bool(json_data.get("updatedResources", {}).get("userMysekaiHarvestMaps"))


def find_diamond_hits(json_data):
    # return {site_id: {"qty": int, "points": [{"qty":int, "seq":?, "x":?, "z":?}, ...]}}
    hits = {}
    for hm in json_data.get("updatedResources", {}).get("userMysekaiHarvestMaps", []):
        site_id = hm.get("mysekaiSiteId")
        for drop in hm.get("userMysekaiSiteHarvestResourceDrops", []):
            if drop.get("resourceType") == "mysekai_material" and int(drop.get("resourceId", -1)) == 12:
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
    # Keep only points not sent in current refresh window.
    now_dt = datetime.now()
    window_id = get_refresh_window_id(now_dt)
    filtered = {}
    changed = False

    for sid, detail in sorted(hits.items()):
        points = detail.get("points", [])
        if not points:
            key = f"{user_id}|{window_id}|site:{sid}|site_only"
            if key in ALERT_DEDUP_CACHE:
                continue
            ALERT_DEDUP_CACHE[key] = time.time()
            filtered[sid] = {"qty": detail.get("qty", 0), "points": []}
            changed = True
            continue

        new_points = []
        qty_sum = 0
        for p in points:
            sig = point_signature(p)
            key = f"{user_id}|{window_id}|site:{sid}|{sig}"
            if key in ALERT_DEDUP_CACHE:
                continue
            ALERT_DEDUP_CACHE[key] = time.time()
            new_points.append(p)
            qty_sum += int(p.get("qty", 0))
            changed = True

        if new_points:
            filtered[sid] = {"qty": qty_sum, "points": new_points}

    if changed:
        save_dedup_cache()
    return window_id, filtered


def send_bot_message(message):
    if not BOT_PUSH_ENABLED:
        return False, "push_disabled"
    if not BOT_PUSH_URL:
        return False, "missing_bot_push_url"
    if not BOT_TARGET_ID or BOT_TARGET_ID == "0":
        return False, "missing_bot_target_id"

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
                logger.info("Alert push succeeded at retry #%s", attempt)
            return True, body[:300]
        except Exception as e:
            last_err = str(e)
            logger.warning("Alert push failed (attempt %s/%s): %s", attempt, BOT_PUSH_RETRY, e)
            if attempt < BOT_PUSH_RETRY:
                time.sleep(1.0 * attempt)
    return False, last_err


def format_hit_text(hits):
    parts = []
    for sid, detail in sorted(hits.items()):
        label = SITE_LABELS.get(sid, f"Unknown map (siteId={sid})")
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
            parts.append(f"{label} diamond x{qty} points: {' '.join(point_text)}{more}")
        else:
            parts.append(f"{label} diamond x{qty} siteId={sid}")
    return " | ".join(parts)
def process_mysekai_alert(out_json, original_url):
    try:
        with open(out_json, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        logger.warning("Alert parse failed: %s", e)
        return

    if not is_mysekai_full_packet(data):
        logger.info("Alert skip: not full mysekai packet")
        return

    hits = find_diamond_hits(data)
    if not hits:
        logger.info("Alert skip: no diamond(id=12) found")
        return

    cleanup_window_dedup_cache()

    user_match = re.search(r"/user/(\d+)", original_url)
    user_id = user_match.group(1) if user_match else "unknown"
    window_id, hits = filter_hits_for_current_window(user_id, hits)
    if not hits:
        logger.info("Alert dedup skip: same diamond points in window %s", window_id)
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
    append_alert_event(event)

    _, hit_dir = ensure_alert_dirs()
    hit_archive = os.path.join(hit_dir, os.path.basename(out_json))
    try:
        shutil.copy2(out_json, hit_archive)
        prune_old_files(hit_dir, "*.json", ALERT_HIT_RETENTION)
        logger.info("Alert hit archived: %s", hit_archive)
    except Exception as e:
        logger.warning("Alert hit archive failed: %s", e)

    message = f"[Mysekai diamond alarm] user: {ALERT_USER_LABEL} {hit_text}"
    ok, detail = send_bot_message(message)
    if ok:
        logger.info("Alert pushed: %s", detail)
    else:
        logger.warning("Alert push failed: %s", detail)


class RequestHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/healthz":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"ok")
            return

        if self.path == "/upload.js":
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
            """ % (PUBLIC_HOST, PORT)

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

        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        original_url = self.headers.get("X-Original-Url", "")
        api_type = extract_api_type(original_url)
        filename = generate_filename(api_type, original_url)
        content_length = int(self.headers["Content-Length"])
        received_data = self.rfile.read(content_length)
        raw_dir, decoded_dir = ensure_output_dirs(api_type)
        raw_path = os.path.join(raw_dir, filename)

        with open(raw_path, "wb") as f:
            f.write(received_data)

        prune_old_files(raw_dir, f"{api_type}_*.bin", RETENTION_COUNT)
        logger.info("Saved [%s]: %s", api_type.upper(), raw_path)
        logger.info("Source URL: %s%s", original_url[:100], "..." if len(original_url) > 100 else "")
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
                map_path, mstatus = render_mysekai_map(out_json, decoded_dir)
                if mstatus == "ok":
                    map_dir = os.path.join(decoded_dir, "maps")
                    prune_old_files(map_dir, "mysekai_*.png", RETENTION_COUNT)
                    logger.info("Mysekai Map Image: %s", map_path)
                else:
                    logger.warning("Mysekai map render failed: %s", mstatus)
                process_mysekai_alert(out_json, original_url)
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
    logger.info("Local datetime.now(): %s", datetime.now().isoformat(timespec="seconds"))
    logger.info("Local timezone(TZ env): %s", os.environ.get("TZ", "(not set)"))
    logger.info("Universal Data Receiver running at http://0.0.0.0:%s", PORT)
    logger.info("Raw output root: %s", RAW_BASE_DIR)
    logger.info("Decoded output root: %s", DECODED_BASE_DIR)
    logger.info("Log output root: %s", LOG_DIR)
    logger.info("apidecrypt region: %s", REGION)
    logger.info("Retention count per type: %s", RETENTION_COUNT)
    logger.info("Alert hit retention: %s", ALERT_HIT_RETENTION)
    logger.info("Alert event retention lines: %s", ALERT_EVENT_RETENTION_LINES)
    logger.info("Alert window cache hours: %s", ALERT_WINDOW_CACHE_HOURS)
    logger.info(
        "Bot push: enabled=%s mode=%s target=%s url=%s retry=%s",
        BOT_PUSH_ENABLED,
        BOT_PUSH_MODE,
        BOT_TARGET_ID,
        BOT_PUSH_URL or "(empty)",
        BOT_PUSH_RETRY,
    )
    logger.info("File naming format: [api_type]_[user]_[timestamp]_[ms]_[pid]_[seq].bin")
    try:
        with socketserver.TCPServer(("", PORT), RequestHandler) as httpd:
            httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("Server stopped by user")




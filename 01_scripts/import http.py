import http.server
import socketserver
import os
import re
import subprocess
import sys
from datetime import datetime

PORT = 8000
LOCAL_IP = '127.0.0.1'
REGION = "cn"
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RAW_BASE_DIR = os.path.join(ROOT_DIR, "02_captures", "raw_api")
DECODED_BASE_DIR = os.path.join(ROOT_DIR, "02_captures", "decoded_api")

def extract_api_type(url):
    # Match /mysekai, /mysekai/, /mysekai/xxx and optional query string
    if re.search(r'/mysekai(?:/|\?|$)', url):
        return 'mysekai'
    if re.search(r'/suite/', url):
        return 'suite'
    return 'unknown'

def generate_filename(api_type, original_url):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    user_id = re.search(r'/user/(\d+)', original_url)
    user_str = f"_user{user_id.group(1)}" if user_id else ""
    return f"{api_type}{user_str}_{timestamp}_{os.getpid()}.bin"


def ensure_capture_dirs(api_type):
    raw_dir = os.path.join(RAW_BASE_DIR, api_type)
    decoded_dir = os.path.join(DECODED_BASE_DIR, api_type)
    os.makedirs(raw_dir, exist_ok=True)
    os.makedirs(decoded_dir, exist_ok=True)
    return raw_dir, decoded_dir


def auto_decrypt_if_supported(api_type, raw_path, decoded_dir):
    if api_type not in ("suite", "mysekai"):
        return None, "skipped"

    json_name = os.path.splitext(os.path.basename(raw_path))[0] + ".json"
    json_path = os.path.join(decoded_dir, json_name)

    # Prefer current interpreter to ensure conda consistency.
    cmd = [
        sys.executable,
        "-m",
        "sssekai",
        "apidecrypt",
        raw_path,
        json_path,
        "--region",
        REGION,
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except FileNotFoundError:
        return None, "python_or_sssekai_not_found"

    if proc.returncode == 0 and os.path.exists(json_path):
        return json_path, "ok"

    return None, (proc.stderr or proc.stdout or "decrypt_failed").strip()


def render_suite_card_if_possible(json_path, decoded_dir):
    if not json_path:
        return None, "no_json"

    card_dir = os.path.join(decoded_dir, "cards")
    card_name = os.path.splitext(os.path.basename(json_path))[0] + ".png"
    card_path = os.path.join(card_dir, card_name)
    renderer = os.path.join(os.path.dirname(__file__), "render_suite_card.py")
    if not os.path.exists(renderer):
        return None, "renderer_not_found"

    cmd = [sys.executable, renderer, json_path, card_path]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode == 0 and os.path.exists(card_path):
        return card_path, "ok"
    return None, (proc.stderr or proc.stdout or "render_failed").strip()

class RequestHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/upload.js':
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
            """ % (LOCAL_IP, PORT)

            js_content = js_content.strip()
            self.send_response(200)
            self.send_header('Content-Type', 'application/javascript; charset=utf-8')
            self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Expires', '0')
            self.send_header('Content-Length', str(len(js_content.encode('utf-8'))))
            self.end_headers()
            self.wfile.write(js_content.encode('utf-8'))
            return

        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        original_url = self.headers.get('X-Original-Url', '')
        api_type = extract_api_type(original_url)
        filename = generate_filename(api_type, original_url)
        content_length = int(self.headers['Content-Length'])
        received_data = self.rfile.read(content_length)
        raw_dir, decoded_dir = ensure_capture_dirs(api_type)
        raw_path = os.path.join(raw_dir, filename)

        with open(raw_path, 'wb') as f:
            f.write(received_data)

        print(f"Saved [{api_type.upper()}]: {raw_path}")
        print(f"Source URL: {original_url[:100]}{'...' if len(original_url) > 100 else ''}")
        print(f"File Size: {len(received_data)/1024:.2f} KB")

        json_path, status = auto_decrypt_if_supported(api_type, raw_path, decoded_dir)
        if status == "ok":
            print(f"Decoded JSON: {json_path}\n")
            if api_type == "suite":
                card_path, cstatus = render_suite_card_if_possible(json_path, decoded_dir)
                if cstatus == "ok":
                    print(f"Suite Card: {card_path}\n")
                else:
                    print(f"Card render failed: {cstatus}\n")
        elif status == "skipped":
            print("Decode: skipped (unsupported api_type)\n")
        elif status == "python_or_sssekai_not_found":
            print("Decode failed: Python/sssekai not found in current environment\n")
        else:
            print(f"Decode failed: {status}\n")

        self.send_response(200)
        self.send_header('Content-Type', 'text/plain; charset=utf-8')
        self.end_headers()

if __name__ == "__main__":
    print(f"Universal Data Receiver running at http://0.0.0.0:{PORT}")
    print(f"Raw output root: {RAW_BASE_DIR}")
    print(f"Decoded output root: {DECODED_BASE_DIR}")
    print(f"apidecrypt region: {REGION}")
    print("File naming format: [api_type]_[user]_[timestamp]_[pid].bin\n")
    try:
        with socketserver.TCPServer(("", PORT), RequestHandler) as httpd:
            httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped by user")

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional


class BackendClient:
    """HTTP client for map query backend."""

    def __init__(self, base_url: str, map_api_path: str, api_key: str, timeout_sec: int):
        self.base_url = (base_url or "").strip().rstrip("/")
        self.map_api_path = (map_api_path or "").strip()
        self.api_key = (api_key or "").strip()
        self.timeout_sec = max(timeout_sec, 1)

    def _build_url(self, site_id: Optional[str], mysekai_user_id: str, requester_qq: str) -> str:
        path = self.map_api_path
        if not path.startswith("/"):
            path = "/" + path
        params = {
            "mysekai_user_id": mysekai_user_id,
            "requester_qq": requester_qq,
        }
        if site_id:
            params["site_id"] = site_id
        qs = urllib.parse.urlencode(params)
        return f"{self.base_url}{path}?{qs}"

    def query_map(self, site_id: Optional[str], mysekai_user_id: str, requester_qq: str) -> Dict[str, Any]:
        if not self.base_url:
            return {"ok": False, "message": "backend_base_url is empty", "text": "", "images": []}

        url = self._build_url(site_id, mysekai_user_id, requester_qq)
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        req = urllib.request.Request(url=url, method="GET", headers=headers)

        try:
            with urllib.request.urlopen(req, timeout=self.timeout_sec) as resp:
                body = resp.read().decode("utf-8", errors="replace")
                payload = json.loads(body) if body else {}
                return self._normalize(payload)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            return {"ok": False, "message": f"http {e.code}: {body[:200]}", "text": "", "images": []}
        except Exception as e:
            return {"ok": False, "message": f"request error: {e}", "text": "", "images": []}

    @staticmethod
    def _normalize(payload: Dict[str, Any]) -> Dict[str, Any]:
        data = payload.get("data", {}) if isinstance(payload, dict) else {}
        ok = bool(payload.get("ok", False)) or payload.get("status") == "ok"
        message = str(payload.get("message", "") or "")

        text = ""
        if isinstance(data, dict):
            text = str(data.get("text", "") or payload.get("text", "") or "")
        if not text:
            text = str(payload.get("text", "") or "")

        images: List[str] = []
        candidates: List[Any] = []
        if isinstance(data, dict):
            candidates.extend(
                [
                    data.get("image_url"),
                    data.get("image"),
                    data.get("images"),
                    payload.get("image_url"),
                    payload.get("image"),
                    payload.get("images"),
                ]
            )
        for item in candidates:
            if isinstance(item, str) and item.startswith(("http://", "https://")):
                images.append(item)
            elif isinstance(item, list):
                for one in item:
                    if isinstance(one, str) and one.startswith(("http://", "https://")):
                        images.append(one)
                    elif isinstance(one, dict):
                        url = one.get("url")
                        if isinstance(url, str) and url.startswith(("http://", "https://")):
                            images.append(url)

        return {"ok": ok, "message": message, "text": text, "images": images}

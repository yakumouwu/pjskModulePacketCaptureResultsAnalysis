from __future__ import annotations

import json
import os
import threading
from typing import Dict, Optional


class BindStore:
    """File-backed one-to-one binding store: qq_user_id -> mysekai_user_id."""

    def __init__(self, file_path: str):
        self._file_path = file_path
        self._lock = threading.Lock()
        self._bindings: Dict[str, str] = {}
        self._load()

    def _load(self) -> None:
        if not os.path.exists(self._file_path):
            return
        try:
            with open(self._file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            bindings = data.get("bindings", {})
            if isinstance(bindings, dict):
                self._bindings = {str(k): str(v) for k, v in bindings.items()}
        except Exception:
            self._bindings = {}

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self._file_path), exist_ok=True)
        data = {"bindings": self._bindings}
        with open(self._file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def count(self) -> int:
        with self._lock:
            return len(self._bindings)

    def get(self, qq_user_id: str) -> Optional[str]:
        with self._lock:
            return self._bindings.get(str(qq_user_id))

    def bind(self, qq_user_id: str, mysekai_user_id: str, max_bindings: int) -> tuple[bool, str]:
        qq_user_id = str(qq_user_id)
        mysekai_user_id = str(mysekai_user_id)
        with self._lock:
            existed = qq_user_id in self._bindings
            if not existed and len(self._bindings) >= max_bindings:
                return False, f"binding limit reached ({max_bindings})"
            self._bindings[qq_user_id] = mysekai_user_id
            self._save()
            return True, "updated" if existed else "created"

    def unbind(self, qq_user_id: str) -> bool:
        qq_user_id = str(qq_user_id)
        with self._lock:
            if qq_user_id not in self._bindings:
                return False
            del self._bindings[qq_user_id]
            self._save()
            return True

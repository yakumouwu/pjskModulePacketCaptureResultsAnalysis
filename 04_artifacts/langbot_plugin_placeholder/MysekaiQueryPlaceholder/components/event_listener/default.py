from __future__ import annotations

import asyncio
import os
import re
import sys
import time
from typing import Optional

from langbot_plugin.api.definition.components.common.event_listener import EventListener
from langbot_plugin.api.entities import context, events
from langbot_plugin.api.entities.builtin.platform import message as platform_message


project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from core.backend_client import BackendClient
from core.bind_store import BindStore


_UID_PATTERN = re.compile(r"^\d{6,25}$")


class DefaultEventListener(EventListener):
    """Mysekai command handler."""

    async def initialize(self):
        await super().initialize()
        cfg = self.plugin.get_config()

        self.command_prefix = str(cfg.get("command_prefix", "mysk") or "mysk").strip().lower()
        self.rate_limit_sec = _to_int(cfg.get("query_rate_limit_sec", "60"), 60, 1, 3600)
        self.timeout_sec = _to_int(cfg.get("request_timeout_sec", "10"), 10, 1, 120)
        self.max_bindings = _to_int(cfg.get("max_bindings", "25"), 25, 1, 10000)

        backend_base_url = str(cfg.get("backend_base_url", "") or "").strip()
        backend_map_api_path = str(cfg.get("backend_map_api_path", "/api/plugin/mysekai/map") or "").strip()
        backend_api_key = str(cfg.get("backend_api_key", "") or "").strip()

        self.backend = BackendClient(
            base_url=backend_base_url,
            map_api_path=backend_map_api_path,
            api_key=backend_api_key,
            timeout_sec=self.timeout_sec,
        )

        data_dir = os.path.join(project_root, "data")
        self.store = BindStore(os.path.join(data_dir, "bindings.json"))
        self.last_query_ts: dict[str, float] = {}

        @self.handler(events.PersonMessageReceived)
        async def handle_private_message(event_context: context.EventContext):
            await self._handle_message(event_context)

        @self.handler(events.GroupMessageReceived)
        async def handle_group_message(event_context: context.EventContext):
            await self._handle_message(event_context)

    async def _handle_message(self, event_context: context.EventContext):
        plain = "".join(
            element.text
            for element in event_context.event.message_chain
            if isinstance(element, platform_message.Plain)
        ).strip()
        if not plain:
            return

        args = _parse_args(plain, self.command_prefix)
        if args is None:
            return

        sender_id = str(event_context.event.sender_id)
        cmd = args[0].lower() if args else "help"

        if cmd in {"help", "h"}:
            await self._reply_help(event_context)
            return

        if cmd in {"ping", "p"}:
            await self._reply_text(event_context, "mysk pong: plugin link is healthy")
            return

        if cmd == "bind":
            if len(args) < 2:
                await self._reply_text(event_context, "usage: mysk bind <mysekai_user_id>")
                return
            mysekai_user_id = args[1].strip()
            if not _UID_PATTERN.match(mysekai_user_id):
                await self._reply_text(event_context, "invalid mysekai_user_id: expected 6-25 digits")
                return
            ok, reason = self.store.bind(sender_id, mysekai_user_id, self.max_bindings)
            if not ok:
                await self._reply_text(event_context, f"bind failed: {reason}")
                return
            await self._reply_text(event_context, f"bind success ({reason}): {mysekai_user_id}")
            return

        if cmd == "unbind":
            removed = self.store.unbind(sender_id)
            if removed:
                await self._reply_text(event_context, "unbind success")
            else:
                await self._reply_text(event_context, "no binding found")
            return

        if cmd == "whoami":
            bound = self.store.get(sender_id)
            if not bound:
                await self._reply_text(event_context, "not bound, use: mysk bind <mysekai_user_id>")
            else:
                await self._reply_text(event_context, f"qq={sender_id}, mysekai_user_id={bound}")
            return

        if cmd == "map":
            bound = self.store.get(sender_id)
            if not bound:
                await self._reply_text(event_context, "not bound, use: mysk bind <mysekai_user_id>")
                return

            # Reject malformed map arguments explicitly instead of silently falling back to all sites.
            if len(args) > 1 and _extract_site_id(args[1:]) is None:
                await self._reply_text(
                    event_context,
                    f"invalid map args, use `{self.command_prefix} map` or `{self.command_prefix} map site <id>`",
                )
                return

            now = time.time()
            last_ts = self.last_query_ts.get(sender_id, 0.0)
            remain = int(self.rate_limit_sec - (now - last_ts))
            if remain > 0:
                await self._reply_text(event_context, f"rate limited, retry in {remain}s")
                return

            site_id = _extract_site_id(args[1:])
            self.last_query_ts[sender_id] = now
            result = await asyncio.to_thread(
                self.backend.query_map,
                site_id,
                bound,
                sender_id,
            )
            if not result.get("ok"):
                msg = result.get("message", "backend error")
                await self._reply_text(event_context, f"map query failed: {msg}")
                return

            text = (result.get("text") or "").strip() or "map query success"
            images = result.get("images", []) or []
            await self._reply_text_with_images(event_context, text, images)
            return

        await self._reply_text(
            event_context,
            f"unknown command: {cmd}. use `{self.command_prefix} help`",
        )

    async def _reply_help(self, event_context: context.EventContext):
        prefix = self.command_prefix
        lines = [
            f"{prefix} ping",
            f"{prefix} bind <mysekai_user_id>",
            f"{prefix} unbind",
            f"{prefix} whoami",
            f"{prefix} map",
            f"{prefix} map site <id>",
        ]
        await self._reply_text(event_context, "available commands:\n" + "\n".join(lines))

    async def _reply_text(self, event_context: context.EventContext, text: str):
        await event_context.reply(
            platform_message.MessageChain(
                [platform_message.Plain(text=text)],
            )
        )
        event_context.prevent_default()

    async def _reply_text_with_images(self, event_context: context.EventContext, text: str, images: list[str]):
        msg_chain = [platform_message.Plain(text=text)]
        for image_url in images:
            msg_chain.append(platform_message.Image(url=image_url))
        await event_context.reply(platform_message.MessageChain(msg_chain))
        event_context.prevent_default()


def _parse_args(message: str, command_prefix: str) -> Optional[list[str]]:
    text = " ".join(message.strip().split())
    if not text:
        return None

    low = text.lower()
    candidates = [command_prefix, f"!{command_prefix}", f"/{command_prefix}"]
    matched = None
    for c in candidates:
        if low == c:
            matched = c
            break
        if low.startswith(c + " "):
            matched = c
            break
    if matched is None:
        return None

    remainder = text[len(matched) :].strip()
    if not remainder:
        return ["help"]
    return remainder.split()


def _extract_site_id(args: list[str]) -> Optional[str]:
    if not args:
        return None
    if len(args) == 1 and args[0].isdigit():
        return args[0]
    if len(args) >= 2 and args[0].lower() == "site" and args[1].isdigit():
        return args[1]
    return None


def _to_int(raw, default: int, lower: int, upper: int) -> int:
    try:
        val = int(str(raw).strip())
        if val < lower:
            return lower
        if val > upper:
            return upper
        return val
    except Exception:
        return default

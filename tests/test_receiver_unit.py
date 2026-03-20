import importlib.util
import os
import json
import tempfile
import threading
import unittest
from http.client import HTTPConnection
from datetime import datetime
from unittest import mock


RECEIVER_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "04_artifacts",
    "docker_receiver_3939_dev",
    "dockerScripts",
    "import http.py",
)


def load_receiver_module():
    spec = importlib.util.spec_from_file_location("receiver_module", RECEIVER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ReceiverLogicTests(unittest.TestCase):
    def setUp(self):
        self.receiver = load_receiver_module()
        self.receiver.NOTIFICATION_DEDUP_CACHE.clear()

    def test_extract_api_type(self):
        self.assertEqual(
            self.receiver.extract_api_type(
                "https://x/api/user/1/mysekai?isForceAllReloadOnlyMysekai=True"
            ),
            "mysekai",
        )
        self.assertEqual(
            self.receiver.extract_api_type("https://x/api/suite/user/1"), "suite"
        )
        self.assertEqual(
            self.receiver.extract_api_type("https://x/api/other"), "unknown"
        )

    def test_find_diamond_hits_only_id_12(self):
        payload = {
            "updatedResources": {
                "userMysekaiHarvestMaps": [
                    {
                        "mysekaiSiteId": 6,
                        "userMysekaiSiteHarvestResourceDrops": [
                            {
                                "resourceType": "mysekai_material",
                                "resourceId": 12,
                                "quantity": 1,
                                "seq": 1,
                                "positionX": 2,
                                "positionZ": 3,
                            },
                            {
                                "resourceType": "mysekai_material",
                                "resourceId": 12,
                                "quantity": 2,
                                "seq": 2,
                                "positionX": 4,
                                "positionZ": 5,
                            },
                            {
                                "resourceType": "mysekai_material",
                                "resourceId": 11,
                                "quantity": 9,
                                "seq": 3,
                                "positionX": 7,
                                "positionZ": 8,
                            },
                            {
                                "resourceType": "mysekai_item",
                                "resourceId": 7,
                                "quantity": 1,
                                "seq": 4,
                                "positionX": 9,
                                "positionZ": 10,
                            },
                        ],
                    }
                ]
            }
        }

        hits = self.receiver.find_diamond_hits(payload)
        self.assertIn(6, hits)
        self.assertEqual(hits[6]["qty"], 3)
        self.assertEqual(len(hits[6]["points"]), 2)
        self.assertEqual(hits[6]["points"][0]["seq"], 1)
        self.assertEqual(hits[6]["points"][1]["x"], 4)
        self.assertEqual(hits[6]["points"][1]["z"], 5)

    def test_get_refresh_window_id_boundaries(self):
        self.assertEqual(
            self.receiver.get_refresh_window_id(datetime(2026, 3, 19, 4, 59, 0)),
            "20260318_1700",
        )
        self.assertEqual(
            self.receiver.get_refresh_window_id(datetime(2026, 3, 19, 5, 0, 0)),
            "20260319_0500",
        )
        self.assertEqual(
            self.receiver.get_refresh_window_id(datetime(2026, 3, 19, 16, 59, 0)),
            "20260319_0500",
        )
        self.assertEqual(
            self.receiver.get_refresh_window_id(datetime(2026, 3, 19, 17, 0, 0)),
            "20260319_1700",
        )

    def test_filter_hits_dedup_same_point_same_window(self):
        fixed_now = datetime(2026, 3, 19, 8, 0, 0)

        class FixedDateTime(datetime):
            @classmethod
            def now(cls, tz=None):
                return fixed_now

        hits = {6: {"qty": 1, "points": [{"qty": 1, "seq": 100, "x": 1, "z": 2}]}}

        with mock.patch.object(
            self.receiver, "datetime", FixedDateTime
        ), mock.patch.object(self.receiver, "save_dedup_cache", lambda: None):
            window_1, filtered_1 = self.receiver.filter_hits_for_current_window(
                "u1", hits
            )
            window_2, filtered_2 = self.receiver.filter_hits_for_current_window(
                "u1", hits
            )

        self.assertEqual(window_1, "20260319_0500")
        self.assertEqual(window_2, "20260319_0500")
        self.assertIn(6, filtered_1)
        self.assertEqual(filtered_2, {})

    def test_filter_hits_allows_new_point_in_same_window(self):
        fixed_now = datetime(2026, 3, 19, 8, 0, 0)

        class FixedDateTime(datetime):
            @classmethod
            def now(cls, tz=None):
                return fixed_now

        first_hits = {6: {"qty": 1, "points": [{"qty": 1, "seq": 100, "x": 1, "z": 2}]}}
        second_hits = {
            6: {"qty": 2, "points": [{"qty": 2, "seq": 101, "x": 3, "z": 4}]}
        }

        with mock.patch.object(
            self.receiver, "datetime", FixedDateTime
        ), mock.patch.object(self.receiver, "save_dedup_cache", lambda: None):
            _, filtered_1 = self.receiver.filter_hits_for_current_window(
                "u1", first_hits
            )
            _, filtered_2 = self.receiver.filter_hits_for_current_window(
                "u1", second_hits
            )

        self.assertIn(6, filtered_1)
        self.assertIn(6, filtered_2)
        self.assertEqual(filtered_2[6]["qty"], 2)


class ReceiverMessageTests(unittest.TestCase):
    class _DummyResp:
        def __init__(self, body):
            self._body = body

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return self._body

    def setUp(self):
        self.receiver = load_receiver_module()
        self.receiver.BOT_PUSH_ENABLED = True
        self.receiver.BOT_PUSH_URL = "http://napcat:3000"
        self.receiver.BOT_PUSH_MODE = "group"
        self.receiver.BOT_TARGET_ID = "123456"
        self.receiver.BOT_TOKEN = "token-abc"
        self.receiver.BOT_PUSH_RETRY = 3

    def test_send_bot_message_group_success_with_token(self):
        calls = []

        def fake_urlopen(req, timeout=0):
            calls.append((req, timeout))
            return self._DummyResp(b'{"status":"ok"}')

        with mock.patch.object(
            self.receiver.urllib.request, "urlopen", side_effect=fake_urlopen
        ):
            ok, detail = self.receiver.send_bot_message("hello")

        self.assertTrue(ok)
        self.assertIn('"status":"ok"', detail)
        self.assertEqual(len(calls), 1)
        req, timeout = calls[0]
        self.assertEqual(timeout, 8)
        self.assertEqual(req.full_url, "http://napcat:3000/send_group_msg")
        self.assertEqual(req.headers.get("Authorization"), "Bearer token-abc")
        body = json.loads(req.data.decode("utf-8"))
        self.assertEqual(body["group_id"], 123456)
        self.assertEqual(body["message"], "hello")

    def test_send_bot_message_private_retries_then_success(self):
        self.receiver.BOT_PUSH_MODE = "private"
        self.receiver.BOT_TARGET_ID = "654321"
        state = {"n": 0}

        def flaky(req, timeout=0):
            state["n"] += 1
            if state["n"] < 3:
                raise RuntimeError("temporary")
            return self._DummyResp(b'{"ok":1}')

        with mock.patch.object(
            self.receiver.urllib.request, "urlopen", side_effect=flaky
        ), mock.patch.object(self.receiver.time, "sleep", lambda *_: None):
            ok, detail = self.receiver.send_bot_message("hello")

        self.assertTrue(ok)
        self.assertIn('"ok":1', detail)
        self.assertEqual(state["n"], 3)

    def test_send_bot_message_invalid_mode(self):
        self.receiver.BOT_PUSH_MODE = "channel"
        ok, detail = self.receiver.send_bot_message("hello")
        self.assertFalse(ok)
        self.assertEqual(detail, "invalid_push_mode:channel")

    def test_send_bot_message_missing_target(self):
        self.receiver.BOT_TARGET_ID = "0"
        ok, detail = self.receiver.send_bot_message("hello")
        self.assertFalse(ok)
        self.assertEqual(detail, "missing_bot_target_id")

    def test_push_text_with_optional_image_modes(self):
        with mock.patch.object(
            self.receiver, "send_bot_message", return_value=(True, "ok")
        ) as send_mock, mock.patch.object(
            self.receiver,
            "image_to_segment",
            return_value={"type": "image", "data": {"file": "base64://x"}},
        ):
            self.receiver.BOT_MESSAGE_MODE = "text"
            self.assertEqual(
                self.receiver.push_text_with_optional_image("txt", "/tmp/a.png"),
                (True, "ok"),
            )
            send_mock.assert_called_with("txt")

            self.receiver.BOT_MESSAGE_MODE = "image"
            self.assertEqual(
                self.receiver.push_text_with_optional_image("txt", "/tmp/a.png"),
                (True, "ok"),
            )
            self.assertEqual(send_mock.call_args_list[-1].args[0][0]["type"], "image")

            self.receiver.BOT_MESSAGE_MODE = "text+image"
            self.assertEqual(
                self.receiver.push_text_with_optional_image("txt", "/tmp/a.png"),
                (True, "ok"),
            )
            payload = send_mock.call_args_list[-1].args[0]
            self.assertEqual(payload[0]["type"], "text")
            self.assertEqual(payload[1]["type"], "image")

    def test_push_text_with_optional_image_fallback_to_text(self):
        self.receiver.BOT_MESSAGE_MODE = "text+image"
        with mock.patch.object(
            self.receiver, "image_to_segment", return_value=None
        ), mock.patch.object(
            self.receiver, "send_bot_message", return_value=(True, "ok")
        ) as send_mock:
            self.assertEqual(
                self.receiver.push_text_with_optional_image("txt", "/tmp/a.png"),
                (True, "ok"),
            )
            send_mock.assert_called_once_with("txt")


class ReceiverFormattingAndCacheTests(unittest.TestCase):
    def setUp(self):
        self.receiver = load_receiver_module()
        self.receiver.NOTIFICATION_DEDUP_CACHE.clear()

    def test_format_hit_text_compact_and_overflow(self):
        hits = {
            6: {
                "qty": 9,
                "points": [
                    {"x": 1, "z": 1},
                    {"x": 2, "z": 2},
                    {"x": 3, "z": 3},
                    {"x": 4, "z": 4},
                    {"x": 5, "z": 5},
                    {"x": 6, "z": 6},
                    {"x": 7, "z": 7},
                ],
            }
        }
        text = self.receiver.format_hit_text(hits)
        self.assertIn("Map 2 (beach)", text)
        self.assertIn("diamond x9", text)
        self.assertIn("...(+1)", text)

    def test_find_diamond_hits_mixed_data(self):
        payload = {
            "updatedResources": {
                "userMysekaiHarvestMaps": [
                    {
                        "mysekaiSiteId": 7,
                        "userMysekaiSiteHarvestResourceDrops": [
                            {
                                "resourceType": "mysekai_material",
                                "resourceId": 12,
                                "quantity": 1,
                                "seq": 1,
                            },
                            {
                                "resourceType": "mysekai_material",
                                "resourceId": 12,
                                "quantity": 3,
                            },
                            {
                                "resourceType": "mysekai_material",
                                "resourceId": 99,
                                "quantity": 4,
                            },
                            {
                                "resourceType": "mysekai_item",
                                "resourceId": 7,
                                "quantity": 2,
                            },
                        ],
                    },
                    {
                        "mysekaiSiteId": 8,
                        "userMysekaiSiteHarvestResourceDrops": [
                            {
                                "resourceType": "mysekai_material",
                                "resourceId": 12,
                                "quantity": 2,
                                "positionX": 8,
                                "positionZ": 9,
                            }
                        ],
                    },
                ]
            }
        }
        hits = self.receiver.find_diamond_hits(payload)
        self.assertEqual(hits[7]["qty"], 4)
        self.assertEqual(hits[8]["qty"], 2)
        self.assertEqual(hits[8]["points"][0]["x"], 8)

    def test_cleanup_window_dedup_cache(self):
        self.receiver.NOTIFICATION_WINDOW_CACHE_HOURS = 1
        now_ts = 2_000_000
        self.receiver.NOTIFICATION_DEDUP_CACHE.update(
            {
                "old": now_ts - 7201,
                "new": now_ts - 1200,
            }
        )
        with mock.patch.object(
            self.receiver.time, "time", return_value=now_ts
        ), mock.patch.object(self.receiver, "save_dedup_cache") as save_mock:
            self.receiver.cleanup_window_dedup_cache()
        self.assertNotIn("old", self.receiver.NOTIFICATION_DEDUP_CACHE)
        self.assertIn("new", self.receiver.NOTIFICATION_DEDUP_CACHE)
        save_mock.assert_called_once()


class ReceiverIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.receiver = load_receiver_module()
        self.receiver.NOTIFICATION_DEDUP_CACHE.clear()

    def test_process_notification_skips_non_full_packet(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "a.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"updatedResources": {}}, f)
            with mock.patch.object(
                self.receiver, "append_notification_event"
            ) as append_mock:
                self.receiver.process_mysekai_notification(
                    path, "https://x/user/1/mysekai"
                )
                append_mock.assert_not_called()

    def test_process_notification_skips_no_diamond(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "b.json")
            payload = {
                "updatedResources": {
                    "userMysekaiHarvestMaps": [
                        {
                            "mysekaiSiteId": 6,
                            "userMysekaiSiteHarvestResourceDrops": [
                                {
                                    "resourceType": "mysekai_material",
                                    "resourceId": 11,
                                    "quantity": 1,
                                }
                            ],
                        }
                    ]
                }
            }
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f)
            with mock.patch.object(
                self.receiver, "append_notification_event"
            ) as append_mock:
                self.receiver.process_mysekai_notification(
                    path, "https://x/user/1/mysekai"
                )
                append_mock.assert_not_called()

    def test_process_notification_hit_flow(self):
        with tempfile.TemporaryDirectory() as td:
            out_json = os.path.join(td, "hit.json")
            payload = {
                "updatedResources": {
                    "userMysekaiHarvestMaps": [
                        {
                            "mysekaiSiteId": 6,
                            "userMysekaiSiteHarvestResourceDrops": [
                                {
                                    "resourceType": "mysekai_material",
                                    "resourceId": 12,
                                    "quantity": 2,
                                    "seq": 1,
                                }
                            ],
                        }
                    ]
                }
            }
            with open(out_json, "w", encoding="utf-8") as f:
                json.dump(payload, f)

            notification_dir = os.path.join(td, "notifications")
            hit_dir = os.path.join(notification_dir, "hits")
            os.makedirs(hit_dir, exist_ok=True)
            filtered_hits = {6: {"qty": 2, "points": [{"qty": 2, "seq": 1}]}}

            with mock.patch.object(
                self.receiver, "cleanup_window_dedup_cache"
            ), mock.patch.object(
                self.receiver,
                "filter_hits_for_current_window",
                return_value=("20260320_0500", filtered_hits),
            ), mock.patch.object(
                self.receiver, "append_notification_event"
            ) as append_mock, mock.patch.object(
                self.receiver,
                "ensure_notification_dirs",
                return_value=(notification_dir, hit_dir),
            ), mock.patch.object(
                self.receiver,
                "render_mysekai_site_maps",
                return_value=({6: os.path.join(td, "m.png")}, "ok"),
            ) as render_mock, mock.patch.object(
                self.receiver,
                "push_text_with_optional_image",
                return_value=(True, "ok"),
            ) as push_mock, mock.patch.object(
                self.receiver, "prune_old_files"
            ):
                self.receiver.process_mysekai_notification(
                    out_json, "https://x/api/user/999/mysekai"
                )

            append_mock.assert_called_once()
            render_mock.assert_called_once()
            push_mock.assert_called_once()
            archived = os.path.join(hit_dir, os.path.basename(out_json))
            self.assertTrue(os.path.exists(archived))


class RequestHandlerTests(unittest.TestCase):
    def setUp(self):
        self.receiver = load_receiver_module()

    def _start_server(self):
        self.receiver.RequestHandler.log_message = lambda *args, **kwargs: None
        server = self.receiver.socketserver.TCPServer(
            ("127.0.0.1", 0), self.receiver.RequestHandler
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return server, thread

    def test_get_healthz(self):
        server, thread = self._start_server()
        try:
            conn = HTTPConnection("127.0.0.1", server.server_address[1], timeout=3)
            conn.request("GET", "/healthz")
            resp = conn.getresponse()
            body = resp.read().decode("utf-8")
            self.assertEqual(resp.status, 200)
            self.assertEqual(body, "ok")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_get_upload_js(self):
        server, thread = self._start_server()
        try:
            conn = HTTPConnection("127.0.0.1", server.server_address[1], timeout=3)
            conn.request("GET", "/upload.js")
            resp = conn.getresponse()
            body = resp.read().decode("utf-8")
            self.assertEqual(resp.status, 200)
            self.assertIn("/upload", body)
            self.assertIn("$httpClient.post", body)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_get_unknown_404(self):
        server, thread = self._start_server()
        try:
            conn = HTTPConnection("127.0.0.1", server.server_address[1], timeout=3)
            conn.request("GET", "/")
            resp = conn.getresponse()
            self.assertEqual(resp.status, 404)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()

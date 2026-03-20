import importlib.util
import os
import unittest
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
        self.receiver.ALERT_DEDUP_CACHE.clear()

    def test_extract_api_type(self):
        self.assertEqual(
            self.receiver.extract_api_type("https://x/api/user/1/mysekai?isForceAllReloadOnlyMysekai=True"),
            "mysekai",
        )
        self.assertEqual(self.receiver.extract_api_type("https://x/api/suite/user/1"), "suite")
        self.assertEqual(self.receiver.extract_api_type("https://x/api/other"), "unknown")

    def test_find_diamond_hits_only_id_12(self):
        payload = {
            "updatedResources": {
                "userMysekaiHarvestMaps": [
                    {
                        "mysekaiSiteId": 6,
                        "userMysekaiSiteHarvestResourceDrops": [
                            {"resourceType": "mysekai_material", "resourceId": 12, "quantity": 1, "seq": 1, "positionX": 2, "positionZ": 3},
                            {"resourceType": "mysekai_material", "resourceId": 12, "quantity": 2, "seq": 2, "positionX": 4, "positionZ": 5},
                            {"resourceType": "mysekai_material", "resourceId": 11, "quantity": 9, "seq": 3, "positionX": 7, "positionZ": 8},
                            {"resourceType": "mysekai_item", "resourceId": 7, "quantity": 1, "seq": 4, "positionX": 9, "positionZ": 10},
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

        with mock.patch.object(self.receiver, "datetime", FixedDateTime), mock.patch.object(
            self.receiver, "save_dedup_cache", lambda: None
        ):
            window_1, filtered_1 = self.receiver.filter_hits_for_current_window("u1", hits)
            window_2, filtered_2 = self.receiver.filter_hits_for_current_window("u1", hits)

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
        second_hits = {6: {"qty": 2, "points": [{"qty": 2, "seq": 101, "x": 3, "z": 4}]}}

        with mock.patch.object(self.receiver, "datetime", FixedDateTime), mock.patch.object(
            self.receiver, "save_dedup_cache", lambda: None
        ):
            _, filtered_1 = self.receiver.filter_hits_for_current_window("u1", first_hits)
            _, filtered_2 = self.receiver.filter_hits_for_current_window("u1", second_hits)

        self.assertIn(6, filtered_1)
        self.assertIn(6, filtered_2)
        self.assertEqual(filtered_2[6]["qty"], 2)


if __name__ == "__main__":
    unittest.main()

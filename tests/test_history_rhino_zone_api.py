# -*- coding: utf-8 -*-
"""API tests for manual Rhino zone endpoints."""

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.app import create_app


class HistoryRhinoZoneApiTestCase(unittest.TestCase):
    """Verify add/delete rhino zone API behavior."""

    def setUp(self) -> None:
        self.client = TestClient(create_app())

    @patch("api.v1.endpoints.history.HistoryService.upsert_manual_rhino_zone")
    def test_add_rhino_zone_success(self, mock_upsert) -> None:
        mock_upsert.return_value = {
            "updated": True,
            "record_id": 11,
            "zone": {"id": "manual-1", "upper": 100.0, "lower": 95.0, "strength_level": "强", "logic_detail": "自定义定义"},
            "message": "写入成功",
        }
        response = self.client.post(
            "/api/v1/history/11/rhino-zones",
            json={"upper": 100, "lower": 95, "strength_level": "强", "definition": "自定义定义"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["updated"])
        self.assertEqual(payload["record_id"], 11)
        self.assertEqual(payload["zone"]["id"], "manual-1")
        self.assertEqual(payload["zone"]["logic_detail"], "自定义定义")
        mock_upsert.assert_called_once()
        kwargs = mock_upsert.call_args.kwargs
        self.assertEqual(kwargs.get("definition"), "自定义定义")

    @patch("api.v1.endpoints.history.HistoryService.delete_manual_rhino_zone")
    def test_delete_rhino_zone_success(self, mock_delete) -> None:
        mock_delete.return_value = {
            "deleted": True,
            "record_id": 11,
            "zone_id": "manual-1",
            "message": "删除成功",
        }
        response = self.client.delete("/api/v1/history/11/rhino-zones/manual-1")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["deleted"])
        self.assertEqual(payload["record_id"], 11)
        self.assertEqual(payload["zone_id"], "manual-1")


if __name__ == "__main__":
    unittest.main()

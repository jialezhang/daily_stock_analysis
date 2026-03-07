# -*- coding: utf-8 -*-
"""API tests for refreshing one history record."""

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.app import create_app


class HistoryRefreshApiTestCase(unittest.TestCase):
    """Verify POST /api/v1/history/{record_id}/refresh behavior."""

    def setUp(self) -> None:
        self.client = TestClient(create_app())

    @patch("api.v1.endpoints.history.HistoryService.refresh_history_record")
    def test_refresh_record_success(self, mock_refresh) -> None:
        mock_refresh.return_value = {
            "updated": True,
            "record_id": 99,
            "mode": "partial",
            "modules": ["technical_indicators"],
            "message": "刷新成功",
        }

        response = self.client.post(
            "/api/v1/history/99/refresh",
            json={"mode": "partial", "modules": ["technical_indicators"]},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["updated"])
        self.assertEqual(payload["record_id"], 99)
        self.assertEqual(payload["mode"], "partial")

    @patch("api.v1.endpoints.history.HistoryService.refresh_history_record")
    def test_refresh_record_not_found(self, mock_refresh) -> None:
        mock_refresh.return_value = {
            "updated": False,
            "record_id": 123,
            "mode": "full",
            "modules": [],
            "message": "未找到 id=123 的分析记录",
        }

        response = self.client.post("/api/v1/history/123/refresh", json={"mode": "full", "modules": []})
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()

# -*- coding: utf-8 -*-
"""API tests for position management endpoints."""

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.app import create_app


class HistoryPositionManagementApiTestCase(unittest.TestCase):
    """Verify GET/PUT /api/v1/history/{record_id}/position-management."""

    def setUp(self) -> None:
        self.client = TestClient(create_app())

    @patch("api.v1.endpoints.history.HistoryService.get_position_management")
    def test_get_position_management_success(self, mock_get) -> None:
        mock_get.return_value = {
            "updated": True,
            "record_id": 11,
            "module": {"target": {"annual_return_target_pct": 30}, "holdings": []},
            "message": "读取成功",
        }
        response = self.client.get("/api/v1/history/11/position-management")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["updated"])
        self.assertEqual(payload["record_id"], 11)
        self.assertIn("module", payload)

    @patch("api.v1.endpoints.history.HistoryService.upsert_position_management")
    def test_put_position_management_success(self, mock_upsert) -> None:
        mock_upsert.return_value = {
            "updated": True,
            "record_id": 11,
            "module": {"target": {"base_currency": "USD"}, "holdings": [{"symbol": "NVDA"}]},
            "message": "保存成功",
        }
        response = self.client.put(
            "/api/v1/history/11/position-management",
            json={
                "target": {"annual_return_target_pct": 30, "base_currency": "USD", "usd_cny": 7.2, "usd_hkd": 7.8},
                "holdings": [
                    {
                        "market_type": "us",
                        "asset_class": "美股",
                        "symbol": "NVDA",
                        "name": "NVIDIA",
                        "quantity": 10,
                        "avg_cost": 100,
                        "current_price": 120,
                        "previous_close": 118,
                        "currency": "USD",
                    }
                ],
                "macro_events": ["Fed rate"],
                "notes": "note",
                "refresh_benchmarks": False,
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["updated"])
        self.assertEqual(payload["record_id"], 11)
        kwargs = mock_upsert.call_args.kwargs
        self.assertEqual(kwargs["record_id"], 11)
        self.assertEqual(kwargs["target"]["base_currency"], "USD")
        self.assertEqual(kwargs["holdings"][0]["symbol"], "NVDA")


if __name__ == "__main__":
    unittest.main()

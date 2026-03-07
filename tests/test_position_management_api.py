# -*- coding: utf-8 -*-
"""API tests for global position management endpoints."""

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.app import create_app


class PositionManagementApiTestCase(unittest.TestCase):
    """Verify GET/PUT/POST refresh endpoints."""

    def setUp(self) -> None:
        self.client = TestClient(create_app())

    @patch("api.v1.endpoints.position_management.PositionManagementService.get_module")
    def test_get_module(self, mock_get) -> None:
        mock_get.return_value = {"updated": True, "module": {"scope": "global"}, "message": "读取成功"}
        response = self.client.get("/api/v1/position-management")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["updated"])
        self.assertEqual(data["module"]["scope"], "global")

    @patch("api.v1.endpoints.position_management.PositionManagementService.upsert_module")
    def test_upsert_module(self, mock_upsert) -> None:
        mock_upsert.return_value = {"updated": True, "module": {"holdings": [{"symbol": "NVDA"}]}, "message": "保存成功"}
        response = self.client.put(
            "/api/v1/position-management",
            json={
                "target": {"initial_position": 100000, "output_currency": "USD", "target_return_pct": 30},
                "holdings": [
                    {
                        "asset_primary": "股票",
                        "asset_secondary": "美股",
                        "symbol": "NVDA",
                        "name": "NVIDIA",
                        "quantity": 10,
                    }
                ],
                "macro_events": ["Fed update"],
                "notes": "global",
                "refresh_benchmarks": False,
            },
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["updated"])
        self.assertEqual(data["module"]["holdings"][0]["symbol"], "NVDA")

    @patch("api.v1.endpoints.position_management.PositionManagementService.refresh_module")
    def test_refresh_module(self, mock_refresh) -> None:
        mock_refresh.return_value = {"updated": True, "module": {"updated_at": "2026-03-01T00:00:00"}, "message": "更新成功"}
        response = self.client.post("/api/v1/position-management/refresh")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["updated"])
        self.assertIn("updated_at", data["module"])

    @patch("api.v1.endpoints.position_management.run_position_daily_review")
    @patch("api.v1.endpoints.position_management.load_latest_position_review")
    @patch("api.v1.endpoints.position_management.GeminiAnalyzer")
    @patch("api.v1.endpoints.position_management.NotificationService")
    def test_review_push(self, _mock_notifier, _mock_analyzer, mock_load_latest, mock_run_review) -> None:
        mock_run_review.return_value = "## 2026-03-02 每日仓位复盘\n\n测试内容"
        mock_load_latest.return_value = {
            "generated_at": "2026-03-02T10:00:00",
            "file_path": "/tmp/position_review_20260302.md",
            "markdown": "## 2026-03-02 每日资产管理复盘",
            "sections": {"macro_cross_market": "test"},
        }
        response = self.client.post("/api/v1/position-management/review-push")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["pushed"])
        self.assertIn("已触发", data["message"])
        self.assertIn("每日仓位复盘", data["report_preview"])
        self.assertIsInstance(data.get("daily_review"), dict)

    @patch("api.v1.endpoints.position_management.load_latest_position_review")
    def test_get_latest_review(self, mock_load_latest) -> None:
        mock_load_latest.return_value = {
            "generated_at": "2026-03-02T10:00:00",
            "file_path": "/tmp/position_review_20260302.md",
            "markdown": "## 2026-03-02 每日资产管理复盘",
            "sections": {
                "macro_cross_market": "A",
                "target_tracking": "B",
                "risk_warning": "C",
                "grid_reference": "D",
            },
        }
        response = self.client.get("/api/v1/position-management/review/latest")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["found"])
        self.assertIsInstance(data.get("daily_review"), dict)

    @patch("api.v1.endpoints.position_management.list_position_reviews")
    def test_get_review_history(self, mock_list_history) -> None:
        mock_list_history.return_value = [
            {
                "review_date": "2026-03-01",
                "generated_at": "2026-03-01T22:00:00",
                "file_path": "/tmp/position_review_20260301.md",
                "sections": {"macro_cross_market": "A"},
                "note": "N1",
            }
        ]
        response = self.client.get("/api/v1/position-management/review/history?limit=30")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["found"])
        self.assertEqual(len(data["reviews"]), 1)

    @patch("api.v1.endpoints.position_management.upsert_position_review_note")
    def test_save_review_note(self, mock_upsert_note) -> None:
        mock_upsert_note.return_value = {"review_date": "2026-03-01", "note": "new note"}
        response = self.client.put("/api/v1/position-management/review/2026-03-01/note", json={"note": "new note"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["updated"])
        self.assertEqual(data["review_date"], "2026-03-01")


    @patch("api.v1.endpoints.position_management.load_latest_portfolio_review")
    def test_get_latest_portfolio_review(self, mock_load_latest) -> None:
        mock_load_latest.return_value = {
            "review_date": "2026-03-07",
            "generated_at": "2026-03-07T21:00:00",
            "total_value_cny": 1050000.0,
            "health_score": 82,
            "health_grade": "A",
            "review_report": "# 组合每日复盘\n\n摘要",
        }
        response = self.client.get("/api/v1/position-management/portfolio-review/latest")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["found"])
        self.assertEqual(data["portfolio_review"]["health_score"], 82)

    @patch("api.v1.endpoints.position_management.list_portfolio_reviews")
    def test_get_portfolio_review_history(self, mock_list_history) -> None:
        mock_list_history.return_value = [
            {
                "review_date": "2026-03-07",
                "generated_at": "2026-03-07T21:00:00",
                "health_score": 82,
                "health_grade": "A",
                "review_report": "# 组合每日复盘",
            }
        ]
        response = self.client.get("/api/v1/position-management/portfolio-review/history?limit=30")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["found"])
        self.assertEqual(len(data["reviews"]), 1)

    @patch("api.v1.endpoints.position_management.run_portfolio_review")
    @patch("api.v1.endpoints.position_management.build_portfolio_from_config")
    @patch("api.v1.endpoints.position_management.build_portfolio_from_position_management_module")
    @patch("api.v1.endpoints.position_management.PositionManagementService.get_module")
    @patch("api.v1.endpoints.position_management.GeminiAnalyzer")
    @patch("api.v1.endpoints.position_management.NotificationService")
    def test_run_portfolio_review_endpoint(
        self,
        _mock_notifier,
        _mock_analyzer,
        mock_get_position_module,
        mock_build_from_module,
        mock_build_portfolio,
        mock_run_review,
    ) -> None:
        mock_get_position_module.return_value = {"module": {"holdings": [{"symbol": "NVDA"}]}}
        mock_build_from_module.return_value = object()
        mock_build_portfolio.return_value = None
        mock_run_review.return_value = "# 组合每日复盘\n\n测试内容"
        response = self.client.post("/api/v1/position-management/portfolio-review/run")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertIn("组合复盘", data["report_preview"])
        self.assertIn("仓位管理", data["message"])
        mock_build_portfolio.assert_not_called()


if __name__ == "__main__":
    unittest.main()

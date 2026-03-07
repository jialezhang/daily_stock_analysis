# -*- coding: utf-8 -*-
"""API tests for daily review module."""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from api.app import create_app


class TestDailyReviewApi:
    """Verify /api/v1/daily-review endpoints."""

    def setup_method(self) -> None:
        self.client = TestClient(create_app())

    @patch("api.v1.endpoints.daily_review.build_period_items")
    def test_history_returns_period_items(self, mock_build_items) -> None:
        mock_build_items.return_value = [
            {
                "dimension": "day",
                "period_key": "2026-03-06",
                "period_label": "2026-03-06",
                "review_date": "2026-03-06",
                "generated_at": "2026-03-06 21:00:00 CST",
                "summary": "summary",
                "snapshot": {"review_date": "2026-03-06"},
                "charts": {"market_scores": {"US": 2.0, "HK": 1.0, "A": 0.0}},
            }
        ]

        response = self.client.get("/api/v1/daily-review/history", params={"dimension": "day", "limit": 30})
        assert response.status_code == 200
        payload = response.json()
        assert payload["found"] is True
        assert payload["items"][0]["dimension"] == "day"
        assert payload["items"][0]["period_key"] == "2026-03-06"

    @patch("api.v1.endpoints.daily_review.run_daily_review")
    @patch("api.v1.endpoints.daily_review.build_period_items")
    def test_run_triggers_review_and_returns_latest_item(self, mock_build_items, mock_run_review) -> None:
        mock_run_review.return_value = "# review"
        mock_build_items.return_value = [
            {
                "dimension": "day",
                "period_key": "2026-03-06",
                "period_label": "2026-03-06",
                "review_date": "2026-03-06",
                "generated_at": "2026-03-06 21:00:00 CST",
                "summary": "summary",
                "snapshot": {"review_date": "2026-03-06"},
                "charts": {"market_scores": {"US": 2.0, "HK": 1.0, "A": 0.0}},
            }
        ]

        response = self.client.post("/api/v1/daily-review/run", json={"push_telegram": False, "use_llm": False})
        assert response.status_code == 200
        payload = response.json()
        assert payload["success"] is True
        assert payload["item"]["period_key"] == "2026-03-06"

    @patch("api.v1.endpoints.daily_review.push_review_by_date")
    def test_push_by_date(self, mock_push) -> None:
        mock_push.return_value = True
        response = self.client.post("/api/v1/daily-review/2026-03-06/push")
        assert response.status_code == 200
        payload = response.json()
        assert payload["pushed"] is True

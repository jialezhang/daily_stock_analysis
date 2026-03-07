# -*- coding: utf-8 -*-
"""Unit tests for position management module persistence."""

import json
import unittest
from types import SimpleNamespace

from src.services.history_service import HistoryService


class _FakeDB:
    def __init__(self) -> None:
        self.record = SimpleNamespace(
            id=1,
            code="NVDA",
            name="NVIDIA",
            news_content="Fed policy update\nMiddle East tension",
            raw_result=json.dumps({}, ensure_ascii=False),
            context_snapshot=json.dumps({}, ensure_ascii=False),
        )

    def get_analysis_history_by_id(self, record_id: int):
        if record_id != 1:
            return None
        return self.record

    def update_analysis_history_by_id(self, record_id: int, updates):
        if record_id != 1:
            return 0
        if "raw_result" in updates:
            self.record.raw_result = updates["raw_result"]
        if "context_snapshot" in updates:
            self.record.context_snapshot = updates["context_snapshot"]
        return 1


class PositionManagementServiceTestCase(unittest.TestCase):
    """Verify position management read/write/refresh behavior."""

    def setUp(self) -> None:
        self.db = _FakeDB()
        self.service = HistoryService(self.db)

    def test_upsert_and_get_position_management(self) -> None:
        result = self.service.upsert_position_management(
            record_id=1,
            target={
                "annual_return_target_pct": 30,
                "base_currency": "USD",
                "usd_cny": 7.2,
                "usd_hkd": 7.8,
            },
            holdings=[
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
            macro_events=["Fed policy path", "Geopolitical risk"],
            notes="core holding",
            refresh_benchmarks=False,
        )
        self.assertTrue(result["updated"])
        module = result["module"] or {}
        self.assertEqual(len(module.get("holdings") or []), 1)
        totals = ((module.get("derived") or {}).get("totals") or {})
        self.assertAlmostEqual(float(totals.get("total_value", 0.0)), 1200.0, places=2)
        self.assertAlmostEqual(float(totals.get("cumulative_pnl", 0.0)), 200.0, places=2)

        raw_after = json.loads(self.db.record.raw_result)
        self.assertIn("position_management", raw_after)
        saved = raw_after["position_management"]
        self.assertEqual(saved.get("notes"), "core holding")
        self.assertEqual(saved.get("target", {}).get("base_currency"), "USD")

        read_result = self.service.get_position_management(record_id=1)
        self.assertTrue(read_result["updated"])
        read_module = read_result["module"] or {}
        self.assertEqual(len(read_module.get("holdings") or []), 1)

    def test_heatmap_is_sorted_by_change_pct_desc(self) -> None:
        result = self.service.upsert_position_management(
            record_id=1,
            target={
                "annual_return_target_pct": 30,
                "base_currency": "USD",
                "usd_cny": 7.2,
                "usd_hkd": 7.8,
            },
            holdings=[
                {
                    "market_type": "us",
                    "asset_class": "美股",
                    "symbol": "NVDA",
                    "name": "NVIDIA",
                    "quantity": 10,
                    "avg_cost": 100,
                    "current_price": 98,
                    "previous_close": 100,
                    "currency": "USD",
                },
                {
                    "market_type": "us",
                    "asset_class": "美股",
                    "symbol": "AAPL",
                    "name": "Apple",
                    "quantity": 10,
                    "avg_cost": 100,
                    "current_price": 105,
                    "previous_close": 100,
                    "currency": "USD",
                },
                {
                    "market_type": "us",
                    "asset_class": "美股",
                    "symbol": "MSFT",
                    "name": "Microsoft",
                    "quantity": 10,
                    "avg_cost": 100,
                    "current_price": 101,
                    "previous_close": 100,
                    "currency": "USD",
                },
            ],
            macro_events=[],
            notes="",
            refresh_benchmarks=False,
        )

        module = result["module"] or {}
        heatmap = ((module.get("derived") or {}).get("heatmap") or [])
        symbols = [str(item.get("symbol") or "") for item in heatmap]
        self.assertEqual(symbols, ["AAPL", "MSFT", "NVDA"])


if __name__ == "__main__":
    unittest.main()

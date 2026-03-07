# -*- coding: utf-8 -*-
"""Tests for global position management service."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.services.position_management_service import PositionManagementService


class PositionManagementServiceTestCase(unittest.TestCase):
    """Verify global module persistence behavior."""

    def setUp(self) -> None:
        self._tmp_dir = tempfile.TemporaryDirectory()
        self.file_path = Path(self._tmp_dir.name) / "position_management.json"
        self.service = PositionManagementService(file_path=self.file_path)

    def tearDown(self) -> None:
        self._tmp_dir.cleanup()

    def test_upsert_and_get_module(self) -> None:
        with patch.object(self.service, "_get_fx_rates", return_value={"usd_cny": 7.1, "hkd_cny": 0.91, "as_of": "x", "source": "test"}):
            with patch.object(
                self.service,
                "_fetch_quote",
                return_value={"latest_price": 120.0, "previous_close": 118.0, "currency": "USD", "name": "NVIDIA"},
            ):
                upsert = self.service.upsert_module(
                    target={"initial_position": 1000, "output_currency": "USD", "target_return_pct": 25},
                    holdings=[
                        {
                            "asset_primary": "股票",
                            "asset_secondary": "美股",
                            "symbol": "NVDA",
                            "quantity": 10,
                        }
                    ],
                    macro_events=["Fed path"],
                    notes="global test",
                    refresh_benchmarks=False,
                )
        self.assertTrue(upsert["updated"])
        self.assertTrue(self.file_path.exists())
        module = upsert["module"] or {}
        self.assertEqual(module.get("scope"), "global")
        self.assertEqual(module.get("target", {}).get("target_return_pct"), 25.0)
        self.assertEqual(len(module.get("holdings", [])), 1)
        self.assertEqual(module.get("holdings", [])[0].get("asset_primary"), "权益类")
        totals = ((module.get("derived") or {}).get("totals") or {})
        self.assertAlmostEqual(float(totals.get("total_value_output", 0)), 1200.0, places=2)

        with patch.object(self.service, "_get_fx_rates", return_value={"usd_cny": 7.1, "hkd_cny": 0.91, "as_of": "x", "source": "test"}):
            with patch.object(
                self.service,
                "_fetch_quote",
                return_value={"latest_price": 120.0, "previous_close": 118.0, "currency": "USD", "name": "NVIDIA"},
            ):
                loaded = self.service.get_module()
        self.assertTrue(loaded["updated"])
        loaded_module = loaded["module"] or {}
        self.assertEqual(loaded_module.get("scope"), "global")
        self.assertEqual(loaded_module.get("notes"), "global test")

    def test_secondary_allocation_generated(self) -> None:
        with patch.object(self.service, "_get_fx_rates", return_value={"usd_cny": 7.1, "hkd_cny": 0.91, "as_of": "x", "source": "test"}):
            with patch.object(
                self.service,
                "_fetch_quote",
                side_effect=[
                    {"latest_price": 100.0, "previous_close": 99.0, "currency": "USD", "name": "NVIDIA"},
                    {"latest_price": 50.0, "previous_close": 49.0, "currency": "USD", "name": "SPY"},
                ],
            ):
                upsert = self.service.upsert_module(
                    target={"initial_position": 1000, "output_currency": "USD", "target_return_pct": 25},
                    holdings=[
                        {
                            "asset_primary": "权益类",
                            "asset_secondary": "美股",
                            "symbol": "NVDA",
                            "quantity": 5,
                        },
                        {
                            "asset_primary": "权益类",
                            "asset_secondary": "ETF",
                            "symbol": "SPY",
                            "quantity": 4,
                        },
                    ],
                    macro_events=[],
                    notes="",
                    refresh_benchmarks=False,
                )

        module = upsert["module"] or {}
        derived = module.get("derived") or {}
        secondary = derived.get("secondary_allocation") or []
        self.assertTrue(len(secondary) >= 2)
        names = [item.get("asset_secondary") for item in secondary]
        self.assertIn("美股", names)
        self.assertIn("ETF", names)

    def test_resolve_hk_symbol_normalization(self) -> None:
        self.assertEqual(self.service._resolve_quote_symbol("00700", "股票", "港股"), "0700.HK")

    def test_cash_holding_without_symbol_is_kept_and_counted(self) -> None:
        with patch.object(
            self.service,
            "_get_fx_rates",
            return_value={"usd_cny": 7.2, "hkd_cny": 0.92, "as_of": "x", "source": "test"},
        ):
            upsert = self.service.upsert_module(
                target={"initial_position": 1000, "output_currency": "USD", "target_return_pct": 20},
                holdings=[
                    {
                        "asset_primary": "现金",
                        "asset_secondary": "人民币现金",
                        "symbol": "",
                        "name": "账户现金",
                        "quantity": 7200,
                        "currency": "CNY",
                    }
                ],
                macro_events=[],
                notes="cash test",
                refresh_benchmarks=False,
            )

        module = upsert["module"] or {}
        holdings = module.get("holdings") or []
        self.assertEqual(len(holdings), 1)
        row = holdings[0]
        self.assertEqual(row.get("asset_primary"), "现金")
        self.assertEqual(row.get("asset_secondary"), "人民币现金")
        self.assertEqual(row.get("latest_price"), 1.0)
        self.assertEqual(row.get("currency"), "CNY")
        self.assertAlmostEqual(float(row.get("market_value_output", 0)), 1000.0, places=2)

        derived = module.get("derived") or {}
        allocation = derived.get("allocation") or []
        secondary = derived.get("secondary_allocation") or []
        self.assertEqual(allocation[0].get("asset_primary"), "现金")
        self.assertEqual(secondary[0].get("asset_secondary"), "人民币现金")

    def test_fallback_name_is_used_when_quote_name_missing(self) -> None:
        with patch.object(
            self.service,
            "_get_fx_rates",
            return_value={"usd_cny": 7.2, "hkd_cny": 0.92, "as_of": "x", "source": "test"},
        ):
            with patch.object(
                self.service,
                "_fetch_quote",
                return_value={"latest_price": 120.0, "previous_close": 118.0, "currency": "USD", "name": ""},
            ):
                upsert = self.service.upsert_module(
                    target={"initial_position": 1000, "output_currency": "USD", "target_return_pct": 20},
                    holdings=[
                        {
                            "asset_primary": "权益类",
                            "asset_secondary": "美股",
                            "symbol": "NVDA",
                            "quantity": 1,
                        }
                    ],
                    macro_events=[],
                    notes="",
                    refresh_benchmarks=False,
                )

        module = upsert["module"] or {}
        holdings = module.get("holdings") or []
        self.assertEqual(len(holdings), 1)
        self.assertEqual(holdings[0].get("name"), "英伟达")

    def test_heatmap_is_sorted_by_change_pct_desc(self) -> None:
        quote_map = {
            "NVDA": {"latest_price": 98.0, "previous_close": 100.0, "currency": "USD", "name": "NVIDIA"},
            "AAPL": {"latest_price": 105.0, "previous_close": 100.0, "currency": "USD", "name": "Apple"},
            "MSFT": {"latest_price": 101.0, "previous_close": 100.0, "currency": "USD", "name": "Microsoft"},
        }
        with patch.object(
            self.service,
            "_get_fx_rates",
            return_value={"usd_cny": 7.2, "hkd_cny": 0.92, "as_of": "x", "source": "test"},
        ):
            with patch.object(
                self.service,
                "_fetch_quote",
                side_effect=lambda symbol: quote_map.get(symbol, {}),
            ):
                upsert = self.service.upsert_module(
                    target={"initial_position": 1000, "output_currency": "USD", "target_return_pct": 20},
                    holdings=[
                        {"asset_primary": "权益类", "asset_secondary": "美股", "symbol": "NVDA", "quantity": 1},
                        {"asset_primary": "权益类", "asset_secondary": "美股", "symbol": "AAPL", "quantity": 1},
                        {"asset_primary": "权益类", "asset_secondary": "美股", "symbol": "MSFT", "quantity": 1},
                    ],
                    macro_events=[],
                    notes="",
                    refresh_benchmarks=False,
                )

        heatmap = ((upsert.get("module") or {}).get("derived") or {}).get("heatmap") or []
        symbols = [str(row.get("symbol") or "") for row in heatmap]
        self.assertEqual(symbols, ["AAPL", "MSFT", "NVDA"])


if __name__ == "__main__":
    unittest.main()

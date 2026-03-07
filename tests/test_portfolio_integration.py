# -*- coding: utf-8 -*-
"""Integration tests for portfolio review wiring."""

import os
import tempfile
import time
import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

from src.config import Config
from src.core.portfolio_review import list_portfolio_reviews, load_latest_portfolio_review
from src.services.position_management_service import PositionManagementService
from src.storage import DatabaseManager
from src.portfolio.models import HealthReport, Portfolio, PortfolioHolding
from src.portfolio.runner import build_portfolio_from_config, build_portfolio_from_position_management_module


class _DummyNotifier:
    def __init__(self) -> None:
        self.saved = []
        self.sent = []

    def save_report_to_file(self, content: str, filename: str) -> str:
        self.saved.append((filename, content))
        return f"/tmp/{filename}"

    def send(self, content: str, email_send_to_all: bool = True) -> bool:
        self.sent.append((content, email_send_to_all))
        return True

    def is_available(self) -> bool:
        return False


class PortfolioIntegrationTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self._db_path = os.path.join(self._temp_dir.name, "portfolio_test.db")
        os.environ["DATABASE_PATH"] = self._db_path
        Config.reset_instance()
        DatabaseManager.reset_instance()
        self.db = DatabaseManager.get_instance()

    def tearDown(self) -> None:
        DatabaseManager.reset_instance()
        Config.reset_instance()
        os.environ.pop("DATABASE_PATH", None)
        self._temp_dir.cleanup()

    def test_build_portfolio_from_config_merges_tag_overrides(self) -> None:
        config = SimpleNamespace(
            portfolio_initial_capital=1_400_000.0,
            portfolio_target_return=0.30,
            portfolio_holdings_json='{"total_value_cny": 1000000, "cash_cny": 100000, "holdings": [{"ticker": "NVDA", "name": "NVIDIA", "market": "US", "shares": 10, "current_price": 120, "value_cny": 300000}, {"ticker": "00700", "name": "Tencent", "market": "HK", "value_cny": 200000, "style": "custom_hk"}]}',
            portfolio_stock_tags_json='{"NVDA": {"sector": "AI Chips", "style": "aggressive_growth", "beta": "very_high"}}',
        )

        portfolio = build_portfolio_from_config(config)

        self.assertIsNotNone(portfolio)
        if portfolio is None:
            self.fail("portfolio should not be None")
        self.assertEqual(portfolio.initial_capital, 1_400_000.0)
        self.assertEqual(portfolio.target_value, 1_820_000.0)
        self.assertEqual(portfolio.total_value_cny, 1_000_000.0)
        self.assertEqual(portfolio.output_currency, "CNY")
        self.assertEqual(portfolio.output_to_cny_rate, 1.0)
        nvda = next(item for item in portfolio.holdings if item.ticker == "NVDA")
        tencent = next(item for item in portfolio.holdings if item.ticker == "00700")
        self.assertEqual(nvda.sector, "AI Chips")
        self.assertEqual(nvda.style, "aggressive_growth")
        self.assertEqual(nvda.beta_level, "very_high")
        self.assertEqual(tencent.style, "custom_hk")
        self.assertAlmostEqual(nvda.weight_pct, 30.0)

    def test_save_portfolio_snapshot_upserts_same_date(self) -> None:
        portfolio = Portfolio(
            total_value_cny=1_000_000.0,
            holdings=[
                PortfolioHolding(
                    ticker="NVDA",
                    name="NVIDIA",
                    market="US",
                    value_cny=350_000.0,
                    weight_pct=35.0,
                ),
                PortfolioHolding(
                    ticker="00700",
                    name="Tencent",
                    market="HK",
                    value_cny=250_000.0,
                    weight_pct=25.0,
                ),
            ],
            cash_cny=150_000.0,
            crypto_value_cny=50_000.0,
        )
        health = HealthReport(score=82, grade="A")

        saved_first = self.db.save_portfolio_snapshot(date(2026, 3, 7), portfolio, health, "# first")
        with self.db.get_session() as session:
            from src.storage import PortfolioSnapshot
            first_row = session.query(PortfolioSnapshot).one()
            first_created_at = first_row.created_at

        time.sleep(0.01)
        portfolio.total_value_cny = 1_050_000.0
        saved_second = self.db.save_portfolio_snapshot(date(2026, 3, 7), portfolio, health, "# second")

        self.assertEqual(saved_first, 1)
        self.assertEqual(saved_second, 1)

        with self.db.get_session() as session:
            rows = session.query(PortfolioSnapshot).all()
            self.assertEqual(len(rows), 1)
            row = rows[0]
            self.assertEqual(row.date, date(2026, 3, 7))
            self.assertEqual(row.total_value_cny, 1_050_000.0)
            self.assertEqual(row.health_score, 82)
            self.assertEqual(row.health_grade, "A")
            self.assertEqual(row.cash_pct, 14.29)
            self.assertEqual(row.us_pct, 33.33)
            self.assertEqual(row.hk_pct, 23.81)
            self.assertEqual(row.crypto_pct, 4.76)
            self.assertEqual(row.review_report, "# second")
            self.assertIn("NVDA", row.holdings_json)
            self.assertGreater(row.created_at, first_created_at)

    def test_load_portfolio_reviews_works_after_session_close(self) -> None:
        portfolio = Portfolio(
            total_value_cny=1_000_000.0,
            holdings=[
                PortfolioHolding(
                    ticker="NVDA",
                    name="NVIDIA",
                    market="US",
                    value_cny=350_000.0,
                    weight_pct=35.0,
                )
            ],
            cash_cny=150_000.0,
        )
        health = HealthReport(score=82, grade="A")

        self.db.save_portfolio_snapshot(date(2026, 3, 7), portfolio, health, "# latest")

        latest = load_latest_portfolio_review()
        history = list_portfolio_reviews(limit=10)

        self.assertIsNotNone(latest)
        if latest is None:
            self.fail("latest portfolio review should not be None")
        self.assertEqual(latest["review_date"], "2026-03-07")
        self.assertEqual(latest["health_score"], 82)
        self.assertEqual(latest["holdings"][0]["ticker"], "NVDA")
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["review_report"], "# latest")

    def test_build_portfolio_from_position_management_module(self) -> None:
        service = PositionManagementService(file_path=os.path.join(self._temp_dir.name, "position_management.json"))
        with patch.object(
            service,
            "_fetch_quote",
            return_value={"latest_price": 120.0, "previous_close": 118.0, "currency": "USD", "name": "NVIDIA"},
        ):
            module_result = service.upsert_module(
                target={"initial_position": 100000.0, "output_currency": "USD", "target_return_pct": 20.0},
                holdings=[
                    {
                        "asset_primary": "权益类",
                        "asset_secondary": "美股",
                        "symbol": "NVDA",
                        "name": "NVIDIA",
                        "quantity": 10,
                        "current_price": 120.0,
                        "latest_price": 120.0,
                        "currency": "USD",
                    },
                    {
                        "asset_primary": "现金",
                        "asset_secondary": "人民币现金",
                        "symbol": "",
                        "name": "账户现金",
                        "quantity": 100000.0,
                        "currency": "CNY",
                    },
                ],
                macro_events=[],
                notes="",
                refresh_benchmarks=False,
            )

        config = SimpleNamespace(
            portfolio_initial_capital=1_400_000.0,
            portfolio_target_return=0.30,
            portfolio_stock_tags_json='{"NVDA": {"sector": "AI Chips", "style": "aggressive_growth", "beta": "very_high"}}',
        )
        portfolio = build_portfolio_from_position_management_module(module_result["module"], config=config)

        self.assertIsNotNone(portfolio)
        if portfolio is None:
            self.fail("portfolio should not be None")
        self.assertAlmostEqual(portfolio.initial_capital, 720000.0, places=2)
        self.assertAlmostEqual(portfolio.total_value_cny, 108640.0, places=2)
        self.assertAlmostEqual(portfolio.cash_cny, 100000.0, places=2)
        self.assertEqual(portfolio.output_currency, "USD")
        self.assertAlmostEqual(portfolio.output_to_cny_rate, 7.2, places=4)
        self.assertEqual(len(portfolio.holdings), 1)
        self.assertEqual(portfolio.holdings[0].ticker, "NVDA")
        self.assertEqual(portfolio.holdings[0].market, "US")
        self.assertEqual(portfolio.holdings[0].lot_size, 1.0)
        self.assertEqual(portfolio.holdings[0].sector, "AI Chips")
        self.assertEqual(portfolio.holdings[0].beta_level, "very_high")

    def test_build_portfolio_from_position_management_module_preserves_lot_size(self) -> None:
        module = {
            "target": {"initial_position": 100000.0, "output_currency": "CNY", "target_return_pct": 20.0},
            "fx": {"usd_cny": 7.2, "hkd_cny": 0.92},
            "holdings": [
                {
                    "asset_primary": "权益类",
                    "asset_secondary": "港股",
                    "symbol": "00700",
                    "name": "腾讯控股",
                    "quantity": 500,
                    "latest_price": 400.0,
                    "currency": "HKD",
                    "market_value_output": 184000.0,
                    "lot_size": 100,
                }
            ],
            "derived": {
                "totals": {"total_value_output": 184000.0},
            },
        }

        portfolio = build_portfolio_from_position_management_module(module, config=SimpleNamespace(portfolio_stock_tags_json=""))

        self.assertIsNotNone(portfolio)
        if portfolio is None:
            self.fail("portfolio should not be None")
        self.assertEqual(len(portfolio.holdings), 1)
        self.assertEqual(portfolio.holdings[0].ticker, "00700")
        self.assertEqual(portfolio.holdings[0].lot_size, 100.0)

    def test_build_portfolio_from_position_management_module_prefers_ticker_market_inference(self) -> None:
        module = {
            "target": {"initial_position": 1400000.0, "output_currency": "CNY", "target_return_pct": 30.0},
            "fx": {"usd_cny": 7.2, "hkd_cny": 0.92},
            "holdings": [
                {
                    "asset_primary": "权益类",
                    "asset_secondary": "A股",
                    "symbol": "NVDA",
                    "name": "NVIDIA",
                    "quantity": 10,
                    "latest_price": 100.0,
                    "currency": "USD",
                    "market_value_output": 7200.0,
                }
            ],
            "derived": {
                "totals": {"total_value_output": 7200.0},
            },
        }

        portfolio = build_portfolio_from_position_management_module(module, config=SimpleNamespace(portfolio_stock_tags_json=""))

        self.assertIsNotNone(portfolio)
        if portfolio is None:
            self.fail("portfolio should not be None")
        self.assertEqual(portfolio.holdings[0].market, "US")

    @patch("src.core.market_review.run_portfolio_review")
    @patch("src.core.market_review.build_portfolio_from_config")
    @patch("src.core.market_review.build_portfolio_from_position_management_module")
    @patch("src.core.market_review.PositionManagementService")
    @patch("src.core.market_review.MarketAnalyzer")
    @patch("src.core.market_review.get_config")
    def test_run_market_review_triggers_portfolio_review_when_enabled(
        self,
        mock_get_config,
        mock_market_analyzer,
        mock_position_service,
        mock_build_portfolio_from_module,
        mock_build_portfolio,
        mock_run_portfolio_review,
    ) -> None:
        notifier = _DummyNotifier()
        portfolio = object()
        mock_get_config.return_value = SimpleNamespace(
            market_review_region="cn",
            portfolio_enabled=True,
            portfolio_initial_capital=1_400_000.0,
            portfolio_target_return=0.30,
            portfolio_holdings_json='{"holdings": []}',
            portfolio_stock_tags_json="",
        )
        mock_market_analyzer.return_value.run_daily_review.return_value = "market review body"
        mock_position_service.return_value.get_module.return_value = {"module": {"holdings": [{"symbol": "NVDA"}]}}
        mock_build_portfolio_from_module.return_value = portfolio
        mock_build_portfolio.return_value = None
        mock_run_portfolio_review.return_value = "# portfolio review"

        from src.core.market_review import run_market_review

        report = run_market_review(
            notifier=notifier,
            analyzer=None,
            search_service=None,
            send_notification=False,
        )

        self.assertEqual(report, "market review body")
        mock_build_portfolio_from_module.assert_called_once()
        mock_build_portfolio.assert_not_called()
        mock_run_portfolio_review.assert_called_once_with(
            portfolio=portfolio,
            notifier=notifier,
            analyzer=None,
            send_notification=False,
        )


if __name__ == "__main__":
    unittest.main()

# -*- coding: utf-8 -*-
"""
Unit tests for Issue #234: intraday realtime technical indicators.

Covers:
- _augment_historical_with_realtime: append/update logic, guards
- _compute_ma_status: MA alignment string
- _enhance_context: today override with realtime + trend_result
"""

import os
import sys
import unittest
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from data_provider.realtime_types import UnifiedRealtimeQuote, RealtimeSource
from src.stock_analyzer import StockTrendAnalyzer, TrendAnalysisResult, TrendStatus
from src.core.pipeline import StockAnalysisPipeline
from src.enums import ReportType


def _make_realtime_quote(
    price: float = 15.72,
    open_price: float = 15.62,
    high: float = 16.29,
    low: float = 15.55,
    volume: int = 13995600,
    change_pct: float = 0.96,
) -> UnifiedRealtimeQuote:
    return UnifiedRealtimeQuote(
        code="600519",
        name="贵州茅台",
        source=RealtimeSource.TENCENT,
        price=price,
        open_price=open_price,
        high=high,
        low=low,
        volume=volume,
        change_pct=change_pct,
    )


def _make_historical_df(days: int = 25, last_date: date = None) -> pd.DataFrame:
    """Build historical OHLCV DataFrame."""
    if last_date is None:
        last_date = date.today() - timedelta(days=1)
    dates = [last_date - timedelta(days=i) for i in range(days - 1, -1, -1)]
    base = 100.0
    data = []
    for i, d in enumerate(dates):
        close = base + i * 0.5
        data.append({
            "code": "600519",
            "date": d,
            "open": close - 0.2,
            "high": close + 0.3,
            "low": close - 0.3,
            "close": close,
            "volume": 1000000 + i * 10000,
            "amount": close * (1000000 + i * 10000),
            "pct_chg": 0.5,
            "ma5": close,
            "ma10": close - 0.1,
            "ma20": close - 0.2,
            "volume_ratio": 1.0,
        })
    return pd.DataFrame(data)


class TestAugmentHistoricalWithRealtime(unittest.TestCase):
    """Tests for _augment_historical_with_realtime."""

    def setUp(self) -> None:
        self._db_path = os.path.join(
            os.path.dirname(__file__), "..", "data", "test_issue234.db"
        )
        os.makedirs(os.path.dirname(self._db_path), exist_ok=True)
        with patch.dict(os.environ, {"DATABASE_PATH": self._db_path}):
            from src.config import Config
            Config._instance = None
            self.config = Config._load_from_env()
        self.pipeline = StockAnalysisPipeline(config=self.config)

    def test_returns_unchanged_when_realtime_none(self) -> None:
        df = _make_historical_df()
        result = self.pipeline._augment_historical_with_realtime(df, None, "600519")
        self.assertIs(result, df)
        self.assertEqual(len(result), len(df))

    def test_returns_unchanged_when_price_invalid(self) -> None:
        df = _make_historical_df()
        quote = _make_realtime_quote(price=0)
        result = self.pipeline._augment_historical_with_realtime(df, quote, "600519")
        self.assertEqual(len(result), len(df))
        quote2 = MagicMock()
        quote2.price = None
        result2 = self.pipeline._augment_historical_with_realtime(df, quote2, "600519")
        self.assertEqual(len(result2), len(df))

    def test_returns_unchanged_when_df_empty(self) -> None:
        df = pd.DataFrame()
        quote = _make_realtime_quote()
        result = self.pipeline._augment_historical_with_realtime(df, quote, "600519")
        self.assertTrue(result.empty)

    def test_returns_unchanged_when_df_missing_close(self) -> None:
        df = pd.DataFrame({"date": [date.today()], "open": [100]})
        quote = _make_realtime_quote()
        result = self.pipeline._augment_historical_with_realtime(df, quote, "600519")
        self.assertEqual(len(result), 1)
        self.assertNotIn("close", result.columns)

    @patch("src.core.pipeline.is_market_open", return_value=True)
    @patch("src.core.pipeline.get_market_for_stock", return_value="cn")
    def test_appends_row_when_last_date_before_today(
        self, _mock_market, _mock_open
    ) -> None:
        df = _make_historical_df(last_date=date.today() - timedelta(days=1))
        quote = _make_realtime_quote(price=15.72)
        result = self.pipeline._augment_historical_with_realtime(df, quote, "600519")
        self.assertEqual(len(result), len(df) + 1)
        last = result.iloc[-1]
        self.assertEqual(last["close"], 15.72)
        self.assertEqual(last["date"], date.today())

    @patch("src.core.pipeline.is_market_open", return_value=True)
    @patch("src.core.pipeline.get_market_for_stock", return_value="cn")
    def test_updates_last_row_when_last_date_is_today(
        self, _mock_market, _mock_open
    ) -> None:
        df = _make_historical_df(last_date=date.today(), days=25)
        df.loc[df.index[-1], "date"] = date.today()
        quote = _make_realtime_quote(price=16.0)
        result = self.pipeline._augment_historical_with_realtime(df, quote, "600519")
        self.assertEqual(len(result), len(df))
        self.assertEqual(result.iloc[-1]["close"], 16.0)


class TestComputeMaStatus(unittest.TestCase):
    """Tests for _compute_ma_status."""

    def test_bullish_alignment(self) -> None:
        status = StockAnalysisPipeline._compute_ma_status(11, 10, 9.5, 9)
        self.assertIn("多头", status)

    def test_bearish_alignment(self) -> None:
        status = StockAnalysisPipeline._compute_ma_status(8, 9, 9.5, 10)
        self.assertIn("空头", status)

    def test_consolidation(self) -> None:
        status = StockAnalysisPipeline._compute_ma_status(10, 10, 10, 10)
        self.assertIn("震荡", status)


class TestEnhanceContextRealtimeOverride(unittest.TestCase):
    """Tests for _enhance_context today override with realtime + trend."""

    def setUp(self) -> None:
        self._db_path = os.path.join(
            os.path.dirname(__file__), "..", "data", "test_issue234.db"
        )
        os.makedirs(os.path.dirname(self._db_path), exist_ok=True)
        with patch.dict(os.environ, {"DATABASE_PATH": self._db_path}):
            from src.config import Config
            Config._instance = None
            self.config = Config._load_from_env()
        self.pipeline = StockAnalysisPipeline(config=self.config)

    def test_today_overridden_when_realtime_and_trend_exist(self) -> None:
        context = {
            "code": "600519",
            "date": (date.today() - timedelta(days=1)).isoformat(),
            "today": {"close": 15.0, "ma5": 14.8, "ma10": 14.5},
            "yesterday": {"close": 14.5, "volume": 1000000},
        }
        quote = _make_realtime_quote(price=15.72, volume=2000000)
        trend = TrendAnalysisResult(
            code="600519",
            trend_status=TrendStatus.BULL,
            ma5=15.5,
            ma10=15.2,
            ma20=14.9,
        )
        enhanced = self.pipeline._enhance_context(
            context, quote, None, trend, "贵州茅台"
        )
        self.assertEqual(enhanced["today"]["close"], 15.72)
        self.assertEqual(enhanced["today"]["ma5"], 15.5)
        self.assertEqual(enhanced["today"]["ma10"], 15.2)
        self.assertEqual(enhanced["today"]["ma20"], 14.9)
        self.assertIn("多头", enhanced["ma_status"])
        self.assertEqual(enhanced["date"], date.today().isoformat())
        self.assertIn("price_change_ratio", enhanced)
        self.assertIn("volume_change_ratio", enhanced)

    def test_today_not_overridden_when_trend_missing(self) -> None:
        context = {"code": "600519", "today": {"close": 15.0}}
        quote = _make_realtime_quote(price=15.72)
        enhanced = self.pipeline._enhance_context(
            context, quote, None, None, "贵州茅台"
        )
        self.assertEqual(enhanced["today"]["close"], 15.0)

    def test_today_not_overridden_when_realtime_missing(self) -> None:
        context = {"code": "600519", "today": {"close": 15.0}}
        trend = TrendAnalysisResult(code="600519", ma5=15.0, ma10=14.8, ma20=14.5)
        enhanced = self.pipeline._enhance_context(
            context, None, None, trend, "贵州茅台"
        )
        self.assertEqual(enhanced["today"]["close"], 15.0)

    def test_today_not_overridden_when_trend_ma_zero(self) -> None:
        """When StockTrendAnalyzer returns early (data insufficient), ma5=0.0. Must not override."""
        context = {"code": "600519", "today": {"close": 15.0, "ma5": 14.8}}
        quote = _make_realtime_quote(price=15.72)
        trend = TrendAnalysisResult(code="600519")  # defaults: ma5=ma10=ma20=0.0
        enhanced = self.pipeline._enhance_context(
            context, quote, None, trend, "贵州茅台"
        )
        self.assertEqual(enhanced["today"]["close"], 15.0)
        self.assertEqual(enhanced["today"]["ma5"], 14.8)

    def test_technical_module_passthrough(self) -> None:
        """technical_module in context should be preserved for downstream prompt/report rendering."""
        context = {
            "code": "600519",
            "today": {"close": 15.0},
            "technical_module": {
                "price_zones": {"strong_support": 14.5},
                "pattern_signals_1y": {"signals": []},
                "technical_indicators": {"overall": {"score": 70}},
            },
        }
        enhanced = self.pipeline._enhance_context(context, None, None, None, "贵州茅台")
        self.assertIn("technical_module", enhanced)
        self.assertIn("price_zones", enhanced["technical_module"])


class TestAnalyzeWithAgentTechnicalModule(unittest.TestCase):
    """Tests for technical_module population in agent analysis path."""

    def setUp(self) -> None:
        self._db_path = os.path.join(
            os.path.dirname(__file__), "..", "data", "test_issue234.db"
        )
        os.makedirs(os.path.dirname(self._db_path), exist_ok=True)
        with patch.dict(os.environ, {"DATABASE_PATH": self._db_path}):
            from src.config import Config
            Config._instance = None
            self.config = Config._load_from_env()
        self.pipeline = StockAnalysisPipeline(config=self.config)

    def test_agent_path_populates_technical_module(self) -> None:
        """Agent analysis result should include deterministic technical_module."""
        class _Bar:
            def __init__(self, payload):
                self._payload = payload

            def to_dict(self):
                return self._payload

        df = _make_historical_df(days=120)
        bars = [_Bar(row) for row in df.to_dict(orient="records")]
        self.pipeline.db.get_data_range = MagicMock(return_value=bars)
        self.pipeline.db.save_analysis_history = MagicMock(return_value=1)
        self.pipeline.search_service = MagicMock()
        self.pipeline.search_service.is_available = False
        self.pipeline.trend_analyzer.build_technical_module = MagicMock(
            return_value={"price_zones": {"strong_support": 100.0}}
        )

        executor = MagicMock()
        executor.run.return_value = MagicMock(
            success=True,
            provider="openai",
            error=None,
            dashboard={
                "sentiment_score": 55,
                "trend_prediction": "震荡",
                "operation_advice": "观望",
                "analysis_summary": "test",
            },
        )

        with patch("src.agent.factory.build_agent_executor", return_value=executor):
            result = self.pipeline._analyze_with_agent(
                code="600519",
                report_type=ReportType.FULL,
                query_id="qid-agent-tech-module",
                stock_name="贵州茅台",
                realtime_quote=None,
                chip_data=None,
            )

        self.assertIsNotNone(result)
        self.assertIsNotNone(result.technical_module)
        self.assertIn("price_zones", result.technical_module)


class TestFetchAndSaveStockDataBackfill(unittest.TestCase):
    """Tests for backfilling long history when technical-module bars are insufficient."""

    def setUp(self) -> None:
        self._db_path = os.path.join(
            os.path.dirname(__file__), "..", "data", "test_issue234.db"
        )
        os.makedirs(os.path.dirname(self._db_path), exist_ok=True)
        with patch.dict(os.environ, {"DATABASE_PATH": self._db_path}):
            from src.config import Config
            Config._instance = None
            self.config = Config._load_from_env()
        self.pipeline = StockAnalysisPipeline(config=self.config)

    def test_backfills_when_today_exists_but_history_insufficient(self) -> None:
        """If only short history exists, fetch_and_save_stock_data should trigger a backfill fetch."""
        self.pipeline.db.has_today_data = MagicMock(return_value=True)
        self.pipeline.db.get_data_range = MagicMock(return_value=[object()] * 42)
        self.pipeline.db.save_daily_data = MagicMock(return_value=42)
        self.pipeline.fetcher_manager.get_daily_data = MagicMock(
            return_value=(
                pd.DataFrame(
                    [
                        {
                            "date": date.today(),
                            "open": 1.0,
                            "high": 1.0,
                            "low": 1.0,
                            "close": 1.0,
                            "volume": 1.0,
                            "amount": 1.0,
                            "pct_chg": 0.0,
                        }
                    ]
                ),
                "MockFetcher",
            )
        )

        ok, err = self.pipeline.fetch_and_save_stock_data("NVDA", force_refresh=False)

        self.assertTrue(ok)
        self.assertIsNone(err)
        self.pipeline.db.get_data_range.assert_called_once()
        self.pipeline.fetcher_manager.get_daily_data.assert_called_once()
        self.pipeline.db.save_daily_data.assert_called_once()

    def test_skip_fetch_when_today_exists_and_history_sufficient(self) -> None:
        """If history is sufficient, should skip network fetch when today's data already exists."""
        self.pipeline.db.has_today_data = MagicMock(return_value=True)
        self.pipeline.db.get_data_range = MagicMock(return_value=[object()] * 260)
        self.pipeline.db.save_daily_data = MagicMock(return_value=0)
        self.pipeline.fetcher_manager.get_daily_data = MagicMock()

        ok, err = self.pipeline.fetch_and_save_stock_data("MSFT", force_refresh=False)

        self.assertTrue(ok)
        self.assertIsNone(err)
        self.pipeline.db.get_data_range.assert_called_once()
        self.pipeline.fetcher_manager.get_daily_data.assert_not_called()
        self.pipeline.db.save_daily_data.assert_not_called()


if __name__ == "__main__":
    unittest.main()

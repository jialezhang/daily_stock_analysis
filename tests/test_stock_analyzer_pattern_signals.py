# -*- coding: utf-8 -*-
"""Unit tests for excel-driven pattern signal overrides."""

import unittest
from unittest.mock import patch

from src.stock_analyzer import (
    BuySignal,
    MACDStatus,
    RSIStatus,
    StockTrendAnalyzer,
    TrendAnalysisResult,
    TrendStatus,
    VolumeStatus,
)


def _make_result() -> TrendAnalysisResult:
    """Build a minimal analysis result for pattern override checks."""
    return TrendAnalysisResult(
        code="000001",
        trend_status=TrendStatus.CONSOLIDATION,
        trend_strength=50,
        ma5=10.0,
        ma10=9.9,
        ma20=9.8,
        current_price=10.0,
        bias_ma5=0.2,
        bias_ma10=0.1,
        bias_ma20=0.1,
        volume_status=VolumeStatus.NORMAL,
        volume_ratio_5d=1.0,
        support_ma5=False,
        support_ma10=False,
        macd_status=MACDStatus.BULLISH,
        macd_signal="neutral",
        rsi_status=RSIStatus.NEUTRAL,
        rsi_signal="neutral",
    )


class StockAnalyzerPatternSignalTestCase(unittest.TestCase):
    """Tests for stop-fall/top pattern matching and action overrides."""

    def setUp(self) -> None:
        self.analyzer = StockTrendAnalyzer()

    @patch("src.stock_analyzer.get_config")
    def test_bottom_pattern_hit_overrides_to_buy(self, mock_get_config) -> None:
        """Bottom pattern hit should produce buy-oriented advice."""
        mock_get_config.return_value.bias_threshold = 5.0
        result = _make_result()
        result.bottom_pattern_hits = ["启明星(成交量+RSI+MACD)"]

        self.analyzer._generate_signal(result)

        self.assertIn(result.buy_signal, [BuySignal.BUY, BuySignal.STRONG_BUY])
        self.assertTrue(any("命中止跌组合" in reason for reason in result.signal_reasons))
        self.assertIn("分批买入", result.pattern_advice)

    @patch("src.stock_analyzer.get_config")
    def test_top_pattern_hit_overrides_to_sell(self, mock_get_config) -> None:
        """Top pattern hit should force sell-oriented advice."""
        mock_get_config.return_value.bias_threshold = 5.0
        result = _make_result()
        result.top_pattern_hits = ["看跌吞没(成交量+CCI+Boll)"]

        self.analyzer._generate_signal(result)

        self.assertIn(result.buy_signal, [BuySignal.SELL, BuySignal.STRONG_SELL])
        self.assertTrue(any("命中见顶组合" in risk for risk in result.risk_factors))
        self.assertIn("卖出", result.pattern_advice)

    def test_parse_indicator_combo(self) -> None:
        """Indicator combo parser should normalize tokens from excel text."""
        combo = "成交量 + CCI + Boll"
        parsed = self.analyzer._parse_indicator_combo(combo)
        self.assertEqual(parsed, ["成交量", "CCI", "Boll"])

    def test_pattern_rules_load(self) -> None:
        """Pattern rules should be available even when excel load fails."""
        rules = self.analyzer.pattern_rules
        self.assertGreaterEqual(len(rules.get("bottom", [])), 5)
        self.assertGreaterEqual(len(rules.get("top", [])), 5)


if __name__ == "__main__":
    unittest.main()

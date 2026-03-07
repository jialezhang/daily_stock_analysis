# -*- coding: utf-8 -*-
"""Tests for technical module generation in StockTrendAnalyzer."""

import unittest
import numpy as np
import pandas as pd

from src.stock_analyzer import StockTrendAnalyzer


def _make_ohlcv_df(days: int = 320) -> pd.DataFrame:
    """Build synthetic daily OHLCV data with trend + oscillation."""
    np.random.seed(7)
    dates = pd.date_range(end=pd.Timestamp.today().normalize(), periods=days, freq="B")
    base = np.linspace(100, 140, days)
    wave = 4 * np.sin(np.linspace(0, 12 * np.pi, days))
    noise = np.random.normal(0, 0.8, days)
    close = base + wave + noise
    open_ = close + np.random.normal(0, 0.6, days)
    high = np.maximum(open_, close) + np.abs(np.random.normal(0.9, 0.4, days))
    low = np.minimum(open_, close) - np.abs(np.random.normal(0.9, 0.4, days))
    volume = np.random.randint(2_000_000, 8_000_000, days)

    return pd.DataFrame(
        {
            "date": dates.date,
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        }
    )


class StockAnalyzerTechnicalModuleTestCase(unittest.TestCase):
    """Validate technical module structure and core fields."""

    def setUp(self) -> None:
        self.analyzer = StockTrendAnalyzer()
        self.df = _make_ohlcv_df()

    def test_build_technical_module_contains_required_sections(self) -> None:
        """Technical module should contain price zones, pattern signals and indicators."""
        module = self.analyzer.build_technical_module(self.df, code="TEST")

        self.assertIsInstance(module, dict)
        self.assertIn("price_zones", module)
        self.assertIn("pattern_signals_1y", module)
        self.assertIn("technical_indicators", module)

    def test_indicator_scores_are_bounded(self) -> None:
        """RSI/ASR/CC scores should be numeric and in [0, 100]."""
        module = self.analyzer.build_technical_module(self.df, code="TEST")
        indicators = module.get("technical_indicators", {})

        for key in ["rsi", "asr", "cc", "sar", "macd", "kdj", "bias", "kc", "bbiboll", "magic_nine_turn", "overall"]:
            score = indicators.get(key, {}).get("score")
            self.assertIsNotNone(score, f"missing score for {key}")
            self.assertGreaterEqual(score, 0)
            self.assertLessEqual(score, 100)

    def test_extended_indicators_have_explanation_and_rich_result(self) -> None:
        """New technical indicators should provide explanation and recent interpretation."""
        module = self.analyzer.build_technical_module(self.df, code="TEST")
        indicators = module.get("technical_indicators", {})

        for key in ["sar", "macd", "kdj", "bias", "kc", "bbiboll", "magic_nine_turn"]:
            item = indicators.get(key, {})
            self.assertIn("explanation", item, f"{key} missing explanation")
            self.assertIn("result", item, f"{key} missing result")
            self.assertTrue(str(item.get("explanation", "")).strip())
            # result should be an interpretation sentence, not empty/simple placeholder
            self.assertGreaterEqual(len(str(item.get("result", "")).strip()), 6)

    def test_pattern_signal_entries_have_date_and_type(self) -> None:
        """Signal history entries should contain date/type/patterns fields."""
        module = self.analyzer.build_technical_module(self.df, code="TEST")
        signals = module.get("pattern_signals_1y", {}).get("signals", [])
        for item in signals:
            self.assertIn("date", item)
            self.assertIn("signal_type", item)
            self.assertIn("patterns", item)
            self.assertIn("signal_strength", item)
            self.assertIn("signal_strength_score", item)
            self.assertIn("future_7d_return_pct", item)
            self.assertIn("future_30d_return_pct", item)
            self.assertIn("future_7d_effective_days", item)
            self.assertIn("future_30d_effective_days", item)

    def test_price_zones_include_multiple_box_clusters(self) -> None:
        """Price zones should expose multiple clustered boxes, not only one static range."""
        module = self.analyzer.build_technical_module(self.df, code="TEST")
        price_zones = module.get("price_zones", {})
        multi_boxes = price_zones.get("multi_boxes", [])

        self.assertIsInstance(multi_boxes, list)
        self.assertGreaterEqual(len(multi_boxes), 2)
        for box in multi_boxes:
            self.assertIn("low", box)
            self.assertIn("high", box)
            self.assertIn("strength_score", box)
            self.assertIn("logic", box)
            self.assertLess(float(box["low"]), float(box["high"]))

    def test_rhino_price_zones_exist_and_are_sorted(self) -> None:
        """Rhino zones should include upper/lower/strength and keep descending upper order."""
        module = self.analyzer.build_technical_module(self.df, code="TEST")
        rhino_zones = module.get("price_zones", {}).get("rhino_zones", [])
        self.assertIsInstance(rhino_zones, list)
        self.assertGreaterEqual(len(rhino_zones), 1)

        uppers = [float(item.get("upper", 0)) for item in rhino_zones]
        self.assertEqual(uppers, sorted(uppers, reverse=True))

        for item in rhino_zones:
            self.assertGreater(float(item.get("upper", 0)), float(item.get("lower", 0)))
            self.assertIn(item.get("strength_level"), ["弱", "中", "强", "超强"])
            self.assertIn("strength_score", item)
            self.assertIn("source_type", item)

    def test_price_zone_box_contains_key_level_evidence(self) -> None:
        """Each zone should include detailed key-level evidence for auditability."""
        module = self.analyzer.build_technical_module(self.df, code="TEST")
        multi_boxes = module.get("price_zones", {}).get("multi_boxes", [])
        self.assertGreaterEqual(len(multi_boxes), 1)

        for box in multi_boxes:
            key_levels = box.get("key_levels", [])
            self.assertIsInstance(key_levels, list)
            self.assertGreaterEqual(len(key_levels), 1)
            self.assertEqual(int(box.get("source_count", 0)), len(key_levels))
            for item in key_levels:
                self.assertIn("price", item)
                self.assertIn("origins", item)
                self.assertIsInstance(item.get("origins"), list)
                self.assertGreaterEqual(len(item.get("origins", [])), 1)


if __name__ == "__main__":
    unittest.main()

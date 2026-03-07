# -*- coding: utf-8 -*-
"""Unit tests for history refresh merge behavior."""

import json
import unittest
from types import SimpleNamespace

from src.services.history_service import HistoryService


class HistoryRefreshMergeTestCase(unittest.TestCase):
    """Verify merge rules for full/partial refresh."""

    def setUp(self) -> None:
        self.service = HistoryService.__new__(HistoryService)

    def test_full_refresh_keeps_old_rhino_zones(self) -> None:
        target = SimpleNamespace(
            raw_result=json.dumps(
                {
                    "technical_module": {
                        "price_zones": {
                            "rhino_zones": [{"name": "old", "upper": 200, "lower": 190}],
                            "current_price": 195,
                        },
                    },
                }
            ),
            context_snapshot=json.dumps(
                {
                    "enhanced_context": {
                        "technical_module": {
                            "price_zones": {
                                "rhino_zones": [{"name": "ctx-old", "upper": 201, "lower": 191}],
                            }
                        }
                    }
                }
            ),
            sentiment_score=60,
            operation_advice="持有",
            trend_prediction="中性",
            analysis_summary="old summary",
            news_content="old news",
            ideal_buy=100.0,
            secondary_buy=95.0,
            stop_loss=90.0,
            take_profit=120.0,
        )
        fresh = SimpleNamespace(
            raw_result=json.dumps(
                {
                    "technical_module": {
                        "price_zones": {
                            "rhino_zones": [{"name": "new", "upper": 300, "lower": 280}],
                            "current_price": 290,
                        },
                    },
                }
            ),
            context_snapshot=json.dumps(
                {
                    "enhanced_context": {
                        "technical_module": {
                            "price_zones": {
                                "rhino_zones": [{"name": "ctx-new", "upper": 310, "lower": 300}],
                            }
                        }
                    }
                }
            ),
            sentiment_score=75,
            operation_advice="买入",
            trend_prediction="上行",
            analysis_summary="new summary",
            news_content="new news",
            ideal_buy=150.0,
            secondary_buy=145.0,
            stop_loss=130.0,
            take_profit=180.0,
        )

        updates = self.service._build_refresh_updates(
            target_record=target,
            fresh_record=fresh,
            mode="full",
            modules=[],
        )

        merged_raw = json.loads(updates["raw_result"])
        rhino = merged_raw["technical_module"]["price_zones"]["rhino_zones"]
        self.assertEqual(rhino[0]["name"], "old")
        self.assertEqual(updates["operation_advice"], "买入")
        self.assertEqual(updates["analysis_summary"], "new summary")

        merged_ctx = json.loads(updates["context_snapshot"])
        ctx_rhino = merged_ctx["enhanced_context"]["technical_module"]["price_zones"]["rhino_zones"]
        self.assertEqual(ctx_rhino[0]["name"], "ctx-old")

    def test_partial_refresh_only_updates_selected_modules(self) -> None:
        target = SimpleNamespace(
            raw_result=json.dumps(
                {
                    "technical_module": {
                        "price_zones": {"rhino_zones": [{"name": "old-rhino"}], "strong_support": 100},
                        "pattern_signals_1y": {"bottom_count": 1},
                        "technical_indicators": {"rsi": {"score": 40, "result": "old"}},
                    }
                }
            ),
            context_snapshot=json.dumps({}),
            sentiment_score=50,
            operation_advice="观望",
            trend_prediction="震荡",
            analysis_summary="old",
            news_content="old",
            ideal_buy=10.0,
            secondary_buy=9.0,
            stop_loss=8.0,
            take_profit=12.0,
        )
        fresh = SimpleNamespace(
            raw_result=json.dumps(
                {
                    "technical_module": {
                        "price_zones": {"rhino_zones": [{"name": "new-rhino"}], "strong_support": 200},
                        "pattern_signals_1y": {"bottom_count": 9},
                        "technical_indicators": {"rsi": {"score": 80, "result": "new"}},
                    }
                }
            ),
            context_snapshot=json.dumps({}),
            sentiment_score=88,
            operation_advice="买入",
            trend_prediction="强势",
            analysis_summary="new",
            news_content="new",
            ideal_buy=20.0,
            secondary_buy=19.0,
            stop_loss=18.0,
            take_profit=25.0,
        )

        updates = self.service._build_refresh_updates(
            target_record=target,
            fresh_record=fresh,
            mode="partial",
            modules=["technical_indicators"],
        )
        merged_raw = json.loads(updates["raw_result"])
        module = merged_raw["technical_module"]
        self.assertEqual(module["technical_indicators"]["rsi"]["score"], 80)
        self.assertEqual(module["pattern_signals_1y"]["bottom_count"], 1)
        self.assertEqual(module["price_zones"]["strong_support"], 100)
        self.assertNotIn("operation_advice", updates)

    def test_partial_price_zone_refresh_still_keeps_old_rhino(self) -> None:
        target = SimpleNamespace(
            raw_result=json.dumps(
                {
                    "technical_module": {
                        "price_zones": {
                            "rhino_zones": [{"name": "old-rhino"}],
                            "strong_support": 101,
                        }
                    }
                }
            ),
            context_snapshot=json.dumps({}),
            sentiment_score=50,
            operation_advice="观望",
            trend_prediction="震荡",
            analysis_summary="old",
            news_content="old",
            ideal_buy=10.0,
            secondary_buy=9.0,
            stop_loss=8.0,
            take_profit=12.0,
        )
        fresh = SimpleNamespace(
            raw_result=json.dumps(
                {
                    "technical_module": {
                        "price_zones": {
                            "rhino_zones": [{"name": "new-rhino"}],
                            "strong_support": 202,
                        }
                    }
                }
            ),
            context_snapshot=json.dumps({}),
            sentiment_score=70,
            operation_advice="买入",
            trend_prediction="上行",
            analysis_summary="new",
            news_content="new",
            ideal_buy=20.0,
            secondary_buy=19.0,
            stop_loss=18.0,
            take_profit=25.0,
        )

        updates = self.service._build_refresh_updates(
            target_record=target,
            fresh_record=fresh,
            mode="partial",
            modules=["price_zones"],
        )
        merged_raw = json.loads(updates["raw_result"])
        price_zones = merged_raw["technical_module"]["price_zones"]
        self.assertEqual(price_zones["strong_support"], 202)
        self.assertEqual(price_zones["rhino_zones"][0]["name"], "old-rhino")

    def test_full_refresh_keeps_position_management_module(self) -> None:
        target = SimpleNamespace(
            raw_result=json.dumps(
                {
                    "position_management": {
                        "target": {"annual_return_target_pct": 30, "base_currency": "USD"},
                        "holdings": [
                            {
                                "market_type": "us",
                                "asset_class": "美股",
                                "symbol": "NVDA",
                                "quantity": 10,
                                "avg_cost": 100,
                                "current_price": 120,
                                "currency": "USD",
                            }
                        ],
                    },
                }
            ),
            context_snapshot=json.dumps({"enhanced_context": {}}),
            code="NVDA",
            name="NVIDIA",
            sentiment_score=50,
            operation_advice="观望",
            trend_prediction="震荡",
            analysis_summary="old",
            news_content="old",
            ideal_buy=10.0,
            secondary_buy=9.0,
            stop_loss=8.0,
            take_profit=12.0,
        )
        fresh = SimpleNamespace(
            raw_result=json.dumps({"technical_module": {"price_zones": {"strong_support": 200}}}),
            context_snapshot=json.dumps({"enhanced_context": {}}),
            sentiment_score=70,
            operation_advice="买入",
            trend_prediction="上行",
            analysis_summary="new",
            news_content="new",
            ideal_buy=20.0,
            secondary_buy=19.0,
            stop_loss=18.0,
            take_profit=25.0,
        )

        updates = self.service._build_refresh_updates(
            target_record=target,
            fresh_record=fresh,
            mode="full",
            modules=[],
        )
        merged_raw = json.loads(updates["raw_result"])
        self.assertIn("position_management", merged_raw)
        self.assertEqual(merged_raw["position_management"]["holdings"][0]["symbol"], "NVDA")


if __name__ == "__main__":
    unittest.main()

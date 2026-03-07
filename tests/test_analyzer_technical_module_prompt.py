# -*- coding: utf-8 -*-
"""Prompt formatting test for technical module section."""

import unittest

from src.analyzer import GeminiAnalyzer


class AnalyzerTechnicalModulePromptTestCase(unittest.TestCase):
    """Ensure prompt includes the technical module section when present."""

    def test_prompt_contains_technical_module_block(self) -> None:
        analyzer = GeminiAnalyzer.__new__(GeminiAnalyzer)
        context = {
            "code": "600519",
            "date": "2026-02-27",
            "today": {"close": 1500, "open": 1490, "high": 1510, "low": 1485},
            "technical_module": {
                "price_zones": {
                    "strong_support": 1450.0,
                    "weak_support": 1420.0,
                    "strong_resistance": 1530.0,
                    "weak_resistance": 1560.0,
                },
                "pattern_signals_1y": {
                    "signals": [
                        {
                            "date": "2026-02-03",
                            "signal_type": "止跌(买入)",
                            "patterns": ["启明星(成交量+RSI+MACD)"],
                        }
                    ]
                },
                "technical_indicators": {
                    "rsi": {"value": 54.2, "score": 72, "result": "中性偏强"},
                    "asr": {"value": 3.8, "score": 80, "result": "波动适中"},
                    "cc": {"value": -22.0, "score": 70, "result": "中性"},
                    "macd": {"value": {"dif": 0.2, "dea": 0.1, "bar": 0.2}, "score": 75, "result": "金叉后红柱扩张，短线偏多"},
                    "kdj": {"value": {"k": 55, "d": 48, "j": 69}, "score": 78, "result": "K上穿D，短线动能转强"},
                    "sar": {"value": 1480.0, "score": 74, "result": "价格在SAR上方，趋势维持偏多"},
                    "bias": {"value": {"bias6": 1.2, "bias12": 0.8, "bias24": 0.5}, "score": 68, "result": "乖离温和，未见明显追高"},
                    "kc": {"value": {"upper": 1520, "mid": 1500, "lower": 1480}, "score": 66, "result": "位于通道中上轨，趋势正常偏强"},
                    "bbiboll": {"value": {"bbi": 1498, "upper": 1530, "lower": 1468}, "score": 67, "result": "运行在BBI上方，趋势偏多"},
                    "magic_nine_turn": {"value": {"buy_count": 0, "sell_count": 6}, "score": 45, "result": "卖出九转进行到6，注意短线衰竭风险"},
                    "overall": {"score": 74, "result": "技术面偏多"},
                },
            },
        }

        prompt = analyzer._format_prompt(context, "贵州茅台", news_context=None)
        self.assertIn("技术面增强模块", prompt)
        self.assertIn("强支撑", prompt)
        self.assertIn("止跌/见顶信号", prompt)
        self.assertIn("MACD", prompt)
        self.assertIn("KDJ", prompt)


if __name__ == "__main__":
    unittest.main()

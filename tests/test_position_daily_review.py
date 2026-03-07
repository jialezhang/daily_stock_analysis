# -*- coding: utf-8 -*-
"""Tests for daily position review flow."""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from src.core.position_review import (
    _extract_review_sections,
    list_position_reviews,
    run_position_daily_review,
    upsert_position_review_note,
)


class _DummyNotifier:
    def __init__(self) -> None:
        self.sent = []
        self.saved = []

    def send_to_telegram(self, content: str) -> bool:
        self.sent.append(content)
        return True

    def save_report_to_file(self, content: str, filename: str) -> str:
        self.saved.append((filename, content))
        return f"/tmp/{filename}"


class _DummyAnalyzer:
    def __init__(self) -> None:
        self.last_prompt = None

    def _call_openai_api(self, prompt: str, generation_config: dict) -> str:
        self.last_prompt = prompt
        return "建议：控制单一二级资产集中度，分批调仓。"


class PositionDailyReviewTestCase(unittest.TestCase):
    """Verify daily position review generation and telegram push."""

    @patch("src.core.position_review.PositionManagementService.get_module")
    @patch("src.core.position_review._fetch_benchmark_return_pct")
    @patch("src.core.position_review._estimate_range_low_high")
    def test_run_position_daily_review_contains_structured_sections(
        self,
        mock_estimate_range,
        mock_benchmark,
        mock_get_module,
    ) -> None:
        mock_benchmark.side_effect = [5.2, 11.7]
        mock_estimate_range.return_value = (100.0, 130.0)
        mock_get_module.return_value = {
            "updated": True,
            "module": {
                "updated_at": "2026-03-02T00:00:00",
                "target": {
                    "initial_position": 100000,
                    "output_currency": "USD",
                    "target_return_pct": 30,
                },
                "derived": {
                    "totals": {
                        "total_value_output": 118000,
                        "profit_pct": 18,
                    },
                    "target_progress": {
                        "gap_to_target_output": 12000,
                    },
                    "secondary_allocation": [
                        {"asset_secondary": "美股", "value_output": 65000, "ratio_pct": 55.08},
                        {"asset_secondary": "ETF", "value_output": 28000, "ratio_pct": 23.73},
                    ],
                },
                "holdings": [
                    {
                        "symbol": "NVDA",
                        "quote_symbol": "NVDA",
                        "asset_primary": "权益类",
                        "asset_secondary": "美股",
                        "latest_price": 120.0,
                        "change_pct": 3.5,
                        "market_value_output": 65000.0,
                        "daily_pnl_output": 820.0,
                    },
                    {
                        "symbol": "BABA",
                        "quote_symbol": "BABA",
                        "asset_primary": "权益类",
                        "asset_secondary": "美股",
                        "latest_price": 85.0,
                        "change_pct": -1.2,
                        "market_value_output": 28000.0,
                        "daily_pnl_output": -120.0,
                    },
                ],
                "macro_events": ["中东冲突升级", "美联储降息预期反复"],
            },
            "message": "读取成功",
        }

        notifier = _DummyNotifier()
        analyzer = _DummyAnalyzer()

        report = run_position_daily_review(
            notifier=notifier,
            analyzer=analyzer,
            market_report="美股波动抬升，风险偏好回落。",
            send_notification=True,
        )

        self.assertIsNotNone(report)
        text = report or ""
        self.assertIn("### 🌪️ 宏观与跨市场风向", text)
        self.assertIn("### 📊 组合偏离度与目标追踪", text)
        self.assertIn("### 💡 行动与网格策略建议", text)
        self.assertIn("风险预警", text)
        self.assertIn("网格/区间操作参考", text)
        self.assertEqual(len(notifier.sent), 1)

    def test_extract_review_sections_supports_legacy_format(self) -> None:
        legacy_markdown = """## 2026-03-02 每日仓位复盘

### 二级分类资产分布
| 二级分类 | 总价值(CNY) | 占比 |
|---|---:|---:|
| 美股 | 100 | 50% |

### 目标与进度
- 当前收益率: 8%
- 年度目标收益率: 30%

### AI 资产配置建议
- 保持分散，控制单一资产仓位。
- 波动加大时按区间做分批交易。
"""
        sections = _extract_review_sections(legacy_markdown)
        self.assertTrue(sections["macro_cross_market"])
        self.assertTrue(sections["target_tracking"])
        self.assertIn("保持分散", sections["risk_warning"])

    def test_upsert_note_and_load_history(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            reports_dir = Path(tmp_dir) / "reports"
            notes_file = Path(tmp_dir) / "data" / "position_review_notes.json"
            reports_dir.mkdir(parents=True, exist_ok=True)
            (reports_dir / "position_review_20260301.md").write_text(
                "## 2026-03-01 每日资产管理复盘\n\n### 🌪️ 宏观与跨市场风向\nA\n\n### 📊 组合偏离度与目标追踪\nB\n\n### 💡 行动与网格策略建议\n- **风险预警**：C\n- **网格/区间操作参考**：D\n",
                encoding="utf-8",
            )
            with patch("src.core.position_review.REPORTS_DIR", reports_dir), patch(
                "src.core.position_review.REVIEW_NOTES_FILE", notes_file
            ):
                upsert_result = upsert_position_review_note("2026-03-01", "这是测试批注")
                self.assertEqual(upsert_result["review_date"], "2026-03-01")
                history = list_position_reviews(limit=10)
                self.assertEqual(len(history), 1)
                self.assertEqual(history[0]["note"], "这是测试批注")


if __name__ == "__main__":
    unittest.main()

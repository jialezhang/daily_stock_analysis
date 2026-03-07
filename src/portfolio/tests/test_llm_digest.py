# -*- coding: utf-8 -*-
"""Tests for portfolio LLM digest generation."""

from src.portfolio.models import (
    AnomalyAlert,
    HealthReport,
    Portfolio,
    RebalancePlan,
    RegimeResult,
    SectorAnalysis,
    TradeAction,
)
from src.portfolio.report.llm_digest import FALLBACK_DIGEST, generate_portfolio_llm_digest


def _sample_inputs():
    portfolio = Portfolio(total_value_cny=1_250_000.0)
    health = HealthReport(score=78, grade="B")
    regimes = [RegimeResult(market="US", regime="balanced"), RegimeResult(market="A", regime="aggressive")]
    sector_analysis = SectorAnalysis(us_style="offensive", a_theme="ai")
    plan = RebalancePlan(
        date="2026-03-07",
        total_asset_cny=1_250_000.0,
        actions=[
            TradeAction(
                direction="SELL",
                ticker="00700",
                name="Tencent",
                market="HK",
                current_value_cny=300_000.0,
                current_pct=24.0,
                target_pct=20.0,
                trade_amount_cny=-30_000.0,
                reason="Reduce concentration",
                priority=1,
                urgency="today",
            )
        ],
    )
    anomalies = [AnomalyAlert(level="YELLOW", name="集中度超限", message="腾讯偏高", action="减仓 00700")]
    return portfolio, health, regimes, sector_analysis, plan, anomalies


def test_generate_portfolio_llm_digest_uses_generate_text_when_available() -> None:
    class _Analyzer:
        def generate_text(self, prompt: str, max_tokens: int, temperature: float) -> str:
            assert "Health score: 78 (B)" in prompt
            assert max_tokens == 1000
            assert temperature == 0.3
            return "- 核心矛盾：腾讯过重\n- 行动：先减仓"

    digest = generate_portfolio_llm_digest(*_sample_inputs(), analyzer=_Analyzer())

    assert "核心矛盾" in digest


def test_generate_portfolio_llm_digest_falls_back_to_call_api_with_retry() -> None:
    class _Analyzer:
        def _call_api_with_retry(self, prompt: str, generation_config: dict) -> str:
            assert "Return 3-5 concise bullet points in Chinese." in prompt
            assert generation_config["temperature"] == 0.3
            assert generation_config["max_output_tokens"] == 1000
            return "- 风险：集中度偏高\n- 动作：降仓"

    digest = generate_portfolio_llm_digest(*_sample_inputs(), analyzer=_Analyzer())

    assert "风险" in digest


def test_generate_portfolio_llm_digest_returns_fallback_on_empty_response() -> None:
    class _Analyzer:
        def _call_api_with_retry(self, prompt: str, generation_config: dict) -> str:
            del prompt, generation_config
            return ""

    digest = generate_portfolio_llm_digest(*_sample_inputs(), analyzer=_Analyzer())

    assert digest == FALLBACK_DIGEST

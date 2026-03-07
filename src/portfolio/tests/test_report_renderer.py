# -*- coding: utf-8 -*-
"""Tests for portfolio report markdown rendering."""

from src.portfolio.models import (
    HealthReport,
    Portfolio,
    PortfolioHolding,
    RebalancePlan,
    RegimeResult,
    SectorAnalysis,
    TradeAction,
)
from src.portfolio.report.renderer import render_portfolio_report


def test_render_portfolio_report_includes_market_rows_in_sector_block() -> None:
    portfolio = Portfolio(
        total_value_cny=1_200_000.0,
        holdings=[
            PortfolioHolding(ticker="NVDA", name="NVIDIA", market="US", value_cny=300_000.0, weight_pct=25.0),
            PortfolioHolding(ticker="00700", name="Tencent", market="HK", value_cny=250_000.0, weight_pct=20.0),
        ],
    )
    health = HealthReport(score=76, grade="B")
    regimes = [
        RegimeResult(market="US", regime_label="谨慎", total_score=-2),
        RegimeResult(market="HK", regime_label="进攻", total_score=3),
        RegimeResult(market="A", regime_label="平衡", total_score=0),
    ]
    sector = SectorAnalysis(
        us_leaders=[
            {"name": "Technology", "ticker": "XLK", "style": "offensive", "rs": 1.2},
            {"name": "Semiconductor", "ticker": "SMH", "style": "offensive", "rs": 1.1},
        ],
        us_laggards=[
            {"name": "Utilities", "ticker": "XLU", "style": "defensive", "rs": -0.4},
        ],
        us_style="offensive",
        us_style_reasoning="美股领涨前三板块集中在进攻风格。",
        a_leaders=[
            {"name": "电子", "change_pct": 3.2},
            {"name": "通信", "change_pct": 2.6},
        ],
        a_laggards=[
            {"name": "银行", "change_pct": -1.2},
        ],
        a_theme="ai",
        a_theme_reasoning="A 股主线集中在 AI 产业链。",
        hk_tech_vs_hsi=2.4,
        hk_style="tech_leading",
    )
    plan = RebalancePlan(
        date="2026-03-07",
        total_asset_cny=1_200_000.0,
        actions=[
            TradeAction(
                direction="SELL",
                ticker="NVDA",
                name="NVIDIA",
                market="US",
                current_value_cny=300_000.0,
                current_pct=25.0,
                target_pct=20.0,
                trade_amount_cny=-50_000.0,
                reason="US 当前超配，优先减持高波动个股。",
                priority=1,
                urgency="today",
            )
        ],
    )

    report = render_portfolio_report(portfolio, health, regimes, sector, plan, [], "- 测试摘要")

    assert "### 美股" in report
    assert "- 环境：谨慎 (-2)" in report
    assert "- 领涨板块：科技（XLK，RS 1.20）；半导体（SMH，RS 1.10）" in report
    assert "### 港股" in report
    assert "- 主线：科技领涨" in report
    assert "### A 股" in report
    assert "- 领涨行业：电子(+3.20%)；通信(+2.60%)" in report


def test_render_portfolio_report_uses_selected_output_currency() -> None:
    portfolio = Portfolio(
        total_value_cny=720_000.0,
        initial_capital=700_000.0,
        target_value=770_000.0,
        output_currency="USD",
        output_to_cny_rate=7.0,
        holdings=[
            PortfolioHolding(ticker="NVDA", name="NVIDIA", market="US", value_cny=350_000.0, weight_pct=48.61),
        ],
    )
    health = HealthReport(score=76, grade="B")
    regimes = [RegimeResult(market="US", regime_label="谨慎", total_score=-2)]
    sector = SectorAnalysis()
    plan = RebalancePlan(date="2026-03-07", total_asset_cny=720_000.0, actions=[])

    report = render_portfolio_report(portfolio, health, regimes, sector, plan, [], "- 测试摘要")

    assert "- 当前资产：102857.14 USD" in report
    assert "- 目标资产：110000.00 USD" in report
    assert "- NVDA | US | 50000.00 USD" in report

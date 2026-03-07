# -*- coding: utf-8 -*-
"""Tests for portfolio health check."""

from src.portfolio.analysis.health_check import evaluate_health
from src.portfolio.models import Portfolio, PortfolioHolding


def _holding(
    ticker: str,
    market: str,
    value_cny: float,
    weight_pct: float,
    *,
    style: str = "tech_growth",
    beta_level: str = "medium",
) -> PortfolioHolding:
    return PortfolioHolding(
        ticker=ticker,
        name=ticker,
        market=market,
        value_cny=value_cny,
        weight_pct=weight_pct,
        style=style,
        beta_level=beta_level,
    )


def test_health_check_flags_critical_allocation_and_style_concentration() -> None:
    portfolio = Portfolio(
        total_value_cny=1_400_000,
        cash_cny=84_000,
        holdings=[
            _holding("NVDA", "US", 500_000, 35.71, beta_level="very_high"),
            _holding("MSFT", "US", 350_000, 25.00),
            _holding("GOOGL", "US", 250_000, 17.86),
            _holding("00700", "HK", 216_000, 15.43),
        ],
    )

    report = evaluate_health(portfolio)

    titles = {issue.title for issue in report.issues}
    assert report.score <= 70
    assert "市场配置偏离过大" in titles
    assert "风格集中度过高" in titles
    assert any(issue.severity == "CRITICAL" for issue in report.issues)


def test_health_check_balanced_portfolio_scores_high() -> None:
    portfolio = Portfolio(
        total_value_cny=1_400_000,
        cash_cny=140_000,
        holdings=[
            _holding("NVDA", "US", 210_000, 15.0, style="tech_growth"),
            _holding("MSFT", "US", 210_000, 15.0, style="tech_growth"),
            _holding("00700", "HK", 280_000, 20.0, style="china_tech"),
            _holding("09988", "HK", 140_000, 10.0, style="china_tech"),
            _holding("600519", "A", 140_000, 10.0, style="consumer"),
            _holding("300750", "A", 140_000, 10.0, style="manufacturing"),
            _holding("BTC", "CRYPTO", 70_000, 5.0, style="alternative", beta_level="very_high"),
        ],
    )

    report = evaluate_health(portfolio)

    assert report.score >= 80
    assert report.grade == "A"


def test_health_check_flags_critical_low_cash() -> None:
    portfolio = Portfolio(
        total_value_cny=1_000_000,
        cash_cny=20_000,
        holdings=[
            _holding("NVDA", "US", 490_000, 49.0, beta_level="very_high"),
            _holding("00700", "HK", 490_000, 49.0, style="china_tech"),
        ],
    )

    report = evaluate_health(portfolio)

    assert any(issue.title == "现金仓位低于最低线" and issue.severity == "CRITICAL" for issue in report.issues)


def test_health_check_score_formula_matches_issue_counts() -> None:
    portfolio = Portfolio(
        total_value_cny=1_000_000,
        cash_cny=20_000,
        target_value=1_800_000,
        holdings=[
            _holding("NVDA", "US", 400_000, 40.0, beta_level="very_high"),
            _holding("MSFT", "US", 300_000, 30.0),
            _holding("GOOGL", "US", 280_000, 28.0),
        ],
    )

    report = evaluate_health(portfolio)

    critical_count = sum(1 for issue in report.issues if issue.severity == "CRITICAL")
    warning_count = sum(1 for issue in report.issues if issue.severity == "WARNING")
    assert report.score == max(0, 100 - critical_count * 15 - warning_count * 5)


def test_health_check_accepts_cn_market_alias() -> None:
    portfolio = Portfolio(
        total_value_cny=1_400_000,
        cash_cny=140_000,
        holdings=[
            _holding("600519", "CN", 280_000, 20.0, style="consumer"),
            _holding("NVDA", "US", 490_000, 35.0),
            _holding("00700", "HK", 420_000, 30.0, style="china_tech"),
            _holding("BTC", "CRYPTO", 70_000, 5.0, style="alternative", beta_level="very_high"),
        ],
    )

    report = evaluate_health(portfolio)

    assert report.allocation_current["A"] == 20.0
    assert report.allocation_target["A"] == 20.0

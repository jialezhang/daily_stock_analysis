# -*- coding: utf-8 -*-
"""Tests for anomaly detection."""

from src.portfolio.analysis.anomaly import detect_anomalies
from src.portfolio.models import LiquidityData, MacroData, Portfolio, PortfolioHolding


def _holding(
    ticker: str,
    market: str,
    weight_pct: float,
    *,
    daily_change_pct: float = 0.0,
    style: str = "tech_growth",
    beta_level: str = "medium",
) -> PortfolioHolding:
    return PortfolioHolding(
        ticker=ticker,
        name=ticker,
        market=market,
        value_cny=1_000_000 * weight_pct / 100.0,
        weight_pct=weight_pct,
        daily_change_pct=daily_change_pct,
        style=style,
        beta_level=beta_level,
    )


def test_detect_anomalies_returns_red_before_yellow() -> None:
    portfolio = Portfolio(
        total_value_cny=1_000_000,
        cash_cny=20_000,
        holdings=[
            _holding("NBIS", "US", 18.0, daily_change_pct=-9.2, beta_level="very_high"),
            _holding("NVDA", "US", 16.0, beta_level="very_high"),
            _holding("00700", "HK", 22.0, style="china_tech"),
        ],
    )
    macro = MacroData(
        date="2026-03-07",
        vix=31.5,
        vix_daily_change_pct=35.0,
        treasury_10y_daily_change_bps=18.0,
        usd_index=107.2,
        hyg_5d_return=-2.6,
    )
    liquidity = LiquidityData(date="2026-03-07")

    alerts = detect_anomalies(macro, liquidity, portfolio)

    assert alerts
    assert alerts[0].level == "RED"
    assert any(alert.level == "YELLOW" for alert in alerts)


def test_detect_anomalies_maps_affected_holdings() -> None:
    portfolio = Portfolio(
        total_value_cny=1_000_000,
        cash_cny=120_000,
        holdings=[
            _holding("NBIS", "US", 18.0, beta_level="very_high"),
            _holding("NVDA", "US", 12.0, beta_level="high"),
            _holding("00700", "HK", 20.0, style="china_tech"),
        ],
    )
    macro = MacroData(date="2026-03-07", vix=32.0, vix_daily_change_pct=40.0)
    liquidity = LiquidityData(date="2026-03-07")

    alerts = detect_anomalies(macro, liquidity, portfolio)
    panic = next(alert for alert in alerts if alert.name == "VIX 恐慌飙升")

    assert "NBIS" in panic.affected_holdings
    assert "NVDA" in panic.affected_holdings


def test_detect_anomalies_returns_empty_for_normal_inputs() -> None:
    portfolio = Portfolio(
        total_value_cny=1_000_000,
        cash_cny=150_000,
        holdings=[
            _holding("NVDA", "US", 15.0, beta_level="medium"),
            _holding("00700", "HK", 15.0, style="china_tech"),
            _holding("600519", "A", 10.0, style="consumer"),
        ],
    )
    macro = MacroData(date="2026-03-07", vix=18.0, usd_index=103.5, hyg_5d_return=0.5)
    liquidity = LiquidityData(date="2026-03-07")

    alerts = detect_anomalies(macro, liquidity, portfolio)

    assert alerts == []

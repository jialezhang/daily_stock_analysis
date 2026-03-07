# -*- coding: utf-8 -*-
"""Tests for rebalance planning."""

from src.portfolio.analysis.anomaly import detect_anomalies
from src.portfolio.analysis.health_check import evaluate_health
from src.portfolio.analysis.market_regime import evaluate_market_regimes
from src.portfolio.analysis.rebalance import build_rebalance_plan
from src.portfolio.models import LiquidityData, MacroData, Portfolio, PortfolioHolding, SectorAnalysis, SectorData


def _holding(
    ticker: str,
    market: str,
    value_cny: float,
    weight_pct: float,
    *,
    shares: float = 0.0,
    current_price: float = 0.0,
    lot_size: float = 1.0,
    daily_change_pct: float = 0.0,
    style: str = "tech_growth",
    beta_level: str = "medium",
) -> PortfolioHolding:
    return PortfolioHolding(
        ticker=ticker,
        name=ticker,
        market=market,
        shares=shares,
        current_price=current_price,
        lot_size=lot_size,
        value_cny=value_cny,
        weight_pct=weight_pct,
        daily_change_pct=daily_change_pct,
        style=style,
        beta_level=beta_level,
    )


def test_rebalance_generates_sell_action_for_overweight_us_in_defensive_regime() -> None:
    portfolio = Portfolio(
        total_value_cny=1_000_000,
        cash_cny=100_000,
        holdings=[
            _holding("NBIS", "US", 220_000, 22.0, daily_change_pct=-4.0, beta_level="very_high"),
            _holding("NVDA", "US", 230_000, 23.0, daily_change_pct=-2.0, beta_level="high"),
            _holding("00700", "HK", 220_000, 22.0, style="china_tech"),
            _holding("600519", "A", 150_000, 15.0, style="consumer"),
        ],
    )
    macro = MacroData(
        date="2026-03-07",
        spy_close=520,
        spy_ma50=560,
        spy_ma200=590,
        vix=29.0,
        hyg_5d_return=-2.2,
        usd_index=106.0,
        kweb_5d_return=0.0,
    )
    liquidity = LiquidityData(date="2026-03-07")
    regimes = evaluate_market_regimes(macro, liquidity, SectorData(date="2026-03-07"))
    health = evaluate_health(portfolio)
    anomalies = detect_anomalies(macro, liquidity, portfolio)

    plan = build_rebalance_plan(portfolio, health, regimes, anomalies, SectorAnalysis())

    assert any(action.direction == "SELL" and action.market == "US" for action in plan.actions)


def test_rebalance_generates_buy_action_for_underweight_a_in_aggressive_regime() -> None:
    portfolio = Portfolio(
        total_value_cny=1_000_000,
        cash_cny=180_000,
        holdings=[
            _holding("NVDA", "US", 300_000, 30.0),
            _holding("00700", "HK", 320_000, 32.0, style="china_tech"),
            _holding("600519", "A", 80_000, 8.0, style="consumer"),
            _holding("300750", "A", 120_000, 12.0, style="manufacturing"),
        ],
    )
    macro = MacroData(date="2026-03-07", usd_index=102.0, kweb_5d_return=2.5)
    liquidity = LiquidityData(
        date="2026-03-07",
        csi300_close=4100,
        csi300_ma20=4000,
        csi300_ma60=3900,
        a_turnover_billion=13000,
        northbound_5d_cumulative=700,
        margin_balance_3d_trend="up",
    )
    regimes = evaluate_market_regimes(macro, liquidity, SectorData(date="2026-03-07"))
    health = evaluate_health(portfolio)

    plan = build_rebalance_plan(portfolio, health, regimes, [], SectorAnalysis())

    assert any(action.direction == "BUY" and action.market == "A" for action in plan.actions)


def test_rebalance_promotes_red_anomaly_actions_to_priority_one() -> None:
    portfolio = Portfolio(
        total_value_cny=1_000_000,
        cash_cny=80_000,
        holdings=[
            _holding("NBIS", "US", 180_000, 18.0, beta_level="very_high"),
            _holding("NVDA", "US", 170_000, 17.0, beta_level="high"),
            _holding("00700", "HK", 220_000, 22.0, style="china_tech"),
            _holding("600519", "A", 140_000, 14.0, style="consumer"),
        ],
    )
    macro = MacroData(date="2026-03-07", vix=32.0, vix_daily_change_pct=33.0)
    health = evaluate_health(portfolio)
    regimes = evaluate_market_regimes(macro, LiquidityData(date="2026-03-07"), SectorData(date="2026-03-07"))
    anomalies = detect_anomalies(macro, LiquidityData(date="2026-03-07"), portfolio)

    plan = build_rebalance_plan(portfolio, health, regimes, anomalies, SectorAnalysis())

    assert plan.actions
    assert plan.actions[0].priority == 1


def test_rebalance_respects_single_trade_caps() -> None:
    portfolio = Portfolio(
        total_value_cny=1_000_000,
        cash_cny=150_000,
        holdings=[
            _holding("NBIS", "US", 300_000, 30.0, daily_change_pct=-5.0, beta_level="very_high"),
            _holding("NVDA", "US", 250_000, 25.0, daily_change_pct=-2.0, beta_level="high"),
            _holding("00700", "HK", 200_000, 20.0, style="china_tech"),
            _holding("600519", "A", 100_000, 10.0, style="consumer"),
        ],
    )
    macro = MacroData(
        date="2026-03-07",
        spy_close=520,
        spy_ma50=560,
        spy_ma200=590,
        vix=27.0,
        hyg_5d_return=-2.1,
        usd_index=104.0,
    )
    liquidity = LiquidityData(
        date="2026-03-07",
        csi300_close=4100,
        csi300_ma20=4000,
        csi300_ma60=3900,
        a_turnover_billion=13000,
        northbound_5d_cumulative=650,
        margin_balance_3d_trend="up",
    )
    health = evaluate_health(portfolio)
    regimes = evaluate_market_regimes(macro, liquidity, SectorData(date="2026-03-07"))

    plan = build_rebalance_plan(portfolio, health, regimes, [], SectorAnalysis())

    for action in plan.actions:
        if action.direction == "SELL":
            assert abs(action.trade_amount_cny) <= action.current_value_cny * 0.3 + 1e-6
        if action.direction == "BUY":
            assert action.trade_amount_cny <= portfolio.total_value_cny * 0.05 + 1e-6


def test_rebalance_rounds_equity_actions_to_board_lots() -> None:
    portfolio = Portfolio(
        total_value_cny=1_000_000,
        cash_cny=100_000,
        holdings=[
            _holding("NVDA", "US", 320_000, 32.0, shares=800, current_price=400.0, lot_size=1, daily_change_pct=-1.0),
            _holding("00700", "HK", 380_000, 38.0, shares=950, current_price=400.0, lot_size=100, daily_change_pct=-2.0),
            _holding("002195", "A", 30_500, 3.05, shares=5000, current_price=6.1, lot_size=100, daily_change_pct=4.0),
            _holding("600519", "A", 169_500, 16.95, shares=100, current_price=1695.0, lot_size=100, daily_change_pct=1.0),
        ],
    )
    macro = MacroData(date="2026-03-07", usd_index=102.0, kweb_5d_return=3.0)
    liquidity = LiquidityData(
        date="2026-03-07",
        csi300_close=4100,
        csi300_ma20=4000,
        csi300_ma60=3900,
        a_turnover_billion=13000,
        northbound_5d_cumulative=900,
        margin_balance_3d_trend="up",
    )
    regimes = evaluate_market_regimes(macro, liquidity, SectorData(date="2026-03-07"))
    health = evaluate_health(portfolio)

    plan = build_rebalance_plan(portfolio, health, regimes, [], SectorAnalysis())

    hk_sell = next(action for action in plan.actions if action.ticker == "00700")
    a_buy = next(action for action in plan.actions if action.ticker == "002195")

    assert hk_sell.direction == "SELL"
    assert hk_sell.share_quantity == 100
    assert abs(hk_sell.trade_amount_cny) == 40_000.0
    assert hk_sell.lot_size == 100

    assert a_buy.direction == "BUY"
    assert a_buy.share_quantity % 100 == 0
    assert a_buy.share_quantity == 8100
    assert a_buy.trade_amount_cny == 49_410.0
    assert a_buy.lot_size == 100

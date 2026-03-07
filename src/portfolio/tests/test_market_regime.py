# -*- coding: utf-8 -*-
"""Tests for portfolio market regime evaluation."""

from src.portfolio.analysis.market_regime import evaluate_market_regimes
from src.portfolio.models import LiquidityData, MacroData, SectorData, SectorEntry


def test_market_regime_returns_aggressive_for_broadly_bullish_inputs() -> None:
    macro = MacroData(
        date="2026-03-07",
        spy_close=610,
        spy_ma50=590,
        spy_ma200=560,
        vix=15,
        hyg_5d_return=1.2,
        usd_index=102,
        kweb_5d_return=3.5,
    )
    liquidity = LiquidityData(
        date="2026-03-07",
        hsi_close=24500,
        hsi_ma20=23600,
        hsi_ma60=22800,
        southbound_5d_avg=250,
        csi300_close=4100,
        csi300_ma20=4000,
        csi300_ma60=3920,
        a_turnover_billion=13000,
        northbound_5d_cumulative=600,
        margin_balance_3d_trend="up",
    )
    sector = SectorData(
        date="2026-03-07",
        us_sectors=[
            SectorEntry("Technology", "XLK", "offensive", 1.5, 1.0),
            SectorEntry("Semiconductor", "SMH", "offensive", 1.8, 1.2),
            SectorEntry("Communication", "XLC", "offensive", 1.2, 0.9),
        ],
    )

    results = {item.market: item for item in evaluate_market_regimes(macro, liquidity, sector)}

    assert results["US"].regime == "aggressive"
    assert results["HK"].regime == "aggressive"
    assert results["A"].regime == "aggressive"


def test_market_regime_returns_defensive_for_broadly_bearish_inputs() -> None:
    macro = MacroData(
        date="2026-03-07",
        spy_close=520,
        spy_ma50=560,
        spy_ma200=590,
        vix=31,
        hyg_5d_return=-2.5,
        usd_index=107.5,
        kweb_5d_return=-4.1,
    )
    liquidity = LiquidityData(
        date="2026-03-07",
        hsi_close=18200,
        hsi_ma20=19100,
        hsi_ma60=20500,
        southbound_5d_avg=-120,
        csi300_close=3400,
        csi300_ma20=3600,
        csi300_ma60=3800,
        a_turnover_billion=7600,
        northbound_5d_cumulative=-900,
        margin_balance_3d_trend="down",
    )
    sector = SectorData(
        date="2026-03-07",
        us_sectors=[
            SectorEntry("Utilities", "XLU", "defensive", 0.1, 0.1),
            SectorEntry("Healthcare", "XLV", "defensive", 0.0, 0.0),
            SectorEntry("Energy", "XLE", "cyclical", -1.8, -1.0),
        ],
    )

    results = {item.market: item for item in evaluate_market_regimes(macro, liquidity, sector)}

    assert results["US"].regime == "defensive"
    assert results["HK"].regime == "defensive"
    assert results["A"].regime == "defensive"


def test_market_regime_weighted_score_is_computed_correctly() -> None:
    macro = MacroData(
        date="2026-03-07",
        spy_close=610,
        spy_ma50=590,
        spy_ma200=560,
        vix=17,
        hyg_5d_return=-2.0,
    )
    liquidity = LiquidityData(date="2026-03-07")
    sector = SectorData(
        date="2026-03-07",
        us_sectors=[
            SectorEntry("Technology", "XLK", "offensive", 1.5, 1.0),
            SectorEntry("Semiconductor", "SMH", "offensive", 1.4, 0.9),
            SectorEntry("Communication", "XLC", "offensive", 1.2, 0.8),
        ],
    )

    results = {item.market: item for item in evaluate_market_regimes(macro, liquidity, sector)}
    us = results["US"]

    assert us.total_score == 4


def test_market_regime_score_details_all_have_reasons() -> None:
    macro = MacroData(date="2026-03-07")
    liquidity = LiquidityData(date="2026-03-07")
    sector = SectorData(date="2026-03-07")

    results = evaluate_market_regimes(macro, liquidity, sector)

    for result in results:
      assert result.score_details
      assert all(detail.get("reason") for detail in result.score_details)

# -*- coding: utf-8 -*-
"""Tests for portfolio data fetchers."""

from src.portfolio.data import liquidity_fetcher, macro_fetcher, sector_fetcher


def test_fetch_macro_data_builds_snapshot_from_price_history(monkeypatch) -> None:
    history_map = {
        "^TNX": [4.20, 4.35],
        "DX-Y.NYB": [104.0, 105.0],
        "^VIX": [18.0, 24.0],
        "CNY=X": [7.10, 7.20],
        "SPY": list(range(1, 251)),
        "HYG": [80.0, 81.0, 82.0, 83.0, 84.0, 85.0],
        "KWEB": [20.0, 21.0, 22.0, 23.0, 24.0, 25.0],
    }

    monkeypatch.setattr(
        macro_fetcher,
        "_fetch_close_history",
        lambda ticker, min_points=2: history_map.get(ticker, []),
        raising=False,
    )

    result = macro_fetcher.fetch_macro_data()

    assert result.treasury_10y == 4.35
    assert result.treasury_10y_daily_change_bps == 15.0
    assert round(float(result.usd_index_daily_change_pct or 0.0), 2) == 0.96
    assert round(float(result.vix_daily_change_pct or 0.0), 2) == 33.33
    assert result.usd_cnh == 7.2
    assert result.spy_close == 250.0
    assert result.spy_ma50 == 225.5
    assert result.spy_ma200 == 150.5
    assert result.hyg_5d_return == 6.25
    assert result.kweb_5d_return == 25.0


def test_fetch_liquidity_data_builds_snapshot_from_market_and_flow_data(monkeypatch) -> None:
    history_map = {
        "^HSI": list(range(20000, 20070)),
        "000300.SS": list(range(4000, 4070)),
    }
    monkeypatch.setattr(
        liquidity_fetcher,
        "_fetch_close_history",
        lambda ticker, min_points=2: history_map.get(ticker, []),
        raising=False,
    )
    monkeypatch.setattr(
        liquidity_fetcher,
        "_fetch_a_market_stats",
        lambda: {"total_amount": 12345.0},
        raising=False,
    )
    monkeypatch.setattr(
        liquidity_fetcher,
        "_fetch_tushare_liquidity_snapshot",
        lambda: {
            "northbound": [100.0, 150.0, 200.0, 250.0, 300.0],
            "southbound": [20.0, 30.0, 40.0, 50.0, 60.0],
            "margin_balance": [1000.0, 1010.0, 1020.0],
        },
        raising=False,
    )

    result = liquidity_fetcher.fetch_liquidity_data()

    assert result.a_turnover_billion == 12345.0
    assert result.margin_balance_billion == 1020.0
    assert result.margin_balance_3d_trend == "up"
    assert result.northbound_daily_billion == 300.0
    assert result.northbound_5d_cumulative == 1000.0
    assert result.southbound_daily_billion == 60.0
    assert result.southbound_5d_avg == 40.0
    assert result.hsi_close == 20069.0
    assert result.hsi_ma20 == 20059.5
    assert result.hsi_ma60 == 20039.5
    assert result.csi300_close == 4069.0
    assert result.csi300_ma20 == 4059.5
    assert result.csi300_ma60 == 4039.5


def test_fetch_sector_data_builds_us_and_a_hk_sector_views(monkeypatch) -> None:
    history_map = {
        "SPY": [100.0, 101.0, 102.0, 103.0, 104.0, 105.0],
        "XLK": [100.0, 102.0, 104.0, 106.0, 108.0, 110.0],
        "XLU": [100.0, 100.0, 100.5, 101.0, 101.5, 102.0],
        "^HSI": [18000.0, 18100.0, 18200.0, 18300.0, 18400.0, 18500.0],
        "KWEB": [30.0, 30.5, 31.0, 32.0, 33.0, 34.0],
    }
    monkeypatch.setattr(
        sector_fetcher,
        "_fetch_close_history",
        lambda ticker, min_points=2: history_map.get(ticker, []),
        raising=False,
    )
    monkeypatch.setattr(
        sector_fetcher,
        "_fetch_a_sector_rankings",
        lambda limit=10: [
            {"name": "电子", "change_pct": 3.2},
            {"name": "通信", "change_pct": 2.4},
            {"name": "银行", "change_pct": -1.1},
        ],
        raising=False,
    )

    result = sector_fetcher.fetch_sector_data()

    assert round(float(result.us_benchmark_return or 0.0), 2) == 5.0
    assert len(result.us_sectors) >= 2
    assert result.us_sectors[0].ticker in {"XLK", "XLU"}
    assert result.a_sectors[0]["name"] == "电子"
    assert round(float(result.hk_benchmark_return or 0.0), 2) == 2.78
    assert round(float(result.hk_tech_return or 0.0), 2) == 13.33

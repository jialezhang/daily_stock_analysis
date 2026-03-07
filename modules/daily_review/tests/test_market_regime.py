"""Tests for market regime evaluation."""

from __future__ import annotations

from datetime import date

from modules.daily_review.analysis.market_regime import evaluate_regime
from modules.daily_review.data.liquidity import LiquidityData
from modules.daily_review.data.macro import MacroData, MacroPoint
from modules.daily_review.data.sector import SectorData, SectorEntry


def _macro(
    *,
    us_10y_daily_abs: float = 0.02,
    usd_index: float = 103.0,
    vix: float = 18.0,
    usd_cnh_daily_abs: float = -0.01,
) -> MacroData:
    return MacroData(
        as_of=date.today(),
        points={
            "us_10y": MacroPoint(
                key="us_10y",
                ticker="^TNX",
                value=4.2,
                daily_change_abs=us_10y_daily_abs,
                daily_change_pct=0.0,
                change_5d_abs=0.0,
                change_5d_pct=0.0,
                ma50=4.1,
                ma200=4.0,
            ),
            "usd_index": MacroPoint(
                key="usd_index",
                ticker="DX-Y.NYB",
                value=usd_index,
                daily_change_abs=0.0,
                daily_change_pct=0.0,
                change_5d_abs=0.0,
                change_5d_pct=0.0,
                ma50=102.5,
                ma200=101.5,
            ),
            "vix": MacroPoint(
                key="vix",
                ticker="^VIX",
                value=vix,
                daily_change_abs=0.0,
                daily_change_pct=0.0,
                change_5d_abs=0.0,
                change_5d_pct=0.0,
                ma50=19.0,
                ma200=20.0,
            ),
            "usd_cnh": MacroPoint(
                key="usd_cnh",
                ticker="CNY=X",
                value=7.2,
                daily_change_abs=usd_cnh_daily_abs,
                daily_change_pct=-0.1,
                change_5d_abs=0.0,
                change_5d_pct=0.0,
                ma50=7.22,
                ma200=7.2,
            ),
        },
    )


def test_us_regime_offensive() -> None:
    macro = _macro(us_10y_daily_abs=0.03, vix=16.0)
    liquidity = LiquidityData(as_of=date.today(), hyg_5d_return=0.03, spy_volume_ratio=1.2)
    sectors = SectorData(
        as_of=date.today(),
        us=[
            SectorEntry("XLK", "科技", "US", "offensive", 1.1, 1.2),
            SectorEntry("SMH", "半导体", "US", "offensive", 1.0, 1.0),
            SectorEntry("XLY", "可选消费", "US", "offensive", 0.9, 0.8),
        ],
        benchmarks={"US": {"close": 520.0, "ma50": 500.0, "ma200": 460.0}},
    )

    result = evaluate_regime("US", macro, liquidity, sectors)

    assert result.regime == "进攻"
    assert result.total_score >= 2
    assert result.position_suggestion == "建议仓位 70-100%"


def test_us_regime_defensive() -> None:
    macro = _macro(us_10y_daily_abs=0.18, vix=30.0)
    liquidity = LiquidityData(as_of=date.today(), hyg_5d_return=-0.03, spy_volume_ratio=0.8)
    sectors = SectorData(
        as_of=date.today(),
        us=[
            SectorEntry("XLK", "科技", "US", "offensive", -1.0, 0.3),
            SectorEntry("XLP", "必选消费", "US", "defensive", 0.8, 0.2),
            SectorEntry("XLE", "能源", "US", "cyclical", 1.2, 0.1),
        ],
        benchmarks={"US": {"close": 430.0, "ma50": 450.0, "ma200": 470.0}},
    )

    result = evaluate_regime("US", macro, liquidity, sectors)

    assert result.regime == "防守"
    assert result.total_score <= -2
    assert result.position_suggestion == "建议仓位 0-40%"


def test_a_regime_balanced() -> None:
    macro = _macro()
    liquidity = LiquidityData(
        as_of=date.today(),
        a_turnover_billion=9000.0,
        northbound_net_billion=5.0,
        margin_balance_trend_3d="flat",
    )
    sectors = SectorData(
        as_of=date.today(),
        a=[
            SectorEntry("801010", "农林牧渔", "A", "消费主线", 0.2, 0.3),
            SectorEntry("801140", "轻工制造", "A", "消费主线", 0.1, 0.2),
            SectorEntry("801750", "计算机", "A", "科技主线", 0.1, 0.1),
            SectorEntry("801780", "银行", "A", "大金融主线", 0.1, 0.05),
            SectorEntry("801030", "基础化工", "A", "资源主线", -0.1, -0.1),
        ],
        benchmarks={"A": {"close": 3600.0, "ma20": 3590.0, "ma60": 3580.0}},
    )

    result = evaluate_regime("A", macro, liquidity, sectors)

    assert result.regime == "平衡"
    assert -1 <= result.total_score <= 1
    assert result.position_suggestion == "建议仓位 40-70%"


def test_hk_regime_offensive() -> None:
    macro = _macro(usd_index=102.0, usd_cnh_daily_abs=-0.02)
    liquidity = LiquidityData(as_of=date.today(), southbound_net_billion=35.0, kweb_5d_return=0.04)
    sectors = SectorData(
        as_of=date.today(),
        hk=[
            SectorEntry("^HSTECH", "恒生科技", "HK", "offensive", 1.0, 2.0),
            SectorEntry("^HSI", "恒生指数", "HK", "benchmark", 0.6, 0.0),
        ],
        benchmarks={"HK": {"close": 18000.0, "ma20": 17500.0, "ma60": 17000.0}},
    )

    result = evaluate_regime("HK", macro, liquidity, sectors)

    assert result.regime == "进攻"
    assert result.total_score >= 2

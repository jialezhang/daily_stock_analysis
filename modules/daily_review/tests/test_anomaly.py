"""Tests for anomaly detection."""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from typing import Callable

import pytest

from modules.daily_review.analysis.anomaly import detect_anomalies
from modules.daily_review.data.liquidity import LiquidityData
from modules.daily_review.data.macro import MacroData, MacroPoint
from modules.daily_review.data.sector import SectorData, SectorEntry
from modules.daily_review.data.stock import StockEntry


def _base_macro() -> MacroData:
    return MacroData(
        as_of=date.today(),
        points={
            "us_10y": MacroPoint("us_10y", "^TNX", 4.2, 0.02, 0.1, 0.05, 0.2, 4.1, 4.0),
            "usd_index": MacroPoint("usd_index", "DX-Y.NYB", 103.0, 0.0, 0.0, 0.0, 0.0, 102.5, 101.5),
            "vix": MacroPoint("vix", "^VIX", 18.0, 0.0, 0.0, 0.0, 0.0, 19.0, 20.0),
            "usd_cnh": MacroPoint("usd_cnh", "CNY=X", 7.2, 0.01, 0.1, 0.01, 0.1, 7.2, 7.1),
        },
    )


def _base_liquidity() -> LiquidityData:
    return LiquidityData(
        as_of=date.today(),
        a_turnover_billion=9000.0,
        northbound_net_billion=10.0,
        northbound_3d_cumulative=10.0,
        margin_balance_5d_change_pct=0.01,
        a_turnover_3d_all_below_7000=False,
        hyg_5d_return=0.0,
    )


def _base_sectors() -> SectorData:
    return SectorData(
        as_of=date.today(),
        us=[SectorEntry("XLC", "通信", "US", "offensive", 0.2, 0.5)],
        hk=[SectorEntry("^HSTECH", "恒生科技", "HK", "offensive", 0.3, 0.4)],
        a=[SectorEntry("801750", "计算机", "A", "科技主线", 0.2, 0.3)],
    )


def _base_stocks() -> list[StockEntry]:
    return [
        StockEntry(
            name="阿里巴巴",
            market="US",
            ticker="BABA",
            sector="XLC",
            daily_change_pct=-0.5,
            sector_daily_change_pct=0.2,
            vs_sector=-0.7,
            volume=1000,
            avg_volume_20=1200,
            volume_ratio=0.8,
            turnover_rate=None,
            ma5=10.0,
            ma20=9.8,
            ma60=9.2,
            signal="➖ 正常",
        )
    ]


@pytest.mark.parametrize(
    ("name", "mutator"),
    [
        ("美债收益率剧震", lambda m, l, s, st: (replace(m, points={**m.points, "us_10y": replace(m.points["us_10y"], daily_change_abs=0.2)}), l, s, st)),
        ("VIX 恐慌飙升", lambda m, l, s, st: (replace(m, points={**m.points, "vix": replace(m.points["vix"], value=31.0)}), l, s, st)),
        ("美元指数突破关键位", lambda m, l, s, st: (replace(m, points={**m.points, "usd_index": replace(m.points["usd_index"], value=108.0)}), l, s, st)),
        ("北向资金恐慌性流出", lambda m, l, s, st: (m, replace(l, northbound_net_billion=-120.0), s, st)),
        ("A 股成交额断崖", lambda m, l, s, st: (m, replace(l, a_turnover_billion=4500.0), s, st)),
        ("离岸人民币急贬", lambda m, l, s, st: (replace(m, points={**m.points, "usd_cnh": replace(m.points["usd_cnh"], daily_change_pct=1.0)}), l, s, st)),
        ("VIX 进入警戒区间", lambda m, l, s, st: (replace(m, points={**m.points, "vix": replace(m.points["vix"], value=27.0)}), l, s, st)),
        ("美债收益率持续攀升", lambda m, l, s, st: (replace(m, points={**m.points, "us_10y": replace(m.points["us_10y"], change_5d_abs=0.3)}), l, s, st)),
        ("北向资金连续流出", lambda m, l, s, st: (m, replace(l, northbound_3d_cumulative=-180.0), s, st)),
        ("融资盘去杠杆", lambda m, l, s, st: (m, replace(l, margin_balance_5d_change_pct=-0.03), s, st)),
        ("A 股持续缩量", lambda m, l, s, st: (m, replace(l, a_turnover_3d_all_below_7000=True), s, st)),
        ("美股信用利差走阔", lambda m, l, s, st: (m, replace(l, hyg_5d_return=-0.03), s, st)),
        (
            "持仓个股异动",
            lambda m, l, s, st: (
                m,
                l,
                s,
                [
                    replace(
                        st[0],
                        daily_change_pct=-4.0,
                        sector_daily_change_pct=0.2,
                        vs_sector=-4.2,
                        volume_ratio=1.0,
                    )
                ],
            ),
        ),
        (
            "持仓个股异常放量",
            lambda m, l, s, st: (
                m,
                l,
                s,
                [
                    replace(
                        st[0],
                        daily_change_pct=-2.5,
                        sector_daily_change_pct=0.0,
                        vs_sector=-2.5,
                        volume_ratio=3.5,
                    )
                ],
            ),
        ),
    ],
)
def test_anomaly_rules_can_be_triggered(
    name: str,
    mutator: Callable[[MacroData, LiquidityData, SectorData, list[StockEntry]], tuple[MacroData, LiquidityData, SectorData, list[StockEntry]]],
) -> None:
    macro = _base_macro()
    liquidity = _base_liquidity()
    sectors = _base_sectors()
    stocks = _base_stocks()

    macro, liquidity, sectors, stocks = mutator(macro, liquidity, sectors, stocks)
    alerts = detect_anomalies(macro=macro, liquidity=liquidity, stocks=stocks, sectors=sectors)

    assert any(a.name == name for a in alerts)


def test_anomaly_normal_case_returns_empty() -> None:
    alerts = detect_anomalies(
        macro=_base_macro(),
        liquidity=_base_liquidity(),
        stocks=_base_stocks(),
        sectors=_base_sectors(),
    )
    assert alerts == []


def test_red_alerts_are_sorted_before_yellow() -> None:
    macro = replace(
        _base_macro(),
        points={
            **_base_macro().points,
            "vix": replace(_base_macro().points["vix"], value=31.0),
        },
    )
    liquidity = replace(_base_liquidity(), hyg_5d_return=-0.03)

    alerts = detect_anomalies(macro=macro, liquidity=liquidity, stocks=_base_stocks(), sectors=_base_sectors())
    levels = [a.level for a in alerts]

    assert "RED" in levels and "YELLOW" in levels
    assert levels.index("RED") < levels.index("YELLOW")

"""Tests for sector flow analysis."""

from __future__ import annotations

from datetime import date

from modules.daily_review.analysis.sector_flow import analyze_sector_preference
from modules.daily_review.data.sector import SectorData, SectorEntry


def test_us_offensive_style_dominant() -> None:
    sectors = SectorData(
        as_of=date.today(),
        us=[
            SectorEntry("XLK", "科技", "US", "offensive", 1.2, 1.3),
            SectorEntry("SMH", "半导体", "US", "offensive", 1.1, 1.1),
            SectorEntry("XLY", "可选消费", "US", "offensive", 0.9, 0.9),
            SectorEntry("XLU", "公用事业", "US", "defensive", -0.2, -0.3),
        ],
    )

    analysis = analyze_sector_preference(sectors)

    assert analysis.us_market_style == "进攻型主导"
    assert len(analysis.us_leaders) == 3


def test_us_defensive_style_dominant() -> None:
    sectors = SectorData(
        as_of=date.today(),
        us=[
            SectorEntry("XLU", "公用事业", "US", "defensive", 1.2, 1.3),
            SectorEntry("XLP", "必选消费", "US", "defensive", 1.1, 1.1),
            SectorEntry("XLV", "医疗", "US", "defensive", 0.9, 0.9),
            SectorEntry("XLK", "科技", "US", "offensive", -0.2, -0.3),
        ],
    )

    analysis = analyze_sector_preference(sectors)

    assert analysis.us_market_style == "防守型主导"


def test_a_theme_is_tech_when_top5_concentrated() -> None:
    sectors = SectorData(
        as_of=date.today(),
        a=[
            SectorEntry("801080", "电子", "A", "科技主线", 1.2, 1.3),
            SectorEntry("801750", "计算机", "A", "科技主线", 1.1, 1.1),
            SectorEntry("801770", "通信", "A", "科技主线", 0.9, 0.9),
            SectorEntry("801760", "传媒", "A", "科技主线", 0.8, 0.8),
            SectorEntry("801740", "国防军工", "A", "科技主线", 0.7, 0.7),
            SectorEntry("801780", "银行", "A", "大金融主线", -0.3, -0.5),
        ],
        hk=[
            SectorEntry("^HSI", "恒生指数", "HK", "benchmark", 0.2, 0.0),
            SectorEntry("^HSTECH", "恒生科技", "HK", "offensive", 0.5, 1.0),
        ],
    )

    analysis = analyze_sector_preference(sectors)

    assert analysis.a_main_theme == "科技主线"
    assert analysis.hk_leader == "恒生科技领跑"

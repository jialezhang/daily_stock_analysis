"""Tests for runner snapshot persistence."""

from __future__ import annotations

import json
from datetime import date

from modules.daily_review.config import DailyReviewConfig, today_shanghai
from modules.daily_review.data.liquidity import LiquidityData
from modules.daily_review.data.macro import MacroData, MacroPoint
from modules.daily_review.data.sector import SectorData, SectorEntry
from modules.daily_review.data.stock import StockEntry
from modules.daily_review.runner import run_daily_review


def _build_macro() -> MacroData:
    return MacroData(
        as_of=date.today(),
        points={
            "us_10y": MacroPoint("us_10y", "^TNX", 4.2, 0.02, 0.5, 0.05, 1.2, 4.1, 4.0),
            "usd_index": MacroPoint("usd_index", "DX-Y.NYB", 104.1, -0.1, -0.2, -0.3, -0.4, 104.5, 103.8),
            "vix": MacroPoint("vix", "^VIX", 17.8, -0.3, -1.4, -0.5, -2.0, 18.2, 19.0),
            "usd_cnh": MacroPoint("usd_cnh", "CNY=X", 7.21, -0.01, -0.1, -0.03, -0.4, 7.25, 7.3),
        },
    )


def _build_liquidity() -> LiquidityData:
    return LiquidityData(
        as_of=date.today(),
        a_turnover_billion=13800,
        northbound_net_billion=32.5,
        southbound_net_billion=18.3,
        northbound_3d_cumulative=45.0,
        margin_balance=16688,
        margin_balance_trend_3d="up",
        margin_balance_5d_change_pct=0.021,
        a_turnover_3d_all_below_7000=False,
        spy_volume_ratio=1.11,
        hyg_5d_return=0.016,
        tlt_5d_return=-0.01,
        kweb_5d_return=0.024,
    )


def _build_sectors() -> SectorData:
    return SectorData(
        as_of=date.today(),
        us=[
            SectorEntry("XLK", "科技", "US", "offensive", 1.2, 0.8),
            SectorEntry("XLY", "可选消费", "US", "offensive", 0.7, 0.4),
            SectorEntry("XLF", "金融", "US", "cyclical", 0.3, 0.1),
        ],
        hk=[
            SectorEntry("^HSI", "恒生指数", "HK", "benchmark", 0.6, 0.2),
            SectorEntry("^HSTECH", "恒生科技", "HK", "offensive", 1.4, 0.5),
        ],
        a=[
            SectorEntry("801080.SI", "电子", "A", "科技主线", 1.1, 0.6),
            SectorEntry("801750.SI", "计算机", "A", "科技主线", 0.9, 0.5),
        ],
        benchmarks={
            "US": {"close": 520.0, "ma50": 510.0, "ma200": 495.0},
            "HK": {"close": 17500.0, "ma20": 17200.0, "ma60": 17650.0},
            "A": {"close": 3700.0, "ma20": 3650.0, "ma60": 3600.0},
        },
    )


def _build_stocks() -> list[StockEntry]:
    return [
        StockEntry(
            name="腾讯控股",
            market="HK",
            ticker="0700.HK",
            sector="恒生科技",
            daily_change_pct=2.0,
            sector_daily_change_pct=1.4,
            vs_sector=0.6,
            volume=12_000_000,
            avg_volume_20=10_000_000,
            volume_ratio=1.2,
            turnover_rate=None,
            ma5=388.0,
            ma20=376.0,
            ma60=365.0,
            signal="📈 放量突破",
        )
    ]


def test_run_daily_review_writes_snapshot_json(tmp_path, monkeypatch) -> None:
    cfg = DailyReviewConfig(
        tushare_token=None,
        output_dir=tmp_path,
        filename_pattern="review_{date}.md",
        telegram_bot_token=None,
        telegram_chat_id=None,
        llm_provider="none",
        llm_model="none",
        llm_api_key=None,
    )
    monkeypatch.setattr("modules.daily_review.runner._collect_data", lambda _cfg: (_build_macro(), _build_liquidity(), _build_sectors(), _build_stocks()))
    monkeypatch.setattr("modules.daily_review.runner.generate_llm_summary", lambda **_: "规则总结")

    report = run_daily_review(config=cfg, send_telegram=False, use_llm=False)
    review_key = today_shanghai().strftime("%Y%m%d")
    markdown_path = tmp_path / f"review_{review_key}.md"
    snapshot_path = tmp_path / f"review_{review_key}.json"

    assert report.startswith("# 📅 ")
    assert markdown_path.exists()
    assert snapshot_path.exists()

    payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
    assert payload["review_date"]
    assert payload["summary"] == "规则总结"
    assert len(payload["regimes"]) == 3
    assert payload["anomalies"]["red_count"] >= 0

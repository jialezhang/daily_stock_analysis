"""Runner for daily multi-market review."""

from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from collections import defaultdict
from dataclasses import asdict, is_dataclass, replace
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from modules.daily_review.analysis.anomaly import AnomalyAlert, detect_anomalies
from modules.daily_review.analysis.market_regime import RegimeResult, evaluate_regime
from modules.daily_review.analysis.sector_flow import SectorAnalysis, analyze_sector_preference
from modules.daily_review.config import DailyReviewConfig, SW_SECTOR_STYLES, US_SECTORS, load_config, today_shanghai
from modules.daily_review.history import save_snapshot
from modules.daily_review.data.liquidity import LiquidityData, fetch_liquidity
from modules.daily_review.data.macro import MacroData, fetch_macro
from modules.daily_review.data.sector import SectorData, SectorEntry, fetch_sectors
from modules.daily_review.data.stock import StockEntry, fetch_stocks
from modules.daily_review.notify.telegram import send_review
from modules.daily_review.report.llm_digest import generate_llm_summary
from modules.daily_review.report.renderer import render_report

logger = logging.getLogger(__name__)


def _sector_daily_for_stock(stock: StockEntry, sectors: SectorData) -> Optional[float]:
    if stock.market == "US":
        row = next((x for x in sectors.us if x.ticker == stock.sector), None)
        return row.daily_change_pct if row else None
    if stock.market == "HK":
        row = next((x for x in sectors.hk if x.name == stock.sector or x.ticker == stock.sector), None)
        return row.daily_change_pct if row else None
    if stock.market == "A":
        row = next((x for x in sectors.a if x.name == stock.sector), None)
        return row.daily_change_pct if row else None
    return None


def _pick_signal(vs_sector: Optional[float], daily_change_pct: Optional[float], volume_ratio: Optional[float]) -> str:
    if vs_sector is not None and vs_sector < -3.0:
        return "🔻 跑输板块"
    if daily_change_pct is not None and volume_ratio is not None and daily_change_pct < -2.0 and volume_ratio > 3.0:
        return "⚠️ 异常下跌"
    if daily_change_pct is not None and volume_ratio is not None and daily_change_pct > 0 and volume_ratio > 1.5:
        return "📈 放量突破"
    return "➖ 正常"


def _enrich_stocks_with_sector(stocks: List[StockEntry], sectors: SectorData) -> List[StockEntry]:
    for stock in stocks:
        sector_daily = _sector_daily_for_stock(stock, sectors)
        stock.sector_daily_change_pct = sector_daily
        if stock.daily_change_pct is not None and sector_daily is not None:
            stock.vs_sector = stock.daily_change_pct - sector_daily
        stock.signal = _pick_signal(stock.vs_sector, stock.daily_change_pct, stock.volume_ratio)
    return stocks


def _a_style_from_name(sector_name: str) -> str:
    for style, names in SW_SECTOR_STYLES.items():
        if sector_name in names:
            return style
    return "其他"


def _us_style_from_sector(sector_name: str) -> str:
    if sector_name in US_SECTORS:
        return US_SECTORS[sector_name]["style"]
    return "offensive"


def _hydrate_sectors_from_stocks(sectors: SectorData, stocks: List[StockEntry]) -> SectorData:
    if sectors.us and sectors.hk and sectors.a:
        return sectors

    grouped = defaultdict(list)
    for stock in stocks:
        if stock.daily_change_pct is None:
            continue
        key = (stock.market, stock.sector)
        grouped[key].append(stock.daily_change_pct)

    def _build_rows(market: str) -> List[SectorEntry]:
        rows: List[SectorEntry] = []
        for (mkt, sector_name), changes in grouped.items():
            if mkt != market or not changes:
                continue
            avg_change = sum(changes) / len(changes)
            if market == "US":
                style = _us_style_from_sector(sector_name)
            elif market == "A":
                style = _a_style_from_name(sector_name)
            elif market == "HK":
                style = "offensive" if "科技" in sector_name else "benchmark"
            else:
                style = "other"
            rows.append(
                SectorEntry(
                    ticker=sector_name,
                    name=sector_name,
                    market=market,
                    style=style,
                    daily_change_pct=avg_change,
                    rs=avg_change,
                )
            )
        return sorted(rows, key=lambda x: x.rs if x.rs is not None else -9999, reverse=True)

    if not sectors.us:
        sectors.us = _build_rows("US")
    if not sectors.hk:
        sectors.hk = _build_rows("HK")
    if not sectors.a:
        sectors.a = _build_rows("A")
    return sectors


def _hydrate_liquidity_from_stocks(liquidity: LiquidityData, stocks: List[StockEntry]) -> LiquidityData:
    if liquidity.spy_volume_ratio is not None:
        return liquidity
    us_ratios = [s.volume_ratio for s in stocks if s.market == "US" and s.volume_ratio is not None]
    if us_ratios:
        liquidity.spy_volume_ratio = sum(us_ratios) / len(us_ratios)
    return liquidity


def save_report(report_markdown: str, config: DailyReviewConfig) -> Path:
    """Save markdown report under configured path."""

    output_dir = Path(config.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    review_date = today_shanghai().strftime("%Y%m%d")
    filename = config.filename_pattern.format(date=review_date)
    path = output_dir / filename
    path.write_text(report_markdown, encoding="utf-8")
    return path


def _run_async(coro) -> bool:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return bool(asyncio.run(coro))

    with ThreadPoolExecutor(max_workers=1) as executor:
        return bool(executor.submit(lambda: asyncio.run(coro)).result())


def _collect_data(config: DailyReviewConfig) -> tuple[MacroData, LiquidityData, SectorData, List[StockEntry]]:
    with ThreadPoolExecutor(max_workers=4) as pool:
        macro_f = pool.submit(fetch_macro)
        liquidity_f = pool.submit(fetch_liquidity, config)
        sectors_f = pool.submit(fetch_sectors, config)
        stocks_f = pool.submit(fetch_stocks, config)

    macro = macro_f.result()
    liquidity = liquidity_f.result()
    sectors = sectors_f.result()
    stocks = stocks_f.result()
    return macro, liquidity, sectors, stocks


def _to_jsonable(value: Any) -> Any:
    """Convert dataclass/date values into JSON-serializable payload."""

    if is_dataclass(value):
        value = asdict(value)
    if isinstance(value, dict):
        return {str(k): _to_jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def _build_snapshot(
    *,
    macro: MacroData,
    liquidity: LiquidityData,
    sectors: SectorData,
    sector_analysis: SectorAnalysis,
    stocks: List[StockEntry],
    regimes: List[RegimeResult],
    anomalies: List[AnomalyAlert],
    summary: str,
    report_path: Path,
) -> Dict[str, Any]:
    now = today_shanghai()
    red_count = sum(1 for item in anomalies if item.level == "RED")
    yellow_count = sum(1 for item in anomalies if item.level == "YELLOW")
    return {
        "review_date": now.strftime("%Y-%m-%d"),
        "generated_at": now.strftime("%Y-%m-%d %H:%M:%S %Z"),
        "summary": summary or "",
        "macro": _to_jsonable(macro),
        "liquidity": _to_jsonable(liquidity),
        "sectors": _to_jsonable(sectors),
        "sector_analysis": _to_jsonable(sector_analysis),
        "stocks": _to_jsonable(stocks),
        "regimes": _to_jsonable(regimes),
        "anomalies": {
            "red_count": red_count,
            "yellow_count": yellow_count,
            "items": _to_jsonable(anomalies),
        },
        "report_path": str(report_path),
    }


def run_daily_review(
    *,
    config: Optional[DailyReviewConfig] = None,
    send_telegram: bool = True,
    use_llm: bool = True,
) -> str:
    """Run full daily review pipeline and return markdown report."""

    cfg = config or load_config()
    macro, liquidity, sectors, stocks = _collect_data(cfg)
    liquidity = _hydrate_liquidity_from_stocks(liquidity, stocks)
    sectors = _hydrate_sectors_from_stocks(sectors, stocks)
    stocks = _enrich_stocks_with_sector(stocks, sectors)

    us_regime: RegimeResult = evaluate_regime("US", macro, liquidity, sectors)
    hk_regime: RegimeResult = evaluate_regime("HK", macro, liquidity, sectors)
    a_regime: RegimeResult = evaluate_regime("A", macro, liquidity, sectors)

    sector_analysis: SectorAnalysis = analyze_sector_preference(sectors)
    anomalies: List[AnomalyAlert] = detect_anomalies(macro, liquidity, stocks, sectors)

    summary_cfg = cfg if use_llm else replace(cfg, llm_provider="none", llm_api_key=None)
    summary = generate_llm_summary(
        macro=macro,
        liquidity=liquidity,
        sectors=sectors,
        stocks=stocks,
        anomalies=anomalies,
        regimes=[us_regime, hk_regime, a_regime],
        config=summary_cfg,
    )

    report = render_report(
        macro=macro,
        liquidity=liquidity,
        sectors=sectors,
        sector_analysis=sector_analysis,
        stocks=stocks,
        regimes=[us_regime, hk_regime, a_regime],
        anomalies=anomalies,
        summary=summary,
    )

    report_path = save_report(report, cfg)
    logger.info("Daily review saved to %s", report_path)
    snapshot = _build_snapshot(
        macro=macro,
        liquidity=liquidity,
        sectors=sectors,
        sector_analysis=sector_analysis,
        stocks=stocks,
        regimes=[us_regime, hk_regime, a_regime],
        anomalies=anomalies,
        summary=summary,
        report_path=report_path,
    )
    snapshot_path = save_snapshot(snapshot, cfg)
    logger.info("Daily review snapshot saved to %s", snapshot_path)

    if send_telegram:
        sent = _run_async(send_review(report, cfg))
        logger.info("Daily review telegram sent: %s", sent)

    return report


if __name__ == "__main__":
    run_daily_review()

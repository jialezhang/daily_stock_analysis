# -*- coding: utf-8 -*-
"""Portfolio review runner."""

from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
import json
import logging
from typing import Any, Dict, Optional

from src.portfolio.analysis.anomaly import detect_anomalies
from src.portfolio.analysis.health_check import evaluate_health
from src.portfolio.analysis.market_regime import evaluate_market_regimes
from src.portfolio.analysis.rebalance import build_rebalance_plan
from src.portfolio.analysis.sector_flow import analyze_sector_flow
from src.portfolio.config import STOCK_TAGS
from src.portfolio.data.liquidity_fetcher import fetch_liquidity_data
from src.portfolio.data.macro_fetcher import fetch_macro_data
from src.portfolio.data.sector_fetcher import fetch_sector_data
from src.portfolio.models import Portfolio, PortfolioHolding
from src.portfolio.report.llm_digest import generate_portfolio_llm_digest
from src.portfolio.report.renderer import render_portfolio_report
from src.storage import get_db


logger = logging.getLogger(__name__)


def _safe_float(value: Any, default: float = 0.0) -> float:
    """Safely convert a value to float."""
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_positive_float(value: Any, default: float = 0.0) -> float:
    """Safely convert a value to a positive float."""
    result = _safe_float(value, default=default)
    return result if result > 0 else default


def _infer_market_from_ticker(ticker: str) -> str:
    """Infer market code from ticker shape."""
    ticker_upper = str(ticker or "").strip().upper()
    if ticker_upper in {"BTC", "ETH", "SOL", "BNB"}:
        return "CRYPTO"
    if ticker_upper.isdigit() and len(ticker_upper) == 5:
        return "HK"
    if ticker_upper.isdigit() and len(ticker_upper) == 6:
        return "A"
    return "US"


def _normalize_market(value: Any, ticker: str) -> str:
    """Normalize market label to portfolio constants."""
    normalized = str(value or "").strip().upper()
    aliases = {
        "US": "US",
        "USA": "US",
        "NASDAQ": "US",
        "NYSE": "US",
        "HK": "HK",
        "HKG": "HK",
        "A": "A",
        "CN": "A",
        "ASHARE": "A",
        "A_SHARE": "A",
        "CRYPTO": "CRYPTO",
        "BTC": "CRYPTO",
    }
    if normalized in aliases:
        return aliases[normalized]
    return _infer_market_from_ticker(ticker)


def _normalize_currency(value: Any) -> str:
    """Normalize currency code for portfolio bridge logic."""
    text = str(value or "").strip().upper()
    if text in {"RMB", "CNY", "CNH"}:
        return "CNY"
    if text == "HKD":
        return "HKD"
    return "USD"


def _to_cny_rate(currency: str, fx: Dict[str, Any]) -> float:
    """Convert one unit of currency to CNY."""
    normalized = _normalize_currency(currency)
    if normalized == "CNY":
        return 1.0
    if normalized == "HKD":
        return max(_safe_float(fx.get("hkd_cny"), 0.92), 0.000001)
    return max(_safe_float(fx.get("usd_cny"), 7.2), 0.000001)


def _load_json_payload(raw_value: str) -> Optional[Any]:
    """Load JSON with empty-string tolerance."""
    text = str(raw_value or "").strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        logger.warning("Portfolio JSON payload is invalid")
        return None


def _load_stock_tags(config: Any) -> Dict[str, Dict[str, Any]]:
    """Merge default stock tags with configured overrides."""
    merged = {key.upper(): dict(value) for key, value in STOCK_TAGS.items()}
    overrides = _load_json_payload(getattr(config, "portfolio_stock_tags_json", ""))
    if isinstance(overrides, dict):
        for ticker, payload in overrides.items():
            ticker_upper = str(ticker or "").strip().upper()
            if not ticker_upper or not isinstance(payload, dict):
                continue
            merged[ticker_upper] = {**merged.get(ticker_upper, {}), **payload}
    return merged


def build_portfolio_from_config(config: Any) -> Optional[Portfolio]:
    """Build a portfolio object from config JSON fields."""
    payload = _load_json_payload(getattr(config, "portfolio_holdings_json", ""))
    if payload is None:
        return None

    if isinstance(payload, list):
        payload = {"holdings": payload}
    if not isinstance(payload, dict):
        logger.warning("Portfolio holdings JSON must be a JSON object or array")
        return None

    stock_tags = _load_stock_tags(config)
    holdings_raw = payload.get("holdings", payload.get("positions", []))
    if not isinstance(holdings_raw, list):
        logger.warning("Portfolio holdings JSON is missing a holdings array")
        return None

    holdings = []
    for item in holdings_raw:
        if not isinstance(item, dict):
            continue
        ticker = str(item.get("ticker") or item.get("symbol") or "").strip().upper()
        if not ticker:
            continue

        tag = stock_tags.get(ticker, {})
        market = _normalize_market(item.get("market") or tag.get("market"), ticker)
        shares = _safe_float(item.get("shares", item.get("quantity")))
        avg_cost = _safe_float(item.get("avg_cost", item.get("cost_price", item.get("cost"))))
        current_price = _safe_float(item.get("current_price", item.get("latest_price", item.get("price"))))
        value_cny = _safe_float(
            item.get("value_cny", item.get("market_value_cny", item.get("market_value_output", item.get("value"))))
        )
        if value_cny <= 0 and shares > 0 and current_price > 0:
            value_cny = shares * current_price

        holdings.append(
            PortfolioHolding(
                ticker=ticker,
                name=str(item.get("name") or item.get("display_name") or ticker),
                market=market,
                shares=shares,
                avg_cost=avg_cost,
                current_price=current_price,
                lot_size=_safe_positive_float(
                    item.get("lot_size", item.get("board_lot", item.get("shares_per_lot", item.get("trade_unit")))),
                    default=1.0,
                ),
                value_cny=value_cny,
                weight_pct=_safe_float(item.get("weight_pct", item.get("ratio_pct"))),
                daily_change_pct=_safe_float(item.get("daily_change_pct", item.get("change_pct"))),
                sector=str(item.get("sector") or tag.get("sector") or ""),
                style=str(item.get("style") or tag.get("style") or ""),
                beta_level=str(item.get("beta_level") or item.get("beta") or tag.get("beta_level") or tag.get("beta") or "medium"),
            )
        )

    initial_capital = _safe_float(
        payload.get("initial_capital", getattr(config, "portfolio_initial_capital", 1_400_000.0)),
        default=1_400_000.0,
    )
    target_return = _safe_float(
        payload.get("target_return", getattr(config, "portfolio_target_return", 0.30)),
        default=0.30,
    )
    cash_cny = _safe_float(payload.get("cash_cny"))
    cash_usd = _safe_float(payload.get("cash_usd"))
    cash_hkd = _safe_float(payload.get("cash_hkd"))
    crypto_value_cny = _safe_float(payload.get("crypto_value_cny"))
    total_value_cny = _safe_float(payload.get("total_value_cny"))
    if total_value_cny <= 0:
        total_value_cny = (
            sum(item.value_cny for item in holdings)
            + cash_cny
            + cash_usd
            + cash_hkd
            + crypto_value_cny
        )

    if total_value_cny > 0:
        for holding in holdings:
            if holding.weight_pct <= 0 and holding.value_cny > 0:
                holding.weight_pct = round(holding.value_cny / total_value_cny * 100.0, 2)

    return Portfolio(
        total_value_cny=total_value_cny,
        initial_capital=initial_capital,
        target_value=round(initial_capital * (1.0 + target_return), 2),
        output_currency=_normalize_currency(payload.get("output_currency", "CNY")),
        output_to_cny_rate=_to_cny_rate(_normalize_currency(payload.get("output_currency", "CNY")), {}),
        holdings=holdings,
        cash_cny=cash_cny,
        cash_usd=cash_usd,
        cash_hkd=cash_hkd,
        crypto_value_cny=crypto_value_cny,
        peak_value_cny=(
            _safe_float(payload.get("peak_value_cny")) if payload.get("peak_value_cny") not in (None, "") else None
        ),
    )


def build_portfolio_from_position_management_module(
    module: Any,
    config: Optional[Any] = None,
) -> Optional[Portfolio]:
    """Build a portfolio snapshot from the global position management module."""
    if not isinstance(module, dict):
        return None

    target = module.get("target") if isinstance(module.get("target"), dict) else {}
    fx = module.get("fx") if isinstance(module.get("fx"), dict) else {}
    derived = module.get("derived") if isinstance(module.get("derived"), dict) else {}
    holdings_raw = module.get("holdings") if isinstance(module.get("holdings"), list) else []
    if not holdings_raw:
        return None

    output_currency = _normalize_currency(target.get("output_currency"))
    output_to_cny = _to_cny_rate(output_currency, fx)
    stock_tags = _load_stock_tags(config or {})

    holdings = []
    cash_cny = 0.0
    for item in holdings_raw:
        if not isinstance(item, dict):
            continue

        primary = str(item.get("asset_primary") or "").strip()
        secondary = str(item.get("asset_secondary") or "").strip()
        ticker = str(item.get("symbol") or "").strip().upper()
        quantity = _safe_float(item.get("quantity"))
        latest_price = _safe_float(item.get("latest_price", item.get("current_price")))
        daily_change_pct = _safe_float(item.get("change_pct", item.get("daily_change_pct")))
        native_currency = _normalize_currency(item.get("currency"))
        native_value = quantity * latest_price
        value_output = _safe_float(item.get("market_value_output"))
        value_cny = value_output * output_to_cny if value_output > 0 else native_value * _to_cny_rate(native_currency, fx)
        tag = stock_tags.get(ticker, {})

        if primary in {"现金", "债券", "货币基金", "贵金属"}:
            cash_cny += value_cny
            continue

        if not ticker:
            continue

        market_hint = item.get("market") or tag.get("market")
        if primary == "加密货币":
            market = "CRYPTO"
        else:
            market = _normalize_market(market_hint, ticker)

        holdings.append(
            PortfolioHolding(
                ticker=ticker,
                name=str(item.get("name") or tag.get("name") or ticker),
                market=market,
                shares=quantity,
                avg_cost=_safe_float(item.get("avg_cost", item.get("cost_price", item.get("cost")))),
                current_price=latest_price,
                lot_size=_safe_positive_float(
                    item.get("lot_size", item.get("board_lot", item.get("shares_per_lot", item.get("trade_unit")))),
                    default=1.0,
                ),
                value_cny=value_cny,
                weight_pct=_safe_float(item.get("weight_pct", item.get("ratio_pct"))),
                daily_change_pct=daily_change_pct,
                sector=str(item.get("sector") or tag.get("sector") or ""),
                style=str(item.get("style") or tag.get("style") or ""),
                beta_level=str(item.get("beta_level") or item.get("beta") or tag.get("beta_level") or tag.get("beta") or "medium"),
            )
        )

    initial_capital = _safe_float(target.get("initial_position")) * output_to_cny
    if initial_capital <= 0:
        initial_capital = _safe_float(getattr(config, "portfolio_initial_capital", 1_400_000.0), 1_400_000.0)
    target_return = _safe_float(target.get("target_return_pct")) / 100.0
    if target_return == 0.0 and target.get("target_return_pct") in (None, ""):
        target_return = _safe_float(getattr(config, "portfolio_target_return", 0.30), 0.30)

    totals = derived.get("totals") if isinstance(derived.get("totals"), dict) else {}
    total_value_cny = _safe_float(totals.get("total_value_output")) * output_to_cny
    if total_value_cny <= 0:
        total_value_cny = cash_cny + sum(item.value_cny for item in holdings)
    if total_value_cny <= 0:
        return None

    for holding in holdings:
        if holding.weight_pct <= 0 and holding.value_cny > 0:
            holding.weight_pct = round(holding.value_cny / total_value_cny * 100.0, 2)

    return Portfolio(
        total_value_cny=round(total_value_cny, 2),
        initial_capital=round(initial_capital, 2),
        target_value=round(initial_capital * (1.0 + target_return), 2),
        output_currency=output_currency,
        output_to_cny_rate=output_to_cny,
        holdings=holdings,
        cash_cny=round(cash_cny, 2),
        cash_usd=0.0,
        cash_hkd=0.0,
        crypto_value_cny=0.0,
    )


def build_portfolio_from_sources(config: Any, position_module: Optional[Any] = None) -> Optional[Portfolio]:
    """Resolve the portfolio source with position management as first priority."""
    portfolio = build_portfolio_from_position_management_module(module=position_module, config=config)
    if portfolio is not None:
        return portfolio
    return build_portfolio_from_config(config)


def run_portfolio_review(
    portfolio: Portfolio,
    notifier: Optional[object],
    analyzer: Optional[object] = None,
    send_notification: bool = True,
) -> Optional[str]:
    """Run the portfolio review end-to-end with safe fallbacks."""

    try:
        with ThreadPoolExecutor(max_workers=4) as executor:
            macro_future = executor.submit(fetch_macro_data)
            liquidity_future = executor.submit(fetch_liquidity_data)
            sector_future = executor.submit(fetch_sector_data)
            macro = macro_future.result()
            liquidity = liquidity_future.result()
            sector = sector_future.result()

        health = evaluate_health(portfolio)
        regimes = evaluate_market_regimes(macro, liquidity, sector)
        sector_analysis = analyze_sector_flow(sector)
        anomalies = detect_anomalies(macro, liquidity, portfolio)
        plan = build_rebalance_plan(portfolio, health, regimes, anomalies, sector_analysis)
        llm_digest = generate_portfolio_llm_digest(portfolio, health, regimes, sector_analysis, plan, anomalies, analyzer)
        report = render_portfolio_report(portfolio, health, regimes, sector_analysis, plan, anomalies, llm_digest)

        try:
            get_db().save_portfolio_snapshot(date.today(), portfolio, health, report)
        except Exception as exc:
            logger.warning("Failed to persist portfolio snapshot: %s", exc)

        if notifier is not None and hasattr(notifier, "save_report_to_file"):
            try:
                date_str = datetime.now().strftime("%Y%m%d")
                notifier.save_report_to_file(report, f"portfolio_review_{date_str}.md")
            except Exception as exc:
                logger.warning("Failed to save portfolio review file: %s", exc)

        if send_notification and notifier is not None and hasattr(notifier, "send"):
            try:
                notifier.send(f"📦 组合复盘\n\n{report}", email_send_to_all=True)
            except Exception as exc:
                logger.warning("Failed to send portfolio review notification: %s", exc)
        return report
    except Exception as exc:
        logger.error("Portfolio review failed: %s", exc, exc_info=True)
        return None

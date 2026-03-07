# -*- coding: utf-8 -*-
"""Portfolio rebalance planning."""

import math
from typing import Dict, List, Tuple

from src.portfolio.config import REBALANCE_THRESHOLD_PCT, TARGET_ALLOCATION
from src.portfolio.models import AnomalyAlert, HealthReport, Portfolio, RebalancePlan, RegimeResult, SectorAnalysis, TradeAction


def _normalize_market_key(value: str) -> str:
    """Normalize market aliases used by different data sources."""
    market = str(value or "").upper()
    return "A" if market == "CN" else market


def _total_asset(portfolio: Portfolio) -> float:
    total = float(portfolio.total_value_cny or 0.0)
    if total > 0:
        return total
    return (
        sum(float(item.value_cny or 0.0) for item in portfolio.holdings)
        + float(portfolio.cash_cny or 0.0)
        + float(portfolio.cash_usd or 0.0)
        + float(portfolio.cash_hkd or 0.0)
    )


def _current_allocations(portfolio: Portfolio, total_asset: float) -> Dict[str, float]:
    values = {"US": 0.0, "HK": 0.0, "A": 0.0, "CASH": 0.0, "CRYPTO": 0.0}
    for holding in portfolio.holdings:
        market = _normalize_market_key(str(holding.market or ""))
        if market in values:
            values[market] += float(holding.value_cny or 0.0)
    values["CASH"] += float(portfolio.cash_cny or 0.0) + float(portfolio.cash_usd or 0.0) + float(portfolio.cash_hkd or 0.0)
    if values["CRYPTO"] == 0.0:
        values["CRYPTO"] = float(portfolio.crypto_value_cny or 0.0)
    return {key: (value / total_asset * 100.0) if total_asset > 0 else 0.0 for key, value in values.items()}


def _dynamic_targets(regimes: List[RegimeResult]) -> Dict[str, float]:
    targets = {key: float(value["target_pct"]) for key, value in TARGET_ALLOCATION.items()}
    regime_map = {item.market: item for item in regimes}
    for market in ("US", "HK", "A"):
        if market in regime_map:
            targets[market] += float(regime_map[market].allocation_adjust_pct)
    targets["CASH"] = max(0.0, 100.0 - targets["US"] - targets["HK"] - targets["A"] - targets["CRYPTO"])
    return targets


def _pick_weakest(holdings, market: str):
    candidates = [holding for holding in holdings if _normalize_market_key(str(holding.market or "")) == market]
    return min(candidates, key=lambda item: float(item.daily_change_pct or 0.0), default=None)


def _pick_strongest(holdings, market: str):
    candidates = [holding for holding in holdings if _normalize_market_key(str(holding.market or "")) == market]
    return max(candidates, key=lambda item: float(item.daily_change_pct or 0.0), default=None)


def _round_trade_to_lot(holding, desired_amount_cny: float) -> Tuple[float, float, float]:
    """Round a trade to a valid board-lot amount."""
    absolute_amount = abs(float(desired_amount_cny or 0.0))
    if absolute_amount <= 0:
        return 0.0, 0.0, max(float(getattr(holding, "lot_size", 1.0) or 1.0), 1.0)

    market = _normalize_market_key(str(getattr(holding, "market", "") or ""))
    lot_size = max(float(getattr(holding, "lot_size", 1.0) or 1.0), 1.0)
    shares = max(float(getattr(holding, "shares", 0.0) or 0.0), 0.0)
    current_value = max(float(getattr(holding, "value_cny", 0.0) or 0.0), 0.0)
    unit_value = current_value / shares if shares > 0 and current_value > 0 else max(float(getattr(holding, "current_price", 0.0) or 0.0), 0.0)

    if market == "CRYPTO" or unit_value <= 0:
        return round(desired_amount_cny, 2), 0.0, lot_size

    lot_value = unit_value * lot_size
    if lot_value <= 0:
        return round(desired_amount_cny, 2), 0.0, lot_size

    lots = math.floor((absolute_amount + 1e-9) / lot_value)
    if lots <= 0:
        return 0.0, 0.0, lot_size

    share_quantity = lots * lot_size
    trade_amount = share_quantity * unit_value
    if desired_amount_cny < 0:
        trade_amount *= -1.0
    return round(trade_amount, 2), round(share_quantity, 6), lot_size


def build_rebalance_plan(
    portfolio: Portfolio,
    health: HealthReport,
    regimes: List[RegimeResult],
    anomalies: List[AnomalyAlert],
    sector_analysis: SectorAnalysis,
) -> RebalancePlan:
    """Build a prioritized rebalance plan."""

    del health, sector_analysis
    total_asset = _total_asset(portfolio)
    current = _current_allocations(portfolio, total_asset)
    targets = _dynamic_targets(regimes)
    actions: List[TradeAction] = []
    used_tickers = set()

    for alert in anomalies:
        if alert.level != "RED":
            continue
        for ticker in alert.affected_holdings:
            holding = next((item for item in portfolio.holdings if item.ticker == ticker), None)
            if holding is None or ticker in used_tickers:
                continue
            current_value = float(holding.value_cny or 0.0)
            raw_trade_amount = min(current_value * 0.1, current_value * 0.3)
            trade_amount, share_quantity, lot_size = _round_trade_to_lot(holding, -raw_trade_amount)
            if abs(trade_amount) <= 0:
                continue
            actions.append(
                TradeAction(
                    direction="SELL",
                    ticker=holding.ticker,
                    name=holding.name,
                    market=_normalize_market_key(str(holding.market or "")),
                    current_value_cny=current_value,
                    current_pct=float(holding.weight_pct or 0.0),
                    target_pct=max(targets.get(_normalize_market_key(str(holding.market or "")), 0.0), 0.0),
                    trade_amount_cny=trade_amount,
                    reason=alert.action,
                    priority=1,
                    urgency="today",
                    share_quantity=share_quantity,
                    lot_size=lot_size,
                )
            )
            used_tickers.add(ticker)

    for market in ("US", "HK", "A"):
        deviation = current.get(market, 0.0) - targets.get(market, 0.0)
        if deviation > REBALANCE_THRESHOLD_PCT:
            weakest = _pick_weakest(portfolio.holdings, market)
            if weakest and weakest.ticker not in used_tickers:
                raw_amount = total_asset * (deviation / 100.0) * 0.5
                capped_amount = min(raw_amount, float(weakest.value_cny or 0.0) * 0.3)
                trade_amount, share_quantity, lot_size = _round_trade_to_lot(weakest, -capped_amount)
                if abs(trade_amount) > 0:
                    actions.append(
                        TradeAction(
                            direction="SELL",
                            ticker=weakest.ticker,
                            name=weakest.name,
                            market=market,
                            current_value_cny=float(weakest.value_cny or 0.0),
                            current_pct=float(weakest.weight_pct or 0.0),
                            target_pct=targets.get(market, 0.0),
                            trade_amount_cny=trade_amount,
                            reason=f"{market} 当前超配 {deviation:.2f}%，优先卖出弱势持仓。",
                            priority=2,
                            urgency="this_week",
                            share_quantity=share_quantity,
                            lot_size=lot_size,
                        )
                    )
                    used_tickers.add(weakest.ticker)
        elif deviation < -REBALANCE_THRESHOLD_PCT:
            strongest = _pick_strongest(portfolio.holdings, market)
            if strongest and strongest.ticker not in used_tickers:
                raw_amount = total_asset * (abs(deviation) / 100.0) * 0.5
                capped_amount = min(raw_amount, total_asset * 0.05)
                trade_amount, share_quantity, lot_size = _round_trade_to_lot(strongest, capped_amount)
                if trade_amount > 0:
                    actions.append(
                        TradeAction(
                            direction="BUY",
                            ticker=strongest.ticker,
                            name=strongest.name,
                            market=market,
                            current_value_cny=float(strongest.value_cny or 0.0),
                            current_pct=float(strongest.weight_pct or 0.0),
                            target_pct=targets.get(market, 0.0),
                            trade_amount_cny=trade_amount,
                            reason=f"{market} 当前低配 {abs(deviation):.2f}%，优先补最强持仓。",
                            priority=2,
                            urgency="this_week",
                            share_quantity=share_quantity,
                            lot_size=lot_size,
                        )
                    )
                    used_tickers.add(strongest.ticker)

    actions.sort(key=lambda item: (item.priority, item.direction != "SELL", item.market, item.ticker))
    net_trade = sum(action.trade_amount_cny for action in actions)
    cash_after_pct = current.get("CASH", 0.0)
    if total_asset > 0:
        cash_after_pct = (
            float(portfolio.cash_cny or 0.0) + float(portfolio.cash_usd or 0.0) + float(portfolio.cash_hkd or 0.0) - net_trade
        ) / total_asset * 100.0

    return RebalancePlan(
        date=regimes[0].score_details[0].get("date", "") if regimes and regimes[0].score_details else "",
        total_asset_cny=round(total_asset, 2),
        cash_after_rebalance_pct=round(cash_after_pct, 2),
        actions=actions,
        expected_allocation={key: round(value, 2) for key, value in targets.items()},
        summary=f"生成 {len(actions)} 条交易建议，优先级 1 动作 {sum(1 for item in actions if item.priority == 1)} 条。",
    )

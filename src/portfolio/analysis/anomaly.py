# -*- coding: utf-8 -*-
"""Portfolio anomaly detection."""

from typing import Dict, List

from src.portfolio.config import CONCENTRATION_LIMITS
from src.portfolio.models import AnomalyAlert, LiquidityData, MacroData, Portfolio


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


def _weight_pct(portfolio: Portfolio, holding_index: int) -> float:
    holding = portfolio.holdings[holding_index]
    if float(holding.weight_pct or 0.0) > 0:
        return float(holding.weight_pct or 0.0)
    total = _total_asset(portfolio)
    return (float(holding.value_cny or 0.0) / total * 100.0) if total > 0 else 0.0


def _style_weights(portfolio: Portfolio) -> Dict[str, float]:
    weights: Dict[str, float] = {}
    for idx, holding in enumerate(portfolio.holdings):
        weights[str(holding.style or "unknown")] = weights.get(str(holding.style or "unknown"), 0.0) + _weight_pct(portfolio, idx)
    return weights


def _build_alert(level: str, name: str, message: str, action: str, affected: List[str]) -> AnomalyAlert:
    return AnomalyAlert(level=level, name=name, message=message, action=action, affected_holdings=affected)


def detect_anomalies(macro: MacroData, liquidity: LiquidityData, portfolio: Portfolio) -> List[AnomalyAlert]:
    """Detect RED and YELLOW anomalies for the current portfolio."""

    alerts: List[AnomalyAlert] = []
    total_asset = _total_asset(portfolio)
    cash_pct = (
        (float(portfolio.cash_cny or 0.0) + float(portfolio.cash_usd or 0.0) + float(portfolio.cash_hkd or 0.0)) / total_asset * 100.0
        if total_asset > 0
        else 0.0
    )
    style_weights = _style_weights(portfolio)

    us_high_beta = [
        holding.ticker
        for holding in portfolio.holdings
        if str(holding.market or "").upper() == "US" and str(holding.beta_level or "").lower() in {"high", "very_high"}
    ]
    hk_a_holdings = [
        holding.ticker for holding in portfolio.holdings if str(holding.market or "").upper() in {"HK", "A"}
    ]
    single_stock_crash = [holding.ticker for holding in portfolio.holdings if float(holding.daily_change_pct or 0.0) < -8.0]
    cash_fill_candidates = [
        holding.ticker
        for holding in sorted(portfolio.holdings, key=lambda item: float(item.daily_change_pct or 0.0))[:3]
    ]
    concentration_items = [
        holding.ticker
        for idx, holding in enumerate(portfolio.holdings)
        if _weight_pct(portfolio, idx) > float(CONCENTRATION_LIMITS["single_stock_max_pct"])
    ]
    concentration_items.extend(
        [style for style, weight in style_weights.items() if weight > float(CONCENTRATION_LIMITS["single_style_max_pct"])]
    )

    if (macro.vix is not None and float(macro.vix) > 30.0) or (
        macro.vix_daily_change_pct is not None and float(macro.vix_daily_change_pct) > 30.0
    ):
        alerts.append(
            _build_alert(
                "RED",
                "VIX 恐慌飙升",
                f"VIX={float(macro.vix or 0.0):.2f}，日变动={float(macro.vix_daily_change_pct or 0.0):.2f}%。",
                f"总仓位降至50%以下。优先卖出高 beta 美股：{', '.join(us_high_beta) or 'N/A'}。",
                us_high_beta,
            )
        )

    if macro.treasury_10y_daily_change_bps is not None and abs(float(macro.treasury_10y_daily_change_bps)) > 15.0:
        alerts.append(
            _build_alert(
                "RED",
                "美债收益率冲击",
                f"10Y 日变动 {float(macro.treasury_10y_daily_change_bps):.2f}bps。",
                f"减仓美股成长股。受影响：{', '.join(us_high_beta) or 'N/A'}。",
                us_high_beta,
            )
        )

    if macro.usd_index is not None and float(macro.usd_index) > 107.0:
        alerts.append(
            _build_alert(
                "RED",
                "美元指数突破107",
                f"美元指数升至 {float(macro.usd_index):.2f}。",
                f"减仓港股和A股。受影响：{', '.join(hk_a_holdings) or 'N/A'}。",
                hk_a_holdings,
            )
        )

    if single_stock_crash:
        alerts.append(
            _build_alert(
                "RED",
                "单只持仓暴跌超8%",
                f"触发标的：{', '.join(single_stock_crash)}。",
                f"检查 {', '.join(single_stock_crash)} 是否有利空消息；无明确催化剂则下一开盘减半仓位。",
                single_stock_crash,
            )
        )

    if portfolio.peak_value_cny and total_asset > 0:
        drawdown_pct = (1.0 - total_asset / float(portfolio.peak_value_cny)) * 100.0
        if drawdown_pct > 15.0:
            affected = [holding.ticker for holding in portfolio.holdings]
            alerts.append(
                _build_alert(
                    "RED",
                    "组合回撤超15%",
                    f"当前组合较峰值回撤 {drawdown_pct:.2f}%。",
                    "启动止损纪律：权益仓位降至60%，优先锁定剩余流动性。",
                    affected,
                )
            )

    if macro.vix is not None and 25.0 < float(macro.vix) <= 30.0:
        alerts.append(
            _build_alert(
                "YELLOW",
                "VIX 进入警戒区",
                f"VIX 当前 {float(macro.vix):.2f}。",
                "暂停新开仓，先观察 1-2 个交易日。",
                [],
            )
        )

    if cash_pct < 5.0:
        alerts.append(
            _build_alert(
                "YELLOW",
                "现金比例低于最低线",
                f"现金占比仅 {cash_pct:.2f}%。",
                f"卖出最弱持仓补充现金至10%。候选：{', '.join(cash_fill_candidates) or 'N/A'}。",
                cash_fill_candidates,
            )
        )

    if concentration_items:
        alerts.append(
            _build_alert(
                "YELLOW",
                "集中度超限",
                f"超限对象：{', '.join(concentration_items)}。",
                f"未来1-2天逐步减仓超配头寸：{', '.join(concentration_items)}。",
                concentration_items,
            )
        )

    if macro.hyg_5d_return is not None and float(macro.hyg_5d_return) < -2.0:
        alerts.append(
            _build_alert(
                "YELLOW",
                "美国信用利差走阔",
                f"HYG 5日收益 {float(macro.hyg_5d_return):.2f}%。",
                f"美股配置转向大盘蓝筹，减仓高 beta：{', '.join(us_high_beta) or 'N/A'}。",
                us_high_beta,
            )
        )

    level_order = {"RED": 0, "YELLOW": 1}
    holding_value_map = {holding.ticker: float(holding.value_cny or 0.0) for holding in portfolio.holdings}
    alerts.sort(
        key=lambda item: (
            level_order.get(item.level, 9),
            -sum(holding_value_map.get(symbol, 0.0) for symbol in item.affected_holdings),
        )
    )
    return alerts

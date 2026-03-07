# -*- coding: utf-8 -*-
"""Portfolio health diagnostics."""

from typing import Dict, List

from src.portfolio.config import CONCENTRATION_LIMITS, REBALANCE_THRESHOLD_PCT, TARGET_ALLOCATION
from src.portfolio.models import HealthIssue, HealthReport, Portfolio


def _normalize_market_key(value: str) -> str:
    """Normalize market aliases used by different data sources."""
    market = str(value or "").upper()
    return "A" if market == "CN" else market


def _total_asset(portfolio: Portfolio) -> float:
    total = float(portfolio.total_value_cny or 0.0)
    if total > 0:
        return total
    cash_total = float(portfolio.cash_cny or 0.0) + float(portfolio.cash_usd or 0.0) + float(portfolio.cash_hkd or 0.0)
    holdings_total = sum(float(item.value_cny or 0.0) for item in portfolio.holdings)
    return holdings_total + cash_total + float(portfolio.crypto_value_cny or 0.0)


def _allocation_current(portfolio: Portfolio, total_asset: float) -> Dict[str, float]:
    values = {"US": 0.0, "HK": 0.0, "A": 0.0, "CASH": 0.0, "CRYPTO": 0.0}
    for item in portfolio.holdings:
        market = _normalize_market_key(str(item.market or ""))
        if market in values:
            values[market] += float(item.value_cny or 0.0)
    values["CASH"] += float(portfolio.cash_cny or 0.0) + float(portfolio.cash_usd or 0.0) + float(portfolio.cash_hkd or 0.0)
    if values["CRYPTO"] == 0.0:
        values["CRYPTO"] = float(portfolio.crypto_value_cny or 0.0)
    return {key: round((value / total_asset * 100.0) if total_asset > 0 else 0.0, 2) for key, value in values.items()}


def _grade(score: int) -> str:
    if score >= 80:
        return "A"
    if score >= 60:
        return "B"
    if score >= 40:
        return "C"
    if score >= 20:
        return "D"
    return "F"


def evaluate_health(portfolio: Portfolio) -> HealthReport:
    """Evaluate portfolio health against concentration and allocation rules."""

    total_asset = _total_asset(portfolio)
    allocation_current = _allocation_current(portfolio, total_asset)
    allocation_target = {key: float(value["target_pct"]) for key, value in TARGET_ALLOCATION.items()}
    allocation_deviation = {
        key: round(allocation_current.get(key, 0.0) - allocation_target.get(key, 0.0), 2)
        for key in allocation_target
    }
    issues: List[HealthIssue] = []

    for market, deviation in allocation_deviation.items():
        if market == "CRYPTO" and abs(deviation) <= REBALANCE_THRESHOLD_PCT:
            continue
        if abs(deviation) > REBALANCE_THRESHOLD_PCT * 2:
            issues.append(
                HealthIssue(
                    severity="CRITICAL",
                    category="allocation",
                    title="市场配置偏离过大",
                    detail=f"{market} 当前 {allocation_current[market]:.2f}%，目标 {allocation_target[market]:.2f}%。",
                    action=f"优先修正 {market} 仓位，使其回到目标区间附近。",
                )
            )
        elif abs(deviation) > REBALANCE_THRESHOLD_PCT:
            issues.append(
                HealthIssue(
                    severity="WARNING",
                    category="allocation",
                    title="市场配置出现偏离",
                    detail=f"{market} 偏离目标 {deviation:+.2f}%。",
                    action=f"本周逐步调整 {market} 仓位。",
                )
            )

    cash_pct = allocation_current.get("CASH", 0.0)
    cash_min_pct = float(TARGET_ALLOCATION["CASH"]["min_pct"])
    cash_target_pct = float(TARGET_ALLOCATION["CASH"]["target_pct"])
    if cash_pct < cash_min_pct:
        issues.append(
            HealthIssue(
                severity="CRITICAL",
                category="cash",
                title="现金仓位低于最低线",
                detail=f"当前现金 {cash_pct:.2f}%，最低要求 {cash_min_pct:.2f}%。",
                action="立即通过减仓弱势头寸补充现金缓冲。",
            )
        )
    elif cash_pct < cash_target_pct:
        issues.append(
            HealthIssue(
                severity="WARNING",
                category="cash",
                title="现金仓位低于目标",
                detail=f"当前现金 {cash_pct:.2f}%，目标 {cash_target_pct:.2f}%。",
                action="控制新增仓位，优先恢复现金安全垫。",
            )
        )

    single_stock_limit = float(CONCENTRATION_LIMITS["single_stock_max_pct"])
    for holding in portfolio.holdings:
        weight_pct = float(holding.weight_pct or ((float(holding.value_cny or 0.0) / total_asset * 100.0) if total_asset > 0 else 0.0))
        if weight_pct > single_stock_limit:
            issues.append(
                HealthIssue(
                    severity="CRITICAL",
                    category="concentration",
                    title="单只持仓集中度过高",
                    detail=f"{holding.ticker} 占比 {weight_pct:.2f}%，上限 {single_stock_limit:.2f}%。",
                    action=f"分批降低 {holding.ticker} 仓位，避免单票风险主导组合。",
                )
            )

    top3_weight = sum(
        sorted(
            (
                float(item.weight_pct or ((float(item.value_cny or 0.0) / total_asset * 100.0) if total_asset > 0 else 0.0))
                for item in portfolio.holdings
            ),
            reverse=True,
        )[:3]
    )
    if top3_weight > float(CONCENTRATION_LIMITS["top3_stocks_max_pct"]):
        issues.append(
            HealthIssue(
                severity="WARNING",
                category="concentration",
                title="前三大持仓过于集中",
                detail=f"前三大持仓合计 {top3_weight:.2f}%。",
                action="将增量资金配置到低相关性资产，分散组合波动来源。",
            )
        )

    style_map: Dict[str, float] = {}
    for holding in portfolio.holdings:
        style = str(holding.style or "unknown")
        weight_pct = float(holding.weight_pct or ((float(holding.value_cny or 0.0) / total_asset * 100.0) if total_asset > 0 else 0.0))
        style_map[style] = style_map.get(style, 0.0) + weight_pct
    for style, weight_pct in style_map.items():
        if weight_pct > float(CONCENTRATION_LIMITS["single_style_max_pct"]):
            issues.append(
                HealthIssue(
                    severity="CRITICAL",
                    category="style",
                    title="风格集中度过高",
                    detail=f"{style} 风格合计占比 {weight_pct:.2f}%。",
                    action="新增仓位避免继续叠加同风格暴露，优先补足防守或低相关板块。",
                )
            )

    very_high_beta_weight = sum(
        float(item.weight_pct or ((float(item.value_cny or 0.0) / total_asset * 100.0) if total_asset > 0 else 0.0))
        for item in portfolio.holdings
        if str(item.beta_level or "").lower() == "very_high"
    )
    if very_high_beta_weight > float(CONCENTRATION_LIMITS["very_high_beta_max_pct"]):
        issues.append(
            HealthIssue(
                severity="WARNING",
                category="style",
                title="高 Beta 暴露偏高",
                detail=f"very_high beta 持仓合计 {very_high_beta_weight:.2f}%。",
                action="优先减持高波动仓位，控制组合下行弹性。",
            )
        )

    current_total = max(total_asset, 0.0)
    target_value = float(portfolio.target_value or 0.0)
    if current_total > 0 and target_value > current_total:
        required_return_pct = (target_value / current_total - 1.0) * 100.0
        severity = None
        if required_return_pct > 60.0:
            severity = "CRITICAL"
        elif required_return_pct > 40.0:
            severity = "WARNING"
        if severity:
            issues.append(
                HealthIssue(
                    severity=severity,
                    category="target",
                    title="目标收益压力过高",
                    detail=f"当前到目标仍需 {required_return_pct:.2f}% 收益。",
                    action="下调预期或降低组合波动，避免以高风险换取高回报。",
                )
            )

    critical_count = sum(1 for issue in issues if issue.severity == "CRITICAL")
    warning_count = sum(1 for issue in issues if issue.severity == "WARNING")
    score = max(0, 100 - critical_count * 15 - warning_count * 5)

    return HealthReport(
        score=score,
        grade=_grade(score),
        issues=issues,
        allocation_current=allocation_current,
        allocation_target=allocation_target,
        allocation_deviation=allocation_deviation,
    )

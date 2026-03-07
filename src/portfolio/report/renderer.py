# -*- coding: utf-8 -*-
"""Markdown renderer for portfolio review."""

from typing import List

from src.portfolio.models import AnomalyAlert, HealthReport, Portfolio, RebalancePlan, RegimeResult, SectorAnalysis

US_SECTOR_NAME_MAP = {
    "Technology": "科技",
    "Semiconductor": "半导体",
    "Communication": "通信",
    "Internet": "互联网",
    "Software": "软件",
    "Utilities": "公用事业",
    "Healthcare": "医疗",
    "Energy": "能源",
    "Aerospace": "航天航空",
    "E-commerce": "电商",
    "EV": "电动车",
    "AI_Infra": "AI 基础设施",
    "Materials": "材料",
    "Satellite": "卫星",
    "Crypto": "加密资产",
}

US_STYLE_LABEL_MAP = {
    "offensive": "进攻风格",
    "defensive": "防御风格",
    "cyclical": "周期风格",
    "mixed": "风格分散",
}

A_THEME_LABEL_MAP = {
    "ai": "AI 主线",
    "unclear": "主线不清晰",
}

HK_STYLE_LABEL_MAP = {
    "tech_leading": "科技领涨",
    "tech_lagging": "科技偏弱",
    "sync": "科技与大盘同步",
}

CURRENCY_LABEL_MAP = {
    "CNY": "CNY",
    "USD": "USD",
    "HKD": "HKD",
}


def _render_alerts(alerts: List[AnomalyAlert]) -> List[str]:
    if not alerts:
        return []
    lines = ["## 异常告警"]
    for alert in alerts:
        lines.append(f"- [{alert.level}] {alert.name}: {alert.message}")
        lines.append(f"  动作：{alert.action}")
    return lines


def _format_us_sector_name(name: str) -> str:
    return US_SECTOR_NAME_MAP.get(str(name or "").strip(), str(name or "").strip())


def _format_us_style(style: str) -> str:
    return US_STYLE_LABEL_MAP.get(str(style or "").strip(), str(style or "").strip() or "风格待定")


def _format_a_theme(theme: str) -> str:
    return A_THEME_LABEL_MAP.get(str(theme or "").strip(), str(theme or "").strip() or "主线待定")


def _format_hk_style(style: str) -> str:
    return HK_STYLE_LABEL_MAP.get(str(style or "").strip(), str(style or "").strip() or "风格待定")


def _localize_reasoning_text(value: str) -> str:
    return (
        str(value or "")
        .replace("offensive", "进攻")
        .replace("defensive", "防御")
        .replace("cyclical", "周期")
        .replace("mixed", "分散")
        .replace("tech_leading", "科技领涨")
        .replace("tech_lagging", "科技偏弱")
        .replace("sync", "同步")
        .replace("unclear", "不清晰")
    )


def _find_regime(regimes: List[RegimeResult], market: str) -> RegimeResult:
    for item in regimes:
        if str(item.market or "").upper() == market.upper():
            return item
    return RegimeResult(market=market)


def _format_output_currency(portfolio: Portfolio) -> str:
    return CURRENCY_LABEL_MAP.get(str(portfolio.output_currency or "CNY").upper(), str(portfolio.output_currency or "CNY").upper())


def _to_output_amount(amount_cny: float, portfolio: Portfolio) -> float:
    rate = float(portfolio.output_to_cny_rate or 0.0)
    if rate <= 0:
        return float(amount_cny or 0.0)
    return float(amount_cny or 0.0) / rate


def _format_us_sector_rows(sector_analysis: SectorAnalysis) -> List[str]:
    leaders = "；".join(
        f"{_format_us_sector_name(str(item.get('name') or ''))}（{str(item.get('ticker') or '')}，RS {float(item.get('rs') or 0.0):.2f}）"
        for item in sector_analysis.us_leaders[:3]
        if item.get("name")
    )
    laggards = "；".join(
        f"{_format_us_sector_name(str(item.get('name') or ''))}（{str(item.get('ticker') or '')}，RS {float(item.get('rs') or 0.0):.2f}）"
        for item in sector_analysis.us_laggards[:3]
        if item.get("name")
    )
    lines = [f"- 主线：{_format_us_style(sector_analysis.us_style)}"]
    if leaders:
        lines.append(f"- 领涨板块：{leaders}")
    if laggards:
        lines.append(f"- 领跌板块：{laggards}")
    if sector_analysis.us_style_reasoning:
        lines.append(f"- 解读：{_localize_reasoning_text(sector_analysis.us_style_reasoning)}")
    return lines


def _format_a_sector_rows(sector_analysis: SectorAnalysis) -> List[str]:
    leaders = "；".join(
        f"{str(item.get('name') or '')}({float(item.get('change_pct') or item.get('daily_return_pct') or 0.0):+.2f}%)"
        for item in sector_analysis.a_leaders[:5]
        if item.get("name")
    )
    laggards = "；".join(
        f"{str(item.get('name') or '')}({float(item.get('change_pct') or item.get('daily_return_pct') or 0.0):+.2f}%)"
        for item in sector_analysis.a_laggards[:5]
        if item.get("name")
    )
    lines = [f"- 主线：{_format_a_theme(sector_analysis.a_theme)}"]
    if leaders:
        lines.append(f"- 领涨行业：{leaders}")
    if laggards:
        lines.append(f"- 领跌行业：{laggards}")
    if sector_analysis.a_theme_reasoning:
        lines.append(f"- 解读：{_localize_reasoning_text(sector_analysis.a_theme_reasoning)}")
    return lines


def _format_hk_sector_rows(sector_analysis: SectorAnalysis) -> List[str]:
    lines = [
        f"- 主线：{_format_hk_style(sector_analysis.hk_style)}",
        f"- 强弱对比：恒生科技相对恒指 {sector_analysis.hk_tech_vs_hsi:+.2f}%",
    ]
    if sector_analysis.hk_tech_vs_hsi > 1.0:
        lines.append("- 解读：港股科技明显跑赢大盘，风险偏好集中在科技成长。")
    elif sector_analysis.hk_tech_vs_hsi < -1.0:
        lines.append("- 解读：港股科技弱于大盘，市场更偏防守或高股息方向。")
    else:
        lines.append("- 解读：港股科技与大盘节奏接近，风格暂未明显偏移。")
    return lines


def render_portfolio_report(
    portfolio: Portfolio,
    health: HealthReport,
    regimes: List[RegimeResult],
    sector_analysis: SectorAnalysis,
    plan: RebalancePlan,
    anomalies: List[AnomalyAlert],
    llm_digest: str,
) -> str:
    """Render a markdown portfolio review."""

    us_regime = _find_regime(regimes, "US")
    hk_regime = _find_regime(regimes, "HK")
    a_regime = _find_regime(regimes, "A")
    output_currency = _format_output_currency(portfolio)

    lines: List[str] = ["# 组合每日复盘"]
    lines.extend(_render_alerts(anomalies))
    lines.extend(
        [
            "## 健康评分",
            f"- 评分：{health.score}",
            f"- 等级：{health.grade}",
            "## 交易建议",
        ]
    )
    for action in plan.actions:
        lines.append(
            f"- P{action.priority} {action.direction} {action.ticker} {_to_output_amount(action.trade_amount_cny, portfolio):.2f} {output_currency}：{action.reason}"
        )

    lines.extend(
        [
            "## 板块风格",
            "### 美股",
            f"- 环境：{us_regime.regime_label} ({us_regime.total_score:.0f})",
        ]
    )
    lines.extend(_format_us_sector_rows(sector_analysis))
    lines.extend(
        [
            "### 港股",
            f"- 环境：{hk_regime.regime_label} ({hk_regime.total_score:.0f})",
        ]
    )
    lines.extend(_format_hk_sector_rows(sector_analysis))
    lines.extend(
        [
            "### A 股",
            f"- 环境：{a_regime.regime_label} ({a_regime.total_score:.0f})",
        ]
    )
    lines.extend(_format_a_sector_rows(sector_analysis))
    lines.append("## 持仓明细")

    for holding in portfolio.holdings:
        lines.append(
            f"- {holding.ticker} | {holding.market} | {_to_output_amount(holding.value_cny, portfolio):.2f} {output_currency} | {holding.weight_pct:.2f}% | {holding.daily_change_pct:+.2f}%"
        )

    lines.extend(
        [
            "## LLM 摘要",
            llm_digest,
            "## 目标追踪",
            f"- 初始资金：{_to_output_amount(portfolio.initial_capital, portfolio):.2f} {output_currency}",
            f"- 当前资产：{_to_output_amount(portfolio.total_value_cny, portfolio):.2f} {output_currency}",
            f"- 目标资产：{_to_output_amount(portfolio.target_value, portfolio):.2f} {output_currency}",
        ]
    )
    return "\n".join(lines) + "\n"

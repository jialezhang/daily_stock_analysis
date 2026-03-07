# -*- coding: utf-8 -*-
"""Market regime evaluation."""

from typing import Any, Dict, List, Tuple

from src.portfolio.config import REGIME_DIMENSIONS, REGIME_POSITION_MAP
from src.portfolio.models import LiquidityData, MacroData, RegimeResult, SectorData


def _trend_score(close: Any, ma_short: Any, ma_long: Any, label: str) -> Tuple[int, str]:
    if close is None or ma_short is None or ma_long is None:
        return 0, f"{label} 数据缺失，维持中性。"
    if float(close) > float(ma_short) > float(ma_long):
        return 1, f"{label} 多头排列，趋势向上。"
    if float(close) < float(ma_short) < float(ma_long):
        return -1, f"{label} 空头排列，趋势偏弱。"
    return 0, f"{label} 均线未形成单边结构，趋势中性。"


def _map_regime(total_score: float) -> Dict[str, Any]:
    for item in REGIME_POSITION_MAP:
        if total_score >= float(item["min_score"]):
            return item
    return REGIME_POSITION_MAP[-1]


def _evaluate_us(macro: MacroData, sector: SectorData) -> RegimeResult:
    details: List[Dict[str, Any]] = []

    trend_score, reason = _trend_score(macro.spy_close, macro.spy_ma50, macro.spy_ma200, "SPY")
    details.append({"dimension": "trend", "score": trend_score, "weight": 2, "weighted": trend_score * 2, "reason": reason})

    volatility_score = 0
    volatility_reason = "VIX 数据缺失，维持中性。"
    if macro.vix is not None:
        if float(macro.vix) < 18:
            volatility_score = 1
            volatility_reason = f"VIX {float(macro.vix):.2f}，波动可控。"
        elif float(macro.vix) > 25:
            volatility_score = -1
            volatility_reason = f"VIX {float(macro.vix):.2f}，风险偏好受压。"
        else:
            volatility_reason = f"VIX {float(macro.vix):.2f}，处于中性区间。"
    details.append(
        {"dimension": "volatility", "score": volatility_score, "weight": 2, "weighted": volatility_score * 2, "reason": volatility_reason}
    )

    credit_score = 0
    credit_reason = "HYG 数据缺失，维持中性。"
    if macro.hyg_5d_return is not None:
        if float(macro.hyg_5d_return) > 0:
            credit_score = 1
            credit_reason = f"HYG 5日收益 {float(macro.hyg_5d_return):.2f}%，信用环境支持风险资产。"
        elif float(macro.hyg_5d_return) < -1.5:
            credit_score = -1
            credit_reason = f"HYG 5日收益 {float(macro.hyg_5d_return):.2f}%，信用利差走阔。"
        else:
            credit_reason = f"HYG 5日收益 {float(macro.hyg_5d_return):.2f}%，信用信号中性。"
    details.append({"dimension": "credit", "score": credit_score, "weight": 1, "weighted": credit_score, "reason": credit_reason})

    top3 = sorted(sector.us_sectors, key=lambda item: item.rs, reverse=True)[:3]
    clarity_score = 0
    clarity_reason = "板块数据不足，维持中性。"
    if len(top3) >= 3:
        styles = [item.style for item in top3]
        if len(set(styles)) == 1:
            clarity_score = 1
            clarity_reason = f"领涨前三板块风格一致，当前由 {styles[0]} 风格主导。"
        else:
            clarity_score = -1
            clarity_reason = "领涨板块风格混杂，主线不够清晰。"
    details.append(
        {"dimension": "sector_clarity", "score": clarity_score, "weight": 1, "weighted": clarity_score, "reason": clarity_reason}
    )

    total_score = sum(detail["weighted"] for detail in details)
    mapped = _map_regime(total_score)
    return RegimeResult(
        market="US",
        total_score=float(total_score),
        regime=str(mapped["regime"]),
        regime_label=str(mapped["label"]),
        allocation_adjust_pct=int(mapped["adjust_pct"]),
        score_details=details,
    )


def _evaluate_hk(macro: MacroData, liquidity: LiquidityData) -> RegimeResult:
    details: List[Dict[str, Any]] = []

    trend_score, reason = _trend_score(liquidity.hsi_close, liquidity.hsi_ma20, liquidity.hsi_ma60, "恒生指数")
    details.append({"dimension": "trend", "score": trend_score, "weight": 2, "weighted": trend_score * 2, "reason": reason})

    southbound_score = 0
    southbound_reason = "南向资金数据缺失，维持中性。"
    if liquidity.southbound_5d_avg is not None:
        if float(liquidity.southbound_5d_avg) > 200:
            southbound_score = 1
            southbound_reason = f"南向5日均值 {float(liquidity.southbound_5d_avg):.2f} 亿，资金持续流入。"
        elif float(liquidity.southbound_5d_avg) < -100:
            southbound_score = -1
            southbound_reason = f"南向5日均值 {float(liquidity.southbound_5d_avg):.2f} 亿，资金持续流出。"
        else:
            southbound_reason = f"南向5日均值 {float(liquidity.southbound_5d_avg):.2f} 亿，方向不明。"
    details.append(
        {"dimension": "southbound", "score": southbound_score, "weight": 2, "weighted": southbound_score * 2, "reason": southbound_reason}
    )

    usd_score = 0
    usd_reason = "美元指数数据缺失，维持中性。"
    if macro.usd_index is not None:
        if float(macro.usd_index) < 103:
            usd_score = 1
            usd_reason = f"美元指数 {float(macro.usd_index):.2f}，对港股压力较小。"
        elif float(macro.usd_index) > 106:
            usd_score = -1
            usd_reason = f"美元指数 {float(macro.usd_index):.2f}，港股面临外部流动性压力。"
        else:
            usd_reason = f"美元指数 {float(macro.usd_index):.2f}，影响中性。"
    details.append({"dimension": "usd_pressure", "score": usd_score, "weight": 1, "weighted": usd_score, "reason": usd_reason})

    kweb_score = 0
    kweb_reason = "KWEB 动量数据缺失，维持中性。"
    if macro.kweb_5d_return is not None:
        if float(macro.kweb_5d_return) > 2:
            kweb_score = 1
            kweb_reason = f"KWEB 5日收益 {float(macro.kweb_5d_return):.2f}%，中概情绪改善。"
        elif float(macro.kweb_5d_return) < -3:
            kweb_score = -1
            kweb_reason = f"KWEB 5日收益 {float(macro.kweb_5d_return):.2f}%，科技权重承压。"
        else:
            kweb_reason = f"KWEB 5日收益 {float(macro.kweb_5d_return):.2f}%，信号中性。"
    details.append({"dimension": "kweb_momentum", "score": kweb_score, "weight": 1, "weighted": kweb_score, "reason": kweb_reason})

    total_score = sum(detail["weighted"] for detail in details)
    mapped = _map_regime(total_score)
    return RegimeResult(
        market="HK",
        total_score=float(total_score),
        regime=str(mapped["regime"]),
        regime_label=str(mapped["label"]),
        allocation_adjust_pct=int(mapped["adjust_pct"]),
        score_details=details,
    )


def _evaluate_a(macro: MacroData, liquidity: LiquidityData) -> RegimeResult:
    details: List[Dict[str, Any]] = []

    trend_score, reason = _trend_score(liquidity.csi300_close, liquidity.csi300_ma20, liquidity.csi300_ma60, "沪深300")
    details.append({"dimension": "trend", "score": trend_score, "weight": 2, "weighted": trend_score * 2, "reason": reason})

    liquidity_score = 0
    liquidity_reason = "成交额数据缺失，维持中性。"
    if liquidity.a_turnover_billion is not None:
        if float(liquidity.a_turnover_billion) > 12000:
            liquidity_score = 1
            liquidity_reason = f"A 股成交额 {float(liquidity.a_turnover_billion):.2f} 亿，交投活跃。"
        elif float(liquidity.a_turnover_billion) < 8000:
            liquidity_score = -1
            liquidity_reason = f"A 股成交额 {float(liquidity.a_turnover_billion):.2f} 亿，流动性偏弱。"
        else:
            liquidity_reason = f"A 股成交额 {float(liquidity.a_turnover_billion):.2f} 亿，流动性中性。"
    details.append(
        {"dimension": "liquidity", "score": liquidity_score, "weight": 2, "weighted": liquidity_score * 2, "reason": liquidity_reason}
    )

    northbound_score = 0
    northbound_reason = "北向资金数据缺失，维持中性。"
    if liquidity.northbound_5d_cumulative is not None:
        if float(liquidity.northbound_5d_cumulative) > 500:
            northbound_score = 1
            northbound_reason = f"北向5日累计 {float(liquidity.northbound_5d_cumulative):.2f} 亿，外资回流。"
        elif float(liquidity.northbound_5d_cumulative) < -800:
            northbound_score = -1
            northbound_reason = f"北向5日累计 {float(liquidity.northbound_5d_cumulative):.2f} 亿，外资撤离明显。"
        else:
            northbound_reason = f"北向5日累计 {float(liquidity.northbound_5d_cumulative):.2f} 亿，信号中性。"
    details.append(
        {"dimension": "northbound", "score": northbound_score, "weight": 1, "weighted": northbound_score, "reason": northbound_reason}
    )

    leverage_score = 0
    leverage_reason = "融资趋势数据缺失，维持中性。"
    trend = str(liquidity.margin_balance_3d_trend or "").lower()
    if trend == "up":
        leverage_score = 1
        leverage_reason = "融资余额近 3 日上升，风险偏好改善。"
    elif trend == "down":
        leverage_score = -1
        leverage_reason = "融资余额近 3 日下降，杠杆资金趋于谨慎。"
    details.append({"dimension": "leverage", "score": leverage_score, "weight": 1, "weighted": leverage_score, "reason": leverage_reason})

    total_score = sum(detail["weighted"] for detail in details)
    mapped = _map_regime(total_score)
    return RegimeResult(
        market="A",
        total_score=float(total_score),
        regime=str(mapped["regime"]),
        regime_label=str(mapped["label"]),
        allocation_adjust_pct=int(mapped["adjust_pct"]),
        score_details=details,
    )


def evaluate_market_regimes(macro: MacroData, liquidity: LiquidityData, sector: SectorData) -> List[RegimeResult]:
    """Evaluate US, HK, and A-share market regimes."""

    return [_evaluate_us(macro, sector), _evaluate_hk(macro, liquidity), _evaluate_a(macro, liquidity)]

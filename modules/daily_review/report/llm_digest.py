"""Optional LLM summary for daily review report."""

from __future__ import annotations

import logging
from typing import List

from modules.daily_review.analysis.anomaly import AnomalyAlert
from modules.daily_review.analysis.market_regime import RegimeResult
from modules.daily_review.config import DailyReviewConfig, LLM_CONFIG
from modules.daily_review.data.liquidity import LiquidityData
from modules.daily_review.data.macro import MacroData
from modules.daily_review.data.sector import SectorData
from modules.daily_review.data.stock import StockEntry

logger = logging.getLogger(__name__)


def _serialize_prompt(
    macro: MacroData,
    liquidity: LiquidityData,
    sectors: SectorData,
    stocks: List[StockEntry],
    anomalies: List[AnomalyAlert],
    regimes: List[RegimeResult],
) -> str:
    macro_lines = []
    for key in ["us_10y", "usd_index", "vix", "usd_cnh"]:
        point = macro.get(key)
        if point is None:
            continue
        macro_lines.append(
            f"- {key}: value={point.value}, daily_abs={point.daily_change_abs}, daily_pct={point.daily_change_pct}, "
            f"change_5d={point.change_5d_abs}"
        )

    regime_lines = [f"- {r.market}: {r.regime}, score={r.total_score}, suggestion={r.position_suggestion}" for r in regimes]
    anomaly_lines = [f"- {a.level} {a.name}: {a.message}" for a in anomalies] or ["- 无触发异常"]

    sector_us = [f"{x.name}(RS={x.rs}, style={x.style})" for x in sectors.us[:5]]
    sector_a = [f"{x.name}(RS={x.rs}, style={x.style})" for x in sectors.a[:5]]
    sector_hk = [f"{x.name}(RS={x.rs}, style={x.style})" for x in sectors.hk[:5]]
    stock_lines = [
        f"- {s.name}({s.market}): chg={s.daily_change_pct}, vs_sector={s.vs_sector}, volume_ratio={s.volume_ratio}, signal={s.signal}"
        for s in stocks
    ]

    return (
        "请基于以下结构化数据给出 3-5 句复盘摘要。\n\n"
        "【市场状态】\n"
        + "\n".join(regime_lines)
        + "\n\n【宏观锚】\n"
        + "\n".join(macro_lines)
        + "\n\n【流动性】\n"
        + f"- A_turnover={liquidity.a_turnover_billion}, northbound={liquidity.northbound_net_billion}, "
        + f"southbound={liquidity.southbound_net_billion}, spy_vol_ratio={liquidity.spy_volume_ratio}, "
        + f"hyg_5d={liquidity.hyg_5d_return}, kweb_5d={liquidity.kweb_5d_return}\n\n"
        + "【板块】\n"
        + f"- US top5: {sector_us}\n- A top5: {sector_a}\n- HK top5: {sector_hk}\n\n"
        + "【持仓】\n"
        + "\n".join(stock_lines if stock_lines else ["- 无持仓数据"])
        + "\n\n【异常】\n"
        + "\n".join(anomaly_lines)
    )


def _generate_rule_based_summary(
    *,
    stocks: List[StockEntry],
    anomalies: List[AnomalyAlert],
    regimes: List[RegimeResult],
) -> str:
    regime_map = {r.market: r for r in regimes}
    parts: List[str] = []

    us = regime_map.get("US")
    hk = regime_map.get("HK")
    a = regime_map.get("A")
    if us and hk and a:
        parts.append(
            f"当前三地仓位建议：美股{us.regime}（{us.position_suggestion}）、"
            f"港股{hk.regime}（{hk.position_suggestion}）、A股{a.regime}（{a.position_suggestion}）。"
        )

    red = [x for x in anomalies if x.level == "RED"]
    yellow = [x for x in anomalies if x.level == "YELLOW"]
    if red:
        parts.append(f"触发 {len(red)} 条紧急告警，优先处理：{red[0].name}。")
    elif yellow:
        parts.append(f"触发 {len(yellow)} 条关注信号，需控制节奏并跟踪资金流。")
    else:
        parts.append("暂无异常告警，市场处于常规波动区间。")

    if stocks:
        ranked = sorted(
            [s for s in stocks if s.daily_change_pct is not None],
            key=lambda s: s.daily_change_pct if s.daily_change_pct is not None else -9999,
            reverse=True,
        )
        if ranked:
            top = ranked[0]
            bottom = ranked[-1]
            parts.append(
                f"持仓表现分化，强势标的为 {top.name}（{top.daily_change_pct:+.2f}%），"
                f"相对偏弱的是 {bottom.name}（{bottom.daily_change_pct:+.2f}%）。"
            )
    else:
        parts.append("当前未获取到持仓行情数据，建议先执行一次关注列表刷新后再复盘。")

    parts.append("若外部行情源波动导致部分字段缺失，可先依据仓位建议执行风险控制，再等待下一次数据刷新确认。")
    return "\n".join(parts)


def generate_llm_summary(
    *,
    macro: MacroData,
    liquidity: LiquidityData,
    sectors: SectorData,
    stocks: List[StockEntry],
    anomalies: List[AnomalyAlert],
    regimes: List[RegimeResult],
    config: DailyReviewConfig,
) -> str:
    """Generate optional LLM summary; fall back silently on failure."""

    if config.llm_provider == "none":
        return _generate_rule_based_summary(stocks=stocks, anomalies=anomalies, regimes=regimes)
    if not config.llm_api_key:
        return _generate_rule_based_summary(stocks=stocks, anomalies=anomalies, regimes=regimes)

    prompt = _serialize_prompt(
        macro=macro,
        liquidity=liquidity,
        sectors=sectors,
        stocks=stocks,
        anomalies=anomalies,
        regimes=regimes,
    )
    try:
        from openai import OpenAI

        client = OpenAI(api_key=config.llm_api_key)
        resp = client.chat.completions.create(
            model=config.llm_model or LLM_CONFIG["model"],
            temperature=LLM_CONFIG["temperature"],
            max_tokens=LLM_CONFIG["max_tokens"],
            messages=[
                {"role": "system", "content": LLM_CONFIG["system_prompt"]},
                {"role": "user", "content": prompt},
            ],
        )
        text = (resp.choices[0].message.content or "").strip()
        return text or _generate_rule_based_summary(stocks=stocks, anomalies=anomalies, regimes=regimes)
    except Exception as exc:
        logger.warning("generate_llm_summary failed: %s", exc)
        return _generate_rule_based_summary(stocks=stocks, anomalies=anomalies, regimes=regimes)

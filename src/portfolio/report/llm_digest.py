# -*- coding: utf-8 -*-
"""Portfolio LLM digest generation."""

import logging
from typing import List, Optional

from src.portfolio.config import PORTFOLIO_LLM_SYSTEM_PROMPT
from src.portfolio.models import AnomalyAlert, HealthReport, Portfolio, RebalancePlan, RegimeResult, SectorAnalysis

logger = logging.getLogger(__name__)
FALLBACK_DIGEST = "(AI 摘要不可用)"


def generate_portfolio_llm_digest(
    portfolio: Portfolio,
    health: HealthReport,
    regimes: List[RegimeResult],
    sector_analysis: SectorAnalysis,
    plan: RebalancePlan,
    anomalies: List[AnomalyAlert],
    analyzer: Optional[object] = None,
) -> str:
    """Generate a concise AI digest with safe fallback."""

    del sector_analysis
    prompt = "\n".join(
        [
            PORTFOLIO_LLM_SYSTEM_PROMPT,
            "Return 3-5 concise bullet points in Chinese. Focus on portfolio contradiction, risk, and next action.",
            f"Portfolio total CNY: {portfolio.total_value_cny:.2f}",
            f"Health score: {health.score} ({health.grade})",
            f"Regimes: {', '.join(f'{item.market}:{item.regime}' for item in regimes)}",
            f"Anomalies: {', '.join(alert.name for alert in anomalies) or 'none'}",
            f"Actions: {', '.join(f'{action.direction} {action.ticker} {action.trade_amount_cny}' for action in plan.actions[:5]) or 'none'}",
        ]
    )
    if analyzer is None:
        return FALLBACK_DIGEST

    try:
        if hasattr(analyzer, "generate_text"):
            response = analyzer.generate_text(prompt, max_tokens=1000, temperature=0.3)
        elif hasattr(analyzer, "_call_api_with_retry"):
            response = analyzer._call_api_with_retry(  # type: ignore[attr-defined]
                prompt,
                {
                    "temperature": 0.3,
                    "max_output_tokens": 1000,
                },
            )
        else:
            return FALLBACK_DIGEST
    except Exception as exc:
        logger.warning("Portfolio LLM digest generation failed: %s", exc)
        return FALLBACK_DIGEST

    text = str(response or "").strip()
    return text or FALLBACK_DIGEST

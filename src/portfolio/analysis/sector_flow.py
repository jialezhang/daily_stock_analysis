# -*- coding: utf-8 -*-
"""Sector flow analysis."""

from typing import Dict, List

from src.portfolio.config import SW_SECTOR_STYLES
from src.portfolio.models import SectorAnalysis, SectorData


def analyze_sector_flow(sector_data: SectorData) -> SectorAnalysis:
    """Analyze style leadership across US, HK, and A-share sectors."""

    result = SectorAnalysis()
    us_ranked = sorted(sector_data.us_sectors, key=lambda item: item.rs, reverse=True)
    result.us_leaders = [
        {"name": item.name, "ticker": item.ticker, "style": item.style, "rs": item.rs}
        for item in us_ranked[:3]
    ]
    result.us_laggards = [
        {"name": item.name, "ticker": item.ticker, "style": item.style, "rs": item.rs}
        for item in sorted(sector_data.us_sectors, key=lambda item: item.rs)[:3]
    ]
    top_us_styles = [item.style for item in us_ranked[:3]]
    for style in ("offensive", "defensive", "cyclical"):
        if top_us_styles.count(style) >= 2:
            result.us_style = style
            result.us_style_reasoning = f"美股领涨前三中至少两项属于 {style} 风格。"
            break
    if not result.us_style_reasoning:
        result.us_style_reasoning = "美股领涨板块风格分散，主线不够集中。"

    a_ranked = sorted(
        [item for item in sector_data.a_sectors if isinstance(item, dict)],
        key=lambda item: float(item.get("rs") or item.get("daily_return_pct") or 0.0),
        reverse=True,
    )
    result.a_leaders = a_ranked[:5]
    result.a_laggards = list(reversed(a_ranked[-5:])) if a_ranked else []
    theme_counter: Dict[str, int] = {}
    for entry in a_ranked[:5]:
        name = str(entry.get("name") or "")
        for theme, sectors in SW_SECTOR_STYLES.items():
            if name in sectors:
                theme_counter[theme] = theme_counter.get(theme, 0) + 1
    if theme_counter:
        theme, count = max(theme_counter.items(), key=lambda item: item[1])
        if count >= 3:
            result.a_theme = theme
            result.a_theme_reasoning = f"A 股前五行业中，{theme} 相关行业占据 {count} 个席位。"
        else:
            result.a_theme_reasoning = "A 股前五行业分布较散，未形成明确单一主题。"
    else:
        result.a_theme_reasoning = "缺少足够的 A 股行业数据。"

    hk_benchmark = float(sector_data.hk_benchmark_return or 0.0)
    hk_tech = float(sector_data.hk_tech_return or 0.0)
    result.hk_tech_vs_hsi = round(hk_tech - hk_benchmark, 2)
    if result.hk_tech_vs_hsi > 1.0:
        result.hk_style = "tech_leading"
    elif result.hk_tech_vs_hsi < -1.0:
        result.hk_style = "tech_lagging"
    else:
        result.hk_style = "sync"
    return result

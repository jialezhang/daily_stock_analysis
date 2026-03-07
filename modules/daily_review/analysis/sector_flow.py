"""Sector preference analysis."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import List

from modules.daily_review.data.sector import SectorData, SectorEntry


@dataclass
class SectorAnalysis:
    """Cross-market sector preference summary."""

    us_leaders: List[SectorEntry] = field(default_factory=list)
    us_laggards: List[SectorEntry] = field(default_factory=list)
    us_market_style: str = "风格混合"
    a_leaders: List[SectorEntry] = field(default_factory=list)
    a_laggards: List[SectorEntry] = field(default_factory=list)
    a_main_theme: str = "无明确主线"
    hk_leader: str = "暂无明显领先方向"


def _sort_by_rs(rows: List[SectorEntry]) -> List[SectorEntry]:
    return sorted(rows, key=lambda x: x.rs if x.rs is not None else -9999, reverse=True)


def _us_style(leaders: List[SectorEntry]) -> str:
    if not leaders:
        return "风格混合"
    styles = [s.style for s in leaders if s.style]
    if len(styles) < 3:
        return "风格混合"
    if all(style == "offensive" for style in styles):
        return "进攻型主导"
    if all(style == "defensive" for style in styles):
        return "防守型主导"
    return "风格混合"


def _a_theme(leaders: List[SectorEntry]) -> str:
    if not leaders:
        return "无明确主线"
    style_counter = Counter([s.style for s in leaders if s.style])
    if not style_counter:
        return "无明确主线"
    theme, count = style_counter.most_common(1)[0]
    if count >= 3:
        return theme
    return "无明确主线"


def _hk_leader(rows: List[SectorEntry]) -> str:
    if not rows:
        return "暂无明显领先方向"
    hsi = next((x for x in rows if x.ticker == "^HSI"), None)
    hstech = next((x for x in rows if x.ticker == "^HSTECH"), None)
    if hsi is None or hstech is None:
        return "暂无明显领先方向"
    hsi_rs = hsi.rs if hsi.rs is not None else 0.0
    hstech_rs = hstech.rs if hstech.rs is not None else 0.0
    if hstech_rs > hsi_rs:
        return "恒生科技领跑"
    if hstech_rs < hsi_rs:
        return "恒生指数领跑"
    return "恒生科技与恒生指数同步"


def analyze_sector_preference(sectors: SectorData) -> SectorAnalysis:
    """Analyze cross-market sector flow preferences and themes."""

    us_sorted = _sort_by_rs(sectors.us)
    a_sorted = _sort_by_rs(sectors.a)
    hk_sorted = _sort_by_rs(sectors.hk)

    us_leaders = us_sorted[:3]
    us_laggards = list(reversed(us_sorted[-3:])) if len(us_sorted) >= 3 else list(reversed(us_sorted))
    a_leaders = a_sorted[:5]
    a_laggards = list(reversed(a_sorted[-5:])) if len(a_sorted) >= 5 else list(reversed(a_sorted))

    return SectorAnalysis(
        us_leaders=us_leaders,
        us_laggards=us_laggards,
        us_market_style=_us_style(us_leaders),
        a_leaders=a_leaders,
        a_laggards=a_laggards,
        a_main_theme=_a_theme(a_leaders),
        hk_leader=_hk_leader(hk_sorted),
    )

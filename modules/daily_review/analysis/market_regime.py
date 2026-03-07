"""Market regime scoring for US/HK/A markets."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from modules.daily_review.data.liquidity import LiquidityData
from modules.daily_review.data.macro import MacroData, MacroPoint
from modules.daily_review.data.sector import SectorData, SectorEntry


@dataclass
class RegimeResult:
    """Scoring result for one market."""

    market: str
    total_score: int
    regime: str
    position_suggestion: str
    score_details: Dict[str, int] = field(default_factory=dict)
    reasoning: str = ""


def _norm_return(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    if abs(value) > 1:
        return value / 100.0
    return value


def _norm_treasury_change(macro_point: Optional[MacroPoint]) -> Optional[float]:
    if macro_point is None or macro_point.daily_change_abs is None:
        return None
    change = macro_point.daily_change_abs
    if macro_point.value is not None and abs(macro_point.value) > 20:
        return change / 10.0
    return change


def _to_regime(total_score: int) -> tuple[str, str]:
    if total_score >= 2:
        return "进攻", "建议仓位 70-100%"
    if total_score <= -2:
        return "防守", "建议仓位 0-40%"
    return "平衡", "建议仓位 40-70%"


def _score_us(macro: MacroData, liquidity: LiquidityData, sectors: SectorData) -> tuple[Dict[str, int], List[str]]:
    details: Dict[str, int] = {}
    reasons: List[str] = []

    hyg_5d = _norm_return(liquidity.hyg_5d_return)
    spy_vol_ratio = liquidity.spy_volume_ratio
    score = 0
    if hyg_5d is not None and spy_vol_ratio is not None:
        if hyg_5d > 0 and spy_vol_ratio > 1.0:
            score = 1
        elif hyg_5d < -0.01:
            score = -1
    details["liquidity"] = score
    reasons.append(
        f"流动性({score:+d}): HYG5日={hyg_5d if hyg_5d is not None else 'NA'}, "
        f"SPY量比={spy_vol_ratio if spy_vol_ratio is not None else 'NA'}"
    )

    us_bench = sectors.benchmarks.get("US", {})
    spy_close = us_bench.get("close")
    spy_ma50 = us_bench.get("ma50")
    spy_ma200 = us_bench.get("ma200")
    score = 0
    if all(v is not None for v in [spy_close, spy_ma50, spy_ma200]):
        if spy_close > spy_ma50 > spy_ma200:
            score = 1
        elif spy_close < spy_ma50 < spy_ma200:
            score = -1
    details["trend"] = score
    reasons.append(f"趋势({score:+d}): SPY={spy_close}, MA50={spy_ma50}, MA200={spy_ma200}")

    treasury_change = _norm_treasury_change(macro.get("us_10y"))
    vix = macro.get("vix").value if macro.get("vix") is not None else None
    score = 0
    if vix is not None and treasury_change is not None:
        if vix < 18 and abs(treasury_change) < 0.05:
            score = 1
        elif vix > 25 or abs(treasury_change) > 0.10:
            score = -1
    details["risk_appetite"] = score
    reasons.append(f"风险偏好({score:+d}): VIX={vix}, 美债日变动={treasury_change}")

    top3 = sectors.us[:3]
    top3_styles = [s.style for s in top3 if s.style]
    top3_rs = [s.rs for s in top3 if s.rs is not None]
    top3_same_style = bool(top3_styles) and len(set(top3_styles)) == 1
    top3_mixed_style = "offensive" in top3_styles and "defensive" in top3_styles
    top3_min_rs = min(top3_rs) if top3_rs else None
    score = 0
    if top3_same_style and top3_min_rs is not None and top3_min_rs > 0.5:
        score = 1
    elif top3_mixed_style:
        score = -1
    details["sector_clarity"] = score
    reasons.append(f"板块主线({score:+d}): top3风格={top3_styles}, top3最小RS={top3_min_rs}")

    return details, reasons


def _score_a(liquidity: LiquidityData, sectors: SectorData) -> tuple[Dict[str, int], List[str]]:
    details: Dict[str, int] = {}
    reasons: List[str] = []

    a_turnover = liquidity.a_turnover_billion
    northbound = liquidity.northbound_net_billion
    score = 0
    if a_turnover is not None and northbound is not None:
        if a_turnover > 12000 and northbound > 0:
            score = 1
        elif a_turnover < 8000 or northbound < -50:
            score = -1
    details["liquidity"] = score
    reasons.append(f"流动性({score:+d}): 成交额={a_turnover}, 北向={northbound}")

    trend_3d = liquidity.margin_balance_trend_3d
    score = 0
    if trend_3d == "up":
        score = 1
    elif trend_3d == "down":
        score = -1
    details["leverage"] = score
    reasons.append(f"杠杆资金({score:+d}): 融资3日趋势={trend_3d}")

    a_bench = sectors.benchmarks.get("A", {})
    close = a_bench.get("close")
    ma20 = a_bench.get("ma20")
    ma60 = a_bench.get("ma60")
    score = 0
    if all(v is not None for v in [close, ma20, ma60]):
        if close > ma20 > ma60:
            score = 1
        elif close < ma20 < ma60:
            score = -1
    details["trend"] = score
    reasons.append(f"趋势({score:+d}): 沪深300={close}, MA20={ma20}, MA60={ma60}")

    top5 = sectors.a[:5]
    top5_styles = [s.style for s in top5 if s.style]
    style_counter = Counter(top5_styles)
    top5_dominant_style_count = max(style_counter.values()) if style_counter else 0
    top5_style_count = len(style_counter)
    score = 0
    if top5_dominant_style_count >= 3:
        score = 1
    elif top5_style_count >= 4:
        score = -1
    details["sector_clarity"] = score
    reasons.append(f"板块主线({score:+d}): top5风格分布={dict(style_counter)}")

    return details, reasons


def _score_hk(macro: MacroData, liquidity: LiquidityData, sectors: SectorData) -> tuple[Dict[str, int], List[str]]:
    details: Dict[str, int] = {}
    reasons: List[str] = []

    southbound = liquidity.southbound_net_billion
    score = 0
    if southbound is not None:
        if southbound > 20:
            score = 1
        elif southbound < -20:
            score = -1
    details["liquidity"] = score
    reasons.append(f"流动性({score:+d}): 南向={southbound}")

    hk_bench = sectors.benchmarks.get("HK", {})
    hsi_close = hk_bench.get("close")
    hsi_ma20 = hk_bench.get("ma20")
    hsi_ma60 = hk_bench.get("ma60")
    score = 0
    if all(v is not None for v in [hsi_close, hsi_ma20]):
        if hsi_close > hsi_ma20:
            score = 1
    if score == 0 and all(v is not None for v in [hsi_close, hsi_ma60]):
        if hsi_close < hsi_ma60:
            score = -1
    details["trend"] = score
    reasons.append(f"趋势({score:+d}): HSI={hsi_close}, MA20={hsi_ma20}, MA60={hsi_ma60}")

    kweb_5d = _norm_return(liquidity.kweb_5d_return)
    score = 0
    if kweb_5d is not None:
        if kweb_5d > 0.02:
            score = 1
        elif kweb_5d < -0.03:
            score = -1
    details["risk_appetite"] = score
    reasons.append(f"风险偏好({score:+d}): KWEB5日={kweb_5d}")

    usd_index = macro.get("usd_index").value if macro.get("usd_index") is not None else None
    usd_cnh_change = macro.get("usd_cnh").daily_change_abs if macro.get("usd_cnh") is not None else None
    score = 0
    if usd_index is not None and usd_cnh_change is not None:
        if usd_index < 103 and usd_cnh_change < 0:
            score = 1
        elif usd_index > 106 or usd_cnh_change > 0.03:
            score = -1
    details["macro_pressure"] = score
    reasons.append(f"宏观压力({score:+d}): 美元指数={usd_index}, USDCNH日变动={usd_cnh_change}")

    return details, reasons


def evaluate_regime(
    market: str,
    macro: MacroData,
    liquidity: LiquidityData,
    sectors: SectorData,
) -> RegimeResult:
    """Evaluate regime score and position suggestion for one market."""

    market = market.upper()
    if market == "US":
        details, reasons = _score_us(macro, liquidity, sectors)
    elif market == "A":
        details, reasons = _score_a(liquidity, sectors)
    elif market == "HK":
        details, reasons = _score_hk(macro, liquidity, sectors)
    else:
        details = {}
        reasons = ["未知市场，默认平衡仓位。"]

    total_score = sum(details.values())
    regime, position = _to_regime(total_score)
    return RegimeResult(
        market=market,
        total_score=total_score,
        regime=regime,
        position_suggestion=position,
        score_details=details,
        reasoning="；".join(reasons),
    )

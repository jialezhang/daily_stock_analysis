"""Markdown report renderer for daily review."""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List

from modules.daily_review.analysis.anomaly import AnomalyAlert
from modules.daily_review.analysis.market_regime import RegimeResult
from modules.daily_review.analysis.sector_flow import SectorAnalysis
from modules.daily_review.config import SH_TZ
from modules.daily_review.data.liquidity import LiquidityData
from modules.daily_review.data.macro import MacroData
from modules.daily_review.data.sector import SectorData
from modules.daily_review.data.stock import StockEntry


def _fmt_num(value, digits: int = 2) -> str:
    if value is None:
        return "N/A"
    return f"{float(value):.{digits}f}"


def _fmt_pct_auto(value) -> str:
    if value is None:
        return "N/A"
    v = float(value)
    if abs(v) <= 1:
        v = v * 100.0
    return f"{v:+.2f}%"


def _fmt_pct_exact(value) -> str:
    if value is None:
        return "N/A"
    return f"{float(value):+.2f}%"


def _fmt_ratio(value) -> str:
    if value is None:
        return "N/A"
    return f"{float(value):.2f}"


def _norm_tnx_value(raw_value, raw_change):
    if raw_value is None:
        return None, None
    value = float(raw_value)
    change = float(raw_change) if raw_change is not None else None
    if abs(value) > 20:
        value = value / 10.0
        if change is not None:
            change = change / 10.0
    return value, change


def _macro_signal(macro: MacroData) -> Dict[str, str]:
    us_10y = macro.get("us_10y")
    vix = macro.get("vix")
    usd_index = macro.get("usd_index")
    usd_cnh = macro.get("usd_cnh")

    tnx_value, tnx_change = _norm_tnx_value(
        us_10y.value if us_10y else None,
        us_10y.daily_change_abs if us_10y else None,
    )
    signals = {
        "us_10y": "➖ 中性",
        "usd_index": "➖ 中性",
        "vix": "➖ 中性",
        "usd_cnh": "➖ 中性",
    }
    if tnx_change is not None:
        if abs(tnx_change) > 0.10:
            signals["us_10y"] = "⚠️ 利率扰动"
        elif abs(tnx_change) < 0.05:
            signals["us_10y"] = "✅ 利率平稳"

    if usd_index and usd_index.value is not None:
        if usd_index.value > 106:
            signals["usd_index"] = "🔻 美元偏强"
        elif usd_index.value < 103:
            signals["usd_index"] = "📈 美元回落"

    if vix and vix.value is not None:
        if vix.value > 25:
            signals["vix"] = "⚠️ 风险偏好下降"
        elif vix.value < 18:
            signals["vix"] = "📈 风险偏好改善"

    if usd_cnh and usd_cnh.daily_change_abs is not None:
        if usd_cnh.daily_change_abs > 0.03:
            signals["usd_cnh"] = "🔻 人民币承压"
        elif usd_cnh.daily_change_abs < 0:
            signals["usd_cnh"] = "📈 人民币走强"

    return signals


def _anomaly_section(anomalies: List[AnomalyAlert]) -> str:
    if not anomalies:
        return "✅ 市场处于常规波动区间"

    red = [x for x in anomalies if x.level == "RED"]
    yellow = [x for x in anomalies if x.level == "YELLOW"]

    lines = []
    if red:
        lines.append("🔴 **紧急告警**")
        for a in red:
            lines.append(f"- {a.name}: {a.message}（建议：{a.action}）")
    elif yellow:
        lines.append("🟡 **关注信号**")
        for a in yellow:
            lines.append(f"- {a.name}: {a.message}（建议：{a.action}）")

    if red and yellow:
        lines.append("")
        lines.append("🟡 **关注信号**")
        for a in yellow:
            lines.append(f"- {a.name}: {a.message}（建议：{a.action}）")

    return "\n".join(lines)


def _regime_map(regimes: List[RegimeResult]) -> Dict[str, RegimeResult]:
    return {r.market: r for r in regimes}


def _stock_rows(stocks: List[StockEntry]) -> str:
    lines = []
    for s in stocks:
        vs_sector = s.vs_sector
        if vs_sector is None and s.daily_change_pct is not None and s.sector_daily_change_pct is not None:
            vs_sector = s.daily_change_pct - s.sector_daily_change_pct
        lines.append(
            "| "
            f"{s.name} | {s.market} | {_fmt_pct_exact(s.daily_change_pct)} | "
            f"{_fmt_pct_exact(vs_sector)} | {_fmt_num(s.volume, 0)} | {s.signal} |"
        )
    return "\n".join(lines) if lines else "| - | - | - | - | - | - |"


def _sector_rows_us(analysis: SectorAnalysis) -> str:
    if not analysis.us_leaders:
        return "| 1 | - | - | - | - |"
    lines = []
    for idx, row in enumerate(analysis.us_leaders, start=1):
        lines.append(
            "| "
            f"{idx} | {row.name} | {_fmt_pct_exact(row.daily_change_pct)} | {_fmt_num(row.rs)} | {row.style} |"
        )
    return "\n".join(lines)


def _sector_rows_a(analysis: SectorAnalysis) -> str:
    if not analysis.a_leaders:
        return "| 1 | - | - | - |"
    lines = []
    for idx, row in enumerate(analysis.a_leaders, start=1):
        lines.append(
            "| "
            f"{idx} | {row.name} | {_fmt_pct_exact(row.daily_change_pct)} | {_fmt_num(row.rs)} |"
        )
    return "\n".join(lines)


def render_report(
    *,
    macro: MacroData,
    liquidity: LiquidityData,
    sectors: SectorData,
    sector_analysis: SectorAnalysis,
    stocks: List[StockEntry],
    regimes: List[RegimeResult],
    anomalies: List[AnomalyAlert],
    summary: str,
) -> str:
    """Render final markdown review report."""

    now = datetime.now(SH_TZ)
    review_date = now.strftime("%Y-%m-%d")
    timestamp = now.strftime("%Y-%m-%d %H:%M:%S %Z")
    macro_signals = _macro_signal(macro)
    regime = _regime_map(regimes)

    us = regime.get("US", RegimeResult("US", 0, "平衡", "建议仓位 40-70%", {}, "数据不足"))
    hk = regime.get("HK", RegimeResult("HK", 0, "平衡", "建议仓位 40-70%", {}, "数据不足"))
    a = regime.get("A", RegimeResult("A", 0, "平衡", "建议仓位 40-70%", {}, "数据不足"))

    us_10y = macro.get("us_10y")
    usd_idx = macro.get("usd_index")
    vix = macro.get("vix")
    usd_cnh = macro.get("usd_cnh")
    tnx_value, tnx_daily = _norm_tnx_value(
        us_10y.value if us_10y else None,
        us_10y.daily_change_abs if us_10y else None,
    )
    _, tnx_5d = _norm_tnx_value(
        us_10y.value if us_10y else None,
        us_10y.change_5d_abs if us_10y else None,
    )
    usd_cnh_pips = usd_cnh.daily_change_abs * 10000 if usd_cnh and usd_cnh.daily_change_abs is not None else None

    return f"""# 📅 {review_date} 三地市场复盘

{_anomaly_section(anomalies)}

---

## 🎯 仓位建议

| 市场 | 状态 | 建议仓位 | 核心逻辑 |
|------|------|----------|----------|
| 🇺🇸 美股 | {us.regime} | {us.position_suggestion} | {us.reasoning} |
| 🇭🇰 港股 | {hk.regime} | {hk.position_suggestion} | {hk.reasoning} |
| 🇨🇳 A 股 | {a.regime} | {a.position_suggestion} | {a.reasoning} |

---

## 一、全球定价锚

| 指标 | 当前值 | 日变动 | 5日变动 | 信号 |
|------|--------|--------|---------|------|
| 10Y 美债 | {_fmt_num(tnx_value)}% | {_fmt_num((tnx_daily * 100) if tnx_daily is not None else None)}bps | {_fmt_num((tnx_5d * 100) if tnx_5d is not None else None)}bps | {macro_signals['us_10y']} |
| 美元指数 | {_fmt_num(usd_idx.value if usd_idx else None)} | {_fmt_pct_exact(usd_idx.daily_change_pct if usd_idx else None)} | {_fmt_pct_exact(usd_idx.change_5d_pct if usd_idx else None)} | {macro_signals['usd_index']} |
| VIX | {_fmt_num(vix.value if vix else None)} | {_fmt_num(vix.daily_change_abs if vix else None)} | — | {macro_signals['vix']} |
| 离岸人民币 | {_fmt_num(usd_cnh.value if usd_cnh else None, 4)} | {_fmt_num(usd_cnh_pips, 0)}pips | — | {macro_signals['usd_cnh']} |

---

## 二、流动性仪表盘

### A 股
| 指标 | 数值 | 判定 |
|------|------|------|
| 成交额 | {_fmt_num(liquidity.a_turnover_billion, 0)} 亿 | {"活跃" if liquidity.a_turnover_billion and liquidity.a_turnover_billion > 12000 else "存量博弈" if liquidity.a_turnover_billion and liquidity.a_turnover_billion >= 8000 else "缩量"} |
| 融资余额变动(5日) | {_fmt_pct_auto(liquidity.margin_balance_5d_change_pct)} | {liquidity.margin_balance_trend_3d or "N/A"} |
| 北向资金 | {_fmt_num(liquidity.northbound_net_billion, 1)} 亿 | {"流入" if liquidity.northbound_net_billion and liquidity.northbound_net_billion > 0 else "流出"} |

### 港股
| 指标 | 数值 | 判定 |
|------|------|------|
| 南向资金 | {_fmt_num(liquidity.southbound_net_billion, 1)} 亿 | {"净流入" if liquidity.southbound_net_billion and liquidity.southbound_net_billion > 0 else "净流出"} |
| KWEB 5日表现 | {_fmt_pct_auto(liquidity.kweb_5d_return)} | {"外资偏好回升" if liquidity.kweb_5d_return and liquidity.kweb_5d_return > 0 else "外资谨慎"} |

### 美股
| 指标 | 数值 | 判定 |
|------|------|------|
| SPY 成交量/20日均量 | {_fmt_ratio(liquidity.spy_volume_ratio)} | {"活跃" if liquidity.spy_volume_ratio and liquidity.spy_volume_ratio > 1 else "一般"} |
| HYG 5日表现 | {_fmt_pct_auto(liquidity.hyg_5d_return)} | {"信用环境改善" if liquidity.hyg_5d_return and liquidity.hyg_5d_return > 0 else "信用环境承压"} |

---

## 三、板块资金流向

### 🇺🇸 美股板块（市场风格：{sector_analysis.us_market_style}）
| 排名 | 板块 | 涨跌幅 | RS | 风格 |
|------|------|--------|----|------|
{_sector_rows_us(sector_analysis)}

### 🇨🇳 A 股板块（当前主线：{sector_analysis.a_main_theme}）
| 排名 | 行业 | 涨跌幅 | RS |
|------|------|--------|----|
{_sector_rows_a(sector_analysis)}

### 🇭🇰 港股方向：{sector_analysis.hk_leader}

---

## 四、持仓监控

| 标的 | 市场 | 涨跌幅 | vs 板块 | 成交量 | 信号 |
|------|------|--------|---------|--------|------|
{_stock_rows(stocks)}

---

## 五、AI 总结

{summary or "（AI 总结暂不可用）"}

---
*自动生成于 {timestamp}*
"""

# -*- coding: utf-8 -*-
"""Daily position review generation and Telegram delivery."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.notification import NotificationService
from src.services.position_management_service import PositionManagementService

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
REPORTS_DIR = PROJECT_ROOT / "reports"
REVIEW_NOTES_FILE = PROJECT_ROOT / "data" / "position_review_notes.json"


def run_position_daily_review(
    notifier: NotificationService,
    analyzer: Optional[Any] = None,
    market_report: str = "",
    send_notification: bool = True,
) -> Optional[str]:
    """
    Build daily position review and optionally send it to Telegram.

    Returns the rendered review markdown, or None when data is unavailable.
    """
    try:
        service = PositionManagementService()
        module_result = service.get_module()
        module = module_result.get("module") if isinstance(module_result, dict) else None
        if not isinstance(module, dict):
            logger.warning("Position daily review skipped: module is empty")
            return None

        review = _build_review_markdown(
            module=module,
            market_report=market_report,
            analyzer=analyzer,
        )

        date_str = datetime.now().strftime("%Y%m%d")
        filename = f"position_review_{date_str}.md"
        notifier.save_report_to_file(review, filename)

        if send_notification:
            success = notifier.send_to_telegram(review)
            if success:
                logger.info("每日仓位复盘已发送至 Telegram")
            else:
                logger.warning("每日仓位复盘发送 Telegram 失败")
        else:
            logger.info("已跳过每日仓位复盘推送 (--no-notify)")
        return review
    except Exception as exc:
        logger.error("生成每日仓位复盘失败: %s", exc, exc_info=True)
        return None


def load_latest_position_review() -> Optional[Dict[str, Any]]:
    """Load latest local position review markdown and extract structured sections."""
    history = list_position_reviews(limit=1)
    if not history:
        return None
    return history[0]


def list_position_reviews(limit: int = 120) -> List[Dict[str, Any]]:
    """Load local daily review history for frontend rendering."""
    if not REPORTS_DIR.exists():
        return []
    limit = max(1, min(3650, int(limit or 120)))
    files = sorted(REPORTS_DIR.glob("position_review_*.md"), key=lambda path: path.stat().st_mtime, reverse=True)[:limit]
    if not files:
        return []
    notes = _read_review_notes()
    reviews: List[Dict[str, Any]] = []
    for path in files:
        payload = _load_review_from_file(path, notes=notes)
        if payload:
            reviews.append(payload)
    return reviews


def upsert_position_review_note(review_date: str, note: str) -> Dict[str, Any]:
    """Persist one manual note for a specific review date."""
    compact_date = _normalize_review_date_compact(review_date)
    if not compact_date:
        raise ValueError("review_date must be YYYYMMDD or YYYY-MM-DD")
    normalized_note = str(note or "").strip()
    notes = _read_review_notes()
    if normalized_note:
        notes[compact_date] = {
            "note": normalized_note,
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        }
    else:
        notes.pop(compact_date, None)
    _write_review_notes(notes)
    return {
        "review_date": _format_review_date(compact_date),
        "note": normalized_note,
    }


def _load_review_from_file(path: Path, notes: Dict[str, Dict[str, str]]) -> Optional[Dict[str, Any]]:
    compact_date = _extract_compact_review_date(path.name)
    if not compact_date:
        return None
    try:
        markdown = path.read_text(encoding="utf-8")
    except Exception:
        return None
    sections = _extract_review_sections(markdown)
    note_entry = notes.get(compact_date, {})
    return {
        "review_date": _format_review_date(compact_date),
        "generated_at": datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds"),
        "file_path": str(path),
        "markdown": markdown,
        "sections": sections,
        "note": str(note_entry.get("note") or ""),
        "note_updated_at": str(note_entry.get("updated_at") or ""),
    }


def _build_review_markdown(module: Dict[str, Any], market_report: str, analyzer: Optional[Any]) -> str:
    sections = _build_review_sections(module=module, market_report=market_report, analyzer=analyzer)
    lines: List[str] = []
    lines.append(f"## {datetime.now().strftime('%Y-%m-%d')} 每日资产管理复盘")
    lines.append("")
    lines.append("### 🌪️ 宏观与跨市场风向")
    lines.append(sections["macro_cross_market"])
    lines.append("")
    lines.append("### 📊 组合偏离度与目标追踪")
    lines.append(sections["target_tracking"])
    lines.append("")
    lines.append("### 💡 行动与网格策略建议")
    lines.append(f"- **风险预警**：{sections['risk_warning']}")
    lines.append(f"- **网格/区间操作参考**：{sections['grid_reference']}")
    return "\n".join(lines)


def _build_review_sections(module: Dict[str, Any], market_report: str, analyzer: Optional[Any]) -> Dict[str, str]:
    target = module.get("target") if isinstance(module.get("target"), dict) else {}
    derived = module.get("derived") if isinstance(module.get("derived"), dict) else {}
    totals = derived.get("totals") if isinstance(derived.get("totals"), dict) else {}
    progress = derived.get("target_progress") if isinstance(derived.get("target_progress"), dict) else {}
    output_currency = str(target.get("output_currency") or derived.get("output_currency") or "USD")
    target_return_pct = _to_float(target.get("target_return_pct"))
    profit_pct = _to_float(totals.get("profit_pct"))
    gap_to_target = _to_float(progress.get("gap_to_target_output"))
    holdings = module.get("holdings") if isinstance(module.get("holdings"), list) else []
    macro_events = module.get("macro_events") if isinstance(module.get("macro_events"), list) else []
    macro_text = "；".join([str(item).strip() for item in macro_events if str(item).strip()][:5])
    market_context = f"{macro_text} {str(market_report or '').strip()}".strip()

    macro_cross_market = _build_macro_cross_market(market_context=market_context, holdings=holdings)
    benchmark_text = _build_target_tracking(
        output_currency=output_currency,
        target_return_pct=target_return_pct,
        profit_pct=profit_pct,
        gap_to_target=gap_to_target,
        holdings=holdings,
    )
    risk_warning = _build_risk_warning(holdings=holdings, market_context=market_context)
    grid_reference = _build_grid_reference(holdings=holdings)

    ai_text = _generate_ai_advice(
        analyzer=analyzer,
        output_currency=output_currency,
        target_return_pct=target_return_pct,
        total_value=_to_float(totals.get("total_value_output")),
        profit_pct=profit_pct,
        gap_to_target=gap_to_target,
        secondary=_normalize_secondary_allocation(module=module, derived=derived),
        market_report=market_context,
    )
    if ai_text:
        benchmark_text = f"{benchmark_text} AI补充：{_compact_text(ai_text, 90)}"

    return {
        "macro_cross_market": str(macro_cross_market or "").strip(),
        "target_tracking": str(benchmark_text or "").strip(),
        "risk_warning": str(risk_warning or "").strip(),
        "grid_reference": str(grid_reference or "").strip(),
    }


def _build_macro_cross_market(market_context: str, holdings: List[Any]) -> str:
    context = str(market_context or "")
    text = "今日跨市场资金风格中性偏谨慎。"
    risk_keywords = ["冲突", "关税", "制裁", "战争", "地缘", "通胀", "加息"]
    easing_keywords = ["降息", "宽松", "刺激", "流动性"]
    if any(keyword in context for keyword in risk_keywords):
        text = "宏观扰动上行，资金偏向防御与现金管理。"
    elif any(keyword in context for keyword in easing_keywords):
        text = "风险偏好修复，资金向成长与高弹性资产回流。"

    has_cn_adr = any(str((row if isinstance(row, dict) else {}).get("symbol") or "").upper() in {"BABA", "PDD", "JD", "BIDU", "NTES", "TME"} for row in holdings)
    has_us_tech = any(str((row if isinstance(row, dict) else {}).get("symbol") or "").upper() in {"NVDA", "MSFT", "AAPL", "AMZN", "META", "TSLA", "GOOGL", "AMD"} for row in holdings)
    has_crypto = any(str((row if isinstance(row, dict) else {}).get("asset_primary") or "") == "加密货币" for row in holdings)
    flows = []
    flows.append(f"中概股{'承压' if any(k in context for k in risk_keywords) else '跟随风险偏好波动'}")
    flows.append(f"美股科技{'分化' if has_us_tech else '影响有限'}")
    if has_crypto:
        flows.append(f"加密资产{'波动放大' if any(k in context for k in risk_keywords) else '活跃度回升'}")
    return f"{text} {market_context or '未录入显著新闻事件。'} 资金流向上，{ '、'.join(flows) }。"


def _build_target_tracking(
    output_currency: str,
    target_return_pct: float,
    profit_pct: float,
    gap_to_target: float,
    holdings: List[Any],
) -> str:
    csi300 = _fetch_benchmark_return_pct("000300.SS")
    nasdaq = _fetch_benchmark_return_pct("^IXIC")
    benchmark_parts: List[str] = []
    if csi300 is not None:
        benchmark_parts.append(f"沪深300约{csi300:.2f}%")
    if nasdaq is not None:
        benchmark_parts.append(f"纳斯达克约{nasdaq:.2f}%")
    bench_text = "、".join(benchmark_parts) if benchmark_parts else "基准数据暂不可用"

    top_gain = None
    top_drag = None
    for row in holdings:
        if not isinstance(row, dict):
            continue
        pnl = _to_float(row.get("daily_pnl_output"))
        symbol = str(row.get("symbol") or row.get("name") or "未命名")
        if top_gain is None or pnl > top_gain[1]:
            top_gain = (symbol, pnl)
        if top_drag is None or pnl < top_drag[1]:
            top_drag = (symbol, pnl)
    alpha_source = f"alpha 主要来自 {top_gain[0]}" if top_gain and top_gain[1] > 0 else "alpha 来源暂不明显"
    drag_source = f"拖累项为 {top_drag[0]}" if top_drag and top_drag[1] < 0 else "拖累项不突出"

    return (
        f"当前组合收益率 {profit_pct:.2f}%，年度目标 {target_return_pct:.2f}%（差额 {gap_to_target:.2f} {output_currency}）。"
        f" 对比{bench_text}，{alpha_source}，{drag_source}。"
    )


def _build_risk_warning(holdings: List[Any], market_context: str) -> str:
    valid_rows = [row for row in holdings if isinstance(row, dict)]
    total_value = sum(_to_float(row.get("market_value_output")) for row in valid_rows)
    if total_value <= 0:
        return "暂无持仓数据，暂不触发集中度风险。"

    max_symbol = "未知"
    max_ratio = 0.0
    class_map: Dict[str, float] = {}
    for row in valid_rows:
        value = _to_float(row.get("market_value_output"))
        symbol = str(row.get("symbol") or row.get("name") or "未知")
        ratio = value / total_value * 100.0 if total_value > 0 else 0.0
        if ratio > max_ratio:
            max_ratio = ratio
            max_symbol = symbol
        primary = str(row.get("asset_primary") or "其他")
        class_map[primary] = class_map.get(primary, 0.0) + value
    top_class = max(class_map.items(), key=lambda item: item[1]) if class_map else ("其他", 0.0)
    class_ratio = top_class[1] / total_value * 100.0 if total_value > 0 else 0.0

    geo_hit = any(keyword in str(market_context or "") for keyword in ["冲突", "关税", "制裁", "战争", "地缘"])
    if max_ratio >= 30:
        return f"{max_symbol} 占组合约 {max_ratio:.2f}% 偏高，建议分批降仓至 20%-25%。"
    if class_ratio >= 55:
        return f"{top_class[0]} 占比约 {class_ratio:.2f}% 偏高，建议做跨资产再平衡。"
    if geo_hit:
        return "地缘事件扰动上行，建议降低高波动敞口并提升现金缓冲。"
    return "当前集中度可控，维持风控阈值与止损纪律即可。"


def _build_grid_reference(holdings: List[Any]) -> str:
    valid_rows = [row for row in holdings if isinstance(row, dict)]
    if not valid_rows:
        return "暂无可评估标的。"
    volatile = max(valid_rows, key=lambda row: abs(_to_float((row or {}).get("change_pct"))))
    symbol = str(volatile.get("symbol") or volatile.get("name") or "未命名")
    latest_price = _to_float(volatile.get("latest_price") or volatile.get("current_price"))
    quote_symbol = str(volatile.get("quote_symbol") or symbol)
    low, high = _estimate_range_low_high(quote_symbol=quote_symbol, latest_price=latest_price)
    if high <= low:
        return f"{symbol} 缺少区间数据，建议按既有止损止盈位执行。"
    ratio = (latest_price - low) / (high - low)
    if ratio >= 0.8:
        signal = "接近区间上沿，宜分批止盈或减仓"
    elif ratio <= 0.2:
        signal = "接近区间下沿，可关注分批吸纳"
    else:
        signal = "位于区间中部，宜等待确认信号"
    return f"{symbol} 今日波动最大，参考区间 {low:.2f}-{high:.2f}，当前价 {latest_price:.2f}，{signal}。"


def _estimate_range_low_high(quote_symbol: str, latest_price: float) -> tuple[float, float]:
    fallback_low = latest_price * 0.95 if latest_price > 0 else 0.0
    fallback_high = latest_price * 1.05 if latest_price > 0 else 0.0
    if not quote_symbol:
        return fallback_low, fallback_high
    try:
        import yfinance as yf

        hist = yf.download(
            tickers=quote_symbol,
            period="2mo",
            progress=False,
            auto_adjust=False,
            threads=False,
        )
        if hist is None or hist.empty:
            return fallback_low, fallback_high
        low_col = hist.get("Low")
        high_col = hist.get("High")
        if low_col is None or high_col is None:
            return fallback_low, fallback_high
        if hasattr(low_col, "columns"):
            low_col = low_col.iloc[:, 0]
        if hasattr(high_col, "columns"):
            high_col = high_col.iloc[:, 0]
        low = float(low_col.dropna().tail(30).min())
        high = float(high_col.dropna().tail(30).max())
        if high > low > 0:
            return low, high
        return fallback_low, fallback_high
    except Exception:
        return fallback_low, fallback_high


def _fetch_benchmark_return_pct(symbol: str) -> Optional[float]:
    try:
        import yfinance as yf

        hist = yf.download(
            tickers=symbol,
            period="1y",
            progress=False,
            auto_adjust=False,
            threads=False,
        )
        if hist is None or hist.empty:
            return None
        close = hist.get("Close")
        if close is None:
            return None
        if hasattr(close, "columns"):
            close = close.iloc[:, 0]
        series = close.dropna()
        if series.empty:
            return None
        latest = float(series.iloc[-1])
        year_prefix = f"{datetime.now().year}-"
        ytd = series[series.index.astype(str).str.startswith(year_prefix)]
        base = float(ytd.iloc[0]) if len(ytd) > 0 else float(series.iloc[max(0, len(series) - 120)])
        if base <= 0:
            return None
        return (latest / base - 1.0) * 100.0
    except Exception:
        return None


def _extract_review_sections(markdown: str) -> Dict[str, str]:
    text = str(markdown or "")
    macro = _extract_between(text, "### 🌪️ 宏观与跨市场风向", "### 📊 组合偏离度与目标追踪")
    target = _extract_between(text, "### 📊 组合偏离度与目标追踪", "### 💡 行动与网格策略建议")
    action = _extract_after(text, "### 💡 行动与网格策略建议")
    risk = ""
    grid = ""
    for line in action.splitlines():
        stripped = line.strip()
        if stripped.startswith("- **风险预警**："):
            risk = stripped.replace("- **风险预警**：", "", 1).strip()
        if stripped.startswith("- **网格/区间操作参考**："):
            grid = stripped.replace("- **网格/区间操作参考**：", "", 1).strip()
    if macro.strip() or target.strip() or risk or grid:
        return {
            "macro_cross_market": macro.strip(),
            "target_tracking": target.strip(),
            "risk_warning": risk,
            "grid_reference": grid,
        }

    # Backward compatibility for legacy markdown before the new fixed 3-part structure.
    legacy_distribution = _extract_between(text, "### 二级分类资产分布", "### 目标与进度")
    legacy_target = _extract_between(text, "### 目标与进度", "### AI 资产配置建议")
    legacy_advice = _extract_after(text, "### AI 资产配置建议")
    bullet_lines = [line.strip()[1:].strip() for line in legacy_advice.splitlines() if line.strip().startswith("-")]
    legacy_risk = bullet_lines[0] if bullet_lines else str(legacy_advice or "").strip()
    legacy_grid = bullet_lines[1] if len(bullet_lines) > 1 else "请参考 AI 资产配置建议原文。"
    legacy_macro = legacy_distribution.strip() or "历史格式复盘（资产分布表）"
    legacy_target_tracking = legacy_target.strip() or "历史格式复盘（目标进度段）"
    return {
        "macro_cross_market": str(legacy_macro or "").strip(),
        "target_tracking": str(legacy_target_tracking or "").strip(),
        "risk_warning": str(legacy_risk or "").strip(),
        "grid_reference": str(legacy_grid or "").strip(),
    }


def _extract_between(text: str, left: str, right: str) -> str:
    if left not in text:
        return ""
    segment = text.split(left, 1)[1]
    if right in segment:
        segment = segment.split(right, 1)[0]
    return segment.strip()


def _extract_after(text: str, left: str) -> str:
    if left not in text:
        return ""
    return text.split(left, 1)[1].strip()


def _compact_text(text: str, limit: int) -> str:
    clean = " ".join(str(text or "").replace("\n", " ").split())
    if len(clean) <= limit:
        return clean
    return f"{clean[: max(0, limit - 1)]}…"


def _normalize_secondary_allocation(module: Dict[str, Any], derived: Dict[str, Any]) -> List[Dict[str, float]]:
    raw = derived.get("secondary_allocation")
    items: List[Dict[str, float]] = []
    if isinstance(raw, list):
        for row in raw:
            if not isinstance(row, dict):
                continue
            items.append(
                {
                    "asset_secondary": str(row.get("asset_secondary") or "其他"),
                    "value_output": _to_float(row.get("value_output")),
                    "ratio_pct": _to_float(row.get("ratio_pct")),
                }
            )
    if items:
        return sorted(items, key=lambda item: item["value_output"], reverse=True)

    holdings = module.get("holdings") if isinstance(module.get("holdings"), list) else []
    total = 0.0
    buffer: Dict[str, float] = {}
    for row in holdings:
        if not isinstance(row, dict):
            continue
        secondary = str(row.get("asset_secondary") or "其他")
        value = _to_float(row.get("market_value_output"))
        total += value
        buffer[secondary] = buffer.get(secondary, 0.0) + value
    if total <= 0:
        return []
    result = []
    for key, value in sorted(buffer.items(), key=lambda item: item[1], reverse=True):
        result.append({"asset_secondary": key, "value_output": value, "ratio_pct": value / total * 100.0})
    return result


def _generate_ai_advice(
    analyzer: Optional[Any],
    output_currency: str,
    target_return_pct: float,
    total_value: float,
    profit_pct: float,
    gap_to_target: float,
    secondary: List[Dict[str, float]],
    market_report: str,
) -> str:
    top_secondary = secondary[0] if secondary else {"asset_secondary": "暂无", "ratio_pct": 0.0}
    fallback = _build_fallback_advice(
        target_return_pct=target_return_pct,
        profit_pct=profit_pct,
        gap_to_target=gap_to_target,
        top_secondary_name=str(top_secondary["asset_secondary"]),
        top_secondary_ratio=_to_float(top_secondary["ratio_pct"]),
        market_report=market_report,
    )
    if not analyzer or not hasattr(analyzer, "_call_openai_api"):
        return fallback

    try:
        secondary_lines = "\n".join(
            [
                f"- {item['asset_secondary']}: {item['value_output']:.2f} {output_currency} ({item['ratio_pct']:.2f}%)"
                for item in secondary
            ]
        )
        prompt = (
            "你是一名资产配置顾问。请基于以下数据给出3-5条简洁可执行建议，"
            "覆盖仓位调整、风险控制、与年度目标的差距管理。输出使用中文Markdown列表。\n\n"
            f"当前总资产: {total_value:.2f} {output_currency}\n"
            f"当前收益率: {profit_pct:.2f}%\n"
            f"年度目标收益率: {target_return_pct:.2f}%\n"
            f"距离目标差额: {gap_to_target:.2f} {output_currency}\n"
            f"二级分类分布:\n{secondary_lines or '- 暂无持仓'}\n\n"
            f"当前市场情况摘要:\n{(market_report or '暂无市场复盘信息')[:1200]}\n"
        )
        text = analyzer._call_openai_api(prompt, {"temperature": 0.2, "max_output_tokens": 700})
        text = str(text or "").strip()
        if text:
            return text
    except Exception as exc:
        logger.warning("生成 AI 资产建议失败，降级为规则建议: %s", exc)
    return fallback


def _build_fallback_advice(
    target_return_pct: float,
    profit_pct: float,
    gap_to_target: float,
    top_secondary_name: str,
    top_secondary_ratio: float,
    market_report: str,
) -> str:
    lines = []
    if top_secondary_ratio >= 55:
        lines.append(f"- `{top_secondary_name}` 占比已达 {top_secondary_ratio:.2f}%，建议分批降低集中度，防止单一风格回撤。")
    elif top_secondary_ratio >= 35:
        lines.append(f"- `{top_secondary_name}` 为当前最大敞口（{top_secondary_ratio:.2f}%），建议设置再平衡阈值并定期复核。")
    else:
        lines.append("- 当前二级分类分布相对均衡，可维持核心仓位并根据信号做小幅动态调整。")

    if profit_pct >= target_return_pct:
        lines.append("- 当前收益率已达到年度目标，优先考虑锁定部分收益并降低高波动资产仓位。")
    elif gap_to_target > 0:
        lines.append("- 距离年度目标仍有差额，建议在回撤时分批布局高质量资产，不追涨。")
    else:
        lines.append("- 当前进度优于目标路径，保持纪律，避免在短期噪音中频繁换仓。")

    if "波动" in (market_report or "") or "风险" in (market_report or ""):
        lines.append("- 市场摘要提示波动/风险上行，建议提高现金或防御资产缓冲，控制组合回撤。")
    else:
        lines.append("- 市场环境未出现明显风险词，建议按既定仓位框架稳步执行并关注关键事件窗口。")
    return "\n".join(lines)


def _to_float(value: Any) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0


def _extract_compact_review_date(filename: str) -> str:
    matched = re.search(r"position_review_(\d{8})\.md$", str(filename))
    if not matched:
        return ""
    return matched.group(1)


def _normalize_review_date_compact(raw: str) -> str:
    text = str(raw or "").strip()
    if re.fullmatch(r"\d{8}", text):
        return text
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        return text.replace("-", "")
    return ""


def _format_review_date(compact_date: str) -> str:
    if not re.fullmatch(r"\d{8}", compact_date):
        return str(compact_date or "")
    return f"{compact_date[0:4]}-{compact_date[4:6]}-{compact_date[6:8]}"


def _read_review_notes() -> Dict[str, Dict[str, str]]:
    if not REVIEW_NOTES_FILE.exists():
        return {}
    try:
        payload = json.loads(REVIEW_NOTES_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(payload, dict):
        return {}
    result: Dict[str, Dict[str, str]] = {}
    for key, value in payload.items():
        compact_date = _normalize_review_date_compact(str(key))
        if not compact_date or not isinstance(value, dict):
            continue
        result[compact_date] = {
            "note": str(value.get("note") or "").strip(),
            "updated_at": str(value.get("updated_at") or ""),
        }
    return result


def _write_review_notes(notes: Dict[str, Dict[str, str]]) -> None:
    REVIEW_NOTES_FILE.parent.mkdir(parents=True, exist_ok=True)
    REVIEW_NOTES_FILE.write_text(
        json.dumps(notes, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

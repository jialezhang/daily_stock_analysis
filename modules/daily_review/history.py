"""Storage and aggregation helpers for daily review snapshots."""

from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Literal, Optional

from modules.daily_review.config import DailyReviewConfig, load_config
from modules.daily_review.notify.telegram import send_review

ReviewDimension = Literal["day", "week", "month"]


def _normalized_date_key(review_date: str) -> str:
    raw = (review_date or "").strip()
    if len(raw) == 8 and raw.isdigit():
        return raw
    return raw.replace("-", "")


def _date_label(date_key: str) -> str:
    if len(date_key) == 8 and date_key.isdigit():
        return f"{date_key[:4]}-{date_key[4:6]}-{date_key[6:8]}"
    return date_key


def _report_path_by_date_key(date_key: str, config: DailyReviewConfig) -> Path:
    return Path(config.output_dir) / f"review_{date_key}.md"


def _snapshot_path_by_date_key(date_key: str, config: DailyReviewConfig) -> Path:
    return Path(config.output_dir) / f"review_{date_key}.json"


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        return None


def save_snapshot(snapshot: Dict[str, Any], config: DailyReviewConfig) -> Path:
    """Persist one daily review snapshot as JSON."""

    date_key = _normalized_date_key(str(snapshot.get("review_date") or ""))
    if not date_key:
        date_key = datetime.now().strftime("%Y%m%d")
        snapshot["review_date"] = _date_label(date_key)
    path = _snapshot_path_by_date_key(date_key, config)
    Path(config.output_dir).mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_snapshot(review_date: str, config: Optional[DailyReviewConfig] = None) -> Optional[Dict[str, Any]]:
    """Load one snapshot by review date (YYYY-MM-DD or YYYYMMDD)."""

    cfg = config or load_config()
    date_key = _normalized_date_key(review_date)
    path = _snapshot_path_by_date_key(date_key, cfg)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def list_snapshots(limit: int = 180, config: Optional[DailyReviewConfig] = None) -> List[Dict[str, Any]]:
    """Load recent daily snapshots, newest first."""

    cfg = config or load_config()
    output_dir = Path(cfg.output_dir)
    if not output_dir.exists():
        return []
    files = sorted(output_dir.glob("review_*.json"), key=lambda p: p.name, reverse=True)
    snapshots: List[Dict[str, Any]] = []
    for path in files[: max(1, limit)]:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if "review_date" not in payload:
                key = path.stem.replace("review_", "")
                payload["review_date"] = _date_label(key)
            snapshots.append(payload)
        except Exception:
            continue
    return snapshots


def _score_to_regime(score: float) -> str:
    if score >= 2:
        return "进攻"
    if score <= -2:
        return "防守"
    return "平衡"


def _position_by_regime(regime: str) -> str:
    if regime == "进攻":
        return "建议仓位 70-100%"
    if regime == "防守":
        return "建议仓位 0-40%"
    return "建议仓位 40-70%"


def _build_chart_payload(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    regimes = snapshot.get("regimes") or []
    anomalies = snapshot.get("anomalies") or {}
    market_scores = {
        str(item.get("market")): _safe_float(item.get("total_score")) or 0.0
        for item in regimes
        if item.get("market")
    }
    return {
        "market_scores": market_scores,
        "anomaly_counts": {
            "red": int(anomalies.get("red_count") or 0),
            "yellow": int(anomalies.get("yellow_count") or 0),
        },
    }


def _to_period_item(snapshot: Dict[str, Any], period_key: str, period_label: str, dimension: ReviewDimension) -> Dict[str, Any]:
    review_date = str(snapshot.get("review_date") or "")
    return {
        "dimension": dimension,
        "period_key": period_key,
        "period_label": period_label,
        "review_date": review_date,
        "generated_at": snapshot.get("generated_at"),
        "summary": snapshot.get("summary") or "",
        "snapshot": snapshot,
        "charts": _build_chart_payload(snapshot),
    }


def _group_key(date_obj: datetime, dimension: ReviewDimension) -> str:
    if dimension == "week":
        year, week, _ = date_obj.isocalendar()
        return f"{year}-W{week:02d}"
    if dimension == "month":
        return date_obj.strftime("%Y-%m")
    return date_obj.strftime("%Y-%m-%d")


def _aggregate_group(group_key: str, snapshots: List[Dict[str, Any]], dimension: ReviewDimension) -> Dict[str, Any]:
    snapshots = sorted(snapshots, key=lambda x: str(x.get("review_date") or ""))
    base = dict(snapshots[-1]) if snapshots else {}

    market_scores: Dict[str, List[float]] = defaultdict(list)
    for snap in snapshots:
        for reg in snap.get("regimes") or []:
            market = str(reg.get("market") or "")
            score = _safe_float(reg.get("total_score"))
            if market and score is not None:
                market_scores[market].append(score)

    merged_regimes: List[Dict[str, Any]] = []
    for market in ["US", "HK", "A"]:
        values = market_scores.get(market, [])
        if not values:
            continue
        avg_score = round(mean(values), 2)
        regime = _score_to_regime(avg_score)
        merged_regimes.append(
            {
                "market": market,
                "total_score": avg_score,
                "regime": regime,
                "position_suggestion": _position_by_regime(regime),
                "score_details": {},
                "reasoning": f"{dimension}维度聚合，样本数 {len(values)}",
            }
        )

    red = sum(int((snap.get("anomalies") or {}).get("red_count") or 0) for snap in snapshots)
    yellow = sum(int((snap.get("anomalies") or {}).get("yellow_count") or 0) for snap in snapshots)
    base["regimes"] = merged_regimes
    base["anomalies"] = {
        "red_count": red,
        "yellow_count": yellow,
        "items": [],
    }
    base["summary"] = str(base.get("summary") or f"{group_key} 聚合复盘，共 {len(snapshots)} 条日度记录。")
    base["review_date"] = str(base.get("review_date") or "")

    return _to_period_item(
        snapshot=base,
        period_key=group_key,
        period_label=group_key,
        dimension=dimension,
    )


def build_period_items(
    *,
    dimension: ReviewDimension = "day",
    limit: int = 180,
    config: Optional[DailyReviewConfig] = None,
) -> List[Dict[str, Any]]:
    """Build day/week/month items for web rendering."""

    snapshots = list_snapshots(limit=limit * 3, config=config)
    if dimension == "day":
        return [
            _to_period_item(
                snapshot=snap,
                period_key=str(snap.get("review_date") or ""),
                period_label=str(snap.get("review_date") or ""),
                dimension="day",
            )
            for snap in snapshots[:limit]
        ]

    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for snap in snapshots:
        review_date = str(snap.get("review_date") or "")
        try:
            dt = datetime.strptime(review_date, "%Y-%m-%d")
        except Exception:
            continue
        key = _group_key(dt, dimension)
        grouped[key].append(snap)

    keys = sorted(grouped.keys(), reverse=True)[:limit]
    return [_aggregate_group(key, grouped[key], dimension) for key in keys]


def _run_async(coro) -> bool:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return bool(asyncio.run(coro))

    with ThreadPoolExecutor(max_workers=1) as executor:
        return bool(executor.submit(lambda: asyncio.run(coro)).result())


def push_review_by_date(review_date: str, config: Optional[DailyReviewConfig] = None) -> bool:
    """Push one saved markdown review to Telegram by date."""

    cfg = config or load_config()
    date_key = _normalized_date_key(review_date)
    path = _report_path_by_date_key(date_key, cfg)
    if not path.exists():
        return False
    content = path.read_text(encoding="utf-8")
    return _run_async(send_review(content, cfg))

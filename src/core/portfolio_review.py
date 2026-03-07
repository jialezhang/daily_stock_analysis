# -*- coding: utf-8 -*-
"""Portfolio review snapshot helpers."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from src.storage import get_db


def _safe_json_loads(raw_value: Any) -> Any:
    """Safely parse JSON strings."""
    if raw_value in (None, ""):
        return None
    if isinstance(raw_value, (dict, list)):
        return raw_value
    try:
        return json.loads(str(raw_value))
    except (TypeError, ValueError, json.JSONDecodeError):
        return None


def _serialize_snapshot(row: Any) -> Dict[str, Any]:
    """Convert one snapshot row to API payload."""
    if isinstance(row, dict):
        get_value = row.get
    else:
        get_value = lambda key, default=None: getattr(row, key, default)
    return {
        "review_date": get_value("date").isoformat() if get_value("date") else "",
        "generated_at": get_value("created_at").isoformat(timespec="seconds") if get_value("created_at") else "",
        "total_value_cny": float(get_value("total_value_cny", 0.0) or 0.0),
        "cash_pct": float(get_value("cash_pct", 0.0) or 0.0),
        "us_pct": float(get_value("us_pct", 0.0) or 0.0),
        "hk_pct": float(get_value("hk_pct", 0.0) or 0.0),
        "a_pct": float(get_value("a_pct", 0.0) or 0.0),
        "crypto_pct": float(get_value("crypto_pct", 0.0) or 0.0),
        "health_score": int(get_value("health_score", 0) or 0),
        "health_grade": str(get_value("health_grade", "") or ""),
        "holdings": _safe_json_loads(get_value("holdings_json", "")) or [],
        "review_report": str(get_value("review_report", "") or ""),
    }


def load_latest_portfolio_review() -> Optional[Dict[str, Any]]:
    """Load the latest persisted portfolio review snapshot."""
    row = get_db().get_latest_portfolio_snapshot()
    if row is None:
        return None
    return _serialize_snapshot(row)


def list_portfolio_reviews(limit: int = 120) -> List[Dict[str, Any]]:
    """Load recent persisted portfolio review snapshots."""
    rows = get_db().list_portfolio_snapshots(limit=limit)
    return [_serialize_snapshot(row) for row in rows]

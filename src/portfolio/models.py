# -*- coding: utf-8 -*-
"""Portfolio module data models."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class MacroData:
    """Macro snapshot."""

    date: str
    treasury_10y: Optional[float] = None
    treasury_10y_daily_change_bps: Optional[float] = None
    treasury_10y_5d_change_bps: Optional[float] = None
    usd_index: Optional[float] = None
    usd_index_daily_change_pct: Optional[float] = None
    vix: Optional[float] = None
    vix_daily_change_pct: Optional[float] = None
    usd_cnh: Optional[float] = None
    spy_close: Optional[float] = None
    spy_ma50: Optional[float] = None
    spy_ma200: Optional[float] = None
    hyg_5d_return: Optional[float] = None
    kweb_5d_return: Optional[float] = None


@dataclass
class LiquidityData:
    """Liquidity snapshot."""

    date: str
    a_turnover_billion: Optional[float] = None
    margin_balance_billion: Optional[float] = None
    margin_balance_3d_trend: Optional[str] = None
    northbound_daily_billion: Optional[float] = None
    northbound_5d_cumulative: Optional[float] = None
    southbound_daily_billion: Optional[float] = None
    southbound_5d_avg: Optional[float] = None
    hsi_close: Optional[float] = None
    hsi_ma20: Optional[float] = None
    hsi_ma60: Optional[float] = None
    csi300_close: Optional[float] = None
    csi300_ma20: Optional[float] = None
    csi300_ma60: Optional[float] = None


@dataclass
class SectorEntry:
    """One sector row."""

    name: str
    ticker: str
    style: str
    daily_return_pct: float
    rs: float


@dataclass
class SectorData:
    """Sector snapshot."""

    date: str
    us_benchmark_return: float = 0.0
    us_sectors: List[SectorEntry] = field(default_factory=list)
    a_benchmark_return: Optional[float] = None
    a_sectors: List[Dict[str, Any]] = field(default_factory=list)
    hk_benchmark_return: Optional[float] = None
    hk_tech_return: Optional[float] = None


@dataclass
class SectorAnalysis:
    """Sector flow analysis result."""

    us_leaders: List[Dict[str, Any]] = field(default_factory=list)
    us_laggards: List[Dict[str, Any]] = field(default_factory=list)
    us_style: str = "mixed"
    us_style_reasoning: str = ""
    a_leaders: List[Dict[str, Any]] = field(default_factory=list)
    a_laggards: List[Dict[str, Any]] = field(default_factory=list)
    a_theme: str = "unclear"
    a_theme_reasoning: str = ""
    hk_tech_vs_hsi: float = 0.0
    hk_style: str = "sync"


@dataclass
class RegimeResult:
    """Single market regime evaluation result."""

    market: str
    total_score: float = 0.0
    regime: str = "balanced"
    regime_label: str = ""
    allocation_adjust_pct: int = 0
    score_details: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class HealthIssue:
    """Health issue."""

    severity: str
    category: str
    title: str
    detail: str
    action: str


@dataclass
class HealthReport:
    """Portfolio health report."""

    score: int
    grade: str
    issues: List[HealthIssue] = field(default_factory=list)
    allocation_current: Dict[str, float] = field(default_factory=dict)
    allocation_target: Dict[str, float] = field(default_factory=dict)
    allocation_deviation: Dict[str, float] = field(default_factory=dict)


@dataclass
class TradeAction:
    """One concrete trade action."""

    direction: str
    ticker: str
    name: str
    market: str
    current_value_cny: float
    current_pct: float
    target_pct: float
    trade_amount_cny: float
    reason: str
    priority: int
    urgency: str
    share_quantity: float = 0.0
    lot_size: float = 1.0


@dataclass
class RebalancePlan:
    """Portfolio rebalance plan."""

    date: str
    total_asset_cny: float
    cash_after_rebalance_pct: float = 0.0
    actions: List[TradeAction] = field(default_factory=list)
    expected_allocation: Dict[str, float] = field(default_factory=dict)
    summary: str = ""


@dataclass
class AnomalyAlert:
    """Anomaly alert."""

    level: str
    name: str
    message: str
    action: str
    affected_holdings: List[str] = field(default_factory=list)


@dataclass
class PortfolioHolding:
    """Single holding in the portfolio."""

    ticker: str
    name: str
    market: str
    shares: float = 0.0
    avg_cost: float = 0.0
    current_price: float = 0.0
    lot_size: float = 1.0
    value_cny: float = 0.0
    weight_pct: float = 0.0
    daily_change_pct: float = 0.0
    sector: str = ""
    style: str = ""
    beta_level: str = "medium"


@dataclass
class Portfolio:
    """Full portfolio snapshot."""

    total_value_cny: float = 0.0
    initial_capital: float = 1_400_000.0
    target_value: float = 1_820_000.0
    output_currency: str = "CNY"
    output_to_cny_rate: float = 1.0
    holdings: List[PortfolioHolding] = field(default_factory=list)
    cash_cny: float = 0.0
    cash_usd: float = 0.0
    cash_hkd: float = 0.0
    crypto_value_cny: float = 0.0
    peak_value_cny: Optional[float] = None

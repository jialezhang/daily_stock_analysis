# -*- coding: utf-8 -*-
"""Portfolio configuration and constants."""

from typing import Any, Dict, List


TARGET_ALLOCATION: Dict[str, Dict[str, Any]] = {
    "US": {"target_pct": 35.0, "min_pct": 25.0, "max_pct": 45.0, "description": "US equities"},
    "HK": {"target_pct": 30.0, "min_pct": 20.0, "max_pct": 40.0, "description": "HK equities"},
    "A": {"target_pct": 20.0, "min_pct": 10.0, "max_pct": 30.0, "description": "A-share equities"},
    "CASH": {"target_pct": 10.0, "min_pct": 5.0, "max_pct": 30.0, "description": "Cash buffer"},
    "CRYPTO": {"target_pct": 5.0, "min_pct": 0.0, "max_pct": 10.0, "description": "Crypto satellite"},
}

REBALANCE_THRESHOLD_PCT = 5.0

CONCENTRATION_LIMITS = {
    "single_stock_max_pct": 15.0,
    "single_style_max_pct": 40.0,
    "top3_stocks_max_pct": 40.0,
    "very_high_beta_max_pct": 20.0,
}

STOCK_TAGS: Dict[str, Dict[str, str]] = {
    "NVDA": {"sector": "Semiconductor", "style": "tech_growth", "beta": "high"},
    "MSFT": {"sector": "Software", "style": "tech_growth", "beta": "medium"},
    "GOOGL": {"sector": "Internet", "style": "tech_growth", "beta": "medium"},
    "TSLA": {"sector": "EV", "style": "tech_growth", "beta": "very_high"},
    "PDD": {"sector": "E-commerce", "style": "china_consumer", "beta": "high"},
    "RKLB": {"sector": "Aerospace", "style": "tech_growth", "beta": "very_high"},
    "NBIS": {"sector": "AI_Infra", "style": "tech_growth", "beta": "very_high"},
    "09988": {"sector": "E-commerce", "style": "china_tech", "beta": "high"},
    "00700": {"sector": "Internet", "style": "china_tech", "beta": "medium"},
    "002195": {"sector": "Materials", "style": "a_share_theme", "beta": "high"},
    "600118": {"sector": "Satellite", "style": "a_share_theme", "beta": "high"},
    "BTC": {"sector": "Crypto", "style": "alternative", "beta": "very_high"},
}

US_SECTOR_ETFS = {
    "XLK": {"name": "Technology", "style": "offensive"},
    "XLY": {"name": "Consumer Discretionary", "style": "offensive"},
    "XLC": {"name": "Communication", "style": "offensive"},
    "SMH": {"name": "Semiconductor", "style": "offensive"},
    "XLF": {"name": "Financials", "style": "cyclical"},
    "XLI": {"name": "Industrials", "style": "cyclical"},
    "XLB": {"name": "Materials", "style": "cyclical"},
    "XLE": {"name": "Energy", "style": "cyclical"},
    "XLRE": {"name": "Real Estate", "style": "cyclical"},
    "XLU": {"name": "Utilities", "style": "defensive"},
    "XLP": {"name": "Consumer Staples", "style": "defensive"},
    "XLV": {"name": "Healthcare", "style": "defensive"},
}

SW_SECTOR_STYLES: Dict[str, List[str]] = {
    "tech_growth": ["电子", "计算机", "通信", "传媒", "国防军工"],
    "financials": ["银行", "非银金融", "房地产"],
    "consumer": [
        "食品饮料",
        "医药生物",
        "家用电器",
        "美容护理",
        "社会服务",
        "商贸零售",
        "纺织服饰",
        "轻工制造",
        "农林牧渔",
    ],
    "cyclical": ["煤炭", "石油石化", "有色金属", "钢铁", "基础化工", "建筑材料"],
    "manufacturing": ["电力设备", "机械设备", "汽车", "建筑装饰", "环保", "公用事业", "交通运输", "综合"],
}

REGIME_DIMENSIONS = {
    "US": {
        "trend": {"weight": 2, "desc": "SPY 均线排列"},
        "volatility": {"weight": 2, "desc": "VIX 水平"},
        "credit": {"weight": 1, "desc": "HYG 信用利差方向"},
        "sector_clarity": {"weight": 1, "desc": "板块领涨一致性"},
    },
    "HK": {
        "trend": {"weight": 2, "desc": "HSI 均线排列"},
        "southbound": {"weight": 2, "desc": "南向资金方向"},
        "usd_pressure": {"weight": 1, "desc": "美元指数压力"},
        "kweb_momentum": {"weight": 1, "desc": "KWEB 动量（外资情绪）"},
    },
    "A": {
        "trend": {"weight": 2, "desc": "沪深300 均线排列"},
        "liquidity": {"weight": 2, "desc": "A 股成交量水平"},
        "northbound": {"weight": 1, "desc": "北向资金方向"},
        "leverage": {"weight": 1, "desc": "融资余额趋势"},
    },
}

REGIME_POSITION_MAP = [
    {"min_score": 3, "label": "进攻", "regime": "aggressive", "adjust_pct": 10},
    {"min_score": 0, "label": "均衡", "regime": "balanced", "adjust_pct": 0},
    {"min_score": -3, "label": "谨慎", "regime": "cautious", "adjust_pct": -10},
    {"min_score": -99, "label": "防守", "regime": "defensive", "adjust_pct": -20},
]

PORTFOLIO_LLM_SYSTEM_PROMPT = (
    "You are an investment advisor managing a cross-market portfolio. "
    "Summarize the core contradiction, give concrete rebalance suggestions, "
    "and explain how anomalies impact current holdings."
)

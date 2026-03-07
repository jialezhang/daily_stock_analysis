"""Configuration and constants for daily multi-market review."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from zoneinfo import ZoneInfo


SH_TZ = ZoneInfo("Asia/Shanghai")
US_TZ = ZoneInfo("US/Eastern")


MACRO_TICKERS: Dict[str, str] = {
    "us_10y": "^TNX",
    "usd_index": "DX-Y.NYB",
    "vix": "^VIX",
    "usd_cnh": "CNY=X",
}


US_LIQUIDITY_TICKERS: Dict[str, str] = {
    "spy_volume": "SPY",
    "hyg": "HYG",
    "tlt": "TLT",
}


HK_LIQUIDITY_TICKERS: Dict[str, str] = {
    "hsi": "^HSI",
    "hstech": "^HSTECH",
    "kweb": "KWEB",
}


US_SECTORS: Dict[str, Dict[str, str]] = {
    "XLK": {"name": "科技", "style": "offensive"},
    "XLY": {"name": "可选消费", "style": "offensive"},
    "XLC": {"name": "通信", "style": "offensive"},
    "SMH": {"name": "半导体", "style": "offensive"},
    "ARKK": {"name": "创新科技", "style": "offensive"},
    "XLF": {"name": "金融", "style": "cyclical"},
    "XLI": {"name": "工业", "style": "cyclical"},
    "XLB": {"name": "材料", "style": "cyclical"},
    "XLRE": {"name": "地产", "style": "cyclical"},
    "XLE": {"name": "能源", "style": "cyclical"},
    "XLU": {"name": "公用事业", "style": "defensive"},
    "XLP": {"name": "必选消费", "style": "defensive"},
    "XLV": {"name": "医疗", "style": "defensive"},
}
US_BENCHMARK = "SPY"


SW_SECTOR_STYLES: Dict[str, List[str]] = {
    "科技主线": ["电子", "计算机", "通信", "传媒", "国防军工"],
    "大金融主线": ["银行", "非银金融", "房地产"],
    "消费主线": [
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
    "资源主线": ["煤炭", "石油石化", "有色金属", "钢铁", "基础化工", "建筑材料"],
}
A_SHARE_BENCHMARK = "000300.SH"


HK_SECTORS: Dict[str, Dict[str, str]] = {
    "^HSI": {"name": "恒生指数", "style": "benchmark"},
    "^HSTECH": {"name": "恒生科技", "style": "offensive"},
    "^HSNF": {"name": "恒生金融", "style": "cyclical"},
    "^HSNP": {"name": "恒生地产", "style": "cyclical"},
    "3033.HK": {"name": "南方恒生科技", "style": "offensive"},
    "2800.HK": {"name": "盈富基金", "style": "benchmark"},
}


WATCHLIST: List[Dict[str, Optional[str]]] = [
    {"name": "腾讯控股", "ticker_yf": "0700.HK", "ticker_ts": None, "market": "HK", "sector": "恒生科技"},
    {"name": "阿里巴巴", "ticker_yf": "BABA", "ticker_ts": None, "market": "US", "sector": "XLC"},
    {"name": "中国卫通", "ticker_yf": None, "ticker_ts": "601698.SH", "market": "A", "sector": "通信"},
    {"name": "中科曙光", "ticker_yf": None, "ticker_ts": "603019.SH", "market": "A", "sector": "计算机"},
]


US_REGIME_RULES = {
    "liquidity": {
        "+1": "hyg_5d_return > 0 and spy_volume_ratio > 1.0",
        "-1": "hyg_5d_return < -0.01",
    },
    "trend": {
        "+1": "spy_close > spy_ma50 and spy_ma50 > spy_ma200",
        "-1": "spy_close < spy_ma50 and spy_ma50 < spy_ma200",
    },
    "risk_appetite": {
        "+1": "vix < 18 and abs(treasury_change) < 0.05",
        "-1": "vix > 25 or abs(treasury_change) > 0.10",
    },
    "sector_clarity": {
        "+1": "top3_same_style and top3_min_rs > 0.5",
        "-1": "top3_mixed_style",
    },
}


A_REGIME_RULES = {
    "liquidity": {
        "+1": "a_turnover > 12000 and northbound > 0",
        "-1": "a_turnover < 8000 or northbound < -50",
    },
    "leverage": {
        "+1": "margin_balance_3d_trend == 'up'",
        "-1": "margin_balance_3d_trend == 'down'",
    },
    "trend": {
        "+1": "csi300_close > csi300_ma20 and csi300_ma20 > csi300_ma60",
        "-1": "csi300_close < csi300_ma20 and csi300_ma20 < csi300_ma60",
    },
    "sector_clarity": {
        "+1": "top5_dominant_style_count >= 3",
        "-1": "top5_style_count >= 4",
    },
}


HK_REGIME_RULES = {
    "liquidity": {
        "+1": "southbound > 20",
        "-1": "southbound < -20",
    },
    "trend": {
        "+1": "hsi_close > hsi_ma20",
        "-1": "hsi_close < hsi_ma60",
    },
    "risk_appetite": {
        "+1": "kweb_5d_return > 0.02",
        "-1": "kweb_5d_return < -0.03",
    },
    "macro_pressure": {
        "+1": "usd_index < 103 and usd_cnh_change < 0",
        "-1": "usd_index > 106 or usd_cnh_change > 0.03",
    },
}


ANOMALY_RULES = {
    "us_treasury_shock": {
        "level": "RED",
        "name": "美债收益率剧震",
        "threshold": 0.15,
    },
    "vix_spike": {
        "level": "RED",
        "name": "VIX 恐慌飙升",
        "vix_abs": 30,
        "vix_change_pct": 0.30,
    },
    "usd_breakout": {
        "level": "RED",
        "name": "美元指数突破关键位",
        "upper": 107,
        "lower": 99,
    },
    "northbound_panic": {
        "level": "RED",
        "name": "北向资金恐慌性流出",
        "threshold": -100,
    },
    "a_share_volume_collapse": {
        "level": "RED",
        "name": "A 股成交额断崖",
        "threshold": 5000,
    },
    "cnh_crash": {
        "level": "RED",
        "name": "离岸人民币急贬",
        "threshold": 0.005,
    },
    "vix_elevated": {
        "level": "YELLOW",
        "name": "VIX 进入警戒区间",
        "lower": 25,
        "upper": 30,
    },
    "treasury_drift": {
        "level": "YELLOW",
        "name": "美债收益率持续攀升",
        "threshold": 0.20,
    },
    "northbound_sustained_outflow": {
        "level": "YELLOW",
        "name": "北向资金连续流出",
        "threshold": -150,
    },
    "margin_deleveraging": {
        "level": "YELLOW",
        "name": "融资盘去杠杆",
        "threshold": -0.02,
    },
    "a_share_volume_shrink": {
        "level": "YELLOW",
        "name": "A 股持续缩量",
    },
    "hyg_credit_stress": {
        "level": "YELLOW",
        "name": "美股信用利差走阔",
        "threshold": -0.02,
    },
    "stock_anomaly": {
        "level": "YELLOW",
        "name": "持仓个股异动",
        "threshold": -3.0,
    },
    "stock_volume_spike": {
        "level": "YELLOW",
        "name": "持仓个股异常放量",
        "volume_ratio": 3.0,
        "drop_pct": -2.0,
    },
}


TELEGRAM_CONFIG = {
    "bot_token_env": "TELEGRAM_BOT_TOKEN",
    "chat_id_env": "TELEGRAM_CHAT_ID",
    "parse_mode": "MarkdownV2",
    "max_message_length": 4000,
}


LLM_CONFIG = {
    "provider": "openai",
    "model": "gpt-4o",
    "api_key_env": "OPENAI_API_KEY",
    "temperature": 0.3,
    "max_tokens": 800,
    "system_prompt": (
        "你是一位管理美股、港股、A股三地仓位的职业投资者的助手。"
        "根据提供的市场数据，用 3-5 句话总结："
        "1) 今日三个市场各自的核心矛盾；"
        "2) 资金在往哪个方向流动；"
        "3) 三个市场各自建议仓位和方向。"
        "语言要简洁、有观点、可执行。"
    ),
}


@dataclass
class DailyReviewConfig:
    """Runtime configuration for daily review."""

    tushare_token: Optional[str]
    output_dir: Path = field(default_factory=lambda: Path("reports"))
    filename_pattern: str = "review_{date}.md"
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    llm_provider: str = "openai"
    llm_model: str = "gpt-4o"
    llm_api_key: Optional[str] = None


@dataclass
class RegimeScorecard:
    """Scorecard container for one market."""

    market: str
    scores: Dict[str, int] = field(default_factory=dict)


def today_shanghai() -> datetime:
    """Return current Shanghai datetime."""

    return datetime.now(SH_TZ)


def load_config() -> DailyReviewConfig:
    """Load runtime config from environment and existing project config."""

    token = os.getenv("TUSHARE_TOKEN")
    if not token:
        try:
            from src.config import get_config

            cfg = get_config()
            token = getattr(cfg, "tushare_token", None)
        except Exception:
            token = None

    return DailyReviewConfig(
        tushare_token=token,
        output_dir=Path("reports"),
        filename_pattern="review_{date}.md",
        telegram_bot_token=os.getenv(TELEGRAM_CONFIG["bot_token_env"]),
        telegram_chat_id=os.getenv(TELEGRAM_CONFIG["chat_id_env"]),
        llm_provider=LLM_CONFIG["provider"],
        llm_model=LLM_CONFIG["model"],
        llm_api_key=os.getenv(LLM_CONFIG["api_key_env"]),
    )

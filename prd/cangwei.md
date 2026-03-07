# 任务：新增跨市场仓位管理 + 增强版每日复盘模块

## 项目背景

这是一个已有的股票分析系统（Python 后端 + React 前端），目前支持：
- 个股分析（A股/美股/港股）：`src/core/pipeline.py`
- 大盘复盘（中国/美国）：`src/core/market_review.py` + `src/market_analyzer.py`
- 多渠道通知推送：`src/notification.py`
- 数据获取：`data_provider/`（yfinance、tushare、akshare 等）
- LLM 分析：`src/analyzer.py`（LiteLLM 统一接口）
- SQLite 存储：`src/storage.py`
- FastAPI 后端：`api/`
- React 前端：`apps/dsa-web/`

**当前大盘复盘（`market_review.py`）只生成叙述性 LLM 报告，不具备以下能力：**
- 追踪用户实际持仓
- 计算配置偏离度
- 生成具体交易动作（买/卖 + 金额）
- 量化评分市场环境
- 分级异常检测与告警

**本次任务将以上所有功能作为新模块 `src/portfolio/` 加入系统。**

---

## 现有代码地图（需要理解的关键文件）

| 文件 | 作用 | 与新模块的关系 |
|------|------|---------------|
| `src/config.py` | 全局配置单例（`Config` dataclass，`.env` 加载） | **修改**：新增 portfolio 配置字段 |
| `src/core/config_registry.py` | 配置字段的 UI 元数据 | **修改**：注册新 portfolio 配置字段 |
| `src/core/market_review.py` | 每日大盘复盘入口 | **修改**：复盘完成后集成 portfolio review |
| `src/market_analyzer.py` | `MarketAnalyzer` 类，获取指数/板块/新闻，调用 LLM | **只读**：复用 `get_market_overview()` 获取指数数据 |
| `src/core/market_strategy.py` | `MarketStrategyBlueprint` 中美策略蓝图 | **只读**：参考策略维度设计模式 |
| `src/core/market_profile.py` | `MarketProfile` 中美区域配置 | **只读**：参考区域配置模式 |
| `src/analyzer.py` | `GeminiAnalyzer`（LiteLLM 封装），`AnalysisResult` | **复用**：调用 `analyzer.generate_text()` 生成 LLM 摘要 |
| `src/notification.py` | `NotificationService` 多渠道推送 | **复用**：调用 `notifier.send()` 推送报告 |
| `src/storage.py` | SQLAlchemy 模型，`StockDatabase` 单例 | **修改**：新增 `PortfolioSnapshot` ORM 模型 |
| `data_provider/base.py` | `DataFetcherManager` 带降级链 | **复用**：获取指数/ETF 数据 |
| `data_provider/yfinance_fetcher.py` | Yahoo Finance 数据源（美/港/A） | **复用**：获取 SPY、VIX、HYG、板块ETF、HSI 等 |
| `data_provider/tushare_fetcher.py` | Tushare Pro 数据源（A股） | **复用**：获取 A 股流动性数据（融资、北向） |
| `src/core/pipeline.py` | `StockAnalysisPipeline` 主编排器 | **只读**：参考并行数据获取模式 |
| `main.py` | CLI 入口，调用 `run_market_review()` | **修改**：新增 `--portfolio-review` 参数 |
| `src/scheduler.py` | 每日定时任务调度器 | **只读**：portfolio review 挂入现有调度 |
| `AGENTS.md` | 编码规范 | **遵守**：英文注释、black+isort、120 字符行宽 |

---

## 新增目录结构

```
src/portfolio/                          # 🆕 全部新文件
├── __init__.py
├── config.py                           # 组合管理专用配置与常量
├── models.py                           # 所有中间结果的 dataclass
├── data/
│   ├── __init__.py
│   ├── macro_fetcher.py                # 获取 VIX、10Y、USD、SPY MA、HYG、KWEB
│   ├── liquidity_fetcher.py            # 获取 A 股成交额、融资、北向/南向、HSI/CSI300 MA
│   └── sector_fetcher.py              # 获取美股板块 ETF RS、申万行业 RS
├── analysis/
│   ├── __init__.py
│   ├── health_check.py                 # 组合健康诊断（100 分制）
│   ├── market_regime.py                # 各市场环境评分（美/港/A）
│   ├── sector_flow.py                  # 板块风格分析（进攻/防守/周期）
│   ├── rebalance.py                    # 再平衡计算引擎 → TradeAction 列表
│   └── anomaly.py                      # 分级异常检测（RED/YELLOW）
├── report/
│   ├── __init__.py
│   ├── renderer.py                     # Markdown 报告渲染器
│   └── llm_digest.py                   # LLM 摘要生成
├── runner.py                           # 主入口：run_portfolio_review()
└── tests/
    ├── __init__.py
    ├── test_health_check.py
    ├── test_rebalance.py
    ├── test_market_regime.py
    └── test_anomaly.py
```

---

## 详细实现规格

### 1. `src/portfolio/config.py` — 组合配置

```python
"""Portfolio position management configuration and constants."""

from dataclasses import dataclass, field
from typing import Dict, List, Any

# 各市场目标配置（占总组合百分比）
TARGET_ALLOCATION: Dict[str, Dict[str, Any]] = {
    "US": {"target_pct": 35, "min_pct": 25, "max_pct": 45, "description": "US equities"},
    "HK": {"target_pct": 30, "min_pct": 20, "max_pct": 40, "description": "HK equities"},
    "A":  {"target_pct": 20, "min_pct": 10, "max_pct": 30, "description": "A-share equities"},
    "CASH": {"target_pct": 10, "min_pct": 5, "max_pct": 30, "description": "Cash buffer"},
    "CRYPTO": {"target_pct": 5, "min_pct": 0, "max_pct": 10, "description": "Crypto satellite"},
}

# 再平衡阈值：偏离超过此值时触发建议
REBALANCE_THRESHOLD_PCT = 5

# 集中度限制
CONCENTRATION_LIMITS = {
    "single_stock_max_pct": 15,
    "single_style_max_pct": 40,
    "top3_stocks_max_pct": 40,
}

# 持仓元数据标签（板块、风格、beta 级别）
# 用户通过 .env 或 Web UI 配置；以下为默认值
STOCK_TAGS: Dict[str, Dict[str, str]] = {
    "NVDA":   {"sector": "Semiconductor", "style": "tech_growth", "beta": "high"},
    "MSFT":   {"sector": "Software",      "style": "tech_growth", "beta": "medium"},
    "GOOGL":  {"sector": "Internet",      "style": "tech_growth", "beta": "medium"},
    "TSLA":   {"sector": "EV",            "style": "tech_growth", "beta": "very_high"},
    "PDD":    {"sector": "E-commerce",    "style": "china_consumer", "beta": "high"},
    "RKLB":   {"sector": "Aerospace",     "style": "tech_growth", "beta": "very_high"},
    "NBIS":   {"sector": "AI_Infra",      "style": "tech_growth", "beta": "very_high"},
    "09988":  {"sector": "E-commerce",    "style": "china_tech",  "beta": "high"},
    "00700":  {"sector": "Internet",      "style": "china_tech",  "beta": "medium"},
    "002195": {"sector": "Materials",     "style": "a_share_theme", "beta": "high"},
    "600118": {"sector": "Satellite",     "style": "a_share_theme", "beta": "high"},
    "BTC":    {"sector": "Crypto",        "style": "alternative",  "beta": "very_high"},
}

# 美股板块 ETF（用于板块轮动分析）
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

# A 股申万行业风格映射
SW_SECTOR_STYLES = {
    "tech_growth": ["电子", "计算机", "通信", "传媒", "国防军工"],
    "financials":  ["银行", "非银金融", "房地产"],
    "consumer":    ["食品饮料", "医药生物", "家用电器", "美容护理", "社会服务",
                    "商贸零售", "纺织服饰", "轻工制造", "农林牧渔"],
    "cyclical":    ["煤炭", "石油石化", "有色金属", "钢铁", "基础化工", "建筑材料"],
    "manufacturing": ["电力设备", "机械设备", "汽车", "建筑装饰", "环保",
                      "公用事业", "交通运输", "综合"],
}

# 宏观指标 ticker（通过 yfinance 获取）
MACRO_TICKERS = {
    "us_10y": "^TNX",
    "usd_index": "DX-Y.NYB",
    "vix": "^VIX",
    "usd_cnh": "CNY=X",
}

LIQUIDITY_TICKERS = {
    "spy": "SPY",
    "hyg": "HYG",
    "tlt": "TLT",
    "kweb": "KWEB",
}

# 市场环境评分维度与权重
REGIME_DIMENSIONS = {
    "US": {
        "trend":          {"weight": 2, "desc": "SPY 均线排列"},
        "volatility":     {"weight": 2, "desc": "VIX 水平"},
        "credit":         {"weight": 1, "desc": "HYG 信用利差方向"},
        "sector_clarity": {"weight": 1, "desc": "板块领涨一致性"},
    },
    "HK": {
        "trend":          {"weight": 2, "desc": "HSI 均线排列"},
        "southbound":     {"weight": 2, "desc": "南向资金方向"},
        "usd_pressure":   {"weight": 1, "desc": "美元指数压力"},
        "kweb_momentum":  {"weight": 1, "desc": "KWEB 动量（外资情绪）"},
    },
    "A": {
        "trend":          {"weight": 2, "desc": "沪深300 均线排列"},
        "liquidity":      {"weight": 2, "desc": "A 股成交量水平"},
        "northbound":     {"weight": 1, "desc": "北向资金方向"},
        "leverage":       {"weight": 1, "desc": "融资余额趋势"},
    },
}

# 环境评分 → 仓位调整映射
REGIME_POSITION_MAP = [
    {"min_score": 3,   "label": "🟢 进攻", "adjust_pct": +10},
    {"min_score": 0,   "label": "🟡 均衡", "adjust_pct": 0},
    {"min_score": -3,  "label": "🟠 谨慎", "adjust_pct": -10},
    {"min_score": -99, "label": "🔴 防守", "adjust_pct": -20},
]

# 异常规则（两级：RED = 今日行动，YELLOW = 观察1-2天）
ANOMALY_RULES = {
    "vix_panic": {
        "level": "RED",
        "name": "VIX 恐慌飙升",
        "condition_desc": "vix > 30 or vix_daily_change_pct > 30%",
        "action_template": "总仓位降至50%以下。优先卖出 beta=very_high 持仓（{affected}）",
    },
    "treasury_shock": {
        "level": "RED",
        "name": "美债收益率冲击",
        "condition_desc": "abs(10y daily change) > 15bps",
        "action_template": "减仓美股成长股。受影响：{affected}",
    },
    "usd_breakout": {
        "level": "RED",
        "name": "美元指数突破107",
        "condition_desc": "usd_index > 107",
        "action_template": "减仓港股和A股。受影响：{affected}",
    },
    "single_stock_crash": {
        "level": "RED",
        "name": "单只持仓暴跌超8%",
        "condition_desc": "any holding daily_change < -8%",
        "action_template": "检查 {affected} 是否有利空消息。若无明确催化剂，下一开盘减半仓位。",
    },
    "portfolio_drawdown": {
        "level": "RED",
        "name": "组合回撤超15%",
        "condition_desc": "drawdown_from_peak > 15%",
        "action_template": "启动止损纪律：权益仓位降至60%。锁定剩余资金。",
    },
    "vix_elevated": {
        "level": "YELLOW",
        "name": "VIX 进入警戒区",
        "condition_desc": "25 < vix <= 30",
        "action_template": "暂停新开仓。持有现有仓位。密切关注。",
    },
    "cash_too_low": {
        "level": "YELLOW",
        "name": "现金比例低于最低线",
        "condition_desc": "cash_pct < 5%",
        "action_template": "卖出最弱持仓补充现金至10%。候选：{affected}",
    },
    "concentration_breach": {
        "level": "YELLOW",
        "name": "集中度超限",
        "condition_desc": "single_stock > 15% or single_style > 40%",
        "action_template": "未来1-2天逐步减仓超配头寸。超配：{affected}",
    },
    "hyg_credit_stress": {
        "level": "YELLOW",
        "name": "美国信用利差走阔",
        "condition_desc": "hyg_5d_return < -2%",
        "action_template": "美股配置转向大盘蓝筹。减仓小盘高beta：{affected}",
    },
}

# LLM 系统提示词（组合复盘摘要用）
PORTFOLIO_LLM_SYSTEM_PROMPT = (
    "You are an investment advisor managing a ~1.4M CNY cross-market portfolio. "
    "Holdings: US tech (NVDA, MSFT, GOOGL, TSLA, PDD, RKLB, NBIS), "
    "HK (Tencent 00700, Alibaba 09988), A-share themes, and small BTC position. "
    "Annual target: 30% return. Current drawdown: ~10%.\n\n"
    "Based on the data provided:\n"
    "1. Summarize today's core contradiction across the 3 markets in 2 sentences.\n"
    "2. Give 1-2 most urgent rebalance suggestions (specific ticker + direction).\n"
    "3. If anomalies exist, assess their concrete impact on current holdings.\n\n"
    "Requirements: Be direct and actionable. Never say 'suggest monitoring'. "
    "Say 'sell NBIS, rotate into XX' instead."
)
```

### 2. `src/portfolio/models.py` — 数据模型

定义模块中使用的所有 dataclass：

```python
"""Portfolio module data models."""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any


@dataclass
class MacroData:
    """宏观数据快照"""
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
    """流动性数据快照"""
    date: str
    a_turnover_billion: Optional[float] = None
    margin_balance_billion: Optional[float] = None
    margin_balance_3d_trend: Optional[str] = None  # "up" | "down" | "flat"
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
    """单个板块条目"""
    name: str
    ticker: str
    style: str  # "offensive" | "defensive" | "cyclical"
    daily_return_pct: float
    rs: float  # 相对强度 = 板块收益 - 基准收益


@dataclass
class SectorData:
    """板块数据快照"""
    date: str
    us_benchmark_return: float = 0.0
    us_sectors: List[SectorEntry] = field(default_factory=list)
    a_benchmark_return: Optional[float] = None
    a_sectors: List[Dict] = field(default_factory=list)
    hk_benchmark_return: Optional[float] = None
    hk_tech_return: Optional[float] = None


@dataclass
class SectorAnalysis:
    """板块分析结果"""
    us_leaders: List[Dict] = field(default_factory=list)
    us_laggards: List[Dict] = field(default_factory=list)
    us_style: str = "mixed"  # "offensive" | "defensive" | "cyclical" | "mixed"
    us_style_reasoning: str = ""
    a_leaders: List[Dict] = field(default_factory=list)
    a_laggards: List[Dict] = field(default_factory=list)
    a_theme: str = "unclear"  # "tech_growth" | "financials" | "consumer" 等
    a_theme_reasoning: str = ""
    hk_tech_vs_hsi: float = 0.0
    hk_style: str = "sync"  # "tech_leading" | "tech_lagging" | "sync"


@dataclass
class RegimeResult:
    """单个市场的环境评分结果"""
    market: str  # "US" | "HK" | "A"
    total_score: float = 0.0
    regime: str = "balanced"  # "aggressive" | "balanced" | "cautious" | "defensive"
    regime_label: str = ""
    allocation_adjust_pct: int = 0
    score_details: List[Dict] = field(default_factory=list)
    # 每项: {"dimension": str, "score": int, "weight": int, "weighted": int, "reason": str}


@dataclass
class HealthIssue:
    """健康检查发现的问题"""
    severity: str  # "CRITICAL" | "WARNING" | "INFO"
    category: str  # "allocation" | "concentration" | "style" | "cash" | "target"
    title: str
    detail: str  # 包含具体数字
    action: str  # 具体可执行建议


@dataclass
class HealthReport:
    """组合健康报告"""
    score: int  # 0-100
    grade: str  # "A" | "B" | "C" | "D" | "F"
    issues: List[HealthIssue] = field(default_factory=list)
    allocation_current: Dict[str, float] = field(default_factory=dict)
    allocation_target: Dict[str, float] = field(default_factory=dict)
    allocation_deviation: Dict[str, float] = field(default_factory=dict)


@dataclass
class TradeAction:
    """单条交易建议"""
    direction: str  # "SELL" | "BUY" | "HOLD"
    ticker: str
    name: str
    market: str
    current_value_cny: float
    current_pct: float
    target_pct: float
    trade_amount_cny: float  # 正=买入，负=卖出
    reason: str
    priority: int  # 1=紧急, 2=本周, 3=可选
    urgency: str  # "today" | "this_week" | "when_ready"


@dataclass
class RebalancePlan:
    """再平衡方案"""
    date: str
    total_asset_cny: float
    cash_after_rebalance_pct: float = 0.0
    actions: List[TradeAction] = field(default_factory=list)
    expected_allocation: Dict[str, float] = field(default_factory=dict)
    summary: str = ""


@dataclass
class AnomalyAlert:
    """异常告警"""
    level: str  # "RED" | "YELLOW"
    name: str
    message: str  # 包含具体数值
    action: str  # 包含具体标的名称的操作建议
    affected_holdings: List[str] = field(default_factory=list)


@dataclass
class PortfolioHolding:
    """单只持仓"""
    ticker: str
    name: str
    market: str  # "US" | "HK" | "A" | "CRYPTO"
    shares: float = 0.0
    avg_cost: float = 0.0
    current_price: float = 0.0
    value_cny: float = 0.0
    weight_pct: float = 0.0
    daily_change_pct: float = 0.0
    sector: str = ""
    style: str = ""
    beta_level: str = "medium"


@dataclass
class Portfolio:
    """完整组合状态，传入复盘流水线"""
    total_value_cny: float = 0.0
    initial_capital: float = 1_400_000.0
    target_value: float = 1_820_000.0
    holdings: List[PortfolioHolding] = field(default_factory=list)
    cash_cny: float = 0.0
    cash_usd: float = 0.0
    cash_hkd: float = 0.0
    crypto_value_cny: float = 0.0
```

### 3. 数据获取层（`src/portfolio/data/`）

#### `macro_fetcher.py` — 宏观数据获取
- 使用 `yfinance.download()` 批量获取近 3 个月数据：`^TNX`、`DX-Y.NYB`、`^VIX`、`CNY=X`、`SPY`、`HYG`、`TLT`、`KWEB`
- 计算：日变动、5日变动、SPY 的 MA50/MA200
- 所有获取逻辑用 try/except 包裹；失败字段设为 `None`
- 返回 `MacroData` dataclass

#### `liquidity_fetcher.py` — 流动性数据获取
- A 股数据通过 `tushare_fetcher.py`（复用已有的 `TushareFetcher`）：
  - `pro.moneyflow_hsgt()` → 北向/南向资金
  - `pro.margin()` → 融资余额
  - A 股成交额：汇总 `pro.daily()` 或用指数成交量代理
  - 沪深300 MA：`pro.index_daily(ts_code='000300.SH')`
- 港股数据通过 `yfinance`：`^HSI` 获取 HSI MA20/MA60
- 若 tushare 不可用，A 股字段设为 `None`（优雅降级）
- 返回 `LiquidityData` dataclass

#### `sector_fetcher.py` — 板块数据获取
- 美股板块：`yfinance.download()` 获取所有板块 ETF + SPY，计算 1 日收益率和 RS（相对强度 = 板块收益 - 基准收益）
- A 股板块：若 tushare 可用，使用 `pro.index_daily()` 获取申万行业指数；否则跳过
- 港股：`yfinance.download('^HSI', '^HSTECH')`，计算 RS
- 返回 `SectorData` dataclass

### 4. 分析引擎（`src/portfolio/analysis/`）

#### `health_check.py` — 组合健康诊断
**输入**：`Portfolio` + 配置
**输出**：`HealthReport`

检查项：
1. **配置偏离**：当前 vs TARGET_ALLOCATION。偏离 > 阈值 → WARNING；> 2倍阈值 → CRITICAL
2. **现金水平**：< min_pct → CRITICAL；< target_pct → WARNING
3. **单只集中度**：任何持仓 > single_stock_max_pct → CRITICAL
4. **前三集中度**：前3大持仓之和 > top3_stocks_max_pct → WARNING
5. **风格集中度**：按 style 标签汇总，任何风格 > single_style_max_pct → CRITICAL
6. **Beta 暴露**：very_high beta 持仓合计 > 20% → WARNING
7. **目标可达性**：所需收益率 > 40% → WARNING；> 60% → CRITICAL

**评分**：起始 100 分，每个 CRITICAL 扣 15 分，每个 WARNING 扣 5 分。
**等级**：A(80+)、B(60-79)、C(40-59)、D(20-39)、F(0-19)。

#### `market_regime.py` — 市场环境评分
**输入**：`MacroData`、`LiquidityData`、`SectorData`
**输出**：每个市场（US、HK、A）的 `RegimeResult`

对每个市场，评估 `REGIME_DIMENSIONS` 中的每个维度：
- 每个维度打分 +1、0 或 -1
- 乘以权重
- 加权分数求和
- 通过 `REGIME_POSITION_MAP` 映射到环境等级
- **每个评分必须包含中文 `reason` 字符串**，解释原因

**美股评分规则：**
- trend：SPY 收盘 > MA50 > MA200 → +1；收盘 < MA50 < MA200 → -1
- volatility：VIX < 18 → +1；VIX > 25 → -1
- credit：HYG 5日收益 > 0 → +1；< -1.5% → -1
- sector_clarity：前3板块同风格 → +1；混合 → -1

**港股评分规则：**
- trend：HSI 收盘 > MA20 > MA60 → +1；收盘 < MA20 < MA60 → -1
- southbound：5日均值 > 200亿 → +1；< -100亿 → -1
- usd_pressure：美元指数 < 103 → +1；> 106 → -1
- kweb_momentum：KWEB 5日收益 > 2% → +1；< -3% → -1

**A 股评分规则：**
- trend：沪深300 收盘 > MA20 > MA60 → +1；收盘 < MA20 < MA60 → -1
- liquidity：A 股成交 > 1.2万亿 → +1；< 8000亿 → -1
- northbound：5日累计 > 500亿 → +1；< -800亿 → -1
- leverage：融资余额3日趋势上升 → +1；下降 → -1

#### `sector_flow.py` — 板块风格分析
**输入**：`SectorData`
**输出**：`SectorAnalysis`

**美股风格**：取 RS 前3板块，检查其 style 标签。≥2 个 offensive → "offensive"；≥2 个 defensive → "defensive"；≥2 个 cyclical → "cyclical"；否则 "mixed"。

**A 股主题**：取前5申万行业，映射到 SW_SECTOR_STYLES 分组，统计哪个分组出现最多。≥3 → 该分组为主题；否则 "unclear"。

#### `rebalance.py` — 再平衡引擎
**输入**：`Portfolio`、`HealthReport`、3个 `RegimeResult`、`List[AnomalyAlert]`、`SectorAnalysis`
**输出**：`RebalancePlan`

**逻辑：**
1. **动态目标配置**：基准 = TARGET_ALLOCATION；按各市场 regime 的 `adjust_pct` 调整；多余部分归入 CASH
2. **计算市场级偏离**：current_pct - dynamic_target_pct
3. **按优先级生成 TradeAction**：
   - P1（今日）：RED 异常动作、单只超集中度、现金低于绝对最低线
   - P2（本周）：超配市场再平衡（卖最弱 RS 持仓）/ 低配市场（买最强 RS）
   - P3（可选）：减仓 very_high beta 弱势股、分散风格
4. **金额计算**：trade_amount = 偏离金额 × 50%（渐进式，非一步到位）；单次卖出 ≤ 该持仓的 30%；单次买入 ≤ 总资产的 5%
5. 按 priority 排序

#### `anomaly.py` — 异常检测
**输入**：`MacroData`、`LiquidityData`、个股数据、`Portfolio`、配置
**输出**：`List[AnomalyAlert]`

遍历 `ANOMALY_RULES`，逐条检查条件是否触发。
对每条触发的规则：
- 根据规则类型确定 `affected_holdings`（如 VIX → 所有美股高 beta 持仓）
- 用实际标的名称替换 `{affected}` 格式化 `action` 字符串
- 排序：RED 优先，然后按受影响市值降序

### 5. 报告与通知（`src/portfolio/report/`）

#### `renderer.py` — Markdown 报告渲染
渲染完整 Markdown 报告，包含以下板块：
1. 🚨 异常告警（RED 优先，然后 YELLOW）— 仅在有告警时显示
2. 🏥 健康评分 + 等级 + 问题表格 + 配置对比表
3. 🎯 交易建议（P1/P2/P3 分区）
4. 📊 市场环境表格（美/港/A 含评分明细）
5. 📈 板块风格摘要
6. 💼 持仓明细表
7. 🤖 LLM 摘要
8. 📍 目标追踪（初始 → 当前 → 目标，所需收益率 %）

#### `llm_digest.py` — LLM 摘要生成
- 将所有数据打包为结构化文本
- 使用 `PORTFOLIO_LLM_SYSTEM_PROMPT` 作为系统提示词
- 调用 `analyzer.generate_text(prompt, max_tokens=1000, temperature=0.3)`
- 失败时回退：返回 "(AI 摘要不可用)"

### 6. `src/portfolio/runner.py` — 主入口

```python
def run_portfolio_review(
    portfolio: Portfolio,
    notifier: NotificationService,
    analyzer: Optional[GeminiAnalyzer] = None,
    send_notification: bool = True,
) -> Optional[str]:
    """
    组合每日复盘主入口。

    步骤：
    1. 并行获取：宏观、流动性、板块数据
    2. 运行健康检查
    3. 评估市场环境（美/港/A）
    4. 分析板块风格
    5. 检测异常
    6. 计算再平衡方案
    7. 生成 LLM 摘要
    8. 渲染报告
    9. 保存 & 推送通知

    返回：
        报告 Markdown 字符串，失败返回 None。
    """
```

使用 `ThreadPoolExecutor(max_workers=4)` 并行获取数据（与 `pipeline.py` 相同模式）。

### 7. 对现有文件的修改

#### `src/config.py` — 在 `Config` dataclass 中新增字段：

```python
# === 组合管理 ===
portfolio_enabled: bool = False  # 总开关
portfolio_initial_capital: float = 1_400_000.0
portfolio_target_return: float = 0.30
portfolio_holdings_json: str = ""  # 持仓 JSON 字符串，从 PORTFOLIO_HOLDINGS 环境变量加载
portfolio_stock_tags_json: str = ""  # STOCK_TAGS 的 JSON 覆盖
```

在 `_load_from_env()` 中添加对应的环境变量解析。

#### `src/core/config_registry.py` — 注册新字段：

新增分类 `"portfolio"`，`display_order: 45`，注册 4 个新字段，配置合适的 UI 控件（开关、数字、JSON 文本框）。

#### `src/storage.py` — 新增 ORM 模型：

```python
class PortfolioSnapshot(Base):
    """每日组合快照，用于追踪。"""
    __tablename__ = 'portfolio_snapshots'
    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False, index=True)
    total_value_cny = Column(Float)
    cash_pct = Column(Float)
    us_pct = Column(Float)
    hk_pct = Column(Float)
    a_pct = Column(Float)
    crypto_pct = Column(Float)
    health_score = Column(Integer)
    health_grade = Column(String(2))
    holdings_json = Column(Text)  # 完整持仓快照 JSON
    review_report = Column(Text)  # 完整 Markdown 报告
    created_at = Column(DateTime, default=datetime.now)
    __table_args__ = (UniqueConstraint('date', name='uix_portfolio_date'),)
```

#### `src/core/market_review.py` — 集成钩子：

在现有大盘复盘完成后，若 `config.portfolio_enabled`：
```python
from src.portfolio.runner import run_portfolio_review
# ... 从配置加载组合 ...
portfolio_report = run_portfolio_review(portfolio, notifier, analyzer, send_notification)
```

#### `main.py` — 新增 CLI 参数：

新增 `--portfolio-review` 参数，可独立触发组合复盘。

### 8. 测试（`src/portfolio/tests/`）

#### `test_health_check.py`
- 构造 94% 权益、75% 科技风格的组合 → 验证生成 CRITICAL 问题
- 构造均衡组合 → 验证高分（≥80）
- 构造现金 < 5% 的组合 → 验证 CRITICAL 现金问题
- 验证评分计算：100 - 15×CRITICAL数 - 5×WARNING数

#### `test_rebalance.py`
- 构造美股超配 + 美股防守环境 → 验证生成 SELL 美股动作
- 构造 A 股低配 + A 股进攻环境 → 验证生成 BUY A 股动作
- 构造 RED 异常 → 验证生成 P1 动作
- 验证单次卖出 ≤ 30%，单次买入 ≤ 5%
- 验证再平衡后预期配置在合理范围内

#### `test_market_regime.py`
- 构造全面看多数据 → 验证 "aggressive" 环境
- 构造全面看空数据 → 验证 "defensive" 环境
- 验证加权分数计算正确
- 验证每个 score_detail 都有非空 reason

#### `test_anomaly.py`
- 对每条 ANOMALY_RULE，构造触发数据 → 验证生成告警
- 验证 affected_holdings 正确映射到组合持仓
- 验证 RED 告警排在 YELLOW 之前
- 构造正常数据 → 验证无告警

---

## 实现约束

1. **永不崩溃**：任何数据源失败都不能阻止报告生成。缺失字段显示 "N/A"。
2. **可执行输出**：每个 `TradeAction` 必须有具体标的、金额、理由和时间线。
3. **可解释评分**：每个 regime 维度评分必须附带中文 `reason` 字符串。
4. **风控优先**：P1（风控）永远排在 P2（再平衡）之前输出。
5. **渐进调仓**：每次调整偏离的 50%，非 100%。
6. **数据源隔离**：tushare 和 yfinance 严格分离，便于替换。
7. **时区正确**：美股数据用 US/Eastern，港股/A 股数据用 Asia/Shanghai。
8. **Telegram 友好**：表格不能太宽，手机端可读。
9. **遵守 AGENTS.md**：英文注释、black+isort 格式、120 字符行宽、不经确认不 `git commit`。
10. **复用现有基础设施**：使用 `DataFetcherManager`、`GeminiAnalyzer.generate_text()`、`NotificationService.send()`、`get_db()` — 不要创建平行实现。

## 依赖（添加到 requirements.txt）

无需新依赖 — 项目已有 `yfinance`、`tushare`、`pandas`、`numpy`、`litellm`、`python-telegram-bot`（通过 notification senders）。

## 验证

实现完成后运行：
```bash
python -m py_compile src/portfolio/__init__.py src/portfolio/config.py src/portfolio/models.py
python -m py_compile src/portfolio/data/macro_fetcher.py src/portfolio/data/liquidity_fetcher.py src/portfolio/data/sector_fetcher.py
python -m py_compile src/portfolio/analysis/health_check.py src/portfolio/analysis/market_regime.py src/portfolio/analysis/sector_flow.py src/portfolio/analysis/rebalance.py src/portfolio/analysis/anomaly.py
python -m py_compile src/portfolio/report/renderer.py src/portfolio/report/llm_digest.py src/portfolio/runner.py
python -m pytest src/portfolio/tests/ -v
```

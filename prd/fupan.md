# Task: 在现有项目中新增「每日市场复盘」模块

## 背景约束
- 这是一个**已有 Python 项目**中的新模块，不是独立项目
- 数据源：A 股用 `tushare pro`，美股/港股用 `yfinance`
- IM 通道：通过 Telegram Bot 推送复盘消息
- Python 3.10+，代码风格与已有项目保持一致

## 新增目录结构
```
modules/daily_review/
├── __init__.py
├── config.py              # 所有配置常量与阈值
├── runner.py              # 入口调度器
├── data/
│   ├── __init__.py
│   ├── macro.py           # 宏观指标采集
│   ├── liquidity.py       # 流动性指标采集
│   ├── sector.py          # 板块数据采集
│   └── stock.py           # 个股数据采集
├── analysis/
│   ├── __init__.py
│   ├── market_regime.py   # 市场状态判定（进攻/防守/观望）
│   ├── sector_flow.py     # 板块资金偏好分析
│   └── anomaly.py         # 异常检测与告警
├── report/
│   ├── __init__.py
│   ├── renderer.py        # Markdown 报告渲染
│   └── llm_digest.py      # LLM 生成摘要（可选）
├── notify/
│   └── telegram.py        # Telegram 推送
└── tests/
    ├── test_market_regime.py
    ├── test_anomaly.py
    └── test_sector_flow.py
```

---

## config.py — 完整配置

```python
"""每日复盘模块配置"""
from dataclasses import dataclass, field

# ============================================================
# 一、数据源配置
# ============================================================

TUSHARE_TOKEN = "从环境变量或项目已有配置中读取"

# ============================================================
# 二、三大市场核心监测指标体系
# ============================================================
#
# 设计原则：每个指标都要回答一个问题——
#   "当前该用多少仓位？该进攻还是防守？"
#
# 指标分为三层：
#   L1 定价锚（决定全球风险偏好的根源）
#   L2 流动性（决定市场能涨多高/跌多深）
#   L3 结构（决定钱往哪个方向流）
# ============================================================

# ---------- L1: 全球定价锚 ----------
# 这些指标决定"大方向"，是仓位管理的最高优先级
MACRO_TICKERS = {
    # 美国 10 年期国债收益率 —— 全球资产定价的分母
    # 逻辑：收益率上行 → 成长股承压、港股承压、A股外资流出
    #       收益率下行 → 成长股受益、流动性宽松预期
    "us_10y": "^TNX",

    # 美元指数 —— 全球资金流向的风向标
    # 逻辑：美元走强 → 新兴市场资金外流、港股承压、人民币贬值压力
    #       美元走弱 → 新兴市场受益、北向资金倾向流入
    "usd_index": "DX-Y.NYB",

    # VIX 恐慌指数 —— 美股期权市场隐含的恐慌程度
    # 逻辑：VIX 是均值回归的，极端值有很强的信号意义
    #   < 15: 市场极度自满，往往是风险积累期（不是卖出信号，但要警惕）
    #   15-20: 正常区间
    #   20-30: 市场紧张，波动加大
    #   > 30: 恐慌模式，历史上往往是中期底部区域（反向指标）
    "vix": "^VIX",

    # 离岸人民币 —— A股和港股的汇率锚
    # 逻辑：人民币贬值 → 外资流出A股、港股承压
    #       人民币升值 → 外资流入、港股受益
    "usd_cnh": "CNY=X",
}

# ---------- L2: 各市场流动性指标 ----------
# 这些指标决定"水位高低"，是仓位弹性的依据

# --- A 股流动性 ---
# tushare 接口映射
TUSHARE_INTERFACES = {
    # 沪深港通资金流向（北向=外资，南向=内地买港股）
    # 接口：moneyflow_hsgt
    # 字段：north_money(北向净买入), south_money(南向净买入)，单位：百万元
    "hsgt_flow": "moneyflow_hsgt",

    # 融资融券汇总
    # 接口：margin（沪市）/ margin（深市）
    # 关注：rzye(融资余额)，日环比变化反映杠杆资金情绪
    "margin": "margin",

    # 每日市场总成交额 —— 通过 daily 接口汇总或用 moneyflow 接口
    # A 股成交额是最直观的市场活跃度指标
    # 逻辑：
    #   > 1.2 万亿：增量资金入场，市场活跃，可以积极参与
    #   8000亿 - 1.2万亿：存量博弈，精选个股
    #   < 8000亿：缩量，观望为主
    #   < 6000亿：极度缩量，往往是阶段性底部区域
    "daily_basic": "daily_basic",

    # 申万行业分类
    # 接口：index_classify（获取行业列表）
    # 接口：sw_daily（获取行业指数日行情）
    "sw_index_classify": "index_classify",
    "sw_daily": "sw_daily",
}

# --- 美股流动性 ---
# 美股没有直接的"成交额"单一指标，用以下代理：
US_LIQUIDITY_TICKERS = {
    # SPY 成交量 —— 美股整体活跃度的代理
    "spy_volume": "SPY",
    # HYG（高收益债 ETF）—— 信用利差的代理
    # 逻辑：HYG 下跌 = 信用利差走阔 = 风险偏好下降 = 避险
    #       HYG 上涨 = 信用利差收窄 = 风险偏好上升 = 进攻
    "hyg": "HYG",
    # TLT（20年美债 ETF）—— 长端利率方向
    # TLT 和成长股通常负相关
    "tlt": "TLT",
}

# --- 港股流动性 ---
# 港股的核心流动性来源是南向资金（内地资金）
# 通过 tushare moneyflow_hsgt 的 south_money 字段获取
# 额外监测：
HK_LIQUIDITY_TICKERS = {
    # 恒生指数
    "hsi": "^HSI",
    # 恒生科技指数 —— 港股核心赛道
    "hstech": "^HSTECH",
    # 中国互联网 ETF（美股上市）—— 外资对中国科技的情绪代理
    "kweb": "KWEB",
}

# ============================================================
# 三、板块划分与资金偏好判断逻辑
# ============================================================

# ---------- 美股板块：标普 11 大行业 + 重点主题 ----------
# 判断逻辑：计算每个板块 ETF 相对 SPY 的超额收益（RS）
#   RS > 0 且连续 3 日为正 → 资金偏好该板块
#   RS < 0 且连续 3 日为负 → 资金撤离该板块
#
# 进攻/防守判断：
#   如果领涨板块是 XLK/XLY/SMH（进攻型）→ 市场风险偏好高
#   如果领涨板块是 XLU/XLP/XLV（防守型）→ 市场在避险
#   如果 XLE 独强 → 通胀交易，对成长股不利

US_SECTORS = {
    # 进攻型板块
    "XLK": {"name": "科技", "style": "offensive"},
    "XLY": {"name": "可选消费", "style": "offensive"},
    "XLC": {"name": "通信", "style": "offensive"},
    "SMH": {"name": "半导体", "style": "offensive"},
    "ARKK": {"name": "创新科技", "style": "offensive"},
    # 周期型板块
    "XLF": {"name": "金融", "style": "cyclical"},
    "XLI": {"name": "工业", "style": "cyclical"},
    "XLB": {"name": "材料", "style": "cyclical"},
    "XLRE": {"name": "地产", "style": "cyclical"},
    "XLE": {"name": "能源", "style": "cyclical"},
    # 防守型板块
    "XLU": {"name": "公用事业", "style": "defensive"},
    "XLP": {"name": "必选消费", "style": "defensive"},
    "XLV": {"name": "医疗", "style": "defensive"},
}
US_BENCHMARK = "SPY"

# ---------- A 股板块：申万一级行业（31个）----------
# 数据来源：tushare index_classify(level='L1', src='SW2021')
#          + sw_daily 获取日行情
#
# 判断逻辑：
#   1. 计算每个行业指数相对沪深300的 RS
#   2. 按 RS 排序，取 Top5 和 Bottom5
#   3. 风格判断：
#      - 如果 Top5 集中在「电子/计算机/通信/国防军工」→ 科技主线
#      - 如果 Top5 集中在「银行/非银/地产」→ 大金融主线（通常是护盘）
#      - 如果 Top5 集中在「食品饮料/医药/家电」→ 消费主线
#      - 如果 Top5 集中在「煤炭/石油/有色」→ 资源/通胀主线
#      - 如果 Top5 分散无规律 → 无明确主线，存量博弈
#
# 申万一级行业风格标签（用于自动判断主线）
SW_SECTOR_STYLES = {
    "科技成长": ["电子", "计算机", "通信", "传媒", "国防军工"],
    "大金融": ["银行", "非银金融", "房地产"],
    "大消费": ["食品饮料", "医药生物", "家用电器", "美容护理",
               "社会服务", "商贸零售", "纺织服饰", "轻工制造", "农林牧渔"],
    "周期资源": ["煤炭", "石油石化", "有色金属", "钢铁", "基础化工", "建筑材料"],
    "制造": ["电力设备", "机械设备", "汽车", "建筑装饰", "环保", "公用事业", "交通运输", "综合"],
}
A_SHARE_BENCHMARK = "000300.SH"  # 沪深300

# ---------- 港股板块 ----------
# 港股板块较简单，主要看几个核心指数的相对表现
HK_SECTORS = {
    "^HSI": {"name": "恒生指数", "style": "benchmark"},
    "^HSTECH": {"name": "恒生科技", "style": "offensive"},
    "^HSNF": {"name": "恒生金融", "style": "cyclical"},
    "^HSNP": {"name": "恒生地产", "style": "cyclical"},
    # 个股 ETF 代理
    "3033.HK": {"name": "南方恒生科技", "style": "offensive"},
    "2800.HK": {"name": "盈富基金(跟踪HSI)", "style": "benchmark"},
}

# ============================================================
# 四、持仓监控列表
# ============================================================
WATCHLIST = [
    {"name": "腾讯控股", "ticker_yf": "0700.HK", "ticker_ts": None,
     "market": "HK", "sector": "恒生科技"},
    {"name": "阿里巴巴", "ticker_yf": "BABA", "ticker_ts": None,
     "market": "US", "sector": "XLC"},
    {"name": "中国卫通", "ticker_yf": None, "ticker_ts": "601698.SH",
     "market": "A", "sector": "通信"},
    {"name": "中科曙光", "ticker_yf": None, "ticker_ts": "603019.SH",
     "market": "A", "sector": "计算机"},
]

# ============================================================
# 五、市场状态判定规则（Market Regime）
# ============================================================
# 这是整个系统最核心的输出：告诉用户当前该用什么仓位
#
# 三档仓位建议：
#   🟢 进攻（70-100% 仓位）：流动性充裕 + 风险偏好高 + 有明确主线
#   🟡 平衡（40-70% 仓位）：流动性一般 + 无明显方向
#   🔴 防守（0-40% 仓位）：流动性收缩 + 风险信号出现
#
# 每个市场独立评分，最终综合

@dataclass
class RegimeScorecard:
    """
    每个市场的状态评分卡，每项 -1/0/+1 分
    总分 > 2 → 进攻
    总分 -1 ~ 2 → 平衡
    总分 < -1 → 防守
    """
    market: str  # "US" / "HK" / "A"
    scores: dict = field(default_factory=dict)
    # scores 示例:
    # {
    #   "liquidity": +1,       # 流动性充裕
    #   "trend": 0,            # 趋势中性
    #   "risk_appetite": +1,   # 风险偏好高
    #   "sector_clarity": -1,  # 板块主线不清晰
    # }

# --- 美股评分规则 ---
US_REGIME_RULES = {
    "liquidity": {
        # HYG 5日涨跌幅 > 0 且 SPY 成交量 > 20日均量 → +1
        # HYG 5日涨跌幅 < -1% → -1
        # 其他 → 0
        "+1": "hyg_5d_return > 0 and spy_volume_ratio > 1.0",
        "-1": "hyg_5d_return < -0.01",
    },
    "trend": {
        # SPY 收盘价 > MA50 且 MA50 > MA200 → +1（多头排列）
        # SPY 收盘价 < MA50 且 MA50 < MA200 → -1（空头排列）
        # 其他 → 0
        "+1": "spy_close > spy_ma50 and spy_ma50 > spy_ma200",
        "-1": "spy_close < spy_ma50 and spy_ma50 < spy_ma200",
    },
    "risk_appetite": {
        # VIX < 18 且 10Y 收益率日变动 < 5bps → +1
        # VIX > 25 或 10Y 收益率日变动 > 10bps → -1
        "+1": "vix < 18 and abs(treasury_change) < 0.05",
        "-1": "vix > 25 or abs(treasury_change) > 0.10",
    },
    "sector_clarity": {
        # 前3领涨板块 RS 均 > 0.5% 且风格一致 → +1
        # 前3领涨板块风格分散（进攻+防守混合）→ -1
        "+1": "top3_same_style and top3_min_rs > 0.5",
        "-1": "top3_mixed_style",
    },
}

# --- A 股评分规则 ---
A_REGIME_RULES = {
    "liquidity": {
        # 成交额 > 1.2万亿 且 北向净买入 > 0 → +1
        # 成交额 < 8000亿 或 北向净卖出 > 50亿 → -1
        "+1": "a_turnover > 12000 and northbound > 0",
        "-1": "a_turnover < 8000 or northbound < -50",
    },
    "leverage": {
        # 融资余额连续3日增加 → +1
        # 融资余额连续3日减少 → -1
        "+1": "margin_balance_3d_trend == 'up'",
        "-1": "margin_balance_3d_trend == 'down'",
    },
    "trend": {
        # 沪深300 > MA20 且 MA20 > MA60 → +1
        # 沪深300 < MA20 且 MA20 < MA60 → -1
        "+1": "csi300_close > csi300_ma20 and csi300_ma20 > csi300_ma60",
        "-1": "csi300_close < csi300_ma20 and csi300_ma20 < csi300_ma60",
    },
    "sector_clarity": {
        # 申万行业 Top5 中 ≥ 3 个属于同一风格 → +1
        # Top5 分散在 ≥ 4 个不同风格 → -1
        "+1": "top5_dominant_style_count >= 3",
        "-1": "top5_style_count >= 4",
    },
}

# --- 港股评分规则 ---
HK_REGIME_RULES = {
    "liquidity": {
        # 南向资金净买入 > 20亿 → +1
        # 南向资金净卖出 > 20亿 → -1
        "+1": "southbound > 20",
        "-1": "southbound < -20",
    },
    "trend": {
        # 恒生指数 > MA20 → +1
        # 恒生指数 < MA60 → -1
        "+1": "hsi_close > hsi_ma20",
        "-1": "hsi_close < hsi_ma60",
    },
    "risk_appetite": {
        # KWEB 5日涨幅 > 2% → +1
        # KWEB 5日跌幅 > 3% → -1（外资在抛售中国科技）
        "+1": "kweb_5d_return > 0.02",
        "-1": "kweb_5d_return < -0.03",
    },
    "macro_pressure": {
        # 美元指数 < 103 且 离岸人民币升值 → +1
        # 美元指数 > 106 或 离岸人民币单日贬值 > 300pips → -1
        "+1": "usd_index < 103 and usd_cnh_change < 0",
        "-1": "usd_index > 106 or usd_cnh_change > 0.03",
    },
}

# ============================================================
# 六、异常告警规则（需要立即处理仓位的信号）
# ============================================================
# 异常 ≠ 日常波动，异常是"需要你放下手里的事立刻看盘"的级别
# 分为两级：
#   🔴 RED（立即行动）：历史上出现后大概率有持续性影响
#   🟡 YELLOW（密切关注）：可能演变为趋势，但也可能是噪音

ANOMALY_RULES = {
    # ========== 🔴 RED 级别：立即行动 ==========

    "us_treasury_shock": {
        "level": "RED",
        "name": "美债收益率剧震",
        "condition": "abs(treasury_10y_daily_change) > 0.15",
        # 10Y 单日变动超过 15bps（如 4.50% → 4.65%）
        # 历史上这种级别的变动通常伴随重大事件（非农/CPI/Fed 意外）
        # 影响：全球股市重新定价，尤其港股和成长股
        "action": "检查持仓中成长股和港股仓位，考虑减仓或对冲",
        "threshold": 0.15,
        "field": "treasury_10y_daily_change",
        "compare": "abs_gt",
    },

    "vix_spike": {
        "level": "RED",
        "name": "VIX 恐慌飙升",
        "condition": "vix > 30 or vix_daily_change_pct > 0.30",
        # VIX 突破 30 或单日涨幅 > 30%
        # 这意味着市场进入恐慌模式，流动性可能枯竭
        # 注意：VIX > 35 反而可能是抄底信号（但需要等企稳）
        "action": "立即审视所有仓位，减仓至防守水平；但若 VIX > 40 可开始分批建仓",
        "thresholds": {"vix_abs": 30, "vix_change_pct": 0.30},
    },

    "usd_breakout": {
        "level": "RED",
        "name": "美元指数突破关键位",
        "condition": "usd_index > 107 or usd_index < 99",
        # 美元突破 107：新兴市场全面承压，港股/A股外资流出加速
        # 美元跌破 99：全球风险偏好大幅改善，新兴市场受益
        "action_up": "减仓港股和 A 股外资重仓股",
        "action_down": "加仓新兴市场相关标的",
        "thresholds": {"upper": 107, "lower": 99},
    },

    "northbound_panic": {
        "level": "RED",
        "name": "北向资金恐慌性流出",
        "condition": "northbound_net < -100",
        # 单日净流出超过 100 亿
        # 这通常意味着外资在系统性减仓，不是个别调仓
        # 历史案例：2022年3月、2023年8月
        "action": "减仓外资重仓股（茅台/宁德/招行等），等待资金流企稳",
        "threshold": -100,
        "field": "northbound_net_billion",
        "compare": "lt",
    },

    "a_share_volume_collapse": {
        "level": "RED",
        "name": "A 股成交额断崖",
        "condition": "a_turnover < 5000",
        # 成交额跌破 5000 亿（2024-2025年标准）
        # 极端缩量意味着市场几乎没有参与意愿
        # 但历史上也往往是底部区域的特征
        "action": "停止交易，等待放量信号；如果已轻仓可开始关注左侧机会",
        "threshold": 5000,
        "field": "a_share_turnover_billion",
        "compare": "lt",
    },

    "cnh_crash": {
        "level": "RED",
        "name": "离岸人民币急贬",
        "condition": "usd_cnh_daily_change > 0.005",
        # USDCNH 单日涨幅超过 500pips（如 7.20 → 7.25）
        # 人民币急贬通常伴随资本外流，A股和港股同时承压
        "action": "减仓港股，关注央行是否出手维稳",
        "threshold": 0.005,
        "field": "usd_cnh_daily_change_pct",
        "compare": "gt",
    },

    # ========== 🟡 YELLOW 级别：密切关注 ==========

    "vix_elevated": {
        "level": "YELLOW",
        "name": "VIX 进入警戒区间",
        "condition": "25 < vix <= 30",
        "action": "控制仓位在 50% 以下，暂停加仓",
        "thresholds": {"lower": 25, "upper": 30},
    },

    "treasury_drift": {
        "level": "YELLOW",
        "name": "美债收益率持续攀升",
        "condition": "treasury_10y_5d_change > 0.20",
        # 5 个交易日累计上行超过 20bps
        # 不是单日剧震，但持续上行的杀伤力更大
        "action": "逐步减仓长久期资产（成长股、港股科技）",
        "threshold": 0.20,
        "field": "treasury_10y_5d_change",
        "compare": "gt",
    },

    "northbound_sustained_outflow": {
        "level": "YELLOW",
        "name": "北向资金连续流出",
        "condition": "northbound_3d_cumulative < -150",
        # 连续 3 日累计流出超过 150 亿
        "action": "减仓外资重仓股，转向内资偏好板块",
        "threshold": -150,
        "field": "northbound_3d_cumulative",
        "compare": "lt",
    },

    "margin_deleveraging": {
        "level": "YELLOW",
        "name": "融资盘去杠杆",
        "condition": "margin_balance_5d_change_pct < -0.02",
        # 融资余额 5 日下降超过 2%
        "action": "警惕融资盘踩踏，避开高融资占比个股",
        "threshold": -0.02,
        "field": "margin_balance_5d_change_pct",
        "compare": "lt",
    },

    "a_share_volume_shrink": {
        "level": "YELLOW",
        "name": "A 股持续缩量",
        "condition": "a_turnover < 7000 for 3 consecutive days",
        # 连续 3 日成交额低于 7000 亿
        "action": "降低交易频率，等待放量方向选择",
        "threshold": 7000,
        "field": "a_share_turnover_3d_all_below",
        "compare": "eq_true",
    },

    "hyg_credit_stress": {
        "level": "YELLOW",
        "name": "美股信用利差走阔",
        "condition": "hyg_5d_return < -0.02",
        # HYG 5日跌幅超过 2%，意味着信用市场在恶化
        "action": "美股仓位转向防守型板块，减少高 beta 敞口",
        "threshold": -0.02,
        "field": "hyg_5d_return",
        "compare": "lt",
    },

    "stock_anomaly": {
        "level": "YELLOW",
        "name": "持仓个股异动",
        "condition": "stock_daily_change < sector_daily_change - 3%",
        # 个股跌幅超过所属板块 3 个百分点
        # 说明不是系统性下跌，是个股出了问题
        "action": "检查个股是否有利空消息，考虑止损",
        "threshold": -3.0,
        "field": "stock_vs_sector_excess_return",
        "compare": "lt",
    },

    "stock_volume_spike": {
        "level": "YELLOW",
        "name": "持仓个股异常放量",
        "condition": "volume > 3 * avg_volume_20d and daily_change < -2%",
        # 放量下跌 = 有人在大量卖出
        "action": "高度警惕，可能有未公开利空，考虑先减仓",
    },
}

# ============================================================
# 七、LLM 配置
# ============================================================
LLM_CONFIG = {
    "provider": "openai",  # "openai" | "none"
    "model": "gpt-4o",
    "api_key_env": "OPENAI_API_KEY",
    "temperature": 0.3,
    "max_tokens": 800,
    "system_prompt": """你是一位管理美股、港股、A股三地仓位的职业投资者的助手。
根据提供的市场数据，用 3-5 句话总结：
1. 今日三个市场各自的核心矛盾是什么
2. 资金在往哪个方向流动（进攻还是防守，哪些板块）
3. 基于以上判断，三个市场各自建议的仓位水平和方向
语言要简洁、有观点、可执行。不要说废话。""",
}

# ============================================================
# 八、Telegram 配置
# ============================================================
TELEGRAM_CONFIG = {
    "bot_token_env": "TELEGRAM_BOT_TOKEN",
    "chat_id_env": "TELEGRAM_CHAT_ID",
    "parse_mode": "MarkdownV2",
    # 消息过长时自动分段发送，Telegram 单条消息限制 4096 字符
    "max_message_length": 4000,
}

# ============================================================
# 九、输出配置
# ============================================================
OUTPUT_CONFIG = {
    "save_path": "./reports/",
    "filename_pattern": "review_{date}.md",
}
```

---

## 模块实现要求

### 1. `data/macro.py`
- 用 `yfinance.download(tickers, period="3mo")` 批量下载所有宏观 ticker
- 返回 `MacroData` dataclass，包含：
  - 当日值、日变动（绝对值和百分比）、5日变动
  - MA50/MA200（用于趋势判断）
- 所有 fetch 操作 wrap try/except，失败返回 None

### 2. `data/liquidity.py`
- A 股数据通过 tushare pro API：
  - `pro.moneyflow_hsgt(trade_date=today)` 获取北向/南向资金
  - `pro.margin(trade_date=today)` 获取融资融券
  - A 股总成交额：`pro.daily_basic(trade_date=today, fields='ts_code,trade_date,turnover_vol,total_mv,amount')` 汇总 amount 字段
- 返回 `LiquidityData` dataclass
- 需要处理 tushare 的日期格式（YYYYMMDD）和交易日判断

### 3. `data/sector.py`
- 美股板块：`yfinance.download(list(US_SECTORS.keys()) + [US_BENCHMARK], period="3mo")`
- A 股板块：
  - `pro.index_classify(level='L1', src='SW2021')` 获取申万一级行业列表
  - `pro.sw_daily(trade_date=today)` 获取当日行业指数行情
  - 计算相对沪深300的 RS
- 港股板块：`yfinance` 获取 HK_SECTORS 中的 ticker
- 返回 `SectorData` dataclass，包含各市场板块列表及 RS 排名

### 4. `data/stock.py`
- 根据 WATCHLIST 中的 market 字段选择数据源
- US/HK → yfinance，A → tushare `pro.daily(ts_code=code)` + `pro.daily_basic()`
- 计算 MA5/MA20/MA60、20日平均成交量、换手率
- 返回 `list[StockEntry]`

### 5. `analysis/market_regime.py`
**这是最核心的模块。**

```python
def evaluate_regime(market: str, macro: MacroData,
                    liquidity: LiquidityData,
                    sectors: SectorData) -> RegimeResult:
    """
    对单个市场进行状态评分。
    返回 RegimeResult:
      - market: str
      - total_score: int
      - regime: "进攻" | "平衡" | "防守"
      - position_suggestion: str  (如 "建议仓位 70-100%")
      - score_details: dict  (每项评分明细)
      - reasoning: str  (评分理由)
    """
```

- 根据 config 中的 US/A/HK_REGIME_RULES 逐项评分
- 每项 +1/0/-1
- 汇总后：
  - 总分 ≥ 2 → 进攻（70-100%）
  - 总分 -1 ~ 1 → 平衡（40-70%）
  - 总分 ≤ -2 → 防守（0-40%）
- `reasoning` 字段用中文说明每项得分的原因

### 6. `analysis/sector_flow.py`

```python
def analyze_sector_preference(sectors: SectorData) -> SectorAnalysis:
    """
    返回 SectorAnalysis:
      - us_leaders: list[SectorEntry]  (Top 3 by RS)
      - us_laggards: list[SectorEntry]  (Bottom 3)
      - us_market_style: str  ("进攻型主导" | "防守型主导" | "风格混合")
      - a_leaders: list  (Top 5 申万行业)
      - a_laggards: list  (Bottom 5)
      - a_main_theme: str  ("科技主线" | "大金融主线" | "消费主线" | "资源主线" | "无明确主线")
      - hk_leader: str
    """
```

- 美股：根据 Top3 板块的 `style` 标签判断市场风格
- A 股：根据 Top5 行业在 `SW_SECTOR_STYLES` 中的归属判断主线
- 港股：比较恒生科技 vs 恒生指数的超额收益

### 7. `analysis/anomaly.py`

```python
def detect_anomalies(macro: MacroData, liquidity: LiquidityData,
                     stocks: list[StockEntry], sectors: SectorData) -> list[AnomalyAlert]:
    """
    遍历 ANOMALY_RULES，逐条检查。
    返回触发的告警列表，按 level 排序（RED 在前）。
    每个 AnomalyAlert 包含:
      - level: "RED" | "YELLOW"
      - name: str
      - message: str (中文，包含具体数值)
      - action: str (建议操作)
    """
```

- 实现时不要用 eval()，而是为每条规则写具体的 if 判断
- 个股异动需要将每只股票的涨跌幅与其所属板块比较

### 8. `report/renderer.py`
渲染最终 Markdown 报告，结构如下：

```markdown
# 📅 {date} 三地市场复盘

{anomaly_alerts_section}

---

## 🎯 仓位建议

| 市场 | 状态 | 建议仓位 | 核心逻辑 |
|------|------|----------|----------|
| 🇺🇸 美股 | {us_regime} | {us_position} | {us_reasoning} |
| 🇭🇰 港股 | {hk_regime} | {hk_position} | {hk_reasoning} |
| 🇨🇳 A 股 | {a_regime} | {a_position} | {a_reasoning} |

---

## 一、全球定价锚

| 指标 | 当前值 | 日变动 | 5日变动 | 信号 |
|------|--------|--------|---------|------|
| 10Y 美债 | {val}% | {chg}bps | {chg5d}bps | {signal} |
| 美元指数 | {val} | {chg}% | {chg5d}% | {signal} |
| VIX | {val} | {chg} | — | {signal} |
| 离岸人民币 | {val} | {chg}pips | — | {signal} |

---

## 二、流动性仪表盘

### A 股
| 指标 | 数值 | 判定 |
|------|------|------|
| 成交额 | {val} 亿 | {label: 活跃/存量博弈/缩量} |
| 融资余额变动 | {val} 亿 | {trend} |
| 北向资金 | {val} 亿 | {label} |

### 港股
| 指标 | 数值 | 判定 |
|------|------|------|
| 南向资金 | {val} 亿 | {label} |
| KWEB 5日表现 | {val}% | {外资情绪} |

### 美股
| 指标 | 数值 | 判定 |
|------|------|------|
| SPY 成交量/20日均量 | {ratio} | {label} |
| HYG 5日表现 | {val}% | {信用环境} |

---

## 三、板块资金流向

### 🇺🇸 美股板块（市场风格：{us_style}）
| 排名 | 板块 | 涨跌幅 | RS | 风格 |
|------|------|--------|----|------|
{us_sector_rows}

### 🇨🇳 A 股板块（当前主线：{a_theme}）
| 排名 | 行业 | 涨跌幅 | RS |
|------|------|--------|----|
{a_sector_rows}

---

## 四、持仓监控

| 标的 | 市场 | 涨跌幅 | vs 板块 | 成交量 | 信号 |
|------|------|--------|---------|--------|------|
{stock_rows}

---

## 五、AI 总结

{llm_summary}

---
*自动生成于 {timestamp}*
```

- 异常告警区域格式：
  - 有 RED 级别：`🔴 **紧急告警**\n{alerts}`
  - 只有 YELLOW：`🟡 **关注信号**\n{alerts}`
  - 无异常：`✅ 市场处于常规波动区间`
- 信号列用 emoji 标记：📈 放量突破 / ⚠️ 异常下跌 / 🔻 跑输板块 / ➖ 正常

### 9. `report/llm_digest.py`
- 将所有数据结构化为文本，发送给 LLM
- 使用 config 中的 system_prompt
- 失败时返回 "（AI 总结暂不可用）"

### 10. `notify/telegram.py`

```python
async def send_review(report_markdown: str, config: dict):
    """
    将报告通过 Telegram Bot 发送。
    - 将 Markdown 转为 Telegram MarkdownV2 格式（转义特殊字符）
    - 如果超过 4000 字符，按 section（---）分段发送
    - 支持发送失败重试（最多 3 次）
    """
```

- 注意 Telegram MarkdownV2 需要转义 `_*[]()~>#+-=|{}.!` 这些字符
- 表格在 Telegram 中显示不好，考虑转为等宽文本格式或简化为列表

### 11. `runner.py`

```python
from concurrent.futures import ThreadPoolExecutor

def run_daily_review():
    """
    入口函数，供外部调用（如定时任务或 Telegram 命令触发）。
    """
    config = load_config()

    # 1. 并行采集数据
    with ThreadPoolExecutor(max_workers=4) as pool:
        macro_f = pool.submit(fetch_macro, config)
        liquidity_f = pool.submit(fetch_liquidity, config)
        sector_f = pool.submit(fetch_sectors, config)
        stock_f = pool.submit(fetch_stocks, config)

    macro = macro_f.result()
    liquidity = liquidity_f.result()
    sectors = sector_f.result()
    stocks = stock_f.result()

    # 2. 分析
    us_regime = evaluate_regime("US", macro, liquidity, sectors)
    hk_regime = evaluate_regime("HK", macro, liquidity, sectors)
    a_regime = evaluate_regime("A", macro, liquidity, sectors)
    sector_analysis = analyze_sector_preference(sectors)
    anomalies = detect_anomalies(macro, liquidity, stocks, sectors)

    # 3. LLM 摘要（可选）
    summary = generate_llm_summary(macro, liquidity, sectors, stocks,
                                    anomalies, [us_regime, hk_regime, a_regime])

    # 4. 渲染报告
    report = render_report(
        macro=macro,
        liquidity=liquidity,
        sectors=sectors,
        sector_analysis=sector_analysis,
        stocks=stocks,
        regimes=[us_regime, hk_regime, a_regime],
        anomalies=anomalies,
        summary=summary,
    )

    # 5. 保存 & 推送
    save_report(report, config)
    await send_telegram(report, config)

    return report
```

### 12. Tests
在 `tests/` 中编写 pytest 测试：

- **test_market_regime.py**：
  - 构造一组"全面看多"的 mock 数据 → 验证输出"进攻"
  - 构造一组"全面看空"的 mock 数据 → 验证输出"防守"
  - 构造一组"混合"数据 → 验证输出"平衡"
  - 分别测试 US/HK/A 三个市场

- **test_anomaly.py**：
  - 为每条 ANOMALY_RULE 构造触发数据，验证告警生成
  - 构造正常数据，验证无告警
  - 验证 RED 级别排在 YELLOW 前面

- **test_sector_flow.py**：
  - 构造全部进攻型板块领涨 → 验证输出"进攻型主导"
  - 构造全部防守型板块领涨 → 验证输出"防守型主导"
  - 构造 A 股 Top5 全是科技 → 验证输出"科技主线"

## requirements.txt (新增依赖)
```
yfinance>=0.2.30
tushare>=1.4.0
pyyaml>=6.0
requests>=2.31.0
openai>=1.0.0
python-telegram-bot>=20.0
```

## 关键实现原则
1. **永不崩溃**：每个数据源 fetch 都 try/except，失败字段设为 None，报告照常生成
2. **数据源隔离**：tushare 和 yfinance 的调用严格分离在各自函数中，方便未来替换
3. **评分可解释**：每个 regime 评分都要附带中文理由，用户要知道"为什么建议防守"
4. **时区正确**：美股用 US/Eastern，港股/A股用 Asia/Shanghai，报告日期用 Asia/Shanghai
5. **幂等执行**：同一天多次运行覆盖同一份报告
6. **Telegram 友好**：报告格式要在手机端可读，表格不要太宽

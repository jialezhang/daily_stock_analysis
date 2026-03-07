# -*- coding: utf-8 -*-
"""
===================================
趋势交易分析器 - 基于用户交易理念
===================================

交易理念核心原则：
1. 严进策略 - 不追高，追求每笔交易成功率
2. 趋势交易 - MA5>MA10>MA20 多头排列，顺势而为
3. 效率优先 - 关注筹码结构好的股票
4. 买点偏好 - 在 MA5/MA10 附近回踩买入

技术标准：
- 多头排列：MA5 > MA10 > MA20
- 乖离率：(Close - MA5) / MA5 < 5%（不追高）
- 量能形态：缩量回调优先
"""

import logging
from collections import defaultdict
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, Any, List, Tuple, Optional
from enum import Enum

import pandas as pd
import numpy as np

from src.config import get_config

logger = logging.getLogger(__name__)


@dataclass
class PatternRule:
    """Rule loaded from excel pattern sheets."""
    category: str  # "bottom" or "top"
    pattern_name: str
    indicators: List[str]
    definition: str = ""


class TrendStatus(Enum):
    """趋势状态枚举"""
    STRONG_BULL = "强势多头"      # MA5 > MA10 > MA20，且间距扩大
    BULL = "多头排列"             # MA5 > MA10 > MA20
    WEAK_BULL = "弱势多头"        # MA5 > MA10，但 MA10 < MA20
    CONSOLIDATION = "盘整"        # 均线缠绕
    WEAK_BEAR = "弱势空头"        # MA5 < MA10，但 MA10 > MA20
    BEAR = "空头排列"             # MA5 < MA10 < MA20
    STRONG_BEAR = "强势空头"      # MA5 < MA10 < MA20，且间距扩大


class VolumeStatus(Enum):
    """量能状态枚举"""
    HEAVY_VOLUME_UP = "放量上涨"       # 量价齐升
    HEAVY_VOLUME_DOWN = "放量下跌"     # 放量杀跌
    SHRINK_VOLUME_UP = "缩量上涨"      # 无量上涨
    SHRINK_VOLUME_DOWN = "缩量回调"    # 缩量回调（好）
    NORMAL = "量能正常"


class BuySignal(Enum):
    """买入信号枚举"""
    STRONG_BUY = "强烈买入"       # 多条件满足
    BUY = "买入"                  # 基本条件满足
    HOLD = "持有"                 # 已持有可继续
    WAIT = "观望"                 # 等待更好时机
    SELL = "卖出"                 # 趋势转弱
    STRONG_SELL = "强烈卖出"      # 趋势破坏


class MACDStatus(Enum):
    """MACD状态枚举"""
    GOLDEN_CROSS_ZERO = "零轴上金叉"      # DIF上穿DEA，且在零轴上方
    GOLDEN_CROSS = "金叉"                # DIF上穿DEA
    BULLISH = "多头"                    # DIF>DEA>0
    CROSSING_UP = "上穿零轴"             # DIF上穿零轴
    CROSSING_DOWN = "下穿零轴"           # DIF下穿零轴
    BEARISH = "空头"                    # DIF<DEA<0
    DEATH_CROSS = "死叉"                # DIF下穿DEA


class RSIStatus(Enum):
    """RSI状态枚举"""
    OVERBOUGHT = "超买"        # RSI > 70
    STRONG_BUY = "强势买入"    # 50 < RSI < 70
    NEUTRAL = "中性"          # 40 <= RSI <= 60
    WEAK = "弱势"             # 30 < RSI < 40
    OVERSOLD = "超卖"         # RSI < 30


@dataclass
class TrendAnalysisResult:
    """趋势分析结果"""
    code: str
    
    # 趋势判断
    trend_status: TrendStatus = TrendStatus.CONSOLIDATION
    ma_alignment: str = ""           # 均线排列描述
    trend_strength: float = 0.0      # 趋势强度 0-100
    
    # 均线数据
    ma5: float = 0.0
    ma10: float = 0.0
    ma20: float = 0.0
    ma60: float = 0.0
    current_price: float = 0.0
    
    # 乖离率（与 MA5 的偏离度）
    bias_ma5: float = 0.0            # (Close - MA5) / MA5 * 100
    bias_ma10: float = 0.0
    bias_ma20: float = 0.0
    
    # 量能分析
    volume_status: VolumeStatus = VolumeStatus.NORMAL
    volume_ratio_5d: float = 0.0     # 当日成交量/5日均量
    volume_trend: str = ""           # 量能趋势描述
    
    # 支撑压力
    support_ma5: bool = False        # MA5 是否构成支撑
    support_ma10: bool = False       # MA10 是否构成支撑
    resistance_levels: List[float] = field(default_factory=list)
    support_levels: List[float] = field(default_factory=list)

    # MACD 指标
    macd_dif: float = 0.0          # DIF 快线
    macd_dea: float = 0.0          # DEA 慢线
    macd_bar: float = 0.0           # MACD 柱状图
    macd_status: MACDStatus = MACDStatus.BULLISH
    macd_signal: str = ""            # MACD 信号描述

    # RSI 指标
    rsi_6: float = 0.0              # RSI(6) 短期
    rsi_12: float = 0.0             # RSI(12) 中期
    rsi_24: float = 0.0             # RSI(24) 长期
    rsi_status: RSIStatus = RSIStatus.NEUTRAL
    rsi_signal: str = ""              # RSI 信号描述

    # 买入信号
    buy_signal: BuySignal = BuySignal.WAIT
    signal_score: int = 0            # 综合评分 0-100
    signal_reasons: List[str] = field(default_factory=list)
    risk_factors: List[str] = field(default_factory=list)
    bottom_pattern_hits: List[str] = field(default_factory=list)
    top_pattern_hits: List[str] = field(default_factory=list)
    pattern_advice: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'code': self.code,
            'trend_status': self.trend_status.value,
            'ma_alignment': self.ma_alignment,
            'trend_strength': self.trend_strength,
            'ma5': self.ma5,
            'ma10': self.ma10,
            'ma20': self.ma20,
            'ma60': self.ma60,
            'current_price': self.current_price,
            'bias_ma5': self.bias_ma5,
            'bias_ma10': self.bias_ma10,
            'bias_ma20': self.bias_ma20,
            'volume_status': self.volume_status.value,
            'volume_ratio_5d': self.volume_ratio_5d,
            'volume_trend': self.volume_trend,
            'support_ma5': self.support_ma5,
            'support_ma10': self.support_ma10,
            'buy_signal': self.buy_signal.value,
            'signal_score': self.signal_score,
            'signal_reasons': self.signal_reasons,
            'risk_factors': self.risk_factors,
            'bottom_pattern_hits': self.bottom_pattern_hits,
            'top_pattern_hits': self.top_pattern_hits,
            'pattern_advice': self.pattern_advice,
            'macd_dif': self.macd_dif,
            'macd_dea': self.macd_dea,
            'macd_bar': self.macd_bar,
            'macd_status': self.macd_status.value,
            'macd_signal': self.macd_signal,
            'rsi_6': self.rsi_6,
            'rsi_12': self.rsi_12,
            'rsi_24': self.rsi_24,
            'rsi_status': self.rsi_status.value,
            'rsi_signal': self.rsi_signal,
        }


class StockTrendAnalyzer:
    """
    股票趋势分析器

    基于用户交易理念实现：
    1. 趋势判断 - MA5>MA10>MA20 多头排列
    2. 乖离率检测 - 不追高，偏离 MA5 超过 5% 不买
    3. 量能分析 - 偏好缩量回调
    4. 买点识别 - 回踩 MA5/MA10 支撑
    5. MACD 指标 - 趋势确认和金叉死叉信号
    6. RSI 指标 - 超买超卖判断
    """
    
    # 交易参数配置（BIAS_THRESHOLD 从 Config 读取，见 _generate_signal）
    VOLUME_SHRINK_RATIO = 0.7   # 缩量判断阈值（当日量/5日均量）
    VOLUME_HEAVY_RATIO = 1.5    # 放量判断阈值
    MA_SUPPORT_TOLERANCE = 0.02  # MA 支撑判断容忍度（2%）

    # MACD 参数（标准12/26/9）
    MACD_FAST = 12              # 快线周期
    MACD_SLOW = 26             # 慢线周期
    MACD_SIGNAL = 9             # 信号线周期

    # RSI 参数
    RSI_SHORT = 6               # 短期RSI周期
    RSI_MID = 12               # 中期RSI周期
    RSI_LONG = 24              # 长期RSI周期
    RSI_OVERBOUGHT = 70        # 超买阈值
    RSI_OVERSOLD = 30          # 超卖阈值
    PATTERN_EXCEL_NAME = "止跌见顶形态.xlsx"
    _PATTERN_RULES_CACHE: Dict[str, List[PatternRule]] = {}

    def __init__(self):
        """初始化分析器"""
        if not self.__class__._PATTERN_RULES_CACHE:
            self.__class__._PATTERN_RULES_CACHE = self._load_pattern_rules()
        self.pattern_rules = self.__class__._PATTERN_RULES_CACHE
    
    def analyze(self, df: pd.DataFrame, code: str) -> TrendAnalysisResult:
        """
        分析股票趋势
        
        Args:
            df: 包含 OHLCV 数据的 DataFrame
            code: 股票代码
            
        Returns:
            TrendAnalysisResult 分析结果
        """
        result = TrendAnalysisResult(code=code)
        
        if df is None or df.empty or len(df) < 20:
            logger.warning(f"{code} 数据不足，无法进行趋势分析")
            result.risk_factors.append("数据不足，无法完成分析")
            return result
        
        # 确保数据按日期排序
        df = df.sort_values('date').reset_index(drop=True)
        
        # 计算均线
        df = self._calculate_mas(df)

        # 计算 MACD 和 RSI
        df = self._calculate_macd(df)
        df = self._calculate_rsi(df)
        df = self._calculate_boll(df)
        df = self._calculate_cci(df)

        # 获取最新数据
        latest = df.iloc[-1]
        result.current_price = float(latest['close'])
        result.ma5 = float(latest['MA5'])
        result.ma10 = float(latest['MA10'])
        result.ma20 = float(latest['MA20'])
        result.ma60 = float(latest.get('MA60', 0))

        # 1. 趋势判断
        self._analyze_trend(df, result)

        # 2. 乖离率计算
        self._calculate_bias(result)

        # 3. 量能分析
        self._analyze_volume(df, result)

        # 4. 支撑压力分析
        self._analyze_support_resistance(df, result)

        # 5. MACD 分析
        self._analyze_macd(df, result)

        # 6. RSI 分析
        self._analyze_rsi(df, result)

        # 7. Excel 形态共振分析
        self._analyze_pattern_signals(df, result)

        # 8. 生成买入信号
        self._generate_signal(result)

        return result
    
    def _calculate_mas(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算均线"""
        df = df.copy()
        df['MA5'] = df['close'].rolling(window=5).mean()
        df['MA10'] = df['close'].rolling(window=10).mean()
        df['MA20'] = df['close'].rolling(window=20).mean()
        if len(df) >= 60:
            df['MA60'] = df['close'].rolling(window=60).mean()
        else:
            df['MA60'] = df['MA20']  # 数据不足时使用 MA20 替代
        return df

    def _calculate_macd(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        计算 MACD 指标

        公式：
        - EMA(12)：12日指数移动平均
        - EMA(26)：26日指数移动平均
        - DIF = EMA(12) - EMA(26)
        - DEA = EMA(DIF, 9)
        - MACD = (DIF - DEA) * 2
        """
        df = df.copy()

        # 计算快慢线 EMA
        ema_fast = df['close'].ewm(span=self.MACD_FAST, adjust=False).mean()
        ema_slow = df['close'].ewm(span=self.MACD_SLOW, adjust=False).mean()

        # 计算快线 DIF
        df['MACD_DIF'] = ema_fast - ema_slow

        # 计算信号线 DEA
        df['MACD_DEA'] = df['MACD_DIF'].ewm(span=self.MACD_SIGNAL, adjust=False).mean()

        # 计算柱状图
        df['MACD_BAR'] = (df['MACD_DIF'] - df['MACD_DEA']) * 2

        return df

    def _calculate_rsi(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        计算 RSI 指标

        公式：
        - RS = 平均上涨幅度 / 平均下跌幅度
        - RSI = 100 - (100 / (1 + RS))
        """
        df = df.copy()

        for period in [self.RSI_SHORT, self.RSI_MID, self.RSI_LONG]:
            # 计算价格变化
            delta = df['close'].diff()

            # 分离上涨和下跌
            gain = delta.where(delta > 0, 0)
            loss = -delta.where(delta < 0, 0)

            # 计算平均涨跌幅
            avg_gain = gain.rolling(window=period).mean()
            avg_loss = loss.rolling(window=period).mean()

            # 计算 RS 和 RSI
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))

            # 填充 NaN 值
            rsi = rsi.fillna(50)  # 默认中性值

            # 添加到 DataFrame
            col_name = f'RSI_{period}'
            df[col_name] = rsi

        return df

    def _calculate_boll(self, df: pd.DataFrame, period: int = 20, std_multiplier: float = 2.0) -> pd.DataFrame:
        """Calculate Bollinger Bands used by pattern resonance checks."""
        df = df.copy()
        mid = df['close'].rolling(window=period).mean()
        std = df['close'].rolling(window=period).std(ddof=0)
        df['BOLL_MID'] = mid
        df['BOLL_UPPER'] = mid + std_multiplier * std
        df['BOLL_LOWER'] = mid - std_multiplier * std
        return df

    def _calculate_cci(self, df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
        """Calculate CCI indicator for pattern resonance checks."""
        df = df.copy()
        typical_price = (df['high'] + df['low'] + df['close']) / 3
        sma = typical_price.rolling(window=period).mean()
        mean_deviation = (typical_price - sma).abs().rolling(window=period).mean()
        denominator = (0.015 * mean_deviation).replace(0, np.nan)
        cci = (typical_price - sma) / denominator
        df['CCI_14'] = cci.fillna(0)
        return df

    def _calculate_kdj(self, df: pd.DataFrame, period: int = 9) -> pd.DataFrame:
        """Calculate KDJ indicator (K, D, J) using RSV smoothing."""
        df = df.copy()
        low_n = df["low"].rolling(window=period, min_periods=1).min()
        high_n = df["high"].rolling(window=period, min_periods=1).max()
        denominator = (high_n - low_n).replace(0, np.nan)
        rsv = ((df["close"] - low_n) / denominator * 100).fillna(50)
        k = rsv.ewm(alpha=1 / 3, adjust=False).mean()
        d = k.ewm(alpha=1 / 3, adjust=False).mean()
        j = 3 * k - 2 * d
        df["KDJ_K"] = k.fillna(50)
        df["KDJ_D"] = d.fillna(50)
        df["KDJ_J"] = j.fillna(50)
        return df

    def _calculate_bias_series(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate BIAS(6/12/24) series."""
        df = df.copy()
        for period in [6, 12, 24]:
            ma = df["close"].rolling(window=period).mean()
            denom = ma.replace(0, np.nan)
            df[f"BIAS_{period}"] = ((df["close"] - ma) / denom * 100).fillna(0)
        return df

    def _calculate_kc(self, df: pd.DataFrame, period: int = 20, atr_period: int = 10, multiplier: float = 2.0) -> pd.DataFrame:
        """Calculate Keltner Channel (KC)."""
        df = df.copy()
        mid = df["close"].ewm(span=period, adjust=False).mean()
        prev_close = df["close"].shift(1)
        tr = pd.concat(
            [
                (df["high"] - df["low"]).abs(),
                (df["high"] - prev_close).abs(),
                (df["low"] - prev_close).abs(),
            ],
            axis=1,
        ).max(axis=1)
        atr = tr.rolling(window=atr_period, min_periods=1).mean()
        df["KC_MID"] = mid
        df["KC_UPPER"] = mid + multiplier * atr
        df["KC_LOWER"] = mid - multiplier * atr
        return df

    def _calculate_bbiboll(self, df: pd.DataFrame, std_period: int = 11, std_multiplier: float = 3.0) -> pd.DataFrame:
        """Calculate BBIBOLL using BBI baseline and close std."""
        df = df.copy()
        ma3 = df["close"].rolling(window=3).mean()
        ma6 = df["close"].rolling(window=6).mean()
        ma12 = df["close"].rolling(window=12).mean()
        ma24 = df["close"].rolling(window=24).mean()
        bbi = (ma3 + ma6 + ma12 + ma24) / 4
        std = df["close"].rolling(window=std_period).std(ddof=0).fillna(0)
        df["BBIBOLL_BBI"] = bbi
        df["BBIBOLL_UPPER"] = bbi + std_multiplier * std
        df["BBIBOLL_LOWER"] = bbi - std_multiplier * std
        return df

    def _calculate_sar(self, df: pd.DataFrame, af_step: float = 0.02, af_max: float = 0.2) -> pd.DataFrame:
        """Calculate Parabolic SAR and trend direction."""
        df = df.copy()
        if df.empty:
            df["SAR"] = []
            df["SAR_TREND"] = []
            return df

        highs = df["high"].astype(float).values
        lows = df["low"].astype(float).values
        closes = df["close"].astype(float).values
        n = len(df)

        sar = np.zeros(n, dtype=float)
        trend = np.ones(n, dtype=int)

        up_trend = True if n == 1 else closes[1] >= closes[0]
        sar[0] = lows[0] if up_trend else highs[0]
        ep = highs[0] if up_trend else lows[0]
        af = af_step
        trend[0] = 1 if up_trend else -1

        for i in range(1, n):
            prev_sar = sar[i - 1]
            if up_trend:
                sar_i = prev_sar + af * (ep - prev_sar)
                sar_i = min(sar_i, lows[i - 1], lows[i - 2] if i > 1 else lows[i - 1])
                if lows[i] < sar_i:
                    up_trend = False
                    sar_i = ep
                    ep = lows[i]
                    af = af_step
                else:
                    if highs[i] > ep:
                        ep = highs[i]
                        af = min(af + af_step, af_max)
            else:
                sar_i = prev_sar + af * (ep - prev_sar)
                sar_i = max(sar_i, highs[i - 1], highs[i - 2] if i > 1 else highs[i - 1])
                if highs[i] > sar_i:
                    up_trend = True
                    sar_i = ep
                    ep = highs[i]
                    af = af_step
                else:
                    if lows[i] < ep:
                        ep = lows[i]
                        af = min(af + af_step, af_max)

            sar[i] = sar_i
            trend[i] = 1 if up_trend else -1

        df["SAR"] = sar
        df["SAR_TREND"] = trend
        return df

    def _calculate_magic_nine_turn(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate TD9-style setup counts (buy/sell)."""
        df = df.copy()
        close = df["close"].astype(float).values
        n = len(close)
        buy_setup = np.zeros(n, dtype=int)
        sell_setup = np.zeros(n, dtype=int)

        for i in range(4, n):
            if close[i] < close[i - 4]:
                buy_setup[i] = buy_setup[i - 1] + 1
            else:
                buy_setup[i] = 0

            if close[i] > close[i - 4]:
                sell_setup[i] = sell_setup[i - 1] + 1
            else:
                sell_setup[i] = 0

        df["TD9_BUY_SETUP"] = buy_setup
        df["TD9_SELL_SETUP"] = sell_setup
        return df

    @classmethod
    def _default_pattern_rules(cls) -> Dict[str, List[PatternRule]]:
        """Fallback rules if excel parsing fails."""
        return {
            "bottom": [
                PatternRule("bottom", "启明星", ["成交量", "RSI", "MACD"]),
                PatternRule("bottom", "看涨吞没", ["成交量", "CCI", "Boll"]),
                PatternRule("bottom", "锤子线", ["支撑位", "Boll", "RSI"]),
                PatternRule("bottom", "倒锤子线", ["成交量", "MACD"]),
                PatternRule("bottom", "看涨孕线", ["Boll缩口", "RSI"]),
            ],
            "top": [
                PatternRule("top", "黄昏之星", ["成交量", "RSI", "MACD"]),
                PatternRule("top", "看跌吞没", ["成交量", "CCI", "Boll"]),
                PatternRule("top", "流星线(射击之星)", ["阻力位", "Boll", "MACD"]),
                PatternRule("top", "上吊线", ["成交量", "RSI"]),
                PatternRule("top", "看跌孕线", ["Boll缩口", "CCI"]),
            ],
        }

    @staticmethod
    def _parse_indicator_combo(combo: str) -> List[str]:
        """Normalize indicator combo text from excel."""
        if not combo:
            return []
        parts = [p.strip() for p in combo.replace("＋", "+").split("+") if p.strip()]
        normalized = []
        for part in parts:
            token = part.replace(" ", "")
            if "Boll缩口" in token:
                normalized.append("Boll缩口")
            elif token.startswith("Boll"):
                normalized.append("Boll")
            elif "RSI" in token:
                normalized.append("RSI")
            elif "MACD" in token:
                normalized.append("MACD")
            elif "CCI" in token:
                normalized.append("CCI")
            elif "支撑位" in token:
                normalized.append("支撑位")
            elif "阻力位" in token:
                normalized.append("阻力位")
            elif "成交量" in token:
                normalized.append("成交量")
        return normalized

    def _load_pattern_rules(self) -> Dict[str, List[PatternRule]]:
        """Load stop-fall/top pattern rules from excel file."""
        rules: Dict[str, List[PatternRule]] = {"bottom": [], "top": []}
        excel_path = Path(__file__).resolve().parents[1] / self.PATTERN_EXCEL_NAME
        if not excel_path.exists():
            logger.warning(f"Pattern excel not found: {excel_path}, using fallback rules")
            return self._default_pattern_rules()

        try:
            sheets = pd.read_excel(excel_path, sheet_name=None)
            for sheet_name, sheet_df in sheets.items():
                if "止跌" in sheet_name:
                    category = "bottom"
                elif "见顶" in sheet_name:
                    category = "top"
                else:
                    continue

                for _, row in sheet_df.iterrows():
                    pattern_name = str(row.get("K线形态", "")).strip()
                    combo = str(row.get("核心共振指标组合", "")).strip()
                    definition = str(row.get("强信号（高胜率）定义", "")).strip()
                    if not pattern_name:
                        continue
                    rules[category].append(
                        PatternRule(
                            category=category,
                            pattern_name=pattern_name,
                            indicators=self._parse_indicator_combo(combo),
                            definition=definition,
                        )
                    )
        except Exception as exc:
            logger.warning(f"Failed to load pattern rules from excel: {exc}; fallback will be used")
            return self._default_pattern_rules()

        if not rules["bottom"] and not rules["top"]:
            logger.warning("No pattern rules parsed from excel; fallback will be used")
            return self._default_pattern_rules()
        return rules

    @staticmethod
    def _candle_components(candle: pd.Series) -> Dict[str, float]:
        """Split candle into body/range/shadows."""
        open_p = float(candle['open'])
        close_p = float(candle['close'])
        high_p = float(candle['high'])
        low_p = float(candle['low'])
        body = abs(close_p - open_p)
        full_range = max(high_p - low_p, 1e-6)
        upper_shadow = high_p - max(open_p, close_p)
        lower_shadow = min(open_p, close_p) - low_p
        return {
            "open": open_p,
            "close": close_p,
            "high": high_p,
            "low": low_p,
            "body": body,
            "range": full_range,
            "upper": max(0.0, upper_shadow),
            "lower": max(0.0, lower_shadow),
        }

    @staticmethod
    def _is_uptrend(df: pd.DataFrame, lookback: int = 6) -> bool:
        """Check simple uptrend before current candle."""
        if len(df) < lookback + 1:
            return False
        return float(df['close'].iloc[-2]) > float(df['close'].iloc[-1 - lookback])

    @staticmethod
    def _is_downtrend(df: pd.DataFrame, lookback: int = 6) -> bool:
        """Check simple downtrend before current candle."""
        if len(df) < lookback + 1:
            return False
        return float(df['close'].iloc[-2]) < float(df['close'].iloc[-1 - lookback])

    def _match_candlestick_pattern(self, df: pd.DataFrame, pattern_name: str) -> bool:
        """Match target candlestick pattern on most recent candles."""
        if len(df) < 3:
            return False

        name = pattern_name.replace(" ", "")
        c = self._candle_components(df.iloc[-1])
        p = self._candle_components(df.iloc[-2])
        p2 = self._candle_components(df.iloc[-3])

        if "启明星" in name:
            first_bear = p2["close"] < p2["open"] and p2["body"] / p2["range"] > 0.45
            second_small = p["body"] / p["range"] < 0.35
            third_bull = c["close"] > c["open"] and c["close"] > (p2["open"] + p2["close"]) / 2
            return first_bear and second_small and third_bull

        if "黄昏之星" in name:
            first_bull = p2["close"] > p2["open"] and p2["body"] / p2["range"] > 0.45
            second_small = p["body"] / p["range"] < 0.35
            third_bear = c["close"] < c["open"] and c["close"] < (p2["open"] + p2["close"]) / 2
            return first_bull and second_small and third_bear

        if "看涨吞没" in name:
            return (
                p["close"] < p["open"]
                and c["close"] > c["open"]
                and c["open"] <= p["close"]
                and c["close"] >= p["open"]
            )

        if "看跌吞没" in name:
            return (
                p["close"] > p["open"]
                and c["close"] < c["open"]
                and c["open"] >= p["close"]
                and c["close"] <= p["open"]
            )

        if "看涨孕线" in name:
            return (
                p["close"] < p["open"]
                and c["close"] > c["open"]
                and c["open"] >= p["close"]
                and c["close"] <= p["open"]
                and c["body"] <= p["body"] * 0.7
            )

        if "看跌孕线" in name:
            return (
                p["close"] > p["open"]
                and c["close"] < c["open"]
                and c["open"] <= p["close"]
                and c["close"] >= p["open"]
                and c["body"] <= p["body"] * 0.7
            )

        if "锤子线" in name and "倒锤子线" not in name:
            return c["lower"] >= c["body"] * 2 and c["upper"] <= c["body"] * 0.6 and self._is_downtrend(df)

        if "倒锤子线" in name:
            return c["upper"] >= c["body"] * 2 and c["lower"] <= c["body"] * 0.6 and self._is_downtrend(df)

        if "流星线" in name or "射击之星" in name:
            return c["upper"] >= c["body"] * 2 and c["lower"] <= c["body"] * 0.5 and self._is_uptrend(df)

        if "上吊线" in name:
            return c["lower"] >= c["body"] * 2 and c["upper"] <= c["body"] * 0.6 and self._is_uptrend(df)

        return False

    def _indicator_resonance(self, df: pd.DataFrame, result: TrendAnalysisResult, rule: PatternRule) -> bool:
        """Validate indicator combinations from excel rule."""
        if not rule.indicators or len(df) < 2:
            return True

        latest = df.iloc[-1]
        prev = df.iloc[-2]
        curr_macd_gap = float(latest.get('MACD_DIF', 0) - latest.get('MACD_DEA', 0))
        prev_macd_gap = float(prev.get('MACD_DIF', 0) - prev.get('MACD_DEA', 0))
        curr_rsi = float(latest.get(f'RSI_{self.RSI_MID}', 50))
        prev_rsi = float(prev.get(f'RSI_{self.RSI_MID}', curr_rsi))
        curr_cci = float(latest.get('CCI_14', 0))
        prev_cci = float(prev.get('CCI_14', curr_cci))
        boll_mid = float(latest.get('BOLL_MID', 0) or 0)
        boll_upper = float(latest.get('BOLL_UPPER', 0) or 0)
        boll_lower = float(latest.get('BOLL_LOWER', 0) or 0)
        boll_bandwidth = (boll_upper - boll_lower) / boll_mid if boll_mid > 0 else 0

        checks: Dict[str, bool] = {
            "成交量": result.volume_ratio_5d >= (1.1 if rule.category == "bottom" else 1.2),
            "RSI": (
                (curr_rsi <= 35 and curr_rsi >= prev_rsi) or (prev_rsi < 30 <= curr_rsi)
                if rule.category == "bottom"
                else (curr_rsi >= 65 and curr_rsi <= prev_rsi) or (prev_rsi > 70 >= curr_rsi)
            ),
            "MACD": (
                curr_macd_gap >= prev_macd_gap and (curr_macd_gap > 0 or result.macd_bar >= float(prev.get('MACD_BAR', 0)))
                if rule.category == "bottom"
                else curr_macd_gap <= prev_macd_gap and (curr_macd_gap < 0 or result.macd_bar <= float(prev.get('MACD_BAR', 0)))
            ),
            "CCI": (
                prev_cci <= -100 < curr_cci
                if rule.category == "bottom"
                else prev_cci >= 100 > curr_cci
            ),
            "Boll": (
                float(latest['low']) <= boll_lower * 1.01 and float(latest['close']) >= boll_lower
                if rule.category == "bottom"
                else float(latest['high']) >= boll_upper * 0.99 and float(latest['close']) <= boll_upper
            ) if boll_upper > 0 and boll_lower > 0 else False,
            "Boll缩口": 0 < boll_bandwidth <= 0.12,
            "支撑位": result.support_ma5 or result.support_ma10,
            "阻力位": (
                bool(result.resistance_levels)
                and float(latest['high']) >= min(result.resistance_levels) * 0.99
                and result.current_price <= min(result.resistance_levels)
            ),
        }
        return all(checks.get(indicator, True) for indicator in rule.indicators)

    def _analyze_pattern_signals(self, df: pd.DataFrame, result: TrendAnalysisResult) -> None:
        """Detect excel-defined bottom/top pattern combinations."""
        bottom_hits: List[str] = []
        top_hits: List[str] = []

        for rule in self.pattern_rules.get("bottom", []):
            if self._match_candlestick_pattern(df, rule.pattern_name) and self._indicator_resonance(df, result, rule):
                bottom_hits.append(f"{rule.pattern_name}({'+'.join(rule.indicators)})")

        for rule in self.pattern_rules.get("top", []):
            if self._match_candlestick_pattern(df, rule.pattern_name) and self._indicator_resonance(df, result, rule):
                top_hits.append(f"{rule.pattern_name}({'+'.join(rule.indicators)})")

        result.bottom_pattern_hits = bottom_hits
        result.top_pattern_hits = top_hits

        if top_hits and bottom_hits:
            result.pattern_advice = "止跌与见顶信号同时出现，优先控制风险，等待确认"
        elif top_hits:
            result.pattern_advice = "命中见顶形态组合，建议卖出或减仓"
        elif bottom_hits:
            result.pattern_advice = "命中止跌形态组合，建议分批买入"

    @staticmethod
    def _pick_strong_weak_levels(levels: List[float], current_price: float, is_support: bool) -> Tuple[float, float]:
        """Pick nearest (strong) and secondary (weak) level around current price."""
        if not levels:
            return 0.0, 0.0

        unique = sorted({float(x) for x in levels if x and x > 0})
        if not unique:
            return 0.0, 0.0

        if is_support:
            candidates = [x for x in unique if x <= current_price]
            if not candidates:
                return unique[0], unique[1] if len(unique) > 1 else unique[0]
            strong = candidates[-1]
            weak = candidates[-2] if len(candidates) >= 2 else strong
            return strong, weak

        candidates = [x for x in unique if x >= current_price]
        if not candidates:
            return unique[-1], unique[-2] if len(unique) > 1 else unique[-1]
        strong = candidates[0]
        weak = candidates[1] if len(candidates) >= 2 else strong
        return strong, weak

    @staticmethod
    def _cluster_price_levels(levels: List[float], merge_ratio: float = 0.02) -> List[List[float]]:
        """Cluster nearby price levels into ranges."""
        unique = sorted({float(x) for x in levels if x and x > 0})
        if not unique:
            return []

        clusters: List[List[float]] = [[unique[0]]]
        for level in unique[1:]:
            anchor = float(np.mean(clusters[-1]))
            ratio = abs(level - anchor) / max(anchor, 1e-9)
            if ratio <= merge_ratio:
                clusters[-1].append(level)
            else:
                clusters.append([level])
        return clusters

    def _build_multi_boxes(
        self,
        current_price: float,
        support_candidates: List[Dict[str, Any]],
        resistance_candidates: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Build multiple support/resistance boxes from clustered key levels."""
        all_candidates = support_candidates + resistance_candidates
        level_values = [float(item.get("value", 0.0) or 0.0) for item in all_candidates]
        clusters = self._cluster_price_levels(level_values, merge_ratio=0.02)
        if not clusters:
            return []

        value_origins: Dict[float, set] = defaultdict(set)
        value_roles: Dict[float, set] = defaultdict(set)
        for item in all_candidates:
            value = float(item.get("value", 0.0) or 0.0)
            if value <= 0:
                continue
            key = round(value, 6)
            value_origins[key].add(str(item.get("origin", "未知来源")))
            value_roles[key].add(str(item.get("role", "candidate")))

        raw_boxes: List[Dict[str, Any]] = []
        for cluster in clusters:
            center = float(np.mean(cluster))
            low = float(min(cluster))
            high = float(max(cluster))
            padding = max(center * 0.006, (high - low) * 0.6, 0.01)
            zone_low = max(0.0, low - padding)
            zone_high = high + padding
            side = "support" if center <= current_price else "resistance"
            distance_pct = abs(center - current_price) / current_price * 100 if current_price > 0 else 0.0
            range_value = max(zone_high - zone_low, 1e-9)
            range_pct = range_value / max(center, 1e-9) * 100
            strength_score = int(
                max(
                    25,
                    min(
                        100,
                        round(
                            35 + len(cluster) * 12 + max(0.0, 24 - distance_pct * 1.5) + min(16.0, range_pct * 0.8)
                        ),
                    ),
                )
            )
            key_levels: List[Dict[str, Any]] = []
            key_level_texts: List[str] = []
            for level in sorted(cluster):
                key = round(float(level), 6)
                origins = sorted(value_origins.get(key, {"未知来源"}))
                roles = sorted(value_roles.get(key, {"candidate"}))
                key_levels.append(
                    {
                        "price": round(float(level), 3),
                        "origins": origins,
                        "roles": roles,
                    }
                )
                key_level_texts.append(f"{round(float(level), 3)}({'+'.join(origins)})")

            padding_low = round(float(zone_low), 3)
            padding_high = round(float(zone_high), 3)
            logic = (
                f"由{len(cluster)}个关键价位聚类形成，区间宽度约{range_pct:.2f}%，"
                f"位于现价{'下方' if side == 'support' else '上方'}{distance_pct:.2f}%，"
                f"判定为{'支撑' if side == 'support' else '阻力'}区。"
            )
            logic_detail = (
                f"关键价位: {'、'.join(key_level_texts)}。"
                f"聚类规则: 相对均值距离<=2.00% 归为同一簇。"
                f"区间构造: 原始簇[{low:.3f}, {high:.3f}]，padding=max(中心价*0.6%, 原始跨度*60%)={padding:.3f}，"
                f"扩展后区间[{padding_low:.3f}, {padding_high:.3f}]。"
                f"位置判断: 中心价{center:.3f}较现价{current_price:.3f}"
                f"{'低' if side == 'support' else '高'}{distance_pct:.2f}%，定性为{'支撑' if side == 'support' else '阻力'}区。"
            )
            raw_boxes.append(
                {
                    "side": side,
                    "center": round(center, 3),
                    "low": round(zone_low, 3),
                    "high": round(zone_high, 3),
                    "distance_pct": round(distance_pct, 2),
                    "range": round(range_value, 3),
                    "range_pct": round(range_pct, 2),
                    "strength_score": strength_score,
                    "source_count": int(len(cluster)),
                    "logic": logic,
                    "logic_detail": logic_detail,
                    "key_levels": key_levels,
                }
            )

        support_boxes = sorted(
            [b for b in raw_boxes if b["side"] == "support"], key=lambda item: item["distance_pct"]
        )[:4]
        resistance_boxes = sorted(
            [b for b in raw_boxes if b["side"] == "resistance"], key=lambda item: item["distance_pct"]
        )[:4]

        result: List[Dict[str, Any]] = []
        for idx, box in enumerate(support_boxes, start=1):
            item = dict(box)
            item["name"] = f"支撑箱体{idx}"
            result.append(item)
        for idx, box in enumerate(resistance_boxes, start=1):
            item = dict(box)
            item["name"] = f"阻力箱体{idx}"
            result.append(item)
        return result

    @staticmethod
    def _score_rsi(rsi_value: float) -> Tuple[int, str]:
        """Score RSI into a normalized 0-100 scale."""
        if rsi_value <= 30:
            return 85, "超卖反弹区"
        if rsi_value <= 45:
            return 72, "偏弱修复区"
        if rsi_value <= 65:
            return 78, "中性偏强"
        if rsi_value <= 80:
            return 45, "偏热区"
        return 20, "过热风险区"

    @staticmethod
    def _score_asr(asr_value: float) -> Tuple[int, str]:
        """Score ASR (average swing range %) into 0-100."""
        if asr_value < 1:
            return 38, "波动过低"
        if asr_value < 2:
            return 62, "低波动"
        if asr_value <= 5:
            return 84, "波动适中"
        if asr_value <= 8:
            return 66, "偏高波动"
        return 42, "高波动风险"

    @staticmethod
    def _score_cc(cc_value: float) -> Tuple[int, str]:
        """Score CC indicator using CCI(14) as proxy."""
        if cc_value < -100:
            return 80, "超卖修复"
        if cc_value <= 100:
            return 72, "中性区"
        return 36, "超买回落风险"

    @staticmethod
    def _clamp_score(score: float) -> int:
        """Clamp indicator score into [0, 100]."""
        return int(max(0, min(100, round(score))))

    @staticmethod
    def _rhino_strength_level(strength_score: int) -> str:
        """Convert numeric strength score into Rhino level text."""
        score = int(max(0, min(100, strength_score)))
        if score >= 86:
            return "超强"
        if score >= 71:
            return "强"
        if score >= 51:
            return "中"
        return "弱"

    def _build_extended_indicator_items(self, tail: pd.DataFrame) -> Dict[str, Any]:
        """Build scored indicator entries with explanations and recent interpretation."""
        latest = tail.iloc[-1]
        prev = tail.iloc[-2] if len(tail) >= 2 else latest
        close = float(latest["close"])

        asr_series = ((tail["high"] - tail["low"]) / tail["close"].replace(0, np.nan) * 100).dropna()
        asr_value = float(asr_series.iloc[-14:].mean()) if len(asr_series) > 0 else 0.0
        rsi_value = float(latest.get(f"RSI_{self.RSI_MID}", 50))
        cc_value = float(latest.get("CCI_14", 0))
        rsi_score, rsi_tag = self._score_rsi(rsi_value)
        asr_score, asr_tag = self._score_asr(asr_value)
        cc_score, cc_tag = self._score_cc(cc_value)

        rsi_result = (
            f"RSI12={rsi_value:.2f}，处于{rsi_tag}。"
            f"{'短线可关注低吸' if rsi_value < 40 else '短线偏强可持有观察' if rsi_value <= 70 else '短线偏热，谨慎追高'}。"
        )
        asr_result = (
            f"近14日平均振幅 ASR={asr_value:.2f}%（{asr_tag}）。"
            f"{'波动过小，突破确认前先观望' if asr_value < 2 else '波动结构健康，可配合趋势交易' if asr_value <= 5 else '波动放大，仓位与止损需更严格'}。"
        )
        cc_result = (
            f"CC(CCI14)={cc_value:.2f}，当前{cc_tag}。"
            f"{'偏向修复反弹' if cc_value < -100 else '尚未出现极端信号，等待方向确认' if cc_value <= 100 else '存在回落压力，宜控仓'}。"
        )

        # MACD
        macd_dif = float(latest.get("MACD_DIF", 0))
        macd_dea = float(latest.get("MACD_DEA", 0))
        macd_bar = float(latest.get("MACD_BAR", 0))
        prev_dif = float(prev.get("MACD_DIF", macd_dif))
        prev_dea = float(prev.get("MACD_DEA", macd_dea))
        prev_bar = float(prev.get("MACD_BAR", macd_bar))
        golden_cross = prev_dif <= prev_dea and macd_dif > macd_dea
        death_cross = prev_dif >= prev_dea and macd_dif < macd_dea
        bar_expand = abs(macd_bar) > abs(prev_bar)
        if golden_cross and macd_dif > 0:
            macd_score = 86
            macd_result = "MACD 零轴上金叉，且红柱放大，趋势延续概率较高，偏买入。"
        elif golden_cross:
            macd_score = 76
            macd_result = "MACD 金叉出现，但仍在零轴附近，适合小仓位试探。"
        elif death_cross:
            macd_score = 28
            macd_result = "MACD 死叉出现，短线回调风险上升，偏减仓/观望。"
        elif macd_dif > macd_dea:
            macd_score = 68 if bar_expand else 62
            macd_result = "MACD 位于多头区，动能尚可，回踩不破可继续持有。"
        else:
            macd_score = 42 if bar_expand else 48
            macd_result = "MACD 位于空头区，尚未企稳，等待金叉或站回零轴再考虑买入。"

        # KDJ
        k_val = float(latest.get("KDJ_K", 50))
        d_val = float(latest.get("KDJ_D", 50))
        j_val = float(latest.get("KDJ_J", 50))
        prev_k = float(prev.get("KDJ_K", k_val))
        prev_d = float(prev.get("KDJ_D", d_val))
        kdj_golden = prev_k <= prev_d and k_val > d_val
        kdj_death = prev_k >= prev_d and k_val < d_val
        if kdj_golden and k_val < 80:
            kdj_score = 78
            kdj_result = "KDJ 金叉出现且未超买，短线动能改善，偏买入。"
        elif kdj_death and k_val > 20:
            kdj_score = 34
            kdj_result = "KDJ 死叉出现，短线转弱，偏减仓或观望。"
        elif j_val < 10:
            kdj_score = 72
            kdj_result = "KDJ 处于极低位，存在超跌反弹窗口，可关注企稳低吸。"
        elif j_val > 100:
            kdj_score = 30
            kdj_result = "KDJ 高位钝化，短线过热，谨慎追高。"
        else:
            kdj_score = 58
            kdj_result = "KDJ 中性震荡，方向尚未明朗，等待进一步确认。"

        # BIAS
        bias6 = float(latest.get("BIAS_6", 0))
        bias12 = float(latest.get("BIAS_12", 0))
        bias24 = float(latest.get("BIAS_24", 0))
        bias_mean = (bias6 + bias12 + bias24) / 3
        if bias_mean <= -6:
            bias_score = 76
            bias_result = "BIAS 三线偏离较大（负向），短线有修复需求，可关注反弹。"
        elif bias_mean >= 6:
            bias_score = 32
            bias_result = "BIAS 三线偏离较大（正向），追高风险上升，偏减仓。"
        elif abs(bias_mean) <= 2:
            bias_score = 70
            bias_result = "BIAS 处于温和区间，价格未显著偏离均值，适合等待趋势确认。"
        elif bias_mean > 0:
            bias_score = 60
            bias_result = "BIAS 略偏正，趋势尚可但不宜重仓追涨。"
        else:
            bias_score = 56
            bias_result = "BIAS 略偏负，短线承压，需观察支撑是否有效。"

        # SAR
        sar_val = float(latest.get("SAR", close))
        prev_sar = float(prev.get("SAR", sar_val))
        sar_up = close >= sar_val
        sar_flip_up = float(prev["close"]) < prev_sar and close >= sar_val
        sar_flip_down = float(prev["close"]) > prev_sar and close <= sar_val
        if sar_flip_up:
            sar_score = 79
            sar_result = "SAR 刚由下转上，趋势反转信号出现，短线偏买入。"
        elif sar_flip_down:
            sar_score = 30
            sar_result = "SAR 刚由上转下，趋势转弱，短线偏卖出或观望。"
        elif sar_up:
            sar_score = 66
            sar_result = "价格位于 SAR 上方，趋势仍偏多，可持有并跟踪止损。"
        else:
            sar_score = 42
            sar_result = "价格位于 SAR 下方，趋势偏空，等待重新站上再参与。"

        # KC
        kc_upper = float(latest.get("KC_UPPER", close))
        kc_mid = float(latest.get("KC_MID", close))
        kc_lower = float(latest.get("KC_LOWER", close))
        kc_width = max(kc_upper - kc_lower, 1e-9)
        kc_pos = (close - kc_lower) / kc_width
        if kc_pos < 0.15:
            kc_score = 72
            kc_result = "价格接近 KC 下轨，若出现止跌信号可尝试低吸。"
        elif kc_pos > 0.85:
            kc_score = 38
            kc_result = "价格接近 KC 上轨，短线易震荡回吐，不宜追高。"
        elif close >= kc_mid:
            kc_score = 64
            kc_result = "价格运行于 KC 中轴上方，通道趋势偏强。"
        else:
            kc_score = 52
            kc_result = "价格位于 KC 中轴下方，通道趋势偏弱，建议观望。"

        # BBIBOLL
        bbi = float(latest.get("BBIBOLL_BBI", close))
        bb_up = float(latest.get("BBIBOLL_UPPER", bbi))
        bb_low = float(latest.get("BBIBOLL_LOWER", bbi))
        bb_width = max(bb_up - bb_low, 1e-9)
        bb_pos = (close - bb_low) / bb_width
        if bb_pos < 0.2:
            bb_score = 70
            bb_result = "价格靠近 BBIBOLL 下沿，关注止跌后回归中枢机会。"
        elif bb_pos > 0.85:
            bb_score = 36
            bb_result = "价格接近 BBIBOLL 上沿，短线过热，注意回撤风险。"
        elif close >= bbi:
            bb_score = 65
            bb_result = "价格站在 BBI 之上，趋势偏多，可持有观察。"
        else:
            bb_score = 50
            bb_result = "价格位于 BBI 下方，趋势偏弱，等待重新走强。"

        # Magic Nine Turn (TD9-style setup)
        buy_count = int(latest.get("TD9_BUY_SETUP", 0))
        sell_count = int(latest.get("TD9_SELL_SETUP", 0))
        if buy_count >= 9:
            td_score = 86
            td_result = f"买入九转已到 {buy_count}，衰竭反转概率提升，可分批试多。"
        elif sell_count >= 9:
            td_score = 18
            td_result = f"卖出九转已到 {sell_count}，短线见顶风险高，偏减仓。"
        elif buy_count >= 6:
            td_score = 68
            td_result = f"买入九转进行到 {buy_count}，接近潜在止跌区，关注确认信号。"
        elif sell_count >= 6:
            td_score = 42
            td_result = f"卖出九转进行到 {sell_count}，上涨动能可能衰竭，谨慎追涨。"
        else:
            td_score = 56
            td_result = "九转计数未到关键阶段，短线信号中性，结合其他指标判断。"

        indicator_items: Dict[str, Any] = {
            "rsi": {
                "value": round(rsi_value, 2),
                "score": int(rsi_score),
                "result": rsi_result,
                "explanation": "Relative Strength Index, measures momentum strength in 0-100 range.",
            },
            "asr": {
                "value": round(asr_value, 2),
                "score": int(asr_score),
                "result": asr_result,
                "explanation": "Average Swing Range, average high-low amplitude in percentage.",
            },
            "cc": {
                "value": round(cc_value, 2),
                "score": int(cc_score),
                "result": cc_result,
                "definition": "CCI(14) proxy",
                "explanation": "CC uses CCI(14) proxy to evaluate deviation from mean price.",
            },
            "sar": {
                "value": round(sar_val, 3),
                "score": int(self._clamp_score(sar_score)),
                "result": sar_result,
                "explanation": "Parabolic SAR tracks trailing stop and trend reversals.",
            },
            "macd": {
                "value": {"dif": round(macd_dif, 4), "dea": round(macd_dea, 4), "bar": round(macd_bar, 4)},
                "score": int(self._clamp_score(macd_score)),
                "result": macd_result,
                "explanation": "MACD compares short/long EMA momentum and crossover direction.",
            },
            "kdj": {
                "value": {"k": round(k_val, 2), "d": round(d_val, 2), "j": round(j_val, 2)},
                "score": int(self._clamp_score(kdj_score)),
                "result": kdj_result,
                "explanation": "KDJ is stochastic oscillator for short-term turning points.",
            },
            "bias": {
                "value": {"bias6": round(bias6, 2), "bias12": round(bias12, 2), "bias24": round(bias24, 2)},
                "score": int(self._clamp_score(bias_score)),
                "result": bias_result,
                "explanation": "BIAS measures percentage distance between price and moving averages.",
            },
            "kc": {
                "value": {"upper": round(kc_upper, 3), "mid": round(kc_mid, 3), "lower": round(kc_lower, 3)},
                "score": int(self._clamp_score(kc_score)),
                "result": kc_result,
                "explanation": "Keltner Channel uses EMA and ATR to define trend channel.",
            },
            "bbiboll": {
                "value": {"bbi": round(bbi, 3), "upper": round(bb_up, 3), "lower": round(bb_low, 3)},
                "score": int(self._clamp_score(bb_score)),
                "result": bb_result,
                "explanation": "BBIBOLL combines BBI baseline with volatility bands.",
            },
            "magic_nine_turn": {
                "value": {"buy_count": buy_count, "sell_count": sell_count},
                "score": int(self._clamp_score(td_score)),
                "result": td_result,
                "explanation": "Magic Nine Turn (TD9-style) counts potential exhaustion setups.",
            },
        }
        return indicator_items

    def _scan_pattern_signals_history(self, df: pd.DataFrame, lookback_bars: int = 252, max_signals: int = 120) -> List[Dict[str, Any]]:
        """Scan recent historical bars and collect bottom/top pattern signals."""
        if df is None or df.empty or len(df) < 20:
            return []

        working = df.sort_values("date").reset_index(drop=True).copy()
        if len(working) > lookback_bars:
            working = working.iloc[-lookback_bars:].reset_index(drop=True)

        signals: List[Dict[str, Any]] = []

        def _future_return_with_days(index: int, offset: int) -> Tuple[Optional[float], int]:
            target = min(index + offset, len(working) - 1)
            effective_days = max(0, target - index)
            if effective_days <= 0:
                return 0.0, 0
            base_price = float(working.iloc[index]["close"])
            future_price = float(working.iloc[target]["close"])
            if base_price <= 0:
                return None, effective_days
            return round((future_price - base_price) / base_price * 100, 2), effective_days

        def _signal_strength(signal_type: str, pattern_count: int, volume_ratio: float, macd_bar: float, rsi_12: float) -> Tuple[int, str]:
            score = 55 + min(max(pattern_count, 0), 3) * 10
            if signal_type.startswith("止跌"):
                if rsi_12 <= 35:
                    score += 10
                if macd_bar > 0:
                    score += 8
                if volume_ratio >= 1.2:
                    score += 8
            else:
                if rsi_12 >= 65:
                    score += 10
                if macd_bar < 0:
                    score += 8
                if volume_ratio >= 1.2:
                    score += 8
            final_score = int(max(30, min(95, score)))
            if final_score >= 80:
                return final_score, "强"
            if final_score >= 65:
                return final_score, "中"
            return final_score, "弱"

        for i in range(19, len(working)):
            window = working.iloc[: i + 1].copy()
            latest = window.iloc[-1]

            vol_5d_avg = window["volume"].iloc[-6:-1].mean() if len(window) >= 6 else 0
            volume_ratio = float(latest["volume"]) / float(vol_5d_avg) if vol_5d_avg and vol_5d_avg > 0 else 0.0
            price = float(latest["close"])
            ma5 = float(latest.get("MA5", price))
            ma10 = float(latest.get("MA10", price))

            resistance_levels: List[float] = []
            if len(window) >= 20:
                recent_high = float(window["high"].iloc[-20:].max())
                if recent_high > price:
                    resistance_levels.append(recent_high)

            ma_support_tolerance = self.MA_SUPPORT_TOLERANCE
            support_ma5 = ma5 > 0 and abs(price - ma5) / ma5 <= ma_support_tolerance and price >= ma5
            support_ma10 = ma10 > 0 and abs(price - ma10) / ma10 <= ma_support_tolerance and price >= ma10

            day_result = TrendAnalysisResult(
                code="",
                current_price=price,
                ma5=ma5,
                ma10=ma10,
                ma20=float(latest.get("MA20", price)),
                volume_ratio_5d=volume_ratio,
                support_ma5=support_ma5,
                support_ma10=support_ma10,
                resistance_levels=resistance_levels,
                macd_dif=float(latest.get("MACD_DIF", 0)),
                macd_dea=float(latest.get("MACD_DEA", 0)),
                macd_bar=float(latest.get("MACD_BAR", 0)),
                rsi_12=float(latest.get(f"RSI_{self.RSI_MID}", 50)),
            )

            bottoms: List[str] = []
            tops: List[str] = []
            for rule in self.pattern_rules.get("bottom", []):
                if self._match_candlestick_pattern(window, rule.pattern_name) and self._indicator_resonance(window, day_result, rule):
                    bottoms.append(f"{rule.pattern_name}({'+'.join(rule.indicators)})")
            for rule in self.pattern_rules.get("top", []):
                if self._match_candlestick_pattern(window, rule.pattern_name) and self._indicator_resonance(window, day_result, rule):
                    tops.append(f"{rule.pattern_name}({'+'.join(rule.indicators)})")

            if bottoms:
                future_7d_return, future_7d_days = _future_return_with_days(i, 7)
                future_30d_return, future_30d_days = _future_return_with_days(i, 30)
                strength_score, strength_label = _signal_strength(
                    signal_type="止跌(买入)",
                    pattern_count=len(bottoms),
                    volume_ratio=volume_ratio,
                    macd_bar=float(latest.get("MACD_BAR", 0)),
                    rsi_12=float(latest.get(f"RSI_{self.RSI_MID}", 50)),
                )
                signals.append(
                    {
                        "date": str(latest["date"]),
                        "signal_type": "止跌(买入)",
                        "patterns": bottoms,
                        "signal_strength_score": strength_score,
                        "signal_strength": strength_label,
                        "future_7d_return_pct": future_7d_return,
                        "future_30d_return_pct": future_30d_return,
                        "future_7d_effective_days": int(future_7d_days),
                        "future_30d_effective_days": int(future_30d_days),
                    }
                )
            if tops:
                future_7d_return, future_7d_days = _future_return_with_days(i, 7)
                future_30d_return, future_30d_days = _future_return_with_days(i, 30)
                strength_score, strength_label = _signal_strength(
                    signal_type="见顶(卖出)",
                    pattern_count=len(tops),
                    volume_ratio=volume_ratio,
                    macd_bar=float(latest.get("MACD_BAR", 0)),
                    rsi_12=float(latest.get(f"RSI_{self.RSI_MID}", 50)),
                )
                signals.append(
                    {
                        "date": str(latest["date"]),
                        "signal_type": "见顶(卖出)",
                        "patterns": tops,
                        "signal_strength_score": strength_score,
                        "signal_strength": strength_label,
                        "future_7d_return_pct": future_7d_return,
                        "future_30d_return_pct": future_30d_return,
                        "future_7d_effective_days": int(future_7d_days),
                        "future_30d_effective_days": int(future_30d_days),
                    }
                )

        if len(signals) > max_signals:
            signals = signals[-max_signals:]
        return signals

    def build_technical_module(self, df: pd.DataFrame, code: str, lookback_bars: int = 252) -> Dict[str, Any]:
        """Build deterministic technical module for per-stock analysis output."""
        if df is None or df.empty or len(df) < 20:
            return {}

        working = df.sort_values("date").reset_index(drop=True).copy()
        working = self._calculate_mas(working)
        working = self._calculate_macd(working)
        working = self._calculate_rsi(working)
        working = self._calculate_boll(working)
        working = self._calculate_cci(working)
        working = self._calculate_kdj(working)
        working = self._calculate_bias_series(working)
        working = self._calculate_kc(working)
        working = self._calculate_bbiboll(working)
        working = self._calculate_sar(working)
        working = self._calculate_magic_nine_turn(working)

        tail = working.iloc[-lookback_bars:].copy() if len(working) > lookback_bars else working.copy()
        latest = tail.iloc[-1]
        current_price = float(latest["close"])

        def _box(n: int) -> Dict[str, float]:
            segment = tail.iloc[-n:] if len(tail) >= n else tail
            low = float(segment["low"].min())
            high = float(segment["high"].max())
            width_pct = (high - low) / low * 100 if low > 0 else 0
            return {"low": round(low, 3), "high": round(high, 3), "width_pct": round(width_pct, 2)}

        box_20 = _box(20)
        box_60 = _box(60)
        box_120 = _box(120)

        swing_high = float(tail["high"].max())
        swing_low = float(tail["low"].min())
        span = max(swing_high - swing_low, 1e-9)
        fib_ratios = [0.236, 0.382, 0.5, 0.618, 0.786]
        fib_levels = {
            f"{int(r * 1000) / 10:g}%": round(swing_low + span * r, 3)
            for r in fib_ratios
        }

        trend_window = tail.iloc[-60:] if len(tail) >= 60 else tail
        trend_support = 0.0
        trend_resistance = 0.0
        slope_support = 0.0
        slope_resistance = 0.0
        if len(trend_window) >= 20:
            x = np.arange(len(trend_window))
            slope_support, intercept_low = np.polyfit(x, trend_window["low"].values, 1)
            slope_resistance, intercept_high = np.polyfit(x, trend_window["high"].values, 1)
            trend_support = float(slope_support * x[-1] + intercept_low)
            trend_resistance = float(slope_resistance * x[-1] + intercept_high)

        support_candidates = [
            {"value": float(latest.get("MA5", 0) or 0), "origin": "MA5", "role": "support"},
            {"value": float(latest.get("MA10", 0) or 0), "origin": "MA10", "role": "support"},
            {"value": float(latest.get("MA20", 0) or 0), "origin": "MA20", "role": "support"},
            {"value": float(latest.get("MA60", 0) or 0), "origin": "MA60", "role": "support"},
            {"value": box_20["low"], "origin": "20日箱体低点", "role": "support"},
            {"value": box_60["low"], "origin": "60日箱体低点", "role": "support"},
            {"value": box_120["low"], "origin": "120日箱体低点", "role": "support"},
            {"value": trend_support, "origin": "趋势线支撑", "role": "support"},
        ] + [
            {"value": float(v), "origin": f"Fib {k}", "role": "support"}
            for k, v in fib_levels.items()
        ]
        resistance_candidates = [
            {"value": box_20["high"], "origin": "20日箱体高点", "role": "resistance"},
            {"value": box_60["high"], "origin": "60日箱体高点", "role": "resistance"},
            {"value": box_120["high"], "origin": "120日箱体高点", "role": "resistance"},
            {"value": trend_resistance, "origin": "趋势线阻力", "role": "resistance"},
        ] + [
            {"value": float(v), "origin": f"Fib {k}", "role": "resistance"}
            for k, v in fib_levels.items()
        ]

        strong_support, weak_support = self._pick_strong_weak_levels(
            [float(item["value"]) for item in support_candidates], current_price, is_support=True
        )
        strong_resistance, weak_resistance = self._pick_strong_weak_levels(
            [float(item["value"]) for item in resistance_candidates], current_price, is_support=False
        )
        multi_boxes = self._build_multi_boxes(current_price, support_candidates, resistance_candidates)
        rhino_zones = sorted(
            [
                {
                    "name": str(box.get("name", "")),
                    "side": str(box.get("side", "")),
                    "upper": round(float(box.get("high", 0.0) or 0.0), 3),
                    "lower": round(float(box.get("low", 0.0) or 0.0), 3),
                    "strength_score": int(box.get("strength_score", 50) or 50),
                    "strength_level": self._rhino_strength_level(int(box.get("strength_score", 50) or 50)),
                    "logic_detail": str(box.get("logic_detail") or box.get("logic") or ""),
                    "key_levels": box.get("key_levels", []),
                    "source_type": "system",
                }
                for box in multi_boxes
                if float(box.get("high", 0.0) or 0.0) > 0 and float(box.get("low", 0.0) or 0.0) > 0
            ],
            key=lambda item: float(item.get("upper", 0.0) or 0.0),
            reverse=True,
        )

        indicators = self._build_extended_indicator_items(tail)
        indicator_order = ["rsi", "asr", "cc", "sar", "macd", "kdj", "bias", "kc", "bbiboll", "magic_nine_turn"]
        scored_values = [indicators.get(k, {}).get("score", 0) for k in indicator_order]
        overall_score = int(round(float(np.mean(scored_values)))) if scored_values else 50

        if overall_score >= 75:
            overall_result = "技术面偏强"
        elif overall_score >= 60:
            overall_result = "技术面中性偏多"
        elif overall_score >= 45:
            overall_result = "技术面中性"
        else:
            overall_result = "技术面偏弱"

        pattern_signals = self._scan_pattern_signals_history(working, lookback_bars=lookback_bars)
        bottom_count = sum(1 for s in pattern_signals if s.get("signal_type") == "止跌(买入)")
        top_count = sum(1 for s in pattern_signals if s.get("signal_type") == "见顶(卖出)")

        return {
            "code": code,
            "window": {
                "start": str(tail.iloc[0]["date"]),
                "end": str(tail.iloc[-1]["date"]),
                "bars": int(len(tail)),
            },
            "price_zones": {
                "current_price": round(current_price, 3),
                "box_ranges": {
                    "short_20": box_20,
                    "mid_60": box_60,
                    "long_120": box_120,
                },
                "multi_boxes": multi_boxes,
                "rhino_zones": rhino_zones,
                "support_boxes": [b for b in multi_boxes if b.get("side") == "support"],
                "resistance_boxes": [b for b in multi_boxes if b.get("side") == "resistance"],
                "fibonacci_levels": fib_levels,
                "trendline": {
                    "support": round(trend_support, 3) if trend_support else 0.0,
                    "resistance": round(trend_resistance, 3) if trend_resistance else 0.0,
                    "slope_support": round(float(slope_support), 6),
                    "slope_resistance": round(float(slope_resistance), 6),
                },
                "strong_support": round(strong_support, 3) if strong_support else 0.0,
                "weak_support": round(weak_support, 3) if weak_support else 0.0,
                "strong_resistance": round(strong_resistance, 3) if strong_resistance else 0.0,
                "weak_resistance": round(weak_resistance, 3) if weak_resistance else 0.0,
            },
            "pattern_signals_1y": {
                "bottom_count": int(bottom_count),
                "top_count": int(top_count),
                "signals": pattern_signals,
            },
            "technical_indicators": {
                **indicators,
                "indicator_order": indicator_order,
                "overall": {
                    "score": int(overall_score),
                    "result": overall_result,
                    "result_detail": f"综合 {len(scored_values)} 项指标，当前技术面结论：{overall_result}。",
                },
            },
        }
    
    def _analyze_trend(self, df: pd.DataFrame, result: TrendAnalysisResult) -> None:
        """
        分析趋势状态
        
        核心逻辑：判断均线排列和趋势强度
        """
        ma5, ma10, ma20 = result.ma5, result.ma10, result.ma20
        
        # 判断均线排列
        if ma5 > ma10 > ma20:
            # 检查间距是否在扩大（强势）
            prev = df.iloc[-5] if len(df) >= 5 else df.iloc[-1]
            prev_spread = (prev['MA5'] - prev['MA20']) / prev['MA20'] * 100 if prev['MA20'] > 0 else 0
            curr_spread = (ma5 - ma20) / ma20 * 100 if ma20 > 0 else 0
            
            if curr_spread > prev_spread and curr_spread > 5:
                result.trend_status = TrendStatus.STRONG_BULL
                result.ma_alignment = "强势多头排列，均线发散上行"
                result.trend_strength = 90
            else:
                result.trend_status = TrendStatus.BULL
                result.ma_alignment = "多头排列 MA5>MA10>MA20"
                result.trend_strength = 75
                
        elif ma5 > ma10 and ma10 <= ma20:
            result.trend_status = TrendStatus.WEAK_BULL
            result.ma_alignment = "弱势多头，MA5>MA10 但 MA10≤MA20"
            result.trend_strength = 55
            
        elif ma5 < ma10 < ma20:
            prev = df.iloc[-5] if len(df) >= 5 else df.iloc[-1]
            prev_spread = (prev['MA20'] - prev['MA5']) / prev['MA5'] * 100 if prev['MA5'] > 0 else 0
            curr_spread = (ma20 - ma5) / ma5 * 100 if ma5 > 0 else 0
            
            if curr_spread > prev_spread and curr_spread > 5:
                result.trend_status = TrendStatus.STRONG_BEAR
                result.ma_alignment = "强势空头排列，均线发散下行"
                result.trend_strength = 10
            else:
                result.trend_status = TrendStatus.BEAR
                result.ma_alignment = "空头排列 MA5<MA10<MA20"
                result.trend_strength = 25
                
        elif ma5 < ma10 and ma10 >= ma20:
            result.trend_status = TrendStatus.WEAK_BEAR
            result.ma_alignment = "弱势空头，MA5<MA10 但 MA10≥MA20"
            result.trend_strength = 40
            
        else:
            result.trend_status = TrendStatus.CONSOLIDATION
            result.ma_alignment = "均线缠绕，趋势不明"
            result.trend_strength = 50
    
    def _calculate_bias(self, result: TrendAnalysisResult) -> None:
        """
        计算乖离率
        
        乖离率 = (现价 - 均线) / 均线 * 100%
        
        严进策略：乖离率超过 5% 不追高
        """
        price = result.current_price
        
        if result.ma5 > 0:
            result.bias_ma5 = (price - result.ma5) / result.ma5 * 100
        if result.ma10 > 0:
            result.bias_ma10 = (price - result.ma10) / result.ma10 * 100
        if result.ma20 > 0:
            result.bias_ma20 = (price - result.ma20) / result.ma20 * 100
    
    def _analyze_volume(self, df: pd.DataFrame, result: TrendAnalysisResult) -> None:
        """
        分析量能
        
        偏好：缩量回调 > 放量上涨 > 缩量上涨 > 放量下跌
        """
        if len(df) < 5:
            return
        
        latest = df.iloc[-1]
        vol_5d_avg = df['volume'].iloc[-6:-1].mean()
        
        if vol_5d_avg > 0:
            result.volume_ratio_5d = float(latest['volume']) / vol_5d_avg
        
        # 判断价格变化
        prev_close = df.iloc[-2]['close']
        price_change = (latest['close'] - prev_close) / prev_close * 100
        
        # 量能状态判断
        if result.volume_ratio_5d >= self.VOLUME_HEAVY_RATIO:
            if price_change > 0:
                result.volume_status = VolumeStatus.HEAVY_VOLUME_UP
                result.volume_trend = "放量上涨，多头力量强劲"
            else:
                result.volume_status = VolumeStatus.HEAVY_VOLUME_DOWN
                result.volume_trend = "放量下跌，注意风险"
        elif result.volume_ratio_5d <= self.VOLUME_SHRINK_RATIO:
            if price_change > 0:
                result.volume_status = VolumeStatus.SHRINK_VOLUME_UP
                result.volume_trend = "缩量上涨，上攻动能不足"
            else:
                result.volume_status = VolumeStatus.SHRINK_VOLUME_DOWN
                result.volume_trend = "缩量回调，洗盘特征明显（好）"
        else:
            result.volume_status = VolumeStatus.NORMAL
            result.volume_trend = "量能正常"
    
    def _analyze_support_resistance(self, df: pd.DataFrame, result: TrendAnalysisResult) -> None:
        """
        分析支撑压力位
        
        买点偏好：回踩 MA5/MA10 获得支撑
        """
        price = result.current_price
        
        # 检查是否在 MA5 附近获得支撑
        if result.ma5 > 0:
            ma5_distance = abs(price - result.ma5) / result.ma5
            if ma5_distance <= self.MA_SUPPORT_TOLERANCE and price >= result.ma5:
                result.support_ma5 = True
                result.support_levels.append(result.ma5)
        
        # 检查是否在 MA10 附近获得支撑
        if result.ma10 > 0:
            ma10_distance = abs(price - result.ma10) / result.ma10
            if ma10_distance <= self.MA_SUPPORT_TOLERANCE and price >= result.ma10:
                result.support_ma10 = True
                if result.ma10 not in result.support_levels:
                    result.support_levels.append(result.ma10)
        
        # MA20 作为重要支撑
        if result.ma20 > 0 and price >= result.ma20:
            result.support_levels.append(result.ma20)
        
        # 近期高点作为压力
        if len(df) >= 20:
            recent_high = df['high'].iloc[-20:].max()
            if recent_high > price:
                result.resistance_levels.append(recent_high)

    def _analyze_macd(self, df: pd.DataFrame, result: TrendAnalysisResult) -> None:
        """
        分析 MACD 指标

        核心信号：
        - 零轴上金叉：最强买入信号
        - 金叉：DIF 上穿 DEA
        - 死叉：DIF 下穿 DEA
        """
        if len(df) < self.MACD_SLOW:
            result.macd_signal = "数据不足"
            return

        latest = df.iloc[-1]
        prev = df.iloc[-2]

        # 获取 MACD 数据
        result.macd_dif = float(latest['MACD_DIF'])
        result.macd_dea = float(latest['MACD_DEA'])
        result.macd_bar = float(latest['MACD_BAR'])

        # 判断金叉死叉
        prev_dif_dea = prev['MACD_DIF'] - prev['MACD_DEA']
        curr_dif_dea = result.macd_dif - result.macd_dea

        # 金叉：DIF 上穿 DEA
        is_golden_cross = prev_dif_dea <= 0 and curr_dif_dea > 0

        # 死叉：DIF 下穿 DEA
        is_death_cross = prev_dif_dea >= 0 and curr_dif_dea < 0

        # 零轴穿越
        prev_zero = prev['MACD_DIF']
        curr_zero = result.macd_dif
        is_crossing_up = prev_zero <= 0 and curr_zero > 0
        is_crossing_down = prev_zero >= 0 and curr_zero < 0

        # 判断 MACD 状态
        if is_golden_cross and curr_zero > 0:
            result.macd_status = MACDStatus.GOLDEN_CROSS_ZERO
            result.macd_signal = "⭐ 零轴上金叉，强烈买入信号！"
        elif is_crossing_up:
            result.macd_status = MACDStatus.CROSSING_UP
            result.macd_signal = "⚡ DIF上穿零轴，趋势转强"
        elif is_golden_cross:
            result.macd_status = MACDStatus.GOLDEN_CROSS
            result.macd_signal = "✅ 金叉，趋势向上"
        elif is_death_cross:
            result.macd_status = MACDStatus.DEATH_CROSS
            result.macd_signal = "❌ 死叉，趋势向下"
        elif is_crossing_down:
            result.macd_status = MACDStatus.CROSSING_DOWN
            result.macd_signal = "⚠️ DIF下穿零轴，趋势转弱"
        elif result.macd_dif > 0 and result.macd_dea > 0:
            result.macd_status = MACDStatus.BULLISH
            result.macd_signal = "✓ 多头排列，持续上涨"
        elif result.macd_dif < 0 and result.macd_dea < 0:
            result.macd_status = MACDStatus.BEARISH
            result.macd_signal = "⚠ 空头排列，持续下跌"
        else:
            result.macd_status = MACDStatus.BULLISH
            result.macd_signal = " MACD 中性区域"

    def _analyze_rsi(self, df: pd.DataFrame, result: TrendAnalysisResult) -> None:
        """
        分析 RSI 指标

        核心判断：
        - RSI > 70：超买，谨慎追高
        - RSI < 30：超卖，关注反弹
        - 40-60：中性区域
        """
        if len(df) < self.RSI_LONG:
            result.rsi_signal = "数据不足"
            return

        latest = df.iloc[-1]

        # 获取 RSI 数据
        result.rsi_6 = float(latest[f'RSI_{self.RSI_SHORT}'])
        result.rsi_12 = float(latest[f'RSI_{self.RSI_MID}'])
        result.rsi_24 = float(latest[f'RSI_{self.RSI_LONG}'])

        # 以中期 RSI(12) 为主进行判断
        rsi_mid = result.rsi_12

        # 判断 RSI 状态
        if rsi_mid > self.RSI_OVERBOUGHT:
            result.rsi_status = RSIStatus.OVERBOUGHT
            result.rsi_signal = f"⚠️ RSI超买({rsi_mid:.1f}>70)，短期回调风险高"
        elif rsi_mid > 60:
            result.rsi_status = RSIStatus.STRONG_BUY
            result.rsi_signal = f"✅ RSI强势({rsi_mid:.1f})，多头力量充足"
        elif rsi_mid >= 40:
            result.rsi_status = RSIStatus.NEUTRAL
            result.rsi_signal = f" RSI中性({rsi_mid:.1f})，震荡整理中"
        elif rsi_mid >= self.RSI_OVERSOLD:
            result.rsi_status = RSIStatus.WEAK
            result.rsi_signal = f"⚡ RSI弱势({rsi_mid:.1f})，关注反弹"
        else:
            result.rsi_status = RSIStatus.OVERSOLD
            result.rsi_signal = f"⭐ RSI超卖({rsi_mid:.1f}<30)，反弹机会大"

    def _generate_signal(self, result: TrendAnalysisResult) -> None:
        """
        生成买入信号

        综合评分系统：
        - 趋势（30分）：多头排列得分高
        - 乖离率（20分）：接近 MA5 得分高
        - 量能（15分）：缩量回调得分高
        - 支撑（10分）：获得均线支撑得分高
        - MACD（15分）：金叉和多头得分高
        - RSI（10分）：超卖和强势得分高
        """
        score = 0
        reasons = []
        risks = []

        # === 趋势评分（30分）===
        trend_scores = {
            TrendStatus.STRONG_BULL: 30,
            TrendStatus.BULL: 26,
            TrendStatus.WEAK_BULL: 18,
            TrendStatus.CONSOLIDATION: 12,
            TrendStatus.WEAK_BEAR: 8,
            TrendStatus.BEAR: 4,
            TrendStatus.STRONG_BEAR: 0,
        }
        trend_score = trend_scores.get(result.trend_status, 12)
        score += trend_score

        if result.trend_status in [TrendStatus.STRONG_BULL, TrendStatus.BULL]:
            reasons.append(f"✅ {result.trend_status.value}，顺势做多")
        elif result.trend_status in [TrendStatus.BEAR, TrendStatus.STRONG_BEAR]:
            risks.append(f"⚠️ {result.trend_status.value}，不宜做多")

        # === 乖离率评分（20分，强势趋势补偿）===
        bias = result.bias_ma5
        if bias != bias or bias is None:  # NaN or None defense
            bias = 0.0
        base_threshold = get_config().bias_threshold

        # Strong trend compensation: relax threshold for STRONG_BULL with high strength
        trend_strength = result.trend_strength if result.trend_strength == result.trend_strength else 0.0
        if result.trend_status == TrendStatus.STRONG_BULL and (trend_strength or 0) >= 70:
            effective_threshold = base_threshold * 1.5
            is_strong_trend = True
        else:
            effective_threshold = base_threshold
            is_strong_trend = False

        if bias < 0:
            # Price below MA5 (pullback)
            if bias > -3:
                score += 20
                reasons.append(f"✅ 价格略低于MA5({bias:.1f}%)，回踩买点")
            elif bias > -5:
                score += 16
                reasons.append(f"✅ 价格回踩MA5({bias:.1f}%)，观察支撑")
            else:
                score += 8
                risks.append(f"⚠️ 乖离率过大({bias:.1f}%)，可能破位")
        elif bias < 2:
            score += 18
            reasons.append(f"✅ 价格贴近MA5({bias:.1f}%)，介入好时机")
        elif bias < base_threshold:
            score += 14
            reasons.append(f"⚡ 价格略高于MA5({bias:.1f}%)，可小仓介入")
        elif bias > effective_threshold:
            score += 4
            risks.append(
                f"❌ 乖离率过高({bias:.1f}%>{effective_threshold:.1f}%)，严禁追高！"
            )
        elif bias > base_threshold and is_strong_trend:
            score += 10
            reasons.append(
                f"⚡ 强势趋势中乖离率偏高({bias:.1f}%)，可轻仓追踪"
            )
        else:
            score += 4
            risks.append(
                f"❌ 乖离率过高({bias:.1f}%>{base_threshold:.1f}%)，严禁追高！"
            )

        # === 量能评分（15分）===
        volume_scores = {
            VolumeStatus.SHRINK_VOLUME_DOWN: 15,  # 缩量回调最佳
            VolumeStatus.HEAVY_VOLUME_UP: 12,     # 放量上涨次之
            VolumeStatus.NORMAL: 10,
            VolumeStatus.SHRINK_VOLUME_UP: 6,     # 无量上涨较差
            VolumeStatus.HEAVY_VOLUME_DOWN: 0,    # 放量下跌最差
        }
        vol_score = volume_scores.get(result.volume_status, 8)
        score += vol_score

        if result.volume_status == VolumeStatus.SHRINK_VOLUME_DOWN:
            reasons.append("✅ 缩量回调，主力洗盘")
        elif result.volume_status == VolumeStatus.HEAVY_VOLUME_DOWN:
            risks.append("⚠️ 放量下跌，注意风险")

        # === 支撑评分（10分）===
        if result.support_ma5:
            score += 5
            reasons.append("✅ MA5支撑有效")
        if result.support_ma10:
            score += 5
            reasons.append("✅ MA10支撑有效")

        # === MACD 评分（15分）===
        macd_scores = {
            MACDStatus.GOLDEN_CROSS_ZERO: 15,  # 零轴上金叉最强
            MACDStatus.GOLDEN_CROSS: 12,      # 金叉
            MACDStatus.CROSSING_UP: 10,       # 上穿零轴
            MACDStatus.BULLISH: 8,            # 多头
            MACDStatus.BEARISH: 2,            # 空头
            MACDStatus.CROSSING_DOWN: 0,       # 下穿零轴
            MACDStatus.DEATH_CROSS: 0,        # 死叉
        }
        macd_score = macd_scores.get(result.macd_status, 5)
        score += macd_score

        if result.macd_status in [MACDStatus.GOLDEN_CROSS_ZERO, MACDStatus.GOLDEN_CROSS]:
            reasons.append(f"✅ {result.macd_signal}")
        elif result.macd_status in [MACDStatus.DEATH_CROSS, MACDStatus.CROSSING_DOWN]:
            risks.append(f"⚠️ {result.macd_signal}")
        else:
            reasons.append(result.macd_signal)

        # === RSI 评分（10分）===
        rsi_scores = {
            RSIStatus.OVERSOLD: 10,       # 超卖最佳
            RSIStatus.STRONG_BUY: 8,     # 强势
            RSIStatus.NEUTRAL: 5,        # 中性
            RSIStatus.WEAK: 3,            # 弱势
            RSIStatus.OVERBOUGHT: 0,       # 超买最差
        }
        rsi_score = rsi_scores.get(result.rsi_status, 5)
        score += rsi_score

        if result.rsi_status in [RSIStatus.OVERSOLD, RSIStatus.STRONG_BUY]:
            reasons.append(f"✅ {result.rsi_signal}")
        elif result.rsi_status == RSIStatus.OVERBOUGHT:
            risks.append(f"⚠️ {result.rsi_signal}")
        else:
            reasons.append(result.rsi_signal)

        # === 综合判断 ===
        result.signal_score = score
        result.signal_reasons = reasons
        result.risk_factors = risks

        # 生成买入信号（调整阈值以适应新的100分制）
        if score >= 75 and result.trend_status in [TrendStatus.STRONG_BULL, TrendStatus.BULL]:
            result.buy_signal = BuySignal.STRONG_BUY
        elif score >= 60 and result.trend_status in [TrendStatus.STRONG_BULL, TrendStatus.BULL, TrendStatus.WEAK_BULL]:
            result.buy_signal = BuySignal.BUY
        elif score >= 45:
            result.buy_signal = BuySignal.HOLD
        elif score >= 30:
            result.buy_signal = BuySignal.WAIT
        elif result.trend_status in [TrendStatus.BEAR, TrendStatus.STRONG_BEAR]:
            result.buy_signal = BuySignal.STRONG_SELL
        else:
            result.buy_signal = BuySignal.SELL

        self._apply_pattern_signal_override(result)

    def _apply_pattern_signal_override(self, result: TrendAnalysisResult) -> None:
        """Apply excel pattern advice as explicit buy/sell overrides."""
        bottom_count = len(result.bottom_pattern_hits)
        top_count = len(result.top_pattern_hits)

        if top_count > 0:
            penalty = min(35, 12 * top_count)
            result.signal_score = max(0, result.signal_score - penalty)
            top_desc = "、".join(result.top_pattern_hits)
            result.risk_factors.insert(0, f"⚠️ 命中见顶组合：{top_desc}")
            result.buy_signal = BuySignal.STRONG_SELL if top_count >= 2 else BuySignal.SELL
            result.pattern_advice = "命中见顶形态组合，建议卖出或减仓"
            return

        if bottom_count > 0:
            bonus = min(25, 10 * bottom_count)
            result.signal_score = min(100, result.signal_score + bonus)
            bottom_desc = "、".join(result.bottom_pattern_hits)
            result.signal_reasons.insert(0, f"✅ 命中止跌组合：{bottom_desc}")
            if result.buy_signal in [BuySignal.WAIT, BuySignal.HOLD, BuySignal.SELL, BuySignal.STRONG_SELL]:
                result.buy_signal = BuySignal.BUY
            if bottom_count >= 2:
                result.buy_signal = BuySignal.STRONG_BUY
            result.pattern_advice = "命中止跌形态组合，建议分批买入"
    
    def format_analysis(self, result: TrendAnalysisResult) -> str:
        """
        格式化分析结果为文本

        Args:
            result: 分析结果

        Returns:
            格式化的分析文本
        """
        lines = [
            f"=== {result.code} 趋势分析 ===",
            f"",
            f"📊 趋势判断: {result.trend_status.value}",
            f"   均线排列: {result.ma_alignment}",
            f"   趋势强度: {result.trend_strength}/100",
            f"",
            f"📈 均线数据:",
            f"   现价: {result.current_price:.2f}",
            f"   MA5:  {result.ma5:.2f} (乖离 {result.bias_ma5:+.2f}%)",
            f"   MA10: {result.ma10:.2f} (乖离 {result.bias_ma10:+.2f}%)",
            f"   MA20: {result.ma20:.2f} (乖离 {result.bias_ma20:+.2f}%)",
            f"",
            f"📊 量能分析: {result.volume_status.value}",
            f"   量比(vs5日): {result.volume_ratio_5d:.2f}",
            f"   量能趋势: {result.volume_trend}",
            f"",
            f"📈 MACD指标: {result.macd_status.value}",
            f"   DIF: {result.macd_dif:.4f}",
            f"   DEA: {result.macd_dea:.4f}",
            f"   MACD: {result.macd_bar:.4f}",
            f"   信号: {result.macd_signal}",
            f"",
            f"📊 RSI指标: {result.rsi_status.value}",
            f"   RSI(6): {result.rsi_6:.1f}",
            f"   RSI(12): {result.rsi_12:.1f}",
            f"   RSI(24): {result.rsi_24:.1f}",
            f"   信号: {result.rsi_signal}",
            f"",
            f"🎯 操作建议: {result.buy_signal.value}",
            f"   综合评分: {result.signal_score}/100",
        ]

        if result.pattern_advice:
            lines.extend([
                "",
                "🧩 形态组合信号:",
                f"   建议: {result.pattern_advice}",
            ])
            if result.bottom_pattern_hits:
                lines.append(f"   止跌命中: {'、'.join(result.bottom_pattern_hits)}")
            if result.top_pattern_hits:
                lines.append(f"   见顶命中: {'、'.join(result.top_pattern_hits)}")

        if result.signal_reasons:
            lines.append(f"")
            lines.append(f"✅ 买入理由:")
            for reason in result.signal_reasons:
                lines.append(f"   {reason}")

        if result.risk_factors:
            lines.append(f"")
            lines.append(f"⚠️ 风险因素:")
            for risk in result.risk_factors:
                lines.append(f"   {risk}")

        return "\n".join(lines)


def analyze_stock(df: pd.DataFrame, code: str) -> TrendAnalysisResult:
    """
    便捷函数：分析单只股票
    
    Args:
        df: 包含 OHLCV 数据的 DataFrame
        code: 股票代码
        
    Returns:
        TrendAnalysisResult 分析结果
    """
    analyzer = StockTrendAnalyzer()
    return analyzer.analyze(df, code)


if __name__ == "__main__":
    # 测试代码
    logging.basicConfig(level=logging.INFO)
    
    # 模拟数据测试
    import numpy as np
    
    dates = pd.date_range(start='2025-01-01', periods=60, freq='D')
    np.random.seed(42)
    
    # 模拟多头排列的数据
    base_price = 10.0
    prices = [base_price]
    for i in range(59):
        change = np.random.randn() * 0.02 + 0.003  # 轻微上涨趋势
        prices.append(prices[-1] * (1 + change))
    
    df = pd.DataFrame({
        'date': dates,
        'open': prices,
        'high': [p * (1 + np.random.uniform(0, 0.02)) for p in prices],
        'low': [p * (1 - np.random.uniform(0, 0.02)) for p in prices],
        'close': prices,
        'volume': [np.random.randint(1000000, 5000000) for _ in prices],
    })
    
    analyzer = StockTrendAnalyzer()
    result = analyzer.analyze(df, '000001')
    print(analyzer.format_analysis(result))

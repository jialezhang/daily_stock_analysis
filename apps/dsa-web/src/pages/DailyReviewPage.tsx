import type React from 'react';
import { useEffect, useMemo, useState } from 'react';
import { Card } from '../components/common';
import { dailyReviewApi } from '../api/dailyReview';
import type {
  DailyReviewAnomalyItem,
  DailyReviewPeriodItem,
  DailyReviewRegime,
  ReviewDimension,
} from '../types/dailyReview';

type ToastState = { type: 'success' | 'error'; message: string } | null;
type AnyRecord = Record<string, unknown>;
type SignalLevel = 'positive' | 'warning' | 'risk' | 'neutral';

type InsightSignal = {
  label: string;
  value: string;
  interpretation: string;
  advice: string;
  level: SignalLevel;
};

type MarketInsight = {
  market: 'US' | 'HK' | 'A';
  title: string;
  score: string;
  regime: string;
  position: string;
  reasoningLines: string[];
  macroSignals: InsightSignal[];
  indexSignals: InsightSignal[];
  sectorSignals: InsightSignal[];
  actions: string[];
};

const DIMENSIONS: Array<{ key: ReviewDimension; label: string }> = [
  { key: 'day', label: '日复盘' },
  { key: 'week', label: '周复盘' },
  { key: 'month', label: '月复盘' },
];

const MARKET_ORDER = ['US', 'HK', 'A'] as const;
const MARKET_LABEL: Record<string, string> = {
  US: '美股',
  HK: '港股',
  A: 'A股',
};
const MARKET_COLOR: Record<string, string> = {
  US: '#22d3ee',
  HK: '#34d399',
  A: '#f59e0b',
};

const asNumber = (value: unknown): number | null => {
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
};

const asRecord = (value: unknown): AnyRecord => (value && typeof value === 'object' ? (value as AnyRecord) : {});

const asRecordArray = (value: unknown): AnyRecord[] => (Array.isArray(value) ? value.map((x) => asRecord(x)) : []);

const pickValue = (obj: AnyRecord, keys: string[]): unknown => {
  for (const key of keys) {
    if (obj[key] !== undefined && obj[key] !== null) return obj[key];
  }
  return undefined;
};

const pickNum = (obj: AnyRecord, keys: string[]): number | null => asNumber(pickValue(obj, keys));

const formatDateTime = (value: string | undefined): string => {
  if (!value) return '-';
  return value;
};

const formatNum = (value: unknown, digits = 2): string => {
  const n = asNumber(value);
  if (n === null) return 'N/A';
  return n.toFixed(digits);
};

const formatSigned = (value: unknown, digits = 2): string => {
  const n = asNumber(value);
  if (n === null) return 'N/A';
  return `${n >= 0 ? '+' : ''}${n.toFixed(digits)}`;
};

const buildTrendPath = (
  values: number[],
  width: number,
  height: number,
  minScore: number,
  maxScore: number,
): string => {
  if (!values.length) return '';
  const left = 16;
  const top = 16;
  const innerWidth = width - left * 2;
  const innerHeight = height - top * 2;
  const step = values.length > 1 ? innerWidth / (values.length - 1) : 0;
  const span = maxScore - minScore || 1;
  const points = values.map((score, index) => {
    const x = left + index * step;
    const y = top + ((maxScore - score) / span) * innerHeight;
    return `${x},${y}`;
  });
  return `M ${points.join(' L ')}`;
};

const topSectorText = (rows: AnyRecord[], size: number): string => {
  if (!rows.length) return '暂无明显主线';
  return rows
    .slice(0, size)
    .map((row) => {
      const name = String(row.name || row.ticker || '-');
      const pct = asNumber(pickValue(row, ['dailyChangePct', 'daily_change_pct']));
      return `${name}(${pct === null ? 'N/A' : `${pct >= 0 ? '+' : ''}${pct.toFixed(2)}%`})`;
    })
    .join('，');
};

const signalStyle = (level: SignalLevel): { border: string; text: string; badge: string } => {
  if (level === 'risk') {
    return {
      border: 'border-red-400/40 bg-red-500/8',
      text: 'text-red-200',
      badge: 'bg-red-500/20 border-red-400/40 text-red-200',
    };
  }
  if (level === 'warning') {
    return {
      border: 'border-amber-300/40 bg-amber-500/8',
      text: 'text-amber-100',
      badge: 'bg-amber-400/20 border-amber-300/40 text-amber-100',
    };
  }
  if (level === 'positive') {
    return {
      border: 'border-emerald-400/40 bg-emerald-500/8',
      text: 'text-emerald-200',
      badge: 'bg-emerald-500/20 border-emerald-400/40 text-emerald-200',
    };
  }
  return {
    border: 'border-white/10 bg-white/4',
    text: 'text-secondary',
    badge: 'bg-white/10 border-white/20 text-white/80',
  };
};

const levelStyle = (level: string): { box: string; badge: string; text: string } => {
  if ((level || '').toUpperCase() === 'RED') {
    return {
      box: 'border-red-400/30 bg-red-500/10',
      badge: 'bg-red-500/20 border-red-400/40 text-red-200',
      text: 'text-red-200',
    };
  }
  return {
    box: 'border-amber-300/30 bg-amber-400/10',
    badge: 'bg-amber-400/20 border-amber-300/40 text-amber-100',
    text: 'text-amber-100',
  };
};

const vixSignal = (vix: number | null): InsightSignal => {
  if (vix === null) {
    return {
      label: 'VIX',
      value: 'N/A',
      interpretation: '波动率数据缺失，风险状态无法确认。',
      advice: '维持中性仓位，等待波动率确认。',
      level: 'neutral',
    };
  }
  if (vix >= 30) {
    return {
      label: 'VIX',
      value: vix.toFixed(2),
      interpretation: '处于恐慌区，市场风险偏好快速收缩。',
      advice: '控制高波动资产敞口，优先防守。',
      level: 'risk',
    };
  }
  if (vix >= 25) {
    return {
      label: 'VIX',
      value: vix.toFixed(2),
      interpretation: '处于警戒区，短线波动与回撤概率上升。',
      advice: '降低追涨频率，仓位保持弹性。',
      level: 'warning',
    };
  }
  if (vix <= 18) {
    return {
      label: 'VIX',
      value: vix.toFixed(2),
      interpretation: '风险偏好较好，波动环境相对友好。',
      advice: '可保留进攻仓位，但避免单边重仓。',
      level: 'positive',
    };
  }
  return {
    label: 'VIX',
    value: vix.toFixed(2),
    interpretation: '处于中性区间，市场尚未给出单边信号。',
    advice: '以结构性机会为主，控制仓位节奏。',
    level: 'neutral',
  };
};

const usIndexSignal = (close: number | null, ma50: number | null, ma200: number | null): InsightSignal => {
  if (close === null || ma50 === null || ma200 === null) {
    return {
      label: 'SPY 结构',
      value: 'N/A',
      interpretation: '均线结构数据不足。',
      advice: '先看趋势确认，再决定进攻仓位。',
      level: 'neutral',
    };
  }
  if (close > ma50 && ma50 > ma200) {
    return {
      label: 'SPY 结构',
      value: `Close ${close.toFixed(2)} / MA50 ${ma50.toFixed(2)} / MA200 ${ma200.toFixed(2)}`,
      interpretation: '多头结构完整，趋势韧性较好。',
      advice: '可维持核心仓位，优先强势板块。',
      level: 'positive',
    };
  }
  if (close < ma50 && ma50 < ma200) {
    return {
      label: 'SPY 结构',
      value: `Close ${close.toFixed(2)} / MA50 ${ma50.toFixed(2)} / MA200 ${ma200.toFixed(2)}`,
      interpretation: '空头结构明显，反弹持续性偏弱。',
      advice: '进攻仓位降档，优先控制回撤。',
      level: 'risk',
    };
  }
  return {
    label: 'SPY 结构',
    value: `Close ${close.toFixed(2)} / MA50 ${ma50.toFixed(2)} / MA200 ${ma200.toFixed(2)}`,
    interpretation: '震荡结构，趋势方向尚不一致。',
    advice: '以轮动交易为主，不宜过度押注方向。',
    level: 'warning',
  };
};

const hkIndexSignal = (close: number | null, ma20: number | null, ma60: number | null): InsightSignal => {
  if (close === null || ma20 === null || ma60 === null) {
    return {
      label: '恒生结构',
      value: 'N/A',
      interpretation: '港股基准趋势数据不足。',
      advice: '关注指数与南向资金共振后再加仓。',
      level: 'neutral',
    };
  }
  if (close > ma20 && ma20 >= ma60) {
    return {
      label: '恒生结构',
      value: `Close ${close.toFixed(2)} / MA20 ${ma20.toFixed(2)} / MA60 ${ma60.toFixed(2)}`,
      interpretation: '短中期趋势转强，反弹延续性较好。',
      advice: '可关注港股核心科技和高流动性龙头。',
      level: 'positive',
    };
  }
  if (close < ma60) {
    return {
      label: '恒生结构',
      value: `Close ${close.toFixed(2)} / MA20 ${ma20.toFixed(2)} / MA60 ${ma60.toFixed(2)}`,
      interpretation: '仍在弱势区间，情绪修复不稳定。',
      advice: '仓位偏防守，等待趋势反转确认。',
      level: 'risk',
    };
  }
  return {
    label: '恒生结构',
    value: `Close ${close.toFixed(2)} / MA20 ${ma20.toFixed(2)} / MA60 ${ma60.toFixed(2)}`,
    interpretation: '处于修复阶段，趋势强度一般。',
    advice: '以分批试仓为主，避免追高。',
    level: 'warning',
  };
};

const aIndexSignal = (close: number | null, ma20: number | null, ma60: number | null): InsightSignal => {
  if (close === null || ma20 === null || ma60 === null) {
    return {
      label: '沪深300结构',
      value: 'N/A',
      interpretation: 'A股趋势数据不足。',
      advice: '等待指数与成交额同步改善。',
      level: 'neutral',
    };
  }
  if (close > ma20 && ma20 > ma60) {
    return {
      label: '沪深300结构',
      value: `Close ${close.toFixed(2)} / MA20 ${ma20.toFixed(2)} / MA60 ${ma60.toFixed(2)}`,
      interpretation: '中短期多头结构形成，风险偏好改善。',
      advice: '可适度提高进攻仓位，优先主线行业。',
      level: 'positive',
    };
  }
  if (close < ma20 && ma20 < ma60) {
    return {
      label: '沪深300结构',
      value: `Close ${close.toFixed(2)} / MA20 ${ma20.toFixed(2)} / MA60 ${ma60.toFixed(2)}`,
      interpretation: '空头结构延续，反弹偏交易性。',
      advice: '降低频率和仓位，控制净值回撤。',
      level: 'risk',
    };
  }
  return {
    label: '沪深300结构',
    value: `Close ${close.toFixed(2)} / MA20 ${ma20.toFixed(2)} / MA60 ${ma60.toFixed(2)}`,
    interpretation: '震荡格局，方向选择尚未完成。',
    advice: '聚焦强度更高的板块龙头。',
    level: 'warning',
  };
};

const normalizeDecimalText = (text: string): string =>
  text.replace(/-?\d+\.\d+/g, (raw) => {
    const num = Number(raw);
    if (!Number.isFinite(num)) return raw;
    return num.toFixed(2);
  });

const splitReasoningLines = (raw: string): string[] => {
  const text = String(raw || '').trim();
  if (!text) return ['暂无评分解释'];
  const lines = text
    .split(/[；;]+/)
    .map((line) => normalizeDecimalText(line.trim()))
    .filter(Boolean);
  return lines.length ? lines : ['暂无评分解释'];
};

const indexSignalFromRow = (row: AnyRecord): InsightSignal => {
  const name = String(row.name || row.ticker || '指数');
  const close = pickNum(row, ['close']);
  const ma20 = pickNum(row, ['ma20']);
  const ma60 = pickNum(row, ['ma60']);
  const daily = pickNum(row, ['dailyChangePct', 'daily_change_pct']);

  let level: SignalLevel = 'neutral';
  let interpretation = '趋势方向不明确。';
  let advice = '保持中性仓位，等待确认信号。';

  if (close !== null && ma20 !== null && ma60 !== null) {
    if (close > ma20 && ma20 > ma60) {
      level = 'positive';
      interpretation = '多头结构，趋势相对健康。';
      advice = '可优先配置强势方向，顺势持有。';
    } else if (close < ma20 && ma20 < ma60) {
      level = 'risk';
      interpretation = '空头结构，反弹持续性偏弱。';
      advice = '降低进攻仓位，先控回撤。';
    } else {
      level = 'warning';
      interpretation = '震荡结构，方向一致性不足。';
      advice = '以低吸高抛或小仓位试错为主。';
    }
  } else if (daily !== null && daily < -1.5) {
    level = 'warning';
    interpretation = '短线回撤明显，情绪波动加大。';
    advice = '谨慎追涨，等待止跌确认。';
  }

  return {
    label: name,
    value: `收盘: ${formatNum(close)}\n日涨跌: ${formatSigned(daily)}%\nMA20: ${formatNum(ma20)}\nMA60: ${formatNum(ma60)}`,
    interpretation,
    advice,
    level,
  };
};

const DailyReviewPage: React.FC = () => {
  const [dimension, setDimension] = useState<ReviewDimension>('day');
  const [items, setItems] = useState<DailyReviewPeriodItem[]>([]);
  const [selectedKey, setSelectedKey] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [running, setRunning] = useState(false);
  const [pushingKey, setPushingKey] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<ToastState>(null);
  const [showTrendModal, setShowTrendModal] = useState(false);

  const loadHistory = async (nextDimension: ReviewDimension, keepSelection: boolean) => {
    setLoading(true);
    setError(null);
    try {
      const response = await dailyReviewApi.getHistory(nextDimension, 180);
      const rows = Array.isArray(response.items) ? response.items : [];
      setItems(rows);
      if (keepSelection && selectedKey && rows.some((item) => item.periodKey === selectedKey)) {
        setSelectedKey(selectedKey);
      } else {
        setSelectedKey(rows[0]?.periodKey || '');
      }
    } catch (err) {
      setItems([]);
      setSelectedKey('');
      setError(err instanceof Error ? err.message : '加载复盘历史失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadHistory(dimension, false);
  }, [dimension]);

  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast(null), 2400);
    return () => window.clearTimeout(timer);
  }, [toast]);

  const selectedItem = useMemo(() => {
    if (!items.length) return null;
    return items.find((item) => item.periodKey === selectedKey) || items[0] || null;
  }, [items, selectedKey]);

  const snapshot = useMemo(() => asRecord(selectedItem?.snapshot), [selectedItem]);

  const regimes = useMemo(
    () => (Array.isArray(snapshot.regimes) ? snapshot.regimes : []) as DailyReviewRegime[],
    [snapshot],
  );

  const anomalyItems = useMemo(
    () =>
      (Array.isArray(asRecord(snapshot.anomalies).items)
        ? (asRecord(snapshot.anomalies).items as DailyReviewAnomalyItem[])
        : []),
    [snapshot],
  );

  const trendSeries = useMemo(() => {
    const source = [...items].slice(0, 24).reverse();
    return {
      labels: source.map((item) => item.periodLabel || item.periodKey),
      US: source.map((item) => asNumber(asRecord(asRecord(item.charts).marketScores).US) ?? 0),
      HK: source.map((item) => asNumber(asRecord(asRecord(item.charts).marketScores).HK) ?? 0),
      A: source.map((item) => asNumber(asRecord(asRecord(item.charts).marketScores).A) ?? 0),
    };
  }, [items]);

  const insights = useMemo((): MarketInsight[] => {
    const macroPoints = asRecord(asRecord(snapshot.macro).points);
    const liquidity = asRecord(snapshot.liquidity);
    const sectors = asRecord(snapshot.sectors);
    const benchmarks = asRecord(sectors.benchmarks);

    const us10y = asRecord(pickValue(macroPoints, ['us10y', 'us10Y', 'us_10y']));
    const usdIndex = asRecord(pickValue(macroPoints, ['usdIndex', 'usd_index']));
    const usdCnh = asRecord(pickValue(macroPoints, ['usdCnh', 'usd_cnh']));
    const vix = asRecord(pickValue(macroPoints, ['vix']));

    const usBench = asRecord(benchmarks.US);
    const hkBench = asRecord(benchmarks.HK);
    const aBench = asRecord(benchmarks.A);

    const usSectors = asRecordArray(sectors.us);
    const hkSectors = asRecordArray(sectors.hk);
    const aSectors = asRecordArray(sectors.a);

    const us10yValue = pickNum(us10y, ['value']);
    const usdIndexValue = pickNum(usdIndex, ['value']);
    const usdCnhValue = pickNum(usdCnh, ['value']);
    const vixValue = pickNum(vix, ['value']);

    const northbound = pickNum(liquidity, ['northboundNetBillion', 'northbound_net_billion']);
    const southbound = pickNum(liquidity, ['southboundNetBillion', 'southbound_net_billion']);
    const aTurnover = pickNum(liquidity, ['aTurnoverBillion', 'a_turnover_billion']);
    const spyVolumeRatio = pickNum(liquidity, ['spyVolumeRatio', 'spy_volume_ratio']);

    const usClose = pickNum(usBench, ['close']);
    const usMa50 = pickNum(usBench, ['ma50']);
    const usMa200 = pickNum(usBench, ['ma200']);
    const hkClose = pickNum(hkBench, ['close']);
    const hkMa20 = pickNum(hkBench, ['ma20']);
    const hkMa60 = pickNum(hkBench, ['ma60']);
    const aClose = pickNum(aBench, ['close']);
    const aMa20 = pickNum(aBench, ['ma20']);
    const aMa60 = pickNum(aBench, ['ma60']);

    const regimeMap = new Map<string, DailyReviewRegime>();
    regimes.forEach((item) => regimeMap.set(String(item.market || '').toUpperCase(), item));

    const buildRegimeSummary = (market: 'US' | 'HK' | 'A'): { regime: string; position: string; reasoning: string } => {
      const item = regimeMap.get(market);
      return {
        regime: String(item?.regime || '-'),
        position: String(item?.positionSuggestion || '-'),
        reasoning: String(item?.reasoning || '暂无解读'),
      };
    };

    const usReg = buildRegimeSummary('US');
    const hkReg = buildRegimeSummary('HK');
    const aReg = buildRegimeSummary('A');

    const usIndexRows = asRecordArray(pickValue(usBench, ['indices']));
    const hkIndexRows = asRecordArray(pickValue(hkBench, ['indices']));
    const aIndexRows = asRecordArray(pickValue(aBench, ['indices']));

    const usSignals: MarketInsight = {
      market: 'US',
      title: '美股',
      score: formatSigned(regimeMap.get('US')?.totalScore),
      regime: usReg.regime,
      position: usReg.position,
      reasoningLines: splitReasoningLines(usReg.reasoning),
      macroSignals: [
        vixSignal(vixValue),
        {
          label: '10Y 美债',
          value: `${formatNum(us10yValue)}%`,
          interpretation:
            us10yValue === null
              ? '利率数据不足。'
              : us10yValue >= 4.5
                ? '长端利率偏高，成长资产估值承压。'
                : '利率压力可控，估值环境相对友好。',
          advice: us10yValue !== null && us10yValue >= 4.5 ? '进攻仓位向高现金流板块倾斜。' : '可保留结构性进攻仓位。',
          level: us10yValue !== null && us10yValue >= 4.5 ? 'warning' : 'positive',
        },
        {
          label: '美元指数',
          value: formatNum(usdIndexValue),
          interpretation:
            usdIndexValue === null
              ? '美元数据不足。'
              : usdIndexValue > 106
                ? '美元偏强，全球流动性环境收紧。'
                : '美元压力一般，外部流动性扰动有限。',
          advice: usdIndexValue !== null && usdIndexValue > 106 ? '美股偏防守，避免过度杠杆。' : '按趋势择强配置。',
          level: usdIndexValue !== null && usdIndexValue > 106 ? 'warning' : 'neutral',
        },
      ],
      indexSignals: [
        ...(usIndexRows.length ? usIndexRows.map((row) => indexSignalFromRow(row)) : [usIndexSignal(usClose, usMa50, usMa200)]),
        {
          label: 'SPY 量比',
          value: `量比: ${formatNum(spyVolumeRatio)}\n阈值: 1.00`,
          interpretation:
            spyVolumeRatio === null
              ? '成交活跃度数据不足。'
              : spyVolumeRatio > 1
                ? '量能活跃，趋势延续概率提升。'
                : '量能一般，突破持续性需观察。',
          advice: spyVolumeRatio !== null && spyVolumeRatio > 1 ? '顺势持有强势板块。' : '减少追涨，等待放量确认。',
          level: spyVolumeRatio !== null && spyVolumeRatio > 1 ? 'positive' : 'warning',
        },
      ],
      sectorSignals: [
        {
          label: '领先板块',
          value: topSectorText(usSectors, 3),
          interpretation: '观察领先板块是否保持连续性，是判断风险偏好的核心。',
          advice: '优先配置连续走强且成交配合的主线板块。',
          level: 'neutral',
        },
      ],
      actions: [
        `仓位基调：${usReg.position}`,
        vixValue !== null && vixValue >= 25 ? '短线降低高beta仓位，优先防守。' : '维持进攻与防守平衡，避免单一风格重仓。',
      ],
    };

    const hkSignals: MarketInsight = {
      market: 'HK',
      title: '港股',
      score: formatSigned(regimeMap.get('HK')?.totalScore),
      regime: hkReg.regime,
      position: hkReg.position,
      reasoningLines: splitReasoningLines(hkReg.reasoning),
      macroSignals: [
        {
          label: 'USDCNH',
          value: formatNum(usdCnhValue),
          interpretation:
            usdCnhValue === null
              ? '汇率数据不足。'
              : usdCnhValue >= 7.3
                ? '人民币偏弱，港股风险溢价抬升。'
                : '汇率压力可控，外资情绪相对稳定。',
          advice: usdCnhValue !== null && usdCnhValue >= 7.3 ? '减少高弹性仓位，控制回撤。' : '可关注资金回流的核心资产。',
          level: usdCnhValue !== null && usdCnhValue >= 7.3 ? 'risk' : 'neutral',
        },
        {
          label: '南向资金',
          value: `${formatNum(southbound)} 亿`,
          interpretation:
            southbound === null
              ? '南向资金数据不足。'
              : southbound > 20
                ? '内资净流入明显，对港股形成支撑。'
                : '南向承接一般，反弹持续性待确认。',
          advice: southbound !== null && southbound > 20 ? '可适度提高港股主线配置。' : '仓位以试探为主，避免追高。',
          level: southbound !== null && southbound > 20 ? 'positive' : 'warning',
        },
      ],
      indexSignals: hkIndexRows.length ? hkIndexRows.map((row) => indexSignalFromRow(row)) : [hkIndexSignal(hkClose, hkMa20, hkMa60)],
      sectorSignals: [
        {
          label: '领先方向',
          value: topSectorText(hkSectors, 2),
          interpretation: '若科技与金融形成轮动，港股结构会更稳定。',
          advice: '优先交易流动性好、政策与业绩共振的板块。',
          level: 'neutral',
        },
      ],
      actions: [`仓位基调：${hkReg.position}`, '关注汇率与南向资金是否同向改善。'],
    };

    const aSignals: MarketInsight = {
      market: 'A',
      title: 'A股',
      score: formatSigned(regimeMap.get('A')?.totalScore),
      regime: aReg.regime,
      position: aReg.position,
      reasoningLines: splitReasoningLines(aReg.reasoning),
      macroSignals: [
        {
          label: '北向资金',
          value: `${formatNum(northbound)} 亿`,
          interpretation:
            northbound === null
              ? '北向数据不足。'
              : northbound < -50
                ? '外资流出明显，权重承压。'
                : northbound > 0
                  ? '外资回流，有利于权重稳定。'
                  : '北向中性，更多依赖内资主导。',
          advice:
            northbound !== null && northbound < -50
              ? '减少外资敏感方向，偏防守。'
              : '保持主线配置，但控制节奏。',
          level: northbound !== null && northbound < -50 ? 'risk' : northbound !== null && northbound > 0 ? 'positive' : 'warning',
        },
        {
          label: '成交额',
          value: `${formatNum(aTurnover)} 亿`,
          interpretation:
            aTurnover === null
              ? '成交额数据不足。'
              : aTurnover > 12000
                ? '市场活跃，具备趋势展开条件。'
                : aTurnover < 8000
                  ? '缩量明显，存量博弈主导。'
                  : '活跃度一般，结构性机会为主。',
          advice:
            aTurnover !== null && aTurnover > 12000
              ? '可适度提高主线仓位。'
              : aTurnover !== null && aTurnover < 8000
                ? '降低频率，等待放量再进攻。'
                : '聚焦辨识度高的龙头。',
          level: aTurnover !== null && aTurnover < 8000 ? 'risk' : aTurnover !== null && aTurnover > 12000 ? 'positive' : 'warning',
        },
      ],
      indexSignals: aIndexRows.length ? aIndexRows.map((row) => indexSignalFromRow(row)) : [aIndexSignal(aClose, aMa20, aMa60)],
      sectorSignals: [
        {
          label: '领先行业',
          value: topSectorText(aSectors, 3),
          interpretation: '主线集中度越高，趋势交易胜率通常越高。',
          advice: '围绕主线做高低切，不追后排。',
          level: 'neutral',
        },
      ],
      actions: [`仓位基调：${aReg.position}`, '若北向转正且放量，可逐步提升进攻仓位。'],
    };

    return [usSignals, hkSignals, aSignals];
  }, [snapshot, regimes]);

  const runReview = async (pushTelegram: boolean) => {
    setRunning(true);
    setError(null);
    try {
      const response = await dailyReviewApi.runReview({ pushTelegram, useLlm: false });
      setToast({ type: 'success', message: response.message || '复盘已更新' });
      await loadHistory(dimension, false);
    } catch (err) {
      setError(err instanceof Error ? err.message : '重新复盘失败');
      setToast({ type: 'error', message: '重新复盘失败，请稍后重试' });
    } finally {
      setRunning(false);
    }
  };

  const pushOneItem = async (item: DailyReviewPeriodItem) => {
    const reviewDate = String(item.reviewDate || '').trim();
    if (!reviewDate) {
      setToast({ type: 'error', message: '该条记录没有可推送日期' });
      return;
    }
    setPushingKey(item.periodKey);
    setError(null);
    try {
      const response = await dailyReviewApi.pushByDate(reviewDate);
      setToast({
        type: response.pushed ? 'success' : 'error',
        message: response.message || (response.pushed ? '已触发推送' : '推送失败'),
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : '推送失败');
      setToast({ type: 'error', message: '推送失败，请稍后重试' });
    } finally {
      setPushingKey(null);
    }
  };

  const chartWidth = 620;
  const chartHeight = 220;
  const scoreMin = -4;
  const scoreMax = 4;

  return (
    <div className="p-4 md:p-6 lg:p-8 space-y-5">
      <div className="flex flex-col gap-4 rounded-2xl border border-white/8 bg-[linear-gradient(140deg,rgba(0,212,255,0.12),rgba(13,13,20,0.92)_45%,rgba(15,34,54,0.85))] p-5">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <p className="label-uppercase">Daily Review</p>
            <h1 className="text-xl md:text-2xl font-semibold text-white">市场复盘中心</h1>
            <p className="text-xs text-secondary mt-1">可视化查看复盘结论，支持历史追溯与 Telegram 推送。</p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {DIMENSIONS.map((item) => (
              <button
                key={item.key}
                type="button"
                className={dimension === item.key ? 'btn-primary !px-3 !py-2' : 'btn-secondary !px-3 !py-2'}
                onClick={() => setDimension(item.key)}
                disabled={loading || running}
              >
                {item.label}
              </button>
            ))}
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            className="btn-secondary !px-3 !py-2"
            onClick={() => void loadHistory(dimension, true)}
            disabled={loading || running}
          >
            刷新列表
          </button>
          <button type="button" className="btn-primary !px-3 !py-2" onClick={() => void runReview(false)} disabled={running}>
            {running ? '复盘中...' : '重新复盘'}
          </button>
          <button type="button" className="btn-secondary !px-3 !py-2" onClick={() => void runReview(true)} disabled={running}>
            复盘并推送
          </button>
        </div>
        {error ? <p className="text-sm text-red-400">{error}</p> : null}
      </div>

      <div className="grid gap-4 xl:grid-cols-[320px_minmax(0,1fr)]">
        <Card title="历史复盘" subtitle={dimension === 'day' ? 'DAY' : dimension === 'week' ? 'WEEK' : 'MONTH'} padding="sm">
          <div className="max-h-[68vh] overflow-y-auto space-y-2 pr-1">
            {loading ? <p className="text-sm text-secondary p-2">加载中...</p> : null}
            {!loading && !items.length ? <p className="text-sm text-secondary p-2">暂无复盘记录</p> : null}
            {!loading &&
              items.map((item) => (
                <div
                  key={item.periodKey}
                  role="button"
                  tabIndex={0}
                  className={`history-item ${selectedItem?.periodKey === item.periodKey ? 'active' : ''}`}
                  onClick={() => setSelectedKey(item.periodKey)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter' || event.key === ' ') {
                      event.preventDefault();
                      setSelectedKey(item.periodKey);
                    }
                  }}
                >
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium text-white truncate">{item.periodLabel || item.periodKey}</p>
                    <p className="text-xs text-secondary truncate">{formatDateTime(item.generatedAt)}</p>
                  </div>
                  <button
                    type="button"
                    className="btn-secondary !px-2 !py-1 !text-[11px]"
                    onClick={(event) => {
                      event.stopPropagation();
                      void pushOneItem(item);
                    }}
                    disabled={pushingKey === item.periodKey}
                  >
                    {pushingKey === item.periodKey ? '推送中' : '推送'}
                  </button>
                </div>
              ))}
          </div>
        </Card>

        <div className="space-y-4">
          {!selectedItem ? (
            <Card title="复盘详情" padding="md">
              <p className="text-secondary text-sm">请选择左侧一条复盘记录。</p>
            </Card>
          ) : (
            <>
              <Card title={selectedItem.periodLabel || selectedItem.periodKey} subtitle="SUMMARY" padding="md">
                <div className="flex flex-col gap-3">
                  <div className="flex flex-wrap items-center gap-2 text-xs text-secondary">
                    <span className="badge badge-cyan">维度: {selectedItem.dimension}</span>
                    <span className="badge badge-purple">日期: {selectedItem.reviewDate || '-'}</span>
                    <span>生成时间: {formatDateTime(selectedItem.generatedAt)}</span>
                  </div>

                  <div className="space-y-2">
                    {anomalyItems.length ? (
                      anomalyItems.slice(0, 6).map((item, idx) => {
                        const style = levelStyle(String(item.level || 'YELLOW'));
                        const markets = (Array.isArray(item.affectedMarkets) ? item.affectedMarkets : [])
                          .map((m) => MARKET_LABEL[m] || m)
                          .join(' / ');
                        return (
                          <div key={`${item.name}-${idx}`} className={`rounded-xl border p-3 ${style.box}`}>
                            <div className="flex flex-wrap items-center gap-2">
                              <span
                                className={`inline-flex items-center rounded-md border px-2 py-0.5 text-[11px] font-semibold ${style.badge}`}
                              >
                                {String(item.level || 'YELLOW').toUpperCase()}
                              </span>
                              <span className={`text-sm font-semibold ${style.text}`}>{item.name}</span>
                              {markets ? <span className="text-[11px] text-secondary">影响市场: {markets}</span> : null}
                            </div>
                            <p className="mt-1 text-sm text-white">{item.message}</p>
                            {item.possibleCause ? <p className="mt-1 text-xs text-secondary">可能原因: {item.possibleCause}</p> : null}
                            {item.potentialImpact ? <p className="mt-1 text-xs text-secondary">潜在影响: {item.potentialImpact}</p> : null}
                          </div>
                        );
                      })
                    ) : (
                      <p className="text-sm text-emerald-300">当前无异常预警。</p>
                    )}
                  </div>

                  <p className="text-sm text-white leading-6">{selectedItem.summary || '暂无摘要'}</p>
                </div>
              </Card>

              <div className="space-y-4">
                {insights.map((item) => (
                  <Card
                    key={item.market}
                    title={`${item.title}市场分析`}
                    subtitle={item.market}
                    padding="md"
                    className="bg-[linear-gradient(160deg,rgba(0,212,255,0.11),rgba(13,13,20,0.96)_36%,rgba(255,255,255,0.03))]"
                  >
                    <div className="space-y-3">
                      <div className="rounded-xl border border-white/12 bg-black/25 p-3">
                        <div className="flex flex-wrap items-center justify-between gap-3">
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="text-xs text-secondary">状态</span>
                            <span className="inline-flex items-center rounded-md border border-cyan/30 bg-cyan/12 px-2 py-1 text-sm font-semibold text-cyan">
                              {item.regime}
                            </span>
                            <span className="text-xs text-secondary">仓位</span>
                            <span className="inline-flex items-center rounded-md border border-amber-300/30 bg-amber-400/12 px-2 py-1 text-sm font-semibold text-amber-100">
                              {item.position}
                            </span>
                          </div>
                          <div className="flex items-center gap-2">
                            <span className="text-xs text-secondary">评分</span>
                            <span className="text-lg font-semibold" style={{ color: MARKET_COLOR[item.market] }}>
                              {item.score}
                            </span>
                            <button
                              type="button"
                              className="inline-flex h-7 w-7 items-center justify-center rounded-md border border-white/15 bg-white/6 text-secondary hover:text-white"
                              onClick={() => setShowTrendModal(true)}
                              title="查看三市场历史评分"
                              aria-label="查看三市场历史评分"
                            >
                              <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor">
                                <path strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" d="M4 19h16M6 15l4-4 3 3 5-6" />
                              </svg>
                            </button>
                          </div>
                        </div>
                        <div className="mt-2 space-y-1">
                          {item.reasoningLines.map((line, idx) => (
                            <p key={`${item.market}-reason-${idx}`} className="text-xs text-white">
                              {line}
                            </p>
                          ))}
                        </div>
                      </div>

                      <div className="grid gap-3 lg:grid-cols-3">
                        <div className="space-y-2">
                          <p className="label-uppercase">宏观信号</p>
                          {item.macroSignals.map((signal) => {
                            const style = signalStyle(signal.level);
                            return (
                              <div key={`${item.market}-${signal.label}`} className={`rounded-lg border p-2 ${style.border}`}>
                                <p className="text-xs text-secondary">{signal.label}</p>
                                <div className={`mt-0.5 space-y-0.5 ${style.text}`}>
                                  {String(signal.value || '')
                                    .split('\\n')
                                    .map((line, idx) => (
                                      <p key={`${item.market}-${signal.label}-macro-${idx}`} className="text-sm font-semibold">
                                        {line}
                                      </p>
                                    ))}
                                </div>
                                <p className="text-xs text-white mt-1">{signal.interpretation}</p>
                                <p className="text-[11px] text-secondary mt-1">建议: {signal.advice}</p>
                              </div>
                            );
                          })}
                        </div>

                        <div className="space-y-2">
                          <p className="label-uppercase">大盘结构</p>
                          {item.indexSignals.map((signal) => {
                            const style = signalStyle(signal.level);
                            return (
                              <div key={`${item.market}-${signal.label}`} className={`rounded-lg border p-2 ${style.border}`}>
                                <p className="text-xs text-secondary">{signal.label}</p>
                                <div className={`mt-0.5 space-y-0.5 ${style.text}`}>
                                  {String(signal.value || '')
                                    .split('\\n')
                                    .map((line, idx) => (
                                      <p key={`${item.market}-${signal.label}-index-${idx}`} className="text-sm font-semibold">
                                        {line}
                                      </p>
                                    ))}
                                </div>
                                <p className="text-xs text-white mt-1">{signal.interpretation}</p>
                                <p className="text-[11px] text-secondary mt-1">建议: {signal.advice}</p>
                              </div>
                            );
                          })}
                        </div>

                        <div className="space-y-2">
                          <p className="label-uppercase">板块信号</p>
                          {item.sectorSignals.map((signal) => {
                            const style = signalStyle(signal.level);
                            return (
                              <div key={`${item.market}-${signal.label}`} className={`rounded-lg border p-2 ${style.border}`}>
                                <div className="flex items-center justify-between gap-2">
                                  <p className="text-xs text-secondary">{signal.label}</p>
                                  <span className={`text-[11px] ${style.text}`}>主线</span>
                                </div>
                                <div className={`mt-0.5 space-y-0.5 ${style.text}`}>
                                  {String(signal.value || '')
                                    .split('\\n')
                                    .map((line, idx) => (
                                      <p key={`${item.market}-${signal.label}-sector-${idx}`} className="text-sm font-semibold">
                                        {line}
                                      </p>
                                    ))}
                                </div>
                                <p className="text-[11px] text-secondary mt-1">{signal.interpretation}</p>
                                <p className="text-[11px] text-secondary mt-1">建议: {signal.advice}</p>
                              </div>
                            );
                          })}
                        </div>
                      </div>

                      <div className="rounded-lg border border-white/10 bg-white/3 p-2">
                        <p className="label-uppercase">操作建议</p>
                        <div className="mt-1 space-y-1">
                          {item.actions.map((action) => (
                            <p key={`${item.market}-${action}`} className="text-xs text-white">• {action}</p>
                          ))}
                        </div>
                      </div>
                    </div>
                  </Card>
                ))}
              </div>
            </>
          )}
        </div>
      </div>

      {showTrendModal ? (
        <div className="fixed inset-0 z-40 bg-black/70 p-4 md:p-8" onClick={() => setShowTrendModal(false)}>
          <div
            className="mx-auto max-w-4xl rounded-2xl border border-white/10 bg-[#0d0d14] p-4 md:p-6"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-3">
              <div>
                <p className="label-uppercase">TREND</p>
                <h3 className="text-lg font-semibold text-white">市场评分历史趋势（美股 / 港股 / A股）</h3>
              </div>
              <button type="button" className="btn-secondary !px-3 !py-1.5" onClick={() => setShowTrendModal(false)}>
                关闭
              </button>
            </div>

            {!trendSeries.labels.length ? (
              <p className="text-sm text-secondary">暂无趋势数据</p>
            ) : (
              <div className="space-y-3">
                <svg
                  viewBox={`0 0 ${chartWidth} ${chartHeight}`}
                  className="w-full h-[240px] rounded-lg bg-white/4 border border-white/8"
                >
                  <line
                    x1="16"
                    y1={chartHeight / 2}
                    x2={chartWidth - 16}
                    y2={chartHeight / 2}
                    stroke="rgba(255,255,255,0.16)"
                  />
                  {MARKET_ORDER.map((market) => {
                    const values = trendSeries[market];
                    const path = buildTrendPath(values, chartWidth, chartHeight, scoreMin, scoreMax);
                    if (!path) return null;
                    return (
                      <path
                        key={market}
                        d={path}
                        fill="none"
                        stroke={MARKET_COLOR[market]}
                        strokeWidth={2}
                        strokeLinecap="round"
                      />
                    );
                  })}
                </svg>
                <div className="flex flex-wrap items-center gap-3 text-xs text-secondary">
                  {MARKET_ORDER.map((market) => (
                    <span key={market} className="inline-flex items-center gap-1">
                      <span className="inline-block h-2 w-2 rounded-full" style={{ background: MARKET_COLOR[market] }} />
                      {MARKET_LABEL[market]}
                    </span>
                  ))}
                  <span>最近 {trendSeries.labels.length} 个周期</span>
                </div>
              </div>
            )}
          </div>
        </div>
      ) : null}

      {toast ? (
        <div
          className={`fixed bottom-6 right-6 z-50 rounded-lg border px-4 py-2 text-sm ${
            toast.type === 'success'
              ? 'border-cyan/30 bg-cyan/10 text-cyan'
              : 'border-red-400/30 bg-red-500/10 text-red-300'
          }`}
        >
          {toast.message}
        </div>
      ) : null}
    </div>
  );
};

export default DailyReviewPage;

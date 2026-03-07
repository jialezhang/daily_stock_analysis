import type React from 'react';
import { useEffect, useMemo, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import Markdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Card } from '../components/common';
import { positionManagementApi } from '../api/positionManagement';
import type {
  PortfolioReviewPayload,
  PositionHoldingInput,
  PositionManagementTarget,
} from '../types/positionManagement';

type AnyRecord = Record<string, unknown>;
type ToastState = { type: 'success' | 'error' | 'info'; message: string } | null;
type MarkdownSection = { title: string; content: string };
type PortfolioAlertLevel = 'red' | 'yellow' | 'green' | 'blue' | 'neutral';
type PortfolioAlertItem = {
  level: PortfolioAlertLevel;
  title: string;
  description: string;
  action: string;
};
type PortfolioTradeItem = {
  direction: string;
  sentence: string;
  reason: string;
};
type PortfolioFactItem = {
  label: string;
  value: string;
};
type PortfolioMarketBoard = {
  market: string;
  environment: string;
  headline?: string;
  leaders?: string;
  laggards?: string;
  relative?: string;
  reasoning?: string;
};
type PortfolioSectionGroups = {
  ai?: MarkdownSection;
  anomalies?: MarkdownSection;
  trades?: MarkdownSection;
  health?: MarkdownSection;
  market?: MarkdownSection;
  sector?: MarkdownSection;
  others: MarkdownSection[];
};
type HoldingModalMode = 'create' | 'edit';
type HoldingModalState = {
  mode: HoldingModalMode;
  sourceId: string;
  draft: PositionHoldingInput;
};
type PortfolioReviewChatSeed = {
  initialMessage: string;
  contextLabel: string;
  persistContext: boolean;
  resetSession: boolean;
  context: Record<string, unknown>;
};
type HoveredOverviewOverlay = {
  top: number;
  height: number;
};

const PRIMARY_ASSET_OPTIONS = ['权益类', '加密货币', '贵金属', '债券', '货币基金', '现金'];
const OUTPUT_CURRENCY_LABEL_MAP: Record<string, string> = {
  CNY: 'RMB',
  RMB: 'RMB',
  USD: 'USD',
  HKD: 'HKD',
};
const SECONDARY_ASSET_MAP: Record<string, string[]> = {
  权益类: ['A股', '港股', '美股', 'ETF'],
  加密货币: ['主流币', '平台币', '稳定币', 'DeFi'],
  贵金属: ['黄金', '白银', '铂金', '钯金'],
  债券: ['国债', '政金债', '信用债', '可转债', '美债'],
  货币基金: ['场内货基', '场外货基', '现金管理'],
  现金: ['人民币现金', '美元现金', '港币现金', '其他现金'],
};

const SYMBOL_NAME_FALLBACK_MAP: Record<string, string> = {
  NVDA: '英伟达',
  MSFT: '微软',
  AAPL: '苹果',
  TSLA: '特斯拉',
  AMZN: '亚马逊',
  META: 'Meta',
  GOOGL: '谷歌A',
  GOOG: '谷歌C',
  AMD: 'AMD',
  NBIS: 'Nebius集团',
  RKLB: '火箭实验室',
  BABA: '阿里巴巴',
  PDD: '拼多多',
  JD: '京东',
  BIDU: '百度',
  NIO: '蔚来',
  LI: '理想汽车',
  XPEV: '小鹏汽车',
  '00700': '腾讯控股',
  '0700': '腾讯控股',
  '03690': '美团',
  '3690': '美团',
  '09988': '阿里巴巴',
  '9988': '阿里巴巴',
  '01810': '小米集团',
  '1810': '小米集团',
  '600519': '贵州茅台',
  '000001': '平安银行',
  '300750': '宁德时代',
  BTC: '比特币',
  VIX: '波动率指数',
  '002195': '岩山科技',
  '600118': '中国卫星',
};

const REVIEW_MARKET_LABEL_MAP: Record<string, string> = {
  US: '美股',
  HK: '港股',
  A: 'A 股',
  CN: 'A 股',
  CRYPTO: '加密资产',
};

const ALERT_TONE_MAP: Record<
  PortfolioAlertLevel,
  {
    card: string;
    title: string;
    text: string;
    action: string;
  }
> = {
  red: {
    card: 'border-rose-400/35 bg-rose-500/12',
    title: 'text-rose-200',
    text: 'text-rose-100',
    action: 'bg-rose-400/12 text-rose-100 border border-rose-300/20',
  },
  yellow: {
    card: 'border-amber-400/35 bg-amber-500/12',
    title: 'text-amber-200',
    text: 'text-amber-100',
    action: 'bg-amber-400/12 text-amber-100 border border-amber-300/20',
  },
  green: {
    card: 'border-emerald-400/35 bg-emerald-500/12',
    title: 'text-emerald-200',
    text: 'text-emerald-100',
    action: 'bg-emerald-400/12 text-emerald-100 border border-emerald-300/20',
  },
  blue: {
    card: 'border-sky-400/35 bg-sky-500/12',
    title: 'text-sky-200',
    text: 'text-sky-100',
    action: 'bg-sky-400/12 text-sky-100 border border-sky-300/20',
  },
  neutral: {
    card: 'border-white/10 bg-black/25',
    title: 'text-white',
    text: 'text-secondary',
    action: 'bg-white/5 text-white border border-white/10',
  },
};

const getFallbackName = (symbol: string): string => {
  const normalized = String(symbol || '').toUpperCase().trim();
  if (!normalized) return '';
  if (SYMBOL_NAME_FALLBACK_MAP[normalized]) return SYMBOL_NAME_FALLBACK_MAP[normalized];
  const digits = normalized.replace(/\D/g, '');
  if (digits && SYMBOL_NAME_FALLBACK_MAP[digits]) return SYMBOL_NAME_FALLBACK_MAP[digits];
  return '';
};

const getChineseDisplayName = (symbol: unknown, name: unknown): string => {
  const symbolText = String(symbol || '').toUpperCase().trim();
  const mapped = getFallbackName(symbolText);
  if (mapped) return mapped;
  const raw = String(name || '').trim();
  return raw;
};

const localizeMarketToken = (value: string): string => {
  const normalized = value.toUpperCase();
  if (REVIEW_MARKET_LABEL_MAP[normalized]) return REVIEW_MARKET_LABEL_MAP[normalized];
  return value;
};

const getReviewHoldingRecord = (review: PortfolioReviewPayload, ticker: string): AnyRecord | null => {
  const rows = Array.isArray(review.holdings) ? review.holdings : [];
  const matched = rows.find((row) => String(asRecord(row).ticker || '').toUpperCase() === ticker);
  return matched ? asRecord(matched) : null;
};

const getReviewChineseName = (review: PortfolioReviewPayload, ticker: string): string => {
  const matched = getReviewHoldingRecord(review, ticker);
  if (matched) {
    const resolved = getChineseDisplayName(matched.ticker, matched.name);
    if (resolved) return resolved;
  }
  return getChineseDisplayName(ticker, '');
};

const inferReviewLotSize = (market: string, rawLotSize: unknown): number => {
  const normalizedLotSize = asNumber(rawLotSize, 0);
  if (normalizedLotSize > 0) return normalizedLotSize;
  const normalizedMarket = String(market || '').toUpperCase();
  if (normalizedMarket === 'A' || normalizedMarket === 'CN' || normalizedMarket === 'HK') return 100;
  return 1;
};

const normalizePrimaryAsset = (value: unknown): string => {
  const raw = String(value || '').trim();
  if (PRIMARY_ASSET_OPTIONS.includes(raw)) return raw;
  if (raw === '股票' || raw === '权益') return '权益类';
  return '权益类';
};

const normalizeSecondaryAsset = (primary: string, value: unknown): string => {
  const options = SECONDARY_ASSET_MAP[primary] || ['A股'];
  const raw = String(value || '').trim();
  if (options.includes(raw)) return raw;
  if (primary === '权益类') {
    if (raw === '沪深A股' || raw === '沪市' || raw === '深市') return 'A股';
  }
  if (primary === '现金') {
    if (raw === '人民币' || raw.toUpperCase() === 'CNY' || raw.toUpperCase() === 'RMB') return '人民币现金';
    if (raw === '美元' || raw.toUpperCase() === 'USD') return '美元现金';
    if (raw === '港币' || raw.toUpperCase() === 'HKD') return '港币现金';
  }
  return options[0];
};

const defaultTarget: PositionManagementTarget = {
  initialPosition: 0,
  outputCurrency: 'USD',
  targetReturnPct: 30,
};

const asRecord = (value: unknown): AnyRecord => {
  return value && typeof value === 'object' ? (value as AnyRecord) : {};
};

const asNumber = (value: unknown, fallback = 0): number => {
  const num = Number(value);
  return Number.isFinite(num) ? num : fallback;
};

const splitMarkdownSections = (value: unknown): MarkdownSection[] => {
  const lines = String(value || '').split('\n');
  const sections: MarkdownSection[] = [];
  let currentTitle = '';
  let currentBody: string[] = [];

  const pushCurrent = () => {
    const content = currentBody.join('\n').trim();
    if (!currentTitle || !content) return;
    sections.push({ title: currentTitle, content });
  };

  lines.forEach((line) => {
    if (line.startsWith('## ')) {
      pushCurrent();
      currentTitle = line.replace(/^##\s+/, '').trim();
      currentBody = [];
      return;
    }
    if (line.startsWith('# ')) return;
    if (!currentTitle) return;
    currentBody.push(line);
  });

  pushCurrent();
  return sections;
};

const normalizePortfolioSectionTitle = (title: string): string => {
  return title.includes('LLM') ? 'AI 建议' : title;
};

const categorizePortfolioSections = (sections: MarkdownSection[]): PortfolioSectionGroups => {
  const groups: PortfolioSectionGroups = { others: [] };
  sections.forEach((section) => {
    const title = normalizePortfolioSectionTitle(section.title);
    if (title === 'AI 建议') {
      groups.ai = { ...section, title };
      return;
    }
    if (title.includes('异常')) {
      groups.anomalies = section;
      return;
    }
    if (title.includes('交易')) {
      groups.trades = section;
      return;
    }
    if (title.includes('健康')) {
      groups.health = section;
      return;
    }
    if (title.includes('市场')) {
      groups.market = section;
      return;
    }
    if (title.includes('板块')) {
      groups.sector = section;
      return;
    }
    if (['持仓明细', '目标追踪'].includes(title)) return;
    groups.others.push({ ...section, title });
  });
  return groups;
};

const parsePortfolioAlertLevel = (value: string): PortfolioAlertLevel => {
  const normalized = value.trim().toUpperCase();
  if (normalized === 'RED') return 'red';
  if (normalized === 'YELLOW') return 'yellow';
  if (normalized === 'GREEN') return 'green';
  if (normalized === 'BLUE') return 'blue';
  return 'neutral';
};

const stripPriorityPrefix = (value: string): string => {
  return value.replace(/^P\d+\s+/i, '').trim();
};

const parsePortfolioAlerts = (content: string): PortfolioAlertItem[] => {
  const lines = content.split('\n');
  const items: PortfolioAlertItem[] = [];
  let current: PortfolioAlertItem | null = null;

  const pushCurrent = () => {
    if (!current) return;
    items.push({
      ...current,
      title: current.title.trim(),
      description: current.description.trim(),
      action: current.action.trim(),
    });
    current = null;
  };

  lines.forEach((line) => {
    const trimmed = line.trim();
    if (!trimmed) return;
    if (trimmed.startsWith('- ')) {
      pushCurrent();
      const rawBody = trimmed.replace(/^-+\s*/, '');
      const match = rawBody.match(/^\[([A-Z]+)\]\s*(.+)$/);
      const level = parsePortfolioAlertLevel(match?.[1] || '');
      const body = String(match?.[2] || rawBody).trim();
      const [titlePart, ...restParts] = body.split(/[:：]/);
      current = {
        level,
        title: String(titlePart || '').trim(),
        description: restParts.join('：').trim(),
        action: '',
      };
      return;
    }
    if (!current) return;
    if (trimmed.startsWith('动作')) {
      current.action = trimmed.replace(/^动作[:：]\s*/, '').trim();
      return;
    }
    current.description = `${current.description} ${trimmed}`.trim();
  });

  pushCurrent();
  return items;
};

const parsePortfolioFacts = (content: string): PortfolioFactItem[] => {
  return content
    .split('\n')
    .map((line) => line.trim())
    .filter((line) => line.startsWith('- '))
    .map((line) => line.replace(/^-+\s*/, ''))
    .map((line) => {
      const [label, ...rest] = line.split(/[:：]/);
      return {
        label: localizeMarketToken(String(label || '').trim()),
        value: rest.join('：').trim(),
      };
    })
    .filter((item) => item.label && item.value);
};

const parsePortfolioMarketBoards = (
  review: PortfolioReviewPayload,
  sectorContent: string,
  marketContent: string,
): PortfolioMarketBoard[] => {
  const localizedSector = localizePortfolioText(review, sectorContent);
  const localizedMarket = localizePortfolioText(review, marketContent);
  const boards: PortfolioMarketBoard[] = [];
  const lines = localizedSector.split("\n");
  let current: PortfolioMarketBoard | null = null;

  const pushCurrent = () => {
    if (!current) return;
    boards.push({
      market: current.market,
      environment: current.environment,
      headline: current.headline,
      leaders: current.leaders,
      laggards: current.laggards,
      relative: current.relative,
      reasoning: current.reasoning,
    });
    current = null;
  };

  lines.forEach((line) => {
    const trimmed = line.trim();
    if (!trimmed) return;
    if (trimmed.startsWith("### ")) {
      pushCurrent();
      current = {
        market: trimmed.replace(/^###\s+/, "").trim(),
        environment: "",
      };
      return;
    }
    if (!current || !trimmed.startsWith("- ")) return;
    const body = trimmed.replace(/^-+\s*/, "");
    const [labelRaw, ...rest] = body.split(/[:：]/);
    const label = String(labelRaw || "").trim();
    const value = rest.join("：").trim();
    if (!value) return;
    if (label === "环境") current.environment = value;
    else if (label === "主线") current.headline = value;
    else if (label.includes("领涨")) current.leaders = value;
    else if (label.includes("领跌")) current.laggards = value;
    else if (label.includes("强弱")) current.relative = value;
    else if (label === "解读") current.reasoning = value;
  });
  pushCurrent();

  if (boards.length > 0) return boards;

  const marketFacts = parsePortfolioFacts(localizedMarket);
  const sectorFacts = parsePortfolioFacts(localizedSector);
  const fallbackMarkets = ["美股", "港股", "A 股"];
  return fallbackMarkets
    .map((market) => {
      const environment = marketFacts.find((item) => item.label === market)?.value || "";
      const headline =
        sectorFacts.find((item) => item.label.startsWith(market))?.value
        || sectorFacts.find((item) => item.label.includes(market.replace(" ", "")))?.value
        || "";
      return {
        market,
        environment,
        headline,
      };
    })
    .filter((item) => item.environment || item.headline);
};

const inferTradeMarketLabel = (review: PortfolioReviewPayload, ticker: string, reason: string): string => {
  const matched = getReviewHoldingRecord(review, ticker);
  const market = String(asRecord(matched).market || '').toUpperCase();
  if (REVIEW_MARKET_LABEL_MAP[market]) return REVIEW_MARKET_LABEL_MAP[market];
  if (reason.startsWith('US ')) return '美股';
  if (reason.startsWith('HK ')) return '港股';
  if (reason.startsWith('A ') || reason.startsWith('CN ')) return 'A 股';
  if (reason.includes('加密')) return '加密资产';
  return '';
};

const localizePortfolioText = (review: PortfolioReviewPayload, value: string): string => {
  let next = String(value || '');

  next = next
    .replace(/\bSELL\b/g, '卖出')
    .replace(/\bBUY\b/g, '买入')
    .replace(/\bHOLD\b/g, '持有')
    .replace(/A股/g, 'A 股')
    .replace(/\bUS\b(?=[:：\s]|$)/g, '美股')
    .replace(/\bHK\b(?=[:：\s]|$)/g, '港股')
    .replace(/\bCN\b(?=[:：\s]|$)/g, 'A 股')
    .replace(/\bA\b(?=[:：\s]|$)/g, 'A 股')
    .replace(/\bCRYPTO\b(?=[:：\s]|$)/g, '加密资产')
    .replace(/\boffensive\b/gi, '进攻')
    .replace(/\bdefensive\b/gi, '防御')
    .replace(/\bcyclical\b/gi, '周期')
    .replace(/\bmixed\b/gi, '分散')
    .replace(/\bunclear\b/gi, '不清晰')
    .replace(/\btech_leading\b/gi, '科技领涨')
    .replace(/\btech_lagging\b/gi, '科技偏弱')
    .replace(/\bsync\b/gi, '同步');

  const replacements = new Map<string, string>();
  Object.entries(SYMBOL_NAME_FALLBACK_MAP).forEach(([symbol, name]) => {
    replacements.set(symbol.toUpperCase(), name);
  });
  (Array.isArray(review.holdings) ? review.holdings : []).forEach((row) => {
    const item = asRecord(row);
    const symbol = String(item.ticker || '').toUpperCase().trim();
    if (!symbol) return;
    const name = getChineseDisplayName(symbol, item.name);
    if (name) replacements.set(symbol, name);
  });

  [...replacements.entries()]
    .sort((a, b) => b[0].length - a[0].length)
    .forEach(([symbol, name]) => {
      const escaped = symbol.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      const matcher = new RegExp(`(^|[^A-Z0-9])(${escaped})(?=$|[^A-Z0-9])`, 'gi');
      next = next.replace(matcher, (_, prefix) => `${prefix}${name}`);
    });

  return next;
};

const deriveTradeQuantityText = (review: PortfolioReviewPayload, ticker: string, amountCny: number): string => {
  const matched = getReviewHoldingRecord(review, ticker);
  if (!matched) return '';
  const shares = asNumber(matched.shares, 0);
  const valueCny = asNumber(matched.value_cny ?? matched.valueCny, 0);
  if (shares <= 0 || valueCny <= 0) return '';
  const unitValueCny = valueCny / shares;
  if (unitValueCny <= 0) return '';
  const market = String(matched.market || '').toUpperCase();
  const quantity = Math.abs(amountCny) / unitValueCny;
  if (market === 'CRYPTO') {
    return `${quantity.toLocaleString('zh-CN', {
      minimumFractionDigits: 0,
      maximumFractionDigits: 4,
    })}枚`;
  }
  const lotSize = inferReviewLotSize(market, matched.lot_size ?? matched.lotSize);
  const normalizedLotSize = Math.max(1, Math.round(lotSize));
  if (normalizedLotSize > 1) {
    const lots = Math.floor(quantity / normalizedLotSize + 1e-9);
    if (lots <= 0) return `不足 1 手（${normalizedLotSize.toLocaleString('zh-CN')}股）`;
    const totalShares = lots * normalizedLotSize;
    return `${lots.toLocaleString('zh-CN')}手（${totalShares.toLocaleString('zh-CN')}股）`;
  }
  const wholeShares = Math.floor(quantity + 1e-9);
  if (wholeShares <= 0) return '不足 1 股';
  return `${wholeShares.toLocaleString('zh-CN')}股`;
};

const parsePortfolioTrades = (content: string, review: PortfolioReviewPayload): PortfolioTradeItem[] => {
  return content
    .split('\n')
    .map((line) => line.trim())
    .filter((line) => line.startsWith('- '))
    .map((line) => stripPriorityPrefix(line.replace(/^-+\s*/, '')))
    .map((line) => {
      const match = line.match(/^(BUY|SELL|HOLD)\s+([A-Z0-9.\-]+)\s+([-\d.]+)\s+([A-Z]+)[：:]\s*(.+)$/i);
      if (!match) {
        return {
          direction: 'INFO',
          sentence: localizePortfolioText(review, line),
          reason: '',
        };
      }
      const [, direction, tickerRaw, amountRaw, currency, reasonRaw] = match;
      const ticker = String(tickerRaw || '').toUpperCase();
      const reason = localizePortfolioText(review, String(reasonRaw || '').trim());
      const amount = Math.abs(asNumber(amountRaw, 0));
      const marketLabel = inferTradeMarketLabel(review, ticker, reason);
      const displayName = getReviewChineseName(review, ticker) || localizePortfolioText(review, ticker);
      const quantityText = deriveTradeQuantityText(review, ticker, amount);
      const actionVerb = direction.toUpperCase() === 'SELL' ? '卖出' : direction.toUpperCase() === 'BUY' ? '买入' : '关注';
      const marketText = marketLabel ? `${marketLabel}的` : '';
      const quantityPart = quantityText ? `，约 ${quantityText}` : '';
      const amountText = amount > 0 ? `，金额约 ${formatCompactNumber(amount)} ${currency}` : '';
      return {
        direction: direction.toUpperCase(),
        sentence: `${actionVerb}${marketText}${displayName}${quantityPart}${amountText}`,
        reason,
      };
    });
};

const sectionToneClassName = (title: string): string => {
  if (title.includes('异常')) return 'border-amber-400/20 bg-amber-400/8';
  if (title.includes('交易')) return 'border-cyan/25 bg-cyan/8';
  if (title.includes('市场')) return 'border-emerald-400/20 bg-emerald-400/8';
  if (title.includes('板块')) return 'border-fuchsia-400/20 bg-fuchsia-400/8';
  if (title.includes('AI')) return 'border-violet-400/20 bg-violet-400/8';
  return 'border-white/10 bg-black/25';
};

const parseTarget = (module: AnyRecord): PositionManagementTarget => {
  const target = asRecord(module.target);
  return {
    initialPosition: asNumber(target.initialPosition ?? target.initial_position, 0),
    outputCurrency: String(target.outputCurrency ?? target.output_currency ?? 'USD').toUpperCase() as PositionManagementTarget['outputCurrency'],
    targetReturnPct: asNumber(target.targetReturnPct ?? target.target_return_pct, 30),
  };
};

const parseHoldings = (module: AnyRecord): PositionHoldingInput[] => {
  const rows = Array.isArray(module.holdings) ? module.holdings : [];
  return rows.map((item, idx) => {
    const row = asRecord(item);
    const primary = normalizePrimaryAsset(row.assetPrimary ?? row.asset_primary);
    const symbol = String(row.symbol ?? '').toUpperCase();
    const rawName = String(row.name ?? '').trim();
    const normalizedName = rawName && rawName.toUpperCase() === symbol ? '' : rawName;
    const resolvedName = normalizedName || getFallbackName(symbol);
    return {
      id: String(row.id ?? `holding-${idx + 1}`),
      assetPrimary: primary,
      assetSecondary: normalizeSecondaryAsset(primary, row.assetSecondary ?? row.asset_secondary),
      symbol,
      name: resolvedName,
      quantity: asNumber(row.quantity, 0),
      currentPrice: asNumber(row.currentPrice ?? row.current_price ?? row.latestPrice ?? row.latest_price, 0),
      previousClose: asNumber(row.previousClose ?? row.previous_close, 0) || undefined,
      currency: String(row.currency ?? 'USD').toUpperCase() as PositionHoldingInput['currency'],
      lotSize: asNumber(row.lotSize ?? row.lot_size, 0) || undefined,
      latestPrice: asNumber(row.latestPrice ?? row.latest_price ?? row.currentPrice ?? row.current_price, 0),
      fxToOutput: asNumber(row.fxToOutput ?? row.fx_to_output, 0),
      marketValueOutput: asNumber(row.marketValueOutput ?? row.market_value_output, 0),
      dailyPnlOutput: asNumber(row.dailyPnlOutput ?? row.daily_pnl_output, 0),
      changePct: asNumber(row.changePct ?? row.change_pct, 0),
    };
  });
};

type SaveOptions = {
  suppressMessage?: boolean;
  successMessage?: string;
  startMessage?: string;
  errorMessage?: string;
  toastOnSuccess?: boolean;
};

const buildDonut = (allocation: AnyRecord[]): string => {
  if (!allocation.length) return 'conic-gradient(rgba(255,255,255,0.14) 0deg 360deg)';
  const colors = ['#22d3ee', '#34d399', '#f59e0b', '#f97316', '#f43f5e', '#a78bfa', '#60a5fa'];
  let start = 0;
  const parts = allocation.map((item, idx) => {
    const ratio = Math.max(0, Math.min(100, asNumber(item.ratioPct ?? item.ratio_pct, 0)));
    const end = start + ratio * 3.6;
    const segment = `${colors[idx % colors.length]} ${start}deg ${end}deg`;
    start = end;
    return segment;
  });
  if (start < 360) parts.push(`rgba(255,255,255,0.08) ${start}deg 360deg`);
  return `conic-gradient(${parts.join(', ')})`;
};

const buildTrendPolyline = (values: number[], width: number, height: number): string => {
  if (!values.length) return '';
  const padding = 14;
  const minValue = Math.min(...values);
  const maxValue = Math.max(...values);
  const range = maxValue - minValue || 1;
  return values
    .map((value, index) => {
      const x = padding + ((width - padding * 2) * index) / Math.max(values.length - 1, 1);
      const y = height - padding - ((value - minValue) / range) * (height - padding * 2);
      return `${x},${y}`;
    })
    .join(' ');
};

const formatCompactNumber = (value: number): string => {
  return new Intl.NumberFormat('zh-CN', {
    notation: 'compact',
    maximumFractionDigits: value >= 1000 ? 1 : 2,
  }).format(value);
};

const getOutputCurrencyLabel = (value: unknown): string => {
  const normalized = String(value || 'USD').toUpperCase();
  return OUTPUT_CURRENCY_LABEL_MAP[normalized] || normalized;
};

const formatMoneyValue = (value: number): string => {
  return value.toLocaleString('zh-CN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
};

const buildPortfolioReviewChatSeed = (
  review: PortfolioReviewPayload | null,
  target: PositionManagementTarget,
  holdings: PositionHoldingInput[],
): PortfolioReviewChatSeed | null => {
  if (!review) return null;
  const sections = splitMarkdownSections(review.reviewReport || '');
  const groups = categorizePortfolioSections(sections);
  const marketBoards = parsePortfolioMarketBoards(review, groups.sector?.content || '', groups.market?.content || '');
  const localizedHoldings = holdings.map((item) => {
    const displayName = getChineseDisplayName(item.symbol, item.name) || String(item.name || item.symbol || '').trim();
    return {
      name: displayName,
      primary_asset: item.assetPrimary,
      market: item.assetSecondary,
      quantity: asNumber(item.quantity, 0),
      price: asNumber(item.latestPrice ?? item.currentPrice, 0),
      currency: String(item.currency || '').toUpperCase(),
      market_value_output: asNumber(item.marketValueOutput, 0),
      daily_change_pct: asNumber(item.changePct, 0),
    };
  });

  return {
    initialMessage: '请结合今天的组合现状、市场情况和今日组合复盘来回答，优先使用中文名称，不要只写代码。',
    contextLabel: '每日复盘答疑',
    persistContext: true,
    resetSession: true,
    context: {
      report_type: 'portfolio_review',
      context_title: '每日复盘答疑',
      review_date: String(review.reviewDate || ''),
      generated_at: String(review.generatedAt || ''),
      portfolio_snapshot: {
        total_value_cny: asNumber(review.totalValueCny, 0),
        cash_pct: asNumber(review.cashPct, 0),
        us_pct: asNumber(review.usPct, 0),
        hk_pct: asNumber(review.hkPct, 0),
        a_pct: asNumber(review.aPct, 0),
        crypto_pct: asNumber(review.cryptoPct, 0),
        health_score: asNumber(review.healthScore, 0),
      },
      portfolio_target: {
        initial_position: asNumber(target.initialPosition, 0),
        output_currency: String(target.outputCurrency || 'USD').toUpperCase(),
        target_return_pct: asNumber(target.targetReturnPct, 0),
      },
      portfolio_holdings: localizedHoldings,
      market_summary: marketBoards,
      portfolio_review_report: String(review.reviewReport || ''),
    },
  };
};

const markdownCardClassName = `
  prose prose-invert prose-sm max-w-none
  prose-headings:text-white prose-headings:font-semibold prose-headings:mt-3 prose-headings:mb-1.5
  prose-h1:text-lg prose-h2:text-base prose-h3:text-sm
  prose-p:leading-relaxed prose-p:mb-2 prose-p:last:mb-0
  prose-strong:text-white prose-strong:font-semibold
  prose-ul:my-1.5 prose-ol:my-1.5 prose-li:my-0.5
  prose-code:text-cyan prose-code:bg-white/5 prose-code:px-1 prose-code:py-0.5 prose-code:rounded prose-code:text-xs
  prose-pre:bg-black/30 prose-pre:border prose-pre:border-white/10 prose-pre:rounded-lg prose-pre:p-3
  prose-table:w-full prose-table:text-sm
  prose-th:text-white prose-th:font-medium prose-th:border-white/20 prose-th:px-3 prose-th:py-1.5 prose-th:bg-white/5
  prose-td:border-white/10 prose-td:px-3 prose-td:py-1.5
  prose-hr:border-white/10 prose-hr:my-3
  prose-a:text-cyan prose-a:no-underline hover:prose-a:underline
  prose-blockquote:border-cyan/30 prose-blockquote:text-secondary
`;

const PortfolioReviewDetails: React.FC<{
  review: PortfolioReviewPayload;
  sectionKeyPrefix: string;
}> = ({ review, sectionKeyPrefix }) => {
  const sections = useMemo(
    () => splitMarkdownSections(review.reviewReport || ''),
    [review.reviewReport],
  );
  const groups = useMemo(() => categorizePortfolioSections(sections), [sections]);
  const alertItems = useMemo(
    () => parsePortfolioAlerts(groups.anomalies?.content || ''),
    [groups.anomalies?.content],
  );
  const tradeItems = useMemo(
    () => parsePortfolioTrades(groups.trades?.content || '', review),
    [groups.trades?.content, review],
  );
  const healthFacts = useMemo(
    () => parsePortfolioFacts(localizePortfolioText(review, groups.health?.content || '')),
    [groups.health?.content, review],
  );
  const healthScore = useMemo(
    () => healthFacts.find((item) => item.label.includes('评分'))?.value || '',
    [healthFacts],
  );
  const marketBoards = useMemo(
    () => parsePortfolioMarketBoards(review, groups.sector?.content || '', groups.market?.content || ''),
    [groups.market?.content, groups.sector?.content, review],
  );

  return (
    <div className="space-y-3">
      {healthScore && (
        <div className="flex flex-wrap items-center gap-2">
          <span className="inline-flex items-center rounded-full border border-amber-300/25 bg-amber-400/12 px-3 py-1 text-xs font-semibold text-amber-100">
            健康度 {healthScore}
          </span>
        </div>
      )}
      {groups.ai && (
        <div className="rounded-xl border border-violet-400/25 bg-violet-500/10 p-4">
          <div className="mb-2 text-[11px] font-semibold tracking-[0.18em] text-violet-100 uppercase">
            AI 建议
          </div>
          <div className={markdownCardClassName}>
            <Markdown remarkPlugins={[remarkGfm]}>{localizePortfolioText(review, groups.ai.content)}</Markdown>
          </div>
        </div>
      )}

      {(alertItems.length > 0 || tradeItems.length > 0) && (
        <div className={`grid grid-cols-1 gap-3 ${alertItems.length > 0 ? 'xl:grid-cols-2' : ''}`}>
          {alertItems.length > 0 && (
            <div className="rounded-xl border border-white/10 bg-black/25 p-3">
              <div className="mb-3 text-[11px] font-semibold tracking-[0.18em] text-amber-100 uppercase">
                异常告警
              </div>
              <div className="space-y-3">
                {alertItems.map((item, idx) => {
                  const tone = ALERT_TONE_MAP[item.level];
                  return (
                      <div key={`${sectionKeyPrefix}-alert-${idx}`} className={`rounded-xl p-3 ${tone.card}`}>
                      <div className={`text-sm font-semibold ${tone.title}`}>{localizePortfolioText(review, item.title)}</div>
                      {item.description && <div className={`mt-1 text-xs leading-5 ${tone.text}`}>{localizePortfolioText(review, item.description)}</div>}
                      {item.action && <div className={`mt-2 rounded-lg px-2.5 py-2 text-xs ${tone.action}`}>动作：{localizePortfolioText(review, item.action)}</div>}
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {tradeItems.length > 0 && (
            <div className="rounded-xl border border-cyan/20 bg-cyan/8 p-3">
              <div className="mb-3 text-[11px] font-semibold tracking-[0.18em] text-cyan-100 uppercase">
                交易建议
              </div>
              <div className="space-y-3">
                {tradeItems.map((item, idx) => (
                  <div key={`${sectionKeyPrefix}-trade-${idx}`} className="rounded-xl border border-cyan/15 bg-black/20 p-3">
                    <div className="flex items-center gap-2">
                      <span
                        className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${
                          item.direction === 'SELL'
                            ? 'bg-rose-500/15 text-rose-200'
                            : item.direction === 'BUY'
                              ? 'bg-emerald-500/15 text-emerald-200'
                              : 'bg-white/10 text-white'
                        }`}
                      >
                        {item.direction === 'SELL' ? '卖出' : item.direction === 'BUY' ? '买入' : '关注'}
                      </span>
                      <span className="text-sm font-medium text-white">{item.sentence}</span>
                    </div>
                    {item.reason && <div className="mt-2 text-xs leading-5 text-cyan-50/90">{item.reason}</div>}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {marketBoards.length > 0 && (
        <div className="space-y-3">
          {marketBoards.map((board) => (
            <div
              key={`${sectionKeyPrefix}-board-${board.market}`}
              className="rounded-xl border border-fuchsia-400/20 bg-fuchsia-500/8 p-3"
            >
              <div className="flex flex-wrap items-center gap-2">
                <div className="text-sm font-semibold text-white">{board.market}</div>
                {board.environment && (
                  <span className="inline-flex items-center rounded-full border border-emerald-300/20 bg-emerald-400/12 px-2.5 py-0.5 text-[11px] text-emerald-100">
                    环境 {board.environment}
                  </span>
                )}
              </div>
              <div className="mt-3 space-y-2 text-sm text-white">
                {board.headline && (
                  <div className="flex flex-col gap-1 md:flex-row md:items-start md:gap-3">
                    <span className="shrink-0 text-[11px] tracking-[0.16em] text-fuchsia-100/80 uppercase">主线</span>
                    <span>{board.headline}</span>
                  </div>
                )}
                {board.leaders && (
                  <div className="flex flex-col gap-1 md:flex-row md:items-start md:gap-3">
                    <span className="shrink-0 text-[11px] tracking-[0.16em] text-fuchsia-100/80 uppercase">领涨</span>
                    <span>{board.leaders}</span>
                  </div>
                )}
                {board.laggards && (
                  <div className="flex flex-col gap-1 md:flex-row md:items-start md:gap-3">
                    <span className="shrink-0 text-[11px] tracking-[0.16em] text-fuchsia-100/80 uppercase">领跌</span>
                    <span>{board.laggards}</span>
                  </div>
                )}
                {board.relative && (
                  <div className="flex flex-col gap-1 md:flex-row md:items-start md:gap-3">
                    <span className="shrink-0 text-[11px] tracking-[0.16em] text-fuchsia-100/80 uppercase">强弱</span>
                    <span>{board.relative}</span>
                  </div>
                )}
                {board.reasoning && (
                  <div className="flex flex-col gap-1 md:flex-row md:items-start md:gap-3">
                    <span className="shrink-0 text-[11px] tracking-[0.16em] text-fuchsia-100/80 uppercase">解读</span>
                    <span className="text-fuchsia-50/90">{board.reasoning}</span>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {groups.others.length > 0 && (
        <div className="grid grid-cols-1 gap-3 xl:grid-cols-2">
          {groups.others.map((section) => (
            <div
              key={`${sectionKeyPrefix}-${section.title}`}
              className={`rounded-xl border p-3 ${sectionToneClassName(section.title)}`}
            >
              <div className="mb-2 text-[11px] font-semibold tracking-[0.18em] text-cyan-100/90 uppercase">
                {section.title}
              </div>
              <div className={markdownCardClassName}>
                <Markdown remarkPlugins={[remarkGfm]}>{localizePortfolioText(review, section.content)}</Markdown>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

const PositionManagementPage: React.FC = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const isAssetDetailsPage = location.pathname === '/position-management/assets';
  const isReviewHistoryPage = location.pathname === '/position-management/reviews';
  const [moduleData, setModuleData] = useState<AnyRecord>({});
  const [target, setTarget] = useState<PositionManagementTarget>(defaultTarget);
  const [targetDraft, setTargetDraft] = useState<PositionManagementTarget>(defaultTarget);
  const [editingTarget, setEditingTarget] = useState(false);
  const [holdings, setHoldings] = useState<PositionHoldingInput[]>([]);
  const [holdingsManagerOpen, setHoldingsManagerOpen] = useState(false);
  const [hoveredSecondaryCategory, setHoveredSecondaryCategory] = useState<string | null>(null);
  const [hoveredOverviewOverlay, setHoveredOverviewOverlay] = useState<HoveredOverviewOverlay | null>(null);
  const [hiddenValueKeys, setHiddenValueKeys] = useState<string[]>([]);
  const [holdingModal, setHoldingModal] = useState<HoldingModalState | null>(null);
  const [pendingDeleteHoldingId, setPendingDeleteHoldingId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [pushingReview, setPushingReview] = useState(false);
  const [runningPortfolioReview, setRunningPortfolioReview] = useState(false);
  const [toast, setToast] = useState<ToastState>(null);
  const [portfolioReview, setPortfolioReview] = useState<PortfolioReviewPayload | null>(null);
  const [loadingPortfolioReview, setLoadingPortfolioReview] = useState(false);
  const [portfolioReviewHistory, setPortfolioReviewHistory] = useState<PortfolioReviewPayload[]>([]);
  const [loadingPortfolioReviewHistory, setLoadingPortfolioReviewHistory] = useState(false);
  const holdingsOverviewTableWrapRef = useRef<HTMLDivElement | null>(null);
  const holdingsOverviewRowRefs = useRef<Record<string, HTMLTableRowElement | null>>({});

  const getPortfolioReviewKey = (review: PortfolioReviewPayload | null | undefined): string => {
    if (!review) return '';
    const explicitDate = String(review.reviewDate || '').trim();
    if (explicitDate) return explicitDate;
    const generatedAt = String(review.generatedAt || '').trim();
    if (generatedAt.length >= 10) return generatedAt.slice(0, 10);
    return '';
  };

  const applyModule = (module: AnyRecord) => {
    const normalizedTarget = parseTarget(module);
    setModuleData(module);
    setTarget(normalizedTarget);
    setTargetDraft(normalizedTarget);
    setHoldings(parseHoldings(module));
    setEditingTarget(false);
    setHoldingModal(null);
    setPendingDeleteHoldingId(null);
  };

  const loadModule = async () => {
    setLoading(true);
    try {
      const response = await positionManagementApi.getModule();
      applyModule(asRecord(response.module));
    } catch (err) {
      setToast({ type: 'error', message: err instanceof Error ? err.message : '加载仓位管理失败' });
    } finally {
      setLoading(false);
    }
  };

  const loadLatestPortfolioReview = async () => {
    setLoadingPortfolioReview(true);
    try {
      const response = await positionManagementApi.getLatestPortfolioReview();
      setPortfolioReview(response.found ? (response.portfolioReview || null) : null);
    } catch {
      setPortfolioReview(null);
    } finally {
      setLoadingPortfolioReview(false);
    }
  };

  const loadPortfolioReviewHistory = async (limit = 180) => {
    setLoadingPortfolioReviewHistory(true);
    try {
      const response = await positionManagementApi.getPortfolioReviewHistory(limit);
      const rows = Array.isArray(response.reviews) ? response.reviews : [];
      setPortfolioReviewHistory(rows);
    } catch (err) {
      setToast({ type: 'error', message: err instanceof Error ? err.message : '加载组合复盘历史失败' });
      setPortfolioReviewHistory([]);
    } finally {
      setLoadingPortfolioReviewHistory(false);
    }
  };

  useEffect(() => {
    if (isReviewHistoryPage) {
      void loadPortfolioReviewHistory();
      return;
    }
    void loadModule();
    if (!isAssetDetailsPage) {
      void loadLatestPortfolioReview();
      void loadPortfolioReviewHistory(60);
    }
  }, [isAssetDetailsPage, isReviewHistoryPage]);

  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast(null), toast.type === 'success' ? 3000 : 2400);
    return () => window.clearTimeout(timer);
  }, [toast]);

  const derived = asRecord(moduleData.derived);
  const totals = asRecord(derived.totals);
  const progress = asRecord(derived.targetProgress ?? derived.target_progress);
  const secondaryAllocation = (
    Array.isArray(derived.secondaryAllocation ?? derived.secondary_allocation)
      ? (derived.secondaryAllocation ?? derived.secondary_allocation)
      : []
  ) as AnyRecord[];
  const heatmap = useMemo(() => {
    const rows = (Array.isArray(derived.heatmap) ? derived.heatmap : []) as AnyRecord[];
    return [...rows].sort(
      (a, b) =>
        asNumber(b.changePct ?? b.change_pct, 0) - asNumber(a.changePct ?? a.change_pct, 0),
    );
  }, [derived.heatmap]);
  const outputCurrencyLabel = getOutputCurrencyLabel(target.outputCurrency || 'USD');

  const saveModule = async (
    nextTarget: PositionManagementTarget,
    nextHoldings: PositionHoldingInput[],
    options?: SaveOptions,
  ): Promise<boolean> => {
    setSaving(true);
    if (options?.startMessage && !options?.suppressMessage) {
      setToast({ type: 'info', message: options.startMessage });
    }
    try {
      const response = await positionManagementApi.upsertModule({
        target: nextTarget,
        holdings: nextHoldings,
        refreshBenchmarks: true,
      });
      applyModule(asRecord(response.module));
      const successText = options?.successMessage || '保存成功';
      if (!options?.suppressMessage && options?.toastOnSuccess) {
        setToast({ type: 'success', message: successText });
      }
      return true;
    } catch (err) {
      const failMsg = err instanceof Error ? err.message : (options?.errorMessage || '保存失败，请稍后重试');
      if (!options?.suppressMessage) {
        setToast({ type: 'error', message: failMsg });
      }
      return false;
    } finally {
      setSaving(false);
    }
  };

  const onSaveTarget = async () => {
    await saveModule(targetDraft, holdings, {
      startMessage: '基础信息保存中...',
      successMessage: '基础信息保存成功',
      errorMessage: '基础信息保存失败',
      toastOnSuccess: true,
    });
  };

  const persistDirtyHoldingsBeforeRefresh = async (): Promise<boolean> => {
    return !saving;
  };

  const refreshAll = async () => {
    const canProceed = await persistDirtyHoldingsBeforeRefresh();
    if (!canProceed) return;
    setRefreshing(true);
    try {
      const response = await positionManagementApi.refreshModule();
      applyModule(asRecord(response.module));
      setToast({ type: 'success', message: '刷新完成（已更新汇率与行情）' });
    } catch (err) {
      setToast({ type: 'error', message: err instanceof Error ? err.message : '刷新失败' });
    } finally {
      setRefreshing(false);
    }
  };

  const refreshEquityQuotes = async () => {
    const canProceed = await persistDirtyHoldingsBeforeRefresh();
    if (!canProceed) return;

    const equityCount = holdings.filter((item) => item.assetPrimary === '权益类' && String(item.symbol || '').trim()).length;
    if (!equityCount) {
      setToast({ type: 'info', message: '当前没有可刷新的权益类持仓' });
      return;
    }
    setRefreshing(true);
    try {
      const response = await positionManagementApi.refreshModule();
      applyModule(asRecord(response.module));
      setToast({ type: 'success', message: `权益类报价刷新成功（${equityCount}项）` });
    } catch (err) {
      const msg = err instanceof Error ? err.message : '权益类报价刷新失败';
      setToast({ type: 'error', message: msg });
    } finally {
      setRefreshing(false);
    }
  };

  const pushDailyReview = async () => {
    setPushingReview(true);
    try {
      const response = await positionManagementApi.pushDailyReview();
      setToast({
        type: response.pushed ? 'success' : 'error',
        message: response.message || (response.pushed ? '复盘推送已触发' : '复盘推送失败'),
      });
    } catch (err) {
      const msg = err instanceof Error ? err.message : '复盘推送失败';
      setToast({ type: 'error', message: msg });
    } finally {
      setPushingReview(false);
    }
  };

  const runPortfolioReview = async () => {
    setRunningPortfolioReview(true);
    try {
      const response = await positionManagementApi.runPortfolioReview();
      setToast({
        type: response.success ? 'success' : 'error',
        message: response.message || (response.success ? '组合复盘已生成' : '组合复盘生成失败'),
      });
      if (response.portfolioReview) {
        setPortfolioReview(response.portfolioReview);
      } else if (!isAssetDetailsPage) {
        await loadLatestPortfolioReview();
      }
      if (isReviewHistoryPage) {
        await loadPortfolioReviewHistory();
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : '组合复盘生成失败';
      setToast({ type: 'error', message: msg });
    } finally {
      setRunningPortfolioReview(false);
    }
  };

  const openCreateHoldingModal = () => {
    const primary = '权益类';
    const secondary = SECONDARY_ASSET_MAP[primary][0];
    const id = `manual-${Date.now()}`;
    setHoldingModal({
      mode: 'create',
      sourceId: id,
      draft: {
        id,
        assetPrimary: primary,
        assetSecondary: secondary,
        symbol: '',
        quantity: 0,
      },
    });
  };

  const openEditHoldingModal = (item: PositionHoldingInput) => {
    const itemId = String(item.id || '');
    const primary = normalizePrimaryAsset(item.assetPrimary);
    setHoldingModal({
      mode: 'edit',
      sourceId: itemId,
      draft: {
        id: itemId,
        assetPrimary: primary,
        assetSecondary: normalizeSecondaryAsset(primary, item.assetSecondary),
        symbol: String(item.symbol || ''),
        quantity: asNumber(item.quantity, 0),
        name: item.name,
        currentPrice: item.currentPrice,
        previousClose: item.previousClose,
        currency: item.currency,
        latestPrice: item.latestPrice,
        fxToOutput: item.fxToOutput,
        marketValueOutput: item.marketValueOutput,
        dailyPnlOutput: item.dailyPnlOutput,
        changePct: item.changePct,
      },
    });
  };

  const updateHoldingModalDraft = (patch: Partial<PositionHoldingInput>) => {
    setHoldingModal((prev) => {
      if (!prev) return prev;
      const next = { ...prev.draft, ...patch };
      if (patch.assetPrimary) {
        const options = SECONDARY_ASSET_MAP[patch.assetPrimary] || ['其他'];
        if (!options.includes(next.assetSecondary || '')) {
          next.assetSecondary = options[0];
        }
      }
      return { ...prev, draft: next };
    });
  };

  const saveHoldingModal = async () => {
    if (!holdingModal || saving) return;
    const draft = holdingModal.draft;
    const primary = normalizePrimaryAsset(draft.assetPrimary);
    const secondary = normalizeSecondaryAsset(primary, draft.assetSecondary);
    const symbol = String(draft.symbol || '').trim().toUpperCase();
    const quantity = Math.max(0, asNumber(draft.quantity, 0));

    if (primary !== '现金' && !symbol) {
      setToast({ type: 'error', message: '请先填写标的代码' });
      return;
    }
    if (quantity <= 0) {
      setToast({ type: 'error', message: '请填写大于 0 的持仓数量' });
      return;
    }

    const normalizedDraft: PositionHoldingInput = {
      ...draft,
      id: holdingModal.sourceId,
      assetPrimary: primary,
      assetSecondary: secondary,
      symbol,
      quantity,
    };
    const nextHoldings = holdingModal.mode === 'create'
      ? [...holdings, normalizedDraft]
      : holdings.map((item) => (String(item.id || '') === holdingModal.sourceId ? normalizedDraft : item));

    const ok = await saveModule(target, nextHoldings, {
      startMessage: holdingModal.mode === 'create' ? '资产录入中...' : '资产修改中...',
      successMessage: holdingModal.mode === 'create' ? '资产录入成功' : '资产修改成功',
      errorMessage: holdingModal.mode === 'create' ? '资产录入失败' : '资产修改失败',
      toastOnSuccess: true,
    });
    if (ok) {
      setHoldingModal(null);
    }
  };

  const removeHolding = async (id: string) => {
    const nextHoldings = holdings.filter((item) => String(item.id || '') !== id);
    const ok = await saveModule(target, nextHoldings, {
      startMessage: '删除资产中...',
      successMessage: '资产删除成功',
      errorMessage: '资产删除失败',
      toastOnSuccess: true,
    });
    if (ok) {
      setPendingDeleteHoldingId(null);
    }
  };

  const getHoldingMarketValue = (item: PositionHoldingInput): number => {
    const livePrice = asNumber(item.latestPrice ?? item.currentPrice, 0);
    const qty = asNumber(item.quantity, 0);
    const fxRate = asNumber(item.fxToOutput, 0);
    if (livePrice > 0 && qty > 0 && fxRate > 0) return livePrice * qty * fxRate;
    return asNumber(item.marketValueOutput, 0);
  };

  const sortedHoldings = [...holdings].sort((a, b) => getHoldingMarketValue(b) - getHoldingMarketValue(a));
  const totalHoldingValue = sortedHoldings.reduce((sum, item) => sum + getHoldingMarketValue(item), 0);
  const secondaryClassValueMap = sortedHoldings.reduce<Record<string, number>>((acc, item) => {
    const key = String(item.assetSecondary || '其他');
    acc[key] = (acc[key] || 0) + getHoldingMarketValue(item);
    return acc;
  }, {});
  const secondaryDistributions = Object.entries(secondaryClassValueMap)
    .map(([assetSecondary, value]) => ({
      assetSecondary,
      value,
      ratioPct: totalHoldingValue > 0 ? (value / totalHoldingValue) * 100 : 0,
    }))
    .sort((a, b) => b.value - a.value);
  const holdingsOverviewRows = useMemo(() => {
    const rows = secondaryAllocation.length > 0
      ? secondaryAllocation.map((item) => ({
        assetSecondary: String(item.assetSecondary ?? item.asset_secondary ?? '其他'),
        value: asNumber(item.valueOutput ?? item.value_output, 0),
        ratioPct: asNumber(item.ratioPct ?? item.ratio_pct, 0),
      }))
      : secondaryDistributions;
    return rows.filter((item) => item.value > 0 || item.ratioPct > 0);
  }, [secondaryAllocation, secondaryDistributions]);
  const assetClassValueMap = sortedHoldings.reduce<Record<string, number>>((acc, item) => {
    const key = String(item.assetPrimary || '其他');
    acc[key] = (acc[key] || 0) + getHoldingMarketValue(item);
    return acc;
  }, {});
  const assetClassRatios = Object.entries(assetClassValueMap)
    .map(([assetPrimary, value]) => ({
      assetPrimary,
      ratioPct: totalHoldingValue > 0 ? (value / totalHoldingValue) * 100 : 0,
    }))
    .sort((a, b) => b.ratioPct - a.ratioPct);

  const onHoldingModalKeyDown: React.KeyboardEventHandler<HTMLInputElement | HTMLSelectElement> = (event) => {
    if (saving) return;
    if (event.key !== 'Enter') return;
    event.preventDefault();
    void saveHoldingModal();
  };

  const hasModuleLoaded = Object.keys(moduleData).length > 0;
  const iconBtn = 'inline-flex items-center justify-center w-7 h-7 rounded border border-white/20 text-xs text-secondary hover:text-white hover:border-cyan/50 transition-colors';
  const pendingDeleteHolding = holdings.find((item) => item.id === pendingDeleteHoldingId) || null;
  const formBusy = loading || saving || refreshing;
  const modalPrimary = holdingModal ? normalizePrimaryAsset(holdingModal.draft.assetPrimary) : '权益类';
  const modalSecondaryOptions = SECONDARY_ASSET_MAP[modalPrimary] || ['其他'];
  const holdingsOverviewDonut = useMemo(() => buildDonut(holdingsOverviewRows), [holdingsOverviewRows]);
  const holdingsOverviewSegments = useMemo(() => {
    let start = 0;
    return holdingsOverviewRows.map((item) => {
      const end = start + Math.max(0, item.ratioPct) * 3.6;
      const segment = { category: item.assetSecondary, startAngle: start, endAngle: end };
      start = end;
      return segment;
    });
  }, [holdingsOverviewRows]);
  const portfolioReviewGeneratedAt = String(portfolioReview?.generatedAt || '');
  const portfolioTrendRows = useMemo(() => {
    return [...portfolioReviewHistory]
      .map((item) => {
        const label = getPortfolioReviewKey(item);
        return {
          label,
          totalValueCny: asNumber(item.totalValueCny, 0),
          healthScore: asNumber(item.healthScore, 0),
        };
      })
      .filter((item) => Boolean(item.label))
      .sort((left, right) => left.label.localeCompare(right.label))
      .slice(-30);
  }, [portfolioReviewHistory]);
  const portfolioValueTrendValues = portfolioTrendRows.map((item) => item.totalValueCny);
  const portfolioHealthTrendValues = portfolioTrendRows.map((item) => item.healthScore);
  const portfolioValuePolyline = buildTrendPolyline(portfolioValueTrendValues, 320, 120);
  const portfolioHealthPolyline = buildTrendPolyline(portfolioHealthTrendValues, 320, 120);
  const portfolioTrendStartLabel = portfolioTrendRows[0]?.label || '';
  const portfolioTrendEndLabel = portfolioTrendRows[portfolioTrendRows.length - 1]?.label || '';
  const portfolioTrendLatestValue = portfolioTrendRows.length
    ? portfolioTrendRows[portfolioTrendRows.length - 1].totalValueCny
    : 0;
  const portfolioTrendLatestHealth = portfolioTrendRows.length
    ? portfolioTrendRows[portfolioTrendRows.length - 1].healthScore
    : 0;
  const portfolioReviewChatSeed = useMemo(
    () => buildPortfolioReviewChatSeed(portfolioReview, target, holdings),
    [holdings, portfolioReview, target],
  );

  const toggleHiddenValue = (key: string) => {
    setHiddenValueKeys((prev) => (
      prev.includes(key) ? prev.filter((item) => item !== key) : [...prev, key]
    ));
  };

  const renderMaskableValue = (key: string, display: string, className: string) => (
    <button
      type="button"
      className={`${className} transition-opacity hover:opacity-80`}
      onClick={() => toggleHiddenValue(key)}
      title={hiddenValueKeys.includes(key) ? '点击显示数值' : '点击隐藏数值'}
    >
      {hiddenValueKeys.includes(key) ? '••••' : display}
    </button>
  );

  const getMaskedValueDisplay = (key: string, display: string) => (hiddenValueKeys.includes(key) ? '••••' : display);

  const handleOverviewDonutMove: React.MouseEventHandler<HTMLDivElement> = (event) => {
    const rect = event.currentTarget.getBoundingClientRect();
    const radius = rect.width / 2;
    const innerRadius = radius - 20;
    const centerX = rect.left + rect.width / 2;
    const centerY = rect.top + rect.height / 2;
    const dx = event.clientX - centerX;
    const dy = event.clientY - centerY;
    const distance = Math.sqrt(dx * dx + dy * dy);
    if (distance < innerRadius || distance > radius) {
      setHoveredSecondaryCategory(null);
      return;
    }
    const angle = (Math.atan2(dy, dx) * 180 / Math.PI + 450) % 360;
    const matched = holdingsOverviewSegments.find((segment) => angle >= segment.startAngle && angle < segment.endAngle);
    setHoveredSecondaryCategory(matched?.category || null);
  };

  const hoveredOverviewItem = useMemo(
    () => holdingsOverviewRows.find((item) => item.assetSecondary === hoveredSecondaryCategory) || null,
    [holdingsOverviewRows, hoveredSecondaryCategory],
  );

  useEffect(() => {
    if (!hoveredSecondaryCategory) {
      setHoveredOverviewOverlay(null);
      return;
    }

    const syncHoveredOverviewOverlay = () => {
      const wrap = holdingsOverviewTableWrapRef.current;
      const row = holdingsOverviewRowRefs.current[hoveredSecondaryCategory];
      if (!wrap || !row) {
        setHoveredOverviewOverlay(null);
        return;
      }
      const wrapRect = wrap.getBoundingClientRect();
      const rowRect = row.getBoundingClientRect();
      setHoveredOverviewOverlay({
        top: rowRect.top - wrapRect.top + wrap.scrollTop,
        height: rowRect.height,
      });
    };

    syncHoveredOverviewOverlay();
    window.addEventListener('resize', syncHoveredOverviewOverlay);
    return () => window.removeEventListener('resize', syncHoveredOverviewOverlay);
  }, [hoveredSecondaryCategory, holdingsOverviewRows]);

  const openPortfolioReviewQa = () => {
    if (!portfolioReviewChatSeed) return;
    navigate('/chat', {
      state: {
        chatSeed: portfolioReviewChatSeed,
      },
    });
  };
  const profitAmountValue = asNumber(totals.profitAmountOutput ?? totals.profit_amount_output, 0);
  const profitPctValue = asNumber(totals.profitPct ?? totals.profit_pct, 0);
  const targetGapValue = asNumber(progress.gapToTargetOutput ?? progress.gap_to_target_output, 0);
  const holdingsManagerContent = (
    <>
      {assetClassRatios.length > 0 && (
        <div className="mb-2 flex flex-wrap items-center gap-2">
          {assetClassRatios.map((item) => (
            <span
              key={`ratio-${item.assetPrimary}`}
              className="inline-flex items-center rounded border border-white/15 bg-black/30 px-2 py-0.5 text-[11px] text-secondary"
            >
              {item.assetPrimary} {item.ratioPct.toFixed(2)}%
            </span>
          ))}
        </div>
      )}
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-muted border-b border-white/10">
              <th className="text-left py-1">一级分类</th>
              <th className="text-left py-1">名称</th>
              <th className="text-right py-1">数量</th>
              <th className="text-right py-1">最新报价</th>
              <th className="text-right py-1">总价值({outputCurrencyLabel})</th>
              <th className="text-right py-1">占比总资产</th>
              <th className="text-right py-1">操作</th>
            </tr>
          </thead>
          <tbody className="text-secondary">
            {sortedHoldings.length === 0 && <tr><td className="py-2 text-muted" colSpan={7}>暂无持仓</td></tr>}
            {sortedHoldings.map((item) => {
              const itemId = String(item.id || '');
              const displayName = getChineseDisplayName(item.symbol, item.name);
              const holdingValue = getHoldingMarketValue(item);
              const holdingRatio = totalHoldingValue > 0 ? (holdingValue / totalHoldingValue) * 100 : 0;
              return (
                <tr key={itemId} className="border-b border-white/5">
                  <td className="py-2">{item.assetPrimary}</td>
                  <td className="py-2">{displayName || <span className="text-muted">未获取名称</span>}</td>
                  <td className="py-2 text-right font-mono">{asNumber(item.quantity, 0).toLocaleString()}</td>
                  <td className="py-2 text-right font-mono">
                    {Math.round(asNumber(item.latestPrice ?? item.currentPrice, 0)).toLocaleString()} {String(item.currency || '')}
                  </td>
                  <td className="py-2 text-right font-mono">{Math.round(holdingValue).toLocaleString()}</td>
                  <td className="py-2 text-right font-mono">{holdingRatio.toFixed(2)}%</td>
                  <td className="py-2 text-right">
                    <div className="inline-flex items-center gap-1">
                      <button
                        type="button"
                        className={iconBtn}
                        title="编辑"
                        onClick={() => openEditHoldingModal(item)}
                      >
                        ✎
                      </button>
                      <button
                        type="button"
                        className={iconBtn}
                        title="删除"
                        onClick={() => setPendingDeleteHoldingId(itemId)}
                      >
                        ✕
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </>
  );

  return (
    <div className="position-management-bright min-h-screen px-4 py-4 md:px-8 md:py-6">
      <div className="mb-2 flex items-center justify-end">
        <button
          type="button"
          className="mr-2 rounded border border-amber-400/40 px-3 py-1 text-xs text-amber-200 hover:bg-amber-300/10 transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
          onClick={() => void runPortfolioReview()}
          disabled={runningPortfolioReview || loading}
        >
          {runningPortfolioReview ? '生成中...' : '组合复盘'}
        </button>
        <button
          type="button"
          className="rounded border border-cyan/40 px-3 py-1 text-xs text-cyan hover:bg-cyan/15 transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
          onClick={() => void pushDailyReview()}
          disabled={pushingReview || loading}
        >
          {pushingReview ? '推送中...' : '复盘推送'}
        </button>
      </div>
      <Card variant="bordered" padding="md" className="text-left">
        <div className="mb-3 flex items-center justify-between gap-2">
          <div className="flex items-baseline gap-2">
            <span className="label-uppercase">POSITION MANAGEMENT</span>
            <h2 className="text-lg font-semibold text-white mt-0.5">
              {isAssetDetailsPage ? '资产明细' : (isReviewHistoryPage ? '过往复盘' : '仓位管理')}
            </h2>
            <span className="text-[11px] text-muted">更新时间 {String(moduleData.updatedAt ?? moduleData.updated_at ?? '—')}</span>
          </div>
          <div className="flex items-center gap-2">
            {(isAssetDetailsPage || isReviewHistoryPage) && (
              <button
                type="button"
                className="rounded border border-white/20 px-2 py-1 text-xs text-secondary hover:text-white hover:border-cyan/50 transition-colors"
                onClick={() => navigate('/position-management')}
              >
                返回
              </button>
            )}
            <button type="button" className={iconBtn} title="刷新汇率与行情" onClick={() => void refreshAll()} disabled={refreshing || loading}>
              {refreshing ? '…' : '↻'}
            </button>
          </div>
        </div>

        {loading && <div className="text-xs text-muted mb-3">加载中...</div>}
        {loading && !hasModuleLoaded && (
          <div className="space-y-3 mb-3">
            <div className="rounded-xl border border-white/10 p-3 bg-black/20 text-xs text-cyan-200">
              基础信息加载中...
            </div>
            <div className="rounded-xl border border-white/10 p-3 bg-black/20 text-xs text-cyan-200">
              持仓与价格加载中...
            </div>
            <div className="rounded-xl border border-white/10 p-3 bg-black/20 text-xs text-cyan-200">
              资产分布与AI建议加载中...
            </div>
          </div>
        )}
        {!loading || hasModuleLoaded ? (
        <fieldset disabled={formBusy} className="contents">
        {isReviewHistoryPage && (
        <>
        <div className="rounded-xl border border-white/10 p-3 bg-black/20 mb-3">
          <div className="mb-2 flex items-center justify-between">
            <div className="text-xs text-muted">组合复盘历史</div>
            <button
              type="button"
              className="rounded border border-white/20 px-2 py-1 text-xs text-secondary hover:text-white hover:border-cyan/50 transition-colors disabled:opacity-60"
              onClick={() => void loadPortfolioReviewHistory()}
              disabled={loadingPortfolioReviewHistory}
            >
              {loadingPortfolioReviewHistory ? '加载中...' : '刷新'}
            </button>
          </div>
          {loadingPortfolioReviewHistory && <div className="text-xs text-cyan-200">组合复盘历史加载中...</div>}
          {!loadingPortfolioReviewHistory && portfolioReviewHistory.length === 0 && (
            <div className="text-xs text-muted">暂无组合复盘记录，可返回主页面点击「组合复盘」生成。</div>
          )}
          {portfolioTrendRows.length > 1 && (
            <div className="mb-3 grid grid-cols-1 gap-3 lg:grid-cols-2">
              <div className="rounded border border-white/10 bg-black/25 p-3">
                <div className="mb-2 flex items-center justify-between gap-2">
                  <div className="text-[11px] text-muted">总资产趋势</div>
                  <div className="font-mono text-xs text-white">{formatCompactNumber(portfolioTrendLatestValue)} CNY</div>
                </div>
                <svg viewBox="0 0 320 120" className="h-28 w-full rounded border border-white/10 bg-black/20">
                  <polyline fill="none" stroke="#22d3ee" strokeWidth="2.5" points={portfolioValuePolyline} />
                </svg>
                <div className="mt-2 flex items-center justify-between text-[11px] text-secondary">
                  <span>{portfolioTrendStartLabel}</span>
                  <span>近 {portfolioTrendRows.length} 次</span>
                  <span>{portfolioTrendEndLabel}</span>
                </div>
              </div>

              <div className="rounded border border-white/10 bg-black/25 p-3">
                <div className="mb-2 flex items-center justify-between gap-2">
                  <div className="text-[11px] text-muted">健康分趋势</div>
                  <div className="font-mono text-xs text-amber-200">{portfolioTrendLatestHealth.toFixed(0)}</div>
                </div>
                <svg viewBox="0 0 320 120" className="h-28 w-full rounded border border-white/10 bg-black/20">
                  <polyline fill="none" stroke="#f59e0b" strokeWidth="2.5" points={portfolioHealthPolyline} />
                </svg>
                <div className="mt-2 flex items-center justify-between text-[11px] text-secondary">
                  <span>{portfolioTrendStartLabel}</span>
                  <span>近 {portfolioTrendRows.length} 次</span>
                  <span>{portfolioTrendEndLabel}</span>
                </div>
              </div>
            </div>
          )}
          <div className="space-y-3">
            {portfolioReviewHistory.map((item) => {
              const key = getPortfolioReviewKey(item);
              return (
                <div key={`${key}-${String(item.generatedAt || '')}`} className="rounded border border-white/10 p-3 bg-black/25">
                  <div className="mb-2 flex items-center justify-between text-[11px] text-muted">
                    <span>{key || String(item.generatedAt || '未知日期')}</span>
                    <span>{String(item.generatedAt || '')}</span>
                  </div>
                  <div className="mt-3 space-y-3">
                    <PortfolioReviewDetails review={item} sectionKeyPrefix={`portfolio-history-${key}`} />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
        </>
        )}
        {!isAssetDetailsPage && !isReviewHistoryPage && (
        <>
        <div className="rounded-xl border border-white/10 p-3 bg-black/20 mb-3">
          <div className="mb-2 flex items-center justify-between">
            <div className="text-xs text-muted">组合复盘</div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                className="rounded border border-violet-400/25 px-2 py-1 text-[11px] text-violet-100 hover:border-violet-300/45 hover:bg-violet-500/10 transition-colors disabled:cursor-not-allowed disabled:opacity-50"
                onClick={openPortfolioReviewQa}
                disabled={!portfolioReviewChatSeed || loadingPortfolioReview}
              >
                每日复盘答疑
              </button>
              <button
                type="button"
                className="rounded border border-white/20 px-2 py-1 text-[11px] text-secondary hover:text-white hover:border-cyan/50 transition-colors"
                onClick={() => navigate('/position-management/reviews')}
              >
                查看历史
              </button>
              <div className="text-[11px] text-muted">
                {loadingPortfolioReview ? '加载中...' : (portfolioReviewGeneratedAt ? `生成时间 ${portfolioReviewGeneratedAt}` : '暂无记录')}
              </div>
            </div>
          </div>
          <div className="mb-2 text-[11px] text-secondary">
            当前组合复盘默认直接使用仓位管理持仓；仅在仓位管理为空时回退到 `PORTFOLIO_HOLDINGS`。
          </div>
          {!portfolioReview && !loadingPortfolioReview && (
            <div className="text-xs text-muted">暂无组合复盘记录，可点击右上角「组合复盘」生成。</div>
          )}
          {portfolioReview && (
            <div className="space-y-3 text-xs">
              {portfolioTrendRows.length > 1 && (
                <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
                  <div className="rounded border border-white/10 bg-black/25 p-3">
                    <div className="mb-2 flex items-center justify-between gap-2">
                      <div className="text-[11px] text-muted">总资产趋势</div>
                      <div className="font-mono text-xs text-white">{formatCompactNumber(portfolioTrendLatestValue)} CNY</div>
                    </div>
                    <svg viewBox="0 0 320 120" className="h-28 w-full rounded border border-white/10 bg-black/20">
                      <polyline fill="none" stroke="#22d3ee" strokeWidth="2.5" points={portfolioValuePolyline} />
                    </svg>
                    <div className="mt-2 flex items-center justify-between text-[11px] text-secondary">
                      <span>{portfolioTrendStartLabel}</span>
                      <span>近 {portfolioTrendRows.length} 次</span>
                      <span>{portfolioTrendEndLabel}</span>
                    </div>
                  </div>

                  <div className="rounded border border-white/10 bg-black/25 p-3">
                    <div className="mb-2 flex items-center justify-between gap-2">
                      <div className="text-[11px] text-muted">健康分趋势</div>
                      <div className="font-mono text-xs text-amber-200">{portfolioTrendLatestHealth.toFixed(0)}</div>
                    </div>
                    <svg viewBox="0 0 320 120" className="h-28 w-full rounded border border-white/10 bg-black/20">
                      <polyline fill="none" stroke="#f59e0b" strokeWidth="2.5" points={portfolioHealthPolyline} />
                    </svg>
                    <div className="mt-2 flex items-center justify-between text-[11px] text-secondary">
                      <span>{portfolioTrendStartLabel}</span>
                      <span>近 {portfolioTrendRows.length} 次</span>
                      <span>{portfolioTrendEndLabel}</span>
                    </div>
                  </div>
                </div>
              )}
              <PortfolioReviewDetails review={portfolioReview} sectionKeyPrefix="portfolio-current" />
            </div>
          )}
        </div>

        <div className="mb-3 grid grid-cols-1 gap-3 xl:grid-cols-[minmax(0,0.95fr)_minmax(0,1.15fr)]">
          <div className="rounded-2xl border border-white/10 bg-[linear-gradient(180deg,rgba(34,211,238,0.08),rgba(8,16,34,0.72))] p-4">
            <div className="mb-4 flex items-start justify-between gap-3">
              <div>
                <div className="text-[11px] font-semibold tracking-[0.18em] text-cyan-100/80 uppercase">目标达成</div>
                <div className="mt-1 text-sm text-secondary">围绕初始仓位、收益和目标差值集中管理组合目标。</div>
              </div>
              {!editingTarget ? (
                <button type="button" className={iconBtn} title="修改目标参数" onClick={() => setEditingTarget(true)}>✎</button>
              ) : (
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    className="rounded border border-cyan/40 px-3 py-1 text-xs text-cyan hover:bg-cyan/15 transition-colors disabled:opacity-60"
                    onClick={() => void onSaveTarget()}
                    disabled={saving}
                  >
                    保存
                  </button>
                  <button
                    type="button"
                    className="rounded border border-white/20 px-3 py-1 text-xs text-secondary hover:text-white hover:border-cyan/50 transition-colors"
                    onClick={() => {
                      setTargetDraft(target);
                      setEditingTarget(false);
                    }}
                  >
                    取消
                  </button>
                </div>
              )}
            </div>

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div className="rounded-2xl border border-white/10 bg-black/25 p-3">
                <div className="text-[11px] tracking-[0.16em] text-muted uppercase">初始仓位</div>
                <div className="mt-2">
                  {renderMaskableValue(
                    'target-initial-position',
                    `${formatMoneyValue(target.initialPosition)} ${outputCurrencyLabel}`,
                    'font-mono text-xl text-white',
                  )}
                </div>
              </div>
              <div className="rounded-2xl border border-white/10 bg-black/25 p-3">
                <div className="text-[11px] tracking-[0.16em] text-muted uppercase">收益额</div>
                <div className="mt-2">
                  {renderMaskableValue(
                    'target-profit-amount',
                    `${formatMoneyValue(profitAmountValue)} ${outputCurrencyLabel}`,
                    `font-mono text-xl ${profitAmountValue >= 0 ? 'text-success' : 'text-danger'}`,
                  )}
                </div>
              </div>
              <div className="rounded-2xl border border-white/10 bg-black/25 p-3">
                <div className="text-[11px] tracking-[0.16em] text-muted uppercase">收益率</div>
                <div className="mt-2">
                  {renderMaskableValue(
                    'target-profit-pct',
                    `${profitPctValue.toFixed(2)}%`,
                    `font-mono text-xl ${profitPctValue >= 0 ? 'text-success' : 'text-danger'}`,
                  )}
                </div>
              </div>
              <div className="rounded-2xl border border-white/10 bg-black/25 p-3">
                <div className="text-[11px] tracking-[0.16em] text-muted uppercase">距离目标差值</div>
                <div className="mt-2">
                  {renderMaskableValue(
                    'target-gap-value',
                    `${formatMoneyValue(targetGapValue)} ${outputCurrencyLabel}`,
                    `font-mono text-xl ${targetGapValue <= 0 ? 'text-success' : 'text-warning'}`,
                  )}
                </div>
              </div>
            </div>

            {!editingTarget ? (
              <div className="mt-4 text-[11px] text-muted">点击任意数值可切换隐藏；目标收益率和计算币种保留在编辑态配置。</div>
            ) : (
              <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-3 text-xs">
                <>
                  <label className="text-muted">
                    初始仓位
                    <input
                      className="mt-1 w-full rounded border border-white/15 bg-black/30 px-2 py-2 text-xs text-white"
                      type="number"
                      value={targetDraft.initialPosition}
                      onChange={(e) => setTargetDraft((prev) => ({ ...prev, initialPosition: Number(e.target.value) }))}
                      onKeyDown={(e) => {
                        if (e.key !== 'Enter') return;
                        e.preventDefault();
                        void onSaveTarget();
                      }}
                    />
                  </label>
                  <label className="text-muted">
                    目标收益率(%)
                    <input
                      className="mt-1 w-full rounded border border-white/15 bg-black/30 px-2 py-2 text-xs text-white"
                      type="number"
                      value={targetDraft.targetReturnPct}
                      onChange={(e) => setTargetDraft((prev) => ({ ...prev, targetReturnPct: Number(e.target.value) }))}
                      onKeyDown={(e) => {
                        if (e.key !== 'Enter') return;
                        e.preventDefault();
                        void onSaveTarget();
                      }}
                    />
                  </label>
                  <label className="text-muted">
                    计算币种
                    <select
                      className="mt-1 w-full rounded border border-white/15 bg-black/30 px-2 py-2 text-xs text-white"
                      value={targetDraft.outputCurrency}
                      onChange={(e) => setTargetDraft((prev) => ({ ...prev, outputCurrency: e.target.value as PositionManagementTarget['outputCurrency'] }))}
                    >
                      <option value="CNY">RMB</option>
                      <option value="USD">USD</option>
                      <option value="HKD">HKD</option>
                      </select>
                  </label>
                </>
              </div>
            )}
          </div>

          <div className="relative rounded-2xl border border-white/10 bg-[linear-gradient(180deg,rgba(16,185,129,0.08),rgba(8,16,34,0.72))] p-4">
            {hoveredOverviewItem && (
              <div className="pointer-events-none absolute left-1/2 top-0 z-20 w-[min(92%,320px)] -translate-x-1/2 -translate-y-1/2 rounded-2xl border border-emerald-300/30 bg-[#0d1d18]/95 px-4 py-3 shadow-[0_18px_40px_rgba(0,0,0,0.45)] backdrop-blur">
                <div className="text-[11px] font-semibold tracking-[0.18em] text-emerald-100/80 uppercase">当前高亮</div>
                <div className="mt-1 text-base font-semibold text-emerald-50">{hoveredOverviewItem.assetSecondary}</div>
                <div className="mt-2 flex items-center justify-between gap-3 text-xs">
                  <span className="text-secondary">总价值</span>
                  <span className="font-mono text-emerald-100">
                    {getMaskedValueDisplay(
                      `holdings-overview-value-${hoveredOverviewItem.assetSecondary}`,
                      `${formatMoneyValue(hoveredOverviewItem.value)} ${outputCurrencyLabel}`,
                    )}
                  </span>
                </div>
                <div className="mt-1 flex items-center justify-between gap-3 text-xs">
                  <span className="text-secondary">占比总资产</span>
                  <span className="font-mono text-emerald-100">
                    {getMaskedValueDisplay(
                      `holdings-overview-ratio-${hoveredOverviewItem.assetSecondary}`,
                      `${hoveredOverviewItem.ratioPct.toFixed(2)}%`,
                    )}
                  </span>
                </div>
              </div>
            )}
            <div className="mb-4 flex items-start justify-between gap-3">
              <div>
                <div className="text-[11px] font-semibold tracking-[0.18em] text-emerald-100/80 uppercase">持仓概览</div>
                <div className="mt-1 text-sm text-secondary">按二级类目查看当前组合结构，并在主页面直接进入持仓修改。</div>
              </div>
              <button
                type="button"
                className="rounded border border-emerald-400/30 px-3 py-1 text-xs text-emerald-100 hover:bg-emerald-500/10 transition-colors"
                onClick={() => setHoldingsManagerOpen(true)}
              >
                修改持仓
              </button>
            </div>

            <div className="grid grid-cols-1 gap-4 lg:grid-cols-[220px_minmax(0,1fr)]">
              <div className="flex flex-col items-center justify-center rounded-2xl border border-white/10 bg-black/20 p-4">
                <div
                  className="relative h-40 w-40 rounded-full"
                  style={{ background: holdingsOverviewDonut }}
                  onMouseMove={handleOverviewDonutMove}
                  onMouseLeave={() => setHoveredSecondaryCategory(null)}
                >
                  <div className="absolute inset-5 flex flex-col items-center justify-center rounded-full bg-[#081022]">
                    <div className="text-[11px] tracking-[0.16em] text-muted uppercase">总资产</div>
                    <div className="mt-1 text-center">
                      {renderMaskableValue(
                        'holdings-total-asset',
                        formatCompactNumber(asNumber(totals.totalValueOutput ?? totals.total_value_output, 0)),
                        'font-mono text-lg text-white',
                      )}
                    </div>
                    <div className="text-[11px] text-secondary">{outputCurrencyLabel}</div>
                  </div>
                </div>
                <div className="mt-3 flex flex-wrap justify-center gap-2">
                  <span className="inline-flex items-center rounded-full border border-white/10 bg-black/25 px-2.5 py-1 text-[11px] text-secondary">
                    {renderMaskableValue('holdings-overview-category-count', `${holdingsOverviewRows.length} 个二级类目`, 'text-[11px] text-secondary')}
                  </span>
                  <span className="inline-flex items-center rounded-full border border-white/10 bg-black/25 px-2.5 py-1 text-[11px] text-secondary">
                    {renderMaskableValue('holdings-overview-holding-count', `${sortedHoldings.length} 个持仓`, 'text-[11px] text-secondary')}
                  </span>
                </div>
              </div>

              <div className="rounded-2xl border border-white/10 bg-black/20 p-3">
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="border-b border-white/10 text-muted">
                        <th className="py-2 text-left">二级类目</th>
                        <th className="py-2 text-right">总价值({outputCurrencyLabel})</th>
                        <th className="py-2 text-right">占比总资产</th>
                      </tr>
                    </thead>
                    <tbody className="text-secondary">
                      {holdingsOverviewRows.length === 0 && (
                        <tr>
                          <td className="py-3 text-muted" colSpan={3}>暂无资产分布</td>
                        </tr>
                      )}
                      {holdingsOverviewRows.map((item) => {
                        const highlighted = hoveredSecondaryCategory === item.assetSecondary;
                        return (
                          <tr
                            key={`secondary-${item.assetSecondary}`}
                            className={`border-b border-white/5 last:border-b-0 transition-all ${
                              highlighted ? 'bg-emerald-400/10 shadow-[inset_0_0_0_1px_rgba(52,211,153,0.28)]' : ''
                            }`}
                          >
                            <td className={`py-2 ${highlighted ? 'text-emerald-100 text-sm font-semibold' : 'text-white'}`}>{item.assetSecondary}</td>
                            <td className="py-2 text-right">
                              {renderMaskableValue(
                                `holdings-overview-value-${item.assetSecondary}`,
                                formatMoneyValue(item.value),
                                `font-mono ${highlighted ? 'text-emerald-100 text-sm' : 'text-secondary'}`,
                              )}
                            </td>
                            <td className="py-2 text-right">
                              {renderMaskableValue(
                                `holdings-overview-ratio-${item.assetSecondary}`,
                                `${item.ratioPct.toFixed(2)}%`,
                                `font-mono ${highlighted ? 'text-emerald-100 text-sm' : 'text-secondary'}`,
                              )}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          </div>
        </div>
        </>
        )}

        {isAssetDetailsPage && (
        <div className="rounded-xl border border-white/10 p-3 bg-black/20 mb-3">
          <div className="mb-2 flex items-center justify-between">
            <div className="text-xs text-muted">资产明细（录入资产分类 / 代码 / 持仓股数）</div>
            <div className="flex items-center gap-2">
              <button type="button" className={iconBtn} title="新增持仓" onClick={openCreateHoldingModal}>+</button>
              <button
                type="button"
                className={iconBtn}
                title="刷新权益类报价"
                onClick={() => void refreshEquityQuotes()}
                disabled={refreshing}
              >
                {refreshing ? '…' : '↻'}
              </button>
            </div>
          </div>
          {holdingsManagerContent}
        </div>
        )}

        {!isAssetDetailsPage && !isReviewHistoryPage && (
        <>
        <div className="rounded-xl border border-white/10 p-3 bg-black/20 mb-3">
          <div className="text-xs text-muted mb-2">涨跌幅热力图</div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
            {heatmap.length === 0 && <div className="text-xs text-muted">暂无热力图数据</div>}
            {heatmap.map((row, idx) => {
              const change = asNumber(row.changePct ?? row.change_pct, 0);
              const intensity = asNumber(row.intensity, Math.min(1, Math.abs(change) / 8));
              const bg = change >= 0 ? `rgba(239,68,68,${0.12 + intensity * 0.5})` : `rgba(52,211,153,${0.12 + intensity * 0.5})`;
              const displayName = getChineseDisplayName(row.symbol, row.name) || String(row.name ?? row.symbol ?? '-');
              return (
                <div key={`heat-${idx}`} className="rounded p-2 border border-white/10" style={{ backgroundColor: bg }}>
                  <div className="text-xs text-white">{displayName}</div>
                  <div className="text-[11px] text-secondary truncate">{String(row.assetPrimary ?? row.asset_primary ?? '')}</div>
                  <div className={`text-xs font-mono ${change >= 0 ? 'text-danger' : 'text-success'}`}>
                    {change >= 0 ? '+' : ''}{change.toFixed(2)}%
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        </>
        )}
        </fieldset>
        ) : null}
      </Card>
      {holdingsManagerOpen && (
        <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/60 px-4" onClick={() => setHoldingsManagerOpen(false)}>
          <div
            className="w-full max-w-5xl rounded-2xl border border-white/15 bg-[#0b1220] p-4 shadow-2xl"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="mb-3 flex items-center justify-between gap-3">
              <div>
                <div className="text-sm font-medium text-white">持仓修改</div>
                <div className="text-xs text-secondary">在主页面直接管理持仓，增删改逻辑与原资产明细页保持一致。</div>
              </div>
              <div className="flex items-center gap-2">
                <button type="button" className={iconBtn} title="新增持仓" onClick={openCreateHoldingModal}>+</button>
                <button
                  type="button"
                  className={iconBtn}
                  title="刷新权益类报价"
                  onClick={() => void refreshEquityQuotes()}
                  disabled={refreshing}
                >
                  {refreshing ? '…' : '↻'}
                </button>
                <button
                  type="button"
                  className="rounded border border-white/20 px-3 py-1 text-xs text-secondary hover:text-white hover:border-cyan/50 transition-colors"
                  onClick={() => setHoldingsManagerOpen(false)}
                >
                  关闭
                </button>
              </div>
            </div>
            {holdingsManagerContent}
          </div>
        </div>
      )}
      {holdingModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-4">
          <div className="w-full max-w-lg rounded-xl border border-white/15 bg-[#0b1220] p-4">
            <div className="text-sm text-white font-medium">
              {holdingModal.mode === 'create' ? '新增资产明细' : '编辑资产明细'}
            </div>
            <div className="mt-3 grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
              <label className="text-muted">
                一级分类
                <select
                  className="mt-1 w-full rounded border border-white/15 bg-black/30 px-2 py-1 text-xs text-white"
                  value={modalPrimary}
                  onChange={(e) => updateHoldingModalDraft({ assetPrimary: normalizePrimaryAsset(e.target.value) })}
                  onKeyDown={onHoldingModalKeyDown}
                  disabled={saving}
                >
                  {PRIMARY_ASSET_OPTIONS.map((option) => <option key={option} value={option}>{option}</option>)}
                </select>
              </label>
              <label className="text-muted">
                二级分类
                <select
                  className="mt-1 w-full rounded border border-white/15 bg-black/30 px-2 py-1 text-xs text-white"
                  value={normalizeSecondaryAsset(modalPrimary, holdingModal.draft.assetSecondary)}
                  onChange={(e) => updateHoldingModalDraft({ assetSecondary: e.target.value })}
                  onKeyDown={onHoldingModalKeyDown}
                  disabled={saving}
                >
                  {modalSecondaryOptions.map((option) => <option key={option} value={option}>{option}</option>)}
                </select>
              </label>
              <label className="text-muted">
                标的代码
                <input
                  className="mt-1 w-full rounded border border-white/15 bg-black/30 px-2 py-1 text-xs text-white font-mono"
                  value={String(holdingModal.draft.symbol || '')}
                  placeholder={modalPrimary === '现金' ? '现金标识（可选）' : '代码（如 NVDA）'}
                  onChange={(e) => updateHoldingModalDraft({ symbol: e.target.value.toUpperCase() })}
                  onKeyDown={onHoldingModalKeyDown}
                  disabled={saving}
                />
              </label>
              <label className="text-muted">
                持仓数量
                <input
                  className="mt-1 w-full rounded border border-white/15 bg-black/30 px-2 py-1 text-xs text-white text-right"
                  type="number"
                  value={asNumber(holdingModal.draft.quantity, 0)}
                  placeholder={modalPrimary === '现金' ? '现金金额' : '持仓数量'}
                  onChange={(e) => updateHoldingModalDraft({ quantity: Number(e.target.value) })}
                  onKeyDown={onHoldingModalKeyDown}
                  disabled={saving}
                />
              </label>
            </div>
            <div className="mt-4 flex items-center justify-end gap-2">
              <button
                type="button"
                className="rounded border border-white/20 px-3 py-1 text-xs text-secondary hover:text-white hover:border-cyan/50 transition-colors"
                onClick={() => setHoldingModal(null)}
                disabled={saving}
              >
                取消
              </button>
              <button
                type="button"
                className="rounded border border-cyan/45 px-3 py-1 text-xs text-cyan hover:bg-cyan/15 transition-colors disabled:opacity-60"
                onClick={() => void saveHoldingModal()}
                disabled={saving}
              >
                {saving ? '保存中...' : '保存'}
              </button>
            </div>
          </div>
        </div>
      )}
      {pendingDeleteHolding && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-4">
          <div className="w-full max-w-sm rounded-xl border border-white/15 bg-[#0b1220] p-4">
            <div className="text-sm text-white font-medium">确认删除持仓</div>
            <div className="mt-2 text-xs text-secondary leading-5">
              确定删除
              {' '}
              <span className="font-mono text-white">
                {String(pendingDeleteHolding.name || pendingDeleteHolding.symbol || '该持仓')}
              </span>
              {' '}吗？
            </div>
            <div className="mt-3 flex items-center justify-end gap-2">
              <button
                type="button"
                className="rounded border border-white/20 px-3 py-1 text-xs text-secondary hover:text-white hover:border-cyan/50 transition-colors"
                onClick={() => setPendingDeleteHoldingId(null)}
              >
                取消
              </button>
              <button
                type="button"
                className="rounded border border-danger/50 px-3 py-1 text-xs text-danger hover:bg-danger/10 transition-colors"
                onClick={() => void removeHolding(String(pendingDeleteHolding.id || ''))}
              >
                删除
              </button>
            </div>
          </div>
        </div>
      )}
      {toast && (
        <div className="fixed right-4 top-4 z-[60]">
          <div
            className={`rounded-lg border px-3 py-2 text-xs shadow-lg ${
              toast.type === 'success'
                ? 'border-emerald-400/40 bg-emerald-500/15 text-emerald-200'
                : toast.type === 'error'
                  ? 'border-rose-400/40 bg-rose-500/15 text-rose-200'
                  : 'border-cyan/40 bg-cyan/15 text-cyan-100'
            }`}
          >
            {toast.message}
          </div>
        </div>
      )}
    </div>
  );
};

export default PositionManagementPage;

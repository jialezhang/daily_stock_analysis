import type React from 'react';
import { useEffect, useMemo, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { Card } from '../components/common';
import { positionManagementApi } from '../api/positionManagement';
import type {
  PositionDailyReviewPayload,
  PositionHoldingInput,
  PositionManagementTarget,
} from '../types/positionManagement';

type AnyRecord = Record<string, unknown>;
type ToastState = { type: 'success' | 'error' | 'info'; message: string } | null;
type HoldingModalMode = 'create' | 'edit';
type HoldingModalState = {
  mode: HoldingModalMode;
  sourceId: string;
  draft: PositionHoldingInput;
};

const PRIMARY_ASSET_OPTIONS = ['权益类', '加密货币', '贵金属', '债券', '货币基金', '现金'];
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

const extractFirstSentence = (value: unknown): string => {
  const text = String(value || '').replace(/\s+/g, ' ').trim();
  if (!text) return '';
  const matched = text.match(/^(.+?[。！？!?]|.+?$)/);
  return String(matched?.[1] || text).trim();
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
      latestPrice: asNumber(row.latestPrice ?? row.latest_price ?? row.currentPrice ?? row.current_price, 0),
      fxToOutput: asNumber(row.fxToOutput ?? row.fx_to_output, 0),
      marketValueOutput: asNumber(row.marketValueOutput ?? row.market_value_output, 0),
      dailyPnlOutput: asNumber(row.dailyPnlOutput ?? row.daily_pnl_output, 0),
      changePct: asNumber(row.changePct ?? row.change_pct, 0),
    };
  });
};

const parseStringList = (value: unknown): string[] => {
  if (!Array.isArray(value)) return [];
  return value.map((item) => String(item || '').trim()).filter(Boolean);
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
  const [holdingModal, setHoldingModal] = useState<HoldingModalState | null>(null);
  const [pendingDeleteHoldingId, setPendingDeleteHoldingId] = useState<string | null>(null);
  const [macroEventsText, setMacroEventsText] = useState('');
  const [notes, setNotes] = useState('');
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [pushingReview, setPushingReview] = useState(false);
  const [toast, setToast] = useState<ToastState>(null);
  const [dailyReview, setDailyReview] = useState<PositionDailyReviewPayload | null>(null);
  const [loadingDailyReview, setLoadingDailyReview] = useState(false);
  const [reviewHistory, setReviewHistory] = useState<PositionDailyReviewPayload[]>([]);
  const [loadingReviewHistory, setLoadingReviewHistory] = useState(false);
  const [reviewNoteDraftMap, setReviewNoteDraftMap] = useState<Record<string, string>>({});
  const [savingReviewNoteKey, setSavingReviewNoteKey] = useState<string | null>(null);
  const [reviewExpanded, setReviewExpanded] = useState(false);

  const getReviewKey = (review: PositionDailyReviewPayload | null | undefined): string => {
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
    setMacroEventsText(parseStringList(module.macroEvents ?? module.macro_events).join('\n'));
    setNotes(String(module.notes ?? ''));
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

  const loadLatestDailyReview = async () => {
    setLoadingDailyReview(true);
    try {
      const response = await positionManagementApi.getLatestDailyReview();
      const nextReview = response.found ? (response.dailyReview || null) : null;
      setDailyReview(nextReview);
      const key = getReviewKey(nextReview);
      if (key) {
        setReviewNoteDraftMap((prev) => ({
          ...prev,
          [key]: String(nextReview?.note || ''),
        }));
      }
    } catch {
      setDailyReview(null);
    } finally {
      setLoadingDailyReview(false);
    }
  };

  const loadReviewHistory = async () => {
    setLoadingReviewHistory(true);
    try {
      const response = await positionManagementApi.getReviewHistory(180);
      const rows = Array.isArray(response.reviews) ? response.reviews : [];
      setReviewHistory(rows);
      setReviewNoteDraftMap((prev) => {
        const next = { ...prev };
        rows.forEach((item) => {
          const key = getReviewKey(item);
          if (!key) return;
          if (!(key in next)) {
            next[key] = String(item.note || '');
          }
        });
        return next;
      });
    } catch (err) {
      setToast({ type: 'error', message: err instanceof Error ? err.message : '加载复盘历史失败' });
      setReviewHistory([]);
    } finally {
      setLoadingReviewHistory(false);
    }
  };

  const saveReviewNote = async (reviewDate: string) => {
    const key = String(reviewDate || '').trim();
    if (!key) return;
    setSavingReviewNoteKey(key);
    try {
      const note = String(reviewNoteDraftMap[key] || '');
      const response = await positionManagementApi.saveReviewNote(key, note);
      setToast({ type: 'success', message: response.message || '批注已保存' });
      setDailyReview((prev) => {
        if (!prev || getReviewKey(prev) !== key) return prev;
        return { ...prev, note };
      });
      setReviewHistory((prev) =>
        prev.map((item) => (getReviewKey(item) === key ? { ...item, note } : item)),
      );
    } catch (err) {
      setToast({ type: 'error', message: '保存复盘批注失败，请稍后重试' });
    } finally {
      setSavingReviewNoteKey(null);
    }
  };

  useEffect(() => {
    if (isReviewHistoryPage) {
      void loadReviewHistory();
      return;
    }
    void loadModule();
    if (!isAssetDetailsPage) {
      void loadLatestDailyReview();
    }
  }, [isAssetDetailsPage, isReviewHistoryPage]);

  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast(null), toast.type === 'success' ? 3000 : 2400);
    return () => window.clearTimeout(timer);
  }, [toast]);

  useEffect(() => {
    setReviewExpanded(false);
  }, [dailyReview?.generatedAt]);

  const derived = asRecord(moduleData.derived);
  const totals = asRecord(derived.totals);
  const progress = asRecord(derived.targetProgress ?? derived.target_progress);
  const allocation = (Array.isArray(derived.allocation) ? derived.allocation : []) as AnyRecord[];
  const heatmap = useMemo(() => {
    const rows = (Array.isArray(derived.heatmap) ? derived.heatmap : []) as AnyRecord[];
    return [...rows].sort(
      (a, b) =>
        asNumber(b.changePct ?? b.change_pct, 0) - asNumber(a.changePct ?? a.change_pct, 0),
    );
  }, [derived.heatmap]);
  const fx = asRecord(moduleData.fx);
  const donutBackground = useMemo(() => buildDonut(allocation), [allocation]);

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
        macroEvents: macroEventsText.split('\n').map((item) => item.trim()).filter(Boolean),
        notes,
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
      if (response.dailyReview) {
        setDailyReview(response.dailyReview);
        const key = getReviewKey(response.dailyReview);
        if (key) {
          setReviewNoteDraftMap((prev) => ({
            ...prev,
            [key]: String(response.dailyReview?.note || ''),
          }));
        }
      } else if (!isAssetDetailsPage) {
        await loadLatestDailyReview();
      }
      if (isReviewHistoryPage) {
        await loadReviewHistory();
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : '复盘推送失败';
      setToast({ type: 'error', message: msg });
    } finally {
      setPushingReview(false);
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

  const outputCurrency = String(target.outputCurrency || 'USD').toUpperCase();
  const hasModuleLoaded = Object.keys(moduleData).length > 0;
  const iconBtn = 'inline-flex items-center justify-center w-7 h-7 rounded border border-white/20 text-xs text-secondary hover:text-white hover:border-cyan/50 transition-colors';
  const pendingDeleteHolding = holdings.find((item) => item.id === pendingDeleteHoldingId) || null;
  const formBusy = loading || saving || refreshing;
  const modalPrimary = holdingModal ? normalizePrimaryAsset(holdingModal.draft.assetPrimary) : '权益类';
  const modalSecondaryOptions = SECONDARY_ASSET_MAP[modalPrimary] || ['其他'];
  const reviewSections = asRecord(dailyReview?.sections);
  const reviewGeneratedAt = String(dailyReview?.generatedAt || '');
  const reviewFilePath = String(dailyReview?.filePath || '');
  const reviewSummary = extractFirstSentence(
    reviewSections.targetTracking || reviewSections.riskWarning || reviewSections.macroCrossMarket || reviewSections.gridReference || '',
  );

  return (
    <div className="position-management-bright min-h-screen px-4 py-4 md:px-8 md:py-6">
      <div className="mb-2 flex items-center justify-end">
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
        <div className="rounded-xl border border-white/10 p-3 bg-black/20 mb-3">
          <div className="mb-2 flex items-center justify-between">
            <div className="text-xs text-muted">每日资产管理复盘历史</div>
            <button
              type="button"
              className="rounded border border-white/20 px-2 py-1 text-xs text-secondary hover:text-white hover:border-cyan/50 transition-colors disabled:opacity-60"
              onClick={() => void loadReviewHistory()}
              disabled={loadingReviewHistory}
            >
              {loadingReviewHistory ? '加载中...' : '刷新'}
            </button>
          </div>
          {loadingReviewHistory && <div className="text-xs text-cyan-200">复盘历史加载中...</div>}
          {!loadingReviewHistory && reviewHistory.length === 0 && (
            <div className="text-xs text-muted">暂无复盘记录，可返回主页面点击「复盘推送」生成。</div>
          )}
          <div className="space-y-3">
            {reviewHistory.map((item) => {
              const key = getReviewKey(item);
              const sections = asRecord(item.sections);
              return (
                <div key={`${key}-${String(item.filePath || '')}`} className="rounded border border-white/10 p-3 bg-black/25">
                  <div className="mb-2 flex items-center justify-between text-[11px] text-muted">
                    <span>{key || String(item.generatedAt || '未知日期')}</span>
                    <span>{String(item.generatedAt || '')}</span>
                  </div>
                  <div className="space-y-2 text-xs">
                    <div>
                      <div className="text-cyan-100 mb-1">### 🌪️ 宏观与跨市场风向</div>
                      <div className="text-secondary leading-5">{String(sections.macroCrossMarket || '—')}</div>
                    </div>
                    <div>
                      <div className="text-cyan-100 mb-1">### 📊 组合偏离度与目标追踪</div>
                      <div className="text-secondary leading-5">{String(sections.targetTracking || '—')}</div>
                    </div>
                    <div>
                      <div className="text-cyan-100 mb-1">### 💡 行动与网格策略建议</div>
                      <div className="text-secondary leading-5">
                        <div>- <span className="text-white">风险预警：</span>{String(sections.riskWarning || '—')}</div>
                        <div>- <span className="text-white">网格/区间操作参考：</span>{String(sections.gridReference || '—')}</div>
                      </div>
                    </div>
                    <div>
                      <div className="text-xs text-muted mb-1">批注</div>
                      <div className="flex items-start gap-2">
                        <textarea
                          className="flex-1 h-20 rounded border border-white/15 bg-black/30 px-2 py-1 text-xs text-white"
                          value={String(reviewNoteDraftMap[key] ?? item.note ?? '')}
                          onChange={(e) => setReviewNoteDraftMap((prev) => ({ ...prev, [key]: e.target.value }))}
                          placeholder="可填写当日复盘批注..."
                        />
                        <button
                          type="button"
                          className="rounded border border-white/20 px-2 py-1 text-xs text-secondary hover:text-white hover:border-cyan/50 transition-colors disabled:opacity-60"
                          onClick={() => void saveReviewNote(key)}
                          disabled={!key || savingReviewNoteKey === key}
                        >
                          {savingReviewNoteKey === key ? '保存中...' : '保存批注'}
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
        )}
        {!isAssetDetailsPage && !isReviewHistoryPage && (
        <>
        <div className="rounded-xl border border-white/10 p-3 bg-black/20 mb-3">
          <div className="mb-2 flex items-center justify-between">
            <div className="text-xs text-muted">每日资产管理复盘</div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                className="rounded border border-white/20 px-2 py-1 text-[11px] text-secondary hover:text-white hover:border-cyan/50 transition-colors"
                onClick={() => navigate('/position-management/reviews')}
              >
                查看过往复盘
              </button>
              <div className="text-[11px] text-muted">
                {loadingDailyReview ? '加载中...' : (reviewGeneratedAt ? `生成时间 ${reviewGeneratedAt}` : '暂无记录')}
              </div>
            </div>
          </div>
          {!dailyReview && !loadingDailyReview && (
            <div className="text-xs text-muted">暂无本地复盘记录，可点击右上角「复盘推送」生成。</div>
          )}
          {dailyReview && (
            <div className="space-y-3 text-xs">
              <div className="rounded border border-white/10 bg-black/25 p-2">
                <div className="flex items-start justify-between gap-2">
                  <div className="text-secondary leading-5">{reviewSummary || '—'}</div>
                  <button
                    type="button"
                    className="shrink-0 rounded border border-white/20 px-2 py-0.5 text-[11px] text-secondary hover:text-white hover:border-cyan/50 transition-colors"
                    onClick={() => setReviewExpanded((prev) => !prev)}
                  >
                    {reviewExpanded ? '收起' : '展开'}
                  </button>
                </div>
              </div>
              {reviewExpanded && (
                <>
                  <div>
                    <div className="text-cyan-100 mb-1">### 🌪️ 宏观与跨市场风向</div>
                    <div className="text-secondary leading-5 whitespace-pre-wrap">{String(reviewSections.macroCrossMarket || '—')}</div>
                  </div>
                  <div>
                    <div className="text-cyan-100 mb-1">### 📊 组合偏离度与目标追踪</div>
                    <div className="text-secondary leading-5 whitespace-pre-wrap">{String(reviewSections.targetTracking || '—')}</div>
                  </div>
                  <div>
                    <div className="text-cyan-100 mb-1">### 💡 行动与网格策略建议</div>
                    <div className="text-secondary leading-5 whitespace-pre-wrap">
                      <div>- <span className="text-white">风险预警：</span>{String(reviewSections.riskWarning || '—')}</div>
                      <div>- <span className="text-white">网格/区间操作参考：</span>{String(reviewSections.gridReference || '—')}</div>
                    </div>
                  </div>
                </>
              )}
              {reviewFilePath && (
                <div className="text-[11px] text-muted font-mono break-all">本地Markdown：{reviewFilePath}</div>
              )}
              <div>
                <div className="text-xs text-muted mb-1">批注</div>
                <div className="flex items-start gap-2">
                  <textarea
                    className="flex-1 h-20 rounded border border-white/15 bg-black/30 px-2 py-1 text-xs text-white"
                    value={String(reviewNoteDraftMap[getReviewKey(dailyReview)] ?? dailyReview.note ?? '')}
                    onChange={(e) => setReviewNoteDraftMap((prev) => ({ ...prev, [getReviewKey(dailyReview)]: e.target.value }))}
                    placeholder="可填写当日复盘批注..."
                  />
                  <button
                    type="button"
                    className="rounded border border-white/20 px-2 py-1 text-xs text-secondary hover:text-white hover:border-cyan/50 transition-colors disabled:opacity-60"
                    onClick={() => void saveReviewNote(getReviewKey(dailyReview))}
                    disabled={!getReviewKey(dailyReview) || savingReviewNoteKey === getReviewKey(dailyReview)}
                  >
                    {savingReviewNoteKey === getReviewKey(dailyReview) ? '保存中...' : '保存批注'}
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>

        <div className="rounded-xl border border-white/10 p-3 bg-black/20 mb-3">
          <div className="mb-2 flex items-center justify-between">
            <div className="text-xs text-muted">基础信息</div>
            {!editingTarget ? (
              <button type="button" className={iconBtn} title="修改基础信息" onClick={() => setEditingTarget(true)}>✎</button>
            ) : (
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  className="rounded border border-white/20 px-2 py-1 text-xs text-secondary hover:text-white hover:border-cyan/50 transition-colors"
                  title="保存"
                  onClick={() => void onSaveTarget()}
                  disabled={saving}
                >
                  保存
                </button>
                <button
                  type="button"
                  className="rounded border border-white/20 px-2 py-1 text-xs text-secondary hover:text-white hover:border-cyan/50 transition-colors"
                  title="取消"
                  onClick={() => {
                    setTargetDraft(target);
                    setEditingTarget(false);
                  }}
                >
                  ✕
                </button>
              </div>
            )}
          </div>

          {!editingTarget ? (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-2 text-xs">
              <div className="rounded border border-white/10 p-2">
                <div className="text-muted">初始仓位</div>
                <div className="text-white font-mono">{target.initialPosition.toFixed(2)} {outputCurrency}</div>
              </div>
              <div className="rounded border border-white/10 p-2">
                <div className="text-muted">输出币种</div>
                <div className="text-white font-mono">{outputCurrency}</div>
              </div>
              <div className="rounded border border-white/10 p-2">
                <div className="text-muted">目标收益率</div>
                <div className="text-white font-mono">{target.targetReturnPct.toFixed(2)}%</div>
              </div>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-2 text-xs">
              <label className="text-muted">
                初始仓位
                <input
                  className="mt-1 w-full rounded border border-white/15 bg-black/30 px-2 py-1 text-xs text-white"
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
                输出币种
                <select
                  className="mt-1 w-full rounded border border-white/15 bg-black/30 px-2 py-1 text-xs text-white"
                  value={targetDraft.outputCurrency}
                  onChange={(e) => setTargetDraft((prev) => ({ ...prev, outputCurrency: e.target.value as PositionManagementTarget['outputCurrency'] }))}
                >
                  <option value="USD">USD</option>
                  <option value="CNY">RMB</option>
                  <option value="HKD">HKD</option>
                </select>
              </label>
              <label className="text-muted">
                目标收益率(%)
                <input
                  className="mt-1 w-full rounded border border-white/15 bg-black/30 px-2 py-1 text-xs text-white"
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
            </div>
          )}

          <div className="grid grid-cols-1 md:grid-cols-4 gap-2 mt-3 text-xs">
            <div className="rounded border border-white/10 p-2">
              <div className="text-muted">USD/CNY</div>
              <div className="font-mono text-cyan">{asNumber(fx.usdCny ?? fx.usd_cny, 0).toFixed(6)}</div>
            </div>
            <div className="rounded border border-white/10 p-2">
              <div className="text-muted">HKD/CNY</div>
              <div className="font-mono text-cyan">{asNumber(fx.hkdCny ?? fx.hkd_cny, 0).toFixed(6)}</div>
            </div>
            <div className="rounded border border-white/10 p-2">
              <div className="text-muted">收益额（{outputCurrency}）</div>
              <div className={`font-mono ${asNumber(totals.profitAmountOutput ?? totals.profit_amount_output, 0) >= 0 ? 'text-success' : 'text-danger'}`}>
                {asNumber(totals.profitAmountOutput ?? totals.profit_amount_output, 0).toFixed(2)}
              </div>
            </div>
            <div className="rounded border border-white/10 p-2">
              <div className="text-muted">收益率</div>
              <div className={`font-mono ${asNumber(totals.profitPct ?? totals.profit_pct, 0) >= 0 ? 'text-success' : 'text-danger'}`}>
                {asNumber(totals.profitPct ?? totals.profit_pct, 0).toFixed(2)}%
              </div>
            </div>
          </div>
        </div>

        <div className="rounded-xl border border-white/10 p-3 bg-black/20 mb-3">
          <div className="mb-2 flex items-center justify-between">
            <div className="text-xs text-muted">仓位分布</div>
            <button
              type="button"
              className="rounded border border-white/20 px-2 py-1 text-xs text-secondary hover:text-white hover:border-cyan/50 transition-colors"
              onClick={() => navigate('/position-management/assets')}
            >
              资产明细
            </button>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-muted border-b border-white/10">
                  <th className="text-left py-1">二级类目</th>
                  <th className="text-right py-1">总价值({outputCurrency})</th>
                  <th className="text-right py-1">占比总资产</th>
                </tr>
              </thead>
              <tbody className="text-secondary">
                {secondaryDistributions.length === 0 && (
                  <tr>
                    <td className="py-2 text-muted" colSpan={3}>暂无资产分布</td>
                  </tr>
                )}
                {secondaryDistributions.map((item) => (
                  <tr key={`secondary-${item.assetSecondary}`} className="border-b border-white/5">
                    <td className="py-2">{item.assetSecondary}</td>
                    <td className="py-2 text-right font-mono">{Math.round(item.value).toLocaleString()}</td>
                    <td className="py-2 text-right font-mono">{item.ratioPct.toFixed(2)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
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
                  <th className="text-right py-1">总价值({outputCurrency})</th>
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
        </div>
        )}

        {!isAssetDetailsPage && !isReviewHistoryPage && (
        <>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-3 mb-3">
          <div className="rounded-xl border border-white/10 p-3 bg-black/20">
            <div className="text-xs text-muted mb-2">资产分布总览</div>
            <div className="flex items-center gap-3">
              <div className="relative h-28 w-28 rounded-full" style={{ background: donutBackground }}>
                <div className="absolute inset-4 rounded-full bg-[#081022]" />
              </div>
              <div className="flex-1 space-y-1">
                {allocation.map((row, idx) => (
                  <div key={`alloc-${idx}`} className="text-xs flex items-center justify-between gap-2">
                    <span>{String(row.assetPrimary ?? row.asset_primary ?? '其他')}</span>
                    <span className="font-mono">{asNumber(row.ratioPct ?? row.ratio_pct, 0).toFixed(2)}%</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="rounded-xl border border-white/10 p-3 bg-black/20 lg:col-span-2">
            <div className="text-xs text-muted mb-2">目标收益进度</div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
              <div className="rounded border border-white/10 p-2"><div className="text-muted">组合总市值</div><div className="font-mono text-white">{asNumber(totals.totalValueOutput ?? totals.total_value_output, 0).toFixed(2)} {outputCurrency}</div></div>
              <div className="rounded border border-white/10 p-2"><div className="text-muted">目标总市值</div><div className="font-mono text-cyan">{asNumber(progress.targetValueOutput ?? progress.target_value_output, 0).toFixed(2)} {outputCurrency}</div></div>
              <div className="rounded border border-white/10 p-2"><div className="text-muted">距离目标</div><div className={`font-mono ${asNumber(progress.gapToTargetOutput ?? progress.gap_to_target_output, 0) <= 0 ? 'text-success' : 'text-warning'}`}>{asNumber(progress.gapToTargetOutput ?? progress.gap_to_target_output, 0).toFixed(2)} {outputCurrency}</div></div>
              <div className="rounded border border-white/10 p-2"><div className="text-muted">目标完成度</div><div className="font-mono text-white">{asNumber(progress.targetProgressPct ?? progress.target_progress_pct, 0).toFixed(2)}%</div></div>
            </div>
          </div>
        </div>

        <div className="rounded-xl border border-white/10 p-3 bg-black/20 mb-3">
          <div className="text-xs text-muted mb-2">涨跌幅热力图</div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
            {heatmap.length === 0 && <div className="text-xs text-muted">暂无热力图数据</div>}
            {heatmap.map((row, idx) => {
              const change = asNumber(row.changePct ?? row.change_pct, 0);
              const intensity = asNumber(row.intensity, Math.min(1, Math.abs(change) / 8));
              const bg = change >= 0 ? `rgba(239,68,68,${0.12 + intensity * 0.5})` : `rgba(52,211,153,${0.12 + intensity * 0.5})`;
              return (
                <div key={`heat-${idx}`} className="rounded p-2 border border-white/10" style={{ backgroundColor: bg }}>
                  <div className="text-xs text-white font-mono">{String(row.symbol ?? '-')}</div>
                  <div className="text-[11px] text-secondary truncate">{String(row.name ?? '')}</div>
                  <div className={`text-xs font-mono ${change >= 0 ? 'text-danger' : 'text-success'}`}>
                    {change >= 0 ? '+' : ''}{change.toFixed(2)}%
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
          <div className="rounded-xl border border-white/10 p-3 bg-black/20">
            <div className="text-xs text-muted mb-1">宏观/地缘事件（每行一条）</div>
            <textarea
              className="w-full h-24 rounded border border-white/15 bg-black/30 px-2 py-1 text-xs text-white"
              value={macroEventsText}
              onChange={(e) => setMacroEventsText(e.target.value)}
              placeholder="例如：美联储利率路径、地缘冲突、原油波动..."
            />
          </div>
          <div className="rounded-xl border border-white/10 p-3 bg-black/20">
            <div className="text-xs text-muted mb-1">备注</div>
            <textarea
              className="w-full h-24 rounded border border-white/15 bg-black/30 px-2 py-1 text-xs text-white"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="每日复盘备注、仓位纪律、再平衡阈值..."
            />
          </div>
        </div>
        </>
        )}
        </fieldset>
        ) : null}
      </Card>
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

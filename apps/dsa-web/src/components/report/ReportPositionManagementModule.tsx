import type React from 'react';
import { useEffect, useMemo, useState } from 'react';
import { Card } from '../common';
import { historyApi } from '../../api/history';
import type {
  PositionHoldingInput,
  PositionManagementTarget,
  ReportDetails as ReportDetailsType,
} from '../../types/analysis';
import type { ModuleRefreshState } from '../../utils/moduleRefresh';

interface ReportPositionManagementModuleProps {
  details?: ReportDetailsType;
  recordId?: number;
  onRefreshModule?: () => void;
  isRefreshing?: boolean;
  refreshState?: ModuleRefreshState;
  updatedAt?: string | null;
}

type AnyRecord = Record<string, unknown>;
type NoticeState = { type: 'success' | 'error' | 'info'; message: string } | null;

const defaultTarget: PositionManagementTarget = {
  annualReturnTargetPct: 30,
  baseCurrency: 'USD',
  usdCny: 7.2,
  usdHkd: 7.8,
};

const marketOptions = [
  { value: 'a_share', label: 'A股' },
  { value: 'hk', label: '港股' },
  { value: 'us', label: '美股' },
  { value: 'crypto', label: '加密货币' },
  { value: 'money_fund', label: '货币基金' },
  { value: 'other', label: '其他' },
];

const assetOptions = ['A股', '港股', '美股', '加密货币', '货币基金', '其他'];
const currencyOptions = ['USD', 'CNY', 'HKD'] as const;

const asRecord = (value: unknown): AnyRecord => {
  return value && typeof value === 'object' ? (value as AnyRecord) : {};
};

const toNumber = (value: unknown, fallback = 0): number => {
  const num = Number(value);
  return Number.isFinite(num) ? num : fallback;
};

const readPositionModule = (details?: ReportDetailsType): AnyRecord | null => {
  if (!details) return null;
  const raw = asRecord(details.rawResult);
  const fromRaw = asRecord(raw.positionManagement ?? raw.position_management);
  if (Object.keys(fromRaw).length > 0) return fromRaw;

  const snapshot = asRecord(details.contextSnapshot);
  const enhanced = asRecord(snapshot.enhancedContext ?? snapshot.enhanced_context);
  const fromContext = asRecord(enhanced.positionManagement ?? enhanced.position_management);
  if (Object.keys(fromContext).length > 0) return fromContext;

  return null;
};

const inferAssetClass = (marketType: string): string => {
  switch ((marketType || '').toLowerCase()) {
    case 'a_share':
    case 'cn':
      return 'A股';
    case 'hk':
      return '港股';
    case 'us':
      return '美股';
    case 'crypto':
      return '加密货币';
    case 'money_fund':
      return '货币基金';
    default:
      return '其他';
  }
};

const parseTarget = (module: AnyRecord | null): PositionManagementTarget => {
  const target = asRecord(module?.target);
  return {
    annualReturnTargetPct: toNumber(target.annualReturnTargetPct ?? target.annual_return_target_pct, 30),
    baseCurrency: String(target.baseCurrency ?? target.base_currency ?? 'USD').toUpperCase() === 'CNY' ? 'CNY' : 'USD',
    usdCny: toNumber(target.usdCny ?? target.usd_cny, 7.2),
    usdHkd: toNumber(target.usdHkd ?? target.usd_hkd, 7.8),
  };
};

const parseHoldings = (module: AnyRecord | null): PositionHoldingInput[] => {
  const rows = Array.isArray(module?.holdings) ? module?.holdings : [];
  return rows.map((item, idx) => {
    const row = asRecord(item);
    const marketType = String(row.marketType ?? row.market_type ?? 'other');
    const symbol = String(row.symbol ?? '').toUpperCase();
    return {
      id: String(row.id ?? `holding-${idx + 1}`),
      marketType,
      assetClass: String(row.assetClass ?? row.asset_class ?? inferAssetClass(marketType)),
      symbol,
      name: String(row.name ?? symbol),
      quantity: toNumber(row.quantity, 0),
      avgCost: toNumber(row.avgCost ?? row.avg_cost, 0),
      currentPrice: toNumber(row.currentPrice ?? row.current_price, 0),
      previousClose: toNumber(row.previousClose ?? row.previous_close, 0) || undefined,
      currency: (String(row.currency ?? 'USD').toUpperCase() as PositionHoldingInput['currency']),
    };
  });
};

const parseStringList = (value: unknown): string[] => {
  if (!Array.isArray(value)) return [];
  return value
    .map((item) => String(item || '').trim())
    .filter(Boolean);
};

const buildDonut = (allocation: AnyRecord[]): string => {
  if (!allocation.length) return 'conic-gradient(rgba(255,255,255,0.14) 0deg 360deg)';
  const colors = ['#22d3ee', '#34d399', '#f59e0b', '#f97316', '#f43f5e', '#a78bfa', '#60a5fa'];
  let start = 0;
  const parts = allocation.map((item, idx) => {
    const ratio = Math.max(0, Math.min(100, toNumber(item.ratioPct ?? item.ratio_pct, 0)));
    const end = start + ratio * 3.6;
    const seg = `${colors[idx % colors.length]} ${start}deg ${end}deg`;
    start = end;
    return seg;
  });
  if (start < 360) parts.push(`rgba(255,255,255,0.08) ${start}deg 360deg`);
  return `conic-gradient(${parts.join(', ')})`;
};

const buildPolyline = (points: AnyRecord[], width: number, height: number, minVal: number, maxVal: number): string => {
  if (points.length <= 0) return '';
  const safeRange = maxVal - minVal || 1;
  return points
    .map((point, idx) => {
      const x = points.length <= 1 ? width / 2 : (idx / (points.length - 1)) * width;
      const val = toNumber(point.value, 0);
      const y = height - ((val - minVal) / safeRange) * height;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(' ');
};

export const ReportPositionManagementModule: React.FC<ReportPositionManagementModuleProps> = ({
  details,
  recordId,
  onRefreshModule,
  isRefreshing = false,
  refreshState = 'idle',
  updatedAt,
}) => {
  const [moduleData, setModuleData] = useState<AnyRecord | null>(null);
  const [target, setTarget] = useState<PositionManagementTarget>(defaultTarget);
  const [holdings, setHoldings] = useState<PositionHoldingInput[]>([]);
  const [macroEventsText, setMacroEventsText] = useState('');
  const [notes, setNotes] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [isDirty, setIsDirty] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [notice, setNotice] = useState<NoticeState>(null);

  useEffect(() => {
    const module = readPositionModule(details);
    setModuleData(module);
    setTarget(parseTarget(module));
    setHoldings(parseHoldings(module));
    setMacroEventsText(parseStringList(module?.macroEvents ?? module?.macro_events).join('\n'));
    setNotes(String(module?.notes ?? ''));
    setIsDirty(false);
    setSaveError(null);
  }, [details]);

  useEffect(() => {
    if (!notice) return;
    const timer = window.setTimeout(() => setNotice(null), 2400);
    return () => window.clearTimeout(timer);
  }, [notice]);

  const derived = asRecord(moduleData?.derived);
  const totals = asRecord(derived.totals);
  const progress = asRecord(derived.targetProgress ?? derived.target_progress);
  const allocation = Array.isArray(derived.allocation) ? (derived.allocation as AnyRecord[]) : [];
  const heatmap = useMemo(() => {
    const rows = Array.isArray(derived.heatmap) ? (derived.heatmap as AnyRecord[]) : [];
    return [...rows].sort(
      (a, b) => toNumber(b.changePct ?? b.change_pct, 0) - toNumber(a.changePct ?? a.change_pct, 0),
    );
  }, [derived.heatmap]);
  const benchmark = asRecord(derived.benchmarkComparison ?? derived.benchmark_comparison);
  const aiWind = asRecord(derived.aiMarketWind ?? derived.ai_market_wind);
  const benchmarkSeries = (Array.isArray(benchmark.series) ? benchmark.series : []) as AnyRecord[];
  const benchmarkPoints = benchmarkSeries.flatMap((row) => (
    (Array.isArray(row.points) ? row.points : []) as AnyRecord[]
  ));
  const minBench = benchmarkPoints.length > 0
    ? Math.min(...benchmarkPoints.map((row) => toNumber(row.value, 0)))
    : -10;
  const maxBench = benchmarkPoints.length > 0
    ? Math.max(...benchmarkPoints.map((row) => toNumber(row.value, 0)))
    : 10;
  const donutBackground = useMemo(() => buildDonut(allocation), [allocation]);

  const onAddHolding = () => {
    setHoldings((prev) => [
      ...prev,
      {
        id: `manual-${Date.now()}`,
        marketType: 'us',
        assetClass: '美股',
        symbol: '',
        name: '',
        quantity: 0,
        avgCost: 0,
        currentPrice: 0,
        currency: 'USD',
      },
    ]);
    setIsDirty(true);
  };

  const onDeleteHolding = (id?: string) => {
    setHoldings((prev) => prev.filter((item) => item.id !== id));
    setIsDirty(true);
  };

  const onUpdateHolding = (id: string | undefined, patch: Partial<PositionHoldingInput>) => {
    setHoldings((prev) => prev.map((row) => {
      if (row.id !== id) return row;
      const next = { ...row, ...patch };
      if (patch.marketType && !patch.assetClass) {
        next.assetClass = inferAssetClass(patch.marketType);
      }
      return next;
    }));
    setIsDirty(true);
  };

  const refreshText = refreshState === 'queued'
    ? '排队中...'
    : refreshState === 'running'
      ? '更新中...'
      : refreshState === 'succeeded'
        ? '已更新'
        : refreshState === 'failed'
          ? '重试更新'
          : '更新';

  const saveModule = async (): Promise<void> => {
    if (!recordId) return;
    setIsSaving(true);
    setSaveError(null);
    setNotice({ type: 'info', message: '保存中...' });
    try {
      const response = await historyApi.upsertPositionManagement(recordId, {
        target,
        holdings,
        macroEvents: macroEventsText.split('\n').map((s) => s.trim()).filter(Boolean),
        notes,
        refreshBenchmarks: true,
      });
      const nextModule = asRecord(response.module);
      setModuleData(nextModule);
      setTarget(parseTarget(nextModule));
      setHoldings(parseHoldings(nextModule));
      setMacroEventsText(parseStringList(nextModule.macroEvents ?? nextModule.macro_events).join('\n'));
      setNotes(String(nextModule.notes ?? ''));
      setIsDirty(false);
      setNotice({ type: 'success', message: '保存成功' });
    } catch (error) {
      const msg = error instanceof Error ? error.message : '保存失败';
      setSaveError(msg);
      setNotice({ type: 'error', message: msg });
    } finally {
      setIsSaving(false);
    }
  };

  const onFieldKeyDown = (event: React.KeyboardEvent<HTMLInputElement | HTMLSelectElement>): void => {
    if (event.key !== 'Enter' || isSaving || !recordId) return;
    event.preventDefault();
    void saveModule();
  };

  const onTextareaKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>): void => {
    if (event.key !== 'Enter' || !event.ctrlKey || isSaving || !recordId) return;
    event.preventDefault();
    void saveModule();
  };

  return (
    <Card variant="bordered" padding="md" className="text-left">
      <div className="mb-3 flex items-center justify-between gap-2">
        <div className="flex items-baseline gap-2">
          <span className="label-uppercase">POSITION MGMT</span>
          <h3 className="text-base font-semibold text-white mt-0.5">仓位管理</h3>
          <span className="text-[11px] text-muted">更新于 {updatedAt || '未更新'}</span>
          {isDirty && <span className="text-[11px] text-warning">有未保存修改</span>}
        </div>
        <div className="flex items-center gap-3">
          <button
            type="button"
            className="text-xs text-cyan hover:text-white transition-colors"
            onClick={onRefreshModule}
            disabled={isRefreshing}
          >
            {refreshText}
          </button>
          <button
            type="button"
            className="text-xs text-emerald-300 hover:text-white transition-colors disabled:text-muted"
            onClick={() => void saveModule()}
            disabled={isSaving || !recordId}
          >
            {isSaving ? '保存中...' : '保存'}
          </button>
        </div>
      </div>
      {isSaving && <div className="mb-2 text-xs text-cyan-200">保存进行中，请稍候...</div>}
      {notice && (
        <div
          className={`mb-2 text-xs ${
            notice.type === 'success'
              ? 'text-emerald-300'
              : notice.type === 'error'
                ? 'text-rose-300'
                : 'text-cyan-200'
          }`}
        >
          {notice.message}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-4 gap-2 mb-3">
        <label className="text-xs text-muted">
          年化目标(%)
          <input
            className="mt-1 w-full rounded border border-white/15 bg-black/30 px-2 py-1 text-xs text-white"
            type="number"
            value={target.annualReturnTargetPct}
            disabled={isSaving}
            onKeyDown={onFieldKeyDown}
            onChange={(e) => {
              setTarget((prev) => ({ ...prev, annualReturnTargetPct: Number(e.target.value) }));
              setIsDirty(true);
            }}
          />
        </label>
        <label className="text-xs text-muted">
          基础币种
          <select
            className="mt-1 w-full rounded border border-white/15 bg-black/30 px-2 py-1 text-xs text-white"
            value={target.baseCurrency}
            disabled={isSaving}
            onKeyDown={onFieldKeyDown}
            onChange={(e) => {
              setTarget((prev) => ({ ...prev, baseCurrency: e.target.value as PositionManagementTarget['baseCurrency'] }));
              setIsDirty(true);
            }}
          >
            <option value="USD">USD</option>
            <option value="CNY">CNY</option>
          </select>
        </label>
        <label className="text-xs text-muted">
          USD/CNY
          <input
            className="mt-1 w-full rounded border border-white/15 bg-black/30 px-2 py-1 text-xs text-white"
            type="number"
            value={target.usdCny}
            disabled={isSaving}
            onKeyDown={onFieldKeyDown}
            onChange={(e) => {
              setTarget((prev) => ({ ...prev, usdCny: Number(e.target.value) }));
              setIsDirty(true);
            }}
          />
        </label>
        <label className="text-xs text-muted">
          USD/HKD
          <input
            className="mt-1 w-full rounded border border-white/15 bg-black/30 px-2 py-1 text-xs text-white"
            type="number"
            value={target.usdHkd}
            disabled={isSaving}
            onKeyDown={onFieldKeyDown}
            onChange={(e) => {
              setTarget((prev) => ({ ...prev, usdHkd: Number(e.target.value) }));
              setIsDirty(true);
            }}
          />
        </label>
      </div>

      <div className="mb-3 flex items-center justify-between">
        <div className="text-xs text-muted">持仓录入与追踪</div>
        <button
          type="button"
          onClick={onAddHolding}
          className="text-xs text-cyan hover:text-white transition-colors disabled:text-muted"
          disabled={isSaving}
        >
          新增持仓
        </button>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-muted border-b border-white/10">
              <th className="text-left py-1">市场</th>
              <th className="text-left py-1">资产大类</th>
              <th className="text-left py-1">代码</th>
              <th className="text-left py-1">名称</th>
              <th className="text-right py-1">数量</th>
              <th className="text-right py-1">成本</th>
              <th className="text-right py-1">现价</th>
              <th className="text-right py-1">前收</th>
              <th className="text-left py-1">币种</th>
              <th className="text-right py-1">操作</th>
            </tr>
          </thead>
          <tbody className="text-secondary">
            {holdings.length === 0 && (
              <tr>
                <td className="py-2 text-muted" colSpan={10}>暂无持仓，请先录入后保存。</td>
              </tr>
            )}
            {holdings.map((row) => (
              <tr key={row.id} className="border-b border-white/5">
                <td className="py-1">
                  <select
                    className="rounded border border-white/15 bg-black/30 px-1 py-0.5 text-xs text-white"
                    value={row.marketType}
                    disabled={isSaving}
                    onKeyDown={onFieldKeyDown}
                    onChange={(e) => onUpdateHolding(row.id, { marketType: e.target.value })}
                  >
                    {marketOptions.map((option) => (
                      <option key={option.value} value={option.value}>{option.label}</option>
                    ))}
                  </select>
                </td>
                <td className="py-1">
                  <select
                    className="rounded border border-white/15 bg-black/30 px-1 py-0.5 text-xs text-white"
                    value={row.assetClass}
                    disabled={isSaving}
                    onKeyDown={onFieldKeyDown}
                    onChange={(e) => onUpdateHolding(row.id, { assetClass: e.target.value })}
                  >
                    {assetOptions.map((item) => (
                      <option key={item} value={item}>{item}</option>
                    ))}
                  </select>
                </td>
                <td className="py-1">
                  <input
                    className="w-24 rounded border border-white/15 bg-black/30 px-1 py-0.5 text-xs text-white"
                    value={row.symbol}
                    disabled={isSaving}
                    onKeyDown={onFieldKeyDown}
                    onChange={(e) => onUpdateHolding(row.id, { symbol: e.target.value.toUpperCase() })}
                  />
                </td>
                <td className="py-1">
                  <input
                    className="w-24 rounded border border-white/15 bg-black/30 px-1 py-0.5 text-xs text-white"
                    value={row.name || ''}
                    disabled={isSaving}
                    onKeyDown={onFieldKeyDown}
                    onChange={(e) => onUpdateHolding(row.id, { name: e.target.value })}
                  />
                </td>
                <td className="py-1 text-right">
                  <input
                    className="w-20 rounded border border-white/15 bg-black/30 px-1 py-0.5 text-xs text-white text-right"
                    type="number"
                    value={row.quantity}
                    disabled={isSaving}
                    onKeyDown={onFieldKeyDown}
                    onChange={(e) => onUpdateHolding(row.id, { quantity: Number(e.target.value) })}
                  />
                </td>
                <td className="py-1 text-right">
                  <input
                    className="w-20 rounded border border-white/15 bg-black/30 px-1 py-0.5 text-xs text-white text-right"
                    type="number"
                    value={row.avgCost}
                    disabled={isSaving}
                    onKeyDown={onFieldKeyDown}
                    onChange={(e) => onUpdateHolding(row.id, { avgCost: Number(e.target.value) })}
                  />
                </td>
                <td className="py-1 text-right">
                  <input
                    className="w-20 rounded border border-white/15 bg-black/30 px-1 py-0.5 text-xs text-white text-right"
                    type="number"
                    value={row.currentPrice}
                    disabled={isSaving}
                    onKeyDown={onFieldKeyDown}
                    onChange={(e) => onUpdateHolding(row.id, { currentPrice: Number(e.target.value) })}
                  />
                </td>
                <td className="py-1 text-right">
                  <input
                    className="w-20 rounded border border-white/15 bg-black/30 px-1 py-0.5 text-xs text-white text-right"
                    type="number"
                    value={row.previousClose ?? ''}
                    disabled={isSaving}
                    onKeyDown={onFieldKeyDown}
                    onChange={(e) => onUpdateHolding(row.id, { previousClose: Number(e.target.value) || undefined })}
                  />
                </td>
                <td className="py-1">
                  <select
                    className="rounded border border-white/15 bg-black/30 px-1 py-0.5 text-xs text-white"
                    value={row.currency}
                    disabled={isSaving}
                    onKeyDown={onFieldKeyDown}
                    onChange={(e) => onUpdateHolding(row.id, { currency: e.target.value as PositionHoldingInput['currency'] })}
                  >
                    {currencyOptions.map((item) => (
                      <option key={item} value={item}>{item}</option>
                    ))}
                  </select>
                </td>
                <td className="py-1 text-right">
                  <button
                    type="button"
                    className="text-danger hover:text-white transition-colors disabled:text-muted"
                    onClick={() => onDeleteHolding(row.id)}
                    disabled={isSaving}
                  >
                    ✕
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="mt-4 grid grid-cols-1 lg:grid-cols-3 gap-3">
        <div className="rounded-xl border border-white/10 p-3 bg-black/20">
          <div className="text-xs text-muted mb-2">资产分布总览</div>
          <div className="flex items-center gap-3">
            <div className="relative h-28 w-28 rounded-full" style={{ background: donutBackground }}>
              <div className="absolute inset-4 rounded-full bg-[#081022]" />
            </div>
            <div className="flex-1 space-y-1">
              {allocation.length === 0 && <div className="text-xs text-muted">无分布数据</div>}
              {allocation.map((row, idx) => (
                <div key={`alloc-${idx}`} className="text-xs flex items-center justify-between text-secondary gap-2">
                  <span>{String(row.assetClass ?? row.asset_class ?? '其他')}</span>
                  <span className="font-mono">{toNumber(row.ratioPct ?? row.ratio_pct, 0).toFixed(2)}%</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="rounded-xl border border-white/10 p-3 bg-black/20 lg:col-span-2">
          <div className="text-xs text-muted mb-2">目标收益进度与基准对比</div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mb-3">
            <div className="rounded border border-white/10 p-2">
              <div className="text-[11px] text-muted">当日盈亏</div>
              <div className={`font-mono text-sm ${toNumber(totals.dailyPnl ?? totals.daily_pnl, 0) >= 0 ? 'text-success' : 'text-danger'}`}>
                {toNumber(totals.dailyPnl ?? totals.daily_pnl, 0).toFixed(2)}
              </div>
            </div>
            <div className="rounded border border-white/10 p-2">
              <div className="text-[11px] text-muted">累计盈亏</div>
              <div className={`font-mono text-sm ${toNumber(totals.cumulativePnl ?? totals.cumulative_pnl, 0) >= 0 ? 'text-success' : 'text-danger'}`}>
                {toNumber(totals.cumulativePnl ?? totals.cumulative_pnl, 0).toFixed(2)}
              </div>
            </div>
            <div className="rounded border border-white/10 p-2">
              <div className="text-[11px] text-muted">当前收益率</div>
              <div className="font-mono text-sm text-cyan">
                {toNumber(progress.currentReturnPct ?? progress.current_return_pct, 0).toFixed(2)}%
              </div>
            </div>
            <div className="rounded border border-white/10 p-2">
              <div className="text-[11px] text-muted">距目标差值</div>
              <div className="font-mono text-sm text-warning">
                {toNumber(progress.gapToTargetPct ?? progress.gap_to_target_pct, 0).toFixed(2)}%
              </div>
            </div>
          </div>
          {benchmarkSeries.length === 0 ? (
            <div className="text-xs text-muted">暂无可用基准曲线，点击保存后会尝试刷新基准数据。</div>
          ) : (
            <div className="space-y-2">
              <svg viewBox="0 0 620 220" className="w-full h-40 rounded border border-white/10 bg-black/20">
                {benchmarkSeries.map((row, idx) => {
                  const colorPalette = ['#22d3ee', '#34d399', '#f59e0b', '#f97316', '#f43f5e', '#a78bfa'];
                  const points = (Array.isArray(row.points) ? row.points : []) as AnyRecord[];
                  return (
                    <polyline
                      key={`line-${String(row.code ?? idx)}`}
                      fill="none"
                      stroke={colorPalette[idx % colorPalette.length]}
                      strokeWidth="2"
                      points={buildPolyline(points, 620, 220, minBench, maxBench)}
                    />
                  );
                })}
              </svg>
              <div className="flex flex-wrap items-center gap-2 text-[11px] text-secondary">
                {benchmarkSeries.map((row, idx) => (
                  <span key={`legend-${String(row.code ?? idx)}`} className="inline-flex items-center gap-1">
                    <span className="inline-block w-2 h-2 rounded-full" style={{ background: ['#22d3ee', '#34d399', '#f59e0b', '#f97316', '#f43f5e', '#a78bfa'][idx % 6] }} />
                    {String(row.name ?? row.code ?? `series-${idx}`)}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="mt-3 rounded-xl border border-white/10 p-3 bg-black/20">
        <div className="text-xs text-muted mb-2">涨跌热力图（当日）</div>
        {heatmap.length === 0 ? (
          <div className="text-xs text-muted">暂无热力图数据</div>
        ) : (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
            {heatmap.map((row, idx) => {
              const change = toNumber(row.changePct ?? row.change_pct, 0);
              const intensity = toNumber(row.intensity, Math.min(1, Math.abs(change) / 8));
              const bg = change >= 0
                ? `rgba(239, 68, 68, ${0.12 + intensity * 0.5})`
                : `rgba(52, 211, 153, ${0.12 + intensity * 0.5})`;
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
        )}
      </div>

      <div className="mt-3 grid grid-cols-1 lg:grid-cols-2 gap-3">
        <div className="rounded-xl border border-white/10 p-3 bg-black/20">
          <div className="text-xs text-muted mb-2">AI 市场风向建议</div>
          <div className="text-xs text-secondary mb-2">
            市场情绪：<span className="text-cyan">{String(aiWind.marketSentiment ?? aiWind.market_sentiment ?? '数据不足')}</span>
          </div>
          <div className="space-y-1 text-xs text-secondary">
            {(parseStringList(aiWind.portfolioRebalance ?? aiWind.portfolio_rebalance)).map((item, idx) => (
              <div key={`rebalance-${idx}`}>- {item}</div>
            ))}
            {(parseStringList(aiWind.actionableInsights ?? aiWind.actionable_insights)).map((item, idx) => (
              <div key={`action-${idx}`}>- {item}</div>
            ))}
            {parseStringList(aiWind.portfolioRebalance ?? aiWind.portfolio_rebalance).length === 0
              && parseStringList(aiWind.actionableInsights ?? aiWind.actionable_insights).length === 0 && (
                <div className="text-muted">暂无建议，保存后自动生成。</div>
              )}
          </div>
          <div className="mt-3">
            <div className="text-[11px] text-muted mb-1">宏观/地缘事件（每行一条）</div>
            <textarea
              className="w-full h-24 rounded border border-white/15 bg-black/30 px-2 py-1 text-xs text-white"
              value={macroEventsText}
              disabled={isSaving}
              onKeyDown={onTextareaKeyDown}
              onChange={(e) => {
                setMacroEventsText(e.target.value);
                setIsDirty(true);
              }}
              placeholder="例如：美联储利率路径变化；中东冲突升级..."
            />
          </div>
        </div>
        <div className="rounded-xl border border-white/10 p-3 bg-black/20">
          <div className="text-xs text-muted mb-2">备注</div>
          <textarea
            className="w-full h-32 rounded border border-white/15 bg-black/30 px-2 py-1 text-xs text-white"
            value={notes}
            disabled={isSaving}
            onKeyDown={onTextareaKeyDown}
            onChange={(e) => {
              setNotes(e.target.value);
              setIsDirty(true);
            }}
            placeholder="可记录你的仓位模型、风险偏好、再平衡规则等。"
          />
          {saveError && <div className="text-xs text-danger mt-2">{saveError}</div>}
        </div>
      </div>
    </Card>
  );
};

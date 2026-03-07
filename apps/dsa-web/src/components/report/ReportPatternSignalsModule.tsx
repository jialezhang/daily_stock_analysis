import type React from 'react';
import type { ReportDetails as ReportDetailsType } from '../../types/analysis';
import type { ModuleRefreshState } from '../../utils/moduleRefresh';
import { Card } from '../common';

interface ReportPatternSignalsModuleProps {
  details?: ReportDetailsType;
  onRefreshModule?: () => void;
  isRefreshing?: boolean;
  refreshState?: ModuleRefreshState;
  updatedAt?: string | null;
}

interface SignalItem {
  date?: string;
  signal_type?: string;
  signalType?: string;
  patterns?: string[];
  signalStrength?: string;
  signal_strength?: string;
  signalStrengthScore?: number;
  signal_strength_score?: number;
  future7dReturnPct?: number;
  future_7d_return_pct?: number;
  future30dReturnPct?: number;
  future_30d_return_pct?: number;
  future7dEffectiveDays?: number;
  future_7d_effective_days?: number;
  future30dEffectiveDays?: number;
  future_30d_effective_days?: number;
}

const readTechnicalModule = (details?: ReportDetailsType): Record<string, unknown> | null => {
  if (!details) return null;

  const raw = details.rawResult as Record<string, unknown> | undefined;
  const fromRaw = (raw?.technicalModule || raw?.technical_module) as Record<string, unknown> | undefined;
  if (fromRaw && Object.keys(fromRaw).length > 0) return fromRaw;

  const snapshot = details.contextSnapshot as Record<string, unknown> | undefined;
  const enhanced = (snapshot?.enhancedContext || snapshot?.enhanced_context) as Record<string, unknown> | undefined;
  const fromContext = (enhanced?.technicalModule || enhanced?.technical_module) as Record<string, unknown> | undefined;
  if (fromContext && Object.keys(fromContext).length > 0) return fromContext;

  return null;
};

export const ReportPatternSignalsModule: React.FC<ReportPatternSignalsModuleProps> = ({
  details,
  onRefreshModule,
  isRefreshing = false,
  refreshState = 'idle',
  updatedAt,
}) => {
  const module = readTechnicalModule(details);
  if (!module) return null;

  const windowInfo = ((module.window || {}) as Record<string, unknown>);
  const signalRoot = ((module.patternSignals1Y || module.pattern_signals_1y) || {}) as Record<string, unknown>;
  const signals = (signalRoot.signals || []) as SignalItem[];
  const recentSignals = signals.slice(-30).reverse();
  const asNumber = (value: unknown, fallback = 0): number => {
    const n = Number(value);
    return Number.isFinite(n) ? n : fallback;
  };
  const asNullableNumber = (value: unknown): number | null => {
    if (value === null || value === undefined) return null;
    const n = Number(value);
    return Number.isFinite(n) ? n : null;
  };
  const inferStrength = (signalType: string, patterns: string[]): { label: string; score: number } => {
    let score = 55 + Math.min(Math.max(patterns.length, 0), 3) * 10;
    const text = patterns.join(' ');
    if (/吞没|黄昏之星|乌云盖顶/.test(text) && signalType.includes('见顶')) score += 10;
    if (/启明星|锤子|倒锤子|晨星/.test(text) && signalType.includes('止跌')) score += 10;
    if (/成交量/.test(text)) score += 8;
    const finalScore = Math.max(30, Math.min(95, score));
    if (finalScore >= 80) return { label: '强', score: finalScore };
    if (finalScore >= 65) return { label: '中', score: finalScore };
    return { label: '弱', score: finalScore };
  };
  const formatReturn = (value: number): string => `${value > 0 ? '+' : ''}${value.toFixed(2)}%`;
  const refreshText = refreshState === 'queued'
    ? '排队中...'
    : refreshState === 'running'
      ? '更新中...'
      : refreshState === 'succeeded'
        ? '已更新'
        : refreshState === 'failed'
          ? '重试更新'
          : '更新';

  return (
    <Card variant="bordered" padding="md" className="text-left">
      <div className="mb-3 flex items-center justify-between gap-2">
        <div className="flex items-baseline gap-2">
          <span className="label-uppercase">PATTERN SIGNALS</span>
          <h3 className="text-base font-semibold text-white mt-0.5">止跌/见顶信号模块</h3>
          <span className="text-[11px] text-muted">更新于 {updatedAt || '未更新'}</span>
        </div>
        <button
          type="button"
          className="text-xs text-cyan hover:text-white transition-colors"
          onClick={onRefreshModule}
          disabled={isRefreshing}
        >
          {refreshText}
        </button>
      </div>

      <div className="text-xs text-muted mb-2">
        止跌 {String(signalRoot.bottomCount ?? signalRoot.bottom_count ?? 0)} 次
        <span className="mx-2 text-muted">|</span>
        见顶 {String(signalRoot.topCount ?? signalRoot.top_count ?? 0)} 次
        <span className="mx-2 text-muted">|</span>
        总计 {String(signals.length)} 条
      </div>

      {Boolean(windowInfo.start || windowInfo.end) && (
        <div className="text-xs text-secondary mb-3">
          窗口: {String(windowInfo.start ?? '—')} ~ {String(windowInfo.end ?? '—')}
        </div>
      )}

      {recentSignals.length === 0 ? (
        <div className="text-xs text-muted">近一年暂无命中的止跌/见顶组合</div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-muted border-b border-white/10">
                <th className="text-left py-1">信号类型</th>
                <th className="text-left py-1">日期</th>
                <th className="text-left py-1">信号组合</th>
                <th className="text-left py-1">信号强弱</th>
                <th className="text-left py-1">未来7天涨跌</th>
                <th className="text-left py-1">未来30天涨跌</th>
              </tr>
            </thead>
            <tbody className="text-secondary">
              {recentSignals.map((item, idx) => {
                const signalType = String(item.signalType || item.signal_type || '—');
                const isBottom = signalType.includes('止跌');
                const icon = isBottom ? '🟢' : '🔴';
                const inferred = inferStrength(signalType, item.patterns || []);
                const strengthRaw = String(item.signalStrength || item.signal_strength || '').trim();
                const scoreRaw = asNullableNumber(item.signalStrengthScore ?? item.signal_strength_score);
                const strength = strengthRaw || inferred.label;
                const strengthScore = scoreRaw ?? inferred.score;
                const ret7 = asNullableNumber(item.future7dReturnPct ?? item.future_7d_return_pct);
                const ret30 = asNullableNumber(item.future30dReturnPct ?? item.future_30d_return_pct);
                const ret7Days = asNumber(item.future7dEffectiveDays ?? item.future_7d_effective_days, 7);
                const ret30Days = asNumber(item.future30dEffectiveDays ?? item.future_30d_effective_days, 30);
                return (
                  <tr key={`${item.date}-${idx}`} className="border-b border-white/5">
                    <td className="py-1">
                      <span className="mr-1">{icon}</span>
                      <span>{isBottom ? '止跌' : '见顶'}</span>
                    </td>
                    <td className="py-1 font-mono text-cyan">{String(item.date || '—')}</td>
                    <td className="py-1">{(item.patterns || []).join('；') || '—'}</td>
                    <td className="py-1">{strength} ({strengthScore})</td>
                    <td className={`py-1 font-mono ${ret7 === null ? 'text-muted' : ret7 >= 0 ? 'text-success' : 'text-danger'}`}>
                      {ret7 === null ? '—' : `${formatReturn(ret7)}${ret7Days < 7 ? ` (${ret7Days}d)` : ''}`}
                    </td>
                    <td className={`py-1 font-mono ${ret30 === null ? 'text-muted' : ret30 >= 0 ? 'text-success' : 'text-danger'}`}>
                      {ret30 === null ? '—' : `${formatReturn(ret30)}${ret30Days < 30 ? ` (${ret30Days}d)` : ''}`}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
};

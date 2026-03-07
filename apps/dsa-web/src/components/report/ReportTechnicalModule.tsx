import type React from 'react';
import type { ReportDetails as ReportDetailsType } from '../../types/analysis';
import type { ModuleRefreshState } from '../../utils/moduleRefresh';
import { Card } from '../common';

interface ReportTechnicalModuleProps {
  details?: ReportDetailsType;
  onRefreshModule?: () => void;
  isRefreshing?: boolean;
  refreshState?: ModuleRefreshState;
  updatedAt?: string | null;
}

interface IndicatorItem {
  value?: unknown;
  score?: number;
  result?: string;
  explanation?: string;
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

export const ReportTechnicalModule: React.FC<ReportTechnicalModuleProps> = ({
  details,
  onRefreshModule,
  isRefreshing = false,
  refreshState = 'idle',
  updatedAt,
}) => {
  const module = readTechnicalModule(details);
  if (!module) return null;

  const indicators = ((module.technicalIndicators || module.technical_indicators) || {}) as Record<string, unknown>;
  const overall = (indicators.overall || {}) as Record<string, unknown>;
  const indicatorOrderRaw = (indicators.indicatorOrder || indicators.indicator_order || []) as string[];
  const indicatorOrder = indicatorOrderRaw.length > 0
    ? indicatorOrderRaw
    : ['rsi', 'asr', 'cc', 'sar', 'macd', 'kdj', 'bias', 'kc', 'bbiboll', 'magic_nine_turn'];

  const formatIndicatorName = (key: string): string => {
    const map: Record<string, string> = {
      rsi: 'RSI',
      asr: 'ASR',
      cc: 'CC',
      sar: 'SAR',
      macd: 'MACD',
      kdj: 'KDJ',
      bias: 'BIAS',
      kc: 'KC',
      bbiboll: 'BBIBOLL',
      magic_nine_turn: '神奇九转',
    };
    return map[key] || key.toUpperCase();
  };

  const formatValue = (value: unknown): string => {
    if (value === null || value === undefined) return '—';
    if (typeof value === 'object' && !Array.isArray(value)) {
      return Object.entries(value as Record<string, unknown>)
        .map(([k, v]) => `${k}:${String(v)}`)
        .join(', ');
    }
    return String(value);
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

  return (
    <Card variant="bordered" padding="md" className="text-left">
      <div className="mb-3 flex items-center justify-between gap-2">
        <div className="flex items-baseline gap-2">
          <span className="label-uppercase">TECH MODULE</span>
          <h3 className="text-base font-semibold text-white mt-0.5">技术指标分析</h3>
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

      <div className="mt-4">
        <div className="text-xs text-muted mb-2">技术指标（含解释与近期解读）</div>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-muted border-b border-white/10">
                <th className="text-left py-1">指标</th>
                <th className="text-left py-1">数值</th>
                <th className="text-left py-1">评分</th>
                <th className="text-left py-1">近期解读</th>
              </tr>
            </thead>
            <tbody className="text-secondary">
              {indicatorOrder.map((key) => {
                const item = (indicators[key] || {}) as IndicatorItem;
                if (!item || Object.keys(item).length === 0) return null;
                return (
                  <tr key={key} className="border-b border-white/5">
                    <td className="py-1">
                      <span>{formatIndicatorName(key)}</span>
                      {item.explanation && (
                        <span
                          title={item.explanation}
                          className="ml-1 inline-flex h-4 w-4 items-center justify-center rounded-full border border-white/20 text-[10px] text-muted cursor-help"
                        >
                          !
                        </span>
                      )}
                    </td>
                    <td className="py-1 font-mono">{formatValue(item.value)}</td>
                    <td className="py-1 font-mono">{String(item.score ?? '—')}</td>
                    <td className="py-1">{String(item.result ?? '—')}</td>
                  </tr>
                );
              })}
              <tr>
                <td className="py-1">总分</td>
                <td className="py-1">-</td>
                <td className="py-1 font-mono">{String(overall.score ?? '—')}</td>
                <td className="py-1">{String(overall.resultDetail ?? overall.result_detail ?? overall.result ?? '—')}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </Card>
  );
};

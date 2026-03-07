import type React from 'react';
import type { ReportStrategy as ReportStrategyType } from '../../types/analysis';
import type { ModuleRefreshState } from '../../utils/moduleRefresh';
import { Card } from '../common';

interface ReportStrategyProps {
  strategy?: ReportStrategyType;
  onRefreshModule?: () => void;
  isRefreshing?: boolean;
  refreshState?: ModuleRefreshState;
  updatedAt?: string | null;
}

interface StrategyItemProps {
  label: string;
  value?: string;
  color: string;
}

const StrategyItem: React.FC<StrategyItemProps> = ({
  label,
  value,
  color,
}) => (
  <div className="relative overflow-hidden rounded-lg bg-elevated border border-white/5 p-3 hover:border-white/10 transition-colors">
    <div className="flex flex-col">
      <span className="text-xs text-muted mb-0.5">{label}</span>
      <span
        className="text-lg font-bold font-mono"
        style={{ color: value ? color : 'var(--text-muted)' }}
      >
        {value || '—'}
      </span>
    </div>
    {/* 底部指示条 */}
    <div
      className="absolute bottom-0 left-0 right-0 h-0.5"
      style={{ background: `linear-gradient(90deg, ${color}00, ${color}, ${color}00)` }}
    />
  </div>
);

/**
 * 策略点位区组件 - 终端风格
 */
export const ReportStrategy: React.FC<ReportStrategyProps> = ({
  strategy,
  onRefreshModule,
  isRefreshing = false,
  refreshState = 'idle',
  updatedAt,
}) => {
  if (!strategy) {
    return null;
  }

  const strategyItems = [
    {
      label: '理想买入',
      value: strategy.idealBuy,
      color: '#00ff88', // success
    },
    {
      label: '二次买入',
      value: strategy.secondaryBuy,
      color: '#00d4ff', // cyan
    },
    {
      label: '止损价位',
      value: strategy.stopLoss,
      color: '#ff4466', // danger
    },
    {
      label: '止盈目标',
      value: strategy.takeProfit,
      color: '#ffaa00', // warning
    },
  ];
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
    <Card variant="bordered" padding="md">
      <div className="mb-3 flex items-center justify-between gap-2">
        <div className="flex items-baseline gap-2">
          <span className="label-uppercase">STRATEGY POINTS</span>
          <h3 className="text-base font-semibold text-white">狙击点位</h3>
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
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {strategyItems.map((item) => (
          <StrategyItem key={item.label} {...item} />
        ))}
      </div>
    </Card>
  );
};

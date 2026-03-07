import type { ReportDetails, HistoryModuleKey, ModuleRefreshJob } from '../types/analysis';

export const moduleLabelMap: Record<HistoryModuleKey, string> = {
  full: '全部',
  summary: '概览',
  price_zones: '价格区间',
  pattern_signals: '止跌/见顶',
  technical_indicators: '技术指标',
  sniper_points: '狙击点位',
  news: '资讯',
  position_management: '仓位管理',
};

const asRecord = (value: unknown): Record<string, unknown> => {
  return value && typeof value === 'object' ? value as Record<string, unknown> : {};
};

export const readModuleUpdateMeta = (details?: ReportDetails): Record<string, Record<string, unknown>> => {
  if (!details) return {};
  const raw = asRecord(details.rawResult);
  const meta = raw.moduleUpdateMeta ?? raw.module_update_meta;
  if (!meta || typeof meta !== 'object') return {};
  return meta as Record<string, Record<string, unknown>>;
};

const toModuleKeys = (module: HistoryModuleKey): string[] => {
  switch (module) {
    case 'price_zones':
      return ['price_zones', 'priceZones'];
    case 'pattern_signals':
      return ['pattern_signals', 'patternSignals'];
    case 'technical_indicators':
      return ['technical_indicators', 'technicalIndicators'];
    case 'sniper_points':
      return ['sniper_points', 'sniperPoints'];
    case 'summary':
      return ['summary'];
    case 'news':
      return ['news'];
    case 'position_management':
      return ['position_management', 'positionManagement'];
    case 'full':
      return ['full'];
    default:
      return [module];
  }
};

export const getModuleLastUpdatedAt = (details: ReportDetails | undefined, module: HistoryModuleKey): string | null => {
  const meta = readModuleUpdateMeta(details);
  const keys = toModuleKeys(module);
  for (const key of keys) {
    const row = asRecord(meta[key]);
    const val = row.lastUpdatedAt ?? row.last_updated_at;
    if (typeof val === 'string' && val.trim()) return val;
  }
  return null;
};

export const getLatestJobByModule = (
  jobs: ModuleRefreshJob[] | undefined,
  module: HistoryModuleKey,
): ModuleRefreshJob | null => {
  if (!jobs || jobs.length === 0) return null;
  const filtered = jobs.filter((item) => item.module === module);
  if (filtered.length === 0) return null;
  return filtered.sort((a, b) => (a.createdAt > b.createdAt ? -1 : 1))[0];
};

export type ModuleRefreshState = 'idle' | 'queued' | 'running' | 'succeeded' | 'failed';

export const getModuleRefreshState = (
  jobs: ModuleRefreshJob[] | undefined,
  module: HistoryModuleKey,
): ModuleRefreshState => {
  const latest = getLatestJobByModule(jobs, module);
  if (!latest) return 'idle';
  return latest.status;
};

export const getModuleUpdatedAtDisplay = (
  details: ReportDetails | undefined,
  jobs: ModuleRefreshJob[] | undefined,
  module: HistoryModuleKey,
): string | null => {
  const fromMeta = getModuleLastUpdatedAt(details, module);
  if (fromMeta) return fromMeta;
  const latest = getLatestJobByModule(jobs, module);
  if (!latest) return null;
  return latest.moduleUpdatedAt || latest.finishedAt || null;
};

export const isModuleRefreshing = (
  jobs: ModuleRefreshJob[] | undefined,
  module: HistoryModuleKey,
): boolean => {
  const latest = getLatestJobByModule(jobs, module);
  if (!latest) return false;
  return latest.status === 'queued' || latest.status === 'running';
};

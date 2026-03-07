import React, { useEffect, useMemo, useState } from 'react';
import type { ReportDetails as ReportDetailsType } from '../../types/analysis';
import type { ModuleRefreshState } from '../../utils/moduleRefresh';
import { historyApi } from '../../api/history';
import { Card } from '../common';

interface ReportPriceZonesModuleProps {
  details?: ReportDetailsType;
  recordId?: number;
  stockCode?: string;
  onRefreshModule?: () => void;
  isRefreshing?: boolean;
  refreshState?: ModuleRefreshState;
  updatedAt?: string | null;
}

interface ZoneKeyLevel {
  price?: number;
  origins?: string[];
  roles?: string[];
}

interface RhinoZone {
  id: string;
  name: string;
  upper: number;
  lower: number;
  strengthLevel: string;
  strengthScore: number;
  keyLevels: ZoneKeyLevel[];
  logicDetail: string;
  sourceType: 'system' | 'manual';
}

type PriceMode = 'classic' | 'rhino';
type RhinoStrength = '弱' | '中' | '强' | '超强';

interface DraftZone {
  id: string;
  lower: string;
  upper: string;
  strength: RhinoStrength;
  definition: string;
}
type NoticeState = { type: 'success' | 'error' | 'info'; message: string } | null;

const asNumber = (value: unknown, fallback = 0): number => {
  const n = Number(value);
  return Number.isFinite(n) ? n : fallback;
};

const isUsTicker = (code?: string): boolean => {
  const val = String(code || '').trim().toUpperCase();
  if (!val) return false;
  if (/^\d{5,6}$/.test(val)) return false;
  if (/^(SH|SZ|BJ)\d{6}$/.test(val)) return false;
  if (/^HK\d{4,6}$/.test(val)) return false;
  return /[A-Z]/.test(val);
};

const readTechnicalModule = (details?: ReportDetailsType): Record<string, unknown> | null => {
  if (!details) return null;
  const direct = ((details as Record<string, unknown>).technicalModule
    || (details as Record<string, unknown>).technical_module) as Record<string, unknown> | undefined;
  if (direct && Object.keys(direct).length > 0) return direct;

  const raw = details.rawResult as Record<string, unknown> | undefined;
  const fromRaw = (raw?.technicalModule || raw?.technical_module) as Record<string, unknown> | undefined;
  if (fromRaw && Object.keys(fromRaw).length > 0) return fromRaw;

  const snapshot = details.contextSnapshot as Record<string, unknown> | undefined;
  const enhanced = (snapshot?.enhancedContext || snapshot?.enhanced_context) as Record<string, unknown> | undefined;
  const fromContext = (enhanced?.technicalModule || enhanced?.technical_module) as Record<string, unknown> | undefined;
  if (fromContext && Object.keys(fromContext).length > 0) return fromContext;
  return null;
};

const buildDefinition = (zone: RhinoZone): string => {
  if (zone.sourceType === 'manual') return zone.logicDetail || '手动定义区间';
  if (!zone.keyLevels || zone.keyLevels.length === 0) return zone.logicDetail || '系统关键价位聚类形成';
  return zone.keyLevels
    .map((level) => `${asNumber(level.price).toFixed(3)}(${(level.origins || []).join('+') || '未知来源'})`)
    .join('、');
};

const findInsertIndexByLower = (sortedZones: RhinoZone[], currentPrice: number): number => {
  for (let i = 0; i < sortedZones.length; i += 1) {
    if (currentPrice > sortedZones[i].lower) {
      return i;
    }
  }
  return sortedZones.length;
};

const locateCurrentPrice = (zones: RhinoZone[], currentPrice: number): { index: number; advice: string } => {
  if (zones.length === 0 || !(currentPrice > 0)) {
    return { index: 0, advice: '暂无可用区间，请先新增或刷新区间数据。' };
  }
  const sorted = [...zones].sort((a, b) => b.upper - a.upper);
  const insertIndex = findInsertIndexByLower(sorted, currentPrice);
  const inside = sorted.find((z) => currentPrice <= z.upper && currentPrice >= z.lower);
  if (inside) {
    return {
      index: insertIndex,
      advice: `当前价位于区间“${inside.name}”内，优先等待边界确认：靠近下限可关注低吸，靠近上限谨慎追涨。`,
    };
  }
  if (currentPrice >= sorted[0].upper) {
    return { index: insertIndex, advice: '当前价位于全部区间上方，偏强但不宜追高，优先等待回踩确认。' };
  }
  if (currentPrice <= sorted[sorted.length - 1].lower) {
    return { index: insertIndex, advice: '当前价位于全部区间下方，偏弱，建议先等待止跌信号再参与。' };
  }
  for (let i = 0; i < sorted.length - 1; i += 1) {
    if (currentPrice < sorted[i].lower && currentPrice > sorted[i + 1].upper) {
      return {
        index: insertIndex,
        advice: '当前价位于区间空档，向上接近阻力位时谨慎，向下接近支撑位时可考虑分批布局。',
      };
    }
  }
  return { index: insertIndex, advice: '当前价与区间边界接近，建议结合量能与趋势信号确认方向。' };
};

export const ReportPriceZonesModule: React.FC<ReportPriceZonesModuleProps> = ({
  details,
  recordId,
  stockCode,
  onRefreshModule,
  isRefreshing = false,
  refreshState = 'idle',
  updatedAt,
}) => {
  if (!details) return null;

  const module = readTechnicalModule(details) || {};
  const zones = ((module.priceZones || module.price_zones) || {}) as Record<string, unknown>;
  const currentPrice = asNumber(zones.currentPrice ?? zones.current_price);
  const isUsSymbol = isUsTicker(stockCode);
  const secondaryModeLabel = isUsSymbol ? 'Rhino 价格区间' : '人工判断区间';

  const rhinoRaw = ((zones.rhinoZones || zones.rhino_zones) || []) as Array<Record<string, unknown>>;
  const classicBoxesRaw = ((zones.multiBoxes || zones.multi_boxes) || []) as Array<Record<string, unknown>>;
  const classicBoxes = classicBoxesRaw
    .map((item, index) => ({
      id: String(item.id || `classic-${index}`),
      name: String(item.name || `区间${index + 1}`),
      side: String(item.side || ''),
      lower: asNumber(item.low, asNumber(item.lower)),
      upper: asNumber(item.high, asNumber(item.upper)),
      strengthLevel: String(item.strengthLevel ?? item.strength_level ?? '中'),
      logicDetail: String(item.logicDetail ?? item.logic_detail ?? item.definition ?? ''),
    }))
    .filter((item) => item.upper > 0 && item.lower > 0 && item.upper > item.lower)
    .sort((a, b) => b.upper - a.upper);
  const allRhinoZones: RhinoZone[] = rhinoRaw
    .map((item, index) => {
      const upper = asNumber(item.upper, asNumber(item.high));
      const lower = asNumber(item.lower, asNumber(item.low));
      const strengthLevel = String(item.strengthLevel ?? item.strength_level ?? '中');
      const sourceTypeRaw = String(item.sourceType ?? item.source_type ?? 'system').toLowerCase();
      const sourceType: 'manual' | 'system' = sourceTypeRaw === 'manual' ? 'manual' : 'system';
      return {
        id: String(item.id || `${sourceTypeRaw}-${index}-${upper}-${lower}`),
        name: String(item.name || `区间${index + 1}`),
        upper,
        lower,
        strengthLevel,
        strengthScore: asNumber(item.strengthScore ?? item.strength_score, 50),
        keyLevels: (item.keyLevels || item.key_levels || []) as ZoneKeyLevel[],
        logicDetail: String(item.logicDetail ?? item.logic_detail ?? item.definition ?? item.logic ?? ''),
        sourceType,
      };
    })
    .filter((item) => item.upper > 0 && item.lower > 0 && item.upper > item.lower)
    .sort((a, b) => b.upper - a.upper);
  // Secondary mode (Rhino / 人工判断区间) only shows manual zones.
  // System-generated zones belong to 智能模式 to avoid mixed semantics.
  const rhinoSystemZones: RhinoZone[] = allRhinoZones.filter(
    (item) => item.sourceType === 'manual',
  );

  const [mode, setMode] = useState<PriceMode>('classic');
  const [localZones, setLocalZones] = useState<RhinoZone[]>([]);
  const [hiddenIds, setHiddenIds] = useState<string[]>([]);
  const [drafts, setDrafts] = useState<DraftZone[]>([]);
  const [editingId, setEditingId] = useState<string>('');
  const [editLower, setEditLower] = useState<string>('');
  const [editUpper, setEditUpper] = useState<string>('');
  const [editStrength, setEditStrength] = useState<RhinoStrength>('中');
  const [editDefinition, setEditDefinition] = useState<string>('');
  const [expandedIds, setExpandedIds] = useState<string[]>([]);
  const [errorText, setErrorText] = useState<string>('');
  const [savingKey, setSavingKey] = useState<string>('');
  const [notice, setNotice] = useState<NoticeState>(null);
  const [pendingText, setPendingText] = useState<string>('');

  useEffect(() => {
    setMode(rhinoSystemZones.length > 0 ? 'rhino' : 'classic');
    setLocalZones([]);
    setHiddenIds([]);
    setDrafts([]);
    setEditingId('');
    setEditDefinition('');
    setErrorText('');
    setNotice(null);
    setPendingText('');
  }, [recordId, rhinoSystemZones.length, currentPrice]);

  useEffect(() => {
    if (!notice) return;
    const timer = window.setTimeout(() => setNotice(null), 2400);
    return () => window.clearTimeout(timer);
  }, [notice]);

  const rhinoZones = useMemo(() => {
    const merged = [...rhinoSystemZones, ...localZones]
      .filter((item) => !hiddenIds.includes(item.id))
      .sort((a, b) => b.upper - a.upper);
    const dedup = new Map<string, RhinoZone>();
    merged.forEach((item) => {
      // Let local edits override initial zones with the same id.
      dedup.set(item.id, item);
    });
    return Array.from(dedup.values()).sort((a, b) => b.upper - a.upper);
  }, [rhinoSystemZones, localZones, hiddenIds]);

  const currentAnchor = useMemo(() => locateCurrentPrice(rhinoZones, currentPrice), [rhinoZones, currentPrice]);
  const classicAsZones = useMemo<RhinoZone[]>(
    () => classicBoxes.map((item) => ({
      id: item.id,
      name: item.name,
      upper: item.upper,
      lower: item.lower,
      strengthLevel: item.strengthLevel,
      strengthScore: 50,
      keyLevels: [],
      logicDetail: item.logicDetail,
      sourceType: 'system',
    })),
    [classicBoxes],
  );
  const classicAnchor = useMemo(
    () => locateCurrentPrice(classicAsZones, currentPrice),
    [classicAsZones, currentPrice],
  );
  const manualRhinoZones = useMemo(
    () => rhinoZones.filter((zone) => zone.sourceType === 'manual'),
    [rhinoZones],
  );
  const refreshText = refreshState === 'queued'
    ? '排队中...'
    : refreshState === 'running'
      ? '更新中...'
      : refreshState === 'succeeded'
        ? '已更新'
        : refreshState === 'failed'
          ? '重试更新'
          : '更新';
  const iconBtnBase = 'h-7 w-7 inline-flex items-center justify-center rounded border transition-all duration-150 cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed opacity-70 hover:opacity-100 hover:scale-[1.03]';
  const iconBtnSave = `${iconBtnBase} border-white/20 bg-emerald-500/12 text-emerald-200 hover:border-emerald-300/50 hover:bg-emerald-500/35 hover:text-white hover:shadow-[0_0_0_1px_rgba(16,185,129,0.35)]`;
  const iconBtnCancel = `${iconBtnBase} border-white/20 bg-white/4 text-secondary hover:border-white/35 hover:bg-white/18 hover:text-white hover:shadow-[0_0_0_1px_rgba(255,255,255,0.18)]`;
  const iconBtnEdit = `${iconBtnBase} border-white/20 bg-cyan/8 text-cyan hover:border-cyan-300/50 hover:bg-cyan/30 hover:text-white hover:shadow-[0_0_0_1px_rgba(34,211,238,0.35)]`;
  const iconBtnDelete = `${iconBtnBase} border-white/20 bg-red-500/12 text-red-200 hover:border-red-300/50 hover:bg-red-500/35 hover:text-white hover:shadow-[0_0_0_1px_rgba(248,113,113,0.35)]`;

  const handleEditKeyDown = (e: React.KeyboardEvent<HTMLInputElement | HTMLSelectElement>, zone: RhinoZone): void => {
    if (e.key === 'Enter') {
      e.preventDefault();
      void saveEdit(zone);
    }
  };

  const handleDraftKeyDown = (e: React.KeyboardEvent<HTMLInputElement | HTMLSelectElement>, draft: DraftZone): void => {
    if (e.key !== 'Enter') return;
    e.preventDefault();
    void saveDraft(draft);
  };

  const addDraft = (): void => {
    setDrafts((prev) => [...prev, {
      id: `draft-${Date.now()}-${prev.length}`,
      lower: '',
      upper: '',
      strength: '中',
      definition: '',
    }]);
  };

  const removeDraft = (id: string): void => {
    setDrafts((prev) => prev.filter((item) => item.id !== id));
  };

  const saveDraft = async (draft: DraftZone): Promise<void> => {
    const lower = Number(draft.lower);
    const upper = Number(draft.upper);
    if (!Number.isFinite(lower) || !Number.isFinite(upper) || lower <= 0 || upper <= 0 || upper <= lower) {
      setErrorText('请先填写合法区间：下限 > 0，且上限 > 下限。');
      return;
    }
    setErrorText('');
    setSavingKey(draft.id);
    setPendingText('新增区间保存中...');
    setNotice({ type: 'info', message: '新增区间保存中...' });
    try {
      if (!recordId) {
        setErrorText('当前记录不可写入，请先从关注列表打开一条报告。');
        setNotice({ type: 'error', message: '当前记录不可写入，请先从关注列表打开一条报告。' });
        return;
      }
      if (recordId) {
        const response = await historyApi.addRhinoZone(recordId, {
          lower,
          upper,
          strengthLevel: draft.strength,
          definition: draft.definition,
        });
        const rawZone = (response.zone || {}) as Record<string, unknown>;
        const zone: RhinoZone = {
          id: String(rawZone.id || `manual-${Date.now()}`),
          name: String(rawZone.name || `手动区间`),
          lower: asNumber(rawZone.lower, lower),
          upper: asNumber(rawZone.upper, upper),
          strengthLevel: String(rawZone.strengthLevel ?? rawZone.strength_level ?? draft.strength),
          strengthScore: asNumber(rawZone.strengthScore ?? rawZone.strength_score, 60),
          keyLevels: (rawZone.keyLevels || rawZone.key_levels || []) as ZoneKeyLevel[],
          logicDetail: String(rawZone.logicDetail ?? rawZone.logic_detail ?? draft.definition ?? '手动定义区间'),
          sourceType: 'manual',
        };
        setLocalZones((prev) => [...prev, zone].sort((a, b) => b.upper - a.upper));
      }
      removeDraft(draft.id);
      setNotice({ type: 'success', message: '区间新增并保存成功' });
    } catch {
      setErrorText('新增区间失败，请稍后重试。');
      setNotice({ type: 'error', message: '新增区间失败，请稍后重试。' });
    } finally {
      setSavingKey('');
      setPendingText('');
    }
  };

  const startEdit = (zone: RhinoZone): void => {
    if (zone.sourceType !== 'manual') return;
    setEditingId(zone.id);
    setEditLower(zone.lower.toString());
    setEditUpper(zone.upper.toString());
    setEditStrength((['弱', '中', '强', '超强'].includes(zone.strengthLevel) ? zone.strengthLevel : '中') as RhinoStrength);
    setEditDefinition(zone.logicDetail || '');
  };

  const saveEdit = async (zone: RhinoZone): Promise<void> => {
    const lower = Number(editLower);
    const upper = Number(editUpper);
    if (!Number.isFinite(lower) || !Number.isFinite(upper) || lower <= 0 || upper <= 0 || upper <= lower) {
      setErrorText('修改失败：请确认下限和上限数值合法。');
      return;
    }
    setErrorText('');
    setSavingKey(zone.id);
    setPendingText('区间修改保存中...');
    setNotice({ type: 'info', message: '区间修改保存中...' });
    try {
      if (recordId) {
        const response = await historyApi.updateRhinoZone(recordId, zone.id, {
          lower,
          upper,
          strengthLevel: editStrength,
          definition: editDefinition,
        });
        const raw = (response.zone || {}) as Record<string, unknown>;
        const merged: RhinoZone = {
          ...zone,
          lower: asNumber(raw.lower, lower),
          upper: asNumber(raw.upper, upper),
          strengthLevel: String(raw.strengthLevel ?? raw.strength_level ?? editStrength),
          strengthScore: asNumber(raw.strengthScore ?? raw.strength_score, zone.strengthScore),
          logicDetail: String(raw.logicDetail ?? raw.logic_detail ?? raw.definition ?? editDefinition ?? zone.logicDetail),
        };
        setLocalZones((prev) => [...prev.filter((x) => x.id !== zone.id), merged].sort((a, b) => b.upper - a.upper));
      }
      setEditingId('');
      setNotice({ type: 'success', message: '区间修改保存成功' });
    } catch {
      setErrorText('修改区间失败，请稍后重试。');
      setNotice({ type: 'error', message: '修改区间失败，请稍后重试。' });
    } finally {
      setSavingKey('');
      setPendingText('');
    }
  };

  const removeZone = async (zone: RhinoZone): Promise<void> => {
    if (zone.sourceType !== 'manual') return;
    setSavingKey(zone.id);
    setPendingText('区间删除中...');
    setNotice({ type: 'info', message: '区间删除中...' });
    try {
      if (recordId) {
        await historyApi.deleteRhinoZone(recordId, zone.id);
      }
      setHiddenIds((prev) => [...prev, zone.id]);
      setLocalZones((prev) => prev.filter((x) => x.id !== zone.id));
      setNotice({ type: 'success', message: '区间删除成功' });
    } catch {
      setErrorText('删除区间失败，请稍后重试。');
      setNotice({ type: 'error', message: '删除区间失败，请稍后重试。' });
    } finally {
      setSavingKey('');
      setPendingText('');
    }
  };

  const toggleExpand = (id: string): void => {
    setExpandedIds((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
  };

  return (
    <Card variant="bordered" padding="md" className="text-left">
      <div className="mb-3 flex items-center justify-between gap-2 flex-wrap">
        <div className="flex items-baseline gap-2">
          <span className="label-uppercase">PRICE ZONES</span>
          <h3 className="text-base font-semibold text-white mt-0.5">价格区间</h3>
          <span className="text-[11px] text-muted">更新于 {updatedAt || '未更新'}</span>
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
          <div className="inline-flex rounded-md border border-white/10 overflow-hidden text-xs">
            <button
              type="button"
              className={`px-3 py-1.5 ${mode === 'classic' ? 'bg-white/15 text-white' : 'bg-transparent text-muted'}`}
              onClick={() => setMode('classic')}
              disabled={Boolean(savingKey)}
            >
              智能模式
            </button>
            <button
              type="button"
              className={`px-3 py-1.5 border-l border-white/10 ${mode === 'rhino' ? 'bg-white/15 text-white' : 'bg-transparent text-muted'}`}
              onClick={() => setMode('rhino')}
              disabled={Boolean(savingKey)}
            >
              {secondaryModeLabel}
            </button>
          </div>
        </div>
      </div>
      {pendingText ? <div className="mb-2 text-xs text-cyan-200">{pendingText}</div> : null}
      {notice ? (
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
      ) : null}

      {mode === 'classic' && (
        <div className="space-y-2">
          <div className="rounded-lg border border-white/10 bg-black/20 overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-muted border-b border-white/10">
                  <th className="text-left py-2 px-2">名称</th>
                  <th className="text-left py-2 px-2">类型</th>
                  <th className="text-left py-2 px-2">下限</th>
                  <th className="text-left py-2 px-2">上限</th>
                  <th className="text-left py-2 px-2">强度</th>
                  <th className="text-left py-2 px-2">区间定义</th>
                </tr>
              </thead>
              <tbody className="text-secondary">
                {classicBoxes.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="py-3 px-2 text-muted">智能模式暂无区间数据。</td>
                  </tr>
                ) : (
                  classicBoxes.map((item, idx) => {
                    const shouldInsert = classicAnchor.index === idx;
                    return (
                      <React.Fragment key={item.id}>
                        {shouldInsert ? (
                          <tr className="bg-amber-500/15 border-y border-amber-400/30">
                            <td className="py-2 px-2 text-amber-200 font-mono" colSpan={6}>
                              当前价 {currentPrice.toFixed(3)} · {classicAnchor.advice}
                            </td>
                          </tr>
                        ) : null}
                        <tr className="border-b border-white/5">
                          <td className="py-2 px-2">{item.name}</td>
                          <td className="py-2 px-2">{item.side === 'support' ? '支撑' : item.side === 'resistance' ? '阻力' : '—'}</td>
                          <td className="py-2 px-2 font-mono text-success">{item.lower.toFixed(3)}</td>
                          <td className="py-2 px-2 font-mono text-warning">{item.upper.toFixed(3)}</td>
                          <td className="py-2 px-2">{item.strengthLevel}</td>
                          <td className="py-2 px-2 truncate max-w-[420px]" title={item.logicDetail || '由关键价位聚类形成'}>
                            {item.logicDetail || '由关键价位聚类形成'}
                          </td>
                        </tr>
                      </React.Fragment>
                    );
                  })
                )}
                {classicAnchor.index >= classicBoxes.length && classicBoxes.length > 0 ? (
                  <tr className="bg-amber-500/15 border-y border-amber-400/30">
                    <td className="py-2 px-2 text-amber-200 font-mono" colSpan={6}>
                      当前价 {currentPrice.toFixed(3)} · {classicAnchor.advice}
                    </td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>
          <div className="rounded-lg border border-white/10 bg-black/20 overflow-x-auto">
            <div className="px-2 py-1.5 text-xs text-secondary border-b border-white/10">手动区间（可编辑/删除）</div>
            <table className="w-full text-xs">
              <thead>
                <tr className="text-muted border-b border-white/10">
                  <th className="text-left py-2 px-2">下限</th>
                  <th className="text-left py-2 px-2">上限</th>
                  <th className="text-left py-2 px-2">强度</th>
                  <th className="text-left py-2 px-2">区间定义</th>
                  <th className="text-right py-2 px-2">操作栏</th>
                </tr>
              </thead>
              <tbody className="text-secondary">
                {manualRhinoZones.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="py-3 px-2 text-muted">暂无手动区间，可切换到“{secondaryModeLabel}”新增。</td>
                  </tr>
                ) : (
                  manualRhinoZones.map((zone) => {
                    const isEditing = editingId === zone.id;
                    return (
                      <tr key={zone.id} className="border-b border-white/5 align-top">
                        <td className="py-2 px-2 font-mono text-success">
                          {isEditing ? (
                            <input
                              type="number"
                              step="0.001"
                              value={editLower}
                              onChange={(e) => setEditLower(e.target.value)}
                              onKeyDown={(e) => handleEditKeyDown(e, zone)}
                              className="h-7 w-24 rounded-md border border-white/10 bg-black/30 px-2 text-xs text-white"
                            />
                          ) : zone.lower.toFixed(3)}
                        </td>
                        <td className="py-2 px-2 font-mono text-warning">
                          {isEditing ? (
                            <input
                              type="number"
                              step="0.001"
                              value={editUpper}
                              onChange={(e) => setEditUpper(e.target.value)}
                              onKeyDown={(e) => handleEditKeyDown(e, zone)}
                              className="h-7 w-24 rounded-md border border-white/10 bg-black/30 px-2 text-xs text-white"
                            />
                          ) : zone.upper.toFixed(3)}
                        </td>
                        <td className="py-2 px-2">
                          {isEditing ? (
                            <select
                              value={editStrength}
                              onChange={(e) => setEditStrength(e.target.value as RhinoStrength)}
                              onKeyDown={(e) => handleEditKeyDown(e, zone)}
                              className="h-7 rounded-md border border-white/10 bg-black/30 px-2 text-xs text-white"
                            >
                              <option value="弱">弱</option>
                              <option value="中">中</option>
                              <option value="强">强</option>
                              <option value="超强">超强</option>
                            </select>
                          ) : (
                            <span>{zone.strengthLevel}</span>
                          )}
                        </td>
                        <td className="py-2 px-2">
                          {isEditing ? (
                            <input
                              type="text"
                              value={editDefinition}
                              onChange={(e) => setEditDefinition(e.target.value)}
                              onKeyDown={(e) => handleEditKeyDown(e, zone)}
                              placeholder="区间定义（可选）"
                              className="h-7 w-full rounded-md border border-white/10 bg-black/30 px-2 text-xs text-white"
                            />
                          ) : (
                            <div className="truncate max-w-[320px]" title={zone.logicDetail || '手动定义区间'}>
                              {zone.logicDetail || '手动定义区间'}
                            </div>
                          )}
                        </td>
                        <td className="py-2 px-2 whitespace-nowrap text-right">
                          {isEditing ? (
                            <div className="flex items-center justify-end gap-1">
                              <button
                                type="button"
                                className={iconBtnSave}
                                disabled={savingKey === zone.id}
                                onClick={() => void saveEdit(zone)}
                                title="保存"
                                aria-label="保存"
                              >
                                {savingKey === zone.id ? '…' : '✓'}
                              </button>
                              <button
                                type="button"
                                className={iconBtnCancel}
                                onClick={() => setEditingId('')}
                                title="取消"
                                aria-label="取消"
                              >
                                ✕
                              </button>
                            </div>
                          ) : (
                            <div className="flex items-center justify-end gap-1">
                              <button
                                type="button"
                                className={iconBtnEdit}
                                onClick={() => startEdit(zone)}
                                title="修改"
                                aria-label="修改"
                              >
                                ✎
                              </button>
                              <button
                                type="button"
                                className={iconBtnDelete}
                                disabled={savingKey === zone.id}
                                onClick={() => void removeZone(zone)}
                                title="删除"
                                aria-label="删除"
                              >
                                🗑
                              </button>
                            </div>
                          )}
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {mode === 'rhino' && (
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <div className="text-xs text-secondary">按价格从高到低展示</div>
            <button
              type="button"
              className="text-xs text-cyan hover:text-white transition-colors"
              onClick={addDraft}
              disabled={Boolean(savingKey)}
            >
              增加区间
            </button>
          </div>

          {drafts.map((draft) => (
            <div key={draft.id} className="rounded-md border border-cyan/30 bg-cyan/5 p-2">
              <div className="grid grid-cols-1 md:grid-cols-6 gap-2 items-center">
                <input
                  type="number"
                  step="0.001"
                  placeholder="下限"
                  value={draft.lower}
                  disabled={savingKey === draft.id}
                  onKeyDown={(e) => handleDraftKeyDown(e, draft)}
                  onChange={(e) => setDrafts((prev) => prev.map((x) => (x.id === draft.id ? { ...x, lower: e.target.value } : x)))}
                  className="h-8 rounded-md border border-white/10 bg-black/30 px-2 text-xs text-white"
                />
                <input
                  type="number"
                  step="0.001"
                  placeholder="上限"
                  value={draft.upper}
                  disabled={savingKey === draft.id}
                  onKeyDown={(e) => handleDraftKeyDown(e, draft)}
                  onChange={(e) => setDrafts((prev) => prev.map((x) => (x.id === draft.id ? { ...x, upper: e.target.value } : x)))}
                  className="h-8 rounded-md border border-white/10 bg-black/30 px-2 text-xs text-white"
                />
                <select
                  value={draft.strength}
                  disabled={savingKey === draft.id}
                  onKeyDown={(e) => handleDraftKeyDown(e, draft)}
                  onChange={(e) => setDrafts((prev) => prev.map((x) => (x.id === draft.id ? { ...x, strength: e.target.value as RhinoStrength } : x)))}
                  className="h-8 rounded-md border border-white/10 bg-black/30 px-2 text-xs text-white"
                >
                  <option value="弱">弱</option>
                  <option value="中">中</option>
                  <option value="强">强</option>
                  <option value="超强">超强</option>
                </select>
                <input
                  type="text"
                  placeholder="区间定义（可选）"
                  value={draft.definition}
                  disabled={savingKey === draft.id}
                  onKeyDown={(e) => handleDraftKeyDown(e, draft)}
                  onChange={(e) => setDrafts((prev) => prev.map((x) => (x.id === draft.id ? { ...x, definition: e.target.value } : x)))}
                  className="h-8 rounded-md border border-white/10 bg-black/30 px-2 text-xs text-white"
                />
                <button
                  type="button"
                  className="h-8 rounded border border-emerald-400/30 bg-emerald-500/20 text-emerald-200 text-xs"
                  onClick={() => void saveDraft(draft)}
                  disabled={savingKey === draft.id}
                >
                  {savingKey === draft.id ? '保存中...' : '保存'}
                </button>
                <button
                  type="button"
                  className="h-8 rounded border border-white/15 bg-white/5 text-secondary text-xs"
                  onClick={() => removeDraft(draft.id)}
                  disabled={savingKey === draft.id}
                >
                  取消
                </button>
              </div>
            </div>
          ))}

          <div className="rounded-lg border border-white/10 bg-black/20 overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-muted border-b border-white/10">
                  <th className="text-left py-2 px-2">下限</th>
                  <th className="text-left py-2 px-2">上限</th>
                  <th className="text-left py-2 px-2">强度</th>
                  <th className="text-left py-2 px-2">区间定义</th>
                  <th className="text-right py-2 px-2">操作栏</th>
                </tr>
              </thead>
              <tbody className="text-secondary">
                {rhinoZones.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="py-3 px-2 text-muted">暂无区间，请点击右上角“增加区间”。</td>
                  </tr>
                ) : (
                  rhinoZones.map((zone, idx) => {
                    const shouldInsert = currentAnchor.index === idx;
                    const definition = buildDefinition(zone);
                    const expanded = expandedIds.includes(zone.id);
                    const isEditing = editingId === zone.id;
                    const canEdit = zone.sourceType === 'manual';
                    return (
                      <React.Fragment key={zone.id}>
                        {shouldInsert ? (
                          <tr className="bg-amber-500/15 border-y border-amber-400/30">
                            <td className="py-2 px-2 text-amber-200 font-mono" colSpan={5}>
                              当前价 {currentPrice.toFixed(3)} · {currentAnchor.advice}
                            </td>
                          </tr>
                        ) : null}
                        <tr className="border-b border-white/5 align-top">
                          <td className="py-2 px-2 font-mono text-success">
                            {isEditing ? (
                              <input
                                type="number"
                                step="0.001"
                                value={editLower}
                                onChange={(e) => setEditLower(e.target.value)}
                                onKeyDown={(e) => handleEditKeyDown(e, zone)}
                                className="h-7 w-24 rounded-md border border-white/10 bg-black/30 px-2 text-xs text-white"
                              />
                            ) : zone.lower.toFixed(3)}
                          </td>
                          <td className="py-2 px-2 font-mono text-warning">
                            {isEditing ? (
                              <input
                                type="number"
                                step="0.001"
                                value={editUpper}
                                onChange={(e) => setEditUpper(e.target.value)}
                                onKeyDown={(e) => handleEditKeyDown(e, zone)}
                                className="h-7 w-24 rounded-md border border-white/10 bg-black/30 px-2 text-xs text-white"
                              />
                            ) : zone.upper.toFixed(3)}
                          </td>
                          <td className="py-2 px-2">
                            {isEditing ? (
                              <select
                                value={editStrength}
                                onChange={(e) => setEditStrength(e.target.value as RhinoStrength)}
                                onKeyDown={(e) => handleEditKeyDown(e, zone)}
                                className="h-7 rounded-md border border-white/10 bg-black/30 px-2 text-xs text-white"
                              >
                                <option value="弱">弱</option>
                                <option value="中">中</option>
                                <option value="强">强</option>
                                <option value="超强">超强</option>
                              </select>
                            ) : (
                              <span>{zone.strengthLevel}</span>
                            )}
                          </td>
                          <td className="py-2 px-2">
                            {isEditing && canEdit ? (
                              <input
                                type="text"
                                value={editDefinition}
                                onChange={(e) => setEditDefinition(e.target.value)}
                                onKeyDown={(e) => handleEditKeyDown(e, zone)}
                                placeholder="区间定义（可选）"
                                className="h-7 w-full rounded-md border border-white/10 bg-black/30 px-2 text-xs text-white"
                              />
                            ) : (
                              <>
                                <div className={expanded ? 'whitespace-normal break-words' : 'truncate max-w-[440px]'} title={definition}>
                                  {definition}
                                </div>
                                {definition.length > 40 ? (
                                  <button
                                    type="button"
                                    className="text-[11px] text-cyan hover:text-white mt-0.5"
                                    onClick={() => toggleExpand(zone.id)}
                                  >
                                    {expanded ? '收起' : '展开'}
                                  </button>
                                ) : null}
                              </>
                            )}
                          </td>
                          <td className="py-2 px-2 whitespace-nowrap text-right">
                            {canEdit ? (
                              isEditing ? (
                                <div className="flex items-center justify-end gap-1">
                                  <button
                                    type="button"
                                    className={iconBtnSave}
                                    disabled={savingKey === zone.id}
                                    onClick={() => void saveEdit(zone)}
                                    title="保存"
                                    aria-label="保存"
                                  >
                                    {savingKey === zone.id ? '…' : '✓'}
                                  </button>
                                  <button
                                    type="button"
                                    className={iconBtnCancel}
                                    onClick={() => setEditingId('')}
                                    title="取消"
                                    aria-label="取消"
                                  >
                                    ✕
                                  </button>
                                </div>
                              ) : (
                                <div className="flex items-center justify-end gap-1">
                                  <button
                                    type="button"
                                    className={iconBtnEdit}
                                    onClick={() => startEdit(zone)}
                                    title="修改"
                                    aria-label="修改"
                                  >
                                    ✎
                                  </button>
                                  <button
                                    type="button"
                                    className={iconBtnDelete}
                                    disabled={savingKey === zone.id}
                                    onClick={() => void removeZone(zone)}
                                    title="删除"
                                    aria-label="删除"
                                  >
                                    🗑
                                  </button>
                                </div>
                              )
                            ) : (
                              <span className="text-muted">系统区间</span>
                            )}
                          </td>
                        </tr>
                      </React.Fragment>
                    );
                  })
                )}
                {currentAnchor.index >= rhinoZones.length && rhinoZones.length > 0 ? (
                  <tr className="bg-amber-500/15 border-y border-amber-400/30">
                    <td className="py-2 px-2 text-amber-200 font-mono" colSpan={5}>
                      当前价 {currentPrice.toFixed(3)} · {currentAnchor.advice}
                    </td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>
          {errorText ? <div className="text-xs text-red-300">{errorText}</div> : null}
        </div>
      )}
    </Card>
  );
};

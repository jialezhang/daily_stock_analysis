import type React from 'react';
import { useEffect, useMemo, useRef, useState } from 'react';
import { Select } from '../common';
import type { ConfigValidationIssue } from '../../types/systemConfig';

type EditorMode = 'structured' | 'json';

type PortfolioHoldingRow = {
  ticker: string;
  name: string;
  market: string;
  shares: string;
  avgCost: string;
  currentPrice: string;
  valueCny: string;
  dailyChangePct: string;
  sector: string;
  style: string;
  betaLevel: string;
};

type PortfolioHoldingsEditorState = {
  totalValueCny: string;
  cashCny: string;
  cashUsd: string;
  cashHkd: string;
  cryptoValueCny: string;
  peakValueCny: string;
  initialCapital: string;
  targetReturn: string;
  holdings: PortfolioHoldingRow[];
};

type PortfolioTagRow = {
  ticker: string;
  sector: string;
  style: string;
  beta: string;
};

interface PortfolioConfigEditorProps {
  configKey: string;
  value: string;
  disabled?: boolean;
  issues?: ConfigValidationIssue[];
  onChange: (value: string) => void;
}

const HOLDING_MARKET_OPTIONS = [
  { value: 'US', label: '美股' },
  { value: 'HK', label: '港股' },
  { value: 'A', label: 'A股' },
  { value: 'CRYPTO', label: '加密' },
];

const HOLDING_BETA_OPTIONS = [
  { value: 'low', label: 'low' },
  { value: 'medium', label: 'medium' },
  { value: 'high', label: 'high' },
  { value: 'very_high', label: 'very_high' },
];

const EMPTY_HOLDING_ROW = (): PortfolioHoldingRow => ({
  ticker: '',
  name: '',
  market: 'US',
  shares: '',
  avgCost: '',
  currentPrice: '',
  valueCny: '',
  dailyChangePct: '',
  sector: '',
  style: '',
  betaLevel: 'medium',
});

const EMPTY_TAG_ROW = (): PortfolioTagRow => ({
  ticker: '',
  sector: '',
  style: '',
  beta: 'medium',
});

function formatEditorValue(value: unknown): string {
  if (value === null || value === undefined) {
    return '';
  }
  return String(value);
}

function toPrettyJson(value: unknown): string {
  return JSON.stringify(value, null, 2);
}

function toSerializableNumber(value: string): number | string | undefined {
  const text = value.trim();
  if (!text) {
    return undefined;
  }
  const numeric = Number(text);
  return Number.isFinite(numeric) ? numeric : text;
}

function parseHoldingsEditor(value: string): PortfolioHoldingsEditorState | null {
  const text = value.trim();
  if (!text) {
    return {
      totalValueCny: '',
      cashCny: '',
      cashUsd: '',
      cashHkd: '',
      cryptoValueCny: '',
      peakValueCny: '',
      initialCapital: '',
      targetReturn: '',
      holdings: [],
    };
  }

  try {
    const parsed = JSON.parse(text);
    const payload = Array.isArray(parsed) ? { holdings: parsed } : parsed;
    if (!payload || typeof payload !== 'object') {
      return null;
    }

    const record = payload as Record<string, unknown>;
    const rawHoldings = Array.isArray(record.holdings)
      ? record.holdings
      : (Array.isArray(record.positions) ? record.positions : []);

    return {
      totalValueCny: formatEditorValue(record.total_value_cny),
      cashCny: formatEditorValue(record.cash_cny),
      cashUsd: formatEditorValue(record.cash_usd),
      cashHkd: formatEditorValue(record.cash_hkd),
      cryptoValueCny: formatEditorValue(record.crypto_value_cny),
      peakValueCny: formatEditorValue(record.peak_value_cny),
      initialCapital: formatEditorValue(record.initial_capital),
      targetReturn: formatEditorValue(record.target_return),
      holdings: rawHoldings
        .filter((item) => item && typeof item === 'object')
        .map((item) => {
          const row = item as Record<string, unknown>;
          return {
            ticker: formatEditorValue(row.ticker ?? row.symbol).toUpperCase(),
            name: formatEditorValue(row.name ?? row.display_name),
            market: formatEditorValue(row.market).toUpperCase() || 'US',
            shares: formatEditorValue(row.shares ?? row.quantity),
            avgCost: formatEditorValue(row.avg_cost ?? row.cost_price ?? row.cost),
            currentPrice: formatEditorValue(row.current_price ?? row.latest_price ?? row.price),
            valueCny: formatEditorValue(
              row.value_cny ?? row.market_value_cny ?? row.market_value_output ?? row.value,
            ),
            dailyChangePct: formatEditorValue(row.daily_change_pct ?? row.change_pct),
            sector: formatEditorValue(row.sector),
            style: formatEditorValue(row.style),
            betaLevel: formatEditorValue(row.beta_level ?? row.beta) || 'medium',
          };
        }),
    };
  } catch {
    return null;
  }
}

function serializeHoldingsEditor(state: PortfolioHoldingsEditorState): string {
  const payload: Record<string, unknown> = {};
  const rootFields: Array<[string, string]> = [
    ['total_value_cny', state.totalValueCny],
    ['cash_cny', state.cashCny],
    ['cash_usd', state.cashUsd],
    ['cash_hkd', state.cashHkd],
    ['crypto_value_cny', state.cryptoValueCny],
    ['peak_value_cny', state.peakValueCny],
    ['initial_capital', state.initialCapital],
    ['target_return', state.targetReturn],
  ];

  rootFields.forEach(([key, rawValue]) => {
    const value = toSerializableNumber(rawValue);
    if (value !== undefined) {
      payload[key] = value;
    }
  });

  payload.holdings = state.holdings
    .map((row) => {
      const nextRow: Record<string, unknown> = {};
      const ticker = row.ticker.trim().toUpperCase();
      const name = row.name.trim();
      const market = row.market.trim().toUpperCase();
      const sector = row.sector.trim();
      const style = row.style.trim();
      const betaLevel = row.betaLevel.trim();

      if (ticker) {
        nextRow.ticker = ticker;
      }
      if (name) {
        nextRow.name = name;
      }
      if (market) {
        nextRow.market = market;
      }
      if (sector) {
        nextRow.sector = sector;
      }
      if (style) {
        nextRow.style = style;
      }
      if (betaLevel) {
        nextRow.beta_level = betaLevel;
      }

      [
        ['shares', row.shares],
        ['avg_cost', row.avgCost],
        ['current_price', row.currentPrice],
        ['value_cny', row.valueCny],
        ['daily_change_pct', row.dailyChangePct],
      ].forEach(([key, rawValue]) => {
        const value = toSerializableNumber(rawValue);
        if (value !== undefined) {
          nextRow[key] = value;
        }
      });

      return nextRow;
    })
    .filter((row) => Object.keys(row).length > 0);

  return toPrettyJson(payload);
}

function parseTagsEditor(value: string): PortfolioTagRow[] | null {
  const text = value.trim();
  if (!text) {
    return [];
  }

  try {
    const parsed = JSON.parse(text);
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
      return null;
    }

    return Object.entries(parsed as Record<string, unknown>)
      .filter(([, payload]) => payload && typeof payload === 'object' && !Array.isArray(payload))
      .map(([ticker, payload]) => {
        const row = payload as Record<string, unknown>;
        return {
          ticker: String(ticker || '').trim().toUpperCase(),
          sector: formatEditorValue(row.sector),
          style: formatEditorValue(row.style),
          beta: formatEditorValue(row.beta_level ?? row.beta) || 'medium',
        };
      });
  } catch {
    return null;
  }
}

function serializeTagsEditor(rows: PortfolioTagRow[]): string {
  const payload = rows.reduce<Record<string, Record<string, string>>>((accumulator, row) => {
    const ticker = row.ticker.trim().toUpperCase();
    if (!ticker) {
      return accumulator;
    }

    const nextRow: Record<string, string> = {};
    if (row.sector.trim()) {
      nextRow.sector = row.sector.trim();
    }
    if (row.style.trim()) {
      nextRow.style = row.style.trim();
    }
    if (row.beta.trim()) {
      nextRow.beta = row.beta.trim();
    }
    accumulator[ticker] = nextRow;
    return accumulator;
  }, {});

  return toPrettyJson(payload);
}

function modeButtonClass(active: boolean): string {
  return active
    ? 'rounded border border-cyan/50 bg-cyan/10 px-2 py-1 text-[11px] text-cyan'
    : 'rounded border border-white/12 bg-black/20 px-2 py-1 text-[11px] text-secondary hover:border-white/20 hover:text-white';
}

function inputValue(value: string): string {
  return value ?? '';
}

export const PortfolioConfigEditor: React.FC<PortfolioConfigEditorProps> = ({
  configKey,
  value,
  disabled = false,
  issues = [],
  onChange,
}) => {
  const [mode, setMode] = useState<EditorMode>('structured');
  const lastStructuredSerializedRef = useRef<string>('');
  const parsedHoldingsValue = useMemo(() => (
    configKey === 'PORTFOLIO_HOLDINGS' ? parseHoldingsEditor(value) : null
  ), [configKey, value]);
  const parsedTagValue = useMemo(() => (
    configKey === 'PORTFOLIO_STOCK_TAGS' ? parseTagsEditor(value) : null
  ), [configKey, value]);
  const [holdingsDraft, setHoldingsDraft] = useState<PortfolioHoldingsEditorState | null>(parsedHoldingsValue);
  const [tagDraft, setTagDraft] = useState<PortfolioTagRow[] | null>(parsedTagValue);
  const holdingsState = configKey === 'PORTFOLIO_HOLDINGS' ? holdingsDraft : null;
  const tagState = configKey === 'PORTFOLIO_STOCK_TAGS' ? tagDraft : null;
  const hasStructuredState = configKey === 'PORTFOLIO_HOLDINGS' ? holdingsState !== null : tagState !== null;
  const parseIssue = issues.find((issue) => issue.code === 'invalid_format');

  useEffect(() => {
    if (configKey === 'PORTFOLIO_HOLDINGS') {
      if (parsedHoldingsValue === null) {
        setHoldingsDraft(null);
      } else if (value !== lastStructuredSerializedRef.current || holdingsDraft === null) {
        setHoldingsDraft(parsedHoldingsValue);
      }
    }

    if (configKey === 'PORTFOLIO_STOCK_TAGS') {
      if (parsedTagValue === null) {
        setTagDraft(null);
      } else if (value !== lastStructuredSerializedRef.current || tagDraft === null) {
        setTagDraft(parsedTagValue);
      }
    }

    if (!hasStructuredState) {
      setMode('json');
    }
  }, [configKey, hasStructuredState, holdingsDraft, parsedHoldingsValue, parsedTagValue, tagDraft, value]);

  const commitHoldings = (nextState: PortfolioHoldingsEditorState) => {
    setHoldingsDraft(nextState);
    const serialized = serializeHoldingsEditor(nextState);
    lastStructuredSerializedRef.current = serialized;
    onChange(serialized);
  };

  const commitTags = (nextState: PortfolioTagRow[]) => {
    setTagDraft(nextState);
    const serialized = serializeTagsEditor(nextState);
    lastStructuredSerializedRef.current = serialized;
    onChange(serialized);
  };

  const renderRawEditor = () => (
    <div className="space-y-2">
      <textarea
        className="input-terminal min-h-[240px] resize-y font-mono text-xs"
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
      />
      <p className="text-[11px] leading-5 text-secondary">
        结构化编辑会回写为 JSON。当前内容无法安全解析时，可在这里直接修正。
      </p>
    </div>
  );

  if (configKey === 'PORTFOLIO_HOLDINGS' && holdingsState) {
    return (
      <div className="space-y-3">
        <div className="flex items-center justify-between gap-2">
          <p className="text-[11px] text-secondary">支持结构化编辑与原始 JSON 双模式。</p>
          <div className="flex items-center gap-2">
            <button type="button" className={modeButtonClass(mode === 'structured')} onClick={() => setMode('structured')}>
              结构化
            </button>
            <button type="button" className={modeButtonClass(mode === 'json')} onClick={() => setMode('json')}>
              JSON
            </button>
          </div>
        </div>

        {mode === 'json' ? renderRawEditor() : (
          <div className="space-y-3">
            <div className="grid grid-cols-1 gap-2 md:grid-cols-2 xl:grid-cols-4">
              {[
                ['总资产 CNY', 'totalValueCny'],
                ['现金 CNY', 'cashCny'],
                ['现金 USD', 'cashUsd'],
                ['现金 HKD', 'cashHkd'],
                ['加密资产 CNY', 'cryptoValueCny'],
                ['历史峰值 CNY', 'peakValueCny'],
                ['初始本金 CNY', 'initialCapital'],
                ['目标收益率', 'targetReturn'],
              ].map(([label, field]) => (
                <label key={field} className="space-y-1">
                  <span className="text-[11px] text-muted">{label}</span>
                  <input
                    type="text"
                    className="input-terminal"
                    value={inputValue(holdingsState[field as keyof PortfolioHoldingsEditorState] as string)}
                    disabled={disabled}
                    onChange={(event) => {
                      commitHoldings({
                        ...holdingsState,
                        [field]: event.target.value,
                      });
                    }}
                  />
                </label>
              ))}
            </div>

            <div className="rounded-xl border border-white/8 bg-black/20 p-3">
              <div className="mb-3 flex items-center justify-between gap-2">
                <div>
                  <div className="text-sm font-semibold text-white">持仓列表</div>
                  <div className="text-[11px] text-secondary">空白行不会写入最终 JSON。</div>
                </div>
                <button
                  type="button"
                  className="btn-secondary !px-3 !py-2 text-xs"
                  disabled={disabled}
                  onClick={() => commitHoldings({
                    ...holdingsState,
                    holdings: [...holdingsState.holdings, EMPTY_HOLDING_ROW()],
                  })}
                >
                  添加持仓
                </button>
              </div>

              <div className="space-y-3">
                {holdingsState.holdings.length === 0 ? (
                  <div className="rounded-lg border border-dashed border-white/10 px-3 py-4 text-xs text-muted">
                    暂无持仓，点击右上角添加。
                  </div>
                ) : holdingsState.holdings.map((row, index) => (
                  <div key={`portfolio-holding-row-${index}`} className="rounded-lg border border-white/10 bg-black/20 p-3">
                    <div className="mb-2 flex items-center justify-between gap-2">
                      <div className="text-[11px] text-muted">持仓 #{index + 1}</div>
                      <button
                        type="button"
                        className="btn-secondary !px-3 !py-1.5 text-[11px]"
                        disabled={disabled}
                        onClick={() => commitHoldings({
                          ...holdingsState,
                          holdings: holdingsState.holdings.filter((_, rowIndex) => rowIndex !== index),
                        })}
                      >
                        删除
                      </button>
                    </div>

                    <div className="grid grid-cols-1 gap-2 md:grid-cols-2 xl:grid-cols-4">
                      <label className="space-y-1">
                        <span className="text-[11px] text-muted">Ticker</span>
                        <input
                          type="text"
                          className="input-terminal"
                          value={row.ticker}
                          disabled={disabled}
                          onChange={(event) => {
                            const nextRows = holdingsState.holdings.map((item, rowIndex) => (
                              rowIndex === index ? { ...item, ticker: event.target.value.toUpperCase() } : item
                            ));
                            commitHoldings({ ...holdingsState, holdings: nextRows });
                          }}
                        />
                      </label>

                      <label className="space-y-1">
                        <span className="text-[11px] text-muted">名称</span>
                        <input
                          type="text"
                          className="input-terminal"
                          value={row.name}
                          disabled={disabled}
                          onChange={(event) => {
                            const nextRows = holdingsState.holdings.map((item, rowIndex) => (
                              rowIndex === index ? { ...item, name: event.target.value } : item
                            ));
                            commitHoldings({ ...holdingsState, holdings: nextRows });
                          }}
                        />
                      </label>

                      <label className="space-y-1">
                        <span className="text-[11px] text-muted">市场</span>
                        <Select
                          value={row.market || 'US'}
                          onChange={(nextValue) => {
                            const nextRows = holdingsState.holdings.map((item, rowIndex) => (
                              rowIndex === index ? { ...item, market: nextValue } : item
                            ));
                            commitHoldings({ ...holdingsState, holdings: nextRows });
                          }}
                          options={HOLDING_MARKET_OPTIONS}
                          disabled={disabled}
                          placeholder=""
                        />
                      </label>

                      <label className="space-y-1">
                        <span className="text-[11px] text-muted">Beta</span>
                        <Select
                          value={row.betaLevel || 'medium'}
                          onChange={(nextValue) => {
                            const nextRows = holdingsState.holdings.map((item, rowIndex) => (
                              rowIndex === index ? { ...item, betaLevel: nextValue } : item
                            ));
                            commitHoldings({ ...holdingsState, holdings: nextRows });
                          }}
                          options={HOLDING_BETA_OPTIONS}
                          disabled={disabled}
                          placeholder=""
                        />
                      </label>

                      {[
                        ['股数', 'shares'],
                        ['成本价', 'avgCost'],
                        ['现价', 'currentPrice'],
                        ['市值 CNY', 'valueCny'],
                        ['日涨跌幅 %', 'dailyChangePct'],
                        ['板块', 'sector'],
                        ['风格', 'style'],
                      ].map(([label, field]) => (
                        <label key={`${field}-${index}`} className="space-y-1">
                          <span className="text-[11px] text-muted">{label}</span>
                          <input
                            type="text"
                            className="input-terminal"
                            value={inputValue(row[field as keyof PortfolioHoldingRow])}
                            disabled={disabled}
                            onChange={(event) => {
                              const nextRows = holdingsState.holdings.map((item, rowIndex) => (
                                rowIndex === index ? { ...item, [field]: event.target.value } : item
                              ));
                              commitHoldings({ ...holdingsState, holdings: nextRows });
                            }}
                          />
                        </label>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {parseIssue ? (
          <p className="text-[11px] text-warning">{parseIssue.message}</p>
        ) : null}
      </div>
    );
  }

  if (configKey === 'PORTFOLIO_STOCK_TAGS' && tagState) {
    return (
      <div className="space-y-3">
        <div className="flex items-center justify-between gap-2">
          <p className="text-[11px] text-secondary">Ticker 为空的行不会写入最终 JSON。</p>
          <div className="flex items-center gap-2">
            <button type="button" className={modeButtonClass(mode === 'structured')} onClick={() => setMode('structured')}>
              结构化
            </button>
            <button type="button" className={modeButtonClass(mode === 'json')} onClick={() => setMode('json')}>
              JSON
            </button>
          </div>
        </div>

        {mode === 'json' ? renderRawEditor() : (
          <div className="space-y-3 rounded-xl border border-white/8 bg-black/20 p-3">
            <div className="flex items-center justify-between gap-2">
              <div>
                <div className="text-sm font-semibold text-white">持仓标签映射</div>
                <div className="text-[11px] text-secondary">用于覆盖 sector / style / beta。</div>
              </div>
              <button
                type="button"
                className="btn-secondary !px-3 !py-2 text-xs"
                disabled={disabled}
                onClick={() => commitTags([...tagState, EMPTY_TAG_ROW()])}
              >
                添加标签
              </button>
            </div>

            <div className="space-y-3">
              {tagState.length === 0 ? (
                <div className="rounded-lg border border-dashed border-white/10 px-3 py-4 text-xs text-muted">
                  暂无覆盖标签，点击右上角添加。
                </div>
              ) : tagState.map((row, index) => (
                <div key={`portfolio-tag-row-${index}`} className="grid grid-cols-1 gap-2 rounded-lg border border-white/10 bg-black/20 p-3 md:grid-cols-2 xl:grid-cols-5">
                  <label className="space-y-1">
                    <span className="text-[11px] text-muted">Ticker</span>
                    <input
                      type="text"
                      className="input-terminal"
                      value={row.ticker}
                      disabled={disabled}
                      onChange={(event) => {
                        const nextRows = tagState.map((item, rowIndex) => (
                          rowIndex === index ? { ...item, ticker: event.target.value.toUpperCase() } : item
                        ));
                        commitTags(nextRows);
                      }}
                    />
                  </label>

                  <label className="space-y-1">
                    <span className="text-[11px] text-muted">Sector</span>
                    <input
                      type="text"
                      className="input-terminal"
                      value={row.sector}
                      disabled={disabled}
                      onChange={(event) => {
                        const nextRows = tagState.map((item, rowIndex) => (
                          rowIndex === index ? { ...item, sector: event.target.value } : item
                        ));
                        commitTags(nextRows);
                      }}
                    />
                  </label>

                  <label className="space-y-1">
                    <span className="text-[11px] text-muted">Style</span>
                    <input
                      type="text"
                      className="input-terminal"
                      value={row.style}
                      disabled={disabled}
                      onChange={(event) => {
                        const nextRows = tagState.map((item, rowIndex) => (
                          rowIndex === index ? { ...item, style: event.target.value } : item
                        ));
                        commitTags(nextRows);
                      }}
                    />
                  </label>

                  <label className="space-y-1">
                    <span className="text-[11px] text-muted">Beta</span>
                    <Select
                      value={row.beta || 'medium'}
                      onChange={(nextValue) => {
                        const nextRows = tagState.map((item, rowIndex) => (
                          rowIndex === index ? { ...item, beta: nextValue } : item
                        ));
                        commitTags(nextRows);
                      }}
                      options={HOLDING_BETA_OPTIONS}
                      disabled={disabled}
                      placeholder=""
                    />
                  </label>

                  <div className="flex items-end">
                    <button
                      type="button"
                      className="btn-secondary !px-3 !py-2 text-xs"
                      disabled={disabled}
                      onClick={() => commitTags(tagState.filter((_, rowIndex) => rowIndex !== index))}
                    >
                      删除
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {parseIssue ? (
          <p className="text-[11px] text-warning">{parseIssue.message}</p>
        ) : null}
      </div>
    );
  }

  return renderRawEditor();
};

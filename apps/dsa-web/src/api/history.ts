import apiClient from './index';
import { toCamelCase } from './utils';
import type {
  HistoryListResponse,
  HistoryItem,
  HistoryFilters,
  AnalysisReport,
  NewsIntelResponse,
  NewsIntelItem,
  HistoryDeleteResponse,
  HistoryRefreshRequest,
  HistoryRefreshResponse,
  HistoryModuleKey,
  ModuleRefreshStartResponse,
  ModuleRefreshJobsResponse,
  RhinoZoneUpsertRequest,
  RhinoZoneUpsertResponse,
  RhinoZoneDeleteResponse,
  PositionManagementUpsertRequest,
  PositionManagementResponse,
} from '../types/analysis';

// ============ API 接口 ============

export interface GetHistoryListParams extends HistoryFilters {
  page?: number;
  limit?: number;
}

export const historyApi = {
  /**
   * 获取历史分析列表
   * @param params 筛选和分页参数
   */
  getList: async (params: GetHistoryListParams = {}): Promise<HistoryListResponse> => {
    const { stockCode, startDate, endDate, page = 1, limit = 20 } = params;

    const queryParams: Record<string, string | number> = { page, limit };
    if (stockCode) queryParams.stock_code = stockCode;
    if (startDate) queryParams.start_date = startDate;
    if (endDate) queryParams.end_date = endDate;

    const response = await apiClient.get<Record<string, unknown>>('/api/v1/history', {
      params: queryParams,
    });

    const data = toCamelCase<{ total: number; page: number; limit: number; items: HistoryItem[] }>(response.data);
    return {
      total: data.total,
      page: data.page,
      limit: data.limit,
      items: data.items.map(item => toCamelCase<HistoryItem>(item)),
    };
  },

  /**
   * 获取历史报告详情
   * @param recordId 分析历史记录主键 ID（使用 ID 而非 query_id，因为 query_id 在批量分析时可能重复）
   */
  getDetail: async (recordId: number): Promise<AnalysisReport> => {
    const response = await apiClient.get<Record<string, unknown>>(`/api/v1/history/${recordId}`);
    return toCamelCase<AnalysisReport>(response.data);
  },

  /**
   * 获取历史报告关联新闻
   * @param recordId 分析历史记录主键 ID
   * @param limit 返回数量限制
   */
  getNews: async (recordId: number, limit = 20, refresh = false): Promise<NewsIntelResponse> => {
    const response = await apiClient.get<Record<string, unknown>>(`/api/v1/history/${recordId}/news`, {
      params: { limit, refresh },
    });

    const data = toCamelCase<NewsIntelResponse>(response.data);
    return {
      total: data.total,
      items: (data.items || []).map(item => toCamelCase<NewsIntelItem>(item)),
    };
  },

  /**
   * 删除历史分析记录
   * @param recordId 分析历史记录主键 ID
   */
  deleteRecord: async (recordId: number): Promise<HistoryDeleteResponse> => {
    const response = await apiClient.delete<Record<string, unknown>>(`/api/v1/history/${recordId}`);
    return toCamelCase<HistoryDeleteResponse>(response.data);
  },

  /**
   * 刷新历史分析记录（全量或子模块）
   * @param recordId 分析历史记录主键 ID
   * @param payload 刷新参数
   */
  refreshRecord: async (recordId: number, payload: HistoryRefreshRequest): Promise<HistoryRefreshResponse> => {
    const response = await apiClient.post<Record<string, unknown>>(`/api/v1/history/${recordId}/refresh`, {
      mode: payload.mode,
      modules: payload.modules || [],
    });
    return toCamelCase<HistoryRefreshResponse>(response.data);
  },

  /**
   * 异步启动模块刷新任务
   * @param recordId 分析历史记录主键 ID
   * @param module 模块名，或 full
   */
  startModuleRefresh: async (recordId: number, module: HistoryModuleKey): Promise<ModuleRefreshStartResponse> => {
    const response = await apiClient.post<Record<string, unknown>>(`/api/v1/history/${recordId}/modules/${module}/refresh`);
    return toCamelCase<ModuleRefreshStartResponse>(response.data);
  },

  /**
   * 查询模块刷新任务状态
   * @param recordId 分析历史记录主键 ID
   */
  getModuleRefreshJobs: async (recordId: number, limit = 20): Promise<ModuleRefreshJobsResponse> => {
    const response = await apiClient.get<Record<string, unknown>>(`/api/v1/history/${recordId}/modules/refresh-jobs`, {
      params: { limit },
    });
    return toCamelCase<ModuleRefreshJobsResponse>(response.data);
  },

  /**
   * 手动新增 Rhino 价格区间（持久化）
   * @param recordId 分析历史记录主键 ID
   * @param payload 区间参数
   */
  addRhinoZone: async (recordId: number, payload: RhinoZoneUpsertRequest): Promise<RhinoZoneUpsertResponse> => {
    const response = await apiClient.post<Record<string, unknown>>(`/api/v1/history/${recordId}/rhino-zones`, {
      upper: payload.upper,
      lower: payload.lower,
      strength_level: payload.strengthLevel,
      name: payload.name,
      definition: payload.definition,
    });
    return toCamelCase<RhinoZoneUpsertResponse>(response.data);
  },

  /**
   * 修改手动 Rhino 价格区间（持久化）
   * @param recordId 分析历史记录主键 ID
   * @param zoneId 区间 ID
   * @param payload 区间参数
   */
  updateRhinoZone: async (
    recordId: number,
    zoneId: string,
    payload: RhinoZoneUpsertRequest,
  ): Promise<RhinoZoneUpsertResponse> => {
    const response = await apiClient.put<Record<string, unknown>>(
      `/api/v1/history/${recordId}/rhino-zones/${encodeURIComponent(zoneId)}`,
      {
        upper: payload.upper,
        lower: payload.lower,
        strength_level: payload.strengthLevel,
        name: payload.name,
        definition: payload.definition,
      },
    );
    return toCamelCase<RhinoZoneUpsertResponse>(response.data);
  },

  /**
   * 删除手动 Rhino 价格区间（持久化）
   * @param recordId 分析历史记录主键 ID
   * @param zoneId 区间 ID
   */
  deleteRhinoZone: async (recordId: number, zoneId: string): Promise<RhinoZoneDeleteResponse> => {
    const response = await apiClient.delete<Record<string, unknown>>(`/api/v1/history/${recordId}/rhino-zones/${encodeURIComponent(zoneId)}`);
    return toCamelCase<RhinoZoneDeleteResponse>(response.data);
  },

  /**
   * 获取仓位管理模块
   */
  getPositionManagement: async (recordId: number): Promise<PositionManagementResponse> => {
    const response = await apiClient.get<Record<string, unknown>>(`/api/v1/history/${recordId}/position-management`);
    return toCamelCase<PositionManagementResponse>(response.data);
  },

  /**
   * 保存仓位管理模块
   */
  upsertPositionManagement: async (
    recordId: number,
    payload: PositionManagementUpsertRequest,
  ): Promise<PositionManagementResponse> => {
    const response = await apiClient.put<Record<string, unknown>>(`/api/v1/history/${recordId}/position-management`, {
      target: {
        annual_return_target_pct: payload.target.annualReturnTargetPct,
        base_currency: payload.target.baseCurrency,
        usd_cny: payload.target.usdCny,
        usd_hkd: payload.target.usdHkd,
      },
      holdings: payload.holdings.map((item) => ({
        id: item.id,
        market_type: item.marketType,
        asset_class: item.assetClass,
        symbol: item.symbol,
        name: item.name,
        quantity: item.quantity,
        avg_cost: item.avgCost,
        current_price: item.currentPrice,
        previous_close: item.previousClose,
        currency: item.currency,
      })),
      refresh_benchmarks: payload.refreshBenchmarks ?? true,
    });
    return toCamelCase<PositionManagementResponse>(response.data);
  },
};

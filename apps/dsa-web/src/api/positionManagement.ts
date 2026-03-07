import apiClient from './index';
import { toCamelCase } from './utils';
import type {
  PositionReviewHistoryResponse,
  PositionManagementResponse,
  PositionReviewLatestResponse,
  PositionReviewNoteUpsertResponse,
  PositionReviewPushResponse,
  PositionManagementUpsertRequest,
} from '../types/positionManagement';

export const positionManagementApi = {
  getModule: async (): Promise<PositionManagementResponse> => {
    const response = await apiClient.get<Record<string, unknown>>('/api/v1/position-management');
    return toCamelCase<PositionManagementResponse>(response.data);
  },

  upsertModule: async (payload: PositionManagementUpsertRequest): Promise<PositionManagementResponse> => {
    const response = await apiClient.put<Record<string, unknown>>('/api/v1/position-management', {
      target: {
        initial_position: payload.target.initialPosition,
        output_currency: payload.target.outputCurrency,
        target_return_pct: payload.target.targetReturnPct,
      },
      holdings: payload.holdings.map((item) => ({
        id: item.id,
        asset_primary: item.assetPrimary,
        asset_secondary: item.assetSecondary,
        symbol: item.symbol,
        name: item.name,
        quantity: item.quantity,
        current_price: item.currentPrice,
        previous_close: item.previousClose,
        currency: item.currency,
      })),
      macro_events: payload.macroEvents || [],
      notes: payload.notes || '',
      refresh_benchmarks: payload.refreshBenchmarks ?? true,
    });
    return toCamelCase<PositionManagementResponse>(response.data);
  },

  refreshModule: async (): Promise<PositionManagementResponse> => {
    const response = await apiClient.post<Record<string, unknown>>('/api/v1/position-management/refresh');
    return toCamelCase<PositionManagementResponse>(response.data);
  },

  pushDailyReview: async (): Promise<PositionReviewPushResponse> => {
    const response = await apiClient.post<Record<string, unknown>>(
      '/api/v1/position-management/review-push',
      undefined,
      { timeout: 120000 },
    );
    return toCamelCase<PositionReviewPushResponse>(response.data);
  },

  getLatestDailyReview: async (): Promise<PositionReviewLatestResponse> => {
    const response = await apiClient.get<Record<string, unknown>>('/api/v1/position-management/review/latest');
    return toCamelCase<PositionReviewLatestResponse>(response.data);
  },

  getReviewHistory: async (limit = 120): Promise<PositionReviewHistoryResponse> => {
    const response = await apiClient.get<Record<string, unknown>>('/api/v1/position-management/review/history', {
      params: { limit },
    });
    return toCamelCase<PositionReviewHistoryResponse>(response.data);
  },

  saveReviewNote: async (reviewDate: string, note: string): Promise<PositionReviewNoteUpsertResponse> => {
    const response = await apiClient.put<Record<string, unknown>>(
      `/api/v1/position-management/review/${encodeURIComponent(reviewDate)}/note`,
      { note },
    );
    return toCamelCase<PositionReviewNoteUpsertResponse>(response.data);
  },
};

import apiClient from './index';
import { toCamelCase } from './utils';
import type {
  DailyReviewHistoryResponse,
  DailyReviewLatestResponse,
  DailyReviewPushResponse,
  DailyReviewRunRequest,
  DailyReviewRunResponse,
  ReviewDimension,
} from '../types/dailyReview';

export const dailyReviewApi = {
  getHistory: async (dimension: ReviewDimension, limit = 180): Promise<DailyReviewHistoryResponse> => {
    const response = await apiClient.get<Record<string, unknown>>('/api/v1/daily-review/history', {
      params: { dimension, limit },
    });
    return toCamelCase<DailyReviewHistoryResponse>(response.data);
  },

  getLatest: async (dimension: ReviewDimension = 'day'): Promise<DailyReviewLatestResponse> => {
    const response = await apiClient.get<Record<string, unknown>>('/api/v1/daily-review/latest', {
      params: { dimension },
    });
    return toCamelCase<DailyReviewLatestResponse>(response.data);
  },

  runReview: async (payload?: DailyReviewRunRequest): Promise<DailyReviewRunResponse> => {
    const response = await apiClient.post<Record<string, unknown>>(
      '/api/v1/daily-review/run',
      {
        push_telegram: payload?.pushTelegram ?? false,
        use_llm: payload?.useLlm ?? false,
      },
      { timeout: 180000 },
    );
    return toCamelCase<DailyReviewRunResponse>(response.data);
  },

  pushByDate: async (reviewDate: string): Promise<DailyReviewPushResponse> => {
    const response = await apiClient.post<Record<string, unknown>>(
      `/api/v1/daily-review/${encodeURIComponent(reviewDate)}/push`,
    );
    return toCamelCase<DailyReviewPushResponse>(response.data);
  },
};

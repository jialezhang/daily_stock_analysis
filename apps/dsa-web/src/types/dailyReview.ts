export type ReviewDimension = 'day' | 'week' | 'month';

export interface DailyReviewAnomalyCounts {
  red: number;
  yellow: number;
}

export interface DailyReviewCharts {
  marketScores?: Record<string, number>;
  anomalyCounts?: DailyReviewAnomalyCounts;
}

export interface DailyReviewRegime {
  market: string;
  totalScore?: number;
  regime?: string;
  positionSuggestion?: string;
  reasoning?: string;
}

export interface DailyReviewAnomalyItem {
  level: string;
  name: string;
  message: string;
  action: string;
  affectedMarkets?: string[];
  possibleCause?: string;
  potentialImpact?: string;
}

export interface DailyReviewSnapshot {
  reviewDate?: string;
  generatedAt?: string;
  summary?: string;
  regimes?: DailyReviewRegime[];
  anomalies?: {
    redCount?: number;
    yellowCount?: number;
    items?: DailyReviewAnomalyItem[];
  };
  [key: string]: unknown;
}

export interface DailyReviewPeriodItem {
  dimension: ReviewDimension;
  periodKey: string;
  periodLabel: string;
  reviewDate: string;
  generatedAt?: string;
  summary: string;
  snapshot?: DailyReviewSnapshot;
  charts?: DailyReviewCharts;
}

export interface DailyReviewHistoryResponse {
  found: boolean;
  message: string;
  dimension: ReviewDimension;
  items: DailyReviewPeriodItem[];
}

export interface DailyReviewLatestResponse {
  found: boolean;
  message: string;
  dimension: ReviewDimension;
  item?: DailyReviewPeriodItem;
}

export interface DailyReviewRunRequest {
  pushTelegram?: boolean;
  useLlm?: boolean;
}

export interface DailyReviewRunResponse {
  success: boolean;
  message: string;
  item?: DailyReviewPeriodItem;
  reportPreview?: string;
}

export interface DailyReviewPushResponse {
  pushed: boolean;
  message: string;
}

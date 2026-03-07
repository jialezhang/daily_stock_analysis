export type PositionBaseCurrency = 'USD' | 'CNY' | 'RMB';
export type PositionQuoteCurrency = 'USD' | 'CNY' | 'RMB' | 'HKD';

export interface PositionManagementTarget {
  initialPosition: number;
  outputCurrency: PositionBaseCurrency | 'HKD';
  targetReturnPct: number;
}

export interface PositionHoldingInput {
  id?: string;
  assetPrimary: string;
  assetSecondary: string;
  symbol: string;
  name?: string;
  quantity: number;
  currentPrice?: number;
  previousClose?: number;
  currency?: PositionQuoteCurrency;
  lotSize?: number;
  latestPrice?: number;
  fxToOutput?: number;
  marketValueOutput?: number;
  dailyPnlOutput?: number;
  changePct?: number;
}

export interface PositionManagementUpsertRequest {
  target: PositionManagementTarget;
  holdings: PositionHoldingInput[];
  refreshBenchmarks?: boolean;
}

export interface PositionManagementResponse {
  updated: boolean;
  module?: Record<string, unknown>;
  message: string;
}

export interface PositionReviewPushResponse {
  pushed: boolean;
  message: string;
  reportPreview?: string;
  dailyReview?: PositionDailyReviewPayload;
}

export interface PositionDailyReviewSections {
  macroCrossMarket?: string;
  targetTracking?: string;
  riskWarning?: string;
  gridReference?: string;
}

export interface PositionDailyReviewPayload {
  reviewDate?: string;
  generatedAt?: string;
  filePath?: string;
  markdown?: string;
  sections?: PositionDailyReviewSections;
  note?: string;
  noteUpdatedAt?: string;
}

export interface PositionReviewLatestResponse {
  found: boolean;
  message: string;
  dailyReview?: PositionDailyReviewPayload;
}

export interface PositionReviewHistoryResponse {
  found: boolean;
  message: string;
  reviews: PositionDailyReviewPayload[];
}

export interface PositionReviewNoteUpsertResponse {
  updated: boolean;
  message: string;
  reviewDate: string;
  note: string;
}

export interface PortfolioReviewPayload {
  reviewDate?: string;
  generatedAt?: string;
  totalValueCny?: number;
  cashPct?: number;
  usPct?: number;
  hkPct?: number;
  aPct?: number;
  cryptoPct?: number;
  healthScore?: number;
  healthGrade?: string;
  holdings?: Record<string, unknown>[];
  reviewReport?: string;
}

export interface PortfolioReviewLatestResponse {
  found: boolean;
  message: string;
  portfolioReview?: PortfolioReviewPayload;
}

export interface PortfolioReviewHistoryResponse {
  found: boolean;
  message: string;
  reviews: PortfolioReviewPayload[];
}

export interface PortfolioReviewRunResponse {
  success: boolean;
  message: string;
  reportPreview?: string;
  portfolioReview?: PortfolioReviewPayload;
}

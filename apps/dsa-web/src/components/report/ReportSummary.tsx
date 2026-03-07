import React from 'react';
import type { AnalysisResult, AnalysisReport, HistoryModuleKey, ModuleRefreshJob } from '../../types/analysis';
import { ReportOverview } from './ReportOverview';
import { ReportStrategy } from './ReportStrategy';
import { ReportPriceZonesModule } from './ReportPriceZonesModule';
import { ReportPatternSignalsModule } from './ReportPatternSignalsModule';
import { ReportTechnicalModule } from './ReportTechnicalModule';
import { ReportNews } from './ReportNews';
import { ReportDetails } from './ReportDetails';
import { getModuleRefreshState, getModuleUpdatedAtDisplay, isModuleRefreshing } from '../../utils/moduleRefresh';

interface ReportSummaryProps {
  data: AnalysisResult | AnalysisReport;
  isHistory?: boolean;
  onRefreshModule?: (module: HistoryModuleKey) => void;
  moduleJobs?: ModuleRefreshJob[];
}

/**
 * 完整报告展示组件
 * 整合概览、策略、资讯、详情四个区域
 */
export const ReportSummary: React.FC<ReportSummaryProps> = ({
  data,
  isHistory = false,
  onRefreshModule,
  moduleJobs = [],
}) => {
  // 兼容 AnalysisResult 和 AnalysisReport 两种数据格式
  const report: AnalysisReport = 'report' in data ? data.report : data;
  // 使用 report id，因为 queryId 在批量分析时可能重复，且历史报告详情接口需要 recordId 来获取关联资讯和详情数据
  const recordId = report.meta.id;

  const { meta, summary, strategy, details } = report;

  return (
    <div className="space-y-3 animate-fade-in">
      {/* 概览区（首屏） */}
      <ReportOverview
        meta={meta}
        summary={summary}
        isHistory={isHistory}
        onRefreshAll={() => onRefreshModule?.('full')}
        isRefreshingAll={isModuleRefreshing(moduleJobs, 'full')}
        refreshState={getModuleRefreshState(moduleJobs, 'full')}
        updatedAt={getModuleUpdatedAtDisplay(details, moduleJobs, 'summary')}
      />

      {/* 价格区间区（独立模块） */}
      <ReportPriceZonesModule
        details={details}
        recordId={recordId}
        stockCode={meta.stockCode}
        onRefreshModule={() => onRefreshModule?.('price_zones')}
        isRefreshing={isModuleRefreshing(moduleJobs, 'price_zones')}
        refreshState={getModuleRefreshState(moduleJobs, 'price_zones')}
        updatedAt={getModuleUpdatedAtDisplay(details, moduleJobs, 'price_zones')}
      />

      {/* 止跌/见顶信号区（独立模块） */}
      <ReportPatternSignalsModule
        details={details}
        onRefreshModule={() => onRefreshModule?.('pattern_signals')}
        isRefreshing={isModuleRefreshing(moduleJobs, 'pattern_signals')}
        refreshState={getModuleRefreshState(moduleJobs, 'pattern_signals')}
        updatedAt={getModuleUpdatedAtDisplay(details, moduleJobs, 'pattern_signals')}
      />

      {/* 技术面模块区 */}
      <ReportTechnicalModule
        details={details}
        onRefreshModule={() => onRefreshModule?.('technical_indicators')}
        isRefreshing={isModuleRefreshing(moduleJobs, 'technical_indicators')}
        refreshState={getModuleRefreshState(moduleJobs, 'technical_indicators')}
        updatedAt={getModuleUpdatedAtDisplay(details, moduleJobs, 'technical_indicators')}
      />

      {/* 资讯区 */}
      <ReportNews
        recordId={recordId}
        onRefreshModule={() => onRefreshModule?.('news')}
        isRefreshing={isModuleRefreshing(moduleJobs, 'news')}
        refreshState={getModuleRefreshState(moduleJobs, 'news')}
        updatedAt={getModuleUpdatedAtDisplay(details, moduleJobs, 'news')}
      />

      {/* 透明度与追溯区 */}
      <ReportDetails details={details} recordId={recordId} />

      {/* 策略点位区（页面最后） */}
      <ReportStrategy
        strategy={strategy}
        onRefreshModule={() => onRefreshModule?.('sniper_points')}
        isRefreshing={isModuleRefreshing(moduleJobs, 'sniper_points')}
        refreshState={getModuleRefreshState(moduleJobs, 'sniper_points')}
        updatedAt={getModuleUpdatedAtDisplay(details, moduleJobs, 'sniper_points')}
      />
    </div>
  );
};

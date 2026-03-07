# -*- coding: utf-8 -*-
"""
===================================
历史记录相关模型
===================================

职责：
1. 定义历史记录列表和详情模型
2. 定义分析报告完整模型
"""

from typing import Optional, List, Any, Literal

from pydantic import BaseModel, Field


class HistoryItem(BaseModel):
    """历史记录摘要（列表展示用）"""

    id: Optional[int] = Field(None, description="分析历史记录主键 ID")
    query_id: str = Field(..., description="分析记录关联 query_id（批量分析时重复）")
    stock_code: str = Field(..., description="股票代码")
    stock_name: Optional[str] = Field(None, description="股票名称")
    report_type: Optional[str] = Field(None, description="报告类型")
    sentiment_score: Optional[int] = Field(
        None, 
        description="情绪评分 (0-100)",
        ge=0,
        le=100
    )
    operation_advice: Optional[str] = Field(None, description="操作建议")
    created_at: Optional[str] = Field(None, description="创建时间")
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": 1234,
                "query_id": "abc123",
                "stock_code": "600519",
                "stock_name": "贵州茅台",
                "report_type": "detailed",
                "sentiment_score": 75,
                "operation_advice": "持有",
                "created_at": "2024-01-01T12:00:00"
            }
        }


class HistoryListResponse(BaseModel):
    """历史记录列表响应"""
    
    total: int = Field(..., description="总记录数")
    page: int = Field(..., description="当前页码")
    limit: int = Field(..., description="每页数量")
    items: List[HistoryItem] = Field(default_factory=list, description="记录列表")
    
    class Config:
        json_schema_extra = {
            "example": {
                "total": 100,
                "page": 1,
                "limit": 20,
                "items": []
            }
        }


class HistoryDeleteResponse(BaseModel):
    """History delete response."""

    deleted: int = Field(..., description="删除成功的记录数（0 或 1）")


class HistoryRefreshRequest(BaseModel):
    """Refresh request for one history record."""

    mode: Literal["full", "partial"] = Field(
        "full",
        description="刷新模式：full=全量刷新（保留 Rhino 价格区间），partial=仅刷新指定子模块",
    )
    modules: List[str] = Field(
        default_factory=list,
        description=(
            "partial 模式下的模块列表：price_zones, pattern_signals, technical_indicators, "
            "sniper_points, summary, news, position_management"
        ),
    )


class HistoryRefreshResponse(BaseModel):
    """Refresh response for one history record."""

    updated: bool = Field(..., description="是否更新成功")
    record_id: int = Field(..., description="被更新的历史记录 ID")
    mode: str = Field(..., description="执行模式")
    modules: List[str] = Field(default_factory=list, description="实际执行的模块")
    message: str = Field("", description="结果说明")


class RhinoZoneUpsertRequest(BaseModel):
    """Request for manual rhino zone upsert."""

    upper: float = Field(..., gt=0, description="区间上限价格")
    lower: float = Field(..., gt=0, description="区间下限价格")
    strength_level: Literal["弱", "中", "强", "超强"] = Field("中", description="强弱程度")
    name: Optional[str] = Field(None, description="区间名称（可选）")
    definition: Optional[str] = Field(None, description="区间定义（可选，自定义展示文案）")


class RhinoZoneDeleteResponse(BaseModel):
    """Delete response for one rhino zone."""

    deleted: bool = Field(..., description="是否删除成功")
    record_id: int = Field(..., description="历史记录 ID")
    zone_id: str = Field(..., description="被删除的区间 ID")


class RhinoZoneUpsertResponse(BaseModel):
    """Upsert response for one rhino zone."""

    updated: bool = Field(..., description="是否更新成功")
    record_id: int = Field(..., description="历史记录 ID")
    zone: Optional[Any] = Field(None, description="写入后的区间数据")
    message: str = Field("", description="结果说明")


class RhinoZoneUpdateRequest(BaseModel):
    """Request for updating one manual rhino zone."""

    upper: float = Field(..., gt=0, description="区间上限价格")
    lower: float = Field(..., gt=0, description="区间下限价格")
    strength_level: Literal["弱", "中", "强", "超强"] = Field("中", description="强弱程度")
    name: Optional[str] = Field(None, description="区间名称（可选）")
    definition: Optional[str] = Field(None, description="区间定义（可选，自定义展示文案）")


class PositionManagementTarget(BaseModel):
    """Position management target and currency config."""

    annual_return_target_pct: float = Field(30.0, ge=-100.0, le=500.0, description="年度收益目标（%）")
    base_currency: Literal["USD", "CNY", "RMB"] = Field("USD", description="统一计价币种")
    usd_cny: float = Field(7.2, gt=0, description="USD/CNY 汇率")
    usd_hkd: float = Field(7.8, gt=0, description="USD/HKD 汇率")


class PositionHoldingInput(BaseModel):
    """One holding row for position management."""

    market_type: str = Field(..., description="市场类型，如 a_share/hk/us/crypto/money_fund")
    asset_class: str = Field(..., description="资产大类，如 A股/港股/美股/加密货币/货币基金")
    symbol: str = Field(..., description="标的代码")
    name: Optional[str] = Field(None, description="标的名称")
    quantity: float = Field(..., ge=0, description="持有数量")
    avg_cost: float = Field(..., ge=0, description="平均建仓成本")
    current_price: float = Field(..., ge=0, description="当前价格")
    previous_close: Optional[float] = Field(None, ge=0, description="前收盘价（用于当日盈亏）")
    currency: Literal["USD", "CNY", "RMB", "HKD"] = Field("USD", description="价格币种")


class PositionManagementUpsertRequest(BaseModel):
    """Upsert position management module payload."""

    target: PositionManagementTarget = Field(default_factory=PositionManagementTarget)
    holdings: List[PositionHoldingInput] = Field(default_factory=list, description="持仓列表")
    macro_events: List[str] = Field(default_factory=list, description="宏观/地缘事件（可手动补充）")
    notes: Optional[str] = Field(None, description="备注")
    refresh_benchmarks: bool = Field(True, description="是否刷新基准指数与收益曲线")


class PositionManagementResponse(BaseModel):
    """Get/upsert position management module response."""

    updated: bool = Field(..., description="是否更新成功")
    record_id: int = Field(..., description="历史记录 ID")
    module: Optional[Any] = Field(None, description="仓位管理模块数据")
    message: str = Field("", description="结果说明")


class ModuleRefreshJob(BaseModel):
    """Async module refresh job payload."""

    job_id: str = Field(..., description="任务 ID")
    record_id: int = Field(..., description="历史记录 ID")
    module: str = Field(..., description="模块名或 full")
    status: Literal["queued", "running", "succeeded", "failed"] = Field(..., description="任务状态")
    message: str = Field("", description="状态说明")
    created_at: str = Field(..., description="创建时间")
    started_at: Optional[str] = Field(None, description="开始时间")
    finished_at: Optional[str] = Field(None, description="结束时间")
    module_updated_at: Optional[str] = Field(None, description="模块最新更新时间")


class ModuleRefreshStartResponse(BaseModel):
    """Start async module refresh response."""

    accepted: bool = Field(..., description="是否接受任务")
    job: ModuleRefreshJob = Field(..., description="任务信息")


class ModuleRefreshJobsResponse(BaseModel):
    """List async module refresh jobs response."""

    total: int = Field(..., description="任务数量")
    items: List[ModuleRefreshJob] = Field(default_factory=list, description="任务列表")


class NewsIntelItem(BaseModel):
    """新闻情报条目"""

    title: str = Field(..., description="新闻标题")
    snippet: str = Field("", description="新闻摘要（最多200字）")
    url: str = Field(..., description="新闻链接")

    class Config:
        json_schema_extra = {
            "example": {
                "title": "公司发布业绩快报，营收同比增长 20%",
                "snippet": "公司公告显示，季度营收同比增长 20%...",
                "url": "https://example.com/news/123"
            }
        }


class NewsIntelResponse(BaseModel):
    """新闻情报响应"""

    total: int = Field(..., description="新闻条数")
    items: List[NewsIntelItem] = Field(default_factory=list, description="新闻列表")

    class Config:
        json_schema_extra = {
            "example": {
                "total": 2,
                "items": []
            }
        }


class ReportMeta(BaseModel):
    """报告元信息"""
    
    id: Optional[int] = Field(None, description="分析历史记录主键 ID（仅历史报告有此字段）")
    query_id: str = Field(..., description="分析记录关联 query_id（批量分析时重复）")
    stock_code: str = Field(..., description="股票代码")
    stock_name: Optional[str] = Field(None, description="股票名称")
    report_type: Optional[str] = Field(None, description="报告类型")
    created_at: Optional[str] = Field(None, description="创建时间")
    current_price: Optional[float] = Field(None, description="分析时股价")
    change_pct: Optional[float] = Field(None, description="分析时涨跌幅(%)")


class ReportSummary(BaseModel):
    """报告概览区"""
    
    analysis_summary: Optional[str] = Field(None, description="关键结论")
    operation_advice: Optional[str] = Field(None, description="操作建议")
    trend_prediction: Optional[str] = Field(None, description="趋势预测")
    sentiment_score: Optional[int] = Field(
        None, 
        description="情绪评分 (0-100)",
        ge=0,
        le=100
    )
    sentiment_label: Optional[str] = Field(None, description="情绪标签")


class ReportStrategy(BaseModel):
    """策略点位区"""
    
    ideal_buy: Optional[str] = Field(None, description="理想买入价")
    secondary_buy: Optional[str] = Field(None, description="第二买入价")
    stop_loss: Optional[str] = Field(None, description="止损价")
    take_profit: Optional[str] = Field(None, description="止盈价")


class ReportDetails(BaseModel):
    """报告详情区"""
    
    news_content: Optional[str] = Field(None, description="新闻摘要")
    technical_module: Optional[Any] = Field(None, description="技术面模块（价格区间/一年信号/指标打分）")
    raw_result: Optional[Any] = Field(None, description="原始分析结果（JSON）")
    context_snapshot: Optional[Any] = Field(None, description="分析时上下文快照（JSON）")


class AnalysisReport(BaseModel):
    """完整分析报告"""
    
    meta: ReportMeta = Field(..., description="元信息")
    summary: ReportSummary = Field(..., description="概览区")
    strategy: Optional[ReportStrategy] = Field(None, description="策略点位区")
    details: Optional[ReportDetails] = Field(None, description="详情区")
    
    class Config:
        json_schema_extra = {
            "example": {
                "meta": {
                    "query_id": "abc123",
                    "stock_code": "600519",
                    "stock_name": "贵州茅台",
                    "report_type": "detailed",
                    "created_at": "2024-01-01T12:00:00"
                },
                "summary": {
                    "analysis_summary": "技术面向好，建议持有",
                    "operation_advice": "持有",
                    "trend_prediction": "看多",
                    "sentiment_score": 75,
                    "sentiment_label": "乐观"
                },
                "strategy": {
                    "ideal_buy": "1800.00",
                    "secondary_buy": "1750.00",
                    "stop_loss": "1700.00",
                    "take_profit": "2000.00"
                },
                "details": None
            }
        }

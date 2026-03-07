# -*- coding: utf-8 -*-
"""Position management schemas."""

from typing import Any, List, Literal, Optional

from pydantic import BaseModel, Field


class PositionManagementTarget(BaseModel):
    """Target and FX settings."""

    initial_position: float = Field(0.0, ge=0, description="初始仓位金额")
    output_currency: Literal["USD", "CNY", "RMB", "HKD"] = Field("USD", description="输出币种")
    target_return_pct: float = Field(30.0, ge=-100.0, le=500.0, description="目标收益率(%)")


class PositionHoldingInput(BaseModel):
    """One holding row."""

    asset_primary: str = Field(..., description="一级资产分类")
    asset_secondary: str = Field(..., description="二级资产分类")
    symbol: str = Field(...)
    name: Optional[str] = Field(None)
    quantity: float = Field(..., ge=0)
    current_price: Optional[float] = Field(None, ge=0)
    previous_close: Optional[float] = Field(None, ge=0)
    currency: Optional[Literal["USD", "CNY", "RMB", "HKD"]] = Field(None)


class PositionManagementUpsertRequest(BaseModel):
    """Upsert payload."""

    target: PositionManagementTarget = Field(default_factory=PositionManagementTarget)
    holdings: List[PositionHoldingInput] = Field(default_factory=list)
    macro_events: List[str] = Field(default_factory=list)
    notes: Optional[str] = Field(None)
    refresh_benchmarks: bool = Field(True)


class PositionManagementResponse(BaseModel):
    """Response payload."""

    updated: bool = Field(...)
    module: Optional[Any] = Field(None)
    message: str = Field("")


class PositionReviewPushResponse(BaseModel):
    """Daily position review push response."""

    pushed: bool = Field(..., description="Whether push was attempted successfully")
    message: str = Field("", description="Operation message")
    report_preview: Optional[str] = Field(None, description="Report preview snippet")
    daily_review: Optional[Any] = Field(None, description="Latest daily review payload")


class PositionReviewLatestResponse(BaseModel):
    """Latest local daily position review."""

    found: bool = Field(..., description="Whether local markdown review exists")
    message: str = Field("", description="Operation message")
    daily_review: Optional[Any] = Field(None, description="Latest daily review payload")


class PositionReviewHistoryResponse(BaseModel):
    """Historical local daily position reviews."""

    found: bool = Field(..., description="Whether any local review exists")
    message: str = Field("", description="Operation message")
    reviews: List[Any] = Field(default_factory=list, description="Review history list")


class PositionReviewNoteUpsertRequest(BaseModel):
    """Manual note upsert payload for one review date."""

    note: str = Field("", description="Manual annotation for one daily review")


class PositionReviewNoteUpsertResponse(BaseModel):
    """Manual note upsert response."""

    updated: bool = Field(..., description="Whether note has been updated")
    message: str = Field("", description="Operation message")
    review_date: str = Field(..., description="Review date in YYYY-MM-DD")
    note: str = Field("", description="Current manual note")

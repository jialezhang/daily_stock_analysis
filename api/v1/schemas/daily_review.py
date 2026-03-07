# -*- coding: utf-8 -*-
"""Schemas for daily review APIs."""

from typing import Any, List, Literal, Optional

from pydantic import BaseModel, Field


ReviewDimension = Literal["day", "week", "month"]


class DailyReviewPeriodItem(BaseModel):
    """One review item for day/week/month dimension."""

    dimension: ReviewDimension = Field(...)
    period_key: str = Field(...)
    period_label: str = Field(...)
    review_date: str = Field("")
    generated_at: Optional[str] = Field(None)
    summary: str = Field("")
    snapshot: Optional[Any] = Field(None)
    charts: Optional[Any] = Field(None)


class DailyReviewHistoryResponse(BaseModel):
    """History response for daily review module."""

    found: bool = Field(...)
    message: str = Field("")
    dimension: ReviewDimension = Field(...)
    items: List[DailyReviewPeriodItem] = Field(default_factory=list)


class DailyReviewLatestResponse(BaseModel):
    """Latest period response for daily review module."""

    found: bool = Field(...)
    message: str = Field("")
    dimension: ReviewDimension = Field(...)
    item: Optional[DailyReviewPeriodItem] = Field(None)


class DailyReviewRunRequest(BaseModel):
    """Run request payload."""

    push_telegram: bool = Field(False, description="Whether to push report to Telegram after run")
    use_llm: bool = Field(False, description="Whether to use LLM summary when rerun")


class DailyReviewRunResponse(BaseModel):
    """Run response payload."""

    success: bool = Field(...)
    message: str = Field("")
    item: Optional[DailyReviewPeriodItem] = Field(None)
    report_preview: Optional[str] = Field(None)


class DailyReviewPushResponse(BaseModel):
    """Push-by-date response payload."""

    pushed: bool = Field(...)
    message: str = Field("")

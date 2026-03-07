# -*- coding: utf-8 -*-
"""Daily review endpoints."""

import logging

from fastapi import APIRouter, HTTPException, Query

from api.v1.schemas.common import ErrorResponse
from api.v1.schemas.daily_review import (
    DailyReviewHistoryResponse,
    DailyReviewLatestResponse,
    DailyReviewPushResponse,
    DailyReviewRunRequest,
    DailyReviewRunResponse,
    ReviewDimension,
)
from modules.daily_review.history import build_period_items, push_review_by_date
from modules.daily_review.runner import run_daily_review

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/history",
    response_model=DailyReviewHistoryResponse,
    responses={
        200: {"description": "History loaded"},
        500: {"description": "Server error", "model": ErrorResponse},
    },
    summary="Get daily review history by day/week/month",
)
def get_daily_review_history(
    dimension: ReviewDimension = Query("day"),
    limit: int = Query(120, ge=1, le=365),
) -> DailyReviewHistoryResponse:
    """Load historical review items by one time dimension."""
    try:
        items = build_period_items(dimension=dimension, limit=limit)
        return DailyReviewHistoryResponse(
            found=bool(items),
            message="读取成功" if items else "暂无复盘记录",
            dimension=dimension,
            items=items,
        )
    except Exception as exc:
        logger.error("Failed to load daily review history: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": f"读取复盘历史失败: {str(exc)}"},
        )


@router.get(
    "/latest",
    response_model=DailyReviewLatestResponse,
    responses={
        200: {"description": "Latest item loaded"},
        500: {"description": "Server error", "model": ErrorResponse},
    },
    summary="Get latest daily review item by dimension",
)
def get_latest_daily_review_item(dimension: ReviewDimension = Query("day")) -> DailyReviewLatestResponse:
    """Load latest review item under day/week/month dimension."""
    try:
        items = build_period_items(dimension=dimension, limit=1)
        item = items[0] if items else None
        return DailyReviewLatestResponse(
            found=item is not None,
            message="读取成功" if item is not None else "暂无复盘记录",
            dimension=dimension,
            item=item,
        )
    except Exception as exc:
        logger.error("Failed to load latest daily review item: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": f"读取最新复盘失败: {str(exc)}"},
        )


@router.post(
    "/run",
    response_model=DailyReviewRunResponse,
    responses={
        200: {"description": "Rerun finished"},
        500: {"description": "Server error", "model": ErrorResponse},
    },
    summary="Rerun daily review pipeline",
)
def rerun_daily_review(request: DailyReviewRunRequest) -> DailyReviewRunResponse:
    """Rerun daily review and return latest day item."""
    try:
        report = run_daily_review(send_telegram=request.push_telegram, use_llm=request.use_llm)
        latest_items = build_period_items(dimension="day", limit=1)
        latest_item = latest_items[0] if latest_items else None
        return DailyReviewRunResponse(
            success=bool(report),
            message="复盘已重新生成",
            item=latest_item,
            report_preview=str(report)[:320] if report else None,
        )
    except Exception as exc:
        logger.error("Failed to rerun daily review: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": f"重新复盘失败: {str(exc)}"},
        )


@router.post(
    "/{review_date}/push",
    response_model=DailyReviewPushResponse,
    responses={
        200: {"description": "Push attempted"},
        500: {"description": "Server error", "model": ErrorResponse},
    },
    summary="Push one saved review markdown to Telegram by date",
)
def push_daily_review(review_date: str) -> DailyReviewPushResponse:
    """Push one saved review markdown by one date key."""
    try:
        pushed = push_review_by_date(review_date)
        if pushed:
            return DailyReviewPushResponse(
                pushed=True,
                message="Telegram 推送已触发，请检查机器人消息。",
            )
        return DailyReviewPushResponse(
            pushed=False,
            message="未找到该日期复盘文件，或推送失败。",
        )
    except Exception as exc:
        logger.error("Failed to push daily review by date %s: %s", review_date, exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": f"复盘推送失败: {str(exc)}"},
        )

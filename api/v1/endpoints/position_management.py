# -*- coding: utf-8 -*-
"""Global position management endpoints."""

import logging

from fastapi import APIRouter, HTTPException, Query

from src.config import get_config
from api.v1.schemas.common import ErrorResponse
from api.v1.schemas.position_management import (
    PortfolioReviewHistoryResponse,
    PortfolioReviewLatestResponse,
    PortfolioReviewRunResponse,
    PositionReviewHistoryResponse,
    PositionReviewLatestResponse,
    PositionManagementResponse,
    PositionReviewNoteUpsertRequest,
    PositionReviewNoteUpsertResponse,
    PositionReviewPushResponse,
    PositionManagementUpsertRequest,
)
from src.analyzer import GeminiAnalyzer
from src.core.portfolio_review import list_portfolio_reviews, load_latest_portfolio_review
from src.core.position_review import (
    list_position_reviews,
    load_latest_position_review,
    run_position_daily_review,
    upsert_position_review_note,
)
from src.notification import NotificationService
from src.portfolio.runner import (
    build_portfolio_from_config,
    build_portfolio_from_position_management_module,
    run_portfolio_review,
)
from src.services.position_management_service import PositionManagementService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "",
    response_model=PositionManagementResponse,
    responses={
        200: {"description": "Position management module"},
        500: {"description": "Server error", "model": ErrorResponse},
    },
    summary="Get global position management module",
)
def get_position_management() -> PositionManagementResponse:
    """Get global position management data."""
    try:
        service = PositionManagementService()
        result = service.get_module()
        return PositionManagementResponse(
            updated=bool(result.get("updated")),
            module=result.get("module"),
            message=str(result.get("message", "")),
        )
    except Exception as exc:
        logger.error("Failed to load position management module: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": f"获取仓位管理失败: {str(exc)}"},
        )


@router.put(
    "",
    response_model=PositionManagementResponse,
    responses={
        200: {"description": "Saved"},
        500: {"description": "Server error", "model": ErrorResponse},
    },
    summary="Upsert global position management module",
)
def upsert_position_management(request: PositionManagementUpsertRequest) -> PositionManagementResponse:
    """Save global position management data."""
    try:
        service = PositionManagementService()
        result = service.upsert_module(
            target=request.target.model_dump(),
            holdings=[item.model_dump() for item in request.holdings],
            macro_events=request.macro_events,
            notes=request.notes,
            refresh_benchmarks=request.refresh_benchmarks,
        )
        return PositionManagementResponse(
            updated=bool(result.get("updated")),
            module=result.get("module"),
            message=str(result.get("message", "")),
        )
    except Exception as exc:
        logger.error("Failed to save position management module: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": f"保存仓位管理失败: {str(exc)}"},
        )


@router.post(
    "/refresh",
    response_model=PositionManagementResponse,
    responses={
        200: {"description": "Refreshed"},
        500: {"description": "Server error", "model": ErrorResponse},
    },
    summary="Refresh global position management derived data",
)
def refresh_position_management() -> PositionManagementResponse:
    """Refresh benchmark and derived metrics."""
    try:
        service = PositionManagementService()
        result = service.refresh_module()
        return PositionManagementResponse(
            updated=bool(result.get("updated")),
            module=result.get("module"),
            message=str(result.get("message", "")),
        )
    except Exception as exc:
        logger.error("Failed to refresh position management module: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": f"刷新仓位管理失败: {str(exc)}"},
        )


@router.post(
    "/review-push",
    response_model=PositionReviewPushResponse,
    responses={
        200: {"description": "Review push attempted"},
        500: {"description": "Server error", "model": ErrorResponse},
    },
    summary="Generate and push daily position review to Telegram",
)
def push_position_review() -> PositionReviewPushResponse:
    """Generate one daily position review and send to Telegram."""
    try:
        notifier = NotificationService()
        analyzer = GeminiAnalyzer()
        report = run_position_daily_review(
            notifier=notifier,
            analyzer=analyzer,
            market_report="",
            send_notification=True,
        )
        latest_review = load_latest_position_review()
        if report:
            return PositionReviewPushResponse(
                pushed=True,
                message="复盘已生成并已触发 Telegram 推送，请查看 Telegram/服务日志确认送达。",
                report_preview=str(report)[:240],
                daily_review=latest_review,
            )
        return PositionReviewPushResponse(
            pushed=False,
            message="复盘生成失败，未推送。",
            report_preview=None,
            daily_review=latest_review,
        )
    except Exception as exc:
        logger.error("Failed to push position daily review: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": f"复盘推送失败: {str(exc)}"},
        )


@router.get(
    "/review/latest",
    response_model=PositionReviewLatestResponse,
    responses={
        200: {"description": "Latest review loaded"},
        500: {"description": "Server error", "model": ErrorResponse},
    },
    summary="Get latest local daily position review markdown",
)
def get_latest_position_review() -> PositionReviewLatestResponse:
    """Get latest local position review for frontend display."""
    try:
        latest_review = load_latest_position_review()
        if latest_review:
            return PositionReviewLatestResponse(
                found=True,
                message="读取成功",
                daily_review=latest_review,
            )
        return PositionReviewLatestResponse(
            found=False,
            message="暂无本地复盘记录",
            daily_review=None,
        )
    except Exception as exc:
        logger.error("Failed to load latest position review: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": f"读取最新复盘失败: {str(exc)}"},
        )


@router.get(
    "/review/history",
    response_model=PositionReviewHistoryResponse,
    responses={
        200: {"description": "Review history loaded"},
        500: {"description": "Server error", "model": ErrorResponse},
    },
    summary="Get local daily position review history",
)
def get_position_review_history(limit: int = Query(60, ge=1, le=365)) -> PositionReviewHistoryResponse:
    """Get local daily review history for the review history page."""
    try:
        reviews = list_position_reviews(limit=limit)
        return PositionReviewHistoryResponse(
            found=bool(reviews),
            message="读取成功" if reviews else "暂无本地复盘记录",
            reviews=reviews,
        )
    except Exception as exc:
        logger.error("Failed to load position review history: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": f"读取复盘历史失败: {str(exc)}"},
        )


@router.get(
    "/portfolio-review/latest",
    response_model=PortfolioReviewLatestResponse,
    responses={
        200: {"description": "Latest portfolio review loaded"},
        500: {"description": "Server error", "model": ErrorResponse},
    },
    summary="Get latest persisted portfolio review snapshot",
)
def get_latest_portfolio_review() -> PortfolioReviewLatestResponse:
    """Get latest portfolio review snapshot for frontend display."""
    try:
        latest_review = load_latest_portfolio_review()
        if latest_review:
            return PortfolioReviewLatestResponse(
                found=True,
                message="读取成功",
                portfolio_review=latest_review,
            )
        return PortfolioReviewLatestResponse(
            found=False,
            message="暂无组合复盘记录",
            portfolio_review=None,
        )
    except Exception as exc:
        logger.error("Failed to load latest portfolio review: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": f"读取最新组合复盘失败: {str(exc)}"},
        )


@router.get(
    "/portfolio-review/history",
    response_model=PortfolioReviewHistoryResponse,
    responses={
        200: {"description": "Portfolio review history loaded"},
        500: {"description": "Server error", "model": ErrorResponse},
    },
    summary="Get persisted portfolio review history",
)
def get_portfolio_review_history(limit: int = Query(60, ge=1, le=365)) -> PortfolioReviewHistoryResponse:
    """Get historical portfolio review snapshots."""
    try:
        reviews = list_portfolio_reviews(limit=limit)
        return PortfolioReviewHistoryResponse(
            found=bool(reviews),
            message="读取成功" if reviews else "暂无组合复盘记录",
            reviews=reviews,
        )
    except Exception as exc:
        logger.error("Failed to load portfolio review history: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": f"读取组合复盘历史失败: {str(exc)}"},
        )


@router.post(
    "/portfolio-review/run",
    response_model=PortfolioReviewRunResponse,
    responses={
        200: {"description": "Portfolio review run completed"},
        500: {"description": "Server error", "model": ErrorResponse},
    },
    summary="Run one portfolio review without notification push",
)
def run_portfolio_review_endpoint() -> PortfolioReviewRunResponse:
    """Run portfolio review from position management first, then config fallback."""
    try:
        config = get_config()
        position_module = None
        source_label = "PORTFOLIO_HOLDINGS"
        try:
            position_module = PositionManagementService().get_module().get("module")
        except Exception as exc:
            logger.warning("Failed to load position management module for portfolio review: %s", exc)
        portfolio = build_portfolio_from_position_management_module(position_module, config=config)
        if portfolio is not None:
            source_label = "仓位管理"
        else:
            portfolio = build_portfolio_from_config(config)
        if portfolio is None:
            return PortfolioReviewRunResponse(
                success=False,
                message="仓位管理模块和 PORTFOLIO_HOLDINGS 都不可用",
                report_preview=None,
                portfolio_review=None,
            )

        notifier = NotificationService()
        analyzer = GeminiAnalyzer()
        report = run_portfolio_review(
            portfolio=portfolio,
            notifier=notifier,
            analyzer=analyzer,
            send_notification=False,
        )
        latest_review = load_latest_portfolio_review()
        return PortfolioReviewRunResponse(
            success=bool(report),
            message=f"组合复盘已生成（数据源：{source_label}）" if report else "组合复盘生成失败",
            report_preview=(f"组合复盘\n\n{str(report or '')}"[:400] if report else None),
            portfolio_review=latest_review,
        )
    except Exception as exc:
        logger.error("Failed to run portfolio review manually: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": f"运行组合复盘失败: {str(exc)}"},
        )


@router.put(
    "/review/{review_date}/note",
    response_model=PositionReviewNoteUpsertResponse,
    responses={
        200: {"description": "Review note updated"},
        400: {"description": "Invalid request", "model": ErrorResponse},
        500: {"description": "Server error", "model": ErrorResponse},
    },
    summary="Save manual note for one daily review",
)
def save_position_review_note(review_date: str, request: PositionReviewNoteUpsertRequest) -> PositionReviewNoteUpsertResponse:
    """Save manual annotation for one review date."""
    try:
        result = upsert_position_review_note(review_date=review_date, note=request.note)
        return PositionReviewNoteUpsertResponse(
            updated=True,
            message="批注已保存",
            review_date=str(result.get("review_date") or review_date),
            note=str(result.get("note") or ""),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid_argument", "message": str(exc)},
        )
    except Exception as exc:
        logger.error("Failed to save position review note: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": f"保存复盘批注失败: {str(exc)}"},
        )

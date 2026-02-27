# -*- coding: utf-8 -*-
"""
===================================
历史查询服务层
===================================

职责：
1. 封装历史记录查询逻辑
2. 提供分页和筛选功能
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

from src.config import get_config
from src.search_service import SearchService
from src.storage import DatabaseManager

logger = logging.getLogger(__name__)


class HistoryService:
    """
    历史查询服务
    
    封装历史分析记录的查询逻辑
    """
    
    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        """
        初始化历史查询服务
        
        Args:
            db_manager: 数据库管理器（可选，默认使用单例）
        """
        self.db = db_manager or DatabaseManager.get_instance()
    
    def get_history_list(
        self,
        stock_code: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        page: int = 1,
        limit: int = 20
    ) -> Dict[str, Any]:
        """
        获取历史分析列表
        
        Args:
            stock_code: 股票代码筛选
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            page: 页码
            limit: 每页数量
            
        Returns:
            包含 total, items 的字典
        """
        try:
            # 解析日期参数
            start_dt = None
            end_dt = None
            
            if start_date:
                try:
                    start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
                except ValueError:
                    logger.warning(f"无效的 start_date 格式: {start_date}")
            
            if end_date:
                try:
                    end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()
                except ValueError:
                    logger.warning(f"无效的 end_date 格式: {end_date}")
            
            # 计算 offset
            offset = (page - 1) * limit
            
            # 使用新的分页查询方法
            records, total = self.db.get_analysis_history_paginated(
                code=stock_code,
                start_date=start_dt,
                end_date=end_dt,
                offset=offset,
                limit=limit
            )
            
            # 转换为响应格式
            items = []
            for record in records:
                items.append({
                    "id": record.id,
                    "query_id": record.query_id,
                    "stock_code": record.code,
                    "stock_name": record.name,
                    "report_type": record.report_type,
                    "sentiment_score": record.sentiment_score,
                    "operation_advice": record.operation_advice,
                    "created_at": record.created_at.isoformat() if record.created_at else None,
                })
            
            return {
                "total": total,
                "items": items,
            }
            
        except Exception as e:
            logger.error(f"查询历史列表失败: {e}", exc_info=True)
            return {"total": 0, "items": []}
    
    def get_history_detail_by_id(self, record_id: int) -> Optional[Dict[str, Any]]:
        """
        获取历史报告详情

        使用数据库主键精确查询，避免 query_id 在批量分析时重复导致返回错误记录。

        Args:
            record_id: 分析历史记录主键 ID

        Returns:
            完整的分析报告字典，不存在返回 None
        """
        try:
            record = self.db.get_analysis_history_by_id(record_id)
            if not record:
                return None

            raw_result = None
            if record.raw_result:
                try:
                    raw_result = json.loads(record.raw_result)
                except json.JSONDecodeError:
                    raw_result = record.raw_result

            context_snapshot = None
            if record.context_snapshot:
                try:
                    context_snapshot = json.loads(record.context_snapshot)
                except json.JSONDecodeError:
                    context_snapshot = record.context_snapshot

            return {
                "id": record.id,
                "query_id": record.query_id,
                "stock_code": record.code,
                "stock_name": record.name,
                "report_type": record.report_type,
                "created_at": record.created_at.isoformat() if record.created_at else None,
                "analysis_summary": record.analysis_summary,
                "operation_advice": record.operation_advice,
                "trend_prediction": record.trend_prediction,
                "sentiment_score": record.sentiment_score,
                "sentiment_label": self._get_sentiment_label(record.sentiment_score or 50),
                "ideal_buy": str(record.ideal_buy) if record.ideal_buy else None,
                "secondary_buy": str(record.secondary_buy) if record.secondary_buy else None,
                "stop_loss": str(record.stop_loss) if record.stop_loss else None,
                "take_profit": str(record.take_profit) if record.take_profit else None,
                "news_content": record.news_content,
                "raw_result": raw_result,
                "context_snapshot": context_snapshot,
            }
        except Exception as e:
            logger.error(f"根据 ID 查询历史详情失败: {e}", exc_info=True)
            return None

    def get_news_intel(self, query_id: str, limit: int = 20) -> List[Dict[str, str]]:
        """
        获取指定 query_id 关联的新闻情报

        Args:
            query_id: 分析记录唯一标识
            limit: 返回数量限制

        Returns:
            新闻情报列表（包含 title、snippet、url）
        """
        try:
            records = self.db.get_news_intel_by_query_id(query_id=query_id, limit=limit)

            if not records:
                records = self._fallback_news_by_analysis_context(query_id=query_id, limit=limit)

            items: List[Dict[str, str]] = []
            for record in records:
                snippet = (record.snippet or "").strip()
                if len(snippet) > 200:
                    snippet = f"{snippet[:197]}..."
                items.append({
                    "title": record.title,
                    "snippet": snippet,
                    "url": record.url,
                })

            return items

        except Exception as e:
            logger.error(f"查询新闻情报失败: {e}", exc_info=True)
            return []

    def get_news_intel_by_record_id(
        self,
        record_id: int,
        limit: int = 20,
        force_refresh: bool = False
    ) -> List[Dict[str, str]]:
        """
        根据分析历史记录 ID 获取关联的新闻情报

        将 record_id 解析为 query_id，再调用 get_news_intel。

        Args:
            record_id: 分析历史记录主键 ID
            limit: 返回数量限制
            force_refresh: 是否强制回源搜索并刷新新闻

        Returns:
            新闻情报列表（包含 title、snippet、url）
        """
        try:
            # 根据 record_id 查出对应的 AnalysisHistory 记录
            record = self.db.get_analysis_history_by_id(record_id)
            if not record:
                logger.warning(f"未找到 record_id={record_id} 的分析记录")
                return []

            # 从记录中获取 query_id，优先返回已有历史新闻
            items = self.get_news_intel(query_id=record.query_id, limit=limit)
            if items and not force_refresh:
                return items

            if not force_refresh:
                return items

            refreshed_items = self._refresh_news_for_record(record_id=record_id, limit=limit)
            return refreshed_items if refreshed_items else items

        except Exception as e:
            logger.error(f"根据 record_id 查询新闻情报失败: {e}", exc_info=True)
            return []

    def _refresh_news_for_record(self, record_id: int, limit: int) -> List[Dict[str, str]]:
        """
        对指定历史记录执行一次回源搜索，并尝试写入数据库。

        如果 URL 唯一约束导致无法关联到当前 query_id，则降级返回本次搜索结果，
        确保前端点击“刷新”后仍可看到内容。
        """
        try:
            record = self.db.get_analysis_history_by_id(record_id)
            if not record:
                return []

            config = get_config()
            search_service = SearchService(
                bocha_keys=config.bocha_api_keys,
                tavily_keys=config.tavily_api_keys,
                brave_keys=config.brave_api_keys,
                serpapi_keys=config.serpapi_keys,
                news_max_age_days=config.news_max_age_days,
            )

            if not search_service.is_available:
                logger.info("刷新新闻失败：未配置可用搜索引擎")
                return []

            stock_name = (record.name or "").strip() or f"股票{record.code}"
            max_results = max(1, min(limit, 20))
            response = search_service.search_stock_news(
                stock_code=record.code,
                stock_name=stock_name,
                max_results=max_results
            )

            if not (response.success and response.results):
                logger.info(
                    f"刷新新闻未返回有效结果: record_id={record_id}, code={record.code}, error={response.error_message}"
                )
                return []

            # 尝试持久化到当前 query_id
            query_context = {
                "query_id": record.query_id or "",
                "query_source": "web",
            }
            self.db.save_news_intel(
                code=record.code,
                name=stock_name,
                dimension="latest_news",
                query=response.query,
                response=response,
                query_context=query_context
            )

            # 优先返回已关联到当前 query_id 的结果
            items = self.get_news_intel(query_id=record.query_id, limit=limit)
            if items:
                return items

            # 兜底：即使因 URL 去重未能关联 query_id，也返回本次刷新结果给前端
            fallback_items: List[Dict[str, str]] = []
            for r in response.results[:limit]:
                snippet = (r.snippet or "").strip()
                if len(snippet) > 200:
                    snippet = f"{snippet[:197]}..."
                fallback_items.append({
                    "title": r.title or "",
                    "snippet": snippet,
                    "url": r.url or "",
                })
            return fallback_items

        except Exception as e:
            logger.error(f"刷新新闻失败: {e}", exc_info=True)
            return []

    def _fallback_news_by_analysis_context(self, query_id: str, limit: int) -> List[Any]:
        """
        Fallback by analysis context when direct query_id lookup returns no news.

        Typical scenarios:
        - URL-level dedup keeps one canonical news row across repeated analyses.
        - Legacy records may have different historical query_id strategies.
        """
        records = self.db.get_analysis_history(query_id=query_id, limit=1)
        if not records:
            return []

        analysis = records[0]
        if not analysis.code or not analysis.created_at:
            return []

        # Narrow down to same-stock recent news, then filter by analysis time window.
        days = max(1, (datetime.now() - analysis.created_at).days + 1)
        candidates = self.db.get_recent_news(code=analysis.code, days=days, limit=max(limit * 5, 50))

        start_time = analysis.created_at - timedelta(hours=6)
        end_time = analysis.created_at + timedelta(hours=6)
        matched = [
            item for item in candidates
            if item.fetched_at and start_time <= item.fetched_at <= end_time
        ]

        return matched[:limit]
    
    def _get_sentiment_label(self, score: int) -> str:
        """
        根据评分获取情绪标签
        
        Args:
            score: 情绪评分 (0-100)
            
        Returns:
            情绪标签
        """
        if score >= 80:
            return "极度乐观"
        elif score >= 60:
            return "乐观"
        elif score >= 40:
            return "中性"
        elif score >= 20:
            return "悲观"
        else:
            return "极度悲观"

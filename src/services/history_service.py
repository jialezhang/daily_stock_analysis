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
import uuid
from copy import deepcopy
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Set

from src.config import get_config
from src.storage import DatabaseManager

logger = logging.getLogger(__name__)


class HistoryService:
    """
    历史查询服务
    
    封装历史分析记录的查询逻辑
    """
    
    SUPPORTED_PARTIAL_MODULES: Set[str] = {
        "price_zones",
        "pattern_signals",
        "technical_indicators",
        "sniper_points",
        "summary",
        "news",
        "position_management",
    }
    ALL_REFRESH_MODULES: List[str] = [
        "price_zones",
        "pattern_signals",
        "technical_indicators",
        "sniper_points",
        "summary",
        "news",
        "position_management",
    ]

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

    def delete_history_record(self, record_id: int) -> int:
        """
        Delete one history record by ID.

        Args:
            record_id: Analysis history primary key.

        Returns:
            Deleted row count (0 or 1).
        """
        try:
            return self.db.delete_analysis_history_by_id(record_id)
        except Exception as e:
            logger.error(f"删除历史记录失败: {e}", exc_info=True)
            return 0

    def refresh_history_record(
        self,
        record_id: int,
        mode: str = "full",
        modules: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Refresh one history record in-place."""
        target_record = self.db.get_analysis_history_by_id(record_id)
        if not target_record:
            return {
                "updated": False,
                "record_id": record_id,
                "mode": mode,
                "modules": [],
                "message": f"未找到 id={record_id} 的分析记录",
            }

        refresh_mode = "partial" if mode == "partial" else "full"
        normalized_modules = self._normalize_refresh_modules(refresh_mode, modules)
        if refresh_mode == "partial" and normalized_modules == ["position_management"]:
            pm_result = self.refresh_position_management(record_id=record_id)
            return {
                "updated": bool(pm_result.get("updated")),
                "record_id": record_id,
                "mode": refresh_mode,
                "modules": normalized_modules,
                "message": str(pm_result.get("message", "")),
            }
        temp_record = self._run_temp_fresh_analysis(
            code=target_record.code,
            report_type=(target_record.report_type or "detailed"),
        )
        if temp_record is None:
            return {
                "updated": False,
                "record_id": record_id,
                "mode": refresh_mode,
                "modules": normalized_modules,
                "message": "刷新失败：未生成新的分析结果",
            }

        try:
            updates = self._build_refresh_updates(
                target_record=target_record,
                fresh_record=temp_record,
                mode=refresh_mode,
                modules=normalized_modules,
            )
            if refresh_mode == "full":
                modules_to_touch = list(self.ALL_REFRESH_MODULES)
            else:
                modules_to_touch = normalized_modules or list(self.ALL_REFRESH_MODULES)
            self._touch_module_update_meta(updates, modules_to_touch)
            updated = self.db.update_analysis_history_by_id(record_id, updates) > 0
            return {
                "updated": updated,
                "record_id": record_id,
                "mode": refresh_mode,
                "modules": normalized_modules,
                "message": "刷新成功" if updated else "刷新失败：落库失败",
            }
        finally:
            if getattr(temp_record, "id", None):
                self.db.delete_analysis_history_by_id(int(temp_record.id))

    def upsert_manual_rhino_zone(
        self,
        record_id: int,
        upper: float,
        lower: float,
        strength_level: str = "中",
        name: Optional[str] = None,
        definition: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Persist one manual rhino zone into history technical module."""
        record = self.db.get_analysis_history_by_id(record_id)
        if not record:
            return {"updated": False, "record_id": record_id, "zone": None, "message": f"未找到 id={record_id} 的分析记录"}
        if not (upper > 0 and lower > 0 and upper > lower):
            return {"updated": False, "record_id": record_id, "zone": None, "message": "区间参数非法：需满足 upper > lower > 0"}

        level = str(strength_level or "中").strip()
        if level not in {"弱", "中", "强", "超强"}:
            level = "中"
        score_map = {"弱": 40, "中": 60, "强": 80, "超强": 95}

        raw_payload = self._safe_json_loads(record.raw_result)
        ctx_payload = self._safe_json_loads(record.context_snapshot)
        tm_raw = self._extract_technical_module_from_raw(raw_payload)
        tm_ctx = self._extract_technical_module_from_context(ctx_payload)

        zone_id = f"manual-{uuid.uuid4().hex[:12]}"
        base_name = (name or "").strip()
        definition_text = str(definition or "").strip()
        existing = self._extract_rhino_zones(tm_raw) or []
        manual_count = sum(1 for z in existing if str((z or {}).get("source_type", (z or {}).get("sourceType", ""))) == "manual")
        zone = {
            "id": zone_id,
            "name": base_name or f"手动区间{manual_count + 1}",
            "upper": float(upper),
            "lower": float(lower),
            "strength_level": level,
            "strength_score": score_map[level],
            "side": "",
            "key_levels": [],
            "logic_detail": definition_text or "手动新增区间",
            "definition": definition_text or "手动新增区间",
            "source_type": "manual",
        }

        rhino_raw = existing + [zone]
        rhino_raw.sort(key=lambda x: self._to_float((x or {}).get("upper")), reverse=True)

        self._inject_rhino_zones(tm_raw, rhino_raw)
        self._inject_rhino_zones(tm_ctx, rhino_raw)
        self._write_technical_module_to_raw(raw_payload, tm_raw)
        self._write_technical_module_to_context(ctx_payload, tm_ctx)

        payload_updates = {
            "raw_result": self._safe_json_dumps(raw_payload),
            "context_snapshot": self._safe_json_dumps(ctx_payload),
        }
        self._touch_module_update_meta(payload_updates, ["price_zones"])
        updated = self.db.update_analysis_history_by_id(record_id, payload_updates) > 0
        return {
            "updated": updated,
            "record_id": record_id,
            "zone": zone if updated else None,
            "message": "写入成功" if updated else "写入失败",
        }

    def delete_manual_rhino_zone(self, record_id: int, zone_id: str) -> Dict[str, Any]:
        """Delete one manual rhino zone by ID."""
        record = self.db.get_analysis_history_by_id(record_id)
        if not record:
            return {"deleted": False, "record_id": record_id, "zone_id": zone_id, "message": f"未找到 id={record_id} 的分析记录"}

        raw_payload = self._safe_json_loads(record.raw_result)
        ctx_payload = self._safe_json_loads(record.context_snapshot)
        tm_raw = self._extract_technical_module_from_raw(raw_payload)
        tm_ctx = self._extract_technical_module_from_context(ctx_payload)

        rhino = self._extract_rhino_zones(tm_raw) or []
        new_rhino = [z for z in rhino if str((z or {}).get("id", "")) != str(zone_id)]
        deleted = len(new_rhino) != len(rhino)
        if not deleted:
            return {"deleted": False, "record_id": record_id, "zone_id": zone_id, "message": "未找到指定区间"}

        self._inject_rhino_zones(tm_raw, new_rhino)
        self._inject_rhino_zones(tm_ctx, new_rhino)
        self._write_technical_module_to_raw(raw_payload, tm_raw)
        self._write_technical_module_to_context(ctx_payload, tm_ctx)

        payload_updates = {
            "raw_result": self._safe_json_dumps(raw_payload),
            "context_snapshot": self._safe_json_dumps(ctx_payload),
        }
        self._touch_module_update_meta(payload_updates, ["price_zones"])
        persisted = self.db.update_analysis_history_by_id(record_id, payload_updates) > 0
        return {
            "deleted": bool(deleted and persisted),
            "record_id": record_id,
            "zone_id": zone_id,
            "message": "删除成功" if deleted and persisted else "删除失败",
        }

    def update_manual_rhino_zone(
        self,
        record_id: int,
        zone_id: str,
        upper: float,
        lower: float,
        strength_level: str = "中",
        name: Optional[str] = None,
        definition: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update one manual rhino zone by ID."""
        record = self.db.get_analysis_history_by_id(record_id)
        if not record:
            return {"updated": False, "record_id": record_id, "zone": None, "message": f"未找到 id={record_id} 的分析记录"}
        if not (upper > 0 and lower > 0 and upper > lower):
            return {"updated": False, "record_id": record_id, "zone": None, "message": "区间参数非法：需满足 upper > lower > 0"}

        level = str(strength_level or "中").strip()
        if level not in {"弱", "中", "强", "超强"}:
            level = "中"
        score_map = {"弱": 40, "中": 60, "强": 80, "超强": 95}

        raw_payload = self._safe_json_loads(record.raw_result)
        ctx_payload = self._safe_json_loads(record.context_snapshot)
        tm_raw = self._extract_technical_module_from_raw(raw_payload)
        tm_ctx = self._extract_technical_module_from_context(ctx_payload)
        rhino = self._extract_rhino_zones(tm_raw) or []

        target_index = -1
        for i, item in enumerate(rhino):
            if str((item or {}).get("id", "")) == str(zone_id):
                target_index = i
                break
        if target_index < 0:
            return {"updated": False, "record_id": record_id, "zone": None, "message": "未找到指定区间"}

        target = rhino[target_index] or {}
        if str(target.get("source_type", target.get("sourceType", "manual"))) != "manual":
            return {"updated": False, "record_id": record_id, "zone": None, "message": "仅支持修改手动区间"}

        updated_zone = dict(target)
        updated_zone["upper"] = float(upper)
        updated_zone["lower"] = float(lower)
        updated_zone["strength_level"] = level
        updated_zone["strength_score"] = score_map[level]
        if name is not None:
            updated_zone["name"] = str(name).strip() or updated_zone.get("name", f"手动区间{target_index + 1}")
        if definition is not None:
            normalized_definition = str(definition).strip() or "手动定义区间"
            updated_zone["logic_detail"] = normalized_definition
            updated_zone["definition"] = normalized_definition
        rhino[target_index] = updated_zone
        rhino.sort(key=lambda x: self._to_float((x or {}).get("upper")), reverse=True)

        self._inject_rhino_zones(tm_raw, rhino)
        self._inject_rhino_zones(tm_ctx, rhino)
        self._write_technical_module_to_raw(raw_payload, tm_raw)
        self._write_technical_module_to_context(ctx_payload, tm_ctx)

        payload_updates = {
            "raw_result": self._safe_json_dumps(raw_payload),
            "context_snapshot": self._safe_json_dumps(ctx_payload),
        }
        self._touch_module_update_meta(payload_updates, ["price_zones"])
        persisted = self.db.update_analysis_history_by_id(record_id, payload_updates) > 0
        return {
            "updated": bool(persisted),
            "record_id": record_id,
            "zone": updated_zone if persisted else None,
            "message": "更新成功" if persisted else "更新失败",
        }

    def get_position_management(self, record_id: int) -> Dict[str, Any]:
        """Read position management module for one history record."""
        record = self.db.get_analysis_history_by_id(record_id)
        if not record:
            return {"updated": False, "record_id": record_id, "module": None, "message": f"未找到 id={record_id} 的分析记录"}

        raw_payload = self._safe_json_loads(record.raw_result)
        ctx_payload = self._safe_json_loads(record.context_snapshot)
        module = self._extract_position_management_from_raw(raw_payload)
        if not isinstance(module, dict) or not module:
            module = self._extract_position_management_from_context(ctx_payload)
        if not isinstance(module, dict):
            module = {}

        if not module:
            module = self._build_position_management_module(
                module={},
                raw_payload=raw_payload,
                record=record,
                refresh_benchmarks=False,
            )

        return {
            "updated": True,
            "record_id": record_id,
            "module": module,
            "message": "读取成功",
        }

    def upsert_position_management(
        self,
        record_id: int,
        target: Optional[Dict[str, Any]] = None,
        holdings: Optional[List[Dict[str, Any]]] = None,
        macro_events: Optional[List[str]] = None,
        notes: Optional[str] = None,
        refresh_benchmarks: bool = True,
    ) -> Dict[str, Any]:
        """Persist position management module for one history record."""
        record = self.db.get_analysis_history_by_id(record_id)
        if not record:
            return {"updated": False, "record_id": record_id, "module": None, "message": f"未找到 id={record_id} 的分析记录"}

        raw_payload = self._safe_json_loads(record.raw_result)
        ctx_payload = self._safe_json_loads(record.context_snapshot)
        existing = self._extract_position_management_from_raw(raw_payload)
        if not isinstance(existing, dict) or not existing:
            existing = self._extract_position_management_from_context(ctx_payload)
        if not isinstance(existing, dict):
            existing = {}

        module: Dict[str, Any] = deepcopy(existing)
        module["target"] = self._normalize_position_target(target or module.get("target"))
        normalized_holdings: List[Dict[str, Any]] = []
        for idx, item in enumerate(holdings or []):
            normalized = self._normalize_position_holding(item, idx + 1)
            if normalized:
                normalized_holdings.append(normalized)
        module["holdings"] = normalized_holdings
        module["macro_events"] = self._normalize_macro_events(macro_events if macro_events is not None else module.get("macro_events"))
        if notes is not None:
            module["notes"] = str(notes).strip()
        module = self._build_position_management_module(
            module=module,
            raw_payload=raw_payload,
            record=record,
            refresh_benchmarks=refresh_benchmarks,
        )

        self._write_position_management_to_raw(raw_payload, module)
        self._write_position_management_to_context(ctx_payload, module)
        payload_updates = {
            "raw_result": self._safe_json_dumps(raw_payload),
            "context_snapshot": self._safe_json_dumps(ctx_payload),
        }
        self._touch_module_update_meta(payload_updates, ["position_management"])
        updated = self.db.update_analysis_history_by_id(record_id, payload_updates) > 0
        return {
            "updated": bool(updated),
            "record_id": record_id,
            "module": module if updated else None,
            "message": "保存成功" if updated else "保存失败",
        }

    def refresh_position_management(self, record_id: int) -> Dict[str, Any]:
        """Recompute position management derived fields for one history record."""
        record = self.db.get_analysis_history_by_id(record_id)
        if not record:
            return {"updated": False, "record_id": record_id, "module": None, "message": f"未找到 id={record_id} 的分析记录"}

        raw_payload = self._safe_json_loads(record.raw_result)
        ctx_payload = self._safe_json_loads(record.context_snapshot)
        module = self._extract_position_management_from_raw(raw_payload)
        if not isinstance(module, dict) or not module:
            module = self._extract_position_management_from_context(ctx_payload)
        if not isinstance(module, dict):
            module = {}

        module = self._build_position_management_module(
            module=module,
            raw_payload=raw_payload,
            record=record,
            refresh_benchmarks=True,
        )
        self._write_position_management_to_raw(raw_payload, module)
        self._write_position_management_to_context(ctx_payload, module)
        payload_updates = {
            "raw_result": self._safe_json_dumps(raw_payload),
            "context_snapshot": self._safe_json_dumps(ctx_payload),
        }
        self._touch_module_update_meta(payload_updates, ["position_management"])
        updated = self.db.update_analysis_history_by_id(record_id, payload_updates) > 0
        return {
            "updated": bool(updated),
            "record_id": record_id,
            "module": module if updated else None,
            "message": "刷新成功" if updated else "刷新失败",
        }

    def _normalize_refresh_modules(self, mode: str, modules: Optional[List[str]]) -> List[str]:
        if mode != "partial":
            return []

        candidates = [str(item).strip().lower() for item in (modules or []) if str(item).strip()]
        normalized = [m for m in candidates if m in self.SUPPORTED_PARTIAL_MODULES]
        if normalized:
            # Keep unique order
            return list(dict.fromkeys(normalized))

        return [
            "price_zones",
            "pattern_signals",
            "technical_indicators",
            "sniper_points",
            "summary",
            "news",
            "position_management",
        ]

    def _run_temp_fresh_analysis(self, code: str, report_type: str):
        from src.services.analysis_service import AnalysisService

        query_id = f"refresh_{code}_{uuid.uuid4().hex[:12]}"
        service = AnalysisService()
        _ = service.analyze_stock(
            stock_code=code,
            report_type=report_type,
            force_refresh=True,
            query_id=query_id,
            send_notification=False,
        )
        records = self.db.get_analysis_history(query_id=query_id, code=code, limit=1)
        return records[0] if records else None

    def _build_refresh_updates(self, target_record, fresh_record, mode: str, modules: List[str]) -> Dict[str, Any]:
        old_raw = self._safe_json_loads(target_record.raw_result)
        new_raw = self._safe_json_loads(fresh_record.raw_result)
        old_ctx = self._safe_json_loads(target_record.context_snapshot)
        new_ctx = self._safe_json_loads(fresh_record.context_snapshot)

        if mode == "full":
            merged_raw = deepcopy(new_raw) if isinstance(new_raw, dict) else {}
            merged_ctx = deepcopy(new_ctx) if isinstance(new_ctx, dict) else {}
            self._preserve_rhino_zone_from_old(old_raw, merged_raw)
            self._preserve_rhino_zone_from_old_context(old_ctx, merged_ctx)
            self._preserve_position_management_from_old(old_raw, merged_raw, target_record)
            self._preserve_position_management_from_old_context(old_ctx, merged_ctx, target_record)
            return {
                "sentiment_score": fresh_record.sentiment_score,
                "operation_advice": fresh_record.operation_advice,
                "trend_prediction": fresh_record.trend_prediction,
                "analysis_summary": fresh_record.analysis_summary,
                "news_content": fresh_record.news_content,
                "ideal_buy": fresh_record.ideal_buy,
                "secondary_buy": fresh_record.secondary_buy,
                "stop_loss": fresh_record.stop_loss,
                "take_profit": fresh_record.take_profit,
                "raw_result": self._safe_json_dumps(merged_raw),
                "context_snapshot": self._safe_json_dumps(merged_ctx),
            }

        merged_raw = deepcopy(old_raw) if isinstance(old_raw, dict) else {}
        merged_ctx = deepcopy(old_ctx) if isinstance(old_ctx, dict) else {}

        if any(m in modules for m in ["price_zones", "pattern_signals", "technical_indicators"]):
            old_tm_raw = self._extract_technical_module_from_raw(merged_raw)
            new_tm_raw = self._extract_technical_module_from_raw(new_raw)
            merged_tm_raw = self._merge_technical_module(old_tm_raw, new_tm_raw, modules)
            self._write_technical_module_to_raw(merged_raw, merged_tm_raw)

            old_tm_ctx = self._extract_technical_module_from_context(merged_ctx)
            new_tm_ctx = self._extract_technical_module_from_context(new_ctx)
            merged_tm_ctx = self._merge_technical_module(old_tm_ctx, new_tm_ctx, modules)
            self._write_technical_module_to_context(merged_ctx, merged_tm_ctx)

        if "position_management" in modules:
            pm_raw = self._extract_position_management_from_raw(merged_raw) or {}
            merged_pm = self._build_position_management_module(
                module=pm_raw,
                raw_payload=merged_raw,
                record=target_record,
                refresh_benchmarks=True,
            )
            self._write_position_management_to_raw(merged_raw, merged_pm)
            self._write_position_management_to_context(merged_ctx, merged_pm)

        updates: Dict[str, Any] = {
            "raw_result": self._safe_json_dumps(merged_raw),
            "context_snapshot": self._safe_json_dumps(merged_ctx),
        }

        if "summary" in modules:
            updates.update(
                {
                    "sentiment_score": fresh_record.sentiment_score,
                    "operation_advice": fresh_record.operation_advice,
                    "trend_prediction": fresh_record.trend_prediction,
                    "analysis_summary": fresh_record.analysis_summary,
                }
            )

        if "sniper_points" in modules:
            updates.update(
                {
                    "ideal_buy": fresh_record.ideal_buy,
                    "secondary_buy": fresh_record.secondary_buy,
                    "stop_loss": fresh_record.stop_loss,
                    "take_profit": fresh_record.take_profit,
                }
            )

        if "news" in modules:
            updates["news_content"] = fresh_record.news_content

        return updates

    def _merge_technical_module(
        self,
        old_module: Optional[Dict[str, Any]],
        new_module: Optional[Dict[str, Any]],
        modules: List[str],
    ) -> Dict[str, Any]:
        merged = deepcopy(old_module) if isinstance(old_module, dict) else {}
        latest = new_module if isinstance(new_module, dict) else {}
        if not latest:
            return merged

        old_rhino = self._extract_rhino_zones(merged)

        if "price_zones" in modules and isinstance(latest.get("price_zones"), dict):
            merged["price_zones"] = deepcopy(latest.get("price_zones"))
        if "pattern_signals" in modules and isinstance(latest.get("pattern_signals_1y"), dict):
            merged["pattern_signals_1y"] = deepcopy(latest.get("pattern_signals_1y"))
        if "technical_indicators" in modules and isinstance(latest.get("technical_indicators"), dict):
            merged["technical_indicators"] = deepcopy(latest.get("technical_indicators"))

        if old_rhino is not None:
            self._inject_rhino_zones(merged, old_rhino)

        return merged

    def _preserve_rhino_zone_from_old(self, old_raw: Dict[str, Any], new_raw: Dict[str, Any]) -> None:
        old_tm = self._extract_technical_module_from_raw(old_raw)
        old_rhino = self._extract_rhino_zones(old_tm)
        if old_rhino is None:
            return
        new_tm = self._extract_technical_module_from_raw(new_raw)
        if not isinstance(new_tm, dict):
            return
        self._inject_rhino_zones(new_tm, old_rhino)
        self._write_technical_module_to_raw(new_raw, new_tm)

    def _preserve_rhino_zone_from_old_context(self, old_ctx: Dict[str, Any], new_ctx: Dict[str, Any]) -> None:
        old_tm = self._extract_technical_module_from_context(old_ctx)
        old_rhino = self._extract_rhino_zones(old_tm)
        if old_rhino is None:
            return
        new_tm = self._extract_technical_module_from_context(new_ctx)
        if not isinstance(new_tm, dict):
            return
        self._inject_rhino_zones(new_tm, old_rhino)
        self._write_technical_module_to_context(new_ctx, new_tm)

    def _preserve_position_management_from_old(
        self,
        old_raw: Dict[str, Any],
        new_raw: Dict[str, Any],
        record: Any,
    ) -> None:
        old_module = self._extract_position_management_from_raw(old_raw)
        if not isinstance(old_module, dict) or not old_module:
            return
        merged = self._build_position_management_module(
            module=old_module,
            raw_payload=new_raw,
            record=record,
            refresh_benchmarks=False,
        )
        self._write_position_management_to_raw(new_raw, merged)

    def _preserve_position_management_from_old_context(
        self,
        old_ctx: Dict[str, Any],
        new_ctx: Dict[str, Any],
        record: Any,
    ) -> None:
        old_module = self._extract_position_management_from_context(old_ctx)
        if not isinstance(old_module, dict) or not old_module:
            return
        merged = self._build_position_management_module(
            module=old_module,
            raw_payload=new_ctx,
            record=record,
            refresh_benchmarks=False,
        )
        self._write_position_management_to_context(new_ctx, merged)

    def _build_position_management_module(
        self,
        module: Dict[str, Any],
        raw_payload: Dict[str, Any],
        record: Any,
        refresh_benchmarks: bool,
    ) -> Dict[str, Any]:
        target = self._normalize_position_target(module.get("target"))
        holdings = []
        for idx, item in enumerate(module.get("holdings") or []):
            normalized = self._normalize_position_holding(item, idx + 1)
            if normalized:
                holdings.append(normalized)

        previous_derived = module.get("derived")
        previous_bench = previous_derived.get("benchmark_comparison") if isinstance(previous_derived, dict) else None
        benchmark_data = self._build_benchmark_comparison(
            holdings=holdings,
            target=target,
            refresh=refresh_benchmarks,
            fallback=previous_bench,
        )
        derived = self._build_position_derived(
            holdings=holdings,
            target=target,
            benchmark_data=benchmark_data,
        )
        ai_market_wind = self._build_ai_market_wind(
            holdings=holdings,
            target=target,
            derived=derived,
            raw_payload=raw_payload,
            record=record,
        )
        return {
            "version": 1,
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "target": target,
            "holdings": holdings,
            "macro_events": self._normalize_macro_events(module.get("macro_events")),
            "notes": str(module.get("notes") or "").strip(),
            "derived": {
                **derived,
                "benchmark_comparison": benchmark_data,
                "ai_market_wind": ai_market_wind,
            },
        }

    def _build_position_derived(
        self,
        holdings: List[Dict[str, Any]],
        target: Dict[str, Any],
        benchmark_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        usd_cny = self._to_float(target.get("usd_cny")) or 7.2
        usd_hkd = self._to_float(target.get("usd_hkd")) or 7.8
        base_currency = self._normalize_base_currency(target.get("base_currency"))

        total_value = 0.0
        total_cost = 0.0
        daily_pnl = 0.0
        allocation: Dict[str, float] = {}
        heatmap: List[Dict[str, Any]] = []
        per_symbol: List[Dict[str, Any]] = []

        for item in holdings:
            quantity = self._to_float(item.get("quantity"))
            current_price = self._to_float(item.get("current_price"))
            avg_cost = self._to_float(item.get("avg_cost"))
            previous_close = self._to_float(item.get("previous_close"))
            currency = self._normalize_currency(item.get("currency"))

            market_value_native = quantity * current_price
            cost_native = quantity * avg_cost
            market_value = self._convert_to_base(
                market_value_native,
                from_currency=currency,
                base_currency=base_currency,
                usd_cny=usd_cny,
                usd_hkd=usd_hkd,
            )
            cost_value = self._convert_to_base(
                cost_native,
                from_currency=currency,
                base_currency=base_currency,
                usd_cny=usd_cny,
                usd_hkd=usd_hkd,
            )
            day_native = quantity * (current_price - previous_close) if previous_close > 0 else 0.0
            day_value = self._convert_to_base(
                day_native,
                from_currency=currency,
                base_currency=base_currency,
                usd_cny=usd_cny,
                usd_hkd=usd_hkd,
            )
            pnl = market_value - cost_value
            ret_pct = (pnl / cost_value * 100.0) if cost_value > 0 else 0.0
            day_pct = ((current_price - previous_close) / previous_close * 100.0) if previous_close > 0 else 0.0

            total_value += market_value
            total_cost += cost_value
            daily_pnl += day_value

            asset_class = str(item.get("asset_class") or "其他")
            allocation[asset_class] = allocation.get(asset_class, 0.0) + market_value
            per_symbol.append(
                {
                    "symbol": item.get("symbol"),
                    "name": item.get("name"),
                    "asset_class": asset_class,
                    "market_type": item.get("market_type"),
                    "market_value": round(market_value, 2),
                    "cost_value": round(cost_value, 2),
                    "pnl": round(pnl, 2),
                    "return_pct": round(ret_pct, 2),
                    "day_change_pct": round(day_pct, 2),
                }
            )
            heatmap.append(
                {
                    "symbol": item.get("symbol"),
                    "name": item.get("name"),
                    "asset_class": asset_class,
                    "change_pct": round(day_pct, 2),
                    "pnl": round(pnl, 2),
                    "intensity": round(min(1.0, abs(day_pct) / 8.0), 4),
                }
            )
        heatmap.sort(key=lambda row: self._to_float(row.get("change_pct")), reverse=True)

        cumulative_pnl = total_value - total_cost
        cumulative_return_pct = (cumulative_pnl / total_cost * 100.0) if total_cost > 0 else 0.0
        target_pct = self._to_float(target.get("annual_return_target_pct")) or 30.0
        today = datetime.now()
        year_days = 366 if (today.year % 4 == 0 and (today.year % 100 != 0 or today.year % 400 == 0)) else 365
        day_of_year = max(1, min(today.timetuple().tm_yday, year_days))
        progress_ratio = day_of_year / year_days
        target_today_pct = target_pct * progress_ratio
        gap_to_target_pct = target_pct - cumulative_return_pct
        days_left = max(1, year_days - day_of_year)
        required_daily_pct = self._estimate_required_daily_return_pct(
            current_return_pct=cumulative_return_pct,
            target_return_pct=target_pct,
            days_left=days_left,
        )

        allocation_rows: List[Dict[str, Any]] = []
        for asset_class, value in sorted(allocation.items(), key=lambda x: x[1], reverse=True):
            ratio = (value / total_value * 100.0) if total_value > 0 else 0.0
            allocation_rows.append(
                {
                    "asset_class": asset_class,
                    "market_value": round(value, 2),
                    "ratio_pct": round(ratio, 2),
                }
            )

        progress_pct = (cumulative_return_pct / target_pct * 100.0) if target_pct != 0 else 0.0
        latest_benchmark = {}
        if isinstance(benchmark_data, dict):
            latest_benchmark = benchmark_data.get("latest_returns") or {}

        return {
            "currency": base_currency,
            "totals": {
                "total_value": round(total_value, 2),
                "total_cost": round(total_cost, 2),
                "daily_pnl": round(daily_pnl, 2),
                "cumulative_pnl": round(cumulative_pnl, 2),
                "cumulative_return_pct": round(cumulative_return_pct, 2),
            },
            "target_progress": {
                "annual_target_pct": round(target_pct, 2),
                "target_today_pct": round(target_today_pct, 2),
                "current_return_pct": round(cumulative_return_pct, 2),
                "gap_to_target_pct": round(gap_to_target_pct, 2),
                "progress_pct": round(progress_pct, 2),
                "days_left": int(days_left),
                "required_daily_return_pct": required_daily_pct,
            },
            "allocation": allocation_rows,
            "heatmap": heatmap,
            "holdings_overview": per_symbol,
            "benchmark_latest_returns": latest_benchmark,
        }

    def _build_benchmark_comparison(
        self,
        holdings: List[Dict[str, Any]],
        target: Dict[str, Any],
        refresh: bool,
        fallback: Any,
    ) -> Dict[str, Any]:
        if not refresh:
            if isinstance(fallback, dict):
                return deepcopy(fallback)
            return {
                "as_of": datetime.now().isoformat(timespec="seconds"),
                "series": [],
                "latest_returns": {},
                "symbols": ["沪深300", "恒生指数", "标普500", "纳斯达克", "VIX"],
            }

        series: List[Dict[str, Any]] = []
        latest_returns: Dict[str, float] = {}
        base_currency = self._normalize_base_currency(target.get("base_currency"))
        usd_cny = self._to_float(target.get("usd_cny")) or 7.2
        usd_hkd = self._to_float(target.get("usd_hkd")) or 7.8

        start_date = (datetime.now() - timedelta(days=365)).date().isoformat()
        end_date = datetime.now().date().isoformat()

        portfolio_points = self._build_portfolio_return_curve(
            holdings=holdings,
            base_currency=base_currency,
            usd_cny=usd_cny,
            usd_hkd=usd_hkd,
            start_date=start_date,
            end_date=end_date,
        )
        if portfolio_points:
            series.append({"name": "组合收益", "code": "portfolio", "points": portfolio_points})
            latest_returns["portfolio"] = round(self._to_float(portfolio_points[-1].get("value")), 2)

        benchmark_symbols = [
            ("沪深300", "hs300", "000300.SS"),
            ("恒生指数", "hsi", "^HSI"),
            ("标普500", "sp500", "^GSPC"),
            ("纳斯达克", "nasdaq", "^IXIC"),
            ("VIX", "vix", "^VIX"),
        ]
        for name, code, yf_symbol in benchmark_symbols:
            points = self._fetch_yfinance_return_curve(yf_symbol, start_date, end_date)
            if not points:
                continue
            series.append({"name": name, "code": code, "points": points})
            latest_returns[code] = round(self._to_float(points[-1].get("value")), 2)

        if not series and isinstance(fallback, dict):
            return deepcopy(fallback)

        return {
            "as_of": datetime.now().isoformat(timespec="seconds"),
            "series": series,
            "latest_returns": latest_returns,
            "symbols": ["沪深300", "恒生指数", "标普500", "纳斯达克", "VIX"],
        }

    def _build_portfolio_return_curve(
        self,
        holdings: List[Dict[str, Any]],
        base_currency: str,
        usd_cny: float,
        usd_hkd: float,
        start_date: str,
        end_date: str,
    ) -> List[Dict[str, Any]]:
        try:
            import pandas as pd
        except Exception:
            return []

        frame_rows: Dict[str, Any] = {}
        for item in holdings:
            symbol = self._resolve_yfinance_symbol(item)
            quantity = self._to_float(item.get("quantity"))
            currency = self._normalize_currency(item.get("currency"))
            if not symbol or quantity <= 0:
                continue
            points = self._fetch_yfinance_price_points(symbol, start_date, end_date)
            if not points:
                continue
            row = {p["date"]: self._to_float(p["value"]) for p in points}
            if not row:
                continue
            series = pd.Series(row, dtype=float).sort_index()
            if series.empty:
                continue
            series = series.ffill().bfill()
            converted = series.apply(
                lambda val: self._convert_to_base(
                    amount=val * quantity,
                    from_currency=currency,
                    base_currency=base_currency,
                    usd_cny=usd_cny,
                    usd_hkd=usd_hkd,
                )
            )
            frame_rows[str(item.get("symbol") or symbol)] = converted

        if not frame_rows:
            return []

        df = pd.DataFrame(frame_rows).sort_index().ffill().bfill()
        if df.empty:
            return []
        total_series = df.sum(axis=1)
        if total_series.empty:
            return []
        first_val = float(total_series.iloc[0])
        if first_val == 0:
            return []

        points: List[Dict[str, Any]] = []
        for index, value in total_series.items():
            dt = str(index)[:10]
            ret = (float(value) / first_val - 1.0) * 100.0
            points.append({"date": dt, "value": round(ret, 4)})
        return points

    def _fetch_yfinance_return_curve(self, yf_symbol: str, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        points = self._fetch_yfinance_price_points(yf_symbol, start_date, end_date)
        if not points:
            return []
        first = self._to_float(points[0].get("value"))
        if first == 0:
            return []
        result = []
        for row in points:
            ret = (self._to_float(row.get("value")) / first - 1.0) * 100.0
            result.append({"date": row.get("date"), "value": round(ret, 4)})
        return result

    def _fetch_yfinance_price_points(self, symbol: str, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        try:
            import yfinance as yf
        except Exception:
            return []

        try:
            df = yf.download(
                tickers=symbol,
                start=start_date,
                end=end_date,
                progress=False,
                auto_adjust=True,
                threads=False,
            )
            if df is None or df.empty:
                return []
            close_col = df.get("Close")
            if close_col is None:
                return []
            if hasattr(close_col, "columns"):
                if close_col.shape[1] <= 0:
                    return []
                close_col = close_col.iloc[:, 0]
            rows = []
            for idx, val in close_col.dropna().items():
                dt = str(idx)[:10]
                rows.append({"date": dt, "value": float(val)})
            return rows
        except Exception:
            return []

    def _build_ai_market_wind(
        self,
        holdings: List[Dict[str, Any]],
        target: Dict[str, Any],
        derived: Dict[str, Any],
        raw_payload: Dict[str, Any],
        record: Any,
    ) -> Dict[str, Any]:
        allocation = derived.get("allocation") if isinstance(derived, dict) else []
        top_allocation = allocation[0] if isinstance(allocation, list) and allocation else {}
        top_ratio = self._to_float(top_allocation.get("ratio_pct"))
        latest_returns = derived.get("benchmark_latest_returns") if isinstance(derived, dict) else {}
        vix = self._to_float((latest_returns or {}).get("vix"))
        if vix >= 30:
            sentiment = "恐惧偏高"
        elif vix >= 20:
            sentiment = "中性偏谨慎"
        elif vix > 0:
            sentiment = "偏贪婪"
        else:
            sentiment = "数据不足"

        recommendations: List[str] = []
        if top_ratio >= 45:
            recommendations.append(
                f"单一资产大类占比 {top_ratio:.1f}%，偏离分散化，建议逐步再平衡。"
            )
        totals = derived.get("totals") if isinstance(derived, dict) else {}
        day_pnl = self._to_float((totals or {}).get("daily_pnl"))
        cum_ret = self._to_float((totals or {}).get("cumulative_return_pct"))
        if day_pnl < 0 and cum_ret > 20:
            recommendations.append("组合累计收益较高且当日回撤，建议对高波动资产分批止盈。")
        if day_pnl > 0 and cum_ret < 0:
            recommendations.append("组合处于修复期，可优先加仓估值合理且趋势修复的核心资产。")

        holding_advice = []
        for item in holdings[:20]:
            symbol = str(item.get("symbol") or "")
            qty = self._to_float(item.get("quantity"))
            current = self._to_float(item.get("current_price"))
            avg = self._to_float(item.get("avg_cost"))
            prev = self._to_float(item.get("previous_close"))
            if qty <= 0 or current <= 0:
                continue
            pnl_pct = ((current - avg) / avg * 100.0) if avg > 0 else 0.0
            day_pct = ((current - prev) / prev * 100.0) if prev > 0 else 0.0
            if pnl_pct >= 20 and day_pct <= -3:
                holding_advice.append(f"{symbol}: 累计盈利较高且出现回撤，可关注部分止盈。")
            elif pnl_pct <= -10 and day_pct >= 2:
                holding_advice.append(f"{symbol}: 超跌后出现反弹，可结合支撑位小仓位试探。")
            elif abs(day_pct) >= 5:
                holding_advice.append(f"{symbol}: 当日波动较大，建议降低杠杆并收紧止损。")

        macro_events = self._normalize_macro_events(raw_payload.get("macro_events"))
        if not macro_events:
            module_macro = raw_payload.get("position_management")
            if isinstance(module_macro, dict):
                macro_events = self._normalize_macro_events(module_macro.get("macro_events"))
        if not macro_events:
            fallback_news = str(getattr(record, "news_content", "") or "").strip()
            if fallback_news:
                macro_events = [line.strip("- ").strip() for line in fallback_news.splitlines() if line.strip()][:3]

        if not recommendations and not holding_advice:
            recommendations.append("当前仓位结构未触发明显风险阈值，维持纪律化交易与分批执行。")

        return {
            "base_currency": self._normalize_base_currency(target.get("base_currency")),
            "market_sentiment": sentiment,
            "vix_return_pct": round(vix, 2) if vix else None,
            "macro_events": macro_events,
            "portfolio_rebalance": recommendations,
            "actionable_insights": holding_advice[:8],
            "as_of": datetime.now().isoformat(timespec="seconds"),
        }

    @staticmethod
    def _estimate_required_daily_return_pct(current_return_pct: float, target_return_pct: float, days_left: int) -> Optional[float]:
        if days_left <= 0:
            return None
        cur_factor = 1.0 + (current_return_pct / 100.0)
        tgt_factor = 1.0 + (target_return_pct / 100.0)
        if cur_factor <= 0 or tgt_factor <= 0:
            return None
        if tgt_factor <= cur_factor:
            return 0.0
        try:
            val = (tgt_factor / cur_factor) ** (1.0 / float(days_left)) - 1.0
            return round(val * 100.0, 4)
        except Exception:
            return None

    def _resolve_yfinance_symbol(self, holding: Dict[str, Any]) -> str:
        market_type = str(holding.get("market_type") or "").strip().lower()
        raw_symbol = str(holding.get("symbol") or "").strip().upper()
        if not raw_symbol:
            return ""

        if market_type in {"a_share", "a", "cn"}:
            digits = "".join(ch for ch in raw_symbol if ch.isdigit())
            if len(digits) == 6:
                if digits.startswith(("600", "601", "603", "605", "688")):
                    return f"{digits}.SS"
                return f"{digits}.SZ"
        if market_type in {"hk", "h_share"}:
            digits = "".join(ch for ch in raw_symbol if ch.isdigit())
            if digits:
                return f"{digits.zfill(4)}.HK"
            if raw_symbol.endswith(".HK"):
                return raw_symbol
        if market_type in {"crypto", "coin"}:
            if "-" in raw_symbol:
                return raw_symbol
            return f"{raw_symbol}-USD"
        return raw_symbol

    def _normalize_position_target(self, target: Any) -> Dict[str, Any]:
        src = target if isinstance(target, dict) else {}
        annual = self._to_float(src.get("annual_return_target_pct"))
        if annual == 0 and src.get("annual_return_target_pct") in (None, ""):
            annual = 30.0
        usd_cny = self._to_float(src.get("usd_cny")) or 7.2
        usd_hkd = self._to_float(src.get("usd_hkd")) or 7.8
        return {
            "annual_return_target_pct": round(annual, 4),
            "base_currency": self._normalize_base_currency(src.get("base_currency")),
            "usd_cny": round(max(0.0001, usd_cny), 6),
            "usd_hkd": round(max(0.0001, usd_hkd), 6),
        }

    def _normalize_position_holding(self, item: Any, fallback_index: int) -> Optional[Dict[str, Any]]:
        if not isinstance(item, dict):
            return None
        symbol = str(item.get("symbol") or "").strip().upper()
        quantity = self._to_float(item.get("quantity"))
        avg_cost = self._to_float(item.get("avg_cost"))
        current_price = self._to_float(item.get("current_price"))
        previous_close = self._to_float(item.get("previous_close"))
        market_type = str(item.get("market_type") or "other").strip().lower()
        asset_class = str(item.get("asset_class") or "").strip()
        if not asset_class:
            asset_class = self._market_type_to_asset_class(market_type)
        if not symbol:
            symbol = f"HOLDING_{fallback_index}"
        return {
            "id": str(item.get("id") or f"holding-{uuid.uuid4().hex[:8]}"),
            "market_type": market_type or "other",
            "asset_class": asset_class,
            "symbol": symbol,
            "name": str(item.get("name") or symbol).strip(),
            "quantity": round(max(0.0, quantity), 6),
            "avg_cost": round(max(0.0, avg_cost), 8),
            "current_price": round(max(0.0, current_price), 8),
            "previous_close": round(max(0.0, previous_close), 8) if previous_close > 0 else None,
            "currency": self._normalize_currency(item.get("currency")),
        }

    @staticmethod
    def _market_type_to_asset_class(market_type: str) -> str:
        mapping = {
            "a_share": "A股",
            "cn": "A股",
            "hk": "港股",
            "h_share": "港股",
            "us": "美股",
            "crypto": "加密货币",
            "coin": "加密货币",
            "money_fund": "货币基金",
        }
        return mapping.get(str(market_type or "").strip().lower(), "其他")

    @staticmethod
    def _normalize_base_currency(value: Any) -> str:
        text = str(value or "").strip().upper()
        if text in {"RMB", "CNY"}:
            return "CNY"
        return "USD"

    @staticmethod
    def _normalize_currency(value: Any) -> str:
        text = str(value or "").strip().upper()
        if text in {"RMB", "CNY", "CNH"}:
            return "CNY"
        if text == "HKD":
            return "HKD"
        return "USD"

    @staticmethod
    def _normalize_macro_events(value: Any) -> List[str]:
        if not isinstance(value, list):
            return []
        rows = []
        for item in value:
            text = str(item or "").strip()
            if text:
                rows.append(text)
        return rows[:10]

    def _convert_to_base(
        self,
        amount: float,
        from_currency: str,
        base_currency: str,
        usd_cny: float,
        usd_hkd: float,
    ) -> float:
        source = self._normalize_currency(from_currency)
        target = self._normalize_base_currency(base_currency)
        if source == target:
            return float(amount)

        amount_val = float(amount)
        if source == "CNY" and target == "USD":
            return amount_val / usd_cny if usd_cny > 0 else amount_val
        if source == "USD" and target == "CNY":
            return amount_val * usd_cny
        if source == "HKD" and target == "USD":
            return amount_val / usd_hkd if usd_hkd > 0 else amount_val
        if source == "USD" and target == "HKD":
            return amount_val * usd_hkd
        if source == "HKD" and target == "CNY":
            usd_val = amount_val / usd_hkd if usd_hkd > 0 else amount_val
            return usd_val * usd_cny
        if source == "CNY" and target == "HKD":
            usd_val = amount_val / usd_cny if usd_cny > 0 else amount_val
            return usd_val * usd_hkd
        return amount_val

    @staticmethod
    def _safe_json_loads(value: Any) -> Dict[str, Any]:
        if isinstance(value, dict):
            return value
        if not value:
            return {}
        try:
            parsed = json.loads(value) if isinstance(value, str) else value
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}

    @staticmethod
    def _safe_json_dumps(value: Any) -> Optional[str]:
        if value is None:
            return None
        try:
            return json.dumps(value, ensure_ascii=False)
        except Exception:
            return None

    @staticmethod
    def _to_float(value: Any) -> float:
        try:
            return float(value)
        except Exception:
            return 0.0

    @staticmethod
    def _extract_technical_module_from_raw(payload: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(payload, dict):
            return {}
        module = payload.get("technical_module")
        return module if isinstance(module, dict) else {}

    @staticmethod
    def _write_technical_module_to_raw(payload: Dict[str, Any], technical_module: Dict[str, Any]) -> None:
        if isinstance(payload, dict):
            payload["technical_module"] = technical_module

    @staticmethod
    def _extract_technical_module_from_context(payload: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(payload, dict):
            return {}
        enhanced = payload.get("enhanced_context")
        if not isinstance(enhanced, dict):
            enhanced = {}
            payload["enhanced_context"] = enhanced
        module = enhanced.get("technical_module")
        if isinstance(module, dict):
            return module
        module = {}
        enhanced["technical_module"] = module
        return module

    @staticmethod
    def _write_technical_module_to_context(payload: Dict[str, Any], technical_module: Dict[str, Any]) -> None:
        if not isinstance(payload, dict):
            return
        enhanced = payload.get("enhanced_context")
        if not isinstance(enhanced, dict):
            enhanced = {}
            payload["enhanced_context"] = enhanced
        enhanced["technical_module"] = technical_module

    @staticmethod
    def _extract_position_management_from_raw(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not isinstance(payload, dict):
            return None
        module = payload.get("position_management")
        return deepcopy(module) if isinstance(module, dict) else None

    @staticmethod
    def _write_position_management_to_raw(payload: Dict[str, Any], module: Dict[str, Any]) -> None:
        if isinstance(payload, dict):
            payload["position_management"] = deepcopy(module)

    @staticmethod
    def _extract_position_management_from_context(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not isinstance(payload, dict):
            return None
        enhanced = payload.get("enhanced_context")
        if not isinstance(enhanced, dict):
            return None
        module = enhanced.get("position_management")
        return deepcopy(module) if isinstance(module, dict) else None

    @staticmethod
    def _write_position_management_to_context(payload: Dict[str, Any], module: Dict[str, Any]) -> None:
        if not isinstance(payload, dict):
            return
        enhanced = payload.get("enhanced_context")
        if not isinstance(enhanced, dict):
            enhanced = {}
            payload["enhanced_context"] = enhanced
        enhanced["position_management"] = deepcopy(module)

    @staticmethod
    def _extract_rhino_zones(technical_module: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
        if not isinstance(technical_module, dict):
            return None
        price_zones = technical_module.get("price_zones")
        if not isinstance(price_zones, dict):
            return None
        rhino = price_zones.get("rhino_zones")
        if not isinstance(rhino, list):
            return None
        return deepcopy(rhino)

    @staticmethod
    def _inject_rhino_zones(technical_module: Dict[str, Any], rhino_zones: List[Dict[str, Any]]) -> None:
        if not isinstance(technical_module, dict):
            return
        price_zones = technical_module.get("price_zones")
        if not isinstance(price_zones, dict):
            price_zones = {}
            technical_module["price_zones"] = price_zones
        price_zones["rhino_zones"] = deepcopy(rhino_zones)

    def _touch_module_update_meta(self, updates: Dict[str, Any], modules: List[str]) -> None:
        """Record per-module update timestamps into raw_result.module_update_meta."""
        raw = self._safe_json_loads(updates.get("raw_result"))
        if not isinstance(raw, dict):
            raw = {}
        meta = raw.get("module_update_meta")
        if not isinstance(meta, dict):
            meta = {}
            raw["module_update_meta"] = meta

        now_iso = datetime.now().isoformat(timespec="seconds")
        module_list = [str(m).strip().lower() for m in modules if str(m).strip()]
        for module in list(dict.fromkeys(module_list)):
            item = meta.get(module)
            if not isinstance(item, dict):
                item = {}
            history = item.get("history")
            if not isinstance(history, list):
                history = []
            history.append(now_iso)
            if len(history) > 30:
                history = history[-30:]
            try:
                prev_count = int(item.get("update_count", 0))
            except Exception:
                prev_count = 0
            item["last_updated_at"] = now_iso
            item["history"] = history
            item["update_count"] = prev_count + 1
            meta[module] = item

        updates["raw_result"] = self._safe_json_dumps(raw)

    def get_module_last_updated_at(self, record_id: int, module: str) -> Optional[str]:
        """Read one module's last_updated_at from raw_result.module_update_meta."""
        record = self.db.get_analysis_history_by_id(record_id)
        if not record:
            return None
        raw = self._safe_json_loads(record.raw_result)
        meta = raw.get("module_update_meta") if isinstance(raw, dict) else None
        if not isinstance(meta, dict):
            return None
        item = meta.get(str(module).strip().lower())
        if not isinstance(item, dict):
            return None
        val = item.get("last_updated_at")
        return str(val) if val else None

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
            from src.search_service import SearchService
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

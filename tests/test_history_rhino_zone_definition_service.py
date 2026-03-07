# -*- coding: utf-8 -*-
"""Unit tests for manual rhino zone definition persistence."""

import json
import unittest
from types import SimpleNamespace

from src.services.history_service import HistoryService


class _FakeDB:
    def __init__(self) -> None:
        self.record = SimpleNamespace(
            id=1,
            raw_result=json.dumps({"technical_module": {"price_zones": {"rhino_zones": []}}}, ensure_ascii=False),
            context_snapshot=json.dumps({"enhanced_context": {"technical_module": {"price_zones": {"rhino_zones": []}}}}, ensure_ascii=False),
        )

    def get_analysis_history_by_id(self, record_id: int):
        if record_id != 1:
            return None
        return self.record

    def update_analysis_history_by_id(self, record_id: int, updates):
        if record_id != 1:
            return 0
        if "raw_result" in updates:
            self.record.raw_result = updates["raw_result"]
        if "context_snapshot" in updates:
            self.record.context_snapshot = updates["context_snapshot"]
        return 1


class RhinoZoneDefinitionServiceTestCase(unittest.TestCase):
    """Verify definition field is persisted and can be updated."""

    def setUp(self) -> None:
        self.db = _FakeDB()
        self.service = HistoryService(self.db)

    def test_definition_persist_on_add_and_update(self) -> None:
        add_result = self.service.upsert_manual_rhino_zone(
            record_id=1,
            upper=200.0,
            lower=190.0,
            strength_level="强",
            definition="初始定义",
        )
        self.assertTrue(add_result["updated"])
        zone = add_result["zone"] or {}
        zone_id = str(zone.get("id", ""))
        self.assertTrue(zone_id)
        self.assertEqual(zone.get("logic_detail"), "初始定义")
        self.assertEqual(zone.get("definition"), "初始定义")

        raw_after_add = json.loads(self.db.record.raw_result)
        saved_zone = raw_after_add["technical_module"]["price_zones"]["rhino_zones"][0]
        self.assertEqual(saved_zone.get("logic_detail"), "初始定义")
        self.assertEqual(saved_zone.get("definition"), "初始定义")

        update_result = self.service.update_manual_rhino_zone(
            record_id=1,
            zone_id=zone_id,
            upper=201.0,
            lower=191.0,
            strength_level="中",
            definition="更新定义",
        )
        self.assertTrue(update_result["updated"])
        updated_zone = update_result["zone"] or {}
        self.assertEqual(updated_zone.get("logic_detail"), "更新定义")
        self.assertEqual(updated_zone.get("definition"), "更新定义")

        raw_after_update = json.loads(self.db.record.raw_result)
        saved_zone_after_update = raw_after_update["technical_module"]["price_zones"]["rhino_zones"][0]
        self.assertEqual(saved_zone_after_update.get("logic_detail"), "更新定义")
        self.assertEqual(saved_zone_after_update.get("definition"), "更新定义")


if __name__ == "__main__":
    unittest.main()

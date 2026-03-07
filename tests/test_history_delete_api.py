# -*- coding: utf-8 -*-
"""Integration tests for deleting analysis history records."""

import os
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from api.app import create_app
from src.analyzer import AnalysisResult
from src.config import Config
from src.storage import DatabaseManager


class HistoryDeleteApiTestCase(unittest.TestCase):
    """Verify DELETE /api/v1/history/{record_id} behavior."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp_dir.name)
        os.environ["DATABASE_PATH"] = str(self.data_dir / "test_history_delete.db")
        Config.reset_instance()
        DatabaseManager.reset_instance()

        self.db = DatabaseManager.get_instance()
        self.client = TestClient(create_app(static_dir=self.data_dir / "empty-static"))

        result = AnalysisResult(
            code="600519",
            name="贵州茅台",
            sentiment_score=70,
            trend_prediction="震荡偏强",
            operation_advice="持有",
            analysis_summary="test summary",
        )
        self.db.save_analysis_history(
            result=result,
            query_id="history_delete_test_qid",
            report_type="detailed",
            news_content="",
            context_snapshot=None,
            save_snapshot=False,
        )
        rows = self.db.get_analysis_history(query_id="history_delete_test_qid", limit=1)
        self.assertTrue(rows)
        self.record_id = rows[0].id

    def tearDown(self) -> None:
        DatabaseManager.reset_instance()
        Config.reset_instance()
        os.environ.pop("DATABASE_PATH", None)
        self.temp_dir.cleanup()

    def test_delete_history_record_success(self) -> None:
        response = self.client.delete(f"/api/v1/history/{self.record_id}")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload.get("deleted"), 1)

        remaining = self.db.get_analysis_history_by_id(self.record_id)
        self.assertIsNone(remaining)

    def test_delete_history_record_not_found(self) -> None:
        response = self.client.delete("/api/v1/history/999999")
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()

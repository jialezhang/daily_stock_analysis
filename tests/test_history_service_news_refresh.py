# -*- coding: utf-8 -*-
"""
HistoryService news refresh tests.
"""

import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from src.analyzer import AnalysisResult
from src.config import Config
from src.search_service import SearchResponse, SearchResult
from src.services.history_service import HistoryService
from src.storage import DatabaseManager


class HistoryServiceNewsRefreshTestCase(unittest.TestCase):
    """Verify refresh path can fetch news for old records with empty intel."""

    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self._db_path = os.path.join(self._temp_dir.name, "test_history_refresh.db")
        os.environ["DATABASE_PATH"] = self._db_path

        Config._instance = None
        DatabaseManager.reset_instance()
        self.db = DatabaseManager.get_instance()
        self.service = HistoryService(self.db)

        result = AnalysisResult(
            code="600118",
            name="中国卫星",
            sentiment_score=50,
            trend_prediction="震荡",
            operation_advice="观望",
            analysis_summary="test",
        )
        self.db.save_analysis_history(
            result=result,
            query_id="qid_001",
            report_type="full",
            news_content=None,
            context_snapshot=None,
            save_snapshot=False,
        )
        self.record_id = self.db.get_analysis_history(query_id="qid_001", limit=1)[0].id

    def tearDown(self) -> None:
        DatabaseManager.reset_instance()
        self._temp_dir.cleanup()

    def test_get_news_intel_by_record_id_force_refresh_fetches_when_empty(self) -> None:
        """Force refresh should fetch and return latest news when no historical news exists."""
        self.assertEqual(
            self.service.get_news_intel_by_record_id(self.record_id, limit=20),
            [],
        )

        fake_response = SearchResponse(
            query="中国卫星 600118 股票 最新消息",
            results=[
                SearchResult(
                    title="中国卫星发布新动态",
                    snippet="测试摘要",
                    url="https://example.com/news/600118",
                    source="example.com",
                    published_date="2026-02-27",
                )
            ],
            provider="Bocha",
            success=True,
        )

        with patch("src.services.history_service.SearchService") as mock_search_service_cls:
            mock_search_service = MagicMock()
            mock_search_service.is_available = True
            mock_search_service.search_stock_news.return_value = fake_response
            mock_search_service_cls.return_value = mock_search_service

            items = self.service.get_news_intel_by_record_id(
                self.record_id,
                limit=20,
                force_refresh=True,
            )

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["title"], "中国卫星发布新动态")


if __name__ == "__main__":
    unittest.main()

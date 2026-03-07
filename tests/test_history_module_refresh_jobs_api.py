# -*- coding: utf-8 -*-
"""API tests for async module refresh job endpoints."""

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.app import create_app
from api.v1.endpoints import history as history_endpoint


class HistoryModuleRefreshJobsApiTestCase(unittest.TestCase):
    """Verify module refresh start/list API behavior."""

    def setUp(self) -> None:
        self.client = TestClient(create_app())
        with history_endpoint._MODULE_REFRESH_LOCK:
            history_endpoint._MODULE_REFRESH_JOBS.clear()

    def tearDown(self) -> None:
        with history_endpoint._MODULE_REFRESH_LOCK:
            history_endpoint._MODULE_REFRESH_JOBS.clear()

    @patch("api.v1.endpoints.history._MODULE_REFRESH_EXECUTOR.submit")
    def test_start_module_refresh_success(self, mock_submit) -> None:
        response = self.client.post("/api/v1/history/11/modules/news/refresh")
        self.assertEqual(response.status_code, 200)
        payload = response.json()

        self.assertTrue(payload["accepted"])
        self.assertEqual(payload["job"]["record_id"], 11)
        self.assertEqual(payload["job"]["module"], "news")
        self.assertEqual(payload["job"]["status"], "queued")
        self.assertIn("job_id", payload["job"])
        mock_submit.assert_called_once()

    def test_start_module_refresh_invalid_module(self) -> None:
        response = self.client.post("/api/v1/history/11/modules/unknown/refresh")
        self.assertEqual(response.status_code, 400)
        payload = response.json()
        detail = payload.get("detail", payload)
        self.assertIn("不支持的模块", detail.get("message", ""))

    def test_list_module_refresh_jobs_by_record(self) -> None:
        with history_endpoint._MODULE_REFRESH_LOCK:
            history_endpoint._MODULE_REFRESH_JOBS["job-a"] = {
                "job_id": "job-a",
                "record_id": 11,
                "module": "news",
                "status": "queued",
                "message": "queued",
                "created_at": "2026-03-01T10:00:00",
                "started_at": None,
                "finished_at": None,
                "module_updated_at": None,
            }
            history_endpoint._MODULE_REFRESH_JOBS["job-b"] = {
                "job_id": "job-b",
                "record_id": 11,
                "module": "summary",
                "status": "succeeded",
                "message": "done",
                "created_at": "2026-03-01T11:00:00",
                "started_at": "2026-03-01T11:00:05",
                "finished_at": "2026-03-01T11:00:10",
                "module_updated_at": "2026-03-01T11:00:10",
            }
            history_endpoint._MODULE_REFRESH_JOBS["job-c"] = {
                "job_id": "job-c",
                "record_id": 22,
                "module": "news",
                "status": "running",
                "message": "running",
                "created_at": "2026-03-01T12:00:00",
                "started_at": "2026-03-01T12:00:03",
                "finished_at": None,
                "module_updated_at": None,
            }

        response = self.client.get("/api/v1/history/11/modules/refresh-jobs?limit=10")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["total"], 2)
        self.assertEqual(payload["items"][0]["job_id"], "job-b")
        self.assertEqual(payload["items"][1]["job_id"], "job-a")


if __name__ == "__main__":
    unittest.main()

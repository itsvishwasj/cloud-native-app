#!/usr/bin/env python3
"""
Automated Unit & Integration Test Suite for Unified Dashboard Server.
Tests API endpoints, research data loading, Gemini AI schema fallback, and error resilience.
"""

import os
import sys
import unittest
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from server import app


class TestDashboardAPI(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    def test_1_health_endpoint(self):
        res = self.app.get("/api/health")
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertIn("kubernetes", data)
        self.assertIn("prometheus", data)
        self.assertIn("prediction_service", data)

    def test_2_overview_endpoint(self):
        res = self.app.get("/api/overview")
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertIn("current_rps", data)
        self.assertIn("current_replicas", data)
        self.assertIn("p95_latency_sec", data)

    def test_3_cicd_endpoint(self):
        res = self.app.get("/api/cicd")
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertEqual(data["status"], "SUCCESS")
        self.assertGreater(len(data["stages"]), 3)

    def test_4_kubernetes_endpoint(self):
        res = self.app.get("/api/kubernetes")
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertIn("current_replicas", data)
        self.assertIn("pods", data)

    def test_5_research_endpoint(self):
        res = self.app.get("/api/research")
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertIn("summary", data)
        self.assertIn("workload_comparison", data)

    def test_6_statistics_endpoint(self):
        res = self.app.get("/api/statistics")
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertEqual(len(data["hypotheses"]), 4)

    def test_7_ai_diagnostics_fallback(self):
        res = self.app.post("/api/ai-diagnostics", json={"error_message": "Test pod failure"})
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertIn("severity", data)
        self.assertIn("error_type", data)
        self.assertIn("suggested_fix", data)
        self.assertTrue(data["requires_human_approval"])

    def test_8_demo_orchestrator(self):
        res_start = self.app.post("/api/demo/start")
        self.assertEqual(res_start.status_code, 200)
        res_status = self.app.get("/api/demo/status")
        self.assertEqual(json.loads(res_status.data)["status"], "RUNNING")
        res_reset = self.app.post("/api/demo/reset")
        self.assertEqual(res_reset.status_code, 200)


if __name__ == "__main__":
    unittest.main()

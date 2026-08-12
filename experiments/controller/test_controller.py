#!/usr/bin/env python3
"""
Automated Unit Test Suite for Predictive Scaling Controller.
Tests replica calculation, safety factors, min/max bounds, scale-up cooldown,
scale-down stabilization, invalid predictions, and failure fallbacks.
"""

import sys
import os
import unittest
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "model"))

from predictive_scaler import ReplicaCalculator, ScalingDecisionEngine, PrometheusAdapter
from predict_service import WorkloadPredictor


class TestPredictiveController(unittest.TestCase):

    def setUp(self):
        self.calculator = ReplicaCalculator(safe_rps_per_pod=1.5, safety_factor=1.15, min_replicas=2, max_replicas=10)
        self.engine = ScalingDecisionEngine(cooldown_sec=30, stabilization_sec=180)
        self.predictor = WorkloadPredictor()

    def test_1_replica_calculation_basic(self):
        # 3.0 RPS / 1.5 * 1.15 = 2.3 -> ceil = 3 replicas
        req = self.calculator.calculate(3.0)
        self.assertEqual(req, 3)

    def test_2_safety_factor(self):
        # 6.0 RPS / 1.5 * 1.15 = 4.6 -> ceil = 5 replicas
        req = self.calculator.calculate(6.0)
        self.assertEqual(req, 5)

    def test_3_min_replica_bound(self):
        # 0.5 RPS -> ceil(0.38) = 1 -> clamped to min_replicas = 2
        req = self.calculator.calculate(0.5)
        self.assertEqual(req, 2)

    def test_4_max_replica_bound(self):
        # 25.0 RPS -> ceil(19.16) = 20 -> clamped to max_replicas = 10
        req = self.calculator.calculate(25.0)
        self.assertEqual(req, 10)

    def test_5_scale_up_decision(self):
        final_desired, action, reason = self.engine.evaluate(current_replicas=2, calculated_replicas=5, now_time=100.0)
        self.assertEqual(action, "scale_up")
        self.assertEqual(final_desired, 5)

    def test_6_cooldown_guard(self):
        # Initial scale up
        self.engine.evaluate(current_replicas=2, calculated_replicas=5, now_time=100.0)
        # Immediate subsequent scale up attempt (10s later < 30s cooldown)
        final_desired, action, reason = self.engine.evaluate(current_replicas=5, calculated_replicas=8, now_time=110.0)
        self.assertEqual(action, "cooldown_active")
        self.assertEqual(final_desired, 5)

    def test_7_scale_down_stabilization_timer(self):
        # Scale down request at t=200
        final_desired, action, reason = self.engine.evaluate(current_replicas=10, calculated_replicas=2, now_time=200.0)
        self.assertEqual(action, "stabilization_pending")
        self.assertEqual(final_desired, 10)

        # 100s later (t=300 < 180s stabilization)
        final_desired, action, reason = self.engine.evaluate(current_replicas=10, calculated_replicas=2, now_time=300.0)
        self.assertEqual(action, "stabilization_active")
        self.assertEqual(final_desired, 10)

        # 200s later (t=400 >= 180s stabilization)
        final_desired, action, reason = self.engine.evaluate(current_replicas=10, calculated_replicas=2, now_time=400.0)
        self.assertEqual(action, "scale_down")
        self.assertEqual(final_desired, 2)

    def test_8_invalid_prediction_fallback(self):
        # Negative prediction
        req = self.calculator.calculate(-5.0)
        self.assertEqual(req, 2)

        # None prediction
        req = self.calculator.calculate(None)
        self.assertEqual(req, 2)

    def test_9_predictor_input_validation(self):
        # Empty telemetry window
        res = self.predictor.predict(pd.DataFrame())
        self.assertEqual(res["predicted_rps_30s"], 0.0)

    def test_10_prometheus_failure_handling(self):
        adapter = PrometheusAdapter(prom_url="http://invalid-host-9999")
        val = adapter.query_instant("up")
        self.assertIsNone(val)


if __name__ == "__main__":
    unittest.main()

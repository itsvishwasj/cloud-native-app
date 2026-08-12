#!/usr/bin/env python3
"""
Real-Time Inference Interface for Workload Prediction Service.
Callable by proposed predictive autoscaling controller in Phase 6.
Uses trend_predictor_config.json parameters for EMA-TAP forecasting.
"""

import os
import sys
import json
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "artifacts", "trend_predictor_config.json")


class WorkloadPredictor:
    """Predictor service encapsulating EMA-TAP workload forecasting logic."""

    def __init__(self, config_file=CONFIG_PATH):
        if os.path.exists(config_file):
            with open(config_file, "r", encoding="utf-8") as f:
                self.config = json.load(f)
        else:
            self.config = {
                "alpha_smoothing": 0.50,
                "momentum_lag_samples": 3,
                "beta_weights": {"15s": 0.50, "30s": 0.25, "60s": 0.00}
            }

        self.alpha = self.config.get("alpha_smoothing", 0.50)
        self.beta = self.config.get("beta_weights", {"15s": 0.50, "30s": 0.25, "60s": 0.00})

    def predict(self, recent_samples_df):
        """
        Accepts recent telemetry DataFrame (minimum 4 samples recommended).
        Returns predicted RPS dictionary for 15s, 30s, and 60s horizons.
        """
        if recent_samples_df.empty:
            return {"predicted_rps_15s": 0.0, "predicted_rps_30s": 0.0, "predicted_rps_60s": 0.0}

        rps_series = recent_samples_df["request_rate_rps"].values

        if len(rps_series) < 4:
            current_rps = float(rps_series[-1])
            return {
                "predicted_rps_15s": round(current_rps, 2),
                "predicted_rps_30s": round(current_rps, 2),
                "predicted_rps_60s": round(current_rps, 2),
            }

        # Calculate EMA over recent window
        ema = np.zeros_like(rps_series)
        ema[0] = rps_series[0]
        for t in range(1, len(rps_series)):
            ema[t] = self.alpha * rps_series[t] + (1 - self.alpha) * ema[t - 1]

        current_rps = float(rps_series[-1])
        ema_now = float(ema[-1])
        ema_lag3 = float(ema[-4]) if len(ema) >= 4 else float(ema[0])
        delta_rps = ema_now - ema_lag3

        pred_15s = max(0.0, current_rps + self.beta.get("15s", 0.50) * delta_rps)
        pred_30s = max(0.0, current_rps + self.beta.get("30s", 0.25) * delta_rps)
        pred_60s = max(0.0, current_rps + self.beta.get("60s", 0.00) * delta_rps)

        return {
            "predicted_rps_15s": round(float(pred_15s), 2),
            "predicted_rps_30s": round(float(pred_30s), 2),
            "predicted_rps_60s": round(float(pred_60s), 2),
        }


def main():
    sample_telemetry = pd.DataFrame([
        {"request_rate_rps": 2.0},
        {"request_rate_rps": 4.0},
        {"request_rate_rps": 8.0},
        {"request_rate_rps": 12.0},
    ])

    predictor = WorkloadPredictor()
    predictions = predictor.predict(sample_telemetry)

    print("=" * 60)
    print("REAL-TIME INFERENCE SERVICE TEST (EMA-TAP)")
    print("=" * 60)
    print(f"Input Current RPS: {sample_telemetry['request_rate_rps'].iloc[-1]} RPS")
    print(f"Predictions: {json.dumps(predictions, indent=2)}")
    print("=" * 60)


if __name__ == "__main__":
    main()

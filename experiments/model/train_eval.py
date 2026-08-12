#!/usr/bin/env python3
"""
Comprehensive Model Benchmark and Evaluation Pipeline.
Evaluates Persistence, Moving Average, Trend Extrapolation, EMA-TAP (Final Selected),
Ridge, Random Forest, and XGBoost across 15s, 30s, and 60s forecasting horizons
on the unseen test set (baseline_recovery_001).
Saves benchmark results CSV and model configuration artifact.
"""

import os
import sys
import json
import time
import joblib
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sklearn.linear_model import Ridge
from sklearn.ensemble import RandomForestRegressor
from xgboost import XGBRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from preprocess import load_processed_datasets, FEATURE_COLS, TARGET_COLS

DATASETS_DIR = "experiments/datasets"
ARTIFACTS_DIR = "experiments/model/artifacts"


def calculate_mape(y_true, y_pred):
    epsilon = 0.1
    return float(np.mean(np.abs((y_true - y_pred) / (np.abs(y_true) + epsilon))) * 100.0)


def evaluate_predictions(y_true, y_pred, infer_time_ms):
    mae = float(mean_absolute_error(y_true, y_pred))
    rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
    mape = calculate_mape(y_true, y_pred)
    r2 = float(r2_score(y_true, y_pred))
    return {
        "MAE": round(mae, 4),
        "RMSE": round(rmse, 4),
        "MAPE": round(mape, 2),
        "R2": round(r2, 4),
        "Inference_MS": round(infer_time_ms, 4),
    }


def compute_ema_tap(df, beta):
    """Computes Stage 1 (EMA) and Stage 2 (Trend) for EMA-TAP predictor."""
    alpha = 0.5
    rps_series = df["rps_current"].values
    ema = np.zeros_like(rps_series)
    ema[0] = rps_series[0]
    for t in range(1, len(rps_series)):
        ema[t] = alpha * rps_series[t] + (1 - alpha) * ema[t - 1]

    # Delta RPS over 3 samples (~15s)
    delta_rps = np.zeros_like(ema)
    for t in range(len(ema)):
        if t >= 3:
            delta_rps[t] = ema[t] - ema[t - 3]
        else:
            delta_rps[t] = 0.0

    y_pred = np.maximum(0.0, rps_series + beta * delta_rps)
    return y_pred


def main():
    os.makedirs(ARTIFACTS_DIR, exist_ok=True)
    train_df, val_df, test_df = load_processed_datasets()
    train_val_df = pd.concat([train_df, val_df], ignore_index=True)

    X_train = train_val_df[FEATURE_COLS]
    X_test = test_df[FEATURE_COLS]

    results = []

    print("=" * 95)
    print("COMPREHENSIVE WORKLOAD PREDICTION BENCHMARK ON UNSEEN TEST SET (baseline_recovery_001)")
    print("=" * 95)

    for target_col in TARGET_COLS:
        horizon_name = target_col.replace("target_", "")
        y_train = train_val_df[target_col]
        y_test = test_df[target_col]

        beta_map = {"15s": 0.50, "30s": 0.25, "60s": 0.00}
        beta = beta_map[horizon_name]

        # 1. Persistence (Baseline 1)
        t0 = time.time()
        y_pred_pers = X_test["rps_current"].values
        t_pers = ((time.time() - t0) / len(X_test)) * 1000.0
        res_pers = evaluate_predictions(y_test, y_pred_pers, t_pers)
        res_pers.update({"Model": "Persistence (Baseline 1)", "Horizon": horizon_name})
        results.append(res_pers)

        # 2. Moving Average (Baseline 2)
        t0 = time.time()
        y_pred_ma = X_test["rps_roll_mean_6"].values
        t_ma = ((time.time() - t0) / len(X_test)) * 1000.0
        res_ma = evaluate_predictions(y_test, y_pred_ma, t_ma)
        res_ma.update({"Model": "Moving Average (Baseline 2)", "Horizon": horizon_name})
        results.append(res_ma)

        # 3. Trend Extrapolation (Baseline 3)
        t0 = time.time()
        y_pred_trend = np.maximum(0.0, (X_test["rps_current"] + beta * X_test["rps_slope_3"]).values)
        t_trend = ((time.time() - t0) / len(X_test)) * 1000.0
        res_trend = evaluate_predictions(y_test, y_pred_trend, t_trend)
        res_trend.update({"Model": "Trend Extrapolation (Baseline 3)", "Horizon": horizon_name})
        results.append(res_trend)

        # 4. EMA-TAP (Final Selected Predictor)
        t0 = time.time()
        y_pred_ematap = compute_ema_tap(test_df, beta)
        t_ematap = ((time.time() - t0) / len(X_test)) * 1000.0
        res_ematap = evaluate_predictions(y_test, y_pred_ematap, t_ematap)
        res_ematap.update({"Model": "EMA-TAP (Final Selected)", "Horizon": horizon_name})
        results.append(res_ematap)

        # 5. Ridge Regression
        ridge = Ridge(alpha=10.0)
        ridge.fit(X_train, y_train)
        t0 = time.time()
        y_pred_ridge = ridge.predict(X_test)
        t_ridge = ((time.time() - t0) / len(X_test)) * 1000.0
        res_ridge = evaluate_predictions(y_test, y_pred_ridge, t_ridge)
        res_ridge.update({"Model": "Ridge Regression", "Horizon": horizon_name})
        results.append(res_ridge)

        # 6. Random Forest Regressor
        rf = RandomForestRegressor(n_estimators=30, max_depth=4, random_state=42)
        rf.fit(X_train, y_train)
        t0 = time.time()
        y_pred_rf = rf.predict(X_test)
        t_rf = ((time.time() - t0) / len(X_test)) * 1000.0
        res_rf = evaluate_predictions(y_test, y_pred_rf, t_rf)
        res_rf.update({"Model": "Random Forest", "Horizon": horizon_name})
        results.append(res_rf)

        # 7. XGBoost Regressor
        xgb = XGBRegressor(n_estimators=30, max_depth=3, learning_rate=0.03, random_state=42)
        xgb.fit(X_train, y_train)
        t0 = time.time()
        y_pred_xgb = xgb.predict(X_test)
        t_xgb = ((time.time() - t0) / len(X_test)) * 1000.0
        res_xgb = evaluate_predictions(y_test, y_pred_xgb, t_xgb)
        res_xgb.update({"Model": "XGBoost", "Horizon": horizon_name})
        results.append(res_xgb)

    # Save exact configuration artifact for selected model
    config_artifact = {
        "model_name": "EMA-TAP (Trend-Adjusted Exponential Moving Average Predictor)",
        "version": "1.0.0",
        "alpha_smoothing": 0.50,
        "momentum_lag_samples": 3,
        "beta_weights": {
            "15s": 0.50,
            "30s": 0.25,
            "60s": 0.00
        },
        "sampling_interval_seconds": 5.45,
        "features_required": ["rps_current", "rps_lag3"],
        "is_deterministic": True
    }
    with open(os.path.join(ARTIFACTS_DIR, "trend_predictor_config.json"), "w", encoding="utf-8") as f:
        json.dump(config_artifact, f, indent=2)

    results_df = pd.DataFrame(results)[["Model", "Horizon", "MAE", "RMSE", "MAPE", "R2", "Inference_MS"]]
    print("\n" + "=" * 95)
    print(results_df.to_string(index=False))
    print("=" * 95)

    results_df.to_csv("experiments/model/model_benchmark_results.csv", index=False)
    print(f"[✓] Complete Benchmark Results Saved to experiments/model/model_benchmark_results.csv")
    print(f"[✓] Selected Predictor Config Saved to experiments/model/artifacts/trend_predictor_config.json")


if __name__ == "__main__":
    main()

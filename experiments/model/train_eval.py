#!/usr/bin/env python3
"""
Comprehensive Model Benchmark and Evaluation Pipeline.

Evaluates:
    1. Persistence
    2. Moving Average
    3. Trend Extrapolation
    4. EMA-TAP (Final Selected)
    5. Ridge Regression
    6. Random Forest
    7. XGBoost

across 15s, 30s, and 60s forecasting horizons
on the unseen test set (baseline_recovery_001).

The final deployed EMA-TAP configuration is:
    alpha = 0.90
    beta15 = 0.50
    beta30 = 0.10
    beta60 = 0.00

Saves:
    - Benchmark results CSV
    - EMA-TAP model configuration artifact
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


# ============================================================
# FINAL EMA-TAP CONFIGURATION
# ============================================================

FINAL_ALPHA = 0.90

FINAL_BETA_MAP = {
    "15s": 0.50,
    "30s": 0.10,
    "60s": 0.00,
}

EMA_LAG_SAMPLES = 3
SAMPLING_INTERVAL_SECONDS = 5.45


# ============================================================
# METRICS
# ============================================================

def calculate_mape(y_true, y_pred):
    """
    Calculate MAPE using epsilon to avoid division by zero.
    """
    epsilon = 0.1

    return float(
        np.mean(
            np.abs(
                (y_true - y_pred)
                / (np.abs(y_true) + epsilon)
            )
        )
        * 100.0
    )


def evaluate_predictions(y_true, y_pred, infer_time_ms):
    """
    Calculate regression evaluation metrics.
    """

    mae = float(
        mean_absolute_error(y_true, y_pred)
    )

    rmse = float(
        np.sqrt(
            mean_squared_error(y_true, y_pred)
        )
    )

    mape = calculate_mape(
        y_true,
        y_pred
    )

    r2 = float(
        r2_score(y_true, y_pred)
    )

    return {
        "MAE": round(mae, 4),
        "RMSE": round(rmse, 4),
        "MAPE": round(mape, 2),
        "R2": round(r2, 4),
        "Inference_MS": round(infer_time_ms, 4),
    }


# ============================================================
# EMA-TAP
# ============================================================

def compute_ema_tap(df, beta):
    """
    Computes the EMA-TAP prediction.

    Stage 1:
        EMA_t = alpha * RPS_t
                + (1-alpha) * EMA_(t-1)

    Stage 2:
        Delta_t = EMA_t - EMA_(t-3)

    Final prediction:
        Y_hat = max(0, RPS_t + beta * Delta_t)

    Final deployed alpha:
        0.90
    """

    alpha = FINAL_ALPHA

    rps_series = df["rps_current"].values

    ema = np.zeros_like(rps_series)

    # Initialize EMA
    ema[0] = rps_series[0]

    # Calculate EMA
    for t in range(1, len(rps_series)):
        ema[t] = (
            alpha * rps_series[t]
            + (1 - alpha) * ema[t - 1]
        )

    # --------------------------------------------------------
    # Momentum / trend over 3 samples
    # --------------------------------------------------------

    delta_rps = np.zeros_like(ema)

    for t in range(len(ema)):

        if t >= EMA_LAG_SAMPLES:
            delta_rps[t] = (
                ema[t]
                - ema[t - EMA_LAG_SAMPLES]
            )

        else:
            delta_rps[t] = 0.0

    # --------------------------------------------------------
    # Trend-adjusted prediction
    # --------------------------------------------------------

    y_pred = np.maximum(
        0.0,
        rps_series + beta * delta_rps
    )

    return y_pred


# ============================================================
# MAIN
# ============================================================

def main():

    os.makedirs(
        ARTIFACTS_DIR,
        exist_ok=True
    )

    # --------------------------------------------------------
    # Load datasets
    # --------------------------------------------------------

    train_df, val_df, test_df = load_processed_datasets()

    train_val_df = pd.concat(
        [train_df, val_df],
        ignore_index=True
    )

    X_train = train_val_df[FEATURE_COLS]
    X_test = test_df[FEATURE_COLS]

    results = []

    # --------------------------------------------------------
    # Header
    # --------------------------------------------------------

    print("=" * 95)
    print(
        "COMPREHENSIVE WORKLOAD PREDICTION "
        "BENCHMARK ON UNSEEN TEST SET "
        "(baseline_recovery_001)"
    )
    print("=" * 95)

    print("\nFinal EMA-TAP configuration:")
    print(f"  Alpha        : {FINAL_ALPHA}")
    print(f"  Lag          : {EMA_LAG_SAMPLES} samples")
    print(f"  Beta 15s     : {FINAL_BETA_MAP['15s']}")
    print(f"  Beta 30s     : {FINAL_BETA_MAP['30s']}")
    print(f"  Beta 60s     : {FINAL_BETA_MAP['60s']}")
    print(
        f"  Sampling     : "
        f"{SAMPLING_INTERVAL_SECONDS} seconds"
    )

    print("\nRunning benchmark...\n")

    # ========================================================
    # HORIZON LOOP
    # ========================================================

    for target_col in TARGET_COLS:

        horizon_name = target_col.replace(
            "target_",
            ""
        )

        y_train = train_val_df[target_col]
        y_test = test_df[target_col]

        beta = FINAL_BETA_MAP[horizon_name]

        print(
            f"--- Horizon: {horizon_name} "
            f"(beta={beta}) ---"
        )

        # ====================================================
        # 1. Persistence
        # ====================================================

        t0 = time.time()

        y_pred_pers = (
            X_test["rps_current"].values
        )

        t_pers = (
            (time.time() - t0)
            / len(X_test)
        ) * 1000.0

        res_pers = evaluate_predictions(
            y_test,
            y_pred_pers,
            t_pers
        )

        res_pers.update({
            "Model": "Persistence (Baseline 1)",
            "Horizon": horizon_name
        })

        results.append(res_pers)

        # ====================================================
        # 2. Moving Average
        # ====================================================

        t0 = time.time()

        y_pred_ma = (
            X_test["rps_roll_mean_6"].values
        )

        t_ma = (
            (time.time() - t0)
            / len(X_test)
        ) * 1000.0

        res_ma = evaluate_predictions(
            y_test,
            y_pred_ma,
            t_ma
        )

        res_ma.update({
            "Model": "Moving Average (Baseline 2)",
            "Horizon": horizon_name
        })

        results.append(res_ma)

        # ====================================================
        # 3. Trend Extrapolation
        # ====================================================

        t0 = time.time()

        y_pred_trend = np.maximum(
            0.0,
            (
                X_test["rps_current"]
                + beta * X_test["rps_slope_3"]
            ).values
        )

        t_trend = (
            (time.time() - t0)
            / len(X_test)
        ) * 1000.0

        res_trend = evaluate_predictions(
            y_test,
            y_pred_trend,
            t_trend
        )

        res_trend.update({
            "Model": "Trend Extrapolation (Baseline 3)",
            "Horizon": horizon_name
        })

        results.append(res_trend)

        # ====================================================
        # 4. EMA-TAP
        # ====================================================

        t0 = time.time()

        y_pred_ematap = compute_ema_tap(
            test_df,
            beta
        )

        t_ematap = (
            (time.time() - t0)
            / len(X_test)
        ) * 1000.0

        res_ematap = evaluate_predictions(
            y_test,
            y_pred_ematap,
            t_ematap
        )

        res_ematap.update({
            "Model": "EMA-TAP (Final Selected)",
            "Horizon": horizon_name
        })

        results.append(res_ematap)

        # ====================================================
        # 5. Ridge Regression
        # ====================================================

        ridge = Ridge(
            alpha=10.0
        )

        ridge.fit(
            X_train,
            y_train
        )

        t0 = time.time()

        y_pred_ridge = ridge.predict(
            X_test
        )

        t_ridge = (
            (time.time() - t0)
            / len(X_test)
        ) * 1000.0

        res_ridge = evaluate_predictions(
            y_test,
            y_pred_ridge,
            t_ridge
        )

        res_ridge.update({
            "Model": "Ridge Regression",
            "Horizon": horizon_name
        })

        results.append(res_ridge)

        # ====================================================
        # 6. Random Forest
        # ====================================================

        rf = RandomForestRegressor(
            n_estimators=30,
            max_depth=4,
            random_state=42
        )

        rf.fit(
            X_train,
            y_train
        )

        t0 = time.time()

        y_pred_rf = rf.predict(
            X_test
        )

        t_rf = (
            (time.time() - t0)
            / len(X_test)
        ) * 1000.0

        res_rf = evaluate_predictions(
            y_test,
            y_pred_rf,
            t_rf
        )

        res_rf.update({
            "Model": "Random Forest",
            "Horizon": horizon_name
        })

        results.append(res_rf)

        # ====================================================
        # 7. XGBoost
        # ====================================================

        xgb = XGBRegressor(
            n_estimators=30,
            max_depth=3,
            learning_rate=0.03,
            random_state=42
        )

        xgb.fit(
            X_train,
            y_train
        )

        t0 = time.time()

        y_pred_xgb = xgb.predict(
            X_test
        )

        t_xgb = (
            (time.time() - t0)
            / len(X_test)
        ) * 1000.0

        res_xgb = evaluate_predictions(
            y_test,
            y_pred_xgb,
            t_xgb
        )

        res_xgb.update({
            "Model": "XGBoost",
            "Horizon": horizon_name
        })

        results.append(res_xgb)

    # ========================================================
    # SAVE FINAL MODEL CONFIGURATION
    # ========================================================

    config_artifact = {
        "model_name":
            "EMA-TAP "
            "(Trend-Adjusted Exponential Moving Average Predictor)",

        "version":
            "1.1.0",

        "alpha_smoothing":
            FINAL_ALPHA,

        "momentum_lag_samples":
            EMA_LAG_SAMPLES,

        "beta_weights": {
            "15s": FINAL_BETA_MAP["15s"],
            "30s": FINAL_BETA_MAP["30s"],
            "60s": FINAL_BETA_MAP["60s"]
        },

        "sampling_interval_seconds":
            SAMPLING_INTERVAL_SECONDS,

        "features_required": [
            "rps_current",
            "rps_lag3"
        ],

        "is_deterministic":
            True
    }

    config_path = os.path.join(
        ARTIFACTS_DIR,
        "trend_predictor_config.json"
    )

    with open(
        config_path,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            config_artifact,
            f,
            indent=2
        )

    # ========================================================
    # RESULTS DATAFRAME
    # ========================================================

    results_df = pd.DataFrame(
        results
    )[
        [
            "Model",
            "Horizon",
            "MAE",
            "RMSE",
            "MAPE",
            "R2",
            "Inference_MS"
        ]
    ]

    # ========================================================
    # PRINT RESULTS
    # ========================================================

    print("\n" + "=" * 95)
    print(
        "FINAL BENCHMARK RESULTS"
    )
    print("=" * 95)

    print(
        results_df.to_string(
            index=False
        )
    )

    print("=" * 95)

    # ========================================================
    # SAVE RESULTS
    # ========================================================

    results_path = (
        "experiments/model/"
        "model_benchmark_results.csv"
    )

    results_df.to_csv(
        results_path,
        index=False
    )

    print(
        f"[✓] Complete Benchmark Results "
        f"Saved to {results_path}"
    )

    print(
        f"[✓] Selected Predictor Config "
        f"Saved to {config_path}"
    )

    print("\nFinal EMA-TAP configuration saved:")
    print(
        json.dumps(
            config_artifact,
            indent=2
        )
    )


if __name__ == "__main__":
    main()

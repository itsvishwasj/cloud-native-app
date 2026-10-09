#!/usr/bin/env python3
"""
EMA-TAP Parameter Selection Experiment.

Searches alpha and beta parameters on the validation workload only.
The final unseen recovery workload is NOT used during tuning.

Selection metrics:
- MAE
- RMSE

The selected parameters are saved for the final benchmark.
"""

import os
import json
import itertools
import numpy as np
import pandas as pd

from sklearn.metrics import mean_absolute_error, mean_squared_error

from preprocess import load_processed_datasets


ARTIFACTS_DIR = "experiments/model/artifacts"
RESULTS_FILE = "experiments/model/parameter_tuning_results.csv"
CONFIG_FILE = os.path.join(
    ARTIFACTS_DIR,
    "tuned_trend_predictor_config.json"
)


# ---------------------------------------------------------
# EMA-TAP prediction
# ---------------------------------------------------------

def compute_ema_tap(rps_values, alpha, beta):
    """
    EMA-TAP predictor.

    Stage 1:
        EMA_t = alpha * RPS_t + (1-alpha) * EMA_(t-1)

    Stage 2:
        Delta_t = EMA_t - EMA_(t-3)

    Stage 3:
        Prediction = max(0, RPS_t + beta * Delta_t)
    """

    rps = np.asarray(rps_values, dtype=float)

    ema = np.zeros_like(rps)

    if len(rps) == 0:
        return ema

    ema[0] = rps[0]

    for t in range(1, len(rps)):
        ema[t] = (
            alpha * rps[t]
            + (1.0 - alpha) * ema[t - 1]
        )

    delta = np.zeros_like(ema)

    for t in range(len(ema)):
        if t >= 3:
            delta[t] = ema[t] - ema[t - 3]

    prediction = np.maximum(
        0.0,
        rps + beta * delta
    )

    return prediction


# ---------------------------------------------------------
# Metrics
# ---------------------------------------------------------

def calculate_metrics(y_true, y_pred):

    mae = mean_absolute_error(
        y_true,
        y_pred
    )

    rmse = np.sqrt(
        mean_squared_error(
            y_true,
            y_pred
        )
    )

    return {
        "MAE": float(mae),
        "RMSE": float(rmse)
    }


# ---------------------------------------------------------
# Main tuning experiment
# ---------------------------------------------------------

def main():

    os.makedirs(
        ARTIFACTS_DIR,
        exist_ok=True
    )

    print("=" * 95)
    print("EMA-TAP PARAMETER SEARCH ON VALIDATION WORKLOAD")
    print("=" * 95)

    # -----------------------------------------------------
    # Load existing project split
    # -----------------------------------------------------

    train_df, val_df, test_df = load_processed_datasets()

    print()
    print("Dataset split:")
    print(f"  Training samples   : {len(train_df)}")
    print(f"  Validation samples : {len(val_df)}")
    print(f"  Test samples       : {len(test_df)}")

    print()
    print("Validation workload:")
    print("  baseline_sustained_001")

    # -----------------------------------------------------
    # Parameter search space
    # -----------------------------------------------------

    alpha_values = [
        0.1,
        0.2,
        0.3,
        0.4,
        0.5,
        0.6,
        0.7,
        0.8,
        0.9
    ]

    beta_values = [
        0.0,
        0.1,
        0.2,
        0.3,
        0.4,
        0.5,
        0.6,
        0.7,
        0.8,
        0.9,
        1.0
    ]

    horizons = {
        "15s": "target_15s",
        "30s": "target_30s",
        "60s": "target_60s"
    }

    results = []

    # -----------------------------------------------------
    # Search parameters independently for each horizon
    # -----------------------------------------------------

    for horizon, target_col in horizons.items():

        print()
        print("-" * 95)
        print(f"Tuning horizon: {horizon}")
        print("-" * 95)

        y_true = val_df[target_col].values
        rps = val_df["rps_current"].values

        horizon_results = []

        for alpha, beta in itertools.product(
            alpha_values,
            beta_values
        ):

            y_pred = compute_ema_tap(
                rps,
                alpha,
                beta
            )

            metrics = calculate_metrics(
                y_true,
                y_pred
            )

            row = {
                "Horizon": horizon,
                "Alpha": alpha,
                "Beta": beta,
                "MAE": metrics["MAE"],
                "RMSE": metrics["RMSE"]
            }

            horizon_results.append(row)
            results.append(row)

        # -------------------------------------------------
        # Select configuration using validation MAE
        # -------------------------------------------------

        horizon_results.sort(
            key=lambda x: (
                x["MAE"],
                x["RMSE"]
            )
        )

        best = horizon_results[0]

        print(
            f"Best parameters for {horizon}: "
            f"alpha={best['Alpha']:.1f}, "
            f"beta={best['Beta']:.1f}"
        )

        print(
            f"Validation MAE  = {best['MAE']:.4f}"
        )

        print(
            f"Validation RMSE = {best['RMSE']:.4f}"
        )

        print()
        print("Top 5 configurations:")

        for rank, result in enumerate(
            horizon_results[:5],
            start=1
        ):

            print(
                f"{rank}. "
                f"alpha={result['Alpha']:.1f}, "
                f"beta={result['Beta']:.1f}, "
                f"MAE={result['MAE']:.4f}, "
                f"RMSE={result['RMSE']:.4f}"
            )

    # -----------------------------------------------------
    # Save complete parameter search
    # -----------------------------------------------------

    results_df = pd.DataFrame(results)

    results_df = results_df.sort_values(
        ["Horizon", "MAE", "RMSE"]
    )

    results_df.to_csv(
        RESULTS_FILE,
        index=False
    )

    # -----------------------------------------------------
    # Extract final parameters
    # -----------------------------------------------------

    selected_parameters = {}

    for horizon in horizons.keys():

        horizon_df = results_df[
            results_df["Horizon"] == horizon
        ].sort_values(
            ["MAE", "RMSE"]
        )

        best = horizon_df.iloc[0]

        selected_parameters[horizon] = {
            "alpha": float(best["Alpha"]),
            "beta": float(best["Beta"]),
            "validation_mae": float(best["MAE"]),
            "validation_rmse": float(best["RMSE"])
        }

    # -----------------------------------------------------
    # Save selected configuration
    # -----------------------------------------------------

    config = {
        "model_name": (
            "EMA-TAP "
            "(Trend-Adjusted Exponential "
            "Moving Average Predictor)"
        ),
        "selection_method": (
            "Grid search on validation workload "
            "using minimum MAE, with RMSE as tie-breaker"
        ),
        "validation_workload": "baseline_sustained_001",
        "test_workload": "baseline_recovery_001",
        "momentum_lag_samples": 3,
        "sampling_interval_seconds": 5.45,
        "selected_parameters": selected_parameters,
        "parameter_search": {
            "alpha_values": alpha_values,
            "beta_values": beta_values
        },
        "test_set_used_during_tuning": False
    }

    with open(
        CONFIG_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            config,
            f,
            indent=2
        )

    # -----------------------------------------------------
    # Final output
    # -----------------------------------------------------

    print()
    print("=" * 95)
    print("FINAL SELECTED PARAMETERS")
    print("=" * 95)

    for horizon, params in selected_parameters.items():

        print(
            f"{horizon}: "
            f"alpha={params['alpha']:.1f}, "
            f"beta={params['beta']:.1f}, "
            f"MAE={params['validation_mae']:.4f}, "
            f"RMSE={params['validation_rmse']:.4f}"
        )

    print()
    print(
        f"[✓] Full search saved to: {RESULTS_FILE}"
    )

    print(
        f"[✓] Selected configuration saved to: {CONFIG_FILE}"
    )

    print()
    print(
        "The unseen recovery test set was NOT used "
        "for parameter selection."
    )


if __name__ == "__main__":
    main()

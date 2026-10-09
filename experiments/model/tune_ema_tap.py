"""
Tune EMA-TAP parameters using ONLY the validation workload.

Training workloads:
    constant, step, spike

Validation workload:
    sustained

Test workload:
    recovery  <-- NEVER used for tuning

Parameters tuned:
    alpha
    lag
    beta for 15s
    beta for 30s
    beta for 60s
"""

import os
import itertools
import numpy as np
import pandas as pd

DATA_DIR = "experiments/model/data"

TRAIN_FILE = os.path.join(DATA_DIR, "train.csv")
VAL_FILE = os.path.join(DATA_DIR, "val.csv")


# ---------------------------------------------------------
# Metrics
# ---------------------------------------------------------

def calculate_metrics(y_true, y_pred):
    y_true = np.asarray(y_true)
    y_pred = np.asarray(y_pred)

    mae = np.mean(np.abs(y_true - y_pred))
    rmse = np.sqrt(np.mean((y_true - y_pred) ** 2))

    # Same epsilon convention used in train_eval.py
    epsilon = 0.1
    mape = np.mean(
        np.abs((y_true - y_pred) / np.maximum(np.abs(y_true), epsilon))
    ) * 100

    ss_res = np.sum((y_true - y_pred) ** 2)
    ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)

    r2 = 1 - ss_res / ss_tot if ss_tot != 0 else 0.0

    return mae, rmse, mape, r2


# ---------------------------------------------------------
# EMA-TAP
# ---------------------------------------------------------

def ema_tap_predict(rps, alpha, lag, beta):
    rps = np.asarray(rps, dtype=float)

    ema = np.zeros(len(rps))
    ema[0] = rps[0]

    for t in range(1, len(rps)):
        ema[t] = (
            alpha * rps[t]
            + (1 - alpha) * ema[t - 1]
        )

    delta = np.zeros(len(rps))

    for t in range(lag, len(rps)):
        delta[t] = ema[t] - ema[t - lag]

    prediction = np.maximum(
        0.0,
        rps + beta * delta
    )

    return prediction


# ---------------------------------------------------------
# Load validation data
# ---------------------------------------------------------

def load_data():
    train_path = TRAIN_FILE
    val_path = VAL_FILE

    if not os.path.exists(train_path):
        raise FileNotFoundError(
            f"Training file not found: {train_path}"
        )

    if not os.path.exists(val_path):
        raise FileNotFoundError(
            f"Validation file not found: {val_path}"
        )

    train = pd.read_csv(train_path)
    val = pd.read_csv(val_path)

    print("=" * 70)
    print("EMA-TAP PARAMETER TUNING")
    print("=" * 70)

    print(f"\nTraining samples   : {len(train)}")
    print(f"Validation samples : {len(val)}")

    return train, val


# ---------------------------------------------------------
# Find RPS column
# ---------------------------------------------------------

def get_rps_column(df):
    candidates = [
        "rps_current",
        "rps",
        "request_rate",
        "http_rps"
    ]

    for column in candidates:
        if column in df.columns:
            return column

    raise ValueError(
        "Could not find RPS column. Available columns:\n"
        + "\n".join(df.columns)
    )


# ---------------------------------------------------------
# Find target columns
# ---------------------------------------------------------

def get_target_column(df, horizon):
    candidates = [
        f"target_{horizon}",
        f"target_rps_{horizon}",
        f"rps_target_{horizon}",
        f"target_{horizon}s"
    ]

    for column in candidates:
        if column in df.columns:
            return column

    raise ValueError(
        f"Could not find target column for {horizon}s.\n"
        f"Available columns:\n{list(df.columns)}"
    )


# ---------------------------------------------------------
# Main tuning procedure
# ---------------------------------------------------------

def main():

    train, val = load_data()

    rps_column = get_rps_column(val)

    print(f"\nRPS column: {rps_column}")

    # Parameter grid
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

    lag_values = [
        2,
        3,
        4,
        5
    ]

    beta_values = [
        0.0,
        0.1,
        0.2,
        0.3,
        0.4,
        0.5,
        0.6,
        0.75,
        1.0
    ]

    horizons = [15, 30, 60]

    results = []

    total = (
        len(alpha_values)
        * len(lag_values)
        * len(beta_values)
        * len(beta_values)
        * len(beta_values)
    )

    print(f"\nTotal parameter combinations: {total:,}")

    print("\nStarting validation tuning...")
    print("Recovery test data is NOT used.\n")

    # -----------------------------------------------------
    # Grid search
    # -----------------------------------------------------

    for alpha in alpha_values:

        for lag in lag_values:

            for beta15 in beta_values:
                for beta30 in beta_values:
                    for beta60 in beta_values:

                        beta_map = {
                            15: beta15,
                            30: beta30,
                            60: beta60
                        }

                        horizon_metrics = {}

                        total_rmse = 0.0
                        total_mae = 0.0

                        valid = True

                        for horizon in horizons:

                            target_column = get_target_column(
                                val,
                                horizon
                            )

                            # Remove rows where target is unavailable
                            mask = (
                                val[rps_column].notna()
                                & val[target_column].notna()
                            )

                            rps = val.loc[
                                mask,
                                rps_column
                            ].values

                            y_true = val.loc[
                                mask,
                                target_column
                            ].values

                            if len(rps) <= lag:
                                valid = False
                                break

                            y_pred = ema_tap_predict(
                                rps,
                                alpha,
                                lag,
                                beta_map[horizon]
                            )

                            # Important:
                            # Prediction at t corresponds to the
                            # target at the same row in the prepared
                            # validation dataframe.
                            mae, rmse, mape, r2 = calculate_metrics(
                                y_true,
                                y_pred
                            )

                            horizon_metrics[horizon] = {
                                "MAE": mae,
                                "RMSE": rmse,
                                "MAPE": mape,
                                "R2": r2
                            }

                            total_mae += mae
                            total_rmse += rmse

                        if not valid:
                            continue

                        # Equal weighting across horizons
                        avg_mae = total_mae / len(horizons)
                        avg_rmse = total_rmse / len(horizons)

                        results.append({
                            "alpha": alpha,
                            "lag": lag,
                            "beta_15": beta15,
                            "beta_30": beta30,
                            "beta_60": beta60,

                            "avg_MAE": avg_mae,
                            "avg_RMSE": avg_rmse,

                            "MAE_15": horizon_metrics[15]["MAE"],
                            "RMSE_15": horizon_metrics[15]["RMSE"],
                            "MAPE_15": horizon_metrics[15]["MAPE"],
                            "R2_15": horizon_metrics[15]["R2"],

                            "MAE_30": horizon_metrics[30]["MAE"],
                            "RMSE_30": horizon_metrics[30]["RMSE"],
                            "MAPE_30": horizon_metrics[30]["MAPE"],
                            "R2_30": horizon_metrics[30]["R2"],

                            "MAE_60": horizon_metrics[60]["MAE"],
                            "RMSE_60": horizon_metrics[60]["RMSE"],
                            "MAPE_60": horizon_metrics[60]["MAPE"],
                            "R2_60": horizon_metrics[60]["R2"],
                        })

    # -----------------------------------------------------
    # Save results
    # -----------------------------------------------------

    results_df = pd.DataFrame(results)

    results_df = results_df.sort_values(
        by=["avg_RMSE", "avg_MAE"]
    )

    output_file = os.path.join(
        DATA_DIR,
        "ema_tap_tuning_results.csv"
    )

    results_df.to_csv(
        output_file,
        index=False
    )

    # -----------------------------------------------------
    # Display best results
    # -----------------------------------------------------

    print("\n" + "=" * 70)
    print("TOP 10 EMA-TAP PARAMETER CONFIGURATIONS")
    print("=" * 70)

    columns = [
        "alpha",
        "lag",
        "beta_15",
        "beta_30",
        "beta_60",
        "avg_MAE",
        "avg_RMSE"
    ]

    print(
        results_df[columns]
        .head(10)
        .to_string(index=False)
    )

    best = results_df.iloc[0]

    print("\n" + "=" * 70)
    print("SELECTED PARAMETERS")
    print("=" * 70)

    print(f"alpha   = {best['alpha']}")
    print(f"lag     = {int(best['lag'])}")
    print(f"beta15  = {best['beta_15']}")
    print(f"beta30  = {best['beta_30']}")
    print(f"beta60  = {best['beta_60']}")

    print("\nValidation metrics:")

    print(
        f"15s -> "
        f"MAE={best['MAE_15']:.4f}, "
        f"RMSE={best['RMSE_15']:.4f}, "
        f"MAPE={best['MAPE_15']:.2f}%, "
        f"R²={best['R2_15']:.4f}"
    )

    print(
        f"30s -> "
        f"MAE={best['MAE_30']:.4f}, "
        f"RMSE={best['RMSE_30']:.4f}, "
        f"MAPE={best['MAPE_30']:.2f}%, "
        f"R²={best['R2_30']:.4f}"
    )

    print(
        f"60s -> "
        f"MAE={best['MAE_60']:.4f}, "
        f"RMSE={best['RMSE_60']:.4f}, "
        f"MAPE={best['MAPE_60']:.2f}%, "
        f"R²={best['R2_60']:.4f}"
    )

    print("\nResults saved to:")
    print(output_file)

    print("\nIMPORTANT:")
    print("The Recovery workload was NOT used for parameter selection.")
    print("The selected parameters must now be locked before final test evaluation.")


if __name__ == "__main__":
    main()

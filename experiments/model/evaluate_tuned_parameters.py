#!/usr/bin/env python3

import numpy as np
import pandas as pd

from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from preprocess import load_processed_datasets


def compute_ema_tap(rps_values, alpha, beta):

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

    r2 = r2_score(
        y_true,
        y_pred
    )

    return mae, rmse, r2


def main():

    _, _, test_df = load_processed_datasets()

    original_parameters = {
        "15s": (0.5, 0.5),
        "30s": (0.5, 0.25),
        "60s": (0.5, 0.0)
    }

    tuned_parameters = {
        "15s": (0.1, 0.0),
        "30s": (0.9, 0.1),
        "60s": (0.5, 0.8)
    }

    targets = {
        "15s": "target_15s",
        "30s": "target_30s",
        "60s": "target_60s"
    }

    results = []

    print("=" * 95)
    print("ORIGINAL vs TUNED EMA-TAP ON UNSEEN RECOVERY TEST")
    print("=" * 95)

    for horizon, target_col in targets.items():

        y_true = test_df[target_col].values
        rps = test_df["rps_current"].values

        # Original
        alpha_original, beta_original = original_parameters[horizon]

        pred_original = compute_ema_tap(
            rps,
            alpha_original,
            beta_original
        )

        mae_o, rmse_o, r2_o = calculate_metrics(
            y_true,
            pred_original
        )

        # Tuned
        alpha_tuned, beta_tuned = tuned_parameters[horizon]

        pred_tuned = compute_ema_tap(
            rps,
            alpha_tuned,
            beta_tuned
        )

        mae_t, rmse_t, r2_t = calculate_metrics(
            y_true,
            pred_tuned
        )

        results.append({
            "Horizon": horizon,
            "Original_Alpha": alpha_original,
            "Original_Beta": beta_original,
            "Original_MAE": mae_o,
            "Original_RMSE": rmse_o,
            "Original_R2": r2_o,
            "Tuned_Alpha": alpha_tuned,
            "Tuned_Beta": beta_tuned,
            "Tuned_MAE": mae_t,
            "Tuned_RMSE": rmse_t,
            "Tuned_R2": r2_t
        })

    results_df = pd.DataFrame(results)

    print()
    print(
        results_df.to_string(
            index=False,
            float_format=lambda x: f"{x:.4f}"
        )
    )

    results_df.to_csv(
        "experiments/model/tuned_vs_original_results.csv",
        index=False
    )

    print()
    print(
        "[✓] Results saved to "
        "experiments/model/tuned_vs_original_results.csv"
    )


if __name__ == "__main__":
    main()

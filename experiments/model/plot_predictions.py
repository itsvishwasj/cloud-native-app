#!/usr/bin/env python3
"""
Prediction Model Visualization Script.
Generates research-quality comparison plots:
- Actual vs Predicted RPS across 15s, 30s, and 60s horizons
- Model Comparison Benchmark charts
Saved in experiments/model/plots/
"""

import os
import sys
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from preprocess import load_processed_datasets, FEATURE_COLS, TARGET_COLS
from train_eval import compute_ema_tap

PLOTS_DIR = "experiments/model/plots"
DATASETS_DIR = "experiments/datasets"


def plot_actual_vs_predicted():
    train_df, val_df, test_df = load_processed_datasets()
    t0 = test_df["timestamp_epoch"].iloc[0]
    time_sec = test_df["timestamp_epoch"] - t0

    horizons = [("15s", "target_15s", 0.50), ("30s", "target_30s", 0.25), ("60s", "target_60s", 0.00)]

    for name, col, beta in horizons:
        fig, ax = plt.subplots(figsize=(10, 5))
        y_true = test_df[col].values
        y_pred_pers = test_df["rps_current"].values
        y_pred_ematap = compute_ema_tap(test_df, beta)

        ax.plot(time_sec, y_true, label="Actual Future RPS", color="#1f77b4", linewidth=2.5)
        ax.plot(time_sec, y_pred_pers, label="Persistence (Baseline 1)", color="#ff7f0e", linestyle="--", linewidth=1.8)
        ax.plot(time_sec, y_pred_ematap, label="EMA-TAP (Final Selected)", color="#2ca02c", linestyle="-.", linewidth=1.8)

        ax.set_title(f"Actual vs Predicted Workload (RPS) — Horizon: {name} (Recovery Scenario)", fontsize=12, fontweight="bold")
        ax.set_xlabel("Elapsed Time (Seconds)")
        ax.set_ylabel("Request Rate (RPS)")
        ax.grid(True, linestyle="--", alpha=0.6)
        ax.legend(loc="upper right")

        plt.tight_layout()
        out_path = os.path.join(PLOTS_DIR, f"actual_vs_predicted_{name}.png")
        plt.savefig(out_path, dpi=200)
        plt.close(fig)
        print(f"[✓] Saved Plot: {out_path}")


def plot_model_comparison():
    res_df = pd.read_csv("experiments/model/model_benchmark_results.csv")
    
    fig, ax = plt.subplots(figsize=(11, 6))
    horizons = ["15s", "30s", "60s"]
    models = res_df["Model"].unique()

    x = np.arange(len(horizons))
    width = 0.11

    for i, model_name in enumerate(models):
        sub = res_df[res_df["Model"] == model_name]
        maes = [sub[sub["Horizon"] == h]["MAE"].values[0] if h in sub["Horizon"].values else 0 for h in horizons]
        ax.bar(x + i * width - (len(models)*width)/2.0, maes, width, label=model_name)

    ax.set_title("Workload Forecasting MAE Benchmark Across Horizons (Unseen Test Set)", fontsize=12, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(horizons)
    ax.set_xlabel("Forecasting Horizon")
    ax.set_ylabel("Mean Absolute Error (MAE in RPS)")
    ax.grid(True, linestyle="--", alpha=0.5)
    ax.legend(loc="upper left", fontsize=9)

    plt.tight_layout()
    out_path = os.path.join(PLOTS_DIR, "model_comparison_benchmark.png")
    plt.savefig(out_path, dpi=200)
    plt.close(fig)
    print(f"[✓] Saved Plot: {out_path}")


def main():
    os.makedirs(PLOTS_DIR, exist_ok=True)
    plot_actual_vs_predicted()
    plot_model_comparison()


if __name__ == "__main__":
    main()

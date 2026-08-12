#!/usr/bin/env python3
"""
Reproducible Preprocessing Pipeline for Workload Prediction Model.
Generates lag, rolling, difference, and multi-horizon target features (15s, 30s, 60s)
without data leakage across experiment boundaries.
"""

import os
import glob
import pandas as pd
import numpy as np

DATASETS_DIR = "experiments/datasets"

FEATURE_COLS = [
    "rps_current",
    "rps_lag1",
    "rps_lag2",
    "rps_lag3",
    "rps_lag6",
    "cpu_lag0",
    "cpu_lag1",
    "rps_roll_mean_3",
    "rps_roll_mean_6",
    "rps_roll_max_6",
    "rps_roll_std_6",
    "rps_slope_3",
    "current_replicas",
]

TARGET_COLS = ["target_15s", "target_30s", "target_60s"]


def create_features_for_df(df):
    """Creates lag, rolling, and multi-horizon target features for a single experiment dataframe."""
    df = df.copy()

    # Base features
    df["rps_current"] = df["request_rate_rps"]
    df["cpu_lag0"] = df["cpu_utilization_percent"]

    # Lags
    df["rps_lag1"] = df["request_rate_rps"].shift(1)
    df["rps_lag2"] = df["request_rate_rps"].shift(2)
    df["rps_lag3"] = df["request_rate_rps"].shift(3)
    df["rps_lag6"] = df["request_rate_rps"].shift(6)
    df["cpu_lag1"] = df["cpu_utilization_percent"].shift(1)

    # Rolling statistics
    df["rps_roll_mean_3"] = df["request_rate_rps"].rolling(window=3).mean()
    df["rps_roll_mean_6"] = df["request_rate_rps"].rolling(window=6).mean()
    df["rps_roll_max_6"] = df["request_rate_rps"].rolling(window=6).max()
    df["rps_roll_std_6"] = df["request_rate_rps"].rolling(window=6).std().fillna(0.0)

    # Slope
    df["rps_slope_3"] = df["request_rate_rps"] - df["request_rate_rps"].shift(3)

    # Multi-horizon Targets (Shift backward in time: target at t+h is rps at row t+h)
    df["target_15s"] = df["request_rate_rps"].shift(-3) # +3 samples (~15s)
    df["target_30s"] = df["request_rate_rps"].shift(-6) # +6 samples (~30s)
    df["target_60s"] = df["request_rate_rps"].shift(-12) # +12 samples (~60s)

    # Drop NaN rows resulting from shifts/lags/targets
    df_clean = df.dropna(subset=FEATURE_COLS + TARGET_COLS).copy()
    return df_clean


def load_processed_datasets():
    """Loads and splits baseline datasets chronologically into Train, Validation, and Test sets."""
    train_experiments = ["baseline_constant_001", "baseline_step_001", "baseline_spike_001"]
    val_experiments = ["baseline_sustained_001"]
    test_experiments = ["baseline_recovery_001"]

    train_dfs = [create_features_for_df(pd.read_csv(f"{DATASETS_DIR}/{eid}.csv")) for eid in train_experiments]
    val_dfs = [create_features_for_df(pd.read_csv(f"{DATASETS_DIR}/{eid}.csv")) for eid in val_experiments]
    test_dfs = [create_features_for_df(pd.read_csv(f"{DATASETS_DIR}/{eid}.csv")) for eid in test_experiments]

    train_data = pd.concat(train_dfs, ignore_index=True)
    val_data = pd.concat(val_dfs, ignore_index=True)
    test_data = pd.concat(test_dfs, ignore_index=True)

    return train_data, val_data, test_data


if __name__ == "__main__":
    train_df, val_df, test_df = load_processed_datasets()
    print("Preprocessing Pipeline Summary:")
    print(f"  Train Set: {len(train_df)} samples (Experiments: Constant, Step, Spike)")
    print(f"  Validation Set: {len(val_df)} samples (Experiment: Sustained)")
    print(f"  Test Set: {len(test_df)} samples (Experiment: Recovery)")
    print(f"  Features ({len(FEATURE_COLS)}): {FEATURE_COLS}")
    print(f"  Targets ({len(TARGET_COLS)}): {TARGET_COLS}")

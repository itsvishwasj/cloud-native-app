#!/usr/bin/env python3
"""
Validated Visualization Script for Controlled HPA Baseline Telemetry Datasets.
Generates 5-panel research plots directly from collected CSV datasets and saves to experiments/analysis/plots/validated/:
1. Request Rate (RPS) vs Time
2. CPU Utilization (%) vs Time
3. Memory Utilization (MiB) vs Time
4. Pod Replicas (Desired, Current, Available) vs Time
5. Latency (P95 & P99) vs Time
"""

import os
import glob
import pandas as pd
import matplotlib.pyplot as plt

DATASETS_DIR = "experiments/datasets"
PLOTS_VALIDATED_DIR = "experiments/analysis/plots/validated"

EXPERIMENT_TITLES = {
    "baseline_constant_001": "Constant Load Baseline Experiment (5 RPS, 2m)",
    "baseline_step_001": "Step Increase Load Baseline Experiment (2 -> 6 -> 12 -> 16 RPS)",
    "baseline_spike_001": "Spike Load Baseline Experiment (2 RPS -> 18 RPS Spike -> 2 RPS)",
    "baseline_sustained_001": "Sustained High Load Baseline Experiment (14 RPS, 5m)",
    "baseline_recovery_001": "Load Decrease Recovery Baseline Experiment (15 -> 8 -> 2 RPS)",
}


def plot_experiment(exp_id):
    csv_path = os.path.join(DATASETS_DIR, f"{exp_id}.csv")
    if not os.path.exists(csv_path):
        return

    df = pd.read_csv(csv_path)
    if df.empty:
        return

    # Relative time in seconds from start
    t0 = df["timestamp_epoch"].iloc[0]
    time_sec = df["timestamp_epoch"] - t0

    fig, axes = plt.subplots(5, 1, figsize=(11, 15), sharex=True)
    fig.suptitle(EXPERIMENT_TITLES.get(exp_id, exp_id), fontsize=13, fontweight="bold")

    # Subplot 1: Request Rate (RPS)
    axes[0].plot(time_sec, df["request_rate_rps"], label="Measured RPS", color="#1f77b4", linewidth=2)
    axes[0].set_ylabel("Request Rate (RPS)")
    axes[0].grid(True, linestyle="--", alpha=0.6)
    axes[0].legend(loc="upper left")

    # Subplot 2: CPU Utilization (%)
    axes[1].plot(time_sec, df["cpu_utilization_percent"], label="CPU Utilization %", color="#d62728", linewidth=2)
    axes[1].axhline(y=50.0, color="#2ca02c", linestyle="--", linewidth=1.5, label="HPA CPU Target (50%)")
    axes[1].set_ylabel("CPU Utilization (%)")
    axes[1].grid(True, linestyle="--", alpha=0.6)
    axes[1].legend(loc="upper left")

    # Subplot 3: Memory Utilization (MiB)
    memory_mib = df["memory_utilization_bytes"] / (1024 * 1024)
    axes[2].plot(time_sec, memory_mib, label="Resident Memory (MiB)", color="#17becf", linewidth=2)
    axes[2].set_ylabel("Memory (MiB)")
    axes[2].grid(True, linestyle="--", alpha=0.6)
    axes[2].legend(loc="upper left")

    # Subplot 4: Replicas (Desired, Current, Available)
    axes[3].step(time_sec, df["hpa_desired_replicas"], where="post", label="HPA Desired Replicas", color="#ff7f0e", linestyle="--", linewidth=2)
    axes[3].step(time_sec, df["current_replicas"], where="post", label="Current Replicas", color="#9467bd", linewidth=2)
    axes[3].step(time_sec, df["available_replicas"], where="post", label="Available Replicas", color="#2ca02c", linewidth=2, alpha=0.8)
    axes[3].set_ylabel("Pod Replicas")
    axes[3].set_yticks(range(0, int(df["current_replicas"].max()) + 3, 2))
    axes[3].grid(True, linestyle="--", alpha=0.6)
    axes[3].legend(loc="upper left")

    # Subplot 5: Latency P95 & P99
    axes[4].plot(time_sec, df["p95_latency_seconds"], label="P95 Latency (s)", color="#8c564b", linewidth=2)
    axes[4].plot(time_sec, df["p99_latency_seconds"], label="P99 Latency (s)", color="#e377c2", linestyle=":", linewidth=2)
    axes[4].axhline(y=1.0, color="#d62728", linestyle="--", linewidth=1, label="SLA Limit (1.0s)")
    axes[4].set_ylabel("Latency (Seconds)")
    axes[4].set_xlabel("Elapsed Time (Seconds)")
    axes[4].grid(True, linestyle="--", alpha=0.6)
    axes[4].legend(loc="upper left")

    plt.tight_layout(rect=[0, 0, 1, 0.97])
    out_path = os.path.join(PLOTS_VALIDATED_DIR, f"{exp_id}.png")
    plt.savefig(out_path, dpi=200)
    plt.close(fig)
    print(f"[✓] Saved Validated Plot: {out_path}")


def main():
    os.makedirs(PLOTS_VALIDATED_DIR, exist_ok=True)
    for exp_id in EXPERIMENT_TITLES.keys():
        plot_experiment(exp_id)


if __name__ == "__main__":
    main()

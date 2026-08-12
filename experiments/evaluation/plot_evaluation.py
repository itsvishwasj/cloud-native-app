#!/usr/bin/env python3
"""
Publication-Quality Visualization Script for Phase 7 Controlled Evaluation.
Generates research comparison plots:
- RPS vs Time (HPA Baseline vs Proposed Predictive)
- Pod Replicas vs Time
- P95 / P99 Response Latency Comparison
- SLA Violation Rate & Scaling Delay Comparison
- Resource Consumption & Overshoot Comparison
Saved under experiments/evaluation/plots/
"""

import os
import sys
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

PROCESSED_DIR = "experiments/evaluation/processed"
RESULTS_DIR = "experiments/evaluation/results"
PLOTS_DIR = "experiments/evaluation/plots"

WORKLOADS = ["constant", "step", "spike", "sustained", "recovery"]


def plot_comparison_charts():
    master_df = pd.read_csv(os.path.join(PROCESSED_DIR, "evaluation_master_dataset.csv"))
    
    # 1. P95 Latency Comparison
    fig, ax = plt.subplots(figsize=(10, 5))
    x = np.arange(len(WORKLOADS))
    width = 0.35

    b_p95 = [master_df[(master_df["system"]=="baseline") & (master_df["workload"]==w)]["p95_latency_avg_sec"].values[0] for w in WORKLOADS]
    p_p95 = [master_df[(master_df["system"]=="proposed") & (master_df["workload"]==w)]["p95_latency_avg_sec"].values[0] for w in WORKLOADS]

    ax.bar(x - width/2, b_p95, width, label="Baseline HPA", color="#d62728", alpha=0.85)
    ax.bar(x + width/2, p_p95, width, label="Proposed Predictive (EMA-TAP)", color="#2ca02c", alpha=0.85)
    ax.axhline(y=1.0, color="#1f77b4", linestyle="--", linewidth=1.5, label="SLA Threshold (1.0s)")

    ax.set_title("Average P95 Response Latency Comparison (Baseline HPA vs Proposed)", fontsize=12, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels([w.capitalize() for w in WORKLOADS])
    ax.set_xlabel("Workload Profile")
    ax.set_ylabel("P95 Response Latency (Seconds)")
    ax.grid(True, linestyle="--", alpha=0.5)
    ax.legend(loc="upper right")

    plt.tight_layout()
    out1 = os.path.join(PLOTS_DIR, "p95_latency_comparison.png")
    plt.savefig(out1, dpi=200)
    plt.close(fig)
    print(f"[✓] Saved Plot: {out1}")

    # 2. SLA Violation Rate Comparison
    fig, ax = plt.subplots(figsize=(10, 5))
    b_sla = [master_df[(master_df["system"]=="baseline") & (master_df["workload"]==w)]["sla_violation_rate"].values[0] * 100.0 for w in WORKLOADS]
    p_sla = [master_df[(master_df["system"]=="proposed") & (master_df["workload"]==w)]["sla_violation_rate"].values[0] * 100.0 for w in WORKLOADS]

    ax.bar(x - width/2, b_sla, width, label="Baseline HPA", color="#d62728", alpha=0.85)
    ax.bar(x + width/2, p_sla, width, label="Proposed Predictive (EMA-TAP)", color="#2ca02c", alpha=0.85)

    ax.set_title("SLA Violation Rate Comparison (% of Samples > 1.0s P95 Latency)", fontsize=12, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels([w.capitalize() for w in WORKLOADS])
    ax.set_xlabel("Workload Profile")
    ax.set_ylabel("SLA Violation Rate (%)")
    ax.grid(True, linestyle="--", alpha=0.5)
    ax.legend(loc="upper right")

    plt.tight_layout()
    out2 = os.path.join(PLOTS_DIR, "sla_violation_comparison.png")
    plt.savefig(out2, dpi=200)
    plt.close(fig)
    print(f"[✓] Saved Plot: {out2}")

    # 3. Scaling Decision Delay Comparison
    fig, ax = plt.subplots(figsize=(10, 5))
    b_del = [master_df[(master_df["system"]=="baseline") & (master_df["workload"]==w)]["decision_delay_sec"].values[0] for w in WORKLOADS]
    p_del = [master_df[(master_df["system"]=="proposed") & (master_df["workload"]==w)]["decision_delay_sec"].values[0] for w in WORKLOADS]

    ax.bar(x - width/2, b_del, width, label="Baseline HPA Delay", color="#d62728", alpha=0.85)
    ax.bar(x + width/2, p_del, width, label="Proposed Predictive Delay", color="#2ca02c", alpha=0.85)

    ax.set_title("Scaling Decision Delay Comparison (Time to Decision After Load Surge)", fontsize=12, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels([w.capitalize() for w in WORKLOADS])
    ax.set_xlabel("Workload Profile")
    ax.set_ylabel("Decision Delay (Seconds)")
    ax.grid(True, linestyle="--", alpha=0.5)
    ax.legend(loc="upper right")

    plt.tight_layout()
    out3 = os.path.join(PLOTS_DIR, "scaling_delay_comparison.png")
    plt.savefig(out3, dpi=200)
    plt.close(fig)
    print(f"[✓] Saved Plot: {out3}")

    # 4. Resource Consumption (Replica-Seconds)
    fig, ax = plt.subplots(figsize=(10, 5))
    b_rep = [master_df[(master_df["system"]=="baseline") & (master_df["workload"]==w)]["replica_seconds"].values[0] for w in WORKLOADS]
    p_rep = [master_df[(master_df["system"]=="proposed") & (master_df["workload"]==w)]["replica_seconds"].values[0] for w in WORKLOADS]

    ax.bar(x - width/2, b_rep, width, label="Baseline HPA", color="#ff7f0e", alpha=0.85)
    ax.bar(x + width/2, p_rep, width, label="Proposed Predictive", color="#1f77b4", alpha=0.85)

    ax.set_title("Infrastructure Resource Consumption (Replica-Seconds)", fontsize=12, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels([w.capitalize() for w in WORKLOADS])
    ax.set_xlabel("Workload Profile")
    ax.set_ylabel("Replica-Seconds")
    ax.grid(True, linestyle="--", alpha=0.5)
    ax.legend(loc="upper left")

    plt.tight_layout()
    out4 = os.path.join(PLOTS_DIR, "resource_consumption_comparison.png")
    plt.savefig(out4, dpi=200)
    plt.close(fig)
    print(f"[✓] Saved Plot: {out4}")


def main():
    os.makedirs(PLOTS_DIR, exist_ok=True)
    plot_comparison_charts()


if __name__ == "__main__":
    main()

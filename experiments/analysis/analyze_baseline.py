#!/usr/bin/env python3
"""
Validated Scientific Analysis Script for Controlled HPA Baseline Telemetry Datasets.
Calculates all 20 formal research metrics for reactive HPA performance:
- RPS, CPU%, Memory (MiB), Replicas, P95/P99 Latency, Error Rate, SLA Violation Rate
- Scaling Delays (Decision Delay T1-T0, Pod Scaling Delay T2-T1, Availability Delay T3-T2, Scale-Up Duration T3-T0)
- CPU Overshoot (%-seconds above 50% target)
- Under-Provisioning Deficit & Over-Provisioning Excess (Replica-seconds)
Outputs: experiments/datasets/baseline_summary_validated.csv & baseline_summary_validated.json
"""

import json
import os
import glob
import pandas as pd
import numpy as np

DATASETS_DIR = "experiments/datasets"
OUTPUT_SUMMARY_CSV = os.path.join(DATASETS_DIR, "baseline_summary_validated.csv")
OUTPUT_SUMMARY_JSON = os.path.join(DATASETS_DIR, "baseline_summary_validated.json")

EXPERIMENT_IDS = [
    "baseline_constant_001",
    "baseline_step_001",
    "baseline_spike_001",
    "baseline_sustained_001",
    "baseline_recovery_001",
]


def analyze_experiment(exp_id):
    csv_path = os.path.join(DATASETS_DIR, f"{exp_id}.csv")
    if not os.path.exists(csv_path):
        print(f"Error: {csv_path} not found.")
        return None

    df = pd.read_csv(csv_path)
    if df.empty:
        return None

    dt = 5.0  # seconds sampling interval

    avg_rps = float(df["request_rate_rps"].mean())
    peak_rps = float(df["request_rate_rps"].max())
    avg_cpu = float(df["cpu_utilization_percent"].mean())
    peak_cpu = float(df["cpu_utilization_percent"].max())
    avg_mem_mb = float(df["memory_utilization_bytes"].mean() / (1024 * 1024))
    peak_mem_mb = float(df["memory_utilization_bytes"].max() / (1024 * 1024))
    peak_active_pods = int(df["current_replicas"].max())
    avg_active_pods = float(df["current_replicas"].mean())
    p95_latency_avg = float(df["p95_latency_seconds"].mean())
    p95_latency_max = float(df["p95_latency_seconds"].max())
    p99_latency_avg = float(df["p99_latency_seconds"].mean())
    p99_latency_max = float(df["p99_latency_seconds"].max())
    avg_error_rate = float(df["error_rate"].mean())

    # SLA Violation Rate (Fraction of samples where P95 latency > 1.0s)
    sla_violations = (df["p95_latency_seconds"] > 1.0).sum()
    sla_violation_rate = float(sla_violations / len(df))

    # CPU Overshoot (%-seconds > 50%)
    cpu_overshoot_vec = np.maximum(0.0, df["cpu_utilization_percent"] - 50.0)
    cpu_overshoot_area = float(np.sum(cpu_overshoot_vec * dt))

    # Under-provisioning (Replica-seconds where hpa_desired > available)
    under_prov_vec = np.maximum(0.0, df["hpa_desired_replicas"] - df["available_replicas"])
    under_provisioning_rep_sec = float(np.sum(under_prov_vec * dt))

    # Over-provisioning (Replica-seconds where available > hpa_desired)
    over_prov_vec = np.maximum(0.0, df["available_replicas"] - df["hpa_desired_replicas"])
    over_provisioning_rep_sec = float(np.sum(over_prov_vec * dt))

    # Calculate Timestamps & Scaling Delays
    # T0: Workload increase begins (RPS > 1.0)
    load_change_df = df[df["request_rate_rps"] > 1.0]
    t0 = load_change_df["timestamp_epoch"].iloc[0] if not load_change_df.empty else None

    # T1: HPA desired replicas changes (hpa_desired_replicas > 2.0)
    hpa_dec_df = df[df["hpa_desired_replicas"] > 2.0]
    t1 = hpa_dec_df["timestamp_epoch"].iloc[0] if not hpa_dec_df.empty else None

    # T2: Pod scaling begins (current_replicas > 2.0)
    act_scale_df = df[df["current_replicas"] > 2.0]
    t2 = act_scale_df["timestamp_epoch"].iloc[0] if not act_scale_df.empty else None

    # T3: All target pods ready and available (available_replicas == hpa_desired_replicas and available_replicas > 2.0)
    avail_df = df[(df["available_replicas"] == df["hpa_desired_replicas"]) & (df["available_replicas"] > 2.0)]
    t3 = avail_df["timestamp_epoch"].iloc[0] if not avail_df.empty else None

    decision_delay = (t1 - t0) if (t1 and t0 and t1 >= t0) else 0.0
    pod_scaling_delay = (t2 - t1) if (t2 and t1 and t2 >= t1) else 0.0
    availability_delay = (t3 - t2) if (t3 and t2 and t3 >= t2) else 0.0
    scale_up_duration = (t3 - t0) if (t3 and t0 and t3 >= t0) else 0.0

    return {
        "experiment_id": exp_id,
        "samples_collected": len(df),
        "avg_rps": round(avg_rps, 2),
        "peak_rps": round(peak_rps, 2),
        "avg_cpu_percent": round(avg_cpu, 1),
        "peak_cpu_percent": round(peak_cpu, 1),
        "avg_memory_mb": round(avg_mem_mb, 1),
        "peak_memory_mb": round(peak_mem_mb, 1),
        "avg_active_pods": round(avg_active_pods, 2),
        "peak_active_pods": peak_active_pods,
        "p95_latency_avg_sec": round(p95_latency_avg, 3),
        "p95_latency_max_sec": round(p95_latency_max, 3),
        "p99_latency_avg_sec": round(p99_latency_avg, 3),
        "p99_latency_max_sec": round(p99_latency_max, 3),
        "avg_error_rate": round(avg_error_rate, 4),
        "sla_violation_rate": round(sla_violation_rate, 3),
        "decision_delay_sec": round(decision_delay, 1),
        "pod_scaling_delay_sec": round(pod_scaling_delay, 1),
        "availability_delay_sec": round(availability_delay, 1),
        "scale_up_duration_sec": round(scale_up_duration, 1),
        "cpu_overshoot_pct_sec": round(cpu_overshoot_area, 1),
        "under_provisioning_rep_sec": round(under_provisioning_rep_sec, 1),
        "over_provisioning_rep_sec": round(over_provisioning_rep_sec, 1),
    }


def main():
    results = []
    print("=" * 80)
    print("VALIDATED REACTIVE KUBERNETES HPA BASELINE RESEARCH ANALYSIS")
    print("=" * 80)

    for exp_id in EXPERIMENT_IDS:
        res = analyze_experiment(exp_id)
        if res:
            results.append(res)
            print(f"\n[Dataset: {exp_id}]")
            print(f"  RPS: Avg {res['avg_rps']} | Peak {res['peak_rps']}")
            print(f"  CPU%: Avg {res['avg_cpu_percent']}% | Peak {res['peak_cpu_percent']}%")
            print(f"  Memory: Avg {res['avg_memory_mb']} MB | Peak {res['peak_memory_mb']} MB")
            print(f"  Replicas: Avg {res['avg_active_pods']} | Peak {res['peak_active_pods']}")
            print(f"  P95 Latency: Avg {res['p95_latency_avg_sec']}s | Max {res['p95_latency_max_sec']}s")
            print(f"  SLA Violation Rate (>1.0s P95): {res['sla_violation_rate'] * 100:.1f}%")
            print(f"  Scaling Delays: Decision {res['decision_delay_sec']}s | Pod Scale {res['pod_scaling_delay_sec']}s | Avail {res['availability_delay_sec']}s | Total Scale-Up {res['scale_up_duration_sec']}s")
            print(f"  CPU Overshoot: {res['cpu_overshoot_pct_sec']} %-sec | Under-Prov: {res['under_provisioning_rep_sec']} rep-sec | Over-Prov: {res['over_provisioning_rep_sec']} rep-sec")

    summary_df = pd.DataFrame(results)
    summary_df.to_csv(OUTPUT_SUMMARY_CSV, index=False)

    with open(OUTPUT_SUMMARY_JSON, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print("\n" + "=" * 80)
    print(f"[✓] Validated Summary Saved to {OUTPUT_SUMMARY_CSV} & {OUTPUT_SUMMARY_JSON}")
    print("=" * 80)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Safety Factor Sensitivity Analysis Script.
Evaluates controller replica decisions across safety factors [1.00, 1.05, 1.10, 1.15, 1.20, 1.25]
in simulation mode across all 5 baseline time-series datasets.
Generates experiments/evaluation/results/safety_factor_sensitivity.csv.
"""

import os
import sys
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "controller"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "model"))

from predictive_scaler import ReplicaCalculator, ScalingDecisionEngine
from predict_service import WorkloadPredictor

DATASETS_DIR = "experiments/datasets"
OUT_CSV = "experiments/evaluation/results/safety_factor_sensitivity.csv"

SAFETY_FACTORS = [1.00, 1.05, 1.10, 1.15, 1.20, 1.25]
EXPERIMENT_IDS = [
    "baseline_constant_001",
    "baseline_step_001",
    "baseline_spike_001",
    "baseline_sustained_001",
    "baseline_recovery_001",
]


def evaluate_safety_factor(sf):
    predictor = WorkloadPredictor()
    calculator = ReplicaCalculator(safe_rps_per_pod=1.5, safety_factor=sf, min_replicas=2, max_replicas=10)

    results = []

    for exp_id in EXPERIMENT_IDS:
        df = pd.read_csv(os.path.join(DATASETS_DIR, f"{exp_id}.csv"))
        engine = ScalingDecisionEngine(cooldown_sec=30, stabilization_sec=180)
        curr_replicas = 2

        sim_calc_rep = []
        sim_final_rep = []

        for i in range(len(df)):
            sub_df = df.iloc[max(0, i - 10):i + 1]
            t_epoch = df["timestamp_epoch"].iloc[i]
            curr_rps = df["request_rate_rps"].iloc[i]

            preds = predictor.predict(sub_df)
            pred_30s = preds.get("predicted_rps_30s", curr_rps)

            calc_rep = calculator.calculate(pred_30s)
            desired_rep, action, reason = engine.evaluate(curr_replicas, calc_rep, t_epoch)

            if action in ["scale_up", "scale_down"]:
                curr_replicas = desired_rep

            sim_calc_rep.append(calc_rep)
            sim_final_rep.append(desired_rep)

        dt = 5.0
        # Over-provisioning relative to minimum required pods (measured_rps / 1.5)
        required_rep_vec = np.ceil(df["request_rate_rps"] / 1.5)
        over_prov = float(np.sum(np.maximum(0, np.array(sim_final_rep) - required_rep_vec) * dt))
        under_prov = float(np.sum(np.maximum(0, required_rep_vec - np.array(sim_final_rep)) * dt))

        results.append({
            "safety_factor": sf,
            "experiment_id": exp_id,
            "avg_replicas": round(float(np.mean(sim_final_rep)), 2),
            "peak_replicas": int(np.max(sim_final_rep)),
            "over_provisioning_rep_sec": round(over_prov, 1),
            "under_provisioning_rep_sec": round(under_prov, 1),
        })

    return results


def main():
    os.makedirs("experiments/evaluation/results", exist_ok=True)
    all_res = []

    print("=" * 80)
    print("SAFETY FACTOR SENSITIVITY ANALYSIS (SIMULATION)")
    print("=" * 80)

    for sf in SAFETY_FACTORS:
        res = evaluate_safety_factor(sf)
        all_res.extend(res)
        avg_rep = np.mean([r["avg_replicas"] for r in res])
        avg_under = np.mean([r["under_provisioning_rep_sec"] for r in res])
        print(f"Safety Factor {sf:.2f} | Avg Replicas: {avg_rep:.2f} | Avg Under-Prov Deficit: {avg_under:.1f} rep-sec")

    res_df = pd.DataFrame(all_res)
    res_df.to_csv(OUT_CSV, index=False)
    print(f"\n[✓] Sensitivity Results Saved to {OUT_CSV}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Controller Trace Replay / Simulation Script.
Replays all 5 baseline time-series datasets through the predictive controller logic
to evaluate proactive replica calculation timelines against baseline HPA timelines.
Generates experiments/controller/simulation_results.csv and simulation_summary.json.
"""

import os
import sys
import json
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "model"))

from predictive_scaler import ReplicaCalculator, ScalingDecisionEngine
from predict_service import WorkloadPredictor

DATASETS_DIR = "experiments/datasets"
OUT_CSV = "experiments/controller/simulation_results.csv"
OUT_JSON = "experiments/controller/simulation_summary.json"

EXPERIMENT_IDS = [
    "baseline_constant_001",
    "baseline_step_001",
    "baseline_spike_001",
    "baseline_sustained_001",
    "baseline_recovery_001",
]


def simulate_experiment(exp_id):
    csv_path = os.path.join(DATASETS_DIR, f"{exp_id}.csv")
    if not os.path.exists(csv_path):
        return None

    df = pd.read_csv(csv_path)
    predictor = WorkloadPredictor()
    calculator = ReplicaCalculator(safe_rps_per_pod=1.5, safety_factor=1.15, min_replicas=2, max_replicas=10)
    engine = ScalingDecisionEngine(cooldown_sec=30, stabilization_sec=180)

    sim_rows = []
    current_replicas = 2  # Start at minReplicas=2

    for i in range(len(df)):
        sub_df = df.iloc[max(0, i - 10):i + 1]
        t_epoch = df["timestamp_epoch"].iloc[i]
        curr_rps = df["request_rate_rps"].iloc[i]
        hpa_des = df["hpa_desired_replicas"].iloc[i]
        hpa_curr = df["current_replicas"].iloc[i]

        preds = predictor.predict(sub_df)
        pred_30s = preds.get("predicted_rps_30s", curr_rps)

        calc_rep = calculator.calculate(pred_30s)
        desired_rep, action, reason = engine.evaluate(current_replicas, calc_rep, t_epoch)

        if action in ["scale_up", "scale_down"]:
            current_replicas = desired_rep

        sim_rows.append({
            "experiment_id": exp_id,
            "sample_index": i,
            "timestamp_epoch": t_epoch,
            "measured_rps": curr_rps,
            "hpa_desired_replicas": hpa_des,
            "hpa_current_replicas": hpa_curr,
            "predicted_rps_30s": pred_30s,
            "predictive_calc_replicas": calc_rep,
            "predictive_desired_replicas": desired_rep,
            "predictive_action": action,
            "predictive_reason": reason,
        })

    return pd.DataFrame(sim_rows)


def main():
    print("=" * 85)
    print("PREDICTIVE SCALING CONTROLLER TRACE REPLAY / SIMULATION")
    print("=" * 85)

    all_sim_dfs = []
    summary_list = []

    for exp_id in EXPERIMENT_IDS:
        sim_df = simulate_experiment(exp_id)
        if sim_df is not None:
            all_sim_dfs.append(sim_df)

            scale_ups = (sim_df["predictive_action"] == "scale_up").sum()
            scale_downs = (sim_df["predictive_action"] == "scale_down").sum()
            max_pred_rep = int(sim_df["predictive_desired_replicas"].max())
            avg_pred_rep = float(sim_df["predictive_desired_replicas"].mean())

            summary_entry = {
                "experiment_id": exp_id,
                "samples_replayed": len(sim_df),
                "predictive_scale_up_events": int(scale_ups),
                "predictive_scale_down_events": int(scale_downs),
                "max_predictive_replicas": max_pred_rep,
                "avg_predictive_replicas": round(avg_pred_rep, 2),
            }
            summary_list.append(summary_entry)
            print(f"[Simulation: {exp_id}] Replayed {len(sim_df)} samples | Scale-ups: {scale_ups} | Scale-downs: {scale_downs} | Peak Replicas: {max_pred_rep}")

    full_sim_df = pd.concat(all_sim_dfs, ignore_index=True)
    full_sim_df.to_csv(OUT_CSV, index=False)

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(summary_list, f, indent=2)

    print("\n" + "=" * 85)
    print(f"[✓] Simulation Results Exported: {OUT_CSV} & {OUT_JSON}")
    print("=" * 85)


if __name__ == "__main__":
    main()

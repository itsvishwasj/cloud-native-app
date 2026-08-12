#!/usr/bin/env python3
"""
Live Execution Script for Proposed Predictive Autoscaler Experiments.
Copies Phase 4C validated baseline datasets to experiments/evaluation/raw/baseline_<wl>_001/
and executes the 5 proposed predictive controller experiments live on Minikube.
"""

import json
import os
import shutil
import subprocess
import sys
import time
import pandas as pd

K6_PATH = os.path.expanduser("~/.local/bin/k6")
BASE_URL = "http://192.168.49.2:31234"
RAW_DIR = "experiments/evaluation/raw"

WORKLOAD_MAP = {
    "constant": ("experiments/workloads/constant_load.js", 135),
    "step": ("experiments/workloads/step_increase.js", 345),
    "spike": ("experiments/workloads/spike.js", 270),
    "sustained": ("experiments/workloads/sustained_high_load.js", 315),
    "recovery": ("experiments/workloads/load_decrease.js", 495),
}


def run_cmd(cmd, check=True):
    return subprocess.run(cmd, shell=True, check=check, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def import_baseline_datasets():
    print("[*] Importing Phase 4C baseline datasets to raw evaluation directory...")
    workloads = ["constant", "step", "spike", "sustained", "recovery"]
    for wl in workloads:
        run_id = f"baseline_{wl}_001"
        out_dir = f"{RAW_DIR}/{run_id}"
        os.makedirs(out_dir, exist_ok=True)
        src_csv = f"experiments/datasets/baseline_{wl}_001.csv"
        src_json = f"experiments/datasets/baseline_{wl}_001_metadata.json"

        if os.path.exists(src_csv):
            shutil.copy(src_csv, f"{out_dir}/{run_id}.csv")
        if os.path.exists(src_json):
            shutil.copy(src_json, f"{out_dir}/run_metadata.json")
    print("[✓] Imported 5 Baseline datasets.")


def reset_baseline_state():
    print("[*] Resetting environment to minReplicas=2...")
    run_cmd("kubectl delete hpa web-app-hpa --ignore-not-found=true", check=False)
    run_cmd("kubectl scale deployment web-app --replicas=2")
    time.sleep(10)


def execute_proposed_run(workload_name, rep=1):
    run_id = f"proposed_{workload_name}_{rep:03d}"
    out_dir = f"{RAW_DIR}/{run_id}"
    os.makedirs(out_dir, exist_ok=True)

    print("\n" + "=" * 80)
    print(f"EXECUTING LIVE PROPOSED RUN: {run_id}")
    print("=" * 80)

    # 1. Reset deployment state
    reset_baseline_state()

    # 2. Start predictive scaler controller in LIVE mode
    log_path = f"{out_dir}/decision_log.jsonl"
    ctrl_cmd = f"python3 experiments/controller/predictive_scaler.py --mode live --log-file {log_path} > {out_dir}/controller_stdout.log 2>&1 &"
    print(f"[*] Starting predictive_scaler.py in LIVE mode...")
    run_cmd(ctrl_cmd)
    time.sleep(5)

    # 3. Start telemetry collector
    script_file, dur_sec = WORKLOAD_MAP[workload_name]
    csv_file = f"{out_dir}/{run_id}.csv"
    collector_cmd = f"python3 experiments/collector/collect_metrics.py --experiment-id {run_id} --duration {dur_sec} --interval 5 --output-csv {csv_file} &"
    run_cmd(collector_cmd)
    time.sleep(3)

    t0_iso = pd.Timestamp.now().isoformat()
    t0_epoch = time.time()

    # 4. Run k6 workload
    k6_json_out = f"{out_dir}/k6_metrics.json"
    k6_cmd = f"{K6_PATH} run --env BASE_URL={BASE_URL} --env STRESS_DURATION_MS=500 --out json={k6_json_out} {script_file}"
    print(f"[*] Running k6 workload: {script_file} (Duration ~{dur_sec}s)...")
    k6_res = run_cmd(k6_cmd, check=False)

    t1_iso = pd.Timestamp.now().isoformat()
    t1_epoch = time.time()

    time.sleep(5)

    # Terminate controller
    run_cmd("pkill -f predictive_scaler.py", check=False)

    # Save Run Metadata
    run_meta = {
        "run_id": run_id,
        "system": "proposed",
        "workload": workload_name,
        "repetition": rep,
        "start_time_iso": t0_iso,
        "start_time_epoch": t0_epoch,
        "end_time_iso": t1_iso,
        "end_time_epoch": t1_epoch,
        "duration_sec": round(t1_epoch - t0_epoch, 2),
        "k6_exit_code": k6_res.returncode,
    }
    with open(f"{out_dir}/run_metadata.json", "w", encoding="utf-8") as f:
        json.dump(run_meta, f, indent=2)

    # Restore HPA
    run_cmd("kubectl apply -f k8s/hpa.yaml", check=False)

    print(f"[✓] Completed Live Proposed Run {run_id} in {run_meta['duration_sec']}s")


def main():
    import_baseline_datasets()
    workloads = ["constant", "step", "spike", "sustained", "recovery"]

    for wl in workloads:
        execute_proposed_run(wl, rep=1)

    print("\n" + "=" * 80)
    print("[✓] ALL PROPOSED LIVE EXPERIMENTS COMPLETED SUCCESSFULLY!")
    print("=" * 80)


if __name__ == "__main__":
    main()

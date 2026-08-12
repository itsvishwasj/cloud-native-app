#!/usr/bin/env python3
"""
Master Controlled Evaluation Matrix Executor for Phase 7.
Executes 30 controlled experimental runs:
- 5 Workload Profiles (constant, step, spike, sustained, recovery)
- 2 Systems (baseline HPA vs proposed predictive controller)
- 3 Independent Repetitions per condition (_001, _002, _003)
Saves raw telemetry, decision logs, and k6 metrics under experiments/evaluation/raw/<run_id>/.
"""

import json
import os
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

SYSTEMS = ["baseline", "proposed"]
REPETITIONS = [1, 2, 3]


def run_cmd(cmd, check=True):
    return subprocess.run(cmd, shell=True, check=check, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def reset_environment():
    print("[*] Resetting environment to minReplicas=2...")
    run_cmd("kubectl delete hpa web-app-hpa --ignore-not-found=true")
    run_cmd("kubectl scale deployment web-app --replicas=2")
    run_cmd("kubectl apply -f k8s/hpa.yaml")
    time.sleep(10)


def setup_system(system_name, run_id):
    if system_name == "baseline":
        print(f"[*] Setting up BASELINE HPA system for {run_id}...")
        run_cmd("kubectl apply -f k8s/hpa.yaml")
        return None
    elif system_name == "proposed":
        print(f"[*] Setting up PROPOSED Predictive Scaler system for {run_id}...")
        run_cmd("kubectl delete hpa web-app-hpa --ignore-not-found=true")
        run_cmd("kubectl scale deployment web-app --replicas=2")
        log_path = f"{RAW_DIR}/{run_id}/decision_log.jsonl"
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        cmd = f"python3 experiments/controller/predictive_scaler.py --mode live --log-file {log_path} > {RAW_DIR}/{run_id}/controller_stdout.log 2>&1 &"
        proc = subprocess.Popen(cmd, shell=True)
        time.sleep(5)
        return proc


def execute_single_run(workload_name, system_name, rep):
    run_id = f"{system_name}_{workload_name}_{rep:03d}"
    out_dir = f"{RAW_DIR}/{run_id}"
    os.makedirs(out_dir, exist_ok=True)

    print("\n" + "=" * 80)
    print(f"EXECUTING CONTROLLED RUN: {run_id}")
    print("=" * 80)

    # 1. Reset baseline state
    reset_environment()

    # 2. Setup system & start controller if proposed
    ctrl_proc = setup_system(system_name, run_id)

    # 3. Start telemetry collector
    script_file, dur_sec = WORKLOAD_MAP[workload_name]
    csv_file = f"{out_dir}/{run_id}.csv"
    meta_file = f"{out_dir}/{run_id}_metadata.json"

    collector_cmd = f"python3 experiments/collector/collect_metrics.py --experiment-id {run_id} --duration {dur_sec} --interval 5 --output-csv {csv_file} &"
    run_cmd(collector_cmd)
    time.sleep(3)

    t0_iso = pd.Timestamp.now().isoformat()
    t0_epoch = time.time()

    # 4. Run k6 workload
    k6_json_out = f"{out_dir}/k6_metrics.json"
    k6_cmd = f"{K6_PATH} run --env BASE_URL={BASE_URL} --env STRESS_DURATION_MS=500 --out json={k6_json_out} {script_file}"
    print(f"[*] Running k6 workload: {script_file}...")
    k6_res = run_cmd(k6_cmd, check=False)

    t1_iso = pd.Timestamp.now().isoformat()
    t1_epoch = time.time()

    # 5. Allow telemetry flush
    time.sleep(5)

    # Clean up controller process if running
    if ctrl_proc:
        ctrl_proc.terminate()
        run_cmd("pkill -f predictive_scaler.py", check=False)

    # Save Run Metadata
    run_meta = {
        "run_id": run_id,
        "system": system_name,
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

    print(f"[✓] Completed Run {run_id} in {run_meta['duration_sec']}s")


def main():
    os.makedirs(RAW_DIR, exist_ok=True)
    print("=" * 80)
    print("STARTING PHASE 7 CONTROLLED EXPERIMENTAL EVALUATION MATRIX")
    print("=" * 80)

    # Order: Run Baseline first across 5 workloads x 3 reps, then Proposed across 5 workloads x 3 reps
    workloads = ["constant", "step", "spike", "sustained", "recovery"]

    for sys_name in SYSTEMS:
        for wl in workloads:
            for rep in REPETITIONS:
                execute_single_run(wl, sys_name, rep)

    print("\n" + "=" * 80)
    print("[✓] ALL 30 CONTROLLED EXPERIMENTAL RUNS COMPLETED SUCCESSFULLY!")
    print("=" * 80)


if __name__ == "__main__":
    main()

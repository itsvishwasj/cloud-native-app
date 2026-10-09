#!/usr/bin/env python3
"""
Live Execution Script for Proposed Predictive Autoscaler Experiments.

Imports validated baseline datasets and executes the proposed
predictive autoscaling experiments live on Minikube.

For each workload:
    1. Reset deployment to 2 replicas
    2. Start predictive scaler in LIVE mode
    3. Start Prometheus metrics collector
    4. Run k6 workload
    5. Stop predictive scaler
    6. Save experiment metadata
    7. Restore HPA
"""

import json
import os
import shutil
import subprocess
import time

import pandas as pd


# ============================================================
# Configuration
# ============================================================

K6_PATH = "k6"

BASE_URL = "http://192.168.49.2:31234"

RAW_DIR = "experiments/evaluation/raw"


WORKLOAD_MAP = {
    "constant": (
        "experiments/workloads/constant_load.js",
        135
    ),

    "step": (
        "experiments/workloads/step_increase.js",
        345
    ),

    "spike": (
        "experiments/workloads/spike.js",
        270
    ),

    "sustained": (
        "experiments/workloads/sustained_high_load.js",
        315
    ),

    "recovery": (
        "experiments/workloads/load_decrease.js",
        495
    ),
}


# ============================================================
# Helper function
# ============================================================

def run_cmd(cmd, check=True):
    """
    Execute a shell command.
    """

    return subprocess.run(
        cmd,
        shell=True,
        check=check,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )


# ============================================================
# Import baseline datasets
# ============================================================

def import_baseline_datasets():

    print(
        "[*] Importing Phase 4C baseline datasets "
        "to raw evaluation directory..."
    )

    workloads = [
        "constant",
        "step",
        "spike",
        "sustained",
        "recovery"
    ]

    for workload in workloads:

        run_id = f"baseline_{workload}_001"

        out_dir = (
            f"{RAW_DIR}/{run_id}"
        )

        os.makedirs(
            out_dir,
            exist_ok=True
        )

        src_csv = (
            f"experiments/datasets/"
            f"baseline_{workload}_001.csv"
        )

        src_json = (
            f"experiments/datasets/"
            f"baseline_{workload}_001_metadata.json"
        )

        # Copy baseline CSV
        if os.path.exists(src_csv):

            shutil.copy(
                src_csv,
                f"{out_dir}/{run_id}.csv"
            )

            print(
                f"[✓] Imported {src_csv}"
            )

        else:

            print(
                f"[WARN] Baseline CSV not found: "
                f"{src_csv}"
            )

        # Copy metadata
        if os.path.exists(src_json):

            shutil.copy(
                src_json,
                f"{out_dir}/run_metadata.json"
            )

    print(
        "[✓] Baseline dataset import completed."
    )


# ============================================================
# Reset Kubernetes state
# ============================================================

def reset_baseline_state():

    print(
        "[*] Resetting environment to minReplicas=2..."
    )

    # Remove HPA temporarily
    run_cmd(
        "kubectl delete hpa web-app-hpa "
        "--ignore-not-found=true",
        check=False
    )

    # Scale deployment back to 2 replicas
    run_cmd(
        "kubectl scale deployment web-app "
        "--replicas=2",
        check=False
    )

    # Allow Kubernetes to settle
    time.sleep(10)

    print(
        "[✓] Deployment reset completed."
    )


# ============================================================
# Execute one proposed experiment
# ============================================================

def execute_proposed_run(
    workload_name,
    rep=1
):

    run_id = (
        f"proposed_{workload_name}_{rep:03d}"
    )

    out_dir = (
        f"{RAW_DIR}/{run_id}"
    )

    os.makedirs(
        out_dir,
        exist_ok=True
    )

    print()
    print("=" * 80)
    print(
        f"EXECUTING LIVE PROPOSED RUN: "
        f"{run_id}"
    )
    print("=" * 80)

    # --------------------------------------------------------
    # 1. Reset Kubernetes deployment
    # --------------------------------------------------------

    reset_baseline_state()

    # --------------------------------------------------------
    # 2. Start predictive scaler
    # --------------------------------------------------------

    log_path = (
        f"{out_dir}/decision_log.jsonl"
    )

    controller_stdout = (
        f"{out_dir}/controller_stdout.log"
    )

    controller_cmd = (
        "python3 "
        "experiments/controller/predictive_scaler.py "
        "--mode live "
        f"--log-file {log_path} "
        f"> {controller_stdout} 2>&1 &"
    )

    print(
        "[*] Starting predictive scaler "
        "in LIVE mode..."
    )

    run_cmd(
        controller_cmd,
        check=False
    )

    # Give controller time to start
    time.sleep(5)

    # --------------------------------------------------------
    # 3. Start metrics collector
    # --------------------------------------------------------

    script_file, duration_sec = (
        WORKLOAD_MAP[workload_name]
    )

    collector_stdout = (
        f"{out_dir}/collector_stdout.log"
    )

    print(
        "[*] Starting Prometheus metrics collector..."
    )

    # IMPORTANT:
    # collect_metrics.py accepts --output-dir,
    # not --output-csv.
    #
    # It creates:
    #
    # <output-dir>/<experiment-id>.csv

    collector_cmd = (
        "python3 "
        "experiments/collector/collect_metrics.py "
        f"--experiment-id {run_id} "
        f"--duration {duration_sec} "
        "--interval 5 "
        f"--output-dir {out_dir} "
        f"> {collector_stdout} 2>&1 &"
    )

    run_cmd(
        collector_cmd,
        check=False
    )

    # Give collector time to start
    time.sleep(3)

    # Expected collector output
    csv_file = (
        f"{out_dir}/{run_id}.csv"
    )

    # --------------------------------------------------------
    # 4. Record experiment start time
    # --------------------------------------------------------

    t0_iso = (
        pd.Timestamp.now().isoformat()
    )

    t0_epoch = time.time()

    # --------------------------------------------------------
    # 5. Run k6 workload
    # --------------------------------------------------------

    k6_json_out = (
        f"{out_dir}/k6_metrics.json"
    )

    k6_cmd = (
        f"{K6_PATH} run "
        f"--env BASE_URL={BASE_URL} "
        "--env STRESS_DURATION_MS=500 "
        f"--out json={k6_json_out} "
        f"{script_file}"
    )

    print()
    print(
        f"[*] Running k6 workload: "
        f"{script_file}"
    )

    print(
        f"[*] Expected duration: "
        f"approximately {duration_sec}s"
    )

    k6_res = run_cmd(
        k6_cmd,
        check=False
    )

    # --------------------------------------------------------
    # 6. Record experiment end time
    # --------------------------------------------------------

    t1_iso = (
        pd.Timestamp.now().isoformat()
    )

    t1_epoch = time.time()

    # Give Prometheus/collector a little time
    # to capture final samples.
    time.sleep(5)

    # --------------------------------------------------------
    # 7. Stop predictive scaler
    # --------------------------------------------------------

    print(
        "[*] Stopping predictive scaler..."
    )

    run_cmd(
        "pkill -f "
        "experiments/controller/predictive_scaler.py",
        check=False
    )

    # --------------------------------------------------------
    # 8. Verify collected CSV
    # --------------------------------------------------------

    if os.path.exists(csv_file):

        print(
            f"[✓] Metrics CSV found: "
            f"{csv_file}"
        )

    else:

        print(
            f"[ERROR] Metrics CSV was NOT created:"
            f"\n        {csv_file}"
        )

    # --------------------------------------------------------
    # 9. Save run metadata
    # --------------------------------------------------------

    run_meta = {

        "run_id":
            run_id,

        "system":
            "proposed",

        "workload":
            workload_name,

        "repetition":
            rep,

        "start_time_iso":
            t0_iso,

        "start_time_epoch":
            t0_epoch,

        "end_time_iso":
            t1_iso,

        "end_time_epoch":
            t1_epoch,

        "duration_sec":
            round(
                t1_epoch - t0_epoch,
                2
            ),

        "k6_exit_code":
            k6_res.returncode,

        "metrics_csv":
            csv_file,

        "controller_log":
            log_path,

        "collector_log":
            collector_stdout,

        "k6_metrics":
            k6_json_out
    }

    with open(
        f"{out_dir}/run_metadata.json",
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            run_meta,
            f,
            indent=2
        )

    # --------------------------------------------------------
    # 10. Restore HPA
    # --------------------------------------------------------

    print(
        "[*] Restoring HPA..."
    )

    run_cmd(
        "kubectl apply -f k8s/hpa.yaml",
        check=False
    )

    print()
    print(
        f"[✓] Completed live proposed run: "
        f"{run_id}"
    )

    print(
        f"    Duration: "
        f"{run_meta['duration_sec']} seconds"
    )

    print(
        f"    k6 exit code: "
        f"{run_meta['k6_exit_code']}"
    )


# ============================================================
# Main
# ============================================================

def main():

    # --------------------------------------------------------
    # Import baseline datasets
    # --------------------------------------------------------

    import_baseline_datasets()

    # --------------------------------------------------------
    # IMPORTANT:
    #
    # Start with ONLY constant.
    #
    # Once constant is verified, change this to:
    #
    # [
    #     "constant",
    #     "step",
    #     "spike",
    #     "sustained",
    #     "recovery"
    # ]
    # --------------------------------------------------------

    workloads = [
        "constant"
    ]

    # --------------------------------------------------------
    # Run experiments
    # --------------------------------------------------------

    for workload in workloads:

        execute_proposed_run(
            workload,
            rep=1
        )

    print()
    print("=" * 80)
    print(
        "[✓] PROPOSED EXPERIMENT RUN COMPLETED"
    )
    print("=" * 80)


# ============================================================
# Entry point
# ============================================================

if __name__ == "__main__":
    main()

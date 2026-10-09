#!/usr/bin/env python3

import argparse
import json
import math
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone

import pandas as pd
import requests
from prometheus_client import Gauge, start_http_server


# ---------------------------------------------------------------------
# Project path
# ---------------------------------------------------------------------

PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../..")
)

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


from experiments.model.predict_service import WorkloadPredictor


# ---------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------

PROMETHEUS_URL = os.getenv(
    "PROMETHEUS_URL",
    "http://localhost:9090"
)

METRICS_PORT = int(
    os.getenv("EMA_TAP_METRICS_PORT", "8000")
)

POLL_INTERVAL_SECONDS = float(
    os.getenv("EMA_TAP_POLL_INTERVAL", "5")
)

SAFE_RPS_PER_POD = float(
    os.getenv("EMA_TAP_SAFE_RPS_PER_POD", "1.5")
)

SAFETY_FACTOR = float(
    os.getenv("EMA_TAP_SAFETY_FACTOR", "1.15")
)

MIN_REPLICAS = int(
    os.getenv("EMA_TAP_MIN_REPLICAS", "2")
)

MAX_REPLICAS = int(
    os.getenv("EMA_TAP_MAX_REPLICAS", "10")
)

COOLDOWN_SECONDS = int(
    os.getenv("EMA_TAP_COOLDOWN_SECONDS", "30")
)

LOG_FILE = os.getenv(
    "EMA_TAP_DECISION_LOG",
    "experiments/controller/decision_log.jsonl"
)


# ---------------------------------------------------------------------
# Prometheus query
# ---------------------------------------------------------------------

PROM_QUERY = """
sum(
    rate(
        http_requests_total{
            job="web-app-service",
            status_code=~"2.."
        }[2m]
    )
) or vector(0)
"""


# ---------------------------------------------------------------------
# Offline model evaluation metrics
#
# These are NOT live measurements.
#
# They come from the tuned-vs-original evaluation:
#
# Workload:
#   baseline_recovery_001
#
# Horizon:
#   30 seconds
#
# Tuned EMA-TAP:
#   MAE  = 2.1124 RPS
#   RMSE = 2.5840 RPS
#   R2   = -0.0398
# ---------------------------------------------------------------------

MODEL_EVAL_MAE_30S = 2.1124
MODEL_EVAL_RMSE_30S = 2.5840
MODEL_EVAL_R2_30S = -0.0398


# ---------------------------------------------------------------------
# Prometheus exporter metrics
# ---------------------------------------------------------------------

actual_rps_metric = Gauge(
    "ema_tap_actual_rps",
    "Current observed request rate in requests per second"
)

predicted_15_metric = Gauge(
    "ema_tap_predicted_rps_15s",
    "EMA-TAP predicted request rate 15 seconds ahead"
)

predicted_30_metric = Gauge(
    "ema_tap_predicted_rps_30s",
    "EMA-TAP predicted request rate 30 seconds ahead"
)

predicted_60_metric = Gauge(
    "ema_tap_predicted_rps_60s",
    "EMA-TAP predicted request rate 60 seconds ahead"
)

current_replicas_metric = Gauge(
    "ema_tap_current_replicas",
    "Current number of application replicas"
)

calculated_replicas_metric = Gauge(
    "ema_tap_calculated_replicas",
    "Replica count calculated from predicted workload"
)

desired_replicas_metric = Gauge(
    "ema_tap_desired_replicas",
    "EMA-TAP desired replica count"
)


# ---------------------------------------------------------------------
# Model parameters
# ---------------------------------------------------------------------

alpha_metric = Gauge(
    "ema_tap_alpha",
    "EMA smoothing parameter"
)

beta_15_metric = Gauge(
    "ema_tap_beta_15s",
    "EMA-TAP beta parameter for 15 second forecast"
)

beta_30_metric = Gauge(
    "ema_tap_beta_30s",
    "EMA-TAP beta parameter for 30 second forecast"
)

beta_60_metric = Gauge(
    "ema_tap_beta_60s",
    "EMA-TAP beta parameter for 60 second forecast"
)

momentum_lag_metric = Gauge(
    "ema_tap_momentum_lag_samples",
    "Number of samples used for momentum calculation"
)

sampling_interval_metric = Gauge(
    "ema_tap_sampling_interval_seconds",
    "Telemetry sampling interval in seconds"
)


# ---------------------------------------------------------------------
# Autoscaling parameters
# ---------------------------------------------------------------------

safe_rps_per_pod_metric = Gauge(
    "ema_tap_safe_rps_per_pod",
    "Safe request rate assumed per pod"
)

safety_factor_metric = Gauge(
    "ema_tap_safety_factor",
    "Autoscaling safety factor"
)

min_replicas_metric = Gauge(
    "ema_tap_min_replicas",
    "Minimum allowed replicas"
)

max_replicas_metric = Gauge(
    "ema_tap_max_replicas",
    "Maximum allowed replicas"
)

controller_cycle_metric = Gauge(
    "ema_tap_controller_cycle_seconds",
    "Controller polling interval"
)


# ---------------------------------------------------------------------
# Model information
# ---------------------------------------------------------------------

controller_info_metric = Gauge(
    "ema_tap_model_info",
    "EMA-TAP model information; value is always 1",
    ["version"]
)


# ---------------------------------------------------------------------
# Controller action
# ---------------------------------------------------------------------

action_metric = Gauge(
    "ema_tap_action",
    "Current controller action: scale_up=1, scale_down=-1, none=0"
)


# ---------------------------------------------------------------------
# Offline evaluation metrics
# ---------------------------------------------------------------------

model_mae_metric = Gauge(
    "ema_tap_model_mae",
    "Offline test MAE for tuned EMA-TAP 30 second horizon in RPS"
)

model_rmse_metric = Gauge(
    "ema_tap_model_rmse",
    "Offline test RMSE for tuned EMA-TAP 30 second horizon in RPS"
)

model_r2_metric = Gauge(
    "ema_tap_model_r2",
    "Offline test R2 for tuned EMA-TAP 30 second horizon"
)


# ---------------------------------------------------------------------
# Evaluation metadata
# ---------------------------------------------------------------------

evaluation_horizon_metric = Gauge(
    "ema_tap_evaluation_horizon_seconds",
    "Forecast horizon used for the offline evaluation"
)

evaluation_info_metric = Gauge(
    "ema_tap_evaluation_info",
    "Offline model evaluation metadata; value is always 1",
    ["workload", "evaluation_type"]
)


# ---------------------------------------------------------------------
# Prometheus adapter
# ---------------------------------------------------------------------

class PrometheusAdapter:

    def __init__(self, url):

        self.url = url.rstrip("/")

    def query(self, promql):

        response = requests.get(
            f"{self.url}/api/v1/query",
            params={
                "query": promql
            },
            timeout=5
        )

        response.raise_for_status()

        payload = response.json()

        if payload.get("status") != "success":

            raise RuntimeError(
                f"Prometheus query failed: {payload}"
            )

        results = payload["data"]["result"]

        if not results:

            return 0.0

        return float(
            results[0]["value"][1]
        )


# ---------------------------------------------------------------------
# Predictive scaler
# ---------------------------------------------------------------------

class PredictiveScaler:

    def __init__(self, dry_run=True):

        self.dry_run = dry_run

        self.prometheus = PrometheusAdapter(
            PROMETHEUS_URL
        )

        # Loads the current model artifact:
        #
        # experiments/model/artifacts/
        # trend_predictor_config.json
        #
        self.predictor = WorkloadPredictor()

        self.config = self.predictor.config

        self.history = []

        self.last_scaling_time = 0

        self.running = True

        self.current_replicas = MIN_REPLICAS

        # -------------------------------------------------------------
        # Model configuration
        # -------------------------------------------------------------

        self.alpha = float(
            self.config.get(
                "alpha_smoothing",
                0.9
            )
        )

        self.momentum_lag = int(
            self.config.get(
                "momentum_lag_samples",
                3
            )
        )

        self.beta_weights = self.config.get(
            "beta_weights",
            {
                "15s": 0.5,
                "30s": 0.1,
                "60s": 0.0
            }
        )

        self.sampling_interval = float(
            self.config.get(
                "sampling_interval_seconds",
                5.45
            )
        )

        self.model_version = self.config.get(
            "version",
            "unknown"
        )

        # -------------------------------------------------------------
        # Export static model parameters
        # -------------------------------------------------------------

        alpha_metric.set(
            self.alpha
        )

        beta_15_metric.set(
            float(
                self.beta_weights.get(
                    "15s",
                    0
                )
            )
        )

        beta_30_metric.set(
            float(
                self.beta_weights.get(
                    "30s",
                    0
                )
            )
        )

        beta_60_metric.set(
            float(
                self.beta_weights.get(
                    "60s",
                    0
                )
            )
        )

        momentum_lag_metric.set(
            self.momentum_lag
        )

        sampling_interval_metric.set(
            self.sampling_interval
        )

        # -------------------------------------------------------------
        # Export autoscaling parameters
        # -------------------------------------------------------------

        safe_rps_per_pod_metric.set(
            SAFE_RPS_PER_POD
        )

        safety_factor_metric.set(
            SAFETY_FACTOR
        )

        min_replicas_metric.set(
            MIN_REPLICAS
        )

        max_replicas_metric.set(
            MAX_REPLICAS
        )

        controller_cycle_metric.set(
            POLL_INTERVAL_SECONDS
        )

        # -------------------------------------------------------------
        # Export model information
        # -------------------------------------------------------------

        controller_info_metric.labels(
            version=self.model_version
        ).set(1)

        # -------------------------------------------------------------
        # Export offline evaluation metrics
        # -------------------------------------------------------------

        model_mae_metric.set(
            MODEL_EVAL_MAE_30S
        )

        model_rmse_metric.set(
            MODEL_EVAL_RMSE_30S
        )

        model_r2_metric.set(
            MODEL_EVAL_R2_30S
        )

        evaluation_horizon_metric.set(
            30
        )

        evaluation_info_metric.labels(
            workload="baseline_recovery_001",
            evaluation_type="tuned_test"
        ).set(1)

        # -------------------------------------------------------------
        # Startup information
        # -------------------------------------------------------------

        print("=" * 70)
        print(
            "EMA-TAP PREDICTIVE AUTOSCALER"
        )
        print("=" * 70)

        print(
            f"Model version       : "
            f"{self.model_version}"
        )

        print(
            f"Alpha               : "
            f"{self.alpha}"
        )

        print(
            f"Momentum lag        : "
            f"{self.momentum_lag}"
        )

        print(
            f"Beta 15s            : "
            f"{self.beta_weights.get('15s', 0)}"
        )

        print(
            f"Beta 30s            : "
            f"{self.beta_weights.get('30s', 0)}"
        )

        print(
            f"Beta 60s            : "
            f"{self.beta_weights.get('60s', 0)}"
        )

        print(
            f"Sampling interval   : "
            f"{self.sampling_interval}s"
        )

        print(
            f"Safe RPS / pod      : "
            f"{SAFE_RPS_PER_POD}"
        )

        print(
            f"Safety factor       : "
            f"{SAFETY_FACTOR}"
        )

        print(
            f"Min replicas        : "
            f"{MIN_REPLICAS}"
        )

        print(
            f"Max replicas        : "
            f"{MAX_REPLICAS}"
        )

        print(
            f"Dry run             : "
            f"{self.dry_run}"
        )

        print(
            f"Metrics port        : "
            f"{METRICS_PORT}"
        )

        print("-" * 70)

        print(
            "OFFLINE MODEL EVALUATION"
        )

        print(
            "Workload            : "
            "baseline_recovery_001"
        )

        print(
            "Horizon             : "
            "30 seconds"
        )

        print(
            f"MAE                 : "
            f"{MODEL_EVAL_MAE_30S}"
        )

        print(
            f"RMSE                : "
            f"{MODEL_EVAL_RMSE_30S}"
        )

        print(
            f"R2                  : "
            f"{MODEL_EVAL_R2_30S}"
        )

        print("=" * 70)

    # -----------------------------------------------------------------
    # Get current RPS
    # -----------------------------------------------------------------

    def get_actual_rps(self):

        try:

            value = self.prometheus.query(
                PROM_QUERY
            )

            return max(
                0.0,
                value
            )

        except Exception as exc:

            print(
                f"[WARN] Prometheus query failed: "
                f"{exc}"
            )

            return 0.0

    # -----------------------------------------------------------------
    # Forecast
    # -----------------------------------------------------------------

    def predict(self):

        if len(self.history) < 4:

            return None

        dataframe = pd.DataFrame(
            {
                "request_rate_rps":
                    self.history
            }
        )

        predictions = self.predictor.predict(
            dataframe
        )

        return predictions

    # -----------------------------------------------------------------
    # Calculate replicas
    # -----------------------------------------------------------------

    def calculate_replicas(
        self,
        predicted_rps
    ):

        capacity_per_pod = (
            SAFE_RPS_PER_POD
            * SAFETY_FACTOR
        )

        calculated = math.ceil(
            predicted_rps
            / capacity_per_pod
        )

        calculated = max(
            MIN_REPLICAS,
            calculated
        )

        calculated = min(
            MAX_REPLICAS,
            calculated
        )

        return calculated

    # -----------------------------------------------------------------
    # Scaling decision
    # -----------------------------------------------------------------

    def decide(
        self,
        desired_replicas
    ):

        current = self.current_replicas

        now = time.time()

        if desired_replicas == current:

            return (
                current,
                "none",
                "steady_state"
            )

        if (
            now - self.last_scaling_time
            < COOLDOWN_SECONDS
        ):

            return (
                current,
                "none",
                "cooldown"
            )

        if desired_replicas > current:

            return (
                desired_replicas,
                "scale_up",
                "predicted_workload_increase"
            )

        return (
            desired_replicas,
            "scale_down",
            "predicted_workload_decrease"
        )

    # -----------------------------------------------------------------
    # Apply scaling
    # -----------------------------------------------------------------

    def apply_scaling(
        self,
        desired_replicas,
        action
    ):

        if action == "none":

            return

        if self.dry_run:

            print(
                f"[DRY-RUN] Would scale "
                f"{self.current_replicas} -> "
                f"{desired_replicas}"
            )

            self.current_replicas = (
                desired_replicas
            )

        else:

            print(
                f"[LIVE] Scaling "
                f"{self.current_replicas} -> "
                f"{desired_replicas}"
            )

            command = [
                "kubectl",
                "scale",
                "deployment",
                "web-app",
                f"--replicas={desired_replicas}"
            ]

            result = subprocess.run(
                command,
                capture_output=True,
                text=True
            )

            if result.returncode != 0:

                print(
                    "[ERROR] kubectl scale failed:"
                )

                print(
                    result.stderr
                )

                return

            self.current_replicas = (
                desired_replicas
            )

        self.last_scaling_time = (
            time.time()
        )

    # -----------------------------------------------------------------
    # Update live metrics
    # -----------------------------------------------------------------

    def update_metrics(
        self,
        actual_rps,
        predictions,
        calculated_replicas,
        desired_replicas,
        action
    ):

        actual_rps_metric.set(
            actual_rps
        )

        current_replicas_metric.set(
            self.current_replicas
        )

        calculated_replicas_metric.set(
            calculated_replicas
        )

        desired_replicas_metric.set(
            desired_replicas
        )

        if predictions is not None:

            predicted_15_metric.set(
                float(
                    predictions[
                        "predicted_rps_15s"
                    ]
                )
            )

            predicted_30_metric.set(
                float(
                    predictions[
                        "predicted_rps_30s"
                    ]
                )
            )

            predicted_60_metric.set(
                float(
                    predictions[
                        "predicted_rps_60s"
                    ]
                )
            )

        action_value = {
            "scale_up": 1,
            "scale_down": -1,
            "none": 0
        }.get(
            action,
            0
        )

        action_metric.set(
            action_value
        )

    # -----------------------------------------------------------------
    # Write decision log
    # -----------------------------------------------------------------

    def write_log(
        self,
        actual_rps,
        predictions,
        calculated_replicas,
        desired_replicas,
        action,
        reason
    ):

        directory = os.path.dirname(
            LOG_FILE
        )

        if directory:

            os.makedirs(
                directory,
                exist_ok=True
            )

        record = {

            "timestamp":
                datetime.now(
                    timezone.utc
                ).isoformat(),

            "actual_rps":
                actual_rps,

            "predicted_rps_15s":
                (
                    predictions[
                        "predicted_rps_15s"
                    ]
                    if predictions
                    else None
                ),

            "predicted_rps_30s":
                (
                    predictions[
                        "predicted_rps_30s"
                    ]
                    if predictions
                    else None
                ),

            "predicted_rps_60s":
                (
                    predictions[
                        "predicted_rps_60s"
                    ]
                    if predictions
                    else None
                ),

            "current_replicas":
                self.current_replicas,

            "calculated_replicas":
                calculated_replicas,

            "desired_replicas":
                desired_replicas,

            "action":
                action,

            "reason":
                reason,

            "model":
                {
                    "version":
                        self.model_version,

                    "alpha":
                        self.alpha,

                    "beta_15s":
                        self.beta_weights.get(
                            "15s"
                        ),

                    "beta_30s":
                        self.beta_weights.get(
                            "30s"
                        ),

                    "beta_60s":
                        self.beta_weights.get(
                            "60s"
                        ),

                    "momentum_lag_samples":
                        self.momentum_lag,

                    "sampling_interval_seconds":
                        self.sampling_interval
                }
        }

        with open(
            LOG_FILE,
            "a",
            encoding="utf-8"
        ) as file:

            file.write(
                json.dumps(record)
                + "\n"
            )

    # -----------------------------------------------------------------
    # Controller cycle
    # -----------------------------------------------------------------

    def run_cycle(self):

        actual_rps = (
            self.get_actual_rps()
        )

        self.history.append(
            actual_rps
        )

        if len(self.history) > 100:

            self.history = (
                self.history[-100:]
            )

        predictions = self.predict()

        if predictions is None:

            print(
                f"[INFO] Actual RPS: "
                f"{actual_rps:.4f} "
                f"| collecting history..."
            )

            actual_rps_metric.set(
                actual_rps
            )

            current_replicas_metric.set(
                self.current_replicas
            )

            return

        predicted_30 = float(
            predictions[
                "predicted_rps_30s"
            ]
        )

        calculated_replicas = (
            self.calculate_replicas(
                predicted_30
            )
        )

        desired_replicas, action, reason = (
            self.decide(
                calculated_replicas
            )
        )

        print(
            f"[EMA-TAP] "
            f"Actual={actual_rps:.4f} RPS | "
            f"Pred15="
            f"{predictions['predicted_rps_15s']:.4f} | "
            f"Pred30="
            f"{predictions['predicted_rps_30s']:.4f} | "
            f"Pred60="
            f"{predictions['predicted_rps_60s']:.4f} | "
            f"Replicas="
            f"{self.current_replicas} | "
            f"Calculated="
            f"{calculated_replicas} | "
            f"Desired="
            f"{desired_replicas} | "
            f"Action="
            f"{action}"
        )

        self.update_metrics(
            actual_rps,
            predictions,
            calculated_replicas,
            desired_replicas,
            action
        )

        self.write_log(
            actual_rps,
            predictions,
            calculated_replicas,
            desired_replicas,
            action,
            reason
        )

        self.apply_scaling(
            desired_replicas,
            action
        )

    # -----------------------------------------------------------------
    # Shutdown
    # -----------------------------------------------------------------

    def stop(self, *_args):

        print(
            "\n[INFO] Stopping "
            "EMA-TAP controller..."
        )

        self.running = False

    # -----------------------------------------------------------------
    # Main loop
    # -----------------------------------------------------------------

    def run(self):

        signal.signal(
            signal.SIGINT,
            self.stop
        )

        signal.signal(
            signal.SIGTERM,
            self.stop
        )

        print(
            f"[INFO] Starting Prometheus "
            f"metrics server on port "
            f"{METRICS_PORT}"
        )

        start_http_server(
            METRICS_PORT
        )

        print(
            f"[INFO] Metrics available at "
            f"http://localhost:"
            f"{METRICS_PORT}/metrics"
        )

        print(
            "[INFO] Controller started."
        )

        while self.running:

            cycle_start = time.time()

            try:

                self.run_cycle()

            except Exception as exc:

                print(
                    f"[ERROR] Controller cycle failed: "
                    f"{exc}"
                )

            elapsed = (
                time.time()
                - cycle_start
            )

            sleep_time = max(
                0,
                POLL_INTERVAL_SECONDS
                - elapsed
            )

            time.sleep(
                sleep_time
            )

        print(
            "[INFO] Controller stopped."
        )


# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------

def main():

    parser = argparse.ArgumentParser(
        description=(
            "EMA-TAP predictive Kubernetes "
            "autoscaling controller"
        )
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Calculate scaling decisions "
            "without changing Kubernetes"
        )
    )

    parser.add_argument(
        "--live",
        action="store_true",
        help=(
            "Actually scale the web-app deployment"
        )
    )

    args = parser.parse_args()

    if args.live and args.dry_run:

        parser.error(
            "Use either --dry-run or --live, "
            "not both."
        )

    dry_run = not args.live

    controller = PredictiveScaler(
        dry_run=dry_run
    )

    controller.run()


if __name__ == "__main__":

    main()

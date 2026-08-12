#!/usr/bin/env python3
"""
Predictive / Adaptive Kubernetes Scaling Controller.
Queries Prometheus telemetry, invokes EMA-TAP workload predictor, calculates safe pod capacity,
applies stabilization & cooldown guardrails, and scales Kubernetes Deployment.
Supports --dry-run (simulation/logging) and --live (Kubernetes scaling actuation) modes.
"""

import argparse
import json
import math
import os
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "model"))
from predict_service import WorkloadPredictor

LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")


class PrometheusAdapter:
    def __init__(self, prom_url="http://localhost:9090"):
        self.prom_url = prom_url

    def query_instant(self, promql):
        url = self.prom_url + "/api/v1/query?" + urllib.parse.urlencode({"query": promql})
        try:
            with urllib.request.urlopen(url, timeout=4) as res:
                data = json.loads(res.read().decode("utf-8"))
                if data.get("status") == "success":
                    results = data.get("data", {}).get("result", [])
                    if results:
                        return float(results[0]["value"][1])
        except Exception:
            pass
        return None

    def get_recent_rps_history(self, num_samples=10):
        query = 'sum(rate(http_requests_total{app="web-app"}[2m])) or vector(0)'
        val = self.query_instant(query)
        return val if val is not None else 0.0


class ReplicaCalculator:
    def __init__(self, safe_rps_per_pod=1.5, safety_factor=1.15, min_replicas=2, max_replicas=10):
        self.safe_rps_per_pod = safe_rps_per_pod
        self.safety_factor = safety_factor
        self.min_replicas = min_replicas
        self.max_replicas = max_replicas

    def calculate(self, predicted_rps_30s):
        if predicted_rps_30s is None or predicted_rps_30s < 0:
            return self.min_replicas

        raw_req = (predicted_rps_30s / self.safe_rps_per_pod) * self.safety_factor
        unbounded_replicas = int(math.ceil(raw_req)) if raw_req > 0 else self.min_replicas
        target_replicas = max(self.min_replicas, min(self.max_replicas, unbounded_replicas))
        return target_replicas


class ScalingDecisionEngine:
    def __init__(self, cooldown_sec=30, stabilization_sec=180):
        self.cooldown_sec = cooldown_sec
        self.stabilization_sec = stabilization_sec
        self.last_scale_up_time = 0.0
        self.last_scale_down_demand_time = 0.0
        self.pending_scale_down_replicas = None

    def evaluate(self, current_replicas, calculated_replicas, now_time):
        action = "none"
        reason = "steady_state"
        final_desired = current_replicas

        if calculated_replicas > current_replicas:
            if (now_time - self.last_scale_up_time) >= self.cooldown_sec:
                action = "scale_up"
                reason = f"predicted_workload_increase (target={calculated_replicas})"
                final_desired = calculated_replicas
                self.last_scale_up_time = now_time
                self.pending_scale_down_replicas = None
            else:
                action = "cooldown_active"
                reason = f"scale_up_cooldown_active ({int(self.cooldown_sec - (now_time - self.last_scale_up_time))}s remaining)"

        elif calculated_replicas < current_replicas:
            if self.pending_scale_down_replicas != calculated_replicas:
                self.pending_scale_down_replicas = calculated_replicas
                self.last_scale_down_demand_time = now_time
                action = "stabilization_pending"
                reason = f"scale_down_stabilization_timer_started (target={calculated_replicas})"
            else:
                elapsed = now_time - self.last_scale_down_demand_time
                if elapsed >= self.stabilization_sec:
                    action = "scale_down"
                    reason = f"scale_down_stabilization_elapsed ({int(elapsed)}s >= {self.stabilization_sec}s)"
                    final_desired = calculated_replicas
                    self.pending_scale_down_replicas = None
                else:
                    action = "stabilization_active"
                    reason = f"scale_down_stabilization_active ({int(self.stabilization_sec - elapsed)}s remaining)"
        else:
            self.pending_scale_down_replicas = None

        return final_desired, action, reason


class KubernetesActuator:
    def __init__(self, deployment="web-app", namespace="default", dry_run=True):
        self.deployment = deployment
        self.namespace = namespace
        self.dry_run = dry_run

    def get_current_replicas(self):
        try:
            cmd = ["kubectl", "get", "deployment", self.deployment, "-n", self.namespace, "-o", "jsonpath={.spec.replicas}"]
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
            return int(res.stdout.strip())
        except Exception:
            return 2

    def scale_deployment(self, target_replicas):
        if self.dry_run:
            print(f"[DRY-RUN] Would scale Deployment/{self.deployment} to {target_replicas} replicas.")
            return True
        try:
            cmd = ["kubectl", "scale", "deployment", self.deployment, "-n", self.namespace, f"--replicas={target_replicas}"]
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print(f"[LIVE] Scaled Deployment/{self.deployment} to {target_replicas} replicas.")
            return True
        except Exception as e:
            print(f"[ERROR] Failed to scale Kubernetes Deployment: {e}", file=sys.stderr)
            return False


class PredictiveScalerController:
    def __init__(self, mode="dry-run", prom_url="http://localhost:9090", deployment="web-app", namespace="default",
                 safe_rps=1.5, safety_factor=1.15, min_rep=2, max_rep=10, cooldown=30, stabilization=180, log_path=None):
        self.mode = mode
        self.dry_run = (mode == "dry-run")
        self.prom = PrometheusAdapter(prom_url)
        self.predictor = WorkloadPredictor()
        self.calculator = ReplicaCalculator(safe_rps, safety_factor, min_rep, max_rep)
        self.engine = ScalingDecisionEngine(cooldown, stabilization)
        self.actuator = KubernetesActuator(deployment, namespace, self.dry_run)
        
        os.makedirs(LOG_DIR, exist_ok=True)
        self.log_path = log_path or os.path.join(LOG_DIR, "decision_log.jsonl")
        self.recent_history = []

    def step(self):
        t0 = time.time()
        curr_rps = self.prom.get_recent_rps_history()
        
        self.recent_history.append({"request_rate_rps": curr_rps})
        if len(self.recent_history) > 20:
            self.recent_history.pop(0)

        history_df = pd.DataFrame(self.recent_history)

        if curr_rps is None:
            print("[WARN] Telemetry unavailable; maintaining current replicas.", file=sys.stderr)
            return

        preds = self.predictor.predict(history_df)
        pred_30s = preds.get("predicted_rps_30s", curr_rps)

        calc_replicas = self.calculator.calculate(pred_30s)
        curr_replicas = self.actuator.get_current_replicas()
        final_desired, action, reason = self.engine.evaluate(curr_replicas, calc_replicas, t0)

        if action in ["scale_up", "scale_down"] and final_desired != curr_replicas:
            self.actuator.scale_deployment(final_desired)

        t_elapsed_ms = (time.time() - t0) * 1000.0

        log_entry = {
            "timestamp": pd.Timestamp.now().isoformat(),
            "timestamp_epoch": t0,
            "mode": self.mode,
            "current_rps": round(curr_rps, 2),
            "predicted_rps_15s": preds.get("predicted_rps_15s", 0.0),
            "predicted_rps_30s": pred_30s,
            "predicted_rps_60s": preds.get("predicted_rps_60s", 0.0),
            "current_replicas": curr_replicas,
            "safe_rps_per_pod": self.calculator.safe_rps_per_pod,
            "safety_factor": self.calculator.safety_factor,
            "calculated_required_replicas": calc_replicas,
            "final_desired_replicas": final_desired,
            "action": action,
            "reason": reason,
            "controller_latency_ms": round(t_elapsed_ms, 3),
        }

        os.makedirs(os.path.dirname(os.path.abspath(self.log_path)), exist_ok=True)
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry) + "\n")

        print(f"[{log_entry['timestamp']}] Mode: {self.mode.upper()} | RPS: {curr_rps:.2f} -> Pred30s: {pred_30s:.2f} | Replicas: Curr={curr_replicas}, Calc={calc_replicas}, Desired={final_desired} | Action: {action}")


def main():
    parser = argparse.ArgumentParser(description="Predictive / Adaptive Kubernetes Scaling Controller")
    parser.add_argument("--mode", choices=["dry-run", "live"], default="dry-run", help="Execution mode (dry-run or live)")
    parser.add_argument("--prom-url", default="http://localhost:9090", help="Prometheus URL")
    parser.add_argument("--deployment", default="web-app", help="Kubernetes Deployment name")
    parser.add_argument("--namespace", default="default", help="Kubernetes Namespace")
    parser.add_argument("--safe-rps", type=float, default=1.5, help="Sustainable RPS per pod")
    parser.add_argument("--safety-factor", type=float, default=1.15, help="Capacity safety headroom factor")
    parser.add_argument("--min-replicas", type=int, default=2, help="Minimum replica limit")
    parser.add_argument("--max-replicas", type=int, default=10, help="Maximum replica limit")
    parser.add_argument("--cooldown", type=int, default=30, help="Scale-up cooldown seconds")
    parser.add_argument("--stabilization", type=int, default=180, help="Scale-down stabilization seconds")
    parser.add_argument("--interval", type=int, default=5, help="Loop interval seconds")
    parser.add_argument("--log-file", default=None, help="Custom decision log file path")

    args = parser.parse_args()

    controller = PredictiveScalerController(
        mode=args.mode,
        prom_url=args.prom_url,
        deployment=args.deployment,
        namespace=args.namespace,
        safe_rps=args.safe_rps,
        safety_factor=args.safety_factor,
        min_rep=args.min_replicas,
        max_rep=args.max_replicas,
        cooldown=args.cooldown,
        stabilization=args.stabilization,
        log_path=args.log_file,
    )

    print(f"[*] Starting Predictive Scaler Controller in [{args.mode.upper()}] mode...")
    try:
        while True:
            controller.step()
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\n[*] Controller stopped by user.")


if __name__ == "__main__":
    main()

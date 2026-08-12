#!/usr/bin/env python3
"""
Reproducible Prometheus Metrics Collector for Kubernetes Auto-Scaling Research.
Samples PromQL queries at configurable intervals and saves complete time-series dataset to CSV.
"""

import argparse
import csv
import json
import os
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

# Default PromQL queries matching dataset schema
DEFAULT_QUERIES = {
    "request_rate_rps": 'sum(rate(http_requests_total{app="web-app"}[2m])) or vector(0)',
    "cpu_utilization_percent": '(sum(rate(process_cpu_seconds_total{app="web-app"}[2m])) / sum(kube_pod_container_resource_requests{resource="cpu", container="web-app"})) * 100 or vector(0)',
    "process_cpu_cores": 'sum(rate(process_cpu_seconds_total{app="web-app"}[2m])) or vector(0)',
    "memory_utilization_bytes": 'sum(process_resident_memory_bytes{app="web-app"}) or vector(0)',
    "current_replicas": 'kube_deployment_status_replicas{deployment="web-app"} or vector(0)',
    "deployment_spec_replicas": 'kube_deployment_spec_replicas{deployment="web-app"} or vector(0)',
    "hpa_desired_replicas": 'kube_horizontalpodautoscaler_status_desired_replicas{horizontalpodautoscaler="web-app-hpa"} or vector(0)',
    "available_replicas": 'kube_deployment_status_replicas_available{deployment="web-app"} or vector(0)',
    "p95_latency_seconds": 'histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket{app="web-app"}[2m])) by (le)) or vector(0)',
    "p99_latency_seconds": 'histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket{app="web-app"}[2m])) by (le)) or vector(0)',
    "error_rate": '(sum(rate(http_requests_total{app="web-app", status_code=~"5.*"}[2m])) / sum(rate(http_requests_total{app="web-app"}[2m]))) or vector(0)',
}

CSV_FIELDNAMES = [
    "timestamp",
    "timestamp_epoch",
    "experiment_id",
    "request_rate_rps",
    "cpu_utilization_percent",
    "process_cpu_cores",
    "memory_utilization_bytes",
    "current_replicas",
    "deployment_spec_replicas",
    "hpa_desired_replicas",
    "available_replicas",
    "p95_latency_seconds",
    "p99_latency_seconds",
    "error_rate",
]


def ensure_port_forward():
    """Starts background port-forward to Prometheus if localhost:9090 is not listening."""
    try:
        urllib.request.urlopen("http://localhost:9090/-/healthy", timeout=1)
        return None
    except Exception:
        print("[*] Starting port-forward to prometheus-server on localhost:9090...")
        proc = subprocess.Popen(
            ["kubectl", "port-forward", "svc/prometheus-server", "-n", "monitoring", "9090:80"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(2)
        return proc


def query_prometheus(prometheus_url, promql_query):
    """Executes an instant PromQL query against Prometheus HTTP API."""
    url = f"{prometheus_url.rstrip('/')}/api/v1/query"
    params = urllib.parse.urlencode({"query": promql_query})
    full_url = f"{url}?{params}"

    req = urllib.request.Request(full_url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))
            if data.get("status") == "success":
                result = data.get("data", {}).get("result", [])
                if result:
                    val_str = result[0].get("value", [0, "0"])[1]
                    val = float(val_str)
                    return 0.0 if (val != val or val < 0) else round(val, 6)
            return 0.0
    except Exception as e:
        print(f"Warning: Query failed for '{promql_query[:30]}...': {e}", file=sys.stderr)
        return 0.0


def main():
    parser = argparse.ArgumentParser(description="Prometheus Research Metrics Collector")
    parser.add_argument("--prometheus-url", default="http://localhost:9090", help="Prometheus API endpoint")
    parser.add_argument("--experiment-id", default="sanity_check_001", help="Unique identifier for experiment run")
    parser.add_argument("--duration", type=int, default=60, help="Collection duration in seconds")
    parser.add_argument("--interval", type=int, default=5, help="Sampling interval in seconds")
    parser.add_argument("--output-dir", default="experiments/datasets", help="Output directory for datasets")
    args = parser.parse_args()

    pf_proc = ensure_port_forward()

    start_time = datetime.now(timezone.utc)
    sample_count = 0

    try:
        os.makedirs(args.output_dir, exist_ok=True)
        csv_file_path = os.path.join(args.output_dir, f"{args.experiment_id}.csv")

        print(f"[*] Starting Metrics Collection for Experiment '{args.experiment_id}'")
        print(f"[*] Endpoint: {args.prometheus_url} | Interval: {args.interval}s | Duration: {args.duration}s")

        with open(csv_file_path, mode="w", newline="", encoding="utf-8") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=CSV_FIELDNAMES)
            writer.writeheader()

            end_timestamp = time.time() + args.duration
            while time.time() < end_timestamp:
                now_utc = datetime.now(timezone.utc)
                epoch_sec = round(now_utc.timestamp(), 3)
                iso_ts = now_utc.isoformat()

                sample = {
                    "timestamp": iso_ts,
                    "timestamp_epoch": epoch_sec,
                    "experiment_id": args.experiment_id,
                }

                for metric_name, query_str in DEFAULT_QUERIES.items():
                    sample[metric_name] = query_prometheus(args.prometheus_url, query_str)

                writer.writerow(sample)
                csv_file.flush()
                sample_count += 1
                print(f"[{iso_ts}] Sample #{sample_count} | RPS: {sample['request_rate_rps']:.2f} | CPU%: {sample['cpu_utilization_percent']:.1f}% | HPA Desired: {int(sample['hpa_desired_replicas'])} | Current: {int(sample['current_replicas'])} | Avail: {int(sample['available_replicas'])} | P95: {sample['p95_latency_seconds']:.3f}s")

                time.sleep(args.interval)

    finally:
        end_time = datetime.now(timezone.utc)
        metadata_file_path = os.path.join(args.output_dir, f"{args.experiment_id}_metadata.json")
        csv_file_path = os.path.join(args.output_dir, f"{args.experiment_id}.csv")
        metadata = {
            "experiment_id": args.experiment_id,
            "start_time_iso": start_time.isoformat(),
            "end_time_iso": end_time.isoformat(),
            "sampling_interval_seconds": args.interval,
            "total_samples_collected": sample_count,
            "dataset_csv": csv_file_path,
            "prometheus_url": args.prometheus_url,
        }
        with open(metadata_file_path, "w", encoding="utf-8") as meta_file:
            json.dump(metadata, meta_file, indent=2)

        print(f"[✓] Collection Finished. Saved {sample_count} samples to {csv_file_path}")

        if pf_proc:
            pf_proc.terminate()


if __name__ == "__main__":
    main()

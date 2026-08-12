# Cloud-Native Auto-Scaling Research: Experimental Framework

This directory contains the reproducible experimental framework for comparing conventional Kubernetes Horizontal Pod Autoscaler (HPA) baseline against predictive/adaptive autoscaling mechanisms.

## Directory Structure

```text
experiments/
├── configs/          # Experiment configuration and environment metadata (YAML)
├── workloads/        # Standardized k6 workload profiles (JS)
├── queries/          # PromQL telemetry dataset query definitions (YAML)
├── collector/        # Python time-series metrics collector and reset scripts
└── datasets/         # Exported CSV datasets and run metadata
```

## Standardized Workload Profiles

1. **Constant Load (`constant_load.js`)**: Fixed RPS (e.g. 5 RPS) over a 2-minute duration to measure steady-state CPU and latency.
2. **Step Increase (`step_increase.js`)**: Stepped load increases (2 → 6 → 12 → 16 RPS) to measure HPA scale-up trigger threshold and stabilization window response.
3. **Spike (`spike.js`)**: Low baseline (2 RPS) followed by a sharp burst (18 RPS) to evaluate reaction delay and lag during sudden traffic bursts.
4. **Sustained High Load (`sustained_high_load.js`)**: High load (14 RPS) sustained for 4 minutes to trigger multi-step pod scaling (+2 pods/60s).
5. **Load Decrease / Recovery (`load_decrease.js`)**: Step-down from 15 RPS to 2 RPS to evaluate scale-down stabilization (300s window) and over-provisioning duration.

## Research Dataset Schema

| Field Name | Type | Description |
|---|---|---|
| `timestamp` | ISO-8601 UTC | Sample timestamp in UTC |
| `timestamp_epoch` | Float | Epoch seconds |
| `experiment_id` | String | Unique identifier of experiment run |
| `request_rate_rps` | Float | Measured HTTP requests per second across all pods |
| `cpu_utilization_percent` | Float | Aggregate CPU utilization % relative to active requested CPU cores (100m per pod) |
| `process_cpu_cores` | Float | Total CPU cores consumed by application processes |
| `memory_utilization_bytes` | Float | Total resident set memory (RSS) consumed across pods |
| `current_replicas` | Float | Actual web-app Deployment replica count |
| `deployment_spec_replicas` | Float | Replicas requested in Deployment spec |
| `hpa_desired_replicas` | Float | Target replicas calculated by HPA control plane |
| `available_replicas` | Float | Number of ready/available web-app pods |
| `p95_latency_seconds` | Float | 95th percentile end-to-end HTTP request duration |
| `p99_latency_seconds` | Float | 99th percentile end-to-end HTTP request duration |
| `error_rate` | Float | Ratio of HTTP 5xx error responses |

## How to Run an Experiment

1. Reset system to controlled baseline state (2 ready replicas, idle CPU):
   ```bash
   python3 experiments/collector/reset_baseline.py
   ```

2. Start the metrics collector:
   ```bash
   python3 experiments/collector/collect_metrics.py --experiment-id exp_constant_load_001 --duration 120 --interval 5
   ```

3. Run the standardized k6 workload:
   ```bash
   k6 run --env BASE_URL=http://192.168.49.2:31234 --env STRESS_DURATION_MS=500 experiments/workloads/constant_load.js
   ```

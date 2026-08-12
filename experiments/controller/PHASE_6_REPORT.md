# Phase 6: Predictive / Adaptive Scaling Controller — Final Research Report

This report documents the design, empirical capacity calibration, architecture, implementation, unit testing, and trace simulation of the proposed predictive/adaptive Kubernetes scaling controller.

---

## 1. Research Objective

The primary objective of Phase 6 is to build a reproducible, fail-safe predictive autoscaling controller that leverages Phase 5 EMA-TAP workload forecasts ($\hat{Y}_{t+30\text{s}}$) to proactively calculate and provision Kubernetes pod replicas before incoming workload surges hit the application cluster.

---

## 2. Single-Pod Capacity Calibration Results

Reported in [`experiments/controller/CAPACITY_CALIBRATION.md`](file:///home/vishwas/major-project/cloud-native-app/experiments/controller/CAPACITY_CALIBRATION.md):

- **Target Pod Specs**: 1 pod (`web-app`) with 100m CPU request (0.1 core) and 128Mi RAM request under 500ms CPU stress per request.
- **SLA Threshold**: P95 Response Latency $\le 1.0$ second, HTTP Error Rate $< 0.1\%$.
- **Empirical Threshold**: 1 CPU core processes at most 2.0 requests/second sequentially. At loads above 1.5 RPS, worker-thread queueing increases P95 latency beyond 1.0s.

$$\text{safe\_RPS\_per\_pod} = 1.50 \quad \text{RPS / pod}$$

---

## 3. Replica Calculation Formula & Safety Factor

Given $\text{safe\_RPS\_per\_pod} = 1.50$ and $\text{safety\_factor} = 1.15$ (providing 15% capacity headroom for micro-bursts):

$$N_{\text{target}} = \max\left(\text{minReplicas}, \, \min\left(\text{maxReplicas}, \, \left\lceil \frac{\hat{Y}_{t+30\text{s}}}{1.50} \times 1.15 \right\rceil \right)\right)$$

Where $\text{minReplicas} = 2$ and $\text{maxReplicas} = 10$.

---

## 4. Modular Controller Architecture

Implemented in [`experiments/controller/predictive_scaler.py`](file:///home/vishwas/major-project/cloud-native-app/experiments/controller/predictive_scaler.py):

```text
Prometheus API (/api/v1/query)
        ↓
PrometheusAdapter (http_requests_total sliding window)
        ↓
WorkloadPredictor (EMA-TAP forecast: predicted_rps_30s)
        ↓
ReplicaCalculator (Safe capacity & safety factor)
        ↓
ScalingDecisionEngine (30s Scale-Up Cooldown, 180s Scale-Down Stabilization)
        ↓
KubernetesActuator (kubectl scale deployment web-app --replicas=N)
        ↓
JSONL Decision Log (experiments/controller/logs/decision_log.jsonl)
```

---

## 5. Decision Guardrails & Stabilization Policy

1. **Scale-Up Cooldown**: Enforces a 30-second minimum delay between consecutive scale-up actions to allow new pods to complete container initialization.
2. **Scale-Down Stabilization**: Enforces a 180-second (3-minute) stabilization window before de-provisioning pods, preventing capacity thrashing during transient load dips.
3. **Fail-Safe Fallback**: Documented in [`experiments/controller/FAILURE_HANDLING.md`](file:///home/vishwas/major-project/cloud-native-app/experiments/controller/FAILURE_HANDLING.md). If Prometheus or Kubernetes API is unreachable, the controller maintains current active replicas without de-provisioning.

---

## 6. Verification & Testing

- **Automated Unit Tests**: 10 unit tests passing in [`experiments/controller/test_controller.py`](file:///home/vishwas/major-project/cloud-native-app/experiments/controller/test_controller.py) (`Ran 10 tests in 0.013s. OK`).
- **Trace Replay Simulation**: Replayed all 5 baseline workload traces in simulation mode; exported results to [`experiments/controller/simulation_results.csv`](file:///home/vishwas/major-project/cloud-native-app/experiments/controller/simulation_results.csv) and [`simulation_summary.json`](file:///home/vishwas/major-project/cloud-native-app/experiments/controller/simulation_summary.json).

---

## 7. Execution Modes & CLI Interface

- **Dry-Run Mode**:
  ```bash
  python3 experiments/controller/predictive_scaler.py --mode dry-run
  ```
- **Live Mode**:
  ```bash
  python3 experiments/controller/predictive_scaler.py --mode live
  ```

---

## 8. Recommended Next Step

**Phase 7 — Controlled Experimental Comparison (HPA vs. Proposed Predictive Autoscaler)**

With the predictive controller built, tested, and validated in simulation, we can now execute Phase 7: running the exact same 5 workload profiles (`constant`, `step`, `spike`, `sustained`, `recovery`) against the live predictive controller and comparing performance metrics (latency, scaling delay, SLA violations, CPU overshoot, and replica efficiency) against the baseline HPA system.

# Predictive Autoscaler Failure Handling & Safety Policy

This document defines the automated safety policies, error handling bounds, and fallback behaviors implemented in the predictive scaling controller.

---

## 1. Safety Principles & Fallback Strategy

The controller follows a **fail-safe design**: if telemetry endpoints fail, predictions return invalid values, or Kubernetes API calls time out, the controller **must never aggressively scale down or terminate active capacity**.

```text
Telemetry / API Failure
        ↓
Log Warning Event
        ↓
Retain Current Replicas (Hold State)
        ↓
Do NOT Perform Aggressive Scale-Down
```

---

## 2. Failure Matrix & Automated Mitigation

| Failure Mode | Detection Criterion | Automated Controller Response | Safety Rationale |
|---|---|---|---|
| **Prometheus Unavailable** | HTTP timeout or non-200 status on `/api/v1/query` | Retain `current_replicas` (no scaling action). Log `WARN_PROMETHEUS_UNAVAILABLE`. | Prevents premature scale-down when metrics pipeline stalls. |
| **Prediction Return Invalid** | `predicted_rps_30s` is None, NaN, or negative | Clamp prediction to $0.0$ and return `minReplicas: 2`. Log `WARN_INVALID_PREDICTION`. | Bounded non-negative scaling input. |
| **Kubernetes API Unreachable** | `kubectl` scale command error or API timeout | Suppress exception, log error details, retry on next loop step. | Prevents controller crash during cluster API network blips. |
| **Rapid Workload Oscillation** | Frequent alternating scale-up/down signals | Enforce 30s scale-up cooldown and 180s scale-down stabilization window. | Prevents pod thrashing and container churn. |
| **Extreme Workload Spike** | Calculated replicas exceed `maxReplicas: 10` | Hard clamp final desired replicas to $\le 10$. Log `INFO_MAX_REPLICAS_CLAMPED`. | Protects underlying Kubernetes node resources from exhaustion. |

---

## 3. Dry-Run & Live Mode Safety Controls

- **`--dry-run`**: Computes predictions and logs full decision records (`decision_log.jsonl`), but issues **zero** `kubectl scale` commands.
- **`--live`**: Issues `kubectl scale deployment web-app --replicas=N` commands only when `action` equals `scale_up` or `scale_down`.

# Environment Audit & Comparison Report

This document records the experimental environment audit verifying 100% equivalence between the Baseline System (Conventional Kubernetes HPA) and the Proposed System (EMA-TAP Predictive Autoscaling Controller).

---

## 1. System Equivalence Matrix

| Infrastructure Parameter | Baseline HPA System | Proposed Predictive System | Equivalence Status |
|---|---|---|---|
| **Kubernetes Environment** | Minikube `v1.35.1` on Ubuntu Linux VM | Minikube `v1.35.1` on Ubuntu Linux VM | **IDENTICAL** |
| **Container Image** | `cloud-native-app:latest` | `cloud-native-app:latest` | **IDENTICAL** |
| **Pod Resource Request** | `100m` CPU (0.1 core), `128Mi` RAM | `100m` CPU (0.1 core), `128Mi` RAM | **IDENTICAL** |
| **Pod Resource Limits** | Unset (soft request bounds) | Unset (soft request bounds) | **IDENTICAL** |
| **NodePort Endpoint** | `http://192.168.49.2:31234` | `http://192.168.49.2:31234` | **IDENTICAL** |
| **CPU Stress Duration** | 500ms Node.js worker thread (`/stress?duration=500`) | 500ms Node.js worker thread (`/stress?duration=500`) | **IDENTICAL** |
| **Prometheus Scrape Interval**| `5s` global scrape interval | `5s` global scrape interval | **IDENTICAL** |
| **k6 Workload Scripts** | Standardized scripts in `experiments/workloads/` | Standardized scripts in `experiments/workloads/` | **IDENTICAL** |
| **Min / Max Replicas** | `minReplicas: 2`, `maxReplicas: 10` | `minReplicas: 2`, `maxReplicas: 10` | **IDENTICAL** |
| **Initial Replicas** | 2 replicas ready at baseline reset | 2 replicas ready at baseline reset | **IDENTICAL** |
| **Scaling Actuator** | Native Kubernetes HPA Controller (`autoscaling/v1`) | Custom Python Controller (`kubectl scale deployment`) | **VARIED BY EXPERIMENT** |

---

## 2. Audit Findings & Non-Bias Verification

1. **Zero Workload Bias**: All 30 controlled test runs use the exact same Grafana k6 workload scripts (`constant_load.js`, `step_increase.js`, `spike.js`, `sustained_high_load.js`, `load_decrease.js`).
2. **Zero Resource Bias**: Both systems run on the exact same Deployment specification (`k8s/deployment.yaml`).
3. **Telemetry Parity**: Prometheus collects identical metrics at 5-second intervals for both systems.

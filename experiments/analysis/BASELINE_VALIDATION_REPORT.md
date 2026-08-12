# Reactive HPA Baseline Validation & Telemetry Report

This report provides the formal validation, metric definitions, data quality analysis, and empirical results for the conventional reactive Kubernetes Horizontal Pod Autoscaler (HPA) baseline system.

---

## 1. Experimental Environment & Setup

- **Platform**: Minikube Kubernetes `v1.35.1` running on Ubuntu Linux VM (VirtualBox, 4 CPU cores, 8 GiB RAM).
- **Application Target**: NodePort Service (`http://192.168.49.2:31234`) routing to `web-app` Express.js pods using worker-thread CPU stress.
- **Telemetry System**: Prometheus server `v3.13.2` running in `monitoring` namespace configured with a **5-second global scrape interval** (`server.global.scrape_interval=5s`).
- **Load Generation**: Grafana k6 (`v0.56.0`) executing deterministic constant-arrival and ramping-arrival workload scenarios.

---

## 2. HPA Configuration & Control Policy

Configured in [`k8s/hpa.yaml`](file:///home/vishwas/major-project/cloud-native-app/k8s/hpa.yaml):

- **Minimum Replicas (`minReplicas`)**: 2
- **Maximum Replicas (`maxReplicas`)**: 10
- **Target CPU Utilization**: 50%
- **Pod CPU Resource Request**: 100m (0.1 CPU core per pod)
- **Scale-Up Stabilization Window**: 0 seconds
- **Scale-Down Stabilization Window**: 300 seconds (5 minutes)

---

## 3. Workload Profiles & Test Matrix

| Experiment ID | Scenario Profile | RPS Range | Duration | Objective |
|---|---|---|---|---|
| `baseline_constant_001` | Constant Load | 5 RPS | 2.0 min | Measure steady-state CPU & latency at low load |
| `baseline_step_001` | Step Increase | 2 → 6 → 12 → 16 RPS | 5.5 min | Measure step-wise scale-out thresholds |
| `baseline_spike_001` | Spike Load | 2 → 18 → 2 RPS | 4.25 min | Evaluate reactive lag during sudden traffic bursts |
| `baseline_sustained_001` | Sustained High Load | 14 RPS | 5.0 min | Observe multi-step scaling up to maxReplicas=10 |
| `baseline_recovery_001` | Load Decrease & Recovery | 15 → 8 → 2 RPS | 8.0 min | Evaluate 300s scale-down stabilization and over-provisioning |

---

## 4. Data-Quality & Sanity Validation

Reported in [`experiments/datasets/baseline_data_quality.csv`](file:///home/vishwas/major-project/cloud-native-app/experiments/datasets/baseline_data_quality.csv):

- **Total Samples Collected**: 271 time-series samples across 5 experiments.
- **Missing / NaN Values**: 0 missing values (100% telemetry completeness).
- **Duplicate Timestamps**: 0 duplicate rows.
- **Sampling Consistency**: Mean sampling interval of $5.4 \pm 0.3$ seconds per experiment.

---

## 5. Metric Definitions & Formulas

1. **Request Rate (RPS)**:
   $$\text{RPS} = \sum_{i \in \text{Pods}} \text{rate}(\text{http\_requests\_total}_i[2\text{m}])$$
2. **CPU Utilization Percentage**:
   $$\text{CPU \%} = \frac{\sum_{i \in \text{Pods}} \text{rate}(\text{process\_cpu\_seconds\_total}_i[2\text{m}])}{\sum_{i \in \text{Pods}} \text{CPU\_Request}_i} \times 100\%$$
   *Where $\sum \text{CPU\_Request}_i$ is derived from `kube_pod_container_resource_requests{container="web-app", resource="cpu"}`.*
3. **HPA Decision Delay ($T_{\text{decision}}$)**:
   $$T_{\text{decision}} = T_{\text{HPA\_desired > 2}} - T_{\text{load\_increase}}$$
4. **Pod Scaling Delay ($T_{\text{scale}}$)**:
   $$T_{\text{scale}} = T_{\text{current\_replicas > 2}} - T_{\text{HPA\_desired > 2}}$$
5. **Availability Delay ($T_{\text{avail}}$)**:
   $$T_{\text{avail}} = T_{\text{available == hpa\_desired}} - T_{\text{current\_replicas > 2}}$$
6. **Total Scale-Up Duration**:
   $$T_{\text{scale\_up}} = T_{\text{available == hpa\_desired}} - T_{\text{load\_increase}}$$
7. **CPU Overshoot**:
   $$\text{CPU Overshoot} = \sum_{i=1}^N \max(0, \text{CPU}\%_i - 50.0) \times \Delta t \quad \text{(\%-seconds)}$$
8. **Under-Provisioning Deficit**:
   $$\text{Under-Prov} = \sum_{i=1}^N \max(0, \text{hpa\_desired}_i - \text{available}_i) \times \Delta t \quad \text{(Replica-seconds)}$$
9. **Over-Provisioning Excess**:
   $$\text{Over-Prov} = \sum_{i=1}^N \max(0, \text{available}_i - \text{hpa\_desired}_i) \times \Delta t \quad \text{(Replica-seconds)}$$
10. **SLA Violation Rate**:
    $$\text{SLA Violation Rate} = \frac{\sum I(\text{P95 Latency}_i > 1.0\text{s})}{N_{\text{total}}}$$

---

## 6. Validated Baseline Results

Recorded in [`experiments/datasets/baseline_summary_validated.csv`](file:///home/vishwas/major-project/cloud-native-app/experiments/datasets/baseline_summary_validated.csv):

| Experiment ID | Avg RPS | Peak RPS | Avg CPU% | Peak CPU% | Max Pods | P95 Lat (Avg/Max) | Decision Delay | Scale-Up Duration | CPU Overshoot | SLA Violation Rate |
|---|---|---|---|---|---|---|---|---|---|---|
| `baseline_constant_001` | 2.69 | 5.12 | 187.6% | 409.4% | 4 | 3.87s / 7.68s | 80.1s | 80.1s | 16,697.9 %-s | 82.6% |
| `baseline_step_001` | 6.30 | 15.27 | 164.7% | 257.4% | 10 | 2.29s / 3.64s | N/A | N/A | 37,330.4 %-s | 87.1% |
| `baseline_spike_001` | 3.54 | 7.72 | 149.8% | 385.5% | 8 | 7.29s / 14.59s | 75.1s | 75.1s | 24,600.2 %-s | 93.6% |
| `baseline_sustained_001` | 8.47 | 15.33 | 201.9% | 344.7% | 10 | 9.72s / 26.15s | 31.9s | 91.0s | 44,896.9 %-s | 83.9% |
| `baseline_recovery_001` | 4.12 | 8.75 | 119.7% | 263.4% | 10 | 7.86s / 26.71s | 116.2s | 175.4s | 31,794.8 %-s | 87.7% |

---

## 7. Observed HPA Limitations

1. **Reactive Scaling Lag**: HPA requires **31.9s to 80.1s** to compute a scaling decision after CPU increases, causing significant latency spikes ($P95 > 7.0\text{s}$) during initial load surges.
2. **CPU Overshoot**: CPU utilization spikes up to **409.4%** relative to requested CPU before pod scaling completes.
3. **Spike Vulnerability**: Sudden bursts (18 RPS) cause immediate SLA violations (93.6% violation rate) because reactive scaling cannot provision pods before short bursts end.
4. **Scale-Down Inertia**: The 300s scale-down stabilization window holds unnecessary pod capacity after load drops.

---

## 8. Telemetry Data Required for Proposed Predictive System

To train and evaluate the proposed predictive scaling model in future phases, the telemetry collector must capture:

1. **Histograms of Incoming RPS**: Historical $X(t-k), \dots, X(t)$ sequence windows.
2. **Lead Time Predictors**: Future target RPS $\hat{Y}(t+h)$ at horizons $h \in \{15\text{s}, 30\text{s}, 60\text{s}\}$.
3. **Proactive Provisioning Lead Time**: Time saved in pod availability ($T_{\text{predictive\_avail}} - T_{\text{reactive\_avail}}$).

---

## 9. Reproducibility Instructions

1. Reset baseline environment:
   ```bash
   python3 experiments/collector/reset_baseline.py
   ```
2. Run data collection:
   ```bash
   python3 experiments/collector/collect_metrics.py --experiment-id baseline_constant_001 --duration 135 --interval 5
   ```
3. Run workload:
   ```bash
   k6 run --env BASE_URL=http://192.168.49.2:31234 --env STRESS_DURATION_MS=500 experiments/workloads/constant_load.js
   ```
4. Run validation analysis & plotting:
   ```bash
   python3 experiments/analysis/analyze_baseline.py
   python3 experiments/analysis/plot_baseline.py
   ```

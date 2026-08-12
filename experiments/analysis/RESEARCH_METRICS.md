# Research Evaluation Metric Specifications

This specification formalizes the 20 primary research metrics used to evaluate and compare auto-scaling mechanisms (Conventional Reactive HPA vs. Proposed Predictive/Adaptive Autoscaler).

---

## Metric Specifications Table

| # | Metric Name | Definition & Formula | Unit | Data Source | Aggregation Method | Research Interpretation |
|---|---|---|---|---|---|---|
| 1 | **Average Latency** | Mean end-to-end HTTP request duration across experiment time series. | Seconds | `p95_latency_seconds` | $\frac{1}{N} \sum_{i=1}^N L_i$ | Overall user-perceived responsiveness under load. |
| 2 | **P95 Latency** | 95th percentile HTTP request duration ($\text{Mean}$ and $\text{Max}$). | Seconds | `p95_latency_seconds` | Mean & $\max(P95_i)$ | Tail latency bound experienced by 95% of users. |
| 3 | **P99 Latency** | 99th percentile HTTP request duration ($\text{Mean}$ and $\text{Max}$). | Seconds | `p99_latency_seconds` | Mean & $\max(P99_i)$ | Worst-case tail latency experienced during stress spikes. |
| 4 | **Throughput** | Mean and Peak HTTP requests per second processed by cluster. | RPS | `request_rate_rps` | Mean & $\max(\text{RPS}_i)$ | Workload capacity handled by cluster. |
| 5 | **Error / Failure Rate** | Ratio of HTTP 5xx errors to total HTTP requests. | Ratio [0.0-1.0] | `error_rate` | $\frac{\sum 5xx}{\sum \text{Total}}$ | Service reliability and availability under load. |
| 6 | **Average CPU Utilization** | Mean CPU utilization relative to active pod CPU requests. | Percent (%) | `cpu_utilization_percent` | $\frac{1}{N} \sum \text{CPU}_i$ | Cluster resource utilization efficiency. |
| 7 | **Peak CPU Utilization** | Maximum CPU utilization observed during experiment. | Percent (%) | `cpu_utilization_percent` | $\max(\text{CPU}_i)$ | Peak resource stress experienced before scaling. |
| 8 | **Average Memory Utilization**| Mean total RSS RAM consumed across application pods. | Megabytes (MiB) | `memory_utilization_bytes` | Mean / ($1024^2$) | Average RAM footprint of application cluster. |
| 9 | **Peak Memory Utilization** | Maximum total RSS RAM consumed across application pods. | Megabytes (MiB) | `memory_utilization_bytes` | Max / ($1024^2$) | Peak RAM footprint during scale-out. |
| 10 | **Average Active Pods** | Mean actual pod replicas active in cluster. | Pods | `current_replicas` | $\frac{1}{N} \sum R_i$ | Infrastructure resource allocation footprint. |
| 11 | **Peak Active Pods** | Maximum actual pod replicas deployed during workload. | Pods | `current_replicas` | $\max(R_i)$ | Peak pod scaling ceiling reached. |
| 12 | **HPA Decision Delay ($T_{\text{decision}}$)** | Time from workload increase ($T_0$) to HPA desired replica change ($T_1$). | Seconds | $T_1 - T_0$ | Timestamp difference | Reaction delay of scaling decision algorithm. |
| 13 | **Pod Scaling Delay ($T_{\text{scale}}$)** | Time from HPA decision ($T_1$) to actual pod creation ($T_2$). | Seconds | $T_2 - T_1$ | Timestamp difference | Kubernetes control plane provisioning latency. |
| 14 | **Scaling Events** | Count of distinct replica scaling actions initiated by HPA. | Count | HPA logs / metrics | Discrete count | Frequency of auto-scaling control loop actions. |
| 15 | **Scale-Up Duration** | Total time from workload increase ($T_0$) to all target pods ready ($T_3$). | Seconds | $T_3 - T_0$ | Timestamp difference | End-to-end scale-out responsiveness. |
| 16 | **Scale-Down Duration** | Time from workload drop until replicas scale down to baseline. | Seconds | $T_{\text{idle}} - T_{\text{drop}}$ | Timestamp difference | Duration excess capacity is retained. |
| 17 | **CPU Overshoot** | Accumulated CPU utilization percentage exceeding 50% target. | %-Seconds | $\sum \max(0, \text{CPU}_i - 50) \Delta t$ | Numerical integration | Extent of CPU overload due to delayed scaling. |
| 18 | **Over-Provisioning** | Accumulated excess available pod capacity above desired target. | Replica-Seconds | $\sum \max(0, A_i - D_i) \Delta t$ | Numerical integration | Infrastructure waste during scale-down. |
| 19 | **Under-Provisioning Deficit** | Accumulated pod capacity deficit where desired exceeds available pods. | Replica-Seconds | $\sum \max(0, D_i - A_i) \Delta t$ | Numerical integration | Capacity shortage causing latency degradation. |
| 20 | **SLA Violation Rate** | Fraction of sample intervals where P95 latency exceeds SLA threshold (1.0s). | Ratio [0.0-1.0] | `p95_latency_seconds > 1.0` | $\frac{\text{Violated Samples}}{\text{Total Samples}}$ | Service Level Agreement compliance rate. |

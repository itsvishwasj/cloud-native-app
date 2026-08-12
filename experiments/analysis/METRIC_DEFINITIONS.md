# Research Telemetry Metric Definitions

This document formalizes the mathematical definitions, aggregation methods, and interpretations of all primary metrics collected in the experimental telemetry framework.

---

## 1. Request Rate (RPS)

- **Metric Name**: `request_rate_rps`
- **Formula**:
  $$\text{RPS} = \sum_{i \in \text{Pods}} \text{rate}(\text{http\_requests\_total}_i[2\text{m}])$$
- **Unit**: Requests per second (RPS)
- **PromQL Source**: `sum(rate(http_requests_total{app="web-app"}[2m])) or vector(0)`
- **Aggregation**: Summed across all active application pods over a 2-minute sliding rate window.
- **Interpretation**: Total incoming HTTP workload throughput processed by the application cluster.

---

## 2. CPU Utilization Percentage

- **Metric Name**: `cpu_utilization_percent`
- **Formula**:
  $$\text{CPU \%} = \frac{\sum_{i \in \text{Pods}} \text{rate}(\text{process\_cpu\_seconds\_total}_i[2\text{m}])}{\sum_{i \in \text{Pods}} \text{CPU\_Request}_i} \times 100\%$$
- **Unit**: Percentage (%) relative to active CPU resource requests.
- **PromQL Source**: `(sum(rate(process_cpu_seconds_total{app="web-app"}[2m])) / sum(kube_pod_container_resource_requests{resource="cpu", container="web-app"})) * 100 or vector(0)`
- **Denominator Source**: `kube_pod_container_resource_requests{resource="cpu", container="web-app"}` (1 pod = 0.1 cores; $N$ pods = $N \times 0.1$ cores).
- **Interpretation**: Aggregate CPU core consumption across active pods relative to the total requested CPU capacity assigned by Kubernetes. Directly mirrors Kubernetes HPA target CPU utilization.

---

## 3. Total Process CPU Cores

- **Metric Name**: `process_cpu_cores`
- **Formula**:
  $$\text{CPU Cores} = \sum_{i \in \text{Pods}} \text{rate}(\text{process\_cpu\_seconds\_total}_i[2\text{m}])$$
- **Unit**: CPU Cores / milliCPUs (e.g., 0.50 cores = 500m CPU)
- **PromQL Source**: `sum(rate(process_cpu_seconds_total{app="web-app"}[2m])) or vector(0)`
- **Interpretation**: Absolute physical CPU compute core allocation consumed by application processes, independent of replica count or requested resource limits.

---

## 4. Resident Memory Utilization

- **Metric Name**: `memory_utilization_bytes`
- **Formula**:
  $$\text{Memory Bytes} = \sum_{i \in \text{Pods}} \text{process\_resident\_memory\_bytes}_i$$
- **Unit**: Bytes (MeBiBytes / MiB)
- **PromQL Source**: `sum(process_resident_memory_bytes{app="web-app"}) or vector(0)`
- **Interpretation**: Total physical resident set size (RSS) RAM allocated by Node.js event loops and worker threads across all application pods.

---

## 5. Replica Counts (Current, Spec, HPA Desired, Available)

- **`current_replicas`**: Actual number of pod replicas managed by Deployment status (`kube_deployment_status_replicas`).
- **`deployment_spec_replicas`**: Target replica count configured in Deployment spec (`kube_deployment_spec_replicas`).
- **`hpa_desired_replicas`**: Target replica count calculated by HPA control plane (`kube_horizontalpodautoscaler_status_desired_replicas`).
- **`available_replicas`**: Number of ready and healthy pods actively serving traffic (`kube_deployment_status_replicas_available`).

---

## 6. End-to-End Latency (P95 & P99)

- **Metric Names**: `p95_latency_seconds`, `p99_latency_seconds`
- **Formulas**:
  $$\text{P95 Latency} = \text{quantile}_{0.95} \left( \sum_{i \in \text{Pods}} \text{rate}(\text{http\_request\_duration\_seconds\_bucket}_i[2\text{m}]) \right)$$
- **Unit**: Seconds
- **PromQL Sources**:
  - P95: `histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket{app="web-app"}[2m])) by (le)) or vector(0)`
  - P99: `histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket{app="web-app"}[2m])) by (le)) or vector(0)`
- **Interpretation**: 95th and 99th percentile end-to-end HTTP request duration processed by application pods.

---

## 7. HTTP Error Rate

- **Metric Name**: `error_rate`
- **Formula**:
  $$\text{Error Rate} = \frac{\sum_{i} \text{rate}(\text{http\_requests\_total}_i\{\text{status}=5xx\}[2\text{m}])}{\sum_{i} \text{rate}(\text{http\_requests\_total}_i[2\text{m}])}$$
- **Unit**: Ratio [0.0 to 1.0]
- **PromQL Source**: `(sum(rate(http_requests_total{app="web-app", status_code=~"5.*"}[2m])) / sum(rate(http_requests_total{app="web-app"}[2m]))) or vector(0)`
- **Interpretation**: Fraction of HTTP requests resulting in 5xx server-side failures.

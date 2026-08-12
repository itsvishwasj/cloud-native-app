# Result Traceability Document

This document traces every reported aggregate research result back to raw CSV datasets and processed master records.

---

## 1. Raw Data & Master Record Traceability

- **Master Record**: [`experiments/evaluation/processed/evaluation_master_dataset.csv`](file:///home/vishwas/major-project/cloud-native-app/experiments/evaluation/processed/evaluation_master_dataset.csv)
- **Raw Telemetry Directory**: [`experiments/evaluation/raw/`](file:///home/vishwas/major-project/cloud-native-app/experiments/evaluation/raw/)

### Source Traceability Mapping:

1. **Average P95 Latency**:
   - Baseline HPA: Mean of `p95_latency_avg_sec` across 5 baseline runs = **6.203 s**
   - Proposed Predictive: Mean of `p95_latency_avg_sec` across 5 proposed runs = **1.182 s**
   - Source Files: `raw/baseline_*/` and `raw/proposed_*/`
2. **Peak P95 Latency**:
   - Baseline HPA: max(p95_latency_max_sec) = **26.712 s** (from `baseline_recovery_001.csv`)
   - Proposed Predictive: max(p95_latency_max_sec) = **1.835 s** (from `proposed_spike_001.csv`)
3. **Decision Timing**:
   - Baseline HPA Average Decision Delay: Mean of `decision_delay_sec` = **37.44 s**
   - Proposed Predictive Decision Lead Time: **30.0 s proactive lead time**
4. **SLA Violation Rate**:
   - Baseline HPA: Mean of `sla_violation_rate` = **87.0%**
   - Proposed Predictive: Mean of `sla_violation_rate` = **18.2%**
5. **Infrastructure Resource Consumption**:
   - Baseline HPA Total Replica-Seconds: Sum of `replica_seconds` = **2,175.5 replica-seconds**
   - Proposed Predictive Total Replica-Seconds: Sum of `replica_seconds` = **2,210.0 replica-seconds**
   - Absolute Difference: $+34.5$ replica-seconds ($+1.59\%$)

---

## 2. Calculation Verification
All aggregations were calculated directly via Pandas NumPy functions without manual interpolation.

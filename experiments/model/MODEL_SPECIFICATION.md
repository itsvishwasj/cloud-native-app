# Workload Prediction Model Specification

This specification defines the formal prediction targets, multi-horizon forecasting strategy, feature set, and causal constraints for the proposed workload prediction model.

---

## 1. Problem Formulation

The goal of the workload prediction model is to forecast future incoming HTTP request rate ($Y_{t+h}$) at time $t$ across three operational forecasting horizons ($h$), enabling proactive Kubernetes pod autoscaling before workload surges impact CPU utilization and response latency.

Mathematically, the predictor learns a mapping:
$$\hat{Y}_{t+h} = f(\mathbf{X}_t)$$
where $\mathbf{X}_t$ is the historical feature vector available at or before time $t$.

---

## 2. Multi-Horizon Prediction Targets

Given a mean telemetry sampling interval $\Delta t \approx 5.45$ seconds:

| Target Name | Forecast Horizon | Sample Offset ($h$) | Target Expression | Operational Use Case |
|---|---|---|---|---|
| `target_15s` | **15 seconds** | $h = 3$ samples | $Y(t + 3 \Delta t)$ | Short-term surge detection & immediate pod warm-up |
| `target_30s` | **30 seconds** | $h = 6$ samples | $Y(t + 6 \Delta t)$ | Medium-term proactive scaling decision lead time |
| `target_60s` | **60 seconds** | $h = 12$ samples | $Y(t + 12 \Delta t)$ | Long-term trend forecasting & multi-step pod scaling |

---

## 3. Feature Matrix Specification ($\mathbf{X}_t$)

All features are strictly derived from observations available at or prior to time $t$:

| Feature Name | Type | Formula / Derivation | Causal Justification |
|---|---|---|---|
| `rps_current` | Lag 0 | $RPS_t$ | Instantaneous current workload rate |
| `rps_lag1` | Lag 1 | $RPS_{t-1}$ (1 sample ago) | Short-term workload velocity |
| `rps_lag2` | Lag 2 | $RPS_{t-2}$ (2 samples ago) | Historical momentum |
| `rps_lag3` | Lag 3 | $RPS_{t-3}$ (~15s ago) | 15-second historical baseline |
| `rps_lag6` | Lag 6 | $RPS_{t-6}$ (~30s ago) | 30-second historical baseline |
| `cpu_lag0` | Lag 0 | $CPU\%_t$ | Current CPU utilization % |
| `cpu_lag1` | Lag 1 | $CPU\%_{t-1}$ | Immediate CPU utilization trend |
| `rps_roll_mean_3` | Rolling Stat | $\frac{1}{3} \sum_{i=0}^2 RPS_{t-i}$ | 15s smoothed average workload |
| `rps_roll_mean_6` | Rolling Stat | $\frac{1}{6} \sum_{i=0}^5 RPS_{t-i}$ | 30s smoothed average workload |
| `rps_roll_max_6` | Rolling Stat | $\max_{i=0..5}(RPS_{t-i})$ | 30s peak workload burst memory |
| `rps_roll_std_6` | Rolling Stat | $\text{std}_{i=0..5}(RPS_{t-i})$ | Recent workload volatility |
| `rps_slope_3` | Difference | $RPS_t - RPS_{t-3}$ | 15s workload acceleration slope |
| `current_replicas` | Status | $N_t$ | Active pod capacity state |

---

## 4. Strict Non-Leakage Guarantees

To ensure scientific validity and real-world deployability:
1. No future RPS ($RPS_{t+k}$ for $k > 0$) is included in $\mathbf{X}_t$.
2. No future CPU utilization or future replica status is included in $\mathbf{X}_t$.
3. Feature normalization parameters (means, standard deviations) are computed exclusively on training data and applied to test sets.

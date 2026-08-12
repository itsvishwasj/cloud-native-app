# Time-Series Baseline Data Analysis Report

This report analyzes the empirical statistical properties of the 5 baseline time-series datasets (`baseline_constant_001`, `baseline_step_001`, `baseline_spike_001`, `baseline_sustained_001`, `baseline_recovery_001`) to inform feature engineering and model selection for the proposed workload predictor.

---

## 1. Dataset Overview & Sampling Characteristics

- **Total Usable Samples**: **269 samples**
- **Total Time Span**: **1,469.16 seconds (~24.5 minutes)**
- **Mean Sampling Frequency**: **5.45 seconds per sample**
- **Completeness**: 100% (0 missing values, 0 NaN values, 0 duplicate timestamps)

---

## 2. Workload Dynamics & Pattern Analysis

The baseline datasets capture five distinct operational workload patterns:
1. **Constant Load**: Low variance around 5 RPS steady-state.
2. **Step Increase**: Non-stationary step transitions (2 → 6 → 12 → 16 RPS).
3. **Spike Load**: Severe non-stationary burst (2 RPS → 18 RPS spike → 2 RPS).
4. **Sustained High Load**: High-volume load (14 RPS) driving cluster scaling to `maxReplicas: 10`.
5. **Load Decrease / Recovery**: Step-wise load drop (15 → 8 → 2 RPS) testing scale-down inertia.

---

## 3. Autocorrelation & Time Dependence

Autocorrelation function (ACF) of `request_rate_rps`:

| Lag (# Samples) | Time Horizon | Autocorrelation ($r$) | Interpretation |
|---|---|---|---|
| Lag 1 | 5.45 seconds | **0.9283** | Extremely high short-term persistence |
| Lag 2 | 10.90 seconds | **0.8642** | Strong local trend continuation |
| Lag 3 | 16.35 seconds | **0.8040** | High predictability at 15s horizon |
| Lag 6 | 32.70 seconds | **0.6328** | Moderate predictability at 30s horizon |
| Lag 12 | 65.40 seconds | **0.3105** | Decay at 60s horizon requiring trend features |

---

## 4. Cross-Correlation Analysis

### A. Workload vs. CPU Utilization
- **Peak Correlation**: $r = 0.6657$ at Shift 0s ($r = 0.5547$ at Shift -5s).
- **Finding**: Incoming RPS is the direct causal driver of container CPU core consumption.

### B. Workload vs. HPA Desired Replicas
- **Peak Correlation**: $r = 0.6364$ at Shift 0s, decaying to $r = 0.4257$ at Shift +25s.
- **Finding**: HPA target calculation reacts after RPS surges occur, creating a decision lag window.

---

## 5. Implications for Forecasting Model Design

1. **Short Horizons (15s / 30s)**: Strong autocorrelation ($r > 0.63$) indicates lag features ($RPS_{t-1}, RPS_{t-2}, RPS_{t-3}$) and rolling means will provide strong predictive power.
2. **Long Horizon (60s)**: Lower autocorrelation ($r = 0.31$) requires slope ($\Delta RPS$), rolling maximums, and multi-step lag features to anticipate trajectory shifts.
3. **Non-Linear Spikes**: Spike and step transitions require non-linear regression models (Random Forest, Gradient Boosting / XGBoost) capable of modeling non-stationary threshold shifts without overfitting.

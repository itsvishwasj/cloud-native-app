# Final Workload Predictor Mathematical Definition

This document provides the exact mathematical definition, smoothing equations, and horizon-specific parameters for the final selected workload prediction model: the **Trend-Adjusted Exponential Moving Average Predictor (EMA-TAP)**.

---

## 1. Mathematical Formulation

The prediction model calculates future incoming request rate ($\hat{Y}_{t+h}$) at time $t$ for forecasting horizon $h \in \{15\text{s}, 30\text{s}, 60\text{s}\}$ using a two-stage filter:

### Stage 1: Exponential Moving Average (EMA) Smoothing
To prevent instantaneous measurement noise in Prometheus metrics from causing false trend extrapolation:
$$\text{EMA}_t = \alpha \cdot \text{RPS}_t + (1 - \alpha) \cdot \text{EMA}_{t-1}$$
*Where $\alpha = 0.50$ is the smoothing factor, and $\text{EMA}_0 = \text{RPS}_0$.*

### Stage 2: 15-Second Workload Momentum ($\Delta \text{RPS}_t$)
$$\Delta \text{RPS}_t = \text{EMA}_t - \text{EMA}_{t-3}$$
*Where $t-3$ represents the telemetry observation approximately 15 seconds prior ($\Delta t \approx 5.45\text{s}$).*

### Stage 3: Horizon-Adjusted Forecast Equation
$$\hat{Y}_{t+h} = \max\left(0.0, \, \text{RPS}_t + \beta_h \cdot \Delta \text{RPS}_t\right)$$

---

## 2. Horizon-Specific Hyperparameters ($\beta_h$)

| Horizon ($h$) | Time Lead | Sample Offset | $\beta_h$ Weight | Rationalization |
|---|---|---|---|---|
| **15 seconds** | 16.35s | $+3$ samples | $\beta_{15\text{s}} = 0.50$ | High short-term momentum extrapolation during rapid scale-up |
| **30 seconds** | 32.70s | $+6$ samples | $\beta_{30\text{s}} = 0.25$ | Moderated momentum extrapolation to match HPA control loop lead time |
| **60 seconds** | 65.40s | $+12$ samples | $\beta_{60\text{s}} = 0.00$ | Pure inertia persistence ($\hat{Y}_{t+60\text{s}} = \text{RPS}_t$) due to trend decay at 60s |

---

## 3. Real-Time Causal Guarantees

1. The calculation of $\text{EMA}_t$ depends strictly on current and historical RPS values ($\text{RPS}_i$ for $i \le t$).
2. No future metrics ($RPS_{t+k}$ for $k > 0$) are used in features or calculations.
3. Negative predictions are bounded at 0.0 using $\max(0.0, \cdot)$.

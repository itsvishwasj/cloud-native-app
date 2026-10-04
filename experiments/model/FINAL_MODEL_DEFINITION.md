# Final Workload Predictor Mathematical Definition

This document provides the exact mathematical definition, smoothing equations, parameter-selection methodology, and deployed parameters for the final selected workload prediction model: the **Trend-Adjusted Exponential Moving Average Predictor (EMA-TAP)**.

---

## 1. Mathematical Formulation

The prediction model calculates future incoming request rate ($\hat{Y}_{t+h}$) at time $t$ for forecasting horizon $h \in \{15\text{s}, 30\text{s}, 60\text{s}\}$ using a two-stage time-series filter.

### Stage 1: Exponential Moving Average (EMA) Smoothing

To reduce instantaneous measurement noise in Prometheus metrics before trend extrapolation:

$$
\text{EMA}_t =
\alpha \cdot \text{RPS}_t
+
(1-\alpha)\cdot\text{EMA}_{t-1}
$$

where:

- $\alpha$ is the EMA smoothing factor.
- $\text{EMA}_0 = \text{RPS}_0$.
- A larger $\alpha$ gives greater weight to the most recent workload observation.

For the deployed predictive scaling controller, the control-oriented smoothing parameter is:

$$
\boxed{\alpha = 0.90}
$$

This value was selected through validation-based parameter tuning because the controller uses the 30-second prediction as its primary scaling horizon.

---

## 2. Workload Momentum

The short-term workload momentum is calculated using the difference between the current EMA and the EMA three telemetry samples earlier:

$$
\Delta \text{RPS}_t =
\text{EMA}_t-\text{EMA}_{t-3}
$$

The telemetry interval is approximately:

$$
\Delta t \approx 5.45\text{ s}
$$

Therefore, the three-sample momentum window corresponds to approximately:

$$
3\times5.45 \approx 16.35\text{ s}
$$

This provides a short-term estimate of whether workload is increasing or decreasing.

---

## 3. Horizon-Adjusted Forecast Equation

The predicted future workload is:

$$
\hat{Y}_{t+h}
=
\max
\left(
0.0,\,
\text{RPS}_t+
\beta_h\Delta\text{RPS}_t
\right)
$$

where $\beta_h$ controls the amount of short-term momentum applied to each forecasting horizon.

The $\max(0.0,\cdot)$ operation ensures that predicted request rate cannot become negative.

---

## 4. Parameter Selection Methodology

The EMA-TAP parameters were not selected arbitrarily.

A grid-search procedure was used to evaluate:

- EMA smoothing factor $\alpha \in \{0.1,0.2,\ldots,0.9\}$
- Momentum weight $\beta \in \{0.0,0.1,\ldots,1.0\}$

This gives:

$$
9\times11=99
$$

parameter combinations evaluated for each forecasting horizon.

### Selection criterion

Parameters were selected using the validation workload:

**Validation workload:** `baseline_sustained_001`

The primary selection metric was:

$$
\text{Minimum MAE}
$$

with RMSE used as the tie-breaker.

The unseen test workload:

**Test workload:** `baseline_recovery_001`

was not used during parameter tuning.

---

## 5. Validation-Selected Parameters

The grid search produced the following horizon-specific parameter combinations:

| Horizon | Selected $\alpha$ | Selected $\beta$ | Validation MAE | Validation RMSE |
|---|---:|---:|---:|---:|
| **15s** | **0.10** | **0.00** | **2.0138** | **2.9309** |
| **30s** | **0.90** | **0.10** | **2.6411** | **3.3486** |
| **60s** | **0.50** | **0.80** | **3.6095** | **4.7396** |

These values are the results of the validation parameter search and are therefore different from the original manually specified parameters.

---

## 6. Deployed Controller Configuration

The predictive autoscaling controller uses the **30-second horizon as its primary control horizon**.

Therefore, the deployed controller uses:

$$
\boxed{\alpha=0.90}
$$

and:

| Horizon | $\beta_h$ |
|---|---:|
| **15s** | **0.50** |
| **30s** | **0.10** |
| **60s** | **0.00** |

The 30-second control configuration is therefore:

$$
\boxed{
\alpha=0.90,\quad
\beta_{30s}=0.10
}
$$

This configuration is the one used by the predictive scaling controller for its replica calculation.

The horizon-specific validation search and the deployed controller configuration should therefore be distinguished: the search identifies the best parameter pair for each individual forecasting horizon, while the deployed controller is configured around its 30-second scaling decision horizon.

---

## 7. Test-Set Comparison

The tuned parameters were evaluated on the unseen `baseline_recovery_001` test workload.

| Horizon | Original MAE | Tuned MAE | Original RMSE | Tuned RMSE | Original $R^2$ | Tuned $R^2$ |
|---|---:|---:|---:|---:|---:|---:|
| **15s** | 1.4610 | **1.2803** | 1.9483 | **1.8578** | 0.4300 | **0.4817** |
| **30s** | 2.1164 | **2.1124** | 2.5844 | **2.5840** | -0.0401 | **-0.0398** |
| **60s** | **2.9506** | 3.0568 | **3.5125** | 3.6188 | **-1.0221** | -1.1463 |

The results show that tuning improved the 15-second forecast substantially and produced a small improvement at 30 seconds. The tuned 60-second configuration did not improve the unseen recovery workload.

This result is retained rather than selectively reporting only improvements, because the test workload was not used for parameter selection.

---

## 8. Real-Time Causal Guarantees

1. The calculation of $\text{EMA}_t$ depends strictly on current and historical RPS values.
2. No future metrics ($RPS_{t+k}$ for $k>0$) are used during prediction.
3. The model uses only information available at prediction time.
4. Negative predictions are bounded at 0.0 using $\max(0.0,\cdot)$.
5. The test workload is isolated from parameter tuning.

---

## 9. Reproducibility

The parameter search is implemented in:

`experiments/model/parameter_tuning.py`

The selected tuning results are stored in:

`experiments/model/parameter_tuning_results.csv`

The tuned deployment configuration is stored in:

`experiments/model/artifacts/tuned_trend_predictor_config.json`

The final test comparison is stored in:

`experiments/model/tuned_vs_original_results.csv`

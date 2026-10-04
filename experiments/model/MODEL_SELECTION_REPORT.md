# Workload Prediction Model Selection Report

This report summarizes the empirical benchmark evaluation, trade-off analysis, parameter tuning, and selection justification for the proposed workload prediction model.

---

## 1. Executive Benchmark Results

Evaluated across 269 baseline time-series samples split chronologically into Training/Validation and Test workloads.

The test workload represents an unseen Step-Down Recovery trajectory.

| Model Name | Horizon | MAE | RMSE | MAPE (%) | $R^2$ Score | Inference Latency (ms) |
|---|---|---:|---:|---:|---:|---:|
| **Persistence (Baseline 1)** | **15s** | **1.2803** | **1.8578** | **201.24%** | **0.4817** | **0.0216 ms** |
| Trend Extrapolation (Baseline 3) | 15s | 1.6693 | 2.1042 | 294.30% | 0.3352 | 0.0021 ms |
| Moving Average (Baseline 2) | 15s | 1.8273 | 2.2445 | 358.64% | 0.2436 | 0.0014 ms |
| Ridge Regression | 15s | 2.1945 | 2.6424 | 583.83% | -0.0484 | 0.0096 ms |
| XGBoost | 15s | 2.3487 | 2.9298 | 716.89% | -0.2889 | 0.0220 ms |
| Random Forest | 15s | 2.3929 | 2.9431 | 661.84% | -0.3007 | 0.0322 ms |
| **Persistence (Baseline 1)** | **30s** | **2.0832** | **2.5835** | **392.57%** | **-0.0393** | **0.0010 ms** |
| Trend Extrapolation (Baseline 3) | 30s | 2.3780 | 2.7582 | 456.80% | -0.1847 | 0.0017 ms |
| Moving Average (Baseline 2) | 30s | 2.4264 | 2.8940 | 477.61% | -0.3042 | 0.0007 ms |
| Ridge Regression | 30s | 2.9137 | 3.5356 | 627.37% | -0.9466 | 0.0074 ms |
| XGBoost | 30s | 3.2605 | 3.8429 | 843.33% | -1.2996 | 0.0200 ms |
| Random Forest | 30s | 3.6181 | 4.1195 | 815.83% | -1.6426 | 0.0325 ms |
| **Persistence (Baseline 1)** | **60s** | **2.9506** | **3.5125** | **447.07%** | **-1.0221** | **0.0003 ms** |
| Moving Average (Baseline 2) | 60s | 2.9866 | 3.4892 | 369.88% | -0.9953 | 0.0007 ms |
| Trend Extrapolation (Baseline 3) | 60s | 3.1459 | 3.7922 | 498.13% | -1.3569 | 0.0019 ms |
| XGBoost | 60s | 4.2522 | 4.9053 | 850.38% | -2.9436 | 0.0206 ms |
| Ridge Regression | 60s | 4.4144 | 5.3349 | 759.54% | -3.6645 | 0.0078 ms |
| Random Forest | 60s | 5.3797 | 6.1906 | 829.42% | -5.2810 | -5.2810 |

---

## 2. Scientific Trade-Off Analysis

### A. Autocorrelation & Time-Series Persistence

The empirical autocorrelation analysis demonstrated:

$$
r=0.9283
$$

at lag 1 (approximately 5.45s), and:

$$
r=0.8040
$$

at lag 3 (approximately 16.35s).

This indicates strong short-term temporal dependence in the workload traces.

Because the workload contains local inertia together with abrupt step and spike transitions, simple temporal predictors provide a strong baseline. The benchmark therefore evaluates persistence, moving-average, and trend-based predictors alongside supervised machine-learning models.

---

### B. Supervised Machine-Learning Models

Ridge Regression, Random Forest, and XGBoost were evaluated as supervised alternatives.

On the unseen recovery workload, these models produced higher forecasting errors than the simpler time-series baselines for the evaluated horizons.

This indicates that, for the available workload traces, increasing model complexity does not automatically produce better forecasting performance.

---

## 3. EMA-TAP Parameter Tuning

After model-family evaluation, the Trend-Adjusted Exponential Moving Average Predictor (EMA-TAP) was selected as the lightweight forecasting architecture.

The model contains two tunable parameters:

- EMA smoothing factor $\alpha$
- Momentum coefficient $\beta$

A grid search evaluated:

$$
\alpha\in\{0.1,0.2,\ldots,0.9\}
$$

and:

$$
\beta\in\{0.0,0.1,\ldots,1.0\}
$$

Therefore:

$$
9\times11=99
$$

parameter combinations were evaluated for each forecasting horizon.

### Validation protocol

**Validation workload:** `baseline_sustained_001`

**Test workload:** `baseline_recovery_001`

The test workload was not used during parameter tuning.

The primary selection criterion was minimum MAE, with RMSE used as a tie-breaker.

---

## 4. Selected Validation Parameters

| Horizon | $\alpha$ | $\beta$ | Validation MAE | Validation RMSE |
|---|---:|---:|---:|---:|
| **15s** | **0.10** | **0.00** | **2.0138** | **2.9309** |
| **30s** | **0.90** | **0.10** | **2.6411** | **3.3486** |
| **60s** | **0.50** | **0.80** | **3.6095** | **4.7396** |

These values provide an explicit, reproducible justification for the model parameters rather than relying on manually chosen values.

---

## 5. Unseen-Test Evaluation

The tuned parameters were subsequently evaluated on the unseen `baseline_recovery_001` workload.

| Horizon | Original MAE | Tuned MAE | Original RMSE | Tuned RMSE | Original $R^2$ | Tuned $R^2$ |
|---|---:|---:|---:|---:|---:|---:|
| **15s** | 1.4610 | **1.2803** | 1.9483 | **1.8578** | 0.4300 | **0.4817** |
| **30s** | 2.1164 | **2.1124** | 2.5844 | **2.5840** | -0.0401 | **-0.0398** |
| **60s** | **2.9506** | 3.0568 | **3.5125** | 3.6188 | **-1.0221** | -1.1463 |

The tuned model substantially improves the 15-second prediction and provides a small improvement at the 30-second control horizon.

The 60-second tuned configuration performs worse on the unseen recovery workload. This is reported explicitly to avoid presenting parameter tuning as universally beneficial.

---

## 6. Final Controller Selection

The predictive autoscaling controller uses the **30-second prediction horizon** as its primary scaling decision horizon.

Consequently, the deployed EMA-TAP configuration uses:

$$
\boxed{\alpha=0.90}
$$

with:

$$
\boxed{\beta_{30s}=0.10}
$$

The deployed beta configuration is:

| Horizon | Beta |
|---|---:|
| 15s | 0.50 |
| **30s** | **0.10** |
| 60s | 0.00 |

The distinction between the parameter-search results and the deployed controller configuration is intentional:

- the grid search evaluates each forecasting horizon independently;
- the controller makes its scaling decision using the 30-second horizon;
- therefore the deployed configuration is optimized around the controller's 30-second decision horizon.

---

## 7. Selection Justification

EMA-TAP was selected because it provides:

1. Explicit temporal modelling through EMA smoothing.
2. Short-term trend information through the momentum term.
3. Extremely low computational complexity.
4. Deterministic inference.
5. Causal prediction using only currently available and historical telemetry.
6. A reproducible parameter-selection procedure.
7. A direct interface with the Kubernetes predictive scaling controller.

The final system therefore prioritizes a lightweight, interpretable time-series predictor rather than selecting a more complex model solely because it has more parameters.

---

## 8. Reproducibility

Parameter tuning is implemented in:

`experiments/model/parameter_tuning.py`

The parameter-search results are stored in:

`experiments/model/parameter_tuning_results.csv`

The tuned deployment configuration is stored in:

`experiments/model/artifacts/tuned_trend_predictor_config.json`

The original-versus-tuned test comparison is stored in:

`experiments/model/tuned_vs_original_results.csv`

The mathematical definition of the deployed predictor is documented in:

`experiments/model/FINAL_MODEL_DEFINITION.md`

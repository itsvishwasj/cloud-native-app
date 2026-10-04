#!/usr/bin/env python3
"""
Real-Time Inference Interface for Workload Prediction Service.

Callable by the proposed predictive autoscaling controller.

Model:
    EMA-TAP
    Trend-Adjusted Exponential Moving Average Predictor

Current tuned configuration:
    alpha = 0.90
    momentum lag = 3 samples

    beta_15s = 0.50
    beta_30s = 0.10
    beta_60s = 0.00

The 30-second configuration is the primary configuration used
by the predictive autoscaling controller for replica calculation.
"""

import os
import sys
import json

import pandas as pd
import numpy as np


# ============================================================
# PATH CONFIGURATION
# ============================================================

MODEL_DIR = os.path.dirname(os.path.abspath(__file__))

CONFIG_PATH = os.path.join(
    MODEL_DIR,
    "artifacts",
    "trend_predictor_config.json"
)


# ============================================================
# WORKLOAD PREDICTOR
# ============================================================

class WorkloadPredictor:
    """
    EMA-TAP workload prediction service.

    EMA:
        EMA_t = alpha * RPS_t
                + (1 - alpha) * EMA_(t-1)

    Trend:
        Delta_RPS = EMA_t - EMA_(t-lag)

    Prediction:
        Y_hat = RPS_current + beta * Delta_RPS

    The prediction is clipped at zero because request rate
    cannot be negative.
    """

    def __init__(self, config_file=CONFIG_PATH):

        # ----------------------------------------------------
        # Load configuration artifact
        # ----------------------------------------------------

        if os.path.exists(config_file):

            with open(
                config_file,
                "r",
                encoding="utf-8"
            ) as f:

                self.config = json.load(f)

        else:

            # ------------------------------------------------
            # Tuned fallback configuration
            #
            # This is intentionally kept consistent with the
            # configuration artifact.
            # ------------------------------------------------

            self.config = {
                "model_name":
                    "EMA-TAP "
                    "(Trend-Adjusted Exponential Moving "
                    "Average Predictor)",

                "version": "1.1.0",

                "alpha_smoothing": 0.90,

                "momentum_lag_samples": 3,

                "beta_weights": {
                    "15s": 0.50,
                    "30s": 0.10,
                    "60s": 0.00
                },

                "sampling_interval_seconds": 5.45,

                "features_required": [
                    "rps_current",
                    "rps_lag3"
                ],

                "is_deterministic": True
            }

        # ----------------------------------------------------
        # Read configuration values
        # ----------------------------------------------------

        self.alpha = float(
            self.config.get(
                "alpha_smoothing",
                0.90
            )
        )

        self.lag = int(
            self.config.get(
                "momentum_lag_samples",
                3
            )
        )

        self.beta = self.config.get(
            "beta_weights",
            {
                "15s": 0.50,
                "30s": 0.10,
                "60s": 0.00
            }
        )


    # ========================================================
    # EMA-TAP PREDICTION
    # ========================================================

    def predict(self, recent_samples_df):
        """
        Predict future workload for 15s, 30s and 60s horizons.

        Parameters
        ----------
        recent_samples_df : pandas.DataFrame

            Must contain:

                request_rate_rps

            Recommended minimum:
                4 samples

        Returns
        -------
        dict

            {
                "predicted_rps_15s": ...,
                "predicted_rps_30s": ...,
                "predicted_rps_60s": ...
            }
        """

        # ----------------------------------------------------
        # Empty telemetry
        # ----------------------------------------------------

        if recent_samples_df is None:

            return {
                "predicted_rps_15s": 0.0,
                "predicted_rps_30s": 0.0,
                "predicted_rps_60s": 0.0
            }


        if recent_samples_df.empty:

            return {
                "predicted_rps_15s": 0.0,
                "predicted_rps_30s": 0.0,
                "predicted_rps_60s": 0.0
            }


        # ----------------------------------------------------
        # Validate required column
        # ----------------------------------------------------

        if "request_rate_rps" not in recent_samples_df.columns:

            raise ValueError(
                "Input DataFrame must contain "
                "'request_rate_rps' column."
            )


        # ----------------------------------------------------
        # Extract RPS history
        # ----------------------------------------------------

        rps_series = (
            recent_samples_df["request_rate_rps"]
            .astype(float)
            .values
        )


        # Remove invalid values
        rps_series = np.nan_to_num(
            rps_series,
            nan=0.0,
            posinf=0.0,
            neginf=0.0
        )


        # RPS cannot be negative
        rps_series = np.maximum(
            rps_series,
            0.0
        )


        # ----------------------------------------------------
        # Insufficient history
        # ----------------------------------------------------

        if len(rps_series) < self.lag + 1:

            current_rps = float(
                rps_series[-1]
            )

            return {
                "predicted_rps_15s":
                    round(current_rps, 2),

                "predicted_rps_30s":
                    round(current_rps, 2),

                "predicted_rps_60s":
                    round(current_rps, 2)
            }


        # ----------------------------------------------------
        # Calculate EMA
        # ----------------------------------------------------

        ema = np.zeros(
            len(rps_series),
            dtype=float
        )

        # Initial EMA
        ema[0] = rps_series[0]


        # Recursive EMA calculation
        for t in range(
            1,
            len(rps_series)
        ):

            ema[t] = (
                self.alpha * rps_series[t]
                +
                (1.0 - self.alpha) * ema[t - 1]
            )


        # ----------------------------------------------------
        # Current workload
        # ----------------------------------------------------

        current_rps = float(
            rps_series[-1]
        )


        # ----------------------------------------------------
        # Trend / momentum component
        #
        # Delta_RPS =
        #     EMA_current - EMA_lagged
        # ----------------------------------------------------

        ema_now = float(
            ema[-1]
        )

        ema_lag = float(
            ema[-1 - self.lag]
        )

        delta_rps = (
            ema_now
            -
            ema_lag
        )


        # ----------------------------------------------------
        # Get beta parameters
        # ----------------------------------------------------

        beta_15 = float(
            self.beta.get(
                "15s",
                0.50
            )
        )

        beta_30 = float(
            self.beta.get(
                "30s",
                0.10
            )
        )

        beta_60 = float(
            self.beta.get(
                "60s",
                0.00
            )
        )


        # ----------------------------------------------------
        # EMA-TAP predictions
        # ----------------------------------------------------

        pred_15s = (
            current_rps
            +
            beta_15 * delta_rps
        )

        pred_30s = (
            current_rps
            +
            beta_30 * delta_rps
        )

        pred_60s = (
            current_rps
            +
            beta_60 * delta_rps
        )


        # ----------------------------------------------------
        # RPS cannot be negative
        # ----------------------------------------------------

        pred_15s = max(
            0.0,
            pred_15s
        )

        pred_30s = max(
            0.0,
            pred_30s
        )

        pred_60s = max(
            0.0,
            pred_60s
        )


        # ----------------------------------------------------
        # Return predictions
        # ----------------------------------------------------

        return {

            "predicted_rps_15s":
                round(
                    float(pred_15s),
                    2
                ),

            "predicted_rps_30s":
                round(
                    float(pred_30s),
                    2
                ),

            "predicted_rps_60s":
                round(
                    float(pred_60s),
                    2
                )
        }


# ============================================================
# CONFIGURATION DISPLAY
# ============================================================

def print_configuration(predictor):
    """
    Print the configuration actually loaded by the
    prediction service.
    """

    print("=" * 65)
    print("EMA-TAP WORKLOAD PREDICTOR CONFIGURATION")
    print("=" * 65)

    print(
        f"Model              : "
        f"{predictor.config.get('model_name', 'EMA-TAP')}"
    )

    print(
        f"Version            : "
        f"{predictor.config.get('version', 'unknown')}"
    )

    print(
        f"Alpha smoothing    : "
        f"{predictor.alpha:.2f}"
    )

    print(
        f"Momentum lag       : "
        f"{predictor.lag} samples"
    )

    print(
        f"Beta 15s           : "
        f"{predictor.beta.get('15s', 0.50):.2f}"
    )

    print(
        f"Beta 30s           : "
        f"{predictor.beta.get('30s', 0.10):.2f}"
    )

    print(
        f"Beta 60s           : "
        f"{predictor.beta.get('60s', 0.00):.2f}"
    )

    print(
        f"Sampling interval  : "
        f"{predictor.config.get('sampling_interval_seconds', 5.45)} s"
    )

    print("=" * 65)


# ============================================================
# TEST / DEMO
# ============================================================

def main():

    # --------------------------------------------------------
    # Example telemetry
    # --------------------------------------------------------

    sample_telemetry = pd.DataFrame(
        [
            {"request_rate_rps": 2.0},
            {"request_rate_rps": 4.0},
            {"request_rate_rps": 8.0},
            {"request_rate_rps": 12.0},
        ]
    )


    # --------------------------------------------------------
    # Create predictor
    # --------------------------------------------------------

    predictor = WorkloadPredictor()


    # --------------------------------------------------------
    # Display loaded configuration
    # --------------------------------------------------------

    print_configuration(
        predictor
    )


    # --------------------------------------------------------
    # Run prediction
    # --------------------------------------------------------

    predictions = predictor.predict(
        sample_telemetry
    )


    # --------------------------------------------------------
    # Display inference result
    # --------------------------------------------------------

    print()
    print("=" * 65)
    print("REAL-TIME INFERENCE SERVICE TEST")
    print("=" * 65)

    print(
        f"Input Current RPS   : "
        f"{sample_telemetry['request_rate_rps'].iloc[-1]}"
    )

    print(
        "Input RPS History   : "
        f"{sample_telemetry['request_rate_rps'].tolist()}"
    )

    print(
        f"EMA Alpha           : "
        f"{predictor.alpha:.2f}"
    )

    print(
        f"Momentum Lag        : "
        f"{predictor.lag} samples"
    )

    print(
        f"Predicted 15s RPS   : "
        f"{predictions['predicted_rps_15s']}"
    )

    print(
        f"Predicted 30s RPS   : "
        f"{predictions['predicted_rps_30s']}"
    )

    print(
        f"Predicted 60s RPS   : "
        f"{predictions['predicted_rps_60s']}"
    )

    print("=" * 65)


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()

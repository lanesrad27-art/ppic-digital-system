"""
ets_forecaster.py
Forecasting ETS / Holt-Winters (Exponential Smoothing).
  - trend="add"
  - seasonal="add" bila data cukup (>= 24 titik) -> seasonal_periods=12
  - bila data < 24 titik: trend-only (tanpa musiman)
  - evaluasi out-of-sample (train/test)
"""

from __future__ import annotations

import logging
import warnings
from typing import Optional

import numpy as np

from modules.forecasting_metrics import evaluate_forecast

logger = logging.getLogger("ppic.ets")
warnings.filterwarnings("ignore")

try:
    from statsmodels.tsa.holtwinters import ExponentialSmoothing
    _HAS_SM = True
except ImportError:  # pragma: no cover
    _HAS_SM = False
    logger.warning("statsmodels tidak tersedia; ETS dinonaktifkan.")

MODEL_NAME = "ETS / Holt-Winters"
_SEASONAL_MIN_POINTS = 24
_SEASONAL_PERIODS = 12


def _make_model(series, seasonal: bool):
    """Bangun objek ExponentialSmoothing sesuai ketersediaan musiman."""
    s = np.asarray(series, dtype=float)
    if seasonal and len(s) >= _SEASONAL_MIN_POINTS:
        return ExponentialSmoothing(
            s, trend="add", seasonal="add",
            seasonal_periods=_SEASONAL_PERIODS,
            initialization_method="estimated",
        )
    # trend-only
    return ExponentialSmoothing(
        s, trend="add", seasonal=None, initialization_method="estimated"
    )


def train_ets_model(series):
    """Latih model ETS. Return fitted model atau None."""
    s = np.asarray(series, dtype=float)
    if not _HAS_SM or len(s) < 4:
        return None
    seasonal = len(s) >= _SEASONAL_MIN_POINTS
    try:
        return _make_model(s, seasonal).fit()
    except Exception as e:  # noqa: BLE001
        logger.error("train_ets_model gagal (seasonal=%s): %s", seasonal, e)
        # Fallback ke trend-only bila seasonal gagal.
        try:
            return _make_model(s, seasonal=False).fit()
        except Exception as e2:  # noqa: BLE001
            logger.error("train_ets_model trend-only juga gagal: %s", e2)
            return None


def evaluate_ets(series, test_size: Optional[int] = None) -> dict:
    """Evaluasi out-of-sample ETS."""
    s = np.asarray(series, dtype=float)
    n = len(s)
    if not _HAS_SM or n < 6:
        return {}
    if test_size is None:
        test_size = max(2, min(6, int(round(n * 0.2))))
    train, test = s[:-test_size], s[-test_size:]
    try:
        seasonal = len(train) >= _SEASONAL_MIN_POINTS
        fitted = _make_model(train, seasonal).fit()
        preds = np.asarray(fitted.forecast(len(test)), dtype=float)
        return evaluate_forecast(test, preds)
    except Exception as e:  # noqa: BLE001
        logger.error("evaluate_ets gagal: %s", e)
        return {}


def forecast_ets(series, horizon: int = 6) -> dict:
    """Latih ETS pada seluruh data lalu forecast `horizon` periode ke depan."""
    s = np.asarray(series, dtype=float)
    if not _HAS_SM:
        return {"error": "statsmodels tidak tersedia.", "model_name": MODEL_NAME}
    if len(s) < 4:
        return {"error": "Data tidak cukup untuk ETS (min 4 titik).",
                "model_name": MODEL_NAME}
    fitted = train_ets_model(s)
    if fitted is None:
        return {"error": "Gagal melatih model ETS.", "model_name": MODEL_NAME}
    try:
        forecast = np.asarray(fitted.forecast(horizon), dtype=float)
        forecast = np.clip(forecast, 0, None)
        seasonal_used = len(s) >= _SEASONAL_MIN_POINTS
        return {
            "model_name": MODEL_NAME,
            "forecast": forecast.tolist(),
            "lower_ci": [],
            "upper_ci": [],
            "seasonal": seasonal_used,
            "metrics": evaluate_ets(s),
        }
    except Exception as e:  # noqa: BLE001
        logger.error("forecast_ets gagal: %s", e)
        return {"error": "Gagal menjalankan ETS pada data ini.",
                "model_name": MODEL_NAME}

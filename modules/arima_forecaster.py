"""
arima_forecaster.py
Forecasting ARIMA dengan:
  - auto order selection berdasarkan AIC
  - ADF test (cek stasioneritas)
  - forecast future + confidence interval (penanganan conf_int robust)
  - evaluasi train/test (out-of-sample), bukan hanya MAPE in-sample

Tidak bergantung pada Streamlit. Aman dipakai di test/CLI.
"""

from __future__ import annotations

import logging
import warnings
from typing import Optional

import numpy as np
import pandas as pd

from modules.forecasting_metrics import evaluate_forecast

logger = logging.getLogger("ppic.arima")
warnings.filterwarnings("ignore")

try:
    from statsmodels.tsa.arima.model import ARIMA
    from statsmodels.tsa.stattools import adfuller
    _HAS_SM = True
except ImportError:  # pragma: no cover
    _HAS_SM = False
    logger.warning("statsmodels tidak tersedia; ARIMA dinonaktifkan.")

MODEL_NAME = "ARIMA"


def adf_test(series) -> dict:
    """Augmented Dickey-Fuller test. Return statistik & apakah stasioner."""
    s = np.asarray(series, dtype=float)
    if not _HAS_SM or len(s) < 6:
        return {"stationary": False, "pvalue": None, "adf_stat": None}
    try:
        result = adfuller(s, autolag="AIC")
        return {
            "adf_stat": float(result[0]),
            "pvalue": float(result[1]),
            "stationary": bool(result[1] < 0.05),
        }
    except Exception as e:  # noqa: BLE001
        logger.error("adf_test gagal: %s", e)
        return {"stationary": False, "pvalue": None, "adf_stat": None}


def _best_arima_order(series, max_p: int = 3, max_d: int = 2, max_q: int = 3):
    """Pilih order (p,d,q) terbaik dengan grid search berdasarkan AIC."""
    s = np.asarray(series, dtype=float)
    best_aic = np.inf
    best_order = (1, 1, 1)
    for p in range(max_p + 1):
        for d in range(max_d + 1):
            for q in range(max_q + 1):
                if p == 0 and q == 0:
                    continue
                try:
                    model = ARIMA(s, order=(p, d, q))
                    fitted = model.fit()
                    if fitted.aic < best_aic:
                        best_aic = fitted.aic
                        best_order = (p, d, q)
                except Exception:  # noqa: BLE001
                    continue
    return best_order, best_aic


def _extract_conf_int(fc_obj) -> tuple[list, list]:
    """Ambil lower/upper CI secara robust (DataFrame atau ndarray)."""
    try:
        conf = fc_obj.conf_int()
    except Exception:  # noqa: BLE001
        return [], []
    if isinstance(conf, pd.DataFrame):
        lower_ci = conf.iloc[:, 0].tolist()
        upper_ci = conf.iloc[:, 1].tolist()
    else:
        conf = np.asarray(conf)
        lower_ci = list(conf[:, 0])
        upper_ci = list(conf[:, 1])
    return lower_ci, upper_ci


def evaluate_arima(series, test_size: Optional[int] = None) -> dict:
    """
    Evaluasi out-of-sample: latih di train, prediksi sepanjang test.
    test_size default = min(6, 20% data).
    """
    s = np.asarray(series, dtype=float)
    n = len(s)
    if not _HAS_SM or n < 8:
        return {}
    if test_size is None:
        test_size = max(2, min(6, int(round(n * 0.2))))
    train, test = s[:-test_size], s[-test_size:]
    try:
        order, _ = _best_arima_order(train)
        fitted = ARIMA(train, order=order).fit()
        preds = np.asarray(fitted.forecast(steps=len(test)), dtype=float)
        return evaluate_forecast(test, preds)
    except Exception as e:  # noqa: BLE001
        logger.error("evaluate_arima gagal: %s", e)
        return {}


def forecast_arima(series, horizon: int = 6) -> dict:
    """
    Latih ARIMA pada seluruh data lalu forecast `horizon` periode ke depan.
    Return dict: forecast, lower_ci, upper_ci, order, aic, adf, metrics, model_name.
    """
    s = np.asarray(series, dtype=float)
    if not _HAS_SM:
        return {"error": "statsmodels tidak tersedia.", "model_name": MODEL_NAME}
    if len(s) < 6:
        return {"error": "Data tidak cukup untuk ARIMA (min 6 titik).",
                "model_name": MODEL_NAME}
    try:
        adf = adf_test(s)
        order, aic = _best_arima_order(s)
        fitted = ARIMA(s, order=order).fit()
        fc_obj = fitted.get_forecast(steps=horizon)
        forecast = np.asarray(fc_obj.predicted_mean, dtype=float)
        forecast = np.clip(forecast, 0, None)  # demand tidak negatif
        lower_ci, upper_ci = _extract_conf_int(fc_obj)
        lower_ci = list(np.clip(np.asarray(lower_ci, dtype=float), 0, None)) if lower_ci else []
        metrics = evaluate_arima(s)
        return {
            "model_name": MODEL_NAME,
            "forecast": forecast.tolist(),
            "lower_ci": lower_ci,
            "upper_ci": upper_ci,
            "order": order,
            "aic": round(float(aic), 2) if np.isfinite(aic) else None,
            "adf": adf,
            "metrics": metrics,
        }
    except Exception as e:  # noqa: BLE001
        logger.error("forecast_arima gagal: %s", e)
        return {"error": "Gagal menjalankan ARIMA pada data ini.",
                "model_name": MODEL_NAME}

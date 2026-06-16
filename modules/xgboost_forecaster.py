"""
xgboost_forecaster.py
Forecasting berbasis machine learning dengan lag features.
  - Memakai XGBoost bila tersedia; bila tidak, fallback ke
    sklearn.ensemble.GradientBoostingRegressor.
  - Fitur: lag_1, lag_2, lag_3, lag_6, lag_12 (bila cukup),
    rolling_mean_3, rolling_mean_6, rolling_std_3, month, quarter.
  - Forecast future dilakukan secara rolling (recursive).
  - Evaluasi out-of-sample (train/test).
"""

from __future__ import annotations

import logging
from typing import Optional

import numpy as np
import pandas as pd

from modules.forecasting_metrics import evaluate_forecast

logger = logging.getLogger("ppic.xgb")

try:
    from xgboost import XGBRegressor  # type: ignore
    _HAS_XGB = True
except ImportError:  # pragma: no cover
    _HAS_XGB = False

try:
    from sklearn.ensemble import GradientBoostingRegressor
    _HAS_SKLEARN = True
except ImportError:  # pragma: no cover
    _HAS_SKLEARN = False

MODEL_NAME = "XGBoost" if _HAS_XGB else "Gradient Boosting"
_LAGS = [1, 2, 3, 6, 12]
_MIN_POINTS = 8


def _make_regressor():
    """Buat regressor: XGBoost bila ada, fallback GradientBoosting."""
    if _HAS_XGB:
        return XGBRegressor(
            n_estimators=300, max_depth=3, learning_rate=0.05,
            subsample=0.9, random_state=42, verbosity=0,
        )
    if _HAS_SKLEARN:
        return GradientBoostingRegressor(
            n_estimators=300, max_depth=3, learning_rate=0.05, random_state=42
        )
    return None


def create_lag_features(series, start_month: int = 1) -> pd.DataFrame:
    """
    Bangun DataFrame fitur lag + rolling + kalender dari deret demand.
    Baris dengan lag NaN (awal deret) dibuang.
    """
    s = pd.Series(np.asarray(series, dtype=float)).reset_index(drop=True)
    n = len(s)
    df = pd.DataFrame({"y": s})
    usable_lags = [lag for lag in _LAGS if lag < n]
    for lag in usable_lags:
        df[f"lag_{lag}"] = s.shift(lag)
    df["rolling_mean_3"] = s.shift(1).rolling(3, min_periods=1).mean()
    df["rolling_mean_6"] = s.shift(1).rolling(6, min_periods=1).mean()
    df["rolling_std_3"] = s.shift(1).rolling(3, min_periods=1).std().fillna(0)
    # fitur kalender (asumsi data bulanan berurutan)
    months = [((start_month - 1 + i) % 12) + 1 for i in range(n)]
    df["month"] = months
    df["quarter"] = [((m - 1) // 3) + 1 for m in months]
    df = df.dropna().reset_index(drop=True)
    return df


def _feature_cols(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns if c != "y"]


def train_xgb_forecaster(series):
    """Latih regressor pada fitur lag. Return (model, feature_cols) atau (None, [])."""
    reg = _make_regressor()
    if reg is None:
        return None, []
    df = create_lag_features(series)
    if df.empty or len(df) < 3:
        return None, []
    cols = _feature_cols(df)
    try:
        reg.fit(df[cols].values, df["y"].values)
        return reg, cols
    except Exception as e:  # noqa: BLE001
        logger.error("train_xgb_forecaster gagal: %s", e)
        return None, []


def _build_feature_row(history: list[float], idx_month: int, cols: list[str]) -> np.ndarray:
    """Bentuk satu baris fitur dari history terkini (untuk rolling forecast)."""
    s = pd.Series(history, dtype=float)
    feats = {}
    for lag in _LAGS:
        if f"lag_{lag}" in cols:
            feats[f"lag_{lag}"] = s.iloc[-lag] if len(s) >= lag else s.mean()
    feats["rolling_mean_3"] = s.iloc[-3:].mean()
    feats["rolling_mean_6"] = s.iloc[-6:].mean()
    feats["rolling_std_3"] = s.iloc[-3:].std() if len(s) >= 2 else 0.0
    month = ((idx_month - 1) % 12) + 1
    feats["month"] = month
    feats["quarter"] = ((month - 1) // 3) + 1
    return np.array([feats[c] for c in cols], dtype=float).reshape(1, -1)


def forecast_xgb_future(series, horizon: int = 6) -> dict:
    """
    Forecast rolling: prediksi 1 bulan, masukkan ke history, hitung ulang lag,
    ulangi hingga horizon tercapai.
    """
    s = list(np.asarray(series, dtype=float))
    if not (_HAS_XGB or _HAS_SKLEARN):
        return {"error": "xgboost/sklearn tidak tersedia.", "model_name": MODEL_NAME}
    if len(s) < _MIN_POINTS:
        return {"error": f"Data tidak cukup untuk ML model (min {_MIN_POINTS} titik).",
                "model_name": MODEL_NAME}
    model, cols = train_xgb_forecaster(s)
    if model is None:
        return {"error": "Gagal melatih ML model.", "model_name": MODEL_NAME}
    try:
        history = list(s)
        preds = []
        for h in range(horizon):
            row = _build_feature_row(history, len(history) + 1, cols)
            yhat = float(model.predict(row)[0])
            yhat = max(0.0, yhat)
            preds.append(yhat)
            history.append(yhat)
        return {
            "model_name": MODEL_NAME,
            "forecast": preds,
            "lower_ci": [],
            "upper_ci": [],
            "metrics": evaluate_xgb(s),
            "used_xgboost": _HAS_XGB,
        }
    except Exception as e:  # noqa: BLE001
        logger.error("forecast_xgb_future gagal: %s", e)
        return {"error": "Gagal menjalankan ML model pada data ini.",
                "model_name": MODEL_NAME}


def evaluate_xgb(series, test_size: Optional[int] = None) -> dict:
    """Evaluasi out-of-sample dengan rolling forecast pada porsi test."""
    s = list(np.asarray(series, dtype=float))
    n = len(s)
    if not (_HAS_XGB or _HAS_SKLEARN) or n < _MIN_POINTS + 2:
        return {}
    if test_size is None:
        test_size = max(2, min(6, int(round(n * 0.2))))
    train, test = s[:-test_size], s[-test_size:]
    model, cols = train_xgb_forecaster(train)
    if model is None:
        return {}
    try:
        history = list(train)
        preds = []
        for h in range(len(test)):
            row = _build_feature_row(history, len(history) + 1, cols)
            yhat = max(0.0, float(model.predict(row)[0]))
            preds.append(yhat)
            history.append(test[h])  # teacher forcing dengan nilai aktual
        return evaluate_forecast(test, preds)
    except Exception as e:  # noqa: BLE001
        logger.error("evaluate_xgb gagal: %s", e)
        return {}

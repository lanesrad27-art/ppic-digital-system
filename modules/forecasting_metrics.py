"""
forecasting_metrics.py
Metrik evaluasi forecast. Semua metrik dihitung dari demand asli (denormalized),
bukan dari data yang sudah dinormalisasi.
"""

import numpy as np


def _to_arrays(actual, predicted):
    a = np.asarray(actual, dtype=float)
    p = np.asarray(predicted, dtype=float)
    n = min(len(a), len(p))
    return a[:n], p[:n]


def mae(actual, predicted) -> float:
    """Mean Absolute Error."""
    a, p = _to_arrays(actual, predicted)
    if len(a) == 0:
        return 0.0
    return float(np.mean(np.abs(a - p)))


def rmse(actual, predicted) -> float:
    """Root Mean Squared Error."""
    a, p = _to_arrays(actual, predicted)
    if len(a) == 0:
        return 0.0
    return float(np.sqrt(np.mean((a - p) ** 2)))


def mape(actual, predicted) -> float:
    """
    Mean Absolute Percentage Error (%).
    Aman jika ada actual = 0: titik tersebut dilewati.
    """
    a, p = _to_arrays(actual, predicted)
    if len(a) == 0:
        return 0.0
    mask = a != 0
    if mask.sum() == 0:
        return 0.0
    return float(np.mean(np.abs((a[mask] - p[mask]) / a[mask])) * 100)


def smape(actual, predicted) -> float:
    """Symmetric Mean Absolute Percentage Error (%). Aman terhadap pembagian nol."""
    a, p = _to_arrays(actual, predicted)
    if len(a) == 0:
        return 0.0
    denom = (np.abs(a) + np.abs(p))
    mask = denom != 0
    if mask.sum() == 0:
        return 0.0
    return float(np.mean(2.0 * np.abs(p[mask] - a[mask]) / denom[mask]) * 100)


def bias(actual, predicted) -> float:
    """Forecast bias = rata-rata (predicted - actual). Positif = over-forecast."""
    a, p = _to_arrays(actual, predicted)
    if len(a) == 0:
        return 0.0
    return float(np.mean(p - a))


def evaluate_forecast(actual, predicted) -> dict:
    """Hitung semua metrik sekaligus."""
    return {
        "MAE": round(mae(actual, predicted), 4),
        "RMSE": round(rmse(actual, predicted), 4),
        "MAPE": round(mape(actual, predicted), 4),
        "sMAPE": round(smape(actual, predicted), 4),
        "Bias": round(bias(actual, predicted), 4),
    }
<<<<<<< HEAD


def mape_quality(mape_value) -> tuple[str, str]:
    """
    Kategori kualitas forecast berdasarkan MAPE (%).
    Return (label, level); level: good / info / warn / bad untuk pewarnaan UI.
    """
    try:
        m = float(mape_value)
    except (ValueError, TypeError):
        return ("Tidak diketahui", "info")
    if m <= 0:
        return ("Tidak diketahui", "info")
    if m < 10:
        return ("Sangat akurat (<10%)", "good")
    if m < 20:
        return ("Baik (10–20%)", "info")
    if m < 50:
        return ("Cukup (20–50%)", "warn")
    return ("Kurang akurat (>50%)", "bad")
=======
>>>>>>> b9a8ad24d2e85e6ab546af78e0b7f10b26833f82

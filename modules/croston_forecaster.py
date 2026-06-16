"""
croston_forecaster.py
Forecasting untuk intermittent demand (banyak nilai 0), mis. spare part.
  - is_intermittent_demand(data): deteksi pola intermittent (ADI & CV^2)
  - croston_forecast(): metode Croston klasik
  - tsb_forecast(): metode Teunter-Syntetos-Babai (TSB)
  - forecast_intermittent(): pilih otomatis & hasilkan forecast horizon
"""

from __future__ import annotations

import logging

import numpy as np

from modules.forecasting_metrics import evaluate_forecast

logger = logging.getLogger("ppic.croston")

MODEL_NAME = "Croston/TSB"
_ADI_THRESHOLD = 1.32   # ambang klasik intermittent
_CV2_THRESHOLD = 0.49


def is_intermittent_demand(data) -> dict:
    """
    Deteksi apakah deret bersifat intermittent.
      ADI = rata-rata interval antar demand non-nol.
      CV^2 = (std/mean)^2 dari nilai demand non-nol.
    Kategori: smooth / intermittent / erratic / lumpy.
    """
    s = np.asarray(data, dtype=float)
    n = len(s)
    nonzero = s[s > 0]
    zero_ratio = float(np.mean(s == 0)) if n > 0 else 0.0
    if len(nonzero) == 0:
        return {"intermittent": True, "category": "no-demand",
                "adi": None, "cv2": None, "zero_ratio": zero_ratio}
    adi = n / len(nonzero)
    mean_nz = nonzero.mean()
    cv2 = float((nonzero.std() / mean_nz) ** 2) if mean_nz > 0 else 0.0

    intermittent = adi >= _ADI_THRESHOLD
    if adi >= _ADI_THRESHOLD and cv2 < _CV2_THRESHOLD:
        category = "intermittent"
    elif adi >= _ADI_THRESHOLD and cv2 >= _CV2_THRESHOLD:
        category = "lumpy"
    elif adi < _ADI_THRESHOLD and cv2 >= _CV2_THRESHOLD:
        category = "erratic"
    else:
        category = "smooth"

    return {
        "intermittent": bool(intermittent or zero_ratio >= 0.3),
        "category": category,
        "adi": round(adi, 3),
        "cv2": round(cv2, 3),
        "zero_ratio": round(zero_ratio, 3),
    }


def croston_forecast(data, alpha: float = 0.1) -> float:
    """
    Metode Croston klasik. Return level forecast per periode (konstan).
    Memisahkan demand size (z) dan interval (p), keduanya di-smoothing.
    """
    s = np.asarray(data, dtype=float)
    nonzero_idx = np.where(s > 0)[0]
    if len(nonzero_idx) == 0:
        return 0.0
    # inisialisasi
    z = s[nonzero_idx[0]]            # estimasi ukuran demand
    p = 1.0                          # estimasi interval
    last_nonzero = nonzero_idx[0]
    for i in range(nonzero_idx[0] + 1, len(s)):
        if s[i] > 0:
            interval = i - last_nonzero
            z = alpha * s[i] + (1 - alpha) * z
            p = alpha * interval + (1 - alpha) * p
            last_nonzero = i
    return float(z / p) if p > 0 else 0.0


def tsb_forecast(data, alpha: float = 0.1, beta: float = 0.1) -> float:
    """
    Metode TSB (Teunter-Syntetos-Babai). Lebih baik untuk item yang bisa
    berhenti (obsolescence) karena probabilitas demand di-update tiap periode.
    Return level forecast per periode (konstan).
    """
    s = np.asarray(data, dtype=float)
    if len(s) == 0:
        return 0.0
    nonzero = s[s > 0]
    z = nonzero[0] if len(nonzero) > 0 else 0.0   # ukuran demand
    prob = float(np.mean(s > 0))                  # probabilitas demand awal
    for t in range(len(s)):
        if s[t] > 0:
            z = alpha * s[t] + (1 - alpha) * z
            prob = beta * 1 + (1 - beta) * prob
        else:
            prob = beta * 0 + (1 - beta) * prob
    return float(prob * z)


def _eval_constant(series, level: float) -> dict:
    """Evaluasi sederhana: bandingkan level konstan vs aktual (in-sample tail)."""
    s = np.asarray(series, dtype=float)
    if len(s) < 4:
        return {}
    tail = s[-min(6, len(s)):]
    preds = np.full(len(tail), level, dtype=float)
    return evaluate_forecast(tail, preds)


def forecast_intermittent(data, horizon: int = 6, method: str = "auto") -> dict:
    """
    Hasilkan forecast intermittent sepanjang horizon (level konstan per bulan).
      method: 'croston', 'tsb', atau 'auto' (pilih TSB bila banyak nol berturut).
    """
    s = np.asarray(data, dtype=float)
    if len(s) < 4:
        return {"error": "Data tidak cukup untuk Croston/TSB (min 4 titik).",
                "model_name": MODEL_NAME}

    info = is_intermittent_demand(s)
    if method == "auto":
        # TSB lebih cocok untuk kategori lumpy / zero_ratio tinggi.
        method = "tsb" if (info.get("zero_ratio", 0) >= 0.5
                           or info.get("category") == "lumpy") else "croston"

    level = tsb_forecast(s) if method == "tsb" else croston_forecast(s)
    level = max(0.0, float(level))
    forecast = [round(level, 2)] * horizon
    return {
        "model_name": f"{MODEL_NAME} ({method.upper()})",
        "forecast": forecast,
        "lower_ci": [],
        "upper_ci": [],
        "method": method,
        "demand_pattern": info,
        "metrics": _eval_constant(s, level),
    }

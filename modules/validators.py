"""
validators.py
Validasi input untuk perhitungan inventory & forecasting.
Semua fungsi mengembalikan (ok: bool, message: str).
"""

from typing import Tuple, Sequence
import re

_SKU_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9\-_]{1,49}$")


def validate_positive_number(value, name: str = "Nilai") -> Tuple[bool, str]:
    """Pastikan value adalah angka > 0."""
    try:
        v = float(value)
    except (ValueError, TypeError):
        return False, f"{name} harus berupa angka."
    if v <= 0:
        return False, f"{name} harus lebih dari 0."
    return True, ""


def validate_non_negative_number(value, name: str = "Nilai") -> Tuple[bool, str]:
    """Pastikan value adalah angka >= 0."""
    try:
        v = float(value)
    except (ValueError, TypeError):
        return False, f"{name} harus berupa angka."
    if v < 0:
        return False, f"{name} tidak boleh negatif."
    return True, ""


def validate_sku(sku: str) -> Tuple[bool, str]:
    """Validasi format SKU (alfanumerik, -, _; 2-50 karakter)."""
    if not sku or not str(sku).strip():
        return False, "SKU tidak boleh kosong."
    if not _SKU_RE.match(str(sku).strip()):
        return False, "SKU hanya boleh huruf, angka, '-' dan '_' (2-50 karakter)."
    return True, ""


def validate_demand_series(series: Sequence, min_points: int = 6) -> Tuple[bool, str]:
    """Validasi deret demand untuk forecasting."""
    if series is None:
        return False, "Data demand kosong."
    try:
        values = [float(x) for x in series]
    except (ValueError, TypeError):
        return False, "Semua nilai demand harus berupa angka."
    if len(values) < min_points:
        return False, f"Butuh minimal {min_points} titik data, hanya ada {len(values)}."
    if any(v < 0 for v in values):
        return False, "Demand tidak boleh negatif."
    if all(v == 0 for v in values):
        return False, "Semua nilai demand adalah 0."
    return True, ""


def validate_forecast_horizon(horizon, allowed=(3, 6, 12)) -> Tuple[bool, str]:
    """Validasi horizon forecast."""
    try:
        h = int(horizon)
    except (ValueError, TypeError):
        return False, "Horizon harus berupa angka bulat."
    if h <= 0:
        return False, "Horizon harus lebih dari 0."
    if allowed and h not in allowed:
        return False, f"Horizon harus salah satu dari {allowed}."
    return True, ""


def validate_window_size(window, series_len: int = None) -> Tuple[bool, str]:
    """Validasi window size (jumlah lag/lookback)."""
    try:
        w = int(window)
    except (ValueError, TypeError):
        return False, "Window size harus berupa angka bulat."
    if w < 1:
        return False, "Window size minimal 1."
    if series_len is not None and w >= series_len:
        return False, "Window size harus lebih kecil dari jumlah data."
    return True, ""

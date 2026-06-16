"""Unit test untuk modules.forecasting_metrics & croston_forecaster (pure python)."""

import math
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from modules.forecasting_metrics import (  # noqa: E402
    mae, rmse, mape, smape, bias, evaluate_forecast,
)
from modules.croston_forecaster import (  # noqa: E402
    is_intermittent_demand, croston_forecast, tsb_forecast, forecast_intermittent,
)


def test_mae_perfect():
    assert mae([10, 20, 30], [10, 20, 30]) == 0


def test_rmse_known():
    # errors 0,0,3 -> rmse = sqrt(9/3)=sqrt(3)
    assert math.isclose(rmse([1, 2, 3], [1, 2, 6]), math.sqrt(3), rel_tol=1e-6)


def test_mape_skips_zero_actual():
    # actual 0 should be skipped, not divide-by-zero
    val = mape([0, 100], [10, 90])
    assert math.isclose(val, 10.0, rel_tol=1e-6)


def test_smape_bounded():
    val = smape([100, 200], [110, 180])
    assert 0 <= val <= 200


def test_bias_sign():
    # prediksi lebih tinggi -> bias positif
    assert bias([10, 10], [12, 12]) > 0
    assert bias([10, 10], [8, 8]) < 0


def test_evaluate_forecast_keys():
    res = evaluate_forecast([10, 20, 30], [11, 19, 31])
    assert set(res.keys()) == {"MAE", "RMSE", "MAPE", "sMAPE", "Bias"}


def test_is_intermittent_detects_zeros():
    z = [0, 0, 5, 0, 0, 8, 0, 0, 6, 0, 0, 7]
    info = is_intermittent_demand(z)
    assert info["intermittent"] is True
    assert info["zero_ratio"] > 0.5


def test_is_intermittent_smooth_series():
    s = [100, 102, 98, 101, 99, 103, 100, 97]
    info = is_intermittent_demand(s)
    assert info["intermittent"] is False


def test_croston_positive_level():
    z = [0, 0, 5, 0, 0, 8, 0, 0, 6, 0, 0, 7]
    assert croston_forecast(z) > 0


def test_tsb_positive_level():
    z = [0, 0, 5, 0, 0, 8, 0, 0, 6, 0, 0, 7]
    assert tsb_forecast(z) > 0


def test_forecast_intermittent_horizon():
    z = [0, 0, 5, 0, 0, 8, 0, 0, 6, 0, 0, 7]
    res = forecast_intermittent(z, horizon=6)
    assert "error" not in res
    assert len(res["forecast"]) == 6
    assert all(v >= 0 for v in res["forecast"])


def test_forecast_intermittent_insufficient_data():
    res = forecast_intermittent([1, 2], horizon=6)
    assert "error" in res

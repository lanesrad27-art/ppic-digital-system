"""Unit test untuk modules.inventory_calculations (tanpa dependensi streamlit)."""

import math
import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from modules.inventory_calculations import (  # noqa: E402
    calculate_eoq, calculate_safety_stock, calculate_rop,
    get_stock_status, calculate_reorder_recommendation, classify_abc,
    calculate_turnover,
)


def test_eoq_basic():
    # H = unit_cost * pct/100 = 10000 * 0.2 = 2000
    # EOQ = sqrt(2*12000*50000/2000) = sqrt(600000) ~ 774.6 -> round 775
    res = calculate_eoq(12000, 50000, 10000, 20)
    assert "error" not in res
    expected = round(math.sqrt(2 * 12000 * 50000 / 2000))
    assert res["eoq"] == expected
    assert res["orders_per_year"] > 0


def test_eoq_invalid_returns_error():
    assert "error" in calculate_eoq(0, 50000, 10000, 20)
    assert "error" in calculate_eoq(12000, 50000, 0, 20)
    assert "error" in calculate_eoq(12000, 50000, 10000, 0)
    assert "error" in calculate_eoq(-5, 50000, 10000, 20)


def test_safety_stock_zero_when_no_variability():
    # max == avg untuk demand & lead time -> safety stock 0
    res = calculate_safety_stock(10, 10, 7, 7)
    assert res["safety_stock"] == 0


def test_safety_stock_positive():
    # (15*10) - (10*7) = 150 - 70 = 80
    res = calculate_safety_stock(10, 15, 7, 10)
    assert res["safety_stock"] == 80


def test_rop():
    # daily = 3650/365 = 10 ; rop = 10*7 + 33 = 103
    res = calculate_rop(3650, 7, 33)
    assert res["rop"] == 103
    assert math.isclose(res["daily_demand"], 10.0, rel_tol=1e-6)


def test_stock_status_levels():
    assert get_stock_status(0, rop=100, safety_stock=50, eoq=200, annual_demand=1200) == "KRITIS"
    assert get_stock_status(80, rop=100, safety_stock=50, eoq=200, annual_demand=1200) == "REORDER"
    assert get_stock_status(150, rop=100, safety_stock=50, eoq=200, annual_demand=1200) == "AMAN"
    # overstock: stok > rop + 2*eoq = 100 + 400 = 500
    assert get_stock_status(600, rop=100, safety_stock=50, eoq=200, annual_demand=1200) == "OVERSTOCK"


def test_reorder_recommendation():
    # stok di bawah ROP -> max(eoq, rop-stok)
    r1 = calculate_reorder_recommendation(20, 100, 200)
    assert r1["needs_reorder"] is True
    assert r1["recommended_order_qty"] == 200
    r2 = calculate_reorder_recommendation(20, 500, 200)
    assert r2["recommended_order_qty"] == 480
    # stok aman -> tidak perlu order
    r3 = calculate_reorder_recommendation(300, 100, 200, status="AMAN")
    assert r3["needs_reorder"] is False
    assert r3["recommended_order_qty"] == 0


def test_classify_abc_total_zero():
    df = pd.DataFrame({"sku": ["A", "B"], "annual_demand": [0, 0], "unit_cost": [0, 0]})
    res = classify_abc(df)
    assert (res["abc_class"] == "C").all()


def test_classify_abc_ranking():
    df = pd.DataFrame({
        "sku": ["A", "B", "C"],
        "annual_demand": [800, 150, 50],
        "unit_cost": [1, 1, 1],
    })
    res = classify_abc(df).set_index("sku")["abc_class"].to_dict()
    assert res["A"] == "A"
    assert res["C"] == "C"


def test_turnover():
    res = calculate_turnover(1200, 100, 10)
    assert math.isclose(res["turnover_ratio"], 12.0, rel_tol=1e-6)
    # avg_stock 0 -> error dict, turnover 0
    res0 = calculate_turnover(1200, 0, 10)
    assert res0["turnover_ratio"] == 0

"""
inventory_calculations.py
Kalkulasi Inventory Control:
  - EOQ (Economic Order Quantity)
  - Safety Stock
  - ROP (Reorder Point)
  - Status stok (KRITIS / REORDER / AMAN / OVERSTOCK)
  - Klasifikasi ABC
  - Inventory Turnover
  - Rekomendasi reorder

Semua fungsi tahan terhadap nilai null/0 dan tidak menyebabkan division by zero.
"""

from __future__ import annotations

import math
from typing import Optional

import numpy as np
import pandas as pd


def _safe_float(value, default: float = 0.0) -> float:
    """Konversi ke float dengan aman; handle None/NaN/string."""
    try:
        if value is None:
            return default
        v = float(value)
        if math.isnan(v) or math.isinf(v):
            return default
        return v
    except (ValueError, TypeError):
        return default


# ──────────────────────────────────────────
# 1. EOQ
# ──────────────────────────────────────────
def calculate_eoq(
    annual_demand: float,
    ordering_cost: float,
    unit_cost: float,
    holding_cost_pct: float,
) -> dict:
    """Hitung EOQ (rumus Wilson). Return dict; berisi key 'error' bila invalid."""
    annual_demand = _safe_float(annual_demand)
    ordering_cost = _safe_float(ordering_cost)
    unit_cost = _safe_float(unit_cost)
    holding_cost_pct = _safe_float(holding_cost_pct)

    if annual_demand <= 0:
        return {"error": "annual_demand harus > 0", "eoq": 0}
    if ordering_cost <= 0:
        return {"error": "ordering_cost harus > 0", "eoq": 0}
    if unit_cost <= 0:
        return {"error": "unit_cost harus > 0", "eoq": 0}
    if holding_cost_pct <= 0:
        return {"error": "holding_cost_pct harus > 0", "eoq": 0}

    H = unit_cost * (holding_cost_pct / 100.0)  # biaya simpan / unit / tahun
    if H <= 0:
        return {"error": "Biaya simpan per unit harus > 0", "eoq": 0}

    eoq = math.sqrt((2 * annual_demand * ordering_cost) / H)
    if eoq <= 0:
        return {"error": "EOQ tidak valid", "eoq": 0}

    orders_per_year = annual_demand / eoq
    cycle_time_days = 365 / orders_per_year if orders_per_year > 0 else 0
    total_order_cost = orders_per_year * ordering_cost
    total_hold_cost = (eoq / 2) * H
    total_annual_cost = total_order_cost + total_hold_cost

    return {
        "eoq": round(eoq),
        "holding_cost_per_unit": round(H, 2),
        "orders_per_year": round(orders_per_year, 1),
        "cycle_time_days": round(cycle_time_days, 1),
        "total_order_cost": round(total_order_cost),
        "total_holding_cost": round(total_hold_cost),
        "total_annual_cost": round(total_annual_cost),
    }


# ──────────────────────────────────────────
# 2. Safety Stock
# ──────────────────────────────────────────
def calculate_safety_stock(
    avg_daily_demand: float,
    max_daily_demand: float,
    avg_lead_time: float,
    max_lead_time: float,
) -> dict:
    """Safety stock metode max: (max_d * max_lt) - (avg_d * avg_lt)."""
    avg_daily_demand = _safe_float(avg_daily_demand)
    max_daily_demand = _safe_float(max_daily_demand)
    avg_lead_time = _safe_float(avg_lead_time)
    max_lead_time = _safe_float(max_lead_time)

    safety_stock = (max_daily_demand * max_lead_time) - (avg_daily_demand * avg_lead_time)
    safety_stock = max(0, round(safety_stock))

    return {
        "safety_stock": safety_stock,
        "avg_daily_demand": round(avg_daily_demand, 2),
        "max_daily_demand": round(max_daily_demand, 2),
        "avg_lead_time_days": avg_lead_time,
        "max_lead_time_days": max_lead_time,
    }


# ──────────────────────────────────────────
# 3. ROP
# ──────────────────────────────────────────
def calculate_rop(
    annual_demand: float,
    lead_time_days: float,
    safety_stock: float,
) -> dict:
    """ROP = (D/365 * lead_time) + safety_stock."""
    annual_demand = _safe_float(annual_demand)
    lead_time_days = _safe_float(lead_time_days)
    safety_stock = _safe_float(safety_stock)

    daily_demand = annual_demand / 365 if annual_demand > 0 else 0
    demand_during_lead_time = daily_demand * lead_time_days
    rop = demand_during_lead_time + safety_stock

    return {
        "rop": round(rop),
        "daily_demand": round(daily_demand, 2),
        "demand_during_lead_time": round(demand_during_lead_time),
        "safety_stock": round(safety_stock),
        "lead_time_days": lead_time_days,
    }


# ──────────────────────────────────────────
# 4. Status stok
# ──────────────────────────────────────────
def get_stock_status(
    current_stock: float,
    rop: float,
    safety_stock: float,
    eoq: Optional[float] = None,
    annual_demand: Optional[float] = None,
) -> str:
    """
    Tentukan status stok.
      KRITIS    : current_stock <= safety_stock
      REORDER   : current_stock <= rop
      OVERSTOCK : stok jauh melebihi kebutuhan (> ROP + 2*EOQ atau > 1 thn demand)
      AMAN      : sisanya
    """
    current_stock = _safe_float(current_stock)
    rop = _safe_float(rop)
    safety_stock = _safe_float(safety_stock)

    if current_stock <= safety_stock:
        return "KRITIS"
    if current_stock <= rop:
        return "REORDER"

    # Deteksi overstock.
    eoq_v = _safe_float(eoq)
    annual_v = _safe_float(annual_demand)
    overstock_threshold = None
    if eoq_v > 0:
        overstock_threshold = rop + 2 * eoq_v
    elif annual_v > 0:
        overstock_threshold = annual_v  # lebih dari 1 tahun demand
    if overstock_threshold and current_stock > overstock_threshold:
        return "OVERSTOCK"

    return "AMAN"


# ──────────────────────────────────────────
# 5. Rekomendasi reorder
# ──────────────────────────────────────────
def calculate_reorder_recommendation(
    current_stock: float,
    rop: float,
    eoq: float,
    status: Optional[str] = None,
) -> dict:
    """
    Rekomendasi jumlah order.
    recommended_order_qty = max(eoq, rop - current_stock) bila perlu reorder.
    Tidak merekomendasikan order bila status AMAN/OVERSTOCK.
    """
    current_stock = _safe_float(current_stock)
    rop = _safe_float(rop)
    eoq = _safe_float(eoq)

    needs_reorder = current_stock <= rop
    if status in ("AMAN", "OVERSTOCK"):
        needs_reorder = False

    if not needs_reorder:
        return {"needs_reorder": False, "recommended_order_qty": 0,
                "deficit": 0}

    deficit = max(0, rop - current_stock)
    recommended = max(eoq, deficit)
    return {
        "needs_reorder": True,
        "recommended_order_qty": int(round(recommended)),
        "deficit": int(round(deficit)),
    }


# ──────────────────────────────────────────
# 6. ABC classification
# ──────────────────────────────────────────
def classify_abc(
    df: pd.DataFrame,
    annual_usage_col: str = "annual_demand",
    unit_cost_col: str = "unit_cost",
) -> pd.DataFrame:
    """
    Klasifikasi ABC berdasarkan nilai penggunaan tahunan.
      A: kumulatif 0-80%, B: 80-95%, C: 95-100%.
    Tahan terhadap total_value = 0 (semua jadi kelas C).
    """
    df = df.copy()
    if df.empty or annual_usage_col not in df or unit_cost_col not in df:
        df["annual_value"] = 0
        df["value_pct"] = 0
        df["cumulative_pct"] = 0
        df["abc_class"] = "C"
        return df

    df[annual_usage_col] = pd.to_numeric(df[annual_usage_col], errors="coerce").fillna(0)
    df[unit_cost_col] = pd.to_numeric(df[unit_cost_col], errors="coerce").fillna(0)
    df["annual_value"] = df[annual_usage_col] * df[unit_cost_col]
    df = df.sort_values("annual_value", ascending=False).reset_index(drop=True)

    total_value = df["annual_value"].sum()
    if total_value <= 0:
        df["value_pct"] = 0.0
        df["cumulative_pct"] = 0.0
        df["abc_class"] = "C"
        return df

    df["value_pct"] = df["annual_value"] / total_value * 100
    df["cumulative_pct"] = df["value_pct"].cumsum()

    def _classify(cum_pct):
        if cum_pct <= 80:
            return "A"
        if cum_pct <= 95:
            return "B"
        return "C"

    df["abc_class"] = df["cumulative_pct"].apply(_classify)
    return df


# ──────────────────────────────────────────
# 7. Turnover
# ──────────────────────────────────────────
def calculate_turnover(annual_demand: float, avg_stock: float, unit_cost: float) -> dict:
    """Inventory turnover & days on hand. Tahan terhadap avg_stock = 0."""
    annual_demand = _safe_float(annual_demand)
    avg_stock = _safe_float(avg_stock)
    unit_cost = _safe_float(unit_cost)

    if avg_stock <= 0 or unit_cost <= 0:
        return {"error": "Rata-rata stok & unit cost harus > 0",
                "turnover_ratio": 0, "days_on_hand": 0}

    cogs = annual_demand * unit_cost
    avg_inv = avg_stock * unit_cost
    turnover = cogs / avg_inv if avg_inv > 0 else 0
    doh = 365 / turnover if turnover > 0 else 0

    return {
        "turnover_ratio": round(turnover, 2),
        "days_on_hand": round(doh, 1),
        "cogs": round(cogs),
        "avg_inventory_value": round(avg_inv),
    }


# ──────────────────────────────────────────
# 8. Batch metrics
# ──────────────────────────────────────────
def calculate_all_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """
    Hitung EOQ, ROP, status, nilai stok, ABC, dan rekomendasi reorder
    untuk seluruh produk dalam DataFrame.

    Kolom dibutuhkan: current_stock, safety_stock, annual_demand,
    unit_cost, ordering_cost, holding_cost_pct, lead_time_days.
    """
    if df is None or df.empty:
        return pd.DataFrame()

    results = []
    for _, row in df.iterrows():
        annual_demand = _safe_float(row.get("annual_demand"))
        unit_cost = _safe_float(row.get("unit_cost"))
        eoq_result = calculate_eoq(
            annual_demand,
            _safe_float(row.get("ordering_cost")),
            unit_cost,
            _safe_float(row.get("holding_cost_pct")),
        )
        rop_result = calculate_rop(
            annual_demand,
            _safe_float(row.get("lead_time_days")),
            _safe_float(row.get("safety_stock")),
        )
        eoq_val = eoq_result.get("eoq", 0)
        rop_val = rop_result.get("rop", 0)
        current_stock = _safe_float(row.get("current_stock"))
        status = get_stock_status(
            current_stock, rop_val, _safe_float(row.get("safety_stock")),
            eoq=eoq_val, annual_demand=annual_demand,
        )
        reorder = calculate_reorder_recommendation(current_stock, rop_val, eoq_val, status)

        results.append({
            **row.to_dict(),
            "eoq": eoq_val,
            "rop": rop_val,
            "status": status,
            "stock_value": round(current_stock * unit_cost),
            "annual_value": round(annual_demand * unit_cost),
            "orders_per_year": eoq_result.get("orders_per_year", 0),
            "total_annual_cost": eoq_result.get("total_annual_cost", 0),
            "recommended_order_qty": reorder["recommended_order_qty"],
        })

    result_df = pd.DataFrame(results)
    # Tambahkan kelas ABC.
    if not result_df.empty and "annual_demand" in result_df and "unit_cost" in result_df:
        abc = classify_abc(result_df)[["sku", "abc_class"]] if "sku" in result_df else None
        if abc is not None:
            result_df = result_df.drop(columns=["abc_class"], errors="ignore").merge(
                abc, on="sku", how="left"
            )
    return result_df

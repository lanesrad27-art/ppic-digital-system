"""
forecast_service.py
Layanan penyimpanan, pengambilan, dan sinkronisasi hasil forecast.

Alur data:
  Forecasting -> forecast_runs + forecast_results (pending)
  -> Forecast Sync -> products.annual_demand (source='forecast')
  -> audit ke forecast_sync_logs.

Semua operasi sync dilakukan dalam SATU transaksi (atomic).
"""

from __future__ import annotations

import logging
import uuid
from datetime import date
from typing import Optional

import pandas as pd
import streamlit as st
from sqlalchemy import text

from modules.database import get_engine, clear_cache

logger = logging.getLogger("ppic.forecast_service")


def new_run_id() -> str:
    """Buat run_id UUID baru."""
    return str(uuid.uuid4())


# ──────────────────────────────────────────
# Simpan hasil forecast
# ──────────────────────────────────────────
def save_forecast_run(run_meta: dict) -> bool:
    """
    Simpan 1 baris metadata run ke forecast_runs.
    run_meta keys: run_id, product_sku, model_name, model_mape, model_mae,
    model_rmse, model_smape, model_bias, window_size, forecast_horizon, created_by.
    """
    engine = get_engine()
    if engine is None:
        return False
    try:
        with engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO forecast_runs
                    (run_id, product_sku, model_name, model_mape, model_mae,
                     model_rmse, model_smape, model_bias, window_size,
                     forecast_horizon, created_by)
                VALUES
                    (:run_id, :product_sku, :model_name, :model_mape, :model_mae,
                     :model_rmse, :model_smape, :model_bias, :window_size,
                     :forecast_horizon, :created_by)
            """), {
                "run_id": run_meta.get("run_id"),
                "product_sku": run_meta.get("product_sku"),
                "model_name": run_meta.get("model_name"),
                "model_mape": run_meta.get("model_mape"),
                "model_mae": run_meta.get("model_mae"),
                "model_rmse": run_meta.get("model_rmse"),
                "model_smape": run_meta.get("model_smape"),
                "model_bias": run_meta.get("model_bias"),
                "window_size": run_meta.get("window_size"),
                "forecast_horizon": run_meta.get("forecast_horizon"),
                "created_by": run_meta.get("created_by"),
            })
        clear_cache()
        return True
    except Exception as e:  # noqa: BLE001
        logger.error("save_forecast_run gagal: %s", e)
        return False


def save_forecast_results(run_id: str, rows: list[dict]) -> bool:
    """
    Simpan baris-baris hasil forecast bulanan ke forecast_results.
    Setiap row: product_sku, product_name, forecast_period, bulan_ke,
    prediksi_demand, lower_bound, upper_bound, model_name, model_mape.
    sync_status otomatis 'pending'.
    """
    engine = get_engine()
    if engine is None or not rows:
        return False
    try:
        with engine.begin() as conn:
            for r in rows:
                conn.execute(text("""
                    INSERT INTO forecast_results
                        (run_id, product_sku, product_name, forecast_period,
                         bulan_ke, prediksi_demand, lower_bound, upper_bound,
                         model_name, model_mape, sync_status)
                    VALUES
                        (:run_id, :product_sku, :product_name, :forecast_period,
                         :bulan_ke, :prediksi_demand, :lower_bound, :upper_bound,
                         :model_name, :model_mape, 'pending')
                """), {
                    "run_id": run_id,
                    "product_sku": r.get("product_sku"),
                    "product_name": r.get("product_name"),
                    "forecast_period": r.get("forecast_period"),
                    "bulan_ke": r.get("bulan_ke"),
                    "prediksi_demand": r.get("prediksi_demand"),
                    "lower_bound": r.get("lower_bound"),
                    "upper_bound": r.get("upper_bound"),
                    "model_name": r.get("model_name"),
                    "model_mape": r.get("model_mape"),
                })
        clear_cache()
        return True
    except Exception as e:  # noqa: BLE001
        logger.error("save_forecast_results gagal: %s", e)
        return False


# ──────────────────────────────────────────
# Ambil data forecast
# ──────────────────────────────────────────
def load_latest_forecasts() -> pd.DataFrame:
    """Ambil run forecast TERBARU per SKU (via view v_latest_forecast_runs)."""
    engine = get_engine()
    if engine is None:
        return pd.DataFrame()
    try:
        return pd.read_sql(text(
            "SELECT * FROM v_latest_forecast_runs ORDER BY product_sku"
        ), engine)
    except Exception as e:  # noqa: BLE001
        logger.error("load_latest_forecasts gagal: %s", e)
        return pd.DataFrame()


def load_pending_forecasts() -> pd.DataFrame:
    """Ambil ringkasan forecast pending + perbandingan demand (view)."""
    engine = get_engine()
    if engine is None:
        return pd.DataFrame()
    try:
        return pd.read_sql(text(
            "SELECT * FROM v_pending_forecasts ORDER BY product_sku"
        ), engine)
    except Exception as e:  # noqa: BLE001
        logger.error("load_pending_forecasts gagal: %s", e)
        return pd.DataFrame()


def load_forecast_detail(run_id: str) -> pd.DataFrame:
    """Ambil detail bulanan untuk satu run_id."""
    engine = get_engine()
    if engine is None or not run_id:
        return pd.DataFrame()
    try:
        return pd.read_sql(text("""
            SELECT * FROM forecast_results
            WHERE run_id = :run_id
            ORDER BY bulan_ke
        """), engine, params={"run_id": run_id})
    except Exception as e:  # noqa: BLE001
        logger.error("load_forecast_detail gagal: %s", e)
        return pd.DataFrame()


def load_forecast_sync_logs() -> pd.DataFrame:
    """Ambil seluruh log sinkronisasi (audit trail)."""
    engine = get_engine()
    if engine is None:
        return pd.DataFrame()
    try:
        return pd.read_sql(text(
            "SELECT * FROM forecast_sync_logs ORDER BY synced_at DESC, id DESC"
        ), engine)
    except Exception as e:  # noqa: BLE001
        logger.error("load_forecast_sync_logs gagal: %s", e)
        return pd.DataFrame()


# ──────────────────────────────────────────
# Annualized demand
# ──────────────────────────────────────────
def annualize_demand(total_forecast_demand: float, months_forecasted: int) -> float:
    """
    Konversi total demand hasil forecast menjadi annual demand.
      horizon 12 bln -> annualized = total
      horizon != 12  -> annualized = total / months * 12
    """
    months_forecasted = int(months_forecasted) if months_forecasted else 0
    if months_forecasted <= 0:
        return 0.0
    if months_forecasted == 12:
        return round(float(total_forecast_demand), 2)
    return round(float(total_forecast_demand) / months_forecasted * 12, 2)


# ──────────────────────────────────────────
# Sync / reject / rollback
# ──────────────────────────────────────────
def sync_forecast_to_product(
    run_id: str, synced_by: str, allow_big_change: bool = False
) -> tuple[bool, str]:
    """
    Sinkronkan hasil forecast satu run ke products.annual_demand.
    Semua langkah dalam satu transaksi:
      1. validasi SKU ada di products
      2. hitung new_annual_demand (annualized)
      3. update products (annual_demand, source='forecast', last_forecast_sync_at)
      4. insert forecast_sync_logs (audit)
      5. update forecast_results.sync_status='synced', synced_by/synced_at
    """
    engine = get_engine()
    if engine is None:
        return False, "Database tidak tersedia."
    if not run_id:
        return False, "run_id kosong."
    try:
        with engine.begin() as conn:
            agg = conn.execute(text("""
                SELECT product_sku,
                       COUNT(*)               AS n_months,
                       SUM(prediksi_demand)   AS total_demand,
                       MAX(forecast_period)   AS last_period
                FROM forecast_results
                WHERE run_id = :run_id AND sync_status = 'pending'
                GROUP BY product_sku
            """), {"run_id": run_id}).mappings().first()
            if not agg:
                return False, "Forecast pending tidak ditemukan untuk run ini."

            sku = agg["product_sku"]
            prod = conn.execute(text(
                "SELECT annual_demand FROM products WHERE sku = :sku"
            ), {"sku": sku}).mappings().first()
            if not prod:
                return False, f"SKU {sku} tidak ditemukan di products. Sync dibatalkan."

            old_demand = float(prod["annual_demand"] or 0)
            new_demand = annualize_demand(agg["total_demand"] or 0, agg["n_months"] or 0)

            # Guard perubahan ekstrem (> 50%).
            if old_demand > 0 and not allow_big_change:
                change_pct = abs(new_demand - old_demand) / old_demand * 100
                if change_pct > 50:
                    return False, (
                        f"Perubahan demand {change_pct:.0f}% (>50%). "
                        "Centang konfirmasi untuk tetap melakukan sync."
                    )

            # 3. update products
            conn.execute(text("""
                UPDATE products
                SET annual_demand = :d,
                    annual_demand_source = 'forecast',
                    last_forecast_sync_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE sku = :sku
            """), {"d": new_demand, "sku": sku})

            # 4. audit log
            conn.execute(text("""
                INSERT INTO forecast_sync_logs
                    (run_id, product_sku, old_annual_demand, new_annual_demand,
                     forecast_date, synced_by)
                VALUES (:run_id, :sku, :old, :new, :fdate, :by)
            """), {
                "run_id": run_id, "sku": sku, "old": old_demand,
                "new": new_demand, "fdate": agg["last_period"], "by": synced_by,
            })

            # 5. tandai forecast_results synced
            conn.execute(text("""
                UPDATE forecast_results
                SET sync_status = 'synced',
                    synced_by = :by,
                    synced_at = CURRENT_TIMESTAMP
                WHERE run_id = :run_id AND sync_status = 'pending'
            """), {"by": synced_by, "run_id": run_id})
        clear_cache()
        return True, (
            f"Forecast {sku} disinkronkan. Annual demand: "
            f"{old_demand:,.0f} -> {new_demand:,.0f}."
        )
    except Exception as e:  # noqa: BLE001
        logger.error("sync_forecast_to_product gagal: %s", e)
        return False, "Gagal melakukan sync. Transaksi dibatalkan."


def reject_forecast(run_id: str, rejected_by: Optional[str] = None) -> tuple[bool, str]:
    """Tandai semua forecast_results pending pada run sebagai 'rejected'."""
    engine = get_engine()
    if engine is None:
        return False, "Database tidak tersedia."
    try:
        with engine.begin() as conn:
            res = conn.execute(text("""
                UPDATE forecast_results
                SET sync_status = 'rejected',
                    synced_by = :by,
                    synced_at = CURRENT_TIMESTAMP
                WHERE run_id = :run_id AND sync_status = 'pending'
            """), {"by": rejected_by, "run_id": run_id})
        clear_cache()
        if res.rowcount == 0:
            return False, "Tidak ada forecast pending untuk ditolak."
        return True, "Forecast ditolak."
    except Exception as e:  # noqa: BLE001
        logger.error("reject_forecast gagal: %s", e)
        return False, "Gagal menolak forecast."


def rollback_forecast_sync(log_id: int) -> tuple[bool, str]:
    """
    Kembalikan annual_demand produk ke nilai lama berdasarkan satu baris
    forecast_sync_logs. Dilakukan dalam satu transaksi.
    """
    engine = get_engine()
    if engine is None:
        return False, "Database tidak tersedia."
    try:
        with engine.begin() as conn:
            log = conn.execute(text(
                "SELECT * FROM forecast_sync_logs WHERE id = :id"
            ), {"id": log_id}).mappings().first()
            if not log:
                return False, "Log sync tidak ditemukan."

            conn.execute(text("""
                UPDATE products
                SET annual_demand = :old,
                    annual_demand_source = 'manual',
                    updated_at = CURRENT_TIMESTAMP
                WHERE sku = :sku
            """), {"old": log["old_annual_demand"], "sku": log["product_sku"]})

            # Kembalikan status hasil forecast run terkait ke 'pending'.
            if log["run_id"]:
                conn.execute(text("""
                    UPDATE forecast_results
                    SET sync_status = 'pending', synced_by = NULL, synced_at = NULL
                    WHERE run_id = :run_id AND sync_status = 'synced'
                """), {"run_id": log["run_id"]})
        clear_cache()
        return True, (
            f"Rollback berhasil. Annual demand {log['product_sku']} "
            f"dikembalikan ke {float(log['old_annual_demand'] or 0):,.0f}."
        )
    except Exception as e:  # noqa: BLE001
        logger.error("rollback_forecast_sync gagal: %s", e)
        return False, "Gagal melakukan rollback."

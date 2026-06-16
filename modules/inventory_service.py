"""
inventory_service.py
Layanan data inventory: stok, transaksi, kategori, supplier, produk.
Semua query memakai parameterized SQL (tidak ada f-string untuk input user).
"""

from __future__ import annotations

import logging
from typing import Optional

import pandas as pd
import streamlit as st
from sqlalchemy import text

from modules.database import get_engine, clear_cache

logger = logging.getLogger("ppic.inventory_service")


@st.cache_data(ttl=60, show_spinner=False)
def load_stock_status() -> pd.DataFrame:
    """Ambil status stok + EOQ + ROP + ABC dari view v_stock_status."""
    engine = get_engine()
    if engine is None:
        return pd.DataFrame()
    try:
        return pd.read_sql(
            text("SELECT * FROM v_stock_status ORDER BY abc_class, name"), engine
        )
    except Exception as e:  # noqa: BLE001
        logger.error("load_stock_status gagal: %s", e)
        return pd.DataFrame()


@st.cache_data(ttl=60, show_spinner=False)
def load_transactions(days: int = 90) -> pd.DataFrame:
    """
    Ambil histori transaksi N hari terakhir.
    Menggunakan parameterized interval (bukan f-string).
    """
    engine = get_engine()
    if engine is None:
        return pd.DataFrame()
    try:
        days = int(days)
    except (ValueError, TypeError):
        days = 90
    query = text("""
        SELECT
            st.id,
            p.sku,
            p.name AS product_name,
            st.transaction_type,
            st.quantity,
            st.unit_price,
            st.reference_no,
            st.notes,
            st.created_by,
            st.transaction_date
        FROM stock_transactions st
        JOIN products p ON st.product_id = p.id
        WHERE st.transaction_date >= CURRENT_DATE - (:days * INTERVAL '1 day')
        ORDER BY st.transaction_date DESC, st.id DESC
    """)
    try:
        return pd.read_sql(query, engine, params={"days": days})
    except Exception as e:  # noqa: BLE001
        logger.error("load_transactions gagal: %s", e)
        return pd.DataFrame()


def add_transaction(
    product_id: int,
    txn_type: str,
    quantity: float,
    unit_price: float = 0,
    reference_no: str = "",
    notes: str = "",
    created_by: Optional[str] = None,
) -> tuple[bool, str]:
    """
    Tambah transaksi IN/OUT dalam satu transaksi DB.
    Transaksi OUT dilindungi di level SQL agar stok tidak pernah negatif.
    """
    engine = get_engine()
    if engine is None:
        return False, "Database tidak tersedia."
    if txn_type not in ("IN", "OUT"):
        return False, "Tipe transaksi harus IN atau OUT."
    try:
        quantity = float(quantity)
    except (ValueError, TypeError):
        return False, "Jumlah tidak valid."
    if quantity <= 0:
        return False, "Jumlah harus lebih dari 0."

    try:
        with engine.begin() as conn:
            if txn_type == "OUT":
                # Proteksi SQL-level: hanya update bila stok mencukupi.
                res = conn.execute(text("""
                    UPDATE products
                    SET current_stock = current_stock - :qty,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = :pid AND current_stock >= :qty
                """), {"qty": quantity, "pid": product_id})
                if res.rowcount == 0:
                    return False, "Stok tidak mencukupi untuk transaksi OUT."
            else:  # IN
                res = conn.execute(text("""
                    UPDATE products
                    SET current_stock = current_stock + :qty,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = :pid
                """), {"qty": quantity, "pid": product_id})
                if res.rowcount == 0:
                    return False, "Produk tidak ditemukan."

            conn.execute(text("""
                INSERT INTO stock_transactions
                    (product_id, transaction_type, quantity, unit_price,
                     reference_no, notes, created_by)
                VALUES (:pid, :ttype, :qty, :price, :ref, :notes, :by)
            """), {
                "pid": product_id, "ttype": txn_type, "qty": quantity,
                "price": unit_price or 0, "ref": reference_no or None,
                "notes": notes or None, "by": created_by,
            })
        clear_cache()
        return True, f"Transaksi {txn_type} berhasil dicatat."
    except Exception as e:  # noqa: BLE001
        logger.error("add_transaction gagal: %s", e)
        return False, "Gagal mencatat transaksi. Silakan coba lagi."


def update_product_demand(product_id: int, annual_demand: float,
                          source: str = "manual") -> tuple[bool, str]:
    """Update annual_demand sebuah produk secara manual."""
    engine = get_engine()
    if engine is None:
        return False, "Database tidak tersedia."
    try:
        annual_demand = float(annual_demand)
    except (ValueError, TypeError):
        return False, "Annual demand tidak valid."
    if annual_demand < 0:
        return False, "Annual demand tidak boleh negatif."
    try:
        with engine.begin() as conn:
            conn.execute(text("""
                UPDATE products
                SET annual_demand = :d,
                    annual_demand_source = :src,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = :pid
            """), {"d": annual_demand, "src": source, "pid": product_id})
        clear_cache()
        return True, "Annual demand diperbarui."
    except Exception as e:  # noqa: BLE001
        logger.error("update_product_demand gagal: %s", e)
        return False, "Gagal memperbarui annual demand."


def update_annual_demand_from_forecast(
    sku: str, new_annual_demand: float, conn=None
) -> int:
    """
    Update annual_demand dari hasil forecast (source='forecast').
    Set last_forecast_sync_at. Bisa dipakai di dalam transaksi yang sudah ada
    dengan mengoper `conn`; bila None, buka transaksi sendiri.
    Return rowcount.
    """
    sql = text("""
        UPDATE products
        SET annual_demand = :d,
            annual_demand_source = 'forecast',
            last_forecast_sync_at = CURRENT_TIMESTAMP,
            updated_at = CURRENT_TIMESTAMP
        WHERE sku = :sku
    """)
    params = {"d": new_annual_demand, "sku": sku}
    if conn is not None:
        return conn.execute(sql, params).rowcount
    engine = get_engine()
    if engine is None:
        return 0
    with engine.begin() as c:
        return c.execute(sql, params).rowcount


@st.cache_data(ttl=300, show_spinner=False)
def load_categories() -> pd.DataFrame:
    engine = get_engine()
    if engine is None:
        return pd.DataFrame()
    try:
        return pd.read_sql(text("SELECT * FROM categories ORDER BY name"), engine)
    except Exception as e:  # noqa: BLE001
        logger.error("load_categories gagal: %s", e)
        return pd.DataFrame()


@st.cache_data(ttl=300, show_spinner=False)
def load_suppliers() -> pd.DataFrame:
    engine = get_engine()
    if engine is None:
        return pd.DataFrame()
    try:
        return pd.read_sql(text("SELECT * FROM suppliers ORDER BY name"), engine)
    except Exception as e:  # noqa: BLE001
        logger.error("load_suppliers gagal: %s", e)
        return pd.DataFrame()


@st.cache_data(ttl=60, show_spinner=False)
def load_products() -> pd.DataFrame:
    """Ambil seluruh produk aktif beserta nama kategori & supplier."""
    engine = get_engine()
    if engine is None:
        return pd.DataFrame()
    try:
        return pd.read_sql(text("""
            SELECT p.*, c.name AS category, s.name AS supplier
            FROM products p
            LEFT JOIN categories c ON p.category_id = c.id
            LEFT JOIN suppliers  s ON p.supplier_id = s.id
            WHERE p.is_active = TRUE
            ORDER BY p.name
        """), engine)
    except Exception as e:  # noqa: BLE001
        logger.error("load_products gagal: %s", e)
        return pd.DataFrame()


def get_product_by_sku(sku: str) -> Optional[dict]:
    """Ambil satu produk berdasarkan SKU. Return dict atau None."""
    engine = get_engine()
    if engine is None or not sku:
        return None
    try:
        with engine.connect() as conn:
            row = conn.execute(text(
                "SELECT * FROM products WHERE sku = :sku"
            ), {"sku": sku}).mappings().first()
        return dict(row) if row else None
    except Exception as e:  # noqa: BLE001
        logger.error("get_product_by_sku gagal: %s", e)
        return None

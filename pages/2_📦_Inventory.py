"""Halaman Inventory — tabel produk + EOQ/ROP/ABC + filter + export."""

import pandas as pd
import streamlit as st

from modules.auth import require_permission
from modules.inventory_service import load_stock_status
from modules.formatting import fmt_int, fmt_rp, fmt_date

st.set_page_config(page_title="Inventory", page_icon="📦", layout="wide")
require_permission("inventory")

st.title("📦 Inventory")

stock = load_stock_status()
if stock.empty:
    st.info("Belum ada data produk.")
    st.stop()

# ── Filter ──
c1, c2, c3, c4 = st.columns(4)
with c1:
    categories = ["(Semua)"] + sorted(stock["category"].dropna().unique().tolist())
    f_cat = st.selectbox("Kategori", categories)
with c2:
    suppliers = ["(Semua)"] + sorted(stock["supplier"].dropna().unique().tolist())
    f_sup = st.selectbox("Supplier", suppliers)
with c3:
    statuses = ["(Semua)"] + sorted(stock["status"].dropna().unique().tolist())
    f_status = st.selectbox("Status Stok", statuses)
with c4:
    abc_classes = ["(Semua)"] + sorted(stock["abc_class"].dropna().unique().tolist())
    f_abc = st.selectbox("Kelas ABC", abc_classes)

filtered = stock.copy()
if f_cat != "(Semua)":
    filtered = filtered[filtered["category"] == f_cat]
if f_sup != "(Semua)":
    filtered = filtered[filtered["supplier"] == f_sup]
if f_status != "(Semua)":
    filtered = filtered[filtered["status"] == f_status]
if f_abc != "(Semua)":
    filtered = filtered[filtered["abc_class"] == f_abc]

st.caption(f"Menampilkan {len(filtered)} dari {len(stock)} produk.")

# ── Tabel tampilan ──
cols = [
    "sku", "name", "category", "supplier", "current_stock", "safety_stock",
    "annual_demand", "annual_demand_source", "eoq", "rop", "status",
    "stock_value", "abc_class", "recommended_order_qty", "last_forecast_sync_at",
]
view = filtered[[c for c in cols if c in filtered.columns]].copy()

if "last_forecast_sync_at" in view:
    view["last_forecast_sync_at"] = view["last_forecast_sync_at"].apply(fmt_date)

st.dataframe(
    view,
    use_container_width=True,
    hide_index=True,
    column_config={
        "stock_value": st.column_config.NumberColumn("Nilai Stok", format="Rp %d"),
        "current_stock": st.column_config.NumberColumn("Stok"),
        "annual_demand": st.column_config.NumberColumn("Annual Demand"),
        "recommended_order_qty": st.column_config.NumberColumn("Rekomendasi Order"),
    },
)

# ── Export CSV ──
csv = filtered.to_csv(index=False).encode("utf-8")
st.download_button("⬇️ Export CSV", csv, "inventory_export.csv", "text/csv")

# ── Upload CSV (opsional, preview saja) ──
with st.expander("📤 Upload Inventory CSV (opsional)"):
    st.caption("Format kolom mengikuti sample_inventory.csv. "
               "Fitur ini menampilkan preview; impor ke DB dilakukan terpisah.")
    up = st.file_uploader("Pilih file CSV", type=["csv"], key="inv_upload")
    if up is not None:
        try:
            df_up = pd.read_csv(up)
            st.success(f"{len(df_up)} baris terbaca.")
            st.dataframe(df_up.head(20), use_container_width=True, hide_index=True)
        except Exception:
            st.error("Gagal membaca file CSV. Periksa format.")

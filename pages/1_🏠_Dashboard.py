"""Halaman Dashboard — KPI ringkas & grafik inventory + forecast."""

import pandas as pd
import plotly.express as px
import streamlit as st

from modules.auth import require_permission
from modules.inventory_service import load_stock_status
from modules.forecast_service import load_pending_forecasts, load_latest_forecasts
from modules.formatting import fmt_int, fmt_rp, fmt_date

st.set_page_config(page_title="Dashboard", page_icon="🏠", layout="wide")
require_permission("dashboard")

st.title("🏠 Dashboard")

stock = load_stock_status()
pending = load_pending_forecasts()
latest = load_latest_forecasts()

if stock.empty:
    st.info("Belum ada data produk. Tambahkan produk / jalankan seed_data.sql.")
    st.stop()

# ── KPI ──
total_sku = len(stock)
total_value = stock["stock_value"].sum() if "stock_value" in stock else 0
kritis = int((stock["status"] == "KRITIS").sum()) if "status" in stock else 0
reorder = int((stock["status"] == "REORDER").sum()) if "status" in stock else 0
overstock = int((stock["status"] == "OVERSTOCK").sum()) if "status" in stock else 0
pending_sync = len(pending) if not pending.empty else 0

last_forecast_date = "-"
if not latest.empty and "created_at" in latest:
    last_forecast_date = fmt_date(latest["created_at"].max())

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total SKU", fmt_int(total_sku))
c2.metric("Nilai Inventory", fmt_rp(total_value))
c3.metric("Stok Kritis", fmt_int(kritis))
c4.metric("Perlu Reorder", fmt_int(reorder))

c5, c6, c7, c8 = st.columns(4)
c5.metric("Overstock", fmt_int(overstock))
c6.metric("Forecast Pending Sync", fmt_int(pending_sync))
c7.metric("Forecast Terakhir", last_forecast_date)
c8.metric("Item Aman", fmt_int(int((stock["status"] == "AMAN").sum())))

st.divider()

# ── Charts ──
col_a, col_b = st.columns(2)
with col_a:
    st.subheader("Distribusi Status Stok")
    status_count = stock["status"].value_counts().reset_index()
    status_count.columns = ["status", "jumlah"]
    fig = px.pie(status_count, names="status", values="jumlah", hole=0.4,
                 color="status",
                 color_discrete_map={"KRITIS": "#e74c3c", "REORDER": "#f39c12",
                                     "AMAN": "#2ecc71", "OVERSTOCK": "#3498db"})
    st.plotly_chart(fig, use_container_width=True)

with col_b:
    st.subheader("Distribusi Kelas ABC")
    if "abc_class" in stock:
        abc_count = stock["abc_class"].value_counts().reset_index()
        abc_count.columns = ["abc_class", "jumlah"]
        fig = px.bar(abc_count.sort_values("abc_class"), x="abc_class", y="jumlah",
                     color="abc_class", text="jumlah")
        st.plotly_chart(fig, use_container_width=True)

col_c, col_d = st.columns(2)
with col_c:
    st.subheader("Top 10 Nilai Inventory")
    top_val = stock.nlargest(10, "stock_value")[["sku", "name", "stock_value"]]
    fig = px.bar(top_val, x="stock_value", y="name", orientation="h")
    fig.update_layout(yaxis={"categoryorder": "total ascending"})
    st.plotly_chart(fig, use_container_width=True)

with col_d:
    st.subheader("Top 10 Risiko Reorder")
    risk = stock[stock["status"].isin(["KRITIS", "REORDER"])]
    if not risk.empty and "recommended_order_qty" in risk:
        risk = risk.nlargest(10, "recommended_order_qty")[
            ["sku", "name", "recommended_order_qty"]]
        fig = px.bar(risk, x="recommended_order_qty", y="name", orientation="h",
                     color_discrete_sequence=["#e74c3c"])
        fig.update_layout(yaxis={"categoryorder": "total ascending"})
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.success("Tidak ada item yang perlu reorder. 🎉")

# ── Forecast pending by model ──
if not pending.empty and "model_name" in pending:
    st.subheader("Forecast Pending per Model")
    by_model = pending["model_name"].value_counts().reset_index()
    by_model.columns = ["model", "jumlah"]
    st.plotly_chart(px.bar(by_model, x="model", y="jumlah", text="jumlah"),
                    use_container_width=True)

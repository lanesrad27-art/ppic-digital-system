"""
Halaman Forecast Insight — ringkasan & analisis hasil forecast.
Membandingkan demand manual vs forecast, risiko stockout, rekomendasi EOQ/ROP baru.
"""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from sqlalchemy import text

from modules.auth import require_permission
from modules.database import get_engine
from modules.inventory_service import load_stock_status
from modules.forecast_service import load_forecast_sync_logs
from modules.formatting import fmt_int, fmt_date

st.set_page_config(page_title="Forecast Insight", page_icon="📊", layout="wide")
require_permission("forecast_insight")

st.title("📊 Forecast Insight")

engine = get_engine()


def _scalar(query: str, params=None):
    if engine is None:
        return None
    try:
        with engine.connect() as conn:
            return conn.execute(text(query), params or {}).scalar()
    except Exception:
        return None


# ── KPI ringkas ──
total_pending = _scalar(
    "SELECT COUNT(DISTINCT run_id) FROM forecast_results WHERE sync_status='pending'") or 0
total_synced = _scalar(
    "SELECT COUNT(DISTINCT run_id) FROM forecast_results WHERE sync_status='synced'") or 0
latest_date = _scalar("SELECT MAX(created_at) FROM forecast_runs")

c1, c2, c3 = st.columns(3)
c1.metric("Forecast Pending", fmt_int(total_pending))
c2.metric("Forecast Synced", fmt_int(total_synced))
c3.metric("Forecast Terakhir", fmt_date(latest_date))

st.divider()

# ── Manual vs Forecast (dari audit log) ──
logs = load_forecast_sync_logs()
if not logs.empty:
    st.subheader("🔄 Perubahan Annual Demand (Manual → Forecast)")
    logs = logs.copy()
    logs["delta"] = logs["new_annual_demand"].astype(float) - logs["old_annual_demand"].astype(float)
    logs["pct"] = logs.apply(
        lambda r: (r["delta"] / r["old_annual_demand"] * 100)
        if r["old_annual_demand"] else None, axis=1)

    top_up = logs.nlargest(5, "delta")[["product_sku", "old_annual_demand",
                                        "new_annual_demand", "delta", "pct"]]
    top_down = logs.nsmallest(5, "delta")[["product_sku", "old_annual_demand",
                                           "new_annual_demand", "delta", "pct"]]
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("**📈 Demand Naik Tertinggi**")
        st.dataframe(top_up, use_container_width=True, hide_index=True)
    with col_b:
        st.markdown("**📉 Demand Turun Tertinggi**")
        st.dataframe(top_down, use_container_width=True, hide_index=True)

    fig = px.bar(logs.sort_values("delta", ascending=False).head(15),
                 x="product_sku", y="delta", color="delta",
                 color_continuous_scale="RdYlGn", title="Perubahan Demand per SKU")
    st.plotly_chart(fig, use_container_width=True)
else:
    st.caption("Belum ada sinkronisasi forecast untuk dianalisis.")

st.divider()

# ── Risiko stockout + rekomendasi EOQ/ROP baru ──
stock = load_stock_status()
if not stock.empty:
    st.subheader("⚠️ Produk Berisiko Stockout")
    risk = stock[stock["status"].isin(["KRITIS", "REORDER"])][
        ["sku", "name", "current_stock", "safety_stock", "rop",
         "eoq", "recommended_order_qty", "annual_demand_source"]]
    if risk.empty:
        st.success("Tidak ada produk berisiko stockout. 🎉")
    else:
        st.dataframe(risk, use_container_width=True, hide_index=True)

    st.subheader("🧮 Rekomendasi EOQ / ROP Terkini")
    forecast_based = stock[stock["annual_demand_source"] == "forecast"][
        ["sku", "name", "annual_demand", "eoq", "rop", "recommended_order_qty"]]
    if forecast_based.empty:
        st.caption("Belum ada produk dengan demand berbasis forecast.")
    else:
        st.dataframe(forecast_based, use_container_width=True, hide_index=True)

    # Komposisi sumber annual demand
    st.subheader("📊 Sumber Annual Demand")
    src = stock["annual_demand_source"].value_counts().reset_index()
    src.columns = ["source", "jumlah"]
    st.plotly_chart(px.pie(src, names="source", values="jumlah", hole=0.4),
                    use_container_width=True)

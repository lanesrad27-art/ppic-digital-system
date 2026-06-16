"""
Halaman EOQ / ROP Calculator — kalkulator interaktif + visualisasi sawtooth.
Selaras dengan API modules.inventory_calculations (fungsi mengembalikan dict).
"""

import plotly.graph_objects as go
import streamlit as st

from modules.auth import require_permission
from modules.inventory_service import load_products
from modules.inventory_calculations import (
    calculate_eoq, calculate_safety_stock, calculate_rop,
    get_stock_status, calculate_reorder_recommendation,
)
from modules.formatting import fmt_int, fmt_rp

st.set_page_config(page_title="EOQ / ROP Calculator", page_icon="🧮", layout="wide")
require_permission("eoq_rop")

st.title("🧮 EOQ / ROP Calculator")
st.caption("Hitung Economic Order Quantity, Reorder Point, Safety Stock, dan rekomendasi order.")

mode = st.radio("Sumber data", ["Input manual", "Ambil dari produk"], horizontal=True)

d = dict(annual_demand=12000.0, ordering_cost=75000.0, unit_cost=185000.0,
         holding_cost_pct=20.0, lead_time_days=14.0, current_stock=200.0)

if mode == "Ambil dari produk":
    products = load_products()
    if not products.empty:
        opts = {f"{r['sku']} — {r['name']}": r for _, r in products.iterrows()}
        sel = st.selectbox("Produk", list(opts.keys()))
        p = opts[sel]
        d.update(
            annual_demand=float(p.get("annual_demand") or 0),
            ordering_cost=float(p.get("ordering_cost") or d["ordering_cost"]),
            unit_cost=float(p.get("unit_cost") or d["unit_cost"]),
            holding_cost_pct=float(p.get("holding_cost_pct") or d["holding_cost_pct"]),
            lead_time_days=float(p.get("lead_time_days") or d["lead_time_days"]),
            current_stock=float(p.get("current_stock") or 0),
        )

st.subheader("Parameter Biaya & Permintaan")
c1, c2, c3 = st.columns(3)
with c1:
    annual_demand = st.number_input("Annual Demand (unit/tahun)",
                                    min_value=0.0, value=d["annual_demand"], step=100.0)
    ordering_cost = st.number_input("Ordering Cost (Rp/order)",
                                    min_value=0.0, value=d["ordering_cost"], step=1000.0)
with c2:
    unit_cost = st.number_input("Unit Cost (Rp/unit)",
                                min_value=0.0, value=d["unit_cost"], step=1000.0)
    holding_cost_pct = st.number_input("Holding Cost (% dari unit cost / tahun)",
                                       min_value=0.0, max_value=100.0,
                                       value=d["holding_cost_pct"], step=1.0)
with c3:
    current_stock = st.number_input("Stok Saat Ini",
                                    min_value=0.0, value=d["current_stock"], step=10.0)

st.subheader("Parameter Lead Time & Variabilitas (Safety Stock)")
c4, c5, c6, c7 = st.columns(4)
avg_daily_default = round(annual_demand / 365.0, 2) if annual_demand else 0.0
with c4:
    avg_daily_demand = st.number_input("Avg Demand Harian",
                                       min_value=0.0, value=float(avg_daily_default), step=1.0)
with c5:
    max_daily_demand = st.number_input("Max Demand Harian",
                                       min_value=0.0,
                                       value=float(round(avg_daily_default * 1.5, 2)), step=1.0)
with c6:
    avg_lead_time = st.number_input("Avg Lead Time (hari)",
                                    min_value=0.0, value=d["lead_time_days"], step=1.0)
with c7:
    max_lead_time = st.number_input("Max Lead Time (hari)",
                                    min_value=0.0,
                                    value=float(round(d["lead_time_days"] * 1.5)), step=1.0)

# ── Hitung ──
eoq_res = calculate_eoq(annual_demand, ordering_cost, unit_cost, holding_cost_pct)
if eoq_res.get("error"):
    st.error(f"EOQ tidak dapat dihitung: {eoq_res['error']}")
    st.stop()

eoq = eoq_res["eoq"]
ss_res = calculate_safety_stock(avg_daily_demand, max_daily_demand, avg_lead_time, max_lead_time)
safety = ss_res["safety_stock"]
rop_res = calculate_rop(annual_demand, avg_lead_time, safety)
rop = rop_res["rop"]
status = get_stock_status(current_stock, rop, safety, eoq, annual_demand)
rec = calculate_reorder_recommendation(current_stock, rop, eoq, status)

status_color = {"KRITIS": "🔴", "REORDER": "🟠", "AMAN": "🟢", "OVERSTOCK": "🔵"}.get(status, "⚪")

st.divider()
st.subheader("📊 Hasil")
m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("EOQ", fmt_int(eoq))
m2.metric("Safety Stock", fmt_int(safety))
m3.metric("Reorder Point", fmt_int(rop))
m4.metric("Rekomendasi Order", fmt_int(rec["recommended_order_qty"]))
m5.metric("Status", f"{status_color} {status}")

m6, m7, m8, m9 = st.columns(4)
m6.metric("Order / Tahun", eoq_res["orders_per_year"])
m7.metric("Siklus (hari)", eoq_res["cycle_time_days"])
m8.metric("Total Ordering Cost", fmt_rp(eoq_res["total_order_cost"]))
m9.metric("Total Holding Cost", fmt_rp(eoq_res["total_holding_cost"]))

st.caption(f"Total biaya persediaan tahunan (order + simpan): "
           f"**{fmt_rp(eoq_res['total_annual_cost'])}** — "
           f"biaya simpan per unit/tahun: {fmt_rp(eoq_res['holding_cost_per_unit'])}.")

st.divider()

# ── Visualisasi sawtooth (inventory cycle) ──
st.subheader("📉 Pola Inventory (Sawtooth)")
daily_demand = rop_res["daily_demand"]
if daily_demand > 0 and eoq > 0:
    cycle_days = eoq / daily_demand
    n_cycles = 3
    xs, ys = [], []
    level = eoq + safety
    t = 0.0
    for _ in range(n_cycles):
        xs += [t, t + cycle_days]
        ys += [level, safety]
        t += cycle_days
        xs.append(t)
        ys.append(level)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", name="Inventory Level"))
    fig.add_hline(y=rop, line_dash="dash", line_color="orange", annotation_text="ROP")
    fig.add_hline(y=safety, line_dash="dot", line_color="red", annotation_text="Safety Stock")
    fig.update_layout(xaxis_title="Hari", yaxis_title="Unit", title="Siklus Persediaan EOQ")
    st.plotly_chart(fig, use_container_width=True)
    st.caption(f"Panjang 1 siklus ≈ {cycle_days:.0f} hari. "
               f"Lakukan pemesanan saat stok mencapai ROP ({fmt_int(rop)} unit).")
else:
    st.info("Masukkan annual demand > 0 untuk melihat grafik siklus.")

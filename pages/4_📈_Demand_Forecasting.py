"""
Halaman Demand Forecasting.
Pilih produk -> sumber data demand -> horizon -> model -> jalankan -> simpan.
Mendukung ARIMA, ETS, XGBoost/GradientBoosting, Croston/TSB, dan Auto Select.
"""

from datetime import date
from dateutil.relativedelta import relativedelta

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from sqlalchemy import text

from modules.auth import require_permission, get_current_user
from modules.database import get_engine
from modules.inventory_service import load_products
from modules.forecast_service import (
    new_run_id, save_forecast_run, save_forecast_results, annualize_demand,
)
from modules.validators import validate_demand_series, validate_forecast_horizon
from modules.formatting import fmt_int
from modules import (
    arima_forecaster as arima,
    ets_forecaster as ets,
    xgboost_forecaster as xgb,
    croston_forecaster as croston,
)

st.set_page_config(page_title="Demand Forecasting", page_icon="📈", layout="wide")
require_permission("forecasting")
user = get_current_user()

st.title("📈 Demand Forecasting")

MODELS = ["Auto Select Best Model", "ARIMA", "ETS / Holt-Winters",
          "XGBoost / Gradient Boosting", "Croston / TSB"]


def _load_demand_from_db(sku: str) -> pd.DataFrame:
    """Ambil demand_history sebuah SKU, terurut periode."""
    engine = get_engine()
    if engine is None:
        return pd.DataFrame()
    try:
        return pd.read_sql(text("""
            SELECT demand_period, demand_qty
            FROM demand_history
            WHERE product_sku = :sku
            ORDER BY demand_period
        """), engine, params={"sku": sku})
    except Exception:
        return pd.DataFrame()


def _run_model(name: str, series, horizon: int) -> dict:
    """Jalankan satu model berdasarkan nama."""
    if name == "ARIMA":
        return arima.forecast_arima(series, horizon)
    if name == "ETS / Holt-Winters":
        return ets.forecast_ets(series, horizon)
    if name == "XGBoost / Gradient Boosting":
        return xgb.forecast_xgb_future(series, horizon)
    if name == "Croston / TSB":
        return croston.forecast_intermittent(series, horizon)
    return {"error": "Model tidak dikenal."}


def _auto_select(series, horizon: int) -> tuple[dict, pd.DataFrame]:
    """Jalankan semua model valid, bandingkan metrik, pilih MAPE terkecil."""
    candidates = ["ARIMA", "ETS / Holt-Winters",
                  "XGBoost / Gradient Boosting", "Croston / TSB"]
    rows, results = [], {}
    for m in candidates:
        res = _run_model(m, series, horizon)
        if res.get("error") or not res.get("forecast"):
            continue
        metrics = res.get("metrics") or {}
        results[m] = res
        rows.append({
            "Model": res.get("model_name", m),
            "MAE": metrics.get("MAE"), "RMSE": metrics.get("RMSE"),
            "MAPE": metrics.get("MAPE"), "sMAPE": metrics.get("sMAPE"),
            "Bias": metrics.get("Bias"), "_key": m,
        })
    if not rows:
        return {"error": "Tidak ada model yang berhasil untuk data ini."}, pd.DataFrame()
    comp = pd.DataFrame(rows)
    # Pilih berdasarkan MAPE; bila MAPE kosong, pakai RMSE.
    sort_key = "MAPE" if comp["MAPE"].notna().any() else "RMSE"
    comp_sorted = comp.sort_values(sort_key, na_position="last").reset_index(drop=True)
    best_key = comp_sorted.iloc[0]["_key"]
    best = results[best_key]
    return best, comp_sorted.drop(columns=["_key"])


# ──────────────────────────────────────────
# Input
# ──────────────────────────────────────────
products = load_products()
if products.empty:
    st.info("Belum ada produk. Tambahkan produk terlebih dahulu.")
    st.stop()

c1, c2, c3 = st.columns(3)
with c1:
    opts = {f"{r['sku']} — {r['name']}": r for _, r in products.iterrows()}
    sel = st.selectbox("Produk", list(opts.keys()))
    product = opts[sel]
with c2:
    horizon = st.selectbox("Forecast Horizon (bulan)", [3, 6, 12], index=1)
with c3:
    model_choice = st.selectbox("Model", MODELS)

source = st.radio("Sumber data demand",
                  ["Dari tabel demand_history", "Upload CSV / Excel"],
                  horizontal=True)

series, periods = None, None
if source == "Dari tabel demand_history":
    dh = _load_demand_from_db(product["sku"])
    if dh.empty:
        st.warning("Tidak ada demand_history untuk SKU ini. Coba upload data.")
    else:
        series = dh["demand_qty"].astype(float).tolist()
        periods = pd.to_datetime(dh["demand_period"]).tolist()
        st.caption(f"{len(series)} titik data demand ditemukan.")
else:
    up = st.file_uploader("Upload file (kolom: demand_period, demand_qty)",
                          type=["csv", "xlsx"])
    if up is not None:
        try:
            df_up = pd.read_csv(up) if up.name.endswith(".csv") else pd.read_excel(up)
            qty_col = "demand_qty" if "demand_qty" in df_up else df_up.columns[-1]
            series = df_up[qty_col].astype(float).tolist()
            if "demand_period" in df_up:
                periods = pd.to_datetime(df_up["demand_period"]).tolist()
            st.success(f"{len(series)} titik data terbaca.")
            st.dataframe(df_up.head(), use_container_width=True, hide_index=True)
        except Exception:
            st.error("Gagal membaca file. Pastikan ada kolom demand_qty.")

# ──────────────────────────────────────────
# Jalankan forecast
# ──────────────────────────────────────────
if st.button("🚀 Jalankan Forecast", type="primary", use_container_width=True):
    ok_h, msg_h = validate_forecast_horizon(horizon)
    ok_s, msg_s = validate_demand_series(series or [], min_points=6)
    if not ok_h:
        st.error(msg_h)
    elif not ok_s:
        st.error(msg_s)
    else:
        with st.spinner("Menghitung forecast..."):
            if model_choice == "Auto Select Best Model":
                best, comp = _auto_select(series, horizon)
            else:
                best = _run_model(model_choice, series, horizon)
                comp = pd.DataFrame()
        if best.get("error"):
            st.error(best["error"])
        else:
            st.session_state["fc_result"] = {
                "best": best, "comp": comp, "series": series,
                "periods": periods, "horizon": horizon,
                "sku": product["sku"], "name": product["name"],
            }

# ──────────────────────────────────────────
# Tampilkan hasil
# ──────────────────────────────────────────
res = st.session_state.get("fc_result")
if res:
    best = res["best"]
    forecast = best.get("forecast", [])
    series = res["series"]
    horizon = res["horizon"]

    st.success(f"Model terpilih: **{best.get('model_name')}**")

    # Chart actual vs forecast + CI
    fig = go.Figure()
    hist_x = list(range(1, len(series) + 1))
    fc_x = list(range(len(series) + 1, len(series) + len(forecast) + 1))
    fig.add_trace(go.Scatter(x=hist_x, y=series, name="Aktual", mode="lines+markers"))
    fig.add_trace(go.Scatter(x=fc_x, y=forecast, name="Forecast",
                             mode="lines+markers", line=dict(dash="dash")))
    if best.get("lower_ci") and best.get("upper_ci"):
        fig.add_trace(go.Scatter(x=fc_x, y=best["upper_ci"], name="Upper CI",
                                 line=dict(width=0), showlegend=False))
        fig.add_trace(go.Scatter(x=fc_x, y=best["lower_ci"], name="CI",
                                 fill="tonexty", line=dict(width=0),
                                 fillcolor="rgba(52,152,219,0.2)"))
    fig.update_layout(title="Aktual vs Forecast", xaxis_title="Periode",
                      yaxis_title="Demand")
    st.plotly_chart(fig, use_container_width=True)

    # Tabel forecast bulanan
    start = (res["periods"][-1] if res.get("periods") else date.today())
    start = pd.to_datetime(start)
    months = [(start + relativedelta(months=i + 1)) for i in range(len(forecast))]
    fc_table = pd.DataFrame({
        "bulan_ke": list(range(1, len(forecast) + 1)),
        "forecast_period": [m.date() for m in months],
        "prediksi_demand": [round(v, 2) for v in forecast],
        "lower_bound": (best.get("lower_ci") or [None] * len(forecast)),
        "upper_bound": (best.get("upper_ci") or [None] * len(forecast)),
    })
    st.subheader("Tabel Forecast Bulanan")
    st.dataframe(fc_table, use_container_width=True, hide_index=True)

    # Metrics
    metrics = best.get("metrics") or {}
    if metrics:
        st.subheader("Metrik Akurasi (out-of-sample)")
        mc = st.columns(5)
        for col, (k, v) in zip(mc, metrics.items()):
            col.metric(k, v)

    # Tabel perbandingan (Auto Select)
    if isinstance(res.get("comp"), pd.DataFrame) and not res["comp"].empty:
        st.subheader("Perbandingan Model")
        st.dataframe(res["comp"], use_container_width=True, hide_index=True)

    # Annualized preview
    total = sum(forecast)
    annualized = annualize_demand(total, len(forecast))
    st.info(f"Total forecast {len(forecast)} bln: **{fmt_int(total)}** → "
            f"Annualized demand: **{fmt_int(annualized)}**")

    # Save
    if st.button("💾 Save Forecast", type="primary"):
        run_id = new_run_id()
        metrics = best.get("metrics") or {}
        meta = {
            "run_id": run_id, "product_sku": res["sku"],
            "model_name": best.get("model_name"),
            "model_mape": metrics.get("MAPE"), "model_mae": metrics.get("MAE"),
            "model_rmse": metrics.get("RMSE"), "model_smape": metrics.get("sMAPE"),
            "model_bias": metrics.get("Bias"), "window_size": len(series),
            "forecast_horizon": horizon, "created_by": (user or {}).get("username"),
        }
        rows = [{
            "product_sku": res["sku"], "product_name": res["name"],
            "forecast_period": r["forecast_period"], "bulan_ke": r["bulan_ke"],
            "prediksi_demand": r["prediksi_demand"],
            "lower_bound": r["lower_bound"], "upper_bound": r["upper_bound"],
            "model_name": best.get("model_name"), "model_mape": metrics.get("MAPE"),
        } for _, r in fc_table.iterrows()]
        ok1 = save_forecast_run(meta)
        ok2 = save_forecast_results(run_id, rows)
        if ok1 and ok2:
            st.success("Forecast disimpan (status: pending). "
                       "Lanjut ke halaman Forecast Sync untuk sinkronisasi.")
            st.session_state.pop("fc_result", None)
        else:
            st.error("Gagal menyimpan forecast.")

"""
Halaman Forecast Sync — sinkronkan hasil forecast ke products.annual_demand.
Hanya admin/planner. Menampilkan perbandingan demand lama vs baru + audit log.
"""

import pandas as pd
import streamlit as st

from modules.auth import require_permission, get_current_user
from modules.forecast_service import (
    load_pending_forecasts, load_forecast_detail, sync_forecast_to_product,
    reject_forecast, load_forecast_sync_logs, rollback_forecast_sync,
    annualize_demand,
)
from modules.formatting import fmt_int, fmt_pct, fmt_date

st.set_page_config(page_title="Forecast Sync", page_icon="🔗", layout="wide")
require_permission("forecast_sync")
user = get_current_user()

st.title("🔗 Forecast Sync")
st.caption("Sinkronkan hasil forecast menjadi annual demand produk.")

pending = load_pending_forecasts()

if pending.empty:
    st.info("Tidak ada forecast pending untuk disinkronkan.")
else:
    # Bangun tabel perbandingan.
    rows = []
    for _, r in pending.iterrows():
        old = float(r.get("current_annual_demand") or 0)
        new = annualize_demand(r.get("total_forecast_demand") or 0, r.get("n_months") or 0)
        diff = new - old
        pct = (diff / old * 100) if old > 0 else None
        rows.append({
            "SKU": r["product_sku"], "Produk": r.get("product_name"),
            "Model": r.get("model_name"), "MAPE": r.get("model_mape"),
            "Forecast Date": fmt_date(r.get("latest_forecast_period")),
            "Annual Lama": old, "Annual Baru": new, "Selisih": diff,
            "Perubahan %": pct, "SKU Ditemukan": bool(r.get("sku_found")),
            "run_id": r["run_id"],
        })
    comp = pd.DataFrame(rows)

    st.dataframe(
        comp.drop(columns=["run_id"]),
        use_container_width=True, hide_index=True,
        column_config={
            "Annual Lama": st.column_config.NumberColumn(format="%d"),
            "Annual Baru": st.column_config.NumberColumn(format="%d"),
            "Selisih": st.column_config.NumberColumn(format="%d"),
            "Perubahan %": st.column_config.NumberColumn(format="%.1f%%"),
        },
    )

    st.divider()
    st.subheader("Aksi Sinkronisasi")

    sel_run = st.selectbox(
        "Pilih forecast (run)",
        comp["run_id"].tolist(),
        format_func=lambda rid: f"{comp.loc[comp['run_id'] == rid, 'SKU'].iloc[0]} "
                                f"— {comp.loc[comp['run_id'] == rid, 'Model'].iloc[0]}",
    )
    sel_row = comp[comp["run_id"] == sel_run].iloc[0]

    # Peringatan SKU tidak ditemukan.
    sku_found = bool(sel_row["SKU Ditemukan"])
    if not sku_found:
        st.error(f"⚠️ SKU {sel_row['SKU']} tidak ditemukan di tabel products. "
                 "Sinkronisasi tidak diizinkan.")

    # Peringatan perubahan > 50%.
    big_change = sel_row["Perubahan %"] is not None and abs(sel_row["Perubahan %"]) > 50
    allow_big = False
    if big_change:
        st.warning(f"⚠️ Perubahan demand {sel_row['Perubahan %']:.0f}% (>50%). "
                   "Periksa kembali sebelum sync.")
        allow_big = st.checkbox("Saya konfirmasi tetap melakukan sync meski perubahan besar.")

    with st.expander("🔍 Lihat detail forecast bulanan"):
        detail = load_forecast_detail(sel_run)
        if detail.empty:
            st.caption("Tidak ada detail.")
        else:
            st.dataframe(detail[["bulan_ke", "forecast_period", "prediksi_demand",
                                 "lower_bound", "upper_bound", "sync_status"]],
                         use_container_width=True, hide_index=True)

    c1, c2 = st.columns(2)
    with c1:
        if st.button("✅ Sync Forecast Terpilih", type="primary",
                     use_container_width=True, disabled=not sku_found):
            ok, msg = sync_forecast_to_product(
                sel_run, (user or {}).get("username"), allow_big_change=allow_big)
            st.success(msg) if ok else st.error(msg)
            if ok:
                st.rerun()
    with c2:
        if st.button("❌ Reject Forecast", use_container_width=True):
            ok, msg = reject_forecast(sel_run, (user or {}).get("username"))
            st.success(msg) if ok else st.error(msg)
            if ok:
                st.rerun()

# ── Audit log + rollback ──
st.divider()
st.subheader("📝 Riwayat Sinkronisasi (Audit Log)")
logs = load_forecast_sync_logs()
if logs.empty:
    st.caption("Belum ada riwayat sinkronisasi.")
else:
    show = logs.copy()
    if "synced_at" in show:
        show["synced_at"] = show["synced_at"].apply(lambda x: fmt_date(x, "%d/%m/%Y %H:%M"))
    st.dataframe(show, use_container_width=True, hide_index=True,
                 column_config={
                     "old_annual_demand": st.column_config.NumberColumn(format="%d"),
                     "new_annual_demand": st.column_config.NumberColumn(format="%d"),
                 })
    log_id = st.selectbox("Pilih log untuk rollback", logs["id"].tolist())
    if st.button("↩️ Rollback Sync Terpilih"):
        ok, msg = rollback_forecast_sync(int(log_id))
        st.success(msg) if ok else st.error(msg)
        if ok:
            st.rerun()

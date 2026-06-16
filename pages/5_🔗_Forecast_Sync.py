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
<<<<<<< HEAD
    annualize_demand, sync_all_forecasts,
)
from modules.formatting import fmt_int, fmt_pct, fmt_date
from modules.forecasting_metrics import mape_quality
=======
    annualize_demand,
)
from modules.formatting import fmt_int, fmt_pct, fmt_date
>>>>>>> b9a8ad24d2e85e6ab546af78e0b7f10b26833f82

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

<<<<<<< HEAD
    # ── Sync All (preview lalu konfirmasi) ──
    with st.container(border=True):
        st.markdown("**⚡ Sync Semua Forecast Pending**")
        st.caption("Tinjau rencana (preview) dulu, baru konfirmasi untuk menjalankan.")
        allow_big_all = st.checkbox(
            "Izinkan perubahan >50% saat Sync All", value=False, key="sync_all_big")

        def _plan_row(row):
            if not row["SKU Ditemukan"]:
                return "SKU Missing", "Skip"
            pct = row["Perubahan %"]
            if pct is not None and abs(pct) > 50 and not allow_big_all:
                return "Big Change", "Skip"
            return "OK", "Sync"

        if st.button("👁️ Preview Sync All", use_container_width=True):
            prev = comp.copy()
            plan = [_plan_row(r) for _, r in prev.iterrows()]
            prev["Status"] = [p[0] for p in plan]
            prev["Action"] = [p[1] for p in plan]
            st.session_state["sync_all_preview"] = prev[[
                "SKU", "Status", "Annual Lama", "Annual Baru",
                "Perubahan %", "MAPE", "Action"]].reset_index(drop=True)

        preview = st.session_state.get("sync_all_preview")
        if preview is not None:
            st.dataframe(
                preview, use_container_width=True, hide_index=True,
                column_config={
                    "Annual Lama": st.column_config.NumberColumn(format="%d"),
                    "Annual Baru": st.column_config.NumberColumn(format="%d"),
                    "Perubahan %": st.column_config.NumberColumn(format="%.1f%%"),
                })
            n_sync = int((preview["Action"] == "Sync").sum())
            n_skip = int((preview["Action"] == "Skip").sum())
            st.caption(f"Akan disinkronkan: **{n_sync}** · dilewati: **{n_skip}**")
            if st.button(f"✅ Konfirmasi Sync All ({n_sync} item)", type="primary",
                         use_container_width=True, disabled=n_sync == 0):
                ok_all, msg_all, detail_all = sync_all_forecasts(
                    (user or {}).get("username"), allow_big_change=allow_big_all)
                (st.success if ok_all else st.warning)(msg_all)
                if detail_all:
                    st.dataframe(pd.DataFrame(detail_all),
                                 use_container_width=True, hide_index=True)
                st.session_state.pop("sync_all_preview", None)
                st.caption("Muat ulang halaman untuk memperbarui daftar pending di atas.")

=======
>>>>>>> b9a8ad24d2e85e6ab546af78e0b7f10b26833f82
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

<<<<<<< HEAD
    # Kualitas forecast berdasarkan MAPE.
    mape_sel = sel_row.get("MAPE")
    has_mape = mape_sel is not None and pd.notna(mape_sel)
    q_label, q_level = mape_quality(mape_sel if has_mape else None)
    q_msg = (f"Kualitas model {sel_row['Model']} — MAPE {float(mape_sel):.1f}% → {q_label}"
             if has_mape else f"Kualitas model — {q_label}")
    {"good": st.success, "info": st.info,
     "warn": st.warning, "bad": st.error}[q_level](q_msg)
    allow_bad = False
    if q_level == "bad":
        st.caption("Pertimbangkan model lain atau tambah data historis sebelum sync.")
        if (user or {}).get("role") == "admin":
            allow_bad = st.checkbox(
                "Override admin: tetap sync meski kualitas forecast buruk (MAPE >50%).")
        else:
            st.error("Kualitas forecast buruk (MAPE >50%). "
                     "Hanya admin yang dapat meng-override sync ini.")

=======
>>>>>>> b9a8ad24d2e85e6ab546af78e0b7f10b26833f82
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
<<<<<<< HEAD
        bad_block = (q_level == "bad") and not allow_bad
        sync_blocked = (not sku_found) or (big_change and not allow_big) or bad_block
        if st.button("✅ Sync Forecast Terpilih", type="primary",
                     use_container_width=True, disabled=sync_blocked):
=======
        if st.button("✅ Sync Forecast Terpilih", type="primary",
                     use_container_width=True, disabled=not sku_found):
>>>>>>> b9a8ad24d2e85e6ab546af78e0b7f10b26833f82
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

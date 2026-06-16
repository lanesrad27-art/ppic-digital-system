"""
Halaman System Health.
Menampilkan status koneksi DB, jumlah baris tabel, ketersediaan paket model,
info runtime, serta utilitas inisialisasi & seed database (khusus admin).
"""

import importlib
import platform
import sys

import streamlit as st

from modules.auth import require_login, is_admin
from modules.database import (
    check_database_connection, init_database, seed_database, get_table_counts,
)

st.set_page_config(page_title="System Health", page_icon="🩺", layout="wide")
user = require_login()

st.title("🩺 System Health")
st.caption("Status sistem, database, dan ketersediaan paket forecasting.")

# ── Koneksi database ──
st.subheader("Database")
db_ok = check_database_connection()
if db_ok:
    st.success("Koneksi database OK.")
else:
    st.error("Database tidak terhubung. Periksa .streamlit/secrets.toml.")

# ── Jumlah baris tabel ──
if db_ok:
    counts = get_table_counts()
    if counts:
        st.markdown("**Jumlah baris tabel**")
        cols = st.columns(3)
        for i, (tbl, cnt) in enumerate(counts.items()):
            display = "-" if cnt is None else f"{cnt:,}".replace(",", ".")
            cols[i % 3].metric(tbl, display)

# ── Ketersediaan paket model ──
st.subheader("Ketersediaan Paket Forecasting")


def _pkg(name: str) -> bool:
    try:
        importlib.import_module(name)
        return True
    except Exception:  # noqa: BLE001
        return False


pkgs = {
    "statsmodels (ARIMA, ETS)": _pkg("statsmodels"),
    "xgboost (opsional)": _pkg("xgboost"),
    "scikit-learn (fallback GBM)": _pkg("sklearn"),
    "bcrypt (password hashing)": _pkg("bcrypt"),
    "plotly (grafik)": _pkg("plotly"),
    "openpyxl (export Excel)": _pkg("openpyxl"),
}
pc = st.columns(2)
for i, (name, ok) in enumerate(pkgs.items()):
    pc[i % 2].markdown(f"{'✅' if ok else '❌'} {name}")

if not pkgs["xgboost (opsional)"]:
    st.info("XGBoost tidak terpasang — model ML otomatis memakai Gradient Boosting "
            "(scikit-learn) sebagai fallback.")
if not pkgs["statsmodels (ARIMA, ETS)"]:
    st.warning("statsmodels tidak terpasang — ARIMA & ETS tidak akan berjalan. "
               "Jalankan: pip install statsmodels")
if not pkgs["bcrypt (password hashing)"]:
    st.info("bcrypt tidak terpasang — hashing memakai fallback PBKDF2-HMAC-SHA256.")

# ── Info runtime ──
st.subheader("Runtime")
st.markdown(f"- Python: `{sys.version.split()[0]}`")
st.markdown(f"- Platform: `{platform.platform()}`")

# ── Utilitas admin ──
st.divider()
st.subheader("Utilitas Database")
if not is_admin(user):
    st.info("Hanya admin yang dapat menjalankan inisialisasi & seed database.")
else:
    a1, a2 = st.columns(2)
    with a1:
        st.caption("Buat tabel & view (idempoten, aman diulang).")
        if st.button("🛠️ Inisialisasi Skema (schema + views)",
                     use_container_width=True):
            ok, msg = init_database()
            st.success(msg) if ok else st.error(msg)
            if ok:
                st.rerun()
    with a2:
        st.caption("Muat data contoh dari sql/seed_data.sql.")
        if st.button("🌱 Load Seed Data", use_container_width=True):
            ok, msg = seed_database()
            st.success(msg) if ok else st.error(msg)
            if ok:
                st.rerun()
        st.warning("Seed data sebaiknya hanya dijalankan pada database kosong/baru.")

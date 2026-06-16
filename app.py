"""
app.py — PPIC Digital System (halaman landing utama).

Hanya berisi: konfigurasi halaman, login/logout, ringkasan fitur, dan
instruksi navigasi. Semua logika bisnis berada di modules/ dan pages/.
"""

import streamlit as st

from modules.database import check_database_connection, init_database
from modules.auth import (
    create_users_table, login_user, logout, get_current_user,
)

st.set_page_config(
    page_title="PPIC Digital System",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Inisialisasi session state ──
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user" not in st.session_state:
    st.session_state.user = None
if "db_initialized" not in st.session_state:
    st.session_state.db_initialized = False


def _ensure_database():
    """Cek koneksi & siapkan tabel sekali per sesi."""
    if st.session_state.db_initialized:
        return True
    if not check_database_connection():
        return False
    init_database()        # schema.sql + views.sql (idempoten)
    create_users_table()   # tabel users + seed admin opsional
    st.session_state.db_initialized = True
    return True


def _render_login():
    """Form login di halaman utama."""
    st.subheader("🔐 Login")
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Masuk", use_container_width=True)
    if submitted:
        user = login_user(username, password)
        if user:
            st.session_state.logged_in = True
            st.session_state.user = user
            st.success(f"Selamat datang, {user.get('full_name') or user['username']}!")
            st.rerun()
        else:
            st.error("Username atau password salah.")


def _render_landing(user: dict):
    """Konten landing setelah login."""
    with st.sidebar:
        st.markdown(f"**👤 {user.get('full_name') or user['username']}**")
        st.caption(f"Role: `{user.get('role')}`")
        if st.button("Logout", use_container_width=True):
            logout()
            st.rerun()

    st.markdown(
        "Gunakan **menu Pages** di sidebar kiri untuk berpindah modul: "
        "Dashboard, Inventory, Stock Transactions, Demand Forecasting, "
        "Forecast Sync, Forecast Insight, EOQ/ROP Calculator, dan User Management."
    )

    st.markdown("### ✨ Fitur Utama")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(
            "- 🏠 **Dashboard** KPI & grafik\n"
            "- 📦 **Inventory** + EOQ/ROP/ABC\n"
            "- 🔄 **Stock Transactions** IN/OUT"
        )
    with c2:
        st.markdown(
            "- 📈 **Demand Forecasting** (ARIMA, ETS, XGBoost, Croston)\n"
            "- 🔗 **Forecast Sync** ke annual demand\n"
            "- 📊 **Forecast Insight**"
        )
    with c3:
        st.markdown(
            "- 🧮 **EOQ / ROP Calculator**\n"
            "- 👥 **User Management**\n"
            "- 📝 **Audit log** sinkronisasi"
        )

    st.divider()
    st.markdown(
        "#### 🔁 Alur Data\n"
        "`Demand History → Forecasting → Forecast Results → "
        "Sync Annual Demand → EOQ/ROP → Reorder Recommendation`"
    )


# ──────────────────────────────────────────
# Main
# ──────────────────────────────────────────
st.title("🏭 PPIC Digital System")
st.caption("Demand Forecasting + Inventory Control + Reorder Recommendation")

db_ok = _ensure_database()
if not db_ok:
    st.error(
        "⚠️ Tidak dapat terhubung ke database. "
        "Periksa konfigurasi pada `.streamlit/secrets.toml` "
        "(lihat `.streamlit/secrets.example.toml`)."
    )
    st.stop()

if not st.session_state.logged_in:
    _render_login()
else:
    _render_landing(get_current_user())

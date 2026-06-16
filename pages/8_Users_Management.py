"""
Halaman User Management — khusus admin.
Buat user, ubah role, hapus user. Menampilkan daftar user & matriks role.
"""

import pandas as pd
import streamlit as st

from modules.auth import (
    require_admin, get_current_user, load_all_users, register_user,
    update_user_role, delete_user, ROLE_PERMISSIONS,
)
from modules.formatting import fmt_date

st.set_page_config(page_title="User Management", page_icon="👥", layout="wide")
require_admin()
user = get_current_user()

st.title("👥 User Management")

ROLES = list(ROLE_PERMISSIONS.keys())

# ── Tambah user ──
with st.expander("➕ Tambah User Baru", expanded=False):
    with st.form("add_user"):
        c1, c2 = st.columns(2)
        with c1:
            new_username = st.text_input("Username")
            new_fullname = st.text_input("Nama Lengkap")
        with c2:
            new_password = st.text_input("Password", type="password")
            new_role = st.selectbox("Role", ROLES)
        submitted = st.form_submit_button("Buat User", use_container_width=True)
    if submitted:
        # signature: register_user(username, password, full_name, role)
        ok, msg = register_user(new_username, new_password, new_fullname, new_role)
        st.success(msg) if ok else st.error(msg)
        if ok:
            st.rerun()

# ── Daftar user ──
st.subheader("Daftar User")
users = load_all_users()
if users.empty:
    st.info("Belum ada user.")
    st.stop()

for _, u in users.iterrows():
    with st.container(border=True):
        c1, c2, c3, c4 = st.columns([3, 2, 2, 1])
        with c1:
            st.markdown(f"**{u['username']}**")
            st.caption(u.get("full_name") or "-")
            if u.get("created_at"):
                st.caption(f"Dibuat: {fmt_date(u['created_at'])}")
        with c2:
            new_role = st.selectbox(
                "Role", ROLES,
                index=ROLES.index(u["role"]) if u["role"] in ROLES else 0,
                key=f"role_{u['id']}")
        with c3:
            if st.button("💾 Update Role", key=f"upd_{u['id']}",
                         use_container_width=True):
                ok, msg = update_user_role(int(u["id"]), new_role)
                st.success(msg) if ok else st.error(msg)
                if ok:
                    st.rerun()
        with c4:
            is_self = (user or {}).get("username") == u["username"]
            if st.button("🗑️", key=f"del_{u['id']}", disabled=is_self,
                         help="Hapus user" if not is_self else "Tidak bisa hapus diri sendiri",
                         use_container_width=True):
                # signature: delete_user(user_id, current_user_id=None)
                ok, msg = delete_user(int(u["id"]), current_user_id=(user or {}).get("id"))
                st.success(msg) if ok else st.error(msg)
                if ok:
                    st.rerun()

# ── Matriks role ──
st.divider()
st.subheader("🔑 Matriks Hak Akses Role")
all_perms = sorted({p for perms in ROLE_PERMISSIONS.values() for p in perms if p != "*"})
matrix = []
for role, perms in ROLE_PERMISSIONS.items():
    row = {"Role": role}
    for p in all_perms:
        row[p] = "✅" if ("*" in perms or p in perms) else ""
    matrix.append(row)
st.dataframe(pd.DataFrame(matrix), use_container_width=True, hide_index=True)

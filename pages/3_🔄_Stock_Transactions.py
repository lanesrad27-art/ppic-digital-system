"""Halaman Stock Transactions — riwayat & input transaksi IN/OUT."""

import streamlit as st

from modules.auth import require_permission, has_permission, get_current_user
from modules.inventory_service import (
    load_transactions, add_transaction, load_products,
)
from modules.formatting import fmt_int, fmt_rp, fmt_date

st.set_page_config(page_title="Stock Transactions", page_icon="🔄", layout="wide")
# Semua role yang punya akses 'transactions' (admin, warehouse) bisa input.
# Viewer/planner hanya bisa melihat halaman ini bila punya izin 'inventory'.
user = get_current_user()
if not user:
    require_permission("transactions")  # akan stop bila belum login

can_input = has_permission(user, "transactions")

st.title("🔄 Stock Transactions")
if not can_input:
    st.info("Anda hanya memiliki akses lihat. Input transaksi khusus role warehouse/admin.")

# ── Form input ──
if can_input:
    products = load_products()
    if products.empty:
        st.warning("Belum ada produk untuk ditransaksikan.")
    else:
        with st.expander("➕ Tambah Transaksi", expanded=True):
            with st.form("txn_form"):
                opts = {f"{r['sku']} — {r['name']}": int(r["id"])
                        for _, r in products.iterrows()}
                col1, col2, col3 = st.columns(3)
                with col1:
                    sel = st.selectbox("Produk", list(opts.keys()))
                    ttype = st.radio("Tipe", ["IN", "OUT"], horizontal=True)
                with col2:
                    qty = st.number_input("Jumlah", min_value=0.0, step=1.0)
                    price = st.number_input("Harga Satuan", min_value=0.0, step=1000.0)
                with col3:
                    ref = st.text_input("Reference No")
                    notes = st.text_input("Catatan")
                submitted = st.form_submit_button("Simpan Transaksi",
                                                  use_container_width=True)
            if submitted:
                ok, msg = add_transaction(
                    product_id=opts[sel], txn_type=ttype, quantity=qty,
                    unit_price=price, reference_no=ref, notes=notes,
                    created_by=(user or {}).get("username"),
                )
                if ok:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)

# ── Riwayat ──
st.subheader("Riwayat Transaksi")
days = st.slider("Rentang hari", min_value=7, max_value=365, value=90, step=7)
txns = load_transactions(days)
if txns.empty:
    st.info("Belum ada transaksi pada rentang ini.")
else:
    show = txns.copy()
    if "transaction_date" in show:
        show["transaction_date"] = show["transaction_date"].apply(
            lambda x: fmt_date(x, "%d/%m/%Y %H:%M"))
    st.dataframe(show, use_container_width=True, hide_index=True,
                 column_config={
                     "unit_price": st.column_config.NumberColumn("Harga", format="Rp %d"),
                     "quantity": st.column_config.NumberColumn("Qty"),
                 })
    c1, c2 = st.columns(2)
    c1.metric("Total IN", fmt_int(txns.loc[txns["transaction_type"] == "IN", "quantity"].sum()))
    c2.metric("Total OUT", fmt_int(txns.loc[txns["transaction_type"] == "OUT", "quantity"].sum()))

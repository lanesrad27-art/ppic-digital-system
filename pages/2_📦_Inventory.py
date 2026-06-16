"""Halaman Inventory — tabel produk + EOQ/ROP/ABC + filter + export."""

import pandas as pd
import streamlit as st

<<<<<<< HEAD
from modules.auth import require_permission, get_current_user, has_permission
from modules.inventory_service import load_stock_status, import_products_csv
from modules.formatting import fmt_int, fmt_rp, fmt_date, to_excel_bytes
=======
from modules.auth import require_permission
from modules.inventory_service import load_stock_status
from modules.formatting import fmt_int, fmt_rp, fmt_date
>>>>>>> b9a8ad24d2e85e6ab546af78e0b7f10b26833f82

st.set_page_config(page_title="Inventory", page_icon="📦", layout="wide")
require_permission("inventory")

st.title("📦 Inventory")

stock = load_stock_status()
if stock.empty:
    st.info("Belum ada data produk.")
    st.stop()

# ── Filter ──
c1, c2, c3, c4 = st.columns(4)
with c1:
    categories = ["(Semua)"] + sorted(stock["category"].dropna().unique().tolist())
    f_cat = st.selectbox("Kategori", categories)
with c2:
    suppliers = ["(Semua)"] + sorted(stock["supplier"].dropna().unique().tolist())
    f_sup = st.selectbox("Supplier", suppliers)
with c3:
    statuses = ["(Semua)"] + sorted(stock["status"].dropna().unique().tolist())
    f_status = st.selectbox("Status Stok", statuses)
with c4:
    abc_classes = ["(Semua)"] + sorted(stock["abc_class"].dropna().unique().tolist())
    f_abc = st.selectbox("Kelas ABC", abc_classes)

filtered = stock.copy()
if f_cat != "(Semua)":
    filtered = filtered[filtered["category"] == f_cat]
if f_sup != "(Semua)":
    filtered = filtered[filtered["supplier"] == f_sup]
if f_status != "(Semua)":
    filtered = filtered[filtered["status"] == f_status]
if f_abc != "(Semua)":
    filtered = filtered[filtered["abc_class"] == f_abc]

st.caption(f"Menampilkan {len(filtered)} dari {len(stock)} produk.")

# ── Tabel tampilan ──
cols = [
    "sku", "name", "category", "supplier", "current_stock", "safety_stock",
    "annual_demand", "annual_demand_source", "eoq", "rop", "status",
    "stock_value", "abc_class", "recommended_order_qty", "last_forecast_sync_at",
]
view = filtered[[c for c in cols if c in filtered.columns]].copy()

if "last_forecast_sync_at" in view:
    view["last_forecast_sync_at"] = view["last_forecast_sync_at"].apply(fmt_date)

st.dataframe(
    view,
    use_container_width=True,
    hide_index=True,
    column_config={
        "stock_value": st.column_config.NumberColumn("Nilai Stok", format="Rp %d"),
        "current_stock": st.column_config.NumberColumn("Stok"),
        "annual_demand": st.column_config.NumberColumn("Annual Demand"),
        "recommended_order_qty": st.column_config.NumberColumn("Rekomendasi Order"),
    },
)

<<<<<<< HEAD
# ── Export ──
ec1, ec2 = st.columns(2)
with ec1:
    csv = filtered.to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Export CSV", csv, "inventory_export.csv",
                       "text/csv", use_container_width=True)
with ec2:
    xlsx = to_excel_bytes(filtered, sheet_name="Inventory")
    st.download_button(
        "⬇️ Export Excel", xlsx, "inventory_export.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True)

# ── Import / Upload Inventory CSV ──
_user = get_current_user()
_can_import = has_permission(_user, "transactions") or (_user or {}).get("role") in ("admin", "planner")


def _validate_import_df(df):
    """Validasi DataFrame impor produk. Return (errors, warnings)."""
    errors, warnings = [], []
    cols = set(df.columns)
    if "sku" not in cols or "name" not in cols:
        errors.append("Kolom wajib 'sku' dan 'name' harus ada.")
        return errors, warnings
    sku_s = df["sku"].astype(str).str.strip()
    n_empty_sku = int((sku_s == "").sum() + df["sku"].isna().sum())
    if n_empty_sku:
        errors.append(f"{n_empty_sku} baris memiliki SKU kosong.")
    n_dup = int(sku_s[sku_s != ""].duplicated().sum())
    if n_dup:
        errors.append(f"{n_dup} SKU duplikat di dalam file.")
    name_s = df["name"].astype(str).str.strip()
    n_empty_name = int((name_s == "").sum() + df["name"].isna().sum())
    if n_empty_name:
        errors.append(f"{n_empty_name} baris memiliki nama kosong.")
    num_cols = ["current_stock", "safety_stock", "annual_demand", "ordering_cost",
                "unit_cost", "holding_cost_pct", "lead_time_days"]
    for c in num_cols:
        if c in cols:
            vals = pd.to_numeric(df[c], errors="coerce")
            n_neg = int((vals < 0).sum())
            if n_neg:
                errors.append(f"{n_neg} nilai negatif pada kolom '{c}'.")
            n_nonnum = int(vals.isna().sum() - df[c].isna().sum())
            if n_nonnum > 0:
                warnings.append(f"{n_nonnum} nilai non-numerik pada '{c}' akan diabaikan.")
    return errors, warnings


with st.expander("📤 Import Inventory CSV"):
    st.caption("Kolom: sku, name (wajib); category, supplier, current_stock, "
               "safety_stock, annual_demand, ordering_cost, unit_cost, "
               "holding_cost_pct, lead_time_days (opsional). "
               "Mengikuti format data/sample_inventory.csv.")
=======
# ── Export CSV ──
csv = filtered.to_csv(index=False).encode("utf-8")
st.download_button("⬇️ Export CSV", csv, "inventory_export.csv", "text/csv")

# ── Upload CSV (opsional, preview saja) ──
with st.expander("📤 Upload Inventory CSV (opsional)"):
    st.caption("Format kolom mengikuti sample_inventory.csv. "
               "Fitur ini menampilkan preview; impor ke DB dilakukan terpisah.")
>>>>>>> b9a8ad24d2e85e6ab546af78e0b7f10b26833f82
    up = st.file_uploader("Pilih file CSV", type=["csv"], key="inv_upload")
    if up is not None:
        try:
            df_up = pd.read_csv(up)
            st.success(f"{len(df_up)} baris terbaca.")
<<<<<<< HEAD
            st.caption("Preview 10 baris pertama:")
            st.dataframe(df_up.head(10), use_container_width=True, hide_index=True)

            errs, warns = _validate_import_df(df_up)
            for w in warns:
                st.warning("⚠️ " + w)
            for e in errs:
                st.error("❌ " + e)

            if not _can_import:
                st.info("Hanya admin/planner yang dapat mengimpor ke database.")
            elif errs:
                st.error("Perbaiki error di atas sebelum mengimpor.")
            else:
                update_existing = st.checkbox(
                    "Perbarui produk yang sudah ada (upsert)", value=True)
                if st.button("⬆️ Import ke Database", type="primary"):
                    ok_im, msg_im, _summary = import_products_csv(
                        df_up, update_existing=update_existing)
                    if ok_im:
                        st.success(msg_im)
                        st.rerun()
                    else:
                        st.error(msg_im)
=======
            st.dataframe(df_up.head(20), use_container_width=True, hide_index=True)
>>>>>>> b9a8ad24d2e85e6ab546af78e0b7f10b26833f82
        except Exception:
            st.error("Gagal membaca file CSV. Periksa format.")

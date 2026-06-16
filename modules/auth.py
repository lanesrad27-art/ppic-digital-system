"""
auth.py
Autentikasi & otorisasi multi-user untuk PPIC Digital System.

- Password hashing menggunakan bcrypt jika tersedia, fallback ke
  PBKDF2-HMAC-SHA256 (hashlib) bila bcrypt tidak terpasang. SHA256 polos
  TIDAK digunakan.
- Role: admin, planner, warehouse, viewer.
- Tidak ada default password 'admin123'. Admin default hanya dibuat bila
  st.secrets["default_admin_password"] tersedia.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import base64
from typing import Optional

import pandas as pd
import streamlit as st
from sqlalchemy import text

from modules.database import get_engine, clear_cache

logger = logging.getLogger("ppic.auth")

ROLES = ["admin", "planner", "warehouse", "viewer"]

# Hak akses per fitur (digunakan oleh halaman untuk gating).
ROLE_PERMISSIONS = {
    "admin": {"dashboard", "inventory", "transactions", "forecasting",
              "forecast_sync", "forecast_insight", "eoq_rop", "user_management"},
    "planner": {"dashboard", "inventory", "forecasting", "forecast_sync",
                "forecast_insight", "eoq_rop"},
    "warehouse": {"dashboard", "inventory", "transactions", "eoq_rop"},
    "viewer": {"dashboard", "inventory"},
}

try:
    import bcrypt  # type: ignore
    _HAS_BCRYPT = True
except ImportError:  # pragma: no cover
    _HAS_BCRYPT = False
    logger.warning("bcrypt tidak tersedia, memakai fallback PBKDF2.")

_PBKDF2_ROUNDS = 200_000


# ──────────────────────────────────────────
# Password hashing
# ──────────────────────────────────────────
def hash_password(password: str) -> str:
    """Hash password. Mengembalikan string siap simpan ke kolom VARCHAR."""
    if not password:
        raise ValueError("Password tidak boleh kosong.")
    if _HAS_BCRYPT:
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    # Fallback PBKDF2: format pbkdf2$<rounds>$<salt_b64>$<hash_b64>
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ROUNDS)
    return "pbkdf2${}${}${}".format(
        _PBKDF2_ROUNDS,
        base64.b64encode(salt).decode("ascii"),
        base64.b64encode(dk).decode("ascii"),
    )


def verify_password(password: str, hashed: str) -> bool:
    """Verifikasi password terhadap hash tersimpan (bcrypt atau PBKDF2)."""
    if not password or not hashed:
        return False
    try:
        if hashed.startswith("pbkdf2$"):
            _, rounds_s, salt_b64, hash_b64 = hashed.split("$")
            salt = base64.b64decode(salt_b64)
            expected = base64.b64decode(hash_b64)
            dk = hashlib.pbkdf2_hmac(
                "sha256", password.encode("utf-8"), salt, int(rounds_s)
            )
            return hmac.compare_digest(dk, expected)
        if _HAS_BCRYPT:
            return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
        # bcrypt hash tapi bcrypt tidak terpasang — tak bisa diverifikasi.
        logger.error("Hash bcrypt ditemukan tapi modul bcrypt tidak tersedia.")
        return False
    except Exception as e:  # noqa: BLE001
        logger.error("verify_password gagal: %s", e)
        return False


# ──────────────────────────────────────────
# Tabel users
# ──────────────────────────────────────────
def create_users_table() -> None:
    """Buat tabel inventory_users bila belum ada, dan seed admin (opsional)."""
    engine = get_engine()
    if engine is None:
        return
    try:
        with engine.begin() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS inventory_users (
                    id          SERIAL PRIMARY KEY,
                    username    VARCHAR(50) UNIQUE NOT NULL,
                    password    VARCHAR(255) NOT NULL,
                    role        VARCHAR(20) DEFAULT 'viewer'
                                CHECK (role IN ('admin','planner','warehouse','viewer')),
                    full_name   VARCHAR(100),
                    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
        _seed_default_admin(engine)
    except Exception as e:  # noqa: BLE001
        logger.error("create_users_table gagal: %s", e)


def _seed_default_admin(engine) -> None:
    """Buat admin default HANYA jika secrets default_admin_password diset."""
    default_pw = None
    try:
        default_pw = st.secrets.get("default_admin_password", None)
    except Exception:  # noqa: BLE001
        default_pw = None

    try:
        with engine.begin() as conn:
            count = conn.execute(
                text("SELECT COUNT(*) FROM inventory_users")
            ).scalar()
            if count and count > 0:
                return  # sudah ada user, jangan ganggu.
            if not default_pw:
                # Tidak ada password default — jangan buat admin otomatis.
                st.warning(
                    "⚠️ Default admin password belum diset di secrets "
                    "(`default_admin_password`). Admin default tidak dibuat. "
                    "Set nilai tersebut lalu restart untuk membuat akun admin awal."
                )
                return
            conn.execute(text("""
                INSERT INTO inventory_users (username, password, role, full_name)
                VALUES ('admin', :pw, 'admin', 'Administrator')
                ON CONFLICT (username) DO NOTHING
            """), {"pw": hash_password(str(default_pw))})
    except Exception as e:  # noqa: BLE001
        logger.error("_seed_default_admin gagal: %s", e)


# ──────────────────────────────────────────
# Operasi user
# ──────────────────────────────────────────
def login_user(username: str, password: str) -> Optional[dict]:
    """Verifikasi kredensial. Return dict user (tanpa password) atau None."""
    engine = get_engine()
    if engine is None or not username or not password:
        return None
    try:
        with engine.connect() as conn:
            row = conn.execute(text("""
                SELECT id, username, password, role, full_name
                FROM inventory_users WHERE username = :u
            """), {"u": username}).mappings().first()
        if row and verify_password(password, row["password"]):
            return {
                "id": row["id"],
                "username": row["username"],
                "role": row["role"],
                "full_name": row["full_name"],
            }
    except Exception as e:  # noqa: BLE001
        logger.error("login_user gagal: %s", e)
    return None


def register_user(username: str, password: str, full_name: str, role: str) -> tuple[bool, str]:
    """Daftarkan user baru. Validasi username unik & role valid."""
    engine = get_engine()
    if engine is None:
        return False, "Database tidak tersedia."
    if not username or not password:
        return False, "Username dan password wajib diisi."
    if role not in ROLES:
        return False, f"Role tidak valid. Pilih salah satu dari {ROLES}."
    try:
        with engine.begin() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM inventory_users WHERE username = :u"),
                {"u": username},
            ).first()
            if exists:
                return False, "Username sudah dipakai."
            conn.execute(text("""
                INSERT INTO inventory_users (username, password, role, full_name)
                VALUES (:u, :p, :r, :n)
            """), {"u": username, "p": hash_password(password), "r": role, "n": full_name})
        clear_cache()
        return True, "User berhasil dibuat."
    except Exception as e:  # noqa: BLE001
        logger.error("register_user gagal: %s", e)
        return False, "Gagal membuat user. Silakan coba lagi."


def load_all_users() -> pd.DataFrame:
    """Ambil semua user (tanpa kolom password)."""
    engine = get_engine()
    if engine is None:
        return pd.DataFrame()
    try:
        return pd.read_sql(
            text("SELECT id, username, full_name, role, created_at "
                 "FROM inventory_users ORDER BY created_at"),
            engine,
        )
    except Exception as e:  # noqa: BLE001
        logger.error("load_all_users gagal: %s", e)
        return pd.DataFrame()


def update_user_role(user_id: int, new_role: str) -> tuple[bool, str]:
    """Ubah role user. Jaga agar minimal selalu ada 1 admin."""
    if new_role not in ROLES:
        return False, "Role tidak valid."
    engine = get_engine()
    if engine is None:
        return False, "Database tidak tersedia."
    try:
        with engine.begin() as conn:
            current = conn.execute(
                text("SELECT role FROM inventory_users WHERE id = :id"),
                {"id": user_id},
            ).scalar()
            if current == "admin" and new_role != "admin":
                admin_count = conn.execute(
                    text("SELECT COUNT(*) FROM inventory_users WHERE role = 'admin'")
                ).scalar()
                if admin_count is not None and admin_count <= 1:
                    return False, "Tidak bisa menurunkan admin terakhir."
            conn.execute(
                text("UPDATE inventory_users SET role = :r WHERE id = :id"),
                {"r": new_role, "id": user_id},
            )
        clear_cache()
        return True, "Role user diperbarui."
    except Exception as e:  # noqa: BLE001
        logger.error("update_user_role gagal: %s", e)
        return False, "Gagal memperbarui role."


def delete_user(user_id: int, current_user_id: Optional[int] = None) -> tuple[bool, str]:
    """
    Hapus user. Aturan:
      - Tidak boleh hapus user yang sedang login.
      - Tidak boleh hapus admin terakhir.
    """
    engine = get_engine()
    if engine is None:
        return False, "Database tidak tersedia."
    if current_user_id is not None and int(user_id) == int(current_user_id):
        return False, "Tidak bisa menghapus user yang sedang login."
    try:
        with engine.begin() as conn:
            role = conn.execute(
                text("SELECT role FROM inventory_users WHERE id = :id"),
                {"id": user_id},
            ).scalar()
            if role is None:
                return False, "User tidak ditemukan."
            if role == "admin":
                admin_count = conn.execute(
                    text("SELECT COUNT(*) FROM inventory_users WHERE role = 'admin'")
                ).scalar()
                if admin_count is not None and admin_count <= 1:
                    return False, "Tidak bisa menghapus admin terakhir."
            conn.execute(
                text("DELETE FROM inventory_users WHERE id = :id"), {"id": user_id}
            )
        clear_cache()
        return True, "User berhasil dihapus."
    except Exception as e:  # noqa: BLE001
        logger.error("delete_user gagal: %s", e)
        return False, "Gagal menghapus user."


# ──────────────────────────────────────────
# Otorisasi helpers
# ──────────────────────────────────────────
def is_admin(user: Optional[dict]) -> bool:
    return bool(user) and user.get("role") == "admin"


def has_permission(user: Optional[dict], feature: str) -> bool:
    """Cek apakah user punya akses ke sebuah fitur."""
    if not user:
        return False
    return feature in ROLE_PERMISSIONS.get(user.get("role", "viewer"), set())


def get_current_user() -> Optional[dict]:
    return st.session_state.get("user")


def require_login() -> dict:
    """Pastikan user sudah login. Stop halaman jika belum."""
    user = st.session_state.get("user")
    if not st.session_state.get("logged_in") or not user:
        st.warning("🔐 Silakan login terlebih dahulu melalui halaman utama (app).")
        st.stop()
    return user


def require_admin() -> dict:
    """Pastikan user adalah admin. Stop halaman jika bukan."""
    user = require_login()
    if not is_admin(user):
        st.error("⛔ Akses ditolak. Hanya admin yang dapat membuka halaman ini.")
        st.stop()
    return user


def require_permission(feature: str) -> dict:
    """Pastikan user punya akses ke fitur tertentu."""
    user = require_login()
    if not has_permission(user, feature):
        st.error(f"⛔ Akses ditolak. Role '{user.get('role')}' tidak punya akses ke fitur ini.")
        st.stop()
    return user


def logout() -> None:
    st.session_state.logged_in = False
    st.session_state.user = None

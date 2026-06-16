"""
database.py
Koneksi & helper query ke PostgreSQL menggunakan SQLAlchemy + pandas.

Mendukung dua format st.secrets["database"]:

  Format A:
    [database]
    url = "postgresql://user:password@host:5432/dbname"

  Format B:
    [database]
    host = ""
    port = 5432
    user = ""
    password = ""
    dbname = ""

Error database mentah tidak ditampilkan ke user production — hanya pesan
user-friendly. Detail teknis di-log ke konsol.
"""

from __future__ import annotations

import os
import logging
from typing import Optional

import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

logger = logging.getLogger("ppic.database")

_FRIENDLY_DB_ERROR = (
    "Tidak dapat terhubung ke database. "
    "Periksa konfigurasi koneksi (.streamlit/secrets.toml) "
    "atau hubungi administrator."
)


def _build_url_from_secrets() -> Optional[str]:
    """Bangun connection URL dari st.secrets, mendukung Format A & B."""
    try:
        db = st.secrets["database"]
    except Exception:
        logger.warning("Secrets [database] tidak ditemukan.")
        return None

    # Format A — url langsung
    if "url" in db and db["url"]:
        return db["url"]

    # Format B — komponen terpisah
    try:
        return (
            f"postgresql://{db['user']}:{db['password']}"
            f"@{db['host']}:{int(db.get('port', 5432))}/{db['dbname']}"
        )
    except KeyError as e:
        logger.warning("Secrets [database] tidak lengkap, key hilang: %s", e)
        return None


@st.cache_resource(show_spinner=False)
def get_engine() -> Optional[Engine]:
    """Buat (dan cache) SQLAlchemy engine. Return None jika gagal."""
    url = _build_url_from_secrets()
    if not url:
        return None
    try:
        engine = create_engine(url, pool_pre_ping=True, pool_recycle=1800)
        # Validasi koneksi sekali di awal.
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return engine
    except Exception as e:  # noqa: BLE001
        logger.error("Gagal membuat engine database: %s", e)
        return None


def check_database_connection() -> bool:
    """Cek apakah database bisa diakses."""
    engine = get_engine()
    if engine is None:
        return False
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as e:  # noqa: BLE001
        logger.error("check_database_connection gagal: %s", e)
        return False


def execute_query(query: str, params: Optional[dict] = None):
    """
    Jalankan statement write (INSERT/UPDATE/DELETE/DDL) dalam satu transaksi.
    Return jumlah baris terpengaruh (rowcount), atau -1 jika gagal.
    """
    engine = get_engine()
    if engine is None:
        st.error(_FRIENDLY_DB_ERROR)
        return -1
    try:
        with engine.begin() as conn:
            result = conn.execute(text(query), params or {})
            return result.rowcount
    except Exception as e:  # noqa: BLE001
        logger.error("execute_query gagal: %s", e)
        st.error("Operasi database gagal. Silakan coba lagi atau hubungi administrator.")
        return -1


def read_sql(query: str, params: Optional[dict] = None) -> pd.DataFrame:
    """Jalankan SELECT dan kembalikan DataFrame. Return DataFrame kosong jika gagal."""
    engine = get_engine()
    if engine is None:
        return pd.DataFrame()
    try:
        return pd.read_sql(text(query), engine, params=params or {})
    except Exception as e:  # noqa: BLE001
        logger.error("read_sql gagal: %s", e)
        return pd.DataFrame()


def init_database(schema_dir: str = "sql") -> tuple[bool, str]:
    """
    Inisialisasi database dengan menjalankan schema.sql lalu views.sql.
    Bersifat idempoten (CREATE TABLE IF NOT EXISTS).
    """
    engine = get_engine()
    if engine is None:
        return False, _FRIENDLY_DB_ERROR

    base = os.path.join(os.path.dirname(os.path.dirname(__file__)), schema_dir)
    files = ["schema.sql", "views.sql"]
    try:
        for fname in files:
            path = os.path.join(base, fname)
            if not os.path.exists(path):
                continue
            with open(path, "r", encoding="utf-8") as f:
                sql_text = f.read()
            with engine.begin() as conn:
                conn.execute(text(sql_text))
        return True, "Database berhasil diinisialisasi."
    except Exception as e:  # noqa: BLE001
        logger.error("init_database gagal: %s", e)
        return False, "Inisialisasi database gagal. Periksa file SQL atau hak akses."


def clear_cache() -> None:
    """Bersihkan cache data Streamlit (dipanggil setelah operasi write)."""
    try:
        st.cache_data.clear()
    except Exception:  # noqa: BLE001
        pass

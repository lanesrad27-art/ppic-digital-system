"""
formatting.py
Helper format angka & tanggal yang konsisten untuk seluruh aplikasi.
"""

from datetime import datetime, date


def fmt_int(val) -> str:
    """Format angka jadi integer dengan pemisah ribuan: 12.345"""
    try:
        return f"{int(round(float(val))):,}".replace(",", ".")
    except (ValueError, TypeError):
        return "-" if val is None else str(val)


def fmt_rp(val) -> str:
    """Format nilai Rupiah konsisten: Rp 2.380.000"""
    try:
        v = int(round(float(val)))
        return f"Rp {v:,}".replace(",", ".")
    except (ValueError, TypeError):
        return "-" if val is None else str(val)


def fmt_pct(val, decimals: int = 1) -> str:
    """Format persentase: 12.5%"""
    try:
        return f"{float(val):.{decimals}f}%"
    except (ValueError, TypeError):
        return "-" if val is None else str(val)


def fmt_date(val, fmt: str = "%d/%m/%Y") -> str:
    """Format tanggal jadi string. Menerima datetime, date, atau string ISO."""
    if val is None or val == "":
        return "-"
    try:
        if isinstance(val, (datetime, date)):
            return val.strftime(fmt)
        parsed = datetime.fromisoformat(str(val).replace("Z", "+00:00"))
        return parsed.strftime(fmt)
    except (ValueError, TypeError):
        return str(val)
<<<<<<< HEAD


def to_excel_bytes(df, sheet_name: str = "Sheet1") -> bytes:
    """
    Konversi DataFrame menjadi file Excel (.xlsx) dalam bentuk bytes.
    Fallback ke CSV-bytes bila engine Excel tidak tersedia.
    """
    import io
    import pandas as pd
    buffer = io.BytesIO()
    try:
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name=(sheet_name[:31] or "Sheet1"))
        return buffer.getvalue()
    except Exception:
        return df.to_csv(index=False).encode("utf-8")
=======
>>>>>>> b9a8ad24d2e85e6ab546af78e0b7f10b26833f82

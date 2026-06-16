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

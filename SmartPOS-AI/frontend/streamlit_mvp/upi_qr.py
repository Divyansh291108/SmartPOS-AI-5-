"""
Generates a standard NPCI UPI deep link + QR code for a given amount.
"""
import io
from urllib.parse import quote

import qrcode


def build_upi_uri(payee_vpa: str, payee_name: str, amount: float, txn_note: str, txn_ref: str) -> str:
    if not payee_vpa:
        raise ValueError("No UPI ID configured for this shop.")
    params = {
        "pa": payee_vpa,
        "pn": payee_name,
        "am": f"{amount:.2f}",
        "cu": "INR",
        "tn": txn_note,
        "tr": txn_ref,
    }
    query = "&".join(f"{k}={quote(str(v))}" for k, v in params.items())
    return f"upi://pay?{query}"


def generate_qr_png(upi_uri: str) -> bytes:
    img = qrcode.make(upi_uri, box_size=8, border=2)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
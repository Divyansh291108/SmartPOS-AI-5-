"""
Thin HTTP client for the SmartPOS AI backend.

This is the ONLY place in the frontend that knows the backend exists.
Every page calls functions here instead of touching requests/URLs
directly, so if the API shape changes later, only this file needs to change.

Backend URL defaults to localhost for local dev; override with the
SMARTPOS_API_URL environment variable when the backend runs elsewhere
(e.g. a deployed URL).

Auth: the backend now requires a bearer token for checkout, refunds,
catalog resets/uploads, user registration, and the AI assistant. Every
function that needs one takes `token` as an explicit argument rather than
storing it globally — Streamlit can serve multiple users from one running
server process, and a module-level token would leak between sessions.
Callers (app.py) keep the token in st.session_state and pass it in.
"""
import os
import pandas as pd
import requests

API_BASE_URL = os.environ.get("SMARTPOS_API_URL", "http://localhost:8000").rstrip("/")
TIMEOUT = 30  # the assistant endpoint calls an LLM and can be slow


class APIError(Exception):
    """Raised for both connection failures and non-2xx responses, so
    callers only need one except clause."""
    pass


class AuthError(APIError):
    """Specifically a 401 — callers should treat this as 'log in again',
    not just 'show an error message'."""
    pass


def _headers(token=None):
    return {"Authorization": f"Bearer {token}"} if token else {}


def _get(path, params=None, token=None):
    try:
        r = requests.get(f"{API_BASE_URL}{path}", params=params, headers=_headers(token), timeout=TIMEOUT)
    except requests.RequestException as e:
        raise APIError(f"Couldn't reach the backend at {API_BASE_URL}: {e}")
    return _unwrap(r)


def _post(path, json=None, files=None, params=None, data=None, token=None,TIMEOUT: int = 120):
    try:
        r = requests.post(f"{API_BASE_URL}{path}", json=json, files=files, params=params,
                           data=data, headers=_headers(token), timeout=TIMEOUT)
    except requests.RequestException as e:
        raise APIError(f"Couldn't reach the backend at {API_BASE_URL}: {e}")
    return _unwrap(r)


def _unwrap(resp):
    if resp.status_code == 401:
        raise AuthError("Session expired or invalid — please sign in again.")
    if resp.status_code >= 400:
        try:
            detail = resp.json().get("detail", resp.text)
        except Exception:
            detail = resp.text
        raise APIError(str(detail))
    return resp.json()


def is_healthy() -> bool:
    try:
        r = requests.get(f"{API_BASE_URL}/", timeout=3)
        return r.status_code == 200
    except requests.RequestException:
        return False


# --------------------------------------------------------------------------
# Auth
# --------------------------------------------------------------------------
def login(username: str, password: str) -> dict:
    """OAuth2PasswordRequestForm on the backend expects form-encoded data,
    not JSON — hence `data=` here instead of `json=`.
    Returns {"access_token", "token_type", "role", "username"}."""
    return _post("/auth/login", data={"username": username, "password": password})


def register(username: str, password: str, role: str, token: str) -> dict:
    """Owner-only — creates a new cashier/owner login."""
    return _post("/auth/register", json={"username": username, "password": password, "role": role}, token=token)


def whoami(token: str) -> dict:
    return _get("/auth/me", token=token)


# --------------------------------------------------------------------------
# Products
# --------------------------------------------------------------------------
def _products_to_df(data) -> pd.DataFrame:
    df = pd.DataFrame(data)
    if not df.empty:
        df["expiry_date"] = pd.to_datetime(df["expiry_date"], errors="coerce")
        df["expiry_date"] = df["expiry_date"].dt.date.where(df["expiry_date"].notna(), None)
    return df


def get_products() -> pd.DataFrame:
    return _products_to_df(_get("/products/"))


def seed_sample_products(token: str) -> pd.DataFrame:
    return _products_to_df(_post("/products/seed-sample", token=token))


def upload_excel(uploaded_file, token: str) -> pd.DataFrame:
    files = {"file": (uploaded_file.name, uploaded_file.getvalue(),
                       "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    return _products_to_df(_post("/products/upload", files=files, token=token))


def get_reorder_suggestions() -> pd.DataFrame:
    return pd.DataFrame(_get("/products/reorder-suggestions"))


# --------------------------------------------------------------------------
# Transactions
# --------------------------------------------------------------------------
def checkout(items: list, payment_method: str, token: str) -> dict:
    """items: list of {"product_id": str, "qty": int, "discount_pct": float}.
    Cashier isn't passed explicitly — the backend attributes the sale to
    whichever user the token belongs to."""
    return _post("/transactions/", json={"items": items, "payment_method": payment_method}, token=token)


def refund(original_txn_id: str, product_id: str, qty: int, token: str) -> dict:
    return _post("/transactions/refund",
                  json={"original_txn_id": original_txn_id, "product_id": product_id, "qty": qty}, token=token)


def get_todays_transactions() -> pd.DataFrame:
    return pd.DataFrame(_get("/transactions/today"))


def get_transaction_history(days: int = 30, start_date=None, end_date=None) -> pd.DataFrame:
    params = {"days": days}
    if start_date and end_date:
        params = {"start_date": start_date.isoformat(), "end_date": end_date.isoformat()}
    df = pd.DataFrame(_get("/transactions/history", params=params))
    if not df.empty:
        df["timestamp"] = pd.to_datetime(df["timestamp"], format="ISO8601")
        df["date"] = df["timestamp"].dt.date
    return df


def reseed_sample_history(token: str, days: int = 30) -> dict:
    return _post("/transactions/seed-sample", params={"days": days}, token=token)


def get_fraud_alerts() -> pd.DataFrame:
    return pd.DataFrame(_get("/transactions/fraud-alerts"))


# --------------------------------------------------------------------------
# Dashboard
# --------------------------------------------------------------------------
def get_dashboard_summary(start_date=None, end_date=None) -> dict:
    params = {}
    if start_date and end_date:
        params = {"start_date": start_date.isoformat(), "end_date": end_date.isoformat()}
    return _get("/dashboard/summary", params=params)


# --------------------------------------------------------------------------
# AI Assistant
# --------------------------------------------------------------------------
def ask_assistant(question: str, token: str) -> str:
    result = _post("/assistant/ask", json={"question": question}, token=token)
    return result["answer"]

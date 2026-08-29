"""
Product business logic: seeding sample data, validating/loading an uploaded
Excel catalog, and computing reorder suggestions from real transaction
history (not simulated history, since the backend has actual data now).
"""
import io
from datetime import datetime, timedelta

import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import func

from models.product import Product
from models.transaction import Transaction

REQUIRED_COLUMNS = ["name", "category", "price", "cost", "stock", "reorder_level"]
OPTIONAL_COLUMNS = ["expiry_days", "gst_rate"]

# Same 25-SKU set as the frontend's mock_data.py, kept here too so the
# backend can seed itself without importing anything from frontend/.
# Added a 7th field: an approximate GST slab (%) per product category —
# 0/5/12/18 are the real Indian GST slabs; exact HSN-code-level rates
# should be entered per product for real use, this is a reasonable default.
SAMPLE_PRODUCTS = [
    ("Basmati Rice 5kg", "Grocery", 480, 390, 42, 15, None, 5),
    ("Toor Dal 1kg", "Grocery", 165, 128, 8, 20, None, 5),
    ("Sunflower Oil 1L", "Grocery", 145, 118, 55, 25, None, 5),
    ("Sugar 1kg", "Grocery", 48, 40, 90, 30, None, 5),
    ("Wheat Atta 5kg", "Grocery", 260, 210, 12, 20, None, 5),
    ("Toned Milk 1L", "Dairy", 62, 52, 30, 40, 3, 0),
    ("Paneer 200g", "Dairy", 90, 70, 6, 15, 4, 5),
    ("Butter 500g", "Dairy", 275, 230, 18, 12, 60, 12),
    ("Curd 400g", "Dairy", 40, 32, 22, 25, 5, 0),
    ("Cola 750ml", "Beverages", 45, 34, 60, 30, 180, 18),
    ("Packaged Juice 1L", "Beverages", 110, 88, 14, 20, 90, 12),
    ("Instant Coffee 100g", "Beverages", 210, 165, 25, 15, 365, 18),
    ("Potato Chips 90g", "Snacks", 30, 21, 75, 40, 120, 12),
    ("Biscuits Family Pack", "Snacks", 55, 40, 5, 30, 150, 18),
    ("Namkeen Mix 400g", "Snacks", 95, 72, 33, 20, 90, 12),
    ("Shampoo 340ml", "Personal Care", 220, 175, 19, 10, 730, 18),
    ("Toothpaste 150g", "Personal Care", 95, 74, 27, 15, 730, 18),
    ("Hand Wash 250ml", "Personal Care", 85, 65, 3, 12, 730, 18),
    ("Dish Wash Liquid 500ml", "Household", 120, 92, 21, 15, None, 18),
    ("Detergent Powder 1kg", "Household", 135, 105, 40, 20, None, 18),
    ("Fresh Bread", "Bakery", 45, 30, 10, 25, 2, 5),
    ("Cake Slice Pack", "Bakery", 60, 40, 4, 10, 3, 5),
    ("Paracetamol 10 tabs", "Pharmacy", 22, 14, 60, 30, 400, 12),
    ("Cough Syrup 100ml", "Pharmacy", 85, 60, 9, 15, 200, 12),
    ("Antacid Tablets", "Pharmacy", 35, 24, 5, 20, 250, 12),
]


class DataValidationError(Exception):
    pass


def seed_sample_data(db: Session, force: bool = False):
    """Populate the products table with the demo catalog, but only if it's
    empty — safe to call on every app startup without wiping real data.
    force=True also clears transaction history, since old transactions
    would otherwise reference product_ids that no longer exist."""
    if not force and db.query(Product).first() is not None:
        return
    if force:
        db.query(Transaction).delete()
    db.query(Product).delete()
    today = datetime.now()
    for i, (name, cat, price, cost, stock, reorder, exp_days, gst_rate) in enumerate(SAMPLE_PRODUCTS):
        expiry = (today + timedelta(days=exp_days)).date() if exp_days else None
        db.add(Product(
            product_id=f"P{i+1:03d}", name=name, category=cat,
            price=price, cost=cost, stock=stock, reorder_level=reorder,
            expiry_date=expiry, gst_rate=gst_rate,
        ))
    db.commit()


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]

    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise DataValidationError(
            f"Missing required column(s): {', '.join(missing)}. "
            f"Required: {', '.join(REQUIRED_COLUMNS)} (optional: {', '.join(OPTIONAL_COLUMNS)})."
        )
    if "expiry_days" not in df.columns:
        df["expiry_days"] = None
    if "gst_rate" not in df.columns:
        df["gst_rate"] = 0.0
    df["gst_rate"] = pd.to_numeric(df["gst_rate"], errors="coerce").fillna(0.0)

    numeric_cols = ["price", "cost", "stock", "reorder_level"]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    if df[numeric_cols].isna().any().any():
        bad_rows = df[df[numeric_cols].isna().any(axis=1)]
        raise DataValidationError(
            f"{len(bad_rows)} row(s) have non-numeric price/cost/stock/reorder_level "
            f"(rows: {bad_rows.index.tolist()[:10]})."
        )

    df["name"] = df["name"].astype(str).str.strip()
    df["category"] = df["category"].astype(str).str.strip()
    if df["name"].eq("").any():
        raise DataValidationError("Every row needs a non-empty product name.")

    today = datetime.now()

    def to_expiry_date(v):
        if pd.isna(v) or v is None or str(v).strip() == "":
            return None
        try:
            return (today + timedelta(days=int(v))).date()
        except (ValueError, TypeError):
            return None

    df["expiry_date"] = df["expiry_days"].apply(to_expiry_date)
    df = df.reset_index(drop=True)
    df["product_id"] = [f"P{i+1:03d}" for i in range(len(df))]
    return df


def load_products_from_excel_bytes(file_bytes: bytes) -> pd.DataFrame:
    try:
        raw = pd.read_excel(io.BytesIO(file_bytes))
    except Exception as e:
        raise DataValidationError(f"Couldn't read that Excel file: {e}")
    if raw.empty:
        raise DataValidationError("The uploaded file has no rows.")
    return _normalize(raw)


def replace_all_products(db: Session, df: pd.DataFrame):
    """Wipes the product catalog and inserts the given DataFrame instead.
    Also clears transaction history — old transactions reference
    product_ids from the old catalog, which no longer exist, so keeping
    them around would corrupt dashboard/history queries. Simple 'replace'
    semantics for the MVP — an upsert-by-name would be a reasonable next
    step once this needs to support incremental updates."""
    db.query(Transaction).delete()
    db.query(Product).delete()
    for _, row in df.iterrows():
        db.add(Product(
            product_id=row["product_id"], name=row["name"], category=row["category"],
            price=float(row["price"]), cost=float(row["cost"]), stock=int(row["stock"]),
            reorder_level=int(row["reorder_level"]), expiry_date=row["expiry_date"],
            gst_rate=float(row.get("gst_rate", 0) or 0),
        ))
    db.commit()


def get_reorder_suggestions(db: Session, lookback_days: int = 30):
    """Low-stock products, with a suggested reorder quantity based on real
    sales velocity from the transactions table (falls back to a
    conservative default of 1/day if a product has no sales history yet)."""
    low_stock = db.query(Product).filter(Product.stock <= Product.reorder_level).all()
    since = datetime.utcnow() - timedelta(days=lookback_days)

    suggestions = []
    for p in low_stock:
        total_qty = (
            db.query(func.sum(Transaction.qty))
            .filter(Transaction.product_id == p.product_id, Transaction.timestamp >= since)
            .scalar()
        ) or 0
        avg_daily = round(total_qty / lookback_days, 1) if total_qty else 1.0
        suggested_qty = max(5, round(avg_daily * 14 - p.stock))
        suggestions.append({
            "product_id": p.product_id, "name": p.name, "stock": p.stock,
            "reorder_level": p.reorder_level, "avg_daily_sales": avg_daily,
            "suggested_order_qty": suggested_qty, "est_cost": round(suggested_qty * p.cost, 2),
        })
    return suggestions

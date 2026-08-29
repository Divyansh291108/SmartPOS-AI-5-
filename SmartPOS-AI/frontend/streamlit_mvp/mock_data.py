"""
Mock data generator for SmartPOS AI prototype.
Simulates a supermarket's product catalog, stock, and historical sales
so the dashboard/AI features have something realistic to show.
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

np.random.seed(42)

CATEGORIES = ["Grocery", "Dairy", "Beverages", "Snacks", "Personal Care", "Household", "Bakery", "Pharmacy"]

PRODUCTS = [
    # name, category, price, cost, stock, reorder_level, expiry_days (None = non-perishable)
    ("Basmati Rice 5kg", "Grocery", 480, 390, 42, 15, None),
    ("Toor Dal 1kg", "Grocery", 165, 128, 8, 20, None),
    ("Sunflower Oil 1L", "Grocery", 145, 118, 55, 25, None),
    ("Sugar 1kg", "Grocery", 48, 40, 90, 30, None),
    ("Wheat Atta 5kg", "Grocery", 260, 210, 12, 20, None),
    ("Toned Milk 1L", "Dairy", 62, 52, 30, 40, 3),
    ("Paneer 200g", "Dairy", 90, 70, 6, 15, 4),
    ("Butter 500g", "Dairy", 275, 230, 18, 12, 60),
    ("Curd 400g", "Dairy", 40, 32, 22, 25, 5),
    ("Cola 750ml", "Beverages", 45, 34, 60, 30, 180),
    ("Packaged Juice 1L", "Beverages", 110, 88, 14, 20, 90),
    ("Instant Coffee 100g", "Beverages", 210, 165, 25, 15, 365),
    ("Potato Chips 90g", "Snacks", 30, 21, 75, 40, 120),
    ("Biscuits Family Pack", "Snacks", 55, 40, 5, 30, 150),
    ("Namkeen Mix 400g", "Snacks", 95, 72, 33, 20, 90),
    ("Shampoo 340ml", "Personal Care", 220, 175, 19, 10, 730),
    ("Toothpaste 150g", "Personal Care", 95, 74, 27, 15, 730),
    ("Hand Wash 250ml", "Personal Care", 85, 65, 3, 12, 730),
    ("Dish Wash Liquid 500ml", "Household", 120, 92, 21, 15, None),
    ("Detergent Powder 1kg", "Household", 135, 105, 40, 20, None),
    ("Fresh Bread", "Bakery", 45, 30, 10, 25, 2),
    ("Cake Slice Pack", "Bakery", 60, 40, 4, 10, 3),
    ("Paracetamol 10 tabs", "Pharmacy", 22, 14, 60, 30, 400),
    ("Cough Syrup 100ml", "Pharmacy", 85, 60, 9, 15, 200),
    ("Antacid Tablets", "Pharmacy", 35, 24, 5, 20, 250),
]

def get_products_df():
    rows = []
    today = datetime.now()
    for i, (name, cat, price, cost, stock, reorder, exp_days) in enumerate(PRODUCTS):
        expiry = (today + timedelta(days=exp_days)).date() if exp_days else None
        rows.append({
            "product_id": f"P{i+1:03d}",
            "name": name,
            "category": cat,
            "price": price,
            "cost": cost,
            "stock": stock,
            "reorder_level": reorder,
            "expiry_date": expiry,
            "margin_pct": round((price - cost) / price * 100, 1),
        })
    return pd.DataFrame(rows)


def get_sales_history(days=30, products_df=None):
    """Simulate 30 days of past sales across products for forecasting/charts.

    Pass products_df to generate history against an uploaded/DB-sourced
    catalog instead of the built-in sample products (e.g. after the user
    loads their own data via the Data Source page).
    """
    products = products_df if products_df is not None else get_products_df()
    today = datetime.now().date()
    records = []
    for d in range(days, 0, -1):
        date = today - timedelta(days=d)
        weekday_boost = 1.4 if date.weekday() in (5, 6) else 1.0
        for _, p in products.iterrows():
            base_qty = np.random.poisson(lam=max(1, int(p["stock"] / 8)))
            qty = max(0, int(base_qty * weekday_boost * np.random.uniform(0.6, 1.3)))
            if qty == 0:
                continue
            payment = np.random.choice(["Cash", "UPI", "Card"], p=[0.35, 0.5, 0.15])
            records.append({
                "date": date,
                "product_id": p["product_id"],
                "name": p["name"],
                "category": p["category"],
                "qty": qty,
                "revenue": round(qty * p["price"], 2),
                "profit": round(qty * (p["price"] - p["cost"]), 2),
                "payment_method": payment,
            })
    return pd.DataFrame(records)


def get_fraud_alerts():
    return pd.DataFrame([
        {"time": "10:42 AM", "type": "Cash Mismatch", "detail": "Drawer short by ₹340 at counter 2", "severity": "High", "cashier": "Rahul S."},
        {"time": "12:15 PM", "type": "Unusual Refund", "detail": "3 refunds on same SKU within 10 min", "severity": "Medium", "cashier": "Priya K."},
        {"time": "1:03 PM", "type": "Discount Misuse", "detail": "Manual discount >20% applied 5x today", "severity": "Medium", "cashier": "Rahul S."},
        {"time": "3:20 PM", "type": "Suspicious Transaction", "detail": "Large cash sale just before shift change", "severity": "Low", "cashier": "Aman V."},
    ])

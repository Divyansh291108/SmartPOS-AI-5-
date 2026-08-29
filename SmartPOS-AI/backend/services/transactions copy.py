from datetime import datetime, date, timedelta

import numpy as np
from sqlalchemy.orm import Session
from sqlalchemy import func

from models.product import Product
from models.transaction import Transaction


class CheckoutError(Exception):
    pass


"""def checkout(db: Session, items: list, payment_method: str, cashier: str = None) -> dict:
    [items: list of {"product_id": str, "qty": int, "discount_pct": float}.
    Validates stock, creates one Transaction row per line, decrements stock
    — all inside one commit so a bad line rolls back the whole checkout.

    Tax note: product.price is treated as MRP (tax-inclusive), matching how
    Indian retail prices are normally displayed. Tax is backed out of that
    price using each product's gst_rate, then split evenly into CGST/SGST —
    correct for intra-state sales (the common case for a single store).
    Inter-state IGST and actual GSTN e-invoice/IRN submission are NOT
    implemented — see backend/README.md for what that would still require.
    ]
    txn_id = f"TXN{int(datetime.utcnow().timestamp() * 1000) % 10**8:08d}"
    lines = []
    total = 0.0
    taxable_value = 0.0
    total_tax = 0.0

    for item in items:
        product = db.query(Product).filter(Product.product_id == item["product_id"]).first()
        if product is None:
            raise CheckoutError(f"Unknown product_id: {item['product_id']}")
        if product.stock < item["qty"]:
            raise CheckoutError(
                f"Not enough stock for {product.name}: have {product.stock}, wanted {item['qty']}"
            )

        discount_pct = float(item.get("discount_pct", 0) or 0)
        effective_price = product.price * (1 - discount_pct / 100)
        revenue = round(effective_price * item["qty"], 2)
        profit = round((effective_price - product.cost) * item["qty"], 2)
        total += revenue

        gst_rate = product.gst_rate or 0.0
        line_taxable = revenue / (1 + gst_rate / 100)
        line_tax = revenue - line_taxable
        taxable_value += line_taxable
        total_tax += line_tax

        txn = Transaction(
            txn_id=txn_id, product_id=product.product_id, name=product.name,
            qty=item["qty"], revenue=revenue, profit=profit,
            payment_method=payment_method, cashier=cashier or "Unknown",
            discount_pct=discount_pct, is_refund=False,
            timestamp=datetime.utcnow(),
        )
        db.add(txn)
        product.stock -= item["qty"]
        lines.append(txn)

    db.commit()
    for line in lines:
        db.refresh(line)

    return {
        "txn_id": txn_id, "total": round(total, 2), "payment_method": payment_method, "lines": lines,
        "taxable_value": round(taxable_value, 2),
        "cgst": round(total_tax / 2, 2), "sgst": round(total_tax / 2, 2), "total_tax": round(total_tax, 2),
    }"""

def checkout(
    db: Session,
    items: list,
    payment_method: str,
    cashier: str = None
) -> dict:

    txn_id = f"TXN{int(datetime.utcnow().timestamp() * 1000) % 10**8:08d}"

    lines = []
    total = 0.0
    taxable_value = 0.0
    total_tax = 0.0

    try:
        for item in items:

            product = (
                db.query(Product)
                .filter(Product.product_id == item["product_id"])
                .first()
            )

            if product is None:
                raise CheckoutError(
                    f"Unknown product_id: {item['product_id']}"
                )

            qty = int(item["qty"])

            if qty <= 0:
                raise CheckoutError(
                    f"Invalid quantity for {product.name}: {qty}"
                )

            if product.stock < qty:
                raise CheckoutError(
                    f"Not enough stock for {product.name}: "
                    f"have {product.stock}, wanted {qty}"
                )

            # -------------------------
            # Discount
            # -------------------------

            discount_pct = float(
                item.get("discount_pct", 0) or 0
            )

            if discount_pct < 0 or discount_pct > 100:
                raise CheckoutError(
                    f"Invalid discount for {product.name}: "
                    f"{discount_pct}%"
                )

            effective_price = (
                product.price *
                (1 - discount_pct / 100)
            )

            revenue = round(
                effective_price * qty,
                2
            )

            profit = round(
                (effective_price - product.cost) * qty,
                2
            )

            total += revenue

            # -------------------------
            # GST
            # -------------------------

            gst_rate = float(
                product.gst_rate or 0.0
            )

            # price is GST-inclusive
            line_taxable = round(
                revenue / (1 + gst_rate / 100),
                2
            )

            line_tax = round(
                revenue - line_taxable,
                2
            )

            taxable_value += line_taxable
            total_tax += line_tax

            # -------------------------
            # Transaction
            # -------------------------

            txn = Transaction(
                txn_id=txn_id,
                product_id=product.product_id,
                name=product.name,
                qty=qty,
                revenue=revenue,
                profit=profit,
                payment_method=payment_method,
                cashier=cashier or "Unknown",
                discount_pct=discount_pct,
                is_refund=False,
                timestamp=datetime.utcnow(),
            )

            db.add(txn)

            # Reduce stock
            product.stock -= qty

            lines.append(txn)

        # -------------------------
        # Final totals
        # -------------------------

        total = round(total, 2)
        taxable_value = round(taxable_value, 2)
        total_tax = round(total_tax, 2)

        cgst = round(total_tax / 2, 2)
        sgst = round(total_tax - cgst, 2)

        # -------------------------
        # Commit everything
        # -------------------------

        db.commit()

        for line in lines:
            db.refresh(line)

        return {
            "txn_id": txn_id,
            "total": total,
            "payment_method": payment_method,
            "lines": lines,
            "taxable_value": taxable_value,
            "cgst": cgst,
            "sgst": sgst,
            "total_tax": total_tax,
        }

    except Exception:
        db.rollback()
        raise

class RefundError(Exception):
    pass


def refund(db: Session, original_txn_id: str, product_id: str, qty: int, cashier: str = None) -> Transaction:
    """Records a refund as a negative-value Transaction row (is_refund=True)
    and restocks the item. Kept separate from checkout() since refunds have
    different validation (must reference a real prior sale) and are the
    signal fraud detection watches for."""
    original = (
        db.query(Transaction)
        .filter(Transaction.txn_id == original_txn_id, Transaction.product_id == product_id, Transaction.is_refund.is_(False))
        .first()
    )
    if original is None:
        raise RefundError(f"No original sale found for txn {original_txn_id} / product {product_id}")
    if qty > original.qty:
        raise RefundError(f"Cannot refund {qty} — original sale was only {original.qty}")

    product = db.query(Product).filter(Product.product_id == product_id).first()
    unit_revenue = original.revenue / original.qty
    unit_profit = original.profit / original.qty

    refund_txn = Transaction(
        txn_id=f"RFND{int(datetime.utcnow().timestamp() * 1000) % 10**8:08d}",
        product_id=product_id, name=original.name, qty=qty,
        revenue=-round(unit_revenue * qty, 2), profit=-round(unit_profit * qty, 2),
        payment_method=original.payment_method, cashier=cashier or "Unknown",
        is_refund=True, discount_pct=original.discount_pct,
        timestamp=datetime.utcnow(),
    )
    db.add(refund_txn)
    if product:
        product.stock += qty
    db.commit()
    db.refresh(refund_txn)
    return refund_txn


def get_todays_transactions(db: Session):
    today = date.today()
    return (
        db.query(Transaction)
        .filter(func.date(Transaction.timestamp) == today.isoformat())
        .order_by(Transaction.timestamp.desc())
        .all()
    )


def seed_sample_history(db: Session, days: int = 30, force: bool = False):
    """Generate synthetic transactions for the past `days` days (not
    including today) so charts have something to show on a fresh database.
    Mirrors the frontend MVP's old mock_data.get_sales_history() logic, but
    writes real rows against whatever products currently exist — so it
    reflects your actual catalog, not a hardcoded one.

    Only runs if the transactions table is empty, unless force=True.
    """
    if not force and db.query(Transaction).first() is not None:
        return

    products = db.query(Product).all()
    if not products:
        return

    today_ = date.today()
    counter = 0
    for d in range(days, 0, -1):
        day = today_ - timedelta(days=d)
        weekday_boost = 1.4 if day.weekday() in (5, 6) else 1.0
        for p in products:
            base_qty = np.random.poisson(lam=max(1, int(p.stock / 8) or 1))
            qty = max(0, int(base_qty * weekday_boost * np.random.uniform(0.6, 1.3)))
            if qty == 0:
                continue
            payment = np.random.choice(["Cash", "UPI", "Card"], p=[0.35, 0.5, 0.15])
            counter += 1
            ts = datetime.combine(day, datetime.min.time()) + timedelta(hours=int(np.random.randint(8, 21)))
            db.add(Transaction(
                txn_id=f"HIST{day.strftime('%Y%m%d')}{counter:04d}",
                product_id=p.product_id, name=p.name, qty=qty,
                revenue=round(qty * p.price, 2), profit=round(qty * (p.price - p.cost), 2),
                payment_method=str(payment), timestamp=ts,
            ))
    db.commit()


def get_transaction_history(db: Session, days: int = 30):
    since = datetime.utcnow() - timedelta(days=days)
    return (
        db.query(Transaction)
        .filter(Transaction.timestamp >= since)
        .order_by(Transaction.timestamp)
        .all()
    )


def get_fraud_alerts(db: Session, window_minutes: int = 60, refund_threshold: int = 3,
                      discount_threshold_pct: float = 20.0, discount_count_threshold: int = 3):
    """Rule-based fraud detection over real transactions — no ML, just
    thresholds, but genuinely computed from what's in the database rather
    than hardcoded like the old frontend mock:

    - Refund spike: same cashier processes >= refund_threshold refunds
      within `window_minutes`.
    - Discount misuse: same cashier applies a discount >=
      discount_threshold_pct more than discount_count_threshold times today.
    """
    alerts = []
    today_start = datetime.combine(datetime.utcnow().date(), datetime.min.time())

    # Refund spikes — check every rolling window_minutes-wide window today
    refunds = (
        db.query(Transaction)
        .filter(Transaction.is_refund.is_(True), Transaction.timestamp >= today_start)
        .order_by(Transaction.timestamp)
        .all()
    )
    by_cashier = {}
    for r in refunds:
        by_cashier.setdefault(r.cashier, []).append(r.timestamp)
    for cashier, times in by_cashier.items():
        times.sort()
        for i in range(len(times) - refund_threshold + 1):
            window = times[i:i + refund_threshold]
            if (window[-1] - window[0]) <= timedelta(minutes=window_minutes):
                alerts.append({
                    "type": "Unusual Refund", "severity": "Medium",
                    "cashier": cashier, "timestamp": window[-1],
                    "detail": f"{refund_threshold} refunds by {cashier} within {window_minutes} minutes",
                })
                break  # one alert per cashier is enough, don't spam duplicates

    # Discount misuse
    big_discounts = (
        db.query(Transaction)
        .filter(Transaction.discount_pct >= discount_threshold_pct, Transaction.timestamp >= today_start)
        .all()
    )
    counts = {}
    for t in big_discounts:
        counts[t.cashier] = counts.get(t.cashier, 0) + 1
    for cashier, count in counts.items():
        if count >= discount_count_threshold:
            alerts.append({
                "type": "Discount Misuse", "severity": "Medium",
                "cashier": cashier, "timestamp": datetime.utcnow(),
                "detail": f"{cashier} applied discounts \u2265{discount_threshold_pct:.0f}% on {count} transactions today",
            })

    return alerts


def get_dashboard_summary(db: Session) -> dict:
    today_txns = get_todays_transactions(db)

    revenue = sum(t.revenue for t in today_txns)
    profit = sum(t.profit for t in today_txns)
    cash = sum(t.revenue for t in today_txns if t.payment_method == "Cash")
    upi = sum(t.revenue for t in today_txns if t.payment_method == "UPI")
    card = sum(t.revenue for t in today_txns if t.payment_method == "Card")
    txn_count = len(set(t.txn_id for t in today_txns))

    low_stock_count = db.query(Product).filter(Product.stock <= Product.reorder_level).count()
    near_cutoff = datetime.utcnow().date()
    expiring_soon_count = (
        db.query(Product)
        .filter(Product.expiry_date.isnot(None))
        .filter(Product.expiry_date <= near_cutoff.__class__.fromordinal(near_cutoff.toordinal() + 5))
        .count()
    )

    return {
        "revenue": round(revenue, 2), "profit": round(profit, 2),
        "cash": round(cash, 2), "upi": round(upi, 2), "card": round(card, 2),
        "transaction_count": txn_count,
        "low_stock_count": low_stock_count, "expiring_soon_count": expiring_soon_count,
    }

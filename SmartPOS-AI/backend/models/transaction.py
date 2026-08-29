from sqlalchemy import Column, String, Float, Integer, DateTime, ForeignKey, Boolean
from datetime import datetime
from database import Base


class Transaction(Base):
    """One row per product line in a checkout — a single txn_id groups
    several rows together, mirroring how the Streamlit MVP's cart worked."""
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    txn_id = Column(String, index=True, nullable=False)
    product_id = Column(String, ForeignKey("products.product_id"), nullable=False)
    name = Column(String, nullable=False)  # snapshot, in case the product is later renamed/removed
    qty = Column(Integer, nullable=False)
    revenue = Column(Float, nullable=False)
    profit = Column(Float, nullable=False)
    payment_method = Column(String, nullable=False)  # Cash | UPI | Card | Split
    cashier = Column(String, nullable=True, default="Unknown")
    is_refund = Column(Boolean, default=False)
    discount_pct = Column(Float, nullable=True, default=0.0)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)

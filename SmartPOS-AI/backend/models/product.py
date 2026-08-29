from sqlalchemy import Column, String, Float, Integer, Date
from database import Base


class Product(Base):
    __tablename__ = "products"

    product_id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    category = Column(String, nullable=False)
    price = Column(Float, nullable=False)  # MRP, tax-inclusive
    cost = Column(Float, nullable=False)
    stock = Column(Integer, nullable=False, default=0)
    reorder_level = Column(Integer, nullable=False, default=0)
    expiry_date = Column(Date, nullable=True)  # None = non-perishable
    gst_rate = Column(Float, nullable=False, default=0.0)  # e.g. 5, 12, 18 — % GST slab

    @property
    def margin_pct(self) -> float:
        if not self.price:
            return 0.0
        return round((self.price - self.cost) / self.price * 100, 1)

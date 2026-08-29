from datetime import date, datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class ProductOut(BaseModel):
    product_id: str
    name: str
    category: str
    price: float
    cost: float
    stock: int
    reorder_level: int
    expiry_date: Optional[date] = None
    margin_pct: float
    gst_rate: float = 0.0

    class Config:
        from_attributes = True  # lets this build directly from a SQLAlchemy Product


class ReorderSuggestion(BaseModel):
    product_id: str
    name: str
    stock: int
    reorder_level: int
    avg_daily_sales: float
    suggested_order_qty: int
    est_cost: float


class CartItem(BaseModel):
    product_id: str
    qty: int = Field(gt=0)
    discount_pct: float = 0.0


class CheckoutRequest(BaseModel):
    items: List[CartItem]
    payment_method: str  # "Cash" | "UPI" | "Card" | "Split"
    cashier: Optional[str] = None  # defaults to the authenticated user server-side


class RefundRequest(BaseModel):
    original_txn_id: str
    product_id: str
    qty: int = Field(gt=0)
    cashier: Optional[str] = None


class TransactionOut(BaseModel):
    txn_id: str
    product_id: str
    name: str
    qty: int
    revenue: float
    profit: float
    payment_method: str
    cashier: Optional[str] = None
    is_refund: bool = False
    discount_pct: float = 0.0
    timestamp: datetime

    class Config:
        from_attributes = True


class CheckoutResponse(BaseModel):
    txn_id: str
    total: float
    payment_method: str
    lines: List[TransactionOut]
    taxable_value: float = 0.0
    cgst: float = 0.0
    sgst: float = 0.0
    total_tax: float = 0.0


class DashboardSummary(BaseModel):
    revenue: float
    profit: float
    cash: float
    upi: float
    card: float
    transaction_count: int
    low_stock_count: int
    expiring_soon_count: int


# --------------------------------------------------------------------------
# Auth
# --------------------------------------------------------------------------
class UserCreate(BaseModel):
    username: str
    password: str
    role: str = "cashier"  # "owner" | "cashier"


class UserOut(BaseModel):
    id: int
    username: str
    role: str

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str
    role: str
    username: str


# --------------------------------------------------------------------------
# Fraud
# --------------------------------------------------------------------------
class FraudAlertOut(BaseModel):
    type: str
    detail: str
    severity: str  # "High" | "Medium" | "Low"
    cashier: str
    timestamp: datetime


# --------------------------------------------------------------------------
# Assistant
# --------------------------------------------------------------------------
class AssistantQuestion(BaseModel):
    question: str


class AssistantAnswer(BaseModel):
    answer: str

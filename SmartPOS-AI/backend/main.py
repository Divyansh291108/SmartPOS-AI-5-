"""
SmartPOS AI backend.

Run with:
    cd backend
    python3 -m venv .venv && source .venv/bin/activate
    pip install -r requirements.txt
    uvicorn main:app --reload

Then open http://localhost:8000/docs for interactive Swagger docs —
the fastest way to test every endpoint without writing any client code.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import engine, Base, SessionLocal
import models  # noqa: F401 — import registers Product/Transaction/User on Base.metadata
import services.products as products_service
import services.transactions as transactions_service
import services.auth_seed as auth_seed_service
from api import products, transactions, dashboard, auth as auth_api, assistant

Base.metadata.create_all(bind=engine)

app = FastAPI(title="SmartPOS AI API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten this before any real deployment
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(products.router, prefix="/products", tags=["products"])
app.include_router(transactions.router, prefix="/transactions", tags=["transactions"])
app.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
app.include_router(auth_api.router, prefix="/auth", tags=["auth"])
app.include_router(assistant.router, prefix="/assistant", tags=["assistant"])


@app.on_event("startup")
def seed_on_startup():
    """Populate sample data on first run only — never overwrites real data."""
    db = SessionLocal()
    try:
        products_service.seed_sample_data(db)
        transactions_service.seed_sample_history(db)
        auth_seed_service.seed_owner_if_none(db)
    finally:
        db.close()


@app.get("/")
def root():
    return {"status": "ok", "service": "SmartPOS AI API"}

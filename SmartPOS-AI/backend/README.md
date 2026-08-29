# Backend

A FastAPI service backing the SmartPOS AI product catalog, checkout, and
dashboard — currently standalone (the Streamlit MVP in `frontend/` still
talks to `mock_data.py`/`data_sources.py` directly; pointing it at this API
instead is the next step, not yet done).

## Run it

    cd backend
    python3 -m venv .venv
    source .venv/bin/activate        # macOS/Linux
    .venv\Scripts\activate           # Windows

    pip install -r requirements.txt
    uvicorn main:app --reload

Then open **http://localhost:8000/docs** — interactive Swagger UI where you
can call every endpoint and see real request/response shapes without
writing any client code.

On first run it creates `../database/smartpos.db` (SQLite) and seeds it
with the same 25-product demo catalog the frontend uses. That seed only
runs if the products table is empty, so it never overwrites real data on
restart.

## Structure

- `main.py` — FastAPI app, CORS, startup seeding, router registration
- `database.py` — engine/session setup. **The only file that changes** when
  moving from SQLite to Postgres (swap `DATABASE_URL`, add `psycopg2-binary`)
- `models/` — SQLAlchemy ORM classes (`Product`, `Transaction`)
- `schemas.py` — Pydantic request/response models
- `services/` — business logic (seeding, Excel validation, checkout,
  reorder suggestions, dashboard aggregation) — kept separate from the API
  layer so it's testable without spinning up HTTP
- `api/` — route definitions, one file per resource

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/products/` | List all products |
| POST | `/products/seed-sample` | Reset catalog to the 25-SKU demo set |
| POST | `/products/upload` | Replace catalog from an uploaded `.xlsx` |
| GET | `/products/reorder-suggestions` | Low-stock items + suggested reorder qty, based on real sales velocity |
| POST | `/transactions/` | Checkout — validates stock, decrements it, records one row per line item |
| GET | `/transactions/today` | Today's transaction lines |
| GET | `/dashboard/summary` | Revenue/cash/UPI/card/profit totals, alert counts |

## What's real vs. still a placeholder

- Checkout, stock decrement, and reorder suggestions use **real data** —
  reorder quantities are computed from actual `transactions` rows, not
  simulated history like the frontend MVP's mock data.
- There's no auth, no multi-store support, and no fraud-detection logic yet
  (the frontend's Fraud & Alerts page is still fully mocked).
- `replace_all_products()` wipes and reinserts the whole catalog on Excel
  upload — fine for the MVP, but an upsert-by-name would be needed before
  this supports incremental catalog updates.

## Tested

Every endpoint has been exercised with `TestClient`, including: seeding,
checkout (success + insufficient-stock 400), stock decrementing correctly,
Excel upload (success + missing-column 400), dashboard aggregation, and
reorder suggestions computed from real transaction history.

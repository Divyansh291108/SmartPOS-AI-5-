# Frontend

`streamlit_mvp/` — the working clickable MVP (Dashboard, Billing, Inventory,
AI Assistant, Fraud & Alerts). Run with a virtual environment:

    cd streamlit_mvp
    python3 -m venv .venv

    # activate it
    source .venv/bin/activate        # macOS/Linux
    .venv\Scripts\activate           # Windows (cmd/PowerShell)

    pip install -r requirements.txt
    streamlit run app.py

To leave the venv later: `deactivate`. `.venv/` is already covered by the
repo's `.gitignore`, so it never gets committed — each machine creates its
own.

## Data sources

The **🔌 Data Source** page lets you switch the product catalog between:

- **Sample data** — the built-in 25-SKU demo set.
- **Upload Excel** — download the template from that tab, fill it in
  (`name, category, price, cost, stock, reorder_level`, optional
  `expiry_days`), and upload it back.
- **Database** — either upload a SQLite `.db` file directly, or paste a
  SQLAlchemy connection string for a live Postgres/MySQL/etc. database and
  pick a table (or write a custom SQL query).

Switching sources regenerates the 30-day sales history against the new
catalog and clears the cart/today's transactions, since those reference
the old product IDs.

**Driver note:** `requirements.txt` includes `sqlalchemy` for the
connection-string path, but not a specific DB driver — install the one
your database needs, e.g. `pip install psycopg2-binary` for Postgres or
`pip install pymysql` for MySQL.

This is a prototype, not the production frontend. When ready to build the
real customer-facing app, this folder is where a React/Next.js (or similar)
project would live instead, consuming the backend/ API.

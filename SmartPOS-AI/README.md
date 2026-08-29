# SmartPOS AI

AI-powered Retail Operating System — payments, inventory, and business
intelligence for small and medium businesses.

## Repo layout

    SmartPOS-AI/
    ├── docs/          product & technical documentation (PRD, SRS, SDD, etc.)
    ├── backend/       API + business logic (not yet built)
    ├── frontend/      streamlit_mvp/ = the working clickable demo
    ├── hardware/      note validator / card reader integration specs
    ├── ai/            forecasting + fraud detection models
    ├── database/      schema and migrations
    ├── deployment/    Docker + CI/CD
    └── tests/         backend, ai, integration tests

## Quickest way to see the frontend running

    cd frontend/streamlit_mvp
    python3 -m venv .venv
    source .venv/bin/activate        # macOS/Linux
    .venv\Scripts\activate           # Windows

    pip install -r requirements.txt
    streamlit run app.py

`.venv/` is git-ignored — recreate it fresh on any machine you clone this
onto.

## Backend (new)

A working FastAPI + SQLite backend now exists in `backend/` — products,
checkout, reorder suggestions, and dashboard summary all run against a real
database instead of in-memory state. See `backend/README.md` for setup and
the full endpoint list.

**Not yet done:** the Streamlit frontend still imports `mock_data.py`
directly rather than calling this API — that wiring is the next step.

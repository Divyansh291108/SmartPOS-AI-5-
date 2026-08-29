"""
Database connection setup.

Dev default: SQLite file at ../database/smartpos.db (relative to this file,
so it lands in the repo's database/ folder regardless of where you launch
uvicorn from).

To move to Postgres later, this is the ONLY file that changes — swap
DATABASE_URL and add the driver (psycopg2-binary) to requirements.txt.
No model or route code needs to change, that's the point of using an ORM.
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "..", "database", "smartpos.db")

# Dev (SQLite) — no extra install needed:
DATABASE_URL = f"sqlite:///{DB_PATH}"

# Prod (Postgres) — uncomment and set via environment variable instead:
DATABASE_URL = os.environ["DATABASE_URL"]
# e.g. postgresql+psycopg2://user:password@host:5432/smartpos

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
#engine = create_engine(DATABASE_URL, connect_args=connect_args)
engine = create_engine(DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """FastAPI dependency — yields a session, always closes it after the request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

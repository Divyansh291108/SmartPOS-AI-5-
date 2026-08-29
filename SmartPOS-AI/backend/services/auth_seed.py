"""
Creates the very first owner account on startup, if no users exist yet.
Credentials come from environment variables so a real password never sits
in source control. Change these before running anywhere but localhost.
"""
import os
from sqlalchemy.orm import Session

from models.user import User
from auth import hash_password

DEFAULT_OWNER_USERNAME = os.environ.get("SMARTPOS_OWNER_USERNAME", "owner")
DEFAULT_OWNER_PASSWORD = os.environ.get("SMARTPOS_OWNER_PASSWORD", "changeme123")


def seed_owner_if_none(db: Session):
    if db.query(User).first() is not None:
        return
    db.add(User(
        username=DEFAULT_OWNER_USERNAME,
        hashed_password=hash_password(DEFAULT_OWNER_PASSWORD),
        role="owner",
    ))
    db.commit()

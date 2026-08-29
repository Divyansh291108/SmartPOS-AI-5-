from sqlalchemy import Column, String, Integer, Boolean
from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, nullable=False, default="cashier")  # "owner" | "cashier"
    is_active = Column(Boolean, default=True)

# Import every model here so Base.metadata.create_all() in main.py
# actually sees them and creates their tables.
from models.product import Product
from models.transaction import Transaction
from models.user import User

__all__ = ["Product", "Transaction", "User"]

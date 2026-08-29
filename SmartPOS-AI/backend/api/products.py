from typing import List

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models.product import Product
from models.user import User
from auth import require_owner
import schemas
import services.products as products_service

router = APIRouter()


@router.get("/", response_model=List[schemas.ProductOut])
def list_products(db: Session = Depends(get_db)):
    return db.query(Product).order_by(Product.category, Product.name).all()


@router.post("/seed-sample", response_model=List[schemas.ProductOut])
def seed_sample(db: Session = Depends(get_db), _owner: User = Depends(require_owner)):
    """Reset the catalog to the built-in 25-SKU demo set. Owner-only —
    this wipes the real catalog and transaction history."""
    products_service.seed_sample_data(db, force=True)
    return db.query(Product).all()


@router.post("/upload", response_model=List[schemas.ProductOut])
async def upload_excel(file: UploadFile = File(...), db: Session = Depends(get_db),
                        _owner: User = Depends(require_owner)):
    """Replace the product catalog with an uploaded Excel file. Owner-only.
    Required columns: name, category, price, cost, stock, reorder_level
    Optional: expiry_days, gst_rate"""
    contents = await file.read()
    try:
        df = products_service.load_products_from_excel_bytes(contents)
    except products_service.DataValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))

    products_service.replace_all_products(db, df)
    return db.query(Product).all()


@router.get("/reorder-suggestions", response_model=List[schemas.ReorderSuggestion])
def reorder_suggestions(db: Session = Depends(get_db)):
    return products_service.get_reorder_suggestions(db)

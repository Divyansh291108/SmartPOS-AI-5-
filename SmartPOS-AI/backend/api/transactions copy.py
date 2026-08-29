from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models.user import User
from auth import get_current_user, require_owner
import schemas
import services.transactions as txn_service

router = APIRouter()


@router.post("/", response_model=schemas.CheckoutResponse)
def checkout(request: schemas.CheckoutRequest, db: Session = Depends(get_db),
             current_user: User = Depends(get_current_user)):
    try:
        result = txn_service.checkout(
            db, items=[i.model_dump() for i in request.items],
            payment_method=request.payment_method,
            cashier=request.cashier or current_user.username,
        )
    except txn_service.CheckoutError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return result


@router.post("/refund", response_model=schemas.TransactionOut)
def refund(request: schemas.RefundRequest, db: Session = Depends(get_db),
           current_user: User = Depends(get_current_user)):
    try:
        return txn_service.refund(
            db, original_txn_id=request.original_txn_id, product_id=request.product_id,
            qty=request.qty, cashier=request.cashier or current_user.username,
        )
    except txn_service.RefundError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/fraud-alerts", response_model=List[schemas.FraudAlertOut])
def fraud_alerts(db: Session = Depends(get_db)):
    return txn_service.get_fraud_alerts(db)


@router.get("/today", response_model=List[schemas.TransactionOut])
def todays_transactions(db: Session = Depends(get_db)):
    return txn_service.get_todays_transactions(db)


@router.get("/history", response_model=List[schemas.TransactionOut])
def transaction_history(days: int = 30, db: Session = Depends(get_db)):
    """Raw transaction lines for the last `days` days — the frontend groups
    these by date/category itself for charting, same shape it already used
    with the old mock data."""
    return txn_service.get_transaction_history(db, days=days)


@router.post("/seed-sample")
def seed_sample_history(days: int = 30, db: Session = Depends(get_db), _owner: User = Depends(require_owner)):
    """Regenerate synthetic sales history against the current product
    catalog. Useful after resetting/uploading a new catalog so the
    Dashboard charts have something to show immediately."""
    txn_service.seed_sample_history(db, days=days, force=True)
    return {"status": "ok", "days": days}

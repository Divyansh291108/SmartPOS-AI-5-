from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
import schemas
import services.transactions as txn_service

router = APIRouter()


@router.get("/summary", response_model=schemas.DashboardSummary)
def dashboard_summary(db: Session = Depends(get_db)):
    return txn_service.get_dashboard_summary(db)

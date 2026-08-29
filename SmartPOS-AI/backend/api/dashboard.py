from datetime import date
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database import get_db
import schemas
import services.transactions as txn_service

router = APIRouter()


@router.get("/summary", response_model=schemas.DashboardSummary)
def dashboard_summary(
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    db: Session = Depends(get_db),
):
    return txn_service.get_dashboard_summary(db, start_date=start_date, end_date=end_date)
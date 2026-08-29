from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models.user import User
from auth import get_current_user
import schemas
import services.assistant as assistant_service

router = APIRouter()


@router.post("/ask", response_model=schemas.AssistantAnswer)
def ask(request: schemas.AssistantQuestion, db: Session = Depends(get_db),
        _current_user: User = Depends(get_current_user)):
    try:
        answer = assistant_service.ask(db, request.question)
    except assistant_service.AssistantError as e:
        raise HTTPException(status_code=503, detail=str(e))
    return {"answer": answer}

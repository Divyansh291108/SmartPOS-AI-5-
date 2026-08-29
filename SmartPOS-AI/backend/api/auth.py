from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from database import get_db
from models.user import User
from auth import authenticate_user, create_access_token, hash_password, require_owner, get_current_user
import schemas

router = APIRouter()


@router.post("/login", response_model=schemas.Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    token = create_access_token({"sub": user.username, "role": user.role})
    return {"access_token": token, "token_type": "bearer", "role": user.role, "username": user.username}


@router.post("/register", response_model=schemas.UserOut)
def register(new_user: schemas.UserCreate, db: Session = Depends(get_db), _owner: User = Depends(require_owner)):
    """Only an existing owner can create new accounts — see seed_owner_if_none()
    in main.py for how the very first owner account gets created."""
    if db.query(User).filter(User.username == new_user.username).first():
        raise HTTPException(status_code=400, detail="Username already exists")
    user = User(username=new_user.username, hashed_password=hash_password(new_user.password), role=new_user.role)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.get("/me", response_model=schemas.UserOut)
def me(current_user: User = Depends(get_current_user)):
    return current_user

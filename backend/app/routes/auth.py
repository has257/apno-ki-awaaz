from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    PasswordSetupRequest,
    RegisterRequest,
    TokenResponse,
)
from app.schemas.user import UserRead
from app.services import auth_service


router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    user, token = auth_service.register_user(db, payload)
    return {"access_token": token, "user": user}


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user, token = auth_service.authenticate_user(db, payload)
    return {"access_token": token, "user": user}


@router.post("/password/setup", response_model=UserRead)
def setup_password(
    payload: PasswordSetupRequest,
    db: Session = Depends(get_db),
):
    return auth_service.set_legacy_password(
        db,
        payload.setup_token,
        payload.new_password,
    )


@router.get("/me", response_model=UserRead)
def read_current_user(current_user: User = Depends(get_current_user)):
    return current_user
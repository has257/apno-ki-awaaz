from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.enums import UserRole
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest
from app.schemas.common import normalize_phone_number
from app.security import (
    create_access_token,
    decode_token,
    hash_password,
    validate_jwt_configuration,
    verify_password,
)


def register_user(db: Session, payload: RegisterRequest) -> tuple[User, str]:
    validate_jwt_configuration()
    user = User(
        full_name=payload.full_name,
        phone_number=payload.phone_number,
        role=payload.role,
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Phone number already registered") from None
    db.refresh(user)
    return user, create_access_token(user.id)


def authenticate_user(db: Session, payload: LoginRequest) -> tuple[User, str]:
    phone_number = normalize_phone_number(payload.phone_number)
    user = db.scalar(select(User).where(User.phone_number == phone_number))
    password_matches = verify_password(
        payload.password,
        user.password_hash if user is not None else None,
    )
    if user is None or not password_matches:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid phone number or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user, create_access_token(user.id)


def set_legacy_password(db: Session, setup_token: str, new_password: str) -> User:
    user_id = decode_token(setup_token, expected_purpose="password_setup")
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid or expired setup token")
    if user.password_hash is not None:
        raise HTTPException(status_code=409, detail="Password has already been set")

    password_hash = hash_password(new_password)
    result = db.execute(
        update(User)
        .where(User.id == user_id, User.password_hash.is_(None))
        .values(password_hash=password_hash)
    )
    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(status_code=409, detail="Password has already been set")
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Password could not be set") from None
    db.refresh(user)
    return user


def require_role(user: User, role: UserRole) -> None:
    if user.role != role:
        raise HTTPException(status_code=403, detail="Not authorized for this operation")
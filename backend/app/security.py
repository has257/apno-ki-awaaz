from datetime import datetime, timedelta, timezone
import secrets

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import HTTPException, status

from app.config import settings


JWT_ISSUER = "apno-ki-awaaz"
password_hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2)
DUMMY_PASSWORD_HASH = password_hasher.hash(secrets.token_urlsafe(32))


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    hash_to_verify = password_hash or DUMMY_PASSWORD_HASH
    try:
        return password_hasher.verify(hash_to_verify, password)
    except (VerificationError, InvalidHashError, TypeError):
        return False


def _jwt_secret() -> str:
    secret = settings.jwt_secret
    if secret is None or len(secret.encode("utf-8")) < 32:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is not configured",
        )
    return secret


def validate_jwt_configuration() -> None:
    _jwt_secret()


def create_token(subject: int, *, purpose: str, expires_minutes: int) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(subject),
        "iss": JWT_ISSUER,
        "iat": now,
        "exp": now + timedelta(minutes=expires_minutes),
        "purpose": purpose,
    }
    return jwt.encode(payload, _jwt_secret(), algorithm="HS256")


def create_access_token(user_id: int) -> str:
    return create_token(
        user_id,
        purpose="access",
        expires_minutes=settings.jwt_access_token_expire_minutes,
    )


def create_password_setup_token(user_id: int) -> str:
    return create_token(user_id, purpose="password_setup", expires_minutes=15)


def decode_token(token: str, *, expected_purpose: str) -> int:
    try:
        payload = jwt.decode(
            token,
            _jwt_secret(),
            algorithms=["HS256"],
            issuer=JWT_ISSUER,
            options={"require": ["sub", "iss", "iat", "exp", "purpose"]},
        )
        if payload.get("purpose") != expected_purpose:
            raise jwt.InvalidTokenError("Wrong token purpose")
        subject = int(payload["sub"])
        if subject <= 0:
            raise jwt.InvalidTokenError("Invalid subject")
        return subject
    except HTTPException:
        raise
    except (jwt.PyJWTError, TypeError, ValueError, KeyError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired credentials",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None
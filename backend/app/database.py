from collections.abc import Generator
import logging

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.exc import ArgumentError, OperationalError, SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings


logger = logging.getLogger(__name__)

engine: Engine | None = None
database_configuration_error: str | None = None

if settings.database_url:
    try:
        engine = create_engine(settings.database_url, pool_pre_ping=True)
    except (ArgumentError, ImportError) as exc:
        database_configuration_error = type(exc).__name__

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    if engine is None:
        if database_configuration_error:
            detail = "Database configuration is invalid"
        else:
            detail = "DATABASE_URL is not configured"
        raise HTTPException(status_code=503, detail=detail)

    db = SessionLocal()
    try:
        yield db
    except OperationalError as exc:
        db.rollback()
        logger.warning("Database operation failed (%s)", type(exc).__name__)
        raise HTTPException(
            status_code=503,
            detail="Database connection failed",
        ) from None
    except SQLAlchemyError as exc:
        db.rollback()
        logger.error("Database operation failed (%s)", type(exc).__name__)
        raise HTTPException(
            status_code=500,
            detail="Database operation failed",
        ) from None
    finally:
        db.close()
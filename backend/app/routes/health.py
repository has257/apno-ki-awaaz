import logging

from fastapi import APIRouter
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.database import database_configuration_error, engine


logger = logging.getLogger(__name__)

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "message": "Apno Ki Awaaz backend is running"
    }


@router.get("/health/database")
def database_health_check():
    if engine is None:
        if database_configuration_error:
            detail = "Database configuration is invalid"
        else:
            detail = "DATABASE_URL is not configured"
        raise HTTPException(status_code=503, detail=detail)

    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        logger.warning("Database health check failed (%s)", type(exc).__name__)
        raise HTTPException(
            status_code=503,
            detail="Database connection failed",
        ) from None

    return {"status": "healthy", "database": "connected"}
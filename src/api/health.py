"""Health check endpoints"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src import __version__
from src.common.config import get_settings
from src.storage.database import check_db_connection, get_db

router = APIRouter(tags=["health"])


@router.get("/healthz")
async def health_check():
    """Basic health check - always returns OK if service is running"""
    return {"status": "healthy", "service": "confluent-billing-portal"}


@router.get("/readyz")
async def readiness_check(db: Session = Depends(get_db)):
    """
    Readiness check - verifies service is ready to handle requests
    Checks database connectivity
    """
    # Check database
    if not check_db_connection():
        raise HTTPException(status_code=503, detail="Database connection failed")

    return {
        "status": "ready",
        "service": "confluent-billing-portal",
        "database": "connected",
    }


@router.get("/version")
async def version_info():
    """Return service version and build information"""
    settings = get_settings()

    return {
        "service": settings.service_name,
        "version": __version__,
        "environment": settings.environment,
    }

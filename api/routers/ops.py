from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from api.database import get_db

router = APIRouter(tags=["Operations"])

@router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "prototype": True,
        "service": "Amaanat API",
        "version": "0.1.0"
    }

@router.get("/ready")
async def ready_check(db: AsyncSession = Depends(get_db)):
    try:
        await db.execute(text("SELECT 1;"))
        return {
            "status": "ready",
            "db": "ok",
            "prototype": True
        }
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Service not ready: Database unavailable"
        )

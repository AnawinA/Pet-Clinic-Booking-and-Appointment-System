"""Health probes (NFR-03)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_session

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
async def live() -> dict[str, str]:
    return {"status": "ok", "instance_id": settings.instance_id}


@router.get("/ready")
async def ready(session: AsyncSession = Depends(get_session)):
    try:
        await session.execute(text("SELECT 1"))
    except Exception:
        return JSONResponse(
            status_code=503,
            content={
                "status": "unavailable",
                "instance_id": settings.instance_id,
                "checks": {"database": "down"},
            },
        )
    return {
        "status": "ok",
        "instance_id": settings.instance_id,
        "checks": {"database": "up"},
    }

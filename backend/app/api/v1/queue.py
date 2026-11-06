"""Live queue (FR-09, US-6, NFR-01)."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.http import not_modified
from app.core.time import now_utc
from app.db.session import get_session
from app.models import User
from app.services.queue_service import live_queue

router = APIRouter(prefix="/queue", tags=["queue"])


@router.get("/live")
async def live(
    request: Request,
    response: Response,
    day: date = Query(alias="date"),
    vet_id: uuid.UUID = Query(),
    since: datetime | None = None,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    entries, etag = await live_queue(session, day=day, vet_id=vet_id, since=since)
    cached = not_modified(request, etag, response)
    if cached is not None:
        return cached
    return {
        "items": [entry.model_dump(mode="json") for entry in entries],
        "server_time": now_utc().isoformat(),
        "etag": etag,
    }

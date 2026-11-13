"""Live queue (FR-09, US-6, NFR-01)."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.errors import forbidden
from app.core.http import not_modified
from app.core.time import now_utc
from app.db.session import get_session
from app.models import User, UserRole
from app.services.queue_service import live_queue

router = APIRouter(prefix="/queue", tags=["queue"])


@router.get("/live")
async def live(
    request: Request,
    response: Response,
    day: date = Query(alias="date"),
    vet_id: uuid.UUID = Query(),
    since: datetime | None = None,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    if user.role == UserRole.VET and vet_id != user.id:
        raise forbidden("คุณไม่มีสิทธิ์ดูคิวของสัตวแพทย์ท่านอื่น")

    entries, etag = await live_queue(session, day=day, vet_id=vet_id, since=since)
    if user.role == UserRole.OWNER:
        entries = [entry for entry in entries if entry.owner_id == user.id]

    cached = not_modified(request, etag, response)
    if cached is not None:
        return cached
    return {
        "items": [entry.model_dump(mode="json") for entry in entries],
        "server_time": now_utc().isoformat(),
        "etag": etag,
    }

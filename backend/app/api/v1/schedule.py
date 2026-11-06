"""Daily schedule (FR-11, US-9, NFR-01)."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_roles
from app.core.errors import forbidden
from app.core.http import not_modified
from app.core.time import now_utc
from app.db.session import get_session
from app.models import User, UserRole
from app.services.queue_service import schedule

router = APIRouter(tags=["schedule"])


@router.get("/schedule")
async def get_schedule(
    request: Request,
    response: Response,
    day: date = Query(alias="date"),
    vet_id: uuid.UUID | None = None,
    since: datetime | None = None,
    user: User = Depends(require_roles(UserRole.VET, UserRole.STAFF)),
    session: AsyncSession = Depends(get_session),
):
    if user.role == UserRole.VET:
        if vet_id is not None and vet_id != user.id:
            raise forbidden("สัตวแพทย์ดูตารางของผู้อื่นไม่ได้")
        vet_id = user.id
    if vet_id is None:
        from app.core.errors import bad_request

        raise bad_request("VET_REQUIRED", "กรุณาระบุ vet_id")

    entries, etag = await schedule(session, day=day, vet_id=vet_id, since=since)
    cached = not_modified(request, etag, response)
    if cached is not None:
        return cached
    return {
        "items": [entry.model_dump(mode="json") for entry in entries],
        "server_time": now_utc().isoformat(),
        "etag": etag,
    }

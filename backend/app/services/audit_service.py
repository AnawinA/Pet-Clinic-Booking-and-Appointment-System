"""Audit trail writer (NFR-10). Always called inside the caller's transaction."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog, User


async def write_audit(
    session: AsyncSession,
    *,
    actor: User | None,
    entity_type: str,
    entity_id: uuid.UUID,
    action: str,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    request_id: str | None = None,
) -> AuditLog:
    entry = AuditLog(
        actor_id=actor.id if actor else None,
        actor_role=actor.role if actor else None,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        before=jsonable_encoder(before) if before is not None else None,
        after=jsonable_encoder(after) if after is not None else None,
        request_id=request_id,
    )
    session.add(entry)
    await session.flush()
    return entry

"""Audit log viewer (NFR-10)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_roles
from app.db.session import get_session
from app.models import AuditLog, User, UserRole
from app.schemas import AuditLogOut

router = APIRouter(prefix="/audit-logs", tags=["audit"])


@router.get("", response_model=list[AuditLogOut])
async def list_audit_logs(
    entity_id: uuid.UUID | None = None,
    action: str | None = None,
    limit: int = 100,
    _: User = Depends(require_roles(UserRole.STAFF)),
    session: AsyncSession = Depends(get_session),
) -> list[AuditLog]:
    stmt = select(AuditLog)
    if entity_id is not None:
        stmt = stmt.where(AuditLog.entity_id == entity_id)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    stmt = stmt.order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(min(limit, 500))
    return list((await session.execute(stmt)).scalars().all())

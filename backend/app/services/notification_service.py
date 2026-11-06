"""In-app notification listing (NFR-02, US-5)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import forbidden, not_found
from app.models import Notification, User
from app.schemas import NotificationOut


def serialize_notification(item: Notification) -> NotificationOut:
    return NotificationOut(
        id=item.id,
        event_id=item.event_id,
        type=item.type,
        title=item.title,
        message=item.message,
        is_read=item.is_read,
        created_at=item.created_at,
    )


async def list_notifications(
    session: AsyncSession,
    user: User,
    *,
    since: datetime | None = None,
    unread_only: bool = False,
    limit: int = 100,
) -> list[NotificationOut]:
    stmt = select(Notification).where(Notification.recipient_id == user.id)
    if since is not None:
        stmt = stmt.where(Notification.created_at > since)
    if unread_only:
        stmt = stmt.where(Notification.is_read.is_(False))
    stmt = stmt.order_by(Notification.created_at.desc()).limit(min(limit, 200))
    rows = (await session.execute(stmt)).scalars().all()
    return [serialize_notification(row) for row in rows]


async def mark_read(
    session: AsyncSession, user: User, *, notification_id: uuid.UUID
) -> NotificationOut:
    item = await session.get(Notification, notification_id)
    if item is None:
        raise not_found("NOTIFICATION_NOT_FOUND", "ไม่พบการแจ้งเตือนนี้")
    if item.recipient_id != user.id:
        raise forbidden("การแจ้งเตือนนี้ไม่ใช่ของคุณ")
    item.is_read = True
    await session.commit()
    return serialize_notification(item)

"""Transactional outbox writer plus appointment payload helpers."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import now_utc
from app.models import Appointment, OutboxEvent

EVENT_BOOKED = "APPOINTMENT_BOOKED"
EVENT_CANCELLED = "APPOINTMENT_CANCELLED"
EVENT_STATUS_CHANGED = "APPOINTMENT_STATUS_CHANGED"
EVENT_RESCHEDULED = "APPOINTMENT_RESCHEDULED"
EVENT_TRANSFERRED = "APPOINTMENT_TRANSFERRED"
EVENT_REMINDER = "APPOINTMENT_REMINDER"
EVENT_RESCHEDULE_REQUESTED = "RESCHEDULE_REQUESTED"
EVENT_RESCHEDULE_REVIEWED = "RESCHEDULE_REVIEWED"
EVENT_TREATMENT_NOTE_ADDED = "TREATMENT_NOTE_ADDED"

ALL_EVENT_TYPES = (
    EVENT_BOOKED,
    EVENT_CANCELLED,
    EVENT_STATUS_CHANGED,
    EVENT_RESCHEDULED,
    EVENT_TRANSFERRED,
    EVENT_REMINDER,
    EVENT_RESCHEDULE_REQUESTED,
    EVENT_RESCHEDULE_REVIEWED,
    EVENT_TREATMENT_NOTE_ADDED,
)


def appointment_payload(
    appt: Appointment,
    *,
    pet_name: str,
    vet_name: str,
    owner_name: str,
    reason: str | None = None,
    **extra: object,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "appointment_id": str(appt.id),
        "owner_id": str(appt.owner_id),
        "vet_id": str(appt.vet_id),
        "pet_name": pet_name,
        "vet_name": vet_name,
        "owner_name": owner_name,
        "slot_start": appt.slot_start.isoformat(),
        "slot_end": appt.slot_end.isoformat(),
        "status": appt.status.value,
    }
    if reason:
        payload["reason"] = reason
    payload.update(extra)
    return payload


async def enqueue(
    session: AsyncSession,
    *,
    event_type: str,
    aggregate_id: uuid.UUID,
    payload: dict[str, object],
    recipient_ids: list[uuid.UUID],
    available_at: datetime | None = None,
) -> OutboxEvent:
    recipients = list(dict.fromkeys(str(recipient_id) for recipient_id in recipient_ids))
    event_payload = dict(payload)
    event_payload["recipient_ids"] = recipients
    event = OutboxEvent(
        event_type=event_type,
        aggregate_id=aggregate_id,
        payload=event_payload,
        available_at=available_at or now_utc(),
    )
    session.add(event)
    await session.flush()
    return event

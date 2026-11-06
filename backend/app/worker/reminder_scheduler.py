"""Reminder scheduling helpers.

Reminders are materialised as outbox rows with ``available_at = slot_start - 1h``.
Before sending, the worker re-checks that the appointment is still BOOKED at that
exact slot, so cancelled/rescheduled appointments never produce stale reminders.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from app.core.config import settings
from app.models import Appointment, AppointmentStatus


def reminder_time(slot_start: datetime) -> datetime:
    return slot_start - timedelta(hours=settings.reminder_hours_before)


def reminder_is_relevant(appt: Appointment | None, payload: dict) -> bool:
    if appt is None or appt.status != AppointmentStatus.BOOKED:
        return False
    return str(payload.get("slot_start")) == appt.slot_start.isoformat()

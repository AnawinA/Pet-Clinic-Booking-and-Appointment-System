"""Shift slot generation (FR-04, US-2)."""

from __future__ import annotations

import uuid
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.time import (
    SLOT_MINUTES,
    local_day_bounds,
    local_slot_to_utc,
    now_utc,
)
from app.models import Appointment, AppointmentStatus, User, UserRole, VetShift
from app.schemas import AvailabilitySlot
from app.services.common import get_vet


async def list_vets(session: AsyncSession) -> list[User]:
    rows = await session.execute(
        select(User)
        .where(User.role == UserRole.VET, User.is_active.is_(True))
        .order_by(User.full_name)
    )
    return list(rows.scalars().all())


async def get_availability(
    session: AsyncSession, *, day: date, vet_id: uuid.UUID | None
) -> list[AvailabilitySlot]:
    if vet_id is not None:
        await get_vet(session, vet_id)

    vet_query = select(User).where(User.role == UserRole.VET, User.is_active.is_(True))
    if vet_id is not None:
        vet_query = vet_query.where(User.id == vet_id)
    vets = list((await session.execute(vet_query.order_by(User.full_name))).scalars().all())
    if not vets:
        return []
    vet_names = {vet.id: vet.full_name for vet in vets}
    vet_ids = list(vet_names)

    shifts = list(
        (
            await session.execute(
                select(VetShift)
                .where(VetShift.shift_date == day, VetShift.vet_id.in_(vet_ids))
                .order_by(VetShift.start_time)
            )
        )
        .scalars()
        .all()
    )
    if not shifts:
        return []

    day_start, day_end = local_day_bounds(day)
    booked = await session.execute(
        select(Appointment.vet_id, Appointment.slot_start).where(
            Appointment.vet_id.in_(vet_ids),
            Appointment.slot_start >= day_start,
            Appointment.slot_start < day_end,
            Appointment.status != AppointmentStatus.CANCELLED,
        )
    )
    busy = {(row[0], row[1]) for row in booked.all()}

    now = now_utc()
    horizon = now + timedelta(days=settings.booking_horizon_days)
    slots: list[AvailabilitySlot] = []
    for shift in shifts:
        cursor = local_slot_to_utc(day, shift.start_time)
        shift_end = local_slot_to_utc(day, shift.end_time)
        while cursor + timedelta(minutes=SLOT_MINUTES) <= shift_end:
            if cursor > now and cursor <= horizon and (shift.vet_id, cursor) not in busy:
                slots.append(
                    AvailabilitySlot(
                        vet_id=shift.vet_id,
                        vet_name=vet_names[shift.vet_id],
                        slot_start=cursor,
                        slot_end=cursor + timedelta(minutes=SLOT_MINUTES),
                    )
                )
            cursor += timedelta(minutes=SLOT_MINUTES)

    slots.sort(key=lambda slot: (slot.slot_start, slot.vet_name))
    return slots

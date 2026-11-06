"""Appointment serialization and shared query helpers."""

from __future__ import annotations

import uuid
from datetime import date, time

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import forbidden, not_found
from app.core.time import local_day_bounds, to_local
from app.models import Appointment, Pet, User, UserRole, VetShift
from app.schemas import AppointmentOut


async def find_covering_shift(
    session: AsyncSession,
    *,
    vet_id: uuid.UUID,
    day: date,
    start: time,
    end: time,
    lock: bool = False,
) -> VetShift | None:
    stmt = (
        select(VetShift)
        .where(
            VetShift.vet_id == vet_id,
            VetShift.shift_date == day,
            VetShift.start_time <= start,
            VetShift.end_time >= end,
        )
        .order_by(VetShift.start_time)
        .limit(1)
    )
    if lock:
        stmt = stmt.with_for_update(read=True)
    return (await session.execute(stmt)).scalars().first()


async def get_vet(session: AsyncSession, vet_id: uuid.UUID) -> User:
    vet = await session.get(User, vet_id)
    if vet is None or vet.role != UserRole.VET or not vet.is_active:
        raise not_found("VET_NOT_FOUND", "ไม่พบสัตวแพทย์ท่านนี้")
    return vet


async def appointment_names(session: AsyncSession, appt: Appointment) -> tuple[str, str, str]:
    pet_name = await session.scalar(select(Pet.name).where(Pet.id == appt.pet_id))
    vet_name = await session.scalar(select(User.full_name).where(User.id == appt.vet_id))
    owner_name = await session.scalar(select(User.full_name).where(User.id == appt.owner_id))
    return pet_name or "-", vet_name or "-", owner_name or "-"


def serialize_appointment(
    appt: Appointment,
    *,
    pet_name: str | None = None,
    vet_name: str | None = None,
    owner_name: str | None = None,
) -> AppointmentOut:
    return AppointmentOut(
        id=appt.id,
        owner_id=appt.owner_id,
        owner_name=owner_name,
        pet_id=appt.pet_id,
        pet_name=pet_name,
        vet_id=appt.vet_id,
        vet_name=vet_name,
        slot_start=appt.slot_start,
        slot_end=appt.slot_end,
        status=appt.status.value,
        symptoms=appt.symptoms,
        cancel_reason=appt.cancel_reason,
        version=appt.version,
        created_at=appt.created_at,
        updated_at=appt.updated_at,
    )


def appointment_snapshot(appt: Appointment) -> dict[str, object]:
    return {
        "status": appt.status.value,
        "slot_start": appt.slot_start.isoformat(),
        "vet_id": str(appt.vet_id),
        "version": appt.version,
        "cancel_reason": appt.cancel_reason,
    }


async def assert_can_view_appointment(
    session: AsyncSession, user: User, appt: Appointment
) -> None:
    """Two-layer check: role plus data ownership (masterplan principle 4)."""
    if user.role == UserRole.STAFF:
        return
    if user.role == UserRole.OWNER and appt.owner_id == user.id:
        return
    if user.role == UserRole.VET and appt.vet_id == user.id:
        return
    raise forbidden("คุณไม่มีสิทธิ์เข้าถึงนัดหมายนี้")


async def assert_can_view_pet(session: AsyncSession, user: User, pet: Pet) -> None:
    if user.role == UserRole.STAFF:
        return
    if user.role == UserRole.OWNER and pet.owner_id == user.id:
        return
    if user.role == UserRole.VET:
        exists = await session.scalar(
            select(Appointment.id)
            .where(Appointment.pet_id == pet.id, Appointment.vet_id == user.id)
            .limit(1)
        )
        if exists is not None:
            return
    raise forbidden("คุณไม่มีสิทธิ์เข้าถึงข้อมูลสัตว์เลี้ยงนี้")


def day_range(day: date) -> tuple[object, object]:
    return local_day_bounds(day)


def local_date_of(value: object) -> date:
    return to_local(value).date()  # type: ignore[arg-type]

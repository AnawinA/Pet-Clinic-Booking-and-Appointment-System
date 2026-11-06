"""Booking and cancellation transactions (FR-05, FR-07, US-1, US-3)."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import conflict, forbidden, not_found
from app.core.time import now_utc, to_local, validate_slot
from app.models import (
    ACTIVE_STATUSES,
    TERMINAL_STATUSES,
    Appointment,
    AppointmentStatus,
    Pet,
    User,
    UserRole,
)
from app.schemas import AppointmentOut
from app.services.audit_service import write_audit
from app.services.common import (
    appointment_names,
    appointment_snapshot,
    find_covering_shift,
    get_vet,
    serialize_appointment,
)
from app.services.outbox_service import (
    EVENT_BOOKED,
    EVENT_CANCELLED,
    EVENT_REMINDER,
    appointment_payload,
    enqueue,
)


def _conflict_code(exc: IntegrityError) -> str:
    detail = str(getattr(exc, "orig", exc))
    if "uq_pet_slot_active" in detail:
        return "PET_SLOT_TAKEN"
    return "SLOT_TAKEN"


async def create_appointment(
    session: AsyncSession,
    owner: User,
    *,
    pet_id: uuid.UUID,
    vet_id: uuid.UUID,
    slot_start: datetime,
    symptoms: str,
    request_id: str | None,
) -> AppointmentOut:
    slot_start, slot_end = validate_slot(slot_start)
    local_start = to_local(slot_start)
    local_end = to_local(slot_end)

    pet = await session.get(Pet, pet_id)
    if pet is None:
        raise not_found("PET_NOT_FOUND", "ไม่พบสัตว์เลี้ยงนี้")
    if pet.owner_id != owner.id:
        raise forbidden("สัตว์เลี้ยงนี้ไม่ใช่ของคุณ")

    vet = await get_vet(session, vet_id)

    shift = await find_covering_shift(
        session,
        vet_id=vet.id,
        day=local_start.date(),
        start=local_start.time(),
        end=local_end.time(),
        lock=True,
    )
    if shift is None:
        from app.core.errors import bad_request

        raise bad_request("SLOT_OUT_OF_RANGE", "สล็อตนี้ไม่อยู่ในกะของสัตวแพทย์")

    appt = Appointment(
        owner_id=owner.id,
        pet_id=pet.id,
        vet_id=vet.id,
        shift_id=shift.id,
        slot_start=slot_start,
        slot_end=slot_end,
        status=AppointmentStatus.BOOKED,
        symptoms=symptoms,
        version=1,
    )
    try:
        async with session.begin_nested():
            session.add(appt)
            await session.flush()
    except IntegrityError as exc:
        raise conflict(_conflict_code(exc), "สล็อตนี้ถูกจองแล้ว") from exc

    await write_audit(
        session,
        actor=owner,
        entity_type="APPOINTMENT",
        entity_id=appt.id,
        action="CREATE",
        after=appointment_snapshot(appt),
        request_id=request_id,
    )

    payload = appointment_payload(appt, pet_name=pet.name, vet_name=vet.full_name,
                                  owner_name=owner.full_name)
    recipients = [owner.id, vet.id]
    await enqueue(
        session,
        event_type=EVENT_BOOKED,
        aggregate_id=appt.id,
        payload=payload,
        recipient_ids=recipients,
    )
    reminder_at = max(
        now_utc(),
        slot_start - timedelta(hours=settings.reminder_hours_before),
    )
    await enqueue(
        session,
        event_type=EVENT_REMINDER,
        aggregate_id=appt.id,
        payload=payload,
        recipient_ids=recipients,
        available_at=reminder_at,
    )

    await session.commit()
    return serialize_appointment(
        appt, pet_name=pet.name, vet_name=vet.full_name, owner_name=owner.full_name
    )


async def cancel_appointment(
    session: AsyncSession,
    actor: User,
    *,
    appointment_id: uuid.UUID,
    reason: str | None,
    request_id: str | None,
) -> AppointmentOut:
    locked = await session.get(Appointment, appointment_id, with_for_update=True)
    if locked is None:
        raise not_found("APPOINTMENT_NOT_FOUND", "ไม่พบนัดหมายนี้")

    if actor.role == UserRole.OWNER:
        if locked.owner_id != actor.id:
            raise forbidden("นัดหมายนี้ไม่ใช่ของคุณ")
        window = timedelta(hours=settings.cancellation_window_hours)
        if now_utc() > locked.slot_start - window:
            from app.core.errors import bad_request

            raise bad_request(
                "CANCEL_WINDOW_CLOSED",
                "ไม่สามารถยกเลิกได้เมื่อเหลือเวลาน้อยกว่า 2 ชั่วโมงก่อนนัด",
            )
    elif actor.role == UserRole.VET:
        raise forbidden("สัตวแพทย์ไม่มีสิทธิ์ยกเลิกนัด")

    if locked.status in TERMINAL_STATUSES:
        raise conflict("INVALID_TRANSITION", "นัดหมายนี้สิ้นสุดแล้ว ไม่สามารถยกเลิกได้")

    before = appointment_snapshot(locked)
    locked.status = AppointmentStatus.CANCELLED
    locked.cancel_reason = reason
    locked.cancelled_at = now_utc()
    locked.updated_at = now_utc()
    locked.version += 1

    pet_name, vet_name, owner_name = await appointment_names(session, locked)
    await write_audit(
        session,
        actor=actor,
        entity_type="APPOINTMENT",
        entity_id=locked.id,
        action="CANCEL",
        before=before,
        after=appointment_snapshot(locked),
        request_id=request_id,
    )
    await enqueue(
        session,
        event_type=EVENT_CANCELLED,
        aggregate_id=locked.id,
        payload=appointment_payload(
            locked,
            pet_name=pet_name,
            vet_name=vet_name,
            owner_name=owner_name,
            reason=reason,
        ),
        recipient_ids=[locked.owner_id, locked.vet_id],
    )

    await session.commit()
    return serialize_appointment(
        locked, pet_name=pet_name, vet_name=vet_name, owner_name=owner_name
    )


async def list_owner_appointments(
    session: AsyncSession, owner: User, *, status: str | None = None
) -> list[AppointmentOut]:
    stmt = (
        select(Appointment, Pet.name, User.full_name)
        .join(Pet, Pet.id == Appointment.pet_id)
        .join(User, User.id == Appointment.vet_id)
        .where(Appointment.owner_id == owner.id)
        .order_by(Appointment.slot_start.desc())
    )
    if status:
        stmt = stmt.where(Appointment.status == AppointmentStatus(status))
    rows = (await session.execute(stmt)).all()
    return [
        serialize_appointment(
            appt, pet_name=pet_name, vet_name=vet_name, owner_name=owner.full_name
        )
        for appt, pet_name, vet_name in rows
    ]


async def get_appointment_for_view(
    session: AsyncSession, actor: User, appointment_id: uuid.UUID
) -> AppointmentOut:
    from app.services.common import assert_can_view_appointment

    appt = await session.get(Appointment, appointment_id)
    if appt is None:
        raise not_found("APPOINTMENT_NOT_FOUND", "ไม่พบนัดหมายนี้")
    await assert_can_view_appointment(session, actor, appt)
    pet_name, vet_name, owner_name = await appointment_names(session, appt)
    return serialize_appointment(
        appt, pet_name=pet_name, vet_name=vet_name, owner_name=owner_name
    )


def is_active(appt: Appointment) -> bool:
    return appt.status in ACTIVE_STATUSES

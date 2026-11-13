"""Live queue, schedule, state machine, reschedule, swap and transfer."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import bad_request, conflict, forbidden, not_found
from app.core.http import build_etag
from app.core.time import SLOT_MINUTES, local_day_bounds, now_utc, to_local, validate_slot
from app.models import (
    ACTIVE_STATUSES,
    ALLOWED_TRANSITIONS,
    Appointment,
    AppointmentStatus,
    Pet,
    User,
)
from app.schemas import AppointmentOut, QueueEntry, QueuePosition, ScheduleEntry
from app.services.audit_service import write_audit
from app.services.common import (
    appointment_names,
    appointment_snapshot,
    find_covering_shift,
    get_vet,
    serialize_appointment,
)
from app.services.outbox_service import (
    EVENT_REMINDER,
    EVENT_RESCHEDULED,
    EVENT_STATUS_CHANGED,
    EVENT_TRANSFERRED,
    appointment_payload,
    enqueue,
)


async def lock_appointment(session: AsyncSession, appointment_id: uuid.UUID) -> Appointment:
    appt = await session.get(Appointment, appointment_id, with_for_update=True)
    if appt is None:
        raise not_found("APPOINTMENT_NOT_FOUND", "ไม่พบนัดหมายนี้")
    return appt


async def get_appointment(session: AsyncSession, appointment_id: uuid.UUID) -> Appointment:
    appt = await session.get(Appointment, appointment_id)
    if appt is None:
        raise not_found("APPOINTMENT_NOT_FOUND", "ไม่พบนัดหมายนี้")
    return appt


async def live_queue(
    session: AsyncSession,
    *,
    day,
    vet_id: uuid.UUID,
    since: datetime | None = None,
) -> tuple[list[QueueEntry], str]:
    vet = await get_vet(session, vet_id)
    day_start, day_end = local_day_bounds(day)
    rows = (
        await session.execute(
            select(Appointment, Pet.name, User.full_name)
            .join(Pet, Pet.id == Appointment.pet_id)
            .join(User, User.id == Appointment.owner_id)
            .where(
                Appointment.vet_id == vet_id,
                Appointment.slot_start >= day_start,
                Appointment.slot_start < day_end,
                Appointment.status.in_(ACTIVE_STATUSES),
            )
            .order_by(Appointment.slot_start)
        )
    ).all()

    now = now_utc()
    entries: list[QueueEntry] = []
    for index, (appt, pet_name, owner_name) in enumerate(rows):
        estimated = max(appt.slot_start, now + timedelta(minutes=SLOT_MINUTES * index))
        entries.append(
            QueueEntry(
                appointment_id=appt.id,
                vet_id=vet_id,
                vet_name=vet.full_name,
                owner_id=appt.owner_id,
                owner_name=owner_name,
                pet_id=appt.pet_id,
                pet_name=pet_name,
                slot_start=appt.slot_start,
                slot_end=appt.slot_end,
                status=appt.status.value,
                ahead_count=index,
                estimated_start=estimated,
                updated_at=appt.updated_at,
            )
        )

    etag = build_etag([row[0].updated_at for row in rows], extra=f"queue:{vet_id}:{day}")
    if since is not None:
        entries = [entry for entry in entries if entry.updated_at >= since]
    return entries, etag


async def queue_position(
    session: AsyncSession, appt: Appointment, *, owner_id: uuid.UUID
) -> QueuePosition:
    if appt.owner_id != owner_id:
        raise forbidden("นัดหมายนี้ไม่ใช่ของคุณ")
    day = to_local(appt.slot_start).date()
    day_start, day_end = local_day_bounds(day)
    rows = (
        (
            await session.execute(
                select(Appointment)
                .where(
                    Appointment.vet_id == appt.vet_id,
                    Appointment.slot_start >= day_start,
                    Appointment.slot_start < day_end,
                    Appointment.status.in_(ACTIVE_STATUSES),
                )
                .order_by(Appointment.slot_start)
            )
        )
        .scalars()
        .all()
    )
    now = now_utc()
    if appt.status in ACTIVE_STATUSES:
        ahead_count = next((i for i, row in enumerate(rows) if row.id == appt.id), 0)
        estimated = max(appt.slot_start, now + timedelta(minutes=SLOT_MINUTES * ahead_count))
    else:
        ahead_count = sum(1 for row in rows if row.slot_start < appt.slot_start)
        estimated = None
    return QueuePosition(
        appointment_id=appt.id,
        ahead_count=ahead_count,
        estimated_start=estimated,
        status=appt.status.value,
    )


async def schedule(
    session: AsyncSession,
    *,
    day,
    vet_id: uuid.UUID,
    since: datetime | None = None,
) -> tuple[list[ScheduleEntry], str]:
    await get_vet(session, vet_id)
    day_start, day_end = local_day_bounds(day)
    rows = (
        await session.execute(
            select(Appointment, Pet.name, User.full_name)
            .join(Pet, Pet.id == Appointment.pet_id)
            .join(User, User.id == Appointment.owner_id)
            .where(
                Appointment.vet_id == vet_id,
                Appointment.slot_start >= day_start,
                Appointment.slot_start < day_end,
            )
            .order_by(Appointment.slot_start)
        )
    ).all()

    now = now_utc()
    active_index = 0
    entries: list[ScheduleEntry] = []
    for appt, pet_name, owner_name in rows:
        estimated: datetime | None = None
        if appt.status in ACTIVE_STATUSES:
            estimated = max(appt.slot_start, now + timedelta(minutes=SLOT_MINUTES * active_index))
            active_index += 1
        entries.append(
            ScheduleEntry(
                appointment_id=appt.id,
                version=appt.version,
                vet_id=appt.vet_id,
                owner_id=appt.owner_id,
                owner_name=owner_name,
                pet_id=appt.pet_id,
                pet_name=pet_name,
                slot_start=appt.slot_start,
                slot_end=appt.slot_end,
                status=appt.status.value,
                symptoms=appt.symptoms,
                estimated_start=estimated,
                updated_at=appt.updated_at,
            )
        )

    etag = build_etag([row[0].updated_at for row in rows], extra=f"schedule:{vet_id}:{day}")
    if since is not None:
        entries = [entry for entry in entries if entry.updated_at >= since]
    return entries, etag


async def change_status(
    session: AsyncSession,
    actor: User,
    *,
    appointment_id: uuid.UUID,
    new_status: str,
    expected_version: int,
    reason: str | None,
    request_id: str | None,
) -> AppointmentOut:
    try:
        target = AppointmentStatus(new_status)
    except ValueError as exc:
        raise bad_request("INVALID_STATUS", "สถานะที่ส่งมาไม่ถูกต้อง") from exc

    appt = await lock_appointment(session, appointment_id)
    if appt.version != expected_version:
        raise conflict("STALE_VERSION", "ข้อมูลถูกแก้ไขโดยผู้ใช้อื่น กรุณาโหลดใหม่")
    if target == AppointmentStatus.NO_SHOW and now_utc() < appt.slot_start:
        raise conflict("NO_SHOW_TOO_EARLY", "กำหนดสถานะไม่มาได้เมื่อถึงเวลาเริ่มนัดหมายแล้ว")
    if target not in ALLOWED_TRANSITIONS[appt.status]:
        raise conflict(
            "INVALID_TRANSITION",
            f"ไม่สามารถเปลี่ยนสถานะจาก {appt.status.value} เป็น {target.value} ได้",
            {"allowed": sorted(status.value for status in ALLOWED_TRANSITIONS[appt.status])},
        )

    before = appointment_snapshot(appt)
    appt.status = target
    appt.version += 1
    appt.updated_at = now_utc()
    if target == AppointmentStatus.CANCELLED:
        appt.cancelled_at = now_utc()
        appt.cancel_reason = reason

    pet_name, vet_name, owner_name = await appointment_names(session, appt)
    await write_audit(
        session,
        actor=actor,
        entity_type="APPOINTMENT",
        entity_id=appt.id,
        action="STATUS_CHANGE",
        before=before,
        after=appointment_snapshot(appt),
        request_id=request_id,
    )
    await enqueue(
        session,
        event_type=EVENT_STATUS_CHANGED,
        aggregate_id=appt.id,
        payload=appointment_payload(
            appt, pet_name=pet_name, vet_name=vet_name, owner_name=owner_name, reason=reason
        ),
        recipient_ids=[appt.owner_id, appt.vet_id],
    )
    await session.commit()
    return serialize_appointment(
        appt, pet_name=pet_name, vet_name=vet_name, owner_name=owner_name
    )


async def apply_reschedule_locked(
    session: AsyncSession,
    actor: User,
    appt: Appointment,
    *,
    new_start: datetime,
    expected_version: int | None,
    reason: str | None,
    request_id: str | None,
) -> AppointmentOut:
    """Reschedule an already row-locked appointment; caller commits."""
    slot_start, slot_end = validate_slot(new_start)
    if expected_version is not None and appt.version != expected_version:
        raise conflict("STALE_VERSION", "ข้อมูลถูกแก้ไขโดยผู้ใช้อื่น กรุณาโหลดใหม่")
    if appt.status not in ACTIVE_STATUSES:
        raise conflict("INVALID_TRANSITION", "ไม่สามารถเลื่อนนัดที่สิ้นสุดแล้ว")

    local_start = to_local(slot_start)
    local_end = to_local(slot_end)
    shift = await find_covering_shift(
        session,
        vet_id=appt.vet_id,
        day=local_start.date(),
        start=local_start.time(),
        end=local_end.time(),
        lock=True,
    )
    if shift is None:
        raise bad_request("SLOT_OUT_OF_RANGE", "สล็อตใหม่อยู่นอกกะของสัตวแพทย์")

    before = appointment_snapshot(appt)
    appt.slot_start = slot_start
    appt.slot_end = slot_end
    appt.shift_id = shift.id
    appt.version += 1
    appt.updated_at = now_utc()
    try:
        await session.flush()
    except IntegrityError as exc:
        raise conflict("SLOT_TAKEN", "สล็อตใหม่ถูกจองแล้ว") from exc

    pet_name, vet_name, owner_name = await appointment_names(session, appt)
    await write_audit(
        session,
        actor=actor,
        entity_type="APPOINTMENT",
        entity_id=appt.id,
        action="RESCHEDULE",
        before=before,
        after=appointment_snapshot(appt),
        request_id=request_id,
    )
    payload = appointment_payload(
        appt, pet_name=pet_name, vet_name=vet_name, owner_name=owner_name, reason=reason
    )
    recipients = [appt.owner_id, appt.vet_id]
    await enqueue(
        session,
        event_type=EVENT_RESCHEDULED,
        aggregate_id=appt.id,
        payload=payload,
        recipient_ids=recipients,
    )
    await enqueue(
        session,
        event_type=EVENT_REMINDER,
        aggregate_id=appt.id,
        payload=payload,
        recipient_ids=recipients,
        available_at=max(
            now_utc(), slot_start - timedelta(hours=settings.reminder_hours_before)
        ),
    )
    return serialize_appointment(
        appt, pet_name=pet_name, vet_name=vet_name, owner_name=owner_name
    )


async def reschedule_appointment(
    session: AsyncSession,
    actor: User,
    *,
    appointment_id: uuid.UUID,
    new_start: datetime,
    expected_version: int,
    reason: str | None,
    request_id: str | None,
) -> AppointmentOut:
    appt = await lock_appointment(session, appointment_id)
    result = await apply_reschedule_locked(
        session,
        actor,
        appt,
        new_start=new_start,
        expected_version=expected_version,
        reason=reason,
        request_id=request_id,
    )
    await session.commit()
    return result


async def swap_appointments(
    session: AsyncSession,
    actor: User,
    *,
    appointment_a_id: uuid.UUID,
    appointment_b_id: uuid.UUID,
    expected_version_a: int,
    expected_version_b: int,
    request_id: str | None,
) -> tuple[AppointmentOut, AppointmentOut]:
    if appointment_a_id == appointment_b_id:
        raise bad_request("INVALID_SWAP", "ไม่สามารถสลับนัดหมายรายการเดียวกันได้")

    rows = (
        (
            await session.execute(
                select(Appointment)
                .where(Appointment.id.in_([appointment_a_id, appointment_b_id]))
                .order_by(Appointment.id)
                .with_for_update()
            )
        )
        .scalars()
        .all()
    )
    by_id = {row.id: row for row in rows}
    if len(by_id) != 2:
        raise not_found("APPOINTMENT_NOT_FOUND", "ไม่พบนัดหมายที่ต้องการสลับ")

    appt_a = by_id[appointment_a_id]
    appt_b = by_id[appointment_b_id]
    if appt_a.version != expected_version_a or appt_b.version != expected_version_b:
        raise conflict("STALE_VERSION", "ข้อมูลถูกแก้ไขโดยผู้ใช้อื่น กรุณาโหลดใหม่")
    if (
        appt_a.status != AppointmentStatus.BOOKED
        or appt_b.status != AppointmentStatus.BOOKED
        or appt_a.vet_id != appt_b.vet_id
        or to_local(appt_a.slot_start).date() != to_local(appt_b.slot_start).date()
    ):
        raise conflict("SWAP_NOT_ALLOWED", "สลับได้เฉพาะนัดสถานะ BOOKED ของแพทย์และวันเดียวกัน")

    # Both target slots must remain covered by the vet's shifts after the swap.
    for appt, other in ((appt_a, appt_b), (appt_b, appt_a)):
        local_start = to_local(other.slot_start)
        local_end = to_local(other.slot_end)
        shift = await find_covering_shift(
            session,
            vet_id=appt.vet_id,
            day=local_start.date(),
            start=local_start.time(),
            end=local_end.time(),
            lock=True,
        )
        if shift is None:
            raise conflict("SWAP_NOT_ALLOWED", "สล็อตปลายทางไม่อยู่ในกะของสัตวแพทย์")

    before_a = appointment_snapshot(appt_a)
    before_b = appointment_snapshot(appt_b)
    a_pet, a_vet, a_owner = await appointment_names(session, appt_a)
    b_pet, _, b_owner = await appointment_names(session, appt_b)

    a_old = (appt_a.slot_start, appt_a.slot_end, appt_a.shift_id)
    b_old = (appt_b.slot_start, appt_b.slot_end, appt_b.shift_id)

    # Move A through a temporary slot so both partial unique indexes stay satisfied.
    temp = datetime(1970, 1, 1, tzinfo=UTC) + timedelta(
        microseconds=uuid.uuid4().int % 86_400_000_000
    )
    appt_a.slot_start = temp
    appt_a.slot_end = temp + timedelta(minutes=SLOT_MINUTES)
    await session.flush()

    appt_b.slot_start, appt_b.slot_end, appt_b.shift_id = a_old
    await session.flush()

    appt_a.slot_start, appt_a.slot_end, appt_a.shift_id = b_old
    appt_a.version += 1
    appt_a.updated_at = now_utc()
    appt_b.version += 1
    appt_b.updated_at = now_utc()
    try:
        await session.flush()
    except IntegrityError as exc:
        raise conflict("SLOT_TAKEN", "ไม่สามารถสลับได้เนื่องจากสล็อตชนกัน") from exc

    await write_audit(
        session,
        actor=actor,
        entity_type="APPOINTMENT",
        entity_id=appt_a.id,
        action="SWAP",
        before=before_a,
        after=appointment_snapshot(appt_a),
        request_id=request_id,
    )
    await write_audit(
        session,
        actor=actor,
        entity_type="APPOINTMENT",
        entity_id=appt_b.id,
        action="SWAP",
        before=before_b,
        after=appointment_snapshot(appt_b),
        request_id=request_id,
    )

    for appt, pet_name in ((appt_a, a_pet), (appt_b, b_pet)):
        owner_name = a_owner if appt is appt_a else b_owner
        await enqueue(
            session,
            event_type=EVENT_RESCHEDULED,
            aggregate_id=appt.id,
            payload=appointment_payload(
                appt, pet_name=pet_name, vet_name=a_vet, owner_name=owner_name,
                reason="สลับคิว",
            ),
            recipient_ids=[appt.owner_id, appt.vet_id],
        )

    await session.commit()
    return (
        serialize_appointment(appt_a, pet_name=a_pet, vet_name=a_vet, owner_name=a_owner),
        serialize_appointment(appt_b, pet_name=b_pet, vet_name=a_vet, owner_name=b_owner),
    )


async def transfer_appointment(
    session: AsyncSession,
    actor: User,
    *,
    appointment_id: uuid.UUID,
    new_vet_id: uuid.UUID,
    expected_version: int,
    reason: str | None,
    request_id: str | None,
) -> AppointmentOut:
    appt = await lock_appointment(session, appointment_id)
    if appt.version != expected_version:
        raise conflict("STALE_VERSION", "ข้อมูลถูกแก้ไขโดยผู้ใช้อื่น กรุณาโหลดใหม่")
    if appt.status not in ACTIVE_STATUSES:
        raise conflict("INVALID_TRANSITION", "ไม่สามารถโอนเคสที่สิ้นสุดแล้ว")
    if new_vet_id == appt.vet_id:
        raise conflict("TRANSFER_SAME_VET", "นัดหมายนี้อยู่กับสัตวแพทย์ท่านนี้อยู่แล้ว")

    old_vet = await session.get(User, appt.vet_id)
    new_vet = await get_vet(session, new_vet_id)
    local_start = to_local(appt.slot_start)
    local_end = to_local(appt.slot_end)
    shift = await find_covering_shift(
        session,
        vet_id=new_vet.id,
        day=local_start.date(),
        start=local_start.time(),
        end=local_end.time(),
        lock=True,
    )
    if shift is None:
        raise bad_request("SLOT_OUT_OF_RANGE", "แพทย์ปลายทางไม่มีกะครอบสล็อตนี้")

    taken = await session.scalar(
        select(Appointment.id).where(
            Appointment.vet_id == new_vet.id,
            Appointment.slot_start == appt.slot_start,
            Appointment.status != AppointmentStatus.CANCELLED,
            Appointment.id != appt.id,
        )
    )
    if taken is not None:
        raise conflict("SLOT_TAKEN", "แพทย์ปลายทางมีนัดในช่วงเวลานี้แล้ว")

    before = appointment_snapshot(appt)
    appt.vet_id = new_vet.id
    appt.shift_id = shift.id
    appt.version += 1
    appt.updated_at = now_utc()
    try:
        await session.flush()
    except IntegrityError as exc:
        raise conflict("SLOT_TAKEN", "แพทย์ปลายทางมีนัดในช่วงเวลานี้แล้ว") from exc

    pet_name, new_vet_name, owner_name = await appointment_names(session, appt)
    after = appointment_snapshot(appt)
    after["previous_vet_id"] = str(old_vet.id) if old_vet else None
    await write_audit(
        session,
        actor=actor,
        entity_type="APPOINTMENT",
        entity_id=appt.id,
        action="TRANSFER",
        before=before,
        after=after,
        request_id=request_id,
    )
    recipients = [appt.owner_id, new_vet.id]
    if old_vet is not None:
        recipients.append(old_vet.id)
    await enqueue(
        session,
        event_type=EVENT_TRANSFERRED,
        aggregate_id=appt.id,
        payload=appointment_payload(
            appt,
            pet_name=pet_name,
            vet_name=new_vet_name,
            owner_name=owner_name,
            reason=reason,
            previous_vet_name=old_vet.full_name if old_vet else None,
        ),
        recipient_ids=recipients,
    )
    await session.commit()
    return serialize_appointment(
        appt, pet_name=pet_name, vet_name=new_vet_name, owner_name=owner_name
    )

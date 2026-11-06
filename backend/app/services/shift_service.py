"""Vet shift management (FR-15, US-14)."""

from __future__ import annotations

import uuid
from datetime import date, time

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import bad_request, conflict, not_found
from app.core.time import CLOSE_TIME, LAST_SLOT_START, OPEN_TIME
from app.models import ACTIVE_STATUSES, Appointment, User, VetShift
from app.schemas import ShiftOut
from app.services.audit_service import write_audit
from app.services.common import get_vet


def _parse_time(value: str) -> time:
    try:
        return time.fromisoformat(value)
    except ValueError as exc:
        raise bad_request("INVALID_SHIFT", "รูปแบบเวลาไม่ถูกต้อง (HH:MM)") from exc


def _validate_window(start: time, end: time) -> None:
    if (
        start < OPEN_TIME
        or end > CLOSE_TIME
        or start >= end
        or start.minute not in (0, 30)
        or end.minute not in (0, 30)
        or start.second
        or end.second
    ):
        raise bad_request(
            "INVALID_SHIFT",
            "กะต้องอยู่ระหว่าง 09:00–17:00 และเริ่ม/สิ้นสุดที่ 00 หรือ 30 นาที",
        )
    if start > LAST_SLOT_START:
        raise bad_request("INVALID_SHIFT", "กะต้องมีสล็อตอย่างน้อย 30 นาที")


async def _has_overlap(
    session: AsyncSession,
    *,
    vet_id: uuid.UUID,
    day: date,
    start: time,
    end: time,
    exclude_id: uuid.UUID | None = None,
) -> bool:
    stmt = select(VetShift.id).where(
        VetShift.vet_id == vet_id,
        VetShift.shift_date == day,
        VetShift.start_time < end,
        VetShift.end_time > start,
    )
    if exclude_id is not None:
        stmt = stmt.where(VetShift.id != exclude_id)
    return (await session.execute(stmt.limit(1))).first() is not None


def serialize_shift(shift: VetShift, vet_name: str | None = None) -> ShiftOut:
    return ShiftOut(
        id=shift.id,
        vet_id=shift.vet_id,
        vet_name=vet_name,
        shift_date=shift.shift_date,
        start_time=shift.start_time.strftime("%H:%M"),
        end_time=shift.end_time.strftime("%H:%M"),
        created_by=shift.created_by,
        created_at=shift.created_at,
    )


async def create_shift(
    session: AsyncSession,
    actor: User,
    *,
    vet_id: uuid.UUID,
    day: date,
    start: str,
    end: str,
    request_id: str | None,
) -> ShiftOut:
    vet = await get_vet(session, vet_id)
    start_time = _parse_time(start)
    end_time = _parse_time(end)
    _validate_window(start_time, end_time)

    if await _has_overlap(
        session, vet_id=vet.id, day=day, start=start_time, end=end_time
    ):
        raise conflict("SHIFT_OVERLAP", "กะนี้ซ้อนกับกะเดิมของสัตวแพทย์")

    shift = VetShift(
        vet_id=vet.id,
        shift_date=day,
        start_time=start_time,
        end_time=end_time,
        created_by=actor.id,
    )
    try:
        async with session.begin_nested():
            session.add(shift)
            await session.flush()
    except IntegrityError as exc:
        raise conflict("SHIFT_OVERLAP", "กะนี้ซ้อนกับกะเดิมของสัตวแพทย์") from exc

    await write_audit(
        session,
        actor=actor,
        entity_type="VET_SHIFT",
        entity_id=shift.id,
        action="SHIFT_CREATED",
        after={
            "vet_id": str(shift.vet_id),
            "shift_date": str(shift.shift_date),
            "start_time": start,
            "end_time": end,
        },
        request_id=request_id,
    )
    await session.commit()
    return serialize_shift(shift, vet.full_name)


async def list_shifts(
    session: AsyncSession,
    *,
    day: date | None,
    vet_id: uuid.UUID | None,
) -> list[ShiftOut]:
    stmt = select(VetShift, User.full_name).join(User, User.id == VetShift.vet_id)
    if day is not None:
        stmt = stmt.where(VetShift.shift_date == day)
    if vet_id is not None:
        stmt = stmt.where(VetShift.vet_id == vet_id)
    rows = (await session.execute(stmt.order_by(VetShift.shift_date, VetShift.start_time))).all()
    return [serialize_shift(shift, vet_name) for shift, vet_name in rows]


async def update_shift(
    session: AsyncSession,
    actor: User,
    *,
    shift_id: uuid.UUID,
    day: date | None,
    start: str | None,
    end: str | None,
    request_id: str | None,
) -> ShiftOut:
    shift = await session.get(VetShift, shift_id, with_for_update=True)
    if shift is None:
        raise not_found("SHIFT_NOT_FOUND", "ไม่พบกะนี้")
    before = {
        "shift_date": str(shift.shift_date),
        "start_time": shift.start_time.strftime("%H:%M"),
        "end_time": shift.end_time.strftime("%H:%M"),
    }
    new_day = day or shift.shift_date
    new_start = _parse_time(start) if start else shift.start_time
    new_end = _parse_time(end) if end else shift.end_time
    _validate_window(new_start, new_end)

    if await _has_overlap(
        session,
        vet_id=shift.vet_id,
        day=new_day,
        start=new_start,
        end=new_end,
        exclude_id=shift.id,
    ):
        raise conflict("SHIFT_OVERLAP", "กะนี้ซ้อนกับกะเดิมของสัตวแพทย์")

    shift.shift_date = new_day
    shift.start_time = new_start
    shift.end_time = new_end
    try:
        await session.flush()
    except IntegrityError as exc:
        raise conflict("SHIFT_OVERLAP", "กะนี้ซ้อนกับกะเดิมของสัตวแพทย์") from exc

    await write_audit(
        session,
        actor=actor,
        entity_type="VET_SHIFT",
        entity_id=shift.id,
        action="SHIFT_UPDATED",
        before=before,
        after={
            "shift_date": str(new_day),
            "start_time": new_start.strftime("%H:%M"),
            "end_time": new_end.strftime("%H:%M"),
        },
        request_id=request_id,
    )
    vet_name = await session.scalar(select(User.full_name).where(User.id == shift.vet_id))
    await session.commit()
    return serialize_shift(shift, vet_name)


async def delete_shift(
    session: AsyncSession,
    actor: User,
    *,
    shift_id: uuid.UUID,
    request_id: str | None,
) -> None:
    shift = await session.get(VetShift, shift_id, with_for_update=True)
    if shift is None:
        raise not_found("SHIFT_NOT_FOUND", "ไม่พบกะนี้")

    active_count = await session.scalar(
        select(func.count(Appointment.id)).where(
            Appointment.shift_id == shift.id,
            Appointment.status.in_(ACTIVE_STATUSES),
        )
    )
    if active_count:
        raise conflict("SHIFT_HAS_APPOINTMENTS", "กะนี้ยังมีนัดที่ยังไม่จบ ไม่สามารถลบได้")

    total_count = await session.scalar(
        select(func.count(Appointment.id)).where(Appointment.shift_id == shift.id)
    )
    if total_count:
        raise conflict(
            "SHIFT_HAS_HISTORY", "กะนี้มีประวัติการนัดหมาย จึงเก็บไว้เพื่อการตรวจสอบ"
        )

    await write_audit(
        session,
        actor=actor,
        entity_type="VET_SHIFT",
        entity_id=shift.id,
        action="SHIFT_DELETED",
        before={
            "vet_id": str(shift.vet_id),
            "shift_date": str(shift.shift_date),
            "start_time": shift.start_time.strftime("%H:%M"),
            "end_time": shift.end_time.strftime("%H:%M"),
        },
        request_id=request_id,
    )
    await session.delete(shift)
    await session.commit()

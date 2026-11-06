"""Reschedule request workflow (FR-12, US-10)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import conflict, forbidden, not_found
from app.core.time import now_utc, validate_slot
from app.models import (
    ACTIVE_STATUSES,
    Appointment,
    RescheduleRequest,
    RescheduleStatus,
    User,
    UserRole,
)
from app.schemas import RescheduleRequestOut
from app.services.audit_service import write_audit
from app.services.common import appointment_names
from app.services.outbox_service import (
    EVENT_RESCHEDULE_REQUESTED,
    EVENT_RESCHEDULE_REVIEWED,
    enqueue,
)
from app.services.queue_service import apply_reschedule_locked


def serialize_request(
    request: RescheduleRequest, requester_name: str | None = None
) -> RescheduleRequestOut:
    return RescheduleRequestOut(
        id=request.id,
        appointment_id=request.appointment_id,
        requested_by=request.requested_by,
        requester_name=requester_name,
        proposed_slot_start=request.proposed_slot_start,
        reason=request.reason,
        status=request.status.value,
        reviewed_by=request.reviewed_by,
        reviewed_at=request.reviewed_at,
        review_note=request.review_note,
        created_at=request.created_at,
    )


async def create_request(
    session: AsyncSession,
    vet: User,
    *,
    appointment_id: uuid.UUID,
    proposed_slot_start: datetime,
    reason: str,
    request_id: str | None,
) -> RescheduleRequestOut:
    appt = await session.get(Appointment, appointment_id)
    if appt is None:
        raise not_found("APPOINTMENT_NOT_FOUND", "ไม่พบนัดหมายนี้")
    if appt.vet_id != vet.id:
        raise forbidden("ขอปรับเวลาได้เฉพาะเคสของตนเอง")
    if appt.status not in ACTIVE_STATUSES:
        raise conflict("INVALID_TRANSITION", "นัดหมายนี้สิ้นสุดแล้ว")

    validate_slot(proposed_slot_start)

    request = RescheduleRequest(
        appointment_id=appt.id,
        requested_by=vet.id,
        proposed_slot_start=proposed_slot_start,
        reason=reason,
        status=RescheduleStatus.PENDING,
    )
    session.add(request)
    await session.flush()

    pet_name, vet_name, owner_name = await appointment_names(session, appt)
    await write_audit(
        session,
        actor=vet,
        entity_type="APPOINTMENT",
        entity_id=appt.id,
        action="RESCHEDULE_REQUESTED",
        after={
            "request_id": str(request.id),
            "proposed_slot_start": proposed_slot_start.isoformat(),
            "reason": reason,
        },
        request_id=request_id,
    )

    staff_ids = list(
        (
            await session.execute(
                select(User.id).where(
                    User.role == UserRole.STAFF, User.is_active.is_(True)
                )
            )
        )
        .scalars()
        .all()
    )
    await enqueue(
        session,
        event_type=EVENT_RESCHEDULE_REQUESTED,
        aggregate_id=appt.id,
        payload={
            "appointment_id": str(appt.id),
            "pet_name": pet_name,
            "vet_name": vet_name,
            "owner_name": owner_name,
            "slot_start": appt.slot_start.isoformat(),
            "slot_end": appt.slot_end.isoformat(),
            "status": appt.status.value,
            "proposed_slot_start": proposed_slot_start.isoformat(),
            "reason": reason,
        },
        recipient_ids=staff_ids,
    )
    await session.commit()
    return serialize_request(request, vet.full_name)


async def list_requests(
    session: AsyncSession, *, status: str | None
) -> list[RescheduleRequestOut]:
    stmt = select(RescheduleRequest, User.full_name).join(
        User, User.id == RescheduleRequest.requested_by
    )
    if status:
        try:
            stmt = stmt.where(RescheduleRequest.status == RescheduleStatus(status))
        except ValueError:
            from app.core.errors import bad_request

            raise bad_request("INVALID_STATUS", "สถานะที่กรองไม่ถูกต้อง") from None
    rows = (
        await session.execute(
            stmt.order_by(RescheduleRequest.created_at.desc(), RescheduleRequest.id)
        )
    ).all()
    return [serialize_request(row[0], row[1]) for row in rows]


async def review_request(
    session: AsyncSession,
    staff: User,
    *,
    request_id: uuid.UUID,
    approve: bool,
    review_note: str | None,
    http_request_id: str | None,
) -> RescheduleRequestOut:
    request = await session.get(RescheduleRequest, request_id)
    if request is None:
        raise not_found("REQUEST_NOT_FOUND", "ไม่พบคำขอปรับเวลา")

    appt = await session.get(Appointment, request.appointment_id, with_for_update=True)
    if appt is None:
        raise not_found("APPOINTMENT_NOT_FOUND", "ไม่พบนัดหมายนี้")

    request = await session.get(RescheduleRequest, request_id, with_for_update=True)
    assert request is not None
    if request.status != RescheduleStatus.PENDING:
        raise conflict("REQUEST_ALREADY_REVIEWED", "คำขอนี้ถูกตรวจสอบแล้ว")

    if approve:
        await apply_reschedule_locked(
            session,
            staff,
            appt,
            new_start=request.proposed_slot_start,
            expected_version=None,
            reason=request.reason,
            request_id=http_request_id,
        )

    request.status = (
        RescheduleStatus.APPROVED if approve else RescheduleStatus.REJECTED
    )
    request.reviewed_by = staff.id
    request.reviewed_at = now_utc()
    request.review_note = review_note
    await session.flush()

    pet_name, vet_name, owner_name = await appointment_names(session, appt)
    await write_audit(
        session,
        actor=staff,
        entity_type="APPOINTMENT",
        entity_id=appt.id,
        action="RESCHEDULE_REVIEWED",
        after={
            "request_id": str(request.id),
            "decision": request.status.value,
            "review_note": review_note,
        },
        request_id=http_request_id,
    )
    await enqueue(
        session,
        event_type=EVENT_RESCHEDULE_REVIEWED,
        aggregate_id=appt.id,
        payload={
            "appointment_id": str(appt.id),
            "pet_name": pet_name,
            "vet_name": vet_name,
            "owner_name": owner_name,
            "slot_start": appt.slot_start.isoformat(),
            "slot_end": appt.slot_end.isoformat(),
            "status": appt.status.value,
            "decision": request.status.value,
            "review_note": review_note,
        },
        recipient_ids=[appt.owner_id, appt.vet_id],
    )
    await session.commit()

    requester_name = await session.scalar(
        select(User.full_name).where(User.id == request.requested_by)
    )
    return serialize_request(request, requester_name)

"""Appointment endpoints (FR-05..15)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_owner, require_roles
from app.db.session import get_session
from app.models import User, UserRole
from app.schemas import (
    AppointmentCreate,
    AppointmentOut,
    CancelRequest,
    QueuePosition,
    RescheduleBody,
    RescheduleRequestCreate,
    RescheduleRequestOut,
    StatusUpdate,
    SwapBody,
    TransferBody,
)
from app.services import booking_service, queue_service, reschedule_service

router = APIRouter(prefix="/appointments", tags=["appointments"])


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


@router.post("", response_model=AppointmentOut, status_code=201)
async def create_appointment(
    payload: AppointmentCreate,
    request: Request,
    owner: User = Depends(require_owner),
    session: AsyncSession = Depends(get_session),
) -> AppointmentOut:
    return await booking_service.create_appointment(
        session,
        owner,
        pet_id=payload.pet_id,
        vet_id=payload.vet_id,
        slot_start=payload.slot_start,
        symptoms=payload.symptoms,
        request_id=_request_id(request),
    )


@router.get("", response_model=list[AppointmentOut])
async def list_my_appointments(
    owner: User = Depends(require_owner),
    status: str | None = None,
    session: AsyncSession = Depends(get_session),
) -> list[AppointmentOut]:
    return await booking_service.list_owner_appointments(session, owner, status=status)


@router.get("/me", response_model=list[AppointmentOut])
async def my_appointments(
    owner: User = Depends(require_owner),
    status: str | None = None,
    session: AsyncSession = Depends(get_session),
) -> list[AppointmentOut]:
    return await booking_service.list_owner_appointments(session, owner, status=status)


@router.post("/swap", response_model=list[AppointmentOut])
async def swap(
    payload: SwapBody,
    request: Request,
    staff: User = Depends(require_roles(UserRole.STAFF)),
    session: AsyncSession = Depends(get_session),
) -> list[AppointmentOut]:
    first, second = await queue_service.swap_appointments(
        session,
        staff,
        appointment_a_id=payload.appointment_a_id,
        appointment_b_id=payload.appointment_b_id,
        expected_version_a=payload.expected_version_a,
        expected_version_b=payload.expected_version_b,
        request_id=_request_id(request),
    )
    return [first, second]


@router.get("/{appointment_id}", response_model=AppointmentOut)
async def get_appointment(
    appointment_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> AppointmentOut:
    return await booking_service.get_appointment_for_view(session, user, appointment_id)


@router.post("/{appointment_id}/cancel", response_model=AppointmentOut)
async def cancel(
    appointment_id: uuid.UUID,
    payload: CancelRequest,
    request: Request,
    user: User = Depends(require_roles(UserRole.OWNER, UserRole.STAFF)),
    session: AsyncSession = Depends(get_session),
) -> AppointmentOut:
    return await booking_service.cancel_appointment(
        session,
        user,
        appointment_id=appointment_id,
        reason=payload.reason,
        request_id=_request_id(request),
    )


@router.get("/{appointment_id}/queue-position", response_model=QueuePosition)
async def queue_position(
    appointment_id: uuid.UUID,
    owner: User = Depends(require_owner),
    session: AsyncSession = Depends(get_session),
) -> QueuePosition:
    appt = await queue_service.get_appointment(session, appointment_id)
    return await queue_service.queue_position(session, appt, owner_id=owner.id)


@router.patch("/{appointment_id}/status", response_model=AppointmentOut)
async def update_status(
    appointment_id: uuid.UUID,
    payload: StatusUpdate,
    request: Request,
    staff: User = Depends(require_roles(UserRole.STAFF)),
    session: AsyncSession = Depends(get_session),
) -> AppointmentOut:
    return await queue_service.change_status(
        session,
        staff,
        appointment_id=appointment_id,
        new_status=payload.status,
        expected_version=payload.expected_version,
        reason=payload.reason,
        request_id=_request_id(request),
    )


@router.patch("/{appointment_id}/reschedule", response_model=AppointmentOut)
async def reschedule(
    appointment_id: uuid.UUID,
    payload: RescheduleBody,
    request: Request,
    staff: User = Depends(require_roles(UserRole.STAFF)),
    session: AsyncSession = Depends(get_session),
) -> AppointmentOut:
    return await queue_service.reschedule_appointment(
        session,
        staff,
        appointment_id=appointment_id,
        new_start=payload.proposed_slot_start,
        expected_version=payload.expected_version,
        reason=payload.reason,
        request_id=_request_id(request),
    )


@router.post("/{appointment_id}/transfer", response_model=AppointmentOut)
async def transfer(
    appointment_id: uuid.UUID,
    payload: TransferBody,
    request: Request,
    staff: User = Depends(require_roles(UserRole.STAFF)),
    session: AsyncSession = Depends(get_session),
) -> AppointmentOut:
    return await queue_service.transfer_appointment(
        session,
        staff,
        appointment_id=appointment_id,
        new_vet_id=payload.vet_id,
        expected_version=payload.expected_version,
        reason=payload.reason,
        request_id=_request_id(request),
    )


@router.post(
    "/{appointment_id}/reschedule-requests",
    response_model=RescheduleRequestOut,
    status_code=201,
)
async def create_reschedule_request(
    appointment_id: uuid.UUID,
    payload: RescheduleRequestCreate,
    request: Request,
    vet: User = Depends(require_roles(UserRole.VET)),
    session: AsyncSession = Depends(get_session),
) -> RescheduleRequestOut:
    return await reschedule_service.create_request(
        session,
        vet,
        appointment_id=appointment_id,
        proposed_slot_start=payload.proposed_slot_start,
        reason=payload.reason,
        request_id=_request_id(request),
    )

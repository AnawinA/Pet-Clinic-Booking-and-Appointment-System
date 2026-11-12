"""Shift management (FR-15, US-14)."""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_roles
from app.core.errors import forbidden
from app.db.session import get_session
from app.models import User, UserRole
from app.schemas import (
    BulkShiftCreate,
    BulkShiftPreviewOut,
    BulkShiftResultOut,
    MessageOut,
    ShiftCreate,
    ShiftOut,
    ShiftUpdate,
)
from app.services import shift_service

router = APIRouter(prefix="/shifts", tags=["shifts"])


@router.get("", response_model=list[ShiftOut])
async def list_shifts(
    day: date | None = Query(default=None, alias="date"),
    vet_id: uuid.UUID | None = None,
    user: User = Depends(require_roles(UserRole.STAFF, UserRole.VET)),
    session: AsyncSession = Depends(get_session),
) -> list[ShiftOut]:
    if user.role == UserRole.VET:
        if vet_id is not None and vet_id != user.id:
            raise forbidden("สัตวแพทย์ดูกะของผู้อื่นไม่ได้")
        vet_id = user.id
    return await shift_service.list_shifts(session, day=day, vet_id=vet_id)


@router.post("", response_model=ShiftOut, status_code=201)
async def create_shift(
    payload: ShiftCreate,
    request: Request,
    staff: User = Depends(require_roles(UserRole.STAFF)),
    session: AsyncSession = Depends(get_session),
) -> ShiftOut:
    return await shift_service.create_shift(
        session,
        staff,
        vet_id=payload.vet_id,
        day=payload.shift_date,
        start=payload.start_time,
        end=payload.end_time,
        request_id=getattr(request.state, "request_id", None),
    )


@router.post("/bulk/preview", response_model=BulkShiftPreviewOut)
async def preview_bulk_shift_creation(
    payload: BulkShiftCreate,
    staff: User = Depends(require_roles(UserRole.STAFF)),
    session: AsyncSession = Depends(get_session),
) -> BulkShiftPreviewOut:
    return await shift_service.preview_bulk_shifts(session, payload)


@router.post("/bulk", response_model=BulkShiftResultOut)
async def create_bulk_shift_creation(
    payload: BulkShiftCreate,
    request: Request,
    staff: User = Depends(require_roles(UserRole.STAFF)),
    session: AsyncSession = Depends(get_session),
) -> BulkShiftResultOut:
    return await shift_service.create_bulk_shifts(
        session,
        staff,
        payload=payload,
        request_id=getattr(request.state, "request_id", None),
    )


@router.patch("/{shift_id}", response_model=ShiftOut)
async def update_shift(
    shift_id: uuid.UUID,
    payload: ShiftUpdate,
    request: Request,
    staff: User = Depends(require_roles(UserRole.STAFF)),
    session: AsyncSession = Depends(get_session),
) -> ShiftOut:
    return await shift_service.update_shift(
        session,
        staff,
        shift_id=shift_id,
        day=payload.shift_date,
        start=payload.start_time,
        end=payload.end_time,
        request_id=getattr(request.state, "request_id", None),
    )


@router.delete("/{shift_id}", response_model=MessageOut)
async def delete_shift(
    shift_id: uuid.UUID,
    request: Request,
    staff: User = Depends(require_roles(UserRole.STAFF)),
    session: AsyncSession = Depends(get_session),
) -> MessageOut:
    await shift_service.delete_shift(
        session,
        staff,
        shift_id=shift_id,
        request_id=getattr(request.state, "request_id", None),
    )
    return MessageOut(message="ลบกะเรียบร้อย")

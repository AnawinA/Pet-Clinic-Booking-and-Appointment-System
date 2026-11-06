"""Availability and vets (FR-04, US-2)."""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas import AvailabilitySlot, VetOut
from app.services import availability_service

router = APIRouter(tags=["availability"])


@router.get("/vets", response_model=list[VetOut])
async def list_vets(
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[VetOut]:
    vets = await availability_service.list_vets(session)
    return [VetOut(id=vet.id, full_name=vet.full_name) for vet in vets]


@router.get("/availability", response_model=list[AvailabilitySlot])
async def availability(
    day: date = Query(alias="date"),
    vet_id: uuid.UUID | None = None,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[AvailabilitySlot]:
    return await availability_service.get_availability(session, day=day, vet_id=vet_id)

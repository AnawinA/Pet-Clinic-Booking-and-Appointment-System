"""Versioned treatment notes (FR-13, US-11)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_roles
from app.db.session import get_session
from app.models import User, UserRole
from app.schemas import TreatmentNoteCreate, TreatmentNoteOut
from app.services import treatment_service

router = APIRouter(prefix="/appointments", tags=["treatment-notes"])


@router.get("/{appointment_id}/treatment-notes", response_model=list[TreatmentNoteOut])
async def list_notes(
    appointment_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[TreatmentNoteOut]:
    return await treatment_service.list_treatment_notes(
        session, user, appointment_id=appointment_id
    )


@router.post(
    "/{appointment_id}/treatment-notes", response_model=TreatmentNoteOut, status_code=201
)
async def add_note(
    appointment_id: uuid.UUID,
    payload: TreatmentNoteCreate,
    request: Request,
    vet: User = Depends(require_roles(UserRole.VET)),
    session: AsyncSession = Depends(get_session),
) -> TreatmentNoteOut:
    return await treatment_service.add_treatment_note(
        session,
        vet,
        appointment_id=appointment_id,
        content=payload.content,
        request_id=getattr(request.state, "request_id", None),
    )

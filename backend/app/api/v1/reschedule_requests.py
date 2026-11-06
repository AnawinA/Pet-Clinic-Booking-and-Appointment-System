"""Reschedule request review (FR-12, US-10)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_roles
from app.db.session import get_session
from app.models import User, UserRole
from app.schemas import RescheduleRequestOut, RescheduleReviewBody
from app.services import reschedule_service

router = APIRouter(tags=["reschedule-requests"])


@router.get("/reschedule-requests", response_model=list[RescheduleRequestOut])
async def list_requests(
    status: str | None = None,
    _: User = Depends(require_roles(UserRole.STAFF)),
    session: AsyncSession = Depends(get_session),
) -> list[RescheduleRequestOut]:
    return await reschedule_service.list_requests(session, status=status)


@router.post(
    "/reschedule-requests/{request_id}/approve", response_model=RescheduleRequestOut
)
async def approve_request(
    request_id: uuid.UUID,
    payload: RescheduleReviewBody,
    request: Request,
    staff: User = Depends(require_roles(UserRole.STAFF)),
    session: AsyncSession = Depends(get_session),
) -> RescheduleRequestOut:
    return await reschedule_service.review_request(
        session,
        staff,
        request_id=request_id,
        approve=True,
        review_note=payload.review_note,
        http_request_id=getattr(request.state, "request_id", None),
    )


@router.post("/reschedule-requests/{request_id}/reject", response_model=RescheduleRequestOut)
async def reject_request(
    request_id: uuid.UUID,
    payload: RescheduleReviewBody,
    request: Request,
    staff: User = Depends(require_roles(UserRole.STAFF)),
    session: AsyncSession = Depends(get_session),
) -> RescheduleRequestOut:
    return await reschedule_service.review_request(
        session,
        staff,
        request_id=request_id,
        approve=False,
        review_note=payload.review_note,
        http_request_id=getattr(request.state, "request_id", None),
    )

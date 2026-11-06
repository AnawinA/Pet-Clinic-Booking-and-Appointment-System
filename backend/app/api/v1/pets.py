"""Pet management and medical history (FR-06, FR-10, US-4, US-8)."""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.core.config import settings
from app.core.deps import get_current_user, require_owner
from app.core.errors import AppError, bad_request, forbidden, not_found
from app.core.time import now_utc
from app.db.session import get_session
from app.models import Appointment, Pet, TreatmentNote, User
from app.schemas import PetCreate, PetHistoryEntry, PetOut, PetUpdate, TreatmentNoteOut
from app.services.audit_service import write_audit
from app.services.common import assert_can_view_pet, serialize_appointment
from app.services.pet_photo_service import delete_pet_photo, save_pet_photo

router = APIRouter(prefix="/pets", tags=["pets"])


async def _get_owned_pet(session: AsyncSession, owner: User, pet_id: uuid.UUID) -> Pet:
    pet = await session.get(Pet, pet_id)
    if pet is None:
        raise not_found("PET_NOT_FOUND", "ไม่พบสัตว์เลี้ยงนี้")
    if pet.owner_id != owner.id:
        raise forbidden("สัตว์เลี้ยงนี้ไม่ใช่ของคุณ")
    return pet


@router.get("", response_model=list[PetOut])
async def list_pets(
    owner: User = Depends(require_owner),
    session: AsyncSession = Depends(get_session),
) -> list[Pet]:
    rows = await session.execute(
        select(Pet).where(Pet.owner_id == owner.id).order_by(Pet.created_at)
    )
    return list(rows.scalars().all())


@router.post("", response_model=PetOut, status_code=201)
async def create_pet(
    payload: PetCreate,
    request: Request,
    owner: User = Depends(require_owner),
    session: AsyncSession = Depends(get_session),
) -> Pet:
    pet = Pet(owner_id=owner.id, **payload.model_dump())
    session.add(pet)
    await session.flush()
    await write_audit(
        session,
        actor=owner,
        entity_type="PET",
        entity_id=pet.id,
        action="PET_CREATED",
        after={"name": pet.name, "species": pet.species},
        request_id=getattr(request.state, "request_id", None),
    )
    await session.commit()
    return pet


@router.get("/{pet_id}", response_model=PetOut)
async def get_pet(
    pet_id: uuid.UUID,
    owner: User = Depends(require_owner),
    session: AsyncSession = Depends(get_session),
) -> Pet:
    return await _get_owned_pet(session, owner, pet_id)


@router.post("/{pet_id}/photo", response_model=PetOut)
async def upload_pet_photo(
    pet_id: uuid.UUID,
    request: Request,
    file: UploadFile = File(...),
    owner: User = Depends(require_owner),
    session: AsyncSession = Depends(get_session),
) -> Pet:
    pet = await _get_owned_pet(session, owner, pet_id)
    if file.content_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise bad_request("INVALID_IMAGE_TYPE", "รองรับเฉพาะไฟล์ JPEG, PNG หรือ WebP")

    data = await file.read(settings.photo_max_bytes + 1)
    if not data:
        raise bad_request("EMPTY_IMAGE", "ไฟล์รูปว่างเปล่า")
    if len(data) > settings.photo_max_bytes:
        limit_mb = settings.photo_max_bytes // (1024 * 1024)
        raise AppError(413, "PHOTO_TOO_LARGE", f"ไฟล์รูปต้องมีขนาดไม่เกิน {limit_mb} MB")

    filename = await run_in_threadpool(save_pet_photo, data, pet.id)
    previous = pet.photo_filename
    pet.photo_filename = filename
    pet.photo_updated_at = now_utc()
    await write_audit(
        session,
        actor=owner,
        entity_type="PET",
        entity_id=pet.id,
        action="PET_PHOTO_UPDATED",
        before={"has_photo": previous is not None},
        after={"has_photo": True},
        request_id=getattr(request.state, "request_id", None),
    )
    try:
        await session.commit()
    except Exception:
        await run_in_threadpool(delete_pet_photo, filename)
        raise
    await run_in_threadpool(delete_pet_photo, previous)
    await session.refresh(pet)
    return pet


@router.get("/{pet_id}/photo", response_class=FileResponse)
async def get_pet_photo(
    pet_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> FileResponse:
    pet = await session.get(Pet, pet_id)
    if pet is None:
        raise not_found("PET_NOT_FOUND", "ไม่พบสัตว์เลี้ยงนี้")
    await assert_can_view_pet(session, user, pet)

    if not pet.photo_filename:
        raise not_found("PET_PHOTO_NOT_FOUND", "สัตว์เลี้ยงนี้ยังไม่มีรูป")
    path = Path(settings.photo_dir) / Path(pet.photo_filename).name
    if not path.is_file():
        raise not_found("PET_PHOTO_NOT_FOUND", "ไม่พบไฟล์รูปนี้")

    return FileResponse(
        path,
        media_type="image/webp",
        headers={"Cache-Control": "private, max-age=60"},
    )


@router.delete("/{pet_id}/photo", response_model=PetOut)
async def remove_pet_photo(
    pet_id: uuid.UUID,
    request: Request,
    owner: User = Depends(require_owner),
    session: AsyncSession = Depends(get_session),
) -> Pet:
    pet = await _get_owned_pet(session, owner, pet_id)
    if not pet.photo_filename:
        raise not_found("PET_PHOTO_NOT_FOUND", "สัตว์เลี้ยงนี้ยังไม่มีรูป")

    previous = pet.photo_filename
    pet.photo_filename = None
    pet.photo_updated_at = None
    await write_audit(
        session,
        actor=owner,
        entity_type="PET",
        entity_id=pet.id,
        action="PET_PHOTO_DELETED",
        before={"has_photo": True},
        after={"has_photo": False},
        request_id=getattr(request.state, "request_id", None),
    )
    await session.commit()
    await run_in_threadpool(delete_pet_photo, previous)
    await session.refresh(pet)
    return pet


@router.patch("/{pet_id}", response_model=PetOut)
async def update_pet(
    pet_id: uuid.UUID,
    payload: PetUpdate,
    request: Request,
    owner: User = Depends(require_owner),
    session: AsyncSession = Depends(get_session),
) -> Pet:
    pet = await _get_owned_pet(session, owner, pet_id)
    changes = payload.model_dump(exclude_unset=True)
    before = {key: getattr(pet, key) for key in changes}
    for key, value in changes.items():
        setattr(pet, key, value)
    await write_audit(
        session,
        actor=owner,
        entity_type="PET",
        entity_id=pet.id,
        action="PET_UPDATED",
        before=before,
        after=changes,
        request_id=getattr(request.state, "request_id", None),
    )
    await session.commit()
    return pet


@router.get("/{pet_id}/history", response_model=list[PetHistoryEntry])
async def pet_history(
    pet_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[PetHistoryEntry]:
    pet = await session.get(Pet, pet_id)
    if pet is None:
        raise not_found("PET_NOT_FOUND", "ไม่พบสัตว์เลี้ยงนี้")
    await assert_can_view_pet(session, user, pet)

    owner_name = await session.scalar(select(User.full_name).where(User.id == pet.owner_id))
    rows = (
        await session.execute(
            select(Appointment, User.full_name)
            .join(User, User.id == Appointment.vet_id)
            .where(Appointment.pet_id == pet.id)
            .order_by(Appointment.slot_start.desc())
        )
    ).all()
    if not rows:
        return []

    appointment_ids = [appt.id for appt, _ in rows]
    note_rows = (
        await session.execute(
            select(TreatmentNote, User.full_name)
            .join(User, User.id == TreatmentNote.created_by)
            .where(TreatmentNote.appointment_id.in_(appointment_ids))
            .order_by(TreatmentNote.version)
        )
    ).all()
    notes_by_appointment: dict[uuid.UUID, list[TreatmentNoteOut]] = {}
    for note, author_name in note_rows:
        notes_by_appointment.setdefault(note.appointment_id, []).append(
            TreatmentNoteOut(
                id=note.id,
                appointment_id=note.appointment_id,
                version=note.version,
                content=note.content,
                created_by=note.created_by,
                author_name=author_name,
                created_at=note.created_at,
            )
        )

    return [
        PetHistoryEntry(
            appointment=serialize_appointment(
                appt, pet_name=pet.name, vet_name=vet_name, owner_name=owner_name
            ),
            treatment_notes=notes_by_appointment.get(appt.id, []),
        )
        for appt, vet_name in rows
    ]

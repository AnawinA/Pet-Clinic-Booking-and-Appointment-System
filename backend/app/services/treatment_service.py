"""Versioned treatment notes (FR-13, US-11)."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import forbidden, not_found
from app.models import Appointment, TreatmentNote, User
from app.schemas import TreatmentNoteOut
from app.services.audit_service import write_audit
from app.services.common import assert_can_view_appointment
from app.services.outbox_service import EVENT_TREATMENT_NOTE_ADDED, enqueue


async def add_treatment_note(
    session: AsyncSession,
    vet: User,
    *,
    appointment_id: uuid.UUID,
    content: str,
    request_id: str | None,
) -> TreatmentNoteOut:
    appt = await session.get(Appointment, appointment_id, with_for_update=True)
    if appt is None:
        raise not_found("APPOINTMENT_NOT_FOUND", "ไม่พบนัดหมายนี้")
    if appt.vet_id != vet.id:
        raise forbidden("สัตวแพทย์ที่ได้รับมอบหมายเท่านั้นที่เขียนบันทึกได้")

    latest = await session.scalar(
        select(func.max(TreatmentNote.version)).where(
            TreatmentNote.appointment_id == appt.id
        )
    )
    version = (latest or 0) + 1
    note = TreatmentNote(
        appointment_id=appt.id,
        version=version,
        content=content,
        created_by=vet.id,
    )
    session.add(note)
    await session.flush()

    await write_audit(
        session,
        actor=vet,
        entity_type="APPOINTMENT",
        entity_id=appt.id,
        action="TREATMENT_NOTE_ADDED",
        after={"note_id": str(note.id), "version": version},
        request_id=request_id,
    )
    await enqueue(
        session,
        event_type=EVENT_TREATMENT_NOTE_ADDED,
        aggregate_id=appt.id,
        payload={
            "appointment_id": str(appt.id),
            "pet_name": None,
            "vet_name": vet.full_name,
            "owner_name": None,
            "slot_start": appt.slot_start.isoformat(),
            "slot_end": appt.slot_end.isoformat(),
            "status": appt.status.value,
            "version": version,
        },
        recipient_ids=[appt.owner_id],
    )
    await session.commit()

    return TreatmentNoteOut(
        id=note.id,
        appointment_id=note.appointment_id,
        version=note.version,
        content=note.content,
        created_by=note.created_by,
        author_name=vet.full_name,
        created_at=note.created_at,
    )


async def list_treatment_notes(
    session: AsyncSession, actor: User, *, appointment_id: uuid.UUID
) -> list[TreatmentNoteOut]:
    appt = await session.get(Appointment, appointment_id)
    if appt is None:
        raise not_found("APPOINTMENT_NOT_FOUND", "ไม่พบนัดหมายนี้")
    await assert_can_view_appointment(session, actor, appt)

    rows = (
        await session.execute(
            select(TreatmentNote, User.full_name)
            .join(User, User.id == TreatmentNote.created_by)
            .where(TreatmentNote.appointment_id == appointment_id)
            .order_by(TreatmentNote.version)
        )
    ).all()
    return [
        TreatmentNoteOut(
            id=note.id,
            appointment_id=note.appointment_id,
            version=note.version,
            content=note.content,
            created_by=note.created_by,
            author_name=author_name,
            created_at=note.created_at,
        )
        for note, author_name in rows
    ]

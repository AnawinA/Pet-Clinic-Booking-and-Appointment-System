from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import AppointmentStatus

if TYPE_CHECKING:
    from app.models.pet import Pet
    from app.models.shift import VetShift
    from app.models.user import User


class Appointment(Base):
    __tablename__ = "appointments"
    __table_args__ = (
        CheckConstraint("slot_end = slot_start + interval '30 minutes'", name="slot_length"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    pet_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("pets.id"), nullable=False
    )
    vet_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    shift_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("vet_shifts.id"), nullable=False
    )
    slot_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    slot_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[AppointmentStatus] = mapped_column(
        Enum(
            AppointmentStatus,
            name="appointment_status",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=AppointmentStatus.BOOKED,
        server_default=text("'BOOKED'"),
    )
    symptoms: Mapped[str] = mapped_column(String, nullable=False)
    cancel_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default=text("1")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    pet: Mapped[Pet] = relationship(lazy="noload")
    vet: Mapped[User] = relationship(lazy="noload", foreign_keys=[vet_id])
    owner: Mapped[User] = relationship(lazy="noload", foreign_keys=[owner_id])
    shift: Mapped[VetShift] = relationship(lazy="noload")

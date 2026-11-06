from __future__ import annotations

import uuid
from datetime import date, datetime, time

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Time, func, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class VetShift(Base):
    """A vet working window. Overlap prevention lives in a PostgreSQL EXCLUDE constraint."""

    __tablename__ = "vet_shifts"
    __table_args__ = (
        CheckConstraint(
            "start_time >= '09:00' AND end_time <= '17:00' AND start_time < end_time",
            name="shift_window",
        ),
        CheckConstraint(
            "EXTRACT(MINUTE FROM start_time) IN (0, 30) "
            "AND EXTRACT(MINUTE FROM end_time) IN (0, 30)",
            name="shift_half_hour",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    vet_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    shift_date: Mapped[date] = mapped_column(Date, nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

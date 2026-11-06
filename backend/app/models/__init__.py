"""Import every model so Alembic and the app see one metadata object."""

from app.db.base import Base
from app.models.appointment import Appointment
from app.models.audit_log import AuditLog
from app.models.enums import (
    ACTIVE_STATUSES,
    ALLOWED_TRANSITIONS,
    TERMINAL_STATUSES,
    AppointmentStatus,
    RescheduleStatus,
    UserRole,
)
from app.models.notification import Notification
from app.models.outbox import OutboxEvent
from app.models.pet import Pet
from app.models.reschedule_request import RescheduleRequest
from app.models.shift import VetShift
from app.models.treatment_note import TreatmentNote
from app.models.user import User

__all__ = [
    "ACTIVE_STATUSES",
    "ALLOWED_TRANSITIONS",
    "TERMINAL_STATUSES",
    "Appointment",
    "AppointmentStatus",
    "AuditLog",
    "Base",
    "Notification",
    "OutboxEvent",
    "Pet",
    "RescheduleRequest",
    "RescheduleStatus",
    "TreatmentNote",
    "User",
    "UserRole",
    "VetShift",
]

from __future__ import annotations

import enum


class UserRole(str, enum.Enum):
    OWNER = "OWNER"
    VET = "VET"
    STAFF = "STAFF"


class AppointmentStatus(str, enum.Enum):
    BOOKED = "BOOKED"
    CHECKED_IN = "CHECKED_IN"
    IN_TREATMENT = "IN_TREATMENT"
    COMPLETED = "COMPLETED"
    NO_SHOW = "NO_SHOW"
    CANCELLED = "CANCELLED"


class RescheduleStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


ACTIVE_STATUSES = (
    AppointmentStatus.BOOKED,
    AppointmentStatus.CHECKED_IN,
    AppointmentStatus.IN_TREATMENT,
)
TERMINAL_STATUSES = (
    AppointmentStatus.COMPLETED,
    AppointmentStatus.NO_SHOW,
    AppointmentStatus.CANCELLED,
)

# Masterplan 4.1: current status -> allowed next statuses (STAFF only).
ALLOWED_TRANSITIONS: dict[AppointmentStatus, set[AppointmentStatus]] = {
    AppointmentStatus.BOOKED: {
        AppointmentStatus.CHECKED_IN,
        AppointmentStatus.NO_SHOW,
        AppointmentStatus.CANCELLED,
    },
    AppointmentStatus.CHECKED_IN: {AppointmentStatus.IN_TREATMENT, AppointmentStatus.NO_SHOW},
    AppointmentStatus.IN_TREATMENT: {AppointmentStatus.COMPLETED},
    AppointmentStatus.COMPLETED: set(),
    AppointmentStatus.NO_SHOW: set(),
    AppointmentStatus.CANCELLED: set(),
}

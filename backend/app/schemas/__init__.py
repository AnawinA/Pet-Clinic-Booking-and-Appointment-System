from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ApiModel(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, from_attributes=True)


# ---------------------------------------------------------------- auth


class UserOut(ApiModel):
    id: UUID
    email: str
    full_name: str
    phone: str | None = None
    role: str
    is_active: bool
    created_at: datetime


class RegisterRequest(ApiModel):
    email: str = Field(min_length=3, max_length=320, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=200)
    phone: str | None = Field(default=None, max_length=30, pattern=r"^[0-9+\-\s()]{6,30}$")


class StaffAccountRequest(RegisterRequest):
    role: str = Field(pattern=r"^(VET|STAFF)$")


class StaffAppointmentResolution(ApiModel):
    appointment_id: UUID
    action: str = Field(pattern=r"^(CANCEL|TRANSFER)$")
    replacement_vet_id: UUID | None = None


class DeleteStaffAccountRequest(ApiModel):
    appointments: list[StaffAppointmentResolution] = Field(default_factory=list)


class StaffUpcomingAppointmentOut(ApiModel):
    appointment_id: UUID
    owner_id: UUID
    owner_name: str
    pet_id: UUID
    pet_name: str
    slot_start: datetime
    slot_end: datetime
    status: str


class LoginRequest(ApiModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(ApiModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    user: UserOut


# ---------------------------------------------------------------- pets


class PetCreate(ApiModel):
    name: str = Field(min_length=1, max_length=100)
    species: str = Field(min_length=1, max_length=60)
    breed: str | None = Field(default=None, max_length=100)
    sex: str | None = Field(default=None, max_length=20)
    birth_date: date | None = None
    weight_kg: Decimal | None = Field(default=None, ge=0, le=999.99)
    medical_notes: str | None = Field(default=None, max_length=4000)

    @field_validator("birth_date")
    @classmethod
    def _birth_date_not_future(cls, value: date | None) -> date | None:
        if value is not None and value > date.today():
            raise ValueError("วันเกิดต้องไม่เป็นวันในอนาคต")
        return value


class PetUpdate(ApiModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    species: str | None = Field(default=None, min_length=1, max_length=60)
    breed: str | None = Field(default=None, max_length=100)
    sex: str | None = Field(default=None, max_length=20)
    birth_date: date | None = None
    weight_kg: Decimal | None = Field(default=None, ge=0, le=999.99)
    medical_notes: str | None = Field(default=None, max_length=4000)


class PetOut(ApiModel):
    id: UUID
    owner_id: UUID
    name: str
    species: str
    breed: str | None
    sex: str | None
    birth_date: date | None
    weight_kg: Decimal | None
    medical_notes: str | None
    photo_updated_at: datetime | None = None
    created_at: datetime


# ---------------------------------------------------------------- shifts / availability


class ShiftCreate(ApiModel):
    vet_id: UUID
    shift_date: date
    start_time: str = Field(pattern=r"^([01][0-9]|2[0-3]):[0-5][0-9]$")
    end_time: str = Field(pattern=r"^([01][0-9]|2[0-3]):[0-5][0-9]$")


class ShiftUpdate(ApiModel):
    shift_date: date | None = None
    start_time: str | None = Field(default=None, pattern=r"^([01][0-9]|2[0-3]):[0-5][0-9]$")
    end_time: str | None = Field(default=None, pattern=r"^([01][0-9]|2[0-3]):[0-5][0-9]$")


class ShiftOut(ApiModel):
    id: UUID
    vet_id: UUID
    vet_name: str | None = None
    shift_date: date
    start_time: str
    end_time: str
    created_by: UUID
    created_at: datetime


class BulkShiftCreate(ApiModel):
    start_date: date
    end_date: date
    start_time: str = Field(pattern=r"^([01][0-9]|2[0-3]):[0-5][0-9]$")
    end_time: str = Field(pattern=r"^([01][0-9]|2[0-3]):[0-5][0-9]$")
    vet_ids: list[UUID] = Field(default_factory=list)
    all_vets: bool = False


class BulkShiftExistingOut(ApiModel):
    shift_id: UUID
    vet_id: UUID
    vet_name: str
    shift_date: date
    start_time: str
    end_time: str
    appointment_count: int


class BulkShiftPreviewOut(ApiModel):
    start_date: date
    end_date: date
    vet_count: int
    day_count: int
    shifts_to_create: int
    existing_shifts: list[BulkShiftExistingOut]
    blocked_shifts: list[BulkShiftExistingOut]


class BulkShiftResultOut(ApiModel):
    created: int
    replaced: int
    vet_count: int
    day_count: int


class VetOut(ApiModel):
    id: UUID
    full_name: str


class AvailabilitySlot(ApiModel):
    vet_id: UUID
    vet_name: str
    slot_start: datetime
    slot_end: datetime


# ---------------------------------------------------------------- appointments


class AppointmentCreate(ApiModel):
    pet_id: UUID
    vet_id: UUID
    slot_start: datetime
    symptoms: str = Field(min_length=1, max_length=2000)


class AppointmentOut(ApiModel):
    id: UUID
    owner_id: UUID
    owner_name: str | None = None
    pet_id: UUID
    pet_name: str | None = None
    vet_id: UUID
    vet_name: str | None = None
    slot_start: datetime
    slot_end: datetime
    status: str
    symptoms: str
    cancel_reason: str | None = None
    version: int
    created_at: datetime
    updated_at: datetime


class CancelRequest(ApiModel):
    reason: str | None = Field(default=None, max_length=500)


class StatusUpdate(ApiModel):
    status: str
    expected_version: int = Field(ge=1)
    reason: str | None = Field(default=None, max_length=500)


class RescheduleBody(ApiModel):
    proposed_slot_start: datetime
    expected_version: int = Field(ge=1)
    reason: str | None = Field(default=None, max_length=500)


class SwapBody(ApiModel):
    appointment_a_id: UUID
    appointment_b_id: UUID
    expected_version_a: int = Field(ge=1)
    expected_version_b: int = Field(ge=1)


class TransferBody(ApiModel):
    vet_id: UUID
    expected_version: int = Field(ge=1)
    reason: str | None = Field(default=None, max_length=500)


class QueueEntry(ApiModel):
    appointment_id: UUID
    vet_id: UUID
    vet_name: str
    owner_id: UUID
    owner_name: str
    pet_id: UUID
    pet_name: str
    slot_start: datetime
    slot_end: datetime
    status: str
    ahead_count: int
    estimated_start: datetime | None
    updated_at: datetime


class QueuePosition(ApiModel):
    appointment_id: UUID
    ahead_count: int
    estimated_start: datetime | None
    status: str


class ScheduleEntry(ApiModel):
    appointment_id: UUID
    version: int
    vet_id: UUID
    owner_id: UUID
    owner_name: str
    pet_id: UUID
    pet_name: str
    slot_start: datetime
    slot_end: datetime
    status: str
    symptoms: str
    estimated_start: datetime | None
    updated_at: datetime


# ---------------------------------------------------------------- treatment notes


class TreatmentNoteCreate(ApiModel):
    content: str = Field(min_length=1, max_length=8000)


class TreatmentNoteOut(ApiModel):
    id: UUID
    appointment_id: UUID
    version: int
    content: str
    created_by: UUID
    author_name: str | None = None
    created_at: datetime


class PetHistoryEntry(ApiModel):
    appointment: AppointmentOut
    treatment_notes: list[TreatmentNoteOut]


# ---------------------------------------------------------------- reschedule requests


class RescheduleRequestCreate(ApiModel):
    proposed_slot_start: datetime
    reason: str = Field(min_length=1, max_length=1000)


class RescheduleReviewBody(ApiModel):
    review_note: str | None = Field(default=None, max_length=1000)


class RescheduleRequestOut(ApiModel):
    id: UUID
    appointment_id: UUID
    requested_by: UUID
    requester_name: str | None = None
    proposed_slot_start: datetime
    reason: str
    status: str
    reviewed_by: UUID | None = None
    reviewed_at: datetime | None = None
    review_note: str | None = None
    created_at: datetime


# ---------------------------------------------------------------- notifications / audit


class NotificationOut(ApiModel):
    id: UUID
    event_id: UUID
    type: str
    title: str
    message: str
    is_read: bool
    created_at: datetime


class AuditLogOut(ApiModel):
    id: int
    actor_id: UUID | None
    actor_role: str | None
    entity_type: str
    entity_id: UUID
    action: str
    before: dict | None
    after: dict | None
    request_id: str | None
    created_at: datetime


class MessageOut(ApiModel):
    message: str

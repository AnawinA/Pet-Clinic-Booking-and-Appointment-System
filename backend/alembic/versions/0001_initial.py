"""Initial PetCare schema (masterplan section 3).

Revision ID: 0001_initial
Revises:
Create Date: 2026-01-01
"""

from __future__ import annotations

from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

UPGRADE_STATEMENTS = [
    "CREATE EXTENSION IF NOT EXISTS citext",
    "CREATE EXTENSION IF NOT EXISTS btree_gist",
    "CREATE TYPE user_role AS ENUM ('OWNER', 'VET', 'STAFF')",
    "CREATE TYPE appointment_status AS ENUM "
    "('BOOKED', 'CHECKED_IN', 'IN_TREATMENT', 'COMPLETED', 'NO_SHOW', 'CANCELLED')",
    "CREATE TYPE reschedule_status AS ENUM ('PENDING', 'APPROVED', 'REJECTED')",
    """
    CREATE TABLE users (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      email CITEXT UNIQUE NOT NULL,
      password_hash TEXT NOT NULL,
      full_name TEXT NOT NULL,
      phone TEXT,
      role user_role NOT NULL,
      is_active BOOLEAN NOT NULL DEFAULT TRUE,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE pets (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      owner_id UUID NOT NULL REFERENCES users(id),
      name TEXT NOT NULL,
      species TEXT NOT NULL,
      breed TEXT,
      sex TEXT,
      birth_date DATE,
      weight_kg NUMERIC(5,2),
      medical_notes TEXT,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE vet_shifts (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      vet_id UUID NOT NULL REFERENCES users(id),
      shift_date DATE NOT NULL,
      start_time TIME NOT NULL,
      end_time TIME NOT NULL,
      created_by UUID NOT NULL REFERENCES users(id),
      created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      CONSTRAINT ck_vet_shifts_window
        CHECK (start_time >= '09:00' AND end_time <= '17:00' AND start_time < end_time),
      CONSTRAINT ck_vet_shifts_half_hour
        CHECK (EXTRACT(MINUTE FROM start_time) IN (0,30)
           AND EXTRACT(MINUTE FROM end_time) IN (0,30)),
      CONSTRAINT shift_no_overlap EXCLUDE USING gist (
        vet_id WITH =,
        tsrange(shift_date + start_time, shift_date + end_time) WITH &&
      )
    )
    """,
    """
    CREATE TABLE appointments (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      owner_id UUID NOT NULL REFERENCES users(id),
      pet_id UUID NOT NULL REFERENCES pets(id),
      vet_id UUID NOT NULL REFERENCES users(id),
      shift_id UUID NOT NULL REFERENCES vet_shifts(id),
      slot_start TIMESTAMPTZ NOT NULL,
      slot_end TIMESTAMPTZ NOT NULL,
      status appointment_status NOT NULL DEFAULT 'BOOKED',
      symptoms TEXT NOT NULL,
      cancel_reason TEXT,
      cancelled_at TIMESTAMPTZ,
      version INT NOT NULL DEFAULT 1,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      CONSTRAINT ck_appointments_slot_length
        CHECK (slot_end = slot_start + interval '30 minutes')
    )
    """,
    "CREATE UNIQUE INDEX uq_vet_slot_active ON appointments(vet_id, slot_start) "
    "WHERE status <> 'CANCELLED'",
    "CREATE UNIQUE INDEX uq_pet_slot_active ON appointments(pet_id, slot_start) "
    "WHERE status <> 'CANCELLED'",
    "CREATE INDEX ix_appt_vet_day ON appointments(vet_id, slot_start)",
    "CREATE INDEX ix_appt_updated ON appointments(updated_at)",
    "CREATE INDEX ix_appt_owner ON appointments(owner_id, slot_start)",
    """
    CREATE TABLE treatment_notes (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      appointment_id UUID NOT NULL REFERENCES appointments(id),
      version INT NOT NULL,
      content TEXT NOT NULL CHECK (length(trim(content)) > 0),
      created_by UUID NOT NULL REFERENCES users(id),
      created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      CONSTRAINT uq_treatment_notes_version UNIQUE (appointment_id, version)
    )
    """,
    """
    CREATE TABLE reschedule_requests (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      appointment_id UUID NOT NULL REFERENCES appointments(id),
      requested_by UUID NOT NULL REFERENCES users(id),
      proposed_slot_start TIMESTAMPTZ NOT NULL,
      reason TEXT NOT NULL CHECK (length(trim(reason)) > 0),
      status reschedule_status NOT NULL DEFAULT 'PENDING',
      reviewed_by UUID REFERENCES users(id),
      reviewed_at TIMESTAMPTZ,
      review_note TEXT,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE audit_logs (
      id BIGSERIAL PRIMARY KEY,
      actor_id UUID,
      actor_role user_role,
      entity_type TEXT NOT NULL,
      entity_id UUID NOT NULL,
      action TEXT NOT NULL,
      before JSONB,
      after JSONB,
      request_id TEXT,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    "CREATE INDEX ix_audit_entity ON audit_logs(entity_id, created_at)",
    """
    CREATE OR REPLACE FUNCTION prevent_audit_log_changes() RETURNS trigger
    LANGUAGE plpgsql AS $$
    BEGIN
      RAISE EXCEPTION 'audit_logs is append-only';
    END;
    $$
    """,
    "CREATE TRIGGER audit_logs_no_update_delete BEFORE UPDATE OR DELETE ON audit_logs "
    "FOR EACH ROW EXECUTE FUNCTION prevent_audit_log_changes()",
    """
    CREATE TABLE outbox_events (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      event_type TEXT NOT NULL,
      aggregate_id UUID NOT NULL,
      payload JSONB NOT NULL,
      available_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      processed_at TIMESTAMPTZ,
      attempts INT NOT NULL DEFAULT 0,
      last_error TEXT,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    "CREATE INDEX ix_outbox_pending ON outbox_events(available_at) WHERE processed_at IS NULL",
    """
    CREATE TABLE notifications (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      event_id UUID NOT NULL REFERENCES outbox_events(id),
      recipient_id UUID NOT NULL REFERENCES users(id),
      type TEXT NOT NULL,
      title TEXT NOT NULL,
      message TEXT NOT NULL,
      is_read BOOLEAN NOT NULL DEFAULT FALSE,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      CONSTRAINT uq_notifications_event_recipient UNIQUE (event_id, recipient_id)
    )
    """,
    "CREATE INDEX ix_notifications_recipient ON notifications(recipient_id, created_at DESC)",
]

DOWNGRADE_STATEMENTS = [
    "DROP TABLE IF EXISTS notifications",
    "DROP TABLE IF EXISTS outbox_events",
    "DROP TRIGGER IF EXISTS audit_logs_no_update_delete ON audit_logs",
    "DROP FUNCTION IF EXISTS prevent_audit_log_changes()",
    "DROP TABLE IF EXISTS audit_logs",
    "DROP TABLE IF EXISTS reschedule_requests",
    "DROP TABLE IF EXISTS treatment_notes",
    "DROP TABLE IF EXISTS appointments",
    "DROP TABLE IF EXISTS vet_shifts",
    "DROP TABLE IF EXISTS pets",
    "DROP TABLE IF EXISTS users",
    "DROP TYPE IF EXISTS reschedule_status",
    "DROP TYPE IF EXISTS appointment_status",
    "DROP TYPE IF EXISTS user_role",
    "DROP EXTENSION IF EXISTS btree_gist",
    "DROP EXTENSION IF EXISTS citext",
]


def upgrade() -> None:
    for statement in UPGRADE_STATEMENTS:
        op.execute(statement)


def downgrade() -> None:
    for statement in DOWNGRADE_STATEMENTS:
        op.execute(statement)

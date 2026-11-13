from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import func, select

from app.models import AuditLog, OutboxEvent
from app.services import booking_service
from tests.conftest import test_session_factory
from tests.helpers import auth, book


async def test_booking_creates_audit_and_two_outbox_events(client, tokens, seeded):
    response = await book(
        client,
        tokens["OWNER"],
        pet_id=seeded["pet1_id"],
        vet_id=seeded["vet1_id"],
        day=seeded["day"],
        hour=9,
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "BOOKED"
    assert body["version"] == 1
    assert body["vet_name"] == "หมอหนึ่ง"

    async with test_session_factory() as session:
        audit_count = await session.scalar(
            select(func.count(AuditLog.id)).where(AuditLog.entity_id == body["id"])
        )
        events = list(
            (
                await session.execute(
                    select(OutboxEvent.event_type).where(
                        OutboxEvent.aggregate_id == body["id"]
                    )
                )
            )
            .scalars()
            .all()
        )
    assert audit_count == 1
    assert sorted(events) == ["APPOINTMENT_BOOKED", "APPOINTMENT_REMINDER"]


async def test_cannot_book_another_owners_pet(client, tokens, seeded):
    response = await book(
        client,
        tokens["OWNER"],
        pet_id=seeded["pet3_id"],
        vet_id=seeded["vet1_id"],
        day=seeded["day"],
        hour=9,
    )
    assert response.status_code == 403


async def test_slot_outside_shift_is_rejected(client, tokens, seeded):
    response = await book(
        client,
        tokens["OWNER"],
        pet_id=seeded["pet1_id"],
        vet_id=seeded["vet1_id"],
        day=seeded["day"] + timedelta(days=5),
        hour=9,
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "SLOT_OUT_OF_RANGE"


async def test_vet_cannot_book(client, tokens, seeded):
    response = await book(
        client,
        tokens["VET"],
        pet_id=seeded["pet1_id"],
        vet_id=seeded["vet1_id"],
        day=seeded["day"],
        hour=9,
    )
    assert response.status_code == 403


async def test_owner_cancel_succeeds_outside_two_hour_window(
    client, tokens, seeded, monkeypatch
):
    booking = await book(
        client,
        tokens["OWNER"],
        pet_id=seeded["pet1_id"],
        vet_id=seeded["vet1_id"],
        day=seeded["day"],
        hour=10,
    )
    assert booking.status_code == 201
    slot_start = __import__("datetime").datetime.fromisoformat(booking.json()["slot_start"])

    monkeypatch.setattr(
        booking_service, "now_utc", lambda: slot_start - timedelta(hours=4)
    )
    response = await client.post(
        f"/api/v1/appointments/{booking.json()['id']}/cancel",
        headers=auth(tokens["OWNER"]),
        json={"reason": "ติดธุระ"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "CANCELLED"

    # The slot frees up immediately because the unique index is partial.
    availability = await client.get(
        "/api/v1/availability",
        params={"date": seeded["day"].isoformat(), "vet_id": str(seeded["vet1_id"])},
        headers=auth(tokens["OWNER"]),
    )
    assert any(
        item["slot_start"] == booking.json()["slot_start"] for item in availability.json()
    )


async def test_owner_cancel_inside_two_hours_is_rejected(client, tokens, seeded, monkeypatch):
    booking = await book(
        client,
        tokens["OWNER"],
        pet_id=seeded["pet1_id"],
        vet_id=seeded["vet1_id"],
        day=seeded["day"],
        hour=11,
    )
    assert booking.status_code == 201
    slot_start = __import__("datetime").datetime.fromisoformat(booking.json()["slot_start"])
    monkeypatch.setattr(
        booking_service, "now_utc", lambda: slot_start - timedelta(hours=1)
    )

    response = await client.post(
        f"/api/v1/appointments/{booking.json()['id']}/cancel",
        headers=auth(tokens["OWNER"]),
        json={"reason": "กระทันหัน"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "CANCEL_WINDOW_CLOSED"


@pytest.mark.parametrize("target_status", ["CHECKED_IN", "IN_TREATMENT"])
async def test_owner_can_only_cancel_booked_appointments(
    client, tokens, seeded, monkeypatch, target_status
):
    booking = await book(
        client,
        tokens["OWNER"],
        pet_id=seeded["pet1_id"],
        vet_id=seeded["vet1_id"],
        day=seeded["day"],
        hour=12,
    )
    appointment_id = booking.json()["id"]
    slot_start = __import__("datetime").datetime.fromisoformat(booking.json()["slot_start"])

    version = booking.json()["version"]
    for status in ("CHECKED_IN", "IN_TREATMENT"):
        updated = await client.patch(
            f"/api/v1/appointments/{appointment_id}/status",
            headers=auth(tokens["STAFF"]),
            json={"status": status, "expected_version": version},
        )
        assert updated.status_code == 200, updated.text
        version = updated.json()["version"]
        if status == target_status:
            break

    monkeypatch.setattr(
        booking_service, "now_utc", lambda: slot_start - timedelta(hours=4)
    )
    response = await client.post(
        f"/api/v1/appointments/{appointment_id}/cancel",
        headers=auth(tokens["OWNER"]),
        json={"reason": "ทดสอบยกเลิกหลังเริ่มกระบวนการ"},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INVALID_TRANSITION"

    detail = await client.get(
        f"/api/v1/appointments/{appointment_id}",
        headers=auth(tokens["OWNER"]),
    )
    assert detail.status_code == 200
    assert detail.json()["status"] == target_status


async def test_staff_can_cancel_inside_two_hours(client, tokens, seeded, monkeypatch):
    booking = await book(
        client,
        tokens["OWNER"],
        pet_id=seeded["pet1_id"],
        vet_id=seeded["vet1_id"],
        day=seeded["day"],
        hour=12,
    )
    assert booking.status_code == 201
    slot_start = __import__("datetime").datetime.fromisoformat(booking.json()["slot_start"])
    monkeypatch.setattr(
        booking_service, "now_utc", lambda: slot_start - timedelta(hours=1)
    )

    response = await client.post(
        f"/api/v1/appointments/{booking.json()['id']}/cancel",
        headers=auth(tokens["STAFF"]),
        json={"reason": "คลินิกปิดฉุกเฉิน"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "CANCELLED"


async def test_queue_position_for_owner(client, tokens, seeded):
    first = await book(
        client, tokens["OWNER"], pet_id=seeded["pet1_id"],
        vet_id=seeded["vet1_id"], day=seeded["day"], hour=13,
    )
    second = await book(
        client, tokens["OWNER"], pet_id=seeded["pet2_id"],
        vet_id=seeded["vet1_id"], day=seeded["day"], hour=14,
    )
    assert first.status_code == second.status_code == 201

    response = await client.get(
        f"/api/v1/appointments/{second.json()['id']}/queue-position",
        headers=auth(tokens["OWNER"]),
    )
    assert response.status_code == 200
    assert response.json()["ahead_count"] == 1
    assert response.json()["estimated_start"] is not None


async def test_live_queue_hides_other_owners_pet_data(client, tokens, seeded):
    other_owner_booking = await book(
        client,
        tokens["OWNER2"],
        pet_id=seeded["pet3_id"],
        vet_id=seeded["vet1_id"],
        day=seeded["day"],
        hour=13,
    )
    own_booking = await book(
        client,
        tokens["OWNER"],
        pet_id=seeded["pet1_id"],
        vet_id=seeded["vet1_id"],
        day=seeded["day"],
        hour=13,
        minute=30,
    )
    assert other_owner_booking.status_code == own_booking.status_code == 201

    response = await client.get(
        "/api/v1/queue/live",
        headers=auth(tokens["OWNER"]),
        params={
            "date": seeded["day"].isoformat(),
            "vet_id": str(seeded["vet1_id"]),
        },
    )

    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["appointment_id"] == own_booking.json()["id"]
    assert items[0]["pet_id"] == str(seeded["pet1_id"])
    assert items[0]["ahead_count"] == 1
    assert all(
        item["pet_id"] != str(seeded["pet3_id"])
        and item["appointment_id"] != other_owner_booking.json()["id"]
        for item in items
    )


async def test_other_owner_cannot_read_or_cancel(client, tokens, seeded):
    booking = await book(
        client, tokens["OWNER"], pet_id=seeded["pet1_id"],
        vet_id=seeded["vet1_id"], day=seeded["day"], hour=15,
    )
    appointment_id = booking.json()["id"]

    detail = await client.get(
        f"/api/v1/appointments/{appointment_id}", headers=auth(tokens["OWNER2"])
    )
    assert detail.status_code == 403

    cancel = await client.post(
        f"/api/v1/appointments/{appointment_id}/cancel",
        headers=auth(tokens["OWNER2"]),
        json={},
    )
    assert cancel.status_code == 403

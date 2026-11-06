from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select

from app.models import AuditLog
from tests.conftest import test_session_factory
from tests.helpers import auth, book


async def test_valid_transition_chain_writes_audit(client, tokens, seeded):
    booking = await book(
        client, tokens["OWNER"], pet_id=seeded["pet1_id"],
        vet_id=seeded["vet1_id"], day=seeded["day"], hour=9,
    )
    appointment_id = booking.json()["id"]
    version = booking.json()["version"]

    for target in ("CHECKED_IN", "IN_TREATMENT", "COMPLETED"):
        response = await client.patch(
            f"/api/v1/appointments/{appointment_id}/status",
            headers=auth(tokens["STAFF"]),
            json={"status": target, "expected_version": version},
        )
        assert response.status_code == 200, response.text
        version = response.json()["version"]
        assert response.json()["status"] == target

    async with test_session_factory() as session:
        count = await session.scalar(
            select(func.count(AuditLog.id)).where(
                AuditLog.entity_id == appointment_id,
                AuditLog.action == "STATUS_CHANGE",
            )
        )
    assert count == 3


async def test_invalid_transition_returns_409(client, tokens, seeded):
    booking = await book(
        client, tokens["OWNER"], pet_id=seeded["pet1_id"],
        vet_id=seeded["vet1_id"], day=seeded["day"], hour=10,
    )
    response = await client.patch(
        f"/api/v1/appointments/{booking.json()['id']}/status",
        headers=auth(tokens["STAFF"]),
        json={"status": "COMPLETED", "expected_version": 1},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INVALID_TRANSITION"


async def test_stale_version_returns_409(client, tokens, seeded):
    booking = await book(
        client, tokens["OWNER"], pet_id=seeded["pet1_id"],
        vet_id=seeded["vet1_id"], day=seeded["day"], hour=11,
    )
    response = await client.patch(
        f"/api/v1/appointments/{booking.json()['id']}/status",
        headers=auth(tokens["STAFF"]),
        json={"status": "CHECKED_IN", "expected_version": 99},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "STALE_VERSION"


async def test_owner_cannot_change_status(client, tokens, seeded):
    booking = await book(
        client, tokens["OWNER"], pet_id=seeded["pet1_id"],
        vet_id=seeded["vet1_id"], day=seeded["day"], hour=12,
    )
    response = await client.patch(
        f"/api/v1/appointments/{booking.json()['id']}/status",
        headers=auth(tokens["OWNER"]),
        json={"status": "CHECKED_IN", "expected_version": 1},
    )
    assert response.status_code == 403


async def test_staff_can_cancel_via_status_endpoint(client, tokens, seeded):
    booking = await book(
        client, tokens["OWNER"], pet_id=seeded["pet1_id"],
        vet_id=seeded["vet1_id"], day=seeded["day"], hour=13,
    )
    response = await client.patch(
        f"/api/v1/appointments/{booking.json()['id']}/status",
        headers=auth(tokens["STAFF"]),
        json={"status": "CANCELLED", "expected_version": 1, "reason": "แพทย์ติดเคสฉุกเฉิน"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "CANCELLED"

    again = await client.patch(
        f"/api/v1/appointments/{booking.json()['id']}/status",
        headers=auth(tokens["STAFF"]),
        json={"status": "CHECKED_IN", "expected_version": 2},
    )
    assert again.status_code == 409


async def test_reschedule_moves_slot(client, tokens, seeded):
    booking = await book(
        client, tokens["OWNER"], pet_id=seeded["pet1_id"],
        vet_id=seeded["vet1_id"], day=seeded["day"], hour=14,
    )
    from tests.helpers import slot

    response = await client.patch(
        f"/api/v1/appointments/{booking.json()['id']}/reschedule",
        headers=auth(tokens["STAFF"]),
        json={
            "proposed_slot_start": slot(seeded["day"], 16, 0).isoformat(),
            "expected_version": 1,
        },
    )
    assert response.status_code == 200, response.text
    assert datetime.fromisoformat(response.json()["slot_start"]) == slot(seeded["day"], 16, 0)
    assert datetime.fromisoformat(response.json()["slot_end"]) == slot(seeded["day"], 16, 30)
    assert response.json()["version"] == 2


async def test_reschedule_conflict_returns_409(client, tokens, seeded):
    first = await book(
        client, tokens["OWNER"], pet_id=seeded["pet1_id"],
        vet_id=seeded["vet1_id"], day=seeded["day"], hour=16,
    )
    second = await book(
        client, tokens["OWNER"], pet_id=seeded["pet2_id"],
        vet_id=seeded["vet1_id"], day=seeded["day"], hour=16, minute=30,
    )

    response = await client.patch(
        f"/api/v1/appointments/{second.json()['id']}/reschedule",
        headers=auth(tokens["STAFF"]),
        json={"proposed_slot_start": first.json()["slot_start"], "expected_version": 1},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "SLOT_TAKEN"


async def test_transfer_requires_target_availability(client, tokens, seeded):
    booking = await book(
        client, tokens["OWNER"], pet_id=seeded["pet1_id"],
        vet_id=seeded["vet1_id"], day=seeded["day"], hour=9,
    )
    response = await client.post(
        f"/api/v1/appointments/{booking.json()['id']}/transfer",
        headers=auth(tokens["STAFF"]),
        json={"vet_id": str(seeded["vet2_id"]), "expected_version": 1},
    )
    assert response.status_code == 200, response.text
    assert response.json()["vet_id"] == str(seeded["vet2_id"])

    async with test_session_factory() as session:
        count = await session.scalar(
            select(func.count(AuditLog.id)).where(
                AuditLog.entity_id == booking.json()["id"], AuditLog.action == "TRANSFER"
            )
        )
    assert count == 1


async def test_swap_two_appointments(client, tokens, seeded):
    first = await book(
        client, tokens["OWNER"], pet_id=seeded["pet1_id"],
        vet_id=seeded["vet1_id"], day=seeded["day"], hour=10,
    )
    second = await book(
        client, tokens["OWNER"], pet_id=seeded["pet2_id"],
        vet_id=seeded["vet1_id"], day=seeded["day"], hour=10, minute=30,
    )
    first_slot = first.json()["slot_start"]
    second_slot = second.json()["slot_start"]

    response = await client.post(
        "/api/v1/appointments/swap",
        headers=auth(tokens["STAFF"]),
        json={
            "appointment_a_id": first.json()["id"],
            "appointment_b_id": second.json()["id"],
            "expected_version_a": 1,
            "expected_version_b": 1,
        },
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result[0]["slot_start"] == second_slot
    assert result[1]["slot_start"] == first_slot

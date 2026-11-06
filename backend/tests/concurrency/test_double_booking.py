from __future__ import annotations

import asyncio
from collections import Counter

from sqlalchemy import func, select

from app.models import Appointment
from tests.conftest import test_session_factory
from tests.helpers import auth, iso_slot


async def test_twenty_parallel_bookings_only_one_wins(client, tokens, seeded):
    body = {
        "pet_id": str(seeded["pet1_id"]),
        "vet_id": str(seeded["vet1_id"]),
        "slot_start": iso_slot(seeded["day"], 9, 0),
        "symptoms": "ทดสอบการจองพร้อมกัน",
    }
    headers = auth(tokens["OWNER"])

    async def attempt() -> int:
        response = await client.post("/api/v1/appointments", json=body, headers=headers)
        return response.status_code

    statuses = await asyncio.gather(*(attempt() for _ in range(20)))
    counts = Counter(statuses)

    assert counts[201] == 1, f"expected one success, got {counts}"
    assert counts[409] == 19, f"expected 19 conflicts, got {counts}"

    async with test_session_factory() as session:
        rows = await session.scalar(
            select(func.count(Appointment.id)).where(
                Appointment.vet_id == seeded["vet1_id"]
            )
        )
    assert rows == 1


async def test_same_pet_cannot_be_booked_twice_in_one_slot(client, tokens, seeded):
    first = await client.post(
        "/api/v1/appointments",
        headers=auth(tokens["OWNER"]),
        json={
            "pet_id": str(seeded["pet1_id"]),
            "vet_id": str(seeded["vet1_id"]),
            "slot_start": iso_slot(seeded["day"], 10, 0),
            "symptoms": "ซึม",
        },
    )
    assert first.status_code == 201

    second = await client.post(
        "/api/v1/appointments",
        headers=auth(tokens["OWNER"]),
        json={
            "pet_id": str(seeded["pet1_id"]),
            "vet_id": str(seeded["vet2_id"]),
            "slot_start": iso_slot(seeded["day"], 10, 0),
            "symptoms": "ซึม",
        },
    )
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "PET_SLOT_TAKEN"

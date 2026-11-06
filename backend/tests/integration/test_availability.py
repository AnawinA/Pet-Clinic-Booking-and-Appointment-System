from __future__ import annotations

from datetime import timedelta
from zoneinfo import ZoneInfo

from tests.helpers import auth, book

BANGKOK = ZoneInfo("Asia/Bangkok")


async def test_no_shift_returns_empty_list(client, tokens, seeded):
    day = seeded["day"] + timedelta(days=10)
    response = await client.get(
        "/api/v1/availability",
        params={"date": day.isoformat(), "vet_id": str(seeded["vet1_id"])},
        headers=auth(tokens["OWNER"]),
    )
    assert response.status_code == 200
    assert response.json() == []


async def test_shift_generates_half_hour_slots(client, tokens, seeded):
    response = await client.get(
        "/api/v1/availability",
        params={"date": seeded["day"].isoformat(), "vet_id": str(seeded["vet1_id"])},
        headers=auth(tokens["OWNER"]),
    )
    assert response.status_code == 200
    slots = response.json()
    assert len(slots) == 16
    first_local = __import__("datetime").datetime.fromisoformat(slots[0]["slot_start"])
    last_local = __import__("datetime").datetime.fromisoformat(slots[-1]["slot_start"])
    assert first_local.astimezone(BANGKOK).strftime("%H:%M") == "09:00"
    assert last_local.astimezone(BANGKOK).strftime("%H:%M") == "16:30"


async def test_booked_slot_disappears_from_availability(client, tokens, seeded):
    booked = await book(
        client,
        tokens["OWNER"],
        pet_id=seeded["pet1_id"],
        vet_id=seeded["vet1_id"],
        day=seeded["day"],
        hour=10,
    )
    assert booked.status_code == 201, booked.text

    response = await client.get(
        "/api/v1/availability",
        params={"date": seeded["day"].isoformat(), "vet_id": str(seeded["vet1_id"])},
        headers=auth(tokens["OWNER"]),
    )
    slots = response.json()
    assert len(slots) == 15
    assert all(slot["slot_start"] != booked.json()["slot_start"] for slot in slots)


async def test_past_date_returns_no_slots(client, tokens, seeded):
    day = seeded["day"] - timedelta(days=5)
    response = await client.get(
        "/api/v1/availability",
        params={"date": day.isoformat(), "vet_id": str(seeded["vet1_id"])},
        headers=auth(tokens["OWNER"]),
    )
    assert response.status_code == 200
    assert response.json() == []


async def test_unknown_vet_returns_404(client, tokens, seeded):
    response = await client.get(
        "/api/v1/availability",
        params={
            "date": seeded["day"].isoformat(),
            "vet_id": "00000000-0000-0000-0000-000000000000",
        },
        headers=auth(tokens["OWNER"]),
    )
    assert response.status_code == 404

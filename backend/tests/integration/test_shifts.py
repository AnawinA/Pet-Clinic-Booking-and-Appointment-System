from __future__ import annotations

from datetime import timedelta

from tests.helpers import auth, book


async def test_staff_creates_shift(client, tokens, seeded):
    day = seeded["day"] + timedelta(days=3)
    response = await client.post(
        "/api/v1/shifts",
        headers=auth(tokens["STAFF"]),
        json={
            "vet_id": str(seeded["vet1_id"]),
            "shift_date": day.isoformat(),
            "start_time": "10:00",
            "end_time": "12:00",
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["start_time"] == "10:00"


async def test_overlapping_shift_returns_409(client, tokens, seeded):
    day = seeded["day"] + timedelta(days=3)
    payload = {
        "vet_id": str(seeded["vet1_id"]),
        "shift_date": day.isoformat(),
        "start_time": "10:00",
        "end_time": "12:00",
    }
    first = await client.post("/api/v1/shifts", headers=auth(tokens["STAFF"]), json=payload)
    assert first.status_code == 201

    overlap = await client.post(
        "/api/v1/shifts",
        headers=auth(tokens["STAFF"]),
        json={**payload, "start_time": "11:00", "end_time": "13:00"},
    )
    assert overlap.status_code == 409
    assert overlap.json()["error"]["code"] == "SHIFT_OVERLAP"


async def test_shift_outside_window_returns_422(client, tokens, seeded):
    response = await client.post(
        "/api/v1/shifts",
        headers=auth(tokens["STAFF"]),
        json={
            "vet_id": str(seeded["vet1_id"]),
            "shift_date": (seeded["day"] + timedelta(days=3)).isoformat(),
            "start_time": "08:00",
            "end_time": "10:00",
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_SHIFT"


async def test_delete_shift_with_pending_appointment_returns_409(client, tokens, seeded):
    shifts = await client.get(
        "/api/v1/shifts",
        params={"date": seeded["day"].isoformat(), "vet_id": str(seeded["vet1_id"])},
        headers=auth(tokens["STAFF"]),
    )
    shift_id = shifts.json()[0]["id"]

    await book(
        client, tokens["OWNER"], pet_id=seeded["pet1_id"],
        vet_id=seeded["vet1_id"], day=seeded["day"], hour=9,
    )

    response = await client.delete(
        f"/api/v1/shifts/{shift_id}", headers=auth(tokens["STAFF"])
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "SHIFT_HAS_APPOINTMENTS"


async def test_delete_unused_shift_succeeds(client, tokens, seeded):
    day = seeded["day"] + timedelta(days=4)
    created = await client.post(
        "/api/v1/shifts",
        headers=auth(tokens["STAFF"]),
        json={
            "vet_id": str(seeded["vet1_id"]),
            "shift_date": day.isoformat(),
            "start_time": "13:00",
            "end_time": "15:00",
        },
    )
    shift_id = created.json()["id"]
    response = await client.delete(
        f"/api/v1/shifts/{shift_id}", headers=auth(tokens["STAFF"])
    )
    assert response.status_code == 200


async def test_vet_only_sees_own_shifts(client, tokens, seeded):
    own = await client.get(
        "/api/v1/shifts",
        headers=auth(tokens["VET"]),
        params={"vet_id": str(seeded["vet1_id"])},
    )
    assert own.status_code == 200
    assert all(item["vet_id"] == str(seeded["vet1_id"]) for item in own.json())

    other = await client.get(
        "/api/v1/shifts",
        headers=auth(tokens["VET"]),
        params={"vet_id": str(seeded["vet2_id"])},
    )
    assert other.status_code == 403


async def test_vet_cannot_create_shift(client, tokens, seeded):
    response = await client.post(
        "/api/v1/shifts",
        headers=auth(tokens["VET"]),
        json={
            "vet_id": str(seeded["vet1_id"]),
            "shift_date": (seeded["day"] + timedelta(days=5)).isoformat(),
            "start_time": "09:00",
            "end_time": "10:00",
        },
    )
    assert response.status_code == 403


async def test_staff_updates_shift(client, tokens, seeded):
    day = seeded["day"] + timedelta(days=6)
    created = await client.post(
        "/api/v1/shifts",
        headers=auth(tokens["STAFF"]),
        json={
            "vet_id": str(seeded["vet2_id"]),
            "shift_date": day.isoformat(),
            "start_time": "09:00",
            "end_time": "12:00",
        },
    )
    shift_id = created.json()["id"]
    updated = await client.patch(
        f"/api/v1/shifts/{shift_id}",
        headers=auth(tokens["STAFF"]),
        json={"end_time": "15:00"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["end_time"] == "15:00"

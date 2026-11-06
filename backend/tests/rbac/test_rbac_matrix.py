from __future__ import annotations

from datetime import timedelta

import pytest

from tests.helpers import auth, book, unique_email

CASES = [
    ("GET", "/api/v1/pets", "OWNER", 200),
    ("GET", "/api/v1/pets", "VET", 403),
    ("GET", "/api/v1/pets", "STAFF", 403),
    ("GET", "/api/v1/audit-logs", "STAFF", 200),
    ("GET", "/api/v1/audit-logs", "OWNER", 403),
    ("GET", "/api/v1/audit-logs", "VET", 403),
    ("GET", "/api/v1/reschedule-requests", "STAFF", 200),
    ("GET", "/api/v1/reschedule-requests", "OWNER", 403),
    ("GET", "/api/v1/reschedule-requests", "VET", 403),
    ("GET", "/api/v1/notifications", "OWNER", 200),
    ("GET", "/api/v1/notifications", "VET", 200),
    ("GET", "/api/v1/notifications", "STAFF", 200),
    ("GET", "/api/v1/vets", "OWNER", 200),
    ("GET", "/api/v1/vets", "VET", 200),
    ("GET", "/api/v1/vets", "STAFF", 200),
]


@pytest.mark.parametrize("method,path,role,expected", CASES)
async def test_rbac_matrix(client, tokens, seeded, method, path, role, expected):
    response = await client.request(method, path, headers=auth(tokens[role]))
    assert response.status_code == expected, f"{method} {path} as {role}: {response.text}"


async def test_schedule_visibility(client, tokens, seeded):
    owner = await client.get(
        "/api/v1/schedule",
        headers=auth(tokens["OWNER"]),
        params={"date": seeded["day"].isoformat()},
    )
    assert owner.status_code == 403

    own = await client.get(
        "/api/v1/schedule",
        headers=auth(tokens["VET"]),
        params={"date": seeded["day"].isoformat(), "vet_id": str(seeded["vet1_id"])},
    )
    assert own.status_code == 200

    other_vet = await client.get(
        "/api/v1/schedule",
        headers=auth(tokens["VET"]),
        params={"date": seeded["day"].isoformat(), "vet_id": str(seeded["vet2_id"])},
    )
    assert other_vet.status_code == 403

    staff = await client.get(
        "/api/v1/schedule",
        headers=auth(tokens["STAFF"]),
        params={"date": seeded["day"].isoformat(), "vet_id": str(seeded["vet2_id"])},
    )
    assert staff.status_code == 200


async def test_shift_endpoints_role_boundaries(client, tokens, seeded):
    day = seeded["day"] + timedelta(days=2)
    payload = {
        "vet_id": str(seeded["vet1_id"]),
        "shift_date": day.isoformat(),
        "start_time": "09:00",
        "end_time": "10:00",
    }
    for role in ("OWNER", "VET"):
        response = await client.post(
            "/api/v1/shifts", headers=auth(tokens[role]), json=payload
        )
        assert response.status_code == 403, role

    created = await client.post(
        "/api/v1/shifts", headers=auth(tokens["STAFF"]), json=payload
    )
    assert created.status_code == 201
    shift_id = created.json()["id"]

    for role in ("OWNER", "VET"):
        response = await client.delete(
            f"/api/v1/shifts/{shift_id}", headers=auth(tokens[role])
        )
        assert response.status_code == 403, role


async def test_staff_account_creation_boundaries(client, tokens):
    for role in ("OWNER", "VET"):
        response = await client.post(
            "/api/v1/auth/staff-accounts",
            headers=auth(tokens[role]),
            json={
                "email": unique_email("blocked"),
                "password": "Password123!",
                "full_name": "ไม่ควรสร้าง",
                "role": "VET",
            },
        )
        assert response.status_code == 403, role


async def test_cross_owner_and_unassigned_vet_cannot_read_appointment(
    client, tokens, seeded
):
    booking = await book(
        client, tokens["OWNER"], pet_id=seeded["pet1_id"],
        vet_id=seeded["vet1_id"], day=seeded["day"], hour=9,
    )
    appointment_id = booking.json()["id"]

    owner = await client.get(
        f"/api/v1/appointments/{appointment_id}", headers=auth(tokens["OWNER"])
    )
    assert owner.status_code == 200

    for role in ("OWNER2", "VET2"):
        response = await client.get(
            f"/api/v1/appointments/{appointment_id}", headers=auth(tokens[role])
        )
        assert response.status_code == 403, role

    staff = await client.get(
        f"/api/v1/appointments/{appointment_id}", headers=auth(tokens["STAFF"])
    )
    assert staff.status_code == 200


async def test_unauthenticated_requests_return_401(client):
    for path in (
        "/api/v1/pets",
        "/api/v1/appointments",
        "/api/v1/notifications",
        "/api/v1/audit-logs",
    ):
        response = await client.get(path)
        assert response.status_code == 401, path

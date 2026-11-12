from __future__ import annotations

from sqlalchemy import select

from app.models import User
from tests.conftest import test_session_factory
from tests.helpers import PASSWORD, auth, book, unique_email


async def test_register_hashes_password_with_argon2id(client):
    email = unique_email("new-owner")
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "StrongPass123!",
            "full_name": "เจ้าของใหม่",
            "phone": "0812345678",
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["role"] == "OWNER"

    async with test_session_factory() as session:
        user = await session.scalar(select(User).where(User.email == email))
        assert user is not None
        assert user.password_hash.startswith("$argon2id$")
        assert "StrongPass123!" not in user.password_hash


async def test_duplicate_email_is_case_insensitive(client):
    email = unique_email("dup")
    first = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": PASSWORD, "full_name": "คนแรก"},
    )
    assert first.status_code == 201
    second = await client.post(
        "/api/v1/auth/register",
        json={"email": email.upper(), "password": PASSWORD, "full_name": "คนที่สอง"},
    )
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "EMAIL_TAKEN"


async def test_login_and_me(client):
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "owner1@test.local", "password": PASSWORD},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    me = await client.get("/api/v1/auth/me", headers=auth(body["access_token"]))
    assert me.status_code == 200
    assert me.json()["role"] == "OWNER"


async def test_wrong_password_and_unknown_email_are_indistinguishable(client):
    wrong_password = await client.post(
        "/api/v1/auth/login",
        json={"email": "owner1@test.local", "password": "WrongPassword1!"},
    )
    unknown_email = await client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@test.local", "password": PASSWORD},
    )
    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json()
    assert wrong_password.json()["error"]["code"] == "INVALID_CREDENTIALS"


async def test_missing_token_returns_401(client):
    response = await client.get("/api/v1/pets")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


async def test_staff_can_list_and_delete_team_account(client, tokens):
    email = unique_email("delete-vet")
    create = await client.post(
        "/api/v1/auth/staff-accounts",
        headers=auth(tokens["STAFF"]),
        json={
            "email": email,
            "password": PASSWORD,
            "full_name": "หมอที่จะถูกลบ",
            "role": "VET",
        },
    )
    assert create.status_code == 201, create.text
    account_id = create.json()["id"]

    listed = await client.get("/api/v1/auth/staff-accounts", headers=auth(tokens["STAFF"]))
    assert listed.status_code == 200, listed.text
    assert any(account["id"] == account_id for account in listed.json())

    deleted = await client.delete(
        f"/api/v1/auth/staff-accounts/{account_id}", headers=auth(tokens["STAFF"])
    )
    assert deleted.status_code == 200, deleted.text

    after = await client.get("/api/v1/auth/staff-accounts", headers=auth(tokens["STAFF"]))
    assert all(account["id"] != account_id for account in after.json())

    login = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": PASSWORD}
    )
    assert login.status_code == 401


async def test_staff_must_resolve_active_vet_appointments_before_delete(
    client, tokens, seeded
):
    cancel_appointment = await book(
        client,
        tokens["OWNER"],
        pet_id=seeded["pet1_id"],
        vet_id=seeded["vet1_id"],
        day=seeded["day"],
        hour=9,
    )
    transfer_appointment = await book(
        client,
        tokens["OWNER"],
        pet_id=seeded["pet1_id"],
        vet_id=seeded["vet1_id"],
        day=seeded["day"],
        hour=9,
        minute=30,
    )
    assert cancel_appointment.status_code == 201, cancel_appointment.text
    assert transfer_appointment.status_code == 201, transfer_appointment.text

    upcoming = await client.get(
        f"/api/v1/auth/staff-accounts/{seeded['vet1_id']}/upcoming-appointments",
        headers=auth(tokens["STAFF"]),
    )
    assert upcoming.status_code == 200, upcoming.text
    assert len(upcoming.json()) == 2

    blocked = await client.delete(
        f"/api/v1/auth/staff-accounts/{seeded['vet1_id']}",
        headers=auth(tokens["STAFF"]),
    )
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "APPOINTMENTS_REQUIRE_RESOLUTION"

    deleted = await client.request(
        "DELETE",
        f"/api/v1/auth/staff-accounts/{seeded['vet1_id']}",
        headers=auth(tokens["STAFF"]),
        json={
            "appointments": [
                {
                    "appointment_id": cancel_appointment.json()["id"],
                    "action": "CANCEL",
                },
                {
                    "appointment_id": transfer_appointment.json()["id"],
                    "action": "TRANSFER",
                    "replacement_vet_id": str(seeded["vet2_id"]),
                },
            ]
        },
    )
    assert deleted.status_code == 200, deleted.text

    cancelled = await client.get(
        f"/api/v1/appointments/{cancel_appointment.json()['id']}",
        headers=auth(tokens["STAFF"]),
    )
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == "CANCELLED"

    transferred = await client.get(
        f"/api/v1/appointments/{transfer_appointment.json()['id']}",
        headers=auth(tokens["STAFF"]),
    )
    assert transferred.status_code == 200, transferred.text
    assert transferred.json()["vet_id"] == str(seeded["vet2_id"])

    vets = await client.get("/api/v1/vets", headers=auth(tokens["OWNER"]))
    assert all(vet["id"] != str(seeded["vet1_id"]) for vet in vets.json())


async def test_staff_cannot_delete_self_or_non_team_account(client, tokens, seeded):
    self_delete = await client.delete(
        f"/api/v1/auth/staff-accounts/{seeded['staff_id']}",
        headers=auth(tokens["STAFF"]),
    )
    assert self_delete.status_code == 409
    assert self_delete.json()["error"]["code"] == "CANNOT_DELETE_SELF"

    owner_delete = await client.delete(
        f"/api/v1/auth/staff-accounts/{seeded['owner1_id']}",
        headers=auth(tokens["STAFF"]),
    )
    assert owner_delete.status_code == 404
    assert owner_delete.json()["error"]["code"] == "ACCOUNT_NOT_FOUND"

    forbidden = await client.get("/api/v1/auth/staff-accounts", headers=auth(tokens["OWNER"]))
    assert forbidden.status_code == 403


async def test_staff_can_create_vet_but_owner_cannot(client, tokens):
    create = await client.post(
        "/api/v1/auth/staff-accounts",
        headers=auth(tokens["STAFF"]),
        json={
            "email": unique_email("new-vet"),
            "password": PASSWORD,
            "full_name": "หมอใหม่",
            "role": "VET",
        },
    )
    assert create.status_code == 201, create.text
    assert create.json()["role"] == "VET"

    forbidden = await client.post(
        "/api/v1/auth/staff-accounts",
        headers=auth(tokens["OWNER"]),
        json={
            "email": unique_email("nope"),
            "password": PASSWORD,
            "full_name": "ไม่ควรสำเร็จ",
            "role": "STAFF",
        },
    )
    assert forbidden.status_code == 403

from __future__ import annotations

from sqlalchemy import select

from app.models import User
from tests.conftest import test_session_factory
from tests.helpers import PASSWORD, auth, unique_email


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

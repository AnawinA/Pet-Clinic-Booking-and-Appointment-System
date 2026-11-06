"""Shared test fixtures.

Tests run against a real PostgreSQL database because the double-booking and
audit guarantees live in DB constraints and triggers, not in Python.
Set TEST_DATABASE_URL to point at a disposable database.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

BACKEND_DIR = Path(__file__).resolve().parents[1]
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://petcare:petcare@localhost:5432/petcare_test",
)
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ.setdefault("JWT_SECRET", "test-secret-key-not-for-production")

from app.db import session as db_session  # noqa: E402
from app.db.session import get_session  # noqa: E402
from app.main import app  # noqa: E402
from app.models import UserRole  # noqa: E402
from tests.helpers import create_pet, create_shift, create_user  # noqa: E402

engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
test_session_factory = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)

# Keep worker/background code using the same disposable test database.
db_session.engine = engine
db_session.SessionLocal = test_session_factory

DB_TABLES = (
    "notifications, outbox_events, audit_logs, treatment_notes, reschedule_requests, "
    "appointments, vet_shifts, pets, users"
)


@pytest_asyncio.fixture(scope="session")
async def db_ready():
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"PostgreSQL test database unavailable ({TEST_DATABASE_URL}): {exc}")

    env = {**os.environ, "DATABASE_URL": TEST_DATABASE_URL}
    subprocess.run(
        [sys.executable, "-m", "alembic", "downgrade", "base"],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
    )
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        pytest.fail(
            "alembic upgrade head failed\nSTDOUT:\n"
            + result.stdout
            + "\nSTDERR:\n"
            + result.stderr
        )
    yield
    await engine.dispose()


@pytest_asyncio.fixture
async def seeded(db_ready):
    async with engine.begin() as connection:
        await connection.execute(text(f"TRUNCATE {DB_TABLES} RESTART IDENTITY CASCADE"))

    async with test_session_factory() as session:
        staff = await create_user(session, "staff@test.local", UserRole.STAFF, "สตาฟทดสอบ")
        vet1 = await create_user(session, "vet1@test.local", UserRole.VET, "หมอหนึ่ง")
        vet2 = await create_user(session, "vet2@test.local", UserRole.VET, "หมอสอง")
        owner1 = await create_user(session, "owner1@test.local", UserRole.OWNER, "เจ้าของหนึ่ง")
        owner2 = await create_user(session, "owner2@test.local", UserRole.OWNER, "เจ้าของสอง")
        pet1 = await create_pet(session, owner1.id, "มะม่วง")
        pet2 = await create_pet(session, owner1.id, "ส้มจี๊ด")
        pet3 = await create_pet(session, owner2.id, "โกโก้")

        from datetime import date, timedelta

        day = date.today() + timedelta(days=1)
        await create_shift(session, vet1.id, staff.id, day)
        await create_shift(session, vet2.id, staff.id, day)
        await session.commit()

        return {
            "staff_id": staff.id,
            "vet1_id": vet1.id,
            "vet2_id": vet2.id,
            "owner1_id": owner1.id,
            "owner2_id": owner2.id,
            "pet1_id": pet1.id,
            "pet2_id": pet2.id,
            "pet3_id": pet3.id,
            "day": day,
        }


@pytest_asyncio.fixture
async def client(seeded):
    async def override_session():
        async with test_session_factory() as session:
            try:
                yield session
            finally:
                await session.close()

    app.dependency_overrides[get_session] = override_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def tokens(client):
    from tests.helpers import PASSWORD

    result: dict[str, str] = {}
    for role, email in (
        ("STAFF", "staff@test.local"),
        ("VET", "vet1@test.local"),
        ("VET2", "vet2@test.local"),
        ("OWNER", "owner1@test.local"),
        ("OWNER2", "owner2@test.local"),
    ):
        response = await client.post(
            "/api/v1/auth/login", json={"email": email, "password": PASSWORD}
        )
        assert response.status_code == 200, response.text
        result[role] = response.json()["access_token"]
    return result

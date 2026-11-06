from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models import Pet, User, UserRole, VetShift

PASSWORD = "Password123!"
BANGKOK = ZoneInfo("Asia/Bangkok")


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def slot(day: date, hour: int = 9, minute: int = 0) -> datetime:
    """Return a UTC datetime representing a Bangkok-local clinic slot."""
    local = datetime.combine(day, time(hour, minute), tzinfo=BANGKOK)
    return local.astimezone(UTC)


def iso_slot(day: date, hour: int = 9, minute: int = 0) -> str:
    return slot(day, hour, minute).isoformat()


async def create_user(
    session: AsyncSession,
    email: str,
    role: UserRole,
    full_name: str | None = None,
) -> User:
    user = User(
        email=email,
        password_hash=hash_password(PASSWORD),
        full_name=full_name or email,
        role=role,
    )
    session.add(user)
    await session.flush()
    return user


async def create_pet(session: AsyncSession, owner_id, name: str = "ทดสอบ") -> Pet:
    pet = Pet(owner_id=owner_id, name=name, species="Dog", breed="Mixed", sex="ผู้")
    session.add(pet)
    await session.flush()
    return pet


async def create_shift(
    session: AsyncSession,
    vet_id,
    created_by,
    day: date,
    start: time = time(9, 0),
    end: time = time(17, 0),
) -> VetShift:
    shift = VetShift(
        vet_id=vet_id,
        shift_date=day,
        start_time=start,
        end_time=end,
        created_by=created_by,
    )
    session.add(shift)
    await session.flush()
    return shift


async def book(
    client,
    token: str,
    *,
    pet_id,
    vet_id,
    day: date,
    hour: int = 9,
    minute: int = 0,
):
    return await client.post(
        "/api/v1/appointments",
        headers=auth(token),
        json={
            "pet_id": str(pet_id),
            "vet_id": str(vet_id),
            "slot_start": iso_slot(day, hour, minute),
            "symptoms": "มีอาการซึมและไม่กินอาหาร",
        },
    )


def unique_email(prefix: str = "user") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10]}@test.local"

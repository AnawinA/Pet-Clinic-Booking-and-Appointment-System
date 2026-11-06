"""Seed demo users, pets and shifts.

Run with:  python -m scripts.seed   (inside the backend container)
"""

from __future__ import annotations

import asyncio
from datetime import date, time, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models import Pet, User, UserRole, VetShift

DEMO_PASSWORD = "Petcare123!"

USERS = [
    ("staff@petcare.local", "สมชาย ผู้ช่วยคลินิก", UserRole.STAFF),
    ("vet1@petcare.local", "นพ.วีรภัทร สุขใจ", UserRole.VET),
    ("vet2@petcare.local", "พญ.ปริญญา ใจดี", UserRole.VET),
    ("owner1@petcare.local", "ณัฐพล ใจรักสัตว์", UserRole.OWNER),
    ("owner2@petcare.local", "มณีรัตน์ รักหมา", UserRole.OWNER),
]

PETS = [
    ("owner1@petcare.local", "มะม่วง", "Dog", "Golden Retriever", "ผู้", 24.5),
    ("owner1@petcare.local", "ส้มจี๊ด", "Cat", "Persian", "เมีย", 4.2),
    ("owner2@petcare.local", "โกโก้", "Dog", "Poodle", "ผู้", 6.8),
]


async def ensure_user(
    session: AsyncSession, email: str, full_name: str, role: UserRole
) -> User:
    user = await session.scalar(select(User).where(User.email == email))
    if user is not None:
        return user
    user = User(
        email=email,
        password_hash=hash_password(DEMO_PASSWORD),
        full_name=full_name,
        phone="0812345678",
        role=role,
    )
    session.add(user)
    await session.flush()
    return user


async def main() -> None:
    async with SessionLocal() as session:
        staff = await ensure_user(session, *USERS[0])
        vets: list[User] = []
        for email, name, role in USERS[1:3]:
            vets.append(await ensure_user(session, email, name, role))
        owners: dict[str, User] = {}
        for email, name, role in USERS[3:]:
            owners[email] = await ensure_user(session, email, name, role)

        for owner_email, pet_name, species, breed, sex, weight in PETS:
            owner = owners[owner_email]
            exists = await session.scalar(
                select(Pet.id).where(Pet.owner_id == owner.id, Pet.name == pet_name)
            )
            if exists is None:
                session.add(
                    Pet(
                        owner_id=owner.id,
                        name=pet_name,
                        species=species,
                        breed=breed,
                        sex=sex,
                        weight_kg=weight,
                        medical_notes="ไม่มีประวัติแพ้ยา",
                    )
                )

        today = date.today()
        for vet in vets:
            for offset in range(0, 7):
                shift_day = today + timedelta(days=offset)
                exists = await session.scalar(
                    select(VetShift.id).where(
                        VetShift.vet_id == vet.id, VetShift.shift_date == shift_day
                    )
                )
                if exists is None:
                    session.add(
                        VetShift(
                            vet_id=vet.id,
                            shift_date=shift_day,
                            start_time=time(9, 0),
                            end_time=time(17, 0),
                            created_by=staff.id,
                        )
                    )

        await session.commit()

    print("Seed completed. Demo accounts (password: %s):" % DEMO_PASSWORD)
    for email, name, role in USERS:
        print(f"  {role.value:<5} {email:<24} {name}")


if __name__ == "__main__":
    asyncio.run(main())

"""Create the first STAFF or VET account (bootstrap tool).

Example:
    python -m scripts.create_staff --email admin@clinic.local \
        --password 'ChangeMe123!' --full-name 'ผู้จัดการคลินิก' --role STAFF
"""

from __future__ import annotations

import argparse
import asyncio

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models import User, UserRole


async def create(email: str, password: str, full_name: str, role: UserRole) -> None:
    async with SessionLocal() as session:
        existing = await session.scalar(select(User.id).where(User.email == email))
        if existing is not None:
            raise SystemExit(f"email already exists: {email}")
        user = User(
            email=email.lower(),
            password_hash=hash_password(password),
            full_name=full_name,
            role=role,
        )
        session.add(user)
        await session.commit()
        print(f"created {role.value} account: {user.email} ({user.id})")


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a STAFF/VET account")
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--full-name", required=True)
    parser.add_argument("--role", choices=["STAFF", "VET"], default="STAFF")
    args = parser.parse_args()
    if len(args.password) < 8:
        raise SystemExit("password must be at least 8 characters")
    asyncio.run(
        create(args.email, args.password, args.full_name, UserRole(args.role))
    )


if __name__ == "__main__":
    main()

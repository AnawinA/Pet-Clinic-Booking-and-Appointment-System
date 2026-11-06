"""Authentication and account creation (FR-01..03, US-7, 16, 17)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_roles
from app.core.errors import conflict, unauthorized
from app.core.security import create_access_token, hash_password, verify_password
from app.db.session import get_session
from app.models import User, UserRole
from app.schemas import (
    LoginRequest,
    RegisterRequest,
    StaffAccountRequest,
    TokenResponse,
    UserOut,
)
from app.services.audit_service import write_audit

router = APIRouter(prefix="/auth", tags=["auth"])

INVALID_CREDENTIALS = "อีเมลหรือรหัสผ่านไม่ถูกต้อง"


async def _create_user(
    session: AsyncSession,
    *,
    email: str,
    password: str,
    full_name: str,
    phone: str | None,
    role: UserRole,
    actor: User | None,
    request_id: str | None,
) -> User:
    existing = await session.scalar(select(User.id).where(User.email == email))
    if existing is not None:
        raise conflict("EMAIL_TAKEN", "อีเมลนี้ถูกใช้งานแล้ว")

    user = User(
        email=email.lower(),
        password_hash=hash_password(password),
        full_name=full_name,
        phone=phone,
        role=role,
    )
    try:
        async with session.begin_nested():
            session.add(user)
            await session.flush()
    except IntegrityError as exc:
        raise conflict("EMAIL_TAKEN", "อีเมลนี้ถูกใช้งานแล้ว") from exc

    await write_audit(
        session,
        actor=actor,
        entity_type="USER",
        entity_id=user.id,
        action="USER_CREATED" if actor else "USER_REGISTERED",
        after={"email": user.email, "role": user.role.value},
        request_id=request_id,
    )
    await session.commit()
    return user


@router.post("/register", response_model=UserOut, status_code=201)
async def register(
    payload: RegisterRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> User:
    return await _create_user(
        session,
        email=payload.email,
        password=payload.password,
        full_name=payload.full_name,
        phone=payload.phone,
        role=UserRole.OWNER,
        actor=None,
        request_id=getattr(request.state, "request_id", None),
    )


@router.post("/staff-accounts", response_model=UserOut, status_code=201)
async def create_staff_account(
    payload: StaffAccountRequest,
    request: Request,
    actor: User = Depends(require_roles(UserRole.STAFF)),
    session: AsyncSession = Depends(get_session),
) -> User:
    return await _create_user(
        session,
        email=payload.email,
        password=payload.password,
        full_name=payload.full_name,
        phone=payload.phone,
        role=UserRole(payload.role),
        actor=actor,
        request_id=getattr(request.state, "request_id", None),
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    user = await session.scalar(select(User).where(User.email == payload.email))
    if user is None:
        # Identical response for unknown email and wrong password.
        raise unauthorized("INVALID_CREDENTIALS", INVALID_CREDENTIALS)
    if not user.is_active or not verify_password(payload.password, user.password_hash):
        raise unauthorized("INVALID_CREDENTIALS", INVALID_CREDENTIALS)

    token, expires_at = create_access_token(user_id=user.id, role=user.role.value)
    return TokenResponse(
        access_token=token,
        expires_at=expires_at,
        user=UserOut(
            id=user.id,
            email=str(user.email),
            full_name=user.full_name,
            phone=user.phone,
            role=user.role.value,
            is_active=user.is_active,
            created_at=user.created_at,
        ),
    )


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)) -> User:
    return user

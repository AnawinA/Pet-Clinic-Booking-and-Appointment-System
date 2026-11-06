"""Shared FastAPI dependencies for authentication and RBAC."""

from __future__ import annotations

import uuid
from collections.abc import Callable

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import forbidden, unauthorized
from app.core.security import decode_access_token
from app.db.session import get_session
from app.models import User, UserRole

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_session),
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise unauthorized()
    payload = decode_access_token(credentials.credentials)
    subject = payload.get("sub")
    try:
        user_id = uuid.UUID(str(subject))
    except (ValueError, TypeError) as exc:
        raise unauthorized("INVALID_TOKEN", "token ไม่ถูกต้อง") from exc

    user = await session.get(User, user_id)
    if user is None or not user.is_active:
        raise unauthorized("INVALID_TOKEN", "token ไม่ถูกต้อง")
    return user


def require_roles(*roles: UserRole) -> Callable[..., object]:
    async def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise forbidden("บทบาทของคุณไม่มีสิทธิ์ใช้งานส่วนนี้")
        return user

    return dependency


def require_owner(user: User = Depends(get_current_user)) -> User:
    if user.role != UserRole.OWNER:
        raise forbidden("เฉพาะเจ้าของสัตว์เลี้ยงเท่านั้น")
    return user

"""Authentication and account creation (FR-01..03, US-7, 16, 17)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_roles
from app.core.errors import bad_request, conflict, not_found, unauthorized
from app.core.security import create_access_token, hash_password, verify_password
from app.core.time import now_utc, to_local
from app.db.session import get_session
from app.models import (
    ACTIVE_STATUSES,
    Appointment,
    AppointmentStatus,
    User,
    UserRole,
    VetShift,
)
from app.schemas import (
    DeleteStaffAccountRequest,
    LoginRequest,
    MessageOut,
    RegisterRequest,
    StaffAccountRequest,
    StaffUpcomingAppointmentOut,
    TokenResponse,
    UserOut,
)
from app.services.audit_service import write_audit
from app.services.common import (
    appointment_names,
    appointment_snapshot,
    find_covering_shift,
    get_vet,
)
from app.services.outbox_service import (
    EVENT_STATUS_CHANGED,
    EVENT_TRANSFERRED,
    appointment_payload,
    enqueue,
)

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


@router.get("/staff-accounts", response_model=list[UserOut])
async def list_staff_accounts(
    _: User = Depends(require_roles(UserRole.STAFF)),
    session: AsyncSession = Depends(get_session),
) -> list[User]:
    users = await session.scalars(
        select(User)
        .where(
            User.role.in_((UserRole.VET, UserRole.STAFF)),
            User.is_active.is_(True),
        )
        .order_by(User.full_name, User.email)
    )
    return list(users)


async def _active_vet_appointments(
    session: AsyncSession, vet_id: UUID, *, lock: bool = False
) -> list[Appointment]:
    stmt = (
        select(Appointment)
        .where(
            Appointment.vet_id == vet_id,
            Appointment.status.in_(ACTIVE_STATUSES),
            Appointment.slot_end >= now_utc(),
        )
        .order_by(Appointment.slot_start)
    )
    if lock:
        stmt = stmt.with_for_update()
    return list((await session.scalars(stmt)).all())


async def _resolve_vet_appointments(
    session: AsyncSession,
    *,
    actor: User,
    vet: User,
    appointments: list[Appointment],
    payload: DeleteStaffAccountRequest | None,
    request_id: str | None,
) -> tuple[int, int]:
    resolutions = payload.appointments if payload else []
    by_id = {resolution.appointment_id: resolution for resolution in resolutions}
    if len(by_id) != len(resolutions):
        raise bad_request(
            "DUPLICATE_APPOINTMENT_RESOLUTION", "มีรายการจัดการนัดหมายซ้ำกัน"
        )

    expected_ids = {appointment.id for appointment in appointments}
    if set(by_id) != expected_ids:
        missing_ids = expected_ids - set(by_id)
        if missing_ids:
            details = []
            for appointment in appointments:
                if appointment.id not in missing_ids:
                    continue
                pet_name, _, owner_name = await appointment_names(session, appointment)
                details.append(
                    {
                        "appointment_id": str(appointment.id),
                        "owner_name": owner_name,
                        "pet_name": pet_name,
                        "slot_start": appointment.slot_start.isoformat(),
                    }
                )
            raise conflict(
                "APPOINTMENTS_REQUIRE_RESOLUTION",
                "กรุณาเลือกยกเลิกหรือโอนนัดหมายที่ยังไม่สิ้นสุดให้ครบทุกรายการ",
                {"appointments": details},
            )
        raise bad_request(
            "INVALID_APPOINTMENT_RESOLUTION",
            "มีรายการจัดการนัดหมายที่ไม่เกี่ยวข้องกับบัญชีนี้",
        )

    plan: list[tuple[Appointment, str, User | None, VetShift | None]] = []
    replacement_vets: dict[UUID, User] = {}
    for appointment in appointments:
        resolution = by_id[appointment.id]
        if resolution.action == "CANCEL":
            plan.append((appointment, "CANCEL", None, None))
            continue

        if resolution.replacement_vet_id is None:
            raise bad_request(
                "REPLACEMENT_VET_REQUIRED", "กรุณาเลือกสัตวแพทย์ปลายทางสำหรับการโอนนัด"
            )
        if resolution.replacement_vet_id == vet.id:
            raise bad_request(
                "TRANSFER_SAME_VET", "ไม่สามารถโอนนัดไปยังสัตวแพทย์ที่กำลังลบบัญชีได้"
            )

        replacement = replacement_vets.get(resolution.replacement_vet_id)
        if replacement is None:
            replacement = await get_vet(session, resolution.replacement_vet_id)
            replacement_vets[replacement.id] = replacement

        local_start = to_local(appointment.slot_start)
        local_end = to_local(appointment.slot_end)
        shift = await find_covering_shift(
            session,
            vet_id=replacement.id,
            day=local_start.date(),
            start=local_start.time(),
            end=local_end.time(),
            lock=True,
        )
        if shift is None:
            raise conflict(
                "TRANSFER_NOT_POSSIBLE",
                f"{replacement.full_name} ไม่มีกะครอบเวลานัดนี้",
                {"appointment_id": str(appointment.id)},
            )

        taken = await session.scalar(
            select(Appointment.id).where(
                Appointment.vet_id == replacement.id,
                Appointment.slot_start == appointment.slot_start,
                Appointment.status != AppointmentStatus.CANCELLED,
                Appointment.id != appointment.id,
            )
        )
        if taken is not None:
            raise conflict(
                "SLOT_TAKEN",
                f"{replacement.full_name} มีนัดในช่วงเวลานี้แล้ว",
                {"appointment_id": str(appointment.id)},
            )

        plan.append((appointment, "TRANSFER", replacement, shift))

    cancelled = 0
    transferred = 0
    for appointment, action, replacement, shift in plan:
        before = appointment_snapshot(appointment)
        if action == "CANCEL":
            appointment.status = AppointmentStatus.CANCELLED
            appointment.cancelled_at = now_utc()
            appointment.cancel_reason = "ลบบัญชีสัตวแพทย์"
            appointment.version += 1
            appointment.updated_at = now_utc()
            pet_name, vet_name, owner_name = await appointment_names(session, appointment)
            await write_audit(
                session,
                actor=actor,
                entity_type="APPOINTMENT",
                entity_id=appointment.id,
                action="STATUS_CHANGE",
                before=before,
                after=appointment_snapshot(appointment),
                request_id=request_id,
            )
            await enqueue(
                session,
                event_type=EVENT_STATUS_CHANGED,
                aggregate_id=appointment.id,
                payload=appointment_payload(
                    appointment,
                    pet_name=pet_name,
                    vet_name=vet_name,
                    owner_name=owner_name,
                    reason="ลบบัญชีสัตวแพทย์",
                ),
                recipient_ids=[appointment.owner_id, appointment.vet_id],
            )
            cancelled += 1
            continue

        assert replacement is not None and shift is not None
        appointment.vet_id = replacement.id
        appointment.shift_id = shift.id
        appointment.version += 1
        appointment.updated_at = now_utc()
        pet_name, new_vet_name, owner_name = await appointment_names(session, appointment)
        after = appointment_snapshot(appointment)
        after["previous_vet_id"] = str(vet.id)
        await write_audit(
            session,
            actor=actor,
            entity_type="APPOINTMENT",
            entity_id=appointment.id,
            action="TRANSFER",
            before=before,
            after=after,
            request_id=request_id,
        )
        await enqueue(
            session,
            event_type=EVENT_TRANSFERRED,
            aggregate_id=appointment.id,
            payload=appointment_payload(
                appointment,
                pet_name=pet_name,
                vet_name=new_vet_name,
                owner_name=owner_name,
                reason="ลบบัญชีสัตวแพทย์",
                previous_vet_name=vet.full_name,
            ),
            recipient_ids=[appointment.owner_id, replacement.id, vet.id],
        )
        transferred += 1

    return cancelled, transferred


@router.get(
    "/staff-accounts/{user_id}/upcoming-appointments",
    response_model=list[StaffUpcomingAppointmentOut],
)
async def list_staff_account_upcoming_appointments(
    user_id: UUID,
    _: User = Depends(require_roles(UserRole.STAFF)),
    session: AsyncSession = Depends(get_session),
) -> list[StaffUpcomingAppointmentOut]:
    target = await session.get(User, user_id)
    if target is None or target.role != UserRole.VET or not target.is_active:
        raise not_found("ACCOUNT_NOT_FOUND", "ไม่พบบัญชี VET ที่ต้องการตรวจสอบ")

    appointments = await _active_vet_appointments(session, target.id)
    result: list[StaffUpcomingAppointmentOut] = []
    for appointment in appointments:
        pet_name, _vet_name, owner_name = await appointment_names(session, appointment)
        result.append(
            StaffUpcomingAppointmentOut(
                appointment_id=appointment.id,
                owner_id=appointment.owner_id,
                owner_name=owner_name,
                pet_id=appointment.pet_id,
                pet_name=pet_name,
                slot_start=appointment.slot_start,
                slot_end=appointment.slot_end,
                status=appointment.status.value,
            )
        )
    return result


@router.delete("/staff-accounts/{user_id}", response_model=MessageOut)
async def delete_staff_account(
    user_id: UUID,
    request: Request,
    payload: DeleteStaffAccountRequest | None = None,
    actor: User = Depends(require_roles(UserRole.STAFF)),
    session: AsyncSession = Depends(get_session),
) -> MessageOut:
    target = await session.get(User, user_id)
    if (
        target is None
        or target.role not in (UserRole.VET, UserRole.STAFF)
        or not target.is_active
    ):
        raise not_found("ACCOUNT_NOT_FOUND", "ไม่พบบัญชี VET/STAFF ที่ต้องการลบ")

    if target.id == actor.id:
        raise conflict("CANNOT_DELETE_SELF", "ไม่สามารถลบบัญชีของตัวเองได้")

    if target.role == UserRole.STAFF:
        if payload and payload.appointments:
            raise bad_request(
                "INVALID_APPOINTMENT_RESOLUTION",
                "บัญชี STAFF ไม่มีนัดหมายที่ต้องจัดการ",
            )
        remaining_staff = await session.scalar(
            select(func.count(User.id)).where(
                User.role == UserRole.STAFF,
                User.is_active.is_(True),
                User.id != target.id,
            )
        )
        if not remaining_staff:
            raise conflict("LAST_STAFF_ACCOUNT", "ต้องมีบัญชี STAFF อย่างน้อย 1 บัญชี")

    cancelled = 0
    transferred = 0
    request_id = getattr(request.state, "request_id", None)
    before = {
        "email": target.email,
        "role": target.role.value,
        "is_active": target.is_active,
    }
    try:
        if target.role == UserRole.VET:
            appointments = await _active_vet_appointments(session, target.id, lock=True)
            cancelled, transferred = await _resolve_vet_appointments(
                session,
                actor=actor,
                vet=target,
                appointments=appointments,
                payload=payload,
                request_id=request_id,
            )

        target.is_active = False
        await write_audit(
            session,
            actor=actor,
            entity_type="USER",
            entity_id=target.id,
            action="USER_DEACTIVATED",
            before=before,
            after={
                **before,
                "is_active": False,
                "appointments_cancelled": cancelled,
                "appointments_transferred": transferred,
            },
            request_id=request_id,
        )
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise conflict(
            "SLOT_TAKEN", "ไม่สามารถโอนนัดได้เนื่องจากช่วงเวลาของสัตวแพทย์ปลายทางไม่ว่าง"
        ) from exc

    message = f"ลบบัญชี {target.email} แล้ว"
    if cancelled or transferred:
        message += f" (ยกเลิก {cancelled} นัด, โอน {transferred} นัด)"
    return MessageOut(message=message)


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

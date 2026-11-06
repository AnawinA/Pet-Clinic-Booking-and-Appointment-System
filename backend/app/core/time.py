"""Time helpers. All storage is UTC (timestamptz); clinic times are Asia/Bangkok."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.core.config import settings
from app.core.errors import bad_request

UTC = UTC
BANGKOK = ZoneInfo(settings.app_tz)
SLOT_MINUTES = 30
OPEN_TIME = time(9, 0)
LAST_SLOT_START = time(16, 30)
CLOSE_TIME = time(17, 0)


def now_utc() -> datetime:
    return datetime.now(tz=UTC)


def to_local(value: datetime) -> datetime:
    return value.astimezone(BANGKOK)


def local_day_bounds(day: date) -> tuple[datetime, datetime]:
    start = datetime.combine(day, time.min, tzinfo=BANGKOK)
    return start.astimezone(UTC), (start + timedelta(days=1)).astimezone(UTC)


def local_slot_to_utc(day: date, start: time) -> datetime:
    return datetime.combine(day, start, tzinfo=BANGKOK).astimezone(UTC)


def slot_out_of_range(message: str = "สล็อตไม่อยู่ในช่วงเวลาที่ให้บริการ") -> Exception:
    return bad_request("SLOT_OUT_OF_RANGE", message)


def validate_slot(slot_start: datetime) -> tuple[datetime, datetime]:
    """Validate the 30-minute slot rules from masterplan section 4.2."""
    if slot_start.tzinfo is None:
        raise slot_out_of_range("slot_start ต้องระบุเขตเวลา")

    slot_start = slot_start.astimezone(UTC)
    local = slot_start.astimezone(BANGKOK)

    if local.second != 0 or local.microsecond != 0 or local.minute not in (0, 30):
        raise slot_out_of_range("สล็อตต้องเริ่มที่เวลา 00 หรือ 30 นาที")
    if local.time() < OPEN_TIME or local.time() > LAST_SLOT_START:
        raise slot_out_of_range("สล็อตต้องอยู่ระหว่าง 09:00–17:00 (สล็อตสุดท้ายเริ่ม 16:30)")

    slot_end = slot_start + timedelta(minutes=SLOT_MINUTES)
    now = now_utc()
    if slot_start <= now:
        raise slot_out_of_range("ไม่สามารถจองสล็อตในอดีตได้")
    if slot_start > now + timedelta(days=settings.booking_horizon_days):
        raise slot_out_of_range("จองล่วงหน้าได้ไม่เกิน 30 วัน")

    return slot_start, slot_end


def ensure_in_future(slot_start: datetime) -> None:
    if slot_start <= now_utc():
        raise slot_out_of_range("ไม่สามารถจองสล็อตในอดีตได้")

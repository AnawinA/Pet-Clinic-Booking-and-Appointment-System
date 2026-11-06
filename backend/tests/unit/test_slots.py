from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.core.errors import AppError
from app.core.time import validate_slot

BANGKOK = ZoneInfo("Asia/Bangkok")


def bkk_slot(day: date, hour: int, minute: int = 0) -> datetime:
    return datetime.combine(day, time(hour, minute), tzinfo=BANGKOK).astimezone(UTC)


def test_accepts_valid_business_hours_slot():
    day = date.today() + timedelta(days=1)
    start, end = validate_slot(bkk_slot(day, 9, 0))
    assert end - start == timedelta(minutes=30)


def test_accepts_last_slot_of_day():
    day = date.today() + timedelta(days=1)
    start, end = validate_slot(bkk_slot(day, 16, 30))
    assert start < end


@pytest.mark.parametrize("hour,minute", [(8, 30), (17, 0), (16, 45), (12, 15)])
def test_rejects_out_of_window_or_misaligned_slots(hour: int, minute: int):
    day = date.today() + timedelta(days=1)
    with pytest.raises(AppError) as exc:
        validate_slot(bkk_slot(day, hour, minute))
    assert exc.value.code == "SLOT_OUT_OF_RANGE"


def test_rejects_past_slot():
    day = date.today() - timedelta(days=1)
    with pytest.raises(AppError) as exc:
        validate_slot(bkk_slot(day, 10, 0))
    assert exc.value.code == "SLOT_OUT_OF_RANGE"


def test_rejects_beyond_thirty_days():
    day = date.today() + timedelta(days=31)
    with pytest.raises(AppError) as exc:
        validate_slot(bkk_slot(day, 10, 0))
    assert exc.value.code == "SLOT_OUT_OF_RANGE"


def test_rejects_naive_datetime():
    with pytest.raises(AppError):
        validate_slot(datetime(2030, 1, 1, 9, 0))


def test_rejects_seconds_precision():
    day = date.today() + timedelta(days=1)
    value = datetime.combine(day, time(9, 0, 30), tzinfo=BANGKOK).astimezone(UTC)
    with pytest.raises(AppError):
        validate_slot(value)

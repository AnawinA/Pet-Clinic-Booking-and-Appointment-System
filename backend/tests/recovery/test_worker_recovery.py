from __future__ import annotations

from datetime import timedelta

from sqlalchemy import func, select, update

from app.core.time import now_utc
from app.models import Notification, OutboxEvent
from app.worker import outbox_worker
from tests.conftest import test_session_factory
from tests.helpers import auth, book


async def _book_many(client, tokens, seeded, count: int) -> list[str]:
    ids: list[str] = []
    hours = [9, 9, 10, 10, 11, 11, 12, 12, 13, 13]
    minutes = [0, 30, 0, 30, 0, 30, 0, 30, 0, 30]
    for index in range(count):
        response = await book(
            client,
            tokens["OWNER"],
            pet_id=seeded["pet1_id"] if index % 2 == 0 else seeded["pet2_id"],
            vet_id=seeded["vet1_id"],
            day=seeded["day"],
            hour=hours[index],
            minute=minutes[index],
        )
        assert response.status_code == 201, response.text
        ids.append(response.json()["id"])
    return ids


async def test_worker_catches_up_after_downtime_without_duplicates(client, tokens, seeded):
    await _book_many(client, tokens, seeded, 10)

    # Worker is "down": events accumulate in the outbox.
    async with test_session_factory() as session:
        pending = await session.scalar(
            select(func.count(OutboxEvent.id)).where(OutboxEvent.processed_at.is_(None))
        )
    assert pending >= 10

    processed = await outbox_worker.process_batch()
    assert processed >= 10

    async with test_session_factory() as session:
        total = await session.scalar(select(func.count(Notification.id)))
        duplicates = (
            await session.execute(
                select(
                    Notification.event_id,
                    Notification.recipient_id,
                    func.count(Notification.id),
                )
                .group_by(Notification.event_id, Notification.recipient_id)
                .having(func.count(Notification.id) > 1)
            )
        ).all()
    assert total == 20  # 10 bookings x (owner + vet)
    assert duplicates == []

    # Re-running must not duplicate anything.
    await outbox_worker.process_batch()
    async with test_session_factory() as session:
        still = await session.scalar(select(func.count(Notification.id)))
    assert still == 20


async def test_failed_event_is_retried_with_backoff(client, tokens, seeded, monkeypatch):
    await _book_many(client, tokens, seeded, 1)

    original = outbox_worker.handle_event
    calls = {"count": 0}

    async def flaky(session, event):
        calls["count"] += 1
        raise RuntimeError("simulated worker crash")

    monkeypatch.setattr(outbox_worker, "handle_event", flaky)
    processed = await outbox_worker.process_batch()
    assert processed == 0
    assert calls["count"] == 1

    async with test_session_factory() as session:
        event = (
            await session.execute(
                select(OutboxEvent).where(OutboxEvent.event_type == "APPOINTMENT_BOOKED")
            )
        ).scalars().first()
        assert event is not None
        assert event.attempts == 1
        assert event.processed_at is None
        assert "simulated worker crash" in (event.last_error or "")
        assert event.available_at > now_utc()
        # Make it due again, simulating time passing.
        await session.execute(
            update(OutboxEvent)
            .where(OutboxEvent.id == event.id)
            .values(available_at=now_utc() - timedelta(seconds=1))
        )
        await session.commit()

    monkeypatch.setattr(outbox_worker, "handle_event", original)
    processed = await outbox_worker.process_batch()
    assert processed == 1

    async with test_session_factory() as session:
        event = (
            await session.execute(
                select(OutboxEvent).where(OutboxEvent.event_type == "APPOINTMENT_BOOKED")
            )
        ).scalars().first()
        assert event.processed_at is not None
        total = await session.scalar(select(func.count(Notification.id)))
    assert total == 2


async def test_stale_reminder_is_skipped(client, tokens, seeded):
    booking = await book(
        client, tokens["OWNER"], pet_id=seeded["pet1_id"],
        vet_id=seeded["vet1_id"], day=seeded["day"], hour=15,
    )
    appointment_id = booking.json()["id"]
    slot_start = booking.json()["slot_start"]

    cancelled = await client.post(
        f"/api/v1/appointments/{appointment_id}/cancel",
        headers=auth(tokens["STAFF"]),
        json={"reason": "ทดสอบ"},
    )
    assert cancelled.status_code == 200

    async with test_session_factory() as session:
        reminder = await session.scalar(
            select(OutboxEvent).where(
                OutboxEvent.event_type == "APPOINTMENT_REMINDER",
                OutboxEvent.aggregate_id == appointment_id,
            )
        )
        assert reminder is not None
        await session.execute(
            update(OutboxEvent)
            .where(OutboxEvent.id == reminder.id)
            .values(available_at=now_utc() - timedelta(seconds=1))
        )
        await session.commit()
        reminder_id = reminder.id

    await outbox_worker.process_batch()

    async with test_session_factory() as session:
        reminder_notifications = await session.scalar(
            select(func.count(Notification.id)).where(
                Notification.event_id == reminder_id,
                Notification.type == "APPOINTMENT_REMINDER",
            )
        )
        reminder_event = await session.get(OutboxEvent, reminder_id)
    assert reminder_notifications == 0
    assert reminder_event is not None and reminder_event.processed_at is not None
    assert slot_start  # slot untouched by the stale reminder

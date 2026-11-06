"""Transactional outbox worker (NFR-02, NFR-04).

Guarantees at-least-once delivery into ``notifications``; the unique
(event_id, recipient_id) constraint plus ON CONFLICT DO NOTHING makes it
effectively exactly-once, durable across worker restarts.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
import uuid
from datetime import timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.config import settings
from app.core.time import now_utc
from app.db.session import SessionLocal
from app.models import Appointment, Notification, OutboxEvent
from app.worker.messages import build_message
from app.worker.reminder_scheduler import reminder_is_relevant

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("petcare.worker")

HEARTBEAT_FILE = Path(os.getenv("HEARTBEAT_FILE", settings.heartbeat_file))


def touch_heartbeat() -> None:
    try:
        HEARTBEAT_FILE.parent.mkdir(parents=True, exist_ok=True)
        HEARTBEAT_FILE.write_text(str(time.time()), encoding="utf-8")
    except OSError:
        logger.warning("cannot write heartbeat file %s", HEARTBEAT_FILE)


async def handle_event(session, event: OutboxEvent) -> None:
    payload = dict(event.payload or {})
    if event.event_type == "APPOINTMENT_REMINDER":
        appt = await session.get(Appointment, event.aggregate_id)
        if not reminder_is_relevant(appt, payload):
            logger.info("skip stale reminder event=%s", event.id)
            return

    recipients: list[uuid.UUID] = []
    for raw in payload.get("recipient_ids", []):
        try:
            recipients.append(uuid.UUID(str(raw)))
        except ValueError:
            continue
    if not recipients:
        return

    title, message = build_message(event.event_type, payload)
    values = [
        {
            "event_id": event.id,
            "recipient_id": recipient_id,
            "type": event.event_type,
            "title": title,
            "message": message,
        }
        for recipient_id in recipients
    ]
    await session.execute(
        pg_insert(Notification)
        .values(values)
        .on_conflict_do_nothing(index_elements=["event_id", "recipient_id"])
    )


async def process_batch(*, limit: int | None = None) -> int:
    """Drain one batch. Safe to call concurrently from multiple workers."""
    processed = 0
    async with SessionLocal() as session:
        async with session.begin():
            events = (
                (
                    await session.execute(
                        select(OutboxEvent)
                        .where(
                            OutboxEvent.processed_at.is_(None),
                            OutboxEvent.available_at <= now_utc(),
                        )
                        .order_by(OutboxEvent.created_at)
                        .limit(limit or settings.outbox_batch_size)
                        .with_for_update(skip_locked=True)
                    )
                )
                .scalars()
                .all()
            )

            for event in events:
                attempts = event.attempts
                try:
                    async with session.begin_nested():
                        await handle_event(session, event)
                        event.processed_at = now_utc()
                        event.last_error = None
                    processed += 1
                except Exception as exc:  # noqa: BLE001 - record and retry
                    logger.exception(
                        "outbox event failed id=%s type=%s",
                        event.id,
                        event.event_type,
                    )
                    event.attempts = attempts + 1
                    event.last_error = str(exc)[:1000]
                    if event.attempts >= settings.outbox_max_attempts:
                        event.processed_at = now_utc()
                        logger.error("outbox event dead-lettered id=%s", event.id)
                    else:
                        backoff = min(300, 5 * (2 ** min(event.attempts, 5)))
                        event.available_at = now_utc() + timedelta(seconds=backoff)
    return processed


async def run_forever() -> None:
    logger.info("outbox worker started instance=%s", settings.instance_id)
    touch_heartbeat()
    while True:
        try:
            processed = await process_batch()
        except Exception:  # noqa: BLE001 - keep the worker alive
            logger.exception("outbox batch failed")
            processed = 0
        touch_heartbeat()
        await asyncio.sleep(1 if processed else settings.worker_poll_seconds)


def main() -> None:
    try:
        asyncio.run(run_forever())
    except KeyboardInterrupt:
        logger.info("outbox worker stopped")


if __name__ == "__main__":
    main()

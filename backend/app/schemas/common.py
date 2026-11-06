from __future__ import annotations

from datetime import datetime

from app.schemas import ApiModel


class ErrorBody(ApiModel):
    code: str
    message: str
    details: dict = {}


class ErrorEnvelope(ApiModel):
    error: ErrorBody


class HealthOut(ApiModel):
    status: str
    instance_id: str
    checks: dict = {}


class QueueResponse(ApiModel):
    items: list[dict]
    server_time: datetime
    etag: str | None = None

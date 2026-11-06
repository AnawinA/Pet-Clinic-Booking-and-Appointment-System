"""HTTP helpers: request ids, ETags and 304 handling."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from fastapi import Request, Response

_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


def build_etag(values: list[datetime], extra: str = "") -> str:
    latest = max(values) if values else _EPOCH
    raw = f"{latest.timestamp():.6f}:{len(values)}:{extra}"
    digest = hashlib.sha1(raw.encode()).hexdigest()[:16]
    return f'W/"{digest}"'


def not_modified(request: Request, etag: str, response: Response) -> Response | None:
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers={"ETag": etag})
    response.headers["ETag"] = etag
    return None

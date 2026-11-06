"""Fire N concurrent booking requests at one slot (Phase 12 concurrency test).

Example (through nginx):
    python -m scripts.concurrency_check --base-url http://localhost \
        --token "$TOKEN" --pet-id ... --vet-id ... --slot-start 2026-...Z
"""

from __future__ import annotations

import argparse
import asyncio
from collections import Counter

import httpx


async def attempt(client: httpx.AsyncClient, url: str, token: str, body: dict) -> int:
    response = await client.post(
        url,
        json=body,
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    return response.status_code


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost")
    parser.add_argument("--token", required=True)
    parser.add_argument("--pet-id", required=True)
    parser.add_argument("--vet-id", required=True)
    parser.add_argument("--slot-start", required=True)
    parser.add_argument("--requests", type=int, default=20)
    args = parser.parse_args()

    body = {
        "pet_id": args.pet_id,
        "vet_id": args.vet_id,
        "slot_start": args.slot_start,
        "symptoms": "ทดสอบการจองพร้อมกัน",
    }
    url = f"{args.base_url.rstrip('/')}/api/v1/appointments"
    async with httpx.AsyncClient() as client:
        results = await asyncio.gather(
            *(attempt(client, url, args.token, body) for _ in range(args.requests))
        )

    counts = Counter(results)
    print("status counts:", dict(counts))
    assert counts[201] == 1, f"expected exactly one 201, got {counts}"
    assert counts[409] == args.requests - 1, f"expected {args.requests - 1} conflicts"
    print("PASS: exactly one booking succeeded")


if __name__ == "__main__":
    asyncio.run(main())

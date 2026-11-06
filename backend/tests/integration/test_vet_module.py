from __future__ import annotations

from datetime import datetime

from tests.helpers import auth, book, slot


async def _appointment(client, tokens, seeded, hour=11):
    response = await book(
        client, tokens["OWNER"], pet_id=seeded["pet1_id"],
        vet_id=seeded["vet1_id"], day=seeded["day"], hour=hour,
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_vet_a_cannot_view_vet_b_case(client, tokens, seeded):
    appointment = await _appointment(client, tokens, seeded)

    own = await client.get(
        f"/api/v1/appointments/{appointment['id']}", headers=auth(tokens["VET"])
    )
    assert own.status_code == 200

    other = await client.get(
        f"/api/v1/appointments/{appointment['id']}", headers=auth(tokens["VET2"])
    )
    assert other.status_code == 403

    staff = await client.get(
        f"/api/v1/appointments/{appointment['id']}", headers=auth(tokens["STAFF"])
    )
    assert staff.status_code == 200


async def test_treatment_notes_are_versioned(client, tokens, seeded):
    appointment = await _appointment(client, tokens, seeded, hour=9)

    denied = await client.post(
        f"/api/v1/appointments/{appointment['id']}/treatment-notes",
        headers=auth(tokens["VET2"]),
        json={"content": "ไม่ควรบันทึกได้"},
    )
    assert denied.status_code == 403

    first = await client.post(
        f"/api/v1/appointments/{appointment['id']}/treatment-notes",
        headers=auth(tokens["VET"]),
        json={"content": "ให้น้ำเกลือและสังเกตอาการ 24 ชั่วโมง"},
    )
    assert first.status_code == 201
    assert first.json()["version"] == 1

    second = await client.post(
        f"/api/v1/appointments/{appointment['id']}/treatment-notes",
        headers=auth(tokens["VET"]),
        json={"content": "อาการดีขึ้น นัดติดตามอีก 7 วัน"},
    )
    assert second.status_code == 201
    assert second.json()["version"] == 2

    notes = await client.get(
        f"/api/v1/appointments/{appointment['id']}/treatment-notes",
        headers=auth(tokens["OWNER"]),
    )
    assert notes.status_code == 200
    assert [item["version"] for item in notes.json()] == [1, 2]

    empty = await client.post(
        f"/api/v1/appointments/{appointment['id']}/treatment-notes",
        headers=auth(tokens["VET"]),
        json={"content": "   "},
    )
    assert empty.status_code == 422


async def test_reschedule_request_requires_reason_and_ownership(client, tokens, seeded):
    appointment = await _appointment(client, tokens, seeded, hour=10)

    empty = await client.post(
        f"/api/v1/appointments/{appointment['id']}/reschedule-requests",
        headers=auth(tokens["VET"]),
        json={"proposed_slot_start": slot(seeded["day"], 14, 0).isoformat(), "reason": " "},
    )
    assert empty.status_code == 422

    other_vet = await client.post(
        f"/api/v1/appointments/{appointment['id']}/reschedule-requests",
        headers=auth(tokens["VET2"]),
        json={"proposed_slot_start": slot(seeded["day"], 14, 0).isoformat(), "reason": "ขอสลับ"},
    )
    assert other_vet.status_code == 403

    created = await client.post(
        f"/api/v1/appointments/{appointment['id']}/reschedule-requests",
        headers=auth(tokens["VET"]),
        json={"proposed_slot_start": slot(seeded["day"], 14, 0).isoformat(), "reason": "ติดผ่าตัด"},
    )
    assert created.status_code == 201, created.text
    assert created.json()["status"] == "PENDING"


async def test_staff_approves_reschedule_request(client, tokens, seeded):
    appointment = await _appointment(client, tokens, seeded, hour=12)
    request = await client.post(
        f"/api/v1/appointments/{appointment['id']}/reschedule-requests",
        headers=auth(tokens["VET"]),
        json={"proposed_slot_start": slot(seeded["day"], 15, 0).isoformat(), "reason": "ขอปรับเวลา"},
    )
    request_id = request.json()["id"]

    listed = await client.get(
        "/api/v1/reschedule-requests", headers=auth(tokens["STAFF"]), params={"status": "PENDING"}
    )
    assert listed.status_code == 200
    assert any(item["id"] == request_id for item in listed.json())

    approved = await client.post(
        f"/api/v1/reschedule-requests/{request_id}/approve",
        headers=auth(tokens["STAFF"]),
        json={"review_note": "อนุมัติ"},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "APPROVED"

    detail = await client.get(
        f"/api/v1/appointments/{appointment['id']}", headers=auth(tokens["STAFF"])
    )
    assert datetime.fromisoformat(detail.json()["slot_start"]) == slot(
        seeded["day"], 15, 0
    )

    again = await client.post(
        f"/api/v1/reschedule-requests/{request_id}/approve",
        headers=auth(tokens["STAFF"]),
        json={},
    )
    assert again.status_code == 409


async def test_staff_rejects_reschedule_request(client, tokens, seeded):
    appointment = await _appointment(client, tokens, seeded, hour=13)
    request = await client.post(
        f"/api/v1/appointments/{appointment['id']}/reschedule-requests",
        headers=auth(tokens["VET"]),
        json={"proposed_slot_start": slot(seeded["day"], 16, 0).isoformat(), "reason": "ขอปรับ"},
    )
    response = await client.post(
        f"/api/v1/reschedule-requests/{request.json()['id']}/reject",
        headers=auth(tokens["STAFF"]),
        json={"review_note": "คิวเต็ม"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "REJECTED"

    detail = await client.get(
        f"/api/v1/appointments/{appointment['id']}", headers=auth(tokens["STAFF"])
    )
    assert detail.json()["slot_start"] == appointment["slot_start"]


async def test_pet_history_access_rules(client, tokens, seeded):
    appointment = await _appointment(client, tokens, seeded, hour=14)
    owner = await client.get(
        f"/api/v1/pets/{seeded['pet1_id']}/history", headers=auth(tokens["OWNER"])
    )
    assert owner.status_code == 200
    assert any(item["appointment"]["id"] == appointment["id"] for item in owner.json())

    vet = await client.get(
        f"/api/v1/pets/{seeded['pet1_id']}/history", headers=auth(tokens["VET"])
    )
    assert vet.status_code == 200

    staff = await client.get(
        f"/api/v1/pets/{seeded['pet1_id']}/history", headers=auth(tokens["STAFF"])
    )
    assert staff.status_code == 200

    unrelated_vet = await client.get(
        f"/api/v1/pets/{seeded['pet1_id']}/history", headers=auth(tokens["VET2"])
    )
    assert unrelated_vet.status_code == 403

    other_owner = await client.get(
        f"/api/v1/pets/{seeded['pet1_id']}/history", headers=auth(tokens["OWNER2"])
    )
    assert other_owner.status_code == 403

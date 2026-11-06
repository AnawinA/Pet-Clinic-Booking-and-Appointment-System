"""Thai notification copy for outbox event types."""

from __future__ import annotations

from datetime import datetime

from app.core.time import BANGKOK

STATUS_LABELS = {
    "BOOKED": "จองแล้ว",
    "CHECKED_IN": "เช็คอินแล้ว",
    "IN_TREATMENT": "กำลังรักษา",
    "COMPLETED": "รักษาเสร็จแล้ว",
    "NO_SHOW": "ไม่มาแสดงตัว",
    "CANCELLED": "ยกเลิกแล้ว",
}


def _format_slot(value: object) -> str:
    if not value:
        return "-"
    try:
        return datetime.fromisoformat(str(value)).astimezone(BANGKOK).strftime("%d/%m/%Y %H:%M")
    except ValueError:
        return str(value)


def build_message(event_type: str, payload: dict) -> tuple[str, str]:
    pet = payload.get("pet_name") or "สัตว์เลี้ยง"
    vet = payload.get("vet_name") or "สัตวแพทย์"
    when = _format_slot(payload.get("slot_start"))

    if event_type == "APPOINTMENT_BOOKED":
        return (
            "ยืนยันการนัดหมาย",
            f"นัดหมายของ {pet} กับ {vet} วันที่ {when} ได้รับการยืนยันแล้ว",
        )
    if event_type == "APPOINTMENT_CANCELLED":
        return (
            "ยกเลิกนัดหมาย",
            f"นัดหมายของ {pet} กับ {vet} วันที่ {when} ถูกยกเลิกแล้ว",
        )
    if event_type == "APPOINTMENT_STATUS_CHANGED":
        status = STATUS_LABELS.get(str(payload.get("status")), str(payload.get("status")))
        return (
            "อัปเดตสถานะนัดหมาย",
            f"นัดหมายของ {pet} กับ {vet} วันที่ {when} เปลี่ยนสถานะเป็น {status}",
        )
    if event_type == "APPOINTMENT_RESCHEDULED":
        return (
            "เลื่อนนัดหมาย",
            f"นัดหมายของ {pet} กับ {vet} ถูกเลื่อนไปเป็นวันที่ {when}",
        )
    if event_type == "APPOINTMENT_TRANSFERRED":
        previous = payload.get("previous_vet_name")
        suffix = f" (เดิม {previous})" if previous else ""
        return (
            "โอนเคส",
            f"เคสของ {pet} วันที่ {when} ถูกโอนให้ {vet}{suffix}",
        )
    if event_type == "APPOINTMENT_REMINDER":
        return (
            "แจ้งเตือนนัดหมาย",
            f"นัดของ {pet} กับ {vet} จะเริ่มเวลา {when} (อีก 1 ชั่วโมง)",
        )
    if event_type == "RESCHEDULE_REQUESTED":
        proposed = _format_slot(payload.get("proposed_slot_start"))
        return (
            "คำขอปรับเวลาใหม่",
            f"{vet} ขอปรับเวลานัดของ {pet} เป็น {proposed} เหตุผล: "
            f"{payload.get('reason', '-')}",
        )
    if event_type == "RESCHEDULE_REVIEWED":
        decision = "อนุมัติ" if payload.get("decision") == "APPROVED" else "ปฏิเสธ"
        return (
            f"คำขอปรับเวลา{decision}",
            f"คำขอปรับเวลาของ {pet} ถูก{decision}แล้ว",
        )
    if event_type == "TREATMENT_NOTE_ADDED":
        version = payload.get("version", "-")
        return (
            "บันทึกการรักษาใหม่",
            f"{vet} บันทึกคำแนะนำการรักษาของ {pet} เวอร์ชัน {version}",
        )
    return ("การแจ้งเตือน", f"มีเหตุการณ์ใหม่สำหรับ {pet}")

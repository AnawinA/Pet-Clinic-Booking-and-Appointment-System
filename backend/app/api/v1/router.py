from fastapi import APIRouter

from app.api.v1 import (
    appointments,
    audit,
    auth,
    availability,
    health,
    notifications,
    pets,
    queue,
    reschedule_requests,
    schedule,
    shifts,
    treatment_notes,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(pets.router)
api_router.include_router(availability.router)
api_router.include_router(appointments.router)
api_router.include_router(queue.router)
api_router.include_router(schedule.router)
api_router.include_router(shifts.router)
api_router.include_router(reschedule_requests.router)
api_router.include_router(treatment_notes.router)
api_router.include_router(notifications.router)
api_router.include_router(audit.router)

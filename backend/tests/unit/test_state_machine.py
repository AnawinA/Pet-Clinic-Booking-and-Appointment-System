from __future__ import annotations

from app.models import ALLOWED_TRANSITIONS, AppointmentStatus


def test_booked_can_check_in_no_show_or_cancel():
    assert ALLOWED_TRANSITIONS[AppointmentStatus.BOOKED] == {
        AppointmentStatus.CHECKED_IN,
        AppointmentStatus.NO_SHOW,
        AppointmentStatus.CANCELLED,
    }


def test_in_treatment_only_completes():
    assert ALLOWED_TRANSITIONS[AppointmentStatus.IN_TREATMENT] == {
        AppointmentStatus.COMPLETED
    }


def test_terminal_states_have_no_transitions():
    for status in (
        AppointmentStatus.COMPLETED,
        AppointmentStatus.NO_SHOW,
        AppointmentStatus.CANCELLED,
    ):
        assert ALLOWED_TRANSITIONS[status] == set()


def test_cannot_skip_from_booked_to_completed():
    assert AppointmentStatus.COMPLETED not in ALLOWED_TRANSITIONS[AppointmentStatus.BOOKED]

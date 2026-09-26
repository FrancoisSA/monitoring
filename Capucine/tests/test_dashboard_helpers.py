from datetime import date

import pytz

from capucine.dashboard import _classify_task_status, _enrich_event_for_display

_TZ = pytz.timezone("Europe/Paris")
_TODAY = date(2025, 6, 10)


def test_classify_task_status_without_due_date_is_upcoming():
    status, due_display = _classify_task_status(None, _TODAY, _TZ)

    assert status == "upcoming"
    assert due_display is None


def test_classify_task_status_overdue():
    status, due_display = _classify_task_status("2025-06-09T00:00:00Z", _TODAY, _TZ)

    assert status == "overdue"
    assert due_display == "09/06/2025"


def test_classify_task_status_today():
    # 10:00 UTC == 12:00 Paris (été, UTC+2) : reste bien le 10 juin en heure locale.
    status, _ = _classify_task_status("2025-06-10T10:00:00Z", _TODAY, _TZ)

    assert status == "today"


def test_classify_task_status_upcoming():
    status, _ = _classify_task_status("2025-06-20T00:00:00Z", _TODAY, _TZ)

    assert status == "upcoming"


def test_classify_task_status_handles_invalid_date_gracefully():
    status, due_display = _classify_task_status("not-a-date", _TODAY, _TZ)

    assert status == "upcoming"
    assert due_display is None


def test_enrich_event_with_time_marks_today():
    event = {"id": "1", "summary": "Réunion", "start": "2025-06-10T14:00:00+02:00", "end": "", "location": ""}

    enriched = _enrich_event_for_display(event, _TODAY, _TZ)

    assert enriched["is_today"] is True
    assert enriched["time_display"] == "14:00"
    assert enriched["date_key"] == "2025-06-10"


def test_enrich_event_with_time_not_today():
    event = {"id": "1", "summary": "Réunion", "start": "2025-06-11T14:00:00+02:00", "end": "", "location": ""}

    enriched = _enrich_event_for_display(event, _TODAY, _TZ)

    assert enriched["is_today"] is False


def test_enrich_all_day_event():
    event = {"id": "1", "summary": "Weekend", "start": "2025-06-10", "end": "2025-06-12", "location": ""}

    enriched = _enrich_event_for_display(event, _TODAY, _TZ)

    assert enriched["time_display"] == "Journée"
    assert enriched["is_today"] is True
    assert enriched["date_key"] == "2025-06-10"


def test_enrich_event_does_not_mutate_input():
    event = {"id": "1", "summary": "Réunion", "start": "2025-06-10T14:00:00+02:00", "end": "", "location": ""}

    _enrich_event_for_display(event, _TODAY, _TZ)

    assert "date_display" not in event

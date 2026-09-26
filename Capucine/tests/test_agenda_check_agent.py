from capucine.agents.agenda_check import AgendaCheckAgent

_AGENDA_PRO_EMAIL_BODY = """
EVENT_UID:uid-1
SUBJECT:Point équipe
STARTTIME:2025-06-10T09:00:00
ENDTIME:2025-06-10T09:30:00
"""


class FakeCalendar:
    timezone = "Europe/Paris"

    def __init__(self, upcoming_events=None):
        self._upcoming_events = upcoming_events or []
        self.upserted = []
        self.deleted = []
        self.find_by_title_results = []

    def get_upcoming_events(self, minutes_ahead):
        return self._upcoming_events

    def upsert_agenda_pro_event(self, **kwargs):
        self.upserted.append(kwargs)
        if getattr(self, "raise_on_upsert", False):
            raise RuntimeError("échec Google simulé")
        return {"id": "gcal-1", "summary": kwargs["summary"]}, kwargs.get("existing_event_id") is None

    def get_calendar_id(self, name):
        return f"cal-{name}"

    def delete_event(self, event_id, calendar_id=None):
        self.deleted.append((event_id, calendar_id))
        return True

    def find_events_by_title(self, title, calendar_name):
        return self.find_by_title_results


class FakeGmail:
    def __init__(self, emails=None):
        self._emails = emails or []
        self._bodies = {}
        self.marked_read = []

    def search_emails(self, keyword, max_results):
        return self._emails

    def get_email(self, email_id):
        return {"id": email_id, "body_text": self._bodies[email_id]}

    def mark_as_read(self, email_id):
        self.marked_read.append(email_id)
        return True


def _agent(calendar=None, gmail=None):
    return AgendaCheckAgent(
        calendar=calendar or FakeCalendar(),
        gmail=gmail or FakeGmail(),
        reminder_advance_minutes=20,
        agenda_pro_calendar_name="Ampere",
    )


def test_notify_false_when_nothing_to_report(deps):
    agent = _agent()

    response = agent.handle("", deps)

    assert response.notify is False


def test_reminder_is_reported_once_then_deduped(deps):
    events = [{"id": "evt-1", "summary": "Réunion", "start": "2025-06-10T09:15:00+02:00", "location": ""}]
    calendar = FakeCalendar(upcoming_events=events)
    agent = _agent(calendar=calendar)

    first = agent.handle("", deps)
    second = agent.handle("", deps)

    assert first.notify is True
    assert "Réunion" in first.text
    assert second.notify is False


def test_agenda_pro_email_creates_calendar_event(deps):
    gmail = FakeGmail(emails=[{"id": "email-1"}])
    gmail._bodies["email-1"] = _AGENDA_PRO_EMAIL_BODY
    calendar = FakeCalendar()
    agent = _agent(calendar=calendar, gmail=gmail)

    response = agent.handle("", deps)

    assert response.notify is True
    assert "Point équipe" in response.text
    assert calendar.upserted[0]["event_uid"] == "uid-1"
    assert gmail.marked_read == ["email-1"]
    assert deps.store.is_agenda_pro_email_processed("email-1") is True
    assert deps.store.get_agenda_pro_event_id("uid-1") == "gcal-1"


def test_agenda_pro_email_already_processed_is_skipped(deps):
    gmail = FakeGmail(emails=[{"id": "email-1"}])
    gmail._bodies["email-1"] = _AGENDA_PRO_EMAIL_BODY
    calendar = FakeCalendar()
    deps.store.mark_agenda_pro_email_processed("email-1")
    agent = _agent(calendar=calendar, gmail=gmail)

    response = agent.handle("", deps)

    assert response.notify is False
    assert calendar.upserted == []
    assert gmail.marked_read == ["email-1"]


def test_agenda_pro_email_is_marked_processed_even_on_upsert_failure(deps):
    gmail = FakeGmail(emails=[{"id": "email-1"}])
    gmail._bodies["email-1"] = _AGENDA_PRO_EMAIL_BODY
    calendar = FakeCalendar()
    calendar.raise_on_upsert = True
    agent = _agent(calendar=calendar, gmail=gmail)

    response = agent.handle("", deps)

    assert response.notify is False
    assert deps.store.is_agenda_pro_email_processed("email-1") is True
    assert gmail.marked_read == ["email-1"]
    # La réservation ratée ne doit pas laisser une ligne orpheline pour uid-1.
    assert deps.store.get_agenda_pro_event_id("uid-1") is None


def test_agenda_pro_cancellation_deletes_known_event(deps):
    body = _AGENDA_PRO_EMAIL_BODY.replace("SUBJECT:Point équipe", "SUBJECT:Declined: Point équipe")
    gmail = FakeGmail(emails=[{"id": "email-1"}])
    gmail._bodies["email-1"] = body
    calendar = FakeCalendar()
    deps.store.save_agenda_pro_event_id("uid-1", "gcal-existing", "Ampere", title="Point équipe", start_time="2025-06-10T09:00:00+02:00")
    agent = _agent(calendar=calendar, gmail=gmail)

    response = agent.handle("", deps)

    assert response.notify is True
    assert "retiré du calendrier" in response.text
    assert calendar.deleted == [("gcal-existing", "cal-Ampere")]
    assert deps.store.get_agenda_pro_event_id("uid-1") is None

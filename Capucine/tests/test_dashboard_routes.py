import pytest

from capucine import dashboard as dashboard_module
from capucine.dashboard import create_app
from capucine.store import Store


class FakeCalendar:
    timezone = "Europe/Paris"

    def __init__(self, events=None):
        self._events = events or []
        self.weekend_upserts = []
        self.weekend_deletes = []

    def list_events(self, days_ahead, max_results):
        return self._events

    def upsert_weekend_note(self, sat_date, note):
        self.weekend_upserts.append((sat_date, note))

    def delete_weekend_note(self, sat_date):
        self.weekend_deletes.append(sat_date)


class FakeTasks:
    def __init__(self, tasks=None):
        self._tasks = tasks or []
        self.completed = []
        self.updated = []

    def list_tasks(self, max_results, show_completed):
        return [dict(t) for t in self._tasks]

    def complete_task(self, task_id):
        self.completed.append(task_id)
        return {"id": task_id, "status": "completed"}

    def update_task(self, task_id, title=None, due=None):
        self.updated.append((task_id, title, due))
        return {"id": task_id, "title": title, "due": due}


def _make_app(tmp_path, valid_credentials, monkeypatch, calendar=None, tasks=None):
    monkeypatch.setattr(dashboard_module.google_auth, "is_credentials_valid", lambda token_file: valid_credentials)

    from capucine.config import Config

    config = Config(
        telegram_bot_token="x", telegram_chat_id=1, ollama_host="x", ollama_model="x", ollama_timeout=1,
        db_path=str(tmp_path / "test.db"), presse_feeds=[], socket_path="x", presse_llm_timeout=1,
        renault_search_queries=[], renault_llm_timeout=1, ia_feeds=[], ia_llm_timeout=1,
        mac_host=None, mac_ssh_user="", mac_ssh_key_path="", mac_address="", mac_model="",
        mac_wake_timeout_s=1, mac_retry_interval_s=1, mac_tts_model_path="",
        mac_tts_voice="", mac_tts_instruct="", mac_stt_model="", piper_voice_model_path="",
        google_credentials_file="unused", google_token_file="unused", calendar_timezone="Europe/Paris",
        calendar_agenda_pro_name="Ampere", extra_calendar_names=[], calendar_reminder_advance_minutes=20,
        agenda_ollama_model="x", agenda_llm_timeout=1,
        dashboard_port=9192, oauth_redirect_uri="http://localhost:9192/auth/callback",
        dashboard_cache_ttl_seconds=0,
    )

    app = create_app(
        config,
        calendar=calendar or FakeCalendar(),
        tasks=tasks or FakeTasks(),
        store=Store(config.db_path),
    )
    app.testing = True
    return app


def test_dashboard_redirects_to_login_when_credentials_invalid(tmp_path, monkeypatch):
    app = _make_app(tmp_path, valid_credentials=False, monkeypatch=monkeypatch)
    client = app.test_client()

    response = client.get("/")

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_api_returns_401_when_credentials_invalid(tmp_path, monkeypatch):
    app = _make_app(tmp_path, valid_credentials=False, monkeypatch=monkeypatch)
    client = app.test_client()

    response = client.get("/api/tasks")

    assert response.status_code == 401
    assert response.get_json()["error"] == "auth_required"


def test_login_page_is_reachable_without_credentials(tmp_path, monkeypatch):
    app = _make_app(tmp_path, valid_credentials=False, monkeypatch=monkeypatch)
    client = app.test_client()

    response = client.get("/login")

    assert response.status_code == 200


def test_api_tasks_classifies_status(tmp_path, monkeypatch):
    tasks = FakeTasks(tasks=[{"id": "t1", "title": "Payer la taxe", "due": "2020-01-01T00:00:00Z", "notes": "", "status": "needsAction"}])
    app = _make_app(tmp_path, valid_credentials=True, monkeypatch=monkeypatch, tasks=tasks)
    client = app.test_client()

    response = client.get("/api/tasks")

    assert response.status_code == 200
    body = response.get_json()
    assert body[0]["status_label"] == "overdue"


def test_api_task_complete_calls_tasks_client(tmp_path, monkeypatch):
    tasks = FakeTasks()
    app = _make_app(tmp_path, valid_credentials=True, monkeypatch=monkeypatch, tasks=tasks)
    client = app.test_client()

    response = client.post("/api/tasks/t1/complete")

    assert response.status_code == 200
    assert tasks.completed == ["t1"]


def test_api_task_update_rejects_invalid_due_format(tmp_path, monkeypatch):
    app = _make_app(tmp_path, valid_credentials=True, monkeypatch=monkeypatch)
    client = app.test_client()

    response = client.put("/api/tasks/t1", json={"title": "x", "due": "not-a-date"})

    assert response.status_code == 400


def test_weekend_notes_round_trip_through_store(tmp_path, monkeypatch):
    calendar = FakeCalendar()
    app = _make_app(tmp_path, valid_credentials=True, monkeypatch=monkeypatch, calendar=calendar)
    client = app.test_client()

    put_response = client.put("/api/weekend-notes/2025-06-14", json={"note": "Randonnée"})
    get_response = client.get("/api/weekend-notes")

    assert put_response.status_code == 200
    assert get_response.get_json() == {"2025-06-14": "Randonnée"}
    assert calendar.weekend_upserts == [("2025-06-14", "Randonnée")]


def test_weekend_notes_empty_note_deletes_from_calendar(tmp_path, monkeypatch):
    calendar = FakeCalendar()
    app = _make_app(tmp_path, valid_credentials=True, monkeypatch=monkeypatch, calendar=calendar)
    client = app.test_client()

    client.put("/api/weekend-notes/2025-06-14", json={"note": "Randonnée"})
    client.put("/api/weekend-notes/2025-06-14", json={"note": ""})

    assert calendar.weekend_deletes == ["2025-06-14"]


def test_api_events_are_enriched(tmp_path, monkeypatch):
    # Date d'été proche (offset +02:00 == offset Paris en juin) pour que
    # l'heure locale affichée corresponde exactement à l'offset fourni — une
    # date trop lointaine (ex. 2099) dépasse la table de transitions DST de
    # pytz, qui retombe alors sur l'heure d'hiver toute l'année.
    events = [{"id": "1", "summary": "Réunion", "start": "2030-06-01T14:00:00+02:00", "end": "", "location": ""}]
    calendar = FakeCalendar(events=events)
    app = _make_app(tmp_path, valid_credentials=True, monkeypatch=monkeypatch, calendar=calendar)
    client = app.test_client()

    response = client.get("/api/events")

    body = response.get_json()
    assert body[0]["time_display"] == "14:00"

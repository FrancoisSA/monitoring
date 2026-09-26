"""Teste GoogleCalendarClient contre un faux client Google (aucun appel
réseau, aucune credential) — seam validé pour ce chantier : les fonctions
publiques de google_calendar.py, cf. plan de portage."""
import itertools

import pytest

from capucine.google_calendar import GoogleCalendarClient


class _Execute:
    def __init__(self, result):
        self._result = result

    def execute(self):
        return self._result


class FakeEventsResource:
    def __init__(self, store: dict, id_counter):
        self._store = store
        self._id_counter = id_counter

    def list(self, calendarId, q=None, privateExtendedProperty=None, **_ignored):
        """Filtrage simplifié : ignore timeMin/timeMax/maxResults/orderBy
        (comportement de filtrage temporel de Google, hors du périmètre
        testé ici) ; ne filtre que sur calendarId + q + privateExtendedProperty."""
        events = list(self._store.get(calendarId, {}).values())
        if q:
            events = [e for e in events if q.strip().lower() in e.get("summary", "").strip().lower()]
        if privateExtendedProperty:
            key, _, value = privateExtendedProperty.partition("=")
            events = [
                e for e in events
                if e.get("extendedProperties", {}).get("private", {}).get(key) == value
            ]
        return _Execute({"items": events})

    def get(self, calendarId, eventId):
        return _Execute(dict(self._store[calendarId][eventId]))

    def insert(self, calendarId, body):
        event_id = f"evt-{next(self._id_counter)}"
        event = dict(body)
        event["id"] = event_id
        self._store.setdefault(calendarId, {})[event_id] = event
        return _Execute(dict(event))

    def update(self, calendarId, eventId, body):
        event = dict(body)
        event["id"] = eventId
        self._store[calendarId][eventId] = event
        return _Execute(dict(event))

    def delete(self, calendarId, eventId):
        self._store[calendarId].pop(eventId, None)
        return _Execute(None)


class FakeCalendarListResource:
    def __init__(self, calendars: dict):
        self._calendars = calendars

    def list(self):
        items = [{"id": cal_id, "summary": name} for name, cal_id in self._calendars.items()]
        return _Execute({"items": items})


class FakeGoogleService:
    """Double minimal de googleapiclient.discovery.build("calendar", "v3", ...)."""

    def __init__(self, extra_calendars: dict = None):
        self._store: dict = {"primary": {}}
        self._id_counter = itertools.count(1)
        self._calendars = {"primary": "primary", **(extra_calendars or {})}

    def events(self):
        return FakeEventsResource(self._store, self._id_counter)

    def calendarList(self):
        return FakeCalendarListResource(self._calendars)


@pytest.fixture
def fake_service():
    return FakeGoogleService(extra_calendars={"Ampere": "ampere-cal-id"})


@pytest.fixture
def client(fake_service):
    c = GoogleCalendarClient(credentials_file="unused", token_file="unused", timezone="Europe/Paris")
    c._get_service = lambda: fake_service  # court-circuite l'auth OAuth réelle
    return c


def test_add_event_creates_new_event(client):
    event = client.add_event(summary="Réunion", start="2025-06-10T14:00:00", end="2025-06-10T15:00:00")

    assert event["summary"] == "Réunion"
    assert event["start"] == "2025-06-10T14:00:00+02:00"


def test_add_event_returns_existing_event_on_duplicate(client, fake_service):
    first = client.add_event(summary="Réunion", start="2025-06-10T14:00:00", end="2025-06-10T15:00:00")
    second = client.add_event(summary="Réunion", start="2025-06-10T14:00:00", end="2025-06-10T15:00:00")

    assert second["id"] == first["id"]
    assert len(fake_service._store["primary"]) == 1


def test_add_event_default_duration_is_one_hour(client):
    event = client.add_event(summary="Point rapide", start="2025-06-10T09:00:00")

    assert event["start"] == "2025-06-10T09:00:00+02:00"
    assert event["end"] == "2025-06-10T10:00:00+02:00"


def test_upsert_agenda_pro_event_creates_when_unknown(client):
    event, created = client.upsert_agenda_pro_event(
        event_uid="uid-1",
        summary="Point équipe",
        start="2025-06-10T09:00:00+02:00",
        end="2025-06-10T09:30:00+02:00",
        calendar_name="Ampere",
    )

    assert created is True
    assert event["summary"] == "Point équipe"


def test_upsert_agenda_pro_event_updates_when_existing_id_known(client):
    created_event, created = client.upsert_agenda_pro_event(
        event_uid="uid-1", summary="Point équipe",
        start="2025-06-10T09:00:00+02:00", end="2025-06-10T09:30:00+02:00",
        calendar_name="Ampere",
    )

    updated_event, created_again = client.upsert_agenda_pro_event(
        event_uid="uid-1", summary="Point équipe (déplacé)",
        start="2025-06-10T10:00:00+02:00", end="2025-06-10T10:30:00+02:00",
        calendar_name="Ampere",
        existing_event_id=created_event["id"],
    )

    assert created_again is False
    assert updated_event["id"] == created_event["id"]
    assert updated_event["summary"] == "Point équipe (déplacé)"


def test_upsert_agenda_pro_event_falls_back_to_duplicate_detection(client):
    """Si le Store n'a pas d'ID connu mais qu'un événement identique existe
    déjà (titre + créneau), on le met à jour plutôt que d'en recréer un —
    filet de sécurité pour un Store désynchronisé (cf. plan de portage)."""
    first, _ = client.upsert_agenda_pro_event(
        event_uid="uid-1", summary="Point équipe",
        start="2025-06-10T09:00:00+02:00", end="2025-06-10T09:30:00+02:00",
        calendar_name="Ampere",
    )

    # Nouvel EVENT_UID (régénéré côté AGENDA PRO), pas d'existing_event_id fourni.
    second, created = client.upsert_agenda_pro_event(
        event_uid="uid-2", summary="Point équipe",
        start="2025-06-10T09:00:00+02:00", end="2025-06-10T09:30:00+02:00",
        calendar_name="Ampere",
    )

    assert created is False
    assert second["id"] == first["id"]


def test_upsert_weekend_note_creates_all_day_event_covering_saturday_and_sunday(client):
    event = client.upsert_weekend_note("2025-06-14", "Randonnée en famille")

    assert event["start"] == "2025-06-14"
    assert event["end"] == "2025-06-16"  # lundi exclu
    assert event["description"] == "Randonnée en famille"


def test_upsert_weekend_note_updates_existing_note_for_same_saturday(client, fake_service):
    first = client.upsert_weekend_note("2025-06-14", "Première note")
    second = client.upsert_weekend_note("2025-06-14", "Note corrigée")

    assert second["id"] == first["id"]
    assert second["description"] == "Note corrigée"
    assert len(fake_service._store["primary"]) == 1


def test_list_events_merges_and_sorts_extra_calendar(fake_service):
    """Un calendrier additionnel (ex. un compte partagé) doit être fusionné
    avec "primary" et trié par heure de début, avec son nom en `calendar_name`
    pour que le dashboard distingue la source."""
    client = GoogleCalendarClient(
        credentials_file="unused", token_file="unused", timezone="Europe/Paris",
        extra_calendar_names=["Ampere"],
    )
    client._get_service = lambda: fake_service

    fake_service._store["primary"]["p1"] = {
        "id": "p1", "summary": "RDV perso",
        "start": {"dateTime": "2025-06-10T14:00:00+02:00"},
        "end": {"dateTime": "2025-06-10T15:00:00+02:00"},
    }
    fake_service._store["ampere-cal-id"] = {"a1": {
        "id": "a1", "summary": "RDV Ampere",
        "start": {"dateTime": "2025-06-10T09:00:00+02:00"},
        "end": {"dateTime": "2025-06-10T09:30:00+02:00"},
    }}

    events = client.list_events(days_ahead=30, max_results=20)

    assert [e["summary"] for e in events] == ["RDV Ampere", "RDV perso"]
    assert events[0]["calendar_name"] == "Ampere"
    assert "calendar_name" not in events[1]


def test_list_events_ignores_unknown_extra_calendar(fake_service):
    """Un nom de calendrier additionnel introuvable ne doit pas faire
    échouer tout le dashboard — seulement être ignoré."""
    client = GoogleCalendarClient(
        credentials_file="unused", token_file="unused", timezone="Europe/Paris",
        extra_calendar_names=["Calendrier inconnu"],
    )
    client._get_service = lambda: fake_service
    fake_service._store["primary"]["p1"] = {
        "id": "p1", "summary": "RDV perso",
        "start": {"dateTime": "2025-06-10T14:00:00+02:00"},
        "end": {"dateTime": "2025-06-10T15:00:00+02:00"},
    }

    events = client.list_events(days_ahead=30, max_results=20)

    assert [e["summary"] for e in events] == ["RDV perso"]

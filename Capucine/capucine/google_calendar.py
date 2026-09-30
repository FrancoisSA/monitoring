"""Client Google Calendar.

Fournit les opérations CRUD sur les événements du calendrier principal :
- Lister les événements à venir
- Ajouter / modifier / supprimer des événements
- Rechercher des événements par mot-clé
- Stocker les notes de weekends comme événements Google Calendar
- Upsert d'événements [AGENDA PRO] identifiés par EVENT_UID (évite les doublons)

Porté depuis prj-jeffrey/services/google_calendar.py. Regroupé dans une
classe (plutôt que des fonctions module-level lisant une config globale)
pour rester cohérent avec le style d'injection de dépendances de Capucine
(cf. capucine/llm/ollama_client.py::OllamaClient) : le fuseau horaire et les
credentials sont liés une fois à la construction, pas relus à chaque appel.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta

import pytz
from googleapiclient.discovery import build

from capucine.google_auth import get_google_credentials

logger = logging.getLogger(__name__)

# Tag privé pour les événements de notes weekends.
_WEEKEND_TAG = "jeffrey_weekend"

# Clé extendedProperties utilisée pour identifier les événements [AGENDA PRO]
# par leur EVENT_UID. Stockée dans extendedProperties.private pour
# retrouver l'événement et le mettre à jour sans doublon.
_EVENT_UID_KEY = "agenda_pro_event_uid"


class GoogleCalendarClient:
    def __init__(
        self,
        credentials_file: str,
        token_file: str,
        timezone: str,
        extra_calendar_names: "list[str] | None" = None,
    ) -> None:
        self._credentials_file = credentials_file
        self._token_file = token_file
        self.timezone = timezone
        self._tz = pytz.timezone(timezone)
        # Calendriers supplémentaires (en plus de "primary") interrogés par
        # list_events — ex. un calendrier d'un autre compte Google partagé
        # en lecture avec le compte authentifié (cf. EXTRA_CALENDAR_NAMES).
        self._extra_calendar_names = extra_calendar_names or []
        # Cache local : nom de calendrier -> calendarId (évite un appel API
        # à chaque upsert).
        self._calendar_id_cache: "dict[str, str]" = {}

    def _get_service(self):
        creds = get_google_credentials(self._credentials_file, self._token_file)
        return build("calendar", "v3", credentials=creds)

    def get_calendar_id(self, name: str) -> str:
        """
        Retourne le calendarId Google correspondant au nom de calendrier
        donné (insensible à la casse). Lève ValueError si introuvable.
        """
        if name in self._calendar_id_cache:
            return self._calendar_id_cache[name]

        service = self._get_service()
        result = service.calendarList().list().execute()
        for cal in result.get("items", []):
            if cal.get("summary", "").strip().lower() == name.strip().lower():
                self._calendar_id_cache[name] = cal["id"]
                return cal["id"]

        raise ValueError(f"Calendrier '{name}' introuvable dans la liste Google Calendar.")

    def _localize(self, dt_str: str) -> str:
        """
        Convertit une chaîne ISO 8601 en datetime localisé au bon fuseau
        horaire. Retourne une chaîne RFC 3339 pour l'API Google.

        Un datetime naïf ici est traité comme heure locale (contrairement à
        capucine/agenda_pro.py::to_local_iso, qui traite un naïf comme UTC) :
        ce n'est PAS une incohérence, ce sont deux sources différentes avec
        deux conventions différentes — les dates traitées ici viennent du
        LLM de /agenda (qui raisonne en heure locale à partir du langage
        naturel), celles de to_local_iso viennent des emails [AGENDA PRO]
        (documentés en UTC). Cf. docs/spec/jeffrey-calendar-reprise/spec.md
        pour le doute d'origine (sur prj-jeffrey, pas ce fichier) et
        tests/test_calendar_timezones.py pour la matrice de tests verrouillant
        ce comportement.
        """
        dt = datetime.fromisoformat(dt_str)
        if dt.tzinfo is None:
            dt = self._tz.localize(dt)
        return dt.isoformat()

    def _fetch_raw_events(self, service, calendar_id: str, time_min: str, time_max: str, max_results: int) -> "list[dict]":
        """Appel brut events().list() pour un calendarId donné."""
        result = service.events().list(
            calendarId=calendar_id,
            timeMin=time_min,
            timeMax=time_max,
            maxResults=max_results,
            singleEvents=True,
            orderBy="startTime",
        ).execute()
        return result.get("items", [])

    def list_events(self, days_ahead: int = 7, max_results: int = 20) -> "list[dict]":
        """
        Liste les événements des N prochains jours, sur le calendrier
        "primary" et sur les calendriers additionnels configurés (cf.
        extra_calendar_names, ex. un calendrier partagé d'un autre compte).
        Les événements sont fusionnés et triés par date de début.
        """
        service = self._get_service()
        now = datetime.now(self._tz)
        time_min, time_max = now.isoformat(), (now + timedelta(days=days_ahead)).isoformat()

        raw_primary = self._fetch_raw_events(service, "primary", time_min, time_max, max_results)
        # Exclure les événements de notes weekends créés par Capucine.
        events = [
            _format_event(e) for e in raw_primary
            if not e.get("extendedProperties", {}).get("private", {}).get(_WEEKEND_TAG)
        ]

        for name in self._extra_calendar_names:
            try:
                calendar_id = self.get_calendar_id(name)
            except ValueError as e:
                logger.warning("[google_calendar] Calendrier additionnel ignoré : %s", e)
                continue
            raw_extra = self._fetch_raw_events(service, calendar_id, time_min, time_max, max_results)
            events.extend(_format_event(e, source=name) for e in raw_extra)

        events.sort(key=lambda e: e["start"] or "")
        return events[:max_results]

    def get_upcoming_events(self, minutes_ahead: int = 20) -> "list[dict]":
        """Retourne les événements qui commencent dans les N prochaines minutes."""
        service = self._get_service()
        now = datetime.now(self._tz)
        time_max = now + timedelta(minutes=minutes_ahead)

        result = service.events().list(
            calendarId="primary",
            timeMin=now.isoformat(),
            timeMax=time_max.isoformat(),
            singleEvents=True,
            orderBy="startTime",
        ).execute()

        return [_format_event(e) for e in result.get("items", [])]

    def _find_duplicate_event(
        self,
        service,
        summary: str,
        start_iso: str,
        end_iso: str,
        calendar_id: str = "primary",
    ) -> "dict | None":
        """
        Recherche un événement déjà présent identique en titre + début + fin.

        On compare sur le triplet (titre normalisé, instant de début,
        instant de fin) car c'est ce qui définit un doublon métier — deux
        invitations au même créneau avec le même titre sont le même
        rendez-vous, quel que soit leur id Google. La comparaison des
        datetimes se fait sur l'instant absolu (objets datetime conscients
        du fuseau) pour ignorer les différences de représentation (offset
        explicite vs timeZone, "+02:00" vs "Z", etc.).
        """
        start_dt = datetime.fromisoformat(start_iso)
        end_dt = datetime.fromisoformat(end_iso)
        target_summary = summary.strip().lower()

        result = service.events().list(
            calendarId=calendar_id,
            timeMin=(start_dt - timedelta(minutes=1)).isoformat(),
            timeMax=(start_dt + timedelta(minutes=1)).isoformat(),
            singleEvents=True,
            orderBy="startTime",
        ).execute()

        for event in result.get("items", []):
            if event.get("summary", "").strip().lower() != target_summary:
                continue
            ev_start = event.get("start", {}).get("dateTime")
            ev_end = event.get("end", {}).get("dateTime")
            if not ev_start or not ev_end:
                continue  # événement « journée entière » : pas comparable à un créneau horaire
            if (datetime.fromisoformat(ev_start) == start_dt
                    and datetime.fromisoformat(ev_end) == end_dt):
                return event
        return None

    def add_event(
        self,
        summary: str,
        start: str,
        end: "str | None" = None,
        description: "str | None" = None,
        location: "str | None" = None,
    ) -> dict:
        """
        Crée un nouvel événement dans le calendrier. Avant l'insertion, on
        vérifie qu'aucun événement identique (même titre, même début et
        même fin) n'existe déjà afin d'éviter les doublons. Si un doublon
        est détecté, on retourne l'événement existant sans rien créer.
        """
        service = self._get_service()

        start_dt = datetime.fromisoformat(start)
        end_dt = datetime.fromisoformat(end) if end else start_dt + timedelta(hours=1)

        start_local = self._localize(start)
        end_local = self._localize(end_dt.isoformat())

        duplicate = self._find_duplicate_event(service, summary, start_local, end_local)
        if duplicate:
            return _format_event(duplicate)

        event_body = {
            "summary": summary,
            "start": {"dateTime": start_local, "timeZone": self.timezone},
            "end": {"dateTime": end_local, "timeZone": self.timezone},
        }
        if description:
            event_body["description"] = description
        if location:
            event_body["location"] = location

        result = service.events().insert(calendarId="primary", body=event_body).execute()
        return _format_event(result)

    def update_event(
        self,
        event_id: str,
        summary: "str | None" = None,
        start: "str | None" = None,
        end: "str | None" = None,
        description: "str | None" = None,
        location: "str | None" = None,
    ) -> dict:
        """Modifie un événement existant."""
        service = self._get_service()
        event = service.events().get(calendarId="primary", eventId=event_id).execute()

        if summary is not None:
            event["summary"] = summary
        if start:
            event["start"] = {"dateTime": self._localize(start), "timeZone": self.timezone}
        if end:
            event["end"] = {"dateTime": self._localize(end), "timeZone": self.timezone}
        if description is not None:
            event["description"] = description
        if location is not None:
            event["location"] = location

        result = service.events().update(calendarId="primary", eventId=event_id, body=event).execute()
        return _format_event(result)

    def delete_event(self, event_id: str, calendar_id: str = "primary") -> bool:
        """Supprime un événement du calendrier."""
        service = self._get_service()
        service.events().delete(calendarId=calendar_id, eventId=event_id).execute()
        return True

    def search_events(self, keyword: str, days_ahead: int = 30) -> "list[dict]":
        """Recherche des événements contenant un mot-clé dans le titre ou la description."""
        service = self._get_service()
        now = datetime.now(self._tz)
        time_max = now + timedelta(days=days_ahead)

        result = service.events().list(
            calendarId="primary",
            q=keyword,
            timeMin=now.isoformat(),
            timeMax=time_max.isoformat(),
            singleEvents=True,
            orderBy="startTime",
        ).execute()

        return [_format_event(e) for e in result.get("items", [])]

    def find_events_by_title(
        self,
        title: str,
        calendar_name: str = "primary",
        days_back: int = 180,
        days_ahead: int = 180,
    ) -> "list[dict]":
        """
        Recherche des événements par titre dans un calendrier donné, passé
        et futur. Utilisé comme fallback quand l'EVENT_UID n'est pas connu.
        """
        service = self._get_service()
        now = datetime.now(self._tz)
        calendar_id = "primary" if calendar_name == "primary" else self.get_calendar_id(calendar_name)

        result = service.events().list(
            calendarId=calendar_id,
            q=title,
            timeMin=(now - timedelta(days=days_back)).isoformat(),
            timeMax=(now + timedelta(days=days_ahead)).isoformat(),
            singleEvents=True,
            orderBy="startTime",
        ).execute()

        return [_format_event(e) for e in result.get("items", [])]

    # ─────────────────────────────────────────────────────────────
    # Notes de weekends — événements multi-jours (Sam→Dim) tagués
    # extendedProperties.private.jeffrey_weekend = "true".
    # ─────────────────────────────────────────────────────────────

    def get_all_weekend_notes(self) -> dict:
        """Retourne toutes les notes de weekends {sat_date: note}."""
        service = self._get_service()
        now = datetime.now(self._tz)
        time_min = (now - timedelta(days=31)).isoformat()
        time_max = (now + timedelta(days=366)).isoformat()

        result = service.events().list(
            calendarId="primary",
            privateExtendedProperty=f"{_WEEKEND_TAG}=true",
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            maxResults=200,
        ).execute()

        notes = {}
        for event in result.get("items", []):
            props = event.get("extendedProperties", {}).get("private", {})
            sat_date = props.get("sat_date")
            note = event.get("description", "")
            if sat_date and note:
                notes[sat_date] = note
        return notes

    def upsert_weekend_note(self, sat_date: str, note: str) -> dict:
        """
        Crée ou met à jour l'événement Google Calendar pour un weekend
        noté. L'événement couvre uniquement le samedi et le dimanche (fin
        = lundi, exclusif).
        """
        service = self._get_service()

        existing = service.events().list(
            calendarId="primary",
            privateExtendedProperty=f"sat_date={sat_date}",
            maxResults=1,
        ).execute().get("items", [])

        sat = date.fromisoformat(sat_date)
        mon = sat + timedelta(days=2)

        event_body = {
            "summary": f"🗓️ {note}",
            "description": note,
            "colorId": "7",
            "start": {"date": sat.isoformat()},
            "end": {"date": mon.isoformat()},
            "extendedProperties": {
                "private": {_WEEKEND_TAG: "true", "sat_date": sat_date},
            },
        }

        if existing:
            result = service.events().update(
                calendarId="primary", eventId=existing[0]["id"], body=event_body
            ).execute()
        else:
            result = service.events().insert(calendarId="primary", body=event_body).execute()

        return _format_event(result)

    def delete_weekend_note(self, sat_date: str) -> bool:
        """Supprime l'événement Google Calendar correspondant au weekend."""
        service = self._get_service()
        existing = service.events().list(
            calendarId="primary",
            privateExtendedProperty=f"sat_date={sat_date}",
            maxResults=1,
        ).execute().get("items", [])

        if existing:
            service.events().delete(calendarId="primary", eventId=existing[0]["id"]).execute()
            return True
        return False

    # ─────────────────────────────────────────────────────────────
    # Événements [AGENDA PRO] — upsert par EVENT_UID.
    # ─────────────────────────────────────────────────────────────

    def delete_gcal_duplicates(self, gcal_event_ids_to_delete: "list[str]", calendar_name: str) -> int:
        """Supprime une liste d'événements Google Calendar (doublons à purger)."""
        service = self._get_service()
        calendar_id = self.get_calendar_id(calendar_name)
        deleted = 0
        for event_id in gcal_event_ids_to_delete:
            try:
                service.events().delete(calendarId=calendar_id, eventId=event_id).execute()
                deleted += 1
            except Exception:
                continue
        return deleted

    def upsert_agenda_pro_event(
        self,
        event_uid: str,
        summary: str,
        start: str,
        end: str,
        description: str = "",
        location: str = "",
        calendar_name: str = "primary",
        existing_event_id: "str | None" = None,
    ) -> "tuple[dict, bool]":
        """
        Crée ou met à jour un événement [AGENDA PRO] identifié par son
        EVENT_UID.

        Args:
            existing_event_id: gcal_event_id déjà connu (depuis le Store).
                Si fourni, court-circuite la recherche par
                privateExtendedProperty (peu fiable, cf. commentaire).

        Returns:
            (event_dict, created) — created=True si nouvel événement.
        """
        service = self._get_service()
        calendar_id = "primary" if calendar_name == "primary" else self.get_calendar_id(calendar_name)

        # Utiliser l'ID fourni par le Store si disponible ; sinon fallback
        # sur le filtre API (privateExtendedProperty est asynchrone et peu
        # fiable comme lookup côté Google).
        if existing_event_id:
            existing = [{"id": existing_event_id}]
        else:
            existing = service.events().list(
                calendarId=calendar_id,
                privateExtendedProperty=f"{_EVENT_UID_KEY}={event_uid}",
                maxResults=1,
            ).execute().get("items", [])

        start_local = self._localize(start)
        end_local = self._localize(end)

        event_body = {
            "summary": summary,
            "start": {"dateTime": start_local, "timeZone": self.timezone},
            "end": {"dateTime": end_local, "timeZone": self.timezone},
            "extendedProperties": {"private": {_EVENT_UID_KEY: event_uid}},
        }
        if description:
            event_body["description"] = description
        if location:
            event_body["location"] = location

        # Filet de sécurité : si aucun événement connu par UID/Store, on
        # vérifie quand même qu'il n'existe pas déjà un événement identique
        # (titre + début + fin) sur ce calendrier. Rattrape les cas où le
        # Store est désynchronisé et où l'EVENT_UID a été régénéré.
        if not existing:
            duplicate = self._find_duplicate_event(service, summary, start_local, end_local, calendar_id)
            if duplicate:
                existing = [duplicate]

        if existing:
            result = service.events().update(
                calendarId=calendar_id, eventId=existing[0]["id"], body=event_body
            ).execute()
            return _format_event(result), False
        else:
            result = service.events().insert(calendarId=calendar_id, body=event_body).execute()
            return _format_event(result), True


def _format_event(event: dict, source: "str | None" = None) -> dict:
    """Normalise un événement Google Calendar en dict simple. `source`
    identifie le calendrier d'origine quand ce n'est pas "primary" (ex. un
    calendrier partagé d'un autre compte), pour affichage distinct côté
    dashboard."""
    start = event.get("start", {})
    end = event.get("end", {})
    formatted = {
        "id": event.get("id"),
        "summary": event.get("summary", "(sans titre)"),
        "start": start.get("dateTime", start.get("date")),
        "end": end.get("dateTime", end.get("date")),
        "description": event.get("description", ""),
        "location": event.get("location", ""),
    }
    if source:
        formatted["calendar_name"] = source
    return formatted

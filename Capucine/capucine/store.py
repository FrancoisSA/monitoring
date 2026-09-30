"""Stockage SQLite léger : historique court de conversation par agent.

Un seul fichier, pas de serveur de base de données à administrer — cohérent
avec la contrainte de légèreté CPU/RAM sur le Raspberry Pi.

Les tables `weekend_notes`, `agenda_pro_events` et
`agenda_pro_processed_emails` sont portées de
prj-jeffrey/dashboard/journal.py. Aucun verrou de concurrence n'est
nécessaire ici (contrairement au `threading.Lock` de Jeffrey) : Capucine
n'a qu'une seule connexion Store, utilisée uniquement depuis la boucle
principale de service.py, jamais en parallèle (cf. commentaire dans
service.py::serve_trigger_socket) — ne pas appeler les méthodes de cette
classe depuis un autre thread sans revalider cette hypothèse.
"""
from __future__ import annotations

import re
import sqlite3
import unicodedata
from datetime import datetime, timedelta
from pathlib import Path


def normalize_title(title: str) -> str:
    """
    Normalise un titre de meeting pour la comparaison de déduplication.

    Deux meetings dont les titres ne diffèrent que par la casse, les
    accents, l'espacement ou la ponctuation de fin sont considérés comme
    identiques (ex. "Apéro Guillaume" == "apéro  guillaume." mais
    "Apéro G" != "apéro guillaume").
    """
    if not title:
        return ""
    # Égalise les variantes de tirets (– — vs -) AVANT l'encode ASCII, car
    # l'en-dash/em-dash (U+2013/U+2014) seraient sinon supprimés par encode.
    title = re.sub(u"[‐-―]", "-", title)
    nfkd = unicodedata.normalize("NFKD", title)
    ascii_str = nfkd.encode("ascii", "ignore").decode("ascii")
    folded = ascii_str.casefold()
    collapsed = re.sub(r"\s+", " ", folded).strip()
    collapsed = re.sub(r"[.!?…]+$", "", collapsed).strip()
    return collapsed


class Store:
    """Une connexion SQLite ouverte une fois et réutilisée — pas de coût
    d'ouverture/fermeture à chaque message (service mono-thread, single
    connexion : sans risque de concurrence)."""

    def __init__(self, db_path: "str | Path") -> None:
        self._db_path = str(db_path)
        self._conn = sqlite3.connect(self._db_path)
        self._init_schema()

    def close(self) -> None:
        self._conn.close()

    def _init_schema(self) -> None:
        with self._conn:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS seen_links (
                    agent TEXT NOT NULL,
                    link TEXT NOT NULL,
                    seen_at TEXT NOT NULL DEFAULT (datetime('now')),
                    PRIMARY KEY (agent, link)
                )
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS weekend_notes (
                    sat_date TEXT PRIMARY KEY,
                    note TEXT NOT NULL DEFAULT ''
                )
                """
            )
            # Mapping EVENT_UID -> gcal_event_id pour la déduplication AGENDA
            # PRO. `title_key` (titre normalisé, cf. normalize_title) permet
            # une comparaison robuste (accents/casse/espacement ignorés).
            # `gcal_event_id` est nullable : une ligne vide sert de
            # "réservation" posée AVANT l'insert Google Calendar, pour
            # bloquer un lookup concurrent qui créerait un doublon.
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS agenda_pro_events (
                    event_uid TEXT PRIMARY KEY,
                    gcal_event_id TEXT,
                    calendar_id TEXT,
                    title TEXT,
                    title_key TEXT,
                    start_time TEXT,
                    created_at TEXT,
                    updated_at TEXT NOT NULL
                )
                """
            )
            self._conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_agenda_pro_title_key_start
                ON agenda_pro_events (title_key, start_time)
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS agenda_pro_processed_emails (
                    email_id TEXT PRIMARY KEY,
                    processed_at TEXT NOT NULL
                )
                """
            )

    def has_seen(self, agent: str, link: str) -> bool:
        """Utilisé par les agents de veille (ex. /renault) pour ne signaler
        qu'un article jamais rencontré lors d'une exécution précédente."""
        row = self._conn.execute(
            "SELECT 1 FROM seen_links WHERE agent = ? AND link = ?", (agent, link)
        ).fetchone()
        return row is not None

    def mark_seen(self, agent: str, link: str) -> None:
        with self._conn:
            self._conn.execute(
                "INSERT OR IGNORE INTO seen_links (agent, link) VALUES (?, ?)",
                (agent, link),
            )

    # ─────────────────────────────────────────────────────────────
    # Notes de weekends — fallback SQLite (source de vérité = Google
    # Calendar, cf. capucine/google_calendar.py).
    # ─────────────────────────────────────────────────────────────

    def get_all_weekend_notes(self) -> dict:
        rows = self._conn.execute(
            "SELECT sat_date, note FROM weekend_notes WHERE note != ''"
        ).fetchall()
        return {row[0]: row[1] for row in rows}

    def set_weekend_note(self, sat_date: str, note: str) -> None:
        with self._conn:
            self._conn.execute(
                "INSERT INTO weekend_notes (sat_date, note) VALUES (?, ?) "
                "ON CONFLICT(sat_date) DO UPDATE SET note = excluded.note",
                (sat_date, note.strip()),
            )

    # ─────────────────────────────────────────────────────────────
    # Événements [AGENDA PRO] — mapping EVENT_UID -> gcal_event_id.
    # ─────────────────────────────────────────────────────────────

    def get_agenda_pro_event_id(self, event_uid: str) -> "str | None":
        """Retourne le gcal_event_id associé à un EVENT_UID, ou None s'il
        est inconnu. `gcal_event_id` peut être '' pour une réservation en
        cours : on retourne None dans ce cas pour éviter de la traiter
        comme un ID valide."""
        row = self._conn.execute(
            "SELECT gcal_event_id FROM agenda_pro_events WHERE event_uid = ?",
            (event_uid,),
        ).fetchone()
        return (row[0] or None) if row else None

    def reserve_agenda_pro_event(
        self, event_uid: str, calendar_id: str, title: "str | None" = None, start_time: "str | None" = None
    ) -> None:
        """Pose une ligne de réservation AVANT l'insert Google Calendar
        (gcal_event_id vide) — à appeler juste avant
        GoogleCalendarClient.upsert_agenda_pro_event."""
        ts = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")
        key = normalize_title(title)
        with self._conn:
            self._conn.execute(
                """INSERT INTO agenda_pro_events
                       (event_uid, gcal_event_id, calendar_id, title, title_key, start_time, created_at, updated_at)
                   VALUES (?, '', ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(event_uid) DO UPDATE SET
                       calendar_id = excluded.calendar_id,
                       title       = excluded.title,
                       title_key   = excluded.title_key,
                       start_time  = excluded.start_time,
                       updated_at  = excluded.updated_at""",
                (event_uid, calendar_id, title, key, start_time, ts, ts),
            )

    def save_agenda_pro_event_id(
        self, event_uid: str, gcal_event_id: str, calendar_id: str,
        title: "str | None" = None, start_time: "str | None" = None,
    ) -> None:
        """Enregistre le mapping EVENT_UID -> gcal_event_id, à appeler après
        chaque insert/update réussi dans Google Calendar."""
        ts = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")
        key = normalize_title(title)
        with self._conn:
            self._conn.execute(
                """INSERT INTO agenda_pro_events
                       (event_uid, gcal_event_id, calendar_id, title, title_key, start_time, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(event_uid) DO UPDATE SET
                       gcal_event_id = excluded.gcal_event_id,
                       calendar_id   = excluded.calendar_id,
                       title         = excluded.title,
                       title_key     = excluded.title_key,
                       start_time    = excluded.start_time,
                       updated_at    = excluded.updated_at""",
                (event_uid, gcal_event_id, calendar_id, title, key, start_time, ts, ts),
            )

    def delete_agenda_pro_event_id(self, event_uid: str) -> None:
        with self._conn:
            self._conn.execute("DELETE FROM agenda_pro_events WHERE event_uid = ?", (event_uid,))

    def find_agenda_pro_event_by_title_and_start(
        self, title: str, start_time: str
    ) -> "tuple[str, str] | None":
        """
        Recherche un événement AGENDA PRO existant par titre normalisé et
        heure de début (comparaison sur "YYYY-MM-DDTHH:MM", secondes/fuseau
        ignorés). Les lignes de réservation (gcal_event_id vide) sont
        ignorées : elles indiquent un insert en cours, pas un événement
        confirmé. Utilisé pour détecter les doublons quand l'EVENT_UID
        change entre deux emails pour le même meeting.

        Retourne (event_uid, gcal_event_id) si trouvé, sinon None.
        """
        key = normalize_title(title)
        if not key:
            return None
        start_prefix = start_time[:16]
        row = self._conn.execute(
            "SELECT event_uid, gcal_event_id FROM agenda_pro_events "
            "WHERE title_key = ? AND start_time LIKE ? AND gcal_event_id != '' "
            "ORDER BY updated_at DESC LIMIT 1",
            (key, start_prefix + "%"),
        ).fetchone()
        return (row[0], row[1]) if row else None

    def cleanup_duplicate_agenda_pro_entries(self, title: str, start_time: str, keep_uid: str) -> int:
        """Supprime tous les doublons d'un même meeting sauf `keep_uid`.
        Appelé après chaque upsert réussi pour éviter l'accumulation de
        lignes orphelines. Retourne le nombre de lignes supprimées."""
        key = normalize_title(title)
        if not key:
            return 0
        start_prefix = start_time[:16]
        with self._conn:
            cursor = self._conn.execute(
                "DELETE FROM agenda_pro_events "
                "WHERE title_key = ? AND start_time LIKE ? AND event_uid != ?",
                (key, start_prefix + "%", keep_uid),
            )
            return cursor.rowcount

    def is_agenda_pro_email_processed(self, email_id: str) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM agenda_pro_processed_emails WHERE email_id = ?", (email_id,)
        ).fetchone()
        return row is not None

    def mark_agenda_pro_email_processed(self, email_id: str) -> None:
        ts = datetime.utcnow().isoformat()
        with self._conn:
            self._conn.execute(
                "INSERT OR IGNORE INTO agenda_pro_processed_emails (email_id, processed_at) VALUES (?, ?)",
                (email_id, ts),
            )

    def purge_old_calendar_records(self, days: int = 30, agenda_pro_days: int = 90) -> None:
        """Supprime les enregistrements calendrier anciens (notes de
        weekends et emails traités après `days` jours, mapping AGENDA PRO
        après `agenda_pro_days` jours)."""
        cutoff = (datetime.utcnow().replace(microsecond=0) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%S")
        cutoff_ap = (datetime.utcnow().replace(microsecond=0) - timedelta(days=agenda_pro_days)).strftime("%Y-%m-%dT%H:%M:%S")
        with self._conn:
            self._conn.execute("DELETE FROM agenda_pro_events WHERE updated_at < ?", (cutoff_ap,))
            self._conn.execute("DELETE FROM agenda_pro_processed_emails WHERE processed_at < ?", (cutoff,))
            self._conn.execute("DELETE FROM weekend_notes WHERE sat_date < ?", (cutoff[:10],))

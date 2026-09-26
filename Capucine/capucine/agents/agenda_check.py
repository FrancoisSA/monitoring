"""Agent /agenda_check : vérification périodique du calendrier.

Déclenché par cron (jamais par une commande Telegram tapée par
l'utilisateur, comme /renault), toutes les 10 minutes
(cf. scripts/trigger.sh + crontab). Combine ce qui était deux jobs
APScheduler distincts dans prj-jeffrey/services/reminder.py
(_check_calendar_reminders et _check_new_emails) en un seul agent, puisque
Capucine n'a pas de scheduler interne (cf. plan de portage) — et sans le
threading.Lock de Jeffrey, inutile ici car l'exécution est toujours
séquentielle dans la boucle principale de service.py (cf. capucine/store.py).
"""
from __future__ import annotations

import logging
from datetime import datetime

import pytz

from capucine.agenda_pro import AgendaProBlock, detect_cancellation, parse_agenda_pro_blocks, to_local_iso
from capucine.agents.base import AgentResponse
from capucine.deps import Deps
from capucine.google_calendar import GoogleCalendarClient
from capucine.google_gmail import GmailClient

logger = logging.getLogger(__name__)

# Clé "agent" du Store (cf. has_seen/mark_seen) sous laquelle les rappels
# déjà envoyés sont enregistrés — un event_id Google Calendar est unique par
# occurrence (singleEvents=True génère un id distinct par occurrence d'un
# événement récurrent), donc pas besoin de purge dédiée pour cette clé.
_REMINDERS_SEEN_KEY = "agenda_check_reminders"


class AgendaCheckAgent:
    name = "agenda_check"

    def __init__(
        self,
        calendar: GoogleCalendarClient,
        gmail: GmailClient,
        reminder_advance_minutes: int,
        agenda_pro_calendar_name: str,
    ) -> None:
        self.calendar = calendar
        self.gmail = gmail
        self.reminder_advance_minutes = reminder_advance_minutes
        self.agenda_pro_calendar_name = agenda_pro_calendar_name

    def handle(self, args: str, deps: Deps) -> AgentResponse:
        # Purge à chaque tick plutôt qu'une fois par nuit comme Jeffrey :
        # le volume (calendrier personnel) est trop faible pour justifier
        # une logique de planification dédiée (cf. plan de portage).
        deps.store.purge_old_calendar_records()

        lines = self._check_reminders(deps) + self._check_agenda_pro_emails(deps)

        if not lines:
            # Pas de spam toutes les 10 min quand rien de nouveau — même
            # comportement que RenaultAgent.
            return AgentResponse(text="", notify=False)

        message = "📅 *Vérification agenda :*\n\n" + "\n".join(lines)
        return AgentResponse(text=message)

    def _check_reminders(self, deps: Deps) -> "list[str]":
        try:
            events = self.calendar.get_upcoming_events(minutes_ahead=self.reminder_advance_minutes)
        except Exception as e:
            logger.error("[agenda_check] Échec récupération événements imminents : %s", e)
            return []

        tz = pytz.timezone(self.calendar.timezone)
        lines = []
        for event in events:
            event_id = event["id"]
            start_str = event["start"]
            if not start_str or deps.store.has_seen(_REMINDERS_SEEN_KEY, event_id):
                continue

            # Parser la date de début — "Z" non supporté par fromisoformat en Python < 3.11.
            start_dt = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
            start_dt = tz.localize(start_dt) if start_dt.tzinfo is None else start_dt.astimezone(tz)

            deps.store.mark_seen(_REMINDERS_SEEN_KEY, event_id)
            line = f"⏰ *{event['summary']}* à {start_dt.strftime('%H:%M')}"
            if event.get("location"):
                line += f" — {event['location']}"
            lines.append(line)
        return lines

    def _check_agenda_pro_emails(self, deps: Deps) -> "list[str]":
        try:
            emails = self.gmail.search_emails(keyword="is:unread [AGENDA PRO]", max_results=10)
        except Exception as e:
            logger.error("[agenda_check] Échec scan emails AGENDA PRO : %s", e)
            return []

        lines = []
        for email_meta in emails:
            lines.extend(self._process_agenda_pro_email(deps, email_meta["id"]))
        return lines

    def _process_agenda_pro_email(self, deps: Deps, email_id: str) -> "list[str]":
        if deps.store.is_agenda_pro_email_processed(email_id):
            self._mark_read_quietly(email_id)
            return []

        try:
            full_email = self.gmail.get_email(email_id)
        except Exception as e:
            logger.error("[agenda_check] Échec lecture email %s : %s", email_id, e)
            return []

        blocks = parse_agenda_pro_blocks(full_email.get("body_text", ""))
        if not blocks:
            logger.warning("[agenda_check] Email %s [AGENDA PRO] : aucun bloc EVENT_UID trouvé.", email_id)
            deps.store.mark_agenda_pro_email_processed(email_id)
            self._mark_read_quietly(email_id)
            return []

        lines = []
        try:
            for block in blocks:
                lines.extend(self._process_agenda_pro_block(deps, block))
        finally:
            # Toujours marquer l'email comme traité, même en cas d'exception
            # partielle : le dédup par email_id empêche tout retraitement futur.
            deps.store.mark_agenda_pro_email_processed(email_id)
            self._mark_read_quietly(email_id)
        return lines

    def _mark_read_quietly(self, email_id: str) -> None:
        try:
            self.gmail.mark_as_read(email_id)
        except Exception as e:
            logger.warning("[agenda_check] Échec marquage lu email %s : %s", email_id, e)

    def _process_agenda_pro_block(self, deps: Deps, block: AgendaProBlock) -> "list[str]":
        clean_subject = detect_cancellation(block.subject)
        if clean_subject is not None:
            return self._process_cancellation(deps, block, clean_subject)

        try:
            start_local = to_local_iso(block.raw_start, self.calendar.timezone)
            end_local = to_local_iso(block.raw_end, self.calendar.timezone)
        except Exception as e:
            logger.warning("[agenda_check] EVENT_UID=%s : datetime invalide : %s", block.event_uid, e)
            return []

        # 1) Lookup par EVENT_UID exact, puis fallback titre normalisé + date
        #    (rattrape les UID régénérés par le système AGENDA PRO).
        existing_id = deps.store.get_agenda_pro_event_id(block.event_uid)
        reused_uid = None
        if not existing_id:
            match = deps.store.find_agenda_pro_event_by_title_and_start(block.subject, start_local)
            if match:
                reused_uid, existing_id = match

        # 2) Réserver AVANT l'insert Google Calendar.
        if not existing_id:
            deps.store.reserve_agenda_pro_event(
                block.event_uid, self.agenda_pro_calendar_name, title=block.subject, start_time=start_local
            )

        # 3) Insert/update Google Calendar.
        try:
            event, created = self.calendar.upsert_agenda_pro_event(
                event_uid=block.event_uid,
                summary=block.subject,
                start=start_local,
                end=end_local,
                description="[AGENDA PRO] géré automatiquement par Capucine.\n\n" + block.raw,
                location=block.location,
                calendar_name=self.agenda_pro_calendar_name,
                existing_event_id=existing_id,
            )
        except Exception as e:
            # Rollback : supprimer la réservation pour qu'un prochain cycle
            # puisse réessayer proprement.
            if not existing_id:
                deps.store.delete_agenda_pro_event_id(block.event_uid)
            logger.error("[agenda_check] Échec upsert AGENDA PRO (EVENT_UID=%s) : %s", block.event_uid, e)
            return []

        if reused_uid:
            deps.store.delete_agenda_pro_event_id(reused_uid)

        deps.store.save_agenda_pro_event_id(
            block.event_uid, event["id"], self.agenda_pro_calendar_name, title=block.subject, start_time=start_local
        )
        deps.store.cleanup_duplicate_agenda_pro_entries(block.subject, start_local, keep_uid=block.event_uid)

        dt = datetime.fromisoformat(start_local)
        action = "ajoutée" if created else "mise à jour"
        return [f"{'🆕' if created else '🔄'} *{block.subject}* — {dt.strftime('%d/%m à %H:%M')} ({action})"]

    def _process_cancellation(self, deps: Deps, block: AgendaProBlock, clean_subject: str) -> "list[str]":
        """Événement refusé : le supprimer du calendrier s'il y est déjà."""
        existing_id = deps.store.get_agenda_pro_event_id(block.event_uid)
        try:
            cal_id = self.calendar.get_calendar_id(self.agenda_pro_calendar_name)
            if existing_id:
                self.calendar.delete_event(existing_id, calendar_id=cal_id)
                deps.store.delete_agenda_pro_event_id(block.event_uid)
            else:
                # Fallback : EVENT_UID absent du Store, recherche par titre.
                matches = self.calendar.find_events_by_title(clean_subject, calendar_name=self.agenda_pro_calendar_name)
                if not matches:
                    return []
                for match in matches:
                    self.calendar.delete_event(match["id"], calendar_id=cal_id)
        except Exception as e:
            logger.warning("[agenda_check] Annulé, échec suppression (EVENT_UID=%s) : %s", block.event_uid, e)
            return []
        return [f"🚫 *{clean_subject}* — retiré du calendrier (refusé)"]

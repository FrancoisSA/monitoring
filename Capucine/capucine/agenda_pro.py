"""Parsing des emails [AGENDA PRO] — logique pure, sans appel réseau.

Un email [AGENDA PRO] peut contenir plusieurs événements, chacun délimité
par un champ EVENT_UID:. Ce module extrait cette logique (auparavant inline
dans prj-jeffrey/services/reminder.py::_check_new_emails) en fonctions pures
testables sans réseau ni credentials — c'est le seam de test principal pour
cette partie (cf. plan de portage).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

import pytz

_CANCEL_KEYWORDS = ("declined:", "annulé:", "annule:", "cancelled:", "canceled:")


@dataclass(frozen=True)
class AgendaProBlock:
    event_uid: str
    subject: str
    raw_start: str
    raw_end: str
    location: str
    raw: str


def parse_agenda_pro_blocks(body: str) -> "list[AgendaProBlock]":
    """
    Découpe le corps d'un email [AGENDA PRO] en blocs, un par événement.

    Chaque bloc commence à un EVENT_UID: et doit contenir EVENT_UID,
    SUBJECT, STARTTIME et ENDTIME pour être retenu ; un bloc auquel il
    manque un de ces champs est ignoré (email malformé ou tronqué).
    """
    raw_blocs = re.split(r"(?=EVENT_UID:)", body, flags=re.IGNORECASE)
    raw_blocs = [b.strip() for b in raw_blocs if re.search(r"EVENT_UID:", b, re.IGNORECASE)]

    blocks = []
    for bloc in raw_blocs:
        uid_match = re.search(r"EVENT_UID:(.*)", bloc, re.IGNORECASE)
        subject_match = re.search(r"SUBJECT:(.*)", bloc, re.IGNORECASE)
        start_match = re.search(r"STARTTIME:(.*)", bloc, re.IGNORECASE)
        end_match = re.search(r"ENDTIME:(.*)", bloc, re.IGNORECASE)

        if not (uid_match and subject_match and start_match and end_match):
            continue

        location_match = re.search(r"Join: (https://[^\s]+)", bloc)

        blocks.append(AgendaProBlock(
            event_uid=uid_match.group(1).strip(),
            subject=subject_match.group(1).strip(),
            raw_start=start_match.group(1).strip(),
            raw_end=end_match.group(1).strip(),
            location=location_match.group(1).strip() if location_match else "",
            raw=bloc,
        ))
    return blocks


def detect_cancellation(subject: str) -> "str | None":
    """
    Retourne le titre nettoyé (sans préfixe) si `subject` indique une
    annulation ("Declined: titre", "[AMPERE] Annulé: titre", etc.), sinon
    None.
    """
    subject_lower = subject.lower()
    matched_prefix = next((p for p in _CANCEL_KEYWORDS if p in subject_lower), None)
    if not matched_prefix:
        return None
    idx = subject_lower.index(matched_prefix) + len(matched_prefix)
    return subject[idx:].strip()


def to_local_iso(dt_string: str, timezone: str) -> str:
    """
    Localise un datetime AGENDA PRO dans le fuseau `timezone`.

    Les dates naïves (sans suffixe timezone) viennent du système AGENDA PRO
    en UTC — on les traite donc comme UTC avant conversion. Les dates avec
    suffixe Z ou +HH:MM sont converties normalement.

    À ne pas confondre avec capucine/google_calendar.py::_localize, qui
    traite un naïf comme heure LOCALE : deux fonctions distinctes pour deux
    sources aux conventions différentes (emails AGENDA PRO en UTC ici, texte
    LLM en heure locale là-bas) — pas une incohérence. Cf.
    tests/test_calendar_timezones.py pour la matrice de tests verrouillant
    les deux comportements.
    """
    dt = datetime.fromisoformat(dt_string.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = pytz.utc.localize(dt)
    return dt.astimezone(pytz.timezone(timezone)).isoformat()

"""Vérifie les conventions de fuseau horaire du calendrier — équivalent de
prj-jeffrey/test_timezone.py, converti en tests pytest déterministes (dates
fixes été/hiver plutôt que "aujourd'hui", pour ne pas dépendre du jour où
la suite tourne).

Couvre :
  1. GoogleCalendarClient._localize() : datetime naïf -> heure locale inchangée
  2. agenda_pro.to_local_iso() : datetime naïf AGENDA PRO traité comme UTC
"""
from datetime import datetime

from capucine.agenda_pro import to_local_iso
from capucine.google_calendar import GoogleCalendarClient

_CAL = GoogleCalendarClient(credentials_file="unused", token_file="unused", timezone="Europe/Paris")

# 10 juin = été (CEST, Paris = UTC+2) ; 10 janvier = hiver (CET, Paris = UTC+1)
_SUMMER_NAIVE = "2025-06-10T14:00:00"
_WINTER_NAIVE = "2025-01-10T14:00:00"


def test_localize_naive_datetime_keeps_its_hour_in_summer():
    dt = datetime.fromisoformat(_CAL._localize(_SUMMER_NAIVE))
    assert dt.hour == 14
    assert dt.utcoffset().total_seconds() / 3600 == 2.0


def test_localize_naive_datetime_keeps_its_hour_in_winter():
    dt = datetime.fromisoformat(_CAL._localize(_WINTER_NAIVE))
    assert dt.hour == 14
    assert dt.utcoffset().total_seconds() / 3600 == 1.0


def test_localize_already_aware_datetime_is_untouched():
    dt = datetime.fromisoformat(_CAL._localize("2025-06-10T14:00:00+05:00"))
    assert dt.hour == 14
    assert dt.utcoffset().total_seconds() / 3600 == 5.0


def test_to_local_iso_treats_naive_datetime_as_utc_in_summer():
    # 12:00 UTC naïf (comportement AGENDA PRO) -> 14:00 Paris en été (UTC+2)
    dt = datetime.fromisoformat(to_local_iso("2025-06-10T12:00:00", "Europe/Paris"))
    assert dt.hour == 14


def test_to_local_iso_treats_naive_datetime_as_utc_in_winter():
    # 12:00 UTC naïf -> 13:00 Paris en hiver (UTC+1)
    dt = datetime.fromisoformat(to_local_iso("2025-01-10T12:00:00", "Europe/Paris"))
    assert dt.hour == 13


def test_to_local_iso_with_z_suffix_matches_naive_utc():
    naive = datetime.fromisoformat(to_local_iso("2025-06-10T12:00:00", "Europe/Paris"))
    with_z = datetime.fromisoformat(to_local_iso("2025-06-10T12:00:00Z", "Europe/Paris"))
    assert naive == with_z


def test_to_local_iso_with_explicit_utc_offset_matches_naive_utc():
    naive = datetime.fromisoformat(to_local_iso("2025-06-10T12:00:00", "Europe/Paris"))
    with_offset = datetime.fromisoformat(to_local_iso("2025-06-10T12:00:00+00:00", "Europe/Paris"))
    assert naive == with_offset


def test_to_local_iso_with_non_utc_offset_converts_correctly():
    # 12:00+05:00 == 07:00 UTC -> 09:00 Paris en été (UTC+2)
    dt = datetime.fromisoformat(to_local_iso("2025-06-10T12:00:00+05:00", "Europe/Paris"))
    assert dt.hour == 9
